#pragma once
// D367 actor prototype (UNAPPLIED). Dense "prepare once per model info, index
// many" path for the recovered game's non-scenery ModelData parts (Leon,
// enemies, weapons, room SMD objects). The source game stays authoritative:
// it still selects, animates, skins (pPosBuf/pNrmBuf), lights (LightSetModel ->
// GX light state) and orders every draw. Only the render representation
// changes: one ftrv per source position, one per-object light set per info,
// one packed colour per source normal, and GX strips published unchanged.
#include "native_model.h"

struct Re4dcActorStats {
    unsigned parts, handled, declined, deferred, culled_infos, culled_parts;
    unsigned info_preparations, position_transforms, light_sets, normals_lit;
    unsigned corners, runs, fallback_runs, fallback_triangles, flushes;
    unsigned workspace_misses, attenuated_lights, near_vertices;
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
}

#if defined(RE4DC_ACTOR_TEST)
// Host test access to the prepared tables of the last prepared info.
struct Re4dcActorScreen { float x, y, w_inverse; };
extern "C" const Re4dcActorScreen* re4dc_actor_test_screen();
extern "C" const unsigned* re4dc_actor_test_shade();
#endif
