"""Blender headless reduction of r100 BIN render meshes (model-space OBJ from export_room_bins_obj.py).

usage: blender -b --factory-startup --python bl_decimate.py -- <in_dir> <out_root> <spec.json>
(e.g. spec r100-planar2.json: planar dissolve at 2 degrees on the static BINs of the chosen r100 set)
spec: {"<variant>": {"keys": ["COMMON_9", ...], "ops": [["planar", deg] | ["collapse", ratio]]}}
Per variant/key: import (OBJ axes round-trip unchanged), apply ops on a copy, transfer the source's
custom normals back (nearest-face interpolated) so runtime lighting keeps authored normals,
export OBJ (tris, uv, normals, one usemtl per source part) to <out_root>/<variant>/<KEY>.obj - a
replacement directory for convert_room_bins.py --lod-substitute - and
measure: triangles, sampled surface distance both ways (model units = source mm), UV deviation at
the nearest source point (texture repeats), normal deviation (deg).
"""
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

SAMPLES = 4000


def import_obj(path):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis='NEGATIVE_Z', up_axis='Y', validate_meshes=False)
    ob = bpy.context.selected_objects[0]
    return ob


def tri_data(ob):
    """World-free (object space) triangles: positions, uvs, normals per corner."""
    me = ob.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data if me.uv_layers.active else None
    V = np.array([v.co[:] for v in me.vertices])
    tris, uvs, nrm = [], [], []
    cn = me.corner_normals
    for lt in me.loop_triangles:
        tris.append(lt.vertices[:])
        uvs.append([uv[l].uv[:] for l in lt.loops] if uv else [(0, 0)] * 3)
        nrm.append([cn[l].vector[:] for l in lt.loops])
    return V, np.array(tris, dtype=np.int64), np.array(uvs), np.array(nrm)


def sample(V, T, n, rng):
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    A = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    if A.sum() <= 0:
        return np.zeros((0, 3)), np.zeros(0, dtype=np.int64)
    pick = rng.choice(len(T), size=n, p=A / A.sum())
    r1, r2 = rng.random(n), rng.random(n); s = np.sqrt(r1)
    P = (1 - s)[:, None] * a[pick] + (s * (1 - r2))[:, None] * b[pick] + (s * r2)[:, None] * c[pick]
    return P, pick


def interp(V, T, UV, N, fi, p):
    a, b, c = (Vector(V[T[fi, k]]) for k in range(3))
    uv = [Vector((UV[fi, k, 0], UV[fi, k, 1], 0)) for k in range(3)]
    nn = [Vector(N[fi, k]) for k in range(3)]
    u = barycentric_transform(Vector(p), a, b, c, *uv)
    n = barycentric_transform(Vector(p), a, b, c, *nn)
    return (u.x, u.y), n


def measure(src, dst, rng):
    V0, T0, U0, N0 = src; V1, T1, U1, N1 = dst
    b0 = BVHTree.FromPolygons([Vector(p) for p in V0], T0.tolist(), all_triangles=True)
    b1 = BVHTree.FromPolygons([Vector(p) for p in V1], T1.tolist(), all_triangles=True)
    P, pick = sample(V1, T1, SAMPLES, rng)
    fwd, duv, dn = [], [], []
    for p, fi in zip(P, pick):
        loc, nrm, f0, d = b0.find_nearest(Vector(p))
        fwd.append(d)
        uv1, n1 = interp(V1, T1, U1, N1, fi, p)
        uv0, n0 = interp(V0, T0, U0, N0, f0, loc)
        duv.append(math.hypot(uv1[0] - uv0[0], uv1[1] - uv0[1]))
        if n1.length > 0 and n0.length > 0:
            dn.append(math.degrees(n1.normalized().angle(n0.normalized(), 0.0)))
    P0, _ = sample(V0, T0, SAMPLES, rng)
    rev = [b1.find_nearest(Vector(p))[3] for p in P0]
    q = lambda x, f: round(float(np.percentile(x, f)), 3) if len(x) else None
    return dict(fwd_mean=round(float(np.mean(fwd)), 3), fwd_p90=q(fwd, 90), fwd_max=round(float(np.max(fwd)), 3),
                rev_mean=round(float(np.mean(rev)), 3), rev_p90=q(rev, 90), rev_max=round(float(np.max(rev)), 3),
                uv_mean=round(float(np.mean(duv)), 4), uv_p90=q(duv, 90), normal_mean_deg=round(float(np.mean(dn)), 2) if dn else None,
                normal_p90_deg=q(dn, 90))


def reduce(ob, ops):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.duplicate()
    dup = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = dup
    for kind, val in ops:
        m = dup.modifiers.new('dec', 'DECIMATE')
        if kind == 'planar':
            m.decimate_type = 'DISSOLVE'
            m.angle_limit = math.radians(val)
            m.delimit = {'MATERIAL', 'SEAM', 'SHARP', 'UV'}
            m.use_dissolve_boundaries = False
        elif kind == 'collapse':
            m.decimate_type = 'COLLAPSE'
            m.ratio = val
            m.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=m.name)
    tri = dup.modifiers.new('tri', 'TRIANGULATE')
    tri.min_vertices = 4
    bpy.ops.object.modifier_apply(modifier=tri.name)
    dt = dup.modifiers.new('nrm', 'DATA_TRANSFER')
    dt.object = ob
    dt.use_loop_data = True
    dt.data_types_loops = {'CUSTOM_NORMAL'}
    dt.loop_mapping = 'POLYINTERP_NEAREST'
    try:
        bpy.ops.object.modifier_apply(modifier=dt.name)
    except Exception as e:  # keep going without transferred normals
        print('normal transfer failed', e)
        dup.modifiers.remove(dt)
    return dup


def export(ob, path):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.obj_export(filepath=str(path), export_selected_objects=True, forward_axis='NEGATIVE_Z', up_axis='Y',
                          export_uv=True, export_normals=True, export_materials=True, export_triangulated_mesh=True,
                          export_object_groups=False, export_material_groups=False, apply_modifiers=True)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    in_dir, out_root, spec = Path(argv[0]), Path(argv[1]), json.loads(Path(argv[2]).read_text())
    rng = np.random.default_rng(7)
    report = {}
    for variant, sp in spec.items():
        od = out_root / variant; od.mkdir(parents=True, exist_ok=True)
        for key in sp['keys']:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            ob = import_obj(in_dir / (key + '.obj'))
            src = tri_data(ob)
            dup = reduce(ob, sp['ops'])
            dst = tri_data(dup)
            export(dup, od / (key + '.obj'))
            m = measure(src, dst, rng)
            m.update(src_tris=int(len(src[1])), tris=int(len(dst[1])), ops=sp['ops'])
            report.setdefault(variant, {})[key] = m
            print(variant, key, m['src_tris'], '->', m['tris'], 'fwd', m['fwd_mean'], 'rev_p90', m['rev_p90'],
                  'uv', m['uv_mean'], 'n', m['normal_mean_deg'])
            sys.stdout.flush()
    (out_root / 'blender-report.json').write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
