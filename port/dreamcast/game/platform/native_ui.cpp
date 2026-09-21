// Narrow ID-quad backend. Reuses the scene Package and owned storage reader.
// Candidate scope: common unmasked UI; unsupported effects are counted/rejected.
#include <kos.h>
#include <fcntl.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include "native_ui.h"
#include "re4dc_platform.h"
#include "../../room/texture_package.hpp"
#include "../../room/room_storage.hpp"
#include "../../room/gpu_lifecycle.hpp"

namespace {
constexpr unsigned kQuadCount=256, kTextureCount=48, kVramBudget=4*1024*1024;
struct Key { unsigned crc,fnv; bool operator==(const Key& b)const{return crc==b.crc && fnv==b.fnv;} };
struct Entry { re4dc::texture::Package package; Key key{}; unsigned frame=0; bool valid=false; };
struct Source { Re4dcUiImage image{}; Key key{}; };
Entry entries[kTextureCount]; Source sources[256]; unsigned nsource;
Re4dcUiQuad quads[kQuadCount]; Entry* handles[kQuadCount]; unsigned nquad,frame,used,peak,staging_peak;
unsigned dropped,unsupported,missing,drawn,culled,loads,reclaimed; bool ready,frame_ready;
extern "C" int re4dc_vi_black();

unsigned image_size(const Re4dcUiImage& i) {
    unsigned bw,bh,bytes;
    switch(i.format) {
    case 0:case 8:case 14:bw=8;bh=8;bytes=32;break;
    case 1:case 2:case 9:bw=8;bh=4;bytes=32;break;
    case 3:bw=4;bh=4;bytes=32;break;
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
Key image_key(const Re4dcUiImage& image) {
    for(unsigned n=0;n<nsource;++n) if(same_image(sources[n].image,image)) return sources[n].key;
    const unsigned metadata[]={image.width,image.height,image.format,image.palette_format,image.palette_bytes};
    Key key{0xffffffffU,2166136261U};hash_bytes(key,metadata,sizeof(metadata));
    hash_bytes(key,image.pixels,image_size(image));
    if(image.palette_bytes) hash_bytes(key,image.palette,image.palette_bytes);
    key.crc=~key.crc;
    if(nsource<256) sources[nsource++]={image,key};
    return key;
}
void close_entry(Entry& entry) {
    if(entry.valid) used-=entry.package.vram_bytes();
    entry.package.close();entry.valid=false;
}
Entry* load(const Re4dcUiImage& image) {
    if(!image.pixels || !image_size(image) || !image.width || !image.height || image.width>1024 || image.height>1024) return nullptr;
    const Key key=image_key(image);
    for(auto& e:entries) if(e.valid && e.key==key) {e.frame=frame;return &e;}
    Entry* slot=nullptr;
    for(auto& e:entries) if(!e.valid){slot=&e;break;}
    if(!slot) for(auto& e:entries) if(e.frame!=frame && (!slot || e.frame<slot->frame)) slot=&e;
    if(!slot) return nullptr;
    close_entry(*slot); // caller has completed both TA and render fences
    char path[96];std::sprintf(path,"/cd/dc/tex/%08x-%08x.re4tex",key.crc,key.fnv);
    re4dc_log("native UI: load %s %ux%u fmt=%u\n",path,image.width,image.height,image.format);
    file_t f=fs_open(path,O_RDONLY);if(f<0) {re4dc_log("native UI: missing package\n");return nullptr;}
    const ssize_t size=fs_total(f);fs_close(f);
    if(size<48 || size>2*1024*1024+4096) return nullptr;
    const int heap_before=re4dc_ui_heap_free();
    void* backing=re4dc_ui_stage_alloc((size+31)&~31U);if(!backing) return nullptr;
    if((unsigned)size>staging_peak) staging_peak=size;
    re4dc::storage::Arena arena;arena.init((unsigned char*)backing,(size+31)&~31U);
    re4dc_log("native UI: read bytes=%u\n",(unsigned)size);
    auto read=re4dc::storage::read_file(arena,path);
    re4dc_log("native UI: read complete error=%s\n",read.error?read.error:"none");
    bool ok=read.data && slot->package.adopt(read.data,read.size);
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
    if(ok) ok=slot->package.upload() && slot->package.release_payload();
    re4dc_log("native UI: upload %s vram=%u\n",ok?"ok":"FAILED",slot->package.vram_bytes());
    if(!ok) slot->package.close();
    re4dc_ui_stage_free(backing);
    re4dc_log("native UI: stage freed bytes=%u heap=%d->%d metadata=%u\n",(unsigned)((size+31)&~31U),heap_before,re4dc_ui_heap_free(),slot->package.metadata_bytes());
    if(ok){++loads;reclaimed+=(size+31)&~31U;}
    if(!ok) return nullptr;
    slot->valid=true;slot->key=key;slot->frame=frame;used+=slot->package.vram_bytes();
    if(used>peak) peak=used;
    return slot;
}
}
extern "C" void re4dc_ui_invalidate_sources(){nsource=0;}
extern "C" void re4dc_ui_init(){
    if(ready)return;
    pvr_init_params_t params=pvr_default_params;
    params.autosort_disabled=1; // source OT is the UI blending order
    ready=pvr_init(&params)==0;
    re4dc_log("native UI: PVR init %s; source ID adapter, 640x480\n",ready?"ok":"FAILED");
    if(ready)pvr_set_bg_color(0,0,0);
}
extern "C" void re4dc_ui_begin(){
    nquad=0;++frame;
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
    for(unsigned i=0;i<nquad && !re4dc_vi_black();++i){
        if(!handles[i])continue;
        const auto& q=quads[i];const auto& t=handles[i]->package.textures()[0];
        unsigned fmt=t.format==re4dc::texture::kRgb565?PVR_TXRFMT_RGB565:
                     t.format==re4dc::texture::kArgb1555?PVR_TXRFMT_ARGB1555:PVR_TXRFMT_ARGB4444;
        pvr_poly_cxt_t c;pvr_poly_cxt_txr(&c,PVR_LIST_TR_POLY,fmt,t.width,t.height,
                            handles[i]->package.pvr_texture(0),PVR_FILTER_BILINEAR);
        c.gen.culling=PVR_CULLING_NONE;c.depth.comparison=PVR_DEPTHCMP_ALWAYS;c.depth.write=PVR_DEPTHWRITE_DISABLE;
        const pvr_blend_mode_t src[]={PVR_BLEND_SRCALPHA,PVR_BLEND_SRCALPHA,PVR_BLEND_ONE,PVR_BLEND_DESTCOLOR,PVR_BLEND_DESTCOLOR};
        const pvr_blend_mode_t dst[]={PVR_BLEND_INVSRCALPHA,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ONE,PVR_BLEND_ZERO};
        c.blend.src=src[q.blend];c.blend.dst=dst[q.blend];c.txr.env=PVR_TXRENV_MODULATEALPHA;c.txr.uv_clamp=PVR_UVCLAMP_UV;
        pvr_poly_hdr_t header;pvr_poly_compile(&header,&c);pvr_prim(&header,sizeof(header));
        pvr_vertex_t v[4]{};const unsigned order[]={0,1,3,2};
        for(unsigned n=0;n<4;++n){unsigned j=order[n];v[n].flags=n==3?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX;
            v[n].x=q.xy[2*j];v[n].y=q.xy[2*j+1];v[n].z=1.0f;
            v[n].u=q.uv[2*j]*q.image.width/t.width;v[n].v=q.uv[2*j+1]*q.image.height/t.height;v[n].argb=q.color;}
        pvr_prim(v,sizeof(v));++drawn;
    }
    pvr_list_finish();pvr_scene_finish();
    if(frame%120==0) re4dc_log("native UI: frame=%u quads=%u drawn=%u missing=%u unsupported=%u drops=%u vram=%u peak=%u staging=%u loads=%u freed=%u culled=%u fb=%08x,%08x black=%d\n",frame,nquad,drawn,missing,unsupported,dropped,used,peak,staging_peak,loads,reclaimed,culled,(unsigned)pvr_get_front_buffer(),(unsigned)pvr_get_back_buffer(),re4dc_vi_black());
}
