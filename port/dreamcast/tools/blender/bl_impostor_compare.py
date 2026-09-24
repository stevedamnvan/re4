"""Blender (-b --python): PS2-tree mesh vs its TREE_IMPOSTOR quad at 12, 15 and 30 m in the r100 fog,
640x480, 60-degree fovy.

usage: blender -b --factory-startup --python bl_impostor_compare.py -- <trees_dir> <impostor_dir> <out_dir> \
           <gc bins, comma list>
<trees_dir>: ps2_trees.py --dc-uv output plus ps2-bark-vq.png; <impostor_dir>: tree_impostors.py output
(impostors.json records, preview/<model>.png = the encoded atlas as pvrtex decodes it).
Mesh: the packaged PS2 tree (DC VQ bark), Workbench texture colour under a world-space studio light (a
stand-in for the runtime's per-vertex source lighting), no anti-aliasing (the PVR draws none), depth by BVH
ray cast. Impostor: rasterised as native_static.cpp mesh_impostor draws it: the record's quad through the
tree's axis facing the eye, cell round(azimuth / (360/N)), half-texel inset, bilinear, punch-through at alpha
0.5, plane depth; its colour is the unlit atlas times one tint, the mean of the lit mesh over the flat-lit
mesh in that view (the runtime's mean lit vertex colour).
Fog (both): r100 capture, GX EXP2 start -1089 end 106857, colour 8d8775, PVR table ramp to 100% over the last
20% before far 42743 (native_static.cpp re4dc_fog_frame); background = fog colour.
Writes per GC BIN <out>/COMMON_<b>.png (rows 12/15/30 m; columns mesh, impostor; each row cropped to the
union of both, scaled nearest to about 320 px high) at the worst azimuth for 16 views (half-way between two
cells), and metrics.json (mean |dRGB| over tree pixels, silhouette IoU, projected height; plus an
8-azimuth sweep per distance).
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

W, H = 640, 480
FOVY = math.radians(60.0)
FOG = dict(start=-1089.0, end=106857.0, far=42743.0, rgb=np.array([0x8d, 0x87, 0x75], np.float32) / 255.0)
EYE = 1600.0
DISTANCES = (12000.0, 15000.0, 30000.0)
AZ_SHOW = 101.25          # half-way between two 16-view directions (worst case for N=16)
SWEEP = [11.25 + 45.0 * k for k in range(8)]


def fog(z):
    t = np.clip((z - FOG['start']) / (FOG['end'] - FOG['start']), 0, 1)
    f = 1.0 - np.exp2(-8.0 * t * t)
    ramp = np.clip((z - 0.8 * FOG['far']) / (0.2 * FOG['far']), 0, 1)
    s = ramp * ramp * (3 - 2 * ramp)
    return f + (1 - f) * s


def setup(light):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = light
    sh.color_type = 'TEXTURE'
    sh.show_backface_culling = False
    if light == 'STUDIO':
        sh.use_world_space_lighting = True
        sh.studiolight_rotate_z = math.radians(35.0)
    sc.display.render_aa = 'OFF'
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    cam = bpy.data.cameras.new('cam')
    co = bpy.data.objects.new('cam', cam)
    sc.collection.objects.link(co)
    sc.camera = co
    cam.sensor_fit = 'VERTICAL'
    cam.angle_y = FOVY
    cam.clip_start, cam.clip_end = 100.0, 300000.0
    return sc, co


def load_png(path):
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1].copy()
    bpy.data.images.remove(img)
    return px


def save_png(path, rgb):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(Path(path).stem, w, h, alpha=True)
    rgba = np.concatenate([rgb, np.ones((h, w, 1), np.float32)], axis=2)
    img.pixels[:] = rgba[::-1].ravel().tolist()
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def rays(M):
    """Per-pixel unit ray directions (H, W, 3) for camera matrix M (columns right, up, back)."""
    right, up, back = (np.array(M.col[i][:3]) for i in range(3))
    tv = math.tan(FOVY / 2)
    xs = ((np.arange(W) + 0.5) / W * 2 - 1) * tv * W / H
    ys = (1 - (np.arange(H) + 0.5) / H * 2) * tv
    d = -back[None, None] + xs[None, :, None] * right[None, None] + ys[:, None, None] * up[None, None]
    return d / np.linalg.norm(d, axis=2, keepdims=True), -back


def camera_at(axis, z0, dist, az):
    phi = math.radians(az)
    back = Vector((math.cos(phi), math.sin(phi), 0.0))
    up = Vector((0.0, 0.0, 1.0))
    M = Matrix((up.cross(back), up, back)).transposed().to_4x4()
    M.translation = Vector((axis[0], axis[1], z0 + EYE)) + back * dist
    return M


def mesh_view(sc, co, bvh, M, tmp):
    co.matrix_world = M
    sc.render.filepath = str(tmp)
    bpy.ops.render.render(write_still=True)
    px = load_png(tmp)
    mask = px[..., 3] > 0.5
    d, fwd = rays(M)
    eye = Vector(M.translation)
    z = np.full((H, W), np.inf, np.float32)
    for y, x in zip(*np.nonzero(mask)):
        hit = bvh.ray_cast(eye, Vector(d[y, x]))
        if hit[0] is not None:
            z[y, x] = float(np.dot(np.array(hit[0] - eye), fwd))
        else:
            mask[y, x] = False
    return px[..., :3], mask, z


def impostor_view(atlas, rec, centre, M):
    n, (cw, ch), cols = rec['views'], rec['cell'], rec['cols']
    fw, fh = 2 * rec['half_w'], 2 * rec['half_h']
    d, fwd = rays(M)
    eye = np.array(M.translation)
    c = np.array(centre)
    b = eye[:2] - c[:2]
    phi = math.atan2(b[1], b[0])
    back = np.array([math.cos(phi), math.sin(phi), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    right = np.cross(up, back)
    t = np.dot(c - eye, back) / np.einsum('hwc,c->hw', d, back)
    p = eye[None, None] + t[..., None] * d
    s = np.einsum('hwc,c->hw', p - c, right)
    h = np.einsum('hwc,c->hw', p - c, up)
    u, v = s / fw + 0.5, 0.5 - h / fh
    k = int(round(phi / (2 * math.pi / n))) % n
    x0, y0 = (k % cols) * cw, (k // cols) * ch
    inside = (u >= 0) & (u < 1) & (v >= 0) & (v < 1) & (t > 0)
    tx = x0 + 0.5 + u * (cw - 1) - 0.5   # half-texel inset, texel centres at +0.5
    ty = y0 + 0.5 + v * (ch - 1) - 0.5
    tx, ty = np.clip(tx, x0, x0 + cw - 1), np.clip(ty, y0, y0 + ch - 1)
    ix, iy = np.floor(tx).astype(int), np.floor(ty).astype(int)
    fx, fy = (tx - ix)[..., None], (ty - iy)[..., None]
    ix1, iy1 = np.minimum(ix + 1, x0 + cw - 1), np.minimum(iy + 1, y0 + ch - 1)
    a = atlas
    samp = (a[iy, ix] * (1 - fx) * (1 - fy) + a[iy, ix1] * fx * (1 - fy) + a[iy1, ix] * (1 - fx) * fy +
            a[iy1, ix1] * fx * fy)
    mask = inside & (samp[..., 3] >= 0.5)
    z = np.where(mask, np.einsum('hwc,c->hw', p - eye[None, None], fwd), np.inf)
    return samp[..., :3], mask, z


def composite(rgb, mask, z):
    f = fog(np.where(mask, z, FOG['far']))[..., None]
    out = np.where(mask[..., None], rgb * (1 - f) + FOG['rgb'] * f, FOG['rgb'][None, None])
    return np.clip(out, 0, 1)


def compare(a, b):
    (ca, ma), (cb, mb) = a, b
    u = ma | mb
    if not u.any():
        return None
    return dict(mean_abs_rgb=round(float(np.abs(ca[u] - cb[u]).mean() * 255), 2),
                iou=round(float((ma & mb).sum() / u.sum()), 3))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    src, imp_dir, out = (Path(p) for p in argv[:3])
    bins = [int(x) for x in argv[3].split(',')]
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((imp_dir / 'impostors.json').read_text())
    records = {r['bin']: r for r in manifest['records']}
    metrics = {}
    for b in bins:
        rec = records[b]
        atlas = load_png(imp_dir / 'preview' / ('%d.png' % rec['model']))
        views = {}
        for light in ('STUDIO', 'FLAT'):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            sc, co = setup(light)
            bpy.ops.wm.obj_import(filepath=str(src / ('COMMON_%d.obj' % b)), forward_axis='NEGATIVE_Z', up_axis='Y')
            ob = bpy.context.selected_objects[0]
            for l in ob.data.uv_layers.active.data:
                l.uv = (l.uv[0], 1.0 - l.uv[1])
            m = bpy.data.materials.new('bark')
            m.use_nodes = True
            nt = m.node_tree
            tex = nt.nodes.new('ShaderNodeTexImage')
            tex.image = bpy.data.images.load(str(src / 'ps2-bark-vq.png'))
            tex.interpolation = 'Linear'
            nt.links.new(tex.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
            nt.nodes.active = tex
            ob.data.materials.clear()
            ob.data.materials.append(m)
            Vw = [ob.matrix_world @ v.co for v in ob.data.vertices]
            bvh = BVHTree.FromPolygons(Vw, [tuple(pl.vertices) for pl in ob.data.polygons], epsilon=0.0)
            V = np.array([v[:] for v in Vw])
            lo, hi = V.min(0), V.max(0)
            axis = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
            z0, z1 = float(lo[2]), float(hi[2])
            for dist in DISTANCES:
                for az in [AZ_SHOW] + SWEEP:
                    views[(light, dist, az)] = mesh_view(sc, co, bvh, camera_at(axis, z0, dist, az), out / '_mesh.png')
        centre = (rec['centre'][0], -rec['centre'][2], rec['centre'][1])  # OBJ (x, y, z) -> Blender (x, -z, y)
        rows, info = [], dict(model=rec['model'], height_mm=round(z1 - z0), distances={})
        for dist in DISTANCES:
            shown, sweep = None, []
            for az in [AZ_SHOW] + SWEEP:
                M = camera_at(axis, z0, dist, az)
                lit, flat = views[('STUDIO', dist, az)], views[('FLAT', dist, az)]
                mk = lit[1]
                tint = lit[0][mk].mean(0) / np.maximum(flat[0][mk].mean(0), 1e-3) if mk.any() else np.ones(3)
                irgb, imask, iz = impostor_view(atlas[..., :4], rec, centre, M)
                ref = (composite(lit[0], lit[1], lit[2]), lit[1])
                got = (composite(np.clip(irgb * tint, 0, 1), imask, iz), imask)
                c = compare(ref, got)
                if az == AZ_SHOW:
                    shown = (ref, got)
                    ys = np.nonzero(mk.any(1))[0]
                    info['distances'][str(int(dist))] = dict(
                        projected_height_px=int(ys[-1] - ys[0] + 1) if len(ys) else 0, shown=c)
                else:
                    sweep.append(c)
            info['distances'][str(int(dist))].update(
                sweep_mean_abs_rgb=round(float(np.mean([x['mean_abs_rgb'] for x in sweep if x])), 2),
                sweep_iou=round(float(np.mean([x['iou'] for x in sweep if x])), 3))
            union = shown[0][1] | shown[1][1]
            ys, xs = np.nonzero(union)
            y0, y1 = max(0, ys.min() - 6), min(H, ys.max() + 7)
            x0, x1 = max(0, xs.min() - 6), min(W, xs.max() + 7)
            scale = max(1, int(round(320 / (y1 - y0))))
            rows.append([np.repeat(np.repeat(c[y0:y1, x0:x1], scale, 0), scale, 1) for c, _ in shown])
        width = max(sum(c.shape[1] + 8 for c in r) for r in rows)
        height = sum(r[0].shape[0] + 8 for r in rows)
        canvas = np.full((height, width, 3), 0.15, np.float32)
        y = 0
        for r in rows:
            x = 0
            for c in r:
                canvas[y:y + c.shape[0], x:x + c.shape[1]] = c
                x += c.shape[1] + 8
            y += r[0].shape[0] + 8
        save_png(out / ('COMMON_%d.png' % b), canvas)
        metrics['COMMON/%d' % b] = info
        print('COMMON/%d' % b, json.dumps(info))
    (out / '_mesh.png').unlink(missing_ok=True)
    (out / 'metrics.json').write_text(json.dumps(dict(
        columns=['mesh', 'impostor'], rows_mm=list(DISTANCES), shown_azimuth_deg=AZ_SHOW, sweep_azimuths_deg=SWEEP,
        crop='each row cropped to the union of both, scaled nearest (integer) to about 320 px high',
        fog=dict(type='EXP2', start=FOG['start'], end=FOG['end'], far=FOG['far'], colour='8d8775'),
        trees=metrics), indent=1))


main()
