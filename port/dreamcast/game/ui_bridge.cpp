// Source ID layout/animation/ordering -> existing native texture/PVR mechanisms.
#include "light.h"
#include "id_sys.h"
#include "texture.h"
#include "camera.h"
#include "main_mem.h"
#include "gx.h"
#include "native_ui.h"
#if RE4DC_NATIVE_STATIC && RE4DC_NATIVE_PKG_HIGH
#include "re4dc_platform.h"
#endif
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
#include <stdio.h>
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

// Controller context for platform/pad.cpp (reads last frame's state, writes nothing):
// 1 LOOK while CameraQuasiFPS::calcDepressionRatio takes Key.substick (player free
// movement: routine 1 idle / walk / back / run / turn / 180 turn / crouch, not aiming),
// 2 ZOOM while the scope (Status_flg[0] 0x40, CameraScope) or binocular (0x400,
// CameraBinocular) camera zooms on the C-stick Y, 0 NATIVE otherwise. The title never
// reads as play: every return to it goes through systemRestartInit, which clears Rno0.
#if RE4DC_W11_FIXTURE
extern "C" void re4dc_w11_frame();
#endif
extern "C" int re4dc_pad_context(){
#if RE4DC_W11_FIXTURE
    re4dc_w11_frame();                                  // W11 test instrumentation (sscrn_bridge.cpp)
#endif
    if(!pG||!pPL||pG->Rno0!=3)return 0;             // gameMainLoop only (not options / door demo / ending)
    unsigned s0=pG->Status_flg[0];
    if(!(s0&0x02000000))return 0;                    // sub screen open or look-down camera (arm bit cleared)
    if(s0&0x400)return 2;                            // binoculars read Joy[0] directly, even under KeyStop
    if(pG->Stop_flg&0x80000000)return 0;             // KeyStop: events, messages, QTEs
    if(s0&0x40)return 2;                             // scope: CameraScope zooms while R (Key 0x10) is held
    if(s0&0x8000)return 0;                           // other first-person views
    if(pPL->hp<=0||pPL->r_no_0!=0)return 0;
    switch(pPL->r_no_1){case 0:case 1:case 2:case 3:case 4:case 5:case 0x11:return 1;}
    return 0;
}

// Which source debug chords would fire now (platform/pad.cpp masks them unless RE4DC_DEBUG_PAD):
// 1 gameDebug's L+START debug menu (game.cpp: Debug_flg[0] bit 31 clear), 2 the sub screen is
// open in a type whose raw Joy Z toggles the item-make / puzzle debug menus (all but the
// Z-opened map, SS_OPEN_MAP, where Z closes the map).
#include "sscrn.h"
extern "C" int re4dc_pad_debug_state(){
    if(!pG)return 0;
    int s=(s32)pG->Debug_flg[0]>=0?1:0;
    if(SubScreenWk.type!=0&&SubScreenWk.type!=SS_OPEN_MAP)s|=2;
    return s;
}

// ---------------------------------------------------------------- room lifecycle
// Order of a room change (src/game): gameDoordemo -> gameStageInit -> StageSet
// [re4dc_room_leave; reload: MemReplaceHeap(1,2); relink: stopRelData,
// MemReplaceHeap(2,3), linkRelData] -> gameRoomInit -> gameRoomMemInit
// [retire hooks again (idempotent), MemReplaceHeap(3,4), re4dc_room_enter].
// One audit line per phase, compared by the capture tooling across round
// trips: enter (heap 4 just rebuilt), steady (a fixed frame count into the
// room) and leave (native owners retired, before any heap is replaced).
#include "room_data.h"
#include "sce_sys.h"
#include "game.h"
#include "native_motion.h"
#include "native_effect.h"
#include "re4dc_platform.h"
extern "C" void re4dc_kos_heap_state(unsigned* free_chunks,unsigned* used,unsigned* break_room);
extern "C" unsigned re4dc_vram_free();
extern "C" int re4dc_fixture_read(const char* path,char* buffer,unsigned size);
extern "C" void re4dc_aram_state(unsigned long* stack_pointer,unsigned long* free_blocks);
extern "C" void re4dc_module_counts(unsigned* fresh,unsigned* restarts,unsigned* unlinks,unsigned* linked);
extern "C" void re4dc_os_thread_stats(unsigned* registered,unsigned* reaped,unsigned* pending);
extern "C" void re4dc_room4_open();
extern "C" void re4dc_room4_close();
extern "C" int re4dc_room4_state(unsigned* generation,unsigned* cells,unsigned* bytes,unsigned* stale,unsigned* refused);
namespace {
struct AuditValues { int heap4_free; unsigned vram_free,kos_free,kos_break; bool valid; };
AuditValues last_audit[3];         // enter, steady, leave
const char* const kPhase[3]={"enter","steady","leave"};
unsigned room_frames;              // gameMainLoop frames since the room was entered
bool steady_logged;
void audit(int phase){
    unsigned kos_free=0,kos_used=0,kos_break=0,fresh=0,restarts=0,unlinks=0,linked=0,threads=0,reaped=0,pending=0;
    unsigned generation=0,cells=0,cell_bytes=0,stale=0,refused=0;
    unsigned long aram_sp=0,aram_blocks=0;
    re4dc_kos_heap_state(&kos_free,&kos_used,&kos_break);
    re4dc_aram_state(&aram_sp,&aram_blocks);
    re4dc_module_counts(&fresh,&restarts,&unlinks,&linked);
    re4dc_os_thread_stats(&threads,&reaped,&pending);
    re4dc_room4_state(&generation,&cells,&cell_bytes,&stale,&refused);
    const unsigned vram=re4dc_vram_free();
    // Every existing source heap must pass the SDK's own consistency walk.
    char bad[16]="";unsigned nbad=0;
    for(int h=0;h<MEM_HEAP_NUM;++h){
        if(Heap[h].handle<0 || Heap[h].status)continue;
        if(OSCheckHeap(Heap[h].handle)<0 && nbad<8){bad[nbad++]=char(h<10?'0'+h:'a'+h-10);bad[nbad]=0;}
    }
    const int heap4=Heap[4].handle>=0?OSCheckHeap(Heap[4].handle):-2;
    // Two lines: re4dc_log formats into 256 bytes.
    re4dc_log("room lifecycle: phase=%s room=%03x generation=%u frames=%u heap4=%08x-%08x size=%u free=%d "
        "heap_check=%s%s native4=%u/%u stale=%u refused=%u\n",
        kPhase[phase],unsigned(pG?pG->room_id:0),generation,room_frames,Heap[4].start,Heap[4].end,
        Heap[4].end-Heap[4].start,heap4,nbad?"bad:":"ok",bad,cells,cell_bytes,stale,refused);
    re4dc_log("room lifecycle: phase=%s vram_free=%u kos_free=%u kos_used=%u kos_break=%u aram_sp=%lx "
        "aram_blocks=%lu modules=%u/%u/%u/%u threads=%u/%u/%u heap=%d\n",
        kPhase[phase],vram,kos_free,kos_used,kos_break,aram_sp,aram_blocks,fresh,restarts,unlinks,linked,
        threads,reaped,pending,int(MemGetCurrentHeap()));
    AuditValues& previous=last_audit[phase];
    const AuditValues now{heap4,vram,kos_free,kos_break,true};
    if(previous.valid)
        re4dc_log("room lifecycle: phase=%s drift heap4=%d vram=%d kos=%d\n",kPhase[phase],
            now.heap4_free-previous.heap4_free,int(now.vram_free-previous.vram_free),
            int(now.kos_free+now.kos_break)-int(previous.kos_free+previous.kos_break));
    previous=now;
    // KOS malloc has only a few KB left once the source arena is carved;
    // thread records, file handles and texture metadata come out of it.
    if(kos_free+kos_break<1024)re4dc_log("room lifecycle: WARNING KOS headroom %u < 1024\n",kos_free+kos_break);
}
}

#if RE4DC_IO_PROBE
// IO_PROBE: room-entry telemetry for the room cycle fixture. At the door request the DVD
// blocking counters (dvd.cpp), the motion-key wait total (native_motion.cpp) and, with
// DISC_ASYNC, the disc service counters are reset. On the first in-room frame one "iotime:"
// line reports the wall time and game frames of the transition, the time the game spent
// blocked in source DVD reads and in motion-key reads, and the bytes; the rest of the wall
// time is CPU. After 240 in-room frames a second line reports the same for steady play.
#include <kos/timer.h>
extern "C" void re4dc_dvd_block_stats(unsigned* n, unsigned long long* total_us, unsigned* worst_us, int reset);
extern "C" unsigned long long re4dc_motion_wait_total_us;
extern "C" unsigned re4dc_ui_frame();
extern "C" void re4dc_iowrap_reset(void);                          // io_wrap.cpp
extern "C" void re4dc_iowrap_report(const char* what, unsigned cycle);
#include "native_motion.h"
namespace {
struct IoCycle { unsigned no; const char* mode; unsigned long long t0, t_enter; unsigned f0; bool pending, steady; Re4dcMotionStats m0; unsigned uf0; };
IoCycle io_cycle{};
void io_reset(){
    unsigned a,b;unsigned long long t;
    re4dc_dvd_block_stats(&a,&t,&b,1);
    re4dc_motion_wait_total_us=0;
    re4dc_motion_get_stats(&io_cycle.m0);
    io_cycle.uf0=re4dc_ui_frame();
    re4dc_iowrap_reset();
}
void io_report(const char* what,unsigned long long wall){
    unsigned bn,bw;unsigned long long bt;
    re4dc_dvd_block_stats(&bn,&bt,&bw,1);
    Re4dcMotionStats m;re4dc_motion_get_stats(&m);
    re4dc_log("iotime: %s cycle=%u mode=%s wall_us=%llu enter_us=%llu game_frames=%u dvd_block n=%u total_us=%llu "
              "worst_us=%u motion loads=%u kb=%llu wait_us=%llu worst_wait_us=%llu ui_frames=%u-%u\n",what,io_cycle.no,io_cycle.mode,wall,
              io_cycle.t_enter>io_cycle.t0?io_cycle.t_enter-io_cycle.t0:0ULL,unsigned(pG->Frame_cnt-io_cycle.f0),bn,bt,bw,
              m.loads-io_cycle.m0.loads,(m.bytes_read-io_cycle.m0.bytes_read)/1024,re4dc_motion_wait_total_us,m.worst_wait_us,io_cycle.uf0,re4dc_ui_frame());
    re4dc_iowrap_report(what,io_cycle.no);
    io_reset();
}
void io_cycle_begin(unsigned no,const char* mode){
    io_cycle.no=no;io_cycle.mode=mode;io_cycle.t0=timer_us_gettime64();io_cycle.t_enter=0;
    io_cycle.f0=unsigned(pG->Frame_cnt);io_cycle.pending=true;io_cycle.steady=false;
    io_reset();
}
void io_cycle_enter(){ if(io_cycle.pending && !io_cycle.t_enter)io_cycle.t_enter=timer_us_gettime64(); }
void io_cycle_frame(unsigned frames_in_room){
    if(!io_cycle.pending)return;
    if(frames_in_room==1){
        const unsigned long long t=timer_us_gettime64();
        io_report("door",t>io_cycle.t0?t-io_cycle.t0:0ULL);
        io_cycle.t0=timer_us_gettime64();io_cycle.t_enter=0;io_cycle.f0=unsigned(pG->Frame_cnt);io_cycle.steady=true;
    } else if(io_cycle.steady && frames_in_room==241){
        const unsigned long long t=timer_us_gettime64();
        io_report("steady",t>io_cycle.t0?t-io_cycle.t0:0ULL);
        io_cycle.pending=false;
    }
}
}
#endif
// StageSet entry (src/game/stage.cpp): the old room is over and every heap
// is still in place. Idempotent; gameRoomMemInit retires again for the paths
// that do not pass through StageSet (ending) and for the first room.
extern "C" void re4dc_room_leave(){
    unsigned generation,cells,bytes,stale,refused;
    if(!re4dc_room4_state(&generation,&cells,&bytes,&stale,&refused))return;
    re4dc_motion_retire_all();
    re4dc_effect_retire_room();
    re4dc_ui_retire_room();
    re4dc_room4_close();
    audit(2);
    re4dc_room4_state(&generation,&cells,&bytes,&stale,&refused);
    if(cells)re4dc_log("room lifecycle: %u native heap-4 cells (%u B) outlived retirement\n",cells,bytes);
}

// gameRoomMemInit after the source replaced heap 4: a new room heap exists.
#if RE4DC_QUALITY
extern "C" void re4dc_quality_freeze(const char* where);
#endif
#if RE4DC_VMU_DEBUG_SLOT
extern "C" void re4dc_dbgslot_room_enter();
extern "C" void re4dc_dbgslot_poll(unsigned generation, unsigned room_frames);
#endif
#if RE4DC_DBG_WARP
extern "C" void re4dc_warp_room_enter(void);
extern "C" void re4dc_warp_poll(void);
#endif
extern "C" void re4dc_room_enter(){
#if RE4DC_QUALITY
    re4dc_quality_freeze("room");
#endif
#if RE4DC_IO_PROBE
    io_cycle_enter();
#endif
#if RE4DC_VMU_DEBUG_SLOT
    re4dc_dbgslot_room_enter();                         // ring entry; FILE 20 start (dbgslot_bridge.cpp)
#endif
#if RE4DC_DBG_WARP
    re4dc_warp_room_enter();                            // test warp rig: flags at the first entry
#endif
    re4dc_room4_open();
    room_frames=0;steady_logged=false;
    audit(0);
}

// ---------------------------------------------------------------- room cycle fixture
// /cd/dc/roomcycle.txt "<mode> <count> <frames>": after <frames> gameMainLoop
// frames in a room (no event holding the game), leave through the source door
// demo into the same room at the same point, <count> times. Test only: absent
// file, no effect. Modes select the source path StageSet takes:
//   door    same room REL, heap 4 rebuilt in place;
//   relink  the room REL is relinked (RoomData.m_RelNo cleared, the r100->r101
//           path: MemReplaceHeap(2,3) over the live heap 4, fresh OSLink);
//   reload  the source continue (GameContinue(1): the save gameStageInit
//           wrote, System_flg 0x80000): stage heap 2, heap 3 and the REL are
//           all rebuilt.
namespace {
struct CycleFixture { bool loaded; int mode; unsigned count,frames,done; Vec pos; float y; unsigned char point; bool anchored; };
CycleFixture cycle{};
const char* const kCycleMode[3]={"door","relink","reload"};
void load_cycle(){
    cycle.loaded=true;
    char text[64]={};
    if(re4dc_fixture_read("/cd/dc/roomcycle.txt",text,sizeof(text)-1)<=0)return;
    char mode[16]={};unsigned count=0,frames=0;
    if(sscanf(text,"%15s %u %u",mode,&count,&frames)!=3)return;
    for(int i=0;i<3;++i)if(!strcmp(mode,kCycleMode[i]))cycle.mode=i+1;
    if(!cycle.mode)return;
    cycle.count=count;cycle.frames=frames;
    re4dc_log("room cycle: fixture mode=%s count=%u frames=%u\n",mode,count,frames);
}
}

// Top of gameMainLoop (Rno0 == 3). 1 = the door demo was requested.
#if RE4DC_W11_FIXTURE
extern "C" int re4dc_w11_room_poll(unsigned generation);
#endif
extern "C" int re4dc_room_cycle_poll(){
    unsigned generation,cells,bytes,stale,refused;
    if(!re4dc_room4_state(&generation,&cells,&bytes,&stale,&refused))return 0;
#if RE4DC_W11_FIXTURE
    re4dc_w11_room_poll(generation);                    // death / life fixture (sscrn_bridge.cpp)
#endif
    ++room_frames;
#if RE4DC_DBG_WARP
    re4dc_warp_poll();                                  // test warp rig: placement log, area dump
#endif
#if RE4DC_VMU_DEBUG_SLOT
    re4dc_dbgslot_poll(generation, room_frames);        // L+START debug save (dbgslot_bridge.cpp)
#endif
#if RE4DC_IO_PROBE
    io_cycle_frame(room_frames);
#endif
    if(!cycle.loaded)load_cycle();
    if(!cycle.mode || !pPL || (pG->Status_flg[1]&0x10000000))return 0;
    if(room_frames<cycle.frames)return 0;
    if(!steady_logged){steady_logged=true;audit(1);}
    if(cycle.done>=cycle.count)return 0;
    if(!cycle.anchored){
        // Every round trip re-enters where the first one left.
        cycle.anchored=true;cycle.pos=pPL->pos;cycle.y=pPL->ang.y;cycle.point=pG->Part;
    }
    ++cycle.done;
#if RE4DC_IO_PROBE
    io_cycle_begin(cycle.done,kCycleMode[cycle.mode-1]);
#endif
    if(cycle.mode==3){
        re4dc_log("room cycle: reload %u/%u room=%03x via GameContinue\n",cycle.done,cycle.count,unsigned(pG->room_id));
        GameContinue(1);
        return 1;
    }
    re4dc_log("room cycle: %s %u/%u room=%03x at (%d,%d,%d)\n",kCycleMode[cycle.mode-1],cycle.done,cycle.count,
        unsigned(pG->room_id),int(cycle.pos.x),int(cycle.pos.y),int(cycle.pos.z));
    pG->room_id_prev=pG->room_id;pG->Part_old=pG->Part;
    pG->next_room=pG->room_id;pG->next_point=cycle.point;
    pG->NextPos=cycle.pos;pG->NextY=cycle.y;
    if(cycle.mode==2)RoomData.m_RelNo=0;
    SceSys.m_door_fade_eff=2;
    pG->Rno0=4;pG->Rno1=0;pG->Rno2=0;pG->Rno3=0;
    return 1;
}

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

// ---------------------------------------------------------------- room heap-4 cells
#include <cstdint>
// Native owners that borrow the source room heap (heap 4). The source rebuilds
// heap 4 wholesale at every room change, and on a stage reload or room-REL
// relink StageSet recreates heaps 2/3 over the live heap 4 range first
// (MemReplaceHeap(1,2)/(2,3)) before gameRoomMemInit replaces heap 4. Native
// room owners therefore retire at StageSet entry, while heap 4 is intact (the
// room lifecycle above), and every native heap-4 cell carries the heap-4
// generation it came from: a free after the rebuild is dropped (the cell went
// with the old heap) instead of being threaded into whatever heap now covers
// that address. Frees name heap 4's handle; Mem_free_h frees to the OS
// current heap, which is heap 3 while StageSet links the next room's REL.
extern "C" void OSFreeToHeap(int,void*);
namespace {
struct alignas(32) Room4Cell { unsigned magic,generation,bytes,reserved[5]; };
static_assert(sizeof(Room4Cell)==32);
constexpr unsigned kRoom4Magic=0x57364834; // "W6H4"
struct Room4 {
    bool live;                     // a room heap 4 exists and native owners may use it
    unsigned generation;           // heap-4 rebuilds seen (gameRoomMemInit)
    unsigned live_cells,live_bytes,stale_frees,refused;
};
Room4 room4{};

void* room_alloc4(unsigned bytes,const char* tag,bool clear){
    if(!room4.live || !memCheckHeapActive(4)){
        ++room4.refused;
        re4dc_log("room lifecycle: refused %s bytes=%u outside a live room heap\n",tag,bytes);
        return nullptr;
    }
    auto* cell=static_cast<Room4Cell*>(clear?mem_calloc(bytes+sizeof(Room4Cell),tag,0,0,4)
                                           :mem_alloc(bytes+sizeof(Room4Cell),tag,0,0,4));
    if(!cell)return nullptr;
    *cell={kRoom4Magic,room4.generation,bytes,{}};
    ++room4.live_cells;room4.live_bytes+=bytes;
    return cell+1;
}
void room_free4(void* p,const char* who){
    if(!p)return;
    auto* cell=static_cast<Room4Cell*>(p)-1;
    const auto address=reinterpret_cast<std::uintptr_t>(cell);
    if(cell->magic!=kRoom4Magic || cell->generation!=room4.generation || !memCheckHeapActive(4) ||
       address<Heap[4].start || address>=Heap[4].end){
        ++room4.stale_frees;
        re4dc_log("room lifecycle: %s dropped stale heap-4 cell %p\n",who,p);
        return;
    }
    cell->magic=0;--room4.live_cells;room4.live_bytes-=cell->bytes;
    OSFreeToHeap(Heap[4].handle,cell);
}
#if RE4DC_NATIVE_STATIC && RE4DC_NATIVE_PKG_HIGH
// NATIVE_PKG_HIGH: room_alloc4 from the top of the highest free heap-4 cell that fits. The cell is
// laid out as mem_alloc's (32-byte header, payload, 32-byte MAD tag for the heap-4 census) and
// joins the allocated list as OSAllocFromHeap's does, so room_free4 / OSFreeToHeap return it.
void* room_alloc4_high(unsigned bytes,const char* tag){
    if(!room4.live || !memCheckHeapActive(4)){
        ++room4.refused;
        re4dc_log("room lifecycle: refused %s bytes=%u outside a live room heap\n",tag,bytes);
        return nullptr;
    }
    // SystemMemInit hands the aligned arena start to OSInitAlloc, which puts the descriptors there.
    auto* d=reinterpret_cast<OSHeapDescriptor*>((u32(re4dc_mem.heap)+0x1FU)&~0x1FU)+Heap[4].handle;
    const u32 payload=(bytes+sizeof(Room4Cell)+0x1FU)&~0x1FU;
    const s32 size=s32(payload+0x40U);
    OSHeapCell* best=nullptr;
    for(OSHeapCell* c=d->free;c;c=c->next)if(c->size>=size)best=c;  // address order: the last fit is highest
    if(!best)return nullptr;
    OSHeapCell* cell;
    if(best->size-size<0x40){
        if(best->prev)best->prev->next=best->next;else d->free=best->next;
        if(best->next)best->next->prev=best->prev;
        cell=best;
    }else{
        best->size-=size;
        cell=reinterpret_cast<OSHeapCell*>(reinterpret_cast<u8*>(best)+best->size);
        cell->size=size;
    }
    cell->prev=nullptr;cell->next=d->allocated;
    if(cell->next)cell->next->prev=cell;
    d->allocated=cell;
    auto* p=reinterpret_cast<u8*>(cell)+0x20;
    u8* t=p+payload;
    t[0]=0;t[1]='M';t[2]='A';t[3]='D';
    snprintf(reinterpret_cast<char*>(t)+4,0x1C,"%s(0)",tag);
    auto* rc=reinterpret_cast<Room4Cell*>(p);
    *rc={kRoom4Magic,room4.generation,bytes,{}};
    ++room4.live_cells;room4.live_bytes+=bytes;
    return rc+1;
}
#endif
}
// gameRoomMemInit rebuilt heap 4: a new generation of native cells may start.
extern "C" void re4dc_room4_open(){++room4.generation;room4.live_cells=0;room4.live_bytes=0;room4.live=true;}
// StageSet entry, after the native owners retired: no new cells until the rebuild.
extern "C" void re4dc_room4_close(){room4.live=false;}
extern "C" int re4dc_room4_state(unsigned* generation,unsigned* cells,unsigned* bytes,unsigned* stale,unsigned* refused){
    *generation=room4.generation;*cells=room4.live_cells;*bytes=room4.live_bytes;
    *stale=room4.stale_frees;*refused=room4.refused;return room4.live;
}

extern "C" void re4dc_model_preparation_owner(void* owner){
#if RE4DC_D349_RENDERER_STACK
    if(preparation_owner==owner)return;
    re4dc_model_detach_retained_storage();
    if(retained_preparation)room_free4(retained_preparation,"native model preparation");
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
        if(before>=int(kRetainedBytes+kAllocationOverhead+sizeof(Room4Cell)+kSourceReserve))
            retained_preparation=room_alloc4(kRetainedBytes,"native model preparation",true);
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
    if(before<int(bytes+kAllocationOverhead+sizeof(Room4Cell)+kSourceReserve)){
        re4dc_log("native static: reject bytes=%u heap4_free=%d reserve=%u\n",bytes,before,kSourceReserve);
        return nullptr;
    }
#if RE4DC_NATIVE_PKG_HIGH
    return room_alloc4_high(bytes,"native static package");
#else
    return room_alloc4(bytes,"native static package",false);
#endif
}
extern "C" void re4dc_static_free(void* data){room_free4(data,"native static package");}
#endif

