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

static void vblankHandler(uint32_t code, void* data)
{
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
