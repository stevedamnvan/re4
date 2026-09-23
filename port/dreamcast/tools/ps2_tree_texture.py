#!/usr/bin/env python3
"""PS2 r100 tree bark (r100_004.TPL entry 0023, 256x64, 16 colours) ->
Dreamcast replacement for the GC tree texture (R100.TPL image 0).

  ps2_tree_texture.py <0023.PNG> <out dir> [--export DIR] [--pvrtex PATH]

The GC tree material (ROOM_MATERIAL_013: diffuse map 0, material flag 00,
opaque) samples R100.TPL image 0 (128x512 CMPR, opaque). The runtime finds a
native texture by the GC source image identity
(prepare_native_ui.image_identity -> /cd/dc/tex/<crc>-<fnv>.re4tex) and
rejects a part whose repeating axis has a package size different from the
source image size (native_ui.cpp re4dc_model_packet_begin); the trees repeat
(UV range about -1.1..2.1). So the replacement keeps the GC key and size:

  * the PS2 image is transposed (256x64 -> 64x256; ps2_trees.py --dc-uv swaps
    u/v to match, which also reproduces the GC layout: along the trunk = v)
    and upsampled 2x (bilinear, wrapping) to 128x512;
  * PS2 alpha is normalised (GS 0x80 = 1.0) and must then be opaque, as the
    GC material is (a PS2 texture with real alpha would need the GC part's
    alpha flags, which this path does not change);
  * KOS pvrtex encodes RGB565 full-codebook VQ (18,432 B of VRAM against
    131,072 B for twiddled RGB565), wrapped by convert_tpl.package_existing_vq;
  * <out>/tex/<gc key>.re4tex (+ .json); previews in <out>/preview/
    (ps2-bark-256x64-source.png, ps2-bark-128x512.png, ps2-bark-vq.png and
    gc-bark.png, the decoded GC image, for verify_tree_uv.py and the Blender
    comparison).

--export defaults as export_room_bins_obj.py (the GC R100.TPL.TPL is read from
it); --pvrtex defaults to $RE4DC_KOS_BASE/utils/pvrtex/pvrtex.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_tpl  # noqa: E402
from export_room_bins_obj import DEFAULT_EXPORT  # noqa: E402
from prepare_native_ui import image_identity  # noqa: E402
from vq_export import write_png  # noqa: E402

GC_TPL = "R100.TPL.TPL"
GC_IMAGE = 0
TARGET = (128, 512)


def read_png(path):
    """8-bit non-interlaced PNG (grey, RGB, palette, grey+alpha, RGBA) -> (w, h, [(r, g, b, a)])."""
    d = Path(path).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s: not a PNG" % path)
    o, idat, pal, trns = 8, b"", [], b""
    while o < len(d):
        n, kind = struct.unpack_from(">I4s", d, o)
        chunk = d[o + 8:o + 8 + n]
        o += 12 + n
        if kind == b"IHDR":
            w, h, depth, ct, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or interlace:
                raise ValueError("%s: only 8-bit non-interlaced PNG" % path)
        elif kind == b"PLTE":
            pal = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif kind == b"tRNS":
            trns = chunk
        elif kind == b"IDAT":
            idat += chunk
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(idat)
    stride = w * ch
    prev, p, px = bytearray(stride), 0, []
    for _ in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        prev = line
        for x in range(w):
            s = line[x * ch:(x + 1) * ch]
            if ct == 6:
                px.append(tuple(s))
            elif ct == 2:
                px.append((s[0], s[1], s[2], 255))
            elif ct == 0:
                px.append((s[0], s[0], s[0], 255))
            elif ct == 4:
                px.append((s[0], s[0], s[0], s[1]))
            else:
                px.append(pal[s[0]] + ((trns[s[0]] if s[0] < len(trns) else 255),))
    return w, h, px


def bilinear_wrap(px, w, h, tw, th):
    out = []
    for y in range(th):
        fy = (y + 0.5) * h / th - 0.5
        y0 = int(fy // 1)
        ty = fy - y0
        for x in range(tw):
            fx = (x + 0.5) * w / tw - 0.5
            x0 = int(fx // 1)
            tx = fx - x0
            acc = [0.0] * 4
            for dy, wy in ((0, 1 - ty), (1, ty)):
                for dx, wx in ((0, 1 - tx), (1, tx)):
                    p = px[((y0 + dy) % h) * w + (x0 + dx) % w]
                    for c in range(4):
                        acc[c] += wx * wy * p[c]
            out.append(tuple(min(255, max(0, round(v))) for v in acc))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png", type=Path, help="r100_004.TPL entry 0023 as extracted to PNG")
    ap.add_argument("out", type=Path)
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT, help="GC r100_full_export directory")
    kos = os.environ.get("RE4DC_KOS_BASE")
    ap.add_argument("--pvrtex", type=Path, default=Path(kos) / "utils/pvrtex/pvrtex" if kos else None,
                    help="KOS pvrtex (default $RE4DC_KOS_BASE/utils/pvrtex/pvrtex)")
    a = ap.parse_args()
    if a.pvrtex is None:
        ap.error("--pvrtex (or RE4DC_KOS_BASE) is required")
    (a.out / "tex").mkdir(parents=True, exist_ok=True)
    (a.out / "preview").mkdir(parents=True, exist_ok=True)
    w, h, px = read_png(a.png)
    if max(p[3] for p in px) <= 128:  # raw GS alpha: 0x80 = 1.0
        px = [(r, g, b, min(255, al * 2)) for r, g, b, al in px]
    if not all(p[3] == 255 for p in px):
        raise SystemExit("PS2 tree texture has alpha; this path assumes the opaque GC tree material")
    transposed = [px[x * w + y] for y in range(w) for x in range(h)]  # new (x, y) = old (y, x)
    big = bilinear_wrap(transposed, h, w, *TARGET)
    png = a.out / "preview" / "ps2-bark-128x512.png"
    write_png(png, big, *TARGET)
    write_png(a.out / "preview" / "ps2-bark-256x64-source.png", px, w, h)
    encoded = a.out / "ps2-bark.dt"
    subprocess.run([str(a.pvrtex), "-i", str(png), "-o", str(encoded), "-f", "RGB565", "-c",
                    "-p", str(a.out / "preview" / "ps2-bark-vq.png")], check=True, capture_output=True)
    gc = convert_tpl.parse_tpl((a.export / GC_TPL).read_bytes())[GC_IMAGE]
    write_png(a.out / "preview" / "gc-bark.png", convert_tpl.decode_image(gc), gc.width, gc.height)
    if (gc.width, gc.height) != TARGET:
        raise SystemExit("GC tree image is %dx%d, expected %dx%d" % (gc.width, gc.height, *TARGET))
    key, _ = image_identity(gc)
    blob, meta = convert_tpl.package_existing_vq(encoded.read_bytes(), "source")
    pkg = a.out / "tex" / (key + ".re4tex")
    pkg.write_bytes(blob)
    meta.update(key=key,
                key_source="GC R100.TPL image %d (%dx%d format %d) = COMMON tree part texture 0" % (
                    GC_IMAGE, gc.width, gc.height, gc.format),
                ps2_source="r100_004.TPL entry 0023 (%dx%d, opaque)" % (w, h),
                transform="transpose (u,v)->(v,u), bilinear wrap 2x to 128x512; meshes swap uv and scale by 255/256",
                encoded_sha256=hashlib.sha256(encoded.read_bytes()).hexdigest(),
                package_sha256=hashlib.sha256(blob).hexdigest(), package_bytes=len(blob))
    pkg.with_suffix(".re4tex.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
