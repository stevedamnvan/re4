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
#include <cassert>
#include <cmath>
#include <cstring>
#include <vector>
unsigned status=99,capacity=100,committed=0,input,output;
pvr_vertex_t pending[100],owned[100];
extern "C" int re4dc_model_diagnostic_enabled(){return 1;}
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart*,Re4dcModelPacket* p){*p={pending,capacity,1,1};return 1;}
extern "C" void re4dc_model_packet_commit(unsigned n){memcpy(owned,pending,n*32);committed=n;}
extern "C" void re4dc_model_result(unsigned r,unsigned i,unsigned o){status=r;input=i;output=o;}
int pvr_prim(const void*,std::size_t){assert(false);return -1;}
std::vector<unsigned char> stream(unsigned op,std::initializer_list<unsigned> ids,bool color=false){
 std::vector<unsigned char> result{(unsigned char)op,0,(unsigned char)ids.size()};
 for(unsigned id:ids){result.push_back(id>>8);result.push_back(id);result.push_back(0);result.push_back(0);
  if(color){result.push_back(0);result.push_back(0);} result.push_back(0);result.push_back(id);}
 return result;
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
 auto strips=stream(0x98,{0,1,3,2});p.cull=2;run(strips);assert(committed==6);p.cull=0;
 auto fan=stream(0xa0,{0,1,2,3});run(fan);assert(committed==6);
 // Captured native packet survives source preparation storage being overwritten.
 auto before=owned[0];pos[0][0]=0;assert(!memcmp(&before,&owned[0],32));run(q);assert(owned[0].x==320);pos[0][0]=-2;
 // Source skinned arrays use six-byte stride, not the rigid palette-id stride.
 short skin[4][3]={{-2,-2,0},{2,-2,0},{2,2,0},{-2,2,0}};
 p.positions=(unsigned char*)skin;p.position_stride=6;run(q);assert(fabs(owned[0].x-256)<.001);
 // Crossing the actual source near plane invokes the shared clipper.
 skin[0][2]=10;run(q);assert(status==0 && committed>0);skin[0][2]=0;
 // Whole-part rollback even if the first triangle fit; no partial part published.
 capacity=3;run(q);assert(status==3 && committed==0);capacity=100;
 auto invalid=q;invalid[4]=8;run(invalid);assert(status==1 && committed==0);
 auto trunc=q;trunc.pop_back();run(trunc);assert(status==1);
 auto badop=q;badop[0]=0x61;run(badop);assert(status==1);
 auto badquad=stream(0x80,{0,1,2});run(badquad);assert(status==1);
 // Colored-corner identity adds a BE index; UV CPU values are signed Q8.
 short signeduv[4][2]={{-256,0},{256,0},{256,256},{-256,256}};
 p.flags=0x80000000;p.uv=(unsigned char*)signeduv;auto colored=stream(0x90,{0,1,2},true);run(colored);
 assert(status==0 && owned[0].u==-1 && owned[1].u==1);
 p.projection[0]=1;run(colored);assert(status==1); // unsupported ortho is explicit
}
"""
   (root/"fixture.cpp").write_text(code)
   game=ROOT/"port/dreamcast/game";room=ROOT/"port/dreamcast/room"
   exe=root/"check"
   subprocess.run(["g++","-std=c++20","-O2","-fsanitize=address,undefined","-fno-omit-frame-pointer",
    "-I"+str(root),"-I"+str(game/"platform/include"),"-I"+str(room),str(root/"fixture.cpp"),
    str(game/"platform/native_model.cpp"),str(room/"pvr_geometry.cpp"),"-o",str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=="__main__":unittest.main()
