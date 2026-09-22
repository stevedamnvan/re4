#include "native_draw_plan.hpp"
#include <limits>
#include <new>

namespace re4dc::render {
namespace {
unsigned be16(const std::uint8_t* p) { return (unsigned(p[0])<<8)|p[1]; }
bool topology(unsigned op, unsigned n, DrawTopology& out) {
    switch(op) {
    case 0x80: out=DrawTopology::quads; return n%4==0;
    case 0x90: out=DrawTopology::triangles; return n%3==0;
    case 0x98: out=DrawTopology::strip; return true;
    case 0xa0: out=DrawTopology::fan; return true;
    default: return false;
    }
}
}
bool inspect_draw_plan(const std::uint8_t* stream, std::uint32_t bytes,
                       bool colored, std::uint32_t positions,
                       std::uint32_t normals, DrawPlanRequirements& out) {
    out={};
    if(!stream || bytes>1024*1024 || !positions || !normals) return false;
    DrawPlanRequirements r;
    const unsigned stride=colored?8:6;
    unsigned offset=0;
    while(offset<bytes) {
        const unsigned op=stream[offset++]; if(!op) continue;
        if(bytes-offset<2) return false;
        const unsigned n=be16(stream+offset); offset+=2;
        DrawTopology kind;
        if(!topology(op,n,kind) || n>(bytes-offset)/stride) return false;
        ++r.primitives; r.corners+=n;
        for(unsigned i=0;i<n;++i) {
            const auto* c=stream+offset+i*stride;
            if(be16(c)>=positions || be16(c+2)>=normals) return false;
            const unsigned uv=be16(c+stride-2),color=colored?be16(c+4):0;
            if(uv>r.max_uv) r.max_uv=uv;
            if(color>r.max_color) r.max_color=color;
        }
        offset+=n*stride;
    }
    r.bytes=sizeof(NativeDrawPlan)+std::size_t(r.primitives)*sizeof(DrawPrimitive)+
            std::size_t(r.corners)*sizeof(DrawCorner);
    out=r; return true;
}
NativeDrawPlan* prepare_draw_plan(void* storage, std::size_t capacity,
                                 const std::uint8_t* stream, std::uint32_t bytes,
                                 bool colored, const DrawPlanRequirements& r) {
    if(!storage || reinterpret_cast<std::uintptr_t>(storage)%alignof(NativeDrawPlan) ||
       !stream || r.bytes>capacity || r.bytes!=sizeof(NativeDrawPlan)+
         std::size_t(r.primitives)*sizeof(DrawPrimitive)+std::size_t(r.corners)*sizeof(DrawCorner)) return nullptr;
    auto* plan=new(storage) NativeDrawPlan{r.primitives,r.corners,r.max_uv,r.max_color};
    auto* primitives=const_cast<DrawPrimitive*>(plan->primitives());
    auto* corners=const_cast<DrawCorner*>(plan->corners());
    unsigned offset=0,pi=0,ci=0;
    const unsigned stride=colored?8:6;
    while(offset<bytes) {
        const unsigned op=stream[offset++]; if(!op) continue;
        if(bytes-offset<2) return nullptr;
        const unsigned n=be16(stream+offset); offset+=2;
        DrawTopology kind;
        if(!topology(op,n,kind) || n>(bytes-offset)/stride ||
           pi>=r.primitives || n>r.corners-ci) return nullptr;
        primitives[pi++]={ci,static_cast<std::uint16_t>(n),kind};
        for(unsigned i=0;i<n;++i) {
            const auto* c=stream+offset+i*stride;
            corners[ci++]={static_cast<std::uint16_t>(be16(c)),
                           static_cast<std::uint16_t>(be16(c+2)),
                           static_cast<std::uint16_t>(be16(c+stride-2)),
                           static_cast<std::uint16_t>(colored?be16(c+4):0)};
        }
        offset+=n*stride;
    }
    return pi==r.primitives && ci==r.corners?plan:nullptr;
}
} // namespace re4dc::render
