#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::room {

inline constexpr char kMagic[8] = {'R', 'E', '4', 'D', 'C', 'R', 'M', '\0'};
inline constexpr std::uint32_t kVersion = 3;
inline constexpr std::uint32_t kFlagSourceGroupMetadata = 1U << 0U;
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


// v4 prelit storage candidates. No runtime expansion into v3 vertices.
// Prefix Header is unchanged; its strides/offsets describe the selected layout.
inline constexpr std::uint32_t kCompactVersion = 4;
inline constexpr std::uint32_t kFlagPrelit = 1U << 1U;
enum class StaticLayout : std::uint32_t { AoS20 = 1, Split24 = 2 };
struct CompactHeader {
    Header base;
    StaticLayout layout;
    std::uint32_t attribute_offset;
    std::uint32_t source_offset;
    std::uint32_t source_count;
    std::uint32_t source_stride;
    std::uint32_t uv_encoding; // 1 = bias + uint16 * scale, per batch
    std::uint32_t bake_policy; // 1 = qualified static/world bake, no view lights
    std::uint32_t reserved;
};
struct CompactVertex {
    float x,y,z;
    std::uint16_t u,v;
    std::uint32_t argb;
};
struct CompactPosition { float x,y,z,w; }; // w is validated as 1.0f
struct CompactAttribute { std::uint16_t u,v; std::uint32_t argb; };
struct CompactGroup {
    std::uint32_t first_batch;
    std::uint16_t batch_count, source;
    float bounds_min[3], bounds_max[3];
};
struct CompactBatch {
    Batch draw;
    std::uint32_t first_vertex, vertex_count;
    float uv_bias[2], uv_scale[2];
};
struct CompactSource {
    SourceGroup state;
    std::uint8_t owner; // 0xff = main scenario; otherwise source block number
    std::uint8_t common;
    std::uint16_t work, bin, reserved;
};
static_assert(sizeof(CompactHeader)==160);
static_assert(sizeof(CompactVertex)==20);
static_assert(sizeof(CompactPosition)==16);
static_assert(sizeof(CompactAttribute)==8);
static_assert(sizeof(CompactGroup)==32);
static_assert(sizeof(CompactBatch)==52);
static_assert(sizeof(CompactSource)==84);

// Load/registration-time source selection. Indices, not borrowed pointers or
// another owner registry. The caller's existing owner generation determines
// validity and must resolve again after replacement/rebase/retirement.
struct CompactSourceRange {
    std::uint32_t source, first_group, group_count;
};

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
    bool compact() const { return header_ && header_->version==kCompactVersion; }
    const CompactHeader* compact_header() const;
    const CompactGroup* compact_groups() const;
    const CompactBatch* compact_batches() const;
    const CompactSource* compact_sources() const;
    // Source SMD owner/work identifies the placed object, including repeated
    // SMX IDs; BIN/common must also match. Cold-path lookup, never per corner.
    // No allocation, source GX parse, geometry copy or retained pointer.
    bool resolve_source(std::uint8_t owner, std::uint16_t work,
                        std::uint16_t bin, bool common,
                        CompactSourceRange& range) const;
    const CompactVertex* compact_vertices() const;
    const CompactPosition* compact_positions() const;
    const CompactAttribute* compact_attributes() const;
    const std::uint16_t* local_indices() const;
    const std::uint16_t* local_primitive_indices() const;
    // Legacy typed accessors return nullptr for v4, never a mis-strided view.
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
    bool validate_compact();

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    const Header* header_ = nullptr;
    const char* error_ = "not opened";
};

} // namespace re4dc::room
