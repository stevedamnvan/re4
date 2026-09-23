"""Blender (-b --python) GC<->PS2 r100 spatial correspondence in world space.

usage: blender -b --factory-startup --python bl_pair_ps2.py -- <gc.obj> <ps2.obj> <out.json> <assign.txt>

GC: JADERLINK R100.allparts.obj (every placed instance, world /100). PS2: RE4_PS2_SCENARIO_SMD_TOOL
r100_004.scenario.obj (world /100). OBJ unit = 10 cm.
  * every GC group is area-sampled; each sample finds the nearest PS2 surface (distance, PS2 group)
  * every PS2 face (centroid + 3 interior points) finds the nearest GC surface; the face is assigned
    to the GC group owning the nearest GC face if within ASSIGN (default 2 units = 20 cm)
No index correspondence is assumed.
"""
import json
import sys
from pathlib import Path

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert_room_bins import parse_obj  # noqa: E402

ASSIGN = 2.0
DENSITY = 4.0      # samples per unit^2 (1 per 25 cm^2 x 100 = per 0.25 m^2)
MAX_SAMPLES = 6000
MIN_SAMPLES = 150


def arrays(obj):
    V = np.asarray(obj['v'], dtype=np.float64)
    F = np.asarray([[c[0] for c in f] for _, f in obj['faces']], dtype=np.int64)
    G = np.asarray(obj['face_groups'], dtype=np.int64)
    return V, F, G


def area(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def sample(V, F, idx, w, n, rng):
    if len(idx) == 0 or w.sum() <= 0:
        return np.zeros((0, 3))
    pick = rng.choice(idx, size=n, p=w / w.sum())
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    a, b, c = V[F[pick, 0]], V[F[pick, 1]], V[F[pick, 2]]
    return (1 - s)[:, None] * a + (s * (1 - r2))[:, None] * b + (s * r2)[:, None] * c


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    gc_path, ps2_path, out_path, assign_path = argv[:4]
    gc = parse_obj(gc_path); ps2 = parse_obj(ps2_path)
    GV, GF, GG = arrays(gc); PV, PF, PG = arrays(ps2)
    GA, PA = area(GV, GF), area(PV, PF)
    print('GC faces', len(GF), 'groups', len(gc['groups']), '| PS2 faces', len(PF), 'groups', len(ps2['groups']))
    gbvh = BVHTree.FromPolygons([Vector(p) for p in GV], GF.tolist(), all_triangles=True, epsilon=0.0)
    pbvh = BVHTree.FromPolygons([Vector(p) for p in PV], PF.tolist(), all_triangles=True, epsilon=0.0)
    rng = np.random.default_rng(1234)

    # PS2 face -> GC group
    n_extra = 3
    pts = [(PV[PF[:, 0]] + PV[PF[:, 1]] + PV[PF[:, 2]]) / 3.0]
    for _ in range(n_extra):
        r1, r2 = rng.random(len(PF)), rng.random(len(PF)); s = np.sqrt(r1)
        pts.append((1 - s)[:, None] * PV[PF[:, 0]] + (s * (1 - r2))[:, None] * PV[PF[:, 1]] + (s * r2)[:, None] * PV[PF[:, 2]])
    ps2_face_group = np.full(len(PF), -1, dtype=np.int64)
    ps2_face_dist = np.zeros(len(PF))
    votes_dist = np.zeros((len(PF), n_extra + 1)); votes_grp = np.zeros((len(PF), n_extra + 1), dtype=np.int64)
    for k, P in enumerate(pts):
        for i, p in enumerate(P):
            loc, nrm, fi, d = gbvh.find_nearest(Vector(p))
            votes_dist[i, k] = d if d is not None else 1e9
            votes_grp[i, k] = GG[fi] if fi is not None else -1
    for i in range(len(PF)):
        vals, counts = np.unique(votes_grp[i], return_counts=True)
        g = vals[np.argmax(counts)]
        dm = votes_dist[i].mean()
        ps2_face_dist[i] = dm
        if dm <= ASSIGN:
            ps2_face_group[i] = g
    with open(assign_path, 'w') as fh:
        for i in range(len(PF)):
            fh.write('%d %.4f\n' % (ps2_face_group[i], ps2_face_dist[i]))

    groups = []
    for g, name in enumerate(gc['groups']):
        idx = np.nonzero(GG == g)[0]
        a = GA[idx].sum()
        n = int(min(MAX_SAMPLES, max(MIN_SAMPLES, a * DENSITY)))
        S = sample(GV, GF, idx, GA[idx], n, rng)
        d = np.zeros(len(S)); hit = {}
        for i, p in enumerate(S):
            loc, nrm, fi, dd = pbvh.find_nearest(Vector(p))
            d[i] = dd if dd is not None else 1e9
            if dd is not None and dd <= ASSIGN:
                pg = ps2['groups'][PG[fi]]
                hit[pg] = hit.get(pg, 0) + 1
        mine = np.nonzero(ps2_face_group == g)[0]
        # reverse: PS2 assigned faces -> distance to this GC group's surface (sampled)
        if len(mine):
            RS = sample(PV, PF, mine, PA[mine], int(min(MAX_SAMPLES, max(MIN_SAMPLES, PA[mine].sum() * DENSITY))), rng)
            rd = np.array([gbvh.find_nearest(Vector(p))[3] for p in RS])
        else:
            rd = np.zeros(0)
        top = sorted(hit.items(), key=lambda kv: -kv[1])[:6]
        groups.append(dict(
            group=name, faces=int(len(idx)), area=round(float(a), 2), samples=int(len(S)),
            fwd_mean=round(float(d.mean()), 3), fwd_p50=round(float(np.percentile(d, 50)), 3),
            fwd_p90=round(float(np.percentile(d, 90)), 3), fwd_max=round(float(d.max()), 3),
            cover_0p1=round(float((d <= 0.1).mean()), 4), cover_0p5=round(float((d <= 0.5).mean()), 4),
            cover_2=round(float((d <= 2.0).mean()), 4),
            ps2_faces=int(len(mine)), ps2_area=round(float(PA[mine].sum()), 2),
            rev_mean=round(float(rd.mean()), 3) if len(rd) else None,
            rev_p90=round(float(np.percentile(rd, 90)), 3) if len(rd) else None,
            rev_max=round(float(rd.max()), 3) if len(rd) else None,
            ps2_groups=[[k, v] for k, v in top]))
        if g % 25 == 0:
            print('group', g, name, groups[-1]['fwd_mean'], groups[-1]['ps2_faces'])
    unassigned = int((ps2_face_group < 0).sum())
    ps2_groups = {}
    for pg in range(len(ps2['groups'])):
        idx = np.nonzero(PG == pg)[0]
        if len(idx) == 0:
            continue
        gs = ps2_face_group[idx]
        vals, counts = np.unique(gs, return_counts=True)
        ps2_groups[ps2['groups'][pg]] = dict(faces=int(len(idx)), assigned={
            (gc['groups'][v] if v >= 0 else '-'): int(c) for v, c in zip(vals, counts)},
            lo=PV[PF[idx].ravel()].min(0).round(2).tolist(), hi=PV[PF[idx].ravel()].max(0).round(2).tolist())
    Path(out_path).write_text(json.dumps(dict(assign_units=ASSIGN, unit_cm=10.0, gc_faces=int(len(GF)),
                                              ps2_faces=int(len(PF)), ps2_unassigned_faces=unassigned,
                                              gc_groups=groups, ps2_groups=ps2_groups), indent=1))
    print('done; PS2 faces unassigned', unassigned)


main()
