#ifndef RE4DC_ROOM_STORAGE_HPP
#define RE4DC_ROOM_STORAGE_HPP

#include <cstddef>
#include <cstdint>
#include <kos/fs.h>

// Explicitly owned storage for everything a room brings in.
//
// Until R4 deliverable 5A every package was memory-mapped out of a romdisk
// linked into .rodata, so no room byte could ever be released. Room-owned
// packages now come off the disc into this arena instead, and retiring the room
// returns the whole region in one operation. That is the lifetime the original
// game gives its room heap: gameRoomMemInit re-carves it from its parent before
// ReadAreaData loads the next room, rather than freeing resource by resource.
namespace re4dc::storage {

// Every package the runtime casts over expects at least 4-byte alignment, and
// the texture upload path copies through the store queue, which wants 32.
inline constexpr std::size_t kArenaAlignment = 32U;

class Arena {
public:
    void init(std::uint8_t* base, std::size_t capacity);

    // Bump-allocates `bytes`, aligned, or returns nullptr when the arena is
    // full. Never partially succeeds.
    std::uint8_t* allocate(std::size_t bytes);

    // Returns the arena to empty. The capacity becomes reusable; the memory is
    // not returned to the general heap, and is not meant to be.
    void reset();

    // Unwinds back to a mark taken before a group of allocations, so a failed
    // load leaves no residue.
    std::size_t mark() const { return used_; }
    void rewind(std::size_t mark);

    std::uint8_t* base() const { return base_; }
    std::size_t used() const { return used_; }
    std::size_t capacity() const { return capacity_; }
    std::size_t available() const { return capacity_ - used_; }

    // Peak usage across every cycle so far, which is the number that sizes the
    // arena rather than any single load.
    std::size_t high_water() const { return high_water_; }
    std::uint32_t resets() const { return resets_; }

private:
    std::uint8_t* base_ = nullptr;
    std::size_t capacity_ = 0;
    std::size_t used_ = 0;
    std::size_t high_water_ = 0;
    std::uint32_t resets_ = 0;
};

struct ReadResult {
    const std::uint8_t* data = nullptr;
    std::size_t size = 0;
    const char* error = nullptr;
    std::uint32_t read_us = 0;
};

// Reads a whole file into the arena with a bounded chunk size, tolerating short
// reads and refusing a truncated one. On any failure the arena is rewound to
// where it started, so a caller can retry without leaking capacity.
ReadResult read_file(Arena& arena, const char* path);

// Synchronous, bounded transport over the existing shared bounce buffer.
// The recovered game uses 16 KiB; the room target retains its 64 KiB default.
// The callback must consume bytes before returning; it cannot retain the buffer
// or re-enter either reader. File position advances; caller owns the handle.
using ChunkConsumer = bool (*)(const std::uint8_t*, std::size_t, void*);
bool read_chunks(file_t file, std::size_t bytes, ChunkConsumer consume, void* context);
bool read_exact(file_t file, void* destination, std::size_t bytes);
// One <=64KiB aligned streaming chunk. Caller owns an open, sector-positioned
// file and 32-byte-aligned destination; size must be a multiple of32. Reuses
// ReaderGuard; no second reader/cache or whole-file allocation. A short final
// non-aligned tail belongs to read_exact(). Failure never reports completion.
bool read_aligned_chunk(file_t file, void* destination, std::size_t bytes);

} // namespace re4dc::storage

#endif
