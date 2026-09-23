// Source ID layout/animation/ordering -> existing native texture/PVR mechanisms.
#include "light.h"
#include "id_sys.h"
#include "texture.h"
#include "camera.h"
#include "main_mem.h"
#include "gx.h"
#include "native_ui.h"
extern "C" void GXGetProjectionv(float*);
extern "C" void GXGetViewportv(float*);
extern "C" void GXProject(float,float,float,const float[3][4],const float*,const float*,float*,float*,float*);

extern "C" int OSCheckHeap(int);
extern "C" int re4dc_ui_heap_free() { return OSCheckHeap(Heap[MemGetCurrentHeap()].handle); }

extern "C" void* re4dc_ui_stage_alloc(unsigned bytes) {
    return mem_alloc(bytes, "native UI texture staging", 0, 1, MEM_HEAP_CURRENT);
}
extern "C" void re4dc_ui_stage_free(void* data) { Mem_free(data); }

extern "C" void re4dc_draw_id_quad(const IdUnit* u) {
    TexWk* wk = IdGetTexWk(u->texId, 1);
    if (!wk || !wk->pTpl || u->texNo >= wk->pTpl->numDescriptors) return;
    const TEXDescriptor* descriptor = TEXGet(wk->pTpl, u->texNo);
    const TEXHeader* tex = descriptor->textureHeader;
    Re4dcUiQuad q = {};
    q.image.pixels = tex->data;
    q.image.width = tex->width; q.image.height = tex->height;
    q.image.format = tex->format; q.image.palette_format = 0xffffffffU;
    if (descriptor->CLUTHeader) {
        q.image.palette = descriptor->CLUTHeader->data;
        q.image.palette_format = descriptor->CLUTHeader->format;
        q.image.palette_bytes = descriptor->CLUTHeader->numEntries * 2;
    }
    CameraCurrentProjection();
    Mtx model;
    PSMTXConcat(IDSystem::m_scrn_mat, u->mat, model);
    float projection[7], viewport[6];
    GXGetProjectionv(projection); GXGetViewportv(viewport);
    for (unsigned i=0; i<4; ++i) {
        float x,y,z;
        GXProject(u->vtx[i].x, u->vtx[i].y, u->vtx[i].z, model,
                  projection, viewport, &x, &y, &z);
        q.xy[2*i] = x * 640.0f / viewport[2];
        q.xy[2*i+1] = y * 480.0f / viewport[3];
    }
    const float uv[8]={u->u0,u->v0,u->u1,u->v0,u->u1,u->v1,u->u0,u->v1};
    for(unsigned i=0;i<8;++i) q.uv[i]=uv[i];
    q.color=((unsigned)(u8)u->col[3]<<24)|((unsigned)(u8)u->col[0]<<16)|
            ((unsigned)(u8)u->col[1]<<8)|(u8)u->col[2];
    q.blend=u->blend_type; q.masked=u->tex_flag & 1;
    re4dc_ui_submit(&q);
}

#include "global.h"
#include "player.h"
#include "native_render_profile.hpp"
#include <string.h>
extern "C" void re4dc_profile_source(re4dc::profile::Source* out){
    *out={};if(!pG)return;
    out->tick=pG->Frame_cnt;out->system=pG->System_flg;out->stop=pG->Stop_flg;
    out->room=(unsigned(pG->stage_no)<<8)|pG->room_no;
    memcpy(out->room_flags,pG->Room_flg,sizeof(out->room_flags));memcpy(out->status,pG->Status_flg,sizeof(out->status));
    memcpy(out->camera,&pG->Cam.param,sizeof(out->camera));
    if(pPL){memcpy(out->player,&pPL->pos,12);memcpy(out->player+3,&pPL->ang,12);
        out->motion_frame=pPL->Motion.Mot_frame;out->motion_state=pPL->Motion.Mot_state;}
}

extern "C" unsigned re4dc_fixture_source_frame(){ return pG ? pG->Frame_cnt : 0; }

#include "native_model.h"
#include "re4dc_platform.h"
namespace {
void* preparation_owner=nullptr;
void* retained_preparation=nullptr;
bool preparation_attempted=false;
constexpr unsigned kRetainedBytes=131072;
// D360 frees147232 bytes without shrinking game capacity. Charge the complete
// new cell (payload + OS header + MAD tag), and leave >=80KiB for source use.
constexpr unsigned kSourceReserve=81920,kAllocationOverhead=64;
}
extern "C" void re4dc_model_preparation_owner(void* owner){
#if RE4DC_D349_RENDERER_STACK
    if(preparation_owner==owner)return;
    re4dc_model_detach_retained_storage();
    if(retained_preparation)Mem_free_h(retained_preparation,4);
    retained_preparation=nullptr;preparation_owner=owner;preparation_attempted=false;
#endif
}
extern "C" void* re4dc_model_retained_storage(unsigned* bytes){
    *bytes=0;
#if RE4DC_D349_RENDERER_STACK
    if(!preparation_owner || MemGetCurrentHeap()!=4 || !memCheckHeapActive(4))return nullptr;
    if(!preparation_attempted){
        preparation_attempted=true;
        const int before=OSCheckHeap(Heap[4].handle);
        if(before>=int(kRetainedBytes+kAllocationOverhead+kSourceReserve))
            retained_preparation=mem_calloc(kRetainedBytes,"native model preparation",0,0,4);
        re4dc_log("native model preparation: bytes=%u source_free=%d->%d owner=%p reserve=%u\n",
            retained_preparation?kRetainedBytes:0,before,OSCheckHeap(Heap[4].handle),preparation_owner,kSourceReserve);
    }
    if(retained_preparation)*bytes=kRetainedBytes;
    return retained_preparation;
#else
    return nullptr;
#endif
}
