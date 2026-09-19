#include "character_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::character {

Package::~Package() {
    close();
}

bool Package::range_valid(std::uint32_t offset, std::uint64_t bytes) const {
    return offset >= sizeof(Header) &&
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
    if(total < static_cast<ssize_t>(sizeof(Header))) {
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
    header_ = reinterpret_cast<const Header*>(data_);
    if(std::memcmp(header_->magic, kMagic, sizeof(kMagic)) != 0 ||
       header_->version != kVersion || header_->header_size != sizeof(Header)) {
        error_ = "magic, version, or header size mismatch";
        close();
        return false;
    }
    if(header_->vertex_count == 0 || header_->index_count % 3U != 0 ||
       header_->clip_count == 0 || header_->frame_count == 0 ||
       !(header_->position_quantum_m > 0.0f)) {
        error_ = "invalid package counts or position quantum";
        close();
        return false;
    }
    const std::uint64_t frame_bytes =
        static_cast<std::uint64_t>(header_->frame_count) *
        header_->vertex_count * 3U * sizeof(std::int16_t);
    if(!range_valid(header_->index_offset,
                    static_cast<std::uint64_t>(header_->index_count) * sizeof(std::uint16_t)) ||
       !range_valid(header_->batch_offset,
                    static_cast<std::uint64_t>(header_->batch_count) * sizeof(Batch)) ||
       !range_valid(header_->clip_offset,
                    static_cast<std::uint64_t>(header_->clip_count) * sizeof(Clip)) ||
       !range_valid(header_->frame_offset, frame_bytes)) {
        error_ = "record range exceeds package";
        close();
        return false;
    }
    const auto* package_indices = indices();
    for(std::uint32_t index = 0; index < header_->index_count; ++index) {
        if(package_indices[index] >= header_->vertex_count) {
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
               header_->index_count) {
            error_ = "batch range exceeds index count";
            close();
            return false;
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
}

const std::uint16_t* Package::indices() const {
    return reinterpret_cast<const std::uint16_t*>(data_ + header_->index_offset);
}

const Batch* Package::batches() const {
    return reinterpret_cast<const Batch*>(data_ + header_->batch_offset);
}

const Clip* Package::clips() const {
    return reinterpret_cast<const Clip*>(data_ + header_->clip_offset);
}

const std::int16_t* Package::frame_positions(std::uint32_t frame) const {
    if(frame >= header_->frame_count) {
        return nullptr;
    }
    const std::size_t stride =
        static_cast<std::size_t>(header_->vertex_count) * 3U;
    return reinterpret_cast<const std::int16_t*>(data_ + header_->frame_offset) +
           frame * stride;
}

} // namespace re4dc::character
