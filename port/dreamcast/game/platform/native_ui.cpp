// Narrow ID-quad backend. Reuses the scene Package and owned storage reader.
// Candidate scope: common unmasked UI; unsupported effects are counted/rejected.
#include <kos.h>
#include <fcntl.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <malloc.h>
#include "native_ui.h"
#include "native_model.h"
#include "re4dc_platform.h"
#include "../../room/texture_package.hpp"
#include "../../room/room_storage.hpp"
#include "../../room/gpu_lifecycle.hpp"
#include "../../room/pvr_geometry.hpp"

namespace {
constexpr unsigned kQuadCount=256, kTextureCount=48, kVramBudget=4*1024*1024;
struct Key { unsigned crc,fnv; bool operator==(const Key& b)const{return crc==b.crc && fnv==b.fnv;} };
struct Entry { re4dc::texture::Package package; Key key{}; unsigned frame=0; bool valid=false; };
struct Source { Re4dcUiImage image{}; Key key{}; };
Entry entries[kTextureCount]; Source sources[256]; unsigned nsource;
re4dc::texture::SourceIdentityTable room_identities,core_identities,player_identities,weapon_identities;unsigned identity_hits;
// Match the recovered loader's four module owners; texture uploads still share
// the existing cache and VRAM budget. These views own no texels or allocations.
struct EnemyIdentity { void* archive=nullptr; re4dc::texture::SourceIdentityTable table; };
EnemyIdentity enemy_identities[4];
Re4dcUiQuad quads[kQuadCount]; Entry* handles[kQuadCount]; unsigned nquad,frame,used,peak,staging_peak;
unsigned dropped,unsupported,missing,drawn,culled,loads,reclaimed; bool ready,frame_ready;
extern "C" int re4dc_vi_black();
// Diagnostic only: 64 KiB of copied native packets, allocated on first model.
// Roll back an entire part on overflow. No deferred source/primitive pointers.
constexpr unsigned kModelPacketBytes=64*1024;
pvr_vertex_t* model_packets; unsigned model_used,model_pending;
int model_diagnostic=-1;
unsigned model_parts,model_invalid,model_resource,model_overflow,model_input,model_output,model_peak,model_presented;


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
    if(!native)native=player_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(!native)native=weapon_identities.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    for(auto& e:enemy_identities)if(!native && e.archive)
        native=e.table.lookup(image.pixels,image.width,image.height,image.format,external.crc,external.fnv);
    if(native<0 || (native && (image.palette || image.palette_bytes))) {
        re4dc_log("native source identity: incompatible descriptor rejected\n");return false;
    }
    if(native) {
        if(identity_hits++<3)re4dc_log("native source identity: %08x-%08x (no source-texel hash)\n",external.crc,external.fnv);
        if(nsource<256)sources[nsource++]={image,external};
        key=external;return true;
    }
    const unsigned metadata[]={image.width,image.height,image.format,image.palette_format,image.palette_bytes};
    key={0xffffffffU,2166136261U};hash_bytes(key,metadata,sizeof(metadata));
    hash_bytes(key,image.pixels,image_size(image));
    if(image.palette_bytes) hash_bytes(key,image.palette,image.palette_bytes);
    key.crc=~key.crc;
    if(nsource<256) sources[nsource++]={image,key};
    return true;
}
void close_entry(Entry& entry) {
    if(entry.valid) used-=entry.package.vram_bytes();
    entry.package.close();entry.valid=false;
}
Entry* load(const Re4dcUiImage& image) {
    if(!image.pixels || !image_size(image) || !image.width || !image.height || image.width>1024 || image.height>1024) return nullptr;
    Key key{};if(!image_key(image,key))return nullptr;
    for(auto& e:entries) if(e.valid && e.key==key) {e.frame=frame;return &e;}
    Entry* slot=nullptr;
    for(auto& e:entries) if(!e.valid){slot=&e;break;}
    if(!slot) for(auto& e:entries) if(e.frame!=frame && (!slot || e.frame<slot->frame)) slot=&e;
    if(!slot) return nullptr;
    close_entry(*slot); // caller has completed both TA and render fences
    char path[96];std::sprintf(path,"/cd/dc/tex/%08x-%08x.re4tex",key.crc,key.fnv);
    re4dc_log("native UI: load %s %ux%u fmt=%u\n",path,image.width,image.height,image.format);
    const int heap_before=re4dc_ui_heap_free();
    bool ok=slot->package.open_streamed(path);
    if(!ok) re4dc_log("native UI: package rejected: %s\n",slot->package.error());
    if(ok) {
        const auto& h=slot->package.header();
        ok=h.texture_count==1 && h.data_size<=kVramBudget;
        if(ok) {
            while(used+h.data_size>kVramBudget) {
                Entry* victim=nullptr;
                for(auto& e:entries) if(e.valid && e.frame!=frame && (!victim || e.frame<victim->frame)) victim=&e;
                if(!victim) {ok=false;break;} close_entry(*victim);
            }
        }
    }
    const unsigned vram_before=pvr_mem_available();
    if(ok) ok=slot->package.upload() && slot->package.release_payload();
    if(ok && slot->package.textures()[0].payload==re4dc::texture::kPayloadVq){
        const auto& t=slot->package.textures()[0];
        const volatile unsigned char* data=(const volatile unsigned char*)slot->package.pvr_texture(0);
        unsigned fnv=2166136261U;
        for(unsigned n=0;n<t.data_size;++n)fnv=(fnv^data[n])*16777619U;
        re4dc_log("native texture VQ: ptr=%08x bytes=%u raw16=%u format=%08x readback_fnv=%08x free_vram=%u allocation_delta=%u\n",(unsigned)data,t.data_size,t.width*t.height*2,re4dc::texture::pvr_format(t),fnv,(unsigned)pvr_mem_available(),vram_before-(unsigned)pvr_mem_available());
    }
    re4dc_log("native UI: upload %s vram=%u\n",ok?"ok":"FAILED",slot->package.vram_bytes());
    if(!ok) slot->package.close();
    re4dc_log("native UI: bounded upload heap=%d->%d metadata=%u staging=existing-65536 source_allocation=0\n",heap_before,re4dc_ui_heap_free(),slot->package.metadata_bytes());
    if(ok)++loads;
    if(!ok) return nullptr;
    slot->valid=true;slot->key=key;slot->frame=frame;used+=slot->package.vram_bytes();
    if(used>peak) peak=used;
    return slot;
}
}
extern "C" void re4dc_ui_invalidate_sources(){nsource=0;}
extern "C" int re4dc_ui_bind_core(void* archive,unsigned bytes){
    nsource=0;
    const bool ok=core_identities.adopt(archive,bytes);
    re4dc_log("native core identities: %s count=%u archive=%u metadata_owner=core\n",ok?"ok":"REJECTED",core_identities.count(),bytes);
    return ok;
}
extern "C" int re4dc_ui_bind_room(void* archive,unsigned bytes){
    nsource=0;identity_hits=0;
    const bool ok=room_identities.adopt(archive,bytes);
    re4dc_log("native room identities: %s count=%u archive=%u metadata_owner=room\n",ok?"ok":"REJECTED",room_identities.count(),bytes);
    return ok;
}
// Player and weapon regions persist across room retirement when the source
// retains them. Their explicit source release/overwrite boundaries clear views.
extern "C" int re4dc_ui_bind_player(void* archive,unsigned bytes){
    nsource=0;bool ok=player_identities.adopt(archive,bytes);
    re4dc_log("native player identities: %s count=%u archive=%u\n",ok?"ok":"REJECTED",player_identities.count(),bytes);return ok;
}
extern "C" int re4dc_ui_bind_weapon(void* archive,unsigned bytes){
    nsource=0;bool ok=weapon_identities.adopt(archive,bytes);
    re4dc_log("native weapon identities: %s count=%u archive=%u\n",ok?"ok":"REJECTED",weapon_identities.count(),bytes);return ok;
}
extern "C" void re4dc_ui_unbind_player(){player_identities.clear();nsource=0;}
extern "C" void re4dc_ui_unbind_weapon(){weapon_identities.clear();nsource=0;}
extern "C" int re4dc_ui_bind_enemy(void* archive,unsigned bytes){
    re4dc::texture::SourceIdentityTable table;
    if(!table.adopt(archive,bytes))return 0;
    if(!table.count())return 1; // ordinary archive; no view needed
    EnemyIdentity* slot=nullptr;
    for(auto& e:enemy_identities){if(e.archive==archive)return 0;if(!e.archive && !slot)slot=&e;}
    if(!slot)return 0;
    slot->archive=archive;slot->table=table;nsource=0;
    re4dc_log("native enemy identities: count=%u archive=%u metadata_owner=enemy upload_staging=0\n",table.count(),bytes);
    return 1;
}
extern "C" void re4dc_ui_unbind_enemy(void* archive){
    for(auto& e:enemy_identities)if(archive && e.archive==archive){e.table.clear();e.archive=nullptr;}
    // Queued packets own copied native vertices/headers and cache handles; no
    // queued reader borrows archive texels. This does not free live VRAM uploads.
    nsource=0;
}
extern "C" void re4dc_ui_retire_room(){
    if(ready && re4dc::gpu::quiesce()!=re4dc::gpu::FenceResult::ready)
        re4dc_missing("native room retire fence failed");
    // No queued draw may outlive its source room. Shared cached uploads may be
    // reloaded from their stable identities; no archive texels are needed.
    // Core descriptors belong to the persistent core region and survive this reset.
    nquad=0;model_used=0;nsource=0;room_identities.clear();identity_hits=0;
    for(auto& e:enemy_identities){e.table.clear();e.archive=nullptr;}
    for(auto& entry:entries)close_entry(entry);
}

extern "C" void re4dc_ui_init(){
    if(ready)return;
    pvr_init_params_t params=pvr_default_params;
    params.autosort_disabled=1; // source OT is the UI blending order
    ready=pvr_init(&params)==0;
    re4dc_log("native UI: PVR init %s; source ID adapter, 640x480\n",ready?"ok":"FAILED");
    if(ready)pvr_set_bg_color(0,0,0);
}
extern "C" void re4dc_ui_begin(){
    if(model_diagnostic==1 && frame%120==0)
        re4dc_log("native model DIAGNOSTIC boundary: frame=%u previous_bytes=%u committed_parts=%u invalid=%u resource=%u overflow=%u presented=%u\n",frame,model_used*32,model_parts,model_invalid,model_resource,model_overflow,model_presented);
    nquad=0;model_used=0;++frame;
    frame_ready=ready && re4dc::gpu::quiesce()==re4dc::gpu::FenceResult::ready;
}
extern "C" void re4dc_ui_submit(const Re4dcUiQuad* q){
    if(!frame_ready)return;
    // Source IdCommonTrans alpha-compare is GREATER 1 after modulation.
    // Zero material alpha cannot produce a surviving fragment for any blend.
    if((q->color>>24)==0){++culled;return;}
    if(q->masked || q->blend>4){++unsupported;return;}
    if(nquad==kQuadCount){++dropped;return;}
    for(unsigned n=0;n<8;++n) if(!std::isfinite(q->xy[n]) || !std::isfinite(q->uv[n])) {++unsupported;return;}
    if(!drawn && !nquad) re4dc_log("native UI: first quad xy=%d,%d color=%08x\n",(int)q->xy[0],(int)q->xy[1],q->color);
    // Source texture storage can be retired by the following TaskScheduler.
    // Resolve/upload while the OT consumer still owns valid source pointers.
    Entry* handle=load(q->image);
    if(!handle){++missing;return;}
    handles[nquad]=handle;quads[nquad++]=*q;
}
extern "C" void re4dc_ui_present(){
    if(!frame_ready)return;
    pvr_scene_begin();pvr_list_begin(PVR_LIST_TR_POLY);
    if(model_used && !re4dc_vi_black()){
        re4dc::render::submit_pvr(model_packets,model_used*sizeof(pvr_vertex_t));
        if(model_presented++<3)re4dc_log("native model DIAGNOSTIC presented: frame=%u bytes=%u\n",frame,model_used*32);
    }
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
        re4dc::render::submit_pvr(commands,sizeof(commands));++drawn;
    }
    pvr_list_finish();pvr_scene_finish();
    if(frame%120==0 && model_diagnostic==1)
        re4dc_log("native model DIAGNOSTIC: frame=%u packets=%u parts=%u invalid=%u resource=%u overflow=%u input=%u emitted=%u peak=%u heap=%d black=%d\n",frame,model_used*32,model_parts,model_invalid,model_resource,model_overflow,model_input,model_output,model_peak,re4dc_ui_heap_free(),re4dc_vi_black());
    if(frame%120==0) re4dc_log("native UI: frame=%u quads=%u drawn=%u missing=%u unsupported=%u drops=%u vram=%u peak=%u staging=%u loads=%u freed=%u culled=%u fb=%08x,%08x black=%d\n",frame,nquad,drawn,missing,unsupported,dropped,used,peak,staging_peak,loads,reclaimed,culled,(unsigned)pvr_get_front_buffer(),(unsigned)pvr_get_back_buffer(),re4dc_vi_black());
}

extern "C" int re4dc_model_diagnostic_enabled(){
    if(model_diagnostic<0){
        file_t f=fs_open("/cd/dc/model-diagnostic.flag",O_RDONLY);
        model_diagnostic=f>=0;if(f>=0)fs_close(f);
        if(model_diagnostic)re4dc_log("native model DIAGNOSTIC enabled: source pose/camera, base textures only; no lighting/TEV/fog acceptance; 65536-byte packet cap\n");
    }
    return model_diagnostic;
}
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart* p,Re4dcModelPacket* out){
    if(!frame_ready || !re4dc_model_diagnostic_enabled() || p->blend>4 || p->depth_mode>2 ||
       p->wrap_s>1 || p->wrap_t>1 || (p->material_flags&4) || (p->image.format>=8 && p->image.format!=14) || !p->image.pixels)return 0;
    if(!model_packets){
        // KOS-owned bounded scratch outlives source room-heap resets. Using the
        // current source heap here would leave a dangling queue after room retire.
        model_packets=(pvr_vertex_t*)memalign(32,kModelPacketBytes);
        re4dc_log("native model DIAGNOSTIC packet allocation=%08x bytes=%u heap=%d\n",(unsigned)model_packets,kModelPacketBytes,re4dc_ui_heap_free());
        if(!model_packets)return 0;
    }
    if(model_used+7>kModelPacketBytes/32)return 0;
    Entry* handle=load(p->image);if(!handle)return 0;
    const auto& t=handle->package.textures()[0];
    // Repeating a padded image would repeat its border. Reject, never change wrap.
    if((p->wrap_s && t.width!=p->image.width)||(p->wrap_t && t.height!=p->image.height))return 0;
    unsigned fmt=re4dc::texture::pvr_format(t);
    pvr_poly_cxt_t c;pvr_poly_cxt_txr(&c,PVR_LIST_TR_POLY,fmt,t.width,t.height,handle->package.pvr_texture(0),PVR_FILTER_BILINEAR);
    c.gen.culling=PVR_CULLING_NONE; // source cull applied once by shared clipper
    c.depth.comparison=p->depth_mode==2?PVR_DEPTHCMP_ALWAYS:PVR_DEPTHCMP_GEQUAL;
    c.depth.write=p->depth_mode==0?PVR_DEPTHWRITE_ENABLE:PVR_DEPTHWRITE_DISABLE;
    const pvr_blend_mode_t src[]={PVR_BLEND_SRCALPHA,PVR_BLEND_SRCALPHA,PVR_BLEND_ONE,PVR_BLEND_DESTCOLOR,PVR_BLEND_ONE};
    const pvr_blend_mode_t dst[]={PVR_BLEND_INVSRCALPHA,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ZERO};
    c.blend.src=src[p->blend];c.blend.dst=dst[p->blend];c.txr.env=PVR_TXRENV_MODULATEALPHA;
    c.txr.uv_clamp=(pvr_uv_clamp_t)((p->wrap_s?0:PVR_UVCLAMP_U)|(p->wrap_t?0:PVR_UVCLAMP_V));
    pvr_poly_hdr_t header;pvr_poly_compile(&header,&c);std::uint32_t count;
    re4dc::render::begin_pvr_packet(model_packets+model_used,count,header);
    model_pending=model_used+count;
    out->vertices=model_packets+model_pending;out->capacity=kModelPacketBytes/32-model_pending;
    out->u_scale=float(p->image.width)/t.width;out->v_scale=float(p->image.height)/t.height;
    if(model_parts<6)re4dc_log("native model DIAGNOSTIC source=%08x info=%08x part=%08x positions=%u stride=%u stream=%u flags=%08x material=%02x cull=%u\n",(unsigned)p->model,(unsigned)p->info,(unsigned)p->part,p->position_count,p->position_stride,p->stream_bytes,p->flags,p->material_flags,p->cull);
    return 1;
}
extern "C" void re4dc_model_packet_commit(unsigned count){
    if(count){model_used=model_pending+count;if(model_used*32>model_peak)model_peak=model_used*32;}
}
extern "C" void re4dc_model_result(unsigned reason,unsigned input,unsigned output){
    if(reason==0)++model_parts;else if(reason==1)++model_invalid;else if(reason==2)++model_resource;else ++model_overflow;
    model_input+=input;model_output+=output;
}
