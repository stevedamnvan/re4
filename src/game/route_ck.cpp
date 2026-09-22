// game/route_ck: enemy route finding on the room's RTP data (pG->Rtp, the "RTP" sub-file of the
// room archive): a set of route points with links between them and a precomputed next-hop table
// (row = current point, column = destination). Enemies ask RouteCkToEm / RouteCkToPos for the
// next position to walk to (a direct line when nothing blocks it, else the next route point;
// cEm::RckMy / RckTo / RckNear cache the points, RckStat bit0 marks the near point as fresh for
// this frame), RouteCkEscEm for the point leading away from someone, RouteCkGetDist for the path
// length. Draw_rtp / Draw_eminfo are the debug displays of the points and the EMI placements.
#include "route_ck.h"
#include "em.h"
#include "player.h"
#include "atari.h"
#include "global.h"
#include "math_sub.h"
#include "dbmodule.h"
#include "eprintf.h"
#include "db_log.h"

// EMI entry as this unit draws it (embarrel.h has its own view of the same data).
struct RckEmiEntry {
    u8 type;       // 0x00  2 = route point
    u8 kind;       // 0x01  line colour: 1 blue, 2 red
    u8 pad_2[2];
    Vec pos;       // 0x04
    u8 pad_10[0x40 - 0x10];
};

struct RckEmiData {
    int n;                  // 0x00
    u8 pad_4[4];
    RckEmiEntry entry[1];   // 0x08
};

// The room's route point data.
static inline RtpData* rtpData()
{
    return (RtpData*)pG->Rtp;
}

// The point array of the RTP data.
static inline RtpPoint* rtpPoint(RtpData* r)
{
    return (RtpPoint*)(r->pointOfs + (u32)r);
}

// The link array (each point's links start at its offLine).
static inline RtpLink* rtpLink(RtpData* r)
{
    return (RtpLink*)(r->linkOfs + (u32)r);
}

// Next-hop table: row = current point, column = destination (read through the Global instance).
static inline s8* rtpNextTbl()
{
    RtpData* r = (RtpData*)Global.Rtp;
    return (s8*)(r->nextOfs + (u32)r);
}

// Next hop from `a` towards `b`.
static inline s8 rtpNext(s8* tbl, int a, int b)
{
    return tbl[rtpData()->nPoint * a + b];
}

extern "C" {
static int rckLineHitCheck(Vec* from, Vec* to, int attr, int flag);
}

// Once per frame before the enemies move: clears every live enemy's and the player's RckStat so
// the near point is looked up again.
void RouteCk()
{
    u32 i;
    u32 n = EmMgr.nArray;

    for (i = 0; i < n; i++) {
#if !defined(__PPC__)
        cEm* em = (cEm*) EmMgr.workAt(i);
        if (!em) continue;
#else
        cEm* em = (cEm*)((u8*)EmMgr.pArray + EmMgr.size * i);
#endif
        if ((em->be_flag & 0x201) == 1) {
            em->RckStat = 0;
        }
    }
    pPL->RckStat = 0;
}

// Where `em` should walk to reach `target`: the target itself (returns 1) when there is no RTP, a
// clear line 500 above the ground with a floor under the midpoint, or no route; else the next
// route point toward the target's nearest point (returns 0), advancing RckMy once within 250 of
// the current point or when the next is in clear view. flag bit0 = skip the direct test unless
// the next hop is the last, bit1 / bit2 (forced for Ashley, id 3) widen / narrow the collision mask.
int RouteCkToEm(cEm* em, cEm* target, Vec* out, int flag)
{
    Vec a;
    Vec b;
    Vec c;
    int p;
    int t;
    int next;
    int mask;
    RtpPoint* pts;
    RtpPoint* pt;
    s8* tbl;
    f32 d2;

    a = em->pos;
    a.y += 500.0f;
    b = target->pos;
    b.y += 500.0f;
    mask = em->atari.m_flag;
    if (em->id == 3) {
        flag |= 4;
    }
    if (!(flag & 1)) {
        if (pG->Rtp == NULL) {
            *out = target->pos;
            return 1;
        }
        if (rckLineHitCheck(&a, &b, mask, flag) == 0) {
            PosToPos(&a, &b, &c, 0.5f);
            if (SatMgr.getFloor(&c, 600.0f, 100000.0f, NULL, 0) > c.y - 2000.0f) {
                *out = target->pos;
                return 1;
            }
        }
    }
    em->RckMy = em->RckNear = getNearInfo(em, 0, mask);
    em->RckTo = target->RckNear = getNearInfo(target, 0, mask);
    p = em->RckMy;
    if (p == -1) {
        *out = target->pos;
        return 1;
    }
    t = em->RckTo;
    if (t == -1) {
        *out = target->pos;
        return 1;
    }
    {
        RtpData* r = (RtpData*) Global.Rtp;
        tbl = (s8*) (r->nextOfs + (u32) r);
    }
    next = rtpNext(tbl, p, t);
    if (next == -1) {
        *out = target->pos;
        return 1;
    }
    if ((flag & 1) && next == t) {
        if (fabsf(a.y - b.y) < 2000.0f) {
            if (pG->Rtp == NULL || rckLineHitCheck(&a, &b, mask, flag) == 0) {
                *out = target->pos;
                return 1;
            }
        }
    }
    mask |= 0x80;
    pts = rtpPoint(rtpData());
    pt = (RtpPoint*)(em->RckMy * sizeof(RtpPoint) + (u32)pts);
    d2 = (em->pos.x - pt->pos.x) * (em->pos.x - pt->pos.x) + (em->pos.z - pt->pos.z) * (em->pos.z - pt->pos.z);
    if (d2 < 62500.0f || (next != em->RckMy && rckLineHitCheck(&a, &pts[next].pos, mask, flag) == 0)) {
        em->RckMy = next;
    }
    *out = rtpPoint(rtpData())[em->RckMy].pos;
    return 0;
}

// Escape point for `em` fleeing `from`: the linked neighbour of its nearest route point that lies
// most directly away from `from` (within 1000 in height); the mirrored position when no RTP.
void RouteCkEscEm(cEm* em, cEm* from, Vec* out)
{
    RtpData* rtp;
    RtpPoint* pt;
    RtpPoint* np;
    int mask;
    u32 i;
    f32 ang;
    f32 best;
    f32 m;

    mask = em->atari.m_flag;
    PSVECSubtract(&em->pos, &from->pos, out);
    PSVECAdd(out, &em->pos, out);
    em->RckNear = getNearInfo(em, 0, mask);
    if (em->RckNear == -1) {
        return;
    }
    rtp = rtpData();
    pt = &rtpPoint(rtp)[em->RckNear];
    *out = pt->pos;
    if (pt->nLine == 0) {
        return;
    }
    ang = GetXZAngle(&em->pos, &from->pos);
    best = 0.0f;
    for (i = 0; i < pt->nLine; i++) {
        // Block-local rtp copy (a second `rtp =` would make the entry block's rtp a global
        // pseudo) and the link entry through a pointer local (a deref'd `tbl[n]` puts the
        // index first in the lhax address; `&tbl[n]` keeps the table first).
        RtpData* r = rtpData();
        RtpLink* lk = &rtpLink(r)[pt->offLine + i];
        np = &rtpPoint(r)[lk->point];
        m = fabsf(Muku(&em->pos, &np->pos, ang, PI));
        if (m < best) {
            continue;
        }
        if (fabsf(np->pos.y - em->pos.y) > 1000.0f) {
            continue;
        }
        best = m;
        *out = np->pos;
    }
}

// RouteCkToEm toward a position: same rules; `dist` (optional) receives the height difference on a
// direct move or the remaining path length (longest edge counted from the current point).
int RouteCkToPos(cEm* em, Vec* target, Vec* out, int flag, f32* dist)
{
    Vec a;
    Vec b;
    Vec c;
    int p;
    int t;
    int next;
    int mask;
    RtpPoint* pts;
    RtpPoint* pt;
    s8* tbl;
    f32 d2;
    f32 dmax;

    a = em->pos;
    a.y += 500.0f;
    b = *target;
    b.y += 500.0f;
    mask = em->atari.m_flag;
    if (em->id == 3) {
        flag |= 4;
    }
    if (!(flag & 1)) {
        if (pG->Rtp == NULL) {
            *out = *target;
            if (dist != NULL) {
                *dist = a.y - b.y;
                *dist = fabsf(*dist);
            }
            return 1;
        }
        if (rckLineHitCheck(&a, &b, mask, flag) == 0) {
            PosToPos(&a, &b, &c, 0.5f);
            if (SatMgr.getFloor(&c, 600.0f, 100000.0f, NULL, 0) > c.y - 2000.0f) {
                *out = *target;
                if (dist != NULL) {
                    *dist = a.y - b.y;
                    *dist = fabsf(*dist);
                }
                return 1;
            }
        }
    }
    em->RckMy = em->RckNear = getNearInfo(em, 0, mask);
    em->RckTo = getNearPoint(&b, 0, mask);
    p = em->RckMy;
    if (p == -1) {
        *out = *target;
        if (dist != NULL) {
            *dist = a.y - b.y;
            *dist = fabsf(*dist);
        }
        return 1;
    }
    t = em->RckTo;
    if (t == -1) {
        *out = *target;
        if (dist != NULL) {
            *dist = a.y - b.y;
            *dist = fabsf(*dist);
        }
        return 1;
    }
    {
        RtpData* r = (RtpData*) Global.Rtp;
        tbl = (s8*) (r->nextOfs + (u32) r);
    }
    next = tbl[rtpData()->nPoint * p + t];
    if (next == -1) {
        *out = *target;
        if (dist != NULL) {
            *dist = a.y - b.y;
            *dist = fabsf(*dist);
        }
        return 1;
    }
    if ((flag & 1) && next == t) {
        if (fabsf(a.y - b.y) < 2000.0f) {
            if (pG->Rtp == NULL || rckLineHitCheck(&a, &b, mask, flag) == 0) {
                *out = *target;
                if (dist != NULL) {
                    *dist = a.y - b.y;
                    *dist = fabsf(*dist);
                }
                return 1;
            }
        }
    }
    mask |= 0x80;
    pts = rtpPoint(rtpData());
    pt = (RtpPoint*)(em->RckMy * sizeof(RtpPoint) + (u32)pts);
    d2 = (em->pos.x - pt->pos.x) * (em->pos.x - pt->pos.x) + (em->pos.z - pt->pos.z) * (em->pos.z - pt->pos.z);
    if (d2 < 62500.0f || (next != em->RckMy && rckLineHitCheck(&a, &pts[next].pos, mask, flag) == 0)) {
        em->RckMy = next;
    }
    *out = rtpPoint(rtpData())[em->RckMy].pos;
    if (dist != NULL) {
        RtpData* r;
        int np;
        // The hop loop reuses `next` (one global pseudo, r30) and keeps the table read in the loop
        // test, so the exit test copied to the entry is the pre-loop `tbl[..]`; the struct-view rtp
        // and `np` are the fresh `pG` load and the hoisted nPoint. A `while` whose body is under
        // 30 raw insns would have the whole body up to the `break` rotated instead.
        dmax = a.y - b.y;
        dmax = fabsf(dmax);
        r = (RtpData*) pGS->Rtp;
        np = r->nPoint;
        next = em->RckMy;
        while ((next = tbl[np * next + em->RckTo]) != -1) {
            f32 d = fabsf(a.y - rtpPoint(r)[next].pos.y);
            if (d > dmax) {
                dmax = d;
            }
            if (next == em->RckTo) {
                break;
            }
        }
        *dist = dmax;
    }
    return 0;
}

// Route step between two positions without an enemy (scenario / camera use): `to` itself (1) when
// reachable directly or unrouted, else the next route point (0).
int RouteCkPosToPos(Vec* from, Vec* to, Vec* out)
{
    Vec a;
    Vec b;
    Vec c;
    int p;
    int t;
    int next;
    RtpData* rtp;
    RtpPoint* pts;
    RtpPoint* pt;
    f32 d2;
    s8* tbl;

    a = *from;
    b = *to;
    a.y += 500.0f;
    b.y += 500.0f;
    if (pG->Rtp == NULL) {
        *out = *to;
        return 1;
    }
    if (rckLineHitCheck(&a, &b, 0, 0) == 0) {
        PosToPos(&a, &b, &c, 0.5f);
        if (SatMgr.getFloor(&c, 600.0f, 100000.0f, NULL, 0) > c.y - 2000.0f) {
            *out = *to;
            return 1;
        }
    }
    p = getNearPoint(&a, 0, 0);
    if (p == -1) {
        *out = *to;
        return 1;
    }
    t = getNearPoint(&b, 0, 0);
    if (t == -1) {
        *out = *to;
        return 1;
    }
    {
        RtpData* r = (RtpData*) Global.Rtp;
        tbl = (s8*) (r->nextOfs + (u32) r);
    }
    next = rtpNext(tbl, p, t);
    if (next == -1) {
        *out = *to;
        return 1;
    }
    rtp = rtpData();
    {
        u32 base = (u32) rtpPoint(rtp);
        pts = (RtpPoint*) base;
        pt = (RtpPoint*)(p * sizeof(RtpPoint) + base);
        d2 = (a.x - pt->pos.x) * (a.x - pt->pos.x) + (a.z - pt->pos.z) * (a.z - pt->pos.z);
        if (d2 < 62500.0f) {
            *out = ((RtpPoint*)(next * sizeof(RtpPoint) + base))->pos;
            return 0;
        }
    }
    if (rckLineHitCheck(&a, &pts[next].pos, 0, 0) == 0) {
        *out = rtpPoint(rtpData())[next].pos;
        return 0;
    }
    *out = rtpPoint(rtpData())[p].pos;
    return 0;
}

// 1 when the nearest route points of the two positions are connected by the next-hop table.
int RouteCkConnectPosCk(Vec* pPos1, Vec* pPos2)
{
    int p;
    int t;

    p = getNearPoint(pPos1, 0, 0);
    if (p == -1) {
        return 0;
    }
    t = getNearPoint(pPos2, 0, 0);
    if (t == -1) {
        return 0;
    }
    if (rtpNext(rtpNextTbl(), p, t) == -1) {
        return 0;
    }
    return 1;
}

// Walking distance between two positions: the route length between their nearest points, or the
// straight XZ distance when the line is clear / no route.
f32 RouteCkPosToPosDis(Vec* from, Vec* to)
{
    Vec a;
    Vec b;
    Vec c;
    int p;
    int t;

    a = *from;
    b = *to;
    a.y += 500.0f;
    b.y += 500.0f;
    if (pG->Rtp != NULL) {
        // COMPILER-DIFF: candidate (reload_cse register table): the original keeps `mr r3,r31; mr r4,r29`
        // for the from/to arguments although r3/r4 still hold them since the entry copies; ours deletes
        // the two copies in reload_cse_regs. The volatile asm forgets the table (a label or call would too).
        asm volatile("" : : : "memory");
        if (rckLineHitCheck(from, to, 0, 0) == 0) {
            PosToPos(&a, &b, &c, 0.5f);
            if (SatMgr.getFloor(&c, 600.0f, 100000.0f, NULL, 0) > c.y - 2000.0f) {
                goto direct;
            }
        }
        p = getNearPoint(from, 0, 0);
        if (p == -1) {
            goto direct;
        }
        t = getNearPoint(to, 0, 0);
        if (t == -1) {
            goto direct;
        }
        return RouteCkGetDist(p, t);
    }
direct:
    return SQRTF((from->x - to->x) * (from->x - to->x) + (from->z - to->z) * (from->z - to->z));
}

// The original zeroes the Vec in place with a memset libcall (`crclr cr1eq` = unprototyped
// call) whose `&p` argument is a pseudo PRE'd with the other arm's copy: a reference inline
// around a `(...)`-prototyped memset reproduces both (`p = Vec()` gives a zeroed temporary
// plus a block copy with our cc1plus).
extern "C" void* memset_v(...) asm("memset");
static inline void vecClear(Vec& v) { memset_v(&v, 0, sizeof(Vec)); }
// Position of route point `no` (zero without RTP).
void RouteCkGetPoint(int no, Vec* out)
{
    RtpData* rtp = rtpData();
    Vec p;

    if (rtp != NULL) {
        p = rtpPoint(rtp)[no].pos;
    } else {
        vecClear(p);
    }
    *out = p;
}

// Number of route points, -1 without RTP.
int RouteCkGetPointNumber()
{
    RtpData* rtp = rtpData();

    return rtp != NULL ? rtp->nPoint : -1;
}

// Path length from point n0 to n1 along the next-hop table (straight distance when unconnected).
f32 RouteCkGetDist(int n0, int n1)
{
    f32 d = 0.0f;
    int next;
    RtpPoint* pt;
    RtpPoint* np;
    s8* tbl;
    Vec tmp;

    if (n0 == n1) {
        return d;
    }
    {
        RtpData* r = (RtpData*) Global.Rtp;
        tbl = (s8*) (r->nextOfs + (u32) r);
    }
    pt = &rtpPoint(rtpData())[n0];
    do {
        next = rtpNext(tbl, n0, n1);
        if (next == -1) {
            PSVECSubtract(&rtpPoint(rtpData())[n0].pos, &rtpPoint(rtpData())[n1].pos, &tmp);
            return PSVECMag(&tmp);
        }
        np = &rtpPoint(rtpData())[next];
        PSVECSubtract(&pt->pos, &np->pos, &tmp);
        d += PSVECMag(&tmp);
        n0 = next;
        pt = np;
    } while (n0 != n1);
    return d;
}

// Dead-stripped by the original linker (STRIP_UNUSED); only its constant pool remains in .rodata.
static f32 route_ck_unused(f32 a)
{
    if (a < -6.2831855f) {
        a = 3.1415927f;
    }
    if (a < 0.0f) {
        a += 6.2831855f;
    }
    return a;
}

// Nearest visible route point to `pos`, -1 when none.
int RouteCkGetNearPoint(Vec* pos)
{
    return getNearPoint(pos, 0, 0);
}

// Route line test against the scroll collision (attr | 0x4000, ignoring the route-only bits
// 0x383070; flag bit1 also 8, without bit2 also 0x40000); non-zero when blocked. debug_mode 8
// draws the line.
static int rckLineHitCheck(Vec* from, Vec* to, int attr, int flag)
{
    Vec pa;
    Vec pb;
    int mask;

    pa = *from;
    pb = *to;
    if (pGS->debug_mode == 8) {
        Draw_line3d(&pa, &pb, 0xFFFF0000, 0);
    }
    attr |= 0x4000;
    mask = 0x383070;
    if (flag & 2) {
        mask = 0x383078;
    }
    if (!(flag & 4)) {
        mask |= 0x40000;
    }
    return SatMgr.hitCheck(&pa, &pb, NULL, NULL, attr, mask);
}

// The enemy's nearest route point, computed once per frame (RckStat bit0 caches RckNear).
int getNearInfo(cEm* em, int mode, int mask)
{
    if (em->RckStat & 1) {
        return em->RckNear;
    }
    em->RckStat |= 1;
    return getNearPoint(&em->pos, mode, mask);
}

// Nearest route point to `pos`: the ten closest are sorted; mode != 0 returns the closest, else
// the first with a clear line from 500 above pos. -1 when none.
s8 getNearPoint(Vec* pos, int mode, int mask)
{
    f32 dist[10];
    int idx[10];
    Vec p2;
    RtpData* rtp;
    RtpPoint* pt;
    int* ip;
    int n;
    int m;
    int i;
    int j;
    int k;
    f32 d;

    rtp = rtpData();
    if (rtp == NULL) {
        return -1;
    }
    n = rtp->nPoint;
    if (n == 0) {
        return -1;
    }
    m = n;
    if (m > 10) {
        m = 10;
    }
    for (i = 0; i < m; i++) {
        dist[i] = 1.0e16f;
    }
    pt = rtpPoint(rtpData());
    for (i = 0; i < n; i++) {
        d = (pos->x - pt->pos.x) * (pos->x - pt->pos.x) + (pos->y - pt->pos.y) * (pos->y - pt->pos.y) +
            (pos->z - pt->pos.z) * (pos->z - pt->pos.z);
        for (j = m; j > 0; j--) {
            if (d > dist[j - 1]) {
                break;
            }
        }
        if (j < m) {
            for (k = m - 1; k > j; k--) {
                idx[k] = idx[k - 1];
                dist[k] = dist[k - 1];
            }
            idx[j] = i;
            dist[j] = d;
        }
        pt++;
    }
    if (mode != 0) {
        return idx[0];
    }
    pt = rtpPoint(rtpData());
    p2 = *pos;
    p2.y += 500.0f;
    for (i = 0, ip = idx; i < m; i++, ip++) {
        if (rckLineHitCheck(&p2, &pt[*ip].pos, mask, 0) == 0) {
            return *ip;
        }
    }
    return -1;
}

// Debug: draws every route point as a marker with its index, the links (blue, white when
// two-way) and their direction arrows.
void Draw_rtp()
{
    RtpData* rtp;
    RtpPoint* pt;
    RtpPoint* np;
    Vec v0;
    Vec v1;
    Vec v2;
    Vec v3;
    Vec v4;
    Vec sp;
    int i;
    int j;
    u32 k;
    int back;
    GlobalWork* g;

    rtp = rtpData();
    if (rtp == NULL) {
        return;
    }
    if (rtp->nPoint == 0) {
        return;
    }
    pt = rtpPoint(rtp);
    for (i = 0; i < rtpData()->nPoint; i++) {
        Vec pp;
        v0 = pt->pos;
        v1 = pt->pos;
        v2 = pt->pos;
        v3 = pt->pos;
        v4 = pt->pos;
        v0.x += 100.0f;
        v1.x -= 100.0f;
        v2.y += 500.0f;
        v3.z += 100.0f;
        v4.z -= 100.0f;
        Draw_line3d(&v0, &v1, 0xFFFFFFFF, 0);
        Draw_line3d(&v0, &v2, 0xFFFFFFFF, 0);
        Draw_line3d(&v1, &v2, 0xFFFFFFFF, 0);
        Draw_line3d(&v3, &v4, 0xFFFFFFFF, 0);
        Draw_line3d(&v3, &v2, 0xFFFFFFFF, 0);
        Draw_line3d(&v4, &v2, 0xFFFFFFFF, 0);
        pp = pt->pos;
        GetScreenPos(&pp, &sp);
        if (sp.z < 1.0f) {
            eprintf2(10, 16, (u32)sp.x - 20, (u32)sp.y + 16, 4, 0, "[%02x]", i);
        }
        pt++;
    }
    // The loop test refreshes a GlobalWork* local: the pG value is one pseudo through the
    // entry copy and the latch (`mr r11,r5` twice), and the body's pRoomRtp load stays.
    for (i = 0; i < ((RtpData*)(g = pG)->Rtp)->nPoint; i++) {
        pt = &rtpPoint(rtpData())[i];
        for (j = 0; j < pt->nLine; j++) {
            Vec d;
            Mtx m;
            Vec e;
            Vec f;
            {
                RtpData* r = rtpData();
                RtpLink* lk = &rtpLink(r)[pt->offLine + j];
                np = &rtpPoint(r)[lk->point];
            }
            back = 0;
            for (k = 0; k < np->nLine; k++) {
                RtpLink* lk = &rtpLink(rtpData())[np->offLine + k];
                if (lk->point == i) {
                    back = 1;
                    break;
                }
            }
            if (back) {
                Draw_line3d(&pt->pos, &np->pos, 0xFFFFFFFF, 0);
            } else {
                Draw_line3d(&pt->pos, &np->pos, 0xFF0000FF, 0);
                PSVECSubtract(&pt->pos, &np->pos, &d);
                PSVECScale(&d, &d, 0.5f);
                PSVECAdd(&np->pos, &d, &f);
                if (d.x == 0.0f && d.z == 0.0f) {
                    continue;
                }
#line 1019 "D:/Bio4/Prog/route_ck.cpp"
                VECNormalize(&d, &d);
                PSVECScale(&d, &d, 500.0f);
                PSMTXRotRad(m, 'y', 0.78539819f);
                PSMTXMultVec(m, &d, &e);
                PSVECAdd(&f, &e, &e);
                Draw_line3d(&f, &e, 0xFF0000FF, 0);
                PSMTXRotRad(m, 'y', -0.78539819f);
                PSMTXMultVec(m, &d, &e);
                PSVECAdd(&f, &e, &e);
                Draw_line3d(&f, &e, 0xFF0000FF, 0);
            }
        }
    }
}

// Debug: draws every EMI (enemy placement) entry as a marker with its index and joins the type 2
// (patrol route) entries into a closed polygon coloured by kind (1 blue, 2 red).
void Draw_eminfo()
{
    RckEmiData* emi;
    RckEmiEntry* e;
    RckEmiEntry* first;
    RckEmiEntry* prev;
    RckEmiEntry* pp;
    Vec v0;
    Vec v1;
    Vec v2;
    Vec v3;
    Vec v4;
    Vec sp;
    Vec ps;
    u32 i;
    u32 col;

    emi = (RckEmiData*)pG->pEmi;
    if (emi == NULL) {
        return;
    }
    if (emi->n == 0) {
        return;
    }
    first = NULL;
    prev = NULL;
    pp = NULL;
    for (i = 0; i < ((RckEmiData*)pG->pEmi)->n; i++) {
        e = &((RckEmiData*)pG->pEmi)->entry[i];
        v0 = e->pos;
        v1 = e->pos;
        v2 = e->pos;
        v3 = e->pos;
        v4 = e->pos;
        v0.x += 100.0f;
        v1.x -= 100.0f;
        v2.y += 500.0f;
        v3.z += 100.0f;
        v4.z -= 100.0f;
        Draw_line3d(&v0, &v1, 0xFFFFFFFF, 0);
        Draw_line3d(&v0, &v2, 0xFFFFFFFF, 0);
        Draw_line3d(&v1, &v2, 0xFFFFFFFF, 0);
        Draw_line3d(&v3, &v4, 0xFFFFFFFF, 0);
        Draw_line3d(&v3, &v2, 0xFFFFFFFF, 0);
        Draw_line3d(&v4, &v2, 0xFFFFFFFF, 0);
        ps = e->pos;
        GetScreenPos(&ps, &sp);
        if (sp.z < 1.0f) {
            eprintf2(10, 16, (u32)sp.x - 20, (u32)sp.y + 16, 4, 0, "[%02x]", i);
        }
        if (e->type == 2) {
            if (prev == NULL) {
                first = e;
            }
            pp = prev;
            prev = e;
            if (prev != NULL && pp != NULL) {
                switch (pp->kind) {
                case 0:
                default:
                    col = 0xFFFFFFFF;
                    break;
                case 1:
                    col = 0xFF0000FF;
                    break;
                case 2:
                    col = 0xFFFF0000;
                    break;
                }
                Draw_line3d(&pp->pos, &e->pos, col, 0);
            }
        }
    }
    if (first != NULL && pp != NULL && prev != NULL) {
        switch (prev->kind) {
        case 0:
        default:
            col = 0xFFFFFFFF;
            break;
        case 1:
            col = 0xFF0000FF;
            break;
        case 2:
            col = 0xFFFF0000;
            break;
        }
        Draw_line3d(&prev->pos, &first->pos, col, 0);
    }
}
