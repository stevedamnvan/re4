// COARSE=1 (30 fps rethink, step 2): the coarse complete square. In-room play runs unchanged
// (enemies, events, HUD, audio); each image is drawn here from gameplay records instead of the
// source visual pipeline:
//   world    every live collision piece's front-facing polygons (SatMgr: the geometry gameplay walks
//            on and collides with) but its invisible walls (kSeeThrough), culled through the pieces'
//            XZ block trees, near-clipped, flat lit, fogged;
//   actors   the player, the partner and every drawn enemy in view as camera-facing ribbons along the
//            parent -> part segments of the gameplay skeleton (the part world matrices of the tick),
//            a blob under each;
//   effects  a billboard per live world-space effect (position, size and colour of the record).
// Trans() of such a tick runs its presentation stages in the qualified PACE_TRANS_SKIP mode (no
// model OT; effects queue only the draws that carry state), and Render() of the image replaces
// the world OTs (0 .. SUBSCRN_NEAR) with re4dc_coarse_draw(); effects, HUD, messages, filters and
// the letterbox keep their source OTs. Render() runs before the next tick's moves, so the records
// read here are the state of the image's own tick.
#include "global.h"
#include "player.h"
#include "pl_npc.h"
#include "em.h"
#include "atari.h"
#include "model.h"
#include "esp.h"
#include "espgen.h"
#include "camera.h"
#include "view.h"
#include <dc/matrix.h>
#include <dc/pvr.h>
#include <kos/timer.h>
#include <string.h>
#include <cstdint>

// <math.h> and dolphin/gx/GXGet.h clash with the game headers (math_sub.h, gx.h): declared here.
extern "C" void GXGetProjectionv(f32* p);                // platform/gx_stub.cpp
extern "C" void GXGetViewportv(f32* vp);
extern "C" std::uint32_t* re4dc_coarse_begin(int fog);   // platform/native_ui.cpp
extern "C" void re4dc_coarse_end(unsigned vertices);
extern "C" void re4dc_log(const char* fmt, ...);
extern "C" void* re4dc_ui_movie_texture() __attribute__((weak));   // ROUTE_MOVIES builds
extern "C" void re4dc_fog_note_far(float far) __attribute__((weak));   // NATIVE_FOG builds
extern "C" int ESP_IsActive(cEsp* esp);                             // esp.cpp (C linkage)

// Global scope: an extern "C" name defined inside the unnamed namespace links to a silent stub.
extern "C" {
int re4dc_coarse_image;   // Render(): the image being drawn is coarse (latched by Trans())
}

namespace {
constexpr float kNear = 40.0f;         // clip plane, mm in front of the eye
constexpr float kFar = 25000.0f;       // block cull distance (FOG_FAR: opaque fog there)
constexpr unsigned kSplit = 30000;     // vertices per header (native_ui's store-queue window)
constexpr unsigned kMaxPolys = 1u << 16;
unsigned char g_seen[kMaxPolys / 8];   // polygons of this piece already drawn (blocks overlap)
// Invisible walls. Collision walls are one-sided (the normal faces the side they hold back) and the
// game's line tests are too: the camera's (cameraHitCheck, from its target to the lens) only meets
// a wall it enters from the front. So nothing keeps a wall whose plane separates the lens (in
// front) from the player (behind) out of the view: one-way barriers are such walls (r101: piece 0
// polygon 690, attr 40000000, 0.5 m in front of the lens, covered the whole view and, the port's
// ClearZbuf being a GX sink, the HUD gauge's 3D digits too). Not drawn: back faces, walls with the
// player behind their plane, and walls the camera looks through by attribute (its scenery test:
// SatMgr.hitCheck flag 0x8000 mask 0x1C2810, which also passes attr 0x800000; attr 0x400: the
// camera-only bounds, seen by flag 0x8000 checks alone).
constexpr u32 kSeeThrough = 0x800000u | 0x1C2810u | 0x400u;

struct Stats {
    unsigned frames, pieces, blocks, polys, backs, hidden, tris, verts, clipped, actors, segments, effects, us;
    unsigned maxVerts, maxUs;
} g_st;

// ------------------------------------------------------------------ store-queue output
struct Out {
    std::uint32_t* sq;
    unsigned n;       // vertices under the current header
    unsigned total;   // vertices this image
};
inline std::uint32_t fbits(float f) { return __builtin_bit_cast(std::uint32_t, f); }
#if RE4DC_COARSE >= 2
// COARSE=2 probe: in the logged images every emitted triangle is tested against a few screen
// points; the nearest (largest 1/W') at each point is what the PVR shows there.
struct Probe {
    float x, y, z;
    char kind;       // W world, A actor segment, B blob, E effect
    unsigned a, b;   // W: piece, polygon; A / B: actor id, part; E: effect slot
};
Probe g_probe[6];
bool g_probing;
char g_kind;
unsigned g_ta, g_tb;
float g_px[2], g_py[2], g_pz[2];
unsigned g_pn;
void probe_tri(float x0, float y0, float z0, float x1, float y1, float z1, float x2, float y2, float z2)
{
    const float d = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (d == 0.0f) {
        return;
    }
    for (Probe& p : g_probe) {
        const float b1 = ((p.x - x0) * (y2 - y0) - (x2 - x0) * (p.y - y0)) / d;
        const float b2 = ((x1 - x0) * (p.y - y0) - (p.x - x0) * (y1 - y0)) / d;
        if (b1 < 0.0f || b2 < 0.0f || b1 + b2 > 1.0f) {
            continue;
        }
        const float z = z0 + b1 * (z1 - z0) + b2 * (z2 - z0);
        if (z > p.z) {
            p.z = z;
            p.kind = g_kind;
            p.a = g_ta;
            p.b = g_tb;
        }
    }
}
inline void tag(char kind, unsigned a, unsigned b)
{
    g_kind = kind;
    g_ta = a;
    g_tb = b;
}
// Attribute words of the candidate polygons of a probed image (floor or not): value -> count.
struct AttrCount {
    u32 attr;
    unsigned floor, other;
};
AttrCount g_attrs[40];
unsigned g_nattrs;
void note_attr(u32 attr, bool floor)
{
    unsigned i = 0;
    while (i < g_nattrs && g_attrs[i].attr != attr) {
        ++i;
    }
    if (i == g_nattrs) {
        if (g_nattrs == 40) {
            return;
        }
        g_attrs[g_nattrs++] = AttrCount{attr, 0, 0};
    }
    (floor ? g_attrs[i].floor : g_attrs[i].other)++;
}
#else
inline void tag(char, unsigned, unsigned) {}
#endif
inline void put(Out& o, std::uint32_t cmd, float x, float y, float z, std::uint32_t argb)
{
#if RE4DC_COARSE >= 2
    if (g_probing) {
        if (g_pn >= 2) {
            probe_tri(g_px[0], g_py[0], g_pz[0], g_px[1], g_py[1], g_pz[1], x, y, z);
        }
        g_px[0] = g_px[1];
        g_py[0] = g_py[1];
        g_pz[0] = g_pz[1];
        g_px[1] = x;
        g_py[1] = y;
        g_pz[1] = z;
        g_pn = cmd == PVR_CMD_VERTEX_EOL ? 0 : g_pn + 1;
    }
#endif
    std::uint32_t* d = o.sq;
    d[0] = cmd;
    d[1] = fbits(x);
    d[2] = fbits(y);
    d[3] = fbits(z);
    d[4] = 0;
    d[5] = 0;
    d[6] = argb;
    d[7] = 0;
    __asm__ __volatile__("pref @%0" : : "r"(d) : "memory");
    o.sq = d + 8;
    o.n++;
}
// Between strips: a new header before the store-queue window fills. False: stop drawing.
inline bool room(Out& o)
{
    if (o.n < kSplit) {
        return o.sq != nullptr;
    }
    re4dc_coarse_end(o.n);
    o.total += o.n;
    o.n = 0;
    o.sq = re4dc_coarse_begin(1);
    return o.sq != nullptr;
}

// ------------------------------------------------------------------ camera
// Screen rows as native_actor_fast.cpp screen_rows: X' Y' W' of a world point; the screen point
// is (X'/W', Y'/W') and the PVR depth 1/W' (GEQUAL).
float g_S[3][4];
float g_focal;                // 320 * P[1]: pixels per unit x at W' = 1
Vec g_eye, g_dir;             // eye and horizontal view direction (world)
Vec g_subject;                // the player's chest (the lens's subject), or the look-at point
float g_cosHalf, g_sinHalf;   // inflated horizontal half field of view
float g_n0x, g_n0z, g_n1x, g_n1z;   // inward side-plane normals (world XZ) through the eye

// Inward normals of the two side planes for a horizontal view direction (x, z).
inline void side_planes(float x, float z, float& n0x, float& n0z, float& n1x, float& n1z)
{
    n0x = x * g_sinHalf + z * g_cosHalf;
    n0z = z * g_sinHalf - x * g_cosHalf;
    n1x = x * g_sinHalf - z * g_cosHalf;
    n1z = z * g_sinHalf + x * g_cosHalf;
}

void setup_camera()
{
    CameraCurrentProjection();
    f32 P[7], V[6];
    GXGetProjectionv(P);
    GXGetViewportv(V);
    const float* m = &pG->Cam.v_mat[0][0];
    const float cx = (V[0] + V[2] * 0.5f) * 640.0f / V[2];
    const float cy = (V[1] + V[3] * 0.5f) * 480.0f / V[3];
    const float rows[3][3] = {{320.0f * P[1], 0.0f, 320.0f * P[2] - cx},
                              {0.0f, -240.0f * P[3], -240.0f * P[4] - cy},
                              {0.0f, 0.0f, -1.0f}};
    for (unsigned r = 0; r < 3; ++r) {
        for (unsigned c = 0; c < 4; ++c) {
            g_S[r][c] = rows[r][0] * m[c] + rows[r][1] * m[4 + c] + rows[r][2] * m[8 + c];
        }
    }
    g_focal = 320.0f * P[1];
    g_eye = pG->Cam.param.pos;
    float dx = pG->Cam.param.at.x - g_eye.x, dz = pG->Cam.param.at.z - g_eye.z;
    const float l = __builtin_sqrtf(dx * dx + dz * dz);
    if (l > 1e-3f) {
        dx /= l;
        dz /= l;
    } else {
        dx = 0.0f;
        dz = 1.0f;
    }
    g_dir.x = dx;
    g_dir.y = 0.0f;
    g_dir.z = dz;
    if (pPL) {
        g_subject = Vec{pPL->pos.x, pPL->pos.y + 1200.0f, pPL->pos.z};
    } else {
        g_subject = pG->Cam.param.at;
    }
    // P[1] = cot(fovx / 2): half = atan(1 / P[1]) + 0.21 rad (~12 degrees for the pitch of the
    // shoulder camera), by the angle sum.
    const float t = 1.0f / P[1];
    const float ca = 1.0f / __builtin_sqrtf(1.0f + t * t), sa = t * ca;
    g_cosHalf = ca * 0.978031f - sa * 0.208460f;
    g_sinHalf = sa * 0.978031f + ca * 0.208460f;
    side_planes(dx, dz, g_n0x, g_n0z, g_n1x, g_n1z);
}

// XMTRX = [rows; 0 0 0 1] (KOS matrix_t is column-major: mt[column][row]).
void load_rows(const float R[3][4])
{
    static matrix_t mt __attribute__((aligned(32)));
    for (unsigned c = 0; c < 4; ++c) {
        mt[c][0] = R[0][c];
        mt[c][1] = R[1][c];
        mt[c][2] = R[2][c];
        mt[c][3] = c == 3 ? 1.0f : 0.0f;
    }
    mat_load(&mt);
}

// R = S * [A; 0 0 0 1] (A: 3x4 affine, piece -> world)
void compose(const float A[3][4], float R[3][4])
{
    for (unsigned r = 0; r < 3; ++r) {
        for (unsigned c = 0; c < 4; ++c) {
            float v = g_S[r][0] * A[0][c] + g_S[r][1] * A[1][c] + g_S[r][2] * A[2][c];
            if (c == 3) {
                v += g_S[r][3];
            }
            R[r][c] = v;
        }
    }
}

struct H {
    float x, y, w;
};
inline H xf(const Vec& p)
{
    float x = p.x, y = p.y, z = p.z;
    mat_trans_single3_nodiv(x, y, z);
    return H{x, y, z};
}
// FSRRA (1 / sqrt, pipelined; FDIV is not): rsqrt(x), and 1 / w for w > 0 as rsqrt(w * w).
inline float rsqrt(float x)
{
    __asm__("fsrra %0" : "+f"(x));
    return x;
}
inline float rcp(float w) { return rsqrt(w * w); }

// ------------------------------------------------------------------ polygons
inline std::uint32_t shade(std::uint32_t rgb, float k)
{
    if (k < 0.0f) {
        k = 0.0f;
    }
    unsigned r = (unsigned) (((rgb >> 16) & 255) * k), g = (unsigned) (((rgb >> 8) & 255) * k),
             b = (unsigned) ((rgb & 255) * k);
    r = r > 255 ? 255 : r;
    g = g > 255 ? 255 : g;
    b = b > 255 ? 255 : b;
    return 0xFF000000u | (r << 16) | (g << 8) | b;
}

// A convex polygon (3 or 4 vertices, fan order), near-clipped against W' >= kNear, as one strip.
void emit_poly(Out& o, const H* v, unsigned n, std::uint32_t argb)
{
    if (n == 3 && v[0].w >= kNear && v[1].w >= kNear && v[2].w >= kNear) {
        const float i0 = rcp(v[0].w), i1 = rcp(v[1].w), i2 = rcp(v[2].w);
        put(o, PVR_CMD_VERTEX, v[0].x * i0, v[0].y * i0, i0, argb);
        put(o, PVR_CMD_VERTEX, v[1].x * i1, v[1].y * i1, i1, argb);
        put(o, PVR_CMD_VERTEX_EOL, v[2].x * i2, v[2].y * i2, i2, argb);
        g_st.tris++;
        return;
    }
    H c[8];
    unsigned m = 0;
    for (unsigned i = 0; i < n; ++i) {
        const H& a = v[i];
        const H& b = v[i + 1 == n ? 0 : i + 1];
        const bool ia = a.w >= kNear, ib = b.w >= kNear;
        if (ia) {
            c[m++] = a;
        }
        if (ia != ib) {
            const float t = (kNear - a.w) / (b.w - a.w);
            c[m++] = H{a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, kNear};
        }
    }
    if (m < 3) {
        return;
    }
    if (m != n) {
        g_st.clipped++;
    }
    // fan 0, 1, ..., m-1 as a strip: 0, 1, m-1, 2, m-2, ...
    const H* seq[8];
    unsigned k = 0, lo = 1, hi = m - 1;
    seq[k++] = &c[0];
    seq[k++] = &c[lo++];
    while (lo <= hi) {
        seq[k++] = &c[hi--];
        if (lo <= hi) {
            seq[k++] = &c[lo++];
        }
    }
    for (unsigned i = 0; i < k; ++i) {
        const float iw = rcp(seq[i]->w);
        put(o, i + 1 == k ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX, seq[i]->x * iw, seq[i]->y * iw, iw, argb);
    }
    g_st.tris += k - 2;
}

// ------------------------------------------------------------------ world (collision pieces)
struct PieceView {
    Vec eye;                    // eye in piece space
    Vec subject;                // g_subject in piece space
    Vec dir;                    // horizontal view direction in piece space
    float n0x, n0z, n1x, n1z;   // inward side-plane normals (XZ) through the eye
};

bool block_visible(const PieceView& pv, const cSatBlock* b)
{
    const float x0 = b->min.x, z0 = b->min.z, x1 = x0 + b->m_Size.x, z1 = z0 + b->m_Size.z;
    const float dx = pv.eye.x < x0 ? x0 - pv.eye.x : pv.eye.x > x1 ? pv.eye.x - x1 : 0.0f;
    const float dz = pv.eye.z < z0 ? z0 - pv.eye.z : pv.eye.z > z1 ? pv.eye.z - z1 : 0.0f;
    if (dx * dx + dz * dz > kFar * kFar) {
        return false;
    }
    if (dx == 0.0f && dz == 0.0f) {
        return true;   // the eye is over the block
    }
    const float xs[4] = {x0, x1, x1, x0}, zs[4] = {z0, z0, z1, z1};
    int behind = 0, out0 = 0, out1 = 0;
    for (int i = 0; i < 4; ++i) {
        const float rx = xs[i] - pv.eye.x, rz = zs[i] - pv.eye.z;
        behind += rx * pv.dir.x + rz * pv.dir.z < -1500.0f;
        out0 += rx * pv.n0x + rz * pv.n0z < -800.0f;
        out1 += rx * pv.n1x + rz * pv.n1z < -800.0f;
    }
    return behind < 4 && out0 < 4 && out1 < 4;
}

unsigned g_piece;   // SatMgr index of the piece being drawn (COARSE=2 probe tags)

void draw_block_polys(Out& o, cSat* sat, const cSatBlock* b, const PieceView& pv, const float N[3][3])
{
    const unsigned n = (unsigned) b->m_nFloor + b->m_nSlope + b->m_nWall;
    const u16* idx = b->idx;
    for (unsigned i = 0; i < n; ++i) {
        const unsigned no = idx[i];
        if (no >= kMaxPolys) {
            continue;
        }
        const unsigned char bit = (unsigned char) (1u << (no & 7));
        if (g_seen[no >> 3] & bit) {
            continue;
        }
        g_seen[no >> 3] |= bit;
        const AtPoly& p = sat->poly_p[no];
        // the world normal (rotation part of the piece matrix): the class and the flat light
        const Vec& pn = sat->norm_p[p.n];
        const Vec& a = sat->vtx[p.v[0]];
        if (pn.x * (pv.eye.x - a.x) + pn.y * (pv.eye.y - a.y) + pn.z * (pv.eye.z - a.z) <= 0.0f) {
            g_st.backs++;
            continue;   // the eye sees its back
        }
        const float ny = N[1][0] * pn.x + N[1][1] * pn.y + N[1][2] * pn.z;
#if RE4DC_COARSE >= 2
        if (g_probing) {
            note_attr(p.attr, ny > 0.7f);
        }
#endif
        if (ny <= 0.7f && ((p.attr & kSeeThrough) ||
                           pn.x * (pv.subject.x - a.x) + pn.y * (pv.subject.y - a.y) + pn.z * (pv.subject.z - a.z) < 0.0f)) {
            g_st.hidden++;
            continue;   // invisible wall: see-through by attribute, or the player behind its plane
        }
        g_st.polys++;
        H v[3];
        v[0] = xf(a);
        v[1] = xf(sat->vtx[p.v[1]]);
        v[2] = xf(sat->vtx[p.v[2]]);
        if (v[0].w < kNear && v[1].w < kNear && v[2].w < kNear) {
            continue;
        }
        if (!room(o)) {
            return;
        }
        const float nx = N[0][0] * pn.x + N[0][1] * pn.y + N[0][2] * pn.z;
        const float nz = N[2][0] * pn.x + N[2][1] * pn.y + N[2][2] * pn.z;
        // the village's tones (fog 716C5A): the HUD gauge is a translucent lens over the view, and
        // its unlit LCD segments show against a light one
        std::uint32_t base;
        if (ny > 0.7f) {
            base = 0x5C5240;   // floors: earth
        } else if (ny < -0.7f) {
            base = 0x443C36;   // ceilings, undersides
        } else {
            base = 0x70685C;   // walls
        }
        const float d = nx * 0.42f + ny * 0.78f + nz * 0.46f;
        tag('W', g_piece, no);
        emit_poly(o, v, 3, shade(base, 0.42f + 0.58f * (d > 0.0f ? d : -0.35f * d)));
    }
}

void draw_blocks(Out& o, cSat* sat, const cSatBlock* b, const PieceView& pv, const float N[3][3])
{
    for (; b; b = b->next) {
        if (!block_visible(pv, b)) {
            continue;
        }
        g_st.blocks++;
        if (b->m_Flag & 1) {
            draw_blocks(o, sat, (const cSatBlock*) b->idx, pv, N);
        } else {
            draw_block_polys(o, sat, b, pv, N);
        }
    }
}

void draw_world(Out& o)
{
    for (u32 i = 0; i < SatMgr.nArray; ++i) {
        cSat* sat = (cSat*) ((u8*) SatMgr.pArray + SatMgr.size * i);
        if (!sat->isAlive() || !sat->block_p || !sat->poly_p) {
            continue;
        }
        g_st.pieces++;
        g_piece = i;
        PieceView pv;
        PSMTXMultVec(sat->imat, &g_eye, &pv.eye);
        PSMTXMultVec(sat->imat, &g_subject, &pv.subject);
        PSMTXMultVecSR(sat->imat, &g_dir, &pv.dir);
        pv.n0x = pv.dir.x * g_sinHalf + pv.dir.z * g_cosHalf;
        pv.n0z = pv.dir.z * g_sinHalf - pv.dir.x * g_cosHalf;
        pv.n1x = pv.dir.x * g_sinHalf - pv.dir.z * g_cosHalf;
        pv.n1z = pv.dir.z * g_sinHalf + pv.dir.x * g_cosHalf;
        const unsigned bytes = (sat->polygon_num + 7u) / 8u;
        memset(g_seen, 0, bytes < sizeof(g_seen) ? bytes : sizeof(g_seen));
        float R[3][4];
        compose(sat->mat, R);
        load_rows(R);
        float N[3][3];
        for (int r = 0; r < 3; ++r) {
            for (int c = 0; c < 3; ++c) {
                N[r][c] = sat->mat[r][c];
            }
        }
        draw_blocks(o, sat, sat->block_p, pv, N);
    }
}

// ------------------------------------------------------------------ actors
// A bone as a camera-facing ribbon: the two joints projected (2 transforms), widened across the
// screen direction of the bone by the limb half-thickness t at each end's depth (at least 0.75 px),
// lit side to shaded side across the width (a cylinder's look), one 4-vertex strip.
void segment(Out& o, const Vec& a, const Vec& b, float t, std::uint32_t rgb)
{
    const float dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z;
    const float len2 = dx * dx + dy * dy + dz * dz;
    if (len2 < 60.0f * 60.0f || len2 > 1600.0f * 1600.0f) {
        return;   // face / finger bones: a cluster of squares at limb width
    }
    const float tl = 0.3f * len2 * rsqrt(len2);   // no wider than 0.3 x the bone
    t = t < tl ? t : tl;
    const H ha = xf(a), hb = xf(b);
    if (ha.w < kNear || hb.w < kNear || !room(o)) {
        return;
    }
    const float ia = rcp(ha.w), ib = rcp(hb.w);
    const float ax = ha.x * ia, ay = ha.y * ia, bx = hb.x * ib, by = hb.y * ib;
    float px = ay - by, py = bx - ax;
    const float pl2 = px * px + py * py;
    if (pl2 > 1e-4f) {
        const float il = rsqrt(pl2);
        px *= il;
        py *= il;
    } else {
        px = 1.0f;   // the bone points at the eye: a square of the half width
        py = 0.0f;
    }
    float wa = t * g_focal * ia, wb = t * g_focal * ib;
    wa = wa < 0.75f ? 0.75f : wa;
    wb = wb < 0.75f ? 0.75f : wb;
    const float k = 0.62f + 0.38f * (dy * dy) * rsqrt(len2 * len2);   // upright limbs catch more light
    const std::uint32_t lit = shade(rgb, k * 1.15f), dark = shade(rgb, k * 0.62f);
    put(o, PVR_CMD_VERTEX, ax + px * wa, ay + py * wa, ia, lit);
    put(o, PVR_CMD_VERTEX, ax - px * wa, ay - py * wa, ia, dark);
    put(o, PVR_CMD_VERTEX, bx + px * wb, by + py * wb, ib, lit);
    put(o, PVR_CMD_VERTEX_EOL, bx - px * wb, by - py * wb, ib, dark);
    g_st.tris += 2;
    g_st.segments++;
}

// Actor bounding sphere (0.9 m above its position, radius 2 m) against the view: distance, behind
// the eye, outside a side plane.
bool actor_visible(const cModel* m)
{
    const float r = 2000.0f;
    const float rx = m->pos.x - g_eye.x, rz = m->pos.z - g_eye.z;
    if (rx * rx + rz * rz > (kFar + r) * (kFar + r)) {
        return false;
    }
    return rx * g_dir.x + rz * g_dir.z > -r && rx * g_n0x + rz * g_n0z > -r && rx * g_n1x + rz * g_n1z > -r;
}

void blob(Out& o, const Vec& at, float r)
{
    const Vec q[4] = {{at.x - r, at.y + 8.0f, at.z - r}, {at.x + r, at.y + 8.0f, at.z - r},
                      {at.x + r, at.y + 8.0f, at.z + r}, {at.x - r, at.y + 8.0f, at.z + r}};
    H v[4];
    for (int i = 0; i < 4; ++i) {
        v[i] = xf(q[i]);
    }
    if (room(o)) {
        emit_poly(o, v, 4, 0xFF1C1814);
    }
}

void draw_model(Out& o, cModel* m, std::uint32_t rgb, float t)
{
    if (!actor_visible(m)) {
        return;
    }
    g_st.actors++;
    for (cParts* p = m->pList; p; p = p->pList) {
        if (p->motParts.flags & 2) {
            continue;   // no world matrix this tick (partsWorldCalc skipped it)
        }
        const cCoord* q = p->pParent;
        if (!q || q == (const cCoord*) m) {
            continue;
        }
        const Vec a = {q->mat[0][3], q->mat[1][3], q->mat[2][3]};
        const Vec b = {p->mat[0][3], p->mat[1][3], p->mat[2][3]};
        tag('A', m->id, 0);
        segment(o, a, b, t, rgb);
    }
    tag('B', m->id, 0);
    blob(o, m->pos, 330.0f);
}

void draw_actors(Out& o)
{
    load_rows(g_S);
    cModel* pl = pPL;
    cModel* sub = pSUB;
    if (pl && (pl->be_flag & 3) == 3) {
        draw_model(o, pl, 0x2F4F9A, 42.0f);
    }
    if (sub && (sub->be_flag & 3) == 3) {
        draw_model(o, sub, 0xC89A3C, 38.0f);
    }
    for (cEm* e = EmMgr.pAlive; e; e = (cEm*) e->pNext) {
        cModel* m = e;
        if (m == pl || m == sub || (m->be_flag & 3) != 3) {
            continue;
        }
        const bool ganado = m->id >= 0x10 && m->id <= 0x20;
        draw_model(o, m, ganado ? 0x8A5A3A : 0x707070, ganado ? 44.0f : 60.0f);
    }
}

// ------------------------------------------------------------------ effects
inline unsigned byte255(float v) { return v <= 0.0f ? 0u : v >= 255.0f ? 255u : (unsigned) v; }

void draw_effects(Out& o)
{
    cEspSystem* sys = g_pEspSys;
    if (!sys || !sys->pEspBuf) {
        return;
    }
    for (u32 i = 0; i < sys->nEsp; i++) {
        cEsp* e = (cEsp*) (sys->pEspBuf + i * 0x150);
        if (!(e->m_Be_flg & 1) || !ESP_IsActive(e)) {
            continue;
        }
        if ((u8) (e->m_Parts_no + 8) <= 5) {
            continue;   // screen sprite (Parts_no 0xF8 .. 0xFD)
        }
        if (e->m_Col_a < 64.0f) {
            continue;   // faint (ambient haze, fading smoke): opaque here, it would hide the view
        }
        Vec w;
        if (e->parent && e->parent != pEffParentWorld) {
            PSMTXMultVec(e->parent->mat, &e->m_Pos, &w);
        } else {
            w = e->m_Pos;
        }
        const H c = xf(w);
        if (c.w < 300.0f || !room(o)) {
            continue;   // at the lens: a full-screen square
        }
        const float s = e->m_Size_base_x * e->m_Size_mul;
        const float iw = rcp(c.w);
        float r = s * g_focal * iw * 0.5f;
        r = r < 1.5f ? 1.5f : r > 32.0f ? 32.0f : r;   // opaque: a marker, never a screen cover
        const float sx = c.x * iw, sy = c.y * iw;
        const std::uint32_t argb =
            0xFF000000u | (byte255(e->m_Col_r) << 16) | (byte255(e->m_Col_g) << 8) | byte255(e->m_Col_b);
        tag('E', i, 0);
        put(o, PVR_CMD_VERTEX, sx - r, sy + r, iw, argb);
        put(o, PVR_CMD_VERTEX, sx - r, sy - r, iw, argb);
        put(o, PVR_CMD_VERTEX, sx + r, sy + r, iw, argb);
        put(o, PVR_CMD_VERTEX_EOL, sx + r, sy - r, iw, argb);
        g_st.tris += 2;
        g_st.effects++;
    }
}
}  // namespace

// Trans() of tick k: 1 in in-room play (the pace.cpp context: Rno0 3, no held picture or room
// change, no sub screen, no movie), where the presentation stages run in the qualified skip mode.
// Latches whether image k (drawn by iteration k+1) is coarse: every such image not dropped.
extern "C" int re4dc_coarse_tick(int dropped)
{
    int ctx = pG && pG->Rno0 == 3 && !(pG->System_flg & (0x400 | 0x100000)) && !(pG->Status_flg[2] & 0x04000000);
    if (ctx && re4dc_ui_movie_texture && re4dc_ui_movie_texture()) {
        ctx = 0;
    }
    re4dc_coarse_image = ctx && !dropped;
    return ctx;
}

// Render() of a coarse image: the whole opaque view, before the effect / HUD OTs.
extern "C" void re4dc_coarse_draw(void)
{
    if (!pG || !SatMgr.pArray) {
        return;
    }
    const std::uint64_t t0 = timer_us_gettime64();
    Out o{re4dc_coarse_begin(1), 0, 0};
    if (!o.sq) {
        return;
    }
    if (re4dc_fog_note_far) {
        re4dc_fog_note_far(View._zfar);   // as a native model draw would: the fog table's far (FOG_FAR)
    }
    setup_camera();
#if RE4DC_COARSE >= 2
    // COARSE=2 (diagnostic): the first images log the camera, Leon's projected root and the first
    // world triangle (native_ui logs the stream state at re4dc_coarse_begin).
    static unsigned dbg;
    if (dbg < 4 || dbg % 600 == 0) {
        load_rows(g_S);
        re4dc_log("COARSE2 n=%u eye %.0f %.0f %.0f dir %.3f %.3f focal %.1f S2 %.4f %.4f %.4f %.1f\n", dbg, g_eye.x,
                  g_eye.y, g_eye.z, g_dir.x, g_dir.z, g_focal, g_S[2][0], g_S[2][1], g_S[2][2], g_S[2][3]);
        if (pPL) {
            const Vec r = {pPL->pos.x, pPL->pos.y + 1000.0f, pPL->pos.z};
            const H h = xf(r);
            re4dc_log("COARSE2 leon %.0f %.0f %.0f -> screen %.1f %.1f w %.1f\n", r.x, r.y, r.z, h.x / h.w, h.y / h.w, h.w);
        }
        for (u32 i = 0; i < SatMgr.nArray; ++i) {
            cSat* sat = (cSat*) ((u8*) SatMgr.pArray + SatMgr.size * i);
            if (!sat->isAlive() || !sat->poly_p) {
                continue;
            }
            const float(*M)[4] = sat->mat;
            re4dc_log("COARSE2 piece %u polys %u mat %.3f %.3f %.3f %.0f | %.3f %.3f %.3f %.0f | %.3f %.3f %.3f %.0f\n", i,
                      sat->polygon_num, M[0][0], M[0][1], M[0][2], M[0][3], M[1][0], M[1][1], M[1][2], M[1][3],
                      M[2][0], M[2][1], M[2][2], M[2][3]);
        }
        static const float pts[6][2] = {{320, 240}, {120, 120}, {520, 120}, {120, 360}, {520, 360}, {320, 400}};
        for (unsigned i = 0; i < 6; ++i) {
            g_probe[i] = Probe{pts[i][0], pts[i][1], 0.0f, '-', 0, 0};
        }
        g_pn = 0;
        g_nattrs = 0;
        g_probing = true;
    }
    ++dbg;
#endif
    draw_world(o);
    draw_actors(o);
    draw_effects(o);
    if (o.sq) {
        re4dc_coarse_end(o.n);
    }
#if RE4DC_COARSE >= 2
    if (g_probing) {
        g_probing = false;
        for (const Probe& p : g_probe) {
            re4dc_log("COARSE2 probe %.0f %.0f: %c %u %u z %.3g W' %.0f\n", p.x, p.y, p.kind, p.a, p.b, p.z,
                      p.z > 0.0f ? 1.0f / p.z : 0.0f);
            if (p.kind != 'W') {
                continue;
            }
            cSat* sat = (cSat*) ((u8*) SatMgr.pArray + SatMgr.size * p.a);
            const AtPoly& q = sat->poly_p[p.b];
            Vec w[3];
            for (int k = 0; k < 3; ++k) {
                PSMTXMultVec(sat->mat, &sat->vtx[q.v[k]], &w[k]);
            }
            const Vec& n = sat->norm_p[q.n];
            re4dc_log("COARSE2   poly %.0f %.0f %.0f | %.0f %.0f %.0f | %.0f %.0f %.0f n %.2f %.2f %.2f attr %08x\n", w[0].x,
                      w[0].y, w[0].z, w[1].x, w[1].y, w[1].z, w[2].x, w[2].y, w[2].z, n.x, n.y, n.z, (unsigned) q.attr);
        }
        for (unsigned i = 0; i < g_nattrs; ++i) {
            re4dc_log("COARSE2 attr %08x floor %u other %u%s\n", (unsigned) g_attrs[i].attr, g_attrs[i].floor,
                      g_attrs[i].other, (g_attrs[i].attr & kSeeThrough) ? " see-through" : "");
        }
    }
#endif
    o.total += o.n;
    const unsigned us = (unsigned) (timer_us_gettime64() - t0);
    g_st.frames++;
    g_st.verts += o.total;
    g_st.us += us;
    g_st.maxVerts = o.total > g_st.maxVerts ? o.total : g_st.maxVerts;
    g_st.maxUs = us > g_st.maxUs ? us : g_st.maxUs;
    if (g_st.frames == 120) {
        const unsigned f = g_st.frames;
        re4dc_log("COARSE t=%u frames=%u pieces=%u blocks=%u polys=%u backs=%u hidden=%u tris=%u verts=%u/%u clipped=%u actors=%u seg=%u fx=%u us=%u/%u\n",
                  (unsigned) pG->Frame_cnt, f, g_st.pieces / f, g_st.blocks / f, g_st.polys / f, g_st.backs / f,
                  g_st.hidden / f, g_st.tris / f, g_st.verts / f, g_st.maxVerts, g_st.clipped / f,
                  g_st.actors / f, g_st.segments / f, g_st.effects / f, g_st.us / f, g_st.maxUs);
        g_st = Stats();
    }
}
