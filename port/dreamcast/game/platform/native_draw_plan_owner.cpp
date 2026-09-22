#include "native_model.h"
#include "re4dc_platform.h"
#include "../../room/native_draw_plan.hpp"
#ifndef RE4DC_MODEL_DRAW_PLANS
#define RE4DC_MODEL_DRAW_PLANS 0
#endif
#if RE4DC_MODEL_DRAW_PLANS
#include "../../room/room_storage.hpp"
#include <cstdlib>
#include <cstdint>
#include <cstring>

namespace {
constexpr unsigned kCapacity=16*1024, kEntries=128, kOwners=12;
struct Owner { const void* key; std::uintptr_t start; unsigned bytes,transient; } owners[kOwners]{};
struct Entry {
    const void* stream=nullptr;
    unsigned bytes=0,positions=0,normals=0,colored=0;
    const re4dc::render::NativeDrawPlan* plan=nullptr;
} entries[kEntries];
re4dc::storage::Arena arena;
unsigned leases=0; bool reset_pending=false, allocation_attempted=false, free_pending=false;
Re4dcDrawPlanStats stats{}, previous{};
unsigned previous_walk_bytes=0;
bool contains(const Owner& o,const void* p,unsigned bytes) {
    auto a=reinterpret_cast<std::uintptr_t>(p);
    return o.key && a>=o.start && a-o.start<=o.bytes && bytes<=o.bytes-(a-o.start);
}
void reset_now() {
    for(auto& e:entries) e={};
    arena.reset();stats.used=0;
    reset_pending=false;++stats.resets;
    if(free_pending){std::free(arena.base());arena.init(nullptr,0);stats.capacity=0;allocation_attempted=false;free_pending=false;}
}
}
extern "C" void re4dc_model_reset_draw_plans() {
    if(leases) reset_pending=true; else reset_now();
}
extern "C" void re4dc_model_bind_draw_owner(const void* key,void* archive,unsigned bytes,unsigned transient) {
    re4dc_model_reset_draw_plans();
    Owner* slot=nullptr;
    for(auto& o:owners) { if(o.key==key) { slot=&o;break; } if(!o.key && !slot) slot=&o; }
    if(!slot) { re4dc_log("native draw plans: owner capacity exhausted\n"); return; }
    *slot={archive && bytes?key:nullptr,reinterpret_cast<std::uintptr_t>(archive),bytes,transient};
}
extern "C" void re4dc_model_retire_draw_plans() {
    for(auto& o:owners)if(o.transient)o={};
    free_pending=true;re4dc_model_reset_draw_plans();
}
extern "C" void re4dc_model_unbind_draw_owner(const void* key) {
    re4dc_model_reset_draw_plans();
    for(auto& o:owners) if(o.key==key) o={};
}
extern "C" const re4dc::render::NativeDrawPlan* re4dc_model_acquire_draw_plan(const Re4dcModelPart* p,int* invalid) {
    *invalid=0;
    if(reset_pending) { ++stats.uncovered;return nullptr; }
    bool owned=false;
    for(const auto& o:owners) if(contains(o,p->part,32) && contains(o,p->stream,p->stream_bytes)) {owned=true;break;}
    if(!owned) {++stats.owner_misses;++stats.uncovered;return nullptr;}
    const unsigned colored=bool(p->flags&0x80000000U);
    unsigned slot=(reinterpret_cast<std::uintptr_t>(p->stream)>>5)&(kEntries-1);
    Entry* entry=nullptr;
    for(unsigned n=0;n<kEntries;++n,slot=(slot+1)&(kEntries-1)) {
        auto& e=entries[slot];
        if(!e.stream) {entry=&e;break;}
        if(e.stream==p->stream && e.bytes==p->stream_bytes && e.positions==p->position_count &&
           e.normals==p->normal_count && e.colored==colored) {
            if(!e.plan) {++stats.capacity_rejects;++stats.uncovered;return nullptr;}
            ++stats.hits;++leases;return e.plan;
        }
    }
    if(!entry) {++stats.capacity_rejects;++stats.uncovered;return nullptr;}
    if(!allocation_attempted) {
        allocation_attempted=true;
        // KOS malloc, never the source operator new / current room heap.
        auto* memory=static_cast<std::uint8_t*>(std::malloc(kCapacity));
        arena.init(memory,memory?kCapacity:0);stats.capacity=arena.capacity();
        re4dc_log("native draw plans: bounded backing=%u source_heap=%d\n",stats.capacity,re4dc_ui_heap_free());
    }
    *entry={p->stream,p->stream_bytes,p->position_count,p->normal_count,colored,nullptr};
    // Stable negative admission avoids re-decoding an uncacheable part on every
    // lookup. Such parts use the explicit reference path; no LRU disc/CPU churn.
    re4dc::render::DrawPlanRequirements requirements;
    stats.source_bytes+=p->stream_bytes;
    if(!re4dc::render::inspect_draw_plan(p->stream,p->stream_bytes,colored,
             p->position_count,p->normal_count,requirements)) {
        *entry={};++stats.invalid;*invalid=1;return nullptr;
    }
    const auto mark=arena.mark();
    void* memory=arena.allocate(requirements.bytes);
    if(!memory) {++stats.capacity_rejects;++stats.uncovered;return nullptr;}
    stats.source_bytes+=p->stream_bytes;
    entry->plan=re4dc::render::prepare_draw_plan(memory,requirements.bytes,p->stream,
                                               p->stream_bytes,colored,requirements);
    if(!entry->plan) {arena.rewind(mark);*entry={};++stats.invalid;*invalid=1;return nullptr;}
    ++stats.installs;++leases;stats.used=arena.used();if(arena.high_water()>stats.peak)stats.peak=arena.high_water();return entry->plan;
}
extern "C" void re4dc_model_release_draw_plan() {
    if(!leases) {re4dc_missing("native draw plan lease underflow");return;}
    if(--leases==0 && reset_pending)reset_now();
}
extern "C" void re4dc_model_draw_plan_frame(unsigned frame) {
    const unsigned walk_bytes=re4dc_model_work_stats()->gx_walk_bytes;
    if(stats.installs!=previous.installs || (stats.hits!=previous.hits && frame%30==0))
        re4dc_log("native draw plans: frame=%u hits=%u installs=%u install_decoded=%u reference_walk=%u uncovered=%u capacity_rejects=%u owner_misses=%u invalid=%u used=%u cap=%u peak=%u resets=%u\n",
          frame,stats.hits-previous.hits,stats.installs-previous.installs,
          stats.source_bytes-previous.source_bytes,walk_bytes-previous_walk_bytes,stats.uncovered-previous.uncovered,
          stats.capacity_rejects-previous.capacity_rejects,stats.owner_misses-previous.owner_misses,
          stats.invalid-previous.invalid,stats.used,stats.capacity,stats.peak,stats.resets);
    previous=stats;previous_walk_bytes=walk_bytes;
}
extern "C" const Re4dcDrawPlanStats* re4dc_model_draw_plan_stats(){return &stats;}
#else
extern "C" void re4dc_model_bind_draw_owner(const void*,void*,unsigned,unsigned) {}
extern "C" void re4dc_model_retire_draw_plans() {}
extern "C" void re4dc_model_unbind_draw_owner(const void*) {}
extern "C" void re4dc_model_reset_draw_plans() {}
extern "C" const re4dc::render::NativeDrawPlan* re4dc_model_acquire_draw_plan(const Re4dcModelPart*,int* invalid) {*invalid=0;return nullptr;}
extern "C" void re4dc_model_release_draw_plan() {}
extern "C" void re4dc_model_draw_plan_frame(unsigned) {}
extern "C" const Re4dcDrawPlanStats* re4dc_model_draw_plan_stats(){static Re4dcDrawPlanStats empty{};return &empty;}
#endif
