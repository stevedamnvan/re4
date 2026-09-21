// Video interface over KOS: mode set-up, retrace wait and the post-retrace
// callback the game's frame loop is paced by (main.cpp postVSyncCallback
// counts vsyncs and resumes the interrupt task scheduler).
#include <kos.h>
#include <dc/vblank.h>

#include "re4dc_platform.h"

typedef unsigned long u32;
typedef int BOOL;
typedef void (*VIRetraceCallback)(void);

static VIRetraceCallback g_postRetrace;
static int g_vblankHandle = -1;
static volatile u32 g_retraceCount;
static int g_black = 1;

extern "C" void re4dc_audio_frame(void);
extern "C" void re4dc_threads_dump(void);

extern "C" volatile unsigned long re4dc_stage;

// Poll-based memory watch: the vblank handler compares a checksum of a region
// every frame and logs the running context the first time it changes.
static volatile unsigned long* g_watchAddr;
static unsigned long g_watchWords;
static unsigned long g_watchSum;
static int g_watchArmed;

static unsigned long watchSum(void)
{
    unsigned long s = 0;
    for (unsigned long i = 0; i < g_watchWords; i++) s = s * 31 + g_watchAddr[i];
    return s;
}

extern "C" void re4dc_watch_set(const void* addr, unsigned long words)
{
    g_watchAddr = (volatile unsigned long*) addr;
    g_watchWords = words;
    g_watchSum = watchSum();
    g_watchArmed = 1;
    re4dc_log("watch: %p x%lu sum %08lx [%08lx %08lx %08lx %08lx]\n", addr, words, g_watchSum,
              g_watchAddr[0], g_watchAddr[1], g_watchAddr[2], g_watchAddr[3]);
}

static void watchPoll(void)
{
    if (!g_watchArmed) return;
    unsigned long s = watchSum();
    if (s == g_watchSum) return;
    g_watchArmed = 0;
    irq_context_t* c = irq_get_context();
    re4dc_log("watch: CHANGED at vblank %lu stage %08lx pc %08lx pr %08lx [%08lx %08lx %08lx %08lx]\n",
              (unsigned long) g_retraceCount, (unsigned long) re4dc_stage, c ? (unsigned long) c->pc : 0,
              c ? (unsigned long) c->pr : 0, g_watchAddr[0], g_watchAddr[1], g_watchAddr[2], g_watchAddr[3]);
    re4dc_threads_dump();
}

static void vblankHandler(uint32_t code, void* data)
{
    watchPoll();
    (void) code;
    (void) data;
    unsigned long prev = re4dc_stage;
    re4dc_stage = 0x1000;
    g_retraceCount++;
    if ((g_retraceCount % 600) == 0) re4dc_log("vblank %lu\n", (unsigned long) g_retraceCount);
    if ((g_retraceCount % 600) == 0) re4dc_threads_dump();
    (void) re4dc_audio_frame;  // the audio frame runs from the frame loop (pad.cpp), not the ISR
    if (g_postRetrace) {
        re4dc_stage = 0x1001;
        g_postRetrace();
    }
    re4dc_stage = prev;
}

extern "C" {

void VIInit(void)
{
    static int done;
    if (done) {
        return;
    }
    done = 1;
    vid_set_mode(DM_640x480, PM_RGB565);
    g_vblankHandle = vblank_handler_add(vblankHandler, NULL);
    re4dc_log("VIInit: 640x480, vblank handler %d\n", g_vblankHandle);
}

void VIConfigure(const void* rm)
{
    (void) rm;  // the Dreamcast renderer owns the display mode
}

void VISetBlack(BOOL black)
{
    g_black = black;
    vid_border_color(0, 0, 0);
}

void VIFlush(void) {}

void VIWaitForRetrace(void)
{
    u32 start = g_retraceCount;
    while (g_retraceCount == start) {
        // the vblank interrupt advances the count; nothing else to do
    }
}

VIRetraceCallback VISetPostRetraceCallback(VIRetraceCallback cb)
{
    VIRetraceCallback old = g_postRetrace;
    g_postRetrace = cb;
    return old;
}

void VISetNextFrameBuffer(void* fb)
{
    (void) fb;  // presentation belongs to the renderer
}

u32 VIGetTvFormat(void) { return 0; }  // VI_NTSC
u32 VIGetNextField(void) { return g_retraceCount & 1; }
u32 VIGetDTVStatus(void) { return 0; }

u32 re4dc_vi_retrace_count(void) { return g_retraceCount; }

}  // extern "C"
