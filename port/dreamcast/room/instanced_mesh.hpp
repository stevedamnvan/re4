#pragma once
// R4IM v1/v2: instanced native scenery meshes (tools/convert_room_bins.py).
//
// One mesh per source BIN in the BIN's own model space; every placement that
// uses the BIN draws it with its live source modelview. A mesh part is matched
// to the source ModelPart by the part header's byte offset inside the BIN and
// its stream size, and the mesh to the live ModelData by its vertex and part
// counts, so a stale or foreign pointer can never select geometry. The offset
// is measured from the BIN's first part header (ModelData::pParts), because
// archive compaction may move the part block inside a BIN.
//
// v2 (convert_room_bins.py --lod) adds levels of detail without changing any
// v1 table: a MeshLodHeader follows the 80-byte header, each part owns a range
// of clusters, each cluster a range of levels ordered by increasing error
// (level 0 = source geometry), and each level a range of the part's meshlets.
// A part's meshlet range still covers every level, so lighting stays one pass.
// Only a LOD-aware runtime may adopt v2 (adopt(..., true)): a v1 draw loop
// would draw every level of a v2 part on top of each other.
#include <cstdint>
#include <cstring>
#include "room_package.hpp"

namespace re4dc::room {
// Header reserved[0]: each vertex colour slot is (CLR0 palette index << 12) |
// 12-bit octahedral source normal until the runtime lights its part, then
// ARGB1555. MeshPart::reserved is that part's lit flag (0 in the file).
constexpr std::uint32_t kColorOctNormal=1;
struct MeshHeader {
    char magic[4];
    std::uint32_t version, bytes, crc;
    std::uint32_t mesh_count, part_count, meshlet_count, vertex_count, strip_bytes, palette_count;
    std::uint32_t mesh_offset, part_offset, meshlet_offset, vertex_offset, strip_offset, palette_offset;
    std::uint32_t reserved[4];
};
struct MeshRecord {
    std::uint16_t bin; std::uint8_t common, owner;
    std::uint16_t source_vertices, source_parts;
    std::uint32_t source_flags, first_part, part_count;
    float origin[3], step[3], bounds_min[3], bounds_max[3];
};
struct MeshPart {
    std::uint32_t source_offset, source_size;
    std::uint8_t texture, alpha, flags, reserved;
    std::uint32_t first_meshlet, meshlet_count;
    float uv_bias[2], uv_scale[2];
};
struct Meshlet {
    std::uint32_t first_vertex, first_strip, strip_bytes;
    std::uint16_t vertex_count, strip_count;
    std::uint16_t bounds_min[3], bounds_max[3]; // mesh grid units
};
// v2 only, at offset 80.
struct MeshLodHeader {
    std::uint32_t cluster_count, level_count, part_lod_offset, cluster_offset, level_offset, reserved[3];
};
struct MeshPartLod { std::uint32_t first_cluster, cluster_count; };
struct MeshCluster {
    std::uint16_t bounds_min[3], bounds_max[3]; // mesh grid units, covers every level
    std::uint32_t first_level, level_count;
};
struct MeshLevel {
    std::uint32_t first_meshlet, meshlet_count;
    float error; // model units; drawn while error * lod_scale <= nearest cluster depth
};
static_assert(sizeof(MeshHeader)==80);
static_assert(sizeof(MeshLodHeader)==32);
static_assert(sizeof(MeshPartLod)==8);
static_assert(sizeof(MeshCluster)==20);
static_assert(sizeof(MeshLevel)==12);
static_assert(sizeof(MeshRecord)==68);
static_assert(sizeof(MeshPart)==36);
static_assert(sizeof(Meshlet)==28);
static_assert(sizeof(CompactVertex12)==12);

class MeshPackage {
public:
    // Validates every offset, range, strip length/index and palette index once;
    // afterwards the draw path trusts the tables. data must be 4-byte aligned.
    // lod: the caller draws v2 levels (and still accepts v1); otherwise v1 only.
    bool adopt(const std::uint8_t* data,std::uint32_t size,bool lod=false){
        close();
        if(size<sizeof(MeshHeader) || (reinterpret_cast<std::uintptr_t>(data)&3U))return fail("size");
        std::memcpy(&h_,data,sizeof(h_));
        if(std::memcmp(h_.magic,"R4IM",4) || !(h_.version==1 || (lod && h_.version==2)) || h_.bytes!=size)return fail("header");
        std::uint32_t head=sizeof(MeshHeader);
        if(h_.version==2){
            head+=sizeof(MeshLodHeader);
            if(size<head)return fail("size");
            std::memcpy(&l_,data+sizeof(MeshHeader),sizeof(l_));
        }
        if(!section(h_.mesh_offset,h_.mesh_count,sizeof(MeshRecord),size,head) ||
           !section(h_.part_offset,h_.part_count,sizeof(MeshPart),size,head) ||
           !section(h_.meshlet_offset,h_.meshlet_count,sizeof(Meshlet),size,head) ||
           !section(h_.vertex_offset,h_.vertex_count,sizeof(CompactVertex12),size,head) ||
           !section(h_.strip_offset,h_.strip_bytes,1,size,head) ||
           !section(h_.palette_offset,h_.palette_count,4,size,head))return fail("section");
        if(h_.version==2 && (!section(l_.part_lod_offset,h_.part_count,sizeof(MeshPartLod),size,head) ||
           !section(l_.cluster_offset,l_.cluster_count,sizeof(MeshCluster),size,head) ||
           !section(l_.level_offset,l_.level_count,sizeof(MeshLevel),size,head)))return fail("lod section");
        if(!h_.palette_count || h_.palette_count>65536U)return fail("palette");
        data_=data;
        if(h_.reserved[0]!=kColorOctNormal)return fail("color encoding");
        if(h_.palette_count>16U)return fail("palette");
        for(unsigned i=0;i<h_.vertex_count;++i)if((vertices()[i].color>>12)>=h_.palette_count)return fail("color");
        for(unsigned i=0;i<h_.part_count;++i)if(parts()[i].reserved)return fail("part state");
        for(unsigned m=0;m<h_.mesh_count;++m){
            const auto& r=meshes()[m];
            if(r.first_part>h_.part_count || r.part_count>h_.part_count-r.first_part)return fail("mesh parts");
            for(unsigned a=0;a<3;++a)if(!(r.step[a]>0.0f) || r.step[a]!=r.step[a])return fail("grid");
        }
        for(unsigned i=0;i<h_.part_count;++i){
            const auto& p=parts()[i];
            if(p.first_meshlet>h_.meshlet_count || p.meshlet_count>h_.meshlet_count-p.first_meshlet)return fail("part meshlets");
        }
        for(unsigned i=0;i<h_.meshlet_count;++i){
            const auto& l=meshlets()[i];
            if(!l.vertex_count || l.vertex_count>256U || l.first_vertex>h_.vertex_count ||
               l.vertex_count>h_.vertex_count-l.first_vertex ||
               l.first_strip>h_.strip_bytes || l.strip_bytes>h_.strip_bytes-l.first_strip)return fail("meshlet");
            const std::uint8_t* s=strips()+l.first_strip;const std::uint8_t* end=s+l.strip_bytes;
            unsigned count=0;
            while(s<end){
                const unsigned n=*s++;
                if(n<3 || n>unsigned(end-s))return fail("strip");
                for(unsigned k=0;k<n;++k)if(s[k]>=l.vertex_count)return fail("strip index");
                s+=n;++count;
            }
            if(count!=l.strip_count)return fail("strip count");
        }
        if(h_.version==2){
            // Every level of every cluster lies inside its own part's meshlet
            // range; errors are finite, non-negative and non-decreasing.
            for(unsigned i=0;i<h_.part_count;++i){
                const auto& p=parts()[i];const auto& pl=part_lods()[i];
                if(pl.first_cluster>l_.cluster_count || pl.cluster_count>l_.cluster_count-pl.first_cluster)return fail("part clusters");
                for(unsigned c=pl.first_cluster;c<pl.first_cluster+pl.cluster_count;++c){
                    const auto& cl=clusters()[c];
                    if(!cl.level_count || cl.first_level>l_.level_count || cl.level_count>l_.level_count-cl.first_level)return fail("cluster levels");
                    float previous=0.0f;
                    for(unsigned k=cl.first_level;k<cl.first_level+cl.level_count;++k){
                        const auto& lv=levels()[k];
                        if(!(lv.error>=previous) || !(lv.error<3.0e38f))return fail("level error");
                        previous=lv.error;
                        if(lv.first_meshlet<p.first_meshlet || lv.meshlet_count>p.meshlet_count ||
                           lv.first_meshlet-p.first_meshlet>p.meshlet_count-lv.meshlet_count)return fail("level meshlets");
                    }
                }
            }
        }
        return true;
    }
    void close(){data_=nullptr;error_=nullptr;l_={};}
    bool valid()const{return data_!=nullptr;}
    bool lod()const{return data_ && h_.version==2;}
    const MeshPartLod* part_lods()const{return at<MeshPartLod>(l_.part_lod_offset);}
    const MeshCluster* clusters()const{return at<MeshCluster>(l_.cluster_offset);}
    const MeshLevel* levels()const{return at<MeshLevel>(l_.level_offset);}
    const char* error()const{return error_;}
    const MeshHeader& header()const{return h_;}
    const MeshRecord* meshes()const{return at<MeshRecord>(h_.mesh_offset);}
    const MeshPart* parts()const{return at<MeshPart>(h_.part_offset);}
    const Meshlet* meshlets()const{return at<Meshlet>(h_.meshlet_offset);}
    const CompactVertex12* vertices()const{return at<CompactVertex12>(h_.vertex_offset);}
    const std::uint8_t* strips()const{return data_+h_.strip_offset;}
    const std::uint32_t* palette()const{return at<std::uint32_t>(h_.palette_offset);}
    // Mesh index for a (bin, common) identity; mesh_count when absent.
    unsigned find(unsigned bin,bool common)const{
        for(unsigned m=0;m<h_.mesh_count;++m)
            if(meshes()[m].bin==bin && (meshes()[m].common!=0)==common)return m;
        return h_.mesh_count;
    }
    // Part of mesh m whose source header sits at offset/size; nullptr otherwise.
    const MeshPart* part(unsigned m,std::uint32_t offset,std::uint32_t size)const{
        const auto& r=meshes()[m];
        for(unsigned i=0;i<r.part_count;++i){
            const auto& p=parts()[r.first_part+i];
            if(p.source_offset==offset && p.source_size==size)return &p;
        }
        return nullptr;
    }
private:
    template<class T> const T* at(std::uint32_t offset)const{return reinterpret_cast<const T*>(data_+offset);}
    static bool section(std::uint32_t offset,std::uint32_t count,std::uint32_t stride,std::uint32_t size,std::uint32_t head){
        return offset>=head && offset<=size && (offset&3U)==0 &&
               std::uint64_t(count)*stride<=std::uint64_t(size-offset);
    }
    bool fail(const char* why){data_=nullptr;error_=why;return false;}
    MeshHeader h_{};
    MeshLodHeader l_{};
    const std::uint8_t* data_=nullptr;
    const char* error_=nullptr;
};
} // namespace re4dc::room
