// Determinism trace (LOGIC_TRACE=1 in game30.mk; never in a product image).
//
// Proves that a build or code change leaves the game logic bit-identical: once per frame-loop
// iteration (src/game/main.cpp, top of the loop, i.e. after the previous iteration's complete
// logic + render pass) it logs one fingerprint line of the logic state through the existing RAM
// log ring (re4dc_log -> re4dc_logbuf, read by the evidence read_log.py; serial on hardware).
// tools/logic_trace_diff.py compares two runs. Read-only: nothing here writes game state, and
// no pointer value is hashed (heap addresses legitimately move with the image size).
//
//   LT t=<Frame_cnt> n=<sample> r=<rng16> sy=<System_flg> sp=<Stop_flg> st=<H Status_flg[4]>
//      rf=<H Room_flg[4]> sc=<H Scenario_flg,Item_find_flg> rm=<stage<<8|room>
//      p=<player pos bits> a=<player ang bits> m=<Mot_frame bits>/<Mot_state>
//      ps=<H player discrete> pf=<H player coords> pm=<H player parts>
//   LU t=<Frame_cnt> n=<sample> e=<alive enemies> es=<H discrete> ef=<H coords> em=<H parts>
//      o=<alive objects> os=<H discrete> of=<H coords> om=<H parts> c=<H camera>
// discrete = be_flag, r_no_0..3, id/type, hp (enemies), Motion.Mot_state: sequencing / AI state.
// coords   = cCoord 0x0C..0xF4 without pParent: mat, l_mat, world, world_old(2), pos, ang, scale,
//            r_scale, prevMat, plus pos_old, speed and Motion.Mot_frame: where collision lands.
// parts    = the same coordinate block of every cParts on the model's pParts chain (world
//            matrices from partsWorldCalc: the MTXConcat/MultVec consumers).
//
// The trace also reports fixture state "room" = <stage<<8|room>/<player placed> for the pad
// script (fixtures/padscript-trace.txt), so gameplay inputs are keyed to the room anchor.
//
// RE4DC_LOGIC_TRACE_DELAY_US=N burns N microseconds per record: the timing-perturbation control.
// A run of the reference build with N > 0 must be STRICT against the same build with N = 0
// before any A/B verdict is trusted (it proves the fixture is insensitive to CPU speed).
#include "global.h"
#include "player.h"
#include "em.h"
#include "obj.h"
#include "re4dc_platform.h"
#include <string.h>

#ifndef RE4DC_LOGIC_TRACE_DELAY_US
#define RE4DC_LOGIC_TRACE_DELAY_US 0
#endif

extern "C" unsigned short re4dc_rnd_state(void);   // src/game/rnd.cpp (trace builds only)
#if RE4DC_LOGIC_TRACE_DELAY_US
#include <kos/timer.h>   // timer_us_gettime64 (static inline)
#endif

namespace {
struct Fnv {
    unsigned h = 2166136261u;
    void word(unsigned w) { h = (h ^ w) * 16777619u; }
    void words(const void* p, unsigned bytes) {
        const unsigned char* b = (const unsigned char*) p;
        for (unsigned i = 0; i + 4 <= bytes; i += 4) {
            unsigned w;
            memcpy(&w, b + i, 4);
            word(w);
        }
    }
    template <class T> void add(const T& v) {
        unsigned w = 0;
        memcpy(&w, &v, sizeof(v) < 4 ? sizeof(v) : 4);
        word(w);
    }
};
inline unsigned bits(float f) { unsigned u; memcpy(&u, &f, 4); return u; }

// cCoord 0x0C..0x6C (mat, l_mat) and 0x70..0xF4 (world .. prevMat): skips the vptr and pParent.
void coord_block(Fnv& f, const void* unit)
{
    const unsigned char* b = (const unsigned char*) unit;
    f.words(b + 0x0C, 0x6C - 0x0C);
    f.words(b + 0x70, 0xF4 - 0x70);
}

void model_state(Fnv& discrete, Fnv& coords, Fnv& parts, cModel* m)
{
    discrete.add(m->be_flag);
    discrete.add(m->stat);
    discrete.add(m->id);
    discrete.add(m->type);
    discrete.add(m->Motion.Mot_state);
    coord_block(coords, m);
    coords.words(&m->speed, sizeof(Vec) * 2);   // speed 0x104, pos_old 0x110
    coords.add(m->Motion.Mot_frame);
    unsigned n = 0;
    for (cModel* p = m->pParts; p && n < 256; p = (cModel*) ((cParts*) p)->pList, ++n)
        coord_block(parts, p);
    parts.word(n);
}

unsigned samples;

// Room digest (hardware check without a serial link, see re4dc_logic_trace_digest).
constexpr unsigned kDigestEvery = 600;
unsigned g_digRoom = ~0u, g_digTicks;
bool g_digStarted;
Fnv g_dig;
unsigned g_latchRoom, g_latchTicks, g_latchDigest;
}  // namespace

// Last latched room digest: FNV over every LT/LU field of every tick since the room anchor (the
// first tick of the current room with the player placed, the anchor logic_trace_diff.py
// --align room uses), latched every 600 anchor ticks and logged as
//   LD t=<Frame_cnt> rm=<room> k=<ticks since anchor> d=<digest>
// On a console without a serial link (GDEMU) an on-screen readout (PERF_HUD) shows the latched
// triple; equal (rm, k, d) on hardware and in Flycast under the same pad fixture means the whole
// room run was bit-identical, which checks Flycast's FPU (fmac) against the SH-4. Returns 0 until
// the first latch. Kept by --gc-sections through the shared input section.
extern "C" __attribute__((section(".text.re4dc_logic_trace"))) int re4dc_logic_trace_digest(unsigned* room,
                                                                                           unsigned* ticks,
                                                                                           unsigned* digest)
{
    if (!g_latchTicks) return 0;
    if (room) *room = g_latchRoom;
    if (ticks) *ticks = g_latchTicks;
    if (digest) *digest = g_latchDigest;
    return 1;
}

extern "C" __attribute__((section(".text.re4dc_logic_trace"))) void re4dc_logic_trace_tick(void)
{
#if RE4DC_LOGIC_TRACE_DELAY_US
    {
        const unsigned long long until = timer_us_gettime64() + RE4DC_LOGIC_TRACE_DELAY_US;
        while (timer_us_gettime64() < until) {
        }
    }
#endif
    if (!pG) return;
    ++samples;
    Fnv st, rf, sc, cam, ps, pf, pm, es, ef, em, os, of, om;
    st.words(pG->Status_flg, sizeof(pG->Status_flg));
    rf.words(pG->Room_flg, sizeof(pG->Room_flg));
    sc.words(pG->Scenario_flg, sizeof(pG->Scenario_flg));
    sc.add(pG->Item_find_flg);
    cam.words(&pG->Cam.param, 32);
    unsigned p[3] = {0, 0, 0}, a[3] = {0, 0, 0}, mf = 0, ms = 0;
    if (pPL) {
        model_state(ps, pf, pm, pPL);
        p[0] = bits(pPL->pos.x); p[1] = bits(pPL->pos.y); p[2] = bits(pPL->pos.z);
        a[0] = bits(pPL->ang.x); a[1] = bits(pPL->ang.y); a[2] = bits(pPL->ang.z);
        mf = bits(pPL->Motion.Mot_frame); ms = pPL->Motion.Mot_state;
    }
    unsigned ne = 0, no = 0;
    for (cUnit* u = (cUnit*) EmMgr.pAlive; u && ne < 1024; u = u->pNext, ++ne) {
        cEm* e = (cEm*) u;
        model_state(es, ef, em, e);
        es.add(e->hp);
    }
    for (cUnit* u = (cUnit*) ObjMgr.pAlive; u && no < 1024; u = u->pNext, ++no)
        model_state(os, of, om, (cModel*) u);
    const unsigned rng = re4dc_rnd_state();
    const unsigned room = (unsigned(pG->stage_no) << 8) | pG->room_no;
    // Fixture sync state for the scripted pad input (platform/pad.cpp "room=<id>/<player>"): lets a
    // gameplay route start at the room's first tick with the player placed, the same anchor
    // logic_trace_diff.py --align room uses, so inputs land on the same room tick in A and B
    // even when loading took a different number of frames. Platform-side only.
    re4dc_fixture_state("room", (int) room, (p[0] | p[1] | p[2]) ? 1 : 0);
    // Two lines per sample: re4dc_log formats into a 256-byte buffer and one line would be ~300
    // characters (the enemy/object/camera fields would be cut off). logic_trace_diff.py joins the
    // LT and LU halves of a sample by (t, n) and drops a sample whose other half is missing.
    re4dc_log("LT t=%u n=%u r=%04x sy=%08x sp=%08x st=%08x rf=%08x sc=%08x rm=%04x p=%08x,%08x,%08x "
              "a=%08x,%08x,%08x m=%08x/%x ps=%08x pf=%08x pm=%08x\n",
              (unsigned) pG->Frame_cnt, samples, rng, (unsigned) pG->System_flg, (unsigned) pG->Stop_flg, st.h,
              rf.h, sc.h, room, p[0], p[1], p[2], a[0], a[1], a[2], mf, ms, ps.h, pf.h, pm.h);
    re4dc_log("LU t=%u n=%u e=%u es=%08x ef=%08x em=%08x o=%u os=%08x of=%08x om=%08x c=%08x\n",
              (unsigned) pG->Frame_cnt, samples, ne, es.h, ef.h, em.h, no, os.h, of.h, om.h, cam.h);

    if (room != g_digRoom) {
        g_digRoom = room; g_digTicks = 0; g_digStarted = false; g_dig = Fnv();
    }
    if (!g_digStarted && (p[0] | p[1] | p[2])) g_digStarted = true;
    if (g_digStarted) {
        const unsigned v[] = {rng, (unsigned) pG->System_flg, (unsigned) pG->Stop_flg, st.h, rf.h, sc.h, room,
                              p[0], p[1], p[2], a[0], a[1], a[2], mf, ms, ps.h, pf.h, pm.h, ne, es.h, ef.h, em.h,
                              no, os.h, of.h, om.h, cam.h};
        for (unsigned w : v) g_dig.word(w);
        if (++g_digTicks % kDigestEvery == 0) {
            g_latchRoom = room; g_latchTicks = g_digTicks; g_latchDigest = g_dig.h;
            re4dc_log("LD t=%u rm=%04x k=%u d=%08x\n", (unsigned) pG->Frame_cnt, room, g_digTicks, g_dig.h);
        }
    }
}
