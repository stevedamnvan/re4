#!/usr/bin/env python3
"""Convert an RE4 GameCube TPL plus MTL bindings to a Dreamcast texture pack.

The input and output contain private game assets. This tracked tool only
contains format conversion code and emits RGB565 or one-bit ARGB1555 pixels in
linear row order. The runtime twiddles those pixels while uploading to PVR RAM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
import zlib
from dataclasses import dataclass


TPL_MAGIC = 0x0020AF30
GX_TF_I4 = 0
GX_TF_IA8 = 3
GX_TF_CMPR = 14

MAGIC = b"RE4DCTX\0"
VERSION = 1
FORMAT_RGB565 = 0
FORMAT_ARGB1555 = 1
FLAG_ALPHA = 1
HEADER = struct.Struct("<8s10I")
TEXTURE = struct.Struct("<64s6I")
IMAGE_NUMBER = re.compile(r"-(\d+)\.png$", re.IGNORECASE)


@dataclass(frozen=True)
class TplImage:
    width: int
    height: int
    format: int
    data: bytes


@dataclass(frozen=True)
class MaterialBinding:
    name: str
    color_image: int
    alpha_image: int | None


def _u32be(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"read outside TPL at 0x{offset:x}")
    return struct.unpack_from(">I", data, offset)[0]


def _expected_image_size(width: int, height: int, image_format: int) -> int:
    if image_format in (GX_TF_I4, GX_TF_CMPR):
        return ((width + 7) // 8) * ((height + 7) // 8) * 32
    if image_format == GX_TF_IA8:
        return ((width + 3) // 4) * ((height + 3) // 4) * 32
    raise ValueError(f"unsupported TPL image format 0x{image_format:x}")


def parse_tpl(data: bytes) -> list[TplImage]:
    if len(data) < 12:
        raise ValueError("TPL is smaller than its header")
    magic, image_count, descriptor_offset = struct.unpack_from(">III", data)
    if magic != TPL_MAGIC:
        raise ValueError(f"unexpected TPL magic 0x{magic:08x}")
    if image_count == 0 or descriptor_offset + image_count * 8 > len(data):
        raise ValueError("TPL descriptor table is outside the file")

    images: list[TplImage] = []
    for image_index in range(image_count):
        texture_header = _u32be(data, descriptor_offset + image_index * 8)
        if texture_header == 0 or texture_header + 12 > len(data):
            raise ValueError(f"image {image_index} has an invalid texture header")
        height, width, image_format, data_offset = struct.unpack_from(
            ">HHII", data, texture_header
        )
        if width == 0 or height == 0:
            raise ValueError(f"image {image_index} has zero dimensions")
        size = _expected_image_size(width, height, image_format)
        if data_offset + size > len(data):
            raise ValueError(f"image {image_index} data is outside the file")
        images.append(TplImage(width, height, image_format, data[data_offset:data_offset + size]))
    return images


def _expand_565(value: int) -> tuple[int, int, int]:
    red = (value >> 11) & 31
    green = (value >> 5) & 63
    blue = value & 31
    return (
        (red << 3) | (red >> 2),
        (green << 2) | (green >> 4),
        (blue << 3) | (blue >> 2),
    )


def _mix(first: tuple[int, int, int], second: tuple[int, int, int],
         first_weight: int, denominator: int) -> tuple[int, int, int]:
    second_weight = denominator - first_weight
    return tuple(
        (first[channel] * first_weight + second[channel] * second_weight) // denominator
        for channel in range(3)
    )


def decode_cmpr(image: TplImage) -> list[tuple[int, int, int, int]]:
    pixels = [(0, 0, 0, 0)] * (image.width * image.height)
    source = memoryview(image.data)
    offset = 0
    for tile_y in range(0, image.height, 8):
        for tile_x in range(0, image.width, 8):
            for sub_y in (0, 4):
                for sub_x in (0, 4):
                    color0, color1 = struct.unpack_from(">HH", source, offset)
                    selectors = source[offset + 4:offset + 8]
                    offset += 8
                    rgb0 = _expand_565(color0)
                    rgb1 = _expand_565(color1)
                    if color0 > color1:
                        palette = (
                            (*rgb0, 255),
                            (*rgb1, 255),
                            (*_mix(rgb0, rgb1, 2, 3), 255),
                            (*_mix(rgb0, rgb1, 1, 3), 255),
                        )
                    else:
                        palette = (
                            (*rgb0, 255),
                            (*rgb1, 255),
                            (*_mix(rgb0, rgb1, 1, 2), 255),
                            (0, 0, 0, 0),
                        )
                    for row in range(4):
                        bits = selectors[row]
                        y = tile_y + sub_y + row
                        if y >= image.height:
                            continue
                        for column in range(4):
                            x = tile_x + sub_x + column
                            if x < image.width:
                                selector = (bits >> (6 - column * 2)) & 3
                                pixels[y * image.width + x] = palette[selector]
    return pixels


def decode_i4(image: TplImage) -> list[tuple[int, int, int, int]]:
    pixels = [(0, 0, 0, 255)] * (image.width * image.height)
    offset = 0
    for tile_y in range(0, image.height, 8):
        for tile_x in range(0, image.width, 8):
            for row in range(8):
                y = tile_y + row
                for pair in range(4):
                    value = image.data[offset]
                    offset += 1
                    for within, nibble in enumerate((value >> 4, value & 15)):
                        x = tile_x + pair * 2 + within
                        if x < image.width and y < image.height:
                            intensity = nibble * 17
                            pixels[y * image.width + x] = (
                                intensity, intensity, intensity, 255
                            )
    return pixels


def decode_ia8(image: TplImage) -> list[tuple[int, int, int, int]]:
    pixels = [(0, 0, 0, 0)] * (image.width * image.height)
    offset = 0
    for tile_y in range(0, image.height, 4):
        for tile_x in range(0, image.width, 4):
            for row in range(4):
                y = tile_y + row
                for column in range(4):
                    alpha = image.data[offset]
                    intensity = image.data[offset + 1]
                    offset += 2
                    x = tile_x + column
                    if x < image.width and y < image.height:
                        pixels[y * image.width + x] = (
                            intensity, intensity, intensity, alpha
                        )
    return pixels


def decode_image(image: TplImage) -> list[tuple[int, int, int, int]]:
    if image.format == GX_TF_CMPR:
        return decode_cmpr(image)
    if image.format == GX_TF_I4:
        return decode_i4(image)
    if image.format == GX_TF_IA8:
        return decode_ia8(image)
    raise ValueError(f"unsupported TPL image format 0x{image.format:x}")


def _image_number(value: str, line_no: int) -> int:
    match = IMAGE_NUMBER.search(value.replace("\\", "/"))
    if match is None:
        raise ValueError(f"MTL line {line_no}: cannot identify image in {value!r}")
    return int(match.group(1))


def parse_mtl(text: str) -> list[MaterialBinding]:
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        fields = raw_line.strip().split()
        if not fields or fields[0].startswith("#"):
            continue
        if fields[0] == "newmtl":
            if len(fields) < 2:
                raise ValueError(f"MTL line {line_no}: material needs a name")
            current = {"name": " ".join(fields[1:]), "color": None, "alpha": None}
            records.append(current)
        elif fields[0] in {"map_Kd", "map_d"}:
            if current is None or len(fields) < 2:
                raise ValueError(f"MTL line {line_no}: map precedes material")
            key = "color" if fields[0] == "map_Kd" else "alpha"
            current[key] = _image_number(fields[-1], line_no)

    bindings: list[MaterialBinding] = []
    names: set[str] = set()
    for record in records:
        name = str(record["name"])
        if name in names:
            raise ValueError(f"duplicate material {name!r}")
        names.add(name)
        if record["color"] is None:
            raise ValueError(f"material {name!r} has no map_Kd")
        bindings.append(MaterialBinding(name, int(record["color"]), record["alpha"]))
    if not bindings:
        raise ValueError("MTL has no textured materials")
    return bindings


def _name_bytes(name: str) -> bytes:
    encoded = name.encode("utf-8")
    if len(encoded) >= 64:
        raise ValueError(f"material name is too long: {name!r}")
    return encoded.ljust(64, b"\0")


def _pack_565(pixel: tuple[int, int, int, int]) -> int:
    red, green, blue, _ = pixel
    return ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3)


def _pack_1555(pixel: tuple[int, int, int, int]) -> int:
    red, green, blue, alpha = pixel
    return ((1 if alpha >= 128 else 0) << 15) | ((red >> 3) << 10) | ((green >> 3) << 5) | (blue >> 3)


def build_package(images: list[TplImage], bindings: list[MaterialBinding]) -> tuple[bytes, dict[str, object]]:
    decoded: dict[int, list[tuple[int, int, int, int]]] = {}
    packed: dict[tuple[int, int | None], tuple[int, int, int, int, int, int]] = {}

    def get_image(index: int) -> tuple[TplImage, list[tuple[int, int, int, int]]]:
        if index < 0 or index >= len(images):
            raise ValueError(f"MTL references missing TPL image {index}")
        if index not in decoded:
            decoded[index] = decode_image(images[index])
        return images[index], decoded[index]

    texture_offset = HEADER.size
    data_offset = texture_offset + len(bindings) * TEXTURE.size
    texture_blob = bytearray()
    data_blob = bytearray()
    manifest_materials: list[dict[str, object]] = []

    for binding in bindings:
        key = (binding.color_image, binding.alpha_image)
        if key not in packed:
            source, pixels = get_image(binding.color_image)
            pixels = list(pixels)
            has_alpha = any(pixel[3] < 128 for pixel in pixels)
            if binding.alpha_image is not None:
                alpha_source, alpha_pixels = get_image(binding.alpha_image)
                if (alpha_source.width, alpha_source.height) != (source.width, source.height):
                    raise ValueError(f"material {binding.name!r} alpha dimensions differ")
                pixels = [
                    (color[0], color[1], color[2], alpha[0])
                    for color, alpha in zip(pixels, alpha_pixels)
                ]
                has_alpha = True
            image_format = FORMAT_ARGB1555 if has_alpha else FORMAT_RGB565
            pack_pixel = _pack_1555 if has_alpha else _pack_565
            raw = b"".join(struct.pack("<H", pack_pixel(pixel)) for pixel in pixels)
            relative_offset = len(data_blob)
            data_blob.extend(raw)
            flags = FLAG_ALPHA if has_alpha else 0
            packed[key] = (
                relative_offset, len(raw), image_format, flags,
                source.width, source.height,
            )
        relative_offset, raw_size, image_format, flags, width, height = packed[key]
        texture_blob.extend(
            TEXTURE.pack(
                _name_bytes(binding.name), width, height,
                image_format, data_offset + relative_offset, raw_size, flags
            )
        )
        manifest_materials.append({
            "name": binding.name,
            "color_image": binding.color_image,
            "alpha_image": binding.alpha_image,
            "width": width,
            "height": height,
            "format": "argb1555" if flags & FLAG_ALPHA else "rgb565",
            "bytes": raw_size,
        })

    payload = bytes(texture_blob + data_blob)
    payload_crc32 = zlib.crc32(payload) & 0xFFFFFFFF
    header = HEADER.pack(
        MAGIC, VERSION, HEADER.size, TEXTURE.size, len(bindings), texture_offset,
        data_offset, len(data_blob), payload_crc32, len(images), 0
    )
    metadata = {
        "format": "re4dc-textures",
        "version": VERSION,
        "tpl_images": len(images),
        "materials": manifest_materials,
        "texture_bytes": len(data_blob),
        "payload_crc32": f"{payload_crc32:08x}",
    }
    return header + payload, metadata


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tpl", type=pathlib.Path, help="private GameCube TPL")
    parser.add_argument("mtl", type=pathlib.Path, help="private exported MTL")
    parser.add_argument("output", type=pathlib.Path, help="private Dreamcast texture pack")
    parser.add_argument("--manifest", type=pathlib.Path, help="JSON manifest path")
    args = parser.parse_args(argv)

    tpl_data = args.tpl.read_bytes()
    mtl_data = args.mtl.read_bytes()
    images = parse_tpl(tpl_data)
    bindings = parse_mtl(mtl_data.decode("utf-8-sig"))
    package, metadata = build_package(images, bindings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(package)
    metadata.update({
        "tpl_source": args.tpl.name,
        "tpl_sha256": sha256_bytes(tpl_data),
        "mtl_source": args.mtl.name,
        "mtl_sha256": sha256_bytes(mtl_data),
        "package": args.output.name,
        "package_bytes": len(package),
        "package_sha256": sha256_bytes(package),
    })
    manifest_path = args.manifest or args.output.with_suffix(args.output.suffix + ".json")
    manifest_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"texture conversion failed: {error}", file=sys.stderr)
        raise SystemExit(1)
