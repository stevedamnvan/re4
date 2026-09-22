// Source heap ownership is retained across current-heap changes.
#include "main_mem.h"
#include "dolphin/os/OSAlloc.h"
#include "native_motion.h"
struct MotionAllocation { int heap; unsigned reserved[7]; };
extern "C" int re4dc_motion_current_heap() { return MemGetCurrentHeap(); }
extern "C" void* re4dc_motion_alloc(unsigned bytes) {
    const int owner=Heap[MemGetCurrentHeap()].handle;
    auto* p=(MotionAllocation*)mem_alloc(bytes+sizeof(MotionAllocation),
        "native motion residency",0,1,MEM_HEAP_CURRENT);
    if(!p)return 0;
    p->heap=owner;return p+1;
}
extern "C" void re4dc_motion_free(void* p) {
    if(!p)return;
    auto* allocation=(MotionAllocation*)p-1;
    OSFreeToHeap(allocation->heap,allocation);
}
