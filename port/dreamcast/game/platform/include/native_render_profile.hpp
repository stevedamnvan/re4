#pragma once
#include <cstdint>
#ifndef RE4DC_NATIVE_RENDER_PROFILE
#define RE4DC_NATIVE_RENDER_PROFILE 0
#endif
// Diagnostic stage WALL time on the one source render thread. Nested scopes
// partition time exclusively; GPU/TA asynchronous durations are separate.
// Read the existing KOS TMU2 clock; never configure a timer/performance counter.
#if RE4DC_NATIVE_RENDER_PROFILE && defined(__sh__)
#include <arch/timer.h>
#endif
namespace re4dc::profile {
enum Stage : unsigned { Outside, ModelSetup, Topology, TransformProject, Lighting,
    Visibility, ClipFallback, PacketPack, TextureResolve, TextureUpload,
    SubmitOP, SubmitPT, SubmitTR, TranslucentEnqueue, TranslucentDrain,
    UiEnqueue, UiDrain, PresentFence, StageCount };
enum Metric : unsigned { TextureLookups, TextureHits, TextureUploads, TextureUploadBytes,
    TextureOpenFailures, TextureUploadFailures, TextureNoSlot, TextureBudgetFailures,
    TextureEvictions, AllocationFailures,
    DirectOP, DirectPT, DirectTR, DeferredMasked, DeferredBlend, DeferredDepth,
    MaskedBytes, BlendBytes, DepthBytes, ViewBytes, LightSetBytes, LightStateBytes,
    BasisBytes, QueueCapacity, QueuePeak, UiQuads, UiBytes, UiCapacity,
    TextureResidentCount, TexturePinnedCount, TexturePinnedBytes, ClockCalibrationTicks, ClockCalibrationSwitches, IntactStrips, ReconstructedStrips, StripClipFallbacks, HardwareCullOP, HardwareCullPT, HardwareCullTR, MetricCount };
struct Source { unsigned tick,system,stop,room,room_flags[4],status[4];float player[6],camera[8],motion_frame;unsigned motion_state; };
struct Snapshot { volatile unsigned sequence;unsigned frame,clock_valid,clock_reads;
    unsigned stage_us[StageCount],calls[StageCount],metrics[MetricCount];Source source; };
static_assert(sizeof(Source)==28*sizeof(std::uint32_t), "source snapshot readback ABI");
static_assert(sizeof(Snapshot)==107*sizeof(std::uint32_t), "profile readback ABI");
#if RE4DC_NATIVE_RENDER_PROFILE && (defined(__sh__) || defined(RE4DC_PROFILE_TEST))
struct State { bool active=false;unsigned stage=Outside,last=0,reads=0;
    std::uint64_t cycles[StageCount]{};unsigned calls[StageCount]{},metrics[MetricCount]{}; };
extern State state;
#if defined(RE4DC_PROFILE_TEST)
extern unsigned test_clock;inline unsigned clock(){return test_clock;}
#else
inline unsigned clock(){
    const timer_val_t time=__dreamcast_get_ticks();
    // Same 80ns tick / seconds conversion as pinned arch_timer_gettime().
    // Unsigned differences remain valid across the ~344s low-word wrap.
    return unsigned(time.secs)*12500000U+time.ticks;
}
#endif
inline unsigned switch_stage(unsigned next){
    const unsigned old=state.stage;if(!state.active || old==next)return old;
    const unsigned now=clock();state.cycles[old]+=unsigned(now-state.last);
    state.last=now;state.stage=next;++state.reads;++state.calls[next];return old;
}
struct Scope { unsigned previous;explicit Scope(unsigned stage):previous(switch_stage(stage)){}
    ~Scope(){switch_stage(previous);}void move(unsigned stage){switch_stage(stage);} };
inline void count(unsigned metric,unsigned value){if(state.active)state.metrics[metric]+=value;}
inline void high(unsigned metric,unsigned value){if(state.active && value>state.metrics[metric])state.metrics[metric]=value;}
inline void begin(){
    state=State{};
#if defined(RE4DC_PROFILE_TEST)
    state.active=true;
#else
    state.active=timer_running(TMU2)!=0;
#endif
    static unsigned calibration=0;static bool calibrated=false;
    state.last=clock();
    if(!calibrated && state.active){
        const unsigned start=clock();
        for(unsigned i=0;i<256;++i){switch_stage(ModelSetup);switch_stage(Outside);}
        calibration=unsigned(clock()-start);calibrated=true;
        state=State{};state.active=true;
    }
    state.metrics[ClockCalibrationTicks]=calibration;
    state.metrics[ClockCalibrationSwitches]=512;
    state.last=clock();state.reads=1;
}
inline void finish(Snapshot& out,unsigned frame,const Source& source){
    const unsigned now=clock();if(state.active)state.cycles[state.stage]+=unsigned(now-state.last);
    out.sequence=out.sequence+1;asm volatile("" ::: "memory");out.source=source;out.frame=frame;out.clock_valid=state.active;out.clock_reads=state.reads+1;
    for(unsigned i=0;i<StageCount;++i){out.stage_us[i]=unsigned(state.cycles[i]*2/25);out.calls[i]=state.calls[i];}
    for(unsigned i=0;i<MetricCount;++i)out.metrics[i]=state.metrics[i];
    state.active=false;asm volatile("" ::: "memory");out.sequence=out.sequence+1;
}
#else
struct Scope { explicit Scope(unsigned){}void move(unsigned){} };
inline void count(unsigned,unsigned){}inline void high(unsigned,unsigned){}
inline void begin(){}inline void finish(Snapshot&,unsigned,const Source&){}
#endif
}
#define RE4DC_PROFILE_SCOPE(stage) re4dc::profile::Scope profile_scope(re4dc::profile::stage)
#define RE4DC_PROFILE_COUNT(metric,value) re4dc::profile::count(re4dc::profile::metric,value)
#define RE4DC_PROFILE_HIGH(metric,value) re4dc::profile::high(re4dc::profile::metric,value)

extern "C" void re4dc_profile_source(re4dc::profile::Source*);
