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
    float uv_offset[2]; unsigned wrap_s,wrap_t;
};
extern "C" {
int re4dc_model_diagnostic_enabled();
void re4dc_model_submit(const Re4dcModelPart*);
// Source-only bridge entry points; opaque types keep SDK/KOS headers separate.
void re4dc_model_material(const void* texture_object,float u,float v,unsigned flags);
void re4dc_draw_model_part(const void* model,const void* info,const void* part,
                          const float modelview[3][4],unsigned pass);
}

// Adapter/owner interface. Returned storage belongs to the one native frame,
// already holds a header, and is committed only after a complete part succeeds.
// A failed part leaves used bytes unchanged. Source pointers never enter it.
struct Re4dcModelPacket { void* vertices; unsigned capacity; float u_scale,v_scale; };
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart*,Re4dcModelPacket*);
extern "C" void re4dc_model_packet_commit(unsigned vertices);
extern "C" void re4dc_model_result(unsigned reason,unsigned input_triangles,unsigned output_triangles);
