#pragma once
#include <cstddef>
#include <cstdint>

namespace re4dc::render {
// The source archive stays authoritative; this immutable transport contains no
// pose, camera, material state or source pointers. The caller owns its lifetime.
enum class DrawTopology : std::uint16_t { quads, triangles, strip, fan };
struct DrawCorner { std::uint16_t position, normal, uv, color; };
struct DrawPrimitive {
    std::uint32_t first_corner;
    std::uint16_t corner_count;
    DrawTopology topology;
};
struct NativeDrawPlan {
    std::uint32_t primitive_count, corner_count, max_uv, max_color;
    const DrawPrimitive* primitives() const {
        return reinterpret_cast<const DrawPrimitive*>(this + 1);
    }
    const DrawCorner* corners() const {
        return reinterpret_cast<const DrawCorner*>(primitives() + primitive_count);
    }
};
struct DrawPlanRequirements {
    std::size_t bytes=0;
    std::uint32_t primitives=0, corners=0, max_uv=0, max_color=0;
};
// Qualification checks every command/index once at installation. No source
// geometry or attribute array is copied. Bounds for animated geometry cannot be
// frozen from its current pose; conservative bounds are a separate later layer.
bool inspect_draw_plan(const std::uint8_t* stream, std::uint32_t bytes,
                       bool colored, std::uint32_t positions,
                       std::uint32_t normals, DrawPlanRequirements& out);
// The inspected stream must remain immutable between inspection and packing.
NativeDrawPlan* prepare_draw_plan(void* storage, std::size_t capacity,
                                 const std::uint8_t* stream, std::uint32_t bytes,
                                 bool colored, const DrawPlanRequirements&);
static_assert(sizeof(DrawCorner)==8 && sizeof(DrawPrimitive)==8);
} // namespace re4dc::render
