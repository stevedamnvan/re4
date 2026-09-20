#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::route {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'R', 'T', 'P', '\0'};
inline constexpr std::uint32_t kVersion = 1;

struct Header {
    char magic[8];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t point_stride;
    std::uint32_t link_stride;
    std::uint32_t point_count;
    std::uint32_t link_count;
    std::uint32_t next_count;
    std::uint32_t point_offset;
    std::uint32_t link_offset;
    std::uint32_t next_offset;
    std::uint32_t payload_crc32;
    float bounds_min[3];
    float bounds_max[3];
};

struct Point {
    float x;
    float y;
    float z;
    std::uint16_t first_link;
    std::uint16_t link_count;
};

struct Link {
    std::int16_t point;
    std::uint16_t flags;
};

static_assert(sizeof(Header) == 76);
static_assert(sizeof(Point) == 16);
static_assert(sizeof(Link) == 4);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    void close();

    const Header& header() const { return *header_; }
    const Point* points() const;
    const Link* links() const;
    const std::int8_t* next_hops() const;
    std::int8_t next(std::uint32_t from, std::uint32_t to) const;
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

} // namespace re4dc::route
