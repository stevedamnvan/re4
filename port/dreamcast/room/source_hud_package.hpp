#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::hud {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'H', 'D', '\0'};
inline constexpr std::uint32_t kVersion = 1;
inline constexpr std::uint32_t kNoTexture = 0xffffffffU;
inline constexpr std::uint8_t kTableFrame = 0;
inline constexpr std::uint8_t kTableLife = 1;
inline constexpr std::uint8_t kTableBullet = 2;

struct Header {
    char magic[8];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t unit_stride;
    std::uint32_t unit_count;
    std::uint32_t unit_offset;
    std::uint32_t frame_start;
    std::uint32_t frame_count;
    std::uint32_t life_start;
    std::uint32_t life_count;
    std::uint32_t bullet_start;
    std::uint32_t bullet_count;
    std::uint32_t payload_crc32;
};

struct Unit {
    std::uint8_t table;
    std::uint8_t flags;
    std::uint8_t mark;
    std::uint8_t number;
    std::uint8_t level;
    std::uint8_t parent;
    std::uint8_t kind;
    std::uint8_t vertex_type;
    std::uint8_t blend_type;
    std::uint8_t transform_type;
    std::uint8_t texture_flags;
    std::uint8_t reserved;
    std::uint32_t first_texture;
    std::uint32_t texture_count;
    float position[3];
    float size[2];
    float rotation[3];
    float uv_max[2];
    std::uint8_t color0[4];
    std::uint8_t color1[4];
};

static_assert(sizeof(Header) == 56);
static_assert(sizeof(Unit) == 68);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    void close();

    const Header& header() const { return *header_; }
    const Unit* units() const;
    const char* error() const { return error_; }

private:
    bool range_valid(std::uint32_t offset, std::uint32_t size) const;

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    const char* error_ = "not opened";
};

} // namespace re4dc::hud
