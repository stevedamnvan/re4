// D367 W11 (SUBSCREEN=1): Dreamcast storage behind the sub screen's GameCube ARAM swap.
// sscrn_bridge.cpp decides what to keep; this file only owns the KOS side:
//  - the backing store, two linear VRAM segments used in order:
//      1. the second TA vertex bank (32-bit area 0x400000 + TA_VERTBUF_KB KiB). pvr_init()
//         allocates two banks, but with TA_DOUBLEBUF=0 (vbuf_doublebuf_disabled) the TA
//         target never leaves bank 0, so bank 1's vertex buffer is never read or written;
//      2. texture-pool blocks (pvr_mem_malloc, at most kMaxBlocks, halving the request when the
//         pool is fragmented) for the remainder, freed at close. When the pool is short, the
//         least recently used native UI uploads that the current scene does not reference are
//         released first (re4dc_ui_reclaim_one; the world is not drawn while the sub screen
//         opens and they reload on demand after it closes).
//    The data never reaches the PVR, so no render fence is involved.
//  - whole-file disc reads for the sub screen's own files (ss_cmmn / ss_pzzl);
//  - a microsecond clock for the open/close cost lines.
#if RE4DC_SUBSCREEN || RE4DC_W11_FIXTURE  // (subscreen.mk; empty in the default image)
#include <kos.h>
#include <fcntl.h>
#include <cctype>
#include <cstdio>
#include <cstring>

#include "re4dc_platform.h"
#include "native_io.h"

#ifndef RE4DC_TA_VERTBUF_KB
#define RE4DC_TA_VERTBUF_KB 1024
#endif
#ifndef RE4DC_TA_DOUBLEBUF
#define RE4DC_TA_DOUBLEBUF 0
#endif
#if RE4DC_SUBSCREEN && RE4DC_TA_DOUBLEBUF
#error SUBSCREEN=1 stores the sub screen backing in the TA bank that TA_DOUBLEBUF=1 uses
#endif

extern "C" int re4dc_dvd_native_path(const char* name, char* output, unsigned capacity);
extern "C" unsigned re4dc_ui_reclaim_one();
// TEX_RESIDENT builds (native_ui.cpp): empties the pool of unreferenced uploads until one block
// fits and holds the room preload until the matching unclaim. Weak: absent in other builds.
extern "C" int re4dc_ui_vram_claim(unsigned bytes) __attribute__((weak));
extern "C" void re4dc_ui_vram_unclaim() __attribute__((weak));

namespace {
constexpr unsigned kBankOffset = 0x400000;  // pvr_allocate_buffers(): bank 1 starts half way
constexpr unsigned kBankBytes = RE4DC_TA_VERTBUF_KB * 1024U;
volatile unsigned* const kBank = reinterpret_cast<volatile unsigned*>(PVR_RAM_BASE + kBankOffset);
constexpr unsigned kMaxBlocks = 16, kMinBlock = 32 * 1024;
struct Store {
    bool open;
    unsigned bytes, bank_bytes, pool_bytes;
    pvr_ptr_t block[kMaxBlocks];
    unsigned block_bytes[kMaxBlocks], nblock;
    unsigned cursor;  // byte position of the next put/get
    unsigned reclaimed_bytes, reclaimed_uploads;
    bool claimed;
};
Store store{};

// The segment holding byte `position` and the bytes left in it from there.
volatile unsigned* word_at(unsigned position, unsigned* run)
{
    if (position < store.bank_bytes) {
        *run = store.bank_bytes - position;
        return kBank + position / 4;
    }
    unsigned at = position - store.bank_bytes;
    for (unsigned i = 0; i < store.nblock; ++i) {
        if (at < store.block_bytes[i]) {
            *run = store.block_bytes[i] - at;
            return reinterpret_cast<volatile unsigned*>(reinterpret_cast<char*>(store.block[i]) + at);
        }
        at -= store.block_bytes[i];
    }
    re4dc_missing("subscreen backing: position outside the store");
    return nullptr;
}

void free_blocks()
{
    for (unsigned i = 0; i < store.nblock; ++i) pvr_mem_free(store.block[i]);
    store.nblock = 0;
}
}

extern "C" {

// Reserves `bytes` (a multiple of 4) of backing: bank 1 first, then a pool block.
int re4dc_ssb_open(unsigned bytes, unsigned* bank_bytes, unsigned* pool_bytes)
{
    if (store.open) {
        re4dc_log("subscreen backing: already open\n");
        return 0;
    }
    store = Store{};
    store.bytes = bytes;
    store.bank_bytes = bytes < kBankBytes ? bytes : kBankBytes;
    store.pool_bytes = bytes - store.bank_bytes;
    unsigned need = store.pool_bytes;
    store.claimed = need && re4dc_ui_vram_claim;
    if (store.claimed) re4dc_ui_vram_claim(need);
    while (need) {
        if (store.nblock == kMaxBlocks) {
            re4dc_log("subscreen backing: %u blocks cannot hold %u B (short %u)\n", kMaxBlocks, store.pool_bytes, need);
            free_blocks();
            if (store.claimed) re4dc_ui_vram_unclaim();
            return 0;
        }
        // Largest block the pool gives now, down to kMinBlock (or the remainder).
        unsigned ask = (need + 31) & ~31U;
        pvr_ptr_t p = nullptr;
        while (!(p = pvr_mem_malloc(ask)) && ask > kMinBlock) ask = ((ask / 2) + 31) & ~31U;
        if (p) {
            const unsigned got = ask < need ? ask : need;
            store.block[store.nblock] = p;
            store.block_bytes[store.nblock++] = got;
            need -= got;
            continue;
        }
        const unsigned freed = re4dc_ui_reclaim_one();
        if (!freed) {
            re4dc_log("subscreen backing: texture pool short by %u B (free %u, blocks %u) after releasing %u uploads\n",
                      need, (unsigned) pvr_mem_available(), store.nblock, store.reclaimed_uploads);
            free_blocks();
            if (store.claimed) re4dc_ui_vram_unclaim();
            return 0;
        }
        store.reclaimed_bytes += freed;
        ++store.reclaimed_uploads;
    }
    store.open = true;
    *bank_bytes = store.bank_bytes;
    *pool_bytes = store.pool_bytes;
    return 1;
}

void re4dc_ssb_rewind() { store.cursor = 0; }

// Appends `bytes` (multiple of 4, `src` 4-aligned) at the cursor.
void re4dc_ssb_put(const void* src, unsigned bytes)
{
    const unsigned* s = static_cast<const unsigned*>(src);
    if (!store.open || store.cursor + bytes > store.bytes) re4dc_missing("subscreen backing overrun");
    while (bytes) {
        unsigned run;
        volatile unsigned* d = word_at(store.cursor, &run);
        if (run > bytes) run = bytes;
        for (unsigned n = run / 4; n; --n) *d++ = *s++;
        store.cursor += run;
        bytes -= run;
    }
}

// Reads `bytes` at the cursor.
void re4dc_ssb_get(void* dst, unsigned bytes)
{
    unsigned* d = static_cast<unsigned*>(dst);
    if (!store.open || store.cursor + bytes > store.bytes) re4dc_missing("subscreen backing underrun");
    while (bytes) {
        unsigned run;
        const volatile unsigned* s = word_at(store.cursor, &run);
        if (run > bytes) run = bytes;
        for (unsigned n = run / 4; n; --n) *d++ = *s++;
        store.cursor += run;
        bytes -= run;
    }
}

void re4dc_ssb_close()
{
    free_blocks();
    if (store.claimed) re4dc_ui_vram_unclaim();
    store = Store{};
}

// Pool blocks in use and native UI uploads released by the last open.
void re4dc_ssb_stats(unsigned* blocks, unsigned* reclaimed_uploads, unsigned* reclaimed_bytes)
{
    *blocks = store.nblock;
    *reclaimed_uploads = store.reclaimed_uploads;
    *reclaimed_bytes = store.reclaimed_bytes;
}

unsigned re4dc_ssb_pool_free() { return (unsigned) pvr_mem_available(); }
unsigned re4dc_ssb_bank_bytes() { return kBankBytes; }
unsigned long long re4dc_ssb_us() { return timer_us_gettime64(); }

// The disc path the source DVD layer would open for `name` ("SS/eng/ss_cmmn.dat").
static bool disc_path(const char* name, char* full, unsigned capacity)
{
    char rel[64];
    unsigned i = 0;
    while (*name == '/' || *name == '\\') ++name;
    for (; *name && i + 1 < sizeof(rel); ++name) rel[i++] = char(std::tolower((unsigned char) (*name == '\\' ? '/' : *name)));
    rel[i] = 0;
    return re4dc_dvd_native_path(rel, full, capacity);
}

long re4dc_ssb_file_size(const char* name)
{
    char full[96];
    if (!disc_path(name, full, sizeof(full))) return -1;
    Re4dcIoScope io;
    file_t f = fs_open(full, O_RDONLY);
    if (f < 0) return -1;
    const long size = (long) fs_total(f);
    fs_close(f);
    return size;
}

// Whole-file read into `dst` (at most `capacity` bytes). Returns the bytes read or -1.
long re4dc_ssb_file_read(const char* name, void* dst, unsigned capacity)
{
    char full[96];
    if (!disc_path(name, full, sizeof(full))) return -1;
    Re4dcIoScope io;
    file_t f = fs_open(full, O_RDONLY);
    if (f < 0) {
        re4dc_log("subscreen backing: open failed %s\n", full);
        return -1;
    }
    long total = (long) fs_total(f), got = 0;
    if (total > (long) capacity) total = (long) capacity;
    while (got < total) {
        const ssize_t r = fs_read(f, static_cast<char*>(dst) + got, (size_t) (total - got));
        if (r <= 0) break;
        got += (long) r;
    }
    fs_close(f);
    return got == total ? got : -1;
}

#if RE4DC_SUBSCREEN_OVL
// The sub screen overlay (SUBSCREEN_OVL=1): /cd/dc/sscrn.ovl, a Dreamcast-only file (no source
// DVD name), read whole into `dst`. Returns the bytes read or -1.
long re4dc_ssb_overlay_read(void* dst, unsigned capacity)
{
    Re4dcIoScope io;
    file_t f = fs_open("/cd/dc/sscrn.ovl", O_RDONLY);
    if (f < 0) return -1;
    long total = (long) fs_total(f), got = 0;
    if (total > (long) capacity) total = (long) capacity;
    while (got < total) {
        const ssize_t r = fs_read(f, static_cast<char*>(dst) + got, (size_t) (total - got));
        if (r <= 0) break;
        got += (long) r;
    }
    fs_close(f);
    return got == total ? got : -1;
}

// Code just written through the operand cache: write it back and drop stale instruction lines.
void re4dc_ssb_code_sync(void* p, unsigned bytes)
{
    dcache_wback_range(reinterpret_cast<uintptr_t>(p), bytes);
    icache_flush_range(reinterpret_cast<uintptr_t>(p), bytes);
}
#endif

}  // extern "C"
#endif  // RE4DC_SUBSCREEN || RE4DC_W11_FIXTURE
