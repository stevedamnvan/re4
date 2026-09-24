"""Blender (-b --python): bake impostor view atlases for the r100 PS2 trees (game TREE_IMPOSTOR=1).

usage: blender -b --factory-startup --python bl_impostor_bake.py -- <in_dir> <out_dir>
           [--views 16] [--cell 128] [--light flat|studio]

in_dir: ps2_trees.py --dc-uv output (COMMON_<b>.obj, ps2-trees.json) plus ps2-bark-vq.png, the Dreamcast bark
as the hardware samples it (ps2_tree_texture.py preview). The GC BINs that use one PS2 model are uniform
scalings of it, so each PS2 model gets one atlas, baked from its first GC BIN.

Per model: `views` orthographic renders around the vertical axis at elevation 0 (cylindrical billboard).
View k looks along -back_k, back_k = (cos a, sin a, 0) in Blender world (= (cos a, 0, -sin a) in the OBJ's
model space), a = 360k/views, framed on the box's vertical centre line: height = box height, width = twice
the largest horizontal distance from that line (any view fits), 2% margin. Cells are 1:2 (w:h) when that
frame is at most half as wide as tall, else 1:1; `cell` texels high; cells fill rows of an atlas at most
1024 wide, power-of-two sides, row 0 at the top.
  * --light flat (default): texture colour only. The runtime modulates the atlas by the mesh's mean lit
    vertex colour, as its geometry modulates the same texture by per-vertex lighting.
  * Workbench, Standard view transform, 4x4 supersampled and box-filtered (coverage-weighted colour);
  * alpha cut at 50% coverage (punch-through); the colours of cut texels are dilated into their transparent
    neighbours so bilinear filtering at the silhouette never pulls in black.
Writes <out>/<model>.png and <out>/impostors.json (per model: reference BIN, box, cell aspect, atlas layout).
tools/tree_impostors.py encodes the atlases (4bpp palettised VQ) and writes the per-BIN records.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

SS = 4


def load(path, image):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis='NEGATIVE_Z', up_axis='Y')
    ob = bpy.context.selected_objects[0]
    for l in ob.data.uv_layers.active.data:  # GX/GS v=0 is image row 0; Blender v=0 is the bottom row
        l.uv = (l.uv[0], 1.0 - l.uv[1])
    m = bpy.data.materials.new('bark')
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(image))
    tex.extension = 'REPEAT'
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    nt.nodes.active = tex
    m.use_backface_culling = False
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return ob


def scene_setup(light):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'FLAT' if light == 'flat' else 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_backface_culling = False
    if light != 'flat':
        sh.use_world_space_lighting = True
        sh.studiolight_rotate_z = math.radians(35.0)
    sc.display.render_aa = 'OFF'
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    return sc


def frame_of(ob):
    """-> axis (x, y), z0, z1, radius (Blender world = model units)."""
    V = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    lo, hi = V.min(0), V.max(0)
    ax, ay = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    r = float(np.sqrt(((V[:, 0] - ax) ** 2 + (V[:, 1] - ay) ** 2).max()))
    return (float(ax), float(ay)), float(lo[2]), float(hi[2]), r


def render_rgba(sc, path):
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]  # top row first
    bpy.data.images.remove(img)
    return px


def downsample(px, ss):
    h, w = px.shape[0] // ss, px.shape[1] // ss
    blk = px.reshape(h, ss, w, ss, 4)
    a = blk[..., 3].mean(axis=(1, 3))
    rgb = (blk[..., :3] * blk[..., 3:4]).sum(axis=(1, 3)) / np.maximum(blk[..., 3].sum(axis=(1, 3)), 1e-6)[..., None]
    return rgb, a


def dilate(rgb, mask, steps=4):
    rgb = rgb.copy()
    m = mask.copy()
    for _ in range(steps):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(m.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sm = np.roll(np.roll(m, dy, 0), dx, 1)
            acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * sm[..., None]
            cnt += sm
        grow = (~m) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][..., None]
        m = m | grow
    return rgb


def pow2(n):
    p = 8
    while p < n:
        p *= 2
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--views', type=int, default=16)
    ap.add_argument('--cell', type=int, default=128, help='cell height in texels')
    ap.add_argument('--light', choices=['flat', 'studio'], default='flat')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
    a.out.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((a.src / 'ps2-trees.json').read_text())['mapping']
    models = {}
    for b in sorted(mapping, key=int):
        models.setdefault(mapping[b]['ps2_bin'], int(b))
    n, ch = a.views, a.cell
    report = dict(views=n, cell_h=ch, light=a.light, supersample=SS, alpha_cut=0.5, models={})
    for model, b in sorted(models.items()):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = scene_setup(a.light)
        ob = load(a.src / ('COMMON_%d.obj' % b), a.src / 'ps2-bark-vq.png')
        (ax, ay), z0, z1, r = frame_of(ob)
        H, W = (z1 - z0) * 1.02, 2 * r * 1.02
        aspect = 0.5 if W <= 0.5 * H else 1.0  # cell width / height
        cam = bpy.data.cameras.new('cam')
        co = bpy.data.objects.new('cam', cam)
        sc.collection.objects.link(co)
        sc.camera = co
        cam.type = 'ORTHO'
        cam.clip_start, cam.clip_end = 1.0, 20.0 * max(H, W)
        cw = int(ch * aspect)
        fh = max(H, W / aspect)             # frame height; width = fh * aspect
        cam.ortho_scale = fh                # the larger (vertical) render side
        sc.render.resolution_x, sc.render.resolution_y = cw * SS, ch * SS
        cols = min(n, 1024 // cw)
        rows = -(-n // cols)
        aw, ah = pow2(cols * cw), pow2(rows * ch)
        atlas = np.zeros((ah, aw, 4), dtype=np.float32)
        for k in range(n):
            phi = 2 * math.pi * k / n
            back = Vector((math.cos(phi), math.sin(phi), 0.0))
            up = Vector((0.0, 0.0, 1.0))
            M = Matrix((up.cross(back), up, back)).transposed().to_4x4()
            M.translation = Vector((ax, ay, (z0 + z1) / 2)) + back * 10.0 * max(H, W)
            co.matrix_world = M
            rgb, cover = downsample(render_rgba(sc, a.out / '_view.png'), SS)
            mask = cover >= 0.5
            y, x = (k // cols) * ch, (k % cols) * cw
            atlas[y:y + ch, x:x + cw] = np.concatenate([dilate(rgb, mask), mask[..., None].astype(np.float32)], axis=2)
        img = bpy.data.images.new(str(model), aw, ah, alpha=True)
        img.pixels[:] = atlas[::-1].ravel().tolist()
        img.filepath_raw = str(a.out / ('%d.png' % model))
        img.file_format = 'PNG'
        img.save()
        report['models'][str(model)] = dict(reference_gc_bin=b, cell_aspect=aspect, cell=[cw, ch], cols=cols,
                                            rows=rows, atlas=[aw, ah], frame_h=fh, coverage=float(atlas[..., 3].mean()))
        print('baked', model, 'from COMMON_%d' % b, 'cell %dx%d atlas %dx%d' % (cw, ch, aw, ah))
    (a.out / '_view.png').unlink(missing_ok=True)
    (a.out / 'impostors.json').write_text(json.dumps(report, indent=1))


main()
