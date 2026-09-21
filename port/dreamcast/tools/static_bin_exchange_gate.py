import pathlib,sys,json,struct,collections,math,hashlib
P=pathlib.Path
sys.path.insert(0,str(P(__file__).resolve().parent))
from convert_character import triangulate

def decode(path):
 d=path.read_bytes();u=lambda o:struct.unpack_from('>I',d,o)[0];h=lambda o:struct.unpack_from('>H',d,o)[0]
 assert d[24]==0 and d[25]==1 and u(44)==0
 flags=u(32); stride=8 if flags&0x80000000 else 6;ns=4 if flags&0x20000000 else 8
 tris=[];materials=[];allcorners=[];cur=u(28)
 for part in range(h(26)):
  materials.append(d[cur:cur+24].hex());p=cur+32;end=p+u(cur+24)
  while p<end:
   op=d[p];p+=1
   if op==0:continue
   count=h(p);p+=2;corners=[]
   for i in range(count):
    pi,ni=h(p),h(p+2);ti=h(p+stride-2)
    xyz=tuple(x/(1<<d[40]) for x in struct.unpack_from('>3h',d,u(48)+pi*8))
    normal=struct.unpack_from('>3b' if ns==4 else '>3h',d,u(52)+ni*ns)
    color=tuple(d[u(12)+h(p+4)*4:u(12)+h(p+4)*4+4]) if stride==8 and u(12) else None
    uv=struct.unpack_from('>2h' if stride==8 else '>2H',d,u(16)+ti*4)
    corners.append((xyz,normal,color,uv));p+=stride
   allcorners.extend(corners)
   for t in triangulate(op,corners):
    if len({v[0] for v in t})<3:continue
    tris.append(t)
  cur=end
 return {'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest(),'flags':hex(flags),'nTex':u(36),'materials':materials,'triangles':tris,'all_colors':sorted({v[2] for v in allcorners}),'zero_normal_corners':sum(not any(v[1]) for v in allcorners)}
def key(t):
 a=[(v[0],v[3]) for v in t];return min(tuple(a[i:]+a[:i]) for i in range(3))

def material_contract(model):
 # nTex is retained from the exact reference, after checking every active sampler.
 for raw in model['materials']:
  h=bytes.fromhex(raw);ids=[h[12]]
  if h[11]&1:ids.append(h[13])
  if h[11]&4:ids.append(h[14])
  if h[11]&16:ids.append(h[23])
  if any(i!=255 and i>=model['nTex'] for i in ids):
   raise ValueError('material sampler outside source texture count')

def prepare(reference,obj):
 a=decode(reference);material_contract(a)
 colors=set(a['all_colors'])
 if colors!={(0,0,0,0)} or a['flags']!='0xa0000000' or a['nTex']!=7 or len(a['materials'])!=1:
  raise ValueError('outside audited constant-zero RGBA static single-part contract')
 # One constant source color for all corners makes this valid even after topology changes.
 lines=obj.read_text().splitlines()
 obj.write_text('\n'.join(' '.join(line.split()[:4])+' 0 0 0 0' if line.startswith('v ') else line for line in lines)+'\n')
 idx=obj.with_suffix('.idxggbin')
 idx.write_text(idx.read_text().replace('UseVertexColor:False','UseVertexColor:True').replace('UseIdxMaterial:False','UseIdxMaterial:True'))

def finalize(reference,candidate):
 a=decode(reference);b=decode(candidate);material_contract(a)
 if set(a['all_colors'])!={(0,0,0,0)} or set(b['all_colors'])!={(0,0,0,0)}:
  raise ValueError('color contract failed; never patch a failed corner stream')
 if a['materials']!=b['materials'] or a['flags']!='0xa0000000' or b['flags']!='0xe0000000' or a['nTex']!=7:
  raise ValueError('source identity/structural flag contract failed')
 data=bytearray(candidate.read_bytes());data[32:40]=reference.read_bytes()[32:40]
 candidate.write_bytes(data)
 return {'source_bytes':a['bytes'],'candidate_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def compare(reference,candidate):
 a=decode(reference);b=decode(candidate)
 aa=collections.Counter(map(key,a['triangles']));bb=collections.Counter(map(key,b['triangles']))
 am={key(t):t for t in a['triangles']};bm={key(t):t for t in b['triangles']};angle=0;nc=0;cc=0
 if len(am)!=len(a['triangles']) or len(bm)!=len(b['triangles']):raise ValueError('duplicate triangle identity needs a separate normal correspondence proof')
 for k in am.keys()&bm.keys():
  for va in am[k]:
   vb=next(v for v in bm[k] if v[0]==va[0])
   nc=max(nc,max(abs(x-y) for x,y in zip(va[1],vb[1])));cc+=va[2]!=vb[2]
   if any(va[1]) and any(vb[1]):
    cos=sum(x*y for x,y in zip(va[1],vb[1]))/(sum(x*x for x in va[1])*sum(x*x for x in vb[1]))**.5
    angle=max(angle,math.degrees(math.acos(max(-1,min(1,cos)))))
 return {'source_bytes':a['bytes'],'candidate_bytes':b['bytes'],'triangles':len(b['triangles']),'oriented_position_uv_equal':aa==bb,'color_corner_differences':cc,'max_normal_component_delta':nc,'max_normal_angle_degrees':angle,'source_zero_normal_corners':a['zero_normal_corners'],'candidate_zero_normal_corners':b['zero_normal_corners'],'metadata_equal':all(a[k]==b[k] for k in ['flags','nTex','materials']),'bounded_gate':aa==bb and a['zero_normal_corners']==b['zero_normal_corners'] and cc==0 and nc<=1 and angle<=0.5 and all(a[k]==b[k] for k in ['flags','nTex','materials'])}

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description='Strict audited constant-color static BIN exchange bridge; rejects other contracts')
 p.add_argument('mode',choices=['prepare','finalize','compare']);p.add_argument('reference',type=P);p.add_argument('candidate',type=P)
 ar=p.parse_args();print(json.dumps(globals()[ar.mode](ar.reference,ar.candidate),indent=2))