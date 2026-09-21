#pragma once

#include <dc/pvr.h>
#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::texture {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'T', 'X', '\0'};
inline constexpr std::uint32_t kVersion = 2;
inline constexpr std::uint32_t kRgb565 = 0;
inline constexpr std::uint32_t kArgb1555 = 1;
inline constexpr std::uint32_t kArgb4444 = 2;
inline constexpr std::uint32_t kAlpha = 1U << 0U;
inline constexpr std::uint32_t kBinaryAlpha = 1U << 1U;
// How the payload is laid out. The runtime never converts a payload; it only
// copies it, so anything the PVR cannot consume directly must be produced by
// the converter.
inline constexpr std::uint32_t kPayloadLinear = 0;
inline constexpr std::uint32_t kPayloadTwiddled = 1;
inline constexpr std::uint32_t kPayloadVq = 2;

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
    std::uint32_t payload;
    std::uint32_t reserved_0;
};

static_assert(sizeof(Header) == 48);
static_assert(sizeof(Texture) == 96);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    bool adopt(const std::uint8_t* data, std::size_t size);
    bool upload();
    // After a successful upload the texels are in texture memory and nothing
    // reads them from the CPU again, so the backing store can go. This keeps
    // the header, the descriptors, the material names, the VRAM pointers and
    // the ownership flags, and copies the metadata into its own allocation so
    // the caller is free to reuse or release the bytes it adopted. It is not
    // close(), which would also free the texture memory.
    //
    // False means nothing changed and the payload is still live and valid.
    bool release_payload();
    bool payload_released() const { return payload_released_; }
    // Bytes of adopted storage that release_payload() made reusable, and the
    // metadata copy that replaced them. The difference is the real saving.
    std::size_t released_bytes() const { return released_bytes_; }
    std::size_t metadata_bytes() const { return metadata_bytes_; }
    void close();

    const Header& header() const { return *header_; }
    const Texture* textures() const;
    const Texture* find(const char* material) const;
    pvr_ptr_t pvr_texture(std::uint32_t index) const;
    const char* error() const { return error_; }
    std::size_t vram_bytes() const { return vram_bytes_; }
    // Descriptors that reused another descriptor's allocation instead of
    // uploading a second copy of the same payload.
    std::uint32_t shared_textures() const { return shared_textures_; }

private:
    bool range_valid(std::uint32_t offset, std::uint32_t size) const;

    bool validate();

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    pvr_ptr_t* pvr_textures_ = nullptr;
    // One flag per descriptor: true when this descriptor allocated the
    // texture memory it points at, false when it borrowed an earlier
    // descriptor's. Only an owner may free.
    bool* owns_texture_ = nullptr;
    // The metadata copy that outlives the adopted bytes, and what the trade
    // cost. Null while the package still points at the caller's storage.
    std::uint8_t* metadata_ = nullptr;
    std::size_t metadata_bytes_ = 0;
    std::size_t released_bytes_ = 0;
    bool payload_released_ = false;
    std::size_t vram_bytes_ = 0;
    std::uint32_t shared_textures_ = 0;
    const char* error_ = "not opened";
};

} // namespace re4dc::texture
