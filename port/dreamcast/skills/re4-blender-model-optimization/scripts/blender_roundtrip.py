"""Offline unmodified OBJ exchange; source-format validation is separate."""
import argparse
import json
from pathlib import Path
import sys


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_obj', type=Path)
    parser.add_argument('output_directory', type=Path,
                        help='New private directory; existing output is refused')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return parser.parse_args(argv)


def main():
    args = parse_args()
    source = args.input_obj.resolve()
    output = args.output_directory.resolve()
    if not source.is_file() or source.suffix.lower() != '.obj':
        raise ValueError('Input must be an existing private OBJ file')
    if output.exists():
        raise FileExistsError('Use a new output directory to preserve evidence')
    import bpy
    if bpy.app.online_access:
        raise RuntimeError('Launch Blender with --offline-mode')
    for addon in list(bpy.context.preferences.addons):
        bpy.ops.preferences.addon_disable(module=addon.module)
    output.mkdir(parents=True)
    api = {name: [p.identifier for p in getattr(bpy.ops.wm, name).get_rna_type().properties]
           for name in ('obj_import', 'obj_export')}
    (output / 'api.json').write_text(json.dumps(api, indent=2))
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    bpy.ops.wm.obj_import(filepath=str(source), forward_axis='Y', up_axis='Z',
                          global_scale=1.0, validate_meshes=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise ValueError('OBJ contains no meshes')
    reference = bpy.data.collections.new('REFERENCE_LOCKED')
    bpy.context.scene.collection.children.link(reference)
    for obj in meshes:
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        reference.objects.link(obj)
        obj.lock_location = obj.lock_rotation = obj.lock_scale = (True,) * 3
    for name in ('CANDIDATE_CONSERVATIVE', 'CANDIDATE_LEAN', 'REVIEW_CAMERAS'):
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    bpy.context.scene['qualification'] = 'UNMODIFIED EXCHANGE ONLY; candidates empty'
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'reference-locked.blend'))
    bpy.ops.wm.obj_export(filepath=str(output / source.name), forward_axis='Y',
                          up_axis='Z', global_scale=1.0, apply_modifiers=False,
                          export_selected_objects=False, export_uv=True,
                          export_normals=True, export_colors=True,
                          export_materials=True, export_triangulated_mesh=False)
    report = {
        'version': bpy.app.version_string,
        'online_access': bpy.app.online_access,
        'addons': list(bpy.context.preferences.addons.keys()),
        'source': str(source),
        'axis_contract': 'Y forward/Z up, scale 1; source mapping requires separate proof',
        'qualification': 'Not source-format or visual acceptance',
        'objects': [{'name': o.name, 'vertices': len(o.data.vertices),
                     'polygons': len(o.data.polygons),
                     'materials': [m.name for m in o.data.materials],
                     'colors': list(o.data.color_attributes.keys()),
                     'bounds': [list(v) for v in o.bound_box]} for o in meshes],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()