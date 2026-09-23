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
#if RE4DC_NATIVE_STATIC
// D367 diagnostic: what occupies the room heap when the room first draws.
// OSAlloc cells tile the heap; a mem_alloc block ends with "\0MAD" + file(line).
static void heap4_census(){
    struct Row { const char* tag; unsigned bytes, count; } rows[40];
    unsigned n=0,other=0,other_cells=0,total=0;
    unsigned a=(Heap[4].start+31U)&~31U;const unsigned end=Heap[4].end;
    while(a+0x20U<=end){
        const int size=reinterpret_cast<const OSHeapCell*>(a)->size;
        if(size<0x20 || (size&31) || a+unsigned(size)>end){re4dc_log("heap4 census: stop at %08x size=%d\n",a,size);break;}
        const auto* t=reinterpret_cast<const unsigned char*>(a+unsigned(size)-0x20U);
        if(size>=0x40 && !t[0] && t[1]=='M' && t[2]=='A' && t[3]=='D'){
            const char* tag=reinterpret_cast<const char*>(t+4);unsigned r=0;
            while(r<n && strcmp(rows[r].tag,tag))++r;
            if(r==n && n<40)rows[n++]={tag,0,0};
            if(r<n){rows[r].bytes+=unsigned(size);++rows[r].count;}else{other+=unsigned(size);++other_cells;}
        }else{other+=unsigned(size);++other_cells;}
        total+=unsigned(size);a+=unsigned(size);
    }
    for(unsigned i=0;i<n;++i)for(unsigned j=i+1;j<n;++j)if(rows[j].bytes>rows[i].bytes){Row x=rows[i];rows[i]=rows[j];rows[j]=x;}
    re4dc_log("heap4 census: span=%u walked=%u free=%d untagged_or_free=%u cells=%u tags=%u\n",
        end-Heap[4].start,total,OSCheckHeap(Heap[4].handle),other,other_cells,n);
    for(unsigned i=0;i<n;++i)re4dc_log("heap4 census: %7u B x%-3u %s\n",rows[i].bytes,rows[i].count,rows[i].tag);
}
#endif
extern "C" void* re4dc_model_retained_storage(unsigned* bytes){
    *bytes=0;
#if RE4DC_D349_RENDERER_STACK
    if(!preparation_owner || MemGetCurrentHeap()!=4 || !memCheckHeapActive(4))return nullptr;
    if(!preparation_attempted){
        preparation_attempted=true;
#if RE4DC_NATIVE_STATIC
        heap4_census();
#endif
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

// Native static packages share heap 4 and the retained preparation's reserve
// policy: never below 80 KiB left for the source. Opened at the first bind of
// their owner, which precedes the lazy retained allocation at first draw.
#if RE4DC_NATIVE_STATIC
#include "native_static.h"
extern "C" int re4dc_static_heap_free(){
    return memCheckHeapActive(4)?OSCheckHeap(Heap[4].handle):-1;
}
extern "C" void* re4dc_static_alloc(unsigned bytes){
    const int before=re4dc_static_heap_free();
    if(before<int(bytes+kAllocationOverhead+kSourceReserve)){
        re4dc_log("native static: reject bytes=%u heap4_free=%d reserve=%u\n",bytes,before,kSourceReserve);
        return nullptr;
    }
    return mem_alloc(bytes,"native static package",0,0,4);
}
extern "C" void re4dc_static_free(void* data){if(data)Mem_free_h(data,4);}
#endif
