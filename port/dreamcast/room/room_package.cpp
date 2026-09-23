#include "room_package.hpp"

#include <fcntl.h>

#include <cstring>
#include <cmath>

// [0] is the check that is running, [1] how far through it. Read by the host
// capture, which has no other view of a load that has not reached a frame yet.
extern "C" {
volatile std::uint32_t g_room_validate_progress[2] = {0U, 0U};
}

namespace re4dc::room {
namespace {

std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffU;
    for(std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for(unsigned bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1U) ^ (0xedb88320U & mask);
        }
    }
    return ~crc;
}

} // namespace

Package::~Package() {
    close();
}

bool Package::range_valid(std::uint32_t offset, std::uint32_t count,
                          std::uint32_t stride) const {
    const std::uint64_t end = static_cast<std::uint64_t>(offset) +
                              static_cast<std::uint64_t>(count) * stride;
    return offset >= sizeof(Header) && end <= size_;
}

bool Package::open(const char* path) {
    close();
    file_ = fs_open(path, O_RDONLY);
    if(file_ == FILEHND_INVALID) {
        error_ = "open failed";
        return false;
    }
    const ssize_t total = fs_total(file_);
    if(total < static_cast<ssize_t>(sizeof(Header))) {
        error_ = "file is smaller than the header";
        close();
        return false;
    }
    size_ = static_cast<std::size_t>(total);
    data_ = static_cast<const std::uint8_t*>(fs_mmap(file_));
    if(data_ == nullptr) {
        error_ = "filesystem does not support mapping";
        close();
        return false;
    }
    return validate();
}

// R4 5A. The same package, parsed out of memory the caller owns rather than a
// mapping into .rodata, so a room can be read into its arena and released by
// resetting it. The bytes are not copied and are not freed here: the arena owns
// them, and close() only drops this object's view of them.
bool Package::adopt(const std::uint8_t* data, std::size_t size) {
    close();
    if(data == nullptr || size < sizeof(Header)) {
        error_ = "adopted buffer is smaller than the header";
        return false;
    }
    data_ = data;
    size_ = size;
    return validate();
}

// The body of open() as it stood, unchanged, so both paths accept and
// reject exactly the same packages.
bool Package::validate() {
    if(reinterpret_cast<std::uintptr_t>(data_) % alignof(Header)) {
        error_="unaligned package backing"; close(); return false;
    }
    header_ = reinterpret_cast<const Header*>(data_);
    if(header_->version==kCompactVersion) return validate_compact();
    if(std::memcmp(header_->magic, kMagic, sizeof(kMagic)) != 0 ||
       header_->version != kVersion || header_->header_size != sizeof(Header)) {
        error_ = "magic, version, or header size mismatch";
        close();
        return false;
    }
    if(header_->vertex_stride != sizeof(Vertex) ||
       header_->index_stride != sizeof(std::uint32_t) ||
       header_->material_stride != sizeof(Material) ||
       header_->group_stride != sizeof(Group) ||
       header_->batch_stride != sizeof(Batch)) {
        error_ = "record stride mismatch";
        close();
        return false;
    }
    if(!range_valid(header_->material_offset, header_->material_count,
                    header_->material_stride) ||
       !range_valid(header_->group_offset, header_->group_count,
                    header_->group_stride) ||
       !range_valid(header_->batch_offset, header_->batch_count,
                    header_->batch_stride) ||
       !range_valid(header_->vertex_offset, header_->vertex_count,
                    header_->vertex_stride) ||
       !range_valid(header_->index_offset, header_->index_count,
                    header_->index_stride) ||
       !range_valid(header_->primitive_offset, header_->primitive_count,
                    sizeof(Primitive)) ||
       !range_valid(header_->primitive_index_offset,
                    header_->primitive_index_count,
                    sizeof(std::uint32_t))) {
        error_ = "record range exceeds package";
        close();
        return false;
    }
    if((header_->flags & kFlagSourceGroupMetadata) != 0U) {
        const std::uint64_t metadata_offset =
            static_cast<std::uint64_t>(header_->index_offset) +
            static_cast<std::uint64_t>(header_->index_count) *
                header_->index_stride;
        if(metadata_offset > 0xffffffffU ||
           !range_valid(static_cast<std::uint32_t>(metadata_offset),
                        header_->group_count, sizeof(SourceGroup))) {
            error_ = "source group metadata exceeds package";
            close();
            return false;
        }
    }
    g_room_validate_progress[0] = 1U;
    g_room_validate_progress[1] =
        static_cast<std::uint32_t>(size_ - header_->header_size);
    if(crc32(data_ + header_->header_size, size_ - header_->header_size) !=
       header_->payload_crc32) {
        error_ = "payload CRC mismatch";
        close();
        return false;
    }
    g_room_validate_progress[0] = 2U;
    const auto* package_indices = indices();
    for(std::uint32_t index = 0; index < header_->index_count; ++index) {
        if(package_indices[index] >= header_->vertex_count) {
            error_ = "index exceeds vertex count";
            close();
            return false;
        }
    }
    const auto* package_primitives = primitives();
    const auto* package_primitive_indices = primitive_indices();
    // The strip table has to be checked before the batch loop reads through it
    // to count triangles.
    g_room_validate_progress[0] = 3U;
    for(std::uint32_t index = 0; index < header_->primitive_count; ++index) {
        const auto& primitive = package_primitives[index];
        if(primitive.vertex_count < 3U ||
           primitive.triangle_count != primitive.vertex_count - 2U ||
           static_cast<std::uint64_t>(primitive.first_vertex) +
                   primitive.vertex_count > header_->primitive_index_count) {
            error_ = "invalid strip primitive";
            close();
            return false;
        }
        for(std::uint32_t vertex = primitive.first_vertex;
            vertex < primitive.first_vertex + primitive.vertex_count;
            ++vertex) {
            if(package_primitive_indices[vertex] >= header_->vertex_count) {
                error_ = "strip index exceeds vertex count";
                close();
                return false;
            }
        }
    }
    std::uint32_t triangles = 0;
    const auto* package_batches = batches();
    g_room_validate_progress[0] = 4U;
    for(std::uint32_t index = 0; index < header_->batch_count; ++index) {
        const auto& batch = package_batches[index];
        const bool triangles_resident =
            (batch.flags & kBatchTrianglesResident) != 0U;
        if((batch.flags & ~kBatchFlagMask) != 0U ||
           static_cast<std::uint64_t>(batch.first_index) +
                   batch.index_count > header_->index_count ||
           static_cast<std::uint64_t>(batch.first_primitive) +
                   batch.primitive_count > header_->primitive_count) {
            error_ = "batch range exceeds package counts";
            close();
            return false;
        }
        if(triangles_resident) {
            if(batch.index_count == 0U || batch.index_count % 3U != 0U) {
                error_ = "resident triangle range is empty or not whole";
                close();
                return false;
            }
        } else {
            // Without a triangle range the strips are the batch, so there has
            // to be at least one, and the range must be empty rather than
            // stale: nothing should be able to read it by accident.
            if(batch.primitive_count == 0U || batch.index_count != 0U ||
               batch.first_index != 0U) {
                error_ = "batch has neither triangles nor strips";
                close();
                return false;
            }
            if((batch.flags & kBatchStripOrderPreserved) == 0U) {
                error_ = "strips are authoritative without an order proof";
                close();
                return false;
            }
        }
        triangles += batch_triangle_count(batch, package_primitives);
    }
    if(triangles != header_->triangle_count) {
        error_ = "batch triangles do not add up to the header count";
        close();
        return false;
    }
    g_room_validate_progress[0] = 5U;
    error_ = nullptr;
    return true;
}

void Package::close() {
    if(file_ != FILEHND_INVALID) {
        fs_close(file_);
    }
    file_ = FILEHND_INVALID;
    data_ = nullptr;
    size_ = 0;
    header_ = nullptr;
}

const Material* Package::materials() const {
    return reinterpret_cast<const Material*>(data_ + header_->material_offset);
}

const Group* Package::groups() const {
    if(compact()) return nullptr;
    return reinterpret_cast<const Group*>(data_ + header_->group_offset);
}

const Batch* Package::batches() const {
    if(compact()) return nullptr;
    return reinterpret_cast<const Batch*>(data_ + header_->batch_offset);
}

const Vertex* Package::vertices() const {
    if(compact()) return nullptr;
    return reinterpret_cast<const Vertex*>(data_ + header_->vertex_offset);
}

const std::uint32_t* Package::indices() const {
    if(compact()) return nullptr;
    return reinterpret_cast<const std::uint32_t*>(data_ + header_->index_offset);
}

const Primitive* Package::primitives() const {
    return reinterpret_cast<const Primitive*>(
        data_ + header_->primitive_offset);
}

const std::uint32_t* Package::primitive_indices() const {
    if(compact()) return nullptr;
    return reinterpret_cast<const std::uint32_t*>(
        data_ + header_->primitive_index_offset);
}

const SourceGroup* Package::source_groups() const {
    if(compact()) return nullptr;
    if((header_->flags & kFlagSourceGroupMetadata) == 0U) {
        return nullptr;
    }
    const std::uint32_t offset =
        header_->index_offset + header_->index_count * header_->index_stride;
    return reinterpret_cast<const SourceGroup*>(data_ + offset);
}


bool Package::validate_compact() {
    const auto fail=[&](const char* reason) { error_=reason; close(); return false; };
    // Direct split vec4 reads require aligned backing, not merely aligned
    // relative section offsets. Arena/ROM-disk callers already provide this.
    if(reinterpret_cast<std::uintptr_t>(data_) % 16U)
        return fail("v4 backing must be 16-byte aligned");
    if(size_<sizeof(CompactHeader) || std::memcmp(header_->magic,kMagic,8) ||
       header_->header_size!=sizeof(CompactHeader)) return fail("v4 header mismatch");
    const auto& h=*reinterpret_cast<const CompactHeader*>(data_);
    const auto& b=h.base;
    const bool split=h.layout==StaticLayout::Split24;
    if((h.layout!=StaticLayout::AoS20 && !split) || h.uv_encoding!=1 ||
       h.bake_policy!=1 || h.reserved || h.source_stride!=sizeof(CompactSource) ||
       b.flags!=(kFlagSourceGroupMetadata|kFlagPrelit) ||
       b.vertex_stride!=(split?sizeof(CompactPosition):sizeof(CompactVertex)) ||
       b.index_stride!=2 || b.material_stride!=sizeof(Material) ||
       b.group_stride!=sizeof(CompactGroup) || b.batch_stride!=sizeof(CompactBatch) ||
       !b.vertex_count || !b.group_count || !b.batch_count ||
       !b.material_count || !h.source_count || h.source_count>65536)
        return fail("v4 layout/stride/count mismatch");
    std::uint64_t end=sizeof(CompactHeader);
    const auto section=[&](std::uint32_t offset,std::uint32_t count,std::uint32_t stride) {
        const std::uint64_t expected=(end+31U)&~std::uint64_t(31U);
        if(offset!=expected || !range_valid(offset,count,stride)) return false;
        for(std::uint64_t i=end;i<expected;++i) if(data_[i]) return false;
        end=expected+static_cast<std::uint64_t>(count)*stride;return true;
    };
    if(!section(b.material_offset,b.material_count,sizeof(Material)) ||
       !section(b.group_offset,b.group_count,sizeof(CompactGroup)) ||
       !section(b.batch_offset,b.batch_count,sizeof(CompactBatch)) ||
       !section(b.vertex_offset,b.vertex_count,b.vertex_stride) ||
       !section(h.attribute_offset,split?b.vertex_count:0,sizeof(CompactAttribute)) ||
       !section(b.index_offset,b.index_count,2) ||
       !section(h.source_offset,h.source_count,sizeof(CompactSource)) ||
       !section(b.primitive_offset,b.primitive_count,sizeof(Primitive)) ||
       !section(b.primitive_index_offset,b.primitive_index_count,2) || end!=size_)
        return fail("v4 section alignment/range mismatch");
    if(crc32(data_+b.header_size,size_-b.header_size)!=b.payload_crc32)
        return fail("payload CRC mismatch");
    const auto bounds_ok=[](const float* lo,const float* hi) {
        for(unsigned a=0;a<3;++a) if(!std::isfinite(lo[a]) ||
            !std::isfinite(hi[a]) || lo[a]>hi[a]) return false;
        return true;
    };
    if(!bounds_ok(b.bounds_min,b.bounds_max)) return fail("v4 invalid room bounds");
    for(std::uint32_t i=0;i<b.material_count;++i)
        if(!std::memchr(materials()[i].name,0,64)) return fail("v4 unterminated material identity");
    const auto* sources=compact_sources();
    for(std::uint32_t i=0;i<h.source_count;++i) {
        const auto& src=sources[i];
        if(src.common>1 || src.reserved || src.state.cull_mode>3 ||
           (src.state.metadata_flags & ~kSourceGroupHasLightVolume))
            return fail("v4 invalid source metadata");
        // SourceGroup's 15 floats are contiguous but are separate C++ arrays.
        for(float f:src.state.light_center) if(!std::isfinite(f)) return fail("v4 nonfinite light volume");
        for(float f:src.state.light_size) if(!std::isfinite(f)) return fail("v4 nonfinite light volume");
        for(float f:src.state.inverse_rotation) if(!std::isfinite(f)) return fail("v4 nonfinite light volume");
    }
    const auto* groups=compact_groups();const auto* batches=compact_batches();
    const auto* prims=primitives();const auto* tri=local_indices();
    const auto* indices=local_primitive_indices();
    std::uint64_t bc=0,vc=0,pc=0,ic=0,sc=0,tc=0;
    for(std::uint32_t gi=0;gi<b.group_count;++gi) {
        const auto& group=groups[gi];
        if(group.source>=h.source_count || !group.batch_count ||
           group.first_batch!=bc || bc+group.batch_count>b.batch_count ||
           !bounds_ok(group.bounds_min,group.bounds_max)) return fail("v4 invalid group");
        for(std::uint32_t k=0;k<group.batch_count;++k,++bc) {
            const auto& batch=batches[bc];const auto& draw=batch.draw;
            if(draw.group!=gi || draw.material>=b.material_count ||
               (draw.flags & ~kBatchFlagMask) || batch.first_vertex!=vc ||
               !batch.vertex_count || batch.vertex_count>65536 ||
               vc+batch.vertex_count>b.vertex_count || draw.first_primitive!=pc ||
               pc+draw.primitive_count>b.primitive_count)
                return fail("v4 invalid batch");
            for(unsigned a=0;a<2;++a)
                if(!std::isfinite(batch.uv_bias[a]) || !std::isfinite(batch.uv_scale[a]) ||
                   batch.uv_scale[a]<0 || !std::isfinite(batch.uv_bias[a]+65535.0f*batch.uv_scale[a]))
                    return fail("v4 invalid UV transform");
            const bool resident=draw.flags&kBatchTrianglesResident;
            if(resident) {
                if(draw.first_index!=ic || !draw.index_count || draw.index_count%3 ||
                   ic+draw.index_count>b.index_count) return fail("v4 invalid triangles");
                for(std::uint32_t j=0;j<draw.index_count;++j,++ic)
                    if(tri[ic]>=batch.vertex_count) return fail("v4 triangle local index out of range");
                tc+=draw.index_count/3;
            } else if(draw.first_index || draw.index_count || !draw.primitive_count ||
                      !(draw.flags&kBatchStripOrderPreserved)) return fail("v4 strips lack order proof");
            for(std::uint32_t j=0;j<draw.primitive_count;++j,++pc) {
                const auto& p=prims[pc];
                if(p.first_vertex!=sc || p.vertex_count<3 ||
                   p.triangle_count!=p.vertex_count-2 || sc+p.vertex_count>b.primitive_index_count)
                    return fail("v4 invalid primitive");
                for(std::uint32_t t=0;t<p.vertex_count;++t,++sc)
                    if(indices[sc]>=batch.vertex_count) return fail("v4 strip local index out of range");
                if(!resident) tc+=p.triangle_count;
            }
            vc+=batch.vertex_count;
        }
    }
    if(bc!=b.batch_count || vc!=b.vertex_count || pc!=b.primitive_count ||
       ic!=b.index_count || sc!=b.primitive_index_count || tc!=b.triangle_count)
        return fail("v4 unowned records/count mismatch");
    for(std::uint32_t i=0;i<b.vertex_count;++i) {
        float x,y,z;std::uint32_t color;
        if(split) {
            const auto& v=compact_positions()[i];x=v.x;y=v.y;z=v.z;
            if(v.w!=1.0f) return fail("v4 position w must be one");
            color=compact_attributes()[i].argb;
        } else {
            const auto& v=compact_vertices()[i];x=v.x;y=v.y;z=v.z;color=v.argb;
        }
        if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z)||color>>24!=255)
            return fail("v4 invalid vertex");
    }
    error_=nullptr;return true;
}

const CompactHeader* Package::compact_header() const {
    return compact()?reinterpret_cast<const CompactHeader*>(data_):nullptr;
}
const CompactGroup* Package::compact_groups() const {
    return compact()?reinterpret_cast<const CompactGroup*>(data_+header_->group_offset):nullptr;
}
const CompactBatch* Package::compact_batches() const {
    return compact()?reinterpret_cast<const CompactBatch*>(data_+header_->batch_offset):nullptr;
}
const CompactSource* Package::compact_sources() const {
    const auto* h=compact_header();
    return h?reinterpret_cast<const CompactSource*>(data_+h->source_offset):nullptr;
}
const CompactVertex* Package::compact_vertices() const {
    const auto* h=compact_header();return h && h->layout==StaticLayout::AoS20?
        reinterpret_cast<const CompactVertex*>(data_+header_->vertex_offset):nullptr;
}
const CompactPosition* Package::compact_positions() const {
    const auto* h=compact_header();return h && h->layout==StaticLayout::Split24?
        reinterpret_cast<const CompactPosition*>(data_+header_->vertex_offset):nullptr;
}
const CompactAttribute* Package::compact_attributes() const {
    const auto* h=compact_header();return h && h->layout==StaticLayout::Split24?
        reinterpret_cast<const CompactAttribute*>(data_+h->attribute_offset):nullptr;
}
const std::uint16_t* Package::local_indices() const {
    return compact()?reinterpret_cast<const std::uint16_t*>(data_+header_->index_offset):nullptr;
}
const std::uint16_t* Package::local_primitive_indices() const {
    return compact()?reinterpret_cast<const std::uint16_t*>(data_+header_->primitive_index_offset):nullptr;
}

} // namespace re4dc::room
