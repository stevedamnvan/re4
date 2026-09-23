// Target CPU fixture, NOT a scene/gameplay executable or a PVR throughput test.
// Uses the four existing owner packages, actual reader, existing D349 direct
// strip assembly and v4 storage adapters. No source state/assets are embedded
// in this source. Each build contains exactly one layout, never both scenes.
#include <kos.h>
#include <dc/matrix.h>
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <vector>
#include "room_package.hpp"
#include "static_room_prepare.hpp"
#include "native_render_profile.hpp"
#include <sh4zam/shz_scalar.h>
#include <sh4zam/shz_mem.h>

KOS_INIT_FLAGS(INIT_DEFAULT);
extern "C" {
volatile char re4dc_logbuf[65536];
volatile unsigned re4dc_loghead=0;
volatile unsigned re4dc_probe_stage=0;
}
static void logf(const char* format,...) {
    char text[2048];va_list args;va_start(args,format);
    const int n=vsnprintf(text,sizeof(text),format,args);va_end(args);
    const unsigned count=std::min(unsigned(n<0?0:n),unsigned(sizeof(text)-1));
    unsigned head=re4dc_loghead;
    for(unsigned i=0;i<count;++i) re4dc_logbuf[head++%65536]=text[i];
    asm volatile("" ::: "memory");re4dc_loghead=head;
}
namespace {
using namespace re4dc;
constexpr unsigned Capacity=4096;
alignas(32) render::DirectStripVertex slots[Capacity];
alignas(32) pvr_vertex_t packets[Capacity];
alignas(32) unsigned copies[8192],copy_dest[8192];
volatile unsigned sink=0;
struct LegacyBatch { std::vector<unsigned> vertices;std::vector<uint16_t> indices, triangles; };
struct Owner { room::Package package;std::vector<LegacyBatch> legacy; };
Owner owners[4];
unsigned ticks(){return profile::clock();}
float us(unsigned t){return t*.08f;}
// Bounded camera-like projection of actual XYZ. It deliberately puts every
// batch in front for a preparation/packet comparison, not a visibility/FPS claim.
alignas(32) matrix_t matrix={
    {320,0,0,0},{0,-320,0,0},{320,240,1,1},{320000,240000,0,1000}
};
void legacy_prepare(const room::Package& p,const LegacyBatch& batch) {
    const auto* v=p.vertices();
    for(unsigned i=0;i<batch.vertices.size();++i) {
        const auto& in=v[batch.vertices[i]];
        float x=in.x,y=in.y,z=in.z;mat_trans_single(x,y,z);
        const unsigned color=0xff000000U|(unsigned(in.nx*255.0f)<<16)|
            (unsigned(in.ny*255.0f)<<8)|unsigned(in.nz*255.0f);
        slots[i]={1.0f/z-1.0f,x,y,z,in.u,in.v,color,0};
    }
}
bool build_legacy(Owner& o) {
    const auto& h=o.package.header();o.legacy.resize(h.batch_count);
    std::vector<int> map(h.vertex_count,-1);
    for(unsigned b=0;b<h.batch_count;++b) {
        auto& local=o.legacy[b];const auto& batch=o.package.batches()[b];
        for(unsigned pi=0;pi<batch.primitive_count;++pi) {
            const auto& prim=o.package.primitives()[batch.first_primitive+pi];
            for(unsigned k=0;k<prim.vertex_count;++k) {
                const auto id=o.package.primitive_indices()[prim.first_vertex+k];
                if(map[id]<0){map[id]=int(local.vertices.size());local.vertices.push_back(id);}
                local.indices.push_back(uint16_t(map[id]));
            }
        }
        for(unsigned k=0;k<batch.index_count;++k) {
            const auto id=o.package.indices()[batch.first_index+k];
            if(map[id]<0){map[id]=int(local.vertices.size());local.vertices.push_back(id);}
            local.triangles.push_back(uint16_t(map[id]));
        }
        // Index tables are load-time control metadata, not candidate residency.
        for(auto i:local.vertices)map[i]=-1;
        if(local.vertices.size()>Capacity)return false;
    }return true;
}
bool check_math(Owner& owner) {
    auto& p=owner.package;if(!p.compact())return true;
    double max_pixel=0,max_depth=0,max_uv=0;unsigned checked=0;
    for(unsigned b=0;b<p.header().batch_count;++b) {
        const auto& batch=p.compact_batches()[b];mat_load(&matrix);
        if(!render::prepare_static_batch(p,batch,slots,Capacity,1.0f,render::StaticMathBackend::Sh4zam))return false;
        for(unsigned i=0;i<batch.vertex_count;++i) {
            const unsigned index=batch.first_vertex+i;float x,y,z,w=1;
            uint16_t u,v;unsigned color;
            if(p.compact_vertices()) {const auto& a=p.compact_vertices()[index];x=a.x;y=a.y;z=a.z;u=a.u;v=a.v;color=a.argb;}
            else {const auto& a=p.compact_positions()[index];x=a.x;y=a.y;z=a.z;const auto& t=p.compact_attributes()[index];u=t.u;v=t.v;color=t.argb;}
            mat_trans_nodiv(x,y,z,w);const float inverse=1.0f/w;
            max_pixel=std::max(max_pixel,double(std::max(std::fabs(slots[i].x-x*inverse),std::fabs(slots[i].y-y*inverse))));
            max_depth=std::max(max_depth,double(std::fabs(slots[i].z-inverse)));
            max_uv=std::max(max_uv,double(std::max(std::fabs(slots[i].u-(batch.uv_bias[0]+u*batch.uv_scale[0])),std::fabs(slots[i].v-(batch.uv_bias[1]+v*batch.uv_scale[1])))));
            if(color!=slots[i].argb || slots[i].oargb!=0)return false;
            ++checked;
        }
    }
    logf("math vertices=%u max_pixel=%.9f max_inverse_depth=%.9f max_uv=%.9f\n",checked,max_pixel,max_depth,max_uv);
    return max_pixel<=.002 && max_depth<=.000001 && max_uv<=.00001;
}
bool run(unsigned backend,unsigned iteration) {
    unsigned prep=0,pack=0,vertices=0,records=0,strips=0,triangles=0,fallbacks=0;
    const unsigned begin=ticks();
    for(auto& owner:owners) {
        auto& p=owner.package;mat_load(&matrix);
        for(unsigned b=0;b<p.header().batch_count;++b) {
            const auto& batch=p.compact()?p.compact_batches()[b].draw:p.batches()[b];
            unsigned t=ticks();
            if(p.compact()) {
                const auto& cb=p.compact_batches()[b];vertices+=cb.vertex_count;
                if(!render::prepare_static_batch(p,cb,slots,Capacity,1.0f,backend?render::StaticMathBackend::Sh4zam:render::StaticMathBackend::D349))return false;
            } else {legacy_prepare(p,owner.legacy[b]);vertices+=owner.legacy[b].vertices.size();}
            prep+=unsigned(ticks()-t);t=ticks();unsigned legacy_offset=0;
            if(!(batch.flags&room::kBatchStripOrderPreserved)) {
                const auto* ids=p.compact()?p.local_indices()+batch.first_index:owner.legacy[b].triangles.data();
                for(unsigned k=0;k<batch.index_count;k+=3) {
                    if(!render::prepare_direct_strip(packets,3,.01f,100000.0f,
                        [&](unsigned j,render::DirectStripVertex& v){v=slots[ids[k+j]];return true;}))return false;
                    asm volatile(""::"r"(packets):"memory");records+=3;++triangles;++fallbacks;
                }
            } else for(unsigned i=0;i<batch.primitive_count;++i) {
                const auto& prim=p.primitives()[batch.first_primitive+i];
                if(prim.vertex_count>Capacity)return false;
                const auto* ids=p.compact()?p.local_primitive_indices()+prim.first_vertex:owner.legacy[b].indices.data()+legacy_offset;
                const bool intact=render::prepare_direct_strip(packets,prim.vertex_count,.01f,100000.0f,
                    [&](unsigned k,render::DirectStripVertex& v){v=slots[ids[k]];return true;});
                if(!intact)return false;
                asm volatile(""::"r"(packets):"memory");
                records+=prim.vertex_count;triangles+=prim.triangle_count;++strips;
                legacy_offset+=prim.vertex_count;
            }
            pack+=unsigned(ticks()-t);sink=sink+packets[0].argb;
        }
    }
    const unsigned elapsed=ticks()-begin;
    if(iteration>=4) logf("sample backend=%u iteration=%u prep_us=%.3f pack_us=%.3f total_us=%.3f vertices=%u records=%u strips=%u triangles=%u fallback_triangles=%u\n",
        backend,iteration-4,us(prep),us(pack),us(elapsed),vertices,records,strips,triangles,fallbacks);
    return true;
}
void auxiliary_math() {
    float max_error=0;unsigned t=ticks();
    for(unsigned n=0;n<40000;++n){const float f=float(n%999)/999.0f;const float a=float(n%37),b=-float(n%29);copies[n%8192]=unsigned(100000+(a+(b-a)*f)*1000);asm volatile("":::"memory");}
    const unsigned reference=ticks()-t;t=ticks();
    for(unsigned n=0;n<40000;++n){const float f=float(n%999)/999.0f;const float a=float(n%37),b=-float(n%29);copies[n%8192]=unsigned(100000+shz_lerpf(a,b,f)*1000);asm volatile("":::"memory");}
    const unsigned candidate=ticks()-t;
    for(unsigned n=0;n<999;++n){float f=float(n)/999.0f;max_error=std::max(max_error,std::fabs(shz_lerpf(-13.2f,19.4f,f)-(-13.2f+(19.4f+13.2f)*f)));}
    t=ticks();for(unsigned n=0;n<1000;++n){std::memcpy(copy_dest,copies,sizeof(copies));asm volatile("":::"memory");}const unsigned copy_ref=ticks()-t;
    t=ticks();for(unsigned n=0;n<1000;++n){shz_memcpy32(copy_dest,copies,sizeof(copies));asm volatile("":::"memory");}const unsigned copy_shz=ticks()-t;
    logf("aux lerp_ref_us=%.3f lerp_shz_us=%.3f lerp_max_error=%.9f copy_ref_us=%.3f copy_shz_us=%.3f copy_bytes=32768000 alignment=32\n",us(reference),us(candidate),max_error,us(copy_ref),us(copy_shz));
}
}
int main() {
    re4dc_probe_stage=1;
    logf("room-layout CPU fixture GCC=%s TMU2=%d source_heap=not_present PVR=not_submitted\n",__VERSION__,timer_running(TMU2));
    const char* paths[]={"/rd/MAINSCENARIO.re4room","/rd/FILE_00.re4room","/rd/FILE_01.re4room","/rd/FILE_02.re4room"};
    bool good=timer_running(TMU2)!=0;
    for(unsigned i=0;good && i<4;++i) {
        if(!owners[i].package.open(paths[i])) {logf("FAIL load owner=%u reason=%s\n",i,owners[i].package.error());good=false;break;}
        auto& p=owners[i].package;
        logf("owner=%u version=%u layout=%u vertices=%u batches=%u\n",i,p.header().version,p.compact()?unsigned(p.compact_header()->layout):0,p.header().vertex_count,p.header().batch_count);
        if(!p.compact())good=build_legacy(owners[i]);
        if(good)good=check_math(owners[i]);
    }
    re4dc_probe_stage=2;
    for(unsigned iteration=0;good && iteration<36;++iteration) {
        good=run(0,iteration);
        if(good && owners[0].package.compact())good=run(1,iteration);
    }
    if(good)auxiliary_math();
    for(auto& o:owners)o.package.close();
    logf("result=%s slots_bytes=%u packet_bytes=%u fixture_only=1\n",good?"PASS":"FAIL",unsigned(sizeof(slots)),unsigned(sizeof(packets)));
    re4dc_probe_stage=good?100:400;
    for(;;)thd_sleep(100);
}
