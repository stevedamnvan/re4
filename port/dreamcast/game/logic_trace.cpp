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
#if defined(RE4DC_DECISION_TRACE) && RE4DC_DECISION_TRACE
#include "esp.h"
#include "espgen.h"
extern EspgenWork* EspgenArray;   // espgen.cpp
extern u32 nEspgen;
#endif
#include <string.h>

#ifndef RE4DC_LOGIC_TRACE_DELAY_US
#define RE4DC_LOGIC_TRACE_DELAY_US 0
#endif
// LOGIC_TRACE_MASK_RENDER=1 (opt-in; frame pacing gates): be_flag 0x08000000 is left out of the
// discrete hash. It is the ot_type-7 first-pass draw marker, set at the end of the model draw
// (trans.cpp commonModelTrans / frontNativeRender), cleared by ModelTrans and read only by the
// draw walk; a skipped draw changes it and nothing else. tools/d367/be_flag_render_bit.py fails
// when any other reader appears. 0 (default): every hash is exactly as before.
#ifndef RE4DC_LOGIC_TRACE_MASK_RENDER
#define RE4DC_LOGIC_TRACE_MASK_RENDER 0
#endif

extern "C" unsigned short re4dc_rnd_state(void);   // src/game/rnd.cpp (trace builds only)
#if RE4DC_LOGIC_TRACE_DELAY_US
#include <kos/timer.h>   // timer_us_gettime64 (static inline)
#endif

#if defined(RE4DC_DECISION_TRACE) && RE4DC_DECISION_TRACE
// Set by snd.cpp around the sound system's own line / area queries: how many run per tick follows
// audio playback time (end_check_tbl), so they go to bucket 6 ("sq") instead of the gameplay buckets.
// Global scope: an extern "C" name defined inside the unnamed namespace links to a silent stub.
extern "C" unsigned re4dc_dt_snd;
unsigned re4dc_dt_snd;
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

#if defined(RE4DC_DECISION_TRACE) && RE4DC_DECISION_TRACE
// GAME_DECISION_TRACE (test builds): decision results hashed per sample, in call order: 0 em-em
// collision (at_mod.cpp), 1 scenery line tests (at_sub.cpp), 2 area checks (sce_at.cpp), 3 damage hit
// tests (dmg.cpp), 4 line query answers and 5 their hit points (atari.cpp). Logged as "LX", with every alive enemy's position bits every 4th sample ("LP").
static Fnv g_dt[8];
static unsigned g_dtn[8];
#if RE4DC_DECISION_TRACE == 2
// Private diagnostic: frames around the tr18/tr19 line-query differences.
extern "C" int re4dc_dt_window(void)
{
    static const unsigned f[] = {644, 1087, 1287, 1729, 2417, 2814, 3183, 3530};
    const unsigned c = (unsigned) pG->Frame_cnt;
    for (unsigned k = 0; k < sizeof(f) / sizeof(f[0]); ++k)
        if (c + 2 >= f[k] && c <= f[k] + 1) return (int) c;
    return -1;
}
#endif
extern "C" unsigned re4dc_dt_note(unsigned kind, unsigned a, unsigned b)
{
    if (re4dc_dt_snd) kind = 6;
    g_dt[kind & 7].word(a);
    g_dt[kind & 7].word(b);
    ++g_dtn[kind & 7];
    return b;
}
#endif
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
#if RE4DC_LOGIC_TRACE_MASK_RENDER
    discrete.add(m->be_flag & ~0x08000000u);
#else
    discrete.add(m->be_flag);
#endif
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
#if RE4DC_LOGIC_TRACE_MASK_RENDER
    {
        // Render-only bits (set / cleared by draw stages a dropped image skips; read only by draw
        // code): [1] 0x08000000 texture-render effects queued (EspTrans, CopyTexRenderMgr),
        // [1] 0x4000 shadow texture made (make_shadow_texture, ShadowTrans), [2] 0x00100000 shadow
        // lights exist (ShadowTrans), [3] 0x10000000 letterbox scissor (inside Render).
        u32 sf[sizeof(pG->Status_flg) / 4];
        memcpy(sf, pG->Status_flg, sizeof(sf));
        sf[1] &= ~0x08004000u;
        sf[2] &= ~0x00100000u;
        sf[3] &= ~0x10000000u;
        st.words(sf, sizeof(sf));
    }
#else
    st.words(pG->Status_flg, sizeof(pG->Status_flg));
#endif
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
#if defined(RE4DC_DECISION_TRACE) && RE4DC_DECISION_TRACE
    // Effect behaviour (every live esp slot and effect generator): the scalar fields, without the
    // owner / model / parent pointers, the vptr, the derived work and m_Mat (built by the draw).
    Fnv ep, eg;
    unsigned nep = 0, neg = 0;
    if (g_pEspSys && g_pEspSys->pEspBuf) {
        for (u32 i = 0; i < g_pEspSys->nEsp; i++) {
            const unsigned char* b = g_pEspSys->pEspBuf + i * 0x150;
            if (!(b[0x0C] & 1)) {
                continue;
            }
            ep.word(i);
            ep.words(b + 0x00, 8);             // Core_flg, kind, owner, Call_no
            ep.words(b + 0x0C, 0x10);          // Be_flg .. Tool_flg
            ep.words(b + 0x20, 4);             // Guid of the attached model
            ep.words(b + 0x28, 0xBC - 0x28);   // Parts_no .. Radius
            ep.words(b + 0xEC, 8);             // shimmer / mask animation
            nep++;
        }
    }
    for (u32 i = 0; EspgenArray && i < nEspgen; i++) {
        const unsigned char* b = (const unsigned char*) &EspgenArray[i];
        if (!(b[0x0C] & 1)) {
            continue;
        }
        eg.word(i);
        eg.words(b + 0x00, 8);
        eg.words(b + 0x0C, 8);
        neg++;
    }
    re4dc_log("LX t=%u n=%u ec=%08x/%u sl=%08x/%u sa=%08x/%u dm=%08x/%u lq=%08x/%u lp=%08x sq=%08x/%u "
              "ep=%08x/%u eg=%08x/%u\n",
              (unsigned) pG->Frame_cnt, samples, g_dt[0].h, g_dtn[0], g_dt[1].h, g_dtn[1], g_dt[2].h, g_dtn[2],
              g_dt[3].h, g_dtn[3], g_dt[4].h, g_dtn[4], g_dt[5].h, g_dt[6].h, g_dtn[6], ep.h, nep, eg.h, neg);
    for (int k = 0; k < 8; ++k) {
        g_dt[k] = Fnv();
        g_dtn[k] = 0;
    }
    if ((samples & 3) == 0) {
        unsigned k = 0;
        for (cUnit* u = (cUnit*) EmMgr.pAlive; u && k < 40; u = u->pNext) {
            const cEm* e = (const cEm*) u;
            unsigned q[3][4];
            unsigned m = 0;
            for (; u && m < 3; ++m) {
                const cEm* f = (const cEm*) u;
                q[m][0] = f->id;
                q[m][1] = bits(f->pos.x);
                q[m][2] = bits(f->pos.y);
                q[m][3] = bits(f->pos.z);
                if (m < 2) u = u->pNext;
            }
            (void) e;
            re4dc_log("LP t=%u k=%u %02x:%08x,%08x,%08x %02x:%08x,%08x,%08x %02x:%08x,%08x,%08x\n",
                      (unsigned) pG->Frame_cnt, k, q[0][0], q[0][1], q[0][2], q[0][3], m > 1 ? q[1][0] : 0xFFU,
                      m > 1 ? q[1][1] : 0U, m > 1 ? q[1][2] : 0U, m > 1 ? q[1][3] : 0U, m > 2 ? q[2][0] : 0xFFU,
                      m > 2 ? q[2][1] : 0U, m > 2 ? q[2][2] : 0U, m > 2 ? q[2][3] : 0U);
            k += m;
            if (!u) break;
        }
    }
#endif

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

#if defined(RE4DC_PACE_CHECK) && RE4DC_PACE_CHECK
// PACE_CHECK=2 (pace.cpp): one FNV over every field of an LT/LU record, without logging. Used
// around the ModelTrans of a dropped image to prove it leaves the logic state untouched.
extern "C" unsigned re4dc_logic_trace_hash(void)
{
    if (!pG) return 0;
    Fnv all, st, rf, sc, cam, ps, pf, pm, es, ef, em, os, of, om;
#if RE4DC_LOGIC_TRACE_MASK_RENDER
    {
        // Render-only bits (set / cleared by draw stages a dropped image skips; read only by draw
        // code): [1] 0x08000000 texture-render effects queued (EspTrans, CopyTexRenderMgr),
        // [1] 0x4000 shadow texture made (make_shadow_texture, ShadowTrans), [2] 0x00100000 shadow
        // lights exist (ShadowTrans), [3] 0x10000000 letterbox scissor (inside Render).
        u32 sf[sizeof(pG->Status_flg) / 4];
        memcpy(sf, pG->Status_flg, sizeof(sf));
        sf[1] &= ~0x08004000u;
        sf[2] &= ~0x00100000u;
        sf[3] &= ~0x10000000u;
        st.words(sf, sizeof(sf));
    }
#else
    st.words(pG->Status_flg, sizeof(pG->Status_flg));
#endif
    rf.words(pG->Room_flg, sizeof(pG->Room_flg));
    sc.words(pG->Scenario_flg, sizeof(pG->Scenario_flg));
    sc.add(pG->Item_find_flg);
    cam.words(&pG->Cam.param, 32);
    if (pPL) {
        model_state(ps, pf, pm, pPL);
        all.words(&pPL->pos, sizeof(pPL->pos)); all.words(&pPL->ang, sizeof(pPL->ang));
        all.add(pPL->Motion.Mot_frame); all.add(pPL->Motion.Mot_state);
    }
    unsigned ne = 0, no = 0;
    for (cUnit* u = (cUnit*) EmMgr.pAlive; u && ne < 1024; u = u->pNext, ++ne) {
        cEm* e = (cEm*) u;
        model_state(es, ef, em, e);
        es.add(e->hp);
    }
    for (cUnit* u = (cUnit*) ObjMgr.pAlive; u && no < 1024; u = u->pNext, ++no)
        model_state(os, of, om, (cModel*) u);
    const unsigned v[] = {re4dc_rnd_state(), (unsigned) pG->System_flg, (unsigned) pG->Stop_flg, st.h, rf.h, sc.h,
                          (unsigned(pG->stage_no) << 8) | pG->room_no, ps.h, pf.h, pm.h, ne, es.h, ef.h, em.h, no,
                          os.h, of.h, om.h, cam.h};
    for (unsigned w : v) all.word(w);
    return all.h;
}
#endif
