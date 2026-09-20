#include "character_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::character {

Package::~Package() {
    close();
}

bool Package::range_valid(std::uint32_t offset, std::uint64_t bytes) const {
    return offset >= header_->header_size &&
           static_cast<std::uint64_t>(offset) + bytes <= size_;
}

bool Package::open(const char* path) {
    close();
    file_ = fs_open(path, O_RDONLY);
    if(file_ == FILEHND_INVALID) {
        error_ = "open failed";
        return false;
    }
    const ssize_t total = fs_total(file_);
    if(total < static_cast<ssize_t>(sizeof(LegacyHeaderV4))) {
        error_ = "file is smaller than the header";
        close();
        return false;
    }
    size_ = static_cast<std::size_t>(total);
    data_ = static_cast<const std::uint8_t*>(fs_mmap(file_));
    if(data_ == nullptr) {
        error_ = "filesystem does not support mapping";
        close();
        return false;
    }
    const auto* legacy = reinterpret_cast<const LegacyHeaderV4*>(data_);
    if(std::memcmp(legacy->magic, kMagic, sizeof(kMagic)) != 0) {
        error_ = "magic mismatch";
        close();
        return false;
    }
    if(legacy->version == kVersion) {
        if(total < static_cast<ssize_t>(sizeof(Header))) {
            error_ = "file is smaller than the v5 header";
            close();
            return false;
        }
        const auto* current = reinterpret_cast<const Header*>(data_);
        if(current->header_size != sizeof(Header)) {
            error_ = "v5 header size mismatch";
            close();
            return false;
        }
        normalized_header_ = *current;
    } else if(legacy->version == kLegacyVersion &&
              legacy->header_size == sizeof(LegacyHeaderV4)) {
        std::memset(&normalized_header_, 0, sizeof(normalized_header_));
        std::memcpy(normalized_header_.magic, legacy->magic,
                    sizeof(normalized_header_.magic));
        normalized_header_.version = legacy->version;
        normalized_header_.header_size = legacy->header_size;
        normalized_header_.position_count = legacy->position_count;
        normalized_header_.draw_vertex_count = legacy->draw_vertex_count;
        normalized_header_.normal_count = legacy->normal_count;
        normalized_header_.index_count = legacy->index_count;
        normalized_header_.batch_count = legacy->batch_count;
        normalized_header_.clip_count = legacy->clip_count;
        normalized_header_.frame_count = legacy->frame_count;
        normalized_header_.primitive_count = legacy->primitive_count;
        normalized_header_.primitive_index_count =
            legacy->primitive_index_count;
        normalized_header_.index_offset = legacy->index_offset;
        normalized_header_.batch_offset = legacy->batch_offset;
        normalized_header_.primitive_offset = legacy->primitive_offset;
        normalized_header_.primitive_index_offset =
            legacy->primitive_index_offset;
        normalized_header_.clip_offset = legacy->clip_offset;
        normalized_header_.draw_vertex_offset = legacy->draw_vertex_offset;
        normalized_header_.normal_position_offset =
            legacy->normal_position_offset;
        normalized_header_.frame_offset = legacy->frame_offset;
        normalized_header_.position_quantum_m = legacy->position_quantum_m;
    } else {
        error_ = "magic, version, or header size mismatch";
        close();
        return false;
    }
    header_ = &normalized_header_;
    if(header_->position_count == 0 || header_->draw_vertex_count == 0 ||
       header_->normal_count == 0 || header_->index_count % 3U != 0 ||
       header_->clip_count == 0 || header_->frame_count == 0 ||
       !(header_->position_quantum_m > 0.0f)) {
        error_ = "invalid package counts or position quantum";
        close();
        return false;
    }
    const std::uint64_t frame_bytes =
        static_cast<std::uint64_t>(header_->frame_count) *
        header_->position_count * 3U * sizeof(std::int16_t);
    const std::uint64_t normal_matrix_bytes =
        static_cast<std::uint64_t>(header_->frame_count) *
        header_->normal_matrix_count * 9U * sizeof(std::int16_t);
    const bool has_source_normals = header_->source_normal_count != 0U;
    if(has_source_normals != (header_->normal_matrix_count != 0U)) {
        error_ = "partial source normal data";
        close();
        return false;
    }
    if(!range_valid(header_->index_offset,
                    static_cast<std::uint64_t>(header_->index_count) * sizeof(std::uint16_t)) ||
       !range_valid(header_->batch_offset,
                    static_cast<std::uint64_t>(header_->batch_count) * sizeof(Batch)) ||
       !range_valid(header_->primitive_offset,
                    static_cast<std::uint64_t>(header_->primitive_count) * sizeof(Primitive)) ||
       !range_valid(header_->primitive_index_offset,
                    static_cast<std::uint64_t>(header_->primitive_index_count) * sizeof(std::uint16_t)) ||
       !range_valid(header_->clip_offset,
                    static_cast<std::uint64_t>(header_->clip_count) * sizeof(Clip)) ||
       !range_valid(header_->draw_vertex_offset,
                    static_cast<std::uint64_t>(header_->draw_vertex_count) * sizeof(DrawVertex)) ||
       !range_valid(header_->normal_position_offset,
                    static_cast<std::uint64_t>(header_->normal_count) * sizeof(std::uint16_t)) ||
       !range_valid(header_->frame_offset, frame_bytes) ||
       (has_source_normals &&
        (!range_valid(header_->normal_source_offset,
                      static_cast<std::uint64_t>(header_->normal_count) *
                          sizeof(std::uint16_t)) ||
         !range_valid(header_->source_normal_offset,
                      static_cast<std::uint64_t>(header_->source_normal_count) *
                          sizeof(SourceNormal)) ||
         !range_valid(header_->normal_matrix_offset,
                      normal_matrix_bytes)))) {
        error_ = "record range exceeds package";
        close();
        return false;
    }
    const auto* package_indices = indices();
    for(std::uint32_t index = 0; index < header_->index_count; ++index) {
        if(package_indices[index] >= header_->draw_vertex_count) {
            error_ = "index exceeds vertex count";
            close();
            return false;
        }
    }
    const auto* package_batches = batches();
    for(std::uint32_t index = 0; index < header_->batch_count; ++index) {
        const Batch& batch = package_batches[index];
        if(batch.index_count == 0 || batch.index_count % 3U != 0 ||
           static_cast<std::uint64_t>(batch.first_index) + batch.index_count >
               header_->index_count ||
           static_cast<std::uint64_t>(batch.first_primitive) +
                   batch.primitive_count > header_->primitive_count) {
            error_ = "batch range exceeds index count";
            close();
            return false;
        }
    }
    if((header_->primitive_count == 0U) !=
       (header_->primitive_index_count == 0U)) {
        error_ = "partial source primitive stream";
        close();
        return false;
    }
    const auto* package_primitives = primitives();
    const auto* package_primitive_indices = primitive_indices();
    for(std::uint32_t index = 0; index < header_->primitive_count; ++index) {
        const Primitive& primitive = package_primitives[index];
        const bool supported = primitive.opcode == 0x80U ||
                               primitive.opcode == 0x90U ||
                               primitive.opcode == 0x98U;
        if(!supported || primitive.vertex_count < 3U ||
           primitive.index_count == 0U || primitive.index_count % 3U != 0U ||
           static_cast<std::uint64_t>(primitive.first_vertex) +
                   primitive.vertex_count > header_->primitive_index_count ||
           static_cast<std::uint64_t>(primitive.first_index) +
                   primitive.index_count > header_->index_count) {
            error_ = "invalid source primitive range";
            close();
            return false;
        }
        for(std::uint32_t vertex = primitive.first_vertex;
            vertex < primitive.first_vertex + primitive.vertex_count; ++vertex) {
            if(package_primitive_indices[vertex] >= header_->draw_vertex_count) {
                error_ = "source primitive index exceeds vertex count";
                close();
                return false;
            }
        }
    }
    const auto* package_clips = clips();
    for(std::uint32_t index = 0; index < header_->clip_count; ++index) {
        const Clip& clip = package_clips[index];
        if(clip.frame_count == 0 || !(clip.frames_per_second > 0.0f) ||
           static_cast<std::uint64_t>(clip.first_frame) + clip.frame_count >
               header_->frame_count) {
            error_ = "clip range exceeds frame count";
            close();
            return false;
        }
    }
    const auto* package_draw_vertices = draw_vertices();
    for(std::uint32_t index = 0; index < header_->draw_vertex_count; ++index) {
        if(package_draw_vertices[index].position >= header_->position_count ||
           package_draw_vertices[index].normal >= header_->normal_count) {
            error_ = "draw vertex exceeds position or normal count";
            close();
            return false;
        }
    }
    const auto* package_normal_positions = normal_positions();
    for(std::uint32_t index = 0; index < header_->normal_count; ++index) {
        if(package_normal_positions[index] >= header_->position_count) {
            error_ = "normal position exceeds position count";
            close();
            return false;
        }
    }
    if(has_source_normals) {
        const auto* package_normal_sources = normal_sources();
        for(std::uint32_t index = 0; index < header_->normal_count; ++index) {
            if(package_normal_sources[index] >= header_->source_normal_count) {
                error_ = "normal source exceeds source normal count";
                close();
                return false;
            }
        }
        const auto* package_source_normals = source_normals();
        for(std::uint32_t index = 0; index < header_->source_normal_count;
            ++index) {
            if(package_source_normals[index].matrix >=
               header_->normal_matrix_count) {
                error_ = "source normal exceeds matrix palette";
                close();
                return false;
            }
        }
    }
    error_ = nullptr;
    return true;
}

void Package::close() {
    if(file_ != FILEHND_INVALID) {
        fs_close(file_);
    }
    file_ = FILEHND_INVALID;
    data_ = nullptr;
    size_ = 0;
    header_ = nullptr;
    normalized_header_ = {};
}

const std::uint16_t* Package::indices() const {
    return reinterpret_cast<const std::uint16_t*>(data_ + header_->index_offset);
}

const Batch* Package::batches() const {
    return reinterpret_cast<const Batch*>(data_ + header_->batch_offset);
}

const Primitive* Package::primitives() const {
    return reinterpret_cast<const Primitive*>(data_ + header_->primitive_offset);
}

const std::uint16_t* Package::primitive_indices() const {
    return reinterpret_cast<const std::uint16_t*>(
        data_ + header_->primitive_index_offset);
}

const Clip* Package::clips() const {
    return reinterpret_cast<const Clip*>(data_ + header_->clip_offset);
}

const DrawVertex* Package::draw_vertices() const {
    return reinterpret_cast<const DrawVertex*>(
        data_ + header_->draw_vertex_offset);
}

const std::uint16_t* Package::normal_positions() const {
    return reinterpret_cast<const std::uint16_t*>(
        data_ + header_->normal_position_offset);
}

const std::uint16_t* Package::normal_sources() const {
    if(header_->source_normal_count == 0U) {
        return nullptr;
    }
    return reinterpret_cast<const std::uint16_t*>(
        data_ + header_->normal_source_offset);
}

const SourceNormal* Package::source_normals() const {
    if(header_->source_normal_count == 0U) {
        return nullptr;
    }
    return reinterpret_cast<const SourceNormal*>(
        data_ + header_->source_normal_offset);
}

const std::int16_t* Package::frame_positions(std::uint32_t frame) const {
    if(frame >= header_->frame_count) {
        return nullptr;
    }
    const std::size_t stride =
        static_cast<std::size_t>(header_->position_count) * 3U;
    return reinterpret_cast<const std::int16_t*>(data_ + header_->frame_offset) +
           frame * stride;
}

const std::int16_t* Package::frame_normal_matrices(
    std::uint32_t frame) const {
    if(frame >= header_->frame_count || header_->normal_matrix_count == 0U) {
        return nullptr;
    }
    const std::size_t stride =
        static_cast<std::size_t>(header_->normal_matrix_count) * 9U;
    return reinterpret_cast<const std::int16_t*>(
               data_ + header_->normal_matrix_offset) +
           frame * stride;
}

} // namespace re4dc::character
