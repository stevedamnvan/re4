#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::collision {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'S', 'A', 'T'};
inline constexpr std::uint32_t kVersion = 1;
inline constexpr char kHierarchyMagic[8] = {
    'R', 'E', '4', 'D', 'C', 'H', 'Y', '\0'};
inline constexpr std::uint32_t kHierarchyVersion = 1;
inline constexpr std::uint32_t kNoBlock = 0xffffffffU;

struct Header {
    char magic[8];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t vertex_stride;
    std::uint32_t normal_stride;
    std::uint32_t polygon_stride;
    std::uint32_t vertex_count;
    std::uint32_t normal_count;
    std::uint32_t polygon_count;
    std::uint32_t floor_count;
    std::uint32_t slope_count;
    std::uint32_t wall_count;
    std::uint32_t vertex_offset;
    std::uint32_t normal_offset;
    std::uint32_t polygon_offset;
    std::uint32_t payload_crc32;
    float bounds_min[3];
    float bounds_max[3];
};

struct Vec3 {
    float x;
    float y;
    float z;
};

struct Polygon {
    std::uint16_t vertex[3];
    std::uint16_t normal;
    std::uint32_t attribute;
};

struct HierarchyHeader {
    char magic[8];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t edge_stride;
    std::uint32_t polygon_edge_stride;
    std::uint32_t block_stride;
    std::uint32_t block_index_stride;
    std::uint32_t edge_count;
    std::uint32_t polygon_edge_count;
    std::uint32_t block_count;
    std::uint32_t block_index_count;
    std::uint32_t edge_offset;
    std::uint32_t polygon_edge_offset;
    std::uint32_t block_offset;
    std::uint32_t block_index_offset;
};

struct PolygonEdges {
    std::uint16_t edge[3];
    std::uint16_t reserved;
};

struct Block {
    float minimum[3];
    float size[3];
    std::uint16_t floor_count;
    std::uint16_t slope_count;
    std::uint16_t wall_count;
    std::uint16_t flags;
    std::uint32_t child;
    std::uint32_t next;
    std::uint32_t first_polygon;
    std::uint32_t polygon_count;
};

static_assert(sizeof(Header) == 92);
static_assert(sizeof(Vec3) == 12);
static_assert(sizeof(Polygon) == 12);
static_assert(sizeof(HierarchyHeader) == 64);
static_assert(sizeof(PolygonEdges) == 8);
static_assert(sizeof(Block) == 48);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    void close();

    const Header& header() const { return *header_; }
    const Vec3* vertices() const;
    const Vec3* normals() const;
    const Polygon* polygons() const;
    bool has_hierarchy() const { return hierarchy_ != nullptr; }
    const HierarchyHeader* hierarchy() const { return hierarchy_; }
    const Vec3* edges() const;
    const PolygonEdges* polygon_edges() const;
    const Block* blocks() const;
    const std::uint16_t* block_indices() const;
    const char* error() const { return error_; }

private:
    bool range_valid(std::uint32_t offset, std::uint32_t count,
                     std::uint32_t stride) const;

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    const HierarchyHeader* hierarchy_ = nullptr;
    const char* error_ = "not opened";
};

} // namespace re4dc::collision
