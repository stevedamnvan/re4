"""Offline, unmodified OBJ Blender preflight; no reduction or promotion. Invoke with Blender --background --factory-startup --offline-mode --disable-autoexec --python this.py -- INPUT.obj PRIVATE_OUTPUT_DIRECTORY."""
import bpy,json,pathlib,sys
args=sys.argv[sys.argv.index('--')+1:];src=pathlib.Path(args[0]);out=pathlib.Path(args[1]);out.mkdir(parents=True,exist_ok=True)
assert not bpy.app.online_access
for addon in list(bpy.context.preferences.addons):
 bpy.ops.preferences.addon_disable(module=addon.module)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.obj_import(filepath=str(src),forward_axis='Y',up_axis='Z',global_scale=1.0,validate_meshes=False)
ref=bpy.data.collections.new('REFERENCE_LOCKED');bpy.context.scene.collection.children.link(ref)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
for obj in meshes:
 for c in list(obj.users_collection): c.objects.unlink(obj)
 ref.objects.link(obj)
 obj.lock_location=(True,)*3;obj.lock_rotation=(True,)*3;obj.lock_scale=(True,)*3
for name in ['CANDIDATE_CONSERVATIVE','CANDIDATE_LEAN','REVIEW_CAMERAS']:
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
bpy.context.scene['qualification']='UNMODIFIED_ROUNDTRIP_ONLY; candidates empty until converter qualification'
bpy.context.scene['axis_contract']='OBJ coordinates unchanged: importer/exporter Y forward, Z up, scale 1; source conversion separate'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'reference-locked.blend'))
bpy.ops.wm.obj_export(filepath=str(out/src.name),forward_axis='Y',up_axis='Z',global_scale=1.0,apply_modifiers=False,export_selected_objects=False,export_uv=True,export_normals=True,export_colors=True,export_materials=True,export_triangulated_mesh=False)
r={'online_access':bpy.app.online_access,'addons':list(bpy.context.preferences.addons.keys()),'objects':[{'name':o.name,'vertices':len(o.data.vertices),'polygons':len(o.data.polygons),'materials':[s.name for s in o.data.materials],'colors':list(o.data.color_attributes.keys()),'bounds':[list(v) for v in o.bound_box]} for o in meshes]}
(out/'blender-report.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
