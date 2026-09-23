#pragma once
// Storage adapter for D349 prepare-once slots. The source/frame owner loads
// XMTRX and selects eligible batches. This unit owns no scene, light, cache,
// animation, resource lifetime or PVR submission. v4 already stores local IDs.
#include "room_package.hpp"
#include "pvr_geometry.hpp"
#include <dc/matrix.h>
#include <cmath>

namespace re4dc::render {
enum class StaticMathBackend { D349, Sh4zam };
bool static_backend_available(StaticMathBackend);
// All positions retain float XYZ. The two layout kernels produce the same slot
// type consumed by prepare_direct_strip(). Caller-provided bounded scratch is
// reused between batches. A crossing strip still uses the existing clipper;
// it must not interpret a nonpositive-depth slot as projected screen position.
bool prepare_static_batch(const room::Package&, const room::CompactBatch&,
    DirectStripVertex* slots, std::uint32_t capacity, float depth_bias,
    StaticMathBackend backend = StaticMathBackend::D349);
// One AoS20 vertex through the loaded XMTRX with prepare_static_batch()'s
// D349 math, for callers whose strips barely share vertices and so prepare
// per strip corner into packet storage instead of a batch slot array. The
// caller applies live UV offset/native scale and alpha. A StaticCorner is a
// decoded AoS20 or AoS12 corner; AoS12 positions stay in grid units and the
// caller's XMTRX carries the package grid.
struct StaticCorner { float x,y,z; std::uint16_t u,v; std::uint32_t argb; };
inline DirectStripVertex prepare_static_vertex(const StaticCorner& in,
    const room::CompactBatch& batch, float depth_bias) {
    float x=in.x,y=in.y,z=in.z,w=1.0f;
    mat_trans_nodiv(x,y,z,w);
    const float inverse=(w>0.0f && is_finite(w))?1.0f/w:0.0f;
    return {w-depth_bias,x*inverse,y*inverse,inverse,
        batch.uv_bias[0]+static_cast<float>(in.u)*batch.uv_scale[0],
        batch.uv_bias[1]+static_cast<float>(in.v)*batch.uv_scale[1],in.argb,0U};
}
inline DirectStripVertex prepare_static_vertex(const room::CompactVertex& in,
    const room::CompactBatch& batch, float depth_bias) {
    return prepare_static_vertex(StaticCorner{in.x,in.y,in.z,in.u,in.v,in.argb},batch,depth_bias);
}
} // namespace re4dc::render
