"""Source primitive transport: endian, source pose/camera, cull, clipping,
whole-part rollback and copied-packet ownership. Does not accept appearance."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which("g++"),"host compiler required")
class NativeModel(unittest.TestCase):
 def test_source_pose_packet_boundary(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/"dc").mkdir()
   (root/"dc/pvr.h").write_text("#pragma once\n#include <cstddef>\n#include <cstdint>\nstruct pvr_vertex_t{std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb;};\nstruct pvr_poly_hdr_t{std::uint32_t words[8];};\n#define PVR_CMD_VERTEX 0xe0000000U\n#define PVR_CMD_VERTEX_EOL 0xf0000000U\nint pvr_prim(const void*,std::size_t);\n")
   code=r"""
#include "native_model.h"
#include "pvr_geometry.hpp"
#include "native_draw_plan.hpp"
#include <cassert>
#include <cmath>
#include <cstring>
#include <vector>
#include <random>
extern "C" void re4dc_model_submit_reference(const Re4dcModelPart*);
std::vector<std::uint32_t> plan_storage;
extern "C" const re4dc::render::NativeDrawPlan* re4dc_model_acquire_draw_plan(const Re4dcModelPart* p,int* invalid){
 re4dc::render::DrawPlanRequirements r;
 *invalid=!re4dc::render::inspect_draw_plan(p->stream,p->stream_bytes,p->flags&0x80000000U,p->position_count,p->normal_count,r);
 if(*invalid)return nullptr;
 plan_storage.resize((r.bytes+3)/4);
 return re4dc::render::prepare_draw_plan(plan_storage.data(),plan_storage.size()*4,p->stream,p->stream_bytes,p->flags&0x80000000U,r);
}
extern "C" void re4dc_model_release_draw_plan(){}
unsigned status=99,capacity=100,committed=0,input,output,binds=0;float uscale=1,vscale=1,predicted_u=1,predicted_v=1;bool bind_fails=false,streaming=false,aborted=false;
std::vector<pvr_vertex_t> all_chunks;
pvr_vertex_t pending[4098],owned[4098];
extern "C" int re4dc_model_diagnostic_enabled(){return 1;}
extern "C" int re4dc_model_packet_reserve(const Re4dcModelPart*,Re4dcModelPacket* p){*p={pending,capacity,predicted_u,predicted_v};return 1;}
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart*,Re4dcModelPacket* p){++binds;*p={pending,capacity,uscale,vscale};return !bind_fails;}
extern "C" void re4dc_model_packet_commit(unsigned n){memcpy(owned,pending,n*32);committed=n;if(streaming)all_chunks.insert(all_chunks.end(),pending,pending+n);}
extern "C" int re4dc_model_packet_streaming(){return streaming;}
extern "C" void re4dc_model_packet_abort(){aborted=true;all_chunks.clear();}
extern "C" void re4dc_model_result(unsigned r,unsigned i,unsigned o){status=r;input=i;output=o;}
int pvr_prim(const void*,std::size_t){assert(false);return -1;}
std::vector<unsigned char> stream(unsigned op,std::initializer_list<unsigned> ids,bool color=false){
 std::vector<unsigned char> result{(unsigned char)op,0,(unsigned char)ids.size()};
 for(unsigned id:ids){result.push_back(id>>8);result.push_back(id);result.push_back(0);result.push_back(0);
  if(color){result.push_back(0);result.push_back(0);} result.push_back(0);result.push_back(id);}
 return result;
}
// Expand actual emitted strips back into the exact triangle order consumed by
// PVR. This catches parity, seam, clipping and rejected-triangle bridging bugs.
std::vector<pvr_vertex_t> expanded(){
 std::vector<pvr_vertex_t> result;unsigned start=0;
 for(unsigned i=0;i<committed;++i){
  const unsigned local=i-start;
  if(local>=2){
   const unsigned a=i-2+(local&1),b=i-1-(local&1);
   for(unsigned id:{a,b,i}){auto v=owned[id];v.flags=0;result.push_back(v);}
  }
  if(owned[i].flags==PVR_CMD_VERTEX_EOL)start=i+1;
 }
 assert(!committed || owned[committed-1].flags==PVR_CMD_VERTEX_EOL);return result;
}
int main(){
 short pos[4][4]={{-2,-2,0,9},{2,-2,0,9},{2,2,0,9},{-2,2,0,9}};
 unsigned short uv[4][2]={{0,0},{32768,0},{32768,32768},{0,32768}};
 Re4dcModelPart p{};p.positions=(unsigned char*)pos;p.position_count=4;p.normal_count=1;p.position_stride=8;
 p.uv=(unsigned char*)uv;p.modelview[0]=p.modelview[5]=p.modelview[10]=1;p.modelview[11]=-10;
 p.projection[1]=p.projection[3]=1;p.projection[5]=-1.f/99;p.projection[6]=-100.f/99;
 p.viewport[2]=640;p.viewport[3]=480;p.viewport[5]=1;
 auto run=[&](std::vector<unsigned char>& data){p.stream=data.data();p.stream_bytes=data.size();status=99;committed=0;re4dc_model_submit(&p);};
 auto q=stream(0x80,{0,1,2,3});run(q);
 assert(status==0 && committed==6 && input==2 && output==2);
 assert(fabs(owned[0].x-256)<.001 && fabs(owned[0].y-288)<.001 && fabs(owned[0].z-.1)<.00001);
 assert(owned[1].u==1 && owned[2].v==1);
 p.cull=2;run(q);assert(committed==6);p.cull=1;run(q);assert(committed==0);p.cull=0;
 auto strips=stream(0x98,{0,1,3,2});p.cull=2;
 const auto strip_before=*re4dc_model_work_stats();
 run(strips);assert(committed==4 && output==2);p.cull=0;
 const auto strip_after=*re4dc_model_work_stats();
#if RE4DC_MODEL_ROOM_STRIPS
 assert(strip_after.room_prepared_strips-strip_before.room_prepared_strips==1);
 assert(strip_after.room_prepared_corners-strip_before.room_prepared_corners==4);
 assert(strip_after.position_references-strip_before.position_references==4);
#else
 assert(strip_after.room_prepared_strips==strip_before.room_prepared_strips);
 assert(strip_after.room_prepared_corners==strip_before.room_prepared_corners);
 assert(strip_after.position_references-strip_before.position_references==6);
#endif
 auto fan=stream(0xa0,{0,1,2,3});run(fan);assert(committed==6);
 // Captured native packet survives source preparation storage being overwritten.
 auto before=owned[0];pos[0][0]=0;assert(!memcmp(&before,&owned[0],32));run(q);assert(owned[0].x==320);pos[0][0]=-2;
 // Source skinned arrays use six-byte stride, not the rigid palette-id stride.
 short skin[4][3]={{-2,-2,0},{2,-2,0},{2,2,0},{-2,2,0}};
 p.positions=(unsigned char*)skin;p.position_stride=6;run(q);assert(fabs(owned[0].x-256)<.001);
 // Crossing the actual source near plane invokes the shared clipper.
 skin[0][2]=10;run(q);assert(status==0 && committed>0);skin[0][2]=0;
 // Whole-part rollback even if the first triangle fit; no partial part published.
 unsigned old_binds=binds;capacity=3;run(q);assert(status==3 && committed==0 && binds==old_binds);capacity=100;
 auto invalid=q;invalid[4]=8;run(invalid);assert(status==1 && committed==0);
 auto trunc=q;trunc.pop_back();run(trunc);assert(status==1);
 auto badop=q;badop[0]=0x61;run(badop);assert(status==1);
 auto badquad=stream(0x80,{0,1,2});run(badquad);assert(status==1);
 // Colored-corner identity adds a BE index; UV CPU values are signed Q8.
 short signeduv[4][2]={{-256,0},{256,0},{256,256},{-256,256}};
 p.flags=0x80000000;p.uv=(unsigned char*)signeduv;auto colored=stream(0x90,{0,1,2},true);run(colored);
 assert(status==0 && owned[0].u==-1 && owned[1].u==1);
 p.projection[0]=1;run(colored);assert(status==1); // unsupported ortho is explicit
 p.projection[0]=0;p.flags=0;p.shift=0;p.uv_offset[0]=p.uv_offset[1]=0;
 short many[66][3];unsigned short manyuv[66][2];
 for(unsigned i=0;i<66;++i){many[i][0]=int(i)-32;many[i][1]=(i&1)?-2:2;many[i][2]=0;manyuv[i][0]=i*128;manyuv[i][1]=(i&1)?32768:0;}
 p.positions=(unsigned char*)many;p.position_count=66;p.position_stride=6;p.uv=(unsigned char*)manyuv;
 p.modelview[11]=-128;p.projection[5]=-1.f/399;p.projection[6]=-400.f/399;
 std::vector<unsigned char> longstrip{0x98,0,66};
 for(unsigned i=0;i<66;++i)for(unsigned byte:{0U,i,0U,0U,0U,i})longstrip.push_back(byte);
 capacity=2048;p.stream=longstrip.data();p.stream_bytes=longstrip.size();committed=0;re4dc_model_submit_reference(&p);
 assert(status==0 && committed==192 && output==64);auto baseline=expanded();
 run(longstrip);assert(status==0 && committed==66 && output==64);auto candidate=expanded();
 assert(candidate.size()==baseline.size() && !memcmp(candidate.data(),baseline.data(),baseline.size()*32));
 // Former overflow now fits; one byte of unrelated capacity is not borrowed.
 capacity=66;run(longstrip);assert(status==0 && committed==66);capacity=65;old_binds=binds;run(longstrip);assert(status==3 && !committed && binds==old_binds);
 capacity=2048;
 // Real previous implementation as oracle, randomized depth/cull/seam cases.
 std::mt19937 rng(335);
 unsigned savings=0;
 for(unsigned trial=0;trial<600;++trial){
  for(unsigned i=0;i<66;++i){
   many[i][0]=int(rng()%81)-40;many[i][1]=int(rng()%61)-30;
   many[i][2]=trial%3==0?int(rng()%261)-130:0;
   manyuv[i][0]=rng();manyuv[i][1]=rng();
  }
  p.cull=trial%4;uscale=trial%2?.75f:1.f;vscale=trial%2?.625f:1.f;
  predicted_u=trial%7?uscale:1;predicted_v=trial%7?vscale:1; // exact fallback for alternate native dimensions
  // A split keeps primitive order; UV changes across it must prevent reuse.
  auto data=longstrip;
  if(trial%5==0){auto seam=stream(0x90,{63,64,65});seam[8]=0;seam[14]=1;data.insert(data.end(),seam.begin(),seam.end());}
  p.stream=data.data();p.stream_bytes=data.size();committed=0;re4dc_model_submit_reference(&p);
  assert(status==0);auto old_count=committed,old_input=input,old_output=output;auto old=expanded();
  run(data);assert(status==0 && input==old_input && output==old_output && committed<=old_count);
  auto now=expanded();assert(now.size()==old.size());
  assert(old.empty() || !memcmp(now.data(),old.data(),old.size()*32));savings+=old_count-committed;
 }
 assert(savings);
 // Binding failure discards all successfully prepared vertices, no partial draw.
 p.cull=0;p.modelview[11]=-128;for(auto& vertex:many)vertex[2]=0;
 bind_fails=true;run(longstrip);assert(status==2 && !committed);bind_fails=false;
 // A completely rejected part consumes no texture handle, including cull-all.
 p.cull=3;unsigned before_binds=binds;run(longstrip);assert(status==0 && output==0 && binds==before_binds);
 p.cull=0;p.modelview[11]=1000;run(longstrip);assert(status==0 && !output && binds==before_binds);

 // Real material alpha, independent of texture data. Opaque legacy packets
 // still compare against the old oracle above; every uniform alpha survives.
 p.positions=(unsigned char*)skin;p.position_count=4;p.position_stride=6;
 p.modelview[11]=-10;p.cull=0;uscale=vscale=predicted_u=predicted_v=1;
 p.flags=0;p.uv=(unsigned char*)uv;capacity=2048;
 for(unsigned alpha=0;alpha<256;++alpha){
  p.alpha_state=alpha;run(q);assert(status==0 && committed==6);
  for(unsigned n=0;n<committed;++n)assert((owned[n].argb>>24)==alpha);
 }
 // Independent color identities, rather than position/normal/UV IDs.
 unsigned char colors[3][4]={{17,29,53,0},{61,79,101,64},{103,127,149,255}};
 p.flags=0x80000000;p.uv=(unsigned char*)signeduv;p.colors=(unsigned char*)colors;p.alpha_state=256|13;
 for(unsigned i=0;i<3;++i)colored[3+i*8+5]=2-i;
 run(colored);assert(status==0 && committed==3);
 assert((owned[0].argb>>24)==255 && (owned[1].argb>>24)==64 && (owned[2].argb>>24)==0);
 // Near-plane clipping interpolates alpha. It must not restore 255 or retain
 // an endpoint's alpha across newly inserted vertices.
 p.modelview[11]=-2;skin[0][2]=2;run(colored);assert(status==0 && committed==6);
 unsigned fractional=0;
 for(unsigned i=0;i<committed;++i){auto a=owned[i].argb>>24;if(a>=126 && a<=160)++fractional;}
 assert(fractional>=2);skin[0][2]=0;p.modelview[11]=-10;
 p.alpha_state=512;run(colored);assert(status==1 && !committed);
 p.alpha_state=256;p.colors=nullptr;run(colored);assert(status==1 && !committed);
 p.alpha_state=255;p.flags=0;p.uv=(unsigned char*)manyuv;

 // Source SDK cull boundary, independently checked in clip space. The SDK
 // flips FRONT/BACK hardware fields and stores a negative viewport Y scale.
 // For all-positive W, GX FRONT rejects non-positive projected XY determinant;
 // that becomes positive screen area. Do not use the viewer enum as the oracle.
 p.positions=(unsigned char*)many;p.position_count=66;p.modelview[11]=-128;
 uscale=vscale=predicted_u=predicted_v=1;capacity=2048;
 for(unsigned trial=0;trial<200;++trial){
  for(unsigned i=0;i<3;++i){many[i][0]=int(rng()%61)-30;many[i][1]=int(rng()%61)-30;many[i][2]=0;}
  const long area=(long(many[1][0])-many[0][0])*(long(many[2][1])-many[0][1])-(long(many[1][1])-many[0][1])*(long(many[2][0])-many[0][0]);
  if(!area)continue;
  auto triangle=stream(0x90,{0,1,2});
  for(unsigned mode=0;mode<3;++mode)for(bool force:{false,true}){
   p.cull=re4dc_model_cull(mode,force);run(triangle);
   const bool rejected=(force || mode==0)?area<=0:mode==1?area>=0:false;
   assert(status==0 && output==(rejected?0U:1U));
  }
 }
 p.cull=re4dc_model_cull(2,false);assert(p.cull==0);
 // Stream across small artificial boundaries and compare exact expanded
 // triangles against the existing unbounded oracle, including seams/clipping.
 p.modelview[11]=-128;p.cull=0;streaming=true;
 for(unsigned trial=0;trial<120;++trial){
  for(unsigned i=0;i<66;++i){many[i][0]=int(rng()%81)-40;many[i][1]=int(rng()%61)-30;many[i][2]=trial%3?0:int(rng()%261)-130;}
  uscale=trial%2?.75f:1.f;vscale=trial%2?.625f:1.f;predicted_u=predicted_v=1;
  capacity=2048;p.stream=longstrip.data();p.stream_bytes=longstrip.size();committed=0;
  re4dc_model_submit_reference(&p);auto baseline=expanded();auto refinput=input,refoutput=output;
  capacity=3+trial%19;all_chunks.clear();aborted=false;auto prior=binds;
  run(longstrip);assert(status==0 && !aborted && input==refinput && output==refoutput);
  assert(binds==prior+1);assert(all_chunks.size()<4098);
  memcpy(owned,all_chunks.data(),all_chunks.size()*32);committed=all_chunks.size();auto emitted=expanded();
  assert(emitted.size()==baseline.size() && !memcmp(emitted.data(),baseline.data(),baseline.size()*32));
 }
 // Over 64KiB of independent geometry uses bounded scratch. No reference and
 // candidate are retained simultaneously by the real owner (only this fixture).
 for(auto& v:many)v[2]=0;uscale=vscale=predicted_u=predicted_v=1;
 auto tri=stream(0x90,{0,1,2});std::vector<unsigned char> large;
 for(unsigned n=0;n<1800;++n)large.insert(large.end(),tri.begin(),tri.end());
 // Ensure a nondegenerate visible triangle.
 many[0][0]=-2;many[0][1]=-2;many[1][0]=2;many[1][1]=-2;many[2][0]=2;many[2][1]=2;
 const auto work_before=*re4dc_model_work_stats();
 capacity=2047;all_chunks.clear();aborted=false;run(large);
 const auto work_after=*re4dc_model_work_stats();
 assert(work_after.position_references-work_before.position_references==5400);
#if RE4DC_MODEL_POSITION_CACHE
 assert(work_after.position_transforms-work_before.position_transforms==3);
 assert(work_after.position_hits-work_before.position_hits==5397);
#else
 assert(work_after.position_transforms-work_before.position_transforms==5400);
 assert(work_after.position_hits==0);
#endif
 assert(status==0 && !aborted && input==1800 && output==1800 && all_chunks.size()==5400);
 // A late nonfinite projection must invalidate previously transferred chunks.
 // Valid source indices pass preflight; overflow appears only during transform.
 many[0][0]=many[1][0]=many[2][0]=0;
 many[0][1]=-2;many[0][2]=0;many[1][1]=2;many[1][2]=0;many[2][1]=0;many[2][2]=2;
 p.modelview[0]=3e38f;p.modelview[2]=1;many[3][0]=32767;
 auto invalid_late=stream(0x90,{0,1,3});large.insert(large.end(),invalid_late.begin(),invalid_late.end());
 all_chunks.clear();aborted=false;run(large);assert(status==3 && aborted && all_chunks.empty());
 // First-chunk binding failure never publishes or repeatedly retries I/O.
 p.modelview[0]=1;p.modelview[2]=0;bind_fails=true;all_chunks.clear();aborted=false;
 run(longstrip);assert(status==2 && all_chunks.empty() && !aborted);



}
"""
   (root/"fixture.cpp").write_text(code)
   game=ROOT/"port/dreamcast/game";room=ROOT/"port/dreamcast/room"
   reference=subprocess.check_output(["git","show","c45c0cf433c1b1fe5ae7595b1bccf29b29a0ed96:port/dreamcast/game/platform/native_model.cpp"],cwd=ROOT,text=True)
   reference=reference.replace('"../../room/pvr_geometry.hpp"','"pvr_geometry.hpp"').replace('void re4dc_model_submit(', 'void re4dc_model_submit_reference(')
   (root/"reference.cpp").write_text(reference)
   exe=root/"check"
   for cache,strips,plans in ((0,0,0),(0,1,0),(1,0,0),(1,1,0),(0,0,1),(0,1,1),(1,0,1),(1,1,1)):
    subprocess.run(["g++","-std=c++20","-O2","-DRE4DC_MODEL_DRAW_PLANS="+str(plans),"-DRE4DC_MODEL_ROOM_STRIPS="+str(strips),"-DRE4DC_MODEL_POSITION_CACHE="+str(cache),"-fsanitize=address,undefined","-fno-omit-frame-pointer",
    "-I"+str(root),"-I"+str(game/"platform/include"),"-I"+str(room),str(root/"fixture.cpp"),str(root/"reference.cpp"),
    str(game/"platform/native_model.cpp"),str(room/"pvr_geometry.cpp"),str(room/"native_draw_plan.cpp"),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
if __name__=="__main__":unittest.main()
