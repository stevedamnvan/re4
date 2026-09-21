#include "room_package.hpp"

#include <fcntl.h>

#include <cstring>

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
    header_ = reinterpret_cast<const Header*>(data_);
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
    if(crc32(data_ + header_->header_size, size_ - header_->header_size) !=
       header_->payload_crc32) {
        error_ = "payload CRC mismatch";
        close();
        return false;
    }
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
    return reinterpret_cast<const Group*>(data_ + header_->group_offset);
}

const Batch* Package::batches() const {
    return reinterpret_cast<const Batch*>(data_ + header_->batch_offset);
}

const Vertex* Package::vertices() const {
    return reinterpret_cast<const Vertex*>(data_ + header_->vertex_offset);
}

const std::uint32_t* Package::indices() const {
    return reinterpret_cast<const std::uint32_t*>(data_ + header_->index_offset);
}

const Primitive* Package::primitives() const {
    return reinterpret_cast<const Primitive*>(
        data_ + header_->primitive_offset);
}

const std::uint32_t* Package::primitive_indices() const {
    return reinterpret_cast<const std::uint32_t*>(
        data_ + header_->primitive_index_offset);
}

const SourceGroup* Package::source_groups() const {
    if((header_->flags & kFlagSourceGroupMetadata) == 0U) {
        return nullptr;
    }
    const std::uint32_t offset =
        header_->index_offset + header_->index_count * header_->index_stride;
    return reinterpret_cast<const SourceGroup*>(data_ + offset);
}

} // namespace re4dc::room
