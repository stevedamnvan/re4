#pragma once
#include <cstddef>
#include <cstdint>

namespace re4dc::render {
// Structural index into the owner's immutable GX display-list storage. Attribute
// indices stay in that storage; no second corner/geometry representation exists.
// Mutable material/pass state is supplied by the source on each submission.
enum class DrawTopology : std::uint16_t { quads, triangles, strip, fan };
struct DrawPrimitive {
    std::uint32_t source_offset : 20;
    // Exact source identity -> dense local slot for qualified <=64-wide runs.
    // 4095 marks the explicit general-index fallback. Reuses offset high bits.
    std::uint32_t local_base : 12;
    std::uint16_t corner_count;
    DrawTopology topology : 2;
    std::uint16_t repeat_minus_one : 14;
    unsigned repeats() const { return unsigned(repeat_minus_one)+1; }
    // Adjacent identical GX commands share one structural span. Original
    // attributes and command headers remain in the source owner, not copied.
    unsigned corner_offset(unsigned i,unsigned stride)const {
        return source_offset+i*(3+corner_count*stride);
    }
};
struct NativeDrawPlan {
    std::uint32_t primitive_count, corner_count, max_uv, max_color;
    const DrawPrimitive* primitives() const {
        return reinterpret_cast<const DrawPrimitive*>(this + 1);
    }
};
// R3v-style direct source-index spans. Attribute indices remain in the source
// GX stream. Only immutable range/primitive boundaries survive installation;
// there is no retained per-corner remap or second geometry representation.
constexpr unsigned kLocalSlots=160;
enum class LocalShadeMode : std::uint8_t { none=0, by_position=1, by_normal=2 };
struct LocalBatch {
    std::uint32_t first_corner,corner_count;
    // Zero count is an explicit fallback for that independent channel.
    std::uint16_t position_base,normal_base,position_count,normal_count;
    LocalShadeMode shade_mode;
    std::uint8_t flags;
    // Installation priority only: capped avoided position/normal work plus
    // twice avoided lighting work. Never a runtime identity or validity key.
    std::uint16_t reuse_score;
};
struct DrawLocalPlan {
    std::uint32_t batches,qualified_corners,bytes;
    const LocalBatch* entries()const{return reinterpret_cast<const LocalBatch*>(this+1);}
};
static_assert(sizeof(LocalBatch)==20 && sizeof(DrawLocalPlan)==12);
// Visit all useful descriptors in source-corner order from an inspected plan
// and its immutable stream. The callback receives a temporary descriptor; no
// allocation or admission occurs. Null stream or callback is a no-op.
void visit_draw_locals(const NativeDrawPlan&,const std::uint8_t* stream,bool colored,
    void* context,void (*finish)(void*,const LocalBatch&));
// Null storage returns the complete useful descriptor requirement. Bounded
// storage admits the highest estimated-reuse batches that fit and returns the
// ACTUAL bytes installed; entries remain ordered by source corner ordinal.
// Whole strips/fans are never split. Independent triangles/quads split only at
// their original primitive boundaries. Missing batches/channels use reference
// preparation, while qualified channels use source_index - batch_base slots.
std::size_t prepare_draw_locals(void*,std::size_t,const NativeDrawPlan&,
    const std::uint8_t*,bool colored);
struct DrawBounds { float minimum[3],maximum[3]; };
struct PrimitiveSphere { float center[3],radius; };
struct DrawPlanBounds {
    DrawBounds group; std::uint32_t primitive_count;
    const PrimitiveSphere* primitives()const{return reinterpret_cast<const PrimitiveSphere*>(this+1);}
};
// Optional conservative data for immutable source positions. Animated arrays
// never qualify. Failure leaves the normal visible path, not missing geometry.
DrawPlanBounds* prepare_draw_bounds(void*,std::size_t,const NativeDrawPlan&,
    const std::uint8_t* stream,bool colored,const std::uint8_t* positions,
    unsigned position_stride,float scale,bool primitive_bounds);
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
static_assert(sizeof(DrawPrimitive)==8 && sizeof(NativeDrawPlan)==16);
} // namespace re4dc::render
