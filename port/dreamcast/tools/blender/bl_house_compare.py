"""Blender (-b --python): side-by-side renders of an r100 house BIN and its render shell (bl_house_shell.py).

usage: blender -b --factory-startup --python bl_house_compare.py -- <source.obj> <shell.obj> <tex_dir> <shell.png>
           <out_dir> [--dists 3000,8000,20000] [--azimuths 8] [--eye 1600]

Cameras stand at eye height (--eye above the BIN's lowest point) on a circle around the BIN's box, at each
distance (source mm) from the box's nearest face, --azimuths evenly spaced, looking at the box centre
lowered to eye height + 1 m; perspective 60 degree vertical field of view, 640x480 (the source's camera).
Both meshes are drawn identically: Workbench, texture colour under the same studio light, alpha-masked parts
clipped at 50%, no anti-aliasing (the Dreamcast draws none), no back-face culling (either side of a GC
board shows). The source uses its own normals and the GC images per part; the shell (no normals in its OBJ)
is shaded with face normals merged within 45 degrees, as convert_room_bins.py lights it, and its carrier
part uses <shell.png>: pass house_shells.py's preview (the VQ-decoded texture) for an honest comparison.
Writes <out>/<dist>-<az>-{src,shell}.png, <out>/pairs-<dist>.png (source top, shell bottom per view) and
<out>/metrics.json: per view the mean absolute RGB difference (0-255) over pixels either mesh covers and the
silhouette IoU; views are also listed worst first.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

RES = (640, 480)
BG = (0.55, 0.53, 0.46)


def setup():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_backface_culling = False
    sh.use_world_space_lighting = True
    sh.studiolight_rotate_z = math.radians(35.0)
    sc.display.render_aa = 'OFF'
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    return sc


def load(path, tex_dir, shell_png):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis='NEGATIVE_Z', up_axis='Y')
    obs = list(bpy.context.selected_objects)
    for ob in obs:
        if not ob.data.polygons or ob.data.has_custom_normals:
            continue
        # no vn: the runtime (convert_room_bins.replace_source) merges face normals within 45 degrees
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45.0))
    for ob in obs:
        for l in ob.data.uv_layers.active.data:
            l.uv = (l.uv[0], 1.0 - l.uv[1])
    for slot in [s for ob in obs for s in ob.material_slots]:
        m = slot.material
        if m is None:
            continue
        mt = re.match(r'p\d+_t(\d+)_a(\d+)', m.name)
        image, mask = None, None
        if m.name.split('.')[0].endswith('_shell'):
            image = shell_png
        elif mt:
            image = tex_dir / (mt.group(1) + '.png')
            if int(mt.group(2)) != 255:
                mask = tex_dir / (mt.group(2) + '.png')
        if image is None or not image.exists():
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(image), check_existing=True)
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
        nt.nodes.active = t
        if mask is not None and mask.exists():
            k = nt.nodes.new('ShaderNodeTexImage')
            k.image = bpy.data.images.load(str(mask), check_existing=True)
            nt.links.new(k.outputs['Color'], bsdf.inputs['Alpha'])  # GX alpha texture: intensity is the mask
    return obs


def box(path):
    V = []
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):
            x, y, z = (float(t) for t in line.split()[1:4])
            V.append((x, -z, y))  # Blender world
    V = np.array(V)
    return V.min(0), V.max(0)


def render(sc, cam, out):
    sc.camera = cam
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(out))
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1].copy()
    bpy.data.images.remove(img)
    # Composite over the background (the stored PNG too, for viewing).
    rgb = px[..., :3] * px[..., 3:4] + np.array(BG) * (1 - px[..., 3:4])
    save(rgb, out)
    return rgb, px[..., 3] > 0.5


def save(rgb, path):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(Path(path).stem, w, h)
    img.pixels[:] = np.concatenate([rgb, np.ones((h, w, 1), np.float32)], 2)[::-1].ravel().tolist()
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src', type=Path)
    ap.add_argument('shell', type=Path)
    ap.add_argument('tex', type=Path)
    ap.add_argument('png', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--dists', default='3000,8000,20000')
    ap.add_argument('--azimuths', type=int, default=8)
    ap.add_argument('--eye', type=float, default=1600.0)
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    a.out.mkdir(parents=True, exist_ok=True)
    lo, hi = box(a.src)
    centre = (lo + hi) / 2
    half = (hi - lo) / 2
    eye_z = lo[2] + a.eye
    renders = {}
    for which, path in (('src', a.src), ('shell', a.shell)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = setup()
        load(path, a.tex, a.png)
        cams = {}
        for d in (float(x) for x in a.dists.split(',')):
            for k in range(a.azimuths):
                phi = 2 * math.pi * k / a.azimuths
                u = Vector((math.cos(phi), math.sin(phi), 0.0))
                # distance from the box surface along u (box support in that direction)
                reach = abs(u.x) * half[0] + abs(u.y) * half[1]
                pos = Vector((centre[0], centre[1], eye_z)) + u * (reach + d)
                target = Vector((centre[0], centre[1], eye_z + 1000.0))
                back = (pos - target).normalized()
                right = Vector((0, 0, 1)).cross(back).normalized()
                up = back.cross(right)
                M = Matrix((right, up, back)).transposed().to_4x4()
                M.translation = pos
                cd = bpy.data.cameras.new('c')
                cd.sensor_fit = 'VERTICAL'
                cd.angle_y = math.radians(60)
                cd.clip_start, cd.clip_end = 100.0, 200000.0
                co = bpy.data.objects.new('c', cd)
                sc.collection.objects.link(co)
                co.matrix_world = M
                name = '%d-%d' % (int(d), k)
                renders.setdefault(name, {})[which] = render(sc, co, a.out / ('%s-%s.png' % (name, which)))
    metrics = {}
    for name, r in renders.items():
        (s, sm), (t, tm) = r['src'], r['shell']
        either = sm | tm
        diff = float(np.abs(s - t)[either].mean() * 255) if either.any() else 0.0
        iou = float((sm & tm).sum() / max(1, either.sum()))
        metrics[name] = dict(mean_abs_rgb=round(diff, 1), silhouette_iou=round(iou, 3))
    for d in a.dists.split(','):
        names = ['%d-%d' % (int(float(d)), k) for k in range(a.azimuths)]
        top = np.concatenate([renders[n]['src'][0] for n in names], 1)
        bottom = np.concatenate([renders[n]['shell'][0] for n in names], 1)
        sheet = np.concatenate([top, np.zeros((6, top.shape[1], 3), np.float32), bottom], 0)
        save(sheet[:, ::2][::2] if a.azimuths > 4 else sheet, a.out / ('pairs-%d.png' % int(float(d))))
    worst = sorted(metrics, key=lambda n: -metrics[n]['mean_abs_rgb'])
    (a.out / 'metrics.json').write_text(json.dumps(dict(views=metrics, worst_first=worst), indent=1))
    print(json.dumps(dict(worst=[(n, metrics[n]) for n in worst[:4]])))


main()
