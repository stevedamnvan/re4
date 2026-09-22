#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::room {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'R', 'M', '\0'};
inline constexpr std::uint32_t kVersion = 3;
inline constexpr std::uint32_t kFlagSourceGroupMetadata = 1U << 0U;
// Selectable static-room representation: nx/ny/nz contain final linear RGB.
inline constexpr std::uint32_t kFlagPrelitVertexColors = 1U << 1U;
inline constexpr std::uint32_t kSourceGroupHasLightVolume = 1U << 0U;
// Source SmxSetFlag() maps bit 3 to an alpha-test reference of 0x80.
inline constexpr std::uint32_t kSourceGroupAlphaOmit128 = 1U << 3U;
inline constexpr std::uint32_t kBatchStripOrderPreserved = 1U << 0U;
// Set when the batch's triangle index range is stored. Clear means its strips
// are its only representation, which the converter permits only after proving
// they reproduce the source triangle order and winding. Nothing may read
// first_index or index_count on a batch without this bit.
inline constexpr std::uint32_t kBatchTrianglesResident = 1U << 1U;
inline constexpr std::uint32_t kBatchFlagMask =
    kBatchStripOrderPreserved | kBatchTrianglesResident;

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
    std::uint32_t primitive_count;
    std::uint32_t primitive_index_count;
    std::uint32_t material_offset;
    std::uint32_t group_offset;
    std::uint32_t batch_offset;
    std::uint32_t vertex_offset;
    std::uint32_t index_offset;
    std::uint32_t primitive_offset;
    std::uint32_t primitive_index_offset;
    std::uint32_t payload_crc32;
    std::uint32_t flags;
    float bounds_min[3];
    float bounds_max[3];
    // The room's total triangle count. index_count no longer gives it: the
    // triangle table holds only the batches that still need one.
    std::uint32_t triangle_count;
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
    std::uint32_t first_primitive;
    std::uint32_t primitive_count;
};

struct Primitive {
    std::uint32_t first_vertex;
    std::uint16_t vertex_count;
    std::uint16_t triangle_count;
};

// The triangles a batch has, wherever they are stored. A batch with a resident
// triangle range answers from it; one represented only by strips answers from
// the strips, which cover exactly the same triangles.
inline std::uint32_t batch_triangle_count(const Batch& batch,
                                          const Primitive* primitives) {
    if((batch.flags & kBatchTrianglesResident) != 0U) {
        return batch.index_count / 3U;
    }
    std::uint32_t triangles = 0;
    for(std::uint32_t index = 0; index < batch.primitive_count; ++index) {
        triangles += primitives[batch.first_primitive + index].triangle_count;
    }
    return triangles;
}

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

static_assert(sizeof(Header) == 128);
static_assert(sizeof(Vertex) == 32);
static_assert(sizeof(Material) == 64);
static_assert(sizeof(Group) == 96);
static_assert(sizeof(Batch) == 28);
static_assert(sizeof(Primitive) == 8);
static_assert(sizeof(SourceGroup) == 76);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    bool adopt(const std::uint8_t* data, std::size_t size);
    void close();

    const Header& header() const { return *header_; }
    const Material* materials() const;
    const Group* groups() const;
    const Batch* batches() const;
    const Vertex* vertices() const;
    const std::uint32_t* indices() const;
    const Primitive* primitives() const;
    const std::uint32_t* primitive_indices() const;
    const SourceGroup* source_groups() const;
    const char* error() const { return error_; }

private:
    bool range_valid(std::uint32_t offset, std::uint32_t count,
                     std::uint32_t stride) const;

    bool validate();

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    const char* error_ = "not opened";
};

} // namespace re4dc::room
