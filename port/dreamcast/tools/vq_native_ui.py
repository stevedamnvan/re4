#!/usr/bin/env python3
"""Re-encode large, padding-dominated native UI packages as full-codebook VQ.

vq_native_ui.py --textures <tex-dir> --log <run-output.txt> --output <dir>

prepare_native_ui.py pads every source image to power-of-two dimensions and
stores 16-bit twiddled texels, so a 528x132 title image occupies 1024x256x2 =
512 KiB of PVR RAM and a 640x360 backdrop 1 MiB. This tool keeps the existing
package's quantized texels, padded dimensions and source identity (file name),
so the runtime's UV scale (source/native size) and lookup are unchanged, and
replaces the payload with a full 256-entry VQ codebook encoded by the pinned
KOS pvrtex (2048 + w*h/4 bytes: 1/8 of 16-bit). Candidates are selected from
the images a run actually loaded ("native UI: load <path> WxH fmt=N"): 2D UI
only (loaded before the first room binds, or an indexed C4/C8 source), padded
16-bit size >= --min-bytes and both sides >= --min-side (thin text strips keep
exact texels). Room/model textures are left alone unless --model-min-bytes
is given (large CMPR-sourced model textures; VQ is 2 bpp vs the source 4 bpp).

Private inputs and outputs: nothing produced here belongs in Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import convert_tpl as tpl  # noqa: E402

ROOM_BIND = "native room identities:"
LOAD = re.compile(r"native UI: load \S*/([0-9a-f]{8}-[0-9a-f]{8})\.re4tex (\d+)x(\d+) fmt=(\d+)")
PVRTEX = "/root/work/kos-re4dc-d336/utils/pvrtex/pvrtex"
FORMAT_NAMES = {tpl.FORMAT_RGB565: "RGB565", tpl.FORMAT_ARGB1555: "ARGB1555", tpl.FORMAT_ARGB4444: "ARGB4444"}


def read_package(blob: bytes):
    header = tpl.HEADER.unpack_from(blob)
    magic, version, header_size, stride, count, texture_offset = header[:6]
    if magic != tpl.MAGIC or version != tpl.VERSION or count != 1 or stride != tpl.TEXTURE.size:
        raise ValueError("expected a single-texture native package")
    fields = tpl.TEXTURE.unpack_from(blob, texture_offset)
    _, width, height, fmt, data_offset, data_size, flags, payload, _ = fields
    if payload != tpl.PAYLOAD_TWIDDLED or data_size != width * height * 2:
        raise ValueError("expected a twiddled 16-bit payload")
    texels = struct.unpack_from("<%dH" % (width * height), blob, data_offset)
    return width, height, fmt, flags, texels


def detwiddle(texels, width, height):
    order = tpl.twiddle_16bpp(list(range(width * height)), width, height)
    linear = [0] * (width * height)
    for twiddled, index in enumerate(order):
        linear[index] = texels[twiddled]
    return linear


def expand(value: int, fmt: int):
    if fmt == tpl.FORMAT_RGB565:
        return (*tpl._expand_565(value), 255)
    if fmt == tpl.FORMAT_ARGB1555:
        r, g, b = (value >> 10) & 31, (value >> 5) & 31, value & 31
        return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255 if value & 0x8000 else 0)
    return (((value >> 8) & 15) * 17, ((value >> 4) & 15) * 17, (value & 15) * 17, (value >> 12) * 17)


def psnr(a, b, width, box):
    """RGBA PSNR over the source rectangle (top-left box of the padded image)."""
    bw, bh = box
    error = 0
    for y in range(bh):
        row = y * width
        for x in range(bw):
            p, q = a[row + x], b[row + x]
            # Weight colour by coverage so fully transparent texels do not count.
            alpha = max(p[3], q[3]) / 255.0
            error += alpha * sum((p[c] - q[c]) ** 2 for c in range(3)) + (p[3] - q[3]) ** 2
    mse = error / (bw * bh * 4)
    return 99.0 if mse == 0 else 10 * math.log10(255 * 255 / mse)


def encode(key, textures, output, pvrtex, box, work):
    from PIL import Image
    source = (textures / (key + ".re4tex")).read_bytes()
    width, height, fmt, flags, texels = read_package(source)
    pixels = [expand(v, fmt) for v in detwiddle(texels, width, height)]
    png = work / (key + ".png")
    preview = work / (key + "-vq.png")
    dt = work / (key + ".dt")
    image = Image.new("RGBA", (width, height))
    image.putdata(pixels)
    image.save(png)
    subprocess.run([pvrtex, "-i", str(png), "-o", str(dt), "-f", FORMAT_NAMES[fmt], "-c", "-p", str(preview)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    package, meta = tpl.package_existing_vq(dt.read_bytes())
    if (meta["width"], meta["height"], meta["format"]) != (width, height, fmt):
        raise ValueError("VQ output changed the native dimensions or format: " + key)
    decoded = list(Image.open(preview).convert("RGBA").getdata())
    quality = psnr(pixels, decoded, width, box)
    (output / (key + ".re4tex")).write_bytes(package)
    return dict(key=key, source_width=box[0], source_height=box[1], native_width=width, native_height=height,
                format=FORMAT_NAMES[fmt], before_vram=width * height * 2, after_vram=meta["vram_bytes"],
                psnr_db=round(quality, 2), source_package_sha256=hashlib.sha256(source).hexdigest(),
                package_sha256=hashlib.sha256(package).hexdigest(), package_bytes=len(package))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--textures", type=pathlib.Path, required=True, help="existing native package directory")
    parser.add_argument("--log", type=pathlib.Path, action="append", required=True, help="run log(s) naming loaded images")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    # Sega hardware notes: VQ pays off from 64x64 up; 32 KiB = 128x128 / 64x256 16-bit.
    parser.add_argument("--min-bytes", type=int, default=32 * 1024)
    parser.add_argument("--min-side", type=int, default=32)
    parser.add_argument("--max-fill", type=float, default=1.0)
    parser.add_argument("--model-min-bytes", type=int, default=0,
                        help="also VQ room/model textures of at least this padded 16-bit size (0: UI only)")
    parser.add_argument("--pvrtex", default=PVRTEX)
    parser.add_argument("--previews", type=pathlib.Path, help="keep source/VQ preview PNGs here")
    args = parser.parse_args(argv)
    seen = {}
    for log in args.log:
        text = log.read_text(errors="replace")
        room = text.find(ROOM_BIND)
        for match in LOAD.finditer(text):
            key, w, h, fmt = match.group(1), int(match.group(2)), int(match.group(3)), int(match.group(4))
            # 2D UI: anything loaded before the first room binds (title/menus), or
            # an indexed (C4/C8) source afterwards (HUD). Model textures are left alone.
            ui = (room < 0 or match.start() < room) or fmt in (8, 9)
            if key in seen:
                ui = ui or seen[key][3]
            seen[key] = (w, h, fmt, ui)
    args.output.mkdir(parents=True, exist_ok=False)
    report = []
    with tempfile.TemporaryDirectory() as scratch:
        work = args.previews or pathlib.Path(scratch)
        work.mkdir(parents=True, exist_ok=True)
        for key, (w, h, source_format, ui) in sorted(seen.items()):
            pw, ph = max(8, 1 << (w - 1).bit_length()), max(8, 1 << (h - 1).bit_length())
            padded = pw * ph * 2
            # Thin strips (text lines) keep exact texels: 2x2 VQ blocks smear them.
            if ui and (padded < args.min_bytes or min(w, h) < args.min_side or w * h > args.max_fill * pw * ph):
                continue
            # Room/model textures only when explicitly requested (--model-min-bytes).
            if not ui and (not args.model_min_bytes or padded < args.model_min_bytes):
                continue
            if not (args.textures / (key + ".re4tex")).is_file():
                continue
            entry = encode(key, args.textures, args.output, args.pvrtex, (w, h), work)
            entry["source_format"] = source_format
            entry["class"] = "ui" if ui else "model"
            report.append(entry)
            print("%s %4dx%-4d -> %4dx%-4d %-8s %8d -> %7d  psnr=%.1f dB" % (
                key, w, h, pw, ph, entry["format"], entry["before_vram"], entry["after_vram"], entry["psnr_db"]))
    total = dict(images=len(report), before_vram=sum(e["before_vram"] for e in report),
                 after_vram=sum(e["after_vram"] for e in report))
    (args.output / "vq-native-ui-report.json").write_text(json.dumps(dict(summary=total, images=report), indent=2) + "\n")
    print("total", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
