// Memory layout: one arena from the KOS heap, carved into the regions the
// GameCube build keeps at fixed addresses. The region sizes are the GameCube's
// (main_mem.cpp SystemMemInit); what remains is the game's OSAlloc arena. The
// GameCube had 21 MB after its ELF for these; the Dreamcast has 16 MB in
// total, so the heap is smaller and R4_ASSET_RESIDENCY_PLAN.md owns the
// consequences. The frame-buffer and FIFO regions (0x80460000, 0x803F0000)
// are not carved: the Dreamcast renderer owns its own.
#include <kos.h>
#include <malloc.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "re4dc_platform.h"

struct Re4dcMemLayout re4dc_mem;

static const unsigned long kDvdSize = 0x80000;      // 0x80370000-0x803F0000
static const unsigned long kSoundSize = 0x70000;    // 0x803F0000-0x80460000
static const unsigned long kCoreSize = 0x234000;    // CORE_DATA_MAX
static const unsigned long kOptionSize = 0x40000;
static const unsigned long kPlayerSize = 0x118000;  // 0x807EC000-0x80904000
static const unsigned long kWeaponSize = 0x70000;
static const unsigned long kMinHeap = 0x300000;

static unsigned char g_frameBuffer[2][32] __attribute__((aligned(32)));
static unsigned char g_fifo[32] __attribute__((aligned(32)));

extern "C" {

void re4dc_mem_init(void)
{
    if (re4dc_mem.arena_lo) {
        return;
    }
    unsigned long fixed = kDvdSize + kSoundSize + kCoreSize + kOptionSize + kPlayerSize + kWeaponSize;
    // Take the largest arena the KOS heap gives us, leaving the runtime some room.
    unsigned long want = 13 * 1024 * 1024;
    void* p = NULL;
    while (want >= fixed + kMinHeap) {
        p = memalign(32, want);
        if (p) {
            break;
        }
        want -= 0x40000;
    }
    if (!p) {
        printf("re4dc_mem_init: no arena (need %lu)\n", fixed + kMinHeap);
        arch_exit();
    }
    unsigned long lo = (unsigned long) p;
    re4dc_mem.arena_lo = lo;
    re4dc_mem.arena_hi = lo + want;
    re4dc_mem.dvd = lo;
    re4dc_mem.sound = re4dc_mem.dvd + kDvdSize;
    re4dc_mem.core = re4dc_mem.sound + kSoundSize;
    re4dc_mem.option = re4dc_mem.core + kCoreSize;
    re4dc_mem.player = re4dc_mem.option + kOptionSize;
    re4dc_mem.weapon = re4dc_mem.player + kPlayerSize;
    re4dc_mem.heap = re4dc_mem.weapon + kWeaponSize;
    re4dc_mem.heap_end = re4dc_mem.arena_hi;
    printf("re4dc_mem: arena %08lx-%08lx dvd %08lx sound %08lx core %08lx option %08lx player %08lx weapon %08lx heap %08lx-%08lx (%lu KB)\n",
           re4dc_mem.arena_lo, re4dc_mem.arena_hi, re4dc_mem.dvd, re4dc_mem.sound, re4dc_mem.core,
           re4dc_mem.option, re4dc_mem.player, re4dc_mem.weapon, re4dc_mem.heap, re4dc_mem.heap_end,
           (re4dc_mem.heap_end - re4dc_mem.heap) / 1024);
}

void* re4dc_frame_buffer(int index)
{
    return g_frameBuffer[index & 1];
}

void* re4dc_gx_fifo(void)
{
    return g_fifo;
}

// The boot log also lives in RAM (a ring the capture tooling reads out of the
// emulator process: evidence read_log.py), because the serial console is not
// captured by the Flycast launcher used here.
#define RE4DC_LOG_SIZE 0x10000
volatile unsigned long re4dc_log_magic __attribute__((aligned(32))) = 0x52453444;  // "RE4D"
volatile unsigned long re4dc_log_head;   // bytes written so far (wraps in the ring)
volatile unsigned long re4dc_stage;      // last platform stage reached (re4dc_set_stage)
char re4dc_logbuf[RE4DC_LOG_SIZE] __attribute__((aligned(32)));

// 1 while stdout is a separate device; 0 once fault.cpp routes the KOS
// debug output into this ring (printing would then loop back here).
int re4dc_log_console = 1;

void re4dc_log_raw(const char* data, unsigned long len)
{
    while (len--) {
        re4dc_logbuf[re4dc_log_head % RE4DC_LOG_SIZE] = *data++;
        re4dc_log_head++;
    }
}

static void logAppend(const char* s)
{
    re4dc_log_raw(s, strlen(s));
}

void re4dc_set_stage(unsigned long stage)
{
    re4dc_stage = stage;
}

void re4dc_log(const char* fmt, ...)
{
    char line[256];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(line, sizeof(line), fmt, ap);
    va_end(ap);
    logAppend(line);
    if (re4dc_log_console) {
        fputs(line, stdout);
    }
}

void re4dc_missing(const char* name)
{
    re4dc_log("RE4DC MISSING: %s called; halting\n", name);
    fflush(stdout);
    for (;;) {
        thd_sleep(1000);
    }
}

}  // extern "C"
