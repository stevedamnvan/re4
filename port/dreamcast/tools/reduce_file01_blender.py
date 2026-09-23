"""Private FILE_01 visual candidates feeding the existing room converter.

Run in an offline, factory Blender session. This is an asset-edit recipe, not a
BIN/package converter. Transparent/unresolved materials retain the original source triangles;
OBJ decimal serialization is not a byte-identity claim. No source collision, scripts, owners or runtime code is edited.
"""
import argparse, collections, hashlib, importlib.util, json, math, pathlib, sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',type=pathlib.Path,required=True)
    ap.add_argument('--private',type=pathlib.Path,required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True)
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    assert not bpy.app.online_access, 'Local-only session required'
    for addon in list(bpy.context.preferences.addons):
        bpy.ops.preferences.addon_disable(module=addon.module)
    a.output.mkdir(exist_ok=False)
    converter=a.repo/'port/dreamcast/tools/convert_room_obj.py'
    spec=importlib.util.spec_from_file_location('room_converter',converter)
    c=importlib.util.module_from_spec(spec);sys.modules[spec.name]=c;spec.loader.exec_module(c)
    objpath=a.private/'FILE_01.obj'
    baseline=json.loads((a.private/'reference-package.json').read_text())
    assert sha(objpath)==baseline['source_sha256']
    parsed=c.parse_obj(objpath,retain_source_indices=True)
    assert len(parsed['group_order'])==50 and parsed['triangles']==24983
    assert all(n.startswith('FILE_01#') for n in parsed['group_order'])
    # Keep soft/binary alpha and unresolved material state entirely unchanged.
    materials=json.loads((a.private/'material-cost.json').read_text())
    opaque={m['material'] for m in materials['materials'] if not m.get('alpha',True) and 'payload_bytes' in m}
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):bpy.data.collections.remove(col)
    cols={}
    for name in ('REFERENCE_LOCKED','CANDIDATE_CONSERVATIVE','CANDIDATE_LEAN','REVIEW_CAMERAS'):
        cols[name]=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(cols[name])
    inputs=[];report={'version':bpy.app.version_string,'build':bpy.app.build_hash.decode(),
        'source_sha256':sha(objpath),'converter_sha256':sha(converter),'online_access':False,
        'source_groups':len(parsed['group_order']),'source_triangles':parsed['triangles'],
        'source_units_to_meters':baseline['source_scale'],
        'limits':{'reference_position_obj':0.0002,'reference_uv':0.00005,'reference_normal_degrees':0.1,
                  'conservative_surface_m':0.10,'lean_surface_m':0.25},
        'arms':{},'batches':[]}
    position_error=uv_error=normal_error=0.0
    for bi,batch in enumerate(parsed['batches']):
        ids={};coords=[];faces=[];normals=[];uvs=[]
        for at in range(0,len(batch.indices),3):
            face=[]
            for vi in batch.indices[at:at+3]:
                v=parsed['vertices'][vi];source_id=parsed['vertex_source_indices'][vi][0]
                if source_id not in ids:ids[source_id]=len(coords);coords.append(v[:3])
                face.append(ids[source_id]);normals.append(v[3:6]);uvs.append(v[6:8])
            faces.append(face)
        mesh=bpy.data.meshes.new(f'batch_{bi:03d}');mesh.from_pydata(coords,[],faces);mesh.update()
        uv=mesh.uv_layers.new(name='SourceUV')
        for i,val in enumerate(uvs):uv.data[i].uv=val
        # Blender's flat-face path ignores custom corner normals. Source
        # discontinuities are carried explicitly by the custom corner array.
        for poly in mesh.polygons:poly.use_smooth=True
        mesh.normals_split_custom_set(normals)
        ob=bpy.data.objects.new(mesh.name,mesh);cols['REFERENCE_LOCKED'].objects.link(ob)
        ob['source_group']=batch.group;ob['source_material']=batch.material;ob['source_batch']=bi
        ob.lock_location=(True,)*3;ob.lock_rotation=(True,)*3;ob.lock_scale=(True,)*3
        for i,co in enumerate(coords):position_error=max(position_error,(Vector(co)-mesh.vertices[i].co).length)
        batch_normal_error=0.0
        for i,(n,t) in enumerate(zip(normals,uvs)):
            uv_error=max(uv_error,max(abs(x-y) for x,y in zip(t,uv.data[i].uv)))
            if Vector(n).length and mesh.corner_normals[i].vector.length:
                batch_normal_error=max(batch_normal_error,Vector(n).angle(mesh.corner_normals[i].vector)*180/math.pi)
        normal_error=max(normal_error,batch_normal_error)
        # Protect source open edges, hard normals, UV seams and extrema. A
        # zero-weight region is never interpreted as permission to edit all.
        edge_faces=collections.defaultdict(list)
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                ni=poly.loop_start+(li-poly.loop_start+1)%poly.loop_total
                edge_faces[mesh.loops[li].edge_index].append((poly,{
                    mesh.loops[k].vertex_index:(uv.data[k].uv.copy(),mesh.corner_normals[k].vector.copy()) for k in (li,ni)}))
        protected=set();required_edges=set()
        key=lambda co:tuple(round(float(x),4) for x in co)
        for edge in mesh.edges:
            pair=edge_faces[edge.index];keep=len(pair)!=2
            if not keep:
                keep=pair[0][0].normal.angle(pair[1][0].normal,0)>math.radians(30)
                for vi in edge.vertices:
                    aa,bb=pair[0][1][vi],pair[1][1][vi]
                    keep=keep or (aa[0]-bb[0]).length>0.00001 or aa[1].angle(bb[1],0)>math.radians(30)
            if keep:
                protected.update(edge.vertices)
                required_edges.add(tuple(sorted(key(mesh.vertices[i].co) for i in edge.vertices)))
        for axis in range(3):
            values=[v.co[axis] for v in mesh.vertices]
            for value in (min(values),max(values)):
                protected.update(v.index for v in mesh.vertices if abs(v.co[axis]-value)<0.00001)
        required={key(mesh.vertices[i].co) for i in protected}
        mesh.calc_loop_triangles()
        tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
        row={'batch':bi,'group':batch.group,'material':batch.material,'triangles':len(faces),
             'opaque_qualified':batch.material in opaque,'protected_vertices':len(protected),
             'vertices':len(coords),'reference_normal_error_degrees':batch_normal_error,
             'blender_qualified':batch_normal_error<=0.1,'arms':{}}
        report['batches'].append(row);inputs.append((ob,batch,protected,required,required_edges,tree))
    report['reference_roundtrip']={'position_max_obj':position_error,'uv_max':uv_error,'normal_max_degrees':normal_error}
    if position_error>0.0002 or uv_error>0.00005:
        (a.output/'report.json').write_text(json.dumps(report,indent=2));raise ValueError('unmodified Blender attribute gate failed')
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'reference-locked.blend'))
    # An unqualified Blender batch is kept from the original OBJ, not exported
    # with a relaxed normal tolerance. The control uses the original source values.
    exports={'reference':[None for v in inputs]}
    for label,ratio,limit in [('CANDIDATE_CONSERVATIVE',0.4,0.10),('CANDIDATE_LEAN',0.15,0.25)]:
        selected=[];counts=collections.Counter()
        for bi,(ob,batch,protected,required,required_edges,tree) in enumerate(inputs):
            cand=ob.copy();cand.data=ob.data.copy();cols[label].objects.link(cand)
            cand.name=f'{label}_{bi:03d}';safe=[i for i in range(len(cand.data.vertices)) if i not in protected]
            row=report['batches'][bi];result={'eligible':row['opaque_qualified'],'safe_vertices':len(safe)}
            changed=False
            if row['opaque_qualified'] and row['blender_qualified'] and safe and len(cand.data.polygons)>8:
                vg=cand.vertex_groups.new(name='ReducibleInterior');vg.add(safe,1.0,'REPLACE')
                mod=cand.modifiers.new('SourceBoundedReduction','DECIMATE');mod.ratio=ratio
                mod.vertex_group=vg.name;mod.vertex_group_factor=1;mod.use_collapse_triangulate=True
                bpy.context.view_layer.objects.active=cand
                bpy.ops.object.modifier_apply(modifier=mod.name)
                cm=cand.data;cm.calc_loop_triangles()
                edges={tuple(sorted(tuple(round(float(x),4) for x in cm.vertices[i].co) for i in e.vertices)) for e in cm.edges}
                verts={tuple(round(float(x),4) for x in v.co) for v in cm.vertices}
                bvh=BVHTree.FromPolygons([v.co for v in cm.vertices],[tuple(t.vertices) for t in cm.loop_triangles],all_triangles=True)
                def samples(m):
                    return [v.co for v in m.vertices]+[sum((m.vertices[i].co for i in t.vertices),Vector())/3 for t in m.loop_triangles]
                error=max([tree.find_nearest(p)[3] for p in samples(cm)]+[bvh.find_nearest(p)[3] for p in samples(ob.data)])*baseline['source_scale']
                result.update(attempted_triangles=len(cm.loop_triangles),sampled_surface_max_m=error,
                    protected_edges_missing=len(required_edges-edges),protected_vertices_missing=len(required-verts))
                accepted=not(required_edges-edges or required-verts) and error<=limit
                if not accepted:
                    rejected=cand.data;cand.data=ob.data.copy();bpy.data.meshes.remove(rejected);counts['reverted_batches']+=1
                result['geometry_gate']=accepted
                changed=accepted and len(cand.data.polygons)<len(ob.data.polygons)
            cand.data.calc_loop_triangles();result['triangles']=len(cand.data.loop_triangles)
            counts['triangles']+=result['triangles'];counts['changed_batches']+=result['triangles']<row['triangles']
            row['arms'][label]=result;selected.append(cand if changed else None);cand.hide_render=True
        report['arms'][label]={'ratio':ratio,**dict(counts)};exports[label]=selected
        print(label,report['arms'][label],flush=True)
    for label,objects in exports.items():
        path=a.output/(label+'.obj');vbase=tbase=nbase=0
        with path.open('w',encoding='utf-8',newline='\n') as f:
            f.write('# Local source-bound Blender edit; materials remain source identities.\n')
            for bi,ob in enumerate(objects):
                batch=inputs[bi][1]
                f.write(f'g {batch.group}\nusemtl {batch.material}\n')
                if ob is None:
                    values={};coords=[];faces=[];normals=[];uvs=[]
                    for i in batch.indices:
                        val=parsed['vertices'][i];pid=parsed['vertex_source_indices'][i][0]
                        if pid not in values:values[pid]=len(coords);coords.append(val[:3])
                        faces.append(values[pid]);normals.append(val[3:6]);uvs.append(val[6:8])
                    triangles=[tuple(range(k,k+3)) for k in range(0,len(faces),3)]
                else:
                    m=ob.data;m.calc_loop_triangles();coords=[v.co for v in m.vertices]
                    faces=[loop.vertex_index for loop in m.loops]
                    normals=[tuple(n.vector) for n in m.corner_normals]
                    uvs=[tuple(t.uv) for t in m.uv_layers.active.data]
                    triangles=[tuple(t.loops) for t in m.loop_triangles]
                for v in coords:f.write('v '+' '.join(format(float(x),'.9g') for x in v)+'\n')
                tex={};norm={};corners=[]
                for tri in triangles:
                    ids=[]
                    for li in tri:
                        t=tuple(uvs[li]);n=tuple(normals[li])
                        if t not in tex:tex[t]=len(tex)+1;f.write('vt '+' '.join(format(x,'.9g') for x in t)+'\n')
                        if n not in norm:norm[n]=len(norm)+1;f.write('vn '+' '.join(format(x,'.9g') for x in n)+'\n')
                        ids.append(f'{vbase+faces[li]+1}/{tbase+tex[t]}/{nbase+norm[n]}')
                    corners.append('f '+' '.join(ids)+'\n')
                f.writelines(corners);vbase+=len(coords);tbase+=len(tex);nbase+=len(norm)
        report.setdefault('outputs',{})[label]={'name':path.name,'sha256':sha(path),'bytes':path.stat().st_size}
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'selectable-candidates.blend'))
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('DONE',json.dumps(report['arms']),flush=True)

if __name__=='__main__':main()
