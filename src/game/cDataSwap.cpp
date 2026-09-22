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
