#pragma once
#include "native_ui.h"
// Synchronous view of a qualified source ModelData part. No source pointers are
// retained after submit. The source has already selected/skinned the model.
struct Re4dcModelPart {
    const void* model; const void* info; const void* part;
    const unsigned char* positions; const unsigned char* normals;
    const unsigned char* uv; const unsigned char* stream;
    unsigned position_count, normal_count, position_stride, stream_bytes;
    unsigned shift, flags, cull, blend, depth_mode, material_flags;
    float modelview[12], projection[7], viewport[6];
    Re4dcUiImage image;
    // Channel zero alpha: low byte material, bit 8 vertex source; other bits reject.
    // RGB remains the explicitly unlit diagnostic until native lighting connects.
    const unsigned char* colors=nullptr; unsigned alpha_state=255;
    float uv_offset[2]; unsigned wrap_s,wrap_t;
};
extern "C" {
int re4dc_model_diagnostic_enabled();
unsigned re4dc_gx_model_alpha();
void re4dc_model_submit(const Re4dcModelPart*);
// Source-only bridge entry points; opaque types keep SDK/KOS headers separate.
void re4dc_model_material(const void* texture_object,float u,float v,unsigned flags);
void re4dc_draw_model_part(const void* model,const void* info,const void* part,
                          const float modelview[3][4],unsigned pass);
}

// Adapter/owner interface. Returned storage belongs to the one native frame,
// reserves header space, and is committed only after a complete part succeeds.
// reserve() performs no texture I/O. begin() binds the validated native texture
// after geometry fits; differing native UV scales require preparation again.
// Default mode rolls back a failed complete part. Streaming mode can reuse this
// scratch after committing chunks; a later failure must abort the whole frame.
// Source pointers never enter the native owner.
struct Re4dcModelPacket { void* vertices; unsigned capacity; float u_scale,v_scale; };
extern "C" int re4dc_model_packet_reserve(const Re4dcModelPart*,Re4dcModelPacket*);
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart*,Re4dcModelPacket*);
extern "C" void re4dc_model_packet_commit(unsigned vertices);
extern "C" void re4dc_model_result(unsigned reason,unsigned input_triangles,unsigned output_triangles);

extern "C" int re4dc_model_packet_streaming();
extern "C" void re4dc_model_packet_abort();

// Source cModel 0/1 selects GX_CULL_FRONT/BACK, not the viewer helper's
// screen-area values. GXSetCullMode swaps the two hardware bits; with GX's
// negative viewport Y scale, FRONT rejects positive screen area, BACK negative.
// Preserve the shared helper/accepted viewer convention at this adapter boundary.
inline unsigned re4dc_model_cull(unsigned source_mode,bool force_front){
    return force_front?2U:(source_mode==0?2U:source_mode==1?1U:0U);
}

// Cumulative preparation work; distinct from PVR/internal TA capacity counters.
// Native cache costs 2 KiB of the existing calling stack, no resident allocation.
struct Re4dcModelWorkStats {
    unsigned part_preparations, position_references, position_transforms, position_hits;
    unsigned room_prepared_strips, room_prepared_corners, room_strip_fallbacks;
    unsigned gx_walk_bytes, prepared_parts, unprepared_parts;
};
extern "C" const Re4dcModelWorkStats* re4dc_model_work_stats();

namespace re4dc::render { struct NativeDrawPlan; }
// Qualified archive ranges come from the existing UI/resource owner. A plan
// contains copied indices only; the current frame still supplies live arrays.
extern "C" void re4dc_model_bind_draw_owner(const void* owner,void* archive,unsigned bytes,unsigned transient);
extern "C" void re4dc_model_unbind_draw_owner(const void* owner);
extern "C" void re4dc_model_reset_draw_plans();
extern "C" const re4dc::render::NativeDrawPlan* re4dc_model_acquire_draw_plan(const Re4dcModelPart*,int* invalid);
extern "C" void re4dc_model_release_draw_plan();
extern "C" void re4dc_model_draw_plan_frame(unsigned frame);
struct Re4dcDrawPlanStats {
    unsigned hits,installs,source_bytes,uncovered,capacity_rejects,invalid,
             used,capacity,peak,resets,owner_misses;
};
extern "C" const Re4dcDrawPlanStats* re4dc_model_draw_plan_stats();

extern "C" void re4dc_model_retire_draw_plans();
