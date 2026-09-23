// Recovered scroll objects -> D349 native static room packages (v4 AoS20).
//
// The source still decides everything about an object: setObj creates and
// places it, its visibility gates decide whether commonModelTrans runs, and
// materialSetup/alphaSetup/blend/cull state is captured per part exactly as
// for the generic path. Only the geometry changes: a bound part draws the
// prelit package batches whose material carries its (texId, alphaTex) key,
// instead of decoding its GX display list and lighting its vertices.
//
// Ownership reuses the existing boundaries. A package view opens on the first
// bind of its owner (main scenario or source block) and retires with that
// owner. Each package source slot records the one live object bound to it and
// that object's creation serial; nothing else is registered. Packets, headers,
// texture pins, pass selection and translucent deferral are the existing
// native_ui frame owner's (re4dc_model_packet_*/re4dc_model_defer_part).
#include <kos.h>
#include <fcntl.h>
#include <malloc.h>
#include <unistd.h>
#include <cmath>
#include <stdio.h>
#include <cstring>
#include "native_static.h"
#include "native_model.h"
#include "re4dc_platform.h"
#include "../../room/room_package.hpp"
#include "../../room/static_room_prepare.hpp"
#include "../../room/pvr_geometry.hpp"

#ifndef RE4DC_NATIVE_STATIC
#define RE4DC_NATIVE_STATIC 0
#endif
#ifndef RE4DC_NATIVE_STATIC_OWNERS
#define RE4DC_NATIVE_STATIC_OWNERS 1U // bit 0 main scenario, bit n+1 block n
#endif

namespace {
using re4dc::room::Package;
constexpr unsigned kViews=6;           // main + source blocks 0..4
constexpr unsigned kMaxMaterials=64;   // per-frame key ownership is one mask word
// Package coordinates are source world units times --source-unit-scale.
constexpr float kPackageToSource=1000.0f;

struct Binding {
    const void* object; unsigned serial, frame;
    unsigned long long drawn, fallback; // material bits owned this frame
    unsigned first_group, group_count;  // resolve_source() at bind
    float world[12];                    // placement the package was baked at
};
struct View {
    Package package;
    unsigned char* storage=nullptr; unsigned bytes=0;
    Binding* bindings=nullptr;
    re4dc::room::MaterialSourceKey keys[kMaxMaterials];
    unsigned room=0; bool attempted=false;
};
View views[kViews];
Re4dcStaticStats stats{};
unsigned last_log_frame=~0U;

unsigned view_index(int block){return block<0?0U:unsigned(block)+1U;}
const char* owner_name(unsigned index,char* out,unsigned size){
    if(!index)snprintf(out,size,"MAINSCENARIO");
    else snprintf(out,size,"FILE_%02u",index-1U);
    return out;
}

void retire(View& v){
    v.package.close();
    if(v.storage){re4dc_static_free(v.storage);stats.package_bytes-=v.bytes;--stats.owners_open;}
    v.storage=nullptr;v.bytes=0;v.bindings=nullptr;v.attempted=false;v.room=0;
}

bool open(View& v,unsigned index,unsigned room){
    if(v.storage && v.room==room)return true;
    if(v.attempted && v.room==room)return false;
    retire(v);v.attempted=true;v.room=room;
    char name[16],path[64];
    snprintf(path,sizeof(path),"/cd/dc/native/r%x%02x/%s.re4room",room>>8,room&255U,owner_name(index,name,sizeof(name)));
    const file_t file=fs_open(path,O_RDONLY);
    if(file==FILEHND_INVALID){++stats.open_failures;re4dc_log("native static: %s missing\n",path);return false;}
    const unsigned size=unsigned(fs_total(file));
    // Package bytes first (32-aligned for v4 sections), then one slot per source.
    const unsigned package_bytes=(size+31U)&~31U;
    stats.heap_before=re4dc_static_heap_free();
    unsigned char* storage=nullptr;
    if(size>=sizeof(re4dc::room::CompactHeader)){
        re4dc::room::CompactHeader header;
        if(fs_read(file,&header,sizeof(header))==ssize_t(sizeof(header)) && header.source_count<=4096){
            const unsigned bytes=package_bytes+header.source_count*unsigned(sizeof(Binding));
            storage=static_cast<unsigned char*>(re4dc_static_alloc(bytes));
            if(storage){
                v.bytes=bytes;std::memcpy(storage,&header,sizeof(header));
                const ssize_t rest=ssize_t(size-sizeof(header));
                if(fs_read(file,storage+sizeof(header),rest)!=rest){re4dc_static_free(storage);storage=nullptr;}
            }else ++stats.alloc_rejects;
        }
    }
    fs_close(file);
    stats.heap_after=re4dc_static_heap_free();
    if(!storage){re4dc_log("native static: %s not loaded (size=%u heap=%d)\n",path,size,stats.heap_before);return false;}
    v.storage=storage;
    if(!v.package.adopt(storage,size) || !v.package.material_keys() ||
       v.package.header().material_count>kMaxMaterials){
        re4dc_log("native static: %s rejected: %s keyed=%d materials=%u\n",path,
            v.package.error()?v.package.error():"layout",v.package.material_keys(),v.package.header().material_count);
        re4dc_static_free(storage);v.storage=nullptr;v.bytes=0;v.package.close();++stats.open_failures;return false;
    }
    const auto& b=v.package.header();
    for(unsigned m=0;m<b.material_count;++m)
        re4dc::room::material_source_key(v.package.materials()[m],v.keys[m]);
    v.bindings=reinterpret_cast<Binding*>(storage+package_bytes);
    std::memset(v.bindings,0,v.package.compact_header()->source_count*sizeof(Binding));
    ++stats.owners_open;stats.package_bytes+=v.bytes;
    // KOS heap headroom: the source arena is a fixed 13 MiB memalign, so image
    // growth comes out of this. Free chunks plus the sbrk break (D367 failed
    // with the break 4 KiB below 0x8cff0000).
    const struct mallinfo kos=mallinfo();
    re4dc_log("native static: %s bytes=%u sources=%u groups=%u batches=%u materials=%u heap4=%d->%d kos_free=%d kos_break=%p\n",
        path,v.bytes,v.package.compact_header()->source_count,b.group_count,b.batch_count,b.material_count,
        stats.heap_before,stats.heap_after,kos.fordblks,sbrk(0));
    return true;
}

// 3x4 row-major affine helpers (GX Mtx layout).
void concat(const float* a,const float* b,float* out){
    for(unsigned r=0;r<3;++r)for(unsigned c=0;c<4;++c)
        out[4*r+c]=a[4*r]*b[c]+a[4*r+1]*b[4+c]+a[4*r+2]*b[8+c]+(c==3?a[4*r+3]:0.0f);
}
bool inverse(const float* m,float* out){
    const float a=m[0],b=m[1],c=m[2],d=m[4],e=m[5],f=m[6],g=m[8],h=m[9],i=m[10];
    const float A=e*i-f*h,B=f*g-d*i,C=d*h-e*g,det=a*A+b*B+c*C;
    if(!std::isfinite(det) || std::fabs(det)<1e-12f)return false;
    const float s=1.0f/det;
    const float r[9]={A*s,(c*h-b*i)*s,(b*f-c*e)*s,B*s,(a*i-c*g)*s,(c*d-a*f)*s,C*s,(b*g-a*h)*s,(a*e-b*d)*s};
    for(unsigned row=0;row<3;++row){
        out[4*row]=r[3*row];out[4*row+1]=r[3*row+1];out[4*row+2]=r[3*row+2];
        out[4*row+3]=-(r[3*row]*m[3]+r[3*row+1]*m[7]+r[3*row+2]*m[11]);
    }
    return true;
}

// Combined screen matrix whose W is view depth: the same mapping as
// native_model.cpp project() applied to modelview-space positions.
void load_screen(const float* mv,const float* p,const float* v){
    const float sx=640.0f/v[2],sy=480.0f/v[3];
    const float row0[4]={320.0f*p[1],0,320.0f*p[2]-sx*(v[0]+v[2]*.5f),0};
    const float row1[4]={0,-240.0f*p[3],-240.0f*p[4]-sy*(v[1]+v[3]*.5f),0};
    const float row2[4]={0,0,1,0},row3[4]={0,0,-1,0};
    const float* rows[4]={row0,row1,row2,row3};
    alignas(32) static matrix_t screen;
    for(unsigned r=0;r<4;++r)for(unsigned c=0;c<4;++c){
        float value=c==3?rows[r][3]:0.0f;
        for(unsigned k=0;k<3;++k)value+=rows[r][k]*mv[4*k+c];
        screen[c][r]=value; // KOS matrix_t is column-major for ftrv
    }
    mat_load(&screen);
}

struct Located { View* view; Binding* binding; unsigned source; };
bool locate(const Re4dcModelPart& p,Located& out){
    for(auto& v:views){
        if(!v.storage)continue;
        const unsigned count=v.package.compact_header()->source_count;
        for(unsigned s=0;s<count;++s){
            Binding& b=v.bindings[s];
            if(b.object!=p.model)continue;
            if(b.serial!=p.serial){++stats.stale_bindings;return false;}
            out={&v,&b,s};return true;
        }
    }
    return false;
}

struct Draw {
    const Re4dcModelPart& p; View& view; unsigned material;
    float mv[12];  // package -> view: group bounds
    float near,far;
    float mvq[12]={}; // stored corner -> view (mv, or mv with the AoS12 grid folded in)
    const std::uint32_t* palette=nullptr;
    Re4dcModelPacket packet{}; pvr_vertex_t* dst=nullptr;
    unsigned used=0,input=0,output=0,alpha=0;
    bool streaming=false,bound=false,submitted=false;
    re4dc::render::ClipParameters clip{};

    static void project(float& x,float& y,float& z,void* context){
        const auto& d=*static_cast<const Draw*>(context);
        const float* p=d.p.projection;const float* v=d.p.viewport;
        const float inv=1.0f/(-z);
        x=(v[2]*.5f*(p[1]*x+p[2]*z)*inv+v[0]+v[2]*.5f)*640.f/v[2];
        y=(-v[3]*.5f*(p[3]*y+p[4]*z)*inv+v[1]+v[3]*.5f)*480.f/v[3];
        z=inv;
    }
    bool bind(){
        if(bound)return true;
        if(!re4dc_model_packet_begin(&p,&packet))return false;
        dst=static_cast<pvr_vertex_t*>(packet.vertices);bound=true;
        load_screen(mvq,p.projection,p.viewport); // binding may yield
        return true;
    }
    bool flush(){
        if(!streaming || !used)return false;
        re4dc_model_packet_commit(used);submitted=true;used=0;
        load_screen(mvq,p.projection,p.viewport);
        return true;
    }
    float u(float value)const{return (value+p.uv_offset[0])*packet.u_scale;}
    float v(float value)const{return (value+p.uv_offset[1])*packet.v_scale;}
    // AoS12 corners stay in grid units: mvq folds origin + q * step in, so the
    // per-corner cost is three integer conversions, not a dequantize.
    re4dc::render::StaticCorner corner(const re4dc::room::CompactVertex& in)const{
        return {in.x,in.y,in.z,in.u,in.v,in.argb};
    }
    re4dc::render::StaticCorner corner(const re4dc::room::CompactVertex12& in)const{
        return {float(in.x),float(in.y),float(in.z),in.u,in.v,palette[in.color]};
    }
    void clip_vertex(const re4dc::render::StaticCorner& in,const re4dc::room::CompactBatch& batch,
                     re4dc::render::RenderVertex& out){
        float x=mvq[0]*in.x+mvq[1]*in.y+mvq[2]*in.z+mvq[3];
        float y=mvq[4]*in.x+mvq[5]*in.y+mvq[6]*in.z+mvq[7];
        float z=mvq[8]*in.x+mvq[9]*in.y+mvq[10]*in.z+mvq[11];
        out={};out.position.world_x=x;out.position.world_y=y;out.position.world_z=z;out.position.depth=-z;
        if(z!=0)project(x,y,z,this);
        out.position.x=x;out.position.y=y;out.position.z=z;
        out.u=u(batch.uv_bias[0]+float(in.u)*batch.uv_scale[0]);
        out.v=v(batch.uv_bias[1]+float(in.v)*batch.uv_scale[1]);
        out.light_red=float((in.argb>>16)&255U)/255.0f;
        out.light_green=float((in.argb>>8)&255U)/255.0f;
        out.light_blue=float(in.argb&255U)/255.0f;
    }
    // 1 emitted/culled, 0 failed before anything was published, -1 failed after.
    template<class Vertex>
    int strip(const Vertex* base,const re4dc::room::CompactBatch& batch,
              const std::uint16_t* index,unsigned count){
        input+=count-2;
        if(count<=packet.capacity){
            if(count>packet.capacity-used && !flush())return submitted?-1:0;
            unsigned outside=15;
            const bool ready=re4dc::render::prepare_direct_strip(dst+used,count,near,far,
                [&](std::uint32_t local,re4dc::render::DirectStripVertex& out){
                    out=re4dc::render::prepare_static_vertex(corner(base[index[local]]),batch,0.0f);
                    out.u=u(out.u);out.v=v(out.v);out.argb=(out.argb&0xffffffU)|alpha;
                    outside&=(out.x<0?1U:0U)|(out.x>640.0f?2U:0U)|(out.y<0?4U:0U)|(out.y>480.0f?8U:0U);
                    return true;
                });
            stats.vertices+=count;
            if(ready){
                if(outside)++stats.strips_culled;
                else {used+=count;output+=count-2;++stats.strips;}
                return 1;
            }
        }
        // Near/far crossing or oversize: the shared clipper, triangle by triangle,
        // keeping strip winding (odd triangles swap their first two corners).
        ++stats.strips_clipped;
        const float alphas[3]={float(alpha>>24)/255.0f,float(alpha>>24)/255.0f,float(alpha>>24)/255.0f};
        for(unsigned i=2;i<count;++i){
            re4dc::render::RenderVertex tri[3];
            clip_vertex(corner(base[index[i-2+(i&1)]]),batch,tri[0]);
            clip_vertex(corner(base[index[i-1-(i&1)]]),batch,tri[1]);
            clip_vertex(corner(base[index[i]]),batch,tri[2]);
            if(packet.capacity-used<6 && !flush())return submitted?-1:0;
            const unsigned emitted=re4dc::render::clip_projected_triangle(tri,dst+used,p.cull,clip,nullptr,alphas);
            used+=emitted*3;output+=emitted;stats.triangles_clipped+=emitted;
        }
        return 1;
    }
    // 1 drawn (possibly nothing visible), 0 fallback allowed, -1 frame aborted.
    int run(const re4dc::room::CompactSourceRange& range){
        const auto& package=view.package;
        if(!re4dc_model_packet_reserve(&p,&packet)){++stats.reserve_rejects;return 0;}
        streaming=re4dc_model_packet_streaming()!=0;
        clip={near,far,640,480,project,this};
        const auto* groups=package.compact_groups();
        const auto* batches=package.compact_batches();
        const auto* vertices=package.compact_vertices();
        const auto* vertices12=package.compact_vertices12();
        palette=package.compact_palette();
        const auto* prims=package.primitives();
        const auto* strip_index=package.local_primitive_indices();
        const auto* triangle_index=package.local_indices();
        for(unsigned g=range.first_group;g<range.first_group+range.group_count;++g){
            const auto& group=groups[g];
            bool has=false;
            for(unsigned k=0;k<group.batch_count && !has;++k)has=batches[group.first_batch+k].draw.material==material;
            if(!has)continue;
            const re4dc::render::DrawBounds bounds{{group.bounds_min[0],group.bounds_min[1],group.bounds_min[2]},
                                                   {group.bounds_max[0],group.bounds_max[1],group.bounds_max[2]}};
            if(!re4dc::render::group_visible(bounds,mv,p.projection,p.viewport,near,far,0)){++stats.groups_culled;continue;}
            ++stats.groups_visible;
            if(!bind()){++stats.bind_rejects;return submitted?-1:0;}
            for(unsigned k=0;k<group.batch_count;++k){
                const auto& batch=batches[group.first_batch+k];
                if(batch.draw.material!=material)continue;
                ++stats.batches;
                const auto walk=[&](const auto* base){
                    int result=1;
                    if(batch.draw.flags&re4dc::room::kBatchTrianglesResident){
                        for(unsigned t=0;t<batch.draw.index_count && result>0;t+=3)
                            result=strip(base,batch,triangle_index+batch.draw.first_index+t,3);
                    }else for(unsigned s=0;s<batch.draw.primitive_count && result>0;++s){
                        const auto& prim=prims[batch.draw.first_primitive+s];
                        result=strip(base,batch,strip_index+prim.first_vertex,prim.vertex_count);
                    }
                    return result;
                };
                const int result=vertices12?walk(vertices12+batch.first_vertex):walk(vertices+batch.first_vertex);
                if(result<=0)return result;
            }
        }
        if(used)re4dc_model_packet_commit(used);
        re4dc_model_result(0,input,output);
        return 1;
    }
};
} // namespace

extern "C" void re4dc_static_bind(const void* object,unsigned room,int block,unsigned work,
                                  unsigned bin,unsigned common,unsigned serial,const float world[12]){
#if RE4DC_NATIVE_STATIC
    const unsigned index=view_index(block);
    if(index>=kViews || !(RE4DC_NATIVE_STATIC_OWNERS&(1U<<index)))return;
    View& v=views[index];
    if(!open(v,index,room))return;
    re4dc::room::CompactSourceRange range;
    if(!v.package.resolve_source(block<0?0xffU:std::uint8_t(block),std::uint16_t(work),
                                 std::uint16_t(bin),common!=0,range)){++stats.bind_misses;return;}
    Binding& b=v.bindings[range.source];
    if(b.object && (b.object!=object || b.serial!=serial))++stats.bind_conflicts;
    b={object,serial,~0U,0,0,range.first_group,range.group_count,{}};
    std::memcpy(b.world,world,sizeof(b.world));
    ++stats.binds;
#else
    (void)object;(void)room;(void)block;(void)work;(void)bin;(void)common;(void)serial;(void)world;
#endif
}

extern "C" void re4dc_static_retire_owner(int block){
    const unsigned index=view_index(block);
    if(index<kViews && views[index].attempted)retire(views[index]);
}
extern "C" void re4dc_static_retire_all(){for(auto& v:views)if(v.attempted)retire(v);}
extern "C" const Re4dcStaticStats* re4dc_static_stats(){return &stats;}

#if RE4DC_NATIVE_STATIC
namespace {
// Lowest alpha in the source colour array; 0 when it cannot be bounded.
unsigned vertex_alpha_min(const Re4dcModelPart& p){
    if(!(p.flags&0x80000000U) || !p.colors || p.uv<=p.colors)return 0;
    const unsigned bytes=unsigned(p.uv-p.colors);
    if(bytes%4 || bytes>65536)return 0;
    unsigned low=255;
    for(unsigned i=3;i<bytes;i+=4)if(p.colors[i]<low)low=p.colors[i];
    return low;
}
}
#endif
extern "C" int re4dc_static_submit(const Re4dcModelPart* part){
#if RE4DC_NATIVE_STATIC
    const Re4dcModelPart& p=*part;
    if(!p.world || !p.view || !p.static_geometry || !stats.owners_open)return 0;
    Located at;
    if(!locate(p,at))return 0;
    Binding& b=*at.binding;View& v=*at.view;
    const unsigned frame=re4dc_ui_frame();
    if(frame!=last_log_frame && frame%600==0){
        last_log_frame=frame;
        re4dc_log("native static: frame=%u native=%u skipped=%u fallback=%u key_misses=%u groups=%u/%u strips=%u culled=%u clipped=%u moved=%u stale=%u vertex_alpha=%u opaque=%u alpha_min=%u reserve=%u bind=%u aborts=%u\n",
            frame,stats.parts_native,stats.parts_skipped,stats.parts_fallback,stats.key_misses,stats.groups_visible,
            stats.groups_visible+stats.groups_culled,stats.strips,stats.strips_culled,stats.strips_clipped,stats.moved_objects,stats.stale_bindings,
            stats.vertex_alpha,stats.vertex_opaque,stats.vertex_alpha_min,stats.reserve_rejects,stats.bind_rejects,stats.aborts);
    }
    if(b.frame!=frame){b.frame=frame;b.drawn=b.fallback=0;}
    const auto& header=v.package.header();
    unsigned material=header.material_count;
    for(unsigned m=0;m<header.material_count;++m)
        if(v.keys[m].texture==p.source_key[0] && v.keys[m].alpha==p.source_key[1]){material=m;break;}
    if(material==header.material_count){++stats.key_misses;return 0;}
    const unsigned long long bit=1ULL<<material;
    // One part per key draws all of that key's batches; its twins either skip
    // (drawn) or follow it to the generic path, never both.
    if(b.fallback&bit){++stats.parts_fallback;return 0;}
    if(b.drawn&bit){++stats.parts_skipped;return 1;}
    // Per-vertex source alpha: the prelit package is opaque, which is exact only
    // while every entry of the model's colour array (pClr up to pTex) is 255.
    Re4dcModelPart opaque;
    const Re4dcModelPart* drawn=&p;
    if(p.alpha_state&256){
        const unsigned low=vertex_alpha_min(p);
        if((!stats.vertex_alpha && !stats.vertex_opaque) || low<stats.vertex_alpha_min)stats.vertex_alpha_min=low;
        if(low<255){b.fallback|=bit;++stats.parts_fallback;++stats.vertex_alpha;return 0;}
        opaque=p;opaque.alpha_state=255;drawn=&opaque;++stats.vertex_opaque;
    }
    if(p.cull==3){b.drawn|=bit;return 1;}
    if(p.projection[0]!=0 || p.viewport[2]<=0 || p.viewport[3]<=0){b.fallback|=bit;return 0;}
    const float near=p.projection[6]/(p.projection[5]-1),far=p.projection[6]/p.projection[5];
    if(!std::isfinite(near)||!std::isfinite(far)||near<=0||far<=near){b.fallback|=bit;return 0;}
    // Queued translucent parts replay through this function in pass order.
    if(re4dc_model_defer_part(drawn))return 1;

    Draw d{*drawn,v,material,{},near,far};
    d.alpha=(drawn->alpha_state&255U)<<24;
    // Package space -> source world (x1000), then the object's movement since
    // it was bound (usually none), then the live source camera.
    float to_world[12]={kPackageToSource,0,0,0, 0,kPackageToSource,0,0, 0,0,kPackageToSource,0};
    if(std::memcmp(p.world,b.world,sizeof(b.world))){
        float inv[12],delta[12],moved[12];
        if(!inverse(b.world,inv)){b.fallback|=bit;return 0;}
        concat(p.world,inv,delta);concat(delta,to_world,moved);
        std::memcpy(to_world,moved,sizeof(moved));++stats.moved_objects;
    }
    concat(p.view,to_world,d.mv);
    if(const auto* q=v.package.compact_quantization()){
        const float grid[12]={q->step[0],0,0,q->origin[0], 0,q->step[1],0,q->origin[1], 0,0,q->step[2],q->origin[2]};
        concat(d.mv,grid,d.mvq);
    }else std::memcpy(d.mvq,d.mv,sizeof(d.mv));
    load_screen(d.mvq,p.projection,p.viewport);
    const int result=d.run({at.source,b.first_group,b.group_count});
    if(result>0){b.drawn|=bit;++stats.parts_native;return 1;}
    if(result<0){re4dc_model_packet_abort();b.drawn|=bit;++stats.aborts;return 1;}
    b.fallback|=bit;++stats.parts_fallback;return 0;
#else
    (void)part;return 0;
#endif
}
