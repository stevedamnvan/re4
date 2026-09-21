"""Offline protected static decimation experiment. Private outputs only; no promotion."""
import bpy,bmesh,pathlib,sys,json,math
from mathutils.bvhtree import BVHTree
root=pathlib.Path(sys.argv[sys.argv.index('--')+1]);out=root/'candidates';out.mkdir(exist_ok=True)
assert not bpy.app.online_access
for addon in list(bpy.context.preferences.addons):bpy.ops.preferences.addon_disable(module=addon.module)
report={}
for ident in [0,1,4,6,7,9]:
 name=f'{ident:04d}';src=root/'set-tool'/f'{name}.obj';folder=out/name;folder.mkdir(exist_ok=True)
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 for mat in list(bpy.data.materials):bpy.data.materials.remove(mat)
 for col in list(bpy.data.collections):bpy.data.collections.remove(col)
 cols={}
 for label in ['REFERENCE_LOCKED','CANDIDATE_CONSERVATIVE','CANDIDATE_LEAN','REVIEW_CAMERAS']:
  cols[label]=bpy.data.collections.new(label);bpy.context.scene.collection.children.link(cols[label])
 bpy.ops.wm.obj_import(filepath=str(src),forward_axis='Y',up_axis='Z',global_scale=1,validate_meshes=False)
 obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
 for col in list(obj.users_collection):col.objects.unlink(obj)
 cols['REFERENCE_LOCKED'].objects.link(obj);obj.name=name+'_REFERENCE'
 obj.lock_location=(True,)*3;obj.lock_rotation=(True,)*3;obj.lock_scale=(True,)*3
 mesh=obj.data; mesh.calc_loop_triangles();uv=mesh.uv_layers.active.data
 edges={e.index:[] for e in mesh.edges};normals=mesh.corner_normals
 for poly in mesh.polygons:
  for li in poly.loop_indices:
   loop=mesh.loops[li];nxt=poly.loop_start+(li-poly.loop_start+1)%poly.loop_total
   edges[loop.edge_index].append((poly,{loop.vertex_index:(tuple(uv[li].uv),tuple(normals[li].vector)),mesh.loops[nxt].vertex_index:(tuple(uv[nxt].uv),tuple(normals[nxt].vector))}))
 protected=set();protected_edges=[]
 for edge in mesh.edges:
  pair=edges[edge.index];protect=len(pair)!=2
  if not protect:
   protect=pair[0][0].material_index!=pair[1][0].material_index or pair[0][0].normal.angle(pair[1][0].normal)>math.radians(30)
   for vi in edge.vertices:
    a,b=pair[0][1][vi],pair[1][1][vi]
    if any(abs(x-y)>1e-5 for x,y in zip(a[0],b[0])) or sum(x*y for x,y in zip(a[1],b[1]))<math.cos(math.radians(30)):protect=True
  if protect:protected.update(edge.vertices);protected_edges.append(tuple(edge.vertices))
 for axis in range(3):
  for value in [min(v.co[axis] for v in mesh.vertices),max(v.co[axis] for v in mesh.vertices)]:
   protected.update(v.index for v in mesh.vertices if abs(v.co[axis]-value)<1e-6)
 key=lambda v:tuple(round(x,5) for x in v)
 required={key(mesh.vertices[i].co) for i in protected}
 req_edges={tuple(sorted(key(mesh.vertices[i].co) for i in e)) for e in protected_edges}
 refcoords=[v.co.copy() for v in mesh.vertices];reftris=[tuple(t.vertices) for t in mesh.loop_triangles];refbvh=BVHTree.FromPolygons(refcoords,reftris,all_triangles=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'reference-locked.blend'))
 arms={}
 for label,ratio in [('CANDIDATE_CONSERVATIVE',.8),('CANDIDATE_LEAN',.6)]:
  cand=obj.copy();cand.data=obj.data.copy();cols[label].objects.link(cand);cand.name=name+'_'+label
  group=cand.vertex_groups.new(name='REDUCIBLE_INTERIOR');safe=[i for i in range(len(mesh.vertices)) if i not in protected]
  if safe:group.add(safe,1,'REPLACE')
  mod=cand.modifiers.new('Constrained reduction','DECIMATE');mod.ratio=ratio;mod.vertex_group=group.name;mod.vertex_group_factor=1;mod.use_collapse_triangulate=True
  bpy.context.view_layer.objects.active=cand;bpy.ops.object.select_all(action='DESELECT');cand.select_set(True)
  bpy.ops.object.modifier_apply(modifier=mod.name) if safe else cand.modifiers.remove(mod)
  cm=cand.data;cm.calc_loop_triangles();coords=[v.co.copy() for v in cm.vertices];tris=[tuple(t.vertices) for t in cm.loop_triangles]
  bvh=BVHTree.FromPolygons(coords,tris,all_triangles=True)
  samples=lambda vs,ts:list(vs)+[sum((vs[i] for i in t),vs[0]*0)/3 for t in ts]
  distance=max([refbvh.find_nearest(p)[3] for p in samples(coords,tris)]+[bvh.find_nearest(p)[3] for p in samples(refcoords,reftris)])
  current={key(v.co) for v in cm.vertices};current_edges={tuple(sorted(key(cm.vertices[i].co) for i in e.vertices)) for e in cm.edges}
  arm=folder/label;arm.mkdir(exist_ok=True)
  bpy.ops.wm.obj_export(filepath=str(arm/f'{name}.obj'),forward_axis='Y',up_axis='Z',global_scale=1,export_selected_objects=True,apply_modifiers=False,export_uv=True,export_normals=True,export_colors=True,export_materials=True,export_triangulated_mesh=True)
  arms[label]={'target_ratio':ratio,'vertices':len(coords),'triangles':len(tris),'protected_vertices':len(required),'protected_vertices_missing':len(required-current),'protected_edges_missing':len(req_edges-current_edges),'sampled_bidirectional_distance_obj_units':distance,'source_mm_per_obj_unit':100,'sampled_distance_mm':distance*100,'safe_interior_vertices':len(safe),'boundary_gate':not(required-current) and not(req_edges-current_edges),'distance_limit_mm':10 if ratio==.8 else 20,'distance_gate':distance*100<=(10 if ratio==.8 else 20)}
  cand.hide_render=True
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'selectable-candidates.blend'))
 report[name]={'reference_triangles':len(reftris),'arms':arms}
(out/'geometry-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))