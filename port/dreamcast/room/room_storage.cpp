#include "room_storage.hpp"

#include <kos.h>

#include <cstring>

namespace re4dc::storage {
namespace {

// Bounded so a single read never monopolises the frame. DCA3 uses 64 KiB on the
// same hardware and services audio between chunks; that pacing belongs to the
// asynchronous work, but the bound is worth keeping from the start.
constexpr std::size_t kReadChunkBytes = 64U * 1024U;

// A CD sector. Requests stay a whole number of these while there is more than
// one left, so the ragged end of a file is always its own request.
constexpr std::size_t kSectorBytes = 2048U;

// Deliberately not 32-byte aligned: that is what steers KOS away from its
// streaming path. Only ever holds one package smaller than kReadChunkBytes.
alignas(32) std::uint8_t g_small_file_bounce[kReadChunkBytes + 32U];
std::uint8_t* small_file_buffer() { return g_small_file_bounce + 16U; }

std::size_t align_up(std::size_t value) {
    return (value + (kArenaAlignment - 1U)) & ~(kArenaAlignment - 1U);
}

} // namespace

void Arena::init(std::uint8_t* base, std::size_t capacity) {
    base_ = base;
    capacity_ = capacity;
    used_ = 0;
    high_water_ = 0;
    resets_ = 0;
}

std::uint8_t* Arena::allocate(std::size_t bytes) {
    if(base_ == nullptr || bytes == 0) {
        return nullptr;
    }
    const std::size_t padded = align_up(bytes);
    if(padded < bytes || padded > capacity_ - used_) {
        return nullptr;
    }
    std::uint8_t* result = base_ + used_;
    used_ += padded;
    if(used_ > high_water_) {
        high_water_ = used_;
    }
    return result;
}

void Arena::reset() {
    used_ = 0;
    ++resets_;
}

void Arena::rewind(std::size_t mark) {
    if(mark <= used_) {
        used_ = mark;
    }
}

ReadResult read_file(Arena& arena, const char* path) {
    ReadResult result{};
    const std::size_t mark = arena.mark();
    const std::uint32_t started = timer_us_gettime64() & 0xffffffffU;

    file_t handle = fs_open(path, O_RDONLY);
    if(handle == FILEHND_INVALID) {
        result.error = "open failed";
        return result;
    }
    const ssize_t total = fs_total(handle);
    if(total <= 0) {
        fs_close(handle);
        result.error = "empty or unsized file";
        return result;
    }
    const std::size_t size = static_cast<std::size_t>(total);
    std::uint8_t* buffer = arena.allocate(size);
    if(buffer == nullptr) {
        fs_close(handle);
        result.error = "room arena exhausted";
        return result;
    }

    // See small_file_buffer(): a package this small is read through the block
    // cache and copied, because the streaming path does not return for it.
    const bool via_bounce = size < kReadChunkBytes;
    std::uint8_t* const target = via_bounce ? small_file_buffer() : buffer;

    std::size_t done = 0;
    while(done < size) {
        const std::size_t remaining = size - done;
        std::size_t want =
            remaining < kReadChunkBytes ? remaining : kReadChunkBytes;
        if(want > kSectorBytes && (want % kSectorBytes) != 0) {
            want -= want % kSectorBytes;
        }
        const ssize_t got = fs_read(handle, target + done, want);
        if(got < 0) {
            fs_close(handle);
            arena.rewind(mark);
            result.error = "read error";
            return result;
        }
        if(got == 0) {
            // End of file before the declared length: a truncated package must
            // never reach a parser.
            fs_close(handle);
            arena.rewind(mark);
            result.error = "unexpected end of file";
            return result;
        }
        done += static_cast<std::size_t>(got);
    }
    fs_close(handle);
    if(via_bounce) {
        std::memcpy(buffer, target, size);
    }

    result.data = buffer;
    result.size = size;
    result.read_us = (timer_us_gettime64() & 0xffffffffU) - started;
    return result;
}

} // namespace re4dc::storage
