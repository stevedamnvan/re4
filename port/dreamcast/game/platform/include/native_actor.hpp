#pragma once
// D367 native actor path for the recovered game's non-scenery ModelData parts
// (Leon, enemies, weapons, room SMD objects). The source game stays
// authoritative: it selects, animates, orders and lights every draw. Only the
// render representation changes.
//
// NATIVE_ACTOR=1 (native_actor.cpp): dense per-info tables, GX list walked per
// corner. NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 (native_actor_fast.cpp): each
// part's GX display list is converted once, in place, into <=128-vertex
// meshlets (unique corner tuples + u8 strip indices); per frame every meshlet
// vertex is transformed/lit once into a small cache and strips are copied.
// NATIVE_ACTOR_SKIN=1 additionally lets the source skip its render-only
// CalcSk1_x pass: the palette is kept and skinning happens at draw time.
#include "native_model.h"

struct Re4dcActorStats {
    unsigned parts, handled, declined, deferred, culled_infos, culled_parts;
    unsigned info_preparations, position_transforms, light_sets, normals_lit;
    unsigned corners, runs, fallback_runs, fallback_triangles, flushes;
    unsigned workspace_misses, attenuated_lights, near_vertices;
    // NATIVE_ACTOR_FAST
    unsigned conversions, conversion_rejects, meshlets, meshlets_culled, meshlets_clipped;
    unsigned vertices, slow_light_vertices, skinned_parts, materialized_infos, skin_registered;
    unsigned transient_conversions, strips_culled, meshlets_whole;
};

// Where the source keeps an info's unskinned arrays (model_bridge.cpp fills
// it from ModelData; platform code stays free of source struct layouts).
struct Re4dcActorSource {
    const unsigned char* positions;  // vtxOrig: s16 x,y,z + s16 palette index
    const unsigned char* normals;    // nrmOrig: s8 x,y,z,u8 index / s16 x,y,z,s16 index
    unsigned position_count, normal_count, palette_entries, small_normals;
};

extern "C" {
// Bind this source frame's scratch. The recommended owner is the tail of the
// source primitive buffer (GetPrimBuff during Render(), released by the next
// SetPrimBuffPtr), so no memory stays resident. nullptr/0 disables the path.
void re4dc_actor_frame(void* workspace, unsigned bytes);
// 1: consumed (drawn, culled, or queued for the existing translucent drain).
// 0: declined before any side effect; the caller runs the generic path.
int re4dc_actor_submit(const Re4dcModelPart* p);
const Re4dcActorStats* re4dc_actor_stats();
// Bytes needed for one info: 12 per source position + 4 per source normal.
inline unsigned re4dc_actor_workspace_bytes(unsigned positions, unsigned normals) {
    return positions * 12U + normals * 4U;
}

// ---- NATIVE_ACTOR_FAST ------------------------------------------------------
// model_bridge.cpp: the unskinned arrays of a cModelInfo. 0 when unknown.
int re4dc_actor_model_source(const void* info, Re4dcActorSource* out);

// ---- NATIVE_ACTOR_SKIN ------------------------------------------------------
// Trans() side (trans.cpp commonScreenMatSub): after the source built this
// info's weight palette (MakeWeightPalette, unchanged), a copy of it lives in
// the frame's primitive buffer. Registering it lets the source skip the
// render-only CalcSk1_x writes into pPosBuf/pNrmBuf for this frame. 1 = the
// caller may skip. `frame` is pG->Frame_cnt (constant from Trans to Render).
int re4dc_actor_skin_register(unsigned frame, const void* info, const void* position_buffer,
                              const float* palette, unsigned entries);
// Registered palette for (info, pPosBuf) or nullptr.
const float* re4dc_actor_skin_palette(const void* info, const void* position_buffer, unsigned* entries);
// trans.cpp: run the source's own CalcSk1_x/_x2 for a registered info into
// its pPosBuf/pNrmBuf from the saved palette (generic-path fallback).
#if RE4DC_NATIVE_ACTOR_SKIN_LAZY
int re4dc_skin_materialize(const void* info, const float* palette);  // 0: no arrays could be allocated
#else
void re4dc_skin_materialize(const void* info, const float* palette);
#endif
// native_model.cpp: before the generic path reads pPosBuf, make it valid.
void re4dc_actor_materialize(const Re4dcModelPart* p);
// NATIVE_ACTOR_SKIN_LAZY: a part of an info registered without arrays
// (positions NULL): allocate and skin them, set p->positions/normals; 0 if
// that is impossible (the generic path then rejects the part).
int re4dc_actor_materialize_lazy(Re4dcModelPart* p);
// model_bridge.cpp: p->positions/normals from the info current pPosBuf/pNrmBuf.
int re4dc_actor_model_buffers(Re4dcModelPart* p);
}

#if defined(RE4DC_ACTOR_TEST)
// Host test access to the prepared tables of the last prepared info.
struct Re4dcActorScreen { float x, y, w_inverse; };
extern "C" const Re4dcActorScreen* re4dc_actor_test_screen();
extern "C" const unsigned* re4dc_actor_test_shade();
#endif
