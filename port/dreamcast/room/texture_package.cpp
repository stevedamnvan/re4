#include "texture_package.hpp"

#include <dc/pvr/pvr_mem.h>
#include <dc/pvr/pvr_txr.h>
#include <fcntl.h>

#include <cstring>
#include <new>

namespace re4dc::texture {
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
    if(std::memcmp(header_->magic, kMagic, sizeof(kMagic)) != 0 ||
       header_->version != kVersion || header_->header_size != sizeof(Header)) {
        error_ = "magic, version, or header size mismatch";
        close();
        return false;
    }
    const std::uint64_t descriptor_bytes =
        static_cast<std::uint64_t>(header_->texture_count) * header_->texture_stride;
    if(header_->texture_stride != sizeof(Texture) ||
       descriptor_bytes > 0xffffffffU ||
       !range_valid(header_->texture_offset,
                    static_cast<std::uint32_t>(descriptor_bytes)) ||
       !range_valid(header_->data_offset, header_->data_size)) {
        error_ = "texture package range or stride mismatch";
        close();
        return false;
    }
    if(crc32(data_ + header_->header_size, size_ - header_->header_size) !=
       header_->payload_crc32) {
        error_ = "payload CRC mismatch";
        close();
        return false;
    }
    for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
        const Texture& texture = textures()[index];
        if(texture.width == 0 || texture.height == 0 ||
           texture.data_size != texture.width * texture.height * 2U ||
           texture.format > kArgb4444 ||
           !range_valid(texture.data_offset, texture.data_size)) {
            error_ = "invalid texture descriptor";
            close();
            return false;
        }
    }
    error_ = nullptr;
    return true;
}

bool Package::upload() {
    if(header_ == nullptr) {
        error_ = "package is not open";
        return false;
    }
    if(pvr_textures_ != nullptr) {
        return true;
    }
    pvr_textures_ = new(std::nothrow) pvr_ptr_t[header_->texture_count]{};
    if(pvr_textures_ == nullptr) {
        error_ = "texture pointer allocation failed";
        return false;
    }
    for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
        const Texture& texture = textures()[index];
        pvr_textures_[index] = pvr_mem_malloc(texture.data_size);
        if(pvr_textures_[index] == nullptr) {
            error_ = "PVR texture allocation failed";
            return false;
        }
        if(texture.payload == kPayloadLinear) {
            // Legacy layout: the PVR cannot consume it, so it is reordered
            // here during upload.
            pvr_txr_load_ex(data_ + texture.data_offset, pvr_textures_[index],
                            texture.width, texture.height, PVR_TXRLOAD_16BPP);
        } else {
            // Already in the layout the PVR expects; copy it straight in.
            pvr_txr_load(data_ + texture.data_offset, pvr_textures_[index],
                         texture.data_size);
        }
        vram_bytes_ += texture.data_size;
    }
    error_ = nullptr;
    return true;
}

void Package::close() {
    if(pvr_textures_ != nullptr) {
        if(header_ != nullptr) {
            for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
                if(pvr_textures_[index] != nullptr) {
                    pvr_mem_free(pvr_textures_[index]);
                }
            }
        }
        delete[] pvr_textures_;
    }
    pvr_textures_ = nullptr;
    vram_bytes_ = 0;
    if(file_ != FILEHND_INVALID) {
        fs_close(file_);
    }
    file_ = FILEHND_INVALID;
    data_ = nullptr;
    size_ = 0;
    header_ = nullptr;
}

const Texture* Package::textures() const {
    return reinterpret_cast<const Texture*>(data_ + header_->texture_offset);
}

const Texture* Package::find(const char* material) const {
    for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
        if(std::strncmp(textures()[index].material, material,
                        sizeof(textures()[index].material)) == 0) {
            return &textures()[index];
        }
    }
    return nullptr;
}

pvr_ptr_t Package::pvr_texture(std::uint32_t index) const {
    if(pvr_textures_ == nullptr || index >= header_->texture_count) {
        return nullptr;
    }
    return pvr_textures_[index];
}

} // namespace re4dc::texture
