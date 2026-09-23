// Narrow ID-quad backend. Reuses the scene Package and owned storage reader.
// Candidate scope: common unmasked UI; unsupported effects are counted/rejected.
#include <kos.h>
#include <dc/sq.h>
#include <fcntl.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <malloc.h>
#include <new>
#include <cstddef>
#include <algorithm>
#ifndef RE4DC_D349_RENDERER_STACK
#define RE4DC_D349_RENDERER_STACK 0
#endif
// Frame-pipeline knobs (obj/pipeline30.h; all default off = previous image).
#ifndef RE4DC_PVR_FAST_WAKE
#define RE4DC_PVR_FAST_WAKE 0
#endif
#ifndef RE4DC_PVR_PIPELINE
#define RE4DC_PVR_PIPELINE 0   // 1 presenter thread (pinned KOS); 2 KOS async present (patched KOS)
#endif
#ifndef RE4DC_TA_DIRECT
#define RE4DC_TA_DIRECT 0
#endif
#ifndef RE4DC_BRIDGE_LEAN
#define RE4DC_BRIDGE_LEAN 0
#endif
#ifndef RE4DC_TA_GUARD
#define RE4DC_TA_GUARD 0
#endif
#ifndef RE4DC_PERF_HUD
#define RE4DC_PERF_HUD 0
#endif
// D367 frontend30 (obj/frontend30.h; default off = previous image): staging
// without libcall compares/copies or redundant zero-fills, one-pass view
// diffs, indexed texture-key lookups (same keys, same first match).
#ifndef RE4DC_COPY_LEAN
#define RE4DC_COPY_LEAN 0
#endif
// VRAM layout (defaults = the previous image: 1 MiB, one bank used, 16-word bins).
#ifndef RE4DC_TA_VERTBUF_KB
#define RE4DC_TA_VERTBUF_KB 1024
#endif
#ifndef RE4DC_TA_DOUBLEBUF
#define RE4DC_TA_DOUBLEBUF 0
#endif
#ifndef RE4DC_TA_OPB_BINS
#define RE4DC_TA_OPB_BINS 16
#endif
#ifndef RE4DC_TA_OPB_OVERFLOW
#define RE4DC_TA_OPB_OVERFLOW 3
#endif
#if (RE4DC_PVR_PIPELINE || RE4DC_TA_DIRECT) && !RE4DC_PVR_STREAM
#error PVR_PIPELINE and TA_DIRECT extend the PVR_STREAM=1 frame owner
#endif
#if RE4DC_PVR_FAST_WAKE || RE4DC_PVR_PIPELINE || RE4DC_TA_GUARD
#include <dc/asic.h>
#include <dc/vblank.h>
#include <kos/genwait.h>
#include <kos/sem.h>
#endif
#include "native_ui.h"
#include "native_model.h"
#include "native_static.h"
#include "native_render_profile.hpp"
#include "pc_sampler.h"
#include "re4dc_platform.h"
#include "../../room/texture_package.hpp"
#include "../../room/room_storage.hpp"
#include "../../room/gpu_lifecycle.hpp"
#include "../../room/pvr_geometry.hpp"

namespace {
constexpr unsigned kQuadCount=256, kTextureCount=RE4DC_PVR_STREAM?80:48, kSourceCount=RE4DC_PVR_STREAM?128:256, kVramBudget=4*1024*1024;
struct Key { unsigned crc,fnv; bool operator==(const Key& b)const{return crc==b.crc && fnv==b.fnv;} };
struct Entry { re4dc::texture::Package package; Key key{}; unsigned frame=0; bool valid=false;
#if RE4DC_D349_RENDERER_STACK
    pvr_poly_hdr_t model_header{};unsigned model_header_key=~0U;
#endif
};
struct Source { Re4dcUiImage image{}; Key key{}; };
// Current source view needs >64 simultaneously pinned native handles. Reuse
// bytes from the optional source-key lookup cache, not the game heap/queue.
// An uncached source descriptor still resolves through its existing owner table.
Entry entries[kTextureCount]; Source sources[kSourceCount]; unsigned nsource;
static_assert(sizeof(entries)+sizeof(sources)<=64*sizeof(Entry)+256*sizeof(Source));
re4dc::texture::SourceIdentityTable room_identities,core_identities,option_identities,player_identities,weapon_identities;unsigned identity_hits;
// Match the recovered loader's four module owners; texture uploads still share
// the existing cache and VRAM budget. These views own no texels or allocations.
struct EnemyIdentity { void* archive=nullptr; re4dc::texture::SourceIdentityTable table; };
EnemyIdentity enemy_identities[4];
// UI grows upward, deferred source draw snapshots downward in the EXISTING
// quad allocation. No full PVR packet copy or additional source heap budget.
alignas(32) unsigned char frame_storage[kQuadCount*sizeof(Re4dcUiQuad)];
Re4dcUiQuad* const quads=reinterpret_cast<Re4dcUiQuad*>(frame_storage);
Entry* handles[kQuadCount]; unsigned nquad,frame,used,peak,staging_peak;
#if RE4DC_D349_RENDERER_STACK
// Only selected lights and current channel/matrix parameters are snapshotted.
// Identical state is shared within this frame; no unselected eight-light copy
// per part, extra allocation, or persistent source pose representation.
using SourceLighting=re4dc::render::SourceLighting;
using SourceLight=re4dc::render::SourceLight;
constexpr unsigned light_parameters=offsetof(SourceLighting,normal_matrix);
constexpr unsigned light_parameter_bytes=sizeof(SourceLighting)-light_parameters;
struct DeferredLightSet { DeferredLightSet* next;unsigned mask; };
DeferredLightSet* deferred_light_sets=nullptr;
struct DeferredLighting { DeferredLighting* next;const DeferredLightSet* lights; };
// Lossless source-state snapshots in the same bounded queue. Camera/projection,
// common array bindings and material defaults are repeated across parts; retain
// one frame basis and only differing 32-bit words. No geometry/pose is copied,
// no quantization, persistent cache, source-heap cut or extra queue allocation.
constexpr unsigned kViewWords=sizeof(Re4dcModelPart)/sizeof(unsigned);
constexpr unsigned kViewMasks=(kViewWords+31)/32;
static_assert(sizeof(Re4dcModelPart)%sizeof(unsigned)==0);
struct DeferredPart { DeferredPart* next;DeferredLighting* lighting;unsigned changed[kViewMasks]; };
Re4dcModelPart* deferred_basis=nullptr;
#if RE4DC_BRIDGE_LEAN
// Same word-difference encoding. The 4-byte memcpy()s above were libcalls on
// SH4 (strict alignment through char*): D367 T spent 4.4 ms/frame of memcpy/
// memset in view_words plus 1.4 ms in its own loop. Re4dcModelPart is 4-byte
// aligned (pointers/floats/unsigned only), so read it as may_alias words.
typedef unsigned __attribute__((may_alias)) AliasWord;
static_assert(alignof(Re4dcModelPart)>=alignof(unsigned));
unsigned view_words(const Re4dcModelPart& p,const Re4dcModelPart& base,unsigned* masks,unsigned* values){
    const auto* a=reinterpret_cast<const AliasWord*>(&p);
    const auto* b=reinterpret_cast<const AliasWord*>(&base);
    unsigned count=0;
    for(unsigned m=0;m<kViewMasks;++m){
        unsigned bits=0;const unsigned first=m*32,last=std::min(kViewWords,first+32);
        for(unsigned i=first;i<last;++i){
            const unsigned word=a[i];
            if(word!=b[i]){bits|=1U<<(i-first);if(values)values[count]=word;++count;}
        }
        if(masks)masks[m]=bits;
    }
    return count;
}
Re4dcModelPart restore_view(const DeferredPart* node){
    Re4dcModelPart out=*deferred_basis;const auto* values=reinterpret_cast<const unsigned*>(node+1);
    auto* words=reinterpret_cast<AliasWord*>(&out);
    for(unsigned m=0;m<kViewMasks;++m)
        for(unsigned bits=node->changed[m];bits;bits&=bits-1)words[m*32+__builtin_ctz(bits)]=*values++;
    return out;
}
#else
unsigned view_words(const Re4dcModelPart& p,const Re4dcModelPart& base,unsigned* masks,unsigned* values){
    unsigned count=0;if(masks)std::memset(masks,0,kViewMasks*sizeof(unsigned));
    for(unsigned i=0;i<kViewWords;++i){
        unsigned a,b;std::memcpy(&a,reinterpret_cast<const char*>(&p)+i*4,4);
        std::memcpy(&b,reinterpret_cast<const char*>(&base)+i*4,4);
        if(a!=b){if(masks)masks[i/32]|=1U<<(i%32);if(values)values[count]=a;++count;}
    }
    return count;
}
Re4dcModelPart restore_view(const DeferredPart* node){
    Re4dcModelPart out=*deferred_basis;const auto* values=reinterpret_cast<const unsigned*>(node+1);
    for(unsigned i=0;i<kViewWords;++i)if(node->changed[i/32]&(1U<<(i%32))){
        std::memcpy(reinterpret_cast<char*>(&out)+i*4,values++,4);
    }
    return out;
}
#endif
DeferredLighting* deferred_lights=nullptr;
unsigned selected_mask(const SourceLighting& s){return s.enable?s.mask&255U:0U;}
unsigned deferred_light_bytes(const SourceLighting&){return sizeof(DeferredLighting)+light_parameter_bytes;}
unsigned deferred_set_bytes(const SourceLighting& s){
    return sizeof(DeferredLightSet)+__builtin_popcount(selected_mask(s))*sizeof(SourceLight);
}
#if RE4DC_COPY_LEAN
// Same equality, stores and restores as below, as aligned word loops: the
// memcmp()/memcpy() calls were libcalls (D367 LD: memcmp 1.1 ms/frame from
// these compares). Records are 4-byte aligned and word-sized (static_asserts).
typedef unsigned __attribute__((may_alias)) LightWord;
static_assert(sizeof(SourceLight)%4==0 && light_parameter_bytes%4==0 && light_parameters%4==0);
static_assert(sizeof(DeferredLightSet)%4==0 && sizeof(DeferredLighting)%4==0);
inline bool same_words(const void* a,const void* b,unsigned bytes){
    const auto* x=static_cast<const LightWord*>(a);const auto* y=static_cast<const LightWord*>(b);
    for(unsigned i=0;i<bytes/4;++i)if(x[i]!=y[i])return false;
    return true;
}
inline void copy_words(void* to,const void* from,unsigned bytes){
    auto* x=static_cast<LightWord*>(to);const auto* y=static_cast<const LightWord*>(from);
    for(unsigned i=0;i<bytes/4;++i)x[i]=y[i];
}
bool same_light_set(const DeferredLightSet* stored,const SourceLighting& source){
    if(stored->mask!=selected_mask(source))return false;
    auto* data=reinterpret_cast<const unsigned char*>(stored+1);
    for(unsigned i=0;i<8;++i)if(stored->mask&(1U<<i)){
        if(!same_words(data,&source.lights[i],sizeof(SourceLight)))return false;
        data+=sizeof(SourceLight);
    }
    return true;
}
bool same_lighting(const DeferredLighting* stored,const SourceLighting& source){
    return same_words(stored+1,reinterpret_cast<const unsigned char*>(&source)+light_parameters,light_parameter_bytes)
        && same_light_set(stored->lights,source);
}
void store_light_set(DeferredLightSet* stored,const SourceLighting& source){
    stored->mask=selected_mask(source);
    auto* data=reinterpret_cast<unsigned char*>(stored+1);
    for(unsigned i=0;i<8;++i)if(stored->mask&(1U<<i)){
        copy_words(data,&source.lights[i],sizeof(SourceLight));data+=sizeof(SourceLight);
    }
}
void store_lighting(DeferredLighting* stored,const SourceLighting& source){
    copy_words(stored+1,reinterpret_cast<const unsigned char*>(&source)+light_parameters,light_parameter_bytes);
}
// Into a default-constructed SourceLighting (unselected lights stay zero, as
// restore_lighting()): no second 0.5 KiB zero-fill and whole-struct copy.
void restore_lighting_into(const DeferredLighting* stored,SourceLighting& source){
    copy_words(reinterpret_cast<unsigned char*>(&source)+light_parameters,stored+1,light_parameter_bytes);
    auto* data=reinterpret_cast<const unsigned char*>(stored->lights+1);
    for(unsigned i=0;i<8;++i)if(stored->lights->mask&(1U<<i)){
        copy_words(&source.lights[i],data,sizeof(SourceLight));data+=sizeof(SourceLight);
    }
}
#else
bool same_light_set(const DeferredLightSet* stored,const SourceLighting& source){
    if(stored->mask!=selected_mask(source))return false;
    auto* data=reinterpret_cast<const unsigned char*>(stored+1);
    for(unsigned i=0;i<8;++i)if(stored->mask&(1U<<i)){
        if(std::memcmp(data,&source.lights[i],sizeof(SourceLight)))return false;
        data+=sizeof(SourceLight);
    }
    return true;
}
bool same_lighting(const DeferredLighting* stored,const SourceLighting& source){
    return !std::memcmp(stored+1,reinterpret_cast<const unsigned char*>(&source)+light_parameters,light_parameter_bytes)
        && same_light_set(stored->lights,source);
}
void store_light_set(DeferredLightSet* stored,const SourceLighting& source){
    stored->mask=selected_mask(source);
    auto* data=reinterpret_cast<unsigned char*>(stored+1);
    for(unsigned i=0;i<8;++i)if(stored->mask&(1U<<i)){
        std::memcpy(data,&source.lights[i],sizeof(SourceLight));data+=sizeof(SourceLight);
    }
}
void store_lighting(DeferredLighting* stored,const SourceLighting& source){
    std::memcpy(stored+1,reinterpret_cast<const unsigned char*>(&source)+light_parameters,light_parameter_bytes);
}
SourceLighting restore_lighting(const DeferredLighting* stored){
    SourceLighting source{};
    std::memcpy(reinterpret_cast<unsigned char*>(&source)+light_parameters,stored+1,light_parameter_bytes);
    auto* data=reinterpret_cast<const unsigned char*>(stored->lights+1);
    for(unsigned i=0;i<8;++i)if(stored->lights->mask&(1U<<i)){
        std::memcpy(&source.lights[i],data,sizeof(SourceLight));data+=sizeof(SourceLight);
    }
    return source;
}
#endif
DeferredPart* deferred_first=nullptr;DeferredPart* deferred_last=nullptr;
unsigned deferred_top=sizeof(frame_storage),deferred_peak=0,deferred_count=0,deferred_drops=0;
unsigned char* deferred_spill=nullptr;unsigned deferred_spill_top=0,deferred_spill_capacity=0;
bool draining_parts=false,source_draws_finished=false;
pvr_list_t draining_list=PVR_LIST_TR_POLY;
void reset_deferred(){deferred_spill=nullptr;deferred_spill_top=deferred_spill_capacity=0;deferred_light_sets=nullptr;deferred_basis=nullptr;deferred_lights=nullptr;deferred_first=deferred_last=nullptr;deferred_top=sizeof(frame_storage);deferred_count=0;}
pvr_list_t select_model_pass(const Re4dcModelPart* p){
    // Alpha is from source material/vertex channels, not texture file format.
    // The separately masked path is classified after its native binding qualifies.
    if(!source_draws_finished && !(p->material_flags&4) && p->depth_mode==0 &&
       (p->blend==4 || (p->blend==0 && p->alpha_state==255)))return PVR_LIST_OP_POLY;
    return PVR_LIST_TR_POLY;
}
#endif
unsigned dropped,unsupported,missing,drawn,culled,loads,reclaimed; bool ready,frame_ready;
extern "C" int re4dc_vi_black();
// Diagnostic only: 64 KiB of copied native packets, allocated on first model.
// Roll back an entire part on overflow. No deferred source/primitive pointers.
constexpr unsigned kModelSlabBytes=64*1024;
constexpr unsigned kModelMetadataBytes=RE4DC_MODEL_DRAW_PLANS?32*1024:0;
// Whole-stack bisection: two static-cache contexts yielded ~1 hit/frame while
// late UI collided with source snapshots. Reassign those same 8 KiB to bounded
// frame ownership; evaluate unchanged source lighting without that tiny cache.
constexpr unsigned kModelStaticLightBytes=0;
constexpr unsigned kModelDeferredSpillBytes=RE4DC_D349_RENDERER_STACK?8192:0;
constexpr unsigned kModelPreparationBytes=RE4DC_D349_RENDERER_STACK?12288:0;
constexpr unsigned kModelPacketBytes=kModelSlabBytes-kModelMetadataBytes-kModelStaticLightBytes-kModelDeferredSpillBytes-kModelPreparationBytes;
pvr_vertex_t* model_packets; unsigned model_used,model_pending; Entry* model_handle;
int model_diagnostic=-1;
unsigned model_parts,model_invalid,model_resource,model_overflow,model_input,model_output,model_peak,model_presented;
unsigned model_capacity_rejects,model_state_rejects,model_texture_rejects,model_wrap_rejects,model_empty_parts,model_scale_rebuilds;
unsigned model_state_bits[8];
unsigned model_alpha_material,model_alpha_vertex,model_alpha_faded;
unsigned model_header_hits,model_header_builds;
Re4dcNativeFrameStats completed_frame{};
re4dc::profile::Snapshot completed_render_profile{};
re4dc::profile::Source render_source_begin{};
Re4dcModelWorkStats frame_work_start{};
Re4dcPreparationStats preparation_start{};
struct PreparationFrame {volatile unsigned sequence;unsigned frame;Re4dcPreparationStats work;unsigned scratch_bytes,packet_bytes;};
PreparationFrame completed_preparation{};
unsigned frame_header_hits,frame_header_builds,frame_pvr_calls,frame_pvr_bytes;
unsigned frame_queue_peak,frame_queue_drops;
std::uint64_t frame_render_start;

#if RE4DC_PVR_FAST_WAKE || RE4DC_PVR_PIPELINE
// KOS wakes a thread blocked in pvr_wait_render_done()/pvr_resolve_frame()
// from the render-done and vblank interrupts without rescheduling (only the
// TA-done path calls thd_schedule(true)). With THD_SCHED_HZ=100 the waiter
// then sleeps until the next 10 ms tick: D367 T idled 29 ms/frame as ONE run
// per frame of ~25 or ~35 ms (render 7.5 + vblank + up to 2 x 10 ms ticks).
// Chain both interrupts and reschedule, as KOS's TA-done path does, only
// while a native PVR waiter is registered. No game thread is woken or
// reordered here: thd_schedule(true) keeps the interrupted thread at the
// front of its priority group.
volatile unsigned pvr_waiters;
asic_evt_handler_entry_t kos_render_done{};
unsigned wake_renders,wake_vblanks;
void render_done_chain(uint32_t code,void* data){
    (void)data;
    if(kos_render_done.hdl)kos_render_done.hdl(code,kos_render_done.data);
    if(pvr_waiters){++wake_renders;thd_schedule(true);}
}
void vblank_wake(uint32_t,void*){
    if(pvr_waiters){++wake_vblanks;thd_schedule(true);}
}
struct PvrWaiter {
    PvrWaiter(){const int o=irq_disable();pvr_waiters=pvr_waiters+1;irq_restore(o);}
    ~PvrWaiter(){const int o=irq_disable();pvr_waiters=pvr_waiters-1;irq_restore(o);}
};
void install_fast_wake(){
    kos_render_done=asic_evt_set_handler(ASIC_EVT_PVR_RENDERDONE_TSP,render_done_chain,nullptr);
    // Registered after pvr_init(): runs after KOS's flip handler.
    const int handle=vblank_handler_add(vblank_wake,nullptr);
    re4dc_log("native pvr wake: render-done chained=%d vblank handler=%d\n",kos_render_done.hdl!=nullptr,handle);
}
#endif
#if RE4DC_TA_GUARD
// Real-hardware TA capacity guard. Flycast neither enforces nor reports TA
// capacity (KOS ta_used stays 0 there); a console does: the TA writes every
// strip into the current bank's vertex (parameter) buffer (~12 B per strip
// header + 24 B per float-UV vertex without offset colour) and one 4-byte
// object pointer per touched tile into the OPBs. Overflow drops or corrupts
// geometry, or halts the render. As dca3 does (rwdc.cpp vertexBufferFree /
// freeVertexTarget / vertexOverflown), skip whole parts once free space falls
// below an adaptive reserve and detect overflow per scene. TA_GUARD=2 also
// declines to present an overflowed scene (the previous image stays shown;
// game state, logic and inputs are untouched either way).
constexpr unsigned kGuardVertbuf=RE4DC_TA_VERTBUF_KB*1024U;
constexpr unsigned kGuardMin=64*1024,kGuardMax=kGuardVertbuf/2,kParamPerHeader=12,kParamPerVertex=24;
unsigned guard_reserve=kGuardMin,guard_scale=256;   // adaptive reserve; hw/estimate x256
unsigned guard_sw;                                  // estimated parameter bytes, this scene
volatile unsigned guard_ta_faults,guard_render_faults; // ASIC error events (interrupt)
unsigned guard_skips,guard_fault_frames,guard_render_fault_frames,guard_discards;
unsigned guard_hw_last,guard_hw_peak,guard_sw_last,guard_sw_peak,guard_opb_last;
asic_evt_handler_entry_t guard_kos[5];
constexpr std::uint16_t kGuardEvents[5]={ASIC_EVT_PVR_OPB_OUTOFMEM,ASIC_EVT_PVR_TA_INPUT_OVERFLOW,
    ASIC_EVT_PVR_TA_INPUT_ERR,ASIC_EVT_PVR_ISP_OUTOFMEM,ASIC_EVT_PVR_STRIP_HALT};
void guard_event(uint32_t code,void* data){
    const unsigned i=unsigned(reinterpret_cast<std::uintptr_t>(data));
    if(i<5 && guard_kos[i].hdl)guard_kos[i].hdl(code,guard_kos[i].data); // KOS PVR_RENDER_DBG builds only
    if(i<3)guard_ta_faults=guard_ta_faults|(1U<<i);else guard_render_faults=guard_render_faults|(1U<<i);
}
void install_guard(){
    // Release KOS leaves these events unhooked and disabled; enable them.
    for(unsigned i=0;i<5;++i){
        guard_kos[i]=asic_evt_set_handler(kGuardEvents[i],guard_event,reinterpret_cast<void*>(std::uintptr_t(i)));
        asic_evt_enable(kGuardEvents[i],ASIC_IRQ_DEFAULT);
    }
    re4dc_log("native TA guard: vertbuf=%u reserve=%u..%u discard=%d estimate=%u+%u/vertex\n",
        kGuardVertbuf,kGuardMin,kGuardMax,RE4DC_TA_GUARD>=2,kParamPerHeader,kParamPerVertex);
}
unsigned guard_estimate(){return unsigned((std::uint64_t(guard_sw)*guard_scale)>>8);}
unsigned guard_hw_free(){
    const unsigned start=PVR_GET(PVR_TA_VERTBUF_START),pos=PVR_GET(PVR_TA_VERTBUF_POS),end=PVR_GET(PVR_TA_VERTBUF_END);
    if(end<=start || pos<start)return ~0U; // registers not live (emulator): estimate only
    return pos<end?end-pos:0;
}
// Part admission (reserve): translucent drain parts keep a quarter reserve so
// the opaque list is what yields first; UI quads are never refused.
bool guard_admit(bool draining){
    const unsigned need=draining?guard_reserve/4:guard_reserve;
    const unsigned est=guard_estimate();
    const unsigned sw_free=est<kGuardVertbuf?kGuardVertbuf-est:0;
    if(std::min(sw_free,guard_hw_free())>=need)return true;
    ++guard_skips;return false;
}
void guard_account(unsigned header_slots,unsigned vertex_slots){
    guard_sw+=header_slots*kParamPerHeader+vertex_slots*kParamPerVertex;
}
void guard_scene_begin(){guard_sw=0;guard_ta_faults=0;}
// Before the last list closes (afterwards KOS may already retarget the TA
// registers to the next bank). Returns the TA-time fault bits of the scene.
unsigned guard_scene_end(){
    const unsigned start=PVR_GET(PVR_TA_VERTBUF_START),pos=PVR_GET(PVR_TA_VERTBUF_POS),end=PVR_GET(PVR_TA_VERTBUF_END);
    const unsigned opb=PVR_GET(PVR_TA_OPB_POS),opb_end=PVR_GET(PVR_TA_OPB_END),opb_init=PVR_GET(PVR_TA_OPB_INIT);
    unsigned faults=guard_ta_faults;
    if(pos>=end)faults|=8;
    if(opb*4>=opb_end && opb!=opb_init)faults|=16; // dca3 vertexOverflown(); Flycast's OPB_POS differs
    guard_hw_last=pos>start?pos-start:0;guard_sw_last=guard_sw;guard_opb_last=opb;
    guard_hw_peak=std::max(guard_hw_peak,guard_hw_last);guard_sw_peak=std::max(guard_sw_peak,guard_sw_last);
    // Calibrate the estimate on hardware (Flycast reports 0: keep 1.0).
    if(guard_hw_last && guard_sw && !(faults&8))
        guard_scale=std::clamp(unsigned((std::uint64_t(guard_hw_last)<<8)/guard_sw),128U,384U);
    if(faults){++guard_fault_frames;guard_reserve=std::min(guard_reserve+32*1024,kGuardMax);}
    else if(guard_reserve>kGuardMin+4*1024)guard_reserve-=4*1024;else guard_reserve=kGuardMin;
    guard_ta_faults=0;
    return faults;
}
// After the render fence: render-time faults of the scene being resolved.
bool guard_present(bool present,unsigned ta_faults){
    const int o=irq_disable();const unsigned render=guard_render_faults;guard_render_faults=0;irq_restore(o);
    if(render)++guard_render_fault_frames;
    if((ta_faults|render) && present && RE4DC_TA_GUARD>=2){++guard_discards;return false;}
    return present;
}
#endif
#if RE4DC_PVR_PIPELINE
// Frame N's render and flip overlap frame N+1's CPU work. The late present/
// discard decision is unchanged (Render_swap still makes it); a presenter
// thread performs the same fence + pvr_resolve_frame() the frame owner used
// to block in. Every later PVR owner step waits for that resolution first:
// the next scene begin (single TA bank, render_completed must be clear) and,
// through re4dc_pvr_vram_fence(), any VRAM free or upload. Game threads and
// the tick order are untouched; the presenter never calls source code.
volatile unsigned present_submitted,present_resolved,present_failures;
unsigned present_reported,fence_blocked,fence_timeouts;
std::uint64_t fence_wait_us;
void present_report(){
    const unsigned failures=present_failures;
    if(failures!=present_reported){
        present_reported=failures;
        if(failures&1)re4dc_missing("native stream completion fence failed");
        if(failures&2)re4dc_missing("native source presentation resolve failed");
    }
}
#if RE4DC_PVR_PIPELINE==2
// PIPELINE=2: no presenter thread. Needs the KOS async-present patch
// (pvr_present_async/pvr_present_wait): the decision is recorded at scene
// finish and applied by the render-done IRQ; the flip happens in the vblank
// IRQ. With TA_DOUBLEBUF=1 frame N+1's TA input also overlaps frame N's render.
// Render faults are only known after the decision, so TA_GUARD>=2 discards on
// TA faults of this scene and render faults of earlier scenes.
void start_presenter(){
    re4dc_log("native frame pipeline: KOS async present (IRQ-applied decision, vblank flip) ta=%s\n",RE4DC_TA_DOUBLEBUF?"double-buffered":"single-bank");
}
void present_fence(){
    if(!pvr_present_pending())return;
    const auto start=timer_us_gettime64();
    if(pvr_present_wait()<0){++fence_timeouts;present_failures=present_failures|1;}
    ++fence_blocked;fence_wait_us+=timer_us_gettime64()-start;
    present_resolved=present_submitted;
    present_report();
}
void present_submit(bool present,unsigned ta_faults){
#if RE4DC_TA_GUARD
    present=guard_present(present,ta_faults);
#else
    (void)ta_faults;
#endif
    present_submitted=present_submitted+1;
    // One decision is outstanding at a time: frame N's flip normally happened
    // long before frame N+1 finishes, so this rarely blocks.
    if(pvr_present_async(present)<0){
        present_fence();
        if(pvr_present_async(present)<0){present_failures=present_failures|2;present_report();}
    }
}
#else
semaphore_t present_request;
volatile bool present_decision;
volatile unsigned present_ta_faults;
alignas(32) unsigned char presenter_stack[4096];
void* presenter_main(void*){
    for(;;){
        sem_wait(&present_request);
        bool present=present_decision;
        unsigned failure=0;
        {
            PvrWaiter waiter;
            if(re4dc::gpu::quiesce()!=re4dc::gpu::FenceResult::ready)failure=1;
            else {
#if RE4DC_TA_GUARD
                present=guard_present(present,present_ta_faults);
#endif
                if(pvr_resolve_frame(present)<0)failure=2;
            }
        }
        const int o=irq_disable();
        present_failures=present_failures|failure;present_resolved=present_resolved+1;
        genwait_wake_all((void*)&present_resolved);
        irq_restore(o);
    }
    return nullptr;
}
void start_presenter(){
    sem_init(&present_request,0);
    kthread_attr_t a{};
    a.stack_size=sizeof(presenter_stack);a.stack_ptr=presenter_stack;
    a.prio=2;a.label="re4dc-present";a.create_detached=true;
    kthread_t* t=thd_create_ex(&a,presenter_main,nullptr);
    if(!t)re4dc_missing("native presenter thread create failed");
    re4dc_log("native frame pipeline: presenter tid=%d prio=2 stack=static:%u\n",t?int(t->tid):-1,unsigned(sizeof(presenter_stack)));
}
void present_fence(){
    if(present_resolved==present_submitted)return;
    const auto start=timer_us_gettime64();
    {
        PvrWaiter waiter;
        const int o=irq_disable();
        while(present_resolved!=present_submitted)
            if(genwait_wait((void*)&present_resolved,"re4dc present fence",250)<0)++fence_timeouts;
        irq_restore(o);
    }
    ++fence_blocked;fence_wait_us+=timer_us_gettime64()-start;
    present_report();
}
void present_submit(bool present,unsigned ta_faults){
    present_decision=present;present_ta_faults=ta_faults;present_submitted=present_submitted+1;
    sem_signal(&present_request);
    // Let the higher-priority presenter reach its render-done wait now, as
    // OSResumeThread yields to a resumed higher-priority thread.
    thd_pass();
}
#endif
#endif

#if RE4DC_PVR_STREAM
// One serial PVR owner, no extra framebuffer or whole-scene packet copy.
// KOS's opt-in manual flip preserves the source's late presentation decision.
bool stream_scene,stream_aborted,stream_retire;
unsigned stream_model_bytes,stream_peak_bytes,stream_discards,stream_black_frames;
#if RE4DC_TA_DIRECT
bool direct_open;               // re4dc_model_direct_begin/end: SQ held
unsigned direct_parts,direct_slots;
#endif
pvr_list_t stream_list=PVR_LIST_TR_POLY;
#if RE4DC_D349_RENDERER_STACK
pvr_list_t desired_list=PVR_LIST_OP_POLY;
#endif
void stream_open() {
#if RE4DC_PVR_PIPELINE
    present_fence(); // previous scene flipped/discarded: TA bank and back buffer free
#if RE4DC_NATIVE_FOG
    re4dc_fog_frame(); // fog registers: the previous scene no longer renders
#endif
#endif
    pvr_scene_begin();
#if RE4DC_TA_GUARD
    guard_scene_begin();
#endif
#if RE4DC_D349_RENDERER_STACK
    stream_list=desired_list;
#else
    stream_list=PVR_LIST_TR_POLY;
#endif
    if(pvr_list_begin(stream_list)<0)re4dc_missing("native stream list begin failed");
    // Do not retain the main thread's SQ mutex across source task dispatch or
    // file/audio services. Each synchronous packet transfer reacquires it.
    sq_unlock();stream_scene=true;
}
#if RE4DC_D349_RENDERER_STACK
void stream_select(pvr_list_t list){
    desired_list=list;
    if(!stream_scene){stream_open();return;}
    if(stream_list==list)return;
    // End the old list once. Never reopen it or replay source ModelRender.
    sq_lock((void*)PVR_TA_INPUT);
    if(pvr_list_finish()<0 || pvr_list_begin(list)<0)re4dc_missing("native pass transition failed");
    sq_unlock();stream_list=list;
}
#endif
void stream_send(const void* data,unsigned bytes) {
    re4dc::profile::Scope profile_scope(stream_list==PVR_LIST_OP_POLY?re4dc::profile::SubmitOP:
        stream_list==PVR_LIST_PT_POLY?re4dc::profile::SubmitPT:re4dc::profile::SubmitTR);
    ++frame_pvr_calls;frame_pvr_bytes+=bytes;
    if(!stream_scene)stream_open();
    sq_lock((void*)PVR_TA_INPUT);
    re4dc::render::submit_pvr(data,bytes);
    sq_unlock();
#if RE4DC_TA_GUARD
    guard_account(1,bytes/32-1); // every call is one header + its vertices
#endif
}
void stream_close(bool present) {
    RE4DC_PROFILE_SCOPE(PresentFence);
    if(!stream_scene)stream_open();
#if RE4DC_TA_GUARD
    const unsigned ta_faults=guard_scene_end();
#else
    const unsigned ta_faults=0;
#endif
    (void)ta_faults;
    sq_lock((void*)PVR_TA_INPUT);
    if(pvr_list_finish()<0 || pvr_scene_finish()<0)re4dc_missing("native stream finish failed");
    stream_scene=false;
#if RE4DC_PVR_PIPELINE
    present_submit(present,ta_faults); // resolved by the presenter; fenced before reuse
#else
    {
#if RE4DC_PVR_FAST_WAKE
    PvrWaiter waiter;
#endif
    if(re4dc::gpu::quiesce()!=re4dc::gpu::FenceResult::ready)
        re4dc_missing("native stream completion fence failed");
#if RE4DC_TA_GUARD
    const bool shown=guard_present(present,ta_faults);
#else
    const bool shown=present;
#endif
    if(pvr_resolve_frame(shown)<0)re4dc_missing("native source presentation resolve failed");
    }
#endif
    if(!present)++stream_discards;
}
#endif
#if RE4DC_PERF_HUD
// On-screen timing for real consoles (a GDEMU/ODE setup has no serial or BBA
// console, and the RAM log is unreadable there). Untextured TR quads at the
// end of each presented frame; photograph or film the screen. Bars at 4 px/ms
// with ticks at 16.7 / 33.3 / 50 ms, value left of each bar (7-segment, in
// 0.1 ms; TA row in KiB, bar = share of the vertex buffer). Rows, top down:
//   white   flip-to-flip interval (KOS stats: the displayed frame time)
//   green   CPU frame period (re4dc_ui_begin to re4dc_ui_begin)
//   yellow  CPU busy from frame begin to this present
//   cyan    PVR render time of the last scene (real fill/sort cost on HW)
//   magenta present wait of the last frame (fence or blocking resolve)
//   orange  TA parameter bytes of the last scene (red: overflow/fault)
std::uint64_t hud_begin,hud_begin_prev;
struct HudBatch { alignas(32) pvr_vertex_t v[128]; unsigned n=1; };
void hud_flush(HudBatch& b){if(b.n>1)stream_send(b.v,b.n*32);b.n=1;}
void hud_rect(HudBatch& b,float x,float y,float w,float h,std::uint32_t argb){
    if(b.n+4>128)hud_flush(b);
    const float xs[4]={x,x,x+w,x+w},ys[4]={y+h,y,y+h,y};
    for(unsigned k=0;k<4;++k){
        auto& v=b.v[b.n++];
        v.flags=k==3?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX;
        v.x=xs[k];v.y=ys[k];v.z=1.0f;v.u=v.v=0;v.argb=argb;v.oargb=0;
    }
}
void hud_number(HudBatch& b,float x,float y,unsigned value,bool tenths,std::uint32_t argb){
    static const unsigned char seg[10]={0x3f,0x06,0x5b,0x4f,0x66,0x6d,0x7d,0x07,0x7f,0x6f};
    constexpr float W=7,H=12,T=2,P=10;
    value=std::min(value,99999U);
    for(int d=0;d<5;++d){
        const unsigned digit=value%10;
        const float dx=x+(4-d)*P;
        if(d>(tenths?1:0) && value==0)break;           // "0.0" / "0" minimum
        value/=10;
        const unsigned m=seg[digit];
        if(m&1)hud_rect(b,dx,y,W,T,argb);
        if(m&2)hud_rect(b,dx+W-T,y,T,H/2,argb);
        if(m&4)hud_rect(b,dx+W-T,y+H/2,T,H/2,argb);
        if(m&8)hud_rect(b,dx,y+H-T,W,T,argb);
        if(m&16)hud_rect(b,dx,y+H/2,T,H/2,argb);
        if(m&32)hud_rect(b,dx,y,T,H/2,argb);
        if(m&64)hud_rect(b,dx,y+H/2-T/2,W,T,argb);
        if(d==0 && tenths)hud_rect(b,dx-3,y+H-T,2,T,argb);
    }
}
HudBatch hud_batch; // 4 KiB .bss (PERF_HUD only), not the caller's stack
void hud_draw(unsigned flip_us,unsigned render_us,unsigned wait_us,unsigned ta_bytes,unsigned ta_capacity,bool ta_fault){
    HudBatch& b=hud_batch;b.n=1;
    pvr_poly_cxt_t c;pvr_poly_cxt_col(&c,PVR_LIST_TR_POLY);
    c.gen.culling=PVR_CULLING_NONE;c.depth.comparison=PVR_DEPTHCMP_ALWAYS;c.depth.write=PVR_DEPTHWRITE_DISABLE;
    pvr_poly_hdr_t header;pvr_poly_compile(&header,&c);
    std::memcpy(&b.v[0],&header,sizeof(header));
    const std::uint64_t now=timer_us_gettime64();
    const unsigned period=hud_begin_prev?unsigned(hud_begin-hud_begin_prev):0,busy=unsigned(now-hud_begin);
    constexpr float X=40,BX=100,Y=324,R=18,PX=4.0f/1000.0f,MAXW=480;
    const unsigned us[5]={flip_us,period,busy,render_us,wait_us};
    const std::uint32_t colors[6]={0xe0ffffffU,0xe040ff40U,0xe0ffff40U,0xe040ffffU,0xe0ff40ffU,ta_fault?0xf0ff2020U:0xe0ffa040U};
    hud_rect(b,X-4,Y-4,BX-X+MAXW+8,6*R+6,0x90000000U);   // backdrop
    for(unsigned r=0;r<5;++r){
        hud_number(b,X,Y+r*R,(us[r]+50)/100,true,colors[r]);
        hud_rect(b,BX,Y+r*R+2,std::min(MAXW,float(us[r])*PX),8,colors[r]);
    }
    const float ta=ta_capacity?std::min(1.0f,float(ta_bytes)/float(ta_capacity)):0.0f;
    hud_number(b,X,Y+5*R,ta_bytes/1024,false,colors[5]);
    hud_rect(b,BX,Y+5*R+2,ta*MAXW,8,colors[5]);
    hud_rect(b,BX+MAXW,Y+5*R,1,12,0xffffffffU);          // 100% of the vertex buffer
    for(float ms:{16.683f,33.367f,50.05f})hud_rect(b,BX+ms*1000*PX,Y-2,1,5*R,0xffffffffU);
    hud_flush(b);
}
#endif



unsigned image_size(const Re4dcUiImage& i) {
    unsigned bw,bh,bytes;
    switch(i.format) {
    case 0:case 8:case 14:bw=8;bh=8;bytes=32;break;
    case 1:case 2:case 9:bw=8;bh=4;bytes=32;break;
    case 3:case 4:case 5:bw=4;bh=4;bytes=32;break;
    case 6:bw=4;bh=4;bytes=64;break;
    default:return 0;
    }
    return ((i.width+bw-1)/bw)*((i.height+bh-1)/bh)*bytes;
}
#if RE4DC_COPY_LEAN
// The same reflected CRC-32 (0xEDB88320), four bits per table step instead of
// one per loop pass: identical keys (package file names) at ~1/4 the work.
constexpr unsigned kCrcNibble[16]={0x00000000U,0x1db71064U,0x3b6e20c8U,0x26d930acU,0x76dc4190U,0x6b6b51f4U,
    0x4db26158U,0x5005713cU,0xedb88320U,0xf00f9344U,0xd6d6a3e8U,0xcb61b38cU,0x9b64c2b0U,0x86d3d2d4U,0xa00ae278U,0xbdbdf21cU};
void hash_bytes(Key& k,const void* ptr,unsigned size) {
    const auto* p=(const unsigned char*)ptr;
    unsigned crc=k.crc,fnv=k.fnv;
    for(unsigned i=0;i<size;++i) {
        fnv=(fnv^p[i])*16777619U;crc^=p[i];
        crc=(crc>>4)^kCrcNibble[crc&15U];crc=(crc>>4)^kCrcNibble[crc&15U];
    }
    k.crc=crc;k.fnv=fnv;
}
#else
void hash_bytes(Key& k,const void* ptr,unsigned size) {
    const auto* p=(const unsigned char*)ptr;
    for(unsigned i=0;i<size;++i) {
        k.fnv=(k.fnv^p[i])*16777619U;k.crc^=p[i];
        for(unsigned b=0;b<8;++b) k.crc=(k.crc>>1)^(0xedb88320U & (0U-(k.crc&1)));
    }
}
#endif
bool same_image(const Re4dcUiImage& a,const Re4dcUiImage& b) {
    return a.pixels==b.pixels && a.palette==b.palette && a.width==b.width && a.height==b.height &&
           a.format==b.format && a.palette_format==b.palette_format && a.palette_bytes==b.palette_bytes;
}
#if RE4DC_COPY_LEAN
// Direct-mapped hints into sources[] / entries[] (index+1, 0 empty). A hint is
// used only after the full equality test; a miss falls back to the original
// scan. sources[] and valid entries[] never hold duplicates (both are appended
// only after a failed scan), so the hinted match is the scan's first match.
unsigned char source_hint[128],entry_hint[128];
inline unsigned source_slot(const Re4dcUiImage& i){
    const unsigned a=unsigned(reinterpret_cast<std::uintptr_t>(i.pixels))^unsigned(reinterpret_cast<std::uintptr_t>(i.palette));
    return ((a>>5)^(a>>12)^i.format)&127U;
}
static_assert(kSourceCount<255 && kTextureCount<255);
#endif
int external_image_key(const Re4dcUiImage& image,Key& external) {
    int native=room_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv,image.palette,image.palette_format,image.palette_bytes);
    if(!native)native=core_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv,image.palette,image.palette_format,image.palette_bytes);
    if(!native)native=option_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv,image.palette,image.palette_format,image.palette_bytes);
    if(!native)native=player_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv,image.palette,image.palette_format,image.palette_bytes);
    if(!native)native=weapon_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv,image.palette,image.palette_format,image.palette_bytes);
    for(auto& e:enemy_identities)if(!native && e.archive)
        native=e.table.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv,image.palette,image.palette_format,image.palette_bytes);
    return native;
}
bool image_key(const Re4dcUiImage& image,Key& key) {
    Key external{};int native=0;
    const bool indexed=image.format==8 || image.format==9;
    // Indexed external records must qualify the CURRENT retained palette before
    // a pointer-key cache hit. A changed palette cannot reuse an old upload or
    // hash the discarded source indices. Ordinary resident images retain their
    // existing fast path. No cache entries or extra allocation are introduced.
    if(indexed)native=external_image_key(image,external);
    if(native<0){re4dc_log("native source identity: incompatible palette rejected\n");return false;}
#if RE4DC_COPY_LEAN
    const unsigned hint=source_slot(image);
    if(!native){
        const unsigned h=source_hint[hint];
        if(h && h<=nsource && same_image(sources[h-1].image,image)){key=sources[h-1].key;return true;}
        for(unsigned n=0;n<nsource;++n) if(same_image(sources[n].image,image)) {source_hint[hint]=(unsigned char)(n+1);key=sources[n].key;return true;}
    }
#else
    if(!native)for(unsigned n=0;n<nsource;++n) if(same_image(sources[n].image,image)) {key=sources[n].key;return true;}
#endif
    if(!indexed)native=external_image_key(image,external);
    if(native<0){re4dc_log("native source identity: incompatible descriptor rejected\n");return false;}
    if(native) {
        if(identity_hits++<3)re4dc_log("native source identity: %08x-%08x (no source-texel hash)\n",external.crc,external.fnv);
#if RE4DC_COPY_LEAN
        if(!indexed && nsource<kSourceCount){source_hint[hint]=(unsigned char)(nsource+1);sources[nsource++]={image,external};}
#else
        if(!indexed && nsource<kSourceCount)sources[nsource++]={image,external};
#endif
        key=external;return true;
    }
    const unsigned metadata[]={image.width,image.height,image.format,image.palette_format,image.palette_bytes};
    key={0xffffffffU,2166136261U};hash_bytes(key,metadata,sizeof(metadata));
    hash_bytes(key,image.pixels,image_size(image));
    if(image.palette_bytes) hash_bytes(key,image.palette,image.palette_bytes);
    key.crc=~key.crc;
#if RE4DC_COPY_LEAN
    if(nsource<kSourceCount){source_hint[hint]=(unsigned char)(nsource+1);sources[nsource++]={image,key};}
#else
    if(nsource<kSourceCount) sources[nsource++]={image,key};
#endif
    return true;
}
#if RE4DC_D349_RENDERER_STACK
bool model_mask_key(const Re4dcModelPart* p,Key& key){
    Key color{},mask{};
    if(!image_key(p->image,color) || !image_key(p->mask,mask))return false;
    const unsigned words[]={color.crc,color.fnv,mask.crc,mask.fnv};
    key={0xffffffffU,2166136261U};
    hash_bytes(key,"R4MPv001",8);hash_bytes(key,words,sizeof(words));key.crc=~key.crc;
    return true;
}
#endif
void close_entry(Entry& entry) {
    if(entry.valid) used-=entry.package.vram_bytes();
    entry.package.close();entry.valid=false;
#if RE4DC_D349_RENDERER_STACK
    entry.model_header_key=~0U;
#endif
}
Entry* load(const Re4dcUiImage& image,bool pin=true,const Key* prepared_key=nullptr) {
    RE4DC_PROFILE_SCOPE(TextureResolve);RE4DC_PROFILE_COUNT(TextureLookups,1);
    if(!image.pixels || !image_size(image) || !image.width || !image.height || image.width>1024 || image.height>1024) return nullptr;
    Key key{};if(prepared_key)key=*prepared_key;else if(!image_key(image,key))return nullptr;
#if RE4DC_COPY_LEAN
    const unsigned hint=(key.crc^(key.crc>>7)^key.fnv)&127U;
    if(const unsigned h=entry_hint[hint]){
        Entry& e=entries[h-1];
        if(e.valid && e.key==key){if(pin)e.frame=frame;RE4DC_PROFILE_COUNT(TextureHits,1);return &e;}
    }
    for(auto& e:entries) if(e.valid && e.key==key) {entry_hint[hint]=(unsigned char)(&e-entries+1);if(pin)e.frame=frame;RE4DC_PROFILE_COUNT(TextureHits,1);return &e;}
#else
    for(auto& e:entries) if(e.valid && e.key==key) {if(pin)e.frame=frame;RE4DC_PROFILE_COUNT(TextureHits,1);return &e;}
#endif
    Entry* slot=nullptr;
    for(auto& e:entries) if(!e.valid){slot=&e;break;}
    if(!slot) for(auto& e:entries) if(e.frame!=frame && (!slot || e.frame<slot->frame)) slot=&e;
    if(!slot) {RE4DC_PROFILE_COUNT(TextureNoSlot,1);return nullptr;}
    if(slot->valid)RE4DC_PROFILE_COUNT(TextureEvictions,1);
    close_entry(*slot); // caller has completed both TA and render fences
    char path[96];std::sprintf(path,"/cd/dc/tex/%08x-%08x.re4tex",key.crc,key.fnv);
    re4dc_log("native UI: load %s %ux%u fmt=%u\n",path,image.width,image.height,image.format);
    const int heap_before=re4dc_ui_heap_free();
    bool ok=slot->package.open_streamed(path);
    if(!ok) {RE4DC_PROFILE_COUNT(TextureOpenFailures,1);re4dc_log("native UI: package rejected: %s\n",slot->package.error());}
    if(ok) {
        const auto& h=slot->package.header();
        ok=h.texture_count==1 && h.data_size<=kVramBudget;
        if(ok) {
            while(used+h.data_size>kVramBudget) {
                Entry* victim=nullptr;
                for(auto& e:entries) if(e.valid && e.frame!=frame && (!victim || e.frame<victim->frame)) victim=&e;
                if(!victim) {RE4DC_PROFILE_COUNT(TextureBudgetFailures,1);ok=false;break;} RE4DC_PROFILE_COUNT(TextureEvictions,1);close_entry(*victim);
            }
        }
    }
    const unsigned vram_before=pvr_mem_available();
    if(ok) {RE4DC_PROFILE_SCOPE(TextureUpload);
        ok=slot->package.upload() && slot->package.release_payload();
        if(ok){RE4DC_PROFILE_COUNT(TextureUploads,1);RE4DC_PROFILE_COUNT(TextureUploadBytes,slot->package.vram_bytes());}
        else RE4DC_PROFILE_COUNT(TextureUploadFailures,1);
    }
    if(ok && slot->package.textures()[0].payload==re4dc::texture::kPayloadVq){
        const auto& t=slot->package.textures()[0];
        const volatile unsigned char* data=(const volatile unsigned char*)slot->package.pvr_texture(0);
        unsigned fnv=2166136261U;
        for(unsigned n=0;n<t.data_size;++n)fnv=(fnv^data[n])*16777619U;
        re4dc_log("native texture VQ: ptr=%08x bytes=%u raw16=%u format=%08x readback_fnv=%08x free_vram=%u allocation_delta=%u\n",(unsigned)data,t.data_size,t.width*t.height*2,re4dc::texture::pvr_format(t),fnv,(unsigned)pvr_mem_available(),vram_before-(unsigned)pvr_mem_available());
    }
    re4dc_log("native UI: upload %s vram=%u\n",ok?"ok":"FAILED",slot->package.vram_bytes());
    if(!ok) slot->package.close();
    re4dc_log("native UI: bounded upload heap=%d->%d metadata=%u staging=shared-16384 source_allocation=0\n",heap_before,re4dc_ui_heap_free(),slot->package.metadata_bytes());
    if(ok)++loads;
    if(!ok) return nullptr;
    slot->valid=true;slot->key=key;slot->frame=pin?frame:0;used+=slot->package.vram_bytes();
    if(used>peak) peak=used;
    return slot;
}
}
#if RE4DC_PVR_PIPELINE
// Called by room/texture_package.cpp (PVR_PIPELINE builds) before VRAM is
// freed or uploaded: it may be referenced by the scene not yet resolved.
extern "C" void re4dc_pvr_vram_fence(){present_fence();}
#endif
extern "C" void re4dc_ui_invalidate_sources(){nsource=0;re4dc_model_reset_draw_plans();}
extern "C" int re4dc_ui_bind_core(void* archive,unsigned bytes){
    nsource=0;
    const bool ok=core_identities.adopt(archive,bytes);
    if(ok)re4dc_model_bind_draw_owner(&core_identities,archive,bytes,0);
    else re4dc_model_unbind_draw_owner(&core_identities);
    re4dc_log("native core identities: %s count=%u archive=%u metadata_owner=core\n",ok?"ok":"REJECTED",core_identities.count(),bytes);
    return ok;
}
extern "C" int re4dc_ui_bind_room(void* archive,unsigned bytes){
    nsource=0;identity_hits=0;
    const bool ok=room_identities.adopt(archive,bytes);
#if RE4DC_D349_RENDERER_STACK
    re4dc_model_preparation_owner(ok?archive:nullptr);
#endif
    if(ok)re4dc_model_bind_draw_owner(&room_identities,archive,bytes,1);
    else re4dc_model_unbind_draw_owner(&room_identities);
    re4dc_log("native room identities: %s count=%u archive=%u metadata_owner=room\n",ok?"ok":"REJECTED",room_identities.count(),bytes);
    return ok;
}
// Option/death UI remains resident across rooms. Borrow only its validated
// identity table; source overwrite invalidates descriptor lookups first.
extern "C" int re4dc_ui_bind_option(void* archive,unsigned bytes){
    nsource=0;bool ok=option_identities.adopt(archive,bytes);
    if(ok)re4dc_model_bind_draw_owner(&option_identities,archive,bytes,0);
    else re4dc_model_unbind_draw_owner(&option_identities);
    re4dc_log("native option identities: %s count=%u archive=%u\n",ok?"ok":"REJECTED",option_identities.count(),bytes);return ok;
}
extern "C" void re4dc_ui_unbind_option(){re4dc_model_unbind_draw_owner(&option_identities);option_identities.clear();nsource=0;}
// Player and weapon regions persist across room retirement when the source
// retains them. Their explicit source release/overwrite boundaries clear views.
extern "C" int re4dc_ui_bind_player(void* archive,unsigned bytes){
    nsource=0;bool ok=player_identities.adopt(archive,bytes);
    if(ok)re4dc_model_bind_draw_owner(&player_identities,archive,bytes,0);
    else re4dc_model_unbind_draw_owner(&player_identities);
    re4dc_log("native player identities: %s count=%u archive=%u\n",ok?"ok":"REJECTED",player_identities.count(),bytes);return ok;
}
extern "C" int re4dc_ui_bind_weapon(void* archive,unsigned bytes){
    nsource=0;bool ok=weapon_identities.adopt(archive,bytes);
    if(ok)re4dc_model_bind_draw_owner(&weapon_identities,archive,bytes,0);
    else re4dc_model_unbind_draw_owner(&weapon_identities);
    re4dc_log("native weapon identities: %s count=%u archive=%u\n",ok?"ok":"REJECTED",weapon_identities.count(),bytes);return ok;
}
extern "C" void re4dc_ui_unbind_player(){re4dc_model_unbind_draw_owner(&player_identities);player_identities.clear();nsource=0;}
extern "C" void re4dc_ui_unbind_weapon(){re4dc_model_unbind_draw_owner(&weapon_identities);weapon_identities.clear();nsource=0;}
extern "C" int re4dc_ui_bind_enemy(void* archive,unsigned bytes){
    re4dc::texture::SourceIdentityTable table;
    if(!table.adopt(archive,bytes))return 0;
    if(!table.count()) {
        re4dc_model_bind_draw_owner(archive,archive,bytes,1);
        return 1; // ordinary archive; no texture view needed
    }
    EnemyIdentity* slot=nullptr;
    for(auto& e:enemy_identities){if(e.archive==archive)return 0;if(!e.archive && !slot)slot=&e;}
    if(!slot)return 0;
    slot->archive=archive;slot->table=table;nsource=0;
    re4dc_model_bind_draw_owner(archive,archive,bytes,1);
    re4dc_log("native enemy identities: count=%u archive=%u metadata_owner=enemy upload_staging=0\n",table.count(),bytes);
    return 1;
}
extern "C" void re4dc_ui_unbind_enemy(void* archive){
#if RE4DC_D349_RENDERER_STACK
    if(deferred_first){reset_deferred();stream_aborted=true;}
#endif
    re4dc_model_unbind_draw_owner(archive);
    for(auto& e:enemy_identities)if(archive && e.archive==archive){e.table.clear();e.archive=nullptr;}
    // Queued packets own copied native vertices/headers and cache handles; no
    // queued reader borrows archive texels. This does not free live VRAM uploads.
    nsource=0;
}
extern "C" void re4dc_ui_retire_room(){
#if RE4DC_D349_RENDERER_STACK
    reset_deferred();
    re4dc_model_preparation_owner(nullptr);
#endif
    re4dc_model_retire_draw_plans();
    // Packets hold copied native vertices, so no queued draw borrows a package.
#if RE4DC_NATIVE_STATIC
    re4dc_static_retire_all();
#endif
#if RE4DC_PVR_STREAM
    // Source room retirement can occur on a task while the main thread owns an
    // unfinished TA list. Keep submitted texture owners until that thread closes
    // and fences the discarded scene at Render_swap; no source CPU pointer is
    // retained by PVR. Waiting here would deadlock the caller against main.
    if(stream_scene){stream_aborted=true;stream_retire=true;}
    else
#endif
#if RE4DC_PVR_PIPELINE
    // The presenter owns the last scene until it resolves; then fence as before.
    if(ready && (present_fence(),re4dc::gpu::quiesce())!=re4dc::gpu::FenceResult::ready)
#else
    if(ready && re4dc::gpu::quiesce()!=re4dc::gpu::FenceResult::ready)
#endif
        re4dc_missing("native room retire fence failed");
    // No queued draw may outlive its source room. Shared cached uploads may be
    // reloaded from their stable identities; no archive texels are needed.
    // Core descriptors belong to the persistent core region and survive this reset.
    nquad=0;model_used=0;model_handle=nullptr;nsource=0;room_identities.clear();identity_hits=0;
    for(auto& e:enemy_identities){e.table.clear();e.archive=nullptr;}
#if RE4DC_PVR_STREAM
    if(!stream_retire)
#endif
    for(auto& entry:entries)close_entry(entry);
}

#if RE4DC_NATIVE_STATIC
extern "C" unsigned re4dc_ui_frame(){return frame;}
#endif
extern "C" void re4dc_ui_init(){
    if(ready)return;
    pvr_init_params_t params=pvr_default_params;
#if RE4DC_PVR_STREAM
    // Serialized ownership uses one TA bank. This pinned KOS still reserves
    // both banks, so doubling their size costs another 1MiB of actual VRAM.
    // Flycast's zero TA-used register does not qualify physical TA capacity.
    params.vertex_buf_size=RE4DC_TA_VERTBUF_KB*1024;params.vbuf_doublebuf_disabled=!RE4DC_TA_DOUBLEBUF;
    if(RE4DC_TA_OPB_BINS==32){params.opb_sizes[PVR_LIST_OP_POLY]=PVR_BINSIZE_32;params.opb_sizes[PVR_LIST_TR_POLY]=PVR_BINSIZE_32;}
    params.opb_overflow_count=RE4DC_TA_OPB_OVERFLOW;
#endif
    params.autosort_disabled=1; // source OT is the UI blending order
    ready=pvr_init(&params)==0;
    re4dc_log("native UI: PVR init %s; source ID adapter, 640x480\n",ready?"ok":"FAILED");
    if(ready){
#if RE4DC_PVR_STREAM
        if(pvr_set_manual_flip(true)<0)re4dc_missing("native manual presentation init failed");
        re4dc_log("native source stream: enabled, scratch=65536 TA=1048576 single-bank; late hold/retire/black preserved\n");
#endif
#if RE4DC_PVR_FAST_WAKE || RE4DC_PVR_PIPELINE
        install_fast_wake();
#endif
#if RE4DC_PVR_PIPELINE
        start_presenter();
#endif
#if RE4DC_TA_GUARD
        install_guard();
#endif
#if RE4DC_TA_GUARD || RE4DC_PERF_HUD || RE4DC_TA_VERTBUF_KB!=1024 || RE4DC_TA_DOUBLEBUF || RE4DC_TA_OPB_BINS!=16 || RE4DC_TA_OPB_OVERFLOW!=3
        re4dc_log("native VRAM layout: vertbuf=%u KiB x%u banks (%s) opb_bins=%u overflow=%u texture_pool_free=%u\n",
            unsigned(RE4DC_TA_VERTBUF_KB),2U,RE4DC_TA_DOUBLEBUF?"double-buffered":"single-bank use",unsigned(RE4DC_TA_OPB_BINS),unsigned(RE4DC_TA_OPB_OVERFLOW),(unsigned)pvr_mem_available());
#endif
        pvr_set_bg_color(0,0,0);
        // Source camera-space units can exceed 10,000. KOS's default 0.0001
        // inverse background depth hides those valid source polygons. Leave
        // near/far visibility to the existing source-projection clipper and
        // place the background behind every positive inverse model depth.
        pvr_set_zclip(0.0f);
    }
}
extern "C" void re4dc_ui_begin(){
#if RE4DC_PERF_HUD
    hud_begin_prev=hud_begin;hud_begin=timer_us_gettime64();
#endif
    re4dc_model_preparation_frame();
#if RE4DC_D349_RENDERER_STACK
    if(deferred_first)re4dc_missing("source pose queue crossed frame reset");
    reset_deferred();source_draws_finished=false;desired_list=PVR_LIST_OP_POLY;
#endif
#if RE4DC_PVR_STREAM
    if(stream_scene || stream_retire)re4dc_missing("native previous frame unresolved");
    stream_aborted=false;stream_model_bytes=0;
#endif
    if(model_diagnostic==1 && frame%120==0)
        re4dc_log("native model DIAGNOSTIC boundary: frame=%u previous_bytes=%u committed_parts=%u invalid=%u resource=%u overflow=%u presented=%u\n",frame,model_used*32,model_parts,model_invalid,model_resource,model_overflow,model_presented);
    nquad=0;model_used=0;++frame;
#if RE4DC_PVR_PIPELINE
    // The previous scene may still render/await its flip: do not wait here.
    // Its fence precedes this frame's scene begin and any VRAM change.
    frame_ready=ready;
#else
    frame_ready=ready && re4dc::gpu::quiesce()==re4dc::gpu::FenceResult::ready;
#if RE4DC_NATIVE_FOG
    if(frame_ready)re4dc_fog_frame(); // PVR fog table/colour; the previous render has completed
#endif
#endif
    re4dc_prepare_model_assets(); // registration/update work precedes frame submission
    re4dc::profile::begin();
#if defined(__sh__)
    re4dc_profile_source(&render_source_begin);
#endif
    frame_render_start=timer_us_gettime64();frame_work_start=*re4dc_model_work_stats();preparation_start=*re4dc_model_preparation_stats();
    frame_header_hits=model_header_hits;frame_header_builds=model_header_builds;
    frame_pvr_calls=frame_pvr_bytes=frame_queue_peak=frame_queue_drops=0;
}
extern "C" void re4dc_ui_submit(const Re4dcUiQuad* q){
    RE4DC_PROFILE_SCOPE(UiEnqueue);
    if(!frame_ready)return;
#if RE4DC_PVR_STREAM
    if(stream_aborted)return;
#endif
    // Source IdCommonTrans alpha-compare is GREATER 1 after modulation.
    // Zero material alpha cannot produce a surviving fragment for any blend.
    if((q->color>>24)==0){++culled;return;}
    if(q->masked || q->blend>4){++unsupported;return;}
#if RE4DC_D349_RENDERER_STACK
    if((nquad+1)*sizeof(Re4dcUiQuad)>deferred_top){++dropped;++frame_queue_drops;stream_aborted=true;return;}
#else
    if(nquad==kQuadCount){++dropped;return;}
#endif
    for(unsigned n=0;n<8;++n) if(!std::isfinite(q->xy[n]) || !std::isfinite(q->uv[n])) {++unsupported;return;}
    if(!drawn && !nquad) re4dc_log("native UI: first quad xy=%d,%d color=%08x\n",(int)q->xy[0],(int)q->xy[1],q->color);
    // Source texture storage can be retired by the following TaskScheduler.
    // Resolve/upload while the OT consumer still owns valid source pointers.
    Entry* handle=load(q->image);
    if(!handle){++missing;return;}
    handles[nquad]=handle;new(quads+nquad++) Re4dcUiQuad(*q);
    RE4DC_PROFILE_COUNT(UiQuads,1);RE4DC_PROFILE_COUNT(UiBytes,sizeof(Re4dcUiQuad));
    RE4DC_PROFILE_HIGH(UiCapacity,sizeof(frame_storage));
}
extern "C" void re4dc_ui_present(){
    RE4DC_PROFILE_SCOPE(UiDrain);
    if(!frame_ready)return;
#if RE4DC_D349_RENDERER_STACK
    if(deferred_first)re4dc_missing("source render barrier did not drain models");
    stream_select(PVR_LIST_TR_POLY);
#endif
#if RE4DC_PVR_STREAM
    if(!stream_scene)stream_open();
#else
    pvr_scene_begin();pvr_list_begin(PVR_LIST_TR_POLY);
    if(model_used && !re4dc_vi_black()){
        re4dc::render::submit_pvr(model_packets,model_used*sizeof(pvr_vertex_t));
        if(model_presented++<3)re4dc_log("native model DIAGNOSTIC presented: frame=%u bytes=%u\n",frame,model_used*32);
    }
#endif
    for(unsigned i=0;i<nquad && !re4dc_vi_black();++i){
        if(!handles[i])continue;
        const auto& q=quads[i];const auto& t=handles[i]->package.textures()[0];
        unsigned fmt=re4dc::texture::pvr_format(t);
        pvr_poly_cxt_t c;pvr_poly_cxt_txr(&c,PVR_LIST_TR_POLY,fmt,t.width,t.height,
                            handles[i]->package.pvr_texture(0),PVR_FILTER_BILINEAR);
        c.gen.culling=PVR_CULLING_NONE;c.depth.comparison=PVR_DEPTHCMP_ALWAYS;c.depth.write=PVR_DEPTHWRITE_DISABLE;
        const pvr_blend_mode_t src[]={PVR_BLEND_SRCALPHA,PVR_BLEND_SRCALPHA,PVR_BLEND_ONE,PVR_BLEND_DESTCOLOR,PVR_BLEND_DESTCOLOR};
        const pvr_blend_mode_t dst[]={PVR_BLEND_INVSRCALPHA,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ZERO};
        c.blend.src=src[q.blend];c.blend.dst=dst[q.blend];c.txr.env=PVR_TXRENV_MODULATEALPHA;c.txr.uv_clamp=PVR_UVCLAMP_UV;
        pvr_poly_hdr_t header;pvr_poly_compile(&header,&c);
        alignas(32) pvr_vertex_t commands[5]{};std::uint32_t count;
        re4dc::render::begin_pvr_packet(commands,count,header);
        pvr_vertex_t* v=commands+count;const unsigned order[]={0,1,3,2};
        for(unsigned n=0;n<4;++n){unsigned j=order[n];v[n].flags=n==3?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX;
            v[n].x=q.xy[2*j];v[n].y=q.xy[2*j+1];v[n].z=1.0f;
            v[n].u=q.uv[2*j]*q.image.width/t.width;v[n].v=q.uv[2*j+1]*q.image.height/t.height;v[n].argb=q.color;}
#if RE4DC_PVR_STREAM
        stream_send(commands,sizeof(commands));
#else
        re4dc::render::submit_pvr(commands,sizeof(commands));
#endif
        ++drawn;
    }
#if RE4DC_PERF_HUD
    if(!re4dc_vi_black()){
        pvr_stats_t hud_stats;pvr_get_stats(&hud_stats);
        const unsigned start=PVR_GET(PVR_TA_VERTBUF_START),pos=PVR_GET(PVR_TA_VERTBUF_POS);
        unsigned ta_bytes=pos>start?pos-start:0;   // live on hardware, 0 in Flycast
        bool ta_fault=false;
#if RE4DC_TA_GUARD
        static unsigned hud_faults;
        ta_bytes=std::max(ta_bytes,guard_estimate());
        ta_fault=guard_fault_frames+guard_render_fault_frames!=hud_faults;hud_faults=guard_fault_frames+guard_render_fault_frames;
#else
        ta_bytes=std::max(ta_bytes,stream_model_bytes/32*24);
#endif
#if RE4DC_PVR_PIPELINE
        static std::uint64_t hud_fence;
        const unsigned wait_us=unsigned(fence_wait_us-hud_fence);hud_fence=fence_wait_us;
#else
        const unsigned wait_us=completed_frame.present_wait_us;
#endif
        hud_draw(unsigned(hud_stats.frame_last_time/1000),unsigned(hud_stats.rnd_last_time/1000),wait_us,
                 ta_bytes,RE4DC_TA_VERTBUF_KB*1024U,ta_fault);
    }
#endif
#if RE4DC_PVR_STREAM
    stream_close(true);
    if(stream_model_bytes && model_presented++<3)
        re4dc_log("native model DIAGNOSTIC presented: frame=%u bytes=%u\n",frame,stream_model_bytes);
    if(frame%120==0 || (stream_model_bytes && model_presented<=3)){
        pvr_stats_t stats;pvr_get_stats(&stats);
        re4dc_log("native stream: frame=%u model_bytes=%u peak=%u discarded=%u black_frames=%u vram_free=%u textures=%u used=%u loads=%u missing=%u ta_used=%u ta_peak=%u present_us=%llu registration_us=%llu render_us=%llu\n",frame,stream_model_bytes,stream_peak_bytes,stream_discards,stream_black_frames,(unsigned)pvr_mem_available(),kTextureCount,used,loads,missing,(unsigned)stats.vtx_buffer_used,(unsigned)stats.vtx_buffer_used_max,(unsigned long long)(stats.frame_last_time/1000),(unsigned long long)(stats.reg_last_time/1000),(unsigned long long)(stats.rnd_last_time/1000));
    }
#if RE4DC_PVR_FAST_WAKE || RE4DC_PVR_PIPELINE
    if(frame%120==0){
#if RE4DC_PVR_PIPELINE
        re4dc_log("native pipeline: frame=%u mode=%s submitted=%u resolved=%u fence_blocked=%u fence_wait_us=%llu fence_timeouts=%u failures=%u wake_render=%u wake_vblank=%u\n",
            frame,RE4DC_PVR_PIPELINE==2?"kos-async":"presenter",present_submitted,present_resolved,fence_blocked,(unsigned long long)fence_wait_us,fence_timeouts,present_failures,wake_renders,wake_vblanks);
#else
        re4dc_log("native pipeline: frame=%u mode=fast-wake wake_render=%u wake_vblank=%u\n",frame,wake_renders,wake_vblanks);
#endif
    }
#endif
#if RE4DC_TA_GUARD
    if(frame%120==0)re4dc_log("native TA guard: frame=%u hw_param=%u hw_peak=%u est=%u est_peak=%u scale=%u reserve=%u skips=%u ta_fault_frames=%u render_fault_frames=%u discards=%u opb_pos=%08x\n",
        frame,guard_hw_last,guard_hw_peak,guard_sw_last,guard_sw_peak,guard_scale,guard_reserve,guard_skips,guard_fault_frames,guard_render_fault_frames,guard_discards,guard_opb_last);
#endif
#if RE4DC_TA_DIRECT
    if(frame%120==0)re4dc_log("native direct: frame=%u parts=%u slots=%u\n",frame,direct_parts,direct_slots);
#endif
#else
    pvr_list_finish();pvr_scene_finish();
#endif
    if(frame%120==0 && model_diagnostic==1)
        re4dc_log("native model DIAGNOSTIC: frame=%u packets=%u parts=%u invalid=%u resource=%u overflow=%u input=%u emitted=%u peak=%u heap=%d black=%d\n",frame,model_used*32,model_parts,model_invalid,model_resource,model_overflow,model_input,model_output,model_peak,re4dc_ui_heap_free(),re4dc_vi_black());
    if(frame%120==0 && model_diagnostic==1)
        re4dc_log("native model rejection: capacity=%u state=%u texture=%u wrap=%u empty=%u scale_rebuild=%u\n",model_capacity_rejects,model_state_rejects,model_texture_rejects,model_wrap_rejects,model_empty_parts,model_scale_rebuilds);
    if(frame%120==0 && model_diagnostic==1)re4dc_log("native model alpha: material=%u vertex=%u faded=%u masks=unsupported\n",model_alpha_material,model_alpha_vertex,model_alpha_faded);
    if(frame%120==0) re4dc_log("native UI: frame=%u quads=%u drawn=%u missing=%u unsupported=%u drops=%u vram=%u peak=%u staging=%u loads=%u freed=%u culled=%u fb=%08x,%08x black=%d\n",frame,nquad,drawn,missing,unsupported,dropped,used,peak,staging_peak,loads,reclaimed,culled,(unsigned)pvr_get_front_buffer(),(unsigned)pvr_get_back_buffer(),re4dc_vi_black());
}

extern "C" void re4dc_ui_end_frame(int present){
    const auto render_end=timer_us_gettime64();
    re4dc_model_draw_plan_frame(frame);
#if RE4DC_PVR_STREAM
    if(!frame_ready)return;
    const bool black=re4dc_vi_black()!=0;
    if(present && !stream_aborted && !black)re4dc_ui_present();
    else {
        if(stream_scene)stream_close(false);
        // A late VI-black request must show a genuinely empty framebuffer;
        // previously submitted world packets cannot simply be ignored now.
        if(present && black){stream_open();stream_close(true);++stream_black_frames;}
    }
    if(stream_retire){for(auto& entry:entries)close_entry(entry);stream_retire=false;}
#else
    if(present)re4dc_ui_present();
#endif
    for(const auto& e:entries)if(e.valid){RE4DC_PROFILE_COUNT(TextureResidentCount,1);
        if(e.frame==frame){RE4DC_PROFILE_COUNT(TexturePinnedCount,1);RE4DC_PROFILE_COUNT(TexturePinnedBytes,e.package.vram_bytes());}}
    re4dc::profile::finish(completed_render_profile,frame,render_source_begin);
    re4dc_pcs_frame(frame); // PC_SAMPLER=1 only: frame boundary in the sample ring
    completed_frame.sequence=completed_frame.sequence+1;
    asm volatile("" ::: "memory");
    completed_frame.frame=frame;
    const auto now=*re4dc_model_work_stats();
    unsigned current[sizeof(now)/sizeof(unsigned)],before[sizeof(now)/sizeof(unsigned)];
    std::memcpy(current,&now,sizeof(now));std::memcpy(before,&frame_work_start,sizeof(now));
    for(unsigned n=0;n<sizeof(now)/sizeof(unsigned);++n)current[n]-=before[n];
    std::memcpy(&completed_frame.work,current,sizeof(now));
    completed_frame.pvr_calls=frame_pvr_calls;completed_frame.pvr_bytes=frame_pvr_bytes;
    completed_frame.header_hits=model_header_hits-frame_header_hits;
    completed_frame.header_builds=model_header_builds-frame_header_builds;
    const auto* plans=re4dc_model_draw_plan_stats();
    completed_frame.plan_used=plans->used;completed_frame.plan_capacity=plans->capacity;
    completed_frame.queue_peak=frame_queue_peak;completed_frame.queue_drops=frame_queue_drops;
    completed_frame.texture_vram=used;completed_frame.texture_peak=peak;
    completed_frame.native_slab=model_packets?kModelSlabBytes:0;
    completed_frame.source_heap_free=re4dc_ui_heap_free();
    completed_frame.render_wall_us=unsigned(render_end-frame_render_start);
    completed_frame.present_wait_us=unsigned(timer_us_gettime64()-render_end);
    completed_frame.present_requested=present;
#if RE4DC_PVR_STREAM
    completed_frame.aborted=stream_aborted;
#endif
    asm volatile("" ::: "memory");
    completed_frame.sequence=completed_frame.sequence+1;
    completed_preparation.sequence++;
    asm volatile("" ::: "memory");
    completed_preparation.frame=frame;
    unsigned prep_now[sizeof(Re4dcPreparationStats)/4],prep_before[sizeof(Re4dcPreparationStats)/4];
    std::memcpy(prep_now,re4dc_model_preparation_stats(),sizeof(prep_now));std::memcpy(prep_before,&preparation_start,sizeof(prep_before));
    for(unsigned i=0;i<sizeof(prep_now)/4;++i)prep_now[i]-=prep_before[i];
    std::memcpy(&completed_preparation.work,prep_now,sizeof(prep_now));
    completed_preparation.scratch_bytes=kModelPreparationBytes;completed_preparation.packet_bytes=kModelPacketBytes;
    asm volatile("" ::: "memory");completed_preparation.sequence++;

}

extern "C" int re4dc_model_diagnostic_enabled(){
    if(model_diagnostic<0){
        file_t f=fs_open("/cd/dc/model-diagnostic.flag",O_RDONLY);
        model_diagnostic=f>=0;if(f>=0)fs_close(f);
        if(model_diagnostic)re4dc_log("native model DIAGNOSTIC stack=%u source pose/camera; packets=%u metadata=%u static_lights=%u slab=%u; full TEV/fog acceptance pending\n",RE4DC_D349_RENDERER_STACK,kModelPacketBytes,kModelMetadataBytes,kModelStaticLightBytes,kModelSlabBytes);
    }
    return model_diagnostic;
}
namespace {
bool ensure_model_storage(){
    if(!model_packets){
        model_packets=(pvr_vertex_t*)memalign(32,kModelSlabBytes);
        if(!model_packets)RE4DC_PROFILE_COUNT(AllocationFailures,1);
        re4dc_log("native model slab=%08x bytes=%u source_heap=%d\n",(unsigned)model_packets,kModelSlabBytes,re4dc_ui_heap_free());
    }
    return model_packets!=nullptr;
}
}
extern "C" int re4dc_model_packet_reserve(const Re4dcModelPart* p,Re4dcModelPacket* out){
    unsigned reason=0;
    if(!frame_ready || !re4dc_model_diagnostic_enabled())reason|=1;
#if RE4DC_PVR_STREAM
    if(stream_aborted)reason|=1;
#endif
    if(p->blend>4 || p->cull>2)reason|=2;
    if(p->depth_mode>2)reason|=4;
    if(p->wrap_s>1 || p->wrap_t>1)reason|=8;
#if RE4DC_D349_RENDERER_STACK
    // Same-coordinate, equal-resolution source masks are prepared offline into
    // one native texture. Other TEV/alpha-test policies remain explicit gaps.
    if((p->material_flags&4) && (!p->mask.pixels || !p->mask_same_uv || p->mask_ref!=0 ||
       p->mask.width!=p->image.width || p->mask.height!=p->image.height))reason|=16;
#else
    if(p->material_flags&4)reason|=16;
#endif
    if(p->image.format>=8 && p->image.format!=14)reason|=32;
#if RE4DC_TA_GUARD && RE4DC_D349_RENDERER_STACK
    if(!reason && !guard_admit(draining_parts)){
        // Budget skip, not a state reject: the part is simply not drawn.
        ++model_capacity_rejects;return 0;
    }
#endif
    if(!p->image.pixels)reason|=64;
    if(!p->image.width || !p->image.height || p->image.width>1024 || p->image.height>1024)reason|=128;
    if(reason){
        ++model_state_rejects;
        for(unsigned bit=0;bit<8;++bit)if(reason&(1U<<bit)){
            if(model_state_bits[bit]++<2)re4dc_log("native model state reject: reason=%02x model=%08x info=%08x part=%08x material=%02x blend=%u depth=%u wrap=%u,%u image=%08x %ux%u fmt=%u vertices=%u stream=%u\n",reason,(unsigned)p->model,(unsigned)p->info,(unsigned)p->part,p->material_flags,p->blend,p->depth_mode,p->wrap_s,p->wrap_t,(unsigned)p->image.pixels,p->image.width,p->image.height,p->image.format,p->position_count,p->stream_bytes);
        }
        return 0;
    }
    if(!ensure_model_storage())return 0;
    if(model_used+4>kModelPacketBytes/32){++model_capacity_rejects;return 0;}
    // Same default padding policy as convert_tpl; binding below checks the
    // actual package. A different native layout triggers exact UV preparation.
    unsigned width=8,height=8;
    while(width<p->image.width)width*=2;
    while(height<p->image.height)height*=2;
    model_pending=model_used+1;
    out->vertices=model_packets+model_pending;out->capacity=kModelPacketBytes/32-model_pending;
    out->u_scale=float(p->image.width)/width;out->v_scale=float(p->image.height)/height;
    return 1;
}
extern "C" void* re4dc_model_preparation_storage(unsigned* bytes){
    *bytes=model_packets?kModelPreparationBytes:0;
    return *bytes?reinterpret_cast<unsigned char*>(model_packets)+kModelPacketBytes:nullptr;
}
extern "C" void* re4dc_model_metadata_storage(unsigned* bytes){
    if(kModelMetadataBytes && !ensure_model_storage()){*bytes=0;return nullptr;}
    // The common slab owns allocation. This tail cannot overlap packet writes, survives
    // frame resets, and is invalidated by the same source owner generations.
    *bytes=model_packets?kModelMetadataBytes:0;
    return *bytes?reinterpret_cast<unsigned char*>(model_packets)+kModelPacketBytes+kModelPreparationBytes+kModelStaticLightBytes+kModelDeferredSpillBytes:nullptr;
}
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart* p,Re4dcModelPacket* out){
    RE4DC_PROFILE_SCOPE(PacketPack);
    if(!re4dc_model_packet_reserve(p,out))return 0;
    Key prepared{};const Key* key=nullptr;
#if RE4DC_D349_RENDERER_STACK
    if(p->material_flags&4){if(!model_mask_key(p,prepared)){++model_texture_rejects;return 0;}key=&prepared;}
#endif
    Entry* handle=load(p->image,false,key);if(!handle){++model_texture_rejects;return 0;}
    const auto& t=handle->package.textures()[0];
    // Repeating a padded image would repeat its border. Reject, never change wrap.
    if((p->wrap_s && t.width!=p->image.width)||(p->wrap_t && t.height!=p->image.height)){++model_wrap_rejects;return 0;}
    unsigned fmt=re4dc::texture::pvr_format(t);
    pvr_list_t list=PVR_LIST_TR_POLY;
#if RE4DC_D349_RENDERER_STACK
    if(stream_aborted)return 0;
    list=draining_parts?draining_list:select_model_pass(p);
    stream_select(list);
#endif
    pvr_poly_hdr_t header;std::uint32_t count;
#if RE4DC_D349_RENDERER_STACK
    const unsigned header_key=list|(p->blend<<3)|(p->depth_mode<<6)|(p->wrap_s<<8)|(p->wrap_t<<10)|((p->material_flags&4)<<12)|(p->cull<<16)
#if RE4DC_NATIVE_FOG
        |(p->source_key[2]?1U<<20:0U) // NATIVE_FOG flag (model_bridge.cpp)
#endif
        ;
    if(handle->model_header_key==header_key){header=handle->model_header;++model_header_hits;}
    else {
#endif
    pvr_poly_cxt_t c;pvr_poly_cxt_txr(&c,list,fmt,t.width,t.height,handle->package.pvr_texture(0),PVR_FILTER_BILINEAR);
#if RE4DC_D349_RENDERER_STACK
    // Same mapping as D349 room_strip_headers; p.cull already includes the
    // recovered game's corrected facing. Clipped fallback retains its winding.
    const pvr_cull_mode_t cull[]={PVR_CULLING_NONE,PVR_CULLING_CCW,PVR_CULLING_CW};
    c.gen.culling=cull[p->cull];
#else
    c.gen.culling=PVR_CULLING_NONE; // reference CPU-cull path
#endif
    c.depth.comparison=p->depth_mode==2?PVR_DEPTHCMP_ALWAYS:PVR_DEPTHCMP_GEQUAL;
    c.depth.write=p->depth_mode==0?PVR_DEPTHWRITE_ENABLE:PVR_DEPTHWRITE_DISABLE;
    const pvr_blend_mode_t src[]={PVR_BLEND_SRCALPHA,PVR_BLEND_SRCALPHA,PVR_BLEND_ONE,PVR_BLEND_DESTCOLOR,PVR_BLEND_ONE};
    const pvr_blend_mode_t dst[]={PVR_BLEND_INVSRCALPHA,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ZERO};
    // Source materialSetup passes channel alpha through; only alphaSetup adds
    // the separate source-selected mask. UI keeps its own
    // texture-alpha policy. Never make base CMPR/intensity alpha the model mask.
    c.blend.src=src[p->blend];c.blend.dst=dst[p->blend];c.txr.env=PVR_TXRENV_MODULATEALPHA;
    c.txr.alpha=PVR_TXRALPHA_DISABLE; // unmasked source base alpha is not a mask
#if RE4DC_D349_RENDERER_STACK
    if(p->material_flags&4)c.txr.alpha=PVR_TXRALPHA_ENABLE;
#endif
    c.txr.uv_clamp=(pvr_uv_clamp_t)((p->wrap_s?0:PVR_UVCLAMP_U)|(p->wrap_t?0:PVR_UVCLAMP_V));
#if RE4DC_NATIVE_FOG
    c.gen.fog_type=p->source_key[2]?PVR_FOG_TABLE:PVR_FOG_DISABLE; // table: native_static.cpp re4dc_fog_frame
#endif
    pvr_poly_compile(&header,&c);++model_header_builds;
#if RE4DC_D349_RENDERER_STACK
        handle->model_header=header;handle->model_header_key=header_key;
    }
#endif
#if RE4DC_D349_RENDERER_STACK
    if(p->cull){
        if(list==PVR_LIST_OP_POLY)RE4DC_PROFILE_COUNT(HardwareCullOP,1);
        else if(list==PVR_LIST_PT_POLY)RE4DC_PROFILE_COUNT(HardwareCullPT,1);
        else RE4DC_PROFILE_COUNT(HardwareCullTR,1);
    }
#endif
    re4dc::render::begin_pvr_packet(model_packets+model_used,count,header);
    model_pending=model_used+count;model_handle=handle;
    out->vertices=model_packets+model_pending;out->capacity=kModelPacketBytes/32-model_pending;
    if(out->u_scale!=float(p->image.width)/t.width || out->v_scale!=float(p->image.height)/t.height)++model_scale_rebuilds;
    out->u_scale=float(p->image.width)/t.width;out->v_scale=float(p->image.height)/t.height;
    if(p->alpha_state&256)++model_alpha_vertex;else ++model_alpha_material;
    if(!(p->alpha_state&256) && (p->alpha_state&255)<255)++model_alpha_faded;
    if(model_parts<6)re4dc_log("native model DIAGNOSTIC source=%08x info=%08x part=%08x positions=%u stride=%u stream=%u flags=%08x material=%02x cull=%u\n",(unsigned)p->model,(unsigned)p->info,(unsigned)p->part,p->position_count,p->position_stride,p->stream_bytes,p->flags,p->material_flags,p->cull);
    return 1;
}
extern "C" void re4dc_model_packet_commit(unsigned count){
    // A loaded but wholly clipped/rolled-back part owns no submitted packets.
    // Keep its upload cached; pin only when this part actually commits a draw.
    if(count){
        model_handle->frame=frame;model_used=model_pending+count;
        if(model_used*32>model_peak)model_peak=model_used*32;
#if RE4DC_PVR_STREAM
        stream_send(model_packets,model_used*32);
        stream_model_bytes+=model_used*32;
        if(stream_model_bytes>stream_peak_bytes)stream_peak_bytes=stream_model_bytes;
        model_used=0; // PVR owns copied packets; reuse the same bounded scratch.
#endif
    }
}
extern "C" void re4dc_model_result(unsigned reason,unsigned input,unsigned output){
    if(reason==0){++model_parts;if(!output)++model_empty_parts;}else if(reason==1)++model_invalid;else if(reason==2)++model_resource;else ++model_overflow;
    model_input+=input;model_output+=output;
}

extern "C" int re4dc_model_packet_streaming(){return RE4DC_PVR_STREAM;}
extern "C" void re4dc_model_packet_abort(){
#if RE4DC_PVR_STREAM
    // Previous chunks may already be in TA. Never present an incomplete model:
    // reject further submissions and let the same source owner discard/fence it.
    stream_aborted=true;model_used=0;model_handle=nullptr;
#endif
}

extern "C" int re4dc_model_direct_enabled(){return RE4DC_TA_DIRECT;}
extern "C" int re4dc_model_direct_begin(const Re4dcModelPart* p,Re4dcModelDirect* out){
#if RE4DC_TA_DIRECT
    if(direct_open){re4dc_missing("native direct part nested");return 0;}
    Re4dcModelPacket packet{};
    // Same qualification, texture bind, pass selection and header as the
    // packet path; the header lands in the slab, then goes out by store queue.
    if(!re4dc_model_packet_begin(p,&packet))return 0;
    if(!stream_scene)stream_open();
    auto* sq=static_cast<std::uint32_t*>(static_cast<void*>(sq_lock((void*)PVR_TA_INPUT)));
    const auto* header=reinterpret_cast<const std::uint32_t*>(model_packets+model_used);
    for(unsigned i=0;i<8;++i)sq[i]=header[i];
    sq_flush(sq);
    direct_open=true;
    model_handle->frame=frame; // the header is in the TA: pinned for this scene
    ++frame_pvr_calls;frame_pvr_bytes+=32;stream_model_bytes+=32;
    out->sq=sq+8;out->scratch=packet.vertices;out->scratch_capacity=packet.capacity;
    out->u_scale=packet.u_scale;out->v_scale=packet.v_scale;
    return 1;
#else
    (void)p;(void)out;return 0;
#endif
}
extern "C" void re4dc_model_direct_end(unsigned vertices){
#if RE4DC_TA_DIRECT
    if(!direct_open)return;
    sq_unlock();direct_open=false;
    if(vertices>32767)re4dc_missing("native direct part exceeded the store-queue window");
    ++direct_parts;direct_slots+=vertices;
#if RE4DC_TA_GUARD
    guard_account(1,vertices);
#endif
    frame_pvr_bytes+=vertices*32;stream_model_bytes+=vertices*32;
    if(stream_model_bytes>stream_peak_bytes)stream_peak_bytes=stream_model_bytes;
    model_used=0;
#else
    (void)vertices;
#endif
}

#if RE4DC_COPY_LEAN && RE4DC_D349_RENDERER_STACK
namespace {
// re4dc_model_defer_part() below with 'source' as the lighting to snapshot
// (nullptr: none) and the same queue layout and admission. The view diff is
// taken once into stack scratch (it was walked twice: size, then fill) and a
// found lighting record supplies its own light set (no second list scan).
int defer_part(const Re4dcModelPart* p,const SourceLighting* source){
    if(draining_parts)return 0;
    if(source_draws_finished){RE4DC_PROFILE_COUNT(DirectTR,1);return 0;}
    if(select_model_pass(p)==PVR_LIST_OP_POLY){RE4DC_PROFILE_COUNT(DirectOP,1);return 0;}
    RE4DC_PROFILE_SCOPE(TranslucentEnqueue);
    if(!frame_ready || stream_aborted)return 1;
    DeferredLighting* lighting=nullptr;
    if(source)for(auto* l=deferred_lights;l;l=l->next)
        if(same_lighting(l,*source)){lighting=l;break;}
    DeferredLightSet* light_set=lighting?const_cast<DeferredLightSet*>(lighting->lights):nullptr;
    if(source && !lighting)for(auto* l=deferred_light_sets;l;l=l->next)
        if(same_light_set(l,*source)){light_set=l;break;}
    const unsigned set_bytes=source && !light_set?(deferred_set_bytes(*source)+31)&~31U:0;
    const unsigned state_bytes=source && !lighting?(deferred_light_bytes(*source)+31)&~31U:0;
    Re4dcModelPart view=*p;view.lighting=nullptr; // separately snapshotted below
    const bool had_basis=deferred_basis!=nullptr;
    unsigned masks[kViewMasks],values[kViewWords];
    const unsigned basis_bytes=had_basis?0:(sizeof(Re4dcModelPart)+31)&~31U;
    const unsigned words=had_basis?view_words(view,*deferred_basis,masks,values):0;
    const unsigned bytes=(sizeof(DeferredPart)+4*words+31)&~31U;
    const unsigned required=bytes+state_bytes+basis_bytes+set_bytes;
    RE4DC_PROFILE_COUNT(ViewBytes,bytes);RE4DC_PROFILE_COUNT(LightSetBytes,set_bytes);
    RE4DC_PROFILE_COUNT(LightStateBytes,state_bytes);RE4DC_PROFILE_COUNT(BasisBytes,basis_bytes);
    if(p->material_flags&4){RE4DC_PROFILE_COUNT(DeferredMasked,1);RE4DC_PROFILE_COUNT(MaskedBytes,required);}
    else if(p->depth_mode){RE4DC_PROFILE_COUNT(DeferredDepth,1);RE4DC_PROFILE_COUNT(DepthBytes,required);}
    else {RE4DC_PROFILE_COUNT(DeferredBlend,1);RE4DC_PROFILE_COUNT(BlendBytes,required);}
    RE4DC_PROFILE_HIGH(QueueCapacity,sizeof(frame_storage)-8192+kModelDeferredSpillBytes);
    unsigned char* storage=frame_storage;unsigned* top=&deferred_top;
    if(required>deferred_top || deferred_top-required<std::max(8192U,nquad*unsigned(sizeof(Re4dcUiQuad)))){
        if(!deferred_spill){deferred_spill=static_cast<unsigned char*>(re4dc_model_deferred_storage(&deferred_spill_capacity));deferred_spill_top=deferred_spill_capacity;}
        if(!deferred_spill || required>deferred_spill_top){
            ++deferred_drops;++frame_queue_drops;stream_aborted=true;re4dc_model_result(3,0,0);return 1;
        }
        storage=deferred_spill;top=&deferred_spill_top;
    }
    if(basis_bytes){*top-=basis_bytes;deferred_basis=new(storage+*top) Re4dcModelPart(view);}
    if(set_bytes){
        *top-=set_bytes;light_set=new(storage+*top) DeferredLightSet{};
        store_light_set(light_set,*source);light_set->next=deferred_light_sets;deferred_light_sets=light_set;
    }
    if(state_bytes){
        *top-=state_bytes;lighting=new(storage+*top) DeferredLighting{};
        lighting->lights=light_set;store_lighting(lighting,*source);lighting->next=deferred_lights;deferred_lights=lighting;
    }
    *top-=bytes;
    auto* node=new(storage+*top) DeferredPart{};
    if(had_basis){
        for(unsigned m=0;m<kViewMasks;++m)node->changed[m]=masks[m];
        auto* out=reinterpret_cast<unsigned*>(node+1);
        for(unsigned i=0;i<words;++i)out[i]=values[i];
    } // else: the basis is this view, no differing words (changed[] stays zero)
    node->lighting=lighting;
    if(deferred_last)deferred_last->next=node;else deferred_first=node;
    deferred_last=node;++deferred_count;
    deferred_peak=std::max(deferred_peak,unsigned(sizeof(frame_storage))-deferred_top+deferred_spill_capacity-deferred_spill_top);
    frame_queue_peak=std::max(frame_queue_peak,unsigned(sizeof(frame_storage))-deferred_top+deferred_spill_capacity-deferred_spill_top);
    RE4DC_PROFILE_HIGH(QueuePeak,frame_queue_peak);
    return 1;
}
}
// Lit native scenery (native_static.cpp): the replay never reads lighting.
extern "C" int re4dc_model_defer_part_unlit(const Re4dcModelPart* p){return defer_part(p,nullptr);}
#elif RE4DC_COPY_LEAN
extern "C" int re4dc_model_defer_part_unlit(const Re4dcModelPart*){return 0;}
#endif
extern "C" int re4dc_model_defer_part(const Re4dcModelPart* p){
#if RE4DC_COPY_LEAN && RE4DC_D349_RENDERER_STACK
    return defer_part(p,p->lighting);
#elif RE4DC_D349_RENDERER_STACK
    if(draining_parts)return 0;
    if(source_draws_finished){RE4DC_PROFILE_COUNT(DirectTR,1);return 0;}
    if(select_model_pass(p)==PVR_LIST_OP_POLY){RE4DC_PROFILE_COUNT(DirectOP,1);return 0;}
    RE4DC_PROFILE_SCOPE(TranslucentEnqueue);
    if(!frame_ready || stream_aborted)return 1;
    // Full current state snapshot; arrays/display-list remain source-owned.
    // Only nonopaque models borrow this space, typically a small minority.
    DeferredLighting* lighting=nullptr;
    if(p->lighting)for(auto* l=deferred_lights;l;l=l->next)
        if(same_lighting(l,*p->lighting)){lighting=l;break;}
    DeferredLightSet* light_set=nullptr;
    if(p->lighting)for(auto* l=deferred_light_sets;l;l=l->next)
        if(same_light_set(l,*p->lighting)){light_set=l;break;}
    const unsigned set_bytes=p->lighting && !light_set?(deferred_set_bytes(*p->lighting)+31)&~31U:0;
    const unsigned state_bytes=p->lighting && !lighting?(deferred_light_bytes(*p->lighting)+31)&~31U:0;
    Re4dcModelPart view=*p;view.lighting=nullptr; // separately snapshotted below
    const unsigned basis_bytes=deferred_basis?0:(sizeof(Re4dcModelPart)+31)&~31U;
    const unsigned words=deferred_basis?view_words(view,*deferred_basis,nullptr,nullptr):0;
    const unsigned bytes=(sizeof(DeferredPart)+4*words+31)&~31U;
    const unsigned required=bytes+state_bytes+basis_bytes+set_bytes;
    RE4DC_PROFILE_COUNT(ViewBytes,bytes);RE4DC_PROFILE_COUNT(LightSetBytes,set_bytes);
    RE4DC_PROFILE_COUNT(LightStateBytes,state_bytes);RE4DC_PROFILE_COUNT(BasisBytes,basis_bytes);
    if(p->material_flags&4){RE4DC_PROFILE_COUNT(DeferredMasked,1);RE4DC_PROFILE_COUNT(MaskedBytes,required);}
    else if(p->depth_mode){RE4DC_PROFILE_COUNT(DeferredDepth,1);RE4DC_PROFILE_COUNT(DepthBytes,required);}
    else {RE4DC_PROFILE_COUNT(DeferredBlend,1);RE4DC_PROFILE_COUNT(BlendBytes,required);}
    RE4DC_PROFILE_HIGH(QueueCapacity,sizeof(frame_storage)-8192+kModelDeferredSpillBytes);
    unsigned char* storage=frame_storage;unsigned* top=&deferred_top;
    // Source UI arrives after model registration. Preserve a measured 8 KiB
    // lane for it and spill snapshots into the former native static-cache tail.
    // This never grows the source arena, native slab or total allocated memory.
    if(required>deferred_top || deferred_top-required<std::max(8192U,nquad*unsigned(sizeof(Re4dcUiQuad)))){
        if(!deferred_spill){deferred_spill=static_cast<unsigned char*>(re4dc_model_deferred_storage(&deferred_spill_capacity));deferred_spill_top=deferred_spill_capacity;}
        if(!deferred_spill || required>deferred_spill_top){
            ++deferred_drops;++frame_queue_drops;stream_aborted=true;re4dc_model_result(3,0,0);return 1;
        }
        storage=deferred_spill;top=&deferred_spill_top;
    }
    if(basis_bytes){*top-=basis_bytes;deferred_basis=new(storage+*top) Re4dcModelPart(view);}
    if(set_bytes){
        *top-=set_bytes;light_set=new(storage+*top) DeferredLightSet{};
        store_light_set(light_set,*p->lighting);light_set->next=deferred_light_sets;deferred_light_sets=light_set;
    }
    if(state_bytes){
        *top-=state_bytes;lighting=new(storage+*top) DeferredLighting{};
        lighting->lights=light_set;store_lighting(lighting,*p->lighting);lighting->next=deferred_lights;deferred_lights=lighting;
    }
    *top-=bytes;
    auto* node=new(storage+*top) DeferredPart{};
    view_words(view,*deferred_basis,node->changed,reinterpret_cast<unsigned*>(node+1));
    node->lighting=lighting;
    if(deferred_last)deferred_last->next=node;else deferred_first=node;
    deferred_last=node;++deferred_count;
    deferred_peak=std::max(deferred_peak,unsigned(sizeof(frame_storage))-deferred_top+deferred_spill_capacity-deferred_spill_top);
    frame_queue_peak=std::max(frame_queue_peak,unsigned(sizeof(frame_storage))-deferred_top+deferred_spill_capacity-deferred_spill_top);
    RE4DC_PROFILE_HIGH(QueuePeak,frame_queue_peak);
    return 1;
#else
    (void)p;return 0;
#endif
}
extern "C" void re4dc_model_finish_source_draws(){
    RE4DC_PROFILE_SCOPE(TranslucentDrain);
#if RE4DC_D349_RENDERER_STACK
    if(!deferred_first){source_draws_finished=true;return;}
    draining_parts=true;
    // Current PVR setup enables OP/TR only. Do not submit a dummy PT list:
    // pinned KOS compares completed-list bits to exactly the enabled-list mask.
    // A future qualified PT material must also budget/enable that list.
    stream_select(PVR_LIST_TR_POLY);draining_list=PVR_LIST_TR_POLY;
    while(deferred_first && !stream_aborted){
        // Copy the small view before I/O can yield. Retirement clears the queue
        // and aborts this same frame; it never frees an in-flight PVR texture.
        Re4dcModelPart view=restore_view(deferred_first);
        const auto* saved_lighting=deferred_first->lighting;
        deferred_first=deferred_first->next;
#if RE4DC_COPY_LEAN
        if(saved_lighting){
            SourceLighting lighting;restore_lighting_into(saved_lighting,lighting);
            view.lighting=&lighting;re4dc_model_submit(&view);
        }else re4dc_model_submit(&view);
#else
        SourceLighting lighting{};
        if(saved_lighting){lighting=restore_lighting(saved_lighting);view.lighting=&lighting;}
        re4dc_model_submit(&view);
#endif
    }
    draining_parts=false;source_draws_finished=true;reset_deferred();
#endif
}

extern "C" void re4dc_model_invalidate_pending(){
    re4dc_model_invalidate_static_lighting();
#if RE4DC_D349_RENDERER_STACK
    if(deferred_first || draining_parts){reset_deferred();stream_aborted=true;}
#endif
}

extern "C" void* re4dc_model_static_lighting_storage(unsigned* bytes){
    *bytes=model_packets?kModelStaticLightBytes:0;
    return *bytes?reinterpret_cast<unsigned char*>(model_packets)+kModelPacketBytes+kModelPreparationBytes:nullptr;
}

extern "C" const Re4dcNativeFrameStats* re4dc_native_frame_stats(){return &completed_frame;}

extern "C" void* re4dc_model_deferred_storage(unsigned* bytes){
    *bytes=model_packets?kModelDeferredSpillBytes:0;
    return *bytes?reinterpret_cast<unsigned char*>(model_packets)+kModelPacketBytes+kModelPreparationBytes+kModelStaticLightBytes:nullptr;
}
