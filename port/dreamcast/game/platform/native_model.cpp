// Narrow ModelData indexed-stream adapter, not a GX display-list interpreter.
// Only an explicitly enabled base-texture diagnostic currently uses this path.
#include "native_model.h"
#include "re4dc_platform.h"
#include "../../room/pvr_geometry.hpp"
#include <cmath>
#include <cstring>
#include <cstdint>
#ifndef RE4DC_MODEL_POSITION_CACHE
#define RE4DC_MODEL_POSITION_CACHE 1
#endif
namespace {
Re4dcModelWorkStats work_stats{};
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
    unsigned strip_vertices=0,output=0;
    bool streaming=false,bound=false,submitted=false,restart_uv=false,resource_failed=false;
#if RE4DC_MODEL_POSITION_CACHE
    // Part-local, source-indexed reuse. Never weld equal coordinates or retain
    // source pointers across submissions. UVs/normals keep their own identities.
    // Collisions simply recompute. The same bounded table survives packet flushes
    // and UV-scale retries because neither changes the source position transform.
    struct CachedPosition { re4dc::render::ProjectedVertex value; unsigned key; };
    CachedPosition positions[64]{};
    static_assert(sizeof(positions)==2048);
#endif
    bool bind(){
        if(bound)return true;
        const float u=packet.u_scale,v=packet.v_scale;
        if(!re4dc_model_packet_begin(&p,&packet)){resource_failed=true;return false;}
        bound=true;
        // No chunk has been published at this point. Alternate native layouts
        // must use their true UV scale before clipping, just like the reference.
        if(u!=packet.u_scale || v!=packet.v_scale){restart_uv=true;return false;}
        return true;
    }
    bool flush(){
        if(!streaming || !bind())return false;
        re4dc_model_packet_commit(used);submitted=true;
        used=strip_vertices=0; // same owner, header, texture pin and scratch
        return true;
    }
    bool vertex(const unsigned char* corner,re4dc::render::RenderVertex& v){
        const unsigned vi=be16(corner),ni=be16(corner+2),ti=be16(corner+stride-2);
        if(vi>=p.position_count || ni>=p.normal_count || !ram(p.uv+ti*4,4))return false;
        v={};++work_stats.position_references;
#if RE4DC_MODEL_POSITION_CACHE
        auto& cached=positions[vi&63U];
        if(cached.key==vi+1U){
            v.position=cached.value;++work_stats.position_hits;
        }else
#endif
        {
            const unsigned char* pos=p.positions+vi*p.position_stride;
            const float a=s16(pos)*scale,b=s16(pos+2)*scale,c=s16(pos+4)*scale;
            const float* m=p.modelview;
            float x=m[0]*a+m[1]*b+m[2]*c+m[3];
            float y=m[4]*a+m[5]*b+m[6]*c+m[7];
            float z=m[8]*a+m[9]*b+m[10]*c+m[11];
            ++work_stats.position_transforms;
            if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z))return false;
            v.position.world_x=x;v.position.world_y=y;v.position.world_z=z;v.position.depth=-z;
            // Behind/near vertices are clipped before projection is consumed.
            if(z!=0)project(x,y,z,&projection);
            v.position.x=x;v.position.y=y;v.position.z=z;
#if RE4DC_MODEL_POSITION_CACHE
            cached.value=v.position;cached.key=vi+1U;
#endif
        }
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
        unsigned count=re4dc::render::clip_projected_triangle(in,out,p.cull,clip);
        for(unsigned i=0;i<count;++i)if(!append_triangle(out+i*3))return false;
        return true;
    }
    bool append_triangle(const pvr_vertex_t* triangle){
        auto* dst=(pvr_vertex_t*)packet.vertices;
        // PVR alternates strip winding. Match the exact two preceding vertices
        // (including UV/color seams), then retain just the new third vertex.
        // CPU clipping/culling has already selected the surviving triangles.
        const unsigned parity=strip_vertices&1;
        const auto equal=[](const pvr_vertex_t& a,const pvr_vertex_t& b){
            return std::memcmp((const unsigned char*)&a+4,
                               (const unsigned char*)&b+4,sizeof(a)-4)==0;
        };
        if(strip_vertices>=3 && equal(dst[used-2+parity],triangle[0]) &&
                                equal(dst[used-1-parity],triangle[1])){
            if(used==packet.capacity){
                if(!flush())return false;
                return append_triangle(triangle); // begin a correctly wound strip
            }
            dst[used-1].flags=PVR_CMD_VERTEX;
            dst[used++]=triangle[2];++strip_vertices;
        }else{
            if(packet.capacity-used<3){
                if(!flush())return false;
                return append_triangle(triangle);
            }
            std::memcpy(dst+used,triangle,3*sizeof(*dst));used+=3;strip_vertices=3;
        }
        ++output;
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
    ++work_stats.part_preparations;
    Builder b{*p,{},projection,{near,far,640,480,project,nullptr},0,0,
              (p->flags&0x80000000U)?8U:6U,std::ldexp(1.0f,-int(p->shift))};
    b.clip.context=&b.projection;
    if(!b.walk(false)){re4dc_model_result(1,0,0);return;}
    // Source data remains live throughout this synchronous call. In streaming
    // mode each bounded chunk is consumed once by the existing native owner;
    // no whole-scene copy and no repeated deformation/preparation pass.
    b.streaming=re4dc_model_packet_streaming()!=0;
    if(!re4dc_model_packet_reserve(p,&b.packet)){re4dc_model_result(2,0,0);return;}
    bool okay=b.walk(true);
    if(okay && b.used)okay=b.bind();
    if(!okay && b.restart_uv){
        // First binding precedes every publication. Restart only for a verified
        // alternate UV scale, retaining the already selected native texture.
        b.restart_uv=false;b.used=b.input=b.output=b.strip_vertices=0;
        okay=b.walk(true);
        if(okay && b.used)okay=b.bind();
    }
    if(!okay){
        if(b.submitted)re4dc_model_packet_abort();
        re4dc_model_result(b.resource_failed?2:3,b.input,0);return;
    }
    re4dc_model_packet_commit(b.used);re4dc_model_result(0,b.input,b.output);
}

extern "C" const Re4dcModelWorkStats* re4dc_model_work_stats(){return &work_stats;}
