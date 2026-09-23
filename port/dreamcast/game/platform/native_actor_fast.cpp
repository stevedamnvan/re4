// D367 actors30: meshlet actor path (NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1).
//
// Same contract as native_actor.cpp (the source selects, animates, lights and
// orders every draw; this file only changes the render representation), with
// a representation built for the SH4 instead of per-corner GX decoding:
//
//  1. Conversion, once per part, in place. The part's GX display list (read
//     only by renderers: GXCallDisplayList is a no-op stub, and the native
//     generic/static walkers reject unknown opcodes) is rewritten into a
//     smaller native blob: <=128-vertex meshlets of unique (position, normal,
//     uv, colour) index tuples, sorted by skinning palette entry, plus u8
//     strip indices (bit 7 = end of strip). Winding and the triangle set are
//     the GX list's; opaque strips are grouped by shared tuples (translucent
//     parts keep GX order). A blob that would not fit in place is built as a
//     per-submit transient instead; if that fails too, the part declines.
//  2. Per frame per meshlet: every tuple is transformed once (ftrv through
//     screen x modelview [x palette entry] x dequantisation, fsrra 1/w) and
//     lit once (per-object directional light set, fipr dots, colour matrix by
//     ftrv) into a 32-byte PVR vertex in a 4 KiB cache; strips are then
//     copied into the packet (or store queues, NATIVE_ACTOR_DIRECT) by index.
//     Meshlets/strips wholly outside one screen edge or the near/far plane
//     are skipped; a meshlet with no vertex outside is emitted whole; strips
//     crossing near take the existing clipper per triangle (near only).
//  3. NATIVE_ACTOR_SKIN: for infos whose source CalcSk1_x pass was skipped
//     (trans.cpp keeps the source-built weight palette in the primitive
//     buffer), positions/normals are skinned here from vtxOrig/nrmOrig with
//     that palette. Anything that needs pPosBuf/pNrmBuf (the generic path)
//     first materializes them with the source's own CalcSk1_x.
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

// TA_DIRECT store-queue submission (needs the frame owner's direct API).
#ifndef RE4DC_NATIVE_ACTOR_SKIN_LAZY
#define RE4DC_NATIVE_ACTOR_SKIN_LAZY 0
#endif
#ifndef RE4DC_ACTOR_DIRECT
#define RE4DC_ACTOR_DIRECT 0
#endif
#if RE4DC_ACTOR_DIRECT
#include "ta_direct.hpp"
#endif

#ifndef RE4DC_ACTOR_ASM
#if defined(__sh__)
#define RE4DC_ACTOR_ASM 1
#else
#define RE4DC_ACTOR_ASM 0
#endif
#endif

namespace {
using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using re4dc::render::SourceLight;
using re4dc::render::SourceLighting;

Re4dcActorStats stats{};
unsigned char* workspace = nullptr;
unsigned workspace_bytes = 0, frame_serial = 0;

// ---------------------------------------------------------------- helpers --
inline unsigned be16(const u8* p) { return (unsigned(p[0]) << 8) | p[1]; }
inline bool ram(const void* p, unsigned bytes) {
#if defined(__sh__)
    const auto a = reinterpret_cast<std::uintptr_t>(p);
    return a >= 0x8c000000U && a < 0x8d000000U && bytes <= 0x8d000000U - a;
#else
    (void)bytes; return p != nullptr;
#endif
}
// 2^e for |e| < 126 without a libm call.
inline float pow2(int e) { return __builtin_bit_cast(float, u32(127 + e) << 23); }
inline float inverse_sqrt(float x) {
#if defined(__sh__)
    return __frsqrt(x);
#else
    return 1.0f / std::sqrt(x);
#endif
}
inline unsigned channel(float x) { return x <= 0.0f ? 0U : x >= 255.0f ? 255U : unsigned(x); }

// XMTRX: KOS matrix_t layout, m[column][row]. Host builds model it in C;
// the qemu-sh4 kernel test supplies its own (qemu has no ftrv).
#if defined(ACTOR_TEST_XMTRX)
ACTOR_TEST_XMTRX
#elif defined(__sh__)
inline void load_xmtrx(const float* m) { mat_load(reinterpret_cast<matrix_t*>(const_cast<float*>(m))); }
#define ACTOR_FTRV(x, y, z, w) mat_trans_nodiv(x, y, z, w)
#else
float host_xmtrx[16];
inline void load_xmtrx(const float* m) { std::memcpy(host_xmtrx, m, sizeof(host_xmtrx)); }
#define ACTOR_FTRV(x, y, z, w) do { const float _x = (x), _y = (y), _z = (z), _w = (w); \
    (x) = host_xmtrx[0] * _x + host_xmtrx[4] * _y + host_xmtrx[8] * _z + host_xmtrx[12] * _w; \
    (y) = host_xmtrx[1] * _x + host_xmtrx[5] * _y + host_xmtrx[9] * _z + host_xmtrx[13] * _w; \
    (z) = host_xmtrx[2] * _x + host_xmtrx[6] * _y + host_xmtrx[10] * _z + host_xmtrx[14] * _w; \
    (w) = host_xmtrx[3] * _x + host_xmtrx[7] * _y + host_xmtrx[11] * _z + host_xmtrx[15] * _w; } while (0)
#endif

// Plain 4x4 (column-major, like matrix_t) x vec4, for setup code only.
inline void mul4(const float* m, const float v[4], float out[4]) {
    for (unsigned r = 0; r < 4; ++r)
        out[r] = m[r] * v[0] + m[4 + r] * v[1] + m[8 + r] * v[2] + m[12 + r] * v[3];
}

// ------------------------------------------------------------ blob format --
// A converted part: header, meshlet table, then per meshlet its records
// (unique corner tuples) and u8 strip indices (bit 7 = last corner of a
// strip). Records are 3 u16 (vi, ni, ti) when every corner of the list has
// the same colour index (header.color_index; true for every D358 actor part)
// and 4 u16 (vi, ni, ti, ci) otherwise (flags bit 0).
constexpr u8 kMagic = 0xFE;  // not a GX opcode: every other walker rejects it
constexpr u8 kVersion = 2;
constexpr unsigned kMaxVertices = 128;   // u8 index, bit 7 = end of strip
constexpr unsigned kMaxIndices = 1024;   // per meshlet (packet slab ~1400)
constexpr unsigned kMaxStrip = 64;       // long GX strips are cut (2-corner overlap)
struct BlobHeader {
    u8 magic, version, flags, reserved;
    u16 meshlets, color_index;
    u32 bytes, triangles;
    float center[3], radius;  // bind-pose bounds of the referenced positions
};
static_assert(sizeof(BlobHeader) == 32, "blob header");
struct MeshletInfo { u16 vertices, indices, triangles, offset4; };  // offset4: bytes / 4
static_assert(sizeof(MeshletInfo) == 8, "meshlet header");
// A meshlet's packed records.
struct Records {
    const u16* r; unsigned stride, color;  // stride 3 or 4 u16
    unsigned vi(unsigned i) const { return r[i * stride]; }
    unsigned ni(unsigned i) const { return r[i * stride + 1]; }
    unsigned ti(unsigned i) const { return r[i * stride + 2]; }
    unsigned ci(unsigned i) const { return stride == 4 ? r[i * stride + 3] : color; }
};

inline const BlobHeader* blob_of(const Re4dcModelPart& p) {
    return p.stream_bytes >= sizeof(BlobHeader) && p.stream[0] == kMagic && p.stream[1] == kVersion
        ? reinterpret_cast<const BlobHeader*>(p.stream) : nullptr;
}

// Palette index of a vtxOrig / nrmOrig entry (0 when not skinned).
struct SortSource {
    const u8* positions = nullptr; const u8* normals = nullptr;
    unsigned position_count = 0, normal_count = 0; bool small_normals = true;
    unsigned position_palette(unsigned vi) const {
        if (!positions || vi >= position_count) return 0;
        return u16(reinterpret_cast<const short*>(positions + vi * 8)[3]);
    }
    unsigned normal_palette(unsigned ni) const {
        if (!normals || ni >= normal_count) return 0;
        return small_normals ? normals[ni * 4 + 3] : u16(reinterpret_cast<const short*>(normals + ni * 8)[3]);
    }
};

#if defined(RE4DC_ACTOR_TEST)
unsigned reject_line = 0, test_meshlets = 0, test_records = 0, test_indices = 0;
#define ACTOR_REJECT() do { reject_line = __LINE__; return false; } while (0)
#else
#define ACTOR_REJECT() return false
#endif

// Bump allocator over one conversion's scratch.
struct Arena {
    u8* p; unsigned left;
    template <class T> T* take(unsigned n) {
        const unsigned bytes = (n * unsigned(sizeof(T)) + 7U) & ~7U;
        if (bytes > left) return nullptr;
        T* r = reinterpret_cast<T*>(p); p += bytes; left -= bytes; return r;
    }
};

// One conversion, run once per part (the result replaces the GX list when it
// is no larger). Three steps:
//  1. The GX list becomes "strips": GX strips (cut at kMaxStrip corners with
//     a two-corner overlap, same winding), quads as 4-corner strips
//     (1,2,0,3), list/fan triangles as 3-corner strips.
//  2. Windows of consecutive strips (as many corners as the scratch allows;
//     whole parts for everything but the largest room objects) are packed
//     into meshlets: seeded by the first unused strip, then greedily the
//     unused strip sharing the most corner tuples with the meshlet
//     (ties: GX order), else the next unused strip that fits. Tuples are
//     deduplicated per window by exact (vi, ni, ti, ci). Translucent parts
//     keep GX order (sequential packing), so their draw order is unchanged.
//  3. Each meshlet's records are sorted by (position palette, normal
//     palette, vi) so draw-time skinning reloads matrices once per run.
// The triangle set and each triangle's winding are the GX list's.
class Converter {
public:
    Converter(const Re4dcModelPart& part, const SortSource& sort, u8* out, unsigned out_bytes, Arena scratch)
        : p(part), s(sort), out(out), capacity(out_bytes), arena(scratch),
          stride((part.flags & 0x80000000U) ? 8U : 6U) {}

    bool run() {
        if (capacity < sizeof(BlobHeader) + 64 || p.stream_bytes > 0x3FFFCU) ACTOR_REJECT();
        if (!parse()) return false;
        infos = arena.take<MeshletInfo>(strip_count);
        if (!infos) ACTOR_REJECT();
        // Per-window working set: ~24 B per corner.
        unsigned window = arena.left > 2048U ? (arena.left - 2048U) / 26U : 0U;
        if (window > corner_total) window = corner_total;
        if (window < 256U && window < corner_total) ACTOR_REJECT();
        const bool keep_order = p.blend != 0;
        used = sizeof(BlobHeader);
        for (unsigned first = 0; first < strip_count;) {
            unsigned last = first, corners = 0;
            while (last < strip_count && (last == first || corners + strips[last].n <= window)) corners += strips[last++].n;
            Arena mark = arena;
            if (!pack(first, last, corners, keep_order)) return false;
            arena = mark;
            first = last;
        }
        if (!meshlets) ACTOR_REJECT();
        const unsigned table_bytes = meshlets * sizeof(MeshletInfo);
        const unsigned data_bytes = used - sizeof(BlobHeader);
        const unsigned total = sizeof(BlobHeader) + table_bytes + data_bytes;
        if (total > capacity) ACTOR_REJECT();
        std::memmove(out + sizeof(BlobHeader) + table_bytes, out + sizeof(BlobHeader), data_bytes);
        auto* info = reinterpret_cast<MeshletInfo*>(out + sizeof(BlobHeader));
        for (unsigned i = 0; i < meshlets; ++i) {
            info[i] = infos[i];
            info[i].offset4 = u16(info[i].offset4 + table_bytes / 4U);
        }
        BlobHeader h{};
        h.magic = kMagic; h.version = kVersion; h.flags = constant_color ? 0 : 1;
        h.meshlets = u16(meshlets); h.color_index = u16(color); h.bytes = total; h.triangles = triangles;
        bounds(h);
        std::memcpy(out, &h, sizeof(h));
        size = total;
        return true;
    }
    unsigned bytes() const { return size; }

private:
    struct Strip { u32 a, b; u16 n; u8 mode, distinct; };  // mode 0 run, 1 quad (1,2,0,3), 2 fan triangle
    const Re4dcModelPart& p;
    const SortSource& s;
    u8* out;
    unsigned capacity;
    Arena arena;
    const unsigned stride;
    Strip* strips = nullptr;
    unsigned strip_count = 0, corner_total = 0;
    bool constant_color = true;
    unsigned color = 0;
    MeshletInfo* infos = nullptr;
    unsigned used = 0, size = 0, meshlets = 0, triangles = 0;
    float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
    bool any_bounds = false;

    const u8* corner(const Strip& t, unsigned k) const {
        static constexpr u8 quad[4] = {1, 2, 0, 3};
        if (t.mode == 0) return p.stream + t.a + k * stride;
        if (t.mode == 1) return p.stream + t.a + quad[k] * stride;
        return k == 0 ? p.stream + t.a : p.stream + t.b + (k - 1) * stride;
    }
    unsigned ci_of(const u8* c) const { return stride == 8 ? be16(c + 4) : 0U; }
    bool same_tuple(const u8* x, const u8* y) const {
        return be16(x) == be16(y) && be16(x + 2) == be16(y + 2) && be16(x + stride - 2) == be16(y + stride - 2) &&
               ci_of(x) == ci_of(y);
    }
    unsigned hash_of(const u8* c) const {
        return (be16(c) * 2654435761U) ^ (be16(c + 2) * 40503U) ^ (be16(c + stride - 2) * 97U) ^ ci_of(c);
    }

    // Step 1 (two passes: count, then fill).
    bool parse() {
        for (unsigned fill = 0; fill < 2; ++fill) {
            unsigned count = 0, offset = 0;
            const u8* st = p.stream;
            auto add = [&](u32 a, u32 b, unsigned n, u8 mode) {
                if (fill) strips[count] = {a, b, u16(n), mode, 0};
                ++count;
            };
            while (offset < p.stream_bytes) {
                const unsigned op = st[offset++];
                if (!op) continue;
                if (p.stream_bytes - offset < 2) ACTOR_REJECT();
                const unsigned n = be16(st + offset); offset += 2;
                if (n > (p.stream_bytes - offset) / stride) ACTOR_REJECT();
                const u32 a = offset;
                offset += n * stride;
                if (op == 0x98) {
                    if (n < 3) continue;
                    unsigned start = 0;
                    while (n - start > kMaxStrip) { add(a + start * stride, 0, kMaxStrip, 0); start += kMaxStrip - 2; }
                    add(a + start * stride, 0, n - start, 0);
                } else if (op == 0x90) {
                    if (n % 3) ACTOR_REJECT();
                    for (unsigned t = 0; t < n; t += 3) add(a + t * stride, 0, 3, 0);
                } else if (op == 0x80) {
                    if (n % 4) ACTOR_REJECT();
                    for (unsigned q = 0; q < n; q += 4) add(a + q * stride, 0, 4, 1);
                } else if (op == 0xa0) {
                    if (n == 4) add(a, 0, 4, 1);
                    else for (unsigned i = 2; i < n; ++i) add(a, a + (i - 1) * stride, 3, 2);
                } else ACTOR_REJECT();
            }
            if (!fill) {
                strip_count = count;
                if (!count) ACTOR_REJECT();
                strips = arena.take<Strip>(count);
                if (!strips) ACTOR_REJECT();
            }
        }
        corner_total = 0;
        const u8* first = corner(strips[0], 0);
        color = ci_of(first);
        for (unsigned i = 0; i < strip_count; ++i) {
            corner_total += strips[i].n;
            for (unsigned k = 0; k < strips[i].n; ++k) constant_color &= ci_of(corner(strips[i], k)) == color;
        }
        if (!constant_color) color = 0;
        return true;
    }

    // Step 2 for strips [first, last).
    bool pack(unsigned first, unsigned last, unsigned corners, bool keep_order) {
        const unsigned count = last - first;
        unsigned hash_size = 16;
        while (hash_size < corners * 2U) hash_size <<= 1;
        u16* hash = arena.take<u16>(hash_size);
        u32* tuple_corner = arena.take<u32>(corners);   // stream offset of the tuple's first corner
        u16* cid = arena.take<u16>(corners);            // per corner: tuple
        u16* strip_cid = arena.take<u16>(count);        // first cid of each strip
        u16* occ_start = arena.take<u16>(corners + 1);  // tuple -> strips (distinct), CSR
        u16* occ = arena.take<u16>(corners);
        u16* stamp = arena.take<u16>(corners);
        u8* local = arena.take<u8>(corners);
        u8* score = arena.take<u8>(count);
        u8* done = arena.take<u8>(count);
        u16* candidates = arena.take<u16>(count);
        u16* rec = arena.take<u16>(kMaxVertices);
        u8* idx = arena.take<u8>(kMaxIndices);
        if (!hash || !tuple_corner || !cid || !strip_cid || !occ_start || !occ || !stamp || !local || !score || !done ||
            !candidates || !rec || !idx) ACTOR_REJECT();
        std::memset(hash, 0, hash_size * 2U);
        unsigned tuples = 0, c = 0;
        for (unsigned i = 0; i < count; ++i) {
            const Strip& t = strips[first + i];
            strip_cid[i] = u16(c);
            for (unsigned k = 0; k < t.n; ++k, ++c) {
                const u8* v = corner(t, k);
                unsigned h = hash_of(v) & (hash_size - 1);
                while (hash[h] && !same_tuple(p.stream + tuple_corner[hash[h] - 1], v)) h = (h + 1) & (hash_size - 1);
                if (!hash[h]) { tuple_corner[tuples] = u32(v - p.stream); hash[h] = u16(++tuples); }
                cid[c] = u16(hash[h] - 1);
            }
        }
        // Distinct tuples per strip and the tuple -> strip lists.
        std::memset(occ_start, 0, (tuples + 1) * 2U);
        for (unsigned i = 0; i < tuples; ++i) stamp[i] = 0xFFFF;
        for (unsigned i = 0; i < count; ++i) {
            unsigned distinct = 0;
            for (unsigned k = 0; k < strips[first + i].n; ++k) {
                const unsigned t = cid[strip_cid[i] + k];
                if (stamp[t] != i) { stamp[t] = u16(i); ++occ_start[t + 1]; ++distinct; }
            }
            strips[first + i].distinct = u8(distinct);
        }
        for (unsigned t = 0; t < tuples; ++t) occ_start[t + 1] = u16(occ_start[t + 1] + occ_start[t]);
        for (unsigned t = 0; t < tuples; ++t) { local[t] = 0; stamp[t] = occ_start[t]; }  // stamp = fill cursor
        for (unsigned i = 0; i < count; ++i)
            for (unsigned k = 0; k < strips[first + i].n; ++k) {
                const unsigned t = cid[strip_cid[i] + k];
                if (stamp[t] == occ_start[t] || occ[stamp[t] - 1] != i) occ[stamp[t]++] = u16(i);
            }
        for (unsigned t = 0; t < tuples; ++t) stamp[t] = 0xFFFF;  // now: meshlet serial
        std::memset(score, 0, count);
        std::memset(done, 0, count);

        unsigned serial = 0, next = 0, remaining = count;
        while (remaining) {
            // New meshlet, seeded by the first unused strip.
            unsigned nrec = 0, nidx = 0, ntri = 0, ncand = 0;
            ++serial;
            while (done[next]) ++next;
            unsigned pick = next;
            for (;;) {
                const Strip& t = strips[first + pick];
                done[pick] = 1; --remaining;
                for (unsigned k = 0; k < t.n; ++k) {
                    const unsigned tu = cid[strip_cid[pick] + k];
                    if (stamp[tu] != serial) {
                        stamp[tu] = u16(serial); local[tu] = u8(nrec); rec[nrec++] = u16(tu);
                        if (!keep_order)
                            for (unsigned o = occ_start[tu]; o < occ_start[tu + 1]; ++o) {
                                const unsigned j = occ[o];
                                if (done[j]) continue;
                                if (!score[j]) candidates[ncand++] = u16(j);
                                ++score[j];
                            }
                    }
                    idx[nidx++] = u8(local[tu] | (k + 1 == t.n ? 0x80U : 0U));
                }
                ntri += t.n - 2U;
                if (!remaining) break;
                // Next strip: most shared tuples that still fits.
                unsigned best = ~0U, best_score = 0;
                for (unsigned q = 0; q < ncand; ++q) {
                    const unsigned j = candidates[q];
                    if (done[j]) continue;
                    const Strip& u = strips[first + j];
                    if (nrec + u.distinct - score[j] > kMaxVertices || nidx + u.n > kMaxIndices) continue;
                    if (score[j] > best_score || (score[j] == best_score && j < best)) { best = j; best_score = score[j]; }
                }
                if (best == ~0U) {
                    // Nothing adjacent fits (always, in keep_order mode): the
                    // first unused strip in GX order, if it fits.
                    while (next < count && done[next]) ++next;
                    if (next < count) {
                        const Strip& u = strips[first + next];
                        unsigned fresh = 0;
                        for (unsigned k = 0; k < u.n; ++k) {
                            const unsigned tu = cid[strip_cid[next] + k];
                            if (stamp[tu] != serial && stamp[tu] != 0xFFFE) { stamp[tu] = 0xFFFE; ++fresh; }  // count once
                        }
                        for (unsigned k = 0; k < u.n; ++k) {
                            const unsigned tu = cid[strip_cid[next] + k];
                            if (stamp[tu] == 0xFFFE) stamp[tu] = 0xFFFF;
                        }
                        if (nrec + fresh <= kMaxVertices && nidx + u.n <= kMaxIndices) best = next;
                    }
                }
                if (best == ~0U) break;
                pick = best;
            }
            for (unsigned q = 0; q < ncand; ++q) score[candidates[q]] = 0;
            if (!finish(rec, nrec, idx, nidx, ntri, tuple_corner)) return false;
        }
        return true;
    }

    void key_of(unsigned tuple, const u32* tuple_corner, u16 f[4]) const {
        const u8* c = p.stream + tuple_corner[tuple];
        f[0] = u16(be16(c)); f[1] = u16(be16(c + 2)); f[2] = u16(be16(c + stride - 2)); f[3] = u16(ci_of(c));
    }

    bool finish(const u16* rec, unsigned nrec, const u8* idx, unsigned nidx, unsigned ntri, const u32* tuple_corner) {
        if (!nidx) return true;
        if (meshlets == strip_count) ACTOR_REJECT();
        // Step 3: order records by (position palette, normal palette, vi).
        u8 order[kMaxVertices], remap[kMaxVertices];
        u32 key_hi[kMaxVertices], key_lo[kMaxVertices];
        u16 f[kMaxVertices][4];
        for (unsigned i = 0; i < nrec; ++i) {
            key_of(rec[i], tuple_corner, f[i]);
            order[i] = u8(i);
            key_hi[i] = (s.position_palette(f[i][0]) << 16) | s.normal_palette(f[i][1]);
            key_lo[i] = (u32(f[i][0]) << 16) | f[i][1];
        }
        for (unsigned i = 1; i < nrec; ++i) {
            const u8 o = order[i];
            unsigned j = i;
            while (j && (key_hi[order[j - 1]] > key_hi[o] || (key_hi[order[j - 1]] == key_hi[o] && key_lo[order[j - 1]] > key_lo[o]))) {
                order[j] = order[j - 1]; --j;
            }
            order[j] = o;
        }
        for (unsigned i = 0; i < nrec; ++i) remap[order[i]] = u8(i);
        const unsigned rs = constant_color ? 3U : 4U;
        const unsigned bytes = (nrec * rs * 2U + nidx + 3U) & ~3U;
        if (used + bytes > capacity || (used + bytes) / 4U > 0xFFFFU) ACTOR_REJECT();
        u16* r = reinterpret_cast<u16*>(out + used);
        for (unsigned i = 0; i < nrec; ++i) {
            const u16* e = f[order[i]];
            r[i * rs] = e[0]; r[i * rs + 1] = e[1]; r[i * rs + 2] = e[2];
            if (rs == 4) r[i * rs + 3] = e[3];
            track(e[0]);
        }
        u8* d = out + used + nrec * rs * 2U;
        for (unsigned i = 0; i < nidx; ++i) d[i] = u8(remap[idx[i] & 127U] | (idx[i] & 128U));
        for (u8* pad = d + nidx; pad < out + used + bytes; ++pad) *pad = 0;
        infos[meshlets++] = {u16(nrec), u16(nidx), u16(ntri), u16(used / 4U)};
        triangles += ntri;
        used += bytes;
#if defined(RE4DC_ACTOR_TEST)
        ++test_meshlets; test_records += nrec; test_indices += nidx;
#endif
        return true;
    }
    void track(unsigned vi) {
        const u8* base = s.positions ? s.positions : p.positions;
        const unsigned st = s.positions ? 8U : p.position_stride;
        const unsigned count = s.positions ? s.position_count : p.position_count;
        if (!base || vi >= count) return;
        const short* v = reinterpret_cast<const short*>(base + vi * st);
        for (unsigned a = 0; a < 3; ++a) { lo[a] = std::min(lo[a], float(v[a])); hi[a] = std::max(hi[a], float(v[a])); }
        any_bounds = true;
    }
    void bounds(BlobHeader& h) const {
        const float q = pow2(-int(p.shift));
        float r2 = 0.0f;
        for (unsigned a = 0; a < 3; ++a) {
            h.center[a] = any_bounds ? (lo[a] + hi[a]) * 0.5f * q : 0.0f;
            const float e = any_bounds ? (hi[a] - lo[a]) * 0.5f * q : 0.0f;
            r2 += e * e;
        }
        h.radius = std::sqrt(r2);
    }
};

// ----------------------------------------------------------- skin registry --
struct SkinEntry { const void* info; const void* positions; const float* palette; unsigned entries, materialized; };
constexpr unsigned kSkins = 64;
SkinEntry skins[kSkins];
unsigned skin_count = 0, skin_frame = ~0U;
SkinEntry* find_skin(const void* info, const void* positions) {
    for (unsigned i = 0; i < skin_count; ++i)
        if (skins[i].info == info && skins[i].positions == positions) return &skins[i];
    return nullptr;
}

// ---------------------------------------------------------- info context --
enum Mode : unsigned { kRigid = 0, kSource = 1, kSkin = 2 };
struct Frame {  // per (info, matrices) per frame
    const void* info = nullptr;
    unsigned frame = ~0U, mode = kRigid;
    float modelview[12]{}, projection[7]{}, viewport[6]{};
    const u8* positions = nullptr; const u8* normals = nullptr;
    unsigned position_stride = 0, normal_stride = 0, position_count = 0, normal_count = 0;
    bool small_normals = true;
    const float* palette = nullptr; unsigned palette_entries = 0;
    float q = 1.0f, nq = 1.0f, near_distance = 0.0f, far_distance = 0.0f;
    alignas(8) float screen[16]{};  // rows X', Y', W, W (x modelview, x q unless skinned)
    float* skin_positions = nullptr;  // palette_entries x 16 (matrix_t) or nullptr
    float* skin_dirs = nullptr;       // palette_entries x 12: light directions per entry (current part)
    u8* skin_ready = nullptr;         // per entry: skin_positions entry built this frame
    u8* dirs_ready = nullptr;         // per entry: skin_dirs entry built for this part's lights
};
constexpr unsigned kFrames = 4;
Frame frames[kFrames];
unsigned frame_victim = 0;

bool same_words(const float* a, const float* b, unsigned n) {
    const u32* x = reinterpret_cast<const u32*>(a); const u32* y = reinterpret_cast<const u32*>(b);
    for (unsigned i = 0; i < n; ++i) if (x[i] != y[i]) return false;
    return true;
}

// Frame workspace, two-ended: tables that live for the whole source frame
// (skin matrices, cached per Frame) come from the top; per-submit scratch
// (a transient conversion) from the bottom and is released by the submit.
unsigned workspace_top = 0, workspace_end = 0;
void* scratch(unsigned bytes) {  // per submit
    bytes = (bytes + 31U) & ~31U;
    if (!workspace || workspace_top + bytes > workspace_end) return nullptr;
    void* p = workspace + workspace_top; workspace_top += bytes; return p;
}
void* frame_table(unsigned bytes) {  // until the next re4dc_actor_frame
    bytes = (bytes + 31U) & ~31U;
    if (!workspace || workspace_end < workspace_top + bytes) return nullptr;
    workspace_end -= bytes;
    return workspace + workspace_end;
}

// Rows of the combined projection (see native_actor.cpp): X'/W and Y'/W are
// the generic path's project() screen coordinates, W = -Zcamera.
void screen_rows(const Re4dcModelPart& p, float M[3][4]) {
    const float* m = p.modelview; const float* P = p.projection; const float* V = p.viewport;
    const float cx = (V[0] + V[2] * 0.5f) * 640.0f / V[2];
    const float cy = (V[1] + V[3] * 0.5f) * 480.0f / V[3];
    const float rows[3][3] = {{320.0f * P[1], 0.0f, 320.0f * P[2] - cx},
                              {0.0f, -240.0f * P[3], -240.0f * P[4] - cy},
                              {0.0f, 0.0f, -1.0f}};
    for (unsigned r = 0; r < 3; ++r)
        for (unsigned c = 0; c < 4; ++c)
            M[r][c] = rows[r][0] * m[c] + rows[r][1] * m[4 + c] + rows[r][2] * m[8 + c];
}

Frame* prepare_frame(const Re4dcModelPart& p, float near_distance, float far_distance) {
    for (Frame& f : frames)
        if (f.frame == frame_serial && f.info == p.info &&
            same_words(f.modelview, p.modelview, 12) && same_words(f.projection, p.projection, 7) &&
            same_words(f.viewport, p.viewport, 6)) {
            // Mode is a function of (info, positions) within a frame.
            return &f;
        }
    Frame& f = frames[frame_victim]; frame_victim = (frame_victim + 1) % kFrames;
    f = Frame{};
    f.info = p.info; f.frame = frame_serial;
    std::memcpy(f.modelview, p.modelview, sizeof(f.modelview));
    std::memcpy(f.projection, p.projection, sizeof(f.projection));
    std::memcpy(f.viewport, p.viewport, sizeof(f.viewport));
    f.near_distance = near_distance; f.far_distance = far_distance;
    f.q = pow2(-int(p.shift));
    f.positions = p.positions; f.position_stride = p.position_stride; f.position_count = p.position_count;
    f.normals = p.normals; f.normal_stride = p.normal_stride; f.normal_count = p.normal_count;
    f.small_normals = p.normal_shift == 6; f.nq = pow2(-int(p.normal_shift));
    f.mode = p.position_stride == 8 ? kRigid : kSource;
    if (p.position_stride == 6) {
        unsigned entries = 0;
        const float* palette = re4dc_actor_skin_palette(p.info, p.positions, &entries);
        Re4dcActorSource src{};
        if (palette && entries && re4dc_actor_model_source(p.info, &src) && src.positions && src.normals &&
            src.position_count == p.position_count && src.normal_count == p.normal_count &&
            bool(src.small_normals) == (p.normal_shift == 6)) {
            f.mode = kSkin; f.palette = palette; f.palette_entries = entries;
            f.positions = src.positions; f.position_stride = 8;
            f.normals = src.normals; f.normal_stride = src.small_normals ? 4U : 8U;
            // One skin table at a time (parts arrive info by info): an older
            // skinned Frame is dropped from the cache and its table reused.
            for (Frame& o : frames)
                if (&o != &f && o.skin_positions) {
                    o.frame = ~0U; o.skin_positions = o.skin_dirs = nullptr; o.skin_ready = o.dirs_ready = nullptr;
                }
            workspace_end = workspace_bytes;
            f.skin_positions = static_cast<float*>(frame_table(entries * (28U * 4U + 2U)));
            if (f.skin_positions) {
                f.skin_dirs = f.skin_positions + entries * 16U;
                f.skin_ready = reinterpret_cast<u8*>(f.skin_dirs + entries * 12U);
                f.dirs_ready = f.skin_ready + entries;
                std::memset(f.skin_ready, 0, entries * 2U);
            }
            ++stats.skinned_parts;
        }
    }
    float M[3][4];
    screen_rows(p, M);
    const float s = f.mode == kSkin ? 1.0f : f.q;
    for (unsigned c = 0; c < 4; ++c) {
        const float k = c < 3 ? s : 1.0f;
        f.screen[c * 4 + 0] = M[0][c] * k; f.screen[c * 4 + 1] = M[1][c] * k;
        f.screen[c * 4 + 2] = M[2][c] * k; f.screen[c * 4 + 3] = M[2][c] * k;
    }
    ++stats.info_preparations;
    return &f;
}

// Combined matrix of palette entry i (skinned): screen x [R_i*q | t_i].
void skin_position_matrix(const Frame& f, unsigned i, float out[16]) {
    const float* P = f.palette + i * 12;  // reordered ROMtx: columns R0,R1,R2,t
    for (unsigned c = 0; c < 4; ++c) {
        const float v[4] = {P[c * 3] * (c < 3 ? f.q : 1.0f), P[c * 3 + 1] * (c < 3 ? f.q : 1.0f),
                            P[c * 3 + 2] * (c < 3 ? f.q : 1.0f), c < 3 ? 0.0f : 1.0f};
        mul4(f.screen, v, out + c * 4);
    }
}
const float* position_matrix(Frame& f, unsigned i, float* fallback) {
    if (i >= f.palette_entries) i = 0;
    if (!f.skin_positions) { skin_position_matrix(f, i, fallback); return fallback; }
    float* m = f.skin_positions + i * 16;
    if (!f.skin_ready[i]) { skin_position_matrix(f, i, m); f.skin_ready[i] = 1; }
    return m;
}

// ---------------------------------------------------------------- lights --
// The source-selected GX lights folded into <=3 directional lights in the
// normals' own space plus a colour matrix: lit = min(cap, C * (m0,m1,m2,1))
// with m_l = d_l + |d_l| (= 2 max(0, n.l_l)); C carries 0.5 x colour x scale
// in columns 0..2 and ambient x scale in column 3. Same per-object
// approximation (evaluated at the part centre) as native_actor.cpp.
struct Lights {
    bool fast = false;       // directional fold valid: diffuse clamp, <=3 lights, caps 255
    bool constant = false;   // lighting disabled: one colour for every vertex
    unsigned count = 0;
    u32 constant_rgb = 0;
    float dir[3][4]{};       // normal space, x nq (w = 0)
    alignas(8) float color[16]{};
    const SourceLighting* source = nullptr;
    re4dc::render::PreparedSourceLights prepared;
};

bool build_lights(const Re4dcModelPart& p, const Frame& f, const float center[3], Lights& L) {
    const SourceLighting& S = *p.lighting;
    L = Lights{};
    L.source = &S;
    constexpr float k = 1.0f / 255.0f;
    float scale[3], ambient[3];
    bool caps255 = true;
    for (unsigned c = 0; c < 3; ++c) {
        scale[c] = S.material[c] * k * S.tev_scale * 255.0f;
        ambient[c] = S.enable ? S.ambient[c] * k : 1.0f;
        caps255 &= scale[c] >= 255.0f;
    }
    if (S.ambient_vertex || S.material_vertex) return false;  // per-vertex colour: slow path
    if (!S.enable) {
        L.constant = true;
        L.constant_rgb = (channel(std::min(ambient[0], 1.0f) * scale[0]) << 16) |
                         (channel(std::min(ambient[1], 1.0f) * scale[1]) << 8) | channel(std::min(ambient[2], 1.0f) * scale[2]);
        return true;
    }
    if (S.diffuse != 2 || !caps255) return false;
    const float* m = p.modelview;
    const float px = m[0] * center[0] + m[1] * center[1] + m[2] * center[2] + m[3];
    const float py = m[4] * center[0] + m[5] * center[1] + m[6] * center[2] + m[7];
    const float pz = m[8] * center[0] + m[9] * center[1] + m[10] * center[2] + m[11];
    const float* N = S.normal_matrix;
    float col[3][3]{};
    for (unsigned i = 0; i < 8; ++i) {
        if (!(S.mask & (1U << i))) continue;
        const SourceLight& s = S.lights[i];
        float lx = s.position[0] - px, ly = s.position[1] - py, lz = s.position[2] - pz;
        const float d2 = lx * lx + ly * ly + lz * lz, d = std::sqrt(d2);
        if (d > 0.0f) { const float r = 1.0f / d; lx *= r; ly *= r; lz *= r; }
        else { lx = 0.0f; ly = 0.0f; lz = 1.0f; }
        float attenuation = 1.0f;
        if (S.attenuation == 1) {
            const float cosine = std::max(0.0f, lx * s.direction[0] + ly * s.direction[1] + lz * s.direction[2]);
            const float angular = std::max(0.0f, s.a[0] + s.a[1] * cosine + s.a[2] * cosine * cosine);
            const float denominator = s.k[0] + s.k[1] * d + s.k[2] * d2;
            attenuation = denominator > 0.0f ? angular / denominator : 0.0f;
        }
        if (s.k[1] != 0.0f || s.k[2] != 0.0f) ++stats.attenuated_lights;
        const float red = s.color[0] * k * attenuation, green = s.color[1] * k * attenuation,
                    blue = s.color[2] * k * attenuation;
        if (std::max(red, std::max(green, blue)) <= 1.0f / 1024.0f) continue;
        if (L.count == 3) return false;  // fourth significant light: slow path
        float* o = L.dir[L.count];
        o[0] = (N[0] * lx + N[4] * ly + N[8] * lz) * f.nq;
        o[1] = (N[1] * lx + N[5] * ly + N[9] * lz) * f.nq;
        o[2] = (N[2] * lx + N[6] * ly + N[10] * lz) * f.nq;
        o[3] = 0.0f;
        col[L.count][0] = red; col[L.count][1] = green; col[L.count][2] = blue;
        ++L.count;
    }
    // Colour matrix (matrix_t: [column][row]); input (m0, m1, m2, 1).
    for (unsigned l = 0; l < 3; ++l)
        for (unsigned c = 0; c < 3; ++c) L.color[l * 4 + c] = 0.5f * col[l][c] * scale[c];
    for (unsigned c = 0; c < 3; ++c) L.color[12 + c] = ambient[c] * scale[c];
    L.fast = true;
    ++stats.light_sets;
    return true;
}

// Light directions of palette entry i (skinned normals): R_i^T l, w = 0,
// cached per entry for the current part's light set.
const float* skin_light_dirs(Frame& f, const Lights& L, unsigned i, float* fallback) {
    if (i >= f.palette_entries) i = 0;
    float* out = f.skin_dirs ? f.skin_dirs + i * 12 : fallback;
    if (f.skin_dirs && f.dirs_ready[i]) return out;
    const float* P = f.palette + i * 12;
    for (unsigned l = 0; l < 3; ++l)
        for (unsigned c = 0; c < 3; ++c)
            out[l * 4 + c] = P[c * 3] * L.dir[l][0] + P[c * 3 + 1] * L.dir[l][1] + P[c * 3 + 2] * L.dir[l][2];
    out[3] = out[7] = out[11] = 0.0f;
    if (f.skin_dirs) f.dirs_ready[i] = 1;
    return out;
}

// ----------------------------------------------------------- the meshlet --
// Outcode bits, built MSB-first by the SH4 kernel's rotcl chain.
constexpr unsigned kOcFar = 1, kOcNear = 2, kOcBottom = 4, kOcTop = 8, kOcRight = 16, kOcLeft = 32;
// Near is the only clipped plane; far and the screen edges only cull (whole
// meshlets / strips), the PVR scissors the rest. Bits above 5 are don't-care.
constexpr unsigned kOcScreen = kOcBottom | kOcTop | kOcRight | kOcLeft, kOcCull = kOcScreen | kOcFar;

// Per-meshlet vertex cache: 128 PVR vertices + 128 outcode bytes (132 slots
// of 32 bytes), carved from the tail of the part's own packet range, which
// is never sent; <= 4.2 KiB, so a meshlet's working set stays in the 16 KiB
// operand cache with its records and indices.
constexpr unsigned kCacheSlots = kMaxVertices + kMaxVertices / 32U;
struct Cache { pvr_vertex_t* v; u8* oc; };

// Position pass constants; the SH4 kernel keeps them in fr7..fr15.
struct PosConst { float zero, au, bu, av, bv, width, height, near_distance, far_distance; };
// Fast light pass: directions 0/1 (fv8/fv12 in the kernel), direction 2
// (reloaded per vertex into fv0), each with w = 0; then the 255 clamp.
struct alignas(8) LightConst { float l0[4], l1[4], l2[4], cap; };

// qemu-sh4 test builds substitute these (qemu has no ftrv/fipr/fsrra).
#ifndef ACTOR_ASM_FTRV
#define ACTOR_ASM_FTRV "ftrv    xmtrx,fv0\n\t"
#define ACTOR_ASM_FSRRA4 "fsrra   fr4\n\t"
#define ACTOR_ASM_FIPR(a) "fipr    " a ",fv4\n\t"
#define ACTOR_ASM_CLOBBER
#endif
#ifndef ACTOR_FSRRA
#define ACTOR_FSRRA(x) inverse_sqrt(x)
#endif
#ifndef ACTOR_DOT3
#define ACTOR_DOT3(a, x, y, z) ((a)[0] * (x) + (a)[1] * (y) + (a)[2] * (z))
#endif

// Pass 1, portable (host; SH4 variants without a kernel; kernel reference).
// Records [0, n) (rs bytes each): position through XMTRX, 1/|w| by
// rsqrt(w^2), x/y scaled, u/v = t * a + b, one outcode byte. With check,
// stops before the first record whose position palette index != palette.
unsigned positions_c(const u8* rec, unsigned rs, unsigned n, const u8* pos, unsigned ps, bool check, int palette,
                     const u8* uv, bool s16_uv, pvr_vertex_t* dst, u8* oc, const PosConst& k, unsigned& all,
                     unsigned& any) {
    unsigned i = 0;
    for (; i < n; ++i, rec += rs) {
        const u16* r = reinterpret_cast<const u16*>(rec);
        const short* s = reinterpret_cast<const short*>(pos + r[0] * ps);
        if (check && s[3] != palette) break;
        const u8* t = uv + r[2] * 4U;
        const float tu = s16_uv ? float(*reinterpret_cast<const short*>(t)) : float(*reinterpret_cast<const u16*>(t));
        const float tv = s16_uv ? float(*reinterpret_cast<const short*>(t + 2)) : float(*reinterpret_cast<const u16*>(t + 2));
        float x = float(s[0]), y = float(s[1]), z = float(s[2]), w = 1.0f;
        ACTOR_FTRV(x, y, z, w);
        const float inv = ACTOR_FSRRA(w * w);
        x *= inv; y *= inv;
        const unsigned code = (k.zero > x ? kOcLeft : 0U) | (x > k.width ? kOcRight : 0U) | (k.zero > y ? kOcTop : 0U) |
                              (y > k.height ? kOcBottom : 0U) | (k.near_distance > w ? kOcNear : 0U) |
                              (w > k.far_distance ? kOcFar : 0U);
        pvr_vertex_t& d = dst[i];
        d.x = x; d.y = y; d.z = inv;
        d.u = tu * k.au + k.bu; d.v = tv * k.av + k.bv;
        oc[i] = u8(code);
        all &= code; any |= code;
    }
    return i;
}

// Pass 2 (fast lights), portable. XMTRX holds the colour matrix. Small (s8)
// normals only; with check, stops at the first record whose normal palette
// index (byte 3) != palette.
unsigned lights_c(const u8* rec, unsigned rs, unsigned n, const u8* nrm, unsigned ns, bool check, unsigned palette,
                  pvr_vertex_t* dst, const LightConst& L, u32 alpha) {
    unsigned i = 0;
    for (; i < n; ++i, rec += rs) {
        const u16* r = reinterpret_cast<const u16*>(rec);
        const signed char* s = reinterpret_cast<const signed char*>(nrm + r[1] * ns);
        if (check && u8(s[3]) != palette) break;
        const float nx = s[0], ny = s[1], nz = s[2];
        const float d2 = ACTOR_DOT3(L.l2, nx, ny, nz), d0 = ACTOR_DOT3(L.l0, nx, ny, nz), d1 = ACTOR_DOT3(L.l1, nx, ny, nz);
        float m0 = std::fabs(d0) + d0, m1 = std::fabs(d1) + d1, m2 = std::fabs(d2) + d2, one = 1.0f;
        ACTOR_FTRV(m0, m1, m2, one);
        if (m0 > L.cap) m0 = L.cap;
        if (m1 > L.cap) m1 = L.cap;
        if (m2 > L.cap) m2 = L.cap;
        dst[i].argb = alpha | (u32(int(m0)) << 16) | (u32(int(m1)) << 8) | u32(int(m2));
    }
    return i;
}

#if defined(__sh__) && RE4DC_ACTOR_ASM
// SH4 pass 1: one dynarec block per record (no calls, no spills), constants
// resident in fr7..fr15, stores through one pre-decrementing pointer.
// ~58 instructions per record (Flycast issue model ~40 cycles).
#define ACTOR_POS_ADDR8 "shll2   r1\n\t" "shll    r1\n\t"
#define ACTOR_POS_ADDR6 "mov     r1,r2\n\t" "shll    r1\n\t" "add     r2,r1\n\t" "shll    r1\n\t"
#define ACTOR_POS_CHECK "mov.w   @(6,r1),r0\n\t" "cmp/eq  %[pal],r0\n\t" "bf      9f\n\t"
#define ACTOR_POS_ASM(ADDR, CHECK) \
    "fmov.s  @%[k]+,fr7\n\t"  "fmov.s  @%[k]+,fr8\n\t"  "fmov.s  @%[k]+,fr9\n\t" \
    "fmov.s  @%[k]+,fr10\n\t" "fmov.s  @%[k]+,fr11\n\t" "fmov.s  @%[k]+,fr12\n\t" \
    "fmov.s  @%[k]+,fr13\n\t" "fmov.s  @%[k]+,fr14\n\t" "fmov.s  @%[k]+,fr15\n" \
    "1:\n\t" \
    "mov.w   @%[rec],r1\n\t"        /* vi */ \
    ADDR \
    "add     %[pos],r1\n\t" \
    CHECK \
    "mov.w   @(4,%[rec]),r0\n\t"    /* ti */ \
    "add     %[rs],%[rec]\n\t" \
    "shll2   r0\n\t" \
    "add     %[uv],r0\n\t" \
    "mov.w   @r0+,r2\n\t" \
    "mov.w   @r0,r0\n\t" \
    "lds     r2,fpul\n\t" "float   fpul,fr0\n\t" "fmov    fr9,fr5\n\t"  "fmac    fr0,fr8,fr5\n\t" \
    "lds     r0,fpul\n\t" "float   fpul,fr0\n\t" "fmov    fr11,fr6\n\t" "fmac    fr0,fr10,fr6\n\t" \
    "mov.w   @r1+,r2\n\t" \
    "mov.w   @r1+,r0\n\t" \
    "lds     r2,fpul\n\t" "float   fpul,fr0\n\t" \
    "mov.w   @r1,r2\n\t" \
    "lds     r0,fpul\n\t" "float   fpul,fr1\n\t" \
    "lds     r2,fpul\n\t" "float   fpul,fr2\n\t" \
    "fldi1   fr3\n\t" \
    ACTOR_ASM_FTRV \
    "fmov    fr3,fr4\n\t" \
    "fmul    fr4,fr4\n\t" \
    ACTOR_ASM_FSRRA4                /* 1/|w| */ \
    "fmov.s  fr6,@-%[dst]\n\t"      /* v @20 */ \
    "fmov.s  fr5,@-%[dst]\n\t"      /* u @16 */ \
    "fmov.s  fr4,@-%[dst]\n\t"      /* z @12 */ \
    "fmul    fr4,fr0\n\t" \
    "fmul    fr4,fr1\n\t" \
    "fmov.s  fr1,@-%[dst]\n\t"      /* y @8  */ \
    "fmov.s  fr0,@-%[dst]\n\t"      /* x @4  */ \
    "fcmp/gt fr0,fr7\n\t"  "rotcl   r1\n\t"     /* x<0    */ \
    "fcmp/gt fr12,fr0\n\t" "rotcl   r1\n\t"     /* x>640  */ \
    "fcmp/gt fr1,fr7\n\t"  "rotcl   r1\n\t"     /* y<0    */ \
    "fcmp/gt fr13,fr1\n\t" "rotcl   r1\n\t"     /* y>480  */ \
    "fcmp/gt fr3,fr14\n\t" "rotcl   r1\n\t"     /* w<near */ \
    "fcmp/gt fr15,fr3\n\t" "rotcl   r1\n\t"     /* w>far  */ \
    "mov.b   r1,@%[oc]\n\t" \
    "add     #1,%[oc]\n\t" \
    "and     r1,%[all]\n\t" \
    "or      r1,%[any]\n\t" \
    "dt      %[n]\n\t" \
    "bf/s    1b\n\t" \
    "add     #52,%[dst]\n"          /* entry+4 -> next entry+24 */ \
    "9:\n\t"
#define ACTOR_POS_OPERANDS \
    : [rec] "+r"(rec), [n] "+r"(left), [dst] "+r"(d), [oc] "+r"(oc), [k] "+r"(kp), [all] "+r"(a), [any] "+r"(o) \
    : [rs] "r"(rs), [pos] "r"(pos), [uv] "r"(uv), [pal] "r"(palette) \
    : "r0", "r1", "r2", "fpul", "fr0", "fr1", "fr2", "fr3", "fr4", "fr5", "fr6", "fr7", "fr8", "fr9", \
      "fr10", "fr11", "fr12", "fr13", "fr14", "fr15", "t", "memory" ACTOR_ASM_CLOBBER
enum PosKernel : unsigned { kPos8 = 0, kPos8Check = 1, kPos6 = 2 };
template <unsigned V>
unsigned positions_asm(const u8* rec, unsigned rs, unsigned n, const u8* pos, int palette, const u8* uv,
                       pvr_vertex_t* dst, u8* oc, const PosConst& k, unsigned& all, unsigned& any) {
    unsigned left = n, a = all, o = any;
    const float* kp = &k.zero;
    float* d = reinterpret_cast<float*>(reinterpret_cast<u8*>(dst) + 24);
    if constexpr (V == kPos8)
        __asm__ __volatile__(ACTOR_POS_ASM(ACTOR_POS_ADDR8, "") ACTOR_POS_OPERANDS);
    else if constexpr (V == kPos8Check)
        __asm__ __volatile__(ACTOR_POS_ASM(ACTOR_POS_ADDR8, ACTOR_POS_CHECK) ACTOR_POS_OPERANDS);
    else
        __asm__ __volatile__(ACTOR_POS_ASM(ACTOR_POS_ADDR6, "") ACTOR_POS_OPERANDS);
    all = a; any = o;
    return n - left;
}

// SH4 pass 2 (fast lights): fipr per light (fv8, fv12 resident; direction 2
// reloaded into fv0), m = d + |d|, colour by ftrv, clamp, pack.
#define ACTOR_NRM_ADDR4 "shll2   r0\n\t"
#define ACTOR_NRM_ADDR3 "mov     r0,r1\n\t" "shll    r0\n\t" "add     r1,r0\n\t"
#define ACTOR_NRM_CHECK "mov.b   @(3,r3),r0\n\t" "extu.b  r0,r0\n\t" "cmp/eq  %[pal],r0\n\t" "bf      9f\n\t"
#define ACTOR_LIGHT_ASM(ADDR, CHECK) \
    "fmov.s  @%[l]+,fr8\n\t"  "fmov.s  @%[l]+,fr9\n\t"  "fmov.s  @%[l]+,fr10\n\t" "fmov.s  @%[l]+,fr11\n\t" \
    "fmov.s  @%[l]+,fr12\n\t" "fmov.s  @%[l]+,fr13\n\t" "fmov.s  @%[l]+,fr14\n\t" "fmov.s  @%[l]+,fr15\n\t" \
    "fldi0   fr7\n" \
    "1:\n\t" \
    "mov.w   @(2,%[rec]),r0\n\t"    /* ni */ \
    "add     %[rs],%[rec]\n\t" \
    ADDR \
    "add     %[nrm],r0\n\t" \
    "mov     r0,r3\n\t" \
    CHECK \
    "mov.b   @r3+,r1\n\t" \
    "mov.b   @r3+,r2\n\t" \
    "mov.b   @r3,r3\n\t" \
    "lds     r1,fpul\n\t" "float   fpul,fr4\n\t" \
    "lds     r2,fpul\n\t" "float   fpul,fr5\n\t" \
    "lds     r3,fpul\n\t" "float   fpul,fr6\n\t" \
    "fmov.s  @%[l]+,fr0\n\t" "fmov.s  @%[l]+,fr1\n\t" "fmov.s  @%[l]+,fr2\n\t" "fmov.s  @%[l],fr3\n\t" \
    "add     #-12,%[l]\n\t" \
    ACTOR_ASM_FIPR("fv0") \
    "fmov    fr7,fr2\n\t" "fabs    fr2\n\t" "fadd    fr7,fr2\n\t"   /* m2 */ \
    ACTOR_ASM_FIPR("fv8") \
    "fmov    fr7,fr0\n\t" "fabs    fr0\n\t" "fadd    fr7,fr0\n\t"   /* m0 */ \
    ACTOR_ASM_FIPR("fv12") \
    "fmov    fr7,fr1\n\t" "fabs    fr1\n\t" "fadd    fr7,fr1\n\t"   /* m1 */ \
    "fldi1   fr3\n\t" \
    ACTOR_ASM_FTRV \
    "fmov.s  @%[cap],fr3\n\t" \
    "fcmp/gt fr3,fr0\n\t" "bf      2f\n\t" "fmov    fr3,fr0\n" "2:\n\t" \
    "fcmp/gt fr3,fr1\n\t" "bf      3f\n\t" "fmov    fr3,fr1\n" "3:\n\t" \
    "fcmp/gt fr3,fr2\n\t" "bf      4f\n\t" "fmov    fr3,fr2\n" "4:\n\t" \
    "ftrc    fr0,fpul\n\t" "sts     fpul,r1\n\t" \
    "ftrc    fr1,fpul\n\t" "sts     fpul,r2\n\t" \
    "ftrc    fr2,fpul\n\t" "sts     fpul,r3\n\t" \
    "shll16  r1\n\t" \
    "shll8   r2\n\t" \
    "or      r2,r1\n\t" \
    "or      r3,r1\n\t" \
    "or      %[alpha],r1\n\t" \
    "mov.l   r1,@%[dst]\n\t" \
    "dt      %[n]\n\t" \
    "bf/s    1b\n\t" \
    "add     #32,%[dst]\n" \
    "9:\n\t"
#define ACTOR_LIGHT_OPERANDS \
    : [rec] "+r"(rec), [n] "+r"(left), [dst] "+r"(d), [l] "+r"(lp) \
    : [rs] "r"(rs), [nrm] "r"(nrm), [cap] "r"(&L.cap), [alpha] "r"(alpha), [pal] "r"(palette) \
    : "r0", "r1", "r2", "r3", "fpul", "fr0", "fr1", "fr2", "fr3", "fr4", "fr5", "fr6", "fr7", "fr8", "fr9", \
      "fr10", "fr11", "fr12", "fr13", "fr14", "fr15", "t", "memory" ACTOR_ASM_CLOBBER
enum LightKernel : unsigned { kNrm4 = 0, kNrm4Check = 1, kNrm3 = 2 };
template <unsigned V>
unsigned lights_asm(const u8* rec, unsigned rs, unsigned n, const u8* nrm, unsigned palette, pvr_vertex_t* dst,
                    const LightConst& L, u32 alpha) {
    unsigned left = n;
    const float* lp = L.l0;
    u32* d = &dst->argb;
    if constexpr (V == kNrm4)
        __asm__ __volatile__(ACTOR_LIGHT_ASM(ACTOR_NRM_ADDR4, "") ACTOR_LIGHT_OPERANDS);
    else if constexpr (V == kNrm4Check)
        __asm__ __volatile__(ACTOR_LIGHT_ASM(ACTOR_NRM_ADDR4, ACTOR_NRM_CHECK) ACTOR_LIGHT_OPERANDS);
    else
        __asm__ __volatile__(ACTOR_LIGHT_ASM(ACTOR_NRM_ADDR3, "") ACTOR_LIGHT_OPERANDS);
    return n - left;
}
#endif

// One strip starting at index: corner count and AND/OR of its outcodes.
struct Strip { unsigned n, all, any; };
inline Strip scan(const u8* oc, const u8* index) {
#if defined(__sh__) && RE4DC_ACTOR_ASM
    unsigned n = 0, all = ~0U, any = 0;
    __asm__(
        "1:\n\t"
        "mov.b   @%[index]+,r0\n\t"   /* sign-extended: EOL -> negative */
        "cmp/pz  r0\n\t"
        "and     #127,r0\n\t"
        "mov.b   @(r0,%[oc]),r1\n\t"
        "add     #1,%[n]\n\t"
        "and     r1,%[all]\n\t"
        "bt/s    1b\n\t"
        "or      r1,%[any]\n\t"
        : [n] "+r"(n), [all] "+r"(all), [any] "+r"(any), [index] "+r"(index)
        : [oc] "r"(oc), "m"(*reinterpret_cast<const u8(*)[kMaxVertices]>(oc))
        : "r0", "r1", "t");
    return {n, all, any};
#else
    Strip s{0, ~0U, 0};
    for (;;) {
        const unsigned e = index[s.n++], c = oc[e & 127U];
        s.all &= c; s.any |= c;
        if (e & 128U) return s;
    }
#endif
}

// Copy the n (>= 1) cache entries of one strip into 32-byte aligned packet
// storage; the last one becomes EOL. 64-bit FPU moves (FPSCR.SZ), as in the
// scenery meshlet path (mesh_fastpath.hpp emit()).
inline pvr_vertex_t* emit(pvr_vertex_t* dst, const pvr_vertex_t* cache, const u8* index, unsigned n) {
#if defined(__sh__) && RE4DC_ACTOR_ASM
    __asm__ __volatile__(
        "fschg\n"
        "1:\n\t"
        "mov.b   @%[index]+,r0\n\t"
        "and     #127,r0\n\t"
        "shld    %[five],r0\n\t"
        "add     %[cache],r0\n\t"
        "fmov    @r0+,dr0\n\t"
        "fmov    @r0+,dr2\n\t"
        "fmov    @r0+,dr4\n\t"
        "fmov    @r0+,dr6\n\t"
        "add     #32,%[dst]\n\t"
        "fmov    dr6,@-%[dst]\n\t"
        "fmov    dr4,@-%[dst]\n\t"
        "fmov    dr2,@-%[dst]\n\t"
        "fmov    dr0,@-%[dst]\n\t"
        "dt      %[n]\n\t"
        "bf/s    1b\n\t"
        "add     #32,%[dst]\n\t"
        "fschg\n"
        : [dst] "+r"(dst), [index] "+r"(index), [n] "+r"(n)
        : [cache] "r"(cache), [five] "r"(5)
        : "r0", "fr0", "fr1", "fr2", "fr3", "fr4", "fr5", "fr6", "fr7", "t", "memory");
    dst[-1].flags = PVR_CMD_VERTEX_EOL;
    return dst;
#else
    for (unsigned k = 0; k < n; ++k) dst[k] = cache[index[k] & 127U];
    dst[n - 1].flags = PVR_CMD_VERTEX_EOL;
    return dst + n;
#endif
}

// A whole meshlet whose strips all qualify (no corner outside a screen edge,
// beyond far or in front of near): every index copied in one loop, the flags
// word derived from index bit 7 (sign of the loaded byte: >> 3 keeps bit 28).
// SQ = true: into the TA store queues, one burst per vertex.
template <bool SQ>
inline void* emit_meshlet(void* dst, const pvr_vertex_t* cache, const u8* index, unsigned n) {
#if defined(__sh__) && RE4DC_ACTOR_ASM
    const u32 vertex = PVR_CMD_VERTEX, eol_bit = PVR_CMD_VERTEX_EOL ^ PVR_CMD_VERTEX;
    auto* d = static_cast<u32*>(dst);
#define ACTOR_EMIT_MESHLET(PREF) \
        "fschg\n" \
        "1:\n\t" \
        "mov.b   @%[index]+,r0\n\t" \
        "mov     r0,r1\n\t" \
        "and     #127,r0\n\t" \
        "shld    %[five],r0\n\t" \
        "add     %[cache],r0\n\t" \
        "fmov    @r0+,dr0\n\t" \
        "fmov    @r0+,dr2\n\t" \
        "fmov    @r0+,dr4\n\t" \
        "fmov    @r0+,dr6\n\t" \
        "shlr2   r1\n\t" \
        "shlr    r1\n\t" \
        "and     %[eol],r1\n\t" \
        "or      %[vertex],r1\n\t" \
        "add     #32,%[dst]\n\t" \
        "fmov    dr6,@-%[dst]\n\t" \
        "fmov    dr4,@-%[dst]\n\t" \
        "fmov    dr2,@-%[dst]\n\t" \
        "fmov    dr0,@-%[dst]\n\t" \
        "mov.l   r1,@%[dst]\n\t" \
        PREF \
        "dt      %[n]\n\t" \
        "bf/s    1b\n\t" \
        "add     #32,%[dst]\n\t" \
        "fschg\n" \
        : [dst] "+r"(d), [index] "+r"(index), [n] "+r"(n) \
        : [cache] "r"(cache), [five] "r"(5), [eol] "r"(eol_bit), [vertex] "r"(vertex) \
        : "r0", "r1", "fr0", "fr1", "fr2", "fr3", "fr4", "fr5", "fr6", "fr7", "t", "memory"
    if constexpr (SQ) __asm__ __volatile__(ACTOR_EMIT_MESHLET("pref    @%[dst]\n\t"));
    else __asm__ __volatile__(ACTOR_EMIT_MESHLET(""));
#undef ACTOR_EMIT_MESHLET
    return d;
#else
    static_assert(!SQ, "store queues are SH4 only");
    auto* d = static_cast<pvr_vertex_t*>(dst);
    for (unsigned k = 0; k < n; ++k) {
        d[k] = cache[index[k] & 127U];
        d[k].flags = (index[k] & 128U) ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
    }
    return d + n;
#endif
}

#if RE4DC_ACTOR_DIRECT
// The same copy straight into the TA through the store queues (TA_DIRECT):
// EOL goes into the last vertex before its burst leaves.
inline std::uint32_t* emit_sq(std::uint32_t* sq, const pvr_vertex_t* cache, const u8* index, unsigned n) {
    const std::uint32_t eol = PVR_CMD_VERTEX_EOL;
    __asm__ __volatile__(
        "fschg\n"
        "1:\n\t"
        "mov.b   @%[index]+,r0\n\t"
        "and     #127,r0\n\t"
        "shld    %[five],r0\n\t"
        "add     %[cache],r0\n\t"
        "fmov    @r0+,dr0\n\t"
        "fmov    @r0+,dr2\n\t"
        "fmov    @r0+,dr4\n\t"
        "fmov    @r0+,dr6\n\t"
        "add     #32,%[sq]\n\t"
        "fmov    dr6,@-%[sq]\n\t"
        "fmov    dr4,@-%[sq]\n\t"
        "fmov    dr2,@-%[sq]\n\t"
        "dt      %[n]\n\t"
        "bf/s    2f\n\t"
        "fmov    dr0,@-%[sq]\n\t"
        "mov.l   %[eol],@%[sq]\n"
        "2:\n\t"
        "pref    @%[sq]\n\t"
        "tst     %[n],%[n]\n\t"
        "bf/s    1b\n\t"
        "add     #32,%[sq]\n\t"
        "fschg\n"
        : [sq] "+r"(sq), [index] "+r"(index), [n] "+r"(n)
        : [cache] "r"(cache), [five] "r"(5), [eol] "r"(eol)
        : "r0", "fr0", "fr1", "fr2", "fr3", "fr4", "fr5", "fr6", "fr7", "t", "memory");
    return sq;
}
#endif

// World (camera) position and normal-space normal of a record, for the
// clipper and the exact slow lighting path.
void world_of(const Frame& f, const Re4dcModelPart& p, const Records& r, unsigned i, float w[3], float n[3]) {
    const short* s = reinterpret_cast<const short*>(f.positions + r.vi(i) * f.position_stride);
    float a = s[0] * f.q, b = s[1] * f.q, c = s[2] * f.q;
    float nx, ny, nz;
    int npi = 0;
    if (f.small_normals) {
        const signed char* t = reinterpret_cast<const signed char*>(f.normals + r.ni(i) * f.normal_stride);
        nx = t[0]; ny = t[1]; nz = t[2]; npi = f.mode == kSkin ? int(u8(t[3])) : 0;
    } else {
        const short* t = reinterpret_cast<const short*>(f.normals + r.ni(i) * f.normal_stride);
        nx = t[0]; ny = t[1]; nz = t[2]; npi = f.mode == kSkin ? int(u16(t[3])) : 0;
    }
    if (f.mode == kSkin) {
        const unsigned pi = unsigned(u16(s[3])) < f.palette_entries ? unsigned(u16(s[3])) : 0U;
        const float* P = f.palette + pi * 12;
        const float x = P[0] * a + P[3] * b + P[6] * c + P[9];
        const float y = P[1] * a + P[4] * b + P[7] * c + P[10];
        const float z = P[2] * a + P[5] * b + P[8] * c + P[11];
        a = x; b = y; c = z;
        const float* R = f.palette + (unsigned(npi) < f.palette_entries ? unsigned(npi) : 0U) * 12;
        const float rx = R[0] * nx + R[3] * ny + R[6] * nz;
        const float ry = R[1] * nx + R[4] * ny + R[7] * nz;
        const float rz = R[2] * nx + R[5] * ny + R[8] * nz;
        nx = rx; ny = ry; nz = rz;
    }
    const float* m = p.modelview;
    w[0] = m[0] * a + m[1] * b + m[2] * c + m[3];
    w[1] = m[4] * a + m[5] * b + m[6] * c + m[7];
    w[2] = m[8] * a + m[9] * b + m[10] * c + m[11];
    nx *= f.nq; ny *= f.nq; nz *= f.nq;
    const float* N = p.lighting ? p.lighting->normal_matrix : nullptr;
    if (N) {
        n[0] = N[0] * nx + N[1] * ny + N[2] * nz;
        n[1] = N[4] * nx + N[5] * ny + N[6] * nz;
        n[2] = N[8] * nx + N[9] * ny + N[10] * nz;
    } else { n[0] = nx; n[1] = ny; n[2] = nz; }
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

// One part: output sink (packet slab, or TA store queues with TA_DIRECT),
// the meshlet cache and the per-meshlet passes.
struct Part {
    const Re4dcModelPart& p;
    Frame& f;
    Projection projection;
    re4dc::render::ClipParameters clip;
    Re4dcModelPacket packet{};
    Cache cache{};
    unsigned used = 0, input = 0, output = 0, primed = 0;
    bool streaming = false, committed = false;
#if RE4DC_ACTOR_DIRECT
    bool direct = false;
    std::uint32_t* sq = nullptr;
    unsigned slots = 0;
#endif
    // Records / lights of the current meshlet.
    const u8* rec = nullptr;
    unsigned rs = 6, color_index = 0;
    const u8* colors = nullptr;
    u32 alpha = 0;

    bool flush() {
        if (!streaming) return false;
        re4dc_model_packet_commit(used); committed = true;
        used = 0; ++stats.flushes;
        return true;
    }
    bool room(unsigned n) {
#if RE4DC_ACTOR_DIRECT
        if (direct) return slots + n <= 32767U;
#endif
        return packet.capacity - used >= n || (flush() && packet.capacity >= n);
    }
    pvr_vertex_t* at() { return static_cast<pvr_vertex_t*>(packet.vertices) + used; }
    void put(const pvr_vertex_t* v, unsigned n) {  // prepared vertices (clipped triangles)
#if RE4DC_ACTOR_DIRECT
        if (direct) { sq = re4dc_ta_put(sq, v, n); slots += n; return; }
#endif
        std::memcpy(at(), v, n * sizeof(pvr_vertex_t)); used += n;
    }
    void strip(const u8* index, unsigned n) {
#if RE4DC_ACTOR_DIRECT
        if (direct) { sq = emit_sq(sq, cache.v, index, n); slots += n; return; }
#endif
        emit(at(), cache.v, index, n); used += n;
    }
    // A meshlet with no corner outside, beyond far or in front of near.
    bool fits(unsigned n) const {
#if RE4DC_ACTOR_DIRECT
        if (direct) return slots + n <= 32767U;
#endif
        return packet.capacity - used >= n || (streaming && packet.capacity >= n);
    }
    bool whole(const u8* index, unsigned count, unsigned triangles) {
        if (!room(count)) return false;
#if RE4DC_ACTOR_DIRECT
        if (direct) {
            sq = static_cast<std::uint32_t*>(emit_meshlet<true>(sq, cache.v, index, count)); slots += count;
        } else
#endif
        { emit_meshlet<false>(at(), cache.v, index, count); used += count; }
        input += triangles; output += triangles;
        return true;
    }
    // Flags/oargb words of the cache entries (the passes never write them).
    void prime(unsigned n) {
        for (; primed < n; ++primed) { cache.v[primed].flags = PVR_CMD_VERTEX; cache.v[primed].oargb = 0; }
    }

    // One meshlet's strips. Each is decided before anything is written (the
    // direct TA path cannot take vertices back): culled when all corners are
    // outside one screen edge or beyond far, copied when no corner is in
    // front of the near plane, else clipped per triangle.
    bool strips(const Records& r, const u8* index, unsigned count) {
        const u8* end = index + count;
        while (index < end) {
            const Strip s = scan(cache.oc, index);
            input += s.n - 2;
            if (s.all & kOcCull) {
                ++stats.strips_culled;
            } else if (!(s.any & kOcNear)) {
                if (!room(s.n)) return false;
                strip(index, s.n);
                output += s.n - 2;
            } else if (!clip_strip(r, index, s.n)) {
                return false;
            }
            index += s.n;
        }
        return true;
    }
    bool clip_strip(const Records& r, const u8* index, unsigned n) {
        ++stats.fallback_runs;
        for (unsigned t = 0; t + 2 < n; ++t) {
            unsigned tri[3] = {t, t + 1, t + 2};
            if (t & 1) std::swap(tri[0], tri[1]);  // strip parity
            re4dc::render::RenderVertex in[3];
            float opacity[3];
            for (unsigned k = 0; k < 3; ++k) {
                const unsigned li = index[tri[k]] & 127U;
                float w[3], nn[3];
                world_of(f, p, r, li, w, nn);
                auto& v = in[k];
                v = {};
                float x = w[0], y = w[1], z = w[2];
                v.position.world_x = x; v.position.world_y = y; v.position.world_z = z;
                v.position.depth = -z;
                if (z != 0.0f) project(x, y, z, &projection);
                v.position.x = x; v.position.y = y; v.position.z = z;
                v.u = cache.v[li].u; v.v = cache.v[li].v;
                const u32 rgb = cache.v[li].argb;
                v.light_red = float((rgb >> 16) & 255) * (1.0f / 255.0f);
                v.light_green = float((rgb >> 8) & 255) * (1.0f / 255.0f);
                v.light_blue = float(rgb & 255) * (1.0f / 255.0f);
                opacity[k] = float(colors ? colors[r.ci(li) * 4 + 3] : (p.alpha_state & 255)) * (1.0f / 255.0f);
            }
            pvr_vertex_t triangles[6];
            const unsigned m = re4dc::render::clip_projected_triangle(in, triangles, u8(p.cull), clip, nullptr, opacity);
            ++stats.fallback_triangles;
            if (m && !room(3 * m)) return false;
            put(triangles, 3 * m);
            output += m;
        }
        return true;
    }
};

// Pass 1 over a meshlet: every record's position/uv/outcode into the cache.
void pass_positions(Part& e, const Records& r, unsigned n, const PosConst& k, bool s16_uv, unsigned& all,
                    unsigned& any) {
    Frame& f = e.f;
    const u8* rec = reinterpret_cast<const u8*>(r.r);
    const unsigned rs = r.stride * 2U;
    all = ~0U; any = 0;
    alignas(8) float temp[16];
    if (f.mode != kSkin) load_xmtrx(f.screen);
    unsigned i = 0;
    while (i < n) {
        int palette = 0;
        if (f.mode == kSkin) {
            palette = reinterpret_cast<const short*>(f.positions + r.vi(i) * 8U)[3];
            load_xmtrx(position_matrix(f, unsigned(palette) < f.palette_entries ? unsigned(palette) : 0U, temp));
        }
        const u8* at = rec + i * rs;
        unsigned done;
#if defined(__sh__) && RE4DC_ACTOR_ASM
        if (s16_uv && f.position_stride == 8)
            done = f.mode == kSkin
                ? positions_asm<kPos8Check>(at, rs, n - i, f.positions, palette, e.p.uv, e.cache.v + i, e.cache.oc + i, k, all, any)
                : positions_asm<kPos8>(at, rs, n - i, f.positions, 0, e.p.uv, e.cache.v + i, e.cache.oc + i, k, all, any);
        else if (s16_uv && f.position_stride == 6)
            done = positions_asm<kPos6>(at, rs, n - i, f.positions, 0, e.p.uv, e.cache.v + i, e.cache.oc + i, k, all, any);
        else
#endif
            done = positions_c(at, rs, n - i, f.positions, f.position_stride, f.mode == kSkin, palette, e.p.uv, s16_uv,
                               e.cache.v + i, e.cache.oc + i, k, all, any);
        i += done;
    }
    stats.position_transforms += n;
}

// Pass 2 (fast directional fold) over a meshlet.
void pass_lights(Part& e, const Lights& L, const Records& r, unsigned n) {
    Frame& f = e.f;
    const u8* rec = reinterpret_cast<const u8*>(r.r);
    const unsigned rs = r.stride * 2U;
    LightConst k{};
    k.cap = 255.0f;
    load_xmtrx(L.color);
    const bool small = f.small_normals;
    const unsigned ns = f.normal_stride;
    if (!small || e.colors) {  // s16 normals / per-vertex alpha: portable loop
        for (unsigned i = 0; i < n; ++i) {
            float nx, ny, nz;
            int pi;
            if (small) {
                const signed char* s = reinterpret_cast<const signed char*>(f.normals + r.ni(i) * ns);
                nx = s[0]; ny = s[1]; nz = s[2]; pi = f.mode == kSkin ? int(u8(s[3])) : 0;
            } else {
                const short* s = reinterpret_cast<const short*>(f.normals + r.ni(i) * ns);
                nx = s[0]; ny = s[1]; nz = s[2]; pi = f.mode == kSkin ? int(u16(s[3])) : 0;
            }
            alignas(8) float temp[12];
            const float* dirs = f.mode == kSkin ? skin_light_dirs(f, L, unsigned(pi), temp) : &L.dir[0][0];
            const float d0 = ACTOR_DOT3(dirs, nx, ny, nz), d1 = ACTOR_DOT3(dirs + 4, nx, ny, nz),
                        d2 = ACTOR_DOT3(dirs + 8, nx, ny, nz);
            float m0 = std::fabs(d0) + d0, m1 = std::fabs(d1) + d1, m2 = std::fabs(d2) + d2, one = 1.0f;
            ACTOR_FTRV(m0, m1, m2, one);
            const u32 a = e.colors ? u32(e.colors[r.ci(i) * 4 + 3]) << 24 : e.alpha;
            e.cache.v[i].argb = a | (channel(m0) << 16) | (channel(m1) << 8) | channel(m2);
        }
        return;
    }
    unsigned i = 0;
    while (i < n) {
        unsigned palette = 0;
        alignas(8) float temp[12];
        const float* dirs = &L.dir[0][0];
        if (f.mode == kSkin) {
            palette = f.normals[r.ni(i) * ns + 3];
            dirs = skin_light_dirs(f, L, palette, temp);
        }
        std::memcpy(k.l0, dirs, 12 * sizeof(float));
        const u8* at = rec + i * rs;
        unsigned done;
#if defined(__sh__) && RE4DC_ACTOR_ASM
        if (ns == 4)
            done = f.mode == kSkin ? lights_asm<kNrm4Check>(at, rs, n - i, f.normals, palette, e.cache.v + i, k, e.alpha)
                                   : lights_asm<kNrm4>(at, rs, n - i, f.normals, 0, e.cache.v + i, k, e.alpha);
        else if (ns == 3 && f.mode != kSkin)
            done = lights_asm<kNrm3>(at, rs, n - i, f.normals, 0, e.cache.v + i, k, e.alpha);
        else
#endif
            done = lights_c(at, rs, n - i, f.normals, ns, f.mode == kSkin, palette, e.cache.v + i, k, e.alpha);
        i += done;
    }
}

// Pass 2 (exact, slow): the generic path's per-vertex evaluator.
void pass_lights_exact(Part& e, const Lights& L, const Records& r, unsigned n) {
    static const u8 white[4] = {255, 255, 255, 255};
    for (unsigned i = 0; i < n; ++i) {
        float w[3], nn[3], rgb[3];
        world_of(e.f, e.p, r, i, w, nn);
        const u8* color = (L.source->ambient_vertex || L.source->material_vertex) && e.p.colors ? e.p.colors + r.ci(i) * 4 : white;
        re4dc::render::evaluate_prepared_source_lighting(w[0], w[1], w[2], nn[0], nn[1], nn[2], *L.source, L.prepared, color, rgb);
        const u32 a = e.colors ? u32(e.colors[r.ci(i) * 4 + 3]) << 24 : e.alpha;
        e.cache.v[i].argb = a | (channel(rgb[0] * 255.0f) << 16) | (channel(rgb[1] * 255.0f) << 8) | channel(rgb[2] * 255.0f);
    }
    stats.slow_light_vertices += n;
}

// A part of a lazily deferred info (no arrays yet) qualifies only if it will
// run in skin mode (prepare_frame's conditions), so no array is ever read.
bool lazy_skin(const Re4dcModelPart& p) {
    if (!RE4DC_NATIVE_ACTOR_SKIN_LAZY || p.positions || p.position_stride != 6) return false;
    const SkinEntry* e = find_skin(p.info, nullptr);
    Re4dcActorSource src{};
    return e && !e->materialized && e->palette && e->entries && re4dc_actor_model_source(p.info, &src) &&
           src.positions && src.normals && src.position_count == p.position_count &&
           src.normal_count == p.normal_count && bool(src.small_normals) == (p.normal_shift == 6);
}

bool qualifies(const Re4dcModelPart& p) {
    return p.lighting && p.alpha_state <= 511 &&
           (!(p.alpha_state & 256) || ((p.flags & 0x80000000U) && p.colors)) &&
           ((!p.lighting->ambient_vertex && !p.lighting->material_vertex) || ((p.flags & 0x80000000U) && p.colors)) &&
           (!p.lighting->enable || p.lighting->attenuation == 1 || p.lighting->attenuation == 2) &&
           p.shift <= 30 && (p.position_stride == 6 || p.position_stride == 8) &&
           (p.normal_shift == 6 || p.normal_shift == 14) && p.normal_stride >= 3 &&
           p.position_count && p.normal_count && p.stream_bytes <= 1024 * 1024 && p.stream_bytes >= 32 &&
           ((ram(p.positions, p.position_count * p.position_stride) &&
             ram(p.normals, p.normal_count * p.normal_stride)) || lazy_skin(p)) &&
           ram(p.stream, p.stream_bytes) && p.uv &&
           p.projection[0] == 0 && p.viewport[2] > 0 && p.viewport[3] > 0;
}

const BlobHeader* convert(const Re4dcModelPart& p) {
    SortSource sort;
    Re4dcActorSource src{};
    if (re4dc_actor_model_source(p.info, &src) && src.positions && src.position_count == p.position_count) {
        sort.positions = src.positions; sort.position_count = src.position_count;
        if (src.normals && src.normal_count == p.normal_count) {
            sort.normals = src.normals; sort.normal_count = src.normal_count; sort.small_normals = src.small_normals != 0;
        }
    }
    const unsigned mark = workspace_top;
    // In place: built in scratch with the GX list's size as the limit.
    {
        u8* out = static_cast<u8*>(scratch(p.stream_bytes));
        const unsigned room = (workspace_end - workspace_top) & ~31U;
        u8* work = out && room ? static_cast<u8*>(scratch(room)) : nullptr;
        if (!work) { ++stats.workspace_misses; workspace_top = mark; return nullptr; }
        Converter c(p, sort, out, p.stream_bytes, Arena{work, room});
        const bool ok = c.run();
        workspace_top = mark;
        if (ok) {
            std::memcpy(const_cast<u8*>(p.stream), out, c.bytes());
            ++stats.conversions;
            return reinterpret_cast<const BlobHeader*>(p.stream);
        }
    }
    // Larger than the GX list: a blob for this submit only (released by it).
    const unsigned room = (workspace_end - workspace_top) & ~31U;
    const unsigned want = std::min((p.stream_bytes * 2U + 1024U + 31U) & ~31U, room / 2U);
    u8* out = static_cast<u8*>(scratch(want));
    const unsigned rest = (workspace_end - workspace_top) & ~31U;
    u8* work = out && rest ? static_cast<u8*>(scratch(rest)) : nullptr;
    if (!work) { ++stats.workspace_misses; workspace_top = mark; return nullptr; }
    Converter c(p, sort, out, want, Arena{work, rest});
    if (!c.run()) { ++stats.conversion_rejects; workspace_top = mark; return nullptr; }
    workspace_top = unsigned(out - workspace) + ((c.bytes() + 31U) & ~31U);
    ++stats.transient_conversions;
    return reinterpret_cast<const BlobHeader*>(out);
}
}  // namespace

extern "C" void re4dc_actor_frame(void* memory, unsigned bytes) {
    workspace = static_cast<unsigned char*>(memory);
    workspace_bytes = memory ? bytes & ~31U : 0;
    workspace_top = 0; workspace_end = workspace_bytes;
    ++frame_serial;
}

extern "C" const Re4dcActorStats* re4dc_actor_stats() { return &stats; }

extern "C" int re4dc_actor_skin_register(unsigned frame, const void* info, const void* position_buffer,
                                         const float* palette, unsigned entries) {
    if (frame != skin_frame) { skin_frame = frame; skin_count = 0; }
#if RE4DC_NATIVE_ACTOR_SKIN_LAZY
    if (!palette || !entries) return 0;
    // Lazy (no arrays): the info's latest Trans() wins, as its pPosBuf would.
    if (!position_buffer)
        if (SkinEntry* e = find_skin(info, nullptr)) { *e = {info, nullptr, palette, entries, 0}; ++stats.skin_registered; return 1; }
    if (skin_count == kSkins) return 0;
#else
    if (skin_count == kSkins || !palette || !entries) return 0;
#endif
    skins[skin_count++] = {info, position_buffer, palette, entries, 0};
    ++stats.skin_registered;
    return 1;
}

extern "C" const float* re4dc_actor_skin_palette(const void* info, const void* position_buffer, unsigned* entries) {
    const SkinEntry* e = find_skin(info, position_buffer);
    if (!e || e->materialized) { *entries = 0; return nullptr; }
    *entries = e->entries;
    return e->palette;
}

extern "C" void re4dc_actor_materialize(const Re4dcModelPart* p) {
    if (!p) return;
    SkinEntry* e = find_skin(p->info, p->positions);
    if (!e || e->materialized) return;
    re4dc_skin_materialize(e->info, e->palette);
    e->materialized = 1;
    ++stats.materialized_infos;
}

#if RE4DC_NATIVE_ACTOR_SKIN_LAZY
extern "C" int re4dc_actor_materialize_lazy(Re4dcModelPart* p) {
    if (!p || p->positions) return 1;
    SkinEntry* e = find_skin(p->info, nullptr);
    if (!e) return 0;
    if (!e->materialized) {
        if (!re4dc_skin_materialize(e->info, e->palette)) return 0;
        e->materialized = 1;
        ++stats.materialized_infos;
    }
    return re4dc_actor_model_buffers(p);
}
#endif

extern "C" int re4dc_actor_submit(const Re4dcModelPart* part) {
    ++stats.parts;
    if (!part || !qualifies(*part)) { ++stats.declined; return 0; }
    const Re4dcModelPart& p = *part;
    const float near_distance = p.projection[6] / (p.projection[5] - 1.0f);
    const float far_distance = p.projection[6] / p.projection[5];
    if (!re4dc::render::is_finite(near_distance) || !re4dc::render::is_finite(far_distance) ||
        near_distance <= 0.0f || far_distance <= near_distance) { ++stats.declined; return 0; }
    const unsigned mark = workspace_top;
    struct Release { unsigned mark; ~Release() { workspace_top = mark; } } release{mark};
    const BlobHeader* blob = blob_of(p);
    if (!blob && !(blob = convert(p))) { ++stats.declined; return 0; }
    const u8* base = reinterpret_cast<const u8*>(blob);
    ++stats.handled;
    if (p.cull == 3) { re4dc_model_result(0, 0, 0); return 1; }
    // Translucent parts keep the existing bounded drain; its replay re-enters
    // re4dc_model_submit and lands here again with draining set.
    if (re4dc_model_defer_part(&p)) { ++stats.deferred; return 1; }

    Frame& f = *prepare_frame(p, near_distance, far_distance);
    if (f.mode == kRigid && blob->radius > 0.0f) {
        // Whole-part depth test of the bind-pose sphere (bind == drawn pose).
        const float* m = p.modelview; const float* c = blob->center;
        const float z = m[8] * c[0] + m[9] * c[1] + m[10] * c[2] + m[11];
        if (-z + blob->radius < near_distance || -z - blob->radius > far_distance) {
            ++stats.culled_parts; re4dc_model_result(0, 0, 0); return 1;
        }
    }
    Part e{p, f, {p.projection, p.viewport}, {near_distance, far_distance, 640.0f, 480.0f, project, nullptr}};
    e.clip.context = &e.projection;
    e.streaming = re4dc_model_packet_streaming() != 0;
    if (!re4dc_model_packet_reserve(&p, &e.packet)) { re4dc_model_result(2, 0, 0); return 1; }
#if RE4DC_ACTOR_DIRECT
    Re4dcModelDirect direct{};
    if (re4dc_model_direct_enabled() && re4dc_model_direct_begin(&p, &direct)) {
        if (direct.scratch_capacity < kCacheSlots) {
            // Nothing sent yet beyond the header: an empty part.
            re4dc_model_direct_end(0); re4dc_model_result(2, 0, 0); return 1;
        }
        e.direct = true; e.sq = direct.sq;
        e.packet.u_scale = direct.u_scale; e.packet.v_scale = direct.v_scale;
        e.cache.v = static_cast<pvr_vertex_t*>(direct.scratch);
    } else
#endif
    {
        if (!re4dc_model_packet_begin(&p, &e.packet) || e.packet.capacity < kCacheSlots + 64U) {
            re4dc_model_result(2, 0, 0);
            return 1;
        }
        e.packet.capacity -= kCacheSlots;
        e.cache.v = static_cast<pvr_vertex_t*>(e.packet.vertices) + e.packet.capacity;
    }
    e.cache.oc = reinterpret_cast<u8*>(e.cache.v + kMaxVertices);

    Lights lights;
    if (!build_lights(p, f, blob->center, lights)) lights.prepared = re4dc::render::prepare_actor_lights(*p.lighting);
    lights.source = p.lighting;
    if (f.skin_dirs) std::memset(f.dirs_ready, 0, f.palette_entries);  // directions follow this part's lights
    const bool s16_uv = (p.flags & 0x80000000U) != 0;
    const float uv_scale = s16_uv ? 1.0f / 256.0f : 1.0f / 32768.0f;
    const PosConst k{0.0f, uv_scale * e.packet.u_scale, p.uv_offset[0] * e.packet.u_scale,
                     uv_scale * e.packet.v_scale, p.uv_offset[1] * e.packet.v_scale, 640.0f, 480.0f,
                     near_distance, far_distance};
    e.colors = (p.alpha_state & 256) ? p.colors : nullptr;
    e.alpha = u32(p.alpha_state & 255) << 24;
    const auto* table = reinterpret_cast<const MeshletInfo*>(base + sizeof(BlobHeader));
    const unsigned rs = (blob->flags & 1U) ? 4U : 3U, color_index = blob->color_index;
    bool ok = true;
    for (unsigned mi = 0; ok && mi < blob->meshlets; ++mi) {
        const MeshletInfo& m = table[mi];
        const Records r{reinterpret_cast<const u16*>(base + m.offset4 * 4U), rs, color_index};
        const u8* index = base + m.offset4 * 4U + m.vertices * rs * 2U;
        ++stats.meshlets; stats.vertices += m.vertices; stats.corners += m.indices;
        unsigned all, any;
        pass_positions(e, r, m.vertices, k, s16_uv, all, any);
        if (all & kOcCull) {
            ++stats.meshlets_culled;
            e.input += m.triangles;
            continue;
        }
        e.prime(m.vertices);
        if (lights.constant) {
            for (unsigned i = 0; i < m.vertices; ++i)
                e.cache.v[i].argb = (e.colors ? u32(e.colors[r.ci(i) * 4 + 3]) << 24 : e.alpha) | lights.constant_rgb;
        } else if (lights.fast) {
            pass_lights(e, lights, r, m.vertices);
        } else {
            pass_lights_exact(e, lights, r, m.vertices);
        }
        stats.normals_lit += m.vertices;
        if (any & kOcNear) ++stats.meshlets_clipped;
        if (!(any & (kOcCull | kOcNear)) && e.fits(m.indices)) { ++stats.meshlets_whole; ok = e.whole(index, m.indices, m.triangles); }
        else ok = e.strips(r, index, m.indices);
    }
#if RE4DC_ACTOR_DIRECT
    if (e.direct) {
        if (!ok) re4dc_model_packet_abort();
        re4dc_model_direct_end(e.slots);
        re4dc_model_result(ok ? 0 : 3, e.input, ok ? e.output : 0);
        return 1;
    }
#endif
    if (!ok) {
        if (e.committed) re4dc_model_packet_abort();
        re4dc_model_result(3, e.input, 0);
        return 1;
    }
    re4dc_model_packet_commit(e.used);
    re4dc_model_result(0, e.input, e.output);
    return 1;
}

#if defined(RE4DC_ACTOR_TEST)
extern "C" unsigned re4dc_actor_test_reject_line() { return reject_line; }
extern "C" void re4dc_actor_test_meshlet_stats(unsigned out[4]) {
    out[0] = test_meshlets; out[1] = test_records; out[2] = test_indices; out[3] = 0;
}
#endif
