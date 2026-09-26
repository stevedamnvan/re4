// COARSE_WORLD (lane wd, test knob): the coarse view's world beyond the flat collision pieces, drawn from
// read-only room data prepared offline (coarse_world.h, generated from private assets; never committed).
// Nothing here is written by gameplay; doors stay their own collision pieces (drawn by coarse.cpp, they
// move with the game).
//   bit 1  house shells: each house BIN of the room (the Standard set's houses; r101's well, BIN 45, is a
//          landmark and never shelled) as its baked render shell (bl_house_shell.py, 400 / 200 faces, a
//          128 x 128 VQ bake with each face's flat light in it), placed by the room SMD, in place of the
//          collision polygons of its outer surfaces (coarse.cpp skips those by coarse_world.h kSkip).
//   bit 2  ground: the collision floors that have the source ground over them, in 6.4 m chunks cut at
//          3.2 m cells, a colour per vertex from the source ground there and one grey detail texture
//          repeating per cell, in place of those floors (kSkipGround).
//   bit 4  sky: the room's sky dome (BIN 0, tex 1 clouds), unfogged, fading into the fog colour towards
//          the horizon (vertex offset colour); game30.mk makes the PVR background the fog colour.
//   bit 8  trees: every tree of the Standard impostor records as its atlas quad (camera-facing, the cell
//          by the eye's azimuth in the tree's frame), queued here and sent in the punch-through list by
//          re4dc_coarse_world_flush() (native_ui re4dc_model_finish_source_draws, after the OP pass).
// Shells: a facing group the eye sees wholly from behind is skipped by one test, a group whose bounding
// sphere is outside a side of the view (a screen edge or the near plane) by another; a group wholly in front
// of the near plane goes out as its strips, each vertex transformed as it goes (16-bit UVs, white: the
// PVR culls the back faces among them); a group across the plane goes out strip by strip (a strip wholly
// outside one side of the view skipped), a strip with a vertex behind the plane triangle by triangle,
// near-clipped with its UVs. Ground chunks: vertices
// transformed once, pieces (convex, wound up) out as strips, near-clipped the same way. Sky: vertices
// transformed and packed once, triangles out as they are or near-clipped. A triangle or piece that needs
// the clip, or a sky triangle, is first dropped when all its vertices are outside one side of the view
// (the 640 x 480 screen or the near plane, in homogeneous coordinates).
#include "coarse_scene.h"
#include "coarse_world.h"
#include "native_model.h"
#include <dc/matrix.h>
#include <dc/pvr.h>
#include <kos/timer.h>
#include <cstdint>

extern "C" std::uint32_t* re4dc_coarse_begin_mode(unsigned crc, unsigned fnv, unsigned width, unsigned height,
                                                  unsigned mode);   // platform/native_ui.cpp
extern "C" void re4dc_coarse_end(unsigned vertices);
extern "C" void re4dc_log(const char* fmt, ...);
#if RE4DC_COARSE_WORLD & 8
extern "C" unsigned re4dc_ui_frame();
extern "C" int re4dc_model_pt_begin(unsigned crc, unsigned fnv, unsigned width, unsigned height, int fog,
                                    Re4dcModelPacket* out);   // TREE_IMPOSTOR (native_ui.cpp)
#endif

namespace {
using namespace coarse_world;
constexpr float kNear = 40.0f;   // as coarse.cpp
constexpr unsigned kModeFog = 1, kModeRepeat = 2, kModeOffset = 4, kModeCullPos = 8, kModeCullNeg = 16,
                   kModeUV16 = 32;
constexpr std::uint32_t kWhite = 0xFFFFFFFFu;

struct Stats {
    unsigned shells, tris, near, groupsCulled, vtxCulled, groupsOff, chunks, gtris, sky, trees, clipped, offscreen,
        verts, us, rejects;
} g_st;

inline std::uint32_t fbits(float f) { return __builtin_bit_cast(std::uint32_t, f); }
inline float bitsf(std::uint32_t u) { return __builtin_bit_cast(float, u); }
inline float rsqrt(float x)
{
    __asm__("fsrra %0" : "+f"(x));
    return x;
}
inline float rcp(float w) { return rsqrt(w * w); }
inline std::uint32_t uv16(float u, float v) { return (fbits(u) & 0xFFFF0000u) | (fbits(v) >> 16); }

struct Emit {
    std::uint32_t* sq;
    unsigned n;
};
inline void put(Emit& o, std::uint32_t cmd, float x, float y, float z, std::uint32_t w4, std::uint32_t w5,
                std::uint32_t argb, std::uint32_t oargb)
{
    std::uint32_t* d = o.sq;
    d[0] = cmd;
    d[1] = fbits(x);
    d[2] = fbits(y);
    d[3] = fbits(z);
    d[4] = w4;
    d[5] = w5;
    d[6] = argb;
    d[7] = oargb;
    __asm__ __volatile__("pref @%0" : : "r"(d) : "memory");
    o.sq = d + 8;
    o.n++;
}

// XMTRX = [S * [I | lo]; 0 0 0 1]: positions relative to lo go through as they are.
void load_rows(const CoarseView& v, const float lo[3])
{
    static matrix_t mt __attribute__((aligned(32)));
    for (unsigned r = 0; r < 3; ++r) {
        mt[0][r] = v.S[r][0];
        mt[1][r] = v.S[r][1];
        mt[2][r] = v.S[r][2];
        mt[3][r] = v.S[r][3] + v.S[r][0] * lo[0] + v.S[r][1] * lo[1] + v.S[r][2] * lo[2];
    }
    mt[0][3] = mt[1][3] = mt[2][3] = 0.0f;
    mt[3][3] = 1.0f;
    mat_load(&mt);
}

#if RE4DC_COARSE_WORLD & 3
// A world box against the view: beyond the far plane, behind the eye, outside a side plane.
bool box_visible(const CoarseView& v, const float lo[3], const float hi[3])
{
    const float x0 = lo[0], z0 = lo[2], x1 = hi[0], z1 = hi[2];
    const float ex = v.eye[0], ez = v.eye[2];
    const float dx = ex < x0 ? x0 - ex : ex > x1 ? ex - x1 : 0.0f;
    const float dz = ez < z0 ? z0 - ez : ez > z1 ? ez - z1 : 0.0f;
    if (dx * dx + dz * dz > v.far * v.far) {
        return false;
    }
    if (dx == 0.0f && dz == 0.0f) {
        return true;
    }
    const float xs[4] = {x0, x1, x1, x0}, zs[4] = {z0, z0, z1, z1};
    int behind = 0, out0 = 0, out1 = 0, beyond = 0;
    for (int i = 0; i < 4; ++i) {
        const float rx = xs[i] - ex, rz = zs[i] - ez;
        const float depth = rx * v.dir[0] + rz * v.dir[1];
        behind += depth < -1500.0f;
        beyond += depth > v.far + 1500.0f;
        out0 += rx * v.n0[0] + rz * v.n0[1] < -800.0f;
        out1 += rx * v.n1[0] + rz * v.n1[1] < -800.0f;
    }
    return behind < 4 && beyond < 4 && out0 < 4 && out1 < 4;
}
#endif

// ------------------------------------------------------------------ near-plane clip
// A clip vertex: X' Y' W', UV, base and offset colour channels (A R G B).
struct CV {
    float x, y, w, u, v, c[4], s[4];
};
inline std::uint32_t argb_of(const float* c)
{
    return ((std::uint32_t) c[0] << 24) | ((std::uint32_t) c[1] << 16) | ((std::uint32_t) c[2] << 8) | (std::uint32_t) c[3];
}
inline void unpack(std::uint32_t argb, float* c)
{
    c[0] = (float) (argb >> 24);
    c[1] = (float) ((argb >> 16) & 0xFFu);
    c[2] = (float) ((argb >> 8) & 0xFFu);
    c[3] = (float) (argb & 0xFFu);
}
// strip order of a convex polygon given in fan order (0 1 n-1 2 n-2 ...): keeps every triangle's winding
inline unsigned zig(unsigned n, unsigned k) { return k == 0 ? 0 : (k & 1) ? (k + 1) >> 1 : n - (k >> 1); }

// The sides of the view a vertex (X' Y' W', screen = X' / W') is outside of: the screen's four edges and
// the near plane, each a half-space in homogeneous coordinates (so valid behind the eye too). A polygon
// whose vertices share a bit is wholly outside the view.
inline unsigned outcode(float x, float y, float w)
{
    return (unsigned) (x < 0.0f) | (unsigned) (x > 640.0f * w) << 1 | (unsigned) (y < 0.0f) << 2 |
           (unsigned) (y > 480.0f * w) << 3 | (unsigned) (w < kNear) << 4;
}

enum ClipKind { kClipUV16, kClipUV32, kClipUV32Offset };
// A convex polygon (fan order) near-clipped against W' >= kNear, out as one strip. The clip keeps the
// winding, so the PVR cull still sees it as authored. kClipUV16: white (the colours are not read),
// kClipUV32: base colour, kClipUV32Offset: base and offset colours.
template <ClipKind kind>
void emit_poly_clip(Emit& o, const CV* in, unsigned n)
{
    CV c[10];
    unsigned m = 0;
    for (unsigned i = 0; i < n; ++i) {
        const CV& a = in[i];
        const CV& b = in[i + 1 == n ? 0 : i + 1];
        const bool ia = a.w >= kNear, ib = b.w >= kNear;
        if (ia) {
            c[m++] = a;
        }
        if (ia != ib) {
            const float t = (kNear - a.w) / (b.w - a.w);
            CV& r = c[m++];
            r.x = a.x + (b.x - a.x) * t;
            r.y = a.y + (b.y - a.y) * t;
            r.w = kNear;
            r.u = a.u + (b.u - a.u) * t;
            r.v = a.v + (b.v - a.v) * t;
            if (kind != kClipUV16) {
                for (unsigned k = 0; k < 4; ++k) {
                    r.c[k] = a.c[k] + (b.c[k] - a.c[k]) * t;
                }
            }
            if (kind == kClipUV32Offset) {
                for (unsigned k = 0; k < 4; ++k) {
                    r.s[k] = a.s[k] + (b.s[k] - a.s[k]) * t;
                }
            }
        }
    }
    if (m < 3) {
        return;
    }
    for (unsigned k = 0; k < m; ++k) {
        const CV& q = c[zig(m, k)];
        const float iw = rcp(q.w);
        const std::uint32_t cmd = k + 1 == m ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
        if (kind == kClipUV16) {
            put(o, cmd, q.x * iw, q.y * iw, iw, uv16(q.u, q.v), 0, kWhite, 0);
        } else {
            put(o, cmd, q.x * iw, q.y * iw, iw, fbits(q.u), fbits(q.v), argb_of(q.c),
                kind == kClipUV32Offset ? argb_of(q.s) : 0);
        }
    }
    g_st.clipped++;
}

#if RE4DC_COARSE_WORLD & 1
// ------------------------------------------------------------------ house shells
union SqVertex {   // one PVR vertex in the store queue (float words stored as floats)
    std::uint32_t u[8];
    float f[8];
};
constexpr std::uint32_t kCmd[2] = {PVR_CMD_VERTEX, PVR_CMD_VERTEX_EOL};

// A group wholly in front of the near plane: each strip vertex (position << 1 | end of strip) transformed
// as it goes out, with its packed UV.
std::uint32_t* emit_group(std::uint32_t* d, const unsigned short (*P)[3], const unsigned short* sp,
                          const unsigned* uv, unsigned n)
{
    for (unsigned i = 0; i < n; ++i) {
        const unsigned w = sp[i];
        const unsigned short* q = P[w >> 1];
        float x = (float) q[0], y = (float) q[1], z = (float) q[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        SqVertex* o = reinterpret_cast<SqVertex*>(d);
        o->u[0] = kCmd[w & 1u];
        o->f[1] = x * iw;
        o->f[2] = y * iw;
        o->f[3] = iw;
        o->u[4] = uv[i];
        o->u[5] = 0;
        o->u[6] = kWhite;
        o->u[7] = 0;
        __asm__ __volatile__("pref @%0" : : "r"(d) : "memory");
        d += 8;
    }
    return d;
}

union SV {   // one strip vertex of the group being clipped: screen x, y, 1 / W' (valid when W' >= kNear), W'
    struct {
        float sx, sy, iw, w, x, y;   // and X' Y' for the clip
        unsigned oc;                 // outcode
    } v;
    std::uint32_t u[7];
};
SV g_sv[kMaxGroupVtx];

inline std::uint32_t* put_sv(std::uint32_t* d, std::uint32_t cmd, const SV& q, std::uint32_t uv)
{
    d[0] = cmd;
    d[1] = q.u[0];
    d[2] = q.u[1];
    d[3] = q.u[2];
    d[4] = uv;
    d[5] = 0;
    d[6] = kWhite;
    d[7] = 0;
    __asm__ __volatile__("pref @%0" : : "r"(d) : "memory");
    return d + 8;
}

// A group across the near plane: its strip vertices transformed into g_sv, then a strip wholly in front
// goes out as it is, else triangle by triangle (wholly in front: as it is; across: near-clipped).
void emit_group_near(Emit& o, const CoarseView& v, const Shell& s, const unsigned short* sp, const unsigned* uv,
                     unsigned nvtx)
{
    const unsigned short(*P)[3] = kPos + s.pos;
    for (unsigned i = 0; i < nvtx; ++i) {
        const unsigned short* q = P[sp[i] >> 1];
        float x = (float) q[0], y = (float) q[1], z = (float) q[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        SV& t = g_sv[i];
        t.v.sx = x * iw;
        t.v.sy = y * iw;
        t.v.iw = iw;
        t.v.w = z;
        t.v.x = x;
        t.v.y = y;
        t.v.oc = outcode(x, y, z);
    }
    std::uint32_t* d = o.sq;
    unsigned j = 0;
    while (j < nvtx) {
        unsigned n = 1, all = g_sv[j].v.oc, any = all;
        while (!(sp[j + n - 1] & 1u)) {
            const unsigned oc = g_sv[j + n].v.oc;
            all &= oc;
            any |= oc;
            ++n;
        }
        const SV* t = g_sv + j;
        const unsigned* uu = uv + j;
        if (all) {
            g_st.offscreen++;
        } else if (!(any & 0x10u)) {
            for (unsigned k = 0; k < n; ++k) {
                d = put_sv(d, kCmd[k + 1 == n], t[k], uu[k]);
            }
            o.n += n;
            g_st.tris += n - 2;
        } else {
            for (unsigned k = 0; k + 2 < n; ++k) {
                // strip triangle k in its authored winding (the odd ones are stored reversed)
                const unsigned a = k + (k & 1), b = k + 1 - (k & 1), c = k + 2;
                const unsigned oa = t[a].v.oc, ob = t[b].v.oc, oc = t[c].v.oc;
                if (oa & ob & oc) {   // outside one side of the view (wholly behind the near plane included)
                    g_st.offscreen++;
                    continue;
                }
                if (!((oa | ob | oc) & 0x10u)) {
                    d = put_sv(d, PVR_CMD_VERTEX, t[a], uu[a]);
                    d = put_sv(d, PVR_CMD_VERTEX, t[b], uu[b]);
                    d = put_sv(d, PVR_CMD_VERTEX_EOL, t[c], uu[c]);
                    o.n += 3;
                    g_st.tris++;
                    continue;
                }
                // across the plane: skip it if the eye sees its back (the world plane), else clip it
                const unsigned short* p0 = P[sp[j + a] >> 1];
                const unsigned short* p1 = P[sp[j + b] >> 1];
                const unsigned short* p2 = P[sp[j + c] >> 1];
                const float ax = (float) p1[0] - p0[0], ay = (float) p1[1] - p0[1], az = (float) p1[2] - p0[2];
                const float bx = (float) p2[0] - p0[0], by = (float) p2[1] - p0[1], bz = (float) p2[2] - p0[2];
                const float nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
                const float ex = v.eye[0] - s.lo[0] - p0[0], ey = v.eye[1] - s.lo[1] - p0[1],
                            ez = v.eye[2] - s.lo[2] - p0[2];
                if (nx * ex + ny * ey + nz * ez <= 0.0f) {
                    continue;
                }
                CV q[3];
                const unsigned idx[3] = {a, b, c};
                for (unsigned i = 0; i < 3; ++i) {
                    const SV& r = t[idx[i]];
                    const std::uint32_t w = uu[idx[i]];
                    q[i].x = r.v.x;
                    q[i].y = r.v.y;
                    q[i].w = r.v.w;
                    q[i].u = bitsf(w & 0xFFFF0000u);
                    q[i].v = bitsf(w << 16);
                }
                o.sq = d;
                emit_poly_clip<kClipUV16>(o, q, 3);
                d = o.sq;
                g_st.tris++;
            }
        }
        j += n;
    }
    o.sq = d;
}

// |gradient| of each side of the view (X', 640 W' - X', Y', 480 W' - Y', W'), per frame
float g_side[5];
inline float norm3(float a, float b, float c)
{
    const float d2 = a * a + b * b + c * c;
    return d2 > 0.0f ? d2 * rsqrt(d2) : 0.0f;
}
void set_sides(const CoarseView& v)
{
    const float *X = v.S[0], *Y = v.S[1], *W = v.S[2];
    g_side[0] = norm3(X[0], X[1], X[2]);
    g_side[1] = norm3(640.0f * W[0] - X[0], 640.0f * W[1] - X[1], 640.0f * W[2] - X[2]);
    g_side[2] = norm3(Y[0], Y[1], Y[2]);
    g_side[3] = norm3(480.0f * W[0] - Y[0], 480.0f * W[1] - Y[1], 480.0f * W[2] - Y[2]);
    g_side[4] = norm3(W[0], W[1], W[2]);
}

unsigned draw_shell(const CoarseView& v, const Shell& s, unsigned cull)
{
    Emit o{re4dc_coarse_begin_mode(s.key[0], s.key[1], s.size, s.size, kModeFog | cull | kModeUV16), 0};
    if (!o.sq) {
        g_st.rejects++;
        return 0;
    }
    g_st.shells++;
    load_rows(v, s.lo);
    const unsigned short(*P)[3] = kPos + s.pos;
    // the eye in the shell's frame (positions are mm over lo)
    const float ex = v.eye[0] - s.lo[0], ey = v.eye[1] - s.lo[1], ez = v.eye[2] - s.lo[2];
    const unsigned short* sp = kStripPos + s.vtx;
    const unsigned* uv = kStripUV + s.vtx;
    const Group* G = kGroup + s.grp;
    bool near = false;
    for (unsigned g = 0; g < s.ngrp; ++g) {
        const Group& c = G[g];
        const float dx = ex - c.c[0], dy = ey - c.c[1], dz = ez - c.c[2];
        const float d2 = dx * dx + dy * dy + dz * dz;
        const float dist = d2 > 1.0f ? d2 * rsqrt(d2) : 1.0f;
        if (c.a[0] * ex + c.a[1] * ey + c.a[2] * ez + c.s * (dist + c.r) <= c.dmin) {
            g_st.groupsCulled++;
            g_st.vtxCulled += c.nvtx;
        } else {
            // the group's sphere against the view's sides: each side's value (X', 640 W' - X', Y',
            // 480 W' - Y', W') is affine, so over the sphere it is the centre's +- r |gradient|
            float cx = c.c[0], cy = c.c[1], cw = c.c[2];
            mat_trans_single3_nodiv(cx, cy, cw);   // X' Y' W' at the centre
            const float* gn = g_side;
            if (cx + c.r * gn[0] < 0.0f || 640.0f * cw - cx + c.r * gn[1] < 0.0f || cy + c.r * gn[2] < 0.0f ||
                480.0f * cw - cy + c.r * gn[3] < 0.0f || cw + c.r * gn[4] < kNear) {
                g_st.groupsOff++;
            } else if (cw - c.r * gn[4] >= kNear) {
                o.sq = emit_group(o.sq, P, sp, uv, c.nvtx);
                o.n += c.nvtx;
                g_st.tris += c.nvtx - 2u * c.nstrip;
            } else {
                near = true;
                emit_group_near(o, v, s, sp, uv, c.nvtx);
            }
        }
        sp += c.nvtx;
        uv += c.nvtx;
    }
    g_st.near += near;
    re4dc_coarse_end(o.n);
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 2
// ------------------------------------------------------------------ ground
struct GV {
    float x, y, iw, w, u, v;   // screen x, y, 1 / W' (valid when W' >= kNear), W', the detail UV
    std::uint32_t col, pad;
};
union GVU {
    GV g;
    std::uint32_t u[8];
};
GVU g_gv[kGroundMaxVtx];

unsigned draw_ground(const CoarseView& v, unsigned cull)
{
    Emit o{nullptr, 0};
    constexpr float kInv = 1.0f / kGroundCell;
    const float far2 = v.far * v.far;
    for (unsigned ci = 0; ci < kChunks; ++ci) {
        const Chunk& c = kChunk[ci];
        // beyond the far plane (the common case): the XZ distance to the chunk square
        const float ex = v.eye[0], ez = v.eye[2];
        const float dx = ex < c.x0 ? c.x0 - ex : ex > c.x0 + kGroundSpan ? ex - c.x0 - kGroundSpan : 0.0f;
        const float dz = ez < c.z0 ? c.z0 - ez : ez > c.z0 + kGroundSpan ? ez - c.z0 - kGroundSpan : 0.0f;
        if (dx * dx + dz * dz > far2) {
            continue;
        }
        const float lo[3] = {c.x0, c.y0, c.z0};
        const float hi[3] = {c.x0 + kGroundSpan, c.y1, c.z0 + kGroundSpan};
        if (!box_visible(v, lo, hi)) {
            continue;
        }
        if (!o.sq) {
            o.sq = re4dc_coarse_begin_mode(kGroundKey[0], kGroundKey[1], kGroundTex, kGroundTex,
                                           kModeFog | kModeRepeat | cull);
            if (!o.sq) {
                g_st.rejects++;
                return 0;
            }
        }
        g_st.chunks++;
        load_rows(v, lo);
        const unsigned short(*P)[3] = kGroundPos + c.vtx;
        const unsigned* col = kGroundCol + c.vtx;
        unsigned behind = 0;
        for (unsigned i = 0; i < c.nvtx; ++i) {
            const float px = (float) P[i][0], pz = (float) P[i][2];
            float x = px, y = (float) P[i][1], z = pz;
            mat_trans_single3_nodiv(x, y, z);
            const float iw = rcp(z);
            GV& g = g_gv[i].g;
            g.x = x * iw;
            g.y = y * iw;
            g.iw = iw;
            g.w = z;
            g.u = px * kInv;
            g.v = pz * kInv;
            g.col = col[i];
            behind += z < kNear;
        }
        const unsigned char* pc = kGroundPiece + c.piece;
        for (unsigned p = 0; p < c.npiece; ++p) {
            const unsigned n = *pc++;
            bool front = true;
            if (behind) {
                for (unsigned k = 0; k < n; ++k) {
                    front = front && g_gv[pc[k]].g.w >= kNear;
                }
            }
            if (front) {
                std::uint32_t* d = o.sq;
                for (unsigned k = 0; k < n; ++k) {
                    const std::uint32_t* q = g_gv[pc[zig(n, k)]].u;
                    d[0] = k + 1 == n ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                    d[1] = q[0];
                    d[2] = q[1];
                    d[3] = q[2];
                    d[4] = q[4];
                    d[5] = q[5];
                    d[6] = q[6];
                    d[7] = 0;
                    __asm__ __volatile__("pref @%0" : : "r"(d) : "memory");
                    d += 8;
                }
                o.sq = d;
                o.n += n;
                g_st.gtris += n - 2;
            } else {
                CV t[8];
                unsigned out = 0x1Fu;
                for (unsigned k = 0; k < n; ++k) {
                    const unsigned i = pc[k];
                    float x = (float) P[i][0], y = (float) P[i][1], z = (float) P[i][2];
                    mat_trans_single3_nodiv(x, y, z);   // XMTRX still holds the chunk's rows
                    t[k].x = x;
                    t[k].y = y;
                    t[k].w = z;
                    out &= outcode(x, y, z);
                }
                if (out) {
                    g_st.offscreen++;
                } else {
                    for (unsigned k = 0; k < n; ++k) {
                        const unsigned i = pc[k];
                        t[k].u = g_gv[i].g.u;
                        t[k].v = g_gv[i].g.v;
                        unpack(g_gv[i].g.col, t[k].c);
                    }
                    emit_poly_clip<kClipUV32>(o, t, n);
                    g_st.gtris += n - 2;
                }
            }
            pc += n;
        }
    }
    if (o.sq) {
        re4dc_coarse_end(o.n);
    }
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 4
// ------------------------------------------------------------------ sky
// base = white x (1 - fade), offset = fog x fade: the clouds fade into the fog colour at the horizon.
unsigned draw_sky(const CoarseView& v)
{
    Emit o{re4dc_coarse_begin_mode(kSkyKey[0], kSkyKey[1], kSkyW, kSkyH, kModeRepeat | kModeOffset), 0};
    if (!o.sq) {
        g_st.rejects++;
        return 0;
    }
    g_st.sky++;
    // the colours (base, offset) of each vertex for this fog colour, packed once
    static float fog[3] = {-1.0f, -1.0f, -1.0f};
    static std::uint32_t argb[kSkyVerts][2];
    if (fog[0] != v.fog_rgb[0] || fog[1] != v.fog_rgb[1] || fog[2] != v.fog_rgb[2]) {
        for (unsigned k = 0; k < 3; ++k) {
            fog[k] = v.fog_rgb[k];
        }
        for (unsigned i = 0; i < kSkyVerts; ++i) {
            const float f = (float) kSkyVertex[i].fade * (1.0f / 255.0f);
            const float b = 255.0f * (1.0f - f);
            const float c[4] = {255.0f, b, b, b}, s[4] = {255.0f, fog[0] * f, fog[1] * f, fog[2] * f};
            argb[i][0] = argb_of(c);
            argb[i][1] = argb_of(s);
        }
    }
    static const float zero[3] = {0.0f, 0.0f, 0.0f};
    load_rows(v, zero);
    // per vertex: its vertex words (x y 1/W' u v argb oargb; valid when W' >= kNear), X' Y' W' and outcode
    static union {
        float f[8];
        std::uint32_t u[8];
    } sv[kSkyVerts] __attribute__((aligned(32)));
    static float cw[kSkyVerts][3];
    static unsigned char oc[kSkyVerts];
    for (unsigned i = 0; i < kSkyVerts; ++i) {
        const SkyVertex& s = kSkyVertex[i];
        float x = s.p[0], y = s.p[1], z = s.p[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        sv[i].f[1] = x * iw;
        sv[i].f[2] = y * iw;
        sv[i].f[3] = iw;
        sv[i].f[4] = s.u;
        sv[i].f[5] = s.v;
        sv[i].u[6] = argb[i][0];
        sv[i].u[7] = argb[i][1];
        cw[i][0] = x;
        cw[i][1] = y;
        cw[i][2] = z;
        oc[i] = (unsigned char) outcode(x, y, z);
    }
    for (unsigned t = 0; t < kSkyTris; ++t) {
        const unsigned i0 = kSkyTri[t][0], i1 = kSkyTri[t][1], i2 = kSkyTri[t][2];
        const unsigned o0 = oc[i0], o1 = oc[i1], o2 = oc[i2];
        if (o0 & o1 & o2) {
            g_st.offscreen++;
            continue;
        }
        if (!((o0 | o1 | o2) & 0x10u)) {
            const unsigned idx[3] = {i0, i1, i2};
            std::uint32_t* d = o.sq;
            for (unsigned k = 0; k < 3; ++k) {
                const std::uint32_t* q = sv[idx[k]].u;
                d[0] = k == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                d[1] = q[1];
                d[2] = q[2];
                d[3] = q[3];
                d[4] = q[4];
                d[5] = q[5];
                d[6] = q[6];
                d[7] = q[7];
                __asm__ __volatile__("pref @%0" : : "r"(d) : "memory");
                d += 8;
            }
            o.sq = d;
            o.n += 3;
        } else {
            const unsigned idx[3] = {i0, i1, i2};
            CV tri[3];
            for (unsigned k = 0; k < 3; ++k) {
                const unsigned i = idx[k];
                tri[k].x = cw[i][0];
                tri[k].y = cw[i][1];
                tri[k].w = cw[i][2];
                tri[k].u = kSkyVertex[i].u;
                tri[k].v = kSkyVertex[i].v;
                unpack(argb[i][0], tri[k].c);
                unpack(argb[i][1], tri[k].s);
            }
            emit_poly_clip<kClipUV32Offset>(o, tri, 3);
        }
    }
    re4dc_coarse_end(o.n);
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 8
// ------------------------------------------------------------------ trees
float turns(float y, float x)   // as native_static.cpp: atan2 in turns, [0, 1)
{
    const float ax = x < 0.0f ? -x : x, ay = y < 0.0f ? -y : y, lo = ax < ay ? ax : ay, hi = ax < ay ? ay : ax;
    if (!(hi > 0.0f)) {
        return 0.0f;
    }
    const float a = lo / hi, s = a * a;
    float r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
    if (ay > ax) {
        r = 1.57079633f - r;
    }
    if (x < 0.0f) {
        r = 3.14159265f - r;
    }
    r *= 0.159154943f;
    return y < 0.0f ? 1.0f - r : r;
}
struct TreeQuad {
    unsigned short atlas, cell;
    float s[4][3];   // screen x, y, 1 / W' per corner: TL, TR, BL, BR
};
constexpr unsigned kTreeQuads = 64;
TreeQuad g_tq[kTreeQuads];
unsigned g_ntq, g_tqFrame = ~0u;

void queue_trees(const CoarseView& v)
{
    g_ntq = 0;
    g_tqFrame = re4dc_ui_frame();
    static const float zero[3] = {0.0f, 0.0f, 0.0f};
    load_rows(v, zero);
    for (unsigned i = 0; i < kTrees && g_ntq < kTreeQuads; ++i) {
        const Tree& t = kTree[i];
        const float dx = v.eye[0] - t.c[0], dz = v.eye[2] - t.c[2];
        const float d2 = dx * dx + dz * dz;
        const float reach = v.far + t.hw;
        if (d2 > reach * reach || d2 < 1.0f) {
            continue;
        }
        const float il = rsqrt(d2), bx = dx * il, bz = dz * il;
        const TreeAtlas& a = kTreeAtlas[t.atlas];
        // the eye's azimuth in the tree's own frame picks the cell (native_static mesh_impostor)
        const float mx = dx * t.ex[0] + dz * t.ex[1], mz = dx * t.ez[0] + dz * t.ez[1];
        unsigned cell = (unsigned) (turns(-mz, mx) * (float) a.views + 0.5f);
        if (cell >= a.views) {
            cell -= a.views;
        }
        TreeQuad& q = g_tq[g_ntq];
        unsigned left = 0, right = 0, top = 0, bottom = 0;
        bool ok = true;
        for (unsigned k = 0; k < 4 && ok; ++k) {
            const float sx = (k & 1) ? t.hw : -t.hw, sy = (k & 2) ? -t.hh : t.hh;
            float x = t.c[0] + sx * bz, y = t.c[1] + sy, z = t.c[2] - sx * bx;
            mat_trans_single3_nodiv(x, y, z);
            if (!(z >= kNear)) {
                ok = false;
                break;
            }
            const float iw = rcp(z);
            float* s = q.s[k];
            s[0] = x * iw;
            s[1] = y * iw;
            s[2] = iw;
            left += s[0] < 0.0f;
            right += s[0] > 640.0f;
            top += s[1] < 0.0f;
            bottom += s[1] > 480.0f;
        }
        if (!ok || left == 4 || right == 4 || top == 4 || bottom == 4) {
            continue;
        }
        q.atlas = (unsigned short) t.atlas;
        q.cell = (unsigned short) cell;
        ++g_ntq;
        ++g_st.trees;
    }
}
#endif
}  // namespace

extern "C" unsigned re4dc_coarse_world_draw(const CoarseView* view)
{
    const std::uint64_t t0 = timer_us_gettime64();
    // the PVR culls what the eye sees from behind: a front face's screen area has the sign opposite det(S3)
    const unsigned cull = view->det > 0.0f ? kModeCullPos : kModeCullNeg;
    unsigned verts = 0;
#if RE4DC_COARSE_WORLD & 4
    verts += draw_sky(*view);
#endif
#if RE4DC_COARSE_WORLD & 2
    verts += draw_ground(*view, cull);
#endif
#if RE4DC_COARSE_WORLD & 1
    set_sides(*view);
    for (unsigned i = 0; i < kShells; ++i) {
        if (box_visible(*view, kShell[i].lo, kShell[i].hi)) {
            verts += draw_shell(*view, kShell[i], cull);
        }
    }
#endif
#if RE4DC_COARSE_WORLD & 8
    queue_trees(*view);
#endif
    (void) cull;
    g_st.verts += verts;
    g_st.us += (unsigned) (timer_us_gettime64() - t0);
    return verts;
}

// The trees queued by this frame's coarse view, one punch-through batch per atlas (native_ui
// re4dc_model_finish_source_draws: after the OP pass, before the translucent drain).
extern "C" void re4dc_coarse_world_flush()
{
#if RE4DC_COARSE_WORLD & 8
    if (g_tqFrame != re4dc_ui_frame()) {
        g_ntq = 0;
        return;
    }
    for (unsigned a = 0; a < kTreeAtlases && g_ntq; ++a) {
        unsigned any = 0;
        for (unsigned i = 0; i < g_ntq; ++i) {
            any += g_tq[i].atlas == a;
        }
        if (!any) {
            continue;
        }
        const TreeAtlas& r = kTreeAtlas[a];
        Re4dcModelPacket packet{};
        if (!re4dc_model_pt_begin(r.key[0], r.key[1], r.atlas_w, r.atlas_h, 1, &packet)) {
            g_st.rejects++;
            continue;
        }
        auto* out = static_cast<pvr_vertex_t*>(packet.vertices);
        unsigned used = 0;
        const float iw = 1.0f / (float) r.atlas_w, ih = 1.0f / (float) r.atlas_h;   // half-texel inset
        for (unsigned i = 0; i < g_ntq && used + 4 <= packet.capacity; ++i) {
            const TreeQuad& q = g_tq[i];
            if (q.atlas != a) {
                continue;
            }
            const unsigned col = q.cell % r.cols, row = q.cell / r.cols;
            const float u0 = ((float) (col * r.cell_w) + 0.5f) * iw, u1 = ((float) ((col + 1) * r.cell_w) - 0.5f) * iw;
            const float v0 = ((float) (row * r.cell_h) + 0.5f) * ih, v1 = ((float) ((row + 1) * r.cell_h) - 0.5f) * ih;
            for (unsigned k = 0; k < 4; ++k) {
                pvr_vertex_t& o = out[used + k];
                o.flags = k == 3 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                o.x = q.s[k][0];
                o.y = q.s[k][1];
                o.z = q.s[k][2];
                o.u = (k & 1) ? u1 : u0;
                o.v = (k & 2) ? v1 : v0;
                o.argb = kTreeArgb;
                o.oargb = 0;
            }
            used += 4;
        }
        re4dc_model_packet_commit(used);
    }
    g_ntq = 0;
#endif
}

extern "C" void re4dc_coarse_world_log(unsigned f)
{
    if (f) {
        re4dc_log("COARSE world shells=%u tris=%u near=%u groups_culled=%u verts_culled=%u groups_off=%u chunks=%u "
                  "ground_tris=%u "
                  "sky=%u trees=%u clipped=%u offscreen=%u verts=%u us=%u rejects=%u\n",
                  g_st.shells / f, g_st.tris / f, g_st.near / f, g_st.groupsCulled / f, g_st.vtxCulled / f, g_st.groupsOff / f,
                  g_st.chunks / f, g_st.gtris / f, g_st.sky / f, g_st.trees / f, g_st.clipped / f, g_st.offscreen / f,
                  g_st.verts / f,
                  g_st.us / f, g_st.rejects);
    }
    g_st = Stats();
}
