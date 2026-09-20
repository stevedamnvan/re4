#include "room_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::room {
namespace {

std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffU;
    for(std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for(unsigned bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1U) ^ (0xedb88320U & mask);
        }
    }
    return ~crc;
}

} // namespace

Package::~Package() {
    close();
}

bool Package::range_valid(std::uint32_t offset, std::uint32_t count,
                          std::uint32_t stride) const {
    const std::uint64_t end = static_cast<std::uint64_t>(offset) +
                              static_cast<std::uint64_t>(count) * stride;
    return offset >= sizeof(Header) && end <= size_;
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
    if(header_->vertex_stride != sizeof(Vertex) ||
       header_->index_stride != sizeof(std::uint32_t) ||
       header_->material_stride != sizeof(Material) ||
       header_->group_stride != sizeof(Group) ||
       header_->batch_stride != sizeof(Batch)) {
        error_ = "record stride mismatch";
        close();
        return false;
    }
    if(!range_valid(header_->material_offset, header_->material_count,
                    header_->material_stride) ||
       !range_valid(header_->group_offset, header_->group_count,
                    header_->group_stride) ||
       !range_valid(header_->batch_offset, header_->batch_count,
                    header_->batch_stride) ||
       !range_valid(header_->vertex_offset, header_->vertex_count,
                    header_->vertex_stride) ||
       !range_valid(header_->index_offset, header_->index_count,
                    header_->index_stride)) {
        error_ = "record range exceeds package";
        close();
        return false;
    }
    if((header_->flags & kFlagSourceGroupMetadata) != 0U) {
        const std::uint64_t metadata_offset =
            static_cast<std::uint64_t>(header_->index_offset) +
            static_cast<std::uint64_t>(header_->index_count) *
                header_->index_stride;
        if(metadata_offset > 0xffffffffU ||
           !range_valid(static_cast<std::uint32_t>(metadata_offset),
                        header_->group_count, sizeof(SourceGroup))) {
            error_ = "source group metadata exceeds package";
            close();
            return false;
        }
    }
    if(crc32(data_ + header_->header_size, size_ - header_->header_size) !=
       header_->payload_crc32) {
        error_ = "payload CRC mismatch";
        close();
        return false;
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

const Material* Package::materials() const {
    return reinterpret_cast<const Material*>(data_ + header_->material_offset);
}

const Group* Package::groups() const {
    return reinterpret_cast<const Group*>(data_ + header_->group_offset);
}

const Batch* Package::batches() const {
    return reinterpret_cast<const Batch*>(data_ + header_->batch_offset);
}

const Vertex* Package::vertices() const {
    return reinterpret_cast<const Vertex*>(data_ + header_->vertex_offset);
}

const std::uint32_t* Package::indices() const {
    return reinterpret_cast<const std::uint32_t*>(data_ + header_->index_offset);
}

const SourceGroup* Package::source_groups() const {
    if((header_->flags & kFlagSourceGroupMetadata) == 0U) {
        return nullptr;
    }
    const std::uint32_t offset =
        header_->index_offset + header_->index_count * header_->index_stride;
    return reinterpret_cast<const SourceGroup*>(data_ + offset);
}

} // namespace re4dc::room
