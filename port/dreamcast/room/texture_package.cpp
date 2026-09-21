#include "texture_package.hpp"

#include <dc/pvr/pvr_mem.h>
#include <dc/pvr/pvr_txr.h>
#include <fcntl.h>

#include <cstring>
#include <cstdlib>

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
    return validate();
}

// R4 5A. The same package, parsed out of memory the caller owns rather than a
// mapping into .rodata, so a room can be read into its arena and released by
// resetting it. The bytes are not copied and are not freed here: the arena owns
// them, and close() only drops this object's view of them.
bool Package::adopt(const std::uint8_t* data, std::size_t size) {
    close();
    if(data == nullptr || size < sizeof(Header)) {
        error_ = "adopted buffer is smaller than the header";
        return false;
    }
    data_ = data;
    size_ = size;
    return validate();
}

// The body of open() as it stood, unchanged, so both paths accept and
// reject exactly the same packages.
bool Package::validate() {
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
        const bool dimensions = texture.width >= 8 && texture.width <= 1024 &&
            texture.height >= 8 && texture.height <= 1024 &&
            (texture.width & (texture.width - 1U)) == 0 &&
            (texture.height & (texture.height - 1U)) == 0;
        // Full 256-entry VQ codebook, no mipmaps or small-codebook pointer bias.
        // Unknown layouts must not fall through as a raw 16-bit upload.
        const std::uint64_t pixels = std::uint64_t(texture.width) * texture.height;
        const std::uint64_t expected = texture.payload == kPayloadVq
            ? 2048U + pixels / 4U : pixels * 2U;
        if(!dimensions || texture.payload > kPayloadVq || texture.reserved_0 != 0 ||
           texture.data_size != expected || texture.format > kArgb4444 ||
           texture.data_offset < header_->data_offset ||
           std::uint64_t(texture.data_offset) + texture.data_size >
               std::uint64_t(header_->data_offset) + header_->data_size ||
           !range_valid(texture.data_offset, texture.data_size)) {
            error_ = "invalid texture dimensions, format, layout or payload size";
            close();
            return false;
        }
    }
    error_ = nullptr;
    return true;
}

std::uint32_t pvr_format(const Texture& texture) {
    const std::uint32_t formats[] = {
        PVR_TXRFMT_RGB565, PVR_TXRFMT_ARGB1555, PVR_TXRFMT_ARGB4444
    };
    return formats[texture.format] |
        (texture.payload == kPayloadVq ? PVR_TXRFMT_VQ_ENABLE : 0U);
}

bool Package::upload() {
    if(header_ == nullptr) {
        error_ = "package is not open";
        return false;
    }
    if(upload_complete_) {
        return true;
    }
    if(pvr_textures_ != nullptr) {
        // A previous attempt allocated but did not finish. Retrying in place
        // would have to know which descriptors already moved their texels,
        // which nothing records, so the only honest answer is to refuse.
        error_ = "previous upload did not complete; close and load again";
        return false;
    }
    pvr_textures_ = static_cast<pvr_ptr_t*>(std::calloc(header_->texture_count, sizeof(pvr_ptr_t)));
    if(pvr_textures_ == nullptr) {
        error_ = "texture pointer allocation failed";
        return false;
    }
    owns_texture_ = static_cast<bool*>(std::calloc(header_->texture_count, sizeof(bool)));
    if(owns_texture_ == nullptr) {
        error_ = "texture ownership allocation failed";
        return false;
    }
    std::uint32_t uploaded = 0;
    for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
        const Texture& texture = textures()[index];

        // R4e: several materials routinely bind the same payload. The
        // converter already stores it once, so two descriptors carry the same
        // data_offset, and the payload at a given offset is by construction
        // the same bytes. Upload it once and let the later descriptors point
        // at the same texture memory.
        bool shared = false;
        for(std::uint32_t earlier = 0; earlier < index; ++earlier) {
            const Texture& candidate = textures()[earlier];
            if(candidate.data_offset == texture.data_offset &&
               candidate.data_size == texture.data_size) {
                pvr_textures_[index] = pvr_textures_[earlier];
                shared = true;
                ++shared_textures_;
                break;
            }
        }
        if(shared) {
            continue;
        }

        pvr_textures_[index] = pvr_mem_malloc(texture.data_size);
        if(pvr_textures_[index] == nullptr) {
            error_ = "PVR texture allocation failed";
            return false;
        }
        owns_texture_[index] = true;
        if(inject_failure_after_ != 0U && uploaded >= inject_failure_after_) {
            error_ = "injected mid-upload failure";
            return false;
        }
        ++uploaded;
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
    upload_complete_ = true;
    error_ = nullptr;
    return true;
}

// Copies the header and the descriptor array out of the adopted bytes and
// points the package at the copy. Everything the runtime asks a texture package
// for after upload -- header(), textures(), find(), pvr_texture() -- reads only
// that prefix, so the texels behind it are free.
//
// Refuses, changing nothing, if the package has not uploaded, if any payload
// would fall inside the prefix (so dropping the rest could not be safe), or if
// the copy cannot be allocated.
bool Package::release_payload() {
    if(payload_released_) {
        return true;
    }
    if(header_ == nullptr || !upload_complete_) {
        error_ = "payload release before a completed upload";
        return false;
    }
    const std::uint64_t descriptor_end =
        static_cast<std::uint64_t>(header_->texture_offset) +
        static_cast<std::uint64_t>(header_->texture_count) *
            header_->texture_stride;
    if(descriptor_end > size_) {
        error_ = "descriptor range outside the package";
        return false;
    }
    const std::size_t prefix = static_cast<std::size_t>(descriptor_end);
    // Every payload must lie beyond the prefix, or the prefix is not a
    // self-contained metadata block and nothing may be dropped.
    for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
        if(textures()[index].data_offset < prefix) {
            error_ = "payload overlaps the metadata prefix";
            return false;
        }
    }
    std::uint8_t* copy = static_cast<std::uint8_t*>(std::malloc(prefix));
    if(copy == nullptr) {
        error_ = "metadata copy allocation failed";
        return false;
    }
    std::memcpy(copy, data_, prefix);
    metadata_ = copy;
    metadata_bytes_ = prefix;
    released_bytes_ = size_;
    payload_released_ = true;
    data_ = copy;
    size_ = prefix;
    header_ = reinterpret_cast<const Header*>(copy);
    // The mapping, if there was one, backed the bytes just copied away.
    if(file_ != FILEHND_INVALID) {
        fs_close(file_);
        file_ = FILEHND_INVALID;
    }
    return true;
}

void Package::close() {
    if(pvr_textures_ != nullptr) {
        if(header_ != nullptr) {
            for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
                // Borrowed pointers are aliases of an owner's allocation;
                // freeing one would be a double free.
                const bool owned =
                    owns_texture_ != nullptr && owns_texture_[index];
                if(owned && pvr_textures_[index] != nullptr) {
                    pvr_mem_free(pvr_textures_[index]);
                }
            }
        }
        std::free(pvr_textures_);
    }
    std::free(owns_texture_);
    owns_texture_ = nullptr;
    pvr_textures_ = nullptr;
    vram_bytes_ = 0;
    shared_textures_ = 0;
    if(file_ != FILEHND_INVALID) {
        fs_close(file_);
    }
    file_ = FILEHND_INVALID;
    std::free(metadata_);
    metadata_ = nullptr;
    metadata_bytes_ = 0;
    released_bytes_ = 0;
    payload_released_ = false;
    upload_complete_ = false;
    inject_failure_after_ = 0;
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
