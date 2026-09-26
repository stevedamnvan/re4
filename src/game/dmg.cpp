// game/dmg.cpp: damage volumes (DmgMgr). Fire, explosions and traps register a cylinder or an
// XZ quad with a damage kind and a lifetime; the objects (boxes, doors, items...) and characters
// poll DmgMgr.hitCheck with their position each frame and react to the kind (1 / 4 / 5 / 7 break
// the breakable objects, 5 is fire). Volumes expire on their own.
// Original source: D:/Bio4/Prog/dmg.cpp.
#include "types.h"
#include "global.h"
#include "dmg.h"
#include "dbmodule.h"
#include "math_sub.h"

// A cManager<cDmg> pool of 0x118 byte works.
cDmgMgr::cDmgMgr() : cManager<cDmg>(0x118, 2)
{
    setName("cDmgMgr");
}

// Places a cylinder (id 0) or quad (id 1) volume into the fresh work.
int cDmgMgr::construct(cDmg* p, int id)
{
    switch (id) {
    case 0:
    default:
        new (p) cDmgCyl;
        p->be_flag = 1;
        break;
    case 1:
        new (p) cDmgP4;
        p->be_flag = 1;
        break;
    }
    p->m_Id = id;
    return 1;
}

// cManager hook (unsigned id).
int cDmgMgr::construct(cDmg* p, u32 id)
{
    return construct(p, (int) id);
}

#if defined(RE4DC_OB_SCAN) && RE4DC_OB_SCAN
#if RE4DC_OB_SCAN == 2
// GAME_OB_SCAN (game30.mk): =2 check counters for the three scan cuts (dmg.cpp, em_set.cpp,
// id_sys.cpp), logged here ("OBS"). None at =1, so the cost build's data layout does not move.
extern "C" {
unsigned long re4dc_ob_chk[12];
}
extern "C" void re4dc_log(const char* fmt, ...);
#endif
// dieCheck is a no-op unless a work carries 0x200 / 0x400: 0x400 is freed on the next call, 0x200
// becomes 0x600 on the next and is freed on the one after. So once two calls have run with no
// destroy in between, the remaining calls of this pass change nothing and are skipped.
static inline u32 obDmgPending(cDmgMgr* m)
{
    u32 i;

    for (i = 0; i < m->nArray; i++) {
        if (((cDmg*) ((u8*) m->pArray + m->size * i))->be_flag & 0x600) {
            return 2;
        }
    }
    return 0;
}
#endif
// Per-frame: counts every live volume's lifetime down and destroys it at 0.
void cDmgMgr::move()
{
    u32 i;

#if defined(RE4DC_OB_SCAN) && RE4DC_OB_SCAN
    u32 need = obDmgPending(this);   // dieCheck calls that can still change a work

    for (i = 0; i < nArray; i++) {
        cDmg* p = (cDmg*) ((u8*) pArray + size * i);
#if RE4DC_OB_SCAN == 2
        // the source call runs; a skip must be a no-op
        if (need == 0 && obDmgPending(this)) {
            re4dc_ob_chk[1]++;
        }
        dieCheck();
#else
        if (need != 0) {
            dieCheck();
        }
#endif
        if (need != 0) {
            need--;
        }
        if ((p->be_flag & 0x201) == 1) {
            if (--p->m_Time == 0) {
                destroy(p);
                need = 2;
            }
        }
    }
#if RE4DC_OB_SCAN == 2
    if (++re4dc_ob_chk[0] % 512 == 1) {
        re4dc_log("OBS dmgmove=%lu skip_mis=%lu hit=%lu hit_mis=%lu hit_src=%lu emlist=%lu em_mis=%lu em_src=%lu "
                  "idsys=%lu id_mis=%lu id_over=%lu id_rest_max=%lu\n",
                  re4dc_ob_chk[0], re4dc_ob_chk[1], re4dc_ob_chk[2], re4dc_ob_chk[3], re4dc_ob_chk[4],
                  re4dc_ob_chk[5], re4dc_ob_chk[6], re4dc_ob_chk[7], re4dc_ob_chk[8], re4dc_ob_chk[9],
                  re4dc_ob_chk[10], re4dc_ob_chk[11]);
    }
#endif
#else
    for (i = 0; i < nArray; i++) {
        cDmg* p = (cDmg*) ((u8*) pArray + size * i);
        dieCheck();
        if ((p->be_flag & 0x201) == 1) {
            if (--p->m_Time == 0) {
                destroy(p);
            }
        }
    }
#endif
}

// Registers a cylinder volume (centre, radius, half height) of `kind` for `time` frames; 1 when
// a work was free.
int cDmgMgr::set(int kind, int time, Vec* pos, f32 r, f32 h)
{
    cDmgCyl* p = (cDmgCyl*) create(0);

    if (p == 0) {
        return 0;
    }
    p->kind = kind;
    p->m_Time = time;
    p->m_Pos = *pos;
    p->m_Radius = r;
    p->m_Height = h;
    return 1;
}

// Registers an XZ quad volume (4 corners, half height) of `kind` for `time` frames.
int cDmgMgr::set(int kind, int time, Vec* pt, f32 h)
{
    cDmgP4* p = (cDmgP4*) create(1);

    if (p == 0) {
        return 0;
    }
    p->kind = kind;
    p->m_Time = time;
    p->m_Pos[0] = pt[0];
    p->m_Pos[1] = pt[1];
    p->m_Pos[2] = pt[2];
    p->m_Pos[3] = pt[3];
    p->h = h;
    return 1;
}

// The kind of the first live volume containing `pos` (its centre in *out); 0 when none.
#if defined(RE4DC_DECISION_TRACE) && RE4DC_DECISION_TRACE
// GAME_DECISION_TRACE (test builds): every damage hit test result, in call order (logic_trace.cpp).
extern "C" unsigned re4dc_dt_note(unsigned kind, unsigned a, unsigned b);
#define DT_DMG(r) re4dc_dt_note(3, i, (u32) (r))
#else
#define DT_DMG(r) (r)
#endif
#if defined(RE4DC_OB_SCAN) && RE4DC_OB_SCAN
// GAME_OB_SCAN: a work passes the live test only while it is on the alive list (create links it
// right after construct sets be_flag 1; destroy unlinks it before marking 0x200; nothing else in
// the game writes a cDmg's be_flag), so the live works come from the list, in slot (= address)
// order, and are tested exactly as the source loop would test them. Returns 0 when the list holds
// something unexpected (outside the array, more than 32 live): the caller runs the source loop.
static inline int obDmgFast(cDmgMgr* m, Vec* pos, Vec* out, u32* hit, int* kind)
{
    cDmg* v[32];
    cDmg* p;
    u32 n = 0;
    u32 k;
    u8* lo = (u8*) m->pArray;
    u8* hi = lo + m->size * m->nArray;

    if (m->pArrayPush != 0) {
        return 0;
    }
    for (p = m->pAlive; p != 0; p = (cDmg*) p->pNext) {
        if ((u8*) p < lo || (u8*) p >= hi) {
            return 0;
        }
        if ((p->be_flag & 0x201) == 1) {
            if (n == 32) {
                return 0;
            }
            k = n++;
            while (k > 0 && v[k - 1] > p) {
                v[k] = v[k - 1];
                k--;
            }
            v[k] = p;
        }
    }
    for (k = 0; k < n; k++) {
        if (v[k]->hitCheck(pos, out)) {
            *hit = (u32) ((u8*) v[k] - lo) / m->size;
            *kind = v[k]->kind;
            return 1;
        }
    }
    *hit = m->nArray;
    *kind = 0;
    return 1;
}
#endif
int cDmgMgr::hitCheck(Vec* pos, Vec* out)
{
    u32 i;

#if defined(RE4DC_OB_SCAN) && RE4DC_OB_SCAN
#if RE4DC_OB_SCAN == 2
    // the fast answer (into a copy of *out) beside the source loop, which runs live
    Vec tmp;
    u32 fi = 0;
    int fk = 0;
    int fast = obDmgFast(this, pos, out ? &tmp : (Vec*) 0, &fi, &fk);
    int src = 0;
    re4dc_ob_chk[2]++;
    for (i = 0; i < nArray; i++) {
        cDmg* p = (cDmg*) ((u8*) pArray + size * i);
        if ((p->be_flag & 0x201) == 1) {
            if (p->hitCheck(pos, out)) {
                src = p->kind;
                break;
            }
        }
    }
    if (!fast) {
        re4dc_ob_chk[4]++;
    } else if (fi != i || fk != src || (src != 0 && out != 0 && (tmp.x != out->x || tmp.y != out->y || tmp.z != out->z))) {
        re4dc_ob_chk[3]++;
    }
    return DT_DMG(src);
#else
    {
        int fk;
        if (obDmgFast(this, pos, out, &i, &fk)) {
            return DT_DMG(fk);
        }
    }
#endif
#endif
    for (i = 0; i < nArray; i++) {
        cDmg* p = (cDmg*) ((u8*) pArray + size * i);
        if ((p->be_flag & 0x201) == 1) {
            if (p->hitCheck(pos, out)) {
                return DT_DMG(p->kind);
            }
        }
    }
    return DT_DMG(0);
}

// Point in cylinder (height band +-m_Height, XZ radius); *out = centre. Debug_flg[2] 0x10000000
// draws the volume.
int cDmgCyl::hitCheck(Vec* p, Vec* out)
{
    if (pG->Debug_flg[2] & 0x10000000) {
        Draw_cylinder(&m_Pos, m_Radius, m_Height, 0xFFFFFFFF);
    }
    if (p->y > m_Pos.y + m_Height) {
        return 0;
    }
    if (p->y < m_Pos.y - m_Height) {
        return 0;
    }
    if ((p->x - m_Pos.x) * (p->x - m_Pos.x) + (p->z - m_Pos.z) * (p->z - m_Pos.z) > m_Radius * m_Radius) {
        return 0;
    }
    if (out) {
        *out = m_Pos;
    }
    return kind;
}

// Point in the XZ quad; *out = the corners' mean.
int cDmgP4::hitCheck(Vec* p, Vec* out)
{
    u32 i;

    if (HitCheckPoint4(p, m_Pos)) {
        if (out) {
            out->x = 0.0f;
            out->y = 0.0f;
            out->z = 0.0f;
            for (i = 0; i < 4; i++) {
                PSVECAdd(out, &m_Pos[i], out);
            }
            PSVECScale(out, out, 0.25f);
        }
        return kind;
    }
    return 0;
}

// Event start: damage volumes are removed.
void cDmg::beginEvent()
{
    DmgMgr.destroy(this);
}

cDmgMgr DmgMgr;

// The split object carries 16 unnamed zero bytes after DmgMgr (0x802DA150): dvd.cpp's .bss follows
// at the next 32-byte boundary and ngcld does not pad for it. A zero-initialised static referenced
// only by a never-called inline is emitted after DmgMgr (first-declaration order) without a body.
static u8 dmg_pad[16];
// Never called: only keeps dmg_pad emitted (see above).
static inline u8* dmgPad()
{
    return dmg_pad;
}
