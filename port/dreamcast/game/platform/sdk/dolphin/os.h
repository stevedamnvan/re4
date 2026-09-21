/* Shim for <dolphin/os.h> seen by the SDK units compiled in platform/sdk
 * (OSAlloc.c): only what they use. */
#ifndef RE4DC_SDK_SHIM_OS_H
#define RE4DC_SDK_SHIM_OS_H

#include <dolphin/types.h>

#define OFFSET(n, a) (((u32) (n)) & ((a) - 1))
#define ASSERTLINE(line, cond) ((void) 0)

void OSReport(const char* msg, ...);

void* OSInitAlloc(void* arenaStart, void* arenaEnd, int maxHeaps);
int OSCreateHeap(void* start, void* end);
void OSDestroyHeap(int heap);
void OSAddToHeap(int heap, void* start, void* end);
int OSSetCurrentHeap(int heap);
void* OSAllocFromHeap(int heap, u32 size);
void* OSAllocFixed(void* rstart, void* rend);
void OSFreeToHeap(int heap, void* ptr);
s32 OSCheckHeap(int heap);
u32 OSReferentSize(void* ptr);
void OSDumpHeap(int heap);
void OSVisitAllocated(void (*visitor)(void*, u32));
extern volatile int __OSCurrHeap;

#endif
