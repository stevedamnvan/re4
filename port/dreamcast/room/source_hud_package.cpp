#include "source_hud_package.hpp"

#include <fcntl.h>

#include <cstring>

namespace re4dc::hud {
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

bool Package::range_valid(std::uint32_t offset, std::uint32_t size) const {
    return offset >= sizeof(Header) &&
           static_cast<std::uint64_t>(offset) + size <= size_;
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
    const std::uint64_t unit_bytes =
        static_cast<std::uint64_t>(header_->unit_count) * header_->unit_stride;
    if(std::memcmp(header_->magic, kMagic, sizeof(kMagic)) != 0 ||
       header_->version != kVersion || header_->header_size != sizeof(Header) ||
       header_->unit_stride != sizeof(Unit) || unit_bytes > 0xffffffffU ||
       !range_valid(header_->unit_offset,
                    static_cast<std::uint32_t>(unit_bytes)) ||
       header_->frame_start + header_->frame_count > header_->unit_count ||
       header_->life_start + header_->life_count > header_->unit_count ||
       header_->bullet_start + header_->bullet_count > header_->unit_count) {
        error_ = "magic, version, stride, or range mismatch";
        close();
        return false;
    }
    if(crc32(data_ + header_->unit_offset,
             static_cast<std::size_t>(unit_bytes)) != header_->payload_crc32) {
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

const Unit* Package::units() const {
    return reinterpret_cast<const Unit*>(data_ + header_->unit_offset);
}

} // namespace re4dc::hud
