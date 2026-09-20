#pragma once

#include <dc/pvr.h>
#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::texture {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'T', 'X', '\0'};
inline constexpr std::uint32_t kVersion = 1;
inline constexpr std::uint32_t kRgb565 = 0;
inline constexpr std::uint32_t kArgb1555 = 1;
inline constexpr std::uint32_t kArgb4444 = 2;
inline constexpr std::uint32_t kAlpha = 1;

struct Header {
    char magic[8];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t texture_stride;
    std::uint32_t texture_count;
    std::uint32_t texture_offset;
    std::uint32_t data_offset;
    std::uint32_t data_size;
    std::uint32_t payload_crc32;
    std::uint32_t source_image_count;
    std::uint32_t flags;
};

struct Texture {
    char material[64];
    std::uint32_t width;
    std::uint32_t height;
    std::uint32_t format;
    std::uint32_t data_offset;
    std::uint32_t data_size;
    std::uint32_t flags;
};

static_assert(sizeof(Header) == 48);
static_assert(sizeof(Texture) == 88);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    bool upload();
    void close();

    const Header& header() const { return *header_; }
    const Texture* textures() const;
    const Texture* find(const char* material) const;
    pvr_ptr_t pvr_texture(std::uint32_t index) const;
    const char* error() const { return error_; }
    std::size_t vram_bytes() const { return vram_bytes_; }

private:
    bool range_valid(std::uint32_t offset, std::uint32_t size) const;

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    pvr_ptr_t* pvr_textures_ = nullptr;
    std::size_t vram_bytes_ = 0;
    const char* error_ = "not opened";
};

} // namespace re4dc::texture
