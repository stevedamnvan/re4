#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::room {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'R', 'M', '\0'};
inline constexpr std::uint32_t kVersion = 1;
inline constexpr std::uint32_t kFlagSourceGroupMetadata = 1U << 0U;
inline constexpr std::uint32_t kSourceGroupHasLightVolume = 1U << 0U;

struct Header {
    char magic[8];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t vertex_stride;
    std::uint32_t index_stride;
    std::uint32_t material_stride;
    std::uint32_t group_stride;
    std::uint32_t batch_stride;
    std::uint32_t vertex_count;
    std::uint32_t index_count;
    std::uint32_t material_count;
    std::uint32_t group_count;
    std::uint32_t batch_count;
    std::uint32_t material_offset;
    std::uint32_t group_offset;
    std::uint32_t batch_offset;
    std::uint32_t vertex_offset;
    std::uint32_t index_offset;
    std::uint32_t payload_crc32;
    std::uint32_t flags;
    float bounds_min[3];
    float bounds_max[3];
};

struct Vertex {
    float x;
    float y;
    float z;
    float nx;
    float ny;
    float nz;
    float u;
    float v;
};

struct Material {
    char name[64];
};

struct Group {
    char name[64];
    std::uint32_t first_batch;
    std::uint32_t batch_count;
    float bounds_min[3];
    float bounds_max[3];
};

struct Batch {
    std::uint32_t material;
    std::uint32_t first_index;
    std::uint32_t index_count;
    std::uint32_t group;
    std::uint32_t flags;
};

// Optional records appended directly after the index array when
// kFlagSourceGroupMetadata is set. Values come from the source room SMX.
struct SourceGroup {
    std::uint32_t select_mask;
    std::uint8_t source_id;
    std::uint8_t object_type;
    std::uint8_t ot_type;
    std::uint8_t cull_mode;
    std::uint32_t flags;
    std::uint32_t metadata_flags;
    float light_center[3];
    float light_size[3];
    float inverse_rotation[9];
};

static_assert(sizeof(Header) == 108);
static_assert(sizeof(Vertex) == 32);
static_assert(sizeof(Material) == 64);
static_assert(sizeof(Group) == 96);
static_assert(sizeof(Batch) == 20);
static_assert(sizeof(SourceGroup) == 76);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    void close();

    const Header& header() const { return *header_; }
    const Material* materials() const;
    const Group* groups() const;
    const Batch* batches() const;
    const Vertex* vertices() const;
    const std::uint32_t* indices() const;
    const SourceGroup* source_groups() const;
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

} // namespace re4dc::room
