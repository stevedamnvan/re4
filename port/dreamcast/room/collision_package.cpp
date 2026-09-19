#include "collision_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::collision {
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
    if(header_->vertex_stride != sizeof(Vec3) ||
       header_->normal_stride != sizeof(Vec3) ||
       header_->polygon_stride != sizeof(Polygon)) {
        error_ = "record stride mismatch";
        close();
        return false;
    }
    if(header_->floor_count + header_->slope_count + header_->wall_count !=
           header_->polygon_count ||
       !range_valid(header_->vertex_offset, header_->vertex_count,
                    header_->vertex_stride) ||
       !range_valid(header_->normal_offset, header_->normal_count,
                    header_->normal_stride) ||
       !range_valid(header_->polygon_offset, header_->polygon_count,
                    header_->polygon_stride)) {
        error_ = "collision counts or ranges are invalid";
        close();
        return false;
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

const Vec3* Package::vertices() const {
    return reinterpret_cast<const Vec3*>(data_ + header_->vertex_offset);
}

const Vec3* Package::normals() const {
    return reinterpret_cast<const Vec3*>(data_ + header_->normal_offset);
}

const Polygon* Package::polygons() const {
    return reinterpret_cast<const Polygon*>(data_ + header_->polygon_offset);
}

} // namespace re4dc::collision
