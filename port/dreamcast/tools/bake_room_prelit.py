#!/usr/bin/env python3
"""Bake qualified r100 room RGB with the existing D349 C++ lighting evaluator.

The native room's 12-byte normal field becomes 12-byte authored color storage;
geometry, topology, UVs, material state and textures remain unchanged. Fails if
any group selects a camera-relative light, or shared normals require conflicting
lighting. This is a PS2-inspired representation, not copied PS2 lighting.
"""
import argparse,hashlib,json,pathlib,re,struct,subprocess,zlib

def block(text,start):
 at=text.index(start);left=text.index('{',at);depth=1;i=left+1
 while depth:
  if text[i]=='{':depth+=1
  if text[i]=='}':depth-=1
  i+=1
 return text[at:i]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=pathlib.Path);p.add_argument('room',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args();a.out.mkdir(exist_ok=False)
 text=(a.source/'port/dreamcast/room/main.cpp').read_text();hpp=(a.source/'port/dreamcast/room/room_package.hpp').read_text()
 code='#include <algorithm>\n#include <cmath>\n#include <cstdint>\n#include <cstdio>\nconstexpr float kPi=3.14159265358979323846f;\nstruct point_t{float x,y,z,w;};\n'
 code+='namespace re4dc::room { constexpr unsigned kSourceGroupHasLightVolume=1;'+block(hpp,'struct SourceGroup {')+';}\n'
 code+=text[text.index('struct SourceLight {'):text.index('#else',text.index('struct SourceLight {'))]
 code+=text[text.index('struct SourceLightingBasis {'):text.index('constexpr std::uint32_t kRoomStaticLightingVertexCapacity',text.index('struct SourceLightingBasis {'))]
 for name in ['void normalize_vector(', 'void prepare_source_lights(', 'void accumulate_source_lighting(', 'void evaluate_source_lighting(', 'bool source_light_hits_group(', 'std::uint32_t source_group_light_selection(']:code+=block(text,name)+'\n'
 code+='''
int main(){prepare_source_lights();re4dc::room::SourceGroup group;float v[8];
 while(fread(&group,sizeof group,1,stdin)==1){if(fread(v,sizeof v,1,stdin)!=1)return 2;
 unsigned mask=source_group_light_selection(&group);if(mask&g_source_dynamic_light_mask)return 3;
 float rgb[3];evaluate_source_lighting(v[0],v[1],v[2],v[3],v[4],v[5],false,rgb[0],rgb[1],rgb[2],mask);
 if(fwrite(rgb,sizeof rgb,1,stdout)!=1)return 4;
 }return 0;}
'''
 cpp=a.out/'bake.cpp';cpp.write_text(code);exe=a.out/'bake';subprocess.run(['g++','-std=c++20','-O2',str(cpp),'-o',str(exe)],check=True)
 data=a.room.read_bytes();I=lambda o:struct.unpack_from('<I',data,o)[0]
 if data[:8]!=b'RE4DCRM\0' or I(8)!=3 or I(12)!=128 or I(96)!=1:raise ValueError('unqualified native room layout')
 if zlib.crc32(data[128:])!=I(92):raise ValueError('room CRC')
 ng,nv=I(48),I(36);go,bo,vo,io,po,pio=[I(o) for o in (68,72,76,80,84,88)];sg=io+I(40)*4
 owners=[set() for _ in range(nv)];groups=[]
 for g in range(ng):
  raw=data[sg+76*g:sg+76*(g+1)];assert len(raw)==76 and struct.unpack_from('<I',raw,12)[0]&1;groups.append(raw)
 for bi in range(I(52)):
  _,first,n,g,flags,pfirst,pn=struct.unpack_from('<7I',data,bo+bi*28);ids=set()
  if flags&2:ids.update(struct.unpack_from('<'+str(n)+'I',data,io+first*4))
  for pi in range(pfirst,pfirst+pn):
   first,n,_=struct.unpack_from('<IHH',data,po+8*pi);ids.update(struct.unpack_from('<'+str(n)+'I',data,pio+first*4))
  for i in ids:owners[i].add(g)
 bindings=[(i,g) for i,gs in enumerate(owners) for g in sorted(gs)];records=b''.join(groups[g]+data[vo+i*32:vo+(i+1)*32] for i,g in bindings)
 result=subprocess.run([str(exe)],input=records,stdout=subprocess.PIPE,check=True).stdout;assert len(result)==len(bindings)*12
 colors={};max_conflict=0
 for k,(i,g) in enumerate(bindings):
  rgb=struct.unpack_from('<3f',result,k*12)
  if i in colors:max_conflict=max(max_conflict,max(abs(a-b) for a,b in zip(colors[i],rgb)))
  else:colors[i]=rgb
 if max_conflict>1/255:raise ValueError('shared vertex lighting differs across source groups: '+str(max_conflict))
 candidate=bytearray(data)
 for i in range(nv):struct.pack_into('<3f',candidate,vo+i*32+12,*colors.get(i,(0,0,0)))
 struct.pack_into('<I',candidate,96,I(96)|2);struct.pack_into('<I',candidate,92,zlib.crc32(candidate[128:]));(a.out/'r100-prelit.re4room').write_bytes(candidate)
 (a.out/'source-colors.f32').write_bytes(b''.join(struct.pack('<3f',*colors.get(i,(0,0,0))) for i in range(nv)))
 report=dict(meaning='D349 source-selected world lighting baked offline; PS2-inspired representation, not PS2 RGB transfer',source_sha256=hashlib.sha256(text.encode()).hexdigest(),reference_sha256=hashlib.sha256(data).hexdigest(),candidate_sha256=hashlib.sha256(candidate).hexdigest(),file_bytes=len(candidate),reference_bytes=len(data),vertices=nv,used_vertices=len(colors),groups=ng,camera_relative_selected=False,max_shared_color_difference=max_conflict,runtime_room_light_evaluations=0,normal_bytes_reused=nv*12,additional_vertex_storage=0)
 (a.out/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()