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
#include <cstdlib>
#include "native_static.h"
#if RE4DC_QUALITY
#include "quality.h"
#endif
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
#ifndef RE4DC_NATIVE_MESH
#define RE4DC_NATIVE_MESH 0
#endif
#if RE4DC_NATIVE_MESH
#include "../../room/instanced_mesh.hpp"
#endif
// Transform-once meshlet path for R4IM meshes (room/mesh_fastpath.hpp). 0 keeps
// the per-strip-corner Emitter path for every meshlet (A/B reference).
#ifndef RE4DC_MESH_FASTPATH
#define RE4DC_MESH_FASTPATH 1
#endif
#ifndef RE4DC_MESH_CLASSIFY
#define RE4DC_MESH_CLASSIFY 0 // 1: skip outcodes in wholly visible meshlets (+1.5 KiB image)
#endif
#if RE4DC_NATIVE_MESH && RE4DC_MESH_FASTPATH
#include "../../room/mesh_fastpath.hpp"
#endif
// R4IM v2 levels of detail (convert_room_bins.py --lod). Per visible cluster
// the coarsest level whose error projects to at most RE4DC_MESH_LOD_PX pixels
// at the cluster's nearest depth is drawn. 0 accepts v1 packages only.
#ifndef RE4DC_MESH_LOD
#define RE4DC_MESH_LOD 0
#endif
#ifndef RE4DC_MESH_LOD_PX
#define RE4DC_MESH_LOD_PX 3
#endif
// Source fog on the native path: GXSetFog state becomes PVR table fog on model
// headers (native_ui.cpp), ramped to 100% at the source View far plane, and
// scenery clusters/meshlets beyond that far plane are rejected (the source's
// own object gate distance, light.cpp setFog/hokanMove -> View.setFarPlane).
#ifndef RE4DC_NATIVE_FOG
#define RE4DC_NATIVE_FOG 0
#endif
#ifndef RE4DC_FOG_FAR
#define RE4DC_FOG_FAR 0 // >0: DC fog/cull far plane (source units) when shorter than the source's
#endif
#ifndef RE4DC_FOG_BACKGROUND
#define RE4DC_FOG_BACKGROUND 1 // background colour follows the fog colour while fog is on
#endif
// D367 frontend30 (obj/frontend30.h; all default off = previous image).
// COPY_LEAN: no zero-fill of clip scratch written before it is read, one
// XMTRX load per mesh part, and no lighting snapshot for deferred parts that
// are already lit. MESH_DIRECT: mesh strips go to the TA through the store
// queues (re4dc_model_direct_begin, TA_DIRECT=1) instead of slab + pvr_prim.
#ifndef RE4DC_COPY_LEAN
#define RE4DC_COPY_LEAN 0
#endif
#ifndef RE4DC_FRONT_LEAN
#define RE4DC_FRONT_LEAN 0
#endif
#ifndef RE4DC_MESH_DIRECT
#define RE4DC_MESH_DIRECT 0
#endif
#ifndef RE4DC_HW_LEAN
#define RE4DC_HW_LEAN 0 // frontend30 pass 2: SH-4 hardware-cost trims (fsrra 1/w in the clipper projection)
#endif
// Clip-path colour / alpha scaling: HW_LEAN multiplies by 1/255 (no fdiv; <= 1 ulp).
#if RE4DC_HW_LEAN
#define RE4DC_INV255 *(1.0f/255.0f)
#else
#define RE4DC_INV255 /255.0f
#endif
#if RE4DC_MESH_DIRECT
#if !RE4DC_NATIVE_MESH || !RE4DC_MESH_FASTPATH
#error MESH_DIRECT extends the NATIVE_MESH fast path
#endif
#include "ta_direct.hpp"
#endif
#if RE4DC_COPY_LEAN
#include <new>
// native_ui.cpp: the translucent queue without a lighting snapshot.
extern "C" int re4dc_model_defer_part_unlit(const Re4dcModelPart*);
#endif
// D367 item 20, TREE_IMPOSTOR (blender30.mk; default off = previous image): a
// mesh with an impostor record draws beyond RE4DC_TREE_IMPOSTOR_MM of view
// depth as one camera-facing punch-through quad (mesh_impostor below).
#if RE4DC_TREE_IMPOSTOR
#if !RE4DC_NATIVE_MESH || !RE4DC_MESH_LOD
#error TREE_IMPOSTOR draws R4IM v2 impostor records (NATIVE_MESH=1 MESH_LOD=1)
#endif
extern "C" int re4dc_model_pt_begin(unsigned crc,unsigned fnv,unsigned width,unsigned height,int fog,Re4dcModelPacket* out);
#endif
// D367 item 21, MESH_TEXTURES (blender30.mk; default off = previous image): a
// part with a texture record draws with that prepared package (mesh_submit).
#if RE4DC_MESH_TEXTURES
#if !RE4DC_NATIVE_MESH || !RE4DC_MESH_LOD
#error MESH_TEXTURES draws R4IM v2 texture records (NATIVE_MESH=1 MESH_LOD=1)
#endif
extern "C" void re4dc_model_texture(const unsigned* key);
#endif

#if RE4DC_QUALITY_ASSETS
#if !RE4DC_QUALITY || !RE4DC_TREE_IMPOSTOR || !RE4DC_MESH_TEXTURES
#error QUALITY_ASSETS needs QUALITY=1 TREE_IMPOSTOR=1 MESH_TEXTURES=1
#endif
extern "C" int re4dc_fixture_read(const char* path,char* buffer,unsigned size);   // os.cpp
#endif

namespace {
using re4dc::room::Package;
#if RE4DC_QUALITY_ASSETS
// Standard asset set (D367_ASSET_PIPELINE.md s16). re4dc_std_room_enter() parses
// native/<room>/low/index.txt once per room entry (Standard mode only) into these
// fixed tables; the text buffer is freed after parsing. A rejected or missing index
// leaves the room on the Original packages (lod_px stays the Standard 5).
struct StdTex { unsigned crc,fnv; unsigned short width,height; unsigned vram; };
struct StdKey { unsigned crc,fnv; };
struct StdCull { unsigned char view,common; unsigned short mesh,bin; float mm; };
struct StdImp { unsigned char view,common; unsigned short bin; float mm; re4dc::room::MeshImpostor rec; };
struct StdPtex { unsigned char view,common; unsigned short part,bin; unsigned key[4]; };
// s16.5 split groves: one impostor per tree = a cluster range of one part.
struct StdImpt { unsigned char view,common; unsigned short bin,part,first,count; float mm; re4dc::room::MeshImpostor rec; };
constexpr unsigned kStdMesh=16,kStdTex=32,kStdDrop=16,kStdCull=64,kStdImp=32,kStdPtex=32,kStdImpt=32,kStdText=4096;
constexpr unsigned kStdTokens=24; // widest record: impt, 21 tokens
struct StdRoom {
    unsigned room=~0U; bool active=false;                 // active: index accepted for this room
    unsigned mesh_bytes[8]; unsigned char mesh_views;     // bit per mesh view: open low/<OWNER>
    unsigned char checked;                                // bit per mesh view: records verified at open
    unsigned ntex,ndrop,ncull,nimp,nptex,nimpt;
    StdTex tex[kStdTex]; StdKey drop[kStdDrop]; StdCull cull[kStdCull]; StdImp imp[kStdImp]; StdPtex ptex[kStdPtex]; StdImpt impt[kStdImpt];
};
StdRoom std_room;
unsigned std_stats[6]; // culled draws, impostor records used, baked parts, low/ opens, tree quads, tree cluster ranges drawn
#endif

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

#if RE4DC_QUALITY_ASSETS
constexpr unsigned kStdCommon=kViews; // COMMON's mesh view (mesh_views[kCommonView])
int std_owner(const char* s){
    if(!std::strcmp(s,"COMMON"))return int(kStdCommon);
    char name[16];
    for(unsigned i=0;i<kViews;++i)if(!std::strcmp(owner_name(i,name,sizeof(name)),s))return int(i);
    return -1;
}
bool std_hex_key(const char* s,unsigned& crc,unsigned& fnv){
    char* e=nullptr;
    crc=unsigned(std::strtoul(s,&e,16));if(e!=s+8 || *e!='-')return false;
    fnv=unsigned(std::strtoul(e+1,&e,16));return e==s+17 && !*e;
}
// Splits one line into at most kStdTokens space-separated tokens (in place).
unsigned std_tokens(char* line,char** t){
    unsigned n=0;
    for(char* s=line;*s && n<kStdTokens;){
        while(*s==' ')++s;
        if(!*s)break;
        t[n++]=s;
        while(*s && *s!=' ')++s;
        if(*s)*s++=0;
    }
    return n;
}
// Parses the index text; false (with a log line) rejects the whole index.
bool std_parse(char* text,unsigned room){
    StdRoom& r=std_room;
    unsigned lines=0;bool header=false,ended=false;
    char* next=text;
    while(*next && !ended){
        char* line=next;
        while(*next && *next!='\n')++next;
        if(*next)*next++=0;
        if(!*line)continue;                      // an empty last line
        if(*line=='#'){++lines;continue;}
        char* t[kStdTokens];const unsigned n=std_tokens(line,t);
        if(!n){++lines;continue;}
        const char* k=t[0];
        const auto num=[](const char* s){return unsigned(std::strtoul(s,nullptr,10));};
        const auto fp=[](const char* s){return float(std::strtod(s,nullptr));};
        if(!header){
            char want[8];snprintf(want,sizeof(want),"r%x%02x",room>>8,room&255U);
            if(n!=3 || std::strcmp(k,"re4dc-std") || std::strcmp(t[1],"1") || std::strcmp(t[2],want)){
                re4dc_log("quality assets: index header rejected (room %s)\n",want);return false;}
            header=true;++lines;continue;
        }
        if(!std::strcmp(k,"end")){
            if(n!=2 || num(t[1])!=lines){re4dc_log("quality assets: index end %s != %u lines\n",n>1?t[1]:"-",lines);return false;}
            ended=true;continue;
        }
        ++lines;
        if(!std::strcmp(k,"lod_px")){
            if(n>=2 && unsigned(fp(t[1])+0.5f)!=unsigned(re4dc_quality()->lod_px+0.5f))
                re4dc_log("quality assets: index lod_px %s, runtime %u\n",t[1],unsigned(re4dc_quality()->lod_px));
        }else if(!std::strcmp(k,"mesh")){
            const int v=n>=4?std_owner(t[1]):-1;
            if(v<0 || (r.mesh_views>>v)&1U){re4dc_log("quality assets: bad mesh record %s\n",n>1?t[1]:"-");return false;}
            r.mesh_views|=1U<<v;r.mesh_bytes[v]=num(t[2]);
        }else if(!std::strcmp(k,"tex")){
            StdTex x{};
            if(n<6 || !std_hex_key(t[1],x.crc,x.fnv) || r.ntex>=kStdTex){re4dc_log("quality assets: bad tex record\n");return false;}
            x.width=(unsigned short)num(t[2]);x.height=(unsigned short)num(t[3]);x.vram=num(t[4]);r.tex[r.ntex++]=x;
        }else if(!std::strcmp(k,"drop")){
            StdKey x{};
            if(n<2 || !std_hex_key(t[1],x.crc,x.fnv) || r.ndrop>=kStdDrop){re4dc_log("quality assets: bad drop record\n");return false;}
            r.drop[r.ndrop++]=x;
        }else if(!std::strcmp(k,"cull")){
            const int v=n>=6?std_owner(t[1]):-1;
            if(v<0 || r.ncull>=kStdCull){re4dc_log("quality assets: bad cull record\n");return false;}
            r.cull[r.ncull++]={(unsigned char)v,(unsigned char)(num(t[4])!=0),(unsigned short)num(t[2]),(unsigned short)num(t[3]),fp(t[5])};
        }else if(!std::strcmp(k,"imp")){
            const int v=n>=18?std_owner(t[1]):-1;
            StdImp x{};
            unsigned kc=0,kf=0;
            if(v<0 || r.nimp>=kStdImp || !std_hex_key(t[6],kc,kf)){re4dc_log("quality assets: bad imp record\n");return false;}
            x.view=(unsigned char)v;x.bin=(unsigned short)num(t[3]);x.common=(unsigned char)(num(t[4])!=0);x.mm=fp(t[5]);
            auto& q=x.rec;q.mesh=num(t[2]);q.key_crc=kc;q.key_fnv=kf;
            q.views=(std::uint16_t)num(t[7]);q.cols=(std::uint16_t)num(t[8]);q.cell_w=(std::uint16_t)num(t[9]);q.cell_h=(std::uint16_t)num(t[10]);
            q.atlas_w=(std::uint16_t)num(t[11]);q.atlas_h=(std::uint16_t)num(t[12]);
            q.centre[0]=fp(t[13]);q.centre[1]=fp(t[14]);q.centre[2]=fp(t[15]);q.half_w=fp(t[16]);q.half_h=fp(t[17]);q.reserved=0;
            if(!q.views || !q.cols || !q.cell_w || !q.cell_h || !(q.half_w>0.0f) || !(q.half_h>0.0f)){re4dc_log("quality assets: bad imp values\n");return false;}
            r.imp[r.nimp++]=x;
        }else if(!std::strcmp(k,"impt")){
            const int v=n>=21?std_owner(t[1]):-1;
            StdImpt x{};unsigned kc=0,kf=0;
            if(v<0 || r.nimpt>=kStdImpt || !std_hex_key(t[9],kc,kf)){re4dc_log("quality assets: bad impt record\n");return false;}
            x.view=(unsigned char)v;x.bin=(unsigned short)num(t[3]);x.common=(unsigned char)(num(t[4])!=0);
            x.part=(unsigned short)num(t[5]);x.first=(unsigned short)num(t[6]);x.count=(unsigned short)num(t[7]);x.mm=fp(t[8]);
            auto& q=x.rec;q.mesh=num(t[2]);q.key_crc=kc;q.key_fnv=kf;
            q.views=(std::uint16_t)num(t[10]);q.cols=(std::uint16_t)num(t[11]);q.cell_w=(std::uint16_t)num(t[12]);q.cell_h=(std::uint16_t)num(t[13]);
            q.atlas_w=(std::uint16_t)num(t[14]);q.atlas_h=(std::uint16_t)num(t[15]);
            q.centre[0]=fp(t[16]);q.centre[1]=fp(t[17]);q.centre[2]=fp(t[18]);q.half_w=fp(t[19]);q.half_h=fp(t[20]);q.reserved=0;
            if(!q.views || !q.cols || !q.cell_w || !q.cell_h || !x.count || x.first+x.count>64U || !(q.half_w>0.0f) || !(q.half_h>0.0f)){
                re4dc_log("quality assets: bad impt values\n");return false;}
            r.impt[r.nimpt++]=x;
        }else if(!std::strcmp(k,"ptex")){
            const int v=n>=8?std_owner(t[1]):-1;
            StdPtex x{};
            if(v<0 || r.nptex>=kStdPtex || !std_hex_key(t[5],x.key[0],x.key[1])){re4dc_log("quality assets: bad ptex record\n");return false;}
            x.view=(unsigned char)v;x.part=(unsigned short)num(t[2]);x.bin=(unsigned short)num(t[3]);x.common=(unsigned char)(num(t[4])!=0);
            x.key[2]=num(t[6]);x.key[3]=num(t[7]);r.ptex[r.nptex++]=x;
        }
        // orig and unknown record types: ignored (staging checks orig)
    }
    if(!header || !ended){re4dc_log("quality assets: index truncated (no end line)\n");return false;}
    return true;
}
// Verifies this view's records against the package opened for it (s16.3: mesh
// index in range with the recorded bin/common; ptex part inside such a mesh).
bool std_check_view(unsigned view,const re4dc::room::MeshPackage& pk){
    const StdRoom& r=std_room;
    const unsigned meshes=pk.header().mesh_count;
    const auto ok=[&](unsigned m,unsigned bin,unsigned common){
        return m<meshes && pk.meshes()[m].bin==bin && (pk.meshes()[m].common!=0)==(common!=0);};
    for(unsigned i=0;i<r.ncull;++i)if(r.cull[i].view==view && !ok(r.cull[i].mesh,r.cull[i].bin,r.cull[i].common))return false;
    for(unsigned i=0;i<r.nimp;++i)if(r.imp[i].view==view && !ok(r.imp[i].rec.mesh,r.imp[i].bin,r.imp[i].common))return false;
    for(unsigned i=0;i<r.nimpt;++i){
        const StdImpt& x=r.impt[i];if(x.view!=view)continue;
        if(!ok(x.rec.mesh,x.bin,x.common))return false;
        const auto& rec=pk.meshes()[x.rec.mesh];
        if(x.part<rec.first_part || x.part>=rec.first_part+rec.part_count)return false;
        if(x.first+x.count>pk.part_lods()[x.part].cluster_count)return false;
        for(unsigned j=0;j<r.nimp;++j)if(r.imp[j].view==view && r.imp[j].rec.mesh==x.rec.mesh)return false; // imp or impt, never both
    }
    for(unsigned i=0;i<r.nptex;++i){
        const StdPtex& x=r.ptex[i];if(x.view!=view)continue;
        bool found=false;
        for(unsigned m=0;m<meshes && !found;++m){
            const auto& rec=pk.meshes()[m];
            found=ok(m,x.bin,x.common) && x.part>=rec.first_part && x.part<rec.first_part+rec.part_count;
        }
        if(!found)return false;
    }
    return true;
}
#endif
void retire(View& v){
    v.package.close();
    if(v.storage){re4dc_static_free(v.storage);stats.package_bytes-=v.bytes;--stats.owners_open;}
    v.storage=nullptr;v.bytes=0;v.bindings=nullptr;v.attempted=false;v.room=0;
}

[[maybe_unused]] bool open(View& v,unsigned index,unsigned room){
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

// Strip emission shared by package and mesh draws: one source part's packet.
struct Emitter {
    const Re4dcModelPart& p;
    float mv[12];  // package -> view: group bounds
    float near,far;
    float mvq[12]={}; // stored corner -> view (mv, or mv with the AoS12 grid folded in)
    const std::uint32_t* palette=nullptr;
    Re4dcModelPacket packet{}; pvr_vertex_t* dst=nullptr;
    unsigned used=0,input=0,output=0,alpha=0;
    unsigned limit=0; // packet slots strips may use: packet.capacity less any borrowed tail
    bool streaming=false,bound=false,submitted=false;
    bool vertex_alpha=false; // corner alpha from the colour palette (source vertex alpha)
    re4dc::render::ClipParameters clip{};
#if RE4DC_HW_LEAN
    float proj_bx=0,proj_by=0; // project()'s viewport offsets in 640x480 pixels
    void set_clip(){
        const float* v=p.viewport;
        proj_bx=(v[0]+v[2]*.5f)*640.f/v[2];proj_by=(v[1]+v[3]*.5f)*480.f/v[3];
        clip={near,far,640,480,project,this};
    }
#else
    void set_clip(){clip={near,far,640,480,project,this};}
#endif

    static void project(float& x,float& y,float& z,void* context){
        const auto& d=*static_cast<const Emitter*>(context);
        const float* p=d.p.projection;const float* v=d.p.viewport;
#if RE4DC_HW_LEAN && defined(__sh__)
        // 1/|z| by fsrra(z*z): the clipper only keeps corners with depth=-z >= near > 0.
        // The viewport terms are per part (proj_setup): v[2]*.5*640/v[2] = 320, v[3]*.5*480/v[3] = 240.
        float inv=z*z;
        __asm__("fsrra %0" : "+f"(inv));
        (void)v;
        x=320.f*(p[1]*x+p[2]*z)*inv+d.proj_bx;
        y=-240.f*(p[3]*y+p[4]*z)*inv+d.proj_by;
        z=inv;
        return;
#else
        const float inv=1.0f/(-z);
#endif
        x=(v[2]*.5f*(p[1]*x+p[2]*z)*inv+v[0]+v[2]*.5f)*640.f/v[2];
        y=(-v[3]*.5f*(p[3]*y+p[4]*z)*inv+v[1]+v[3]*.5f)*480.f/v[3];
        z=inv;
    }
#if RE4DC_MESH_DIRECT
    // Store-queue sink (MeshDraw only): the header goes to the TA at bind(),
    // strips follow as they are accepted; the slab range is staging for the
    // clipper and the transform cache only. Nothing can be rolled back once
    // bound, so later failures abort the frame (submitted).
    bool direct=false; std::uint32_t* sq=nullptr; unsigned slots=0;
    void end_direct(){if(sq){re4dc_model_direct_end(slots);sq=nullptr;}}
    void put(unsigned n){sq=re4dc_ta_put(sq,dst+used,n);slots+=n;}
#endif
    bool bind(){
        if(bound)return true;
#if RE4DC_MESH_DIRECT
        if(direct){
            Re4dcModelDirect out{};
            if(!re4dc_model_direct_begin(&p,&out))return false;
            sq=out.sq;submitted=true;
            packet.vertices=out.scratch;packet.capacity=out.scratch_capacity;
            packet.u_scale=out.u_scale;packet.v_scale=out.v_scale;
            dst=static_cast<pvr_vertex_t*>(out.scratch);bound=true;limit=out.scratch_capacity;
            load_screen(mvq,p.projection,p.viewport); // binding may yield
            return true;
        }
#endif
        if(!re4dc_model_packet_begin(&p,&packet))return false;
        dst=static_cast<pvr_vertex_t*>(packet.vertices);bound=true;limit=packet.capacity;
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
    // Packages index a palette; lit meshes (palette==nullptr) store ARGB1555.
    [[gnu::always_inline]] static std::uint32_t argb1555(std::uint16_t c){
        const std::uint32_t r=(c>>10)&31U,g=(c>>5)&31U,b=c&31U;
        return ((c&0x8000U)?0xff000000U:0U)|(((r<<3)|(r>>2))<<16)|(((g<<3)|(g>>2))<<8)|((b<<3)|(b>>2));
    }
    // Per corner: this unit is -Os, which otherwise keeps the decode out of line.
    [[gnu::always_inline]] re4dc::render::StaticCorner corner(const re4dc::room::CompactVertex12& in)const{
        return {float(in.x),float(in.y),float(in.z),in.u,in.v,palette?palette[in.color]:argb1555(in.color)};
    }
    void clip_vertex(const re4dc::render::StaticCorner& in,const re4dc::room::CompactBatch& batch,
                     re4dc::render::RenderVertex& out){
        float x=mvq[0]*in.x+mvq[1]*in.y+mvq[2]*in.z+mvq[3];
        float y=mvq[4]*in.x+mvq[5]*in.y+mvq[6]*in.z+mvq[7];
        float z=mvq[8]*in.x+mvq[9]*in.y+mvq[10]*in.z+mvq[11];
#if RE4DC_COPY_LEAN
        out.offset_color=0; // every other field is assigned below (no 52-byte memset per corner)
#else
        out={};
#endif
        out.position.world_x=x;out.position.world_y=y;out.position.world_z=z;out.position.depth=-z;
        if(z!=0)project(x,y,z,this);
        out.position.x=x;out.position.y=y;out.position.z=z;
        out.u=u(batch.uv_bias[0]+float(in.u)*batch.uv_scale[0]);
        out.v=v(batch.uv_bias[1]+float(in.v)*batch.uv_scale[1]);
        out.light_red=float((in.argb>>16)&255U)RE4DC_INV255;
        out.light_green=float((in.argb>>8)&255U)RE4DC_INV255;
        out.light_blue=float(in.argb&255U)RE4DC_INV255;
    }
    // 1 emitted/culled, 0 failed before anything was published, -1 failed after.
    template<class Vertex,class Index>
    int strip(const Vertex* base,const re4dc::room::CompactBatch& batch,
              const Index* index,unsigned count){
        input+=count-2;
        if(count<=limit){
            if(count>limit-used && !flush())return submitted?-1:0;
            unsigned outside=15;
            const bool ready=re4dc::render::prepare_direct_strip(dst+used,count,near,far,
                [&](std::uint32_t local,re4dc::render::DirectStripVertex& out){
                    out=re4dc::render::prepare_static_vertex(corner(base[index[local]]),batch,0.0f);
                    out.u=u(out.u);out.v=v(out.v);
                    if(!vertex_alpha)out.argb=(out.argb&0xffffffU)|alpha;
                    outside&=(out.x<0?1U:0U)|(out.x>640.0f?2U:0U)|(out.y<0?4U:0U)|(out.y>480.0f?8U:0U);
                    return true;
                });
            stats.vertices+=count;
            if(ready){
                if(outside)++stats.strips_culled;
#if RE4DC_MESH_DIRECT
                else if(sq){put(count);output+=count-2;++stats.strips;}
#endif
                else {used+=count;output+=count-2;++stats.strips;}
                return 1;
            }
        }
        return clip_strip(base,batch,index,count);
    }
    // Near/far crossing or oversize: the shared clipper, triangle by triangle,
    // keeping strip winding (odd triangles swap their first two corners).
    // input was already counted by the caller.
    template<class Vertex,class Index>
    int clip_strip(const Vertex* base,const re4dc::room::CompactBatch& batch,
                   const Index* index,unsigned count){
        ++stats.strips_clipped;
        float alphas[3]={float(alpha>>24)RE4DC_INV255,float(alpha>>24)RE4DC_INV255,float(alpha>>24)RE4DC_INV255};
        for(unsigned i=2;i<count;++i){
            re4dc::render::RenderVertex tri[3];
            const re4dc::render::StaticCorner corners[3]={corner(base[index[i-2+(i&1)]]),
                corner(base[index[i-1-(i&1)]]),corner(base[index[i]])};
            for(unsigned k=0;k<3;++k){
                clip_vertex(corners[k],batch,tri[k]);
                if(vertex_alpha)alphas[k]=float(corners[k].argb>>24)RE4DC_INV255;
            }
            if(limit-used<6 && !flush())return submitted?-1:0;
            const unsigned emitted=re4dc::render::clip_projected_triangle(tri,dst+used,p.cull,clip,nullptr,alphas);
#if RE4DC_MESH_DIRECT
            if(sq){if(emitted)put(emitted*3);output+=emitted;stats.triangles_clipped+=emitted;continue;}
#endif
            used+=emitted*3;output+=emitted;stats.triangles_clipped+=emitted;
        }
        return 1;
    }
};
struct Draw : Emitter {
    View& view; unsigned material;
    // 1 drawn (possibly nothing visible), 0 fallback allowed, -1 frame aborted.
    int run(const re4dc::room::CompactSourceRange& range){
        const auto& package=view.package;
        if(!re4dc_model_packet_reserve(&p,&packet)){++stats.reserve_rejects;return 0;}
        streaming=re4dc_model_packet_streaming()!=0;
#if RE4DC_HW_LEAN
        set_clip();
#else
        clip={near,far,640,480,project,static_cast<Emitter*>(this)};
#endif
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

#if RE4DC_NATIVE_MESH
// Instanced native meshes (R4IM): one per source BIN in model space, drawn with
// the part's live source modelview. setObj records object -> mesh in its
// owner's table (inside the owner's allocation); the room's common BIN set is
// a seventh view owned with the room.
// The table holds one entry per placement: 4 per packaged BIN (r101: 209
// placements of 81 BINs, r103: 286 of 119), a power of two from 128 to 1024.
constexpr unsigned kMeshViews=kViews+1,kCommonView=kViews,kEntries=128,kEntriesMax=1024;
unsigned entries_for(unsigned meshes){unsigned n=kEntries;while(n<4U*meshes && n<kEntriesMax)n<<=1;return n;}
struct MeshEntry { const void* object; std::uint16_t mesh; std::uint8_t common,used; };
struct MeshView {
    re4dc::room::MeshPackage package;
    unsigned char* storage=nullptr; unsigned bytes=0;
    MeshEntry* entries=nullptr; unsigned capacity=0; // owner views only
    const std::uint32_t* lut=nullptr; // ARGB1555 -> 8888 halves, same allocation
    re4dc::room::CompactVertex12* gather=nullptr; // v3: one meshlet's gathered corners, same allocation
    unsigned room=0; bool attempted=false;
};
MeshView mesh_views[kMeshViews];
#if RE4DC_TREE_IMPOSTOR
// This frame's impostor quads (screen x, y, 1/w per corner: TL, TR, BL, BR),
// sent per atlas by re4dc_static_flush_impostors(). A retired view clears it.
struct ImpostorQuad { const re4dc::room::MeshImpostor* record; std::uint32_t argb; std::uint16_t cell; std::uint8_t fog,pad; float s[4][3]; };
constexpr unsigned kImpostorQuads=48;
ImpostorQuad impostor_queue[kImpostorQuads];
unsigned impostor_count=0,impostor_frame=~0U,impostor_flushed=~0U;
const void* impostor_object=nullptr; bool impostor_queued=false; // the last first-part decision
unsigned impostor_stats[4]; // quads queued, parts skipped, queue full, batches sent
#endif
#if RE4DC_MESH_FASTPATH
constexpr unsigned kLutBytes=512*4;
#else
constexpr unsigned kLutBytes=0;
#endif
// v3: a meshlet has at most 256 corners (R4IM meshlet bound).
constexpr unsigned kGatherBytes=(256U*unsigned(sizeof(re4dc::room::CompactVertex12))+31U)&~31U;

void retire(MeshView& v){
#if RE4DC_TREE_IMPOSTOR
    impostor_frame=~0U; // queued records may point into this view
#endif
    v.package.close();
    if(v.storage){re4dc_static_free(v.storage);stats.package_bytes-=v.bytes;--stats.owners_open;}
    v.storage=nullptr;v.bytes=0;v.entries=nullptr;v.capacity=0;v.lut=nullptr;v.gather=nullptr;v.attempted=false;v.room=0;
}

bool open(MeshView& v,unsigned index,unsigned room){
    if(v.storage && v.room==room)return true;
    if(v.attempted && v.room==room)return false;
    retire(v);v.attempted=true;v.room=room;
    char name[16],path[64];
    if(index==kCommonView)snprintf(name,sizeof(name),"COMMON");
    else owner_name(index,name,sizeof(name));
    snprintf(path,sizeof(path),"/cd/dc/native/r%x%02x/%s.re4mesh",room>>8,room&255U,name);
#if RE4DC_QUALITY_ASSETS
    const unsigned view=unsigned(&v-mesh_views);
    const bool low=std_room.active && std_room.room==room && ((std_room.mesh_views>>view)&1U);
    if(low){snprintf(path,sizeof(path),"/cd/dc/native/r%x%02x/low/%s.re4mesh",room>>8,room&255U,name);++std_stats[3];}
#endif
    const file_t file=fs_open(path,O_RDONLY);
    if(file==FILEHND_INVALID){++stats.open_failures;re4dc_log("native mesh: %s missing\n",path);return false;}
    const unsigned size=unsigned(fs_total(file));
#if RE4DC_QUALITY_ASSETS
    if(low && size!=std_room.mesh_bytes[view]){
        re4dc_log("quality assets: %s is %u B, index says %u: Original package\n",path,size,std_room.mesh_bytes[view]);
        fs_close(file);std_room.mesh_views&=~(1U<<view);v.attempted=false;return open(v,index,room);
    }
#endif
    const unsigned package_bytes=(size+31U)&~31U;
    // Header first: the placement table is sized from its mesh count.
    re4dc::room::MeshHeader head{};
    const bool headed=size>=sizeof(head) && fs_read(file,&head,sizeof(head))==ssize_t(sizeof(head));
    const unsigned capacity=index==kCommonView?0U:entries_for(headed?head.mesh_count:0U);
    const unsigned table=capacity*unsigned(sizeof(MeshEntry));
    // v3 indexed meshlets gather their corners here (kGatherBytes after the LUT): heap 4, not the
    // packet range (with MESH_DIRECT only ~400 slots remain there after the part headers, less than
    // the transform cache plus a gather) and not static storage (the KOS heap has a few KiB).
    const unsigned gather=headed && head.version==3?kGatherBytes:0U;
    stats.heap_before=re4dc_static_heap_free();
    auto* storage=headed?static_cast<unsigned char*>(re4dc_static_alloc(package_bytes+table+kLutBytes+gather)):nullptr;
    const ssize_t rest=ssize_t(size-sizeof(head));
    if(!storage){if(headed)++stats.alloc_rejects;}
    else{
        std::memcpy(storage,&head,sizeof(head));
        if(fs_read(file,storage+sizeof(head),rest)!=rest){re4dc_static_free(storage);storage=nullptr;}
    }
    fs_close(file);
    stats.heap_after=re4dc_static_heap_free();
    if(!storage){re4dc_log("native mesh: %s not loaded (size=%u heap=%d)\n",path,size,stats.heap_before);return false;}
    if(!v.package.adopt(storage,size,RE4DC_MESH_LOD!=0)){
        re4dc_log("native mesh: %s rejected: %s\n",path,v.package.error());
        re4dc_static_free(storage);++stats.open_failures;
#if RE4DC_QUALITY_ASSETS
        // A rejected Standard package: this owner opens its Original package instead.
        if(low){std_room.mesh_views&=~(1U<<view);v.attempted=false;re4dc_log("quality assets: Original package for this owner\n");return open(v,index,room);}
#endif
        return false;
    }
    v.storage=storage;v.bytes=package_bytes+table+kLutBytes+gather;
#if RE4DC_QUALITY_ASSETS
    // Per-mesh records apply only to the package they were built against.
    if(std_room.active && std_room.room==room){
        if(!low || !std_check_view(view,v.package)){
            if(low)re4dc_log("quality assets: %s records do not match the package: records off for this room\n",path);
            if(low){std_room.ncull=std_room.nimp=std_room.nptex=std_room.nimpt=0;}
        }else std_room.checked|=1U<<view;
    }
#endif
    if(gather)v.gather=reinterpret_cast<re4dc::room::CompactVertex12*>(storage+package_bytes+table+kLutBytes);
    if(table){v.entries=reinterpret_cast<MeshEntry*>(storage+package_bytes);v.capacity=capacity;std::memset(v.entries,0,table);}
#if RE4DC_MESH_FASTPATH
    auto* lut=reinterpret_cast<std::uint32_t*>(storage+package_bytes+table);
    re4dc::vp::build_lut(lut);v.lut=lut;
#endif
    ++stats.owners_open;stats.package_bytes+=v.bytes;
    const struct mallinfo kos=mallinfo();
    const auto& h=v.package.header();
    re4dc_log("native mesh: %s bytes=%u version=%u meshes=%u parts=%u meshlets=%u vertices=%u heap4=%d->%d kos_free=%d entries=%u\n",
        path,v.bytes,h.version,h.mesh_count,h.part_count,h.meshlet_count,h.vertex_count,
        stats.heap_before,stats.heap_after,kos.fordblks,v.capacity);
    return true;
}

unsigned entry_slot(const void* object,unsigned capacity){
    return unsigned(reinterpret_cast<std::uintptr_t>(object)>>4)&(capacity-1U);}
const MeshEntry* find_entry(const void* object,unsigned& owner){
    for(unsigned i=0;i<kViews;++i){
        const MeshView& v=mesh_views[i];
        if(!v.entries)continue;
        const unsigned n=v.capacity;
        for(unsigned k=0,s=entry_slot(object,n);k<n;++k,s=(s+1)&(n-1U)){
            const MeshEntry& e=v.entries[s];
            if(!e.used)break;
            if(e.object==object){owner=i;return &e;}
        }
    }
    return nullptr;
}

void bind_mesh(const void* object,unsigned room,int block,unsigned bin,unsigned common){
    const unsigned index=view_index(block);
    if(index>=kViews || !(RE4DC_NATIVE_STATIC_OWNERS&(1U<<index)) ||
       (common && !(RE4DC_NATIVE_STATIC_OWNERS&(1U<<kCommonView)))){++stats.unowned_binds;return;}
    MeshView& owner=mesh_views[index];
    if(!open(owner,index,room))return;
    MeshView& target=common?mesh_views[kCommonView]:owner;
    if(common && !open(target,kCommonView,room))return;
    const unsigned mesh=target.package.find(bin,common!=0);
    if(mesh>=target.package.header().mesh_count){
        ++stats.bind_misses;
        if(stats.bind_misses<=48)re4dc_log("native mesh: bind miss view=%u bin=%u common=%u\n",index,bin,common);
        return;
    }
    const unsigned n=owner.capacity;
    for(unsigned k=0,s=entry_slot(object,n);k<n;++k,s=(s+1)&(n-1U)){
        MeshEntry& e=owner.entries[s];
        if(e.used && e.object!=object)continue;
        e={object,std::uint16_t(mesh),std::uint8_t(common!=0),1};++stats.binds;return;
    }
    ++stats.bind_conflicts;
    re4dc_log("native mesh: view=%u object table full\n",index);
}

// 6+6-bit octahedral code -> unit normal (tools/convert_room_bins.py oct12).
void oct_normal(unsigned code,float n[3]){
    float x=float(code&63U)*(2.0f/63.0f)-1.0f,y=float((code>>6)&63U)*(2.0f/63.0f)-1.0f;
    const float z=1.0f-std::fabs(x)-std::fabs(y);
    if(z<0){
        const float ox=x;
        x=(1.0f-std::fabs(y))*(ox>=0?1.0f:-1.0f);
        y=(1.0f-std::fabs(ox))*(y>=0?1.0f:-1.0f);
    }
    const float inverse=1.0f/std::sqrt(x*x+y*y+z*z);
    n[0]=x*inverse;n[1]=y*inverse;n[2]=z*inverse;
}
std::uint16_t pack1555(const float rgb[3],unsigned alpha){
    const auto c=[](float v){return unsigned((v<0?0.0f:v>1?1.0f:v)*31.0f+0.5f);};
    return std::uint16_t((alpha>=128?0x8000U:0U)|(c(rgb[0])<<10)|(c(rgb[1])<<5)|c(rgb[2]));
}
// Prelights one part once, at its first draw, with the source evaluator and
// this draw's live light state (view-space, like the generic path): the
// stored slot becomes ARGB1555. Instances share the result and camera-
// relative lights stay as first seen - the labelled Dreamcast compromise.
void light_part(MeshView& v,const re4dc::room::MeshRecord& mesh,re4dc::room::MeshPart& part,
                const Re4dcModelPart& p){
    auto* vertices=reinterpret_cast<re4dc::room::CompactVertex12*>(v.storage+v.package.header().vertex_offset);
    const std::uint32_t* palette=v.package.palette();
    re4dc::render::PreparedSourceLights lights;
    if(p.lighting)lights=re4dc::render::prepare_actor_lights(*p.lighting);
    const float* m=p.modelview;
    const auto* lets=v.package.meshlets()+part.first_meshlet;
    // v3 indexed meshlets share their part's pool: light the pool [lo, hi)
    // once (adopt() proved pools disjoint) instead of each meshlet's corners.
    std::uint32_t lo=0,hi=0;
    const bool pool=v.package.shared() && v.package.part_pool(part,lo,hi);
    const unsigned ranges=pool?1U:part.meshlet_count;
    for(unsigned i=0;i<ranges;++i){
        const std::uint32_t first=pool?lo:lets[i].first_vertex,count=pool?hi-lo:lets[i].vertex_count;
        for(unsigned k=0;k<count;++k){
            auto& corner=vertices[first+k];
            const std::uint32_t argb=palette[corner.color>>12];
            const std::uint8_t color[4]={std::uint8_t(argb>>16),std::uint8_t(argb>>8),std::uint8_t(argb),std::uint8_t(argb>>24)};
            float rgb[3]={1.0f,1.0f,1.0f};
            if(p.lighting){
                const float x=mesh.origin[0]+float(corner.x)*mesh.step[0];
                const float y=mesh.origin[1]+float(corner.y)*mesh.step[1];
                const float z=mesh.origin[2]+float(corner.z)*mesh.step[2];
                float n[3];oct_normal(corner.color&0xfffU,n);
                const float* nm=p.lighting->normal_matrix;
                re4dc::render::evaluate_prepared_source_lighting(
                    m[0]*x+m[1]*y+m[2]*z+m[3],m[4]*x+m[5]*y+m[6]*z+m[7],m[8]*x+m[9]*y+m[10]*z+m[11],
                    nm[0]*n[0]+nm[1]*n[1]+nm[2]*n[2],nm[4]*n[0]+nm[5]*n[1]+nm[6]*n[2],nm[8]*n[0]+nm[9]*n[1]+nm[10]*n[2],
                    *p.lighting,lights,color,rgb);
            }
            corner.color=pack1555(rgb,color[3]);
        }
    }
    part.reserved=1;
    ++stats.parts_lit;
}

struct MeshDraw : Emitter {
    const re4dc::room::MeshPackage& package; const re4dc::room::MeshPart& part;
    const std::uint32_t* lut; // mesh view's colour LUT (nullptr: per-corner path)
    re4dc::room::CompactVertex12* gather_pool; // mesh view's v3 gather buffer (nullptr: v1/v2)
    // Cluster/meshlet rejection distance: min(projection far, source View far)
    // with RE4DC_NATIVE_FOG, else the projection far. Vertices still clip
    // against the projection far, so a straddling strip is drawn whole (fully
    // fogged past the View far) instead of going through the clipper.
    float cull_far=0;
    unsigned part_index=0; // v2: index into the package's part LOD table
#if RE4DC_QUALITY_ASSETS
    std::uint64_t skip_clusters=0; // Standard impt: clusters (bit = index in the part) drawn as tree quads
#endif
    float lod_scale=0;     // v2: level error (model units) * lod_scale <= depth
    re4dc::room::CompactBatch batch{};
    // v3: an indexed meshlet's corners are gathered from its part pool into
    // the view's gather buffer (kGatherBytes in the package allocation), so the
    // transform and the clipper still read one contiguous meshlet.
    re4dc::room::CompactVertex12* gathered=nullptr;
    bool borrow_gather(){
        if(gathered || !package.shared())return true;
        gathered=gather_pool;
        return gathered!=nullptr;
    }
    const re4dc::room::CompactVertex12* corners(const re4dc::room::Meshlet& l){
        const auto* base=package.vertices()+l.first_vertex;
        if(!package.indexed(l))return base;
        // Three word moves per corner: R4IM vertices are 4-byte aligned.
        typedef std::uint32_t __attribute__((may_alias)) Word;
        const std::uint16_t* offsets=package.pool_offsets(l);
        const Word* in=reinterpret_cast<const Word*>(base);Word* out=reinterpret_cast<Word*>(gathered);
        for(unsigned k=0;k<l.vertex_count;++k,out+=3){
            const Word* c=in+3U*offsets[k];
            out[0]=c[0];out[1]=c[1];out[2]=c[2];
        }
        return gathered;
    }
#if RE4DC_MESH_FASTPATH
    // Transform-once state: the cache borrows the last kCacheSlots slots of
    // the bound packet range (never sent: strips stop at 'limit').
    pvr_vertex_t* cache=nullptr; std::uint8_t* outcodes=nullptr;
    re4dc::vp::Constants k{};
    bool borrow(){
        if(cache)return true;
        if(!lut || limit<re4dc::vp::kCacheSlots+64U)return false; // small slab: per-corner path
        limit-=re4dc::vp::kCacheSlots;
        cache=dst+limit;outcodes=reinterpret_cast<std::uint8_t*>(cache+re4dc::vp::kCacheEntries);
        re4dc::vp::prime(cache,re4dc::vp::kCacheEntries);
        // After bind(): packet.u_scale/v_scale are the bound texture's.
        k={part.uv_scale[0],part.uv_bias[0],p.uv_offset[0],packet.u_scale,
           part.uv_scale[1],part.uv_bias[1],p.uv_offset[1],packet.v_scale,near,far,
           vertex_alpha?~0U:0x00ffffffU,vertex_alpha?0U:alpha,lut,{}};
        k.finish();
        return true;
    }
    // One visible meshlet: every vertex once through XMTRX, then each strip is
    // accepted (copied from the cache), culled (all corners outside one screen
    // edge) or handed to the unchanged clipper (a corner outside near/far),
    // the same three outcomes, in the same order, as Emitter::strip().
    int meshlet(const re4dc::room::Meshlet& l,const re4dc::room::CompactBatch& batch){
        namespace vp=re4dc::vp;
        const float bmin[3]={float(l.bounds_min[0]),float(l.bounds_min[1]),float(l.bounds_min[2])};
        const float bmax[3]={float(l.bounds_max[0]),float(l.bounds_max[1]),float(l.bounds_max[2])};
        // RE4DC_MESH_CLASSIFY=0 (default) saves ~1.5 KiB of image, i.e. KOS heap,
        // at ~8 cycles per vertex for outcodes in every meshlet.
        const unsigned checks=RE4DC_MESH_CLASSIFY?vp::classify(bmin,bmax,mvq,p.projection,p.viewport,near,far):vp::kChecksAll;
        const auto* base=corners(l);
        const auto* in=reinterpret_cast<const vp::Vertex12*>(base);
        if(checks==vp::kChecksNone)vp::transform<vp::kChecksNone>(in,l.vertex_count,cache,outcodes,k);
        else if(checks==vp::kChecksScreen)vp::transform<vp::kChecksScreen>(in,l.vertex_count,cache,outcodes,k);
        else vp::transform<vp::kChecksAll>(in,l.vertex_count,cache,outcodes,k);
        const unsigned screen=vp::screen_mask(checks),depth=vp::depth_mask(checks);
        const std::uint8_t* s=package.strip_begin(l);
        const std::uint8_t* const end=s+l.strip_bytes;
        while(s<end){
            const unsigned n=*s++;
            input+=n-2;
            vp::StripCodes c{0,0};
            if(screen)c=vp::codes(outcodes,s,n);
            if((c.any&depth) || n>limit){
                if(n<=limit)stats.vertices+=n;
                const int result=clip_strip(base,batch,s,n);
                if(result<=0)return result;
            }else {
                stats.vertices+=n;
                if(c.all&screen)++stats.strips_culled;
#if RE4DC_MESH_DIRECT
                else if(sq){sq=vp::emit_sq(sq,cache,s,n);slots+=n;output+=n-2;++stats.strips;}
#endif
                else {
                    if(n>limit-used && !flush())return submitted?-1:0;
                    vp::emit(dst+used,cache,s,n);
                    used+=n;output+=n-2;++stats.strips;
                }
            }
            s+=n;
        }
        return 1;
    }
#endif
    // One meshlet: 1 drawn or culled, 0 fallback allowed, -1 frame aborted.
    int draw(const re4dc::room::Meshlet& l){
        const re4dc::render::DrawBounds bounds{
            {float(l.bounds_min[0]),float(l.bounds_min[1]),float(l.bounds_min[2])},
            {float(l.bounds_max[0]),float(l.bounds_max[1]),float(l.bounds_max[2])}};
        if(!re4dc::render::group_visible(bounds,mvq,p.projection,p.viewport,near,cull_far,0)){++stats.groups_culled;return 1;}
        ++stats.groups_visible;
        if(!bind()){++stats.bind_rejects;return submitted?-1:0;}
        ++stats.batches;
        if(!borrow_gather()){++stats.reserve_rejects;return submitted?-1:0;}
#if RE4DC_MESH_FASTPATH
        // A slab too small to lend the cache behaves like any other
        // capacity failure: generic fallback, or abort once published.
        if(!borrow()){++stats.reserve_rejects;return submitted?-1:0;}
        return meshlet(l,batch);
#else
        const auto* base=corners(l);
        const std::uint8_t* s=package.strip_begin(l);
        const std::uint8_t* const end=s+l.strip_bytes;
        while(s<end){
            const unsigned n=*s++;
            const int result=strip(base,batch,s,n);
            if(result<=0)return result;
            s+=n;
        }
        return 1;
#endif
    }
#if RE4DC_MESH_LOD
    // v2: cluster test, then the coarsest level within tolerance at the
    // cluster's nearest view depth (group_visible's support radius along z).
    int draw_clusters(){
        const auto& lod=package.part_lods()[part_index];
        const auto* clusters=package.clusters();const auto* levels=package.levels();
        for(unsigned c=lod.first_cluster;c<lod.first_cluster+lod.cluster_count;++c){
#if RE4DC_QUALITY_ASSETS
            if(skip_clusters && c-lod.first_cluster<64U && ((skip_clusters>>(c-lod.first_cluster))&1U))continue;
#endif
            const auto& cl=clusters[c];
            float lo[3],hi[3];
            for(unsigned a=0;a<3;++a){lo[a]=float(cl.bounds_min[a]);hi[a]=float(cl.bounds_max[a]);}
            const re4dc::render::DrawBounds bounds{{lo[0],lo[1],lo[2]},{hi[0],hi[1],hi[2]}};
            if(!re4dc::render::group_visible(bounds,mvq,p.projection,p.viewport,near,cull_far,0)){++stats.clusters_culled;continue;}
            ++stats.clusters_visible;
            float depth=-mvq[11],radius=0;
            for(unsigned a=0;a<3;++a){
                depth-=mvq[8+a]*(lo[a]+hi[a])*0.5f;
                radius+=std::fabs(mvq[8+a])*(hi[a]-lo[a])*0.5f;
            }
            depth-=radius;
            if(depth<near)depth=near;
            unsigned level=cl.level_count-1;
            while(level && levels[cl.first_level+level].error*lod_scale>depth)--level;
            ++stats.lod_draws[level<3?level:3];
            const auto& lv=levels[cl.first_level+level];
            const auto* lets=package.meshlets()+lv.first_meshlet;
            for(unsigned i=0;i<lv.meshlet_count;++i){
                const int result=draw(lets[i]);
                if(result<=0)return result;
            }
        }
        return 1;
    }
#endif
    int run(){
        if(!re4dc_model_packet_reserve(&p,&packet)){++stats.reserve_rejects;return 0;}
        streaming=re4dc_model_packet_streaming()!=0;
#if RE4DC_HW_LEAN
        set_clip();
#else
        clip={near,far,640,480,project,static_cast<Emitter*>(this)};
#endif
        palette=nullptr; // lit ARGB1555 corners (light_part)
        batch.uv_bias[0]=part.uv_bias[0];batch.uv_bias[1]=part.uv_bias[1];
        batch.uv_scale[0]=part.uv_scale[0];batch.uv_scale[1]=part.uv_scale[1];
#if RE4DC_MESH_LOD
        if(package.lod()){
            const int result=draw_clusters();
            if(result<=0)return result;
        }else
#endif
        {
            const auto* lets=package.meshlets()+part.first_meshlet;
            for(unsigned i=0;i<part.meshlet_count;++i){
                const int result=draw(lets[i]);
                if(result<=0)return result;
            }
        }
        if(used)re4dc_model_packet_commit(used);
        re4dc_model_result(0,input,output);
        return 1;
    }
};
#endif
} // namespace

extern "C" void re4dc_static_bind(const void* object,unsigned room,int block,unsigned work,
                                  unsigned bin,unsigned common,unsigned serial,const float world[12]){
#if RE4DC_NATIVE_MESH
    (void)work;(void)serial;(void)world;
    bind_mesh(object,room,block,bin,common);
#elif RE4DC_NATIVE_STATIC
    const unsigned index=view_index(block);
    if(index>=kViews || !(RE4DC_NATIVE_STATIC_OWNERS&(1U<<index))){
        ++stats.unowned_binds;
        if(stats.unowned_binds<=48)re4dc_log("native static: unowned bind block=%d work=%u bin=%u common=%u object=%p\n",block,work,bin,common,object);
        return;
    }
    View& v=views[index];
    if(!open(v,index,room))return;
    re4dc::room::CompactSourceRange range;
    if(!v.package.resolve_source(block<0?0xffU:std::uint8_t(block),std::uint16_t(work),
                                 std::uint16_t(bin),common!=0,range)){
        ++stats.bind_misses;
        if(stats.bind_misses<=48)re4dc_log("native static: bind miss view=%u work=%u bin=%u common=%u object=%p\n",index,work,bin,common,object);
        return;
    }
    Binding& b=v.bindings[range.source];
    if(b.object && (b.object!=object || b.serial!=serial)){
        ++stats.bind_conflicts;
        if(stats.bind_conflicts<=48)re4dc_log("native static: bind conflict view=%u source=%u work=%u bin=%u common=%u object=%p previous=%p\n",
            index,range.source,work,bin,common,object,b.object);
    }
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
#if RE4DC_NATIVE_MESH
    if(index<kViews && mesh_views[index].attempted)retire(mesh_views[index]);
#endif
}
extern "C" void re4dc_static_retire_all(){
    for(auto& v:views)if(v.attempted)retire(v);
#if RE4DC_NATIVE_MESH
    for(auto& v:mesh_views)if(v.attempted)retire(v);
#endif
}
extern "C" const Re4dcStaticStats* re4dc_static_stats(){return &stats;}
#if RE4DC_QUALITY_ASSETS
// ui_bridge.cpp re4dc_room_enter(): after the quality freeze, before any package
// of the room opens. Original never reads the index (nor low/ or texlow/).
extern "C" void re4dc_std_room_enter(unsigned room){
    StdRoom& r=std_room;
    r.room=room;r.active=false;r.mesh_views=0;r.checked=0;r.ntex=r.ndrop=r.ncull=r.nimp=r.nptex=r.nimpt=0;
    if(!re4dc_quality_std_assets())return;
    char path[64];snprintf(path,sizeof(path),"/cd/dc/native/r%x%02x/low/index.txt",room>>8,room&255U);
    char* text=static_cast<char*>(std::malloc(kStdText));
    const int n=text?re4dc_fixture_read(path,text,kStdText):-1;
    if(n<=0){re4dc_log("quality assets: %s missing: Original packages\n",path);std::free(text);return;}
    if(n>=int(kStdText)){re4dc_log("quality assets: %s larger than %u B: Original packages\n",path,kStdText);std::free(text);return;}
    text[n]=0;
    r.active=std_parse(text,room);
    std::free(text);
    if(!r.active){r.mesh_views=0;r.ntex=r.ndrop=r.ncull=r.nimp=r.nptex=r.nimpt=0;re4dc_log("quality assets: %s rejected: Original packages\n",path);return;}
    re4dc_log("quality assets: %s mesh=%02x tex=%u drop=%u cull=%u imp=%u impt=%u ptex=%u\n",path,r.mesh_views,r.ntex,r.ndrop,r.ncull,r.nimp,r.nimpt,r.nptex);
}
// native_ui.cpp: texture keys Standard adds (texlow/), and the room keys it drops.
extern "C" int re4dc_std_texlow(unsigned crc,unsigned fnv){
    const StdRoom& r=std_room;if(!r.active)return 0;
    for(unsigned i=0;i<r.ntex;++i)if(r.tex[i].crc==crc && r.tex[i].fnv==fnv)return 1;
    return 0;
}
extern "C" int re4dc_std_dropped(unsigned crc,unsigned fnv){
    const StdRoom& r=std_room;if(!r.active)return 0;
    for(unsigned i=0;i<r.ndrop;++i)if(r.drop[i].crc==crc && r.drop[i].fnv==fnv)return 1;
    return 0;
}
// i-th added texture: key, size and VRAM bytes; 0 past the end.
extern "C" int re4dc_std_texture(unsigned i,unsigned out[5]){
    const StdRoom& r=std_room;if(!r.active || i>=r.ntex)return 0;
    const StdTex& t=r.tex[i];out[0]=t.crc;out[1]=t.fnv;out[2]=t.width;out[3]=t.height;out[4]=t.vram;return 1;
}
#endif
#if RE4DC_TREE_IMPOSTOR
// native_ui re4dc_model_finish_source_draws(): after the OP pass, before the
// translucent drain. One PT packet per (atlas, fog) with each quad as a
// 4-corner strip; a later impostor candidate this frame draws geometry.
extern "C" void re4dc_static_flush_impostors(){
    const unsigned frame=re4dc_ui_frame();
    if(impostor_flushed==frame)return;
    impostor_flushed=frame;
    if(impostor_frame!=frame)return;
    for(unsigned i=0;i<impostor_count;++i){
        const auto* first=impostor_queue[i].record;
        if(!first)continue;
        const unsigned fog=impostor_queue[i].fog;
        Re4dcModelPacket packet{};
        const bool bound=re4dc_model_pt_begin(first->key_crc,first->key_fnv,first->atlas_w,first->atlas_h,int(fog),&packet)!=0;
        auto* out=static_cast<pvr_vertex_t*>(packet.vertices);unsigned used=0;
        for(unsigned j=i;j<impostor_count;++j){
            ImpostorQuad& q=impostor_queue[j];
            const auto* r=q.record;
            if(!r || r->key_crc!=first->key_crc || r->key_fnv!=first->key_fnv || q.fog!=fog)continue;
            q.record=nullptr;
            if(!bound || used+4>packet.capacity)continue;
            const unsigned col=q.cell%r->cols,row=q.cell/r->cols;
            const float iw=1.0f/float(r->atlas_w),ih=1.0f/float(r->atlas_h); // half-texel inset: no neighbour bleed
            const float u0=(float(col*r->cell_w)+0.5f)*iw,u1=(float((col+1)*r->cell_w)-0.5f)*iw;
            const float v0=(float(row*r->cell_h)+0.5f)*ih,v1=(float((row+1)*r->cell_h)-0.5f)*ih;
            for(unsigned k=0;k<4;++k){
                pvr_vertex_t& o=out[used+k];
                o.flags=k==3?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX;
                o.x=q.s[k][0];o.y=q.s[k][1];o.z=q.s[k][2];
                o.u=(k&1)?u1:u0;o.v=(k&2)?v1:v0;o.argb=q.argb;o.oargb=0;
            }
            used+=4;
        }
        if(bound){re4dc_model_packet_commit(used);++impostor_stats[3];}
    }
    impostor_count=0;
}
#endif
#if RE4DC_FRONT_LEAN
// 1 when 'object' is bound to a native mesh whose source identity matches
// (vertices, display lists) and every part of it is already lit (light_part
// ran): the mesh then never reads source lighting again (trans.cpp).
extern "C" int re4dc_static_mesh_lit(const void* object,unsigned vertices,unsigned parts){
#if RE4DC_NATIVE_MESH
    if(!stats.owners_open)return 0;
    unsigned owner=0;
    const MeshEntry* e=find_entry(object,owner);
    if(!e)return 0;
    const MeshView& v=e->common?mesh_views[kCommonView]:mesh_views[owner];
    if(!v.package.valid() || e->mesh>=v.package.header().mesh_count)return 0;
    const auto& mesh=v.package.meshes()[e->mesh];
    if(!v.package.source_identity(e->mesh,vertices,parts) || !mesh.part_count)return 0;
    const auto* list=v.package.parts()+mesh.first_part;
    for(unsigned i=0;i<mesh.part_count;++i)if(!list[i].reserved)return 0;
    return 1;
#else
    (void)object;(void)vertices;(void)parts;return 0;
#endif
}
#endif

#ifndef RE4DC_SCENERY_GATE
#define RE4DC_SCENERY_GATE 0 // obj/scenery30.h (D367 scenery30 S1a)
#endif
#if RE4DC_SCENERY_GATE
namespace { unsigned gate_tests,gate_culled,gate_frame_log=~0U; }
extern "C" float re4dc_fog_far_for_gate(float zfar);
// S1a: 1 when the whole native mesh bound to 'object' lies beyond the depth at which
// mesh_submit's MeshDraw rejects every cluster (cull_far: the projection far, or the fogged
// source View far when fog is on). The mesh's grid box (origin .. origin + 65535 step) contains
// every cluster box, so each cluster would have failed the same depth test: the caller may
// skip the model's render setup with identical pixels.
extern "C" int re4dc_static_gate(const void* object,const float mv[12],const float projection[7],float zfar){
#if RE4DC_NATIVE_MESH
    if(!stats.owners_open)return 0;
    unsigned owner=0;
    const MeshEntry* e=find_entry(object,owner);
    if(!e)return 0;
    const MeshView& v=e->common?mesh_views[kCommonView]:mesh_views[owner];
    if(!v.package.valid() || e->mesh>=v.package.header().mesh_count)return 0;
    if(projection[0]!=0)return 0;
    const float near=projection[6]/(projection[5]-1),far=projection[6]/projection[5];
    if(!re4dc::render::is_finite(near)||!re4dc::render::is_finite(far)||near<=0||far<=near)return 0;
    float cull_far=far;
#if RE4DC_NATIVE_FOG
    if(re4dc_fog_enabled()){const float view_far=re4dc_fog_far_for_gate(zfar);if(view_far>near && view_far<far)cull_far=view_far;}
#else
    (void)zfar;
#endif
    const auto& mesh=v.package.meshes()[e->mesh];
    float vz=mv[11],rz=0;
    for(unsigned a=0;a<3;++a){
        const float extent=mesh.step[a]*(65535.0f*0.5f),center=mesh.origin[a]+extent;
        vz+=mv[8+a]*center;rz+=std::fabs(mv[8+a])*extent;
    }
    ++gate_tests;
    const unsigned frame=re4dc_ui_frame();
    if(frame%600==0 && frame!=gate_frame_log){gate_frame_log=frame;re4dc_log("native scenery gate: frame=%u tests=%u culled=%u\n",frame,gate_tests,gate_culled);}
    if(-vz-rz>cull_far){++gate_culled;return 1;}
    return 0;
#else
    (void)object;(void)mv;(void)projection;(void)zfar;return 0;
#endif
}
#endif
#if RE4DC_NATIVE_FOG
namespace {
// Last GXSetFog state (gx_stub.cpp) and the source View far plane seen by the
// model bridge. Temporary type-0 calls (effects, filters, thermal/black) reach
// parts as fog off through Re4dcModelPart::source_key[2]; the table keeps the last
// fogged state and is rewritten only when that state changes.
struct FogState { int type; float start,end,far; unsigned rgba; };
FogState fog_now{0,0,0,0,0},fog_loaded{-1,0,0,0,0};
constexpr float kFogRamp=0.8f; // ramp to 100% over the last 20% before the far plane
// 2^x for x in [-8, 0] without libm (powf alone is ~2 KB of image): halve
// per whole step, then e^y on y=frac*ln2 in (-0.7, 0] (Taylor, error < 2e-4,
// far below the table's 8-bit alpha).
float fog_exp2(float x){
    float r=1.0f;
    while(x<=-1.0f){r*=0.5f;x+=1.0f;}
    const float y=x*0.69314718f;
    return r*(1.0f+y*(1.0f+y*(0.5f+y*(1.0f/6.0f+y*(1.0f/24.0f+y*(1.0f/120.0f))))));
}
// GX fog amount at eye depth z (GXSetFog: perspective and orthographic
// variants share the curve on t=(z-start)/(end-start)).
float gx_fog(int type,float start,float end,float z){
    if(!(end>start))return z>=end?1.0f:0.0f;
    float t=(z-start)/(end-start);
    t=t<0?0.0f:t>1?1.0f:t;
    switch(type&7){
    case 4: return 1.0f-fog_exp2(-8.0f*t);
    case 5: return 1.0f-fog_exp2(-8.0f*t*t);
    case 6: return fog_exp2(-8.0f*(1.0f-t));
    case 7: return fog_exp2(-8.0f*(1.0f-t)*(1.0f-t));
    default: return t;
    }
}
}
extern "C" void re4dc_fog_capture(int type,float start,float end,unsigned rgba){
    fog_now.type=type;fog_now.start=start;fog_now.end=end;fog_now.rgba=rgba;
}
extern "C" unsigned re4dc_fog_enabled(){return fog_now.type!=0;}
#if RE4DC_SCENERY_GATE
extern "C" float re4dc_fog_far_for_gate(float far){ // re4dc_fog_note_far's clamp, without noting
#if RE4DC_FOG_FAR > 0
    if(!(far<=float(RE4DC_FOG_FAR)))far=float(RE4DC_FOG_FAR);
#endif
    return far;
}
#endif
extern "C" void re4dc_fog_note_far(float far){
#if RE4DC_FOG_FAR > 0
    if(!(far<=float(RE4DC_FOG_FAR)))far=float(RE4DC_FOG_FAR);
#endif
    fog_now.far=far;
}
#if RE4DC_FOG_TA_DOUBLEBUF
// With a double-buffered TA the previous scene may still render at frame start and reads the fog
// registers: native_ui fences only when this frame changes them.
extern "C" int re4dc_fog_frame_pending(){
    return fog_now.type && !(fog_now.type==fog_loaded.type && fog_now.start==fog_loaded.start &&
        fog_now.end==fog_loaded.end && fog_now.far==fog_loaded.far && fog_now.rgba==fog_loaded.rgba);
}
#endif
// Frame start (native_ui re4dc_ui_begin, after the previous render's fence):
// PVR table fog indexes scaled 1/w, entry j <-> depth far/v(j) with
// v(j)=2^(j>>4)*((j&15)+16)/16 (KOS pvr_fog.c), entry 0 at the far plane.
extern "C" void re4dc_fog_frame(){
    if(!fog_now.type)return;
    if(fog_now.type==fog_loaded.type && fog_now.start==fog_loaded.start && fog_now.end==fog_loaded.end &&
       fog_now.far==fog_loaded.far && fog_now.rgba==fog_loaded.rgba)return;
    fog_loaded=fog_now;
    const float far=fog_now.far>1.0f?fog_now.far:(fog_now.end>1.0f?fog_now.end:1.0f);
    const float r=float((fog_now.rgba>>24)&255U)/255.0f,g=float((fog_now.rgba>>16)&255U)/255.0f,
                b=float((fog_now.rgba>>8)&255U)/255.0f;
    float table[129];
    for(unsigned j=0;j<129;++j){
        const float v=j<128?float((j&15U)+16U)/16.0f*float(1U<<(j>>4)):256.0f;
        const float z=far/v;
        float f=gx_fog(fog_now.type,fog_now.start,fog_now.end,z);
        const float ramp=(z-kFogRamp*far)/((1.0f-kFogRamp)*far);
        if(ramp>0){const float s=ramp>=1?1.0f:ramp*ramp*(3.0f-2.0f*ramp);f+=(1.0f-f)*s;}
        table[j]=f;
    }
    pvr_fog_table_color(1.0f,r,g,b);
    pvr_fog_far_depth(far);
    pvr_fog_table_custom(table);
#if RE4DC_FOG_BACKGROUND
    pvr_set_bg_color(r,g,b);
#endif
    re4dc_log("native fog: type=%d start=%d end=%d far=%d colour=%08x near=%u%% mid=%u%%\n",fog_now.type,
        int(fog_now.start),int(fog_now.end),int(far),fog_now.rgba,unsigned(table[128]*100.0f),unsigned(table[64]*100.0f));
}
#endif

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
void log_stats(unsigned frame){
    if(frame!=last_log_frame && frame%600==0){
        last_log_frame=frame;
        re4dc_log("native static: frame=%u native=%u skipped=%u fallback=%u key_misses=%u groups=%u/%u strips=%u culled=%u clipped=%u moved=%u stale=%u vertex_alpha=%u opaque=%u alpha_unused=%u alpha_min=%u reserve=%u bind=%u aborts=%u\n",
            frame,stats.parts_native,stats.parts_skipped,stats.parts_fallback,stats.key_misses,stats.groups_visible,
            stats.groups_visible+stats.groups_culled,stats.strips,stats.strips_culled,stats.strips_clipped,stats.moved_objects,stats.stale_bindings,
            stats.vertex_alpha,stats.vertex_opaque,stats.vertex_alpha_unused,stats.vertex_alpha_min,stats.reserve_rejects,stats.bind_rejects,stats.aborts);
        re4dc_log("native static: frame=%u vertices=%u batches=%u binds=%u misses=%u conflicts=%u unowned=%u unbound=%u lit=%u\n",
            frame,stats.vertices,stats.batches,stats.binds,stats.bind_misses,stats.bind_conflicts,stats.unowned_binds,
            stats.locate_misses,stats.parts_lit);
#if RE4DC_MESH_LOD || RE4DC_NATIVE_FOG
        re4dc_log("native static: frame=%u clusters=%u/%u lod=%u/%u/%u/%u px=%u\n",frame,stats.clusters_visible,
            stats.clusters_visible+stats.clusters_culled,stats.lod_draws[0],stats.lod_draws[1],stats.lod_draws[2],
            stats.lod_draws[3],unsigned(RE4DC_MESH_LOD_PX));
#endif
#if RE4DC_TREE_IMPOSTOR
        re4dc_log("native static: frame=%u impostors=%u parts_skipped=%u queue_full=%u batches=%u switch_mm=%u\n",frame,
            impostor_stats[0],impostor_stats[1],impostor_stats[2],impostor_stats[3],unsigned(RE4DC_TREE_IMPOSTOR_MM));
#if RE4DC_QUALITY_ASSETS
        if(std_room.active)re4dc_log("quality assets: frame=%u culled=%u imp=%u baked=%u low_opens=%u tree_quads=%u tree_geom=%u checked=%02x\n",frame,
            std_stats[0],std_stats[1],std_stats[2],std_stats[3],std_stats[4],std_stats[5],std_room.checked);
#endif
#endif
    }
}
#if RE4DC_NATIVE_MESH
// Source ModelData identity words read from the live BIN (cModelInfo::pData at
// 0x0C; nVtx 0x38, displist_num 0x1A and the relocated pParts 0x1C after the
// load-time byte-order mirror).
#if RE4DC_COPY_LEAN
// Same words as below as aligned loads (cModelInfo/ModelData are 4-aligned);
// a 2/4-byte memcpy through char* is a libcall on SH-4.
typedef const unsigned char* __attribute__((may_alias)) AliasPtr;
typedef std::uint16_t __attribute__((may_alias)) AliasHalf;
const unsigned char* model_data(const Re4dcModelPart& p){
    return *reinterpret_cast<const AliasPtr*>(static_cast<const unsigned char*>(p.info)+0x0C);
}
const unsigned char* first_part(const unsigned char* data){
    return *reinterpret_cast<const AliasPtr*>(data+0x1C);
}
#else
const unsigned char* model_data(const Re4dcModelPart& p){
    const unsigned char* data;
    std::memcpy(&data,static_cast<const unsigned char*>(p.info)+0x0C,sizeof(data));
    return data;
}
const unsigned char* first_part(const unsigned char* data){
    const unsigned char* parts;
    std::memcpy(&parts,data+0x1C,sizeof(parts));
    return parts;
}
#endif
#if RE4DC_TREE_IMPOSTOR
// atan2(y, x) in turns, [0, 1): octant reduction and a 7th-order minimax
// arctangent (error < 1e-5 rad); libm's atan2 would grow this -Os unit.
float turns(float y,float x){
    const float ax=std::fabs(x),ay=std::fabs(y),lo=ax<ay?ax:ay,hi=ax<ay?ay:ax;
    if(!(hi>0.0f))return 0.0f;
    const float a=lo/hi,s=a*a;
    float r=((-0.0464964749f*s+0.15931422f)*s-0.327622764f)*s*a+a;
    if(ay>ax)r=1.57079633f-r;
    if(x<0.0f)r=3.14159265f-r;
    r*=0.159154943f;
    return y<0.0f?1.0f-r:r;
}
// Area-weighted mean lit colour of the mesh's full-detail surface (level 0 of
// every cluster of every lit part; ARGB8888), cached in the record once every
// part is lit. The quad modulates the atlas's unlit albedo by it, as the
// geometry modulates the same texture by its per-vertex lighting.
std::uint32_t impostor_color(const MeshView& v,const re4dc::room::MeshRecord& mesh,re4dc::room::MeshImpostor& r){
    if(r.reserved)return r.reserved;
    float sum[3]={0,0,0},total=0;bool all=true;
    const auto& pk=v.package;
    for(unsigned i=mesh.first_part;i<mesh.first_part+mesh.part_count;++i){
        if(!pk.parts()[i].reserved){all=false;continue;}
        const auto& lod=pk.part_lods()[i];
        for(unsigned c=lod.first_cluster;c<lod.first_cluster+lod.cluster_count;++c){
            const auto& lv=pk.levels()[pk.clusters()[c].first_level];
            for(unsigned l=lv.first_meshlet;l<lv.first_meshlet+lv.meshlet_count;++l){
                const auto& let=pk.meshlets()[l];
                const auto* base=pk.vertices()+let.first_vertex;
                const std::uint8_t* s=pk.strips()+let.first_strip;const std::uint8_t* end=s+let.strip_bytes;
                while(s<end){
                    const unsigned n=*s++;
                    for(unsigned k=2;k<n;++k){
                        const auto &a=base[s[k-2]],&b=base[s[k-1]],&d=base[s[k]];
                        float e[2][3];
                        for(unsigned x=0;x<3;++x){
                            const float o=float((&a.x)[x]);
                            e[0][x]=(float((&b.x)[x])-o)*mesh.step[x];e[1][x]=(float((&d.x)[x])-o)*mesh.step[x];
                        }
                        const float cx=e[0][1]*e[1][2]-e[0][2]*e[1][1],cy=e[0][2]*e[1][0]-e[0][0]*e[1][2],
                                    cz=e[0][0]*e[1][1]-e[0][1]*e[1][0],area=std::sqrt(cx*cx+cy*cy+cz*cz);
                        const re4dc::room::CompactVertex12* corners[3]={&a,&b,&d};
                        for(const auto* q:corners){
                            const unsigned col=q->color;
                            sum[0]+=area*float((col>>10)&31U);sum[1]+=area*float((col>>5)&31U);sum[2]+=area*float(col&31U);
                        }
                        total+=3.0f*area;
                    }
                    s+=n;
                }
            }
        }
    }
    std::uint32_t argb=0xffffffffU;
    if(total>0){argb=0xff000000U;for(unsigned a=0;a<3;++a)argb|=unsigned(sum[a]*(255.0f/31.0f)/total+0.5f)<<(16-8*a);}
    if(all && total>0)r.reserved=argb;
    return argb;
}
// 0: draw the geometry; 1: the mesh is its impostor's (queued, or hidden
// beyond the fog/far plane or the screen). The mesh's first part decides for
// the whole object; its other parts follow that decision.
int mesh_impostor(MeshView& v,unsigned mesh_index,const re4dc::room::MeshPart& part,const Re4dcModelPart& p,
                  float near,float far){
#if RE4DC_QUALITY_ASSETS
    // Standard: the index's imp records replace the package's (s16.3), with their own switch depth.
    re4dc::room::MeshImpostor* r=nullptr;float switch_mm=float(RE4DC_TREE_IMPOSTOR_MM);
    if(std_room.active){
        const unsigned view=unsigned(&v-mesh_views);
        if((std_room.checked>>view)&1U)
            for(unsigned i=0;i<std_room.nimp;++i)if(std_room.imp[i].view==view && std_room.imp[i].rec.mesh==mesh_index){
                r=&std_room.imp[i].rec;switch_mm=std_room.imp[i].mm;break;}
    }else r=const_cast<re4dc::room::MeshImpostor*>(v.package.impostor(mesh_index));
#else
    auto* r=const_cast<re4dc::room::MeshImpostor*>(v.package.impostor(mesh_index));
#endif
    if(!r)return 0;
    const unsigned frame=re4dc_ui_frame();
    const auto& mesh=v.package.meshes()[mesh_index];
    if(&part!=v.package.parts()+mesh.first_part){
        if(impostor_frame!=frame || p.model!=impostor_object || !impostor_queued)return 0;
        ++impostor_stats[1];return 1;
    }
    if(impostor_frame!=frame){impostor_frame=frame;impostor_count=0;}
    impostor_object=p.model;impostor_queued=false;
    if(impostor_flushed==frame)return 0; // after this frame's PT batches: geometry
    const float* m=p.modelview;const float* C=r->centre;
    float c[3];
    for(unsigned i=0;i<3;++i)c[i]=m[4*i]*C[0]+m[4*i+1]*C[1]+m[4*i+2]*C[2]+m[4*i+3];
#if RE4DC_QUALITY_ASSETS
    if(!(-c[2]>=switch_mm))return 0;
    if(std_room.active)++std_stats[1];
#else
    if(!(-c[2]>=float(RE4DC_TREE_IMPOSTOR_MM)))return 0;
#endif
    const float scale=std::sqrt(m[0]*m[0]+m[1]*m[1]+m[2]*m[2]);
    if(-c[2]-(r->half_w>r->half_h?r->half_w:r->half_h)*scale>far){impostor_queued=true;return 1;} // as its clusters
    if(impostor_count>=kImpostorQuads){++impostor_stats[2];return 0;}
    // Camera direction in model space (A^T of a rotation-and-uniform-scale
    // modelview, unnormalised), its azimuth's cell, and the facing quad.
    const float dx=-(m[0]*c[0]+m[4]*c[1]+m[8]*c[2]),dz=-(m[2]*c[0]+m[6]*c[1]+m[10]*c[2]);
    const float length=std::sqrt(dx*dx+dz*dz),bx=length>0?dx/length:1.0f,bz=length>0?dz/length:0.0f;
    unsigned cell=unsigned(turns(-dz,dx)*float(r->views)+0.5f);
    if(cell>=r->views)cell-=r->views;
    ImpostorQuad& q=impostor_queue[impostor_count];
    const float* P=p.projection;const float* V=p.viewport;
    unsigned left=0,right=0,top=0,bottom=0;
    for(unsigned k=0;k<4;++k){
        const float sx=(k&1)?r->half_w:-r->half_w,sy=(k&2)?-r->half_h:r->half_h;
        const float x=C[0]+sx*bz,y=C[1]+sy,z=C[2]-sx*bx;
        const float vx=m[0]*x+m[1]*y+m[2]*z+m[3],vy=m[4]*x+m[5]*y+m[6]*z+m[7],vz=m[8]*x+m[9]*y+m[10]*z+m[11];
        if(!(-vz>near))return 0;
        const float inv=1.0f/(-vz);
        float* s=q.s[k];
        s[0]=(V[2]*.5f*(P[1]*vx+P[2]*vz)*inv+V[0]+V[2]*.5f)*640.f/V[2];
        s[1]=(-V[3]*.5f*(P[3]*vy+P[4]*vz)*inv+V[1]+V[3]*.5f)*480.f/V[3];
        s[2]=inv;
        left+=s[0]<0;right+=s[0]>640.0f;top+=s[1]<0;bottom+=s[1]>480.0f;
    }
    impostor_queued=true;
    if(left==4 || right==4 || top==4 || bottom==4)return 1;
    q.record=r;q.cell=std::uint16_t(cell);q.fog=p.source_key[2]?1:0;q.argb=impostor_color(v,mesh,*r);
    ++impostor_count;++impostor_stats[0];
    return 1;
}
#endif
#if RE4DC_QUALITY_ASSETS
// s16.5: one tree of a split grove. 1: the tree is its quad (queued, or hidden
// beyond the far plane / off screen): skip its clusters. 0: draw its clusters.
int tree_quad(MeshView& v,const re4dc::room::MeshRecord& mesh,StdImpt& t,const Re4dcModelPart& p,float near,float far){
    const unsigned frame=re4dc_ui_frame();
    if(impostor_frame!=frame){impostor_frame=frame;impostor_count=0;}
    if(impostor_flushed==frame)return 0; // after this frame's PT batches: geometry
    re4dc::room::MeshImpostor* r=&t.rec;
    const float* m=p.modelview;const float* C=r->centre;
    float c[3];
    for(unsigned i=0;i<3;++i)c[i]=m[4*i]*C[0]+m[4*i+1]*C[1]+m[4*i+2]*C[2]+m[4*i+3];
    if(!(-c[2]>=t.mm))return 0;
    const float scale=std::sqrt(m[0]*m[0]+m[1]*m[1]+m[2]*m[2]);
    if(-c[2]-(r->half_w>r->half_h?r->half_w:r->half_h)*scale>far)return 1;
    if(impostor_count>=kImpostorQuads){++impostor_stats[2];return 0;}
    const float dx=-(m[0]*c[0]+m[4]*c[1]+m[8]*c[2]),dz=-(m[2]*c[0]+m[6]*c[1]+m[10]*c[2]);
    const float length=std::sqrt(dx*dx+dz*dz),bx=length>0?dx/length:1.0f,bz=length>0?dz/length:0.0f;
    unsigned cell=unsigned(turns(-dz,dx)*float(r->views)+0.5f);
    if(cell>=r->views)cell-=r->views;
    ImpostorQuad& q=impostor_queue[impostor_count];
    const float* P=p.projection;const float* V=p.viewport;
    unsigned left=0,right=0,top=0,bottom=0;
    for(unsigned k=0;k<4;++k){
        const float sx=(k&1)?r->half_w:-r->half_w,sy=(k&2)?-r->half_h:r->half_h;
        const float x=C[0]+sx*bz,y=C[1]+sy,z=C[2]-sx*bx;
        const float vx=m[0]*x+m[1]*y+m[2]*z+m[3],vy=m[4]*x+m[5]*y+m[6]*z+m[7],vz=m[8]*x+m[9]*y+m[10]*z+m[11];
        if(!(-vz>near))return 0;
        const float inv=1.0f/(-vz);
        float* s=q.s[k];
        s[0]=(V[2]*.5f*(P[1]*vx+P[2]*vz)*inv+V[0]+V[2]*.5f)*640.f/V[2];
        s[1]=(-V[3]*.5f*(P[3]*vy+P[4]*vz)*inv+V[1]+V[3]*.5f)*480.f/V[3];
        s[2]=inv;
        left+=s[0]<0;right+=s[0]>640.0f;top+=s[1]<0;bottom+=s[1]>480.0f;
    }
    if(left==4 || right==4 || top==4 || bottom==4)return 1;
    q.record=r;q.cell=std::uint16_t(cell);q.fog=p.source_key[2]?1:0;q.argb=impostor_color(v,mesh,*r);
    ++impostor_count;++impostor_stats[0];++std_stats[4];
    return 1;
}
#endif
int mesh_submit(const Re4dcModelPart& p){
    if(!p.static_geometry || !p.info || !p.part || !stats.owners_open)return 0;
    unsigned owner=0;
    const MeshEntry* e=find_entry(p.model,owner);
    if(!e){
        ++stats.locate_misses;
        if(stats.locate_misses<=32)re4dc_log("native mesh: unbound part model=%p\n",p.model);
        return 0;
    }
    MeshView& v=e->common?mesh_views[kCommonView]:mesh_views[owner];
    if(!v.package.valid() || e->mesh>=v.package.header().mesh_count){++stats.stale_bindings;return 0;}
    const auto& mesh=v.package.meshes()[e->mesh];
    const unsigned char* data=model_data(p);
    std::uint16_t vertices=0,parts=0;
#if RE4DC_COPY_LEAN
    if(data){vertices=*reinterpret_cast<const AliasHalf*>(data+0x38);parts=*reinterpret_cast<const AliasHalf*>(data+0x1A);}
#else
    if(data){std::memcpy(&vertices,data+0x38,2);std::memcpy(&parts,data+0x1A,2);}
#endif
    const std::uintptr_t offset=data?reinterpret_cast<std::uintptr_t>(p.part)-reinterpret_cast<std::uintptr_t>(first_part(data)):~std::uintptr_t(0);
    // Source layout, or a room archive that released this BIN's GX payload
    // (instanced_mesh.hpp source_part; such a part has no GX fallback).
    const auto* part=(data && offset<0x100000U)?
        v.package.source_part(e->mesh,vertices,parts,std::uint32_t(offset),p.stream_bytes):nullptr;
    if(!part){
        ++stats.key_misses;
        if(stats.key_misses<=32)re4dc_log("native mesh: part mismatch bin=%u common=%u vertices=%u/%u parts=%u/%u offset=%u size=%u\n",
            mesh.bin,mesh.common,vertices,mesh.source_vertices,parts,mesh.source_parts,unsigned(offset),p.stream_bytes);
        return 0;
    }
    // Before any deferral: p.lighting points at the bridge's stack copy.
    // The package lives in this view's writable heap-4 allocation.
    if(!part->reserved){
#if RE4DC_COPY_LEAN
        // Queued parts replay without a lighting snapshot (they were lit when
        // queued); only a package reopened within the frame arrives here unlit.
        if(!p.lighting)return 1;
#endif
        light_part(v,mesh,const_cast<re4dc::room::MeshPart&>(*part),p);
    }
    // Source vertex alpha: the mesh palette carries the authored CLR0 alpha, so
    // translucent vertex-alpha parts draw natively (and defer like any other).
#if RE4DC_COPY_LEAN
    union OpaqueCopy { Re4dcModelPart part; OpaqueCopy(){} } opaque; // built only when used
#else
    Re4dcModelPart opaque;
#endif
    const Re4dcModelPart* drawn=&p;
    bool vertex_alpha=false;
    if(p.alpha_state&256){
        const unsigned low=vertex_alpha_min(p);
        const bool alpha_unused=p.blend==0 && !(p.material_flags&4) && p.mask_ref>255;
        if(low<255 && !alpha_unused){vertex_alpha=true;++stats.vertex_alpha;}
        else {
#if RE4DC_COPY_LEAN
            new(&opaque.part) Re4dcModelPart(p);opaque.part.alpha_state=255;drawn=&opaque.part;
#else
            opaque=p;opaque.alpha_state=255;drawn=&opaque;
#endif
            if(low<255)++stats.vertex_alpha_unused;else ++stats.vertex_opaque;
        }
    }
    if(p.cull==3)return 1;
    if(p.projection[0]!=0 || p.viewport[2]<=0 || p.viewport[3]<=0)return 0;
    const float near=p.projection[6]/(p.projection[5]-1),far=p.projection[6]/p.projection[5];
    if(!re4dc::render::is_finite(near)||!re4dc::render::is_finite(far)||near<=0||far<=near)return 0;
#if RE4DC_QUALITY_ASSETS
    // Standard clutter cull (s16.3): the mesh's bounds centre at view depth >= mm draws nothing.
    if(std_room.active){
        const unsigned view=unsigned(&v-mesh_views);
        if((std_room.checked>>view)&1U)
            for(unsigned i=0;i<std_room.ncull;++i){
                const StdCull& c=std_room.cull[i];
                if(c.view!=view || c.mesh!=e->mesh)continue;
                const float* m=drawn->modelview;
                const float cx=(mesh.bounds_min[0]+mesh.bounds_max[0])*0.5f,cy=(mesh.bounds_min[1]+mesh.bounds_max[1])*0.5f,
                            cz=(mesh.bounds_min[2]+mesh.bounds_max[2])*0.5f;
                if(-(m[8]*cx+m[9]*cy+m[10]*cz+m[11])>=c.mm){++std_stats[0];return 1;}
                break;
            }
    }
#endif
#if RE4DC_TREE_IMPOSTOR
    {
        float cull=far;
#if RE4DC_NATIVE_FOG
        if(p.source_key[2] && fog_now.far>near && fog_now.far<far)cull=fog_now.far; // as MeshDraw::cull_far
#endif
        if(mesh_impostor(v,e->mesh,*part,*drawn,near,cull))return 1;
    }
#endif
    // Queued translucent parts replay through this function in pass order.
#if RE4DC_COPY_LEAN
    // The part is lit (above): a replay never reads its lighting again.
    if(re4dc_model_defer_part_unlit(drawn))return 1;
#else
    if(re4dc_model_defer_part(drawn))return 1;
#endif
    MeshDraw d{{*drawn,{},near,far},v.package,*part,v.lut,v.gather};
#if RE4DC_QUALITY_ASSETS
    if(std_room.active && std_room.nimpt){
        const unsigned view=unsigned(&v-mesh_views),index=unsigned(part-v.package.parts());
        if((std_room.checked>>view)&1U){
            float quad_far=far;
#if RE4DC_NATIVE_FOG
            if(drawn->source_key[2] && fog_now.far>near && fog_now.far<far)quad_far=fog_now.far;
#endif
            unsigned trees=0,quads=0;
            for(unsigned i=0;i<std_room.nimpt;++i){
                StdImpt& t=std_room.impt[i];
                if(t.view!=view || t.part!=index)continue;
                ++trees;
                if(tree_quad(v,mesh,t,*drawn,near,quad_far)){d.skip_clusters|=((std::uint64_t(1)<<t.count)-1U)<<t.first;++quads;}
                else ++std_stats[5];
            }
            const unsigned all=v.package.part_lods()[index].cluster_count;
            if(trees && quads==trees && all<=64U && d.skip_clusters==(all==64U?~std::uint64_t(0):(std::uint64_t(1)<<all)-1U))return 1;
        }
    }
#endif
    d.alpha=(drawn->alpha_state&255U)<<24;d.vertex_alpha=vertex_alpha;
    d.cull_far=far;
#if RE4DC_MESH_DIRECT
    d.direct=true;
#endif
#if RE4DC_NATIVE_FOG
    {
        const float view_far=fog_now.far; // source View._zfar, noted by model_bridge.cpp
        if(p.source_key[2] && view_far>near && view_far<far)d.cull_far=view_far; // hidden by the fog ramp
    }
#endif
#if RE4DC_MESH_LOD
    {
        // Pixels per model unit at unit depth: modelview scale (largest row,
        // placement scale included) times the projection's pixel scale.
        const float* m=drawn->modelview;
        float scale=0;
        for(unsigned r=0;r<3;++r){
            const float n=m[4*r]*m[4*r]+m[4*r+1]*m[4*r+1]+m[4*r+2]*m[4*r+2];
            if(n>scale)scale=n;
        }
        const float px_x=320.0f*std::fabs(p.projection[1]),px_y=240.0f*std::fabs(p.projection[3]);
        const float px=px_x>px_y?px_x:px_y;
        d.part_index=unsigned(part-v.package.parts());
#if RE4DC_QUALITY
        d.lod_scale=std::sqrt(scale)*px/re4dc_quality()->lod_px;   // Standard: 5 px (RQ_LOD_COARSE)
#else
        d.lod_scale=std::sqrt(scale)*px/float(RE4DC_MESH_LOD_PX);
#endif
    }
#endif
    // Mesh grid -> source model space -> live source view (node matrix included).
    const float grid[12]={mesh.step[0],0,0,mesh.origin[0], 0,mesh.step[1],0,mesh.origin[1],
                          0,0,mesh.step[2],mesh.origin[2]};
    concat(drawn->modelview,grid,d.mvq);
#if RE4DC_COPY_LEAN
    // MeshDraw reads mvq only, and bind() loads XMTRX before its first use
    // (culled parts never need it): no mv copy, no second matrix build.
#else
    std::memcpy(d.mv,d.mvq,sizeof(d.mv));
    load_screen(d.mvq,p.projection,p.viewport);
#endif
#if RE4DC_MESH_TEXTURES
    // A part with a texture record (a baked house shell) binds that package.
    unsigned baked[4];
#if RE4DC_QUALITY_ASSETS
    // Standard: the index's ptex records replace the package's texture records (s16.3).
    const unsigned* texture=nullptr;
    if(std_room.active){
        const unsigned view=unsigned(&v-mesh_views),index=unsigned(part-v.package.parts());
        if((std_room.checked>>view)&1U)
            for(unsigned i=0;i<std_room.nptex;++i)if(std_room.ptex[i].view==view && std_room.ptex[i].part==index){texture=std_room.ptex[i].key;++std_stats[2];break;}
        if(texture)re4dc_model_texture(texture);
    }else{
        const auto* record=v.package.texture(unsigned(part-v.package.parts()));
        if(record){baked[0]=record->key_crc;baked[1]=record->key_fnv;baked[2]=record->width;baked[3]=record->height;re4dc_model_texture(baked);texture=baked;}
    }
#else
    const auto* texture=v.package.texture(unsigned(part-v.package.parts()));
    if(texture){baked[0]=texture->key_crc;baked[1]=texture->key_fnv;baked[2]=texture->width;baked[3]=texture->height;re4dc_model_texture(baked);}
#endif
    const int result=d.run();
    if(texture)re4dc_model_texture(nullptr);
#else
    const int result=d.run();
#endif
#if RE4DC_MESH_DIRECT
    d.end_direct(); // before any abort: releases the store queues
#endif
    if(result>0){++stats.parts_native;return 1;}
    if(result<0){re4dc_model_packet_abort();++stats.aborts;return 1;}
    ++stats.parts_fallback;return 0;
}
#endif
}
#endif
extern "C" int re4dc_static_submit(const Re4dcModelPart* part){
#if RE4DC_NATIVE_STATIC
    const Re4dcModelPart& p=*part;
    const unsigned frame=re4dc_ui_frame();
    log_stats(frame);
#if RE4DC_NATIVE_MESH
    return mesh_submit(p);
#endif
    if(!p.world || !p.view || !p.static_geometry || !stats.owners_open)return 0;
    Located at;
    if(!locate(p,at)){
        ++stats.locate_misses;
        if(stats.locate_misses<=32)re4dc_log("native static: unlocated part model=%p serial=%u key=%u/%u\n",p.model,p.serial,p.source_key[0],p.source_key[1]);
        return 0;
    }
    Binding& b=*at.binding;View& v=*at.view;
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
        // Vertex alpha only reaches the image through blending or an alpha
        // test. An opaque (blend 0), unmasked, non-alpha-texture material draws
        // the same whatever its vertex alpha, so it is native opaque too.
        const bool alpha_unused=p.blend==0 && !(p.material_flags&4) && p.mask_ref>255;
        if(low<255 && !alpha_unused){b.fallback|=bit;++stats.parts_fallback;++stats.vertex_alpha;return 0;}
        opaque=p;opaque.alpha_state=255;drawn=&opaque;
        if(low<255)++stats.vertex_alpha_unused;else ++stats.vertex_opaque;
    }
    if(p.cull==3){b.drawn|=bit;return 1;}
    if(p.projection[0]!=0 || p.viewport[2]<=0 || p.viewport[3]<=0){b.fallback|=bit;return 0;}
    const float near=p.projection[6]/(p.projection[5]-1),far=p.projection[6]/p.projection[5];
    if(!re4dc::render::is_finite(near)||!re4dc::render::is_finite(far)||near<=0||far<=near){b.fallback|=bit;return 0;}
    // Queued translucent parts replay through this function in pass order.
    if(re4dc_model_defer_part(drawn))return 1;

    Draw d{{*drawn,{},near,far},v,material};
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
