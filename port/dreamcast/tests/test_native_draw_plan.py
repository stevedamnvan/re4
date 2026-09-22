"""Prepared structural transport and actual archive-owner lifetimes, asset-free."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class NativeDrawPlan(unittest.TestCase):
 def test_actual_owner_reuse_replacement_retirement_and_capacity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'kos').mkdir()
   (p/'kos/fs.h').write_text('''#pragma once
#include <sys/types.h>
#include <cstddef>
#include <fcntl.h>
using file_t=int;
#define FILEHND_INVALID -1
file_t fs_open(const char*,int);ssize_t fs_read(file_t,void*,size_t);
ssize_t fs_total(file_t);int fs_close(file_t);
''')
   (p/'kos.h').write_text('#include <kos/fs.h>\n#include <cstdint>\nstd::uint64_t timer_us_gettime64();\n')
   (p/'fixture.cpp').write_text(r'''
#include "native_model.h"
#include "native_draw_plan.hpp"
#include <cassert>
#include <vector>
#include <cstring>
extern "C" void re4dc_log(const char*,...){}
extern "C" void re4dc_missing(const char*){assert(false);}
extern "C" int re4dc_ui_heap_free(){return 66592;}
extern "C" const Re4dcModelWorkStats* re4dc_model_work_stats(){static Re4dcModelWorkStats s{};return &s;}
void put16(unsigned char* p,unsigned n){p[0]=n>>8;p[1]=n;}
void stream(std::vector<unsigned char>& a,unsigned count){
 a.assign(32+3+count*6,0);a[32]=0x98;put16(a.data()+33,count);
 for(unsigned i=0;i<count;++i){put16(a.data()+35+i*6,i%4);put16(a.data()+37+i*6,0);put16(a.data()+39+i*6,i%4);}
}
int main(){
 std::vector<unsigned char> archive;stream(archive,4);
 Re4dcModelPart p{};p.part=archive.data();p.stream=archive.data()+32;p.stream_bytes=archive.size()-32;
 p.position_count=4;p.normal_count=1;
 int key,invalid=0;
 assert(!re4dc_model_acquire_draw_plan(&p,&invalid) && !invalid);
 for(unsigned cycle=0;cycle<3;++cycle){
  re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),1);
  const auto* plan=re4dc_model_acquire_draw_plan(&p,&invalid);assert(plan && !invalid);
  assert(plan->primitive_count==1 && plan->corner_count==4);
  assert(plan->primitives()[0].topology==re4dc::render::DrawTopology::strip);
  assert(plan->corners()[3].position==3 && plan->corners()[2].uv==2);
  re4dc_model_release_draw_plan();
  const auto before=*re4dc_model_draw_plan_stats();
  for(unsigned i=0;i<100;++i){assert(re4dc_model_acquire_draw_plan(&p,&invalid)==plan);re4dc_model_release_draw_plan();}
  const auto after=*re4dc_model_draw_plan_stats();
  assert(after.source_bytes==before.source_bytes && after.installs==before.installs);
  assert(after.hits-before.hits==100 && after.used==before.used);
  assert(re4dc_model_acquire_draw_plan(&p,&invalid)==plan);
  re4dc_model_retire_draw_plans(); // still leased: copied records remain live
  assert(plan->corners()[3].position==3);
  assert(!re4dc_model_acquire_draw_plan(&p,&invalid));
  re4dc_model_release_draw_plan();
  assert(re4dc_model_draw_plan_stats()->used==0 && re4dc_model_draw_plan_stats()->capacity==0);
  assert(!re4dc_model_acquire_draw_plan(&p,&invalid));
 }
 // Reuse the exact source address after explicit owner replacement.
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),0);
 auto* old=re4dc_model_acquire_draw_plan(&p,&invalid);assert(old);
 re4dc_model_unbind_draw_owner(&key);put16(archive.data()+35,2);
 assert(old->corners()[0].position==0);re4dc_model_release_draw_plan();
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),0);
 auto* changed=re4dc_model_acquire_draw_plan(&p,&invalid);assert(changed && changed->corners()[0].position==2);
 re4dc_model_release_draw_plan();
 // Invalid indices and truncated/unknown commands cannot become native plans.
 put16(archive.data()+35,7);re4dc_model_reset_draw_plans();
 assert(!re4dc_model_acquire_draw_plan(&p,&invalid) && invalid==1);
 re4dc_model_unbind_draw_owner(&key);stream(archive,4);p.part=archive.data();p.stream=archive.data()+32;
 re4dc::render::DrawPlanRequirements req;
 for(unsigned bytes=1;bytes<27;++bytes)assert(!re4dc::render::inspect_draw_plan(p.stream,bytes,false,4,1,req));
 archive[32]=0x61;assert(!re4dc::render::inspect_draw_plan(p.stream,27,false,4,1,req));
 // Oversized admission fails once, then remains an explicit uncached part.
 stream(archive,9000);p.part=archive.data();p.stream=archive.data()+32;p.stream_bytes=archive.size()-32;
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),1);
 assert(!re4dc_model_acquire_draw_plan(&p,&invalid) && !invalid);
 const auto bytes=re4dc_model_draw_plan_stats()->source_bytes;
 assert(!re4dc_model_acquire_draw_plan(&p,&invalid) && !invalid);
 assert(re4dc_model_draw_plan_stats()->source_bytes==bytes);
 assert(re4dc_model_draw_plan_stats()->used==0);
 re4dc_model_retire_draw_plans();
}
''')
   game=ROOT/'port/dreamcast/game';room=ROOT/'port/dreamcast/room'
   subprocess.run(['g++','-std=c++20','-O2','-DRE4DC_MODEL_DRAW_PLANS=1',
    '-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fsanitize=address,undefined',
    '-I'+str(p),'-I'+str(game/'platform/include'),'-I'+str(room),str(p/'fixture.cpp'),
    str(game/'platform/native_draw_plan_owner.cpp'),str(room/'native_draw_plan.cpp'),
    str(room/'room_storage.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
if __name__=='__main__':unittest.main()
