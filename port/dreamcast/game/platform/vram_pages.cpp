// VRAM_PAGES=1 (default off: this file then compiles to nothing and the image is unchanged).
// Replaces KOS's weak pvr_mem_* allocator (dlmalloc over texture RAM, pvr_mem.c) with an
// allocator whose bookkeeping lives in main RAM, so no block header sits in VRAM.
//
// Why: dlmalloc keeps a 4-byte header in front of each block and rounds blocks to 32 bytes,
// so after any earlier block the next address is 32 bytes past a 2 KiB page. UI_VRAM's
// texture_package allocate_texture() wants a VQ texture (codebook) on a 2 KiB page and a
// texture of at most one page inside one page; it therefore re-allocated every VQ texture
// with 2016 bytes of padding: +2048 bytes per resident texture (r100: ~78 textures, 161 KB
// between the cache's accounted bytes and the physical pool).
//
// Placement here: a request of at least one page starts on a page boundary; a smaller one
// never straddles a page (the same rule allocate_texture() checks, so its first allocation
// is always accepted). Best fit over the free extents (least leftover, then lowest address);
// frees coalesce with both neighbours. Everything outside texture RAM is untouched.
// Render only: game state never reads VRAM addresses.
#if RE4DC_VRAM_PAGES
#include <kos.h>
#include <dc/pvr.h>
#include <cstdint>
#include <cstring>
#include "re4dc_platform.h"

namespace {
constexpr std::uint32_t kGran = 32, kPage = 2048;
constexpr unsigned kMaxFree = 256, kMaxAlloc = 512;
struct Extent { std::uint32_t off, len; };      // offsets from base, both multiples of kGran
Extent free_list[kMaxFree]; unsigned nfree;     // sorted by offset, never adjacent
Extent alloc_list[kMaxAlloc]; unsigned nalloc;  // sorted by offset
std::uintptr_t base; std::uint32_t pool, free_bytes;
unsigned fails, peak_alloc, peak_free;

bool insert_at(Extent* list, unsigned& n, unsigned cap, unsigned at, Extent e) {
    if(n >= cap) return false;
    std::memmove(list + at + 1, list + at, (n - at) * sizeof(Extent));
    list[at] = e; ++n; return true;
}
void erase_at(Extent* list, unsigned& n, unsigned at) {
    std::memmove(list + at, list + at + 1, (n - at - 1) * sizeof(Extent)); --n;
}
unsigned lower_bound(const Extent* list, unsigned n, std::uint32_t off) {
    unsigned lo = 0, hi = n;
    while(lo < hi) { const unsigned mid = (lo + hi) / 2; if(list[mid].off < off) lo = mid + 1; else hi = mid; }
    return lo;
}
// Placement offset of `len` bytes in extent e, or ~0 if it does not fit.
std::uint32_t place(const Extent& e, std::uint32_t len) {
    const std::uintptr_t abs = base + e.off;
    std::uintptr_t at = abs;
    if(len >= kPage) at = (abs + kPage - 1) & ~std::uintptr_t(kPage - 1);
    else if((abs & (kPage - 1)) + len > kPage) at = (abs + kPage - 1) & ~std::uintptr_t(kPage - 1);
    const std::uint32_t off = std::uint32_t(at - base);
    return off + len <= e.off + e.len ? off : ~0U;
}
}

extern "C" {
void pvr_mem_initialize(pvr_ptr_t texture_base, size_t available) {
    base = reinterpret_cast<std::uintptr_t>(texture_base);
    pool = std::uint32_t(available) & ~(kGran - 1);
    if(!base) pool = 0;
}
void pvr_mem_reset(void) {
    irq_disable_scoped();
    nalloc = 0; nfree = 0; free_bytes = 0;
    if(base && pool) { free_list[0] = {0, pool}; nfree = 1; free_bytes = pool; }
}
pvr_ptr_t pvr_mem_malloc(size_t size) {
    if(!base || !size || size > pool) { ++fails; return nullptr; }
    const std::uint32_t len = (std::uint32_t(size) + kGran - 1) & ~(kGran - 1);
    irq_disable_scoped();
    unsigned best = ~0U; std::uint32_t best_at = 0, best_left = ~0U;
    for(unsigned i = 0; i < nfree; ++i) {
        const std::uint32_t at = place(free_list[i], len);
        if(at == ~0U) continue;
        const std::uint32_t left = free_list[i].len - len;
        if(left < best_left) { best = i; best_at = at; best_left = left; if(!left) break; }
    }
    if(best == ~0U || nalloc >= kMaxAlloc) { ++fails; return nullptr; }
    const Extent e = free_list[best];
    const Extent front{e.off, best_at - e.off}, back{best_at + len, e.off + e.len - best_at - len};
    // Replace the extent by its non-empty remainders (at most one extra entry).
    if(front.len && back.len) {
        if(nfree >= kMaxFree) { ++fails; return nullptr; }
        free_list[best] = front; insert_at(free_list, nfree, kMaxFree, best + 1, back);
    }
    else if(front.len) free_list[best] = front;
    else if(back.len) free_list[best] = back;
    else erase_at(free_list, nfree, best);
    insert_at(alloc_list, nalloc, kMaxAlloc, lower_bound(alloc_list, nalloc, best_at), Extent{best_at, len});
    free_bytes -= len;
    if(nalloc > peak_alloc) peak_alloc = nalloc;
    if(nfree > peak_free) peak_free = nfree;
    return reinterpret_cast<pvr_ptr_t>(base + best_at);
}
void pvr_mem_free(pvr_ptr_t chunk) {
    if(!chunk || !base) return;
    const std::uint32_t off = std::uint32_t(reinterpret_cast<std::uintptr_t>(chunk) - base);
    irq_disable_scoped();
    const unsigned a = lower_bound(alloc_list, nalloc, off);
    if(a >= nalloc || alloc_list[a].off != off) {
        re4dc_log("vram pages: free of unknown block %08x\n", unsigned(reinterpret_cast<std::uintptr_t>(chunk)));
        return;
    }
    Extent e = alloc_list[a]; erase_at(alloc_list, nalloc, a);
    free_bytes += e.len;
    unsigned i = lower_bound(free_list, nfree, e.off);
    if(i && free_list[i - 1].off + free_list[i - 1].len == e.off) { --i; free_list[i].len += e.len; }
    else if(!insert_at(free_list, nfree, kMaxFree, i, e)) {
        // Cannot happen: a free extent sits between two allocations, so nfree <= nalloc + 1.
        re4dc_log("vram pages: free list full, %u bytes lost\n", e.len); free_bytes -= e.len; return;
    }
    if(i + 1 < nfree && free_list[i].off + free_list[i].len == free_list[i + 1].off) {
        free_list[i].len += free_list[i + 1].len; erase_at(free_list, nfree, i + 1);
    }
}
size_t pvr_mem_available(void) { return base ? free_bytes : 0; }
void pvr_mem_print_list(void) {}
void pvr_mem_stats(void) {}

// VRAM_CENSUS: allocator view for native_ui.cpp.
void re4dc_vram_pages_census(unsigned* out) {
    // out: allocs, alloc_bytes, extents, free_bytes, largest, hist[5] (<2K, <8K, <32K, <128K, >=128K),
    //      fails, peak_alloc, peak_free
    irq_disable_scoped();
    std::uint32_t used = 0, largest = 0; unsigned hist[5] = {0, 0, 0, 0, 0};
    for(unsigned i = 0; i < nalloc; ++i) used += alloc_list[i].len;
    for(unsigned i = 0; i < nfree; ++i) {
        const std::uint32_t l = free_list[i].len;
        if(l > largest) largest = l;
        ++hist[l < 2048 ? 0 : l < 8192 ? 1 : l < 32768 ? 2 : l < 131072 ? 3 : 4];
    }
    out[0] = nalloc; out[1] = used; out[2] = nfree; out[3] = free_bytes; out[4] = largest;
    for(unsigned k = 0; k < 5; ++k) out[5 + k] = hist[k];
    out[10] = fails; out[11] = peak_alloc; out[12] = peak_free;
}
}
#endif
