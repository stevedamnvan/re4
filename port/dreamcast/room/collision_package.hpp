#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::collision {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'S', 'A', 'T'};
inline constexpr std::uint32_t kVersion = 1;

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

static_assert(sizeof(Header) == 92);
static_assert(sizeof(Vec3) == 12);
static_assert(sizeof(Polygon) == 12);

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
    const char* error() const { return error_; }

private:
    bool range_valid(std::uint32_t offset, std::uint32_t count,
                     std::uint32_t stride) const;

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    const char* error_ = "not opened";
};

} // namespace re4dc::collision
