// Recovered commonModelTrans -> existing native frame/packet/texture owner.
// Diagnostic base-material connection; not full GX lighting/TEV emulation.
#include "light.h"
#include "global.h"
#include "model.h"
#include "gx.h"
#include "native_model.h"
#if RE4DC_NATIVE_FOG
#include "view.h"
extern "C" unsigned re4dc_fog_enabled();
extern "C" void re4dc_fog_note_far(float far);
#endif
#include <stddef.h>
#include <string.h>
static_assert(sizeof(ModelPart)==0x20 && offsetof(ModelPart,size)==0x18);
static_assert(offsetof(ModelData,pParts)==0x1c && offsetof(ModelData,nVtx)==0x38);
static_assert(sizeof(void*)==4 && sizeof(GXTexObj)==32);
extern "C" void GXGetProjectionv(float*);
extern "C" void GXGetViewportv(float*);
#if RE4DC_NATIVE_ACTOR
#include "native_actor.hpp"
extern "C" void* re4dc_prim_tail(unsigned bytes,unsigned reserve);
#endif
namespace {
#if RE4DC_NATIVE_ACTOR
// Once per source Render(): the actor workspace is the unused tail of this
// frame's primitive buffer. Trans() filled the buffer before Render(); the next
// SetPrimBuffPtr() (after Render() and its translucent drain) releases it, so
// nothing stays resident. 56 KiB covers the largest D358 actor info
// (3622 positions x 12 + 2785 normals x 4 = 54,604 B); a larger or unfunded
// info declines to the generic path.
unsigned actor_frame=~0U;
void bind_actor_frame(){
    if(actor_frame==pG->Frame_cnt)return;
    actor_frame=pG->Frame_cnt;
    constexpr unsigned kBytes=56*1024,kReserve=16*1024;
#if RE4DC_NATIVE_ACTOR_FAST
    // Meshlet path: per-part conversion scratch + skin tables; 96 KiB when
    // the buffer has it, else the same 56 KiB (larger parts then decline).
    constexpr unsigned kFastBytes=96*1024;
    if(void* fw=re4dc_prim_tail(kFastBytes,kReserve)){re4dc_actor_frame(fw,kFastBytes);return;}
#endif
    void* w=re4dc_prim_tail(kBytes,kReserve);
    re4dc_actor_frame(w,w?kBytes:0);
}
#endif
Re4dcUiImage selected{},mask{};
unsigned mask_ref=256,mask_same_uv;
unsigned wrap_s,wrap_t;
float scroll_u,scroll_v;
}
#if RE4DC_NATIVE_ACTOR_FAST
// Unskinned source arrays of an info, for draw-time skinning (NATIVE_ACTOR_SKIN).
extern "C" int re4dc_actor_model_source(const void* info_ptr,Re4dcActorSource* out){
    auto* info=(const cModelInfo*)info_ptr;
    if(!info || !out || !info->pData)return 0;
    const ModelData* d=info->pData;
    out->positions=(const unsigned char*)d->vtxOrig;out->normals=(const unsigned char*)d->nrmOrig;
    out->position_count=d->nVtx;out->normal_count=d->nNrm;
    out->palette_entries=d->weight_ext_num>0xff?d->weight_ext_num:d->weight_palette_num;
    out->small_normals=(d->flags&0x20000000U)!=0;
    return 1;
}
#endif
extern "C" void re4dc_model_material(const void* object,float u,float v,unsigned flags){
    selected={};mask={};mask_ref=256;mask_same_uv=0;
    if(!object || (flags&4))return; // multi-texture blend needs its own native path
    // Current native GXTexObj layout, after source texture animation/swaps.
    const unsigned* w=(const unsigned*)object;
    selected.pixels=(const void*)w[0];selected.width=w[1]>>16;selected.height=w[1]&65535;
    selected.format=w[2];selected.palette_format=0xffffffffU;
    wrap_s=(w[3]>>8)&255;wrap_t=w[3]&255;
    scroll_u=(flags&1)?u:0;scroll_v=(flags&1)?v:0;
}
extern "C" void re4dc_model_alpha_material(const void* object,unsigned ref,unsigned same_uv){
#if RE4DC_D349_RENDERER_STACK
    if(!object)return;
    const unsigned* w=(const unsigned*)object;
    mask.pixels=(const void*)w[0];mask.width=w[1]>>16;mask.height=w[1]&65535;
    mask.format=w[2];mask.palette_format=0xffffffffU;
    mask_ref=ref;mask_same_uv=same_uv && ((w[3]>>8)&255)==wrap_s && (w[3]&255)==wrap_t;
#else
    (void)object;(void)ref;(void)same_uv;
#endif
}
#if RE4DC_FRONT_NATIVE>=2
// D367 FRONT_NATIVE=2 (trans.cpp ModelRender): the source path records a hash per field group of
// every part it submits for one model (mode 1); the native replay (mode 2) is compared part by
// part and not drawn. Groups: 0 geometry/arrays/modes, 1 modelview, 2 projection+viewport,
// 3 texture+uv, 4 alpha state, 5 alpha mask, 6 static binding, 7 lighting contents.
extern "C" void re4dc_log(const char* fmt,...);
namespace {
constexpr unsigned kFrontParts=512,kFrontGroups=8;
unsigned front_mode,front_n,front_k,front_model_bad,front_block=~0U,front_logged;
unsigned front_hash[kFrontParts][kFrontGroups];
unsigned front_models,front_parts,front_bad_parts,front_bad_models,front_group_bad[kFrontGroups];
inline unsigned fnv(unsigned h,const void* p,unsigned n){
    auto* b=(const unsigned char*)p;for(unsigned i=0;i<n;++i)h=(h^b[i])*16777619U;return h;
}
template<class T> inline unsigned fv(unsigned h,const T& v){return fnv(h,&v,sizeof(v));}
inline unsigned fimg(unsigned h,const Re4dcUiImage& i){
    h=fv(h,i.pixels);h=fv(h,i.palette);h=fv(h,i.width);h=fv(h,i.height);h=fv(h,i.format);
    h=fv(h,i.palette_format);return fv(h,i.palette_bytes);
}
void front_hash_part(const Re4dcModelPart* p,unsigned* g){
    const unsigned s=2166136261U;unsigned h=s;
    h=fv(h,p->model);h=fv(h,p->info);h=fv(h,p->part);h=fv(h,p->positions);h=fv(h,p->normals);
    h=fv(h,p->uv);h=fv(h,p->stream);h=fv(h,p->position_count);h=fv(h,p->normal_count);
    h=fv(h,p->position_stride);h=fv(h,p->stream_bytes);h=fv(h,p->shift);h=fv(h,p->flags);
    h=fv(h,p->cull);h=fv(h,p->blend);h=fv(h,p->depth_mode);h=fv(h,p->material_flags);
    h=fv(h,p->colors);h=fv(h,p->normal_stride);h=fv(h,p->normal_shift);g[0]=fv(h,p->static_geometry);
    g[1]=fnv(s,p->modelview,sizeof(p->modelview));
    g[2]=fnv(fnv(s,p->projection,sizeof(p->projection)),p->viewport,sizeof(p->viewport));
    h=fimg(s,p->image);h=fv(h,p->uv_offset[0]);h=fv(h,p->uv_offset[1]);h=fv(h,p->wrap_s);g[3]=fv(h,p->wrap_t);
    g[4]=fv(s,p->alpha_state);
    h=fimg(s,p->mask);h=fv(h,p->mask_ref);g[5]=fv(h,p->mask_same_uv);
    h=fv(s,p->serial);h=fv(h,p->world);h=fv(h,p->view);g[6]=fnv(h,p->source_key,sizeof(p->source_key));
    g[7]=p->lighting?fnv(s,p->lighting,sizeof(*p->lighting)):0;
}
int front_verify_part(const Re4dcModelPart* p){
    if(!front_mode)return 0;
    unsigned g[kFrontGroups];front_hash_part(p,g);
    if(front_mode==1){
        if(front_n<kFrontParts)memcpy(front_hash[front_n],g,sizeof(g));
        ++front_n;return 0;
    }
    const unsigned k=front_k++;++front_parts;
    unsigned bad=k<front_n && k<kFrontParts?0U:0x100U;
    for(unsigned i=0;!bad && i<kFrontGroups;++i)if(g[i]!=front_hash[k][i]){bad|=1U<<i;++front_group_bad[i];}
    if(bad){
        ++front_bad_parts;front_model_bad=1;
        if(front_logged<24){++front_logged;
            re4dc_log("front_native: MISMATCH frame=%u model=%p info=%p part=%p k=%u groups=0x%x\n",
                      pG->Frame_cnt,p->model,p->info,p->part,k,bad);}
    }
    return 1;
}
}
extern "C" void re4dc_front_verify(int mode){
    if(mode==1)front_n=0;
    else if(mode==2){front_k=0;front_model_bad=0;}
    else if(front_mode==2){
        ++front_models;
        if(front_k!=front_n){front_model_bad=1;
            if(front_logged<24){++front_logged;re4dc_log("front_native: COUNT frame=%u source=%u native=%u\n",pG->Frame_cnt,front_n,front_k);}}
        front_bad_models+=front_model_bad;
        const unsigned block=pG->Frame_cnt/600;
        if(block!=front_block){front_block=block;
            re4dc_log("front_native: frame=%u models=%u parts=%u bad_models=%u bad_parts=%u groups=%u,%u,%u,%u,%u,%u,%u,%u\n",
                pG->Frame_cnt,front_models,front_parts,front_bad_models,front_bad_parts,front_group_bad[0],front_group_bad[1],
                front_group_bad[2],front_group_bad[3],front_group_bad[4],front_group_bad[5],front_group_bad[6],front_group_bad[7]);}
    }
    front_mode=(unsigned)mode;
}
#endif
extern "C" void re4dc_draw_model_part(const void* model,const void* info_ptr,
 const void* part_ptr,const float mv[3][4],unsigned pass){
    if(!re4dc_model_diagnostic_enabled() || pass)return;
#if RE4DC_NATIVE_ACTOR
    bind_actor_frame();
#endif
    auto* m=(const cModel*)model;auto* info=(const cModelInfo*)info_ptr;
    auto* part=(const ModelPart*)part_ptr;const auto* d=info->pData;
    Re4dcModelPart p{};p.model=m;p.info=info;p.part=part;
    const bool rigid=(m->be_flag&0x4000) ||
      (d->weight_palette_num<=1 && d->weight_ext_num<=0xff && !(info->be_flag&2) && d->nParts==1);
    p.positions=(const unsigned char*)(rigid?d->vtxOrig:info->pPosBuf[pG->vtx_buf_no]);
    p.normals=(const unsigned char*)(rigid?d->nrmOrig:info->pNrmBuf[pG->vtx_buf_no]);
    p.position_stride=rigid?8:6;p.position_count=d->nVtx;p.normal_count=d->nNrm;
    p.uv=(const unsigned char*)d->pTex;p.stream=(const unsigned char*)part+32;p.stream_bytes=part->size;
    p.shift=d->shift;p.flags=d->flags;p.material_flags=part->flags;
    p.cull=re4dc_model_cull(m->CullMode,(pG->Debug_flg[0]&0x20000000)!=0);
    p.blend=info->blend_mode;p.depth_mode=m->z_mode;
    memcpy(p.modelview,mv,sizeof(p.modelview));GXGetProjectionv(p.projection);GXGetViewportv(p.viewport);
#if RE4DC_NATIVE_FOG
    // Fog as the source set it for this draw (effects/filters/thermal turn it
    // off temporarily) rides in the spare source_key[2] byte, so the part
    // layout (and the deferral queue's word diffs) is unchanged; the
    // fog-derived View far plane (light.cpp setFog) is global frame state.
    p.source_key[2]=(unsigned char)re4dc_fog_enabled();re4dc_fog_note_far(View._zfar);
#endif
    p.colors=(const unsigned char*)d->pClr;p.alpha_state=re4dc_gx_model_alpha();
    p.image=selected;p.uv_offset[0]=scroll_u;p.uv_offset[1]=scroll_v;p.wrap_s=wrap_s;p.wrap_t=wrap_t;
#if RE4DC_D349_RENDERER_STACK
    p.mask=mask;p.mask_ref=mask_ref;p.mask_same_uv=mask_same_uv;
#if RE4DC_BRIDGE_LEAN
    // Borrow the live GX state for this synchronous submit (no 0.5 KiB zero +
    // copy per part); nothing changes it before re4dc_model_submit returns and
    // the translucent queue still snapshots its own copy.
    p.lighting=re4dc_gx_model_lighting_ref();
#else
    re4dc::render::SourceLighting lighting;
    re4dc_gx_model_lighting(&lighting);p.lighting=&lighting;
#endif
    const bool nrm8=(d->flags&0x20000000U)!=0;
    p.static_geometry=rigid && m->kindid==2 && !d->shapeOfs && !(info->be_flag&2);
    p.normal_stride=nrm8?(rigid?4:3):(rigid?8:6);p.normal_shift=nrm8?6:14;
#endif
#if RE4DC_NATIVE_STATIC && !RE4DC_NATIVE_MESH
    // Single-node static scroll objects only: a multi-node part's own matrix is
    // not represented by the object-level placement the package was baked at.
    // Every other part keeps these words at their defaults, because translucent
    // parts are queued as word differences in a bounded deferral queue (D367).
    if(p.static_geometry && m->nParts<=1){
        p.serial=m->serial;p.world=&m->mat[0][0];p.view=&pG->Cam.v_mat[0][0];
        p.source_key[0]=part->texId;p.source_key[1]=(part->flags&4)?part->alphaTex:0xff;
    }
#endif
#if RE4DC_FRONT_NATIVE>=2
    if(front_verify_part(&p))return;  // native replay: compared, not drawn
#endif
    re4dc_model_submit(&p);
}
