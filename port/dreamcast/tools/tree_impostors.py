#!/usr/bin/env python3
"""Impostor atlases and records for the r100 PS2 trees (game TREE_IMPOSTOR=1).

  tree_impostors.py <out dir> --bake DIR --trees DIR [--pvrtex PATH] [--owner 0xfe]

--bake: tools/blender/bl_impostor_bake.py output (<model>.png, impostors.json);
--trees: ps2_trees.py --dc-uv output (COMMON_<b>.obj in each GC BIN's model
space, ps2-trees.json: GC BIN -> PS2 model).

1. Each atlas is encoded by KOS pvrtex as 4bpp palettised, twiddled, full-
   codebook VQ (-f PAL4BPP -c: 2 KiB codebook + one byte per 4x4 block) and
   wrapped as a one-texture package, format kPal4 (texture_package.hpp): the
   VQ data followed by its 16 palette entries as ARGB1555 (the runtime loads
   them into a palette RAM bank; ARGB1555 keeps bilinear filtering). The
   package key is (crc32, FNV-1a) of that payload: <out>/tex/<crc>-<fnv>.re4tex.
2. Every GC BIN that uses a baked PS2 model gets a record in its own model
   units, framed exactly as the bake framed its reference BIN (the GC BINs of
   one model are uniform scalings of it): centre on the box's vertical axis
   at mid height, half height = frame height / 2, half width = half height x
   cell aspect. <out>/impostors.json is the manifest for
   mesh_annotate.py --impostors.
Previews of the encoded atlases (as pvrtex decodes them) go to <out>/preview/.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_tpl as tpl  # noqa: E402

FORMAT_PAL4 = 3  # texture_package.hpp kPal4 (TREE_IMPOSTOR builds only)


def fnv1a(data):
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def obj_box(path):
    xs, ys, zs = [], [], []
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            x, y, z = (float(t) for t in line.split()[1:4])
            xs.append(x), ys.append(y), zs.append(z)
    ax, az = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    r = max(((x - ax) ** 2 + (z - az) ** 2) ** 0.5 for x, z in zip(xs, zs))
    return ax, az, min(ys), max(ys), r


def frame(box, aspect):
    """The bake's orthographic frame for this box (bl_impostor_bake.py)."""
    ax, az, y0, y1, r = box
    fh = max((y1 - y0) * 1.02, 2 * r * 1.02 / aspect)
    return dict(centre=[ax, (y0 + y1) / 2, az], half_w=fh * aspect / 2, half_h=fh / 2)


def package_pal4(dt, pal, name):
    """pvrtex DcTx (PAL4BPP, full-codebook VQ) + DPAL -> kPal4 texture package bytes, info."""
    if len(dt) < 32 or dt[:4] != b"DcTx":
        raise ValueError("expected a pvrtex DcTx file")
    size, = struct.unpack_from("<I", dt, 4)
    version, units, book, colors = dt[8:12]
    width, height, mode = struct.unpack_from("<HHI", dt, 12)
    if (size != len(dt) or version or units or book != 255 or colors > 15 or (mode >> 27) & 7 != 5 or
            not mode & (1 << 30) or (8 << ((mode >> 3) & 7), 8 << (mode & 7)) != (width, height)):
        raise ValueError("expected 4bpp palettised full-codebook VQ without mipmaps")
    data = 2048 + width * height // 16
    if len(dt) != (32 + data + 31) & ~31:
        raise ValueError("unexpected VQ payload size")
    if pal[:4] != b"DPAL":
        raise ValueError("expected a pvrtex DPAL palette")
    count, = struct.unpack_from("<I", pal, 4)
    entries = struct.unpack_from("<%dI" % count, pal, 8)
    if count > 16:
        raise ValueError("more than 16 palette entries")
    argb1555 = []
    for c in list(entries) + [0] * (16 - count):
        a, r, g, b = c >> 24, (c >> 16) & 255, (c >> 8) & 255, c & 255
        argb1555.append((0x8000 if a >= 128 else 0) | (r >> 3) << 10 | (g >> 3) << 5 | b >> 3)
    payload = dt[32:32 + data] + struct.pack("<16H", *argb1555)
    start = tpl.HEADER.size + tpl.TEXTURE.size
    descriptor = tpl.TEXTURE.pack(tpl._name_bytes(name), width, height, FORMAT_PAL4, start, len(payload),
                                  tpl.FLAG_ALPHA | tpl.FLAG_BINARY_ALPHA, tpl.PAYLOAD_VQ, 0)
    body = descriptor + payload
    header = tpl.HEADER.pack(tpl.MAGIC, tpl.VERSION, tpl.HEADER.size, tpl.TEXTURE.size, 1, tpl.HEADER.size, start,
                             len(payload), zlib.crc32(body) & 0xFFFFFFFF, 1, 0)
    key = (zlib.crc32(payload) & 0xFFFFFFFF, fnv1a(payload))
    return header + body, key, dict(width=width, height=height, vram_bytes=len(payload), palette=count)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--bake", type=Path, required=True)
    ap.add_argument("--trees", type=Path, required=True)
    ap.add_argument("--owner", default="0xfe")
    ap.add_argument("--pvrtex", type=Path,
                    default=Path(os.environ.get("RE4DC_KOS_BASE", "/root/work/kos-re4dc-d367")) / "utils/pvrtex/pvrtex")
    a = ap.parse_args()
    bake = json.loads((a.bake / "impostors.json").read_text())
    mapping = json.loads((a.trees / "ps2-trees.json").read_text())["mapping"]
    for d in ("tex", "preview", "work"):
        (a.out / d).mkdir(parents=True, exist_ok=True)
    atlases, records = {}, []
    for model, info in sorted(bake["models"].items()):
        work = a.out / "work" / model
        subprocess.run([str(a.pvrtex), "-i", str(a.bake / ("%s.png" % model)), "-o", str(work) + ".dt",
                        "-f", "PAL4BPP", "-c", "--preview", str(a.out / "preview" / ("%s.png" % model))],
                       check=True, stdout=subprocess.DEVNULL)
        blob, key, meta = package_pal4((Path(str(work) + ".dt")).read_bytes(),
                                       (Path(str(work) + ".dt.pal")).read_bytes(), "impostor_%s" % model)
        name = "%08x-%08x.re4tex" % key
        (a.out / "tex" / name).write_bytes(blob)
        atlases[model] = dict(meta, key=["%08x" % key[0], "%08x" % key[1]], package=name,
                              cell=info["cell"], cols=info["cols"], atlas=info["atlas"])
        if meta["width"] != info["atlas"][0] or meta["height"] != info["atlas"][1]:
            raise ValueError("encoded atlas size differs from the bake")
    for b in sorted(mapping, key=int):
        model = str(mapping[b]["ps2_bin"])
        if model not in atlases:
            continue
        at, info = atlases[model], bake["models"][model]
        f = frame(obj_box(a.trees / ("COMMON_%s.obj" % b)), info["cell_aspect"])
        records.append(dict(owner=a.owner, bin=int(b), common=True, model=int(model), key=at["key"],
                            views=bake["views"], cols=at["cols"], cell=at["cell"], atlas=at["atlas"], **f))
    manifest = dict(views=bake["views"], cell_h=bake["cell_h"], light=bake["light"],
                    vram_bytes=sum(v["vram_bytes"] for v in atlases.values()), atlases=atlases, records=records)
    (a.out / "impostors.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(dict(atlases=len(atlases), records=len(records), vram_bytes=manifest["vram_bytes"])))


if __name__ == "__main__":
    main()
