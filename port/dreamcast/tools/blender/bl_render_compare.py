"""Blender (-b --python): textured GC vs PS2 tree comparison renders.

usage: blender -b --factory-startup --python bl_render_compare.py --          <gc_dir> <ps2_dir> <ps2_dc_dir> <texture_dir> <out_dir> <bins comma list>
  gc_dir      export_room_bins_obj.py output (COMMON_<b>.obj, raw GX UV)
  ps2_dir     ps2_trees.py output without --dc-uv (PS2 UV, raw/255)
  ps2_dc_dir  ps2_trees.py --dc-uv output (the packaged UV layout)
  texture_dir ps2_tree_texture.py output (preview/gc-bark.png, ps2-bark-256x64-source.png, ps2-bark-vq.png)
Paths must be absolute (Blender's OBJ importer; on Windows use native paths).
Per BIN one PNG, left to right:
  GC mesh + GC texture | PS2 mesh + PS2 256x64 texture (PS2 UVs) | PS2 mesh + DC VQ 128x512 (packaged UV layout)
Columns 2 and 3 must look the same (UV/texture transform check). UVs use the GX/GS convention (v=0 is image
row 0), so V is flipped for Blender. Image alpha drives an alpha-clip material (the textures are opaque).
Workbench, flat texture colour + studio light, no fog, same camera for the three.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def load(path):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.obj_import(filepath=str(path), forward_axis='NEGATIVE_Z', up_axis='Y')
    obs = list(bpy.context.selected_objects)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for l in ob.data.uv_layers.active.data:
        l.uv = (l.uv[0], 1.0 - l.uv[1])
    return ob


def material(name, image_path):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(image_path))
    tex.extension = 'REPEAT'
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    try:
        m.blend_method = 'CLIP'
        m.alpha_threshold = 0.5
    except AttributeError:
        pass
    m.use_backface_culling = False
    nt.nodes.active = tex
    return m


def label(text, loc, size):
    bpy.ops.object.text_add(location=loc)
    t = bpy.context.object
    t.data.body = text; t.data.size = size; t.data.align_x = 'CENTER'
    t.rotation_euler = (math.radians(90), 0, 0)
    return t


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    gc_dir, ps2_dir, dc_dir, tex = (Path(p) for p in argv[:4])
    out = Path(argv[4]); out.mkdir(parents=True, exist_ok=True)
    bins = [int(b) for b in argv[5].split(',')]
    for b in bins:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.light = 'STUDIO'
        sc.display.shading.color_type = 'TEXTURE'
        sc.display.shading.show_backface_culling = False
        sc.render.resolution_x, sc.render.resolution_y = 1500, 700
        sc.render.film_transparent = False
        world = bpy.data.worlds.new('w'); sc.world = world
        cols = [('GC mesh + GC texture', gc_dir / ('COMMON_%d.obj' % b), tex / 'preview/gc-bark.png'),
                ('PS2 mesh + PS2 texture', ps2_dir / ('COMMON_%d.obj' % b), tex / 'preview/ps2-bark-256x64-source.png'),
                ('PS2 mesh + DC VQ texture (packaged UVs)', dc_dir / ('COMMON_%d.obj' % b),
                 tex / 'preview/ps2-bark-vq.png')]
        obs = []
        for i, (name, mesh, img) in enumerate(cols):
            ob = load(mesh)
            ob.data.materials.clear(); ob.data.materials.append(material(name, img))
            obs.append(ob)
        # common extent
        lo = Vector((1e18,) * 3); hi = Vector((-1e18,) * 3)
        for ob in obs:
            for v in ob.data.vertices:
                p = ob.matrix_world @ v.co
                lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
        size = hi - lo
        step = max(size.x, size.y) * 1.15
        centre = (lo + hi) / 2
        for i, ob in enumerate(obs):
            ob.location.x += (i - 1) * step
            label(cols[i][0], (centre.x + (i - 1) * step, centre.y - size.y * 0.75, lo.z - size.z * 0.05), size.z * 0.045)
        label('COMMON/%d  GC %d tris | PS2 %d tris' % (b, len(obs[0].data.polygons), len(obs[1].data.polygons)),
              (centre.x, centre.y - size.y * 0.75, hi.z + size.z * 0.08), size.z * 0.05)
        cam = bpy.data.cameras.new('cam'); co = bpy.data.objects.new('cam', cam); sc.collection.objects.link(co)
        sc.camera = co
        cam.type = 'ORTHO'
        cam.ortho_scale = max(3 * step, size.z * 1.35 * 1500 / 700)
        co.location = (centre.x, centre.y - max(size) * 4, centre.z + size.z * 0.02)
        co.rotation_euler = (math.radians(90), 0, 0)
        cam.clip_end = max(size) * 20
        sc.render.filepath = str(out / ('COMMON_%d.png' % b))
        bpy.ops.render.render(write_still=True)
        print('wrote', sc.render.filepath)


if __name__ == '__main__':
    main()
