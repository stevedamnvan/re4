#include "texture_package.hpp"
#include "room_storage.hpp"

#include <dc/pvr/pvr_mem.h>
#include <dc/pvr/pvr_txr.h>
#include <fcntl.h>

#include <cstring>
#include <cstdlib>

// Game PVR_PIPELINE=1 lets the PVR render the previous scene while the CPU
// continues; its frame owner waits for that render before VRAM is freed or
// overwritten. Other builds (room tool, default game) compile nothing here.
#ifndef RE4DC_PVR_PIPELINE
#define RE4DC_PVR_PIPELINE 0
#endif
#if RE4DC_PVR_PIPELINE
extern "C" void re4dc_pvr_vram_fence();
#endif

namespace re4dc::texture {
namespace {
inline void vram_fence() {
#if RE4DC_PVR_PIPELINE
    re4dc_pvr_vram_fence();
#endif
}

std::uint32_t crc_update(std::uint32_t crc, const std::uint8_t* data, std::size_t size) {
    for(std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for(unsigned bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1U) ^ (0xedb88320U & mask);
        }
    }
    return crc;
}
std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    return ~crc_update(0xffffffffU,data,size);
}

// Store queues copy complete 32-byte units. Full-codebook 8x8 VQ has
// a 16-byte tail; pad only the transfer, within PVR allocator alignment.
void upload_native(const std::uint8_t* src, void* destination, std::size_t bytes) {
    const std::size_t bulk=bytes&~std::size_t(31);
    if(bulk) pvr_txr_load(src,destination,bulk);
    if(bytes!=bulk) {
        alignas(32) std::uint8_t tail[32]{};
        std::memcpy(tail,src+bulk,bytes-bulk);
        pvr_txr_load(tail,static_cast<std::uint8_t*>(destination)+bulk,32);
    }
}

#ifndef RE4DC_UI_VRAM
#define RE4DC_UI_VRAM 0
#endif
#if RE4DC_UI_VRAM
// Game UI_VRAM=1. PVR texture RAM is paged in 2 KiB units (Sega hardware
// notes): a full VQ codebook (exactly 2 KiB) is placed on a page boundary and
// a texture of at most one page never straddles two. The allocator only
// guarantees 32 bytes, so re-place such a texture inside a block padded by one
// page less 32 bytes; if that block is unavailable keep the plain one (layout,
// not correctness). pvr_textures_ then holds count sampled pointers followed
// by count allocation bases (what pvr_mem_free() must receive); the class
// layout is unchanged, so translation units built without the knob agree.
pvr_ptr_t allocate_texture(std::size_t bytes, bool vq, pvr_ptr_t& base) {
    constexpr std::uintptr_t kPage = 2048;
    base = pvr_mem_malloc(bytes);
    if(base == nullptr) return nullptr;
    const std::uintptr_t start = reinterpret_cast<std::uintptr_t>(base);
    const bool placed = vq ? (start & (kPage - 1U)) == 0 :
        bytes > kPage || (start & (kPage - 1U)) + bytes <= kPage;
    if(placed) return base;
    pvr_mem_free(base);
    base = pvr_mem_malloc(bytes + kPage - 32U);
    if(base == nullptr) {
        base = pvr_mem_malloc(bytes);
        return base;
    }
    return reinterpret_cast<pvr_ptr_t>(
        (reinterpret_cast<std::uintptr_t>(base) + kPage - 1U) & ~(kPage - 1U));
}
#endif
} // namespace

namespace {
unsigned word(const std::uint8_t* p) { unsigned v; std::memcpy(&v,p,4); return v; }
unsigned half(const std::uint8_t* p) { std::uint16_t v; std::memcpy(&v,p,2); return v; }
}

bool SourceIdentityTable::adopt(const void* archive, std::size_t bytes) {
    clear();
    if(!archive || bytes < 16) return false;
    auto* data = static_cast<const std::uint8_t*>(archive);
    const unsigned slots=word(data);
    if(slots > (bytes-16)/8) return false;
    const std::uint8_t* native=nullptr;
    std::size_t native_bytes=0;
    for(unsigned i=0;i<slots;++i) {
        if(std::memcmp(data+16+4*slots+4*i,"NTR",4)) continue;
        const unsigned off=word(data+16+4*i);
        if(native || off>bytes || bytes-off<32) return false;
        native=data+off;native_bytes=bytes-off;
    }
    if(!native) return true; // original qualified archive stays selectable
    if(std::memcmp(native,"R4NTBL\0",8) || word(native+8)!=1 || word(native+16)!=12 ||
       word(native+28)!=bytes || word(native+24)<=bytes) return false;
    const unsigned count=word(native+12);
    if(!count || count>(native_bytes-32)/12 || count>1024 ||
       crc32(native+32,count*12)!=word(native+20)) return false;
    for(unsigned i=0;i<count;++i) {
        const auto* entry=native+32+i*12;
        const unsigned record=word(entry),header=word(entry+4),tpl=word(entry+8);
        if(record>bytes-32 || header>bytes-36 || tpl>bytes-12 ||
           (record&31) || (header&3) || (tpl&3)) return false;
        const auto* p=data+record;const auto* h=data+header;
        const unsigned w=word(p+16),ht=word(p+20),fmt=word(p+24);
        const bool indexed=!std::memcmp(p,"R4PREF\0",8);
        if(indexed) {
            if(record>bytes-64 || (fmt!=8 && fmt!=9) || word(p+32)>2 ||
               !word(p+36) || (word(p+36)&1) || word(p+36)>(fmt==8?32U:512U) ||
               word(p+28)<64 || word(p+48) || word(p+52) || word(p+56) || word(p+60))return false;
        }
        if((!indexed && (std::memcmp(p,"R4NREF\0",8) || (fmt>6 && fmt!=14))) || !w || !ht || w>1024 || ht>1024 ||
           // minLOD 0 only: the native package is the base level. A max LOD
           // is a whole externalized chain (--compact-room-mips); the Dreamcast
           // renderer samples the base level and never reads source texels.
           h[33] || (h[34] && indexed) || h[35] ||
           w!=half(h+2) || ht!=half(h) || fmt!=word(h+4) ||
           std::uint64_t(tpl)+word(h+8)!=record) return false;
    }
    data_=data;bytes_=bytes;table_=native+32;count_=count;
    return true;
}

#ifndef RE4DC_TEX_RESIDENT
#define RE4DC_TEX_RESIDENT 0
#endif
#ifndef RE4DC_TEX_PAYLOAD_CRC
#define RE4DC_TEX_PAYLOAD_CRC 0
#endif
#if RE4DC_TEX_RESIDENT
bool SourceIdentityTable::record(unsigned index,unsigned& crc,unsigned& fnv,unsigned& width,unsigned& height,unsigned& format) const {
    if(!data_ || index>=count_) return false;
    const auto start=word(table_+12*index);
    if(std::uint64_t(start)+32>bytes_) return false;
    const auto* p=data_+start;
    crc=word(p+8);fnv=word(p+12);width=word(p+16);height=word(p+20);format=word(p+24);
    return true;
}
#endif
int SourceIdentityTable::lookup(const void* pixels,unsigned width,unsigned height,unsigned format,
                                  unsigned& crc,unsigned& fnv,const void* palette,unsigned palette_format,unsigned palette_bytes) const {
    const auto address=reinterpret_cast<std::uintptr_t>(pixels);
    const auto base=reinterpret_cast<std::uintptr_t>(data_);
    if(!data_ || address<base || address-base>=bytes_) return false;
    const auto offset=address-base;
    for(unsigned i=0;i<count_;++i) {
        const auto start=word(table_+12*i);
        const bool indexed=!std::memcmp(data_+start,"R4PREF\0",8);
        if(offset<start || offset-start>=(indexed?64U:32U)) continue;
        if(offset!=start) return -1;
        const auto* p=data_+offset;
        if(word(p+16)!=width || word(p+20)!=height || word(p+24)!=format) return -1;
        if(indexed) {
            if(!palette || palette_format!=word(p+32) || palette_bytes!=word(p+36))return -1;
            auto* bytes=static_cast<const std::uint8_t*>(palette);unsigned fingerprint=2166136261U;
            for(unsigned j=0;j<palette_bytes;++j)fingerprint=(fingerprint^bytes[j])*16777619U;
            if(fingerprint!=word(p+44) || crc32(bytes,palette_bytes)!=word(p+40))return -1;
        } else if(palette || palette_bytes)return -1;
        crc=word(p+8);fnv=word(p+12);return true;
    }
    return false;
}

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

bool Package::open_streamed(const char* path) {
    close();
    file_ = fs_open(path,O_RDONLY);
    if(file_ == FILEHND_INVALID) { error_="open failed"; return false; }
    const ssize_t total=fs_total(file_);
    Header h{};
    if(total < static_cast<ssize_t>(sizeof(h)) || !storage::read_exact(file_,&h,sizeof(h))) {
        error_="streamed header read failed";close();return false;
    }
    // Bound metadata before trusting offsets/counts. Prepared native packages
    // place the descriptor table directly after the header; no texel overlap.
    const std::uint64_t prefix=std::uint64_t(h.texture_offset)+std::uint64_t(h.texture_count)*sizeof(Texture);
    if(std::memcmp(h.magic,kMagic,8) || h.version!=kVersion || h.header_size!=sizeof(h) ||
       h.texture_stride!=sizeof(Texture) || h.texture_offset!=sizeof(h) ||
       !h.texture_count || prefix>64*1024 || prefix>std::uint64_t(total) || h.data_offset<prefix) {
        error_="invalid streamed metadata layout";close();return false;
    }
    size_=static_cast<std::size_t>(total);
    metadata_bytes_=static_cast<std::size_t>(prefix);
    metadata_=static_cast<std::uint8_t*>(std::malloc(metadata_bytes_));
    if(!metadata_) { error_="streamed metadata allocation failed";close();return false; }
    std::memcpy(metadata_,&h,sizeof(h));
    if(!storage::read_exact(file_,metadata_+sizeof(h),metadata_bytes_-sizeof(h))) {
        error_="streamed descriptor read failed";close();return false;
    }
    data_=metadata_;streamed_=true;
    if(!validate()) return false;
    for(unsigned i=0;i<header_->texture_count;++i) {
        if(textures()[i].payload==kPayloadLinear) {
            error_="streamed upload requires native texture layout";close();return false;
        }
    }
#if RE4DC_TEX_RESIDENT && !RE4DC_TEX_PAYLOAD_CRC
    // TEX_RESIDENT: no payload CRC pass on the render thread (it read the whole
    // file a second time through a bit-serial CRC: tens of ms per texture). The
    // payload CRC is verified when the disc is staged (tools/d367/stage.sh);
    // the header and every descriptor were validated above. TEX_PAYLOAD_CRC=1
    // restores the runtime check for debugging.
    error_=nullptr;return true;
#endif
    // Validate once before any VRAM allocation or publishing this package.
    std::uint32_t crc=0xffffffffU;
    if(fs_seek(file_,sizeof(Header),SEEK_SET)!=sizeof(Header) ||
       !storage::read_chunks(file_,size_-sizeof(Header),[](const std::uint8_t* p,std::size_t n,void* ctx) {
           auto& c=*static_cast<std::uint32_t*>(ctx);c=crc_update(c,p,n);return true;
       },&crc) || ~crc!=header_->payload_crc32) {
        error_="streamed payload read or CRC mismatch";close();return false;
    }
    error_=nullptr;return true;
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
    if(!streamed_ && crc32(data_ + header_->header_size, size_ - header_->header_size) !=
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
    vram_fence();
#if RE4DC_UI_VRAM
    pvr_textures_ = static_cast<pvr_ptr_t*>(std::calloc(2U * header_->texture_count, sizeof(pvr_ptr_t)));
#else
    pvr_textures_ = static_cast<pvr_ptr_t*>(std::calloc(header_->texture_count, sizeof(pvr_ptr_t)));
#endif
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

#if RE4DC_UI_VRAM
        pvr_textures_[index] = allocate_texture(texture.data_size,
            texture.payload == kPayloadVq, pvr_textures_[header_->texture_count + index]);
#else
        pvr_textures_[index] = pvr_mem_malloc(texture.data_size);
#endif
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
        if(streamed_) {
            auto* target=static_cast<std::uint8_t*>(pvr_textures_[index]);
            if(fs_seek(file_,texture.data_offset,SEEK_SET)!=static_cast<off_t>(texture.data_offset) ||
               !storage::read_chunks(file_,texture.data_size,[](const std::uint8_t* src,std::size_t n,void* ctx) {
                   auto*& dst=*static_cast<std::uint8_t**>(ctx);
                   upload_native(src,dst,n);dst+=n;return true;
               },&target)) {
                error_="streamed texture upload read failed";return false;
            }
        } else if(texture.payload == kPayloadLinear) {
            // Legacy layout: the PVR cannot consume it, so it is reordered
            // here during upload.
            pvr_txr_load_ex(data_ + texture.data_offset, pvr_textures_[index],
                            texture.width, texture.height, PVR_TXRLOAD_16BPP);
        } else {
            // Already in the layout the PVR expects; copy it straight in.
            upload_native(data_ + texture.data_offset, pvr_textures_[index],
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
    if(streamed_) {
        // No whole-file CPU payload was allocated: do not count it as freed.
        fs_close(file_);file_=FILEHND_INVALID;
        size_=metadata_bytes_;payload_released_=true;return true;
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
        vram_fence();
        if(header_ != nullptr) {
            for(std::uint32_t index = 0; index < header_->texture_count; ++index) {
                // Borrowed pointers are aliases of an owner's allocation;
                // freeing one would be a double free.
                const bool owned =
                    owns_texture_ != nullptr && owns_texture_[index];
#if RE4DC_UI_VRAM
                if(owned && pvr_textures_[header_->texture_count + index] != nullptr) {
                    pvr_mem_free(pvr_textures_[header_->texture_count + index]);
                }
#else
                if(owned && pvr_textures_[index] != nullptr) {
                    pvr_mem_free(pvr_textures_[index]);
                }
#endif
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
    streamed_ = false;
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
