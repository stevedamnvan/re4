"""Native single-owner submission: source hold, retirement and KOS flip policy.
Exercises the actual adapter bodies and applies the pinned KOS patch to its source.
No hardware timing or scene-fidelity acceptance is implied by these fixtures.
"""
from pathlib import Path
import os,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
BASE='804b3195ebd1a06a27cc2b3a5eacf7a2429040a3'
KOS=Path(os.environ.get('RE4DC_KOS_REFERENCE','/root/work/kos'))

def compile_run(code):
 with tempfile.TemporaryDirectory() as d:
  p=Path(d);(p/'check.cpp').write_text('#include \"native_render_profile.hpp\"\n'+code)
  subprocess.run(['g++','-std=c++20','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(p/'check.cpp'),'-o',str(p/'check')],check=True)
  subprocess.run([str(p/'check')],check=True)

@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class NativeStream(unittest.TestCase):
 @unittest.skipUnless((KOS/'.git').exists(),'pinned KOS source required')
 def test_actual_patched_manual_flip(self):
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d)
   for name in ('kernel/arch/dreamcast/hardware/pvr/pvr_irq.c','kernel/arch/dreamcast/include/dc/pvr.h'):
    p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(subprocess.check_output(['git','show',BASE+':'+name],cwd=KOS))
   subprocess.run(['git','apply','--check',str(ROOT/'port/dreamcast/patches/kos-804b319-manual-flip.patch')],cwd=tmp,check=True)
   subprocess.run(['git','apply',str(ROOT/'port/dreamcast/patches/kos-804b319-manual-flip.patch')],cwd=tmp,check=True)
   source=(tmp/'kernel/arch/dreamcast/hardware/pvr/pvr_irq.c').read_text()
  policy=source[source.index('static bool pvr_manual_flip;'):source.index('/*\n   PVR interrupt handler')]
  handler=source[source.index('void pvr_vblank_handler('):source.index('void pvr_int_handler(')]
  code=r'''
#include <cassert>
#include <cstdint>
#define irq_disable_scoped() ((void)0)
struct State {bool valid=true;int ta_busy=0,render_busy=0,render_completed=0,view_target=0;} pvr_state;
unsigned flips=0,wakes=0,renders=0;bool timeout=false;
constexpr int PVR_SYNC_VBLANK=1,PVR_SYNC_PAGEFLIP=2;
void pvr_sync_stats(int){}void pvr_sync_view(){++flips;}
void pvr_render_lists(){++renders;}void genwait_wake_all(void*){++wakes;}
void pvr_vblank_handler(uint32_t,void*);
int genwait_wait(void*,const char*,int){if(timeout)return -1;pvr_vblank_handler(0,nullptr);return 0;}
'''+policy+handler+r'''
int main(){
 // Existing default auto-flip remains intact.
 pvr_state.render_completed=1;pvr_vblank_handler(0,nullptr);assert(flips==1 && pvr_state.view_target==1 && !pvr_state.render_completed);
 assert(pvr_set_manual_flip(true)==0);
 for(unsigned n=0;n<100;++n){
  pvr_state.render_completed=1;auto front=pvr_state.view_target;auto old=flips;
  for(int vblank=0;vblank<10;++vblank)pvr_vblank_handler(0,nullptr);
  assert(pvr_state.render_completed && pvr_state.view_target==front && flips==old);
  assert(pvr_resolve_frame(false)==0);assert(!pvr_state.render_completed && pvr_state.view_target==front);
  pvr_state.render_completed=1;assert(pvr_resolve_frame(true)==0);
  assert(!pvr_state.render_completed && pvr_state.view_target==(front^1) && flips==old+1);
 }
 assert(pvr_resolve_frame(true)==-1); // no completed frame
 pvr_state.render_completed=1;pvr_state.ta_busy=1;assert(pvr_resolve_frame(true)==-1);
 pvr_state.ta_busy=0;pvr_state.render_busy=1;assert(pvr_resolve_frame(false)==-1);
 pvr_state.render_busy=0;assert(pvr_set_manual_flip(false)==-1);
 timeout=true;auto old=flips;assert(pvr_resolve_frame(true)==-1);pvr_vblank_handler(0,nullptr);assert(flips==old && pvr_state.render_completed);
 timeout=false;assert(pvr_resolve_frame(true)==0 && flips==old+1);
 assert(pvr_set_manual_flip(false)==0);pvr_state.render_completed=1;pvr_vblank_handler(0,nullptr);assert(flips==old+2);
}
'''
  compile_run(code)

 def test_stream_ownership_hold_black_and_retire(self):
  source=(ROOT/'port/dreamcast/game/platform/native_ui.cpp').read_text()
  helpers='#if RE4DC_PVR_STREAM\n'+source[source.index('bool stream_scene,'):source.index('unsigned image_size(')]
  retire=source[source.index('extern "C" void re4dc_ui_retire_room()'):source.index('extern "C" void re4dc_ui_init()')]
  end=source[source.index('extern "C" void re4dc_ui_end_frame('):source.index('extern "C" int re4dc_model_diagnostic_enabled()')]
  end=end.replace('    const auto render_end=timer_us_gettime64();','')
  end=end[:end.index('    for(const auto& e:entries)if(e.valid)')]+'}\n'
  start=source.index('extern "C" void re4dc_model_packet_abort()')
  abort=source[start:source.index('\n}',start)+3]
  code=r'''
#include <cassert>
#include <stdexcept>
#define RE4DC_PVR_STREAM 1
#define PVR_LIST_TR_POLY 2
#define PVR_LIST_OP_POLY 0
#define PVR_LIST_PT_POLY 4
using pvr_list_t=int;
extern "C" void re4dc_prepare_model_assets(){}
extern "C" void re4dc_model_retire_draw_plans(){}
#define PVR_TA_INPUT 0x1000
unsigned frame_pvr_calls=0,frame_pvr_bytes=0;
unsigned current=0,locks=0,owner=99,submitted=0,finishes=0,flips=0,closes=0,fences=0,presents=0;
bool opened=false,done=false,fail_fence=false,black=false;
void sq_lock(void*){assert(!locks || owner==current);owner=current;++locks;}
void sq_unlock(){assert(locks && owner==current);--locks;}
void pvr_scene_begin(){assert(!opened && !done);opened=true;}
int pvr_list_begin(int){sq_lock(nullptr);return 0;}
int pvr_list_finish(){assert(opened && locks);sq_unlock();return 0;}
int pvr_scene_finish(){assert(opened && !locks);opened=false;done=true;++finishes;return 0;}
int pvr_resolve_frame(bool show){assert(done && !opened);done=false;if(show)++flips;return 0;}
namespace re4dc::render {void submit_pvr(const void*,unsigned bytes){assert(opened && locks && owner==current);submitted+=bytes;}}
namespace re4dc::gpu {
enum class FenceResult{ready,failed};
FenceResult quiesce(){assert(!opened && !locks);++fences;return fail_fence?FenceResult::failed:FenceResult::ready;}
}
void re4dc_missing(const char*){throw std::runtime_error("explicit failure");}
struct Entry{bool live=true;};Entry entries[2];Entry* model_handle=nullptr;
void close_entry(Entry& e){assert(!opened && !done && !locks);if(e.live){e.live=false;++closes;}}
struct Table{void clear(){}} room_identities;
struct EnemyIdentity{Table table;void* archive=(void*)1;} enemy_identities[2];
bool ready=true,frame_ready=true;unsigned nquad,model_used,nsource,identity_hits,frame;
void re4dc_model_draw_plan_frame(unsigned){}
int re4dc_vi_black(){return black;}
'''+helpers+retire+abort+r'''
extern "C" void re4dc_ui_present(){++presents;stream_close(true);}
'''+end+r'''
int main(){
 int packet=1;
 // SQ lock released between packets, including task-local operations.
 stream_send(&packet,32);assert(!locks && opened);current=1;sq_lock(nullptr);sq_unlock();current=0;
 stream_send(&packet,64);assert(submitted==96 && !locks);re4dc_ui_end_frame(1);assert(flips==1 && finishes==1 && presents==1);
 // Source late hold keeps the front buffer; cached uploads remain live.
 stream_send(&packet,32);re4dc_ui_end_frame(0);assert(flips==1 && !opened && !done && !closes && stream_discards==1);
 // Source task can retire after a packet without waiting on main's open list.
 stream_send(&packet,32);current=1;re4dc_ui_retire_room();assert(stream_retire && stream_aborted && !closes);
 re4dc_ui_retire_room();assert(!closes);current=0;re4dc_ui_end_frame(1);
 assert(flips==1 && closes==2 && !stream_retire && !opened && !done);
 stream_aborted=false;for(auto& e:entries)e.live=true;
 // A late VI-black request discards prior geometry and presents an empty scene.
 stream_send(&packet,32);unsigned old_finishes=finishes;black=true;re4dc_ui_end_frame(1);
 assert(finishes==old_finishes+2 && flips==2 && stream_black_frames==1);
 // Black + hold must retain the previous front, without forcing a black flip.
 stream_send(&packet,32);re4dc_ui_end_frame(0);assert(flips==2);black=false;
 // Late failure in a chunked model discards the whole frame, retaining cache.
 stream_send(&packet,32);model_used=9;model_handle=&entries[0];re4dc_model_packet_abort();
 assert(stream_aborted && !model_used && !model_handle);re4dc_ui_end_frame(1);
 assert(flips==2 && !opened && !done && closes==2);stream_aborted=false;
 // Retirement when no scene is open uses the existing immediate fence.
 re4dc_ui_retire_room();assert(closes==4 && !stream_retire);
 stream_send(&packet,32);fail_fence=true;bool failed=false;
 try{re4dc_ui_end_frame(1);}catch(const std::runtime_error&){failed=true;}
 assert(failed && flips==2 && done); // no successful presentation on failed fence
}
'''
  compile_run(code)


 def test_integrated_deferred_source_views(self):
  source=(ROOT/'port/dreamcast/game/platform/native_ui.cpp').read_text()
  structs=source[source.index('using SourceLighting='):source.index('\n#endif',source.index('using SourceLighting='))]
  bodies=source[source.index('extern "C" int re4dc_model_defer_part('):source.index('extern "C" void* re4dc_model_static_lighting_storage(')]
  compile_run(r'''
#include "native_model.h"
#include <cassert>
#include <new>
#include <algorithm>
#include <vector>
#include <cstring>
#include <cstddef>
#define RE4DC_D349_RENDERER_STACK 1
using pvr_list_t=int;
constexpr int PVR_LIST_OP_POLY=0,PVR_LIST_PT_POLY=4,PVR_LIST_TR_POLY=2;
alignas(32) unsigned char frame_storage[256*sizeof(Re4dcUiQuad)];
unsigned nquad=0,frame_queue_peak=0,frame_queue_drops=0;
constexpr unsigned kModelDeferredSpillBytes=8192;
alignas(32) unsigned char spill[8192];
extern "C" void* re4dc_model_deferred_storage(unsigned* bytes){*bytes=sizeof(spill);return spill;}
bool frame_ready=true,stream_aborted=false;
std::vector<unsigned> draws,passes;bool retire_in_draw=false;
void stream_select(pvr_list_t p){assert(p==PVR_LIST_OP_POLY || p==PVR_LIST_TR_POLY);passes.push_back(p);}
void re4dc_model_result(unsigned,unsigned,unsigned){}
extern "C" void re4dc_model_invalidate_static_lighting(){}
'''+structs+r'''
extern "C" void re4dc_model_submit(const Re4dcModelPart* p){
 assert(draining_parts);
 draws.push_back(p->image.width);
 assert(p->lighting && p->lighting->material[0]==p->image.width);
 assert(p->lighting->lights[7].color[0]==73);
 assert(!re4dc_model_defer_part(p));
 if(retire_in_draw)re4dc_model_invalidate_pending();
}
'''+bodies+r'''
int main(){
 Re4dcModelPart p{};re4dc::render::SourceLighting lighting{};p.lighting=&lighting;
 p.depth_mode=0;p.alpha_state=255;p.blend=0;
 assert(!re4dc_model_defer_part(&p)); // opaque stays synchronous
 p.alpha_state=128;
 lighting.enable=1;lighting.mask=128;lighting.lights[7].color[0]=73;
 for(unsigned n=1;n<=3;++n){
   p.image.width=n;lighting.material[0]=n;
   assert(re4dc_model_defer_part(&p));
 }
 lighting.material[0]=99; // source mutable state is not retained by pointer
 assert(draws.empty() && deferred_count==3);
 re4dc_model_finish_source_draws();
 assert((draws==std::vector<unsigned>{1,2,3}));
 assert((passes==std::vector<unsigned>{PVR_LIST_TR_POLY}));
 assert(!deferred_first && source_draws_finished && !draining_parts);
 // No draw from after Render may survive into reused source primitive storage.
 assert(!re4dc_model_defer_part(&p));
 source_draws_finished=false;re4dc_model_finish_source_draws();
 assert(source_draws_finished); // empty barrier still ends borrowing
 // Owner generation retirement during an I/O yield cancels remaining views.
 source_draws_finished=false;retire_in_draw=true;
 p.image.width=9;lighting.material[0]=9;assert(re4dc_model_defer_part(&p));
 assert(re4dc_model_defer_part(&p));unsigned before=draws.size();
 re4dc_model_finish_source_draws();
 assert(stream_aborted && draws.size()==before+1 && !deferred_first);
 // Many parts share source frame state without retaining caller storage.
 stream_aborted=false;source_draws_finished=false;retire_in_draw=false;reset_deferred();
 const auto draw_start=draws.size();
 for(unsigned n=1;n<=240;++n){p.image.width=9;lighting.material[0]=9;p.uv_offset[0]=float(n);assert(re4dc_model_defer_part(&p));}
 assert(!stream_aborted && deferred_count==240);
 re4dc_model_finish_source_draws();assert(draws.size()==draw_start+240);
 for(unsigned n=1;n<=240;++n)assert(draws[draw_start+n-1]==9);
 // Different actor/object normal transforms still share immutable selected
 // light records. Restored per-model transforms and source values stay exact.
 stream_aborted=false;source_draws_finished=false;reset_deferred();
 for(unsigned n=0;n<120;++n){lighting.normal_matrix[0]=float(n);p.image.width=9;lighting.material[0]=9;assert(re4dc_model_defer_part(&p));}
 assert(!stream_aborted && deferred_count==120);
 re4dc_model_finish_source_draws();
 // Bounded queue never overwrites existing UI data or becomes a partial frame.
 stream_aborted=false;source_draws_finished=false;retire_in_draw=false;
 nquad=255;frame_storage[0]=73;
 for(unsigned n=0;n<1000 && !stream_aborted;++n){p.uv_offset[0]=float(n);assert(re4dc_model_defer_part(&p));}
 assert(stream_aborted && deferred_drops==1 && frame_storage[0]==73);
 re4dc_model_invalidate_pending();assert(!deferred_first);
}
''')

 def test_source_swap_keeps_ppc_and_delivers_hold(self):
  source=(ROOT/'src/game/main_sub.cpp').read_text()
  body=source[source.index('void Render_swap()'):source.index('// Start of the game frame:',source.index('void Render_swap()'))]
  old=subprocess.check_output(['git','show','d09e995:src/game/main_sub.cpp'],cwd=ROOT,text=True)
  old=old[old.index('void Render_swap()'):old.index('// Start of the game frame:',old.index('void Render_swap()'))]
  def ppc(text):return subprocess.check_output(['g++','-E','-P','-D__PPC__','-x','c++','-'],input=text,text=True)
  self.assertEqual(ppc(body),ppc(old))
  compile_run(r'''
#include <cassert>
#define RE4DC_GAME 1
struct G{unsigned System_flg;} g;G* pG=&g;
void* pFrame_buff[2]={(void*)1,(void*)2};void* pCurrent_buff=pFrame_buff[0];
int decisions=0,last=-1,sets=0,flushes=0;
void re4dc_ui_end_frame(int p){++decisions;last=p;}
void VISetNextFrameBuffer(void*){++sets;}void VIFlush(){++flushes;}
'''+body+r'''
int main(){Render_swap();assert(decisions==1 && last==1 && sets==1 && flushes==1 && pCurrent_buff==pFrame_buff[1]);g.System_flg=0x400;Render_swap();assert(decisions==2 && last==0 && sets==1 && flushes==2 && pCurrent_buff==pFrame_buff[1]);}
''')

if __name__=='__main__':unittest.main()
