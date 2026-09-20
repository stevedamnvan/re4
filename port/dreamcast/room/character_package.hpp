#pragma once

#include <kos/fs.h>

#include <cstddef>
#include <cstdint>

namespace re4dc::character {

inline constexpr char kMagic[4] = {'R', '4', 'C', 'H'};
inline constexpr std::uint32_t kVersion = 5;
inline constexpr std::uint32_t kLegacyVersion = 4;

struct LegacyHeaderV4 {
    char magic[4];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t position_count;
    std::uint32_t draw_vertex_count;
    std::uint32_t normal_count;
    std::uint32_t index_count;
    std::uint32_t batch_count;
    std::uint32_t clip_count;
    std::uint32_t frame_count;
    std::uint32_t primitive_count;
    std::uint32_t primitive_index_count;
    std::uint32_t index_offset;
    std::uint32_t batch_offset;
    std::uint32_t primitive_offset;
    std::uint32_t primitive_index_offset;
    std::uint32_t clip_offset;
    std::uint32_t draw_vertex_offset;
    std::uint32_t normal_position_offset;
    std::uint32_t frame_offset;
    float position_quantum_m;
};

struct Header {
    char magic[4];
    std::uint32_t version;
    std::uint32_t header_size;
    std::uint32_t position_count;
    std::uint32_t draw_vertex_count;
    std::uint32_t normal_count;
    std::uint32_t source_normal_count;
    std::uint32_t index_count;
    std::uint32_t batch_count;
    std::uint32_t clip_count;
    std::uint32_t frame_count;
    std::uint32_t primitive_count;
    std::uint32_t primitive_index_count;
    std::uint32_t normal_matrix_count;
    std::uint32_t index_offset;
    std::uint32_t batch_offset;
    std::uint32_t primitive_offset;
    std::uint32_t primitive_index_offset;
    std::uint32_t clip_offset;
    std::uint32_t draw_vertex_offset;
    std::uint32_t normal_position_offset;
    std::uint32_t normal_source_offset;
    std::uint32_t source_normal_offset;
    std::uint32_t frame_offset;
    std::uint32_t normal_matrix_offset;
    float position_quantum_m;
};

struct Batch {
    std::uint32_t first_index;
    std::uint32_t index_count;
    std::uint32_t material;
    std::uint32_t source_part;
    std::uint32_t first_primitive;
    std::uint32_t primitive_count;
};

struct Primitive {
    std::uint32_t first_vertex;
    std::uint32_t first_index;
    std::uint16_t vertex_count;
    std::uint16_t index_count;
    std::uint8_t opcode;
    std::uint8_t reserved[3];
};

struct Clip {
    char name[16];
    std::uint32_t first_frame;
    std::uint32_t frame_count;
    float frames_per_second;
    float root_forward_speed_mps;
};

struct DrawVertex {
    std::uint16_t position;
    std::uint16_t normal;
    float u;
    float v;
};

struct SourceNormal {
    std::int16_t x;
    std::int16_t y;
    std::int16_t z;
    std::uint16_t matrix;
};

static_assert(sizeof(Header) == 104);
static_assert(sizeof(LegacyHeaderV4) == 84);
static_assert(sizeof(Batch) == 24);
static_assert(sizeof(Primitive) == 16);
static_assert(sizeof(Clip) == 32);
static_assert(sizeof(DrawVertex) == 12);
static_assert(sizeof(SourceNormal) == 8);

class Package {
public:
    Package() = default;
    Package(const Package&) = delete;
    Package& operator=(const Package&) = delete;
    ~Package();

    bool open(const char* path);
    void close();

    const Header& header() const { return *header_; }
    const std::uint16_t* indices() const;
    const Batch* batches() const;
    const Primitive* primitives() const;
    const std::uint16_t* primitive_indices() const;
    const Clip* clips() const;
    const DrawVertex* draw_vertices() const;
    const std::uint16_t* normal_positions() const;
    const std::uint16_t* normal_sources() const;
    const SourceNormal* source_normals() const;
    const std::int16_t* frame_positions(std::uint32_t frame) const;
    const std::int16_t* frame_normal_matrices(std::uint32_t frame) const;
    const char* error() const { return error_; }

private:
    bool range_valid(std::uint32_t offset, std::uint64_t bytes) const;

    file_t file_ = FILEHND_INVALID;
    const std::uint8_t* data_ = nullptr;
    std::size_t size_ = 0;
    Header normalized_header_{};
    const Header* header_ = nullptr;
    const char* error_ = "not opened";
};

} // namespace re4dc::character
