#include "route_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::route {
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
    const std::uint64_t expected_next =
        static_cast<std::uint64_t>(header_->point_count) *
        header_->point_count;
    if(header_->point_count > 127U ||
       header_->point_stride != sizeof(Point) ||
       header_->link_stride != sizeof(Link) ||
       expected_next != header_->next_count ||
       !range_valid(header_->point_offset, header_->point_count,
                    header_->point_stride) ||
       !range_valid(header_->link_offset, header_->link_count,
                    header_->link_stride) ||
       !range_valid(header_->next_offset, header_->next_count, 1U)) {
        error_ = "route counts, strides, or ranges are invalid";
        close();
        return false;
    }
    for(std::uint32_t index = 0; index < header_->point_count; ++index) {
        const Point& point = points()[index];
        if(static_cast<std::uint32_t>(point.first_link) + point.link_count >
           header_->link_count) {
            error_ = "route point link range is invalid";
            close();
            return false;
        }
    }
    for(std::uint32_t index = 0; index < header_->link_count; ++index) {
        if(links()[index].point < 0 ||
           static_cast<std::uint32_t>(links()[index].point) >=
               header_->point_count) {
            error_ = "route link target is invalid";
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

const Point* Package::points() const {
    return reinterpret_cast<const Point*>(data_ + header_->point_offset);
}

const Link* Package::links() const {
    return reinterpret_cast<const Link*>(data_ + header_->link_offset);
}

const std::int8_t* Package::next_hops() const {
    return reinterpret_cast<const std::int8_t*>(data_ + header_->next_offset);
}

std::int8_t Package::next(std::uint32_t from, std::uint32_t to) const {
    if(from >= header_->point_count || to >= header_->point_count) {
        return -1;
    }
    return next_hops()[header_->point_count * from + to];
}

} // namespace re4dc::route
