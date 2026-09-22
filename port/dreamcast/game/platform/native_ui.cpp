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
#include "native_ui.h"
#include "native_model.h"
#include "native_render_profile.hpp"
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
DeferredLighting* deferred_lights=nullptr;
unsigned selected_mask(const SourceLighting& s){return s.enable?s.mask&255U:0U;}
unsigned deferred_light_bytes(const SourceLighting&){return sizeof(DeferredLighting)+light_parameter_bytes;}
unsigned deferred_set_bytes(const SourceLighting& s){
    return sizeof(DeferredLightSet)+__builtin_popcount(selected_mask(s))*sizeof(SourceLight);
}
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

#if RE4DC_PVR_STREAM
// One serial PVR owner, no extra framebuffer or whole-scene packet copy.
// KOS's opt-in manual flip preserves the source's late presentation decision.
bool stream_scene,stream_aborted,stream_retire;
unsigned stream_model_bytes,stream_peak_bytes,stream_discards,stream_black_frames;
pvr_list_t stream_list=PVR_LIST_TR_POLY;
#if RE4DC_D349_RENDERER_STACK
pvr_list_t desired_list=PVR_LIST_OP_POLY;
#endif
void stream_open() {
    pvr_scene_begin();
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
}
void stream_close(bool present) {
    RE4DC_PROFILE_SCOPE(PresentFence);
    if(!stream_scene)stream_open();
    sq_lock((void*)PVR_TA_INPUT);
    if(pvr_list_finish()<0 || pvr_scene_finish()<0)re4dc_missing("native stream finish failed");
    stream_scene=false;
    if(re4dc::gpu::quiesce()!=re4dc::gpu::FenceResult::ready)
        re4dc_missing("native stream completion fence failed");
    if(pvr_resolve_frame(present)<0)re4dc_missing("native source presentation resolve failed");
    if(!present)++stream_discards;
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
void hash_bytes(Key& k,const void* ptr,unsigned size) {
    const auto* p=(const unsigned char*)ptr;
    for(unsigned i=0;i<size;++i) {
        k.fnv=(k.fnv^p[i])*16777619U;k.crc^=p[i];
        for(unsigned b=0;b<8;++b) k.crc=(k.crc>>1)^(0xedb88320U & (0U-(k.crc&1)));
    }
}
bool same_image(const Re4dcUiImage& a,const Re4dcUiImage& b) {
    return a.pixels==b.pixels && a.palette==b.palette && a.width==b.width && a.height==b.height &&
           a.format==b.format && a.palette_format==b.palette_format && a.palette_bytes==b.palette_bytes;
}
bool image_key(const Re4dcUiImage& image,Key& key) {
    for(unsigned n=0;n<nsource;++n) if(same_image(sources[n].image,image)) {key=sources[n].key;return true;}
    Key external{};
    int native=room_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(!native)native=core_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(!native)native=option_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(!native)native=player_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(!native)native=weapon_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    for(auto& e:enemy_identities)if(!native && e.archive)
        native=e.table.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(native<0 || (native && (image.palette || image.palette_bytes))) {
        re4dc_log("native source identity: incompatible descriptor rejected\n");return false;
    }
    if(native) {
        if(identity_hits++<3)re4dc_log("native source identity: %08x-%08x (no source-texel hash)\n",external.crc,external.fnv);
        if(nsource<kSourceCount)sources[nsource++]={image,external};
        key=external;return true;
    }
    const unsigned metadata[]={image.width,image.height,image.format,image.palette_format,image.palette_bytes};
    key={0xffffffffU,2166136261U};hash_bytes(key,metadata,sizeof(metadata));
    hash_bytes(key,image.pixels,image_size(image));
    if(image.palette_bytes) hash_bytes(key,image.palette,image.palette_bytes);
    key.crc=~key.crc;
    if(nsource<kSourceCount) sources[nsource++]={image,key};
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
    for(auto& e:entries) if(e.valid && e.key==key) {if(pin)e.frame=frame;RE4DC_PROFILE_COUNT(TextureHits,1);return &e;}
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
#endif
    re4dc_model_retire_draw_plans();
#if RE4DC_PVR_STREAM
    // Source room retirement can occur on a task while the main thread owns an
    // unfinished TA list. Keep submitted texture owners until that thread closes
    // and fences the discarded scene at Render_swap; no source CPU pointer is
    // retained by PVR. Waiting here would deadlock the caller against main.
    if(stream_scene){stream_aborted=true;stream_retire=true;}
    else
#endif
    if(ready && re4dc::gpu::quiesce()!=re4dc::gpu::FenceResult::ready)
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

extern "C" void re4dc_ui_init(){
    if(ready)return;
    pvr_init_params_t params=pvr_default_params;
#if RE4DC_PVR_STREAM
    // Serialized ownership uses one TA bank. This pinned KOS still reserves
    // both banks, so doubling their size costs another 1MiB of actual VRAM.
    // Flycast's zero TA-used register does not qualify physical TA capacity.
    params.vertex_buf_size=1024*1024;params.vbuf_doublebuf_disabled=1;
#endif
    params.autosort_disabled=1; // source OT is the UI blending order
    ready=pvr_init(&params)==0;
    re4dc_log("native UI: PVR init %s; source ID adapter, 640x480\n",ready?"ok":"FAILED");
    if(ready){
#if RE4DC_PVR_STREAM
        if(pvr_set_manual_flip(true)<0)re4dc_missing("native manual presentation init failed");
        re4dc_log("native source stream: enabled, scratch=65536 TA=1048576 single-bank; late hold/retire/black preserved\n");
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
    frame_ready=ready && re4dc::gpu::quiesce()==re4dc::gpu::FenceResult::ready;
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
#if RE4DC_PVR_STREAM
    stream_close(true);
    if(stream_model_bytes && model_presented++<3)
        re4dc_log("native model DIAGNOSTIC presented: frame=%u bytes=%u\n",frame,stream_model_bytes);
    if(frame%120==0 || (stream_model_bytes && model_presented<=3)){
        pvr_stats_t stats;pvr_get_stats(&stats);
        re4dc_log("native stream: frame=%u model_bytes=%u peak=%u discarded=%u black_frames=%u vram_free=%u textures=%u used=%u loads=%u missing=%u ta_used=%u ta_peak=%u present_us=%llu registration_us=%llu render_us=%llu\n",frame,stream_model_bytes,stream_peak_bytes,stream_discards,stream_black_frames,(unsigned)pvr_mem_available(),kTextureCount,used,loads,missing,(unsigned)stats.vtx_buffer_used,(unsigned)stats.vtx_buffer_used_max,(unsigned long long)(stats.frame_last_time/1000),(unsigned long long)(stats.reg_last_time/1000),(unsigned long long)(stats.rnd_last_time/1000));
    }
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
    const unsigned header_key=list|(p->blend<<3)|(p->depth_mode<<6)|(p->wrap_s<<8)|(p->wrap_t<<10)|((p->material_flags&4)<<12)|(p->cull<<16);
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

extern "C" int re4dc_model_defer_part(const Re4dcModelPart* p){
#if RE4DC_D349_RENDERER_STACK
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
        SourceLighting lighting{};
        if(saved_lighting){lighting=restore_lighting(saved_lighting);view.lighting=&lighting;}
        re4dc_model_submit(&view);
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
