// Route cutscenes (PS2-inspired profile: prerecorded cinematics as presentation).
// The caller keeps its whole source sequence around the event: flags, enemy
// sets, positions, doors, ladders, SceAtDataReset. This replaces only the
// evd playback (bodies, camera, lights, messages) with the PS2 movie of the
// same event and reproduces the lasting parts of Event::ExeBeginEvt,
// Event::RunEvtCancel (skip) and Event::ExeEndEvt that outlive an event.
// None of the route evds (GC or PS2) carries SetPl/SetList/PosPl/Func packets.
#include "types.h"
#include "global.h"
#include "main.h"
#include "player.h"
#include "event.h"
#include "sce.h"
#include "snd.h"
#include "route_movie.h"
#include <string.h>
extern "C" void re4dc_log(const char* fmt, ...);

// Source Evt_*_Func handlers read only funcMode (and NowCut/NowFrame in mode 1)
// in the begin/end/cancel modes used here; no event body exists to fetch.
static void routeFunc(RouteEvtFunc func, int mode)
{
    if (func == 0) {
        return;
    }
    alignas(8) static u8 storage[sizeof(Event)];
    memset(storage, 0, sizeof(storage));
    Event* e = (Event*) storage;
    e->funcMode = mode;
    func(e);
}

int RouteMoviePlay(unsigned id, unsigned flags, RouteEvtFunc func, RouteMovieTick tick)
{
    if (!re4dc_movie_available(id)) {
        return RE4DC_MOVIE_UNHANDLED;
    }
    // Event::ExeBeginEvt: scenario event nesting, event-running status, begin func.
    SceEventStart(0);
    BitOn(pG->Status_flg[2], 0x00080000);
    BitOn(pG->Status_flg[2], 0x00010000);
    BitOff(pG->Status_flg[3], 0x01000000);
    routeFunc(func, 0);
    pG->System_flg |= 0x400;
    if (flags & ROUTE_MOVIE_SND_EVENT) {
        SndEventInit();
    }
    // cSofdec::initWork display contract: the game is hidden while the picture
    // plays and Disp_flg is restored afterwards. Stop_flg stays exactly as the
    // source event left it, so enemy/NoSuspend timing matches a real event.
    const u32 disp = pG->Disp_flg;
    pG->Disp_flg = 0xFFFFFFFF;
    // The movie owns presentation until it ends (the task does not sleep, so no
    // game frame runs); skip is the event cancel key, Key bit 29 = PAD START.
    int st = re4dc_movie_play(id, 0x1000, tick);
    pG->System_flg &= ~0x400;  // Event::Run releases the held picture after frame 0
    pG->Disp_flg = disp;
    if (st == RE4DC_MOVIE_UNHANDLED) {
        st = RE4DC_MOVIE_ERROR;  // media vanished after the check: effects still complete
    }
    if (st == RE4DC_MOVIE_SKIP) {
        // Event::RunEvtCancel: cancel marker, then the handler's cancel mode.
        pG->Status_flg[3] |= 0x01000000;
        routeFunc(func, 3);
    }
    // Event::ExeEndEvt, lasting part. No event player body existed, so the
    // player keeps its own position (the PS2 evds carry no pl0000 body).
    if (!(flags & ROUTE_MOVIE_KEEP_POSE)) {
        Vec pos = pPL->pos;
        Vec rot = pPL->ang;
        pPL->zeroPartsPosInit(&pos, &rot);
    }
    pG->Disp_flg &= ~0x800;
    routeFunc(func, 2);
    pG->System_flg |= 0x40;
    if (flags & ROUTE_MOVIE_SND_EVENT) {
        SndEventEnd();
    }
    BitOff(pG->Status_flg[2], 0x00080000);
    BitOff(pG->Status_flg[2], 0x00010000);
    SceEventEnd(0);
    re4dc_log("route cutscene: id=%05x terminal=%d skip_func=%d end_func=%d pose=%s scenario0=%08x system=%08x\n",
              id, st, st == RE4DC_MOVIE_SKIP && func != 0, func != 0,
              (flags & ROUTE_MOVIE_KEEP_POSE) ? "kept" : "zero-parts", pG->Scenario_flg[0], pG->System_flg);
    return st;
}
