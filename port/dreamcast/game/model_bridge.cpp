// Recovered commonModelTrans -> existing native frame/packet/texture owner.
// Diagnostic base-material connection; not full GX lighting/TEV emulation.
#include "light.h"
#include "global.h"
#include "model.h"
#include "gx.h"
#include "native_model.h"
#include <stddef.h>
#include <string.h>
static_assert(sizeof(ModelPart)==0x20 && offsetof(ModelPart,size)==0x18);
static_assert(offsetof(ModelData,pParts)==0x1c && offsetof(ModelData,nVtx)==0x38);
static_assert(sizeof(void*)==4 && sizeof(GXTexObj)==32);
extern "C" void GXGetProjectionv(float*);
extern "C" void GXGetViewportv(float*);
namespace {
Re4dcUiImage selected{},mask{};
unsigned mask_ref=256,mask_same_uv;
unsigned wrap_s,wrap_t;
float scroll_u,scroll_v;
}
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
extern "C" void re4dc_draw_model_part(const void* model,const void* info_ptr,
 const void* part_ptr,const float mv[3][4],unsigned pass){
    if(!re4dc_model_diagnostic_enabled() || pass)return;
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
    p.colors=(const unsigned char*)d->pClr;p.alpha_state=re4dc_gx_model_alpha();
    p.image=selected;p.uv_offset[0]=scroll_u;p.uv_offset[1]=scroll_v;p.wrap_s=wrap_s;p.wrap_t=wrap_t;
#if RE4DC_D349_RENDERER_STACK
    p.mask=mask;p.mask_ref=mask_ref;p.mask_same_uv=mask_same_uv;
    re4dc::render::SourceLighting lighting;
    re4dc_gx_model_lighting(&lighting);p.lighting=&lighting;
    const bool nrm8=(d->flags&0x20000000U)!=0;
    p.static_geometry=rigid && m->kindid==2 && !d->shapeOfs && !(info->be_flag&2);
    p.normal_stride=nrm8?(rigid?4:3):(rigid?8:6);p.normal_shift=nrm8?6:14;
#endif
    re4dc_model_submit(&p);
}
