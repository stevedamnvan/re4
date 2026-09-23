#include "static_room_prepare.hpp"
#include <dc/matrix.h>
#include <cmath>
#if defined(RE4DC_STATIC_SH4ZAM)
#include <sh4zam/shz_xmtrx.h>
#include <sh4zam/shz_scalar.h>
#endif

namespace re4dc::render {
namespace {
template<bool Split, bool Shz>
void prepare(const room::Package& package, const room::CompactBatch& batch,
             DirectStripVertex* out, float depth_bias) {
    const auto* aos=package.compact_vertices();
    const auto* xyz=package.compact_positions();
    const auto* attr=package.compact_attributes();
    if constexpr(Split) { xyz+=batch.first_vertex;attr+=batch.first_vertex; }
    else aos+=batch.first_vertex;
    for(std::uint32_t i=0;i<batch.vertex_count;++i) {
        float x,y,z;std::uint16_t u,v;std::uint32_t color;
        if constexpr(Split) {
            x=xyz[i].x;y=xyz[i].y;z=xyz[i].z;
            u=attr[i].u;v=attr[i].v;color=attr[i].argb;
        } else {
            x=aos[i].x;y=aos[i].y;z=aos[i].z;
            u=aos[i].u;v=aos[i].v;color=aos[i].argb;
        }
        float w=1.0f;
#if defined(RE4DC_STATIC_SH4ZAM)
        if constexpr(Shz) {
            // Split storage can supply a complete aligned vec4 directly; AoS
            // retains three unchanged XYZ floats and supplies the implicit one.
            const auto q=shz_xmtrx_transform_vec4(Split?
                shz_vec4_deref(&xyz[i]):shz_vec4_init(x,y,z,1.0f));
            x=q.x;y=q.y;z=q.z;w=q.w;
        } else
#endif
        { mat_trans_nodiv(x,y,z,w); }
        float inverse=0.0f;
        if(w>0.0f && std::isfinite(w)) {
#if defined(RE4DC_STATIC_SH4ZAM)
            // FSRRA(x*x) loses the sign and can overflow/underflow. Keep the
            // ordinary division outside this qualified finite positive range.
            if constexpr(Shz) {
                inverse=(w>=1.0e-18f && w<=1.0e18f)?shz_invf_fsrra(w):1.0f/w;
            } else
#endif
            inverse=1.0f/w;
        }
        out[i]={w-depth_bias,x*inverse,y*inverse,inverse,
            batch.uv_bias[0]+static_cast<float>(u)*batch.uv_scale[0],
            batch.uv_bias[1]+static_cast<float>(v)*batch.uv_scale[1],color,0U};
    }
}
}

bool static_backend_available(StaticMathBackend backend) {
    if(backend==StaticMathBackend::D349) return true;
#if defined(RE4DC_STATIC_SH4ZAM)
    return backend==StaticMathBackend::Sh4zam;
#else
    return false;
#endif
}
bool prepare_static_batch(const room::Package& package,const room::CompactBatch& batch,
    DirectStripVertex* slots,std::uint32_t capacity,float depth_bias,StaticMathBackend backend) {
    if(!package.compact() || !slots || capacity<batch.vertex_count ||
       !static_backend_available(backend)) return false;
    const bool split=package.compact_header()->layout==room::StaticLayout::Split24;
#if defined(RE4DC_STATIC_SH4ZAM)
    if(backend==StaticMathBackend::Sh4zam) {
        if(split) prepare<true,true>(package,batch,slots,depth_bias);
        else prepare<false,true>(package,batch,slots,depth_bias);
        return true;
    }
#endif
    if(split) prepare<true,false>(package,batch,slots,depth_bias);
    else prepare<false,false>(package,batch,slots,depth_bias);
    return true;
}
} // namespace re4dc::render
