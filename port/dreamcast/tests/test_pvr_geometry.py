"""Check extracted clipping against the pinned pre-extraction native renderer."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]
REFERENCE="be32de77be1bd1e485f82be444e05de11d4da5e1"
@unittest.skipUnless(shutil.which("g++"),"host compiler required")
class NativeGeometry(unittest.TestCase):
 def test_reference_packets_and_clip_edges(self):
  old=subprocess.check_output(["git","show",REFERENCE+":port/dreamcast/room/main.cpp"],cwd=ROOT,text=True)
  def between(a,b):
   i=old.index(a);return old[i:old.index(b,i)]
  reference=between("std::uint32_t shade_color(","#if defined(RE4DC_SOURCE_SCENE)")
  reference+=between("RenderVertex interpolate_vertex(","#if defined(RE4DC_CULL_AUDIT)")
  reference+=between("std::uint32_t clip_projected_triangle(","void fill_room_entry(")
  declarations=r"""
#include "pvr_geometry.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <cassert>
#include <random>
using re4dc::render::RenderVertex;
static void projection(float& x,float& y,float& z){
 x=320.0f+230.0f*x/z;y=240.0f-230.0f*y/z;z=1.0f/z;
}
namespace reference {
constexpr float kNearClipDistance=.1f,kFarClipDistance=1000.f,kScreenWidth=640.f,kScreenHeight=480.f;
constexpr unsigned kCullNone=0,kCullFront=1,kCullBack=2,kCullAll=3;
struct FrameStats {unsigned room_near_trivial_accepts=0,room_near_trivial_rejects=0,room_near_crossings=0;};
void mat_trans_single(float& x,float& y,float& z){projection(x,y,z);}
"""
  checks=r"""
}
unsigned copied;
alignas(32) unsigned char submitted[160];
int pvr_prim(const void* p,size_t bytes){
 assert(bytes==sizeof(submitted));memcpy(submitted,p,bytes);copied=bytes;return 0;
}
void project(float& x,float& y,float& z,void*){projection(x,y,z);}
int main(){
 re4dc::render::ClipParameters parameters{.1f,1000.f,640.f,480.f,project,nullptr};
 std::mt19937 random(314159);
 std::uniform_real_distribution<float> coord(-3,3),colour(-1,2);
 for(unsigned trial=0;trial<10000;++trial){
  RenderVertex input[3]{};
  for(auto& v:input){
   v.position.world_x=coord(random);v.position.world_y=coord(random);
   float z=coord(random);
   if(fabs(z)<.00001f)z=.1f;
   // Include exact near-plane, far-reject and degenerate cases.
   if(trial%17==0)z=.1f;if(trial%19==0)z=2000.f;
   v.position.world_z=z;v.position.depth=z;
   v.position.x=v.position.world_x;v.position.y=v.position.world_y;v.position.z=z;
   projection(v.position.x,v.position.y,v.position.z);
   v.u=coord(random);v.v=coord(random);
   v.light_red=colour(random);v.light_green=colour(random);v.light_blue=colour(random);
   v.offset_color=random();
  }
  if(trial%23==0)input[2]=input[1];
  for(unsigned cull=0;cull<4;++cull){
   pvr_vertex_t actual[8],expected[8];
   memset(actual,0xcd,sizeof(actual));memset(expected,0xcd,sizeof(expected));
   reference::FrameStats before;re4dc::render::ClipStats after;
   auto n=reference::clip_projected_triangle(input,expected,cull,&before);
   auto m=re4dc::render::clip_projected_triangle(input,actual,cull,parameters,&after);
   assert(n==m && n<=2);
   assert(!memcmp(expected,actual,sizeof(actual)));
   assert(before.room_near_trivial_accepts==after.accepts);
   assert(before.room_near_trivial_rejects==after.rejects);
   assert(before.room_near_crossings==after.crossings);
  }
 }
 pvr_poly_hdr_t header;memset(&header,0x5a,sizeof(header));
 alignas(32) pvr_vertex_t packet[5]{};unsigned count=999;
 re4dc::render::begin_pvr_packet(packet,count,header);
 assert(count==1 && !memcmp(packet,&header,sizeof(header)));
 for(unsigned i=1;i<5;++i)packet[i].flags=i==4?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX;
 re4dc::render::submit_pvr(packet,sizeof(packet));
 assert(copied==sizeof(packet) && !memcmp(submitted,packet,sizeof(packet)));
 memset(packet,0xee,sizeof(packet)); // producer storage can be reused after copy
 assert(memcmp(submitted,packet,sizeof(packet)));
}
"""
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);(p/"dc").mkdir()
   (p/"dc/pvr.h").write_text("#pragma once\n#include <cstddef>\n#include <cstdint>\nstruct pvr_vertex_t{std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb;};\nstruct pvr_poly_hdr_t{std::uint32_t words[8];};\n#define PVR_CMD_VERTEX 0xe0000000U\n#define PVR_CMD_VERTEX_EOL 0xf0000000U\nint pvr_prim(const void*,std::size_t);\n")
   cpp=p/"test.cpp";cpp.write_text(declarations+reference+checks);exe=p/"test"
   subprocess.run(["g++","-std=c++20","-O2","-I"+str(p),"-I"+str(ROOT/"port/dreamcast/room"),str(cpp),str(ROOT/"port/dreamcast/room/pvr_geometry.cpp"),"-o",str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=="__main__":unittest.main()
