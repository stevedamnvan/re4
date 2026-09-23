#!/usr/bin/env python3
"""PS2 r100 tree models (r100_004 BIN 139-147) as render replacements for the
GC tree BINs (COMMON 0-10).

  ps2_trees.py <out dir> --ps2-obj r100_004.scenario.obj [--ps2-idx ...idx_ps2_smd]
               [--export DIR] [--gc-obj R100.allparts.obj] [--dc-uv] [--groves 2,3=145]

Inputs are local, never committed: the PS2 scenario OBJ and .idx_ps2_smd that
JADERLINK's RE4_PS2_SCENARIO_SMD_TOOL writes for r100_004.SMD (see README,
"PS2 tree packages"), and the GC r100 export (--export, default as
export_room_bins_obj.py; --gc-obj defaults to its R100.allparts.obj).

1. Each PS2 tree BIN's local mesh is recovered from the world OBJ by inverting
   one instance's placement (.idx_ps2_smd: position x100, Euler angles,
   scale). The Euler order is the one on which the BIN's instances agree
   (vertex order is the BIN record order, so local coordinates coincide).
2. Every GC tree BIN is mapped to a PS2 tree BIN by majority vote of the
   nearest PS2 tree instance (<= 15 m) over the GC BIN's placed instances,
   else by the closest bounding-box shape.
3. <out>/COMMON_<b>.obj is written in the GC BIN's model space (uniform scale
   by height, bottom centre on the GC BIN's box), one part (material p0_...),
   PS2 UVs and normals; <out>/ps2-trees.json records the mapping. The GC
   placement, instances, collision and part identity are untouched: the
   converter only swaps the triangles (convert_room_bins.py --lod-substitute
   <out>).

--dc-uv writes UVs for the Dreamcast bark (ps2_tree_texture.py): PS2 raw/255
becomes raw/256 and u/v swap for the transposed 128x512 texture. Without it
the UVs index the PS2 256x64 image (for comparison renders only: packaged
with the GC bark they sample it transposed).
--groves B[,B]=PS2BIN rebuilds GC grove BINs as one PS2 tree per GC trunk
(base, height, yaw 97 degrees apart).
"""
import argparse
import itertools
import json
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_room_bins as crb  # noqa: E402
from export_room_bins_obj import DEFAULT_EXPORT, DIRS  # noqa: E402

TREES = range(139, 148)
NEAREST_MM = 15000.0


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def read_idx(path):
    """.idx_ps2_smd -> {SMD number: dict(position (source units), rotation, scale, bin)}.
    The tool prints float32 values (positions / 100); rounding back through
    float32 reproduces the SMD's own values."""
    out, cur = {}, None
    for line in Path(path).read_text(errors="replace").splitlines():
        m = re.fullmatch(r"SMD_(\d+)", line.strip())
        if m:
            cur = out.setdefault(int(m.group(1)), {})
            continue
        if cur is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        cur[key.strip()] = value.strip()
    inst = {}
    for n, kv in out.items():
        if "BinFileID" not in kv:
            continue
        inst[n] = dict(instance=n, bin=int(kv["BinFileID"]),
                       position=[f32(f32(float(kv["Position" + a])) * 100.0) for a in "XYZ"],
                       rotation=[f32(float(kv["Angle" + a])) for a in "XYZ"],
                       scale=[f32(float(kv["Scale" + a])) for a in "XYZ"])
    return inst


def gc_trunks(src):
    """Trunks of a GC tree BIN: connected components that start near the
    ground and span more than 30% of the height -> [(base xyz, height)]."""
    pos = src["positions"]
    tris = [tuple(k[0] for k in t) for p in src["parts"] for s in p["strips"] for t in crb.strip_triangles(s)] + \
           [tuple(k[0] for k in t) for p in src["parts"] for t in p["loose"]]
    ids = {}
    wid = [ids.setdefault(p, len(ids)) for p in pos]
    par = list(range(len(ids)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for t in tris:
        a, b, c = (wid[i] for i in t)
        par[find(a)] = find(b)
        par[find(c)] = find(b)
    comps = {}
    for t in tris:
        comps.setdefault(find(wid[t[0]]), set()).update(t)
    ys = [pos[i][1] for t in tris for i in t]
    y0, y1 = min(ys), max(ys)
    out = []
    for vs in comps.values():
        v = [pos[i] for i in vs]
        lo = min(p[1] for p in v)
        hi = max(p[1] for p in v)
        if lo < y0 + 0.12 * (y1 - y0) and hi - lo > 0.3 * (y1 - y0):
            base = [p for p in v if p[1] < lo + 0.05 * (y1 - y0)]
            out.append(((sum(p[0] for p in base) / len(base), lo, sum(p[2] for p in base) / len(base)), hi - lo))
    return sorted(out)


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rotation(order, r):
    f = {"x": _rx(r[0]), "y": _ry(r[1]), "z": _rz(r[2])}
    m = f[order[0]]
    for axis in order[1:]:
        m = _mul(m, f[axis])
    return m


def local(verts, inst, order):
    """World OBJ vertices (source units / 100) -> the instance's local frame."""
    r = rotation(order, inst["rotation"])
    out = []
    for p in verts:
        d = [p[a] * 100.0 - inst["position"][a] for a in range(3)]
        q = [sum(r[k][i] * d[k] for k in range(3)) for i in range(3)]  # R^T d
        out.append(tuple(q[a] / inst["scale"][a] for a in range(3)))
    return out


def faces_of(obj, fi):
    """parse_obj face -> (v indices, vt indices or None, vn indices or None)."""
    corners = obj["faces"][fi][1]
    t = tuple(c[1] for c in corners)
    n = tuple(c[2] for c in corners)
    return (tuple(c[0] for c in corners), t if None not in t else None, n if None not in n else None)


def ps2_models(ps2, inst):
    """-> {PS2 BIN: dict(v (local), faces, lo, hi)}, report."""
    gfaces = defaultdict(list)
    for fi, g in enumerate(ps2["face_groups"]):
        gfaces[g].append(faces_of(ps2, fi))
    groups = {}
    for gi, name in enumerate(ps2["groups"]):
        m = re.match(r"PS2SCENARIO#SMD_(\d+)#SMX_\d+#TYPE_\w+#BIN_(\d+)#", name)
        if m and int(m.group(2)) in TREES:
            groups.setdefault(int(m.group(2)), []).append((int(m.group(1)), gi))
    models, report = {}, {}
    for b, gl in sorted(groups.items()):
        best = None
        for order in ("".join(p) for p in itertools.permutations("xyz")):
            locs = []
            for smd, gi in gl[:6]:
                vs = sorted({v for f in gfaces[gi] for v in f[0]})
                locs.append(local([ps2["v"][v] for v in vs], inst[smd], order))
            n = min(len(l) for l in locs)
            err = sum(math.dist(locs[0][i], l[i]) for l in locs[1:] for i in range(n)) / max(1, n * (len(locs) - 1))
            if best is None or err < best[0]:
                best = (err, order, locs[0])
        err, order, verts = best
        smd, gi = gl[0]
        vs = sorted({v for f in gfaces[gi] for v in f[0]})
        idx = {v: i for i, v in enumerate(vs)}
        faces = [(tuple(idx[v] for v in f[0]), f[1], f[2]) for f in gfaces[gi]]
        lo = [min(p[a] for p in verts) for a in range(3)]
        hi = [max(p[a] for p in verts) for a in range(3)]
        models[b] = dict(v=verts, faces=faces, lo=lo, hi=hi)
        report[b] = dict(instances=len(gl), euler=order, instance_agreement_units=round(err, 2),
                         tris=len(faces), extent=[round(hi[a] - lo[a]) for a in range(3)])
        print("PS2 BIN", b, report[b])
    return models, report


def gc_votes(gc, inst):
    """Nearest PS2 tree instance per placed GC tree (COMMON 0-10) -> {bin: Counter(PS2 BIN)}."""
    lo = defaultdict(lambda: [1e18] * 3)
    hi = defaultdict(lambda: [-1e18] * 3)
    for fi, g in enumerate(gc["face_groups"]):
        for c in gc["faces"][fi][1]:
            p = gc["v"][c[0]]
            for a in range(3):
                lo[g][a] = min(lo[g][a], p[a])
                hi[g][a] = max(hi[g][a], p[a])
    votes = defaultdict(Counter)
    for g, name in enumerate(gc["groups"]):
        m = re.search(r"BIN_(\d+)#CommonBIN", name)
        if not m or int(m.group(1)) > 10 or g not in lo:
            continue
        c = [(lo[g][a] + hi[g][a]) * 50.0 for a in range(3)]
        near = min((math.hypot(i["position"][0] - c[0], i["position"][2] - c[2]), i["bin"]) for i in inst.values())
        if near[0] <= NEAREST_MM:
            votes[int(m.group(1))][near[1]] += 1
    return votes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--ps2-obj", type=Path, required=True, help="SMD tool r100_004.scenario.obj")
    ap.add_argument("--ps2-idx", type=Path, help="SMD tool .idx_ps2_smd (default: next to --ps2-obj)")
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT, help="GC r100_full_export directory")
    ap.add_argument("--gc-obj", type=Path, help="GC placed-instance OBJ (default: <export>/R100.allparts.obj)")
    ap.add_argument("--dc-uv", action="store_true", help="UVs for the transposed DC bark (ps2_tree_texture.py)")
    ap.add_argument("--groves", metavar="B[,B]=PS2BIN", help="one PS2 tree per GC trunk in these BINs")
    a = ap.parse_args()
    idx = a.ps2_idx or a.ps2_obj.with_name(a.ps2_obj.name[:-len(".obj")] + ".idx_ps2_smd")
    gc_obj = a.gc_obj or a.export / "R100.allparts.obj"
    groves = {}
    if a.groves:
        spec, model = a.groves.split("=")
        groves = {int(x): int(model) for x in spec.split(",")}
    a.out.mkdir(parents=True, exist_ok=True)
    inst = {n: i for n, i in read_idx(idx).items() if i["bin"] in TREES}
    ps2 = crb.parse_obj(a.ps2_obj)
    models, model_report = ps2_models(ps2, inst)
    report = dict(models=model_report, mapping={}, dc_uv=a.dc_uv)
    votes = gc_votes(crb.parse_obj(gc_obj), inst)
    for b in range(11):
        src = crb.parse_bin((a.export / DIRS["COMMON"] / ("%04d.BIN" % b)).read_bytes())
        used = {k[0] for p in src["parts"] for s in p["strips"] for k in s} | \
               {k[0] for p in src["parts"] for t in p["loose"] for k in t}
        glo = [min(src["positions"][i][x] for i in used) for x in range(3)]
        ghi = [max(src["positions"][i][x] for i in used) for x in range(3)]
        ge = [ghi[x] - glo[x] for x in range(3)]
        if votes[b]:
            pick, how = votes[b].most_common(1)[0][0], "nearest-instance vote %s" % dict(votes[b])
        else:
            def shape(m):
                e = [m["hi"][x] - m["lo"][x] for x in range(3)]
                return abs(math.log(max(e[0], e[2]) / e[1]) - math.log(max(ge[0], ge[2]) / ge[1]))
            pick, how = min(models, key=lambda k: shape(models[k])), "shape (no PS2 tree within 15 m)"
        if b in groves:
            pick, how = groves[b], "grove: one PS2 BIN %d per GC trunk" % groves[b]
        m = models[pick]
        mc = [(m["lo"][0] + m["hi"][0]) / 2, m["lo"][1], (m["lo"][2] + m["hi"][2]) / 2]
        if b in groves:
            places = [(base, height / (m["hi"][1] - m["lo"][1]), math.radians(97.0 * k))
                      for k, (base, height) in enumerate(gc_trunks(src))]
        else:
            places = [([(glo[0] + ghi[0]) / 2, glo[1], (glo[2] + ghi[2]) / 2], ge[1] / (m["hi"][1] - m["lo"][1]), 0.0)]
        lines = ["# PS2 r100_004 BIN %d fitted into GC COMMON/%d model space (%d placement(s), scale %s)" % (
            pick, b, len(places), ",".join("%.3f" % p[1] for p in places))]
        for base, sc, yaw in places:
            cy, sy = math.cos(yaw), math.sin(yaw)
            for p in m["v"]:
                d = [(p[x] - mc[x]) * sc for x in range(3)]
                lines.append("v %.4f %.4f %.4f" % (base[0] + cy * d[0] + sy * d[2], base[1] + d[1],
                                                   base[2] - sy * d[0] + cy * d[2]))
        vts = sorted({t for f in m["faces"] if f[1] for t in f[1]})
        vti = {t: i + 1 for i, t in enumerate(vts)}
        for t in vts:
            u, v = ps2["vt"][t]
            if a.dc_uv:  # PS2 raw/255 -> raw/256, swapped for the transposed DC texture
                u, v = v * 255.0 / 256.0, u * 255.0 / 256.0
            lines.append("vt %.6f %.6f" % (u, v))
        vns = sorted({n for f in m["faces"] if f[2] for n in f[2]})
        vni = {n: i + 1 for i, n in enumerate(vns)}
        for base, sc, yaw in places:  # one rotated normal set per placement
            cy, sy = math.cos(yaw), math.sin(yaw)
            for n in vns:
                x, y, z = ps2["vn"][n]
                lines.append("vn %.6f %.6f %.6f" % (cy * x + sy * z, y, -sy * x + cy * z))
        lines += ["g part_0", "usemtl p0_t0_ps2bin%d" % pick]
        for k in range(len(places)):
            vo, no = k * len(m["v"]), k * len(vns)
            for v, t, n in m["faces"]:
                lines.append("f " + " ".join("%d/%s/%s" % (v[j] + 1 + vo, vti[t[j]] if t else "",
                                                           vni[n[j]] + no if n else "") for j in range(3)))
        (a.out / ("COMMON_%d.obj" % b)).write_text("\n".join(lines).replace("//\n", "\n") + "\n")
        report["mapping"][b] = dict(ps2_bin=pick, how=how, gc_extent=[round(x) for x in ge],
                                    scale=round(places[0][1], 3), placements=len(places),
                                    ps2_tris=len(m["faces"]) * len(places))
        print("GC COMMON/%d ext %s -> PS2 BIN %d x%d (%d tris) scale %.3f  [%s]" % (
            b, [round(x) for x in ge], pick, len(places), len(m["faces"]) * len(places), places[0][1], how))
    (a.out / "ps2-trees.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
