#pragma once
// Extracted native packet/near-plane mechanism, shared by scene and recovered game.
// Inputs are already prepared by the owning model path; this unit never skins,
// selects animation, reads source archives or owns a PVR frame.
#include <cstddef>
#include <cstdint>
#include <dc/pvr.h>
namespace re4dc::render {
struct ProjectedVertex {
    float x;
    float y;
    float z;
    float world_x;
    float world_y;
    float world_z;
    float depth;
};

struct RenderVertex {
    ProjectedVertex position;
    float u;
    float v;
    float light_red;
    float light_green;
    float light_blue;
    std::uint32_t offset_color;
};

using ProjectPoint = void (*)(float&, float&, float&, void*);
struct ClipParameters {
    float near_distance, far_distance, width, height;
    ProjectPoint project;
    void* context;
};
struct ClipStats {
    std::uint32_t accepts=0, rejects=0, crossings=0;
};
// Cull values preserve the existing scene representation: none/front/back/all.
std::uint32_t clip_projected_triangle(const RenderVertex*, pvr_vertex_t*,
    std::uint8_t cull_mode, const ClipParameters&, ClipStats* = nullptr, const float* alpha = nullptr);
std::uint32_t shade_color(float red, float green, float blue);
void begin_pvr_packet(pvr_vertex_t*, std::uint32_t&, const pvr_poly_hdr_t&);
void submit_pvr(const void*, std::size_t);
} // namespace re4dc::render
