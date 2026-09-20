#include "collision_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::collision {
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
    header_ = reinterpret_cast<const Header*>(data_);
    if(std::memcmp(header_->magic, kMagic, sizeof(kMagic)) != 0 ||
       header_->version != kVersion || header_->header_size != sizeof(Header)) {
        error_ = "magic, version, or header size mismatch";
        close();
        return false;
    }
    if(header_->vertex_stride != sizeof(Vec3) ||
       header_->normal_stride != sizeof(Vec3) ||
       header_->polygon_stride != sizeof(Polygon)) {
        error_ = "record stride mismatch";
        close();
        return false;
    }
    if(header_->floor_count + header_->slope_count + header_->wall_count !=
           header_->polygon_count ||
       !range_valid(header_->vertex_offset, header_->vertex_count,
                    header_->vertex_stride) ||
       !range_valid(header_->normal_offset, header_->normal_count,
                    header_->normal_stride) ||
       !range_valid(header_->polygon_offset, header_->polygon_count,
                    header_->polygon_stride)) {
        error_ = "collision counts or ranges are invalid";
        close();
        return false;
    }
    const std::uint64_t hierarchy_offset =
        static_cast<std::uint64_t>(header_->polygon_offset) +
        static_cast<std::uint64_t>(header_->polygon_count) *
            header_->polygon_stride;
    if(hierarchy_offset < size_) {
        if(hierarchy_offset > 0xffffffffU ||
           !range_valid(static_cast<std::uint32_t>(hierarchy_offset), 1U,
                        sizeof(HierarchyHeader))) {
            error_ = "collision hierarchy header exceeds package";
            close();
            return false;
        }
        hierarchy_ = reinterpret_cast<const HierarchyHeader*>(
            data_ + hierarchy_offset);
        if(std::memcmp(hierarchy_->magic, kHierarchyMagic,
                       sizeof(kHierarchyMagic)) != 0 ||
           hierarchy_->version != kHierarchyVersion ||
           hierarchy_->header_size != sizeof(HierarchyHeader) ||
           hierarchy_->edge_stride != sizeof(Vec3) ||
           hierarchy_->polygon_edge_stride != sizeof(PolygonEdges) ||
           hierarchy_->block_stride != sizeof(Block) ||
           hierarchy_->block_index_stride != sizeof(std::uint16_t) ||
           hierarchy_->polygon_edge_count != header_->polygon_count ||
           !range_valid(hierarchy_->edge_offset, hierarchy_->edge_count,
                        hierarchy_->edge_stride) ||
           !range_valid(hierarchy_->polygon_edge_offset,
                        hierarchy_->polygon_edge_count,
                        hierarchy_->polygon_edge_stride) ||
           !range_valid(hierarchy_->block_offset, hierarchy_->block_count,
                        hierarchy_->block_stride) ||
           !range_valid(hierarchy_->block_index_offset,
                        hierarchy_->block_index_count,
                        hierarchy_->block_index_stride)) {
            error_ = "collision hierarchy header or ranges are invalid";
            close();
            return false;
        }
        const PolygonEdges* hierarchy_polygon_edges = polygon_edges();
        for(std::uint32_t polygon = 0;
            polygon < hierarchy_->polygon_edge_count; ++polygon) {
            for(unsigned edge = 0; edge < 3U; ++edge) {
                if(hierarchy_polygon_edges[polygon].edge[edge] >=
                   hierarchy_->edge_count) {
                    error_ = "collision hierarchy edge index is invalid";
                    close();
                    return false;
                }
            }
        }
        const Block* hierarchy_blocks = blocks();
        const std::uint16_t* hierarchy_indices = block_indices();
        for(std::uint32_t block = 0; block < hierarchy_->block_count;
            ++block) {
            const Block& record = hierarchy_blocks[block];
            const bool parent = (record.flags & 1U) != 0U;
            const std::uint64_t reference_end =
                static_cast<std::uint64_t>(record.first_polygon) +
                record.polygon_count;
            if((record.child != kNoBlock &&
                record.child >= hierarchy_->block_count) ||
               (record.next != kNoBlock &&
                record.next >= hierarchy_->block_count) ||
               reference_end > hierarchy_->block_index_count ||
               (parent && (record.child == kNoBlock ||
                           record.polygon_count != 0U)) ||
               (!parent && (record.child != kNoBlock ||
                 record.polygon_count !=
                    static_cast<std::uint32_t>(record.floor_count) +
                    record.slope_count + record.wall_count))) {
                error_ = "collision hierarchy block is invalid";
                close();
                return false;
            }
            for(std::uint32_t reference = 0;
                reference < record.polygon_count; ++reference) {
                if(hierarchy_indices[record.first_polygon + reference] >=
                   header_->polygon_count) {
                    error_ = "collision hierarchy polygon index is invalid";
                    close();
                    return false;
                }
            }
        }
    }
    if(crc32(data_ + header_->header_size, size_ - header_->header_size) !=
       header_->payload_crc32) {
        error_ = "payload CRC mismatch";
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
    hierarchy_ = nullptr;
}

const Vec3* Package::vertices() const {
    return reinterpret_cast<const Vec3*>(data_ + header_->vertex_offset);
}

const Vec3* Package::normals() const {
    return reinterpret_cast<const Vec3*>(data_ + header_->normal_offset);
}

const Polygon* Package::polygons() const {
    return reinterpret_cast<const Polygon*>(data_ + header_->polygon_offset);
}

const Vec3* Package::edges() const {
    return hierarchy_ == nullptr
        ? nullptr
        : reinterpret_cast<const Vec3*>(data_ + hierarchy_->edge_offset);
}

const PolygonEdges* Package::polygon_edges() const {
    return hierarchy_ == nullptr
        ? nullptr
        : reinterpret_cast<const PolygonEdges*>(
              data_ + hierarchy_->polygon_edge_offset);
}

const Block* Package::blocks() const {
    return hierarchy_ == nullptr
        ? nullptr
        : reinterpret_cast<const Block*>(data_ + hierarchy_->block_offset);
}

const std::uint16_t* Package::block_indices() const {
    return hierarchy_ == nullptr
        ? nullptr
        : reinterpret_cast<const std::uint16_t*>(
              data_ + hierarchy_->block_index_offset);
}

} // namespace re4dc::collision
