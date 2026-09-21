// Small platform pieces: cache control, performance counters, the SN host
// file API, the asm memset/memclr units, the SDK texture-palette lookup, the
// room-archive decoder entry (a C port is the next dependency) and the
// bridges for members the sources call through GCC 2.95 link names.
#include <kos.h>
#include <string.h>

#include "re4dc_platform.h"

typedef unsigned char u8;
typedef unsigned short u16;
typedef signed long s32;
typedef unsigned long u32;

extern "C" {

// ---- cache (DC* = the SDK's data-cache ops)
void DCFlushRange(void* addr, u32 n) { dcache_flush_range((uintptr_t) addr, n); }
void DCFlushRangeNoSync(void* addr, u32 n) { dcache_flush_range((uintptr_t) addr, n); }
void DCStoreRange(void* addr, u32 n) { dcache_flush_range((uintptr_t) addr, n); }
void DCStoreRangeNoSync(void* addr, u32 n) { dcache_flush_range((uintptr_t) addr, n); }
void DCInvalidateRange(void* addr, u32 n) { dcache_inval_range((uintptr_t) addr, n); }

// ---- performance monitor / MSR
void PPCMtmmcr0(u32 v) { (void) v; }
void PPCMtmmcr1(u32 v) { (void) v; }
void PPCMtpmc1(u32 v) { (void) v; }
void PPCMtpmc2(u32 v) { (void) v; }
void PPCMtpmc3(u32 v) { (void) v; }
void PPCMtpmc4(u32 v) { (void) v; }
u32 PPCMfpmc1(void) { return 0; }
void PPCMtmsr(u32 v) { (void) v; }
void PPCSync(void) {}

// ---- SN host file system (dev-mode only): unavailable
int PCinit(void) { return -1; }
int PCopen(const char* path, int flags, int mode) { (void) path; (void) flags; (void) mode; return -1; }
int PCcreat(const char* path, int mode) { (void) path; (void) mode; return -1; }
int PCclose(int fd) { (void) fd; return -1; }
int PCread(int fd, void* buf, int n) { (void) fd; (void) buf; (void) n; return -1; }
int PCwrite(int fd, const void* buf, int n) { (void) fd; (void) buf; (void) n; return -1; }
int PClseek(int fd, int ofs, int whence) { (void) fd; (void) ofs; (void) whence; return -1; }

// ---- game/memset_2.s
void memclr_asm(void* dst, u32 n) { memset(dst, 0, n); }
void memset_asm(void* dst, int c, u32 n) { memset(dst, c, n); }

// ---- charPipeline texPalette.c
struct TEXDescriptor { u32 w[2]; };  // textureHeader, CLUTHeader
struct TEXPalette { u32 versionNumber; u32 numDescriptors; TEXDescriptor* descriptorArray; };
TEXDescriptor* TEXGet(TEXPalette* pal, u32 id) { return &pal->descriptorArray[id]; }

// ---- game/yz2asm.s: the room-archive decoder loop. Not ported yet; the
// first room load reports it.
void yz2Decode_Decode(void* ctx, void* dst, u32 size, void* ev)
{
    (void) ctx; (void) dst; (void) size; (void) ev;
    re4dc_missing("yz2Decode_Decode (room archive decoder)");
}

}  // extern "C"

// ---- bridges: members the sources reach through their GCC 2.95 link name
// where the SH-4 build has no out-of-line copy.
struct Event;
extern "C" void re4dc_FlgOnStatus(Event* e, u32 no) asm("FlgOnStatus__5EventUl");
void re4dc_FlgOnStatus(Event* e, u32 no)
{
    // include/event.h: `f = &StatusFlag (0x44); f[no >> 5] |= 0x80000000 >> (no & 0x1F)`
    u32* f = (u32*) ((u8*) e + 0x44);
    f[no >> 5] |= 0x80000000u >> (no & 0x1F);
}
