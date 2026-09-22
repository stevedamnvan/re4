#pragma once
// Extracted native packet/near-plane mechanism, shared by scene and recovered game.
// Inputs are already prepared by the owning model path; this unit never skins,
// selects animation, reads source archives or owns a PVR frame.
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <dc/pvr.h>
#include "native_draw_plan.hpp"
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

// The accepted room and character renderer's one-pass strip assembly. The
// caller reserves the whole range before entering and publishes only on true;
// a false result leaves private scratch that must be rewound/fallback-clipped.
// Preparation stays with the source owner (cached room slot, character corner,
// or recovered ModelData view). No animation, resource or frame owner lives here.
struct DirectStripVertex {
    float depth, x, y, z, u, v;
    std::uint32_t argb, oargb;
};
template<class Prepare>
bool prepare_direct_strip(pvr_vertex_t* output, std::uint32_t count,
                          float near_distance, float far_distance,
                          Prepare&& prepare) {
    for(std::uint32_t local=0; local<count; ++local) {
        DirectStripVertex vertex;
        if(!prepare(local, vertex) || vertex.depth<near_distance ||
           vertex.depth>far_distance) return false;
        output[local] = {
            .flags=local+1==count ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
            .x=vertex.x, .y=vertex.y, .z=vertex.z, .u=vertex.u, .v=vertex.v,
            .argb=vertex.argb, .oargb=vertex.oargb,
        };
    }
    return true;
}

// Screen-space rejection shared by the clipped fallback and prepared strips.
// Depth clipping remains the caller's job; exact area/sign/edge policy is the
// existing room clipper's, including its cull-none degenerate threshold.
template<class Position>
bool triangle_visible_xy(const Position& a, const Position& b, const Position& c,
                         std::uint8_t cull_mode, float width, float height) {
    const float area=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
    const bool outside=(a.x<0 && b.x<0 && c.x<0) ||
        (a.x>width && b.x>width && c.x>width) ||
        (a.y<0 && b.y<0 && c.y<0) ||
        (a.y>height && b.y>height && c.y>height);
    const bool culled=cull_mode==3 || (cull_mode==2 && area>=0) ||
        (cull_mode==1 && area<=0) || (cull_mode==0 && std::fabs(area)<.0001f);
    return !outside && !culled;
}

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
// Historical group/primitive support-radius rejection with explicit projection
// bias. Recovered GX projection uses zero; the room's KOS matrix uses +1.
bool group_visible(const DrawBounds&,const float modelview[12],const float projection[7],
    const float viewport[6],float near_distance,float far_distance,float depth_bias=0);
bool primitive_visible(const PrimitiveSphere&,const float modelview[12],const float projection[7],
    const float viewport[6],float near_distance,float far_distance,float depth_bias=0);
std::uint32_t shade_color(float red, float green, float blue);
void begin_pvr_packet(pvr_vertex_t*, std::uint32_t&, const pvr_poly_hdr_t&);
void submit_pvr(const void*, std::size_t);
} // namespace re4dc::render
