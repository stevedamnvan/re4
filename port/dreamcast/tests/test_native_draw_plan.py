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
unsigned lighting_invalidations=0;
extern "C" void re4dc_model_invalidate_static_lighting(){++lighting_invalidations;}
extern "C" void re4dc_model_invalidate_pending(){}
extern "C" void re4dc_log(const char*,...){}
extern "C" void re4dc_missing(const char*){assert(false);}
extern "C" int re4dc_ui_heap_free(){return 66592;}
alignas(32) unsigned char native_metadata[32768];
extern "C" void* re4dc_model_metadata_storage(unsigned* bytes){*bytes=sizeof(native_metadata);return native_metadata;}
const re4dc::render::NativeDrawPlan* install(const Re4dcModelPart* p,int* invalid){
 int result=re4dc_model_prepare_draw_plan(p);*invalid=result<0;
 return result>0?re4dc_model_acquire_draw_plan(p,invalid):nullptr;
}
unsigned index(const Re4dcModelPart& p,const re4dc::render::NativeDrawPlan* plan,unsigned corner,unsigned field=0){
 const auto* c=p.stream+plan->primitives()[0].source_offset+corner*6+field;
 return (unsigned(c[0])<<8)|c[1];
}
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
  assert(re4dc_model_begin_asset_update());assert(!re4dc_model_begin_asset_update());
  const auto before_lookup=*re4dc_model_draw_plan_stats();
  assert(!re4dc_model_acquire_draw_plan(&p,&invalid));
  assert(re4dc_model_draw_plan_stats()->source_bytes==before_lookup.source_bytes);
  assert(re4dc_model_draw_plan_stats()->used==before_lookup.used);
  const auto* plan=install(&p,&invalid);assert(plan && !invalid);
  assert(plan->primitive_count==1 && plan->corner_count==4);
  assert(plan->primitives()[0].topology==re4dc::render::DrawTopology::strip);
  assert(index(p,plan,3)==3 && index(p,plan,2,4)==2);
  re4dc_model_release_draw_plan();
  const auto before=*re4dc_model_draw_plan_stats();
  for(unsigned i=0;i<100;++i){assert(re4dc_model_prepare_draw_plan(&p)==1);assert(re4dc_model_acquire_draw_plan(&p,&invalid)==plan);re4dc_model_release_draw_plan();}
  const auto after=*re4dc_model_draw_plan_stats();
  assert(after.source_bytes==before.source_bytes && after.installs==before.installs);
  assert(after.hits-before.hits==200 && after.used==before.used);
  assert(re4dc_model_acquire_draw_plan(&p,&invalid)==plan);
  re4dc_model_retire_draw_plans(); // leased structural records and live source remain valid until return
  assert(index(p,plan,3)==3);
  assert(!re4dc_model_acquire_draw_plan(&p,&invalid));
  re4dc_model_release_draw_plan();
  assert(re4dc_model_draw_plan_stats()->used==0 && re4dc_model_draw_plan_stats()->capacity==0);
  assert(!re4dc_model_acquire_draw_plan(&p,&invalid));
 }
 // Reuse the exact source address after explicit owner replacement.
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),0);
 auto* old=install(&p,&invalid);assert(old);
 re4dc_model_unbind_draw_owner(&key);
 assert(index(p,old,0)==0);re4dc_model_release_draw_plan();
 put16(archive.data()+35,2); // source replacement follows last live reader
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),0);
 auto* changed=install(&p,&invalid);assert(changed && index(p,changed,0)==2);
 re4dc_model_release_draw_plan();

 // Bounds use source identity and quantization, not just equal coordinates.
 re4dc_model_unbind_draw_owner(&key);
 stream(archive,4);archive.resize(archive.size()+32,0);
 p.part=archive.data();p.stream=archive.data()+32;p.stream_bytes=27;
 p.positions=archive.data()+59;p.position_stride=8;p.shift=1;p.static_geometry=1;
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),0);
 const auto* bounded=install(&p,&invalid);
 assert(bounded && re4dc_model_acquired_bounds());re4dc_model_release_draw_plan();
 ++p.shift;
 assert(re4dc_model_acquire_draw_plan(&p,&invalid)==bounded && !re4dc_model_acquired_bounds());
 re4dc_model_release_draw_plan();--p.shift;p.positions+=8;
 assert(re4dc_model_acquire_draw_plan(&p,&invalid)==bounded && !re4dc_model_acquired_bounds());
 re4dc_model_release_draw_plan();p.positions-=8;p.static_geometry=0;
 assert(re4dc_model_acquire_draw_plan(&p,&invalid)==bounded && !re4dc_model_acquired_bounds());
 re4dc_model_release_draw_plan();p.static_geometry=1;
 assert(re4dc_model_acquire_draw_plan(&p,&invalid)==bounded && re4dc_model_acquired_bounds());
 re4dc_model_release_draw_plan();p.static_geometry=0;
 // Invalid indices and truncated/unknown commands cannot become native plans.
 put16(archive.data()+35,7);re4dc_model_reset_draw_plans();
 assert(!install(&p,&invalid) && invalid==1);
 re4dc_model_unbind_draw_owner(&key);stream(archive,4);p.part=archive.data();p.stream=archive.data()+32;
 re4dc::render::DrawPlanRequirements req;
 for(unsigned bytes=1;bytes<27;++bytes)assert(!re4dc::render::inspect_draw_plan(p.stream,bytes,false,4,1,req));
 archive[32]=0x61;assert(!re4dc::render::inspect_draw_plan(p.stream,27,false,4,1,req));
 // Direct source-index batches preserve primitive boundaries without another
 // per-corner representation. Asset generation still owns all source backing.
 {
  std::vector<unsigned char> source(3+600*6);source[0]=0x90;put16(source.data()+1,600);
  for(unsigned i=0;i<600;++i){put16(source.data()+3+i*6,(i/3)%210);put16(source.data()+5+i*6,i%2);put16(source.data()+7+i*6,i%4);}
  re4dc::render::DrawPlanRequirements d;
  assert(re4dc::render::inspect_draw_plan(source.data(),source.size(),false,210,2,d));
  std::vector<unsigned> backing((d.bytes+3)/4);
  const auto* topology=re4dc::render::prepare_draw_plan(backing.data(),d.bytes,source.data(),source.size(),false,d);
  const auto bytes=re4dc::render::prepare_draw_locals(nullptr,0,*topology,source.data(),false);
  std::vector<unsigned> local((bytes+3)/4);
  const auto partial=re4dc::render::prepare_draw_locals(local.data(),32,*topology,source.data(),false);
  assert(partial==32 && ((const re4dc::render::DrawLocalPlan*)local.data())->batches==1);
  assert(re4dc::render::prepare_draw_locals(local.data(),bytes,*topology,source.data(),false)==bytes);
  const auto& plan=*(const re4dc::render::DrawLocalPlan*)local.data();
  assert(plan.batches>1 && plan.qualified_corners==600);
  assert(bytes==sizeof(plan)+plan.batches*sizeof(re4dc::render::LocalBatch));
  unsigned visited=0;
  for(unsigned i=0;i<plan.batches;++i){const auto& batch=plan.entries()[i];
   assert(batch.first_corner%3==0 && batch.corner_count%3==0);
   for(unsigned j=0;j<batch.corner_count;++j){const auto* c=source.data()+3+(batch.first_corner+j)*6;
    unsigned vi=(c[0]<<8)|c[1],ni=(c[2]<<8)|c[3];
    assert(!batch.position_count || vi-batch.position_base<batch.position_count);
    assert(!batch.normal_count || ni-batch.normal_base<batch.normal_count);++visited;
   }
  }
  assert(visited==600);
  // An oversized whole strip retains safe independent normal reuse only.
  source[0]=0x98;
  assert(re4dc::render::inspect_draw_plan(source.data(),source.size(),false,210,2,d));
  topology=re4dc::render::prepare_draw_plan(backing.data(),d.bytes,source.data(),source.size(),false,d);
  assert(re4dc::render::prepare_draw_locals(local.data(),bytes,*topology,source.data(),false)==32);
  const auto& strip=((const re4dc::render::DrawLocalPlan*)local.data())->entries()[0];
  assert(strip.corner_count==600 && strip.position_count==0 && strip.normal_count==2);
  assert(strip.shade_mode==re4dc::render::LocalShadeMode::none);
 }
 // Corner count does not determine metadata bytes: one 9000-corner command
 // occupies the same 24-byte plan as a four-corner command.
 stream(archive,9000);p.part=archive.data();p.stream=archive.data()+32;p.stream_bytes=archive.size()-32;
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),1);
 auto* large=install(&p,&invalid);assert(large && !invalid);
 assert(large->primitive_count==1 && large->corner_count==9000);
 assert(re4dc::render::inspect_draw_plan(p.stream,p.stream_bytes,false,4,1,req) && req.bytes==24);
 re4dc_model_release_draw_plan();re4dc_model_retire_draw_plans();
 // Repeated source commands retain one span; original bytes remain backing.
 archive.assign(32+9000*21,0);
 for(unsigned i=0;i<9000;++i){auto* c=archive.data()+32+i*21;c[0]=0x90;put16(c+1,3);}
 p.part=archive.data();p.stream=archive.data()+32;p.stream_bytes=archive.size()-32;
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),1);
 auto* repeated=install(&p,&invalid);assert(repeated && !invalid);
 assert(repeated->primitive_count==1 && repeated->primitives()[0].repeats()==9000);
 assert(repeated->primitives()[0].corner_offset(8999,6)==3+8999*21);
 re4dc_model_release_draw_plan();re4dc_model_retire_draw_plans();
 // Alternating topology cannot share spans; bounded failure stays explicit.
 for(unsigned i=1;i<9000;i+=2)archive[32+i*21]=0x98;
 re4dc_model_bind_draw_owner(&key,archive.data(),archive.size(),1);
 assert(!install(&p,&invalid) && !invalid);
 const auto bytes=re4dc_model_draw_plan_stats()->source_bytes;
 assert(!re4dc_model_acquire_draw_plan(&p,&invalid) && !invalid);
 assert(re4dc_model_draw_plan_stats()->source_bytes==bytes);
 assert(re4dc_model_draw_plan_stats()->used>0 && re4dc_model_draw_plan_stats()->used<=32768); // table is retained even on failed admission
 re4dc_model_retire_draw_plans();

 // Global admission sees 460 useful spans, including two later valuable groups.
 // Repeated commands compress topology, never the source-backed local spans.
 {
  std::vector<unsigned char> sources[4];Re4dcModelPart parts[4]{};int keys[4];
  const unsigned batches[]={300,80,80,1},counts[]={20,30,12,3};
  for(unsigned group=0;group<4;++group){
   auto& src=sources[group];const unsigned command=3+counts[group]*6;
   src.assign(32+batches[group]*command,0);
   for(unsigned i=0;i<batches[group];++i){auto* c=src.data()+32+i*command;c[0]=0x98;put16(c+1,counts[group]);
    for(unsigned j=0;j<counts[group];++j){unsigned id=group==3?j:(i%2)*400;put16(c+3+j*6,id);put16(c+5+j*6,id);}}
   auto& part=parts[group];part.part=src.data();part.stream=src.data()+32;part.stream_bytes=src.size()-32;
   part.position_count=part.normal_count=401;
   re4dc_model_bind_draw_owner(&keys[group],src.data(),src.size(),1);
  }
  const auto originals=std::vector<std::vector<unsigned char>>(sources,sources+4);
  assert(re4dc_model_begin_asset_update());
  const auto invalidations=lighting_invalidations;
  for(unsigned i=0;i<4;++i){assert(re4dc_model_prepare_draw_plan(&parts[i])==1);
   assert(re4dc_model_acquire_draw_plan(&parts[i],&invalid));assert(!re4dc_model_acquired_locals());re4dc_model_release_draw_plan();}
  for(unsigned i=0;i<3;++i)assert(re4dc_model_prepare_draw_plan(&parts[2])==1);
  assert(lighting_invalidations==invalidations);
  re4dc_model_finish_asset_update();assert(lighting_invalidations==invalidations+1);
  std::vector<re4dc::render::LocalBatch> copies[4];const re4dc::render::DrawLocalPlan* pointers[4]{};
  unsigned total=0;
  for(unsigned group=0;group<4;++group){
   assert(re4dc_model_acquire_draw_plan(&parts[group],&invalid));auto* local=re4dc_model_acquired_locals();pointers[group]=local;
   if(group==3)assert(!local);
   else {
    assert(local&&local->batches==(group==0?96:80));total+=local->batches;
    assert(local->bytes==12+20*local->batches&&local->qualified_corners==local->batches*counts[group]);
    copies[group].assign(local->entries(),local->entries()+local->batches);
    for(unsigned j=0;j<local->batches;++j){const auto& b=local->entries()[j];
     assert(b.corner_count==counts[group]&&b.first_corner%counts[group]==0);
     if(j)assert(local->entries()[j-1].first_corner<b.first_corner);
     unsigned source_batch=b.first_corner/counts[group];assert(source_batch<batches[group]);
     unsigned id=(source_batch%2)*400;
     assert(b.position_base==id&&b.normal_base==id&&b.position_count==1&&b.normal_count==1);
     assert(b.shade_mode==re4dc::render::LocalShadeMode::by_position&&b.reuse_score==4*(counts[group]-1));
    }
   }
   re4dc_model_release_draw_plan();assert(sources[group]==originals[group]);
  }
  assert(total==256&&re4dc_model_draw_plan_stats()->used<=32768);
  const auto stable=*re4dc_model_draw_plan_stats();
  for(unsigned iteration=0;iteration<3;++iteration){
   assert(!re4dc_model_begin_asset_update());
   for(unsigned i=0;i<4;++i)assert(re4dc_model_prepare_draw_plan(&parts[i])==1);
   for(unsigned i=0;i<3;++i)assert(re4dc_model_prepare_draw_plan(&parts[2])==1);
   re4dc_model_finish_asset_update();
  }
  assert(re4dc_model_draw_plan_stats()->source_bytes==stable.source_bytes&&re4dc_model_draw_plan_stats()->installs==stable.installs);
  assert(re4dc_model_draw_plan_stats()->used==stable.used&&lighting_invalidations==invalidations+1);
  for(unsigned group=0;group<4;++group){assert(re4dc_model_acquire_draw_plan(&parts[group],&invalid));
   assert(re4dc_model_acquired_locals()==pointers[group]);re4dc_model_release_draw_plan();}
  assert(re4dc_model_acquire_draw_plan(&parts[2],&invalid));
  auto* leased=re4dc_model_acquired_locals();assert(leased);
  re4dc_model_reset_draw_plans();
  assert(std::memcmp(leased->entries(),copies[2].data(),copies[2].size()*sizeof(copies[2][0]))==0);
  assert(!re4dc_model_acquire_draw_plan(&parts[2],&invalid));re4dc_model_release_draw_plan();
  assert(re4dc_model_begin_asset_update());assert(re4dc_model_prepare_draw_plan(&parts[2])==1);
  re4dc_model_finish_asset_update();assert(re4dc_model_acquire_draw_plan(&parts[2],&invalid));
  assert(re4dc_model_acquired_locals()->batches==80);re4dc_model_release_draw_plan();
  re4dc_model_unbind_draw_owner(&keys[2]);assert(!re4dc_model_acquire_draw_plan(&parts[2],&invalid));
  re4dc_model_bind_draw_owner(&keys[2],sources[2].data(),sources[2].size(),1);
  assert(install(&parts[2],&invalid)&&re4dc_model_acquired_locals());re4dc_model_release_draw_plan();
  for(unsigned group=0;group<4;++group)assert(sources[group]==originals[group]);
  re4dc_model_retire_draw_plans();assert(re4dc_model_draw_plan_stats()->used==0);
 }
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
