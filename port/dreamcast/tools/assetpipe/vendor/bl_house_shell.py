"""Blender (-b --python): low-poly render shell of an r100 house BIN with its GC detail baked to one texture.

usage: blender -b --factory-startup --python bl_house_shell.py -- <FILE_01_<bin>.obj> <tex_dir> <out_dir>
           [--faces 400] [--tex-size 512] [--carrier 0] [--keep-alpha] [--cull-hidden]
           [--method weld|voxel] [--weld 20] [--dissolve 2] [--voxel 80] [--extrude 30] [--ray 300]
           [--normals source|none]

<obj>: export_room_bins_obj.py output in BIN model space (source mm), one material per source part named
p<part>_t<image>_a<alpha image or 255>_f<material flags>; <tex_dir>/<image>.png are the decoded R100.TPL images.

1. hi = the BIN's opaque parts (material flags without the alpha-mask bit 4), textured as the GC draws them
   (GX v flipped for Blender, repeat wrap).
2. shell (--method weld, default) = hi with its UVs and materials dropped and its vertices welded within
   --weld mm (the part and UV splits no longer constrain simplification); --cull-hidden deletes the faces no
   player viewpoint sees from either side (rings 3 m and 12 m out at 1.6/4/10 m height, 16 azimuths; a face
   is hidden only if its centre and eight points near its corners and edge midpoints all are), then planar
   dissolve (--dissolve degrees) and quadric collapse to --faces triangles. --method voxel remeshes a
   solidified copy instead (kept for comparison: it loses thin boards and planar walls).
3. Smart UV project + pack; Cycles bakes hi's texture colour (DIFFUSE, colour only: lighting stays per
   vertex at runtime) onto the shell, selected-to-active, rays from --extrude mm outside looking --ray mm
   inward, into one --tex-size square image.
4. Writes <out>/<stem>.obj: the shell as part --carrier (material p<carrier>_shell; UVs in the GX
   convention for the baked image; --normals none (default): no vn, convert_room_bins.py merges face
   normals within 45 degrees; source: the nearest source corner's GC normal, which streaks where a
   collapsed triangle spans differently lit source faces)
   plus, with --keep-alpha, the source faces of the alpha-masked parts under their own materials; every
   other part is left empty (convert_room_bins.py --lod-substitute draws nothing for it). <out>/<stem>.png
   is the baked texture, <out>/<stem>.json the metrics: triangles, and the distance from the source
   surface to the shell and back (cm; 20k area-weighted samples).
The shell is render-only: collision, placement and part identity stay the GC BIN's.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def import_obj(path):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis='NEGATIVE_Z', up_axis='Y')
    ob = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)  # mesh data = world (Z up)
    if ob.data.uv_layers.active:
        for l in ob.data.uv_layers.active.data:
            l.uv = (l.uv[0], 1.0 - l.uv[1])
    return ob


def texture_materials(ob, tex_dir):
    for slot in ob.material_slots:
        m = slot.material
        mt = re.match(r'p\d+_t(\d+)', m.name) if m else None
        if not mt or not (tex_dir / (mt.group(1) + '.png')).exists():
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(tex_dir / (mt.group(1) + '.png')), check_existing=True)
        t.extension = 'REPEAT'
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])


def select_only(*obs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or obs[0]


def split_alpha(ob):
    """Separate the alpha-masked parts (flag bit 4) into their own object; -> (opaque, alpha or None)."""
    masked = [i for i, s in enumerate(ob.material_slots)
              if s.material and (m := re.search(r'_f(\d+)$', s.material.name)) and int(m.group(1)) & 4]
    if not masked:
        return ob, None
    select_only(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(ob.data)
    for f in bm.faces:
        f.select = f.material_index in masked
    bmesh.update_edit_mesh(ob.data)
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
    alpha = next(o for o in bpy.context.selected_objects if o is not ob)
    return ob, alpha


def apply(ob, mod):
    select_only(ob)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def viewpoints(ob, eye, dists=(3000.0, 12000.0), heights=(1600.0, 4000.0, 10000.0), azimuths=16):
    """Where a player camera can be: rings around the box at eye height and above."""
    V = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    lo, hi = V.min(0), V.max(0)
    c, half = (lo + hi) / 2, (hi - lo) / 2
    out = []
    for d in dists:
        for h in heights:
            for k in range(azimuths):
                phi = 2 * math.pi * (k + 0.5 * (h > heights[0])) / azimuths
                u = Vector((math.cos(phi), math.sin(phi), 0.0))
                reach = abs(u.x) * half[0] + abs(u.y) * half[1]
                out.append(Vector((c[0], c[1], lo[2] + h)) + u * (reach + d))
    return out


def outside_faces(ob, points):
    """Delete the faces no viewpoint sees (walls voxelise as two sheets; the player sees the outer one)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bvh = BVHTree.FromBMesh(bm)
    hidden = []
    for f in bm.faces:
        c = f.calc_center_median()
        # the centre and points near each corner and edge midpoint: a face is hidden only if all are
        corners = [v.co for v in f.verts]
        mids = [(corners[i] + corners[i - 1]) / 2 for i in range(len(corners))]
        samples = [c] + [c.lerp(q, 0.85) for q in corners + mids]
        seen = False
        for n in (f.normal, -f.normal):  # either side: GC boards are single-sided with mixed winding
            ranked = sorted(points, key=lambda p: -(p - c).normalized().dot(n))
            for o in samples:
                for p in ranked:
                    d = p - o
                    if d.dot(n) <= 0:
                        break
                    dist = d.length
                    d /= dist
                    if bvh.ray_cast(o + n * 5.0, d, dist)[0] is None:
                        seen = True
                        break
                if seen:
                    break
            if seen:
                break
        if not seen:
            hidden.append(f)
    bmesh.ops.delete(bm, geom=hidden, context='FACES')
    bm.to_mesh(ob.data)
    bm.free()
    return len(hidden)


def surface_samples(ob, n, seed=2):
    me = ob.data
    me.calc_loop_triangles()
    V = np.array([ob.matrix_world @ v.co for v in me.vertices])
    T = np.array([t.vertices[:] for t in me.loop_triangles])
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(T), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    return a[pick] + (b[pick] - a[pick]) * u[:, None] + (c[pick] - a[pick]) * v[:, None]


def distances(src, dst, n=20000):
    bm = bmesh.new()
    bm.from_mesh(dst.data)
    bm.transform(dst.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    d = np.array([(bvh.find_nearest(Vector(p))[3] or 0.0) for p in surface_samples(src, n)]) / 10.0  # mm -> cm
    bm.free()
    return dict(p50=round(float(np.percentile(d, 50)), 1), p90=round(float(np.percentile(d, 90)), 1),
                p99=round(float(np.percentile(d, 99)), 1), max=round(float(d.max()), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('obj', type=Path)
    ap.add_argument('tex', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--voxel', type=float, default=80.0)
    ap.add_argument('--faces', type=int, default=400)
    ap.add_argument('--tex-size', type=int, default=512)
    ap.add_argument('--carrier', type=int, default=0)
    ap.add_argument('--keep-alpha', action='store_true')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--method', choices=['weld', 'voxel'], default='weld')
    ap.add_argument('--weld', type=float, default=20.0, help='mm')
    ap.add_argument('--dissolve', type=float, default=2.0, help='planar dissolve angle, degrees')
    ap.add_argument('--cull-hidden', action='store_true')
    ap.add_argument('--normals', choices=['source', 'none'], default='none')
    ap.add_argument('--extrude', type=float, default=30.0, help='bake cage extrusion, mm')
    ap.add_argument('--ray', type=float, default=300.0, help='bake max ray distance, mm')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    a.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src = import_obj(a.obj)
    texture_materials(src, a.tex)
    source_tris = sum(len(p.vertices) - 2 for p in src.data.polygons)
    hi, alpha = split_alpha(src)

    select_only(hi)
    bpy.ops.object.duplicate()
    lo = bpy.context.selected_objects[0]
    lo.data.materials.clear()
    for uv in list(lo.data.uv_layers):  # the bake replaces them: seams no longer constrain the collapse
        lo.data.uv_layers.remove(uv)
    remeshed = hidden = 0
    if a.method == 'voxel':
        mod = lo.modifiers.new('s', 'SOLIDIFY')  # single-sided boards need a volume to voxelise
        mod.thickness, mod.offset = 2.5 * a.voxel, -1.0
        apply(lo, mod)
        mod = lo.modifiers.new('r', 'REMESH')
        mod.mode, mod.voxel_size, mod.adaptivity = 'VOXEL', a.voxel, 0.0
        apply(lo, mod)
        remeshed = len(lo.data.polygons)
        hidden = outside_faces(lo, viewpoints(hi, 1600.0))
    else:  # weld: the GC surface itself, welded across part/UV splits, faces no viewpoint sees removed
        select_only(lo)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=a.weld)
        bpy.ops.mesh.delete_loose()
        bpy.ops.object.mode_set(mode='OBJECT')
        remeshed = len(lo.data.polygons)
        hidden = outside_faces(lo, viewpoints(hi, 1600.0)) if a.cull_hidden else 0
    mod = lo.modifiers.new('p', 'DECIMATE')
    mod.decimate_type, mod.angle_limit = 'DISSOLVE', math.radians(a.dissolve)
    apply(lo, mod)
    mod = lo.modifiers.new('t', 'TRIANGULATE')
    apply(lo, mod)
    n = len(lo.data.polygons)
    if n > a.faces:
        mod = lo.modifiers.new('c', 'DECIMATE')
        mod.decimate_type, mod.ratio, mod.use_collapse_triangulate = 'COLLAPSE', a.faces / n, True
        apply(lo, mod)
    shell_tris = len(lo.data.polygons)

    # UVs and bake.
    lo.data.uv_layers.new(name='bake')
    select_only(lo)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.004, area_weight=1.0)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    image = bpy.data.images.new('shell', a.tex_size, a.tex_size, alpha=False)
    m = bpy.data.materials.new('p%d_shell' % a.carrier)
    m.use_nodes = True
    t = m.node_tree.nodes.new('ShaderNodeTexImage')
    t.image = image
    m.node_tree.nodes.active = t
    lo.data.materials.append(m)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = a.samples
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.use_cage = False
    # Rays start --extrude outside the shell and look up to --ray inward: short enough that detail in
    # front of a wall (shutters, posts) is not projected onto the wall behind it.
    sc.render.bake.cage_extrusion = a.extrude
    sc.render.bake.max_ray_distance = a.ray
    sc.render.bake.margin = 8
    select_only(hi, lo, active=lo)
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})
    image.filepath_raw = str(a.out / (a.obj.stem + '.png'))
    image.file_format = 'PNG'
    image.save()

    metrics = dict(source=a.obj.name, source_triangles=source_tris, method=a.method, voxel_mm=a.voxel, weld_mm=a.weld, remeshed_faces=remeshed,
                   hidden_faces_removed=hidden, shell_triangles=shell_tris, texture=[a.tex_size, a.tex_size],
                   alpha_triangles=sum(len(p.vertices) - 2 for p in alpha.data.polygons) if alpha else 0,
                   source_to_shell_cm=distances(hi, lo), shell_to_source_cm=distances(lo, hi))

    # --normals source: the shell takes the GC vertex normal of the nearest source face corner.
    if a.normals == 'source':
        mod = lo.modifiers.new('n', 'DATA_TRANSFER')
        mod.object = hi
        mod.use_loop_data = True
        mod.data_types_loops = {'CUSTOM_NORMAL'}
        mod.loop_mapping = 'POLYINTERP_NEAREST'
        apply(lo, mod)

    # Export: shell (+ alpha parts), GX v convention.
    for l in lo.data.uv_layers.active.data:
        l.uv = (l.uv[0], 1.0 - l.uv[1])
    export = [lo]
    if alpha and a.keep_alpha:
        for l in alpha.data.uv_layers.active.data:
            l.uv = (l.uv[0], 1.0 - l.uv[1])
        export.append(alpha)
    select_only(*export)
    bpy.ops.wm.obj_export(filepath=str(a.out / (a.obj.stem + '.obj')), export_selected_objects=True,
                          forward_axis='NEGATIVE_Z', up_axis='Y', export_normals=a.normals == 'source', export_uv=True,
                          export_materials=True, export_triangulated_mesh=True, apply_modifiers=True)
    (a.out / (a.obj.stem + '.json')).write_text(json.dumps(metrics, indent=1))
    print(json.dumps(metrics))


main()
