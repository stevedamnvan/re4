#pragma once
// Storage adapter for D349 prepare-once slots. The source/frame owner loads
// XMTRX and selects eligible batches. This unit owns no scene, light, cache,
// animation, resource lifetime or PVR submission. v4 already stores local IDs.
#include "room_package.hpp"
#include "pvr_geometry.hpp"

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
} // namespace re4dc::render
