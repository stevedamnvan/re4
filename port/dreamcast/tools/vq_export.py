#!/usr/bin/env python3
"""Export every r100 material three ways for the R4 VQ quality pass.

For each material this writes, under the output directory:

  <name>-gc.png       the GameCube source decoded at its authored resolution
  <name>-now.png      what the accepted package ships: the build's box
                      reduction to the 256-pixel limit, then the 16-bit
                      quantisation the runtime uploads, expanded back to the
                      GameCube resolution for comparison
  <name>-vq.png       pvrtex's own preview of a full-resolution VQ encode

Comparing -now and -vq against -gc answers the question the R4 plan asks: does
vector quantisation at the authored resolution beat the reduced uncompressed
texture we ship today, measured against the same ground truth?

Pure Python: WSL has no PIL, so the PNG writer here is minimal (8-bit RGBA,
filter type 0). Reading back is done on the Windows side.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import subprocess
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import convert_tpl  # noqa: E402


def write_png(path: pathlib.Path, pixels, width: int, height: int) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        row = pixels[y * width:(y + 1) * width]
        for pixel in row:
            raw.extend(bytes(pixel))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload +
                struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", header) +
        chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
        chunk(b"IEND", b""))


def quantise_16bit(pixels, has_alpha: bool, binary_alpha: bool):
    """Apply the same 16-bit narrowing the converter writes into the package,
    then expand back to 8 bits per channel so it can be compared as an image."""
    out = []
    for red, green, blue, alpha in pixels:
        if not has_alpha:
            r5, g6, b5 = red >> 3, green >> 2, blue >> 3
            out.append(((r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4),
                        (b5 << 3) | (b5 >> 2), 255))
        elif binary_alpha:
            r5, g5, b5 = red >> 3, green >> 3, blue >> 3
            out.append(((r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2),
                        (b5 << 3) | (b5 >> 2), 255 if alpha >= 128 else 0))
        else:
            r4, g4, b4, a4 = red >> 4, green >> 4, blue >> 4, alpha >> 4
            out.append((r4 * 17, g4 * 17, b4 * 17, a4 * 17))
    return out


def upscale(pixels, width, height, target_width, target_height):
    """Nearest-neighbour expansion, used only so a reduced texture can be
    compared against the authored resolution pixel for pixel."""
    out = []
    for y in range(target_height):
        source_y = min(height - 1, y * height // target_height)
        for x in range(target_width):
            source_x = min(width - 1, x * width // target_width)
            out.append(pixels[source_y * width + source_x])
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tpl", type=pathlib.Path, required=True)
    parser.add_argument("--mtl", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--pvrtex", type=pathlib.Path, required=True)
    parser.add_argument("--max-dimension", type=int, default=256)
    parser.add_argument("--only", help="comma-separated material names")
    args = parser.parse_args(argv)

    images = convert_tpl.parse_tpl(args.tpl.read_bytes())
    bindings = convert_tpl.parse_mtl(
        args.mtl.read_bytes().decode("utf-8-sig"))
    args.out.mkdir(parents=True, exist_ok=True)
    wanted = set(args.only.split(",")) if args.only else None
    decoded: dict[int, list] = {}

    def pixels_for(index):
        if index not in decoded:
            decoded[index] = convert_tpl.decode_image(images[index])
        return decoded[index]

    for binding in bindings:
        if wanted is not None and binding.name not in wanted:
            continue
        color = images[binding.color_image]
        width, height = color.width, color.height
        pixels = pixels_for(binding.color_image)
        if binding.alpha_image is not None:
            alpha = pixels_for(binding.alpha_image)
            if len(alpha) == len(pixels):
                pixels = [(c[0], c[1], c[2], a[0])
                          for c, a in zip(pixels, alpha)]
        alphas = {pixel[3] for pixel in pixels}
        has_alpha = alphas != {255}
        binary_alpha = has_alpha and alphas <= {0, 255}

        gc_path = args.out / f"{binding.name}-gc.png"
        write_png(gc_path, pixels, width, height)

        # What ships today: box-reduce to the limit, quantise, expand back.
        now, now_width, now_height = pixels, width, height
        while now_width > args.max_dimension or now_height > args.max_dimension:
            now, now_width, now_height = convert_tpl.downsample_box(
                now, now_width, now_height)
        now = quantise_16bit(now, has_alpha, binary_alpha)
        write_png(args.out / f"{binding.name}-now.png",
                  upscale(now, now_width, now_height, width, height),
                  width, height)

        # Full-resolution VQ, encoded by pvrtex, previewed by pvrtex.
        result = subprocess.run(
            [str(args.pvrtex), "-i", str(gc_path),
             "-o", str(args.out / f"{binding.name}.dt"),
             "-f", "AUTO", "-c",
             "-p", str(args.out / f"{binding.name}-vq.png")],
            capture_output=True, text=True)
        if result.returncode != 0:
            print("pvrtex failed for %s: %s" % (
                binding.name, result.stderr.strip().splitlines()[-1:]),
                file=sys.stderr)
            continue
        print("%-20s %dx%d alpha=%s" % (
            binding.name, width, height,
            "binary" if binary_alpha else ("yes" if has_alpha else "no")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
