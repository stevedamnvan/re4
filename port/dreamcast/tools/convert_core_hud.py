#!/usr/bin/env python3
"""Convert the original RE4 core.das cockpit data for the Dreamcast runtime.

The input and both outputs contain private game data and stay outside source
control.  The tracked converter preserves the GameCube HUD's 640x480
coordinates, hierarchy, colours, texture frames, and masked sprites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
import zlib
from dataclasses import dataclass

import convert_tpl as tpl


HUD_MAGIC = b"RE4DCHD\0"
HUD_VERSION = 1
HUD_HEADER = struct.Struct("<8s12I")
HUD_UNIT = struct.Struct("<12BII10f8B")

TABLE_FRAME = 0
TABLE_LIFE = 1
TABLE_BULLET = 2
NO_TEXTURE = 0xFFFFFFFF

DEFAULT_ARC_OFFSET = 0x400
DEFAULT_TEXTURE_OFFSET = 0x1A0BE0
DEFAULT_LIFE_OFFSET = 0x21B240
DEFAULT_FRAME_OFFSET = 0x223300
DEFAULT_BULLET_OFFSET = 0x22F760


@dataclass(frozen=True)
class SourceUnit:
    table: int
    flags: int
    mark: int
    number: int
    level: int
    parent: int
    kind: int
    tex_id: int
    vtx_type: int
    blend_type: int
    trans_type: int
    tex_flags: int
    mask_id: int
    pos: tuple[float, float, float]
    size: tuple[float, float]
    rot: tuple[float, float, float]
    col0: bytes
    col1: bytes


@dataclass(frozen=True)
class TextureVariant:
    tex_id: int
    mask_id: int | None
    frames: tuple[tpl.TplImage, ...]
    content_width: int
    content_height: int


def u32be(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"read outside core.das at 0x{offset:x}")
    return struct.unpack_from(">I", data, offset)[0]


def parse_id_table(data: bytes, offset: int, table: int) -> list[SourceUnit]:
    if data[offset:offset + 5] != b"2.00\0":
        raise ValueError(f"HUD table at 0x{offset:x} is not version 2.00")
    count = data[offset + 5]
    end = offset + 8 + count * 0x8C
    if end > len(data):
        raise ValueError(f"HUD table at 0x{offset:x} is truncated")
    units = []
    for index in range(count):
        base = offset + 8 + index * 0x8C
        (flags, mark, number, level, parent, _, kind, _, tex_id, vtx_type,
         _, _, _, _) = struct.unpack_from(">3x14B", data, base)
        units.append(SourceUnit(
            table=table,
            flags=flags,
            mark=mark,
            number=number,
            level=level,
            parent=parent,
            kind=kind,
            tex_id=tex_id,
            vtx_type=vtx_type,
            blend_type=data[base + 0x6C],
            trans_type=data[base + 0x6D],
            tex_flags=data[base + 0x6F],
            mask_id=data[base + 0x6E],
            pos=struct.unpack_from(">3f", data, base + 0x14),
            size=struct.unpack_from(">2f", data, base + 0x50),
            rot=struct.unpack_from(">3f", data, base + 0x60),
            col0=data[base + 0x58:base + 0x5C],
            col1=data[base + 0x5C:base + 0x60],
        ))
    return units


def parse_hud_textures(
    data: bytes, offset: int
) -> tuple[dict[int, tuple[tpl.TplImage, ...]], dict[str, object]]:
    if u32be(data, offset) != 0xB:
        raise ValueError("cockpit texture block is not version 0xB")
    id_offset = u32be(data, offset + 4)
    tpl_offset = u32be(data, offset + 0x18)
    animation_offset = u32be(data, offset + 0x1C)
    count = u32be(data, offset + id_offset)
    if count == 0 or count != u32be(data, offset + tpl_offset):
        raise ValueError("cockpit texture tables disagree")
    ids = [
        struct.unpack_from(">H", data, offset + id_offset + 4 + index * 8)[0]
        for index in range(count)
    ]
    relative_offsets = [
        u32be(data, offset + tpl_offset + 4 + index * 4)
        for index in range(count)
    ]
    starts = [offset + tpl_offset + value for value in relative_offsets]
    textures: dict[int, tuple[tpl.TplImage, ...]] = {}
    for index, tex_id in enumerate(ids):
        end = starts[index + 1] if index + 1 < count else offset + animation_offset
        if tex_id in textures:
            raise ValueError(f"duplicate cockpit texture id 0x{tex_id:02x}")
        textures[tex_id] = tuple(tpl.parse_tpl(data[starts[index]:end]))
    return textures, {
        "version": 0xB,
        "texture_ids": count,
        "texture_offset": offset,
    }


def _next_power_of_two(value: int) -> int:
    result = 8
    while result < value:
        result *= 2
    if result > 1024:
        raise ValueError(f"HUD texture dimension {value} exceeds PVR limits")
    return result


def _resample(
    pixels: list[tuple[int, int, int, int]], width: int, height: int,
    target_width: int, target_height: int,
) -> list[tuple[int, int, int, int]]:
    return [
        pixels[min(height - 1, y * height // target_height) * width +
               min(width - 1, x * width // target_width)]
        for y in range(target_height)
        for x in range(target_width)
    ]


def _composite_frames(
    color_frames: tuple[tpl.TplImage, ...],
    mask_frames: tuple[tpl.TplImage, ...] | None,
) -> tuple[list[list[tuple[int, int, int, int]]], int, int]:
    width = max(image.width for image in color_frames)
    height = max(image.height for image in color_frames)
    if mask_frames:
        width = max(width, max(image.width for image in mask_frames))
        height = max(height, max(image.height for image in mask_frames))
    frames = []
    for index, color_image in enumerate(color_frames):
        color = tpl.decode_image(color_image)
        if (color_image.width, color_image.height) != (width, height):
            color = _resample(
                color, color_image.width, color_image.height, width, height
            )
        if mask_frames:
            mask_image = mask_frames[index % len(mask_frames)]
            mask = tpl.decode_image(mask_image)
            if (mask_image.width, mask_image.height) != (width, height):
                mask = _resample(
                    mask, mask_image.width, mask_image.height, width, height
                )
            color = [
                (pixel[0], pixel[1], pixel[2],
                 pixel[3] * mask_pixel[3] // 255)
                for pixel, mask_pixel in zip(color, mask)
            ]
        frames.append(color)
    return frames, width, height


def unit_uses_r100_slice_texture(
    unit: SourceUnit, units: list[SourceUnit]
) -> bool:
    if unit.kind == 1 or unit.tex_id == 0xFF:
        return False
    if unit.table == TABLE_FRAME:
        return True
    if unit.table == TABLE_BULLET:
        return unit.mark == 0x31
    # The 30-second r100 slice has Leon alone with the starting handgun.
    # Preserve layout/group records, but do not embed Ashley, alternate-player,
    # empty-inventory, or off-screen colour-template rasters.
    if unit.parent == 0xFF and unit.pos[1] <= -240.0:
        return False
    if unit.mark in {0x02, 0x04, 0x05, 0x09, 0x17, 0x18, 0x19,
                     0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x3F, 0x41, 0x42}:
        return False
    if unit.col0[3] == 0:
        return False
    by_number = {
        candidate.number: candidate
        for candidate in units
        if candidate.table == TABLE_LIFE
    }
    parent = unit.parent
    while parent != 0xFF:
        ancestor = by_number.get(parent)
        if ancestor is None:
            break
        if ancestor.mark in {1, 3}:
            return False
        parent = ancestor.parent
    return True


def build_packages(
    core_data: bytes, texture_offset: int, tables: list[tuple[int, int]],
    twiddle: bool = False,
) -> tuple[bytes, bytes, dict[str, object]]:
    textures, source_metadata = parse_hud_textures(core_data, texture_offset)
    units = [
        unit
        for table, offset in tables
        for unit in parse_id_table(core_data, offset, table)
    ]
    variants: dict[tuple[int, int | None], TextureVariant] = {}
    for unit in units:
        if not unit_uses_r100_slice_texture(unit, units):
            continue
        if unit.tex_id not in textures:
            raise ValueError(f"HUD unit references missing texture 0x{unit.tex_id:02x}")
        mask_id = unit.mask_id if unit.tex_flags & 1 else None
        if mask_id is not None and mask_id not in textures:
            raise ValueError(f"HUD unit references missing mask 0x{mask_id:02x}")
        key = (unit.tex_id, mask_id)
        if key not in variants:
            color_frames = textures[unit.tex_id]
            mask_frames = textures[mask_id] if mask_id is not None else None
            _, width, height = _composite_frames(color_frames, mask_frames)
            variants[key] = TextureVariant(
                unit.tex_id, mask_id, color_frames, width, height
            )

    descriptor_blob = bytearray()
    image_blob = bytearray()
    variant_runtime: dict[tuple[int, int | None], tuple[int, int, float, float]] = {}
    texture_metadata = []
    packed_payloads: dict[tuple[bytes, int, int, int], tuple[int, int]] = {}
    descriptor_count = sum(len(variant.frames) for variant in variants.values())
    image_data_offset = tpl.HEADER.size + descriptor_count * tpl.TEXTURE.size
    descriptor_index = 0
    for key, variant in variants.items():
        mask_frames = textures[variant.mask_id] if variant.mask_id is not None else None
        frames, content_width, content_height = _composite_frames(
            variant.frames, mask_frames
        )
        padded_width = _next_power_of_two(content_width)
        padded_height = _next_power_of_two(content_height)
        first_descriptor = descriptor_index
        for frame_index, pixels in enumerate(frames):
            padded = [(0, 0, 0, 0)] * (padded_width * padded_height)
            for y in range(content_height):
                start = y * padded_width
                source = y * content_width
                padded[start:start + content_width] = pixels[source:source + content_width]
            has_alpha = any(pixel[3] < 255 for pixel in padded)
            image_format = tpl.FORMAT_ARGB4444 if has_alpha else tpl.FORMAT_RGB565
            pack_pixel = tpl._pack_4444 if has_alpha else tpl._pack_565
            texels = [pack_pixel(pixel) for pixel in padded]
            if twiddle:
                texels = tpl.twiddle_16bpp(texels, padded_width, padded_height)
            raw = b"".join(struct.pack("<H", texel) for texel in texels)
            payload_key = (raw, padded_width, padded_height, image_format)
            if payload_key not in packed_payloads:
                packed_payloads[payload_key] = (len(image_blob), len(raw))
                image_blob.extend(raw)
            relative_offset, raw_size = packed_payloads[payload_key]
            name = f"HUD_{variant.tex_id:02X}_{frame_index:02X}"
            if variant.mask_id is not None:
                name += f"_M{variant.mask_id:02X}"
            descriptor_blob.extend(tpl.TEXTURE.pack(
                tpl._name_bytes(name), padded_width, padded_height, image_format,
                image_data_offset + relative_offset, raw_size,
                tpl.FLAG_ALPHA if has_alpha else 0,
                tpl.PAYLOAD_TWIDDLED if twiddle else tpl.PAYLOAD_LINEAR, 0,
            ))
            texture_metadata.append({
                "name": name,
                "source_width": content_width,
                "source_height": content_height,
                "width": padded_width,
                "height": padded_height,
                "format": "argb4444" if has_alpha else "rgb565",
                "payload": "twiddled" if twiddle else "linear",
            })
            descriptor_index += 1
        variant_runtime[key] = (
            first_descriptor,
            len(frames),
            content_width / padded_width,
            content_height / padded_height,
        )

    texture_payload = bytes(descriptor_blob + image_blob)
    texture_crc = zlib.crc32(texture_payload) & 0xFFFFFFFF
    texture_package = tpl.HEADER.pack(
        tpl.MAGIC, tpl.VERSION, tpl.HEADER.size, tpl.TEXTURE.size,
        descriptor_count, tpl.HEADER.size, image_data_offset, len(image_blob),
        texture_crc, descriptor_count, 0,
    ) + texture_payload

    packed_units = bytearray()
    table_ranges: dict[int, tuple[int, int]] = {}
    for table, _ in tables:
        indices = [index for index, unit in enumerate(units) if unit.table == table]
        table_ranges[table] = (
            indices[0] if indices else 0,
            len(indices),
        )
    unit_metadata = []
    for unit in units:
        if not unit_uses_r100_slice_texture(unit, units):
            first_texture, texture_count, u1, v1 = NO_TEXTURE, 0, 1.0, 1.0
        else:
            mask_id = unit.mask_id if unit.tex_flags & 1 else None
            first_texture, texture_count, u1, v1 = variant_runtime[
                (unit.tex_id, mask_id)
            ]
        packed_units.extend(HUD_UNIT.pack(
            unit.table, unit.flags, unit.mark, unit.number, unit.level,
            unit.parent, unit.kind, unit.vtx_type, unit.blend_type,
            unit.trans_type, unit.tex_flags, 0,
            first_texture, texture_count,
            *unit.pos, *unit.size, *unit.rot, u1, v1,
            *unit.col0, *unit.col1,
        ))
        unit_metadata.append({
            "table": unit.table,
            "mark": unit.mark,
            "number": unit.number,
            "parent": unit.parent,
            "texture": unit.tex_id,
            "mask": unit.mask_id if unit.tex_flags & 1 else None,
            "texture_first": first_texture,
            "texture_count": texture_count,
        })
    layout_crc = zlib.crc32(packed_units) & 0xFFFFFFFF
    frame_start, frame_count = table_ranges[TABLE_FRAME]
    life_start, life_count = table_ranges[TABLE_LIFE]
    bullet_start, bullet_count = table_ranges[TABLE_BULLET]
    layout_package = HUD_HEADER.pack(
        HUD_MAGIC, HUD_VERSION, HUD_HEADER.size, HUD_UNIT.size, len(units),
        HUD_HEADER.size, frame_start, frame_count, life_start, life_count,
        bullet_start, bullet_count, layout_crc,
    ) + packed_units

    metadata = {
        "format": "re4dc-source-hud",
        "version": HUD_VERSION,
        "source": source_metadata,
        "units": unit_metadata,
        "textures": texture_metadata,
        "texture_descriptors": descriptor_count,
        "texture_bytes": len(image_blob),
        "layout_bytes": len(layout_package),
        "layout_sha256": hashlib.sha256(layout_package).hexdigest(),
        "texture_package_bytes": len(texture_package),
        "texture_package_sha256": hashlib.sha256(texture_package).hexdigest(),
    }
    return layout_package, texture_package, metadata


def integer(value: str) -> int:
    return int(value, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=pathlib.Path, help="private etc/core.das")
    parser.add_argument("layout_output", type=pathlib.Path)
    parser.add_argument("texture_output", type=pathlib.Path)
    parser.add_argument("--manifest", type=pathlib.Path)
    parser.add_argument(
        "--twiddle", action="store_true",
        help="write payloads in the PVR's twiddled order so the runtime can "
             "copy them straight into texture memory",
    )
    parser.add_argument("--arc-offset", type=integer, default=DEFAULT_ARC_OFFSET)
    parser.add_argument("--texture-offset", type=integer, default=DEFAULT_TEXTURE_OFFSET)
    parser.add_argument("--life-offset", type=integer, default=DEFAULT_LIFE_OFFSET)
    parser.add_argument("--frame-offset", type=integer, default=DEFAULT_FRAME_OFFSET)
    parser.add_argument("--bullet-offset", type=integer, default=DEFAULT_BULLET_OFFSET)
    args = parser.parse_args(argv)

    core_data = args.core.read_bytes()
    arc = args.arc_offset
    layout, textures, metadata = build_packages(
        core_data,
        arc + args.texture_offset,
        [
            (TABLE_FRAME, arc + args.frame_offset),
            (TABLE_LIFE, arc + args.life_offset),
            (TABLE_BULLET, arc + args.bullet_offset),
        ],
        twiddle=args.twiddle,
    )
    args.layout_output.parent.mkdir(parents=True, exist_ok=True)
    args.texture_output.parent.mkdir(parents=True, exist_ok=True)
    args.layout_output.write_bytes(layout)
    args.texture_output.write_bytes(textures)
    metadata.update({
        "core_source": args.core.name,
        "core_sha256": hashlib.sha256(core_data).hexdigest(),
        "layout_package": args.layout_output.name,
        "texture_package": args.texture_output.name,
    })
    manifest = args.manifest or args.layout_output.with_suffix(
        args.layout_output.suffix + ".json"
    )
    manifest.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "units": len(metadata["units"]),
        "textures": metadata["texture_descriptors"],
        "texture_bytes": metadata["texture_bytes"],
        "layout_sha256": metadata["layout_sha256"],
        "texture_package_sha256": metadata["texture_package_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, struct.error) as error:
        print(f"source HUD conversion failed: {error}", file=sys.stderr)
        raise SystemExit(1)
