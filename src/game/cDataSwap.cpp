// game/cDataSwap: swap a memory range out to a heap copy or ARAM so heap 11 can reuse it
// (D:/Bio4/Prog/cDataSwap.cpp).
#include "types.h"
#include "global.h"
#include "map_obj.h"
#include "light.h"
#include "widget.h"
#include "dvd.h"
#include "main_mem.h"
#include "datactrl.h"
#include "cDataSwap.h"
#if defined(RE4DC_GAME) && !defined(__PPC__)
#include "re4dc_platform.h"
#endif
#if defined(RE4DC_GAME) && !defined(__PPC__) && RE4DC_SUBSCREEN
// D367 VMU S0 (SUBSCREEN=1, subscreen.mk): Dreamcast storage for the swapped range when the heap
// copy does not fit. The range goes to the W11 VRAM backing (platform/subscreen_backing.cpp: the
// idle second TA vertex bank, then texture-pool blocks) and comes back byte-exact, checked by hash.
// The sub screen and the card screen never overlap: a second open is refused and halts below.
extern "C" {
int re4dc_ssb_open(unsigned bytes, unsigned* bank_bytes, unsigned* pool_bytes);
void re4dc_ssb_rewind();
void re4dc_ssb_put(const void* src, unsigned bytes);
void re4dc_ssb_get(void* dst, unsigned bytes);
void re4dc_ssb_close();
unsigned long long re4dc_ssb_us();
}
enum { kSwapVram = 4 };  // m_be_flag: copy in the VRAM backing
static u32 swapVramHash;
static u32 swapHash(u32 addr, u32 size)
{
    const u32* p = (const u32*) addr;
    u32 h = 2166136261U;
    for (u32 n = size / 4; n; --n) h = (h ^ *p++) * 16777619U;
    return h;
}
#endif

extern "C" {
void SubScreenAramRead();
}

// Nothing swapped yet.
cDataSwap::cDataSwap()
{
    m_be_flag = 0;
    m_SwapMaddr = 0;
    m_SwapAaddr = 0;
    m_SwapSize = 0;
}

// (the room code calls SwapIn explicitly)
cDataSwap::~cDataSwap()
{
}

// Frees `size` bytes at `addr` (room data) for reuse: copies them to a heap block (be_flag bit0)
// or, when MRAM is short, DMAs them to ARAM (bit1: the data controller's free ARAM, the caller's
// `aram`, or the subscreen area 0xD00000 for blocks under 3 MB), then creates heap 11 over the
// range and makes it current. 1 when the range is available.
int cDataSwap::SwapOut(u32 addr, u32 size, u32 aram)
{
    int ret = 0;

    if (m_be_flag != 0) {
        return 0;
    }
    m_CurHeapNo = MemGetCurrentHeap();
    this->m_SwapSize = size;
#line 64 "D:/Bio4/Prog/cDataSwap.cpp"
    mram = MEM_ALLOC(size, 0, 13);
    if (mram == NULL) {
#if defined(RE4DC_GAME) && !defined(__PPC__) && RE4DC_SUBSCREEN
        {
            unsigned bank = 0, pool = 0;
            const unsigned long long t0 = re4dc_ssb_us();
            if ((size & 3) || (addr & 3) || !re4dc_ssb_open(size, &bank, &pool)) {
                re4dc_missing("cDataSwap: VRAM backing unavailable (sub screen open or VRAM short)");
                return 0;
            }
            re4dc_ssb_rewind();
            re4dc_ssb_put((const void*) addr, size);
            swapVramHash = swapHash(addr, size);
            this->m_SwapMaddr = addr;
            m_be_flag |= kSwapVram;
            re4dc_log("cDataSwap: out addr=%08x size=%u bank=%u pool=%u us=%u hash=%08x\n", (unsigned) addr,
                      (unsigned) size, bank, pool, (unsigned) (re4dc_ssb_us() - t0), (unsigned) swapVramHash);
            MemSuspendHeap(m_CurHeapNo);
            MemCreateHeap(11, this->m_SwapMaddr, this->m_SwapMaddr + this->m_SwapSize);
            MemSetCurrentHeap(11);
            return 1;
        }
#endif
#if defined(RE4DC_GAME) && !defined(__PPC__)
        // ARQ currently provides no mutable backing. Do not reuse live archive
        // bytes (including borrowed native identities) without a real snapshot.
        re4dc_missing("cDataSwap mutable ARAM backing unavailable");
        return 0;
#endif
        this->m_SwapAaddr = DC.getAramFree(size);
        if (this->m_SwapAaddr != 0) {
            m_be_flag |= 2;
        } else if (aram != 0) {
            this->m_SwapAaddr = aram;
            m_be_flag |= 2;
        } else if (size > 0x2FFFFF) {
            return 0;
        } else {
            this->m_SwapAaddr = 0xD00000;
            m_be_flag |= 2;
        }
        if (m_be_flag & 2) {
            this->m_SwapMaddr = addr;
            Aram.DmaTransReq(0, addr, this->m_SwapAaddr, this->m_SwapSize, 1);
        }
    } else {
        this->m_SwapMaddr = (u32) mram;
        m_be_flag |= 1;
    }
    if (m_be_flag & 3) {
        MemSuspendHeap(m_CurHeapNo);
        ret = 1;
        MemCreateHeap(11, this->m_SwapMaddr, this->m_SwapMaddr + this->m_SwapSize);
        MemSetCurrentHeap(11);
    }
    return ret;
}

// Undoes SwapOut: destroys heap 11, DMAs the data back from ARAM (re-reading the subscreen ARAM
// data when its area was used), restores the previous heap and frees the heap copy.
void cDataSwap::SwapIn()
{
    if (m_be_flag != 0) {
        MemDestroyHeap(11);
#if defined(RE4DC_GAME) && !defined(__PPC__) && RE4DC_SUBSCREEN
        if (m_be_flag & kSwapVram) {
            const unsigned long long t0 = re4dc_ssb_us();
            re4dc_ssb_rewind();
            re4dc_ssb_get((void*) m_SwapMaddr, m_SwapSize);
            re4dc_ssb_close();
            const u32 h = swapHash(m_SwapMaddr, m_SwapSize);
            re4dc_log("cDataSwap: in addr=%08x size=%u us=%u hash=%08x %s\n", (unsigned) m_SwapMaddr,
                      (unsigned) m_SwapSize, (unsigned) (re4dc_ssb_us() - t0), (unsigned) h,
                      h == swapVramHash ? "ok" : "MISMATCH");
            if (h != swapVramHash) {
                re4dc_missing("cDataSwap: VRAM backing corrupted");
            }
        }
#endif
        if (m_be_flag & 2) {
            Aram.DmaTransReq(1, m_SwapAaddr, m_SwapMaddr, m_SwapSize, 1);
            if (m_SwapAaddr == 0xD00000) {
                SubScreenAramRead();
            }
        }
        MemSignalHeap(m_CurHeapNo);
        MemSetCurrentHeap(m_CurHeapNo);
        if (mram != NULL) {
            Mem_free(mram);
        }
        m_be_flag = 0;
    }
}
