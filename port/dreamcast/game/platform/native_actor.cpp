// D367 actor prototype (UNAPPLIED; see PROPOSAL.md option A).
//
// Replaces, for non-scenery ModelData parts only, the generic per-corner path
// of native_model.cpp (per-corner cache probes, per-vertex point-light
// evaluation with ~8 FDIV/FSQRT per light, per-triangle clip/pack) with:
//   1. per model info, once: every source position through one combined
//      screen x modelview x dequantisation XMTRX (ftrv + fsrra), plus an exact
//      screen-rectangle / near-far cull of the whole info;
//   2. per model info, once: the source's GX light selection converted to a
//      per-object set of directional lights in normal space (the captured
//      scene lights are GX "infinite" lights ~1e5 units away, k=(1,0,0)), then
//      one packed colour per source normal (fipr per light, no divides);
//   3. per part: the GX display list walked once; strips/quads/fans published
//      as PVR strips from the two tables (near/far crossings use the existing
//      clipper, exactly like the generic path).
// Nothing here decides visibility, animation, pose, light selection or order:
// those come from the source game through Re4dcModelPart, as today.
#include "native_actor.hpp"
#include "../../room/pvr_geometry.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#if defined(__sh__)
#include <dc/matrix.h>
#include <dc/fmath_base.h>
#endif

namespace {
using re4dc::render::SourceLight;
using re4dc::render::SourceLighting;

struct Screen { float x, y, w_inverse; };  // w_inverse <= 0: outside [near, far]
static_assert(sizeof(Screen) == 12, "workspace layout");

struct DirectionalLight { float x, y, z, red, green, blue; };
struct LightSet {
    DirectionalLight lights[8];
    unsigned count = 0;
    unsigned diffuse = 2;
    float ambient[3] = {1.0f, 1.0f, 1.0f};
    float scale[3] = {255.0f, 255.0f, 255.0f};  // material * tev_scale * 255
};

struct Prepared {
    const void* info = nullptr;
    const unsigned char* positions = nullptr;
    const unsigned char* normals = nullptr;
    unsigned position_count = 0, normal_count = 0, position_stride = 0;
    unsigned normal_stride = 0, shift = 0, normal_shift = 0, frame = 0;
    float modelview[12]{}, projection[7]{}, viewport[6]{};
    SourceLighting lighting{};
    bool positions_ready = false, shades_ready = false, visible = false;
    float centroid[3]{};  // model units after dequantisation
};

unsigned char* workspace = nullptr;
unsigned workspace_bytes = 0, frame_serial = 0;
Prepared prepared;
Re4dcActorStats stats{};

inline unsigned be16(const unsigned char* p) { return (unsigned(p[0]) << 8) | p[1]; }
inline int s16(const unsigned char* p) { short v; std::memcpy(&v, p, 2); return v; }
inline unsigned u16(const unsigned char* p) { unsigned short v; std::memcpy(&v, p, 2); return v; }
inline bool ram(const void* p, unsigned bytes) {
#if defined(__sh__)
    const auto a = reinterpret_cast<std::uintptr_t>(p);
    return a >= 0x8c000000U && a < 0x8d000000U && bytes <= 0x8d000000U - a;
#else
    (void)bytes; return p != nullptr;
#endif
}
inline float reciprocal(float w) {
#if defined(__sh__)
    // Same qualified FSRRA range as static_room_prepare.cpp (w is positive).
    if (w >= 1.0e-18f && w <= 1.0e18f) return __frsqrt(w * w);
#endif
    return 1.0f / w;
}
inline float dot3(float ax, float ay, float az, float bx, float by, float bz) {
#if defined(__sh__)
    return __fipr(ax, ay, az, 0.0f, bx, by, bz, 0.0f);
#else
    return ax * bx + ay * by + az * bz;
#endif
}
inline unsigned channel(float x) { return unsigned(std::clamp(x, 0.0f, 255.0f)); }

Screen* screen_table() { return reinterpret_cast<Screen*>(workspace); }
std::uint32_t* shade_table(unsigned position_count) {
    return reinterpret_cast<std::uint32_t*>(workspace + position_count * sizeof(Screen));
}

// Exactly native_model.cpp's project(), for the clipped fallback only.
struct Projection { const float* p; const float* v; };
void project(float& x, float& y, float& z, void* context) {
    const auto& c = *static_cast<const Projection*>(context);
    const float inv = 1.0f / (-z);
    x = (c.v[2] * .5f * (c.p[1] * x + c.p[2] * z) * inv + c.v[0] + c.v[2] * .5f) * 640.f / c.v[2];
    y = (-c.v[3] * .5f * (c.p[3] * y + c.p[4] * z) * inv + c.v[1] + c.v[3] * .5f) * 480.f / c.v[3];
    z = inv;
}

bool same_positions(const Re4dcModelPart& p) {
    const Prepared& s = prepared;
    return s.positions_ready && s.frame == frame_serial && s.info == p.info &&
           s.positions == p.positions && s.position_count == p.position_count &&
           s.position_stride == p.position_stride && s.shift == p.shift &&
           !std::memcmp(s.modelview, p.modelview, sizeof(s.modelview)) &&
           !std::memcmp(s.projection, p.projection, sizeof(s.projection)) &&
           !std::memcmp(s.viewport, p.viewport, sizeof(s.viewport));
}

// Pass 1: one XMTRX transform per source position. Rows of the combined
// matrix produce (X, Y, W, W) with W = -Zcamera; X/W and Y/W equal project().
void prepare_positions(const Re4dcModelPart& p, float near_distance, float far_distance) {
    Prepared& s = prepared;
    s.info = p.info; s.positions = p.positions; s.position_count = p.position_count;
    s.position_stride = p.position_stride; s.shift = p.shift; s.frame = frame_serial;
    std::memcpy(s.modelview, p.modelview, sizeof(s.modelview));
    std::memcpy(s.projection, p.projection, sizeof(s.projection));
    std::memcpy(s.viewport, p.viewport, sizeof(s.viewport));
    s.positions_ready = true; s.shades_ready = false;
    ++stats.info_preparations; stats.position_transforms += p.position_count;

    const float* m = p.modelview; const float* P = p.projection; const float* V = p.viewport;
    const float q = std::ldexp(1.0f, -int(p.shift));
    const float cx = (V[0] + V[2] * 0.5f) * 640.0f / V[2];
    const float cy = (V[1] + V[3] * 0.5f) * 480.0f / V[3];
    const float rows[3][3] = {{320.0f * P[1], 0.0f, 320.0f * P[2] - cx},
                              {0.0f, -240.0f * P[3], -240.0f * P[4] - cy},
                              {0.0f, 0.0f, -1.0f}};
    float M[3][4];
    for (unsigned r = 0; r < 3; ++r)
        for (unsigned c = 0; c < 4; ++c) {
            const float v = rows[r][0] * m[c] + rows[r][1] * m[4 + c] + rows[r][2] * m[8 + c];
            M[r][c] = c < 3 ? v * q : v;
        }
#if defined(__sh__)
    alignas(32) matrix_t xm;
    for (unsigned c = 0; c < 4; ++c) {
        xm[c][0] = M[0][c]; xm[c][1] = M[1][c]; xm[c][2] = M[2][c]; xm[c][3] = M[2][c];
    }
    mat_load(&xm);
#endif
    Screen* out = screen_table();
    float min_x = 1e30f, max_x = -1e30f, min_y = 1e30f, max_y = -1e30f;
    int sum_x = 0, sum_y = 0, sum_z = 0;  // <= 32767 * 65535 fits in 31 bits
    unsigned valid = 0, before_near = 0;
    const unsigned char* src = p.positions;
    const unsigned stride = p.position_stride;
    for (unsigned i = 0; i < p.position_count; ++i, src += stride) {
        const short* v = reinterpret_cast<const short*>(src);
        const int a = v[0], b = v[1], c = v[2];
        sum_x += a; sum_y += b; sum_z += c;
        float x = float(a), y = float(b), z = float(c), w = 1.0f;
#if defined(__sh__)
        mat_trans_nodiv(x, y, z, w);
#else
        const float tx = M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3];
        const float ty = M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3];
        w = M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3];
        x = tx; y = ty;
#endif
        if (w >= near_distance && w <= far_distance) {
            const float inverse = reciprocal(w);
            x *= inverse; y *= inverse;
            out[i] = {x, y, inverse};
            min_x = std::min(min_x, x); max_x = std::max(max_x, x);
            min_y = std::min(min_y, y); max_y = std::max(max_y, y);
            ++valid;
        } else {
            out[i] = {0.0f, 0.0f, -1.0f};
            before_near += w < near_distance ? 1U : 0U;
        }
    }
    const unsigned invalid = p.position_count - valid;
    stats.near_vertices += before_near;
    const float inverse_count = 1.0f / float(p.position_count);
    s.centroid[0] = float(sum_x) * inverse_count * q;
    s.centroid[1] = float(sum_y) * inverse_count * q;
    s.centroid[2] = float(sum_z) * inverse_count * q;
    if (invalid) {
        // Conservative: a crossing triangle may still be visible. Only an info
        // wholly before the near plane (or wholly beyond far) is culled.
        s.visible = valid || (before_near && before_near != invalid);
    } else {
        s.visible = !(max_x < 0.0f || min_x > 640.0f || max_y < 0.0f || min_y > 480.0f);
    }
    if (!s.visible) ++stats.culled_infos;
}

// Per-object light set: the source-selected GX lights evaluated once at the
// info centroid (same attenuation formula as source_lighting.cpp), then moved
// into the normals' own space so a lit normal needs no normal transform.
LightSet build_lights(const Re4dcModelPart& p) {
    const SourceLighting& L = *p.lighting;
    LightSet set;
    constexpr float k = 1.0f / 255.0f;
    set.diffuse = L.diffuse;
    for (unsigned c = 0; c < 3; ++c) {
        set.ambient[c] = L.enable ? L.ambient[c] * k : 1.0f;
        set.scale[c] = L.material[c] * k * L.tev_scale * 255.0f;
    }
    if (!L.enable) return set;
    const float* m = p.modelview;
    const float* c = prepared.centroid;
    const float px = m[0] * c[0] + m[1] * c[1] + m[2] * c[2] + m[3];
    const float py = m[4] * c[0] + m[5] * c[1] + m[6] * c[2] + m[7];
    const float pz = m[8] * c[0] + m[9] * c[1] + m[10] * c[2] + m[11];
    const float* N = L.normal_matrix;
    const float nq = std::ldexp(1.0f, -int(p.normal_shift));
    for (unsigned i = 0; i < 8; ++i) {
        if (!(L.mask & (1U << i))) continue;
        const SourceLight& s = L.lights[i];
        float lx = s.position[0] - px, ly = s.position[1] - py, lz = s.position[2] - pz;
        const float d2 = lx * lx + ly * ly + lz * lz, d = std::sqrt(d2);
        if (d > 0.0f) { const float r = 1.0f / d; lx *= r; ly *= r; lz *= r; }
        else { lx = 0.0f; ly = 0.0f; lz = 1.0f; }
        float attenuation = 1.0f;
        if (L.attenuation == 1) {
            const float cosine = std::max(0.0f, lx * s.direction[0] + ly * s.direction[1] + lz * s.direction[2]);
            const float angular = std::max(0.0f, s.a[0] + s.a[1] * cosine + s.a[2] * cosine * cosine);
            const float denominator = s.k[0] + s.k[1] * d + s.k[2] * d2;
            attenuation = denominator > 0.0f ? angular / denominator : 0.0f;
        }
        if (s.k[1] != 0.0f || s.k[2] != 0.0f) ++stats.attenuated_lights;
        const float red = s.color[0] * k * attenuation, green = s.color[1] * k * attenuation,
                    blue = s.color[2] * k * attenuation;
        if (std::max(red, std::max(green, blue)) <= 1.0f / 1024.0f) continue;
        if (set.diffuse == 0) {  // GX_DF_NONE: the light adds its colour regardless of N
            set.ambient[0] += red; set.ambient[1] += green; set.ambient[2] += blue;
            continue;
        }
        // dot(Nmatrix * n, l) == dot(n, Nmatrix^T * l); fold the normal quantum.
        DirectionalLight& out = set.lights[set.count++];
        out.x = (N[0] * lx + N[4] * ly + N[8] * lz) * nq;
        out.y = (N[1] * lx + N[5] * ly + N[9] * lz) * nq;
        out.z = (N[2] * lx + N[6] * ly + N[10] * lz) * nq;
        out.red = red; out.green = green; out.blue = blue;
    }
    ++stats.light_sets;
    return set;
}

// Pass 2: one packed RGB per source normal (alpha is attached per corner).
void prepare_shades(const Re4dcModelPart& p) {
    Prepared& s = prepared;
    s.normals = p.normals; s.normal_count = p.normal_count; s.normal_stride = p.normal_stride;
    s.normal_shift = p.normal_shift; s.lighting = *p.lighting; s.shades_ready = true;
    const LightSet set = build_lights(p);
    std::uint32_t* out = shade_table(p.position_count);
    const unsigned char* src = p.normals;
    const bool small = p.normal_shift == 6;
    stats.normals_lit += p.normal_count;
    if (set.count <= 4 && small) {
        // Common case (every captured actor: 2-3 lights, s8 normals): the up
        // to four light directions are the rows of XMTRX, so ONE ftrv yields
        // all N.L terms of a normal. Unused rows are zero with zero colour.
        float dir[4][3] = {}, col[4][3] = {};
        for (unsigned l = 0; l < set.count; ++l) {
            dir[l][0] = set.lights[l].x; dir[l][1] = set.lights[l].y; dir[l][2] = set.lights[l].z;
            col[l][0] = set.lights[l].red; col[l][1] = set.lights[l].green; col[l][2] = set.lights[l].blue;
        }
#if defined(__sh__)
        alignas(32) matrix_t lm = {};
        for (unsigned l = 0; l < 4; ++l) { lm[0][l] = dir[l][0]; lm[1][l] = dir[l][1]; lm[2][l] = dir[l][2]; }
        mat_load(&lm);
#endif
        const bool clamp_diffuse = set.diffuse == 2;
        for (unsigned i = 0; i < p.normal_count; ++i, src += p.normal_stride) {
            const auto* n = reinterpret_cast<const signed char*>(src);
            float d0 = n[0], d1 = n[1], d2 = n[2], d3 = 0.0f;
#if defined(__sh__)
            mat_trans_nodiv(d0, d1, d2, d3);
#else
            const float x = d0, y = d1, z = d2;
            d0 = dir[0][0] * x + dir[0][1] * y + dir[0][2] * z;
            d1 = dir[1][0] * x + dir[1][1] * y + dir[1][2] * z;
            d2 = dir[2][0] * x + dir[2][1] * y + dir[2][2] * z;
            d3 = dir[3][0] * x + dir[3][1] * y + dir[3][2] * z;
#endif
            if (clamp_diffuse) {
                d0 = d0 > 0.0f ? d0 : 0.0f; d1 = d1 > 0.0f ? d1 : 0.0f;
                d2 = d2 > 0.0f ? d2 : 0.0f; d3 = d3 > 0.0f ? d3 : 0.0f;
            }
            float r = set.ambient[0] + d0 * col[0][0] + d1 * col[1][0] + d2 * col[2][0] + d3 * col[3][0];
            float g = set.ambient[1] + d0 * col[0][1] + d1 * col[1][1] + d2 * col[2][1] + d3 * col[3][1];
            float b = set.ambient[2] + d0 * col[0][2] + d1 * col[1][2] + d2 * col[2][2] + d3 * col[3][2];
            r = std::clamp(r, 0.0f, 1.0f) * set.scale[0];
            g = std::clamp(g, 0.0f, 1.0f) * set.scale[1];
            b = std::clamp(b, 0.0f, 1.0f) * set.scale[2];
            out[i] = (channel(r) << 16) | (channel(g) << 8) | channel(b);
        }
        return;
    }
    for (unsigned i = 0; i < p.normal_count; ++i, src += p.normal_stride) {
        float nx, ny, nz;
        if (small) {
            const auto* n = reinterpret_cast<const signed char*>(src);
            nx = n[0]; ny = n[1]; nz = n[2];
        } else {
            const auto* n = reinterpret_cast<const short*>(src);
            nx = n[0]; ny = n[1]; nz = n[2];
        }
        float r = set.ambient[0], g = set.ambient[1], b = set.ambient[2];
        for (unsigned l = 0; l < set.count; ++l) {
            const DirectionalLight& d = set.lights[l];
            float diffuse = dot3(nx, ny, nz, d.x, d.y, d.z);
            if (set.diffuse == 2) diffuse = diffuse > 0.0f ? diffuse : 0.0f;
            r += diffuse * d.red; g += diffuse * d.green; b += diffuse * d.blue;
        }
        r = std::clamp(r, 0.0f, 1.0f) * set.scale[0];
        g = std::clamp(g, 0.0f, 1.0f) * set.scale[1];
        b = std::clamp(b, 0.0f, 1.0f) * set.scale[2];
        out[i] = (channel(r) << 16) | (channel(g) << 8) | channel(b);
    }
}

struct Emitter {
    const Re4dcModelPart& p;
    Re4dcModelPacket packet{};
    const Screen* screen;
    const std::uint32_t* shade;
    Projection projection;
    re4dc::render::ClipParameters clip;
    unsigned stride, used = 0, input = 0, output = 0, material_alpha = 255;
    bool s16_uv = false, vertex_alpha = false, streaming = false, bad = false, committed = false;

    bool flush() {
        if (!streaming) return false;
        re4dc_model_packet_commit(used); committed = true;
        used = 0; ++stats.flushes;
        return true;
    }
    float uv_scale() const { return s16_uv ? 1.0f / 256.0f : 1.0f / 32768.0f; }
    bool corner(const unsigned char* c, pvr_vertex_t& d, bool last, unsigned& outside) {
        const unsigned vi = be16(c), ni = be16(c + 2), ti = be16(c + stride - 2);
        if (vi >= p.position_count || ni >= p.normal_count) { bad = true; return false; }
        const Screen& s = screen[vi];
        if (!(s.w_inverse > 0.0f)) return false;  // near/far crossing -> clipped run
        const unsigned char* uv = p.uv + ti * 4;
        if (!ram(uv, 4)) { bad = true; return false; }
        const float u = float(s16_uv ? s16(uv) : int(u16(uv))) * uv_scale();
        const float v = float(s16_uv ? s16(uv + 2) : int(u16(uv + 2))) * uv_scale();
        unsigned alpha = material_alpha;
        if (vertex_alpha) {
            const unsigned ci = be16(c + 4);
            if (!ram(p.colors + ci * 4, 4)) { bad = true; return false; }
            alpha = p.colors[ci * 4 + 3];
        }
        outside &= (s.x < 0.0f ? 1U : 0U) | (s.x > 640.0f ? 2U : 0U) |
                   (s.y < 0.0f ? 4U : 0U) | (s.y > 480.0f ? 8U : 0U);
        d.flags = last ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
        d.x = s.x; d.y = s.y; d.z = s.w_inverse;
        d.u = (u + p.uv_offset[0]) * packet.u_scale;
        d.v = (v + p.uv_offset[1]) * packet.v_scale;
        d.argb = (alpha << 24) | shade[ni];
        d.oargb = 0;
        return true;
    }
    // Generic-path equivalent for one triangle that crosses near/far.
    template<class At> bool clipped(At at, unsigned first, unsigned count) {
        for (unsigned t = first; t + 2 < first + count; ++t) {
            unsigned index[3] = {t, t + 1, t + 2};
            if (t & 1) std::swap(index[0], index[1]);  // strip parity, as Builder::primitive
            re4dc::render::RenderVertex in[3];
            float opacity[3];
            for (unsigned k = 0; k < 3; ++k) {
                const unsigned char* c = at(index[k]);
                const unsigned vi = be16(c), ni = be16(c + 2), ti = be16(c + stride - 2);
                const unsigned char* uv = p.uv + ti * 4;
                const auto* pos = reinterpret_cast<const short*>(p.positions + vi * p.position_stride);
                const float q = std::ldexp(1.0f, -int(p.shift));
                const float a = pos[0] * q, b = pos[1] * q, cz = pos[2] * q;
                const float* m = p.modelview;
                float x = m[0] * a + m[1] * b + m[2] * cz + m[3];
                float y = m[4] * a + m[5] * b + m[6] * cz + m[7];
                float z = m[8] * a + m[9] * b + m[10] * cz + m[11];
                auto& v = in[k];
                v = {};
                v.position.world_x = x; v.position.world_y = y; v.position.world_z = z;
                v.position.depth = -z;
                if (z != 0.0f) project(x, y, z, &projection);
                v.position.x = x; v.position.y = y; v.position.z = z;
                v.u = (float(s16_uv ? s16(uv) : int(u16(uv))) * uv_scale() + p.uv_offset[0]) * packet.u_scale;
                v.v = (float(s16_uv ? s16(uv + 2) : int(u16(uv + 2))) * uv_scale() + p.uv_offset[1]) * packet.v_scale;
                const std::uint32_t rgb = shade[ni];
                v.light_red = float((rgb >> 16) & 255) / 255.0f;
                v.light_green = float((rgb >> 8) & 255) / 255.0f;
                v.light_blue = float(rgb & 255) / 255.0f;
                const unsigned alpha = vertex_alpha ? p.colors[be16(c + 4) * 4 + 3] : material_alpha;
                opacity[k] = float(alpha) / 255.0f;
            }
            pvr_vertex_t triangles[6];
            const unsigned n = re4dc::render::clip_projected_triangle(in, triangles, p.cull, clip, nullptr, opacity);
            ++input;
            ++stats.fallback_triangles;
            for (unsigned i = 0; i < n; ++i) {
                if (packet.capacity - used < 3 && !flush()) return false;
                std::memcpy(static_cast<pvr_vertex_t*>(packet.vertices) + used, triangles + i * 3, 3 * sizeof(pvr_vertex_t));
                used += 3; ++output;
            }
        }
        return true;
    }
    // One PVR strip run of `count` corners in strip order (quads/fans already
    // reordered by the caller). Long runs split at even corners (winding).
    template<class At> bool run(unsigned count, At at) {
        ++stats.runs; stats.corners += count;
        unsigned start = 0;
        while (start + 2 < count) {
            if (packet.capacity - used < 3 && !flush()) return false;
            unsigned n = std::min(count - start, packet.capacity - used);
            if (start + n < count && (n & 1)) --n;
            if (n < 3) { if (!flush()) return false; continue; }
            auto* d = static_cast<pvr_vertex_t*>(packet.vertices) + used;
            unsigned k = 0, outside = 15;
            for (; k < n; ++k) if (!corner(at(start + k), d[k], k + 1 == n, outside)) break;
            if (bad) return false;
            if (k == n) {
                input += n - 2;
                if (!outside) { used += n; output += n - 2; }  // else: wholly off one screen edge
            } else {
                ++stats.fallback_runs;
                if (!clipped(at, start, n)) return false;
            }
            if (start + n >= count) break;
            start += n - 2;
        }
        return true;
    }
    bool walk() {
        unsigned offset = 0;
        while (offset < p.stream_bytes) {
            const unsigned op = p.stream[offset++];
            if (!op) continue;
            if (p.stream_bytes - offset < 2) return false;
            const unsigned n = be16(p.stream + offset); offset += 2;
            if (n > (p.stream_bytes - offset) / stride) return false;
            const unsigned char* v = p.stream + offset; offset += n * stride;
            const auto linear = [&](unsigned base) { return [=, this](unsigned i) { return v + (base + i) * stride; }; };
            static constexpr unsigned quad_order[4] = {1, 2, 0, 3};  // (a,b,c)(a,c,d) as one strip
            if (op == 0x98) {
                if (n >= 3 && !run(n, linear(0))) return false;
            } else if (op == 0x90) {
                if (n % 3) return false;
                for (unsigned t = 0; t < n; t += 3) if (!run(3, linear(t))) return false;
            } else if (op == 0x80) {
                if (n % 4) return false;
                for (unsigned q = 0; q < n; q += 4)
                    if (!run(4, [=, this](unsigned i) { return v + (q + quad_order[i]) * stride; })) return false;
            } else if (op == 0xa0) {
                if (n == 4) { if (!run(4, [=, this](unsigned i) { return v + quad_order[i] * stride; })) return false; }
                else for (unsigned i = 2; i < n; ++i) {
                    const unsigned tri[3] = {0, i - 1, i};
                    if (!run(3, [=, this](unsigned k) { return v + tri[k] * stride; })) return false;
                }
            } else return false;
            if (bad) return false;
        }
        return true;
    }
};

bool qualifies(const Re4dcModelPart& p) {
    const SourceLighting* L = p.lighting;
    return L && !L->ambient_vertex && !L->material_vertex &&
           (!L->enable || L->attenuation == 1 || L->attenuation == 2) &&
           p.alpha_state <= 511 &&
           (!(p.alpha_state & 256) || ((p.flags & 0x80000000U) && p.colors)) &&
           p.shift <= 30 && (p.position_stride == 6 || p.position_stride == 8) &&
           (p.normal_shift == 6 || p.normal_shift == 14) && p.normal_stride >= 3 &&
           p.position_count && p.normal_count && p.stream_bytes <= 1024 * 1024 &&
           ram(p.positions, p.position_count * p.position_stride) &&
           ram(p.normals, p.normal_count * p.normal_stride) && ram(p.stream, p.stream_bytes) &&
           p.projection[0] == 0 && p.viewport[2] > 0 && p.viewport[3] > 0;
}
}  // namespace

extern "C" void re4dc_actor_frame(void* memory, unsigned bytes) {
    workspace = static_cast<unsigned char*>(memory);
    workspace_bytes = memory ? bytes : 0;
    ++frame_serial;
    prepared.positions_ready = prepared.shades_ready = false;
}

extern "C" const Re4dcActorStats* re4dc_actor_stats() { return &stats; }

extern "C" int re4dc_actor_submit(const Re4dcModelPart* part) {
    ++stats.parts;
    if (!part || !qualifies(*part)) { ++stats.declined; return 0; }
    const Re4dcModelPart& p = *part;
    if (!workspace || re4dc_actor_workspace_bytes(p.position_count, p.normal_count) > workspace_bytes) {
        ++stats.workspace_misses; ++stats.declined; return 0;
    }
    const float near_distance = p.projection[6] / (p.projection[5] - 1.0f);
    const float far_distance = p.projection[6] / p.projection[5];
    if (!std::isfinite(near_distance) || !std::isfinite(far_distance) ||
        near_distance <= 0.0f || far_distance <= near_distance) { ++stats.declined; return 0; }
    ++stats.handled;
    if (p.cull == 3) { re4dc_model_result(0, 0, 0); return 1; }

    if (!same_positions(p)) prepare_positions(p, near_distance, far_distance);
    if (!prepared.visible) {
        ++stats.culled_parts;
        re4dc_model_result(0, 0, 0);
        return 1;
    }
    // Translucent parts keep the existing bounded drain; its replay re-enters
    // re4dc_model_submit and lands here again with draining set.
    if (re4dc_model_defer_part(&p)) { ++stats.deferred; return 1; }
    if (!prepared.shades_ready || prepared.normals != p.normals || prepared.normal_count != p.normal_count ||
        prepared.normal_stride != p.normal_stride || prepared.normal_shift != p.normal_shift ||
        std::memcmp(&prepared.lighting, p.lighting, sizeof(SourceLighting)))
        prepare_shades(p);

    Emitter e{p, {}, screen_table(), shade_table(p.position_count), {p.projection, p.viewport},
              {near_distance, far_distance, 640.0f, 480.0f, project, nullptr},
              (p.flags & 0x80000000U) ? 8U : 6U};
    e.clip.context = &e.projection;
    e.material_alpha = p.alpha_state & 255;
    e.s16_uv = (p.flags & 0x80000000U) != 0;
    e.vertex_alpha = (p.alpha_state & 256) != 0;
    e.streaming = re4dc_model_packet_streaming() != 0;
    if (!re4dc_model_packet_reserve(&p, &e.packet) || !re4dc_model_packet_begin(&p, &e.packet)) {
        re4dc_model_result(2, 0, 0);
        return 1;
    }
    if (!e.walk()) {
        if (e.committed) re4dc_model_packet_abort();
        re4dc_model_result(3, e.input, 0);
        return 1;
    }
    re4dc_model_packet_commit(e.used);
    re4dc_model_result(0, e.input, e.output);
    return 1;
}

#if defined(RE4DC_ACTOR_TEST)
extern "C" const Re4dcActorScreen* re4dc_actor_test_screen() {
    return reinterpret_cast<const Re4dcActorScreen*>(screen_table());
}
extern "C" const unsigned* re4dc_actor_test_shade() { return shade_table(prepared.position_count); }
#endif
