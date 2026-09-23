#!/usr/bin/env python3
"""Check that packaged tree UVs index the DC bark as PS2 UVs index the PS2 bark.

  verify_tree_uv.py <COMMON.re4mesh> <ps2_tree_texture.py out dir>

For every COMMON tree BIN (0-10) the package's strip triangles are decoded
(part UV bias/scale times the u16 vertex UV) and three interior points per
triangle are sampled in
  DC:  the pvrtex VQ preview of the 128x512 bark at the packaged (u, v);
  PS2: the 256x64 source at the PS2 UV, (v, u) * 256/255 (SMD tool raw/255);
reporting the mean absolute RGB difference, with two controls that must be
clearly worse: the PS2 lookup without the transpose, and the GC bark.
Exit status 1 when DC vs PS2 is not below both controls.
"""
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps2_tree_texture import read_png  # noqa: E402


def sampler(path):
    w, h, px = read_png(path)

    def sample(u, v):  # nearest, wrapping; GX/GS convention: v = 0 is image row 0
        return px[(int((v % 1.0) * h) % h) * w + int((u % 1.0) * w) % w]
    return sample


def tree_triangles(package):
    """COMMON tree BINs of an R4IM package -> {bin: [((u, v) * 3)]} over every level."""
    d = Path(package).read_bytes()
    h = struct.unpack_from("<4s19I", d, 0)
    meshes = h[4]
    mesh_o, part_o, let_o, vert_o, strip_o = h[10:15]
    out = {}
    for i in range(meshes):
        m = struct.unpack_from("<HBBHHIII12f", d, mesh_o + 68 * i)
        if not m[1] or m[0] > 10:
            continue
        tris = []
        for pi in range(m[6], m[6] + m[7]):
            p = struct.unpack_from("<IIBBBBII4f", d, part_o + 36 * pi)
            ulo, vlo, us, vs = p[8:12]
            for li in range(p[6], p[6] + p[7]):
                let = struct.unpack_from("<IIIHH6H", d, let_o + 28 * li)
                verts = [struct.unpack_from("<6H", d, vert_o + 12 * (let[0] + k)) for k in range(let[3])]
                uv = [(ulo + v[3] * us, vlo + v[4] * vs) for v in verts]
                s, end = strip_o + let[1], strip_o + let[1] + let[2]
                while s < end:
                    n = d[s]
                    idx = d[s + 1:s + 1 + n]
                    s += 1 + n
                    tris += [(uv[idx[k]], uv[idx[k + 1]], uv[idx[k + 2]]) for k in range(n - 2)]
        out[m[0]] = tris
    return out


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    package, tex = Path(sys.argv[1]), Path(sys.argv[2]) / "preview"
    dc = sampler(tex / "ps2-bark-vq.png")
    ps2 = sampler(tex / "ps2-bark-256x64-source.png")
    gc = sampler(tex / "gc-bark.png")
    rnd = random.Random(5)
    k = 256.0 / 255.0

    def diff(a, b):
        return sum(abs(a[c] - b[c]) for c in range(3)) / 3.0
    total = {"dc_vs_ps2": [], "control_no_transpose": [], "control_gc_texture": []}
    for b, tris in sorted(tree_triangles(package).items()):
        acc, n = dict.fromkeys(total, 0.0), 0
        for t in tris:
            for _ in range(3):
                r1, r2 = rnd.random(), rnd.random()
                if r1 + r2 > 1:
                    r1, r2 = 1 - r1, 1 - r2
                u = t[0][0] + r1 * (t[1][0] - t[0][0]) + r2 * (t[2][0] - t[0][0])
                v = t[0][1] + r1 * (t[1][1] - t[0][1]) + r2 * (t[2][1] - t[0][1])
                a = dc(u, v)
                acc["dc_vs_ps2"] += diff(a, ps2(v * k, u * k))
                acc["control_no_transpose"] += diff(a, ps2(u * k, v * k))
                acc["control_gc_texture"] += diff(a, gc(u, v))
                n += 1
        print("COMMON/%d tris %d  mean |RGB| diff: DC vs PS2 %.1f   no-transpose control %.1f   GC control %.1f" % (
            b, len(tris), acc["dc_vs_ps2"] / n, acc["control_no_transpose"] / n, acc["control_gc_texture"] / n))
        for key in total:
            total[key].append(acc[key] / n)
    mean = {key: round(sum(v) / len(v), 1) for key, v in total.items()}
    print("ALL", mean)
    if not mean["dc_vs_ps2"] < min(mean["control_no_transpose"], mean["control_gc_texture"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
