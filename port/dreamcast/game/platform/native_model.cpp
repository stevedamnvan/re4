// Narrow ModelData indexed-stream adapter, not a GX display-list interpreter.
// Only an explicitly enabled base-texture diagnostic currently uses this path.
#include "native_model.h"
#include "re4dc_platform.h"
#include "../../room/pvr_geometry.hpp"
#include <cmath>
#include <cstring>
#include <cstdint>
namespace {
unsigned be16(const unsigned char* p){return (unsigned(p[0])<<8)|p[1];}
short s16(const unsigned char* p){short v;std::memcpy(&v,p,2);return v;}
unsigned u16(const unsigned char* p){unsigned short v;std::memcpy(&v,p,2);return v;}
bool ram(const void* p,unsigned bytes){
#if defined(__sh__)
    auto a=(std::uintptr_t)p;
    return a>=0x8c000000U && a<0x8d000000U && bytes<=0x8d000000U-a;
#else
    return p!=nullptr;
#endif
}
struct Projection { const float* p; const float* v; };
void project(float& x,float& y,float& z,void* context){
    const auto& c=*(const Projection*)context;
    const float inv=1.0f/(-z);
    x=(c.v[2]*.5f*(c.p[1]*x+c.p[2]*z)*inv+c.v[0]+c.v[2]*.5f)*640.f/c.v[2];
    y=(-c.v[3]*.5f*(c.p[3]*y+c.p[4]*z)*inv+c.v[1]+c.v[3]*.5f)*480.f/c.v[3];
    z=inv;
}
struct Builder {
    const Re4dcModelPart& p; Re4dcModelPacket packet{};
    Projection projection; re4dc::render::ClipParameters clip;
    unsigned used=0,input=0,stride; float scale;
    bool vertex(const unsigned char* corner,re4dc::render::RenderVertex& v){
        const unsigned vi=be16(corner),ni=be16(corner+2),ti=be16(corner+stride-2);
        if(vi>=p.position_count || ni>=p.normal_count || !ram(p.uv+ti*4,4))return false;
        const unsigned char* pos=p.positions+vi*p.position_stride;
        const float a=s16(pos)*scale,b=s16(pos+2)*scale,c=s16(pos+4)*scale;
        const float* m=p.modelview;
        float x=m[0]*a+m[1]*b+m[2]*c+m[3];
        float y=m[4]*a+m[5]*b+m[6]*c+m[7];
        float z=m[8]*a+m[9]*b+m[10]*c+m[11];
        if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z))return false;
        v={};v.position.world_x=x;v.position.world_y=y;v.position.world_z=z;v.position.depth=-z;
        // Behind/near vertices are clipped before their projected coordinates are used.
        if(z!=0)project(x,y,z,&projection);
        v.position.x=x;v.position.y=y;v.position.z=z;
        const auto* uv=p.uv+ti*4;
        float u=(p.flags&0x80000000U)?s16(uv)/256.f:u16(uv)/32768.f;
        float w=(p.flags&0x80000000U)?s16(uv+2)/256.f:u16(uv+2)/32768.f;
        v.u=(u+p.uv_offset[0])*packet.u_scale;v.v=(w+p.uv_offset[1])*packet.v_scale;
        // Deliberately unlit diagnostic. Source light/material parity is not accepted.
        v.light_red=v.light_green=v.light_blue=1;
        return true;
    }
    bool triangle(const unsigned char* a,const unsigned char* b,const unsigned char* c){
        re4dc::render::RenderVertex in[3];
        if(!vertex(a,in[0])||!vertex(b,in[1])||!vertex(c,in[2]))return false;
        pvr_vertex_t out[6];++input;
        unsigned count=3*re4dc::render::clip_projected_triangle(in,out,p.cull,clip);
        if(count>packet.capacity-used)return false;
        std::memcpy((pvr_vertex_t*)packet.vertices+used,out,count*sizeof(out[0]));used+=count;
        return true;
    }
    bool walk(bool emit){
        unsigned offset=0;
        while(offset<p.stream_bytes){
            unsigned op=p.stream[offset++];if(!op)continue;
            if(p.stream_bytes-offset<2)return false;
            unsigned n=be16(p.stream+offset);offset+=2;
            if(n>(p.stream_bytes-offset)/stride)return false;
            const auto* v=p.stream+offset;offset+=n*stride;
            if((op==0x80 && n%4) || (op==0x90 && n%3) ||
               (op!=0x80 && op!=0x90 && op!=0x98 && op!=0xa0))return false;
            for(unsigned i=0;i<n;++i){
                if(be16(v+i*stride)>=p.position_count || be16(v+i*stride+2)>=p.normal_count ||
                   !ram(p.uv+be16(v+i*stride+stride-2)*4,4))return false;
            }
            if(!emit)continue;
            if(op==0x80){for(unsigned i=0;i<n;i+=4)
                if(!triangle(v+i*stride,v+(i+1)*stride,v+(i+2)*stride) ||
                   !triangle(v+i*stride,v+(i+2)*stride,v+(i+3)*stride))return false;
            }else if(op==0x90){for(unsigned i=0;i<n;i+=3)
                if(!triangle(v+i*stride,v+(i+1)*stride,v+(i+2)*stride))return false;
            }else{for(unsigned i=2;i<n;++i){
                unsigned a=op==0xa0?0:i-2,b=i-1;
                if(op==0x98 && (i&1)){unsigned t=a;a=b;b=t;}
                if(!triangle(v+a*stride,v+b*stride,v+i*stride))return false;
            }}
        }
        return true;
    }
};
}
extern "C" void re4dc_model_submit(const Re4dcModelPart* p){
    if(!re4dc_model_diagnostic_enabled())return;
    if(!p || p->shift>30 || (p->position_stride!=6 && p->position_stride!=8) ||
       !p->position_count || !p->normal_count || p->stream_bytes>1024*1024 ||
       !ram(p->positions,p->position_count*p->position_stride) || !ram(p->stream,p->stream_bytes) ||
       p->projection[0]!=0 || p->viewport[2]<=0 || p->viewport[3]<=0){re4dc_model_result(1,0,0);return;}
    Projection projection{p->projection,p->viewport};
    const float near=p->projection[6]/(p->projection[5]-1),far=p->projection[6]/p->projection[5];
    if(!std::isfinite(near)||!std::isfinite(far)||near<=0||far<=near){re4dc_model_result(1,0,0);return;}
    Builder b{*p,{},projection,{near,far,640,480,project,nullptr},0,0,
              (p->flags&0x80000000U)?8U:6U,std::ldexp(1.0f,-int(p->shift))};
    b.clip.context=&b.projection;
    if(!b.walk(false)){re4dc_model_result(1,0,0);return;}
    if(!re4dc_model_packet_begin(p,&b.packet)){re4dc_model_result(2,0,0);return;}
    if(!b.walk(true)){re4dc_model_result(3,b.input,0);return;}
    re4dc_model_packet_commit(b.used);re4dc_model_result(0,b.input,b.used/3);
}
