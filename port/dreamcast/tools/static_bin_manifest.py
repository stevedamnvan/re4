"""Write a private source/candidate identity and numerical-gate manifest."""
import pathlib,json,hashlib,sys
from static_bin_exchange_gate import compare
r=pathlib.Path(sys.argv[1]);original=pathlib.Path(sys.argv[2]);audit=pathlib.Path(sys.argv[3])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
geo=json.loads((r/'candidates/geometry-report.json').read_text());inv=json.loads(audit.read_text());owner=next(x for x in inv['smds'] if x['owner']=='r100.arc#5')
models={x['bin']:x for x in owner['models']};entries=[]
for i in range(11):
 n=f'{i:04d}';src=r/'set-source'/f'{n}.BIN';assert src.read_bytes()==(original/src.name).read_bytes()
 entry={'source_identity':{'archive':'r100.arc','tag':'SMD','ordinal':5,'bin':i},'source_sha256':sha(src),'source_bytes':src.stat().st_size,'audit':models[i],'tool_only_gate':compare(src,r/'set-tool'/src.name),'selected':n in geo}
 if n in geo:
  q=r/'set-blender-qualified'/n/src.name;entry['blender_gate']=compare(src,q);assert entry['blender_gate']['bounded_gate'];entry['roundtrip_sha256']=sha(q);entry['roundtrip_bytes']=q.stat().st_size
  entry['arms']={}
  for arm,metrics in geo[n]['arms'].items():
   p=r/'candidates'/n/arm/src.name;entry['arms'][arm]={**metrics,'encoded_bytes':p.stat().st_size,'encoded_sha256':sha(p),'decision':'reject: distance gate' if not metrics['distance_gate'] else 'no geometry saving'}
  entry['blend_sha256']=sha(r/'candidates'/n/'selectable-candidates.blend')
 entries.append(entry)
out={'decision':'not worthwhile; no package/runtime promotion','whole_set_byte_ceiling':sum(x['source_bytes'] for x in entries),'qualified_set_source_bytes':sum(x['source_bytes'] for x in entries if x['selected']),'qualified_roundtrip_bytes':sum(x['roundtrip_bytes'] for x in entries if x['selected']),'normal_gate':'<=0.5 degree and <=1 signed component; exact positions/UV/winding/colors/material/header flags; not exact normal arrays','actual_allocation':'source room archive, not repeated DAT instances or block pool','runtime_saving_measured':False,'tools':{'upstream_source_commit':'638e9d5f63fb8322cfab0d48f4ffbb23f6e7bb68','release_exe_sha256':sha(r/'tools/bin-v1.0.4/JADERLINK_RE4_GCWII_BIN_TOOL.exe'),'patched_dll_sha256':sha(r/'tools/bin-color-fix.dll'),'blender_version':'5.2.0 LTS','blender_build':'fbe6228777e7'},'entries':entries}
(r/'source-candidate-manifest.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='entries'},indent=2))