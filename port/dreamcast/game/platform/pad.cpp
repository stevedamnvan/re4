// Controller interface over maple: the four GameCube channels map to the four
// Dreamcast ports; a standard controller fills the PADStatus the game's
// PadRead (src/game/pad.cpp) translates into its JOY words.
#include <kos.h>
#include <dc/maple.h>
#include <dc/maple/controller.h>
#include <string.h>
#include <stdio.h>

#include "re4dc_platform.h"

typedef signed char s8;
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned long u32;
typedef int BOOL;

struct PADStatus {
    u16 button;
    s8 stickX, stickY, substickX, substickY;
    u8 triggerLeft, triggerRight, analogA, analogB;
    s8 err;
    u8 pad_B;
};

enum {
    PAD_BUTTON_LEFT = 0x0001, PAD_BUTTON_RIGHT = 0x0002, PAD_BUTTON_DOWN = 0x0004, PAD_BUTTON_UP = 0x0008,
    PAD_TRIGGER_Z = 0x0010, PAD_TRIGGER_R = 0x0020, PAD_TRIGGER_L = 0x0040,
    PAD_BUTTON_A = 0x0100, PAD_BUTTON_B = 0x0200, PAD_BUTTON_X = 0x0400, PAD_BUTTON_Y = 0x0800, PAD_BUTTON_START = 0x1000,
};
enum { PAD_ERR_NONE = 0, PAD_ERR_NO_CONTROLLER = -1 };

static s8 axis(int v)  // maple -128..127 -> GameCube -128..127 (already the same range)
{
    if (v > 127) v = 127;
    if (v < -128) v = -128;
    return (s8) v;
}


// Scripted input fixture: /cd/dc/padscript.txt lists "frame buttons hold"
// lines (retrace count at which the press starts, GameCube PAD_* button bits
// in hex, frames held). PADRead ORs a running entry into port 0, so a boot
// through the card check / title screens is reproducible without a player.
struct PadScriptEntry { u32 frame; u16 buttons; u16 hold; };
static PadScriptEntry g_script[64];
static int g_scriptCount = -1;  // -1: not loaded yet
int re4dc_diag;

extern "C" u32 re4dc_vi_retrace_count(void);

static void loadScript(void)
{
    g_scriptCount = 0;
    file_t d = fs_open("/cd/dc/diag.txt", O_RDONLY);
    if (d >= 0) {
        fs_close(d);
        re4dc_diag = 1;
        re4dc_log("fixture: /cd/dc/diag.txt present, periodic diagnostics on" "\n");
    }
    file_t f = fs_open("/cd/dc/padscript.txt", O_RDONLY);
    if (f < 0) return;
    static char text[2048];
    ssize_t n = fs_read(f, text, sizeof(text) - 1);
    fs_close(f);
    if (n <= 0) return;
    text[n] = 0;
    char* line = text;
    while (line && *line && g_scriptCount < 64) {
        char* next = strchr(line, '\n');
        if (next) *next++ = 0;
        unsigned frame, buttons, hold;
        if (*line != '#' && sscanf(line, "%u %x %u", &frame, &buttons, &hold) == 3) {
            g_script[g_scriptCount].frame = frame;
            g_script[g_scriptCount].buttons = (u16) buttons;
            g_script[g_scriptCount].hold = (u16) hold;
            g_scriptCount++;
        }
        line = next;
    }
    re4dc_log("pad: script /cd/dc/padscript.txt: %d entries\n", g_scriptCount);
}

static u16 scriptButtons(void)
{
    if (g_scriptCount < 0) loadScript();
    u32 now = re4dc_vi_retrace_count();
    u16 b = 0;
    for (int i = 0; i < g_scriptCount; i++) {
        if (now >= g_script[i].frame && now < g_script[i].frame + g_script[i].hold) {
            if (now == g_script[i].frame) re4dc_log("pad: script press %04x at frame %lu\n", g_script[i].buttons, (unsigned long) now);
            b |= g_script[i].buttons;
        }
    }
    return b;
}

extern "C" {

BOOL PADInit(void) { return 1; }
int PADReset(u32 mask) { (void) mask; return 1; }
BOOL PADRecalibrate(u32 mask) { (void) mask; return 1; }
void PADSetAnalogMode(u32 mode) { (void) mode; }
void PADControlMotor(int chan, u32 cmd) { (void) chan; (void) cmd; }

void re4dc_audio_frame(void);

u32 PADRead(PADStatus* status)
{
    // The sound driver's audio-frame callback (audio_stub.cpp): once per game
    // frame from the frame loop, the earliest point on the game's own thread.
    re4dc_audio_frame();
    u32 connected = 0;
    for (int i = 0; i < 4; i++) {
        PADStatus* p = &status[i];
        memset(p, 0, sizeof(*p));
        u16 scripted = i == 0 ? scriptButtons() : 0;
        maple_device_t* dev = maple_enum_type(i, MAPLE_FUNC_CONTROLLER);
        const cont_state_t* st = dev ? (const cont_state_t*) maple_dev_status(dev) : NULL;
        static const cont_state_t idle = {};
        if (st == NULL && (i != 0 || g_scriptCount <= 0)) {
            p->err = PAD_ERR_NO_CONTROLLER;
            continue;
        }
        if (st == NULL) st = &idle;  // a scripted port counts as connected
        connected |= 0x80000000u >> i;
        {
            static int seen[4];
            if (!seen[i]) { seen[i] = 1; re4dc_log("pad %d: controller present\n", i); }
        }
        u16 b = 0;
        if (st->buttons & CONT_A) b |= PAD_BUTTON_A;
        if (st->buttons & CONT_B) b |= PAD_BUTTON_B;
        if (st->buttons & CONT_X) b |= PAD_BUTTON_X;
        if (st->buttons & CONT_Y) b |= PAD_BUTTON_Y;
        if (st->buttons & CONT_START) b |= PAD_BUTTON_START;
        if (st->buttons & CONT_DPAD_UP) b |= PAD_BUTTON_UP;
        if (st->buttons & CONT_DPAD_DOWN) b |= PAD_BUTTON_DOWN;
        if (st->buttons & CONT_DPAD_LEFT) b |= PAD_BUTTON_LEFT;
        if (st->buttons & CONT_DPAD_RIGHT) b |= PAD_BUTTON_RIGHT;
        if (st->ltrig > 128) b |= PAD_TRIGGER_L;
        if (st->rtrig > 128) b |= PAD_TRIGGER_R;
        if (st->buttons & CONT_C) b |= PAD_TRIGGER_Z;   // six-button pads: C = Z
        if (st->buttons & CONT_Z) b |= PAD_TRIGGER_Z;
        b |= scripted;
        {
            static u16 lastLogged[4];
            if (b != lastLogged[i]) {
                re4dc_log("pad %d: buttons %04x\n", i, (unsigned) b);
                lastLogged[i] = b;
            }
        }
        p->button = b;
        p->stickX = axis(st->joyx);
        p->stickY = axis(-st->joyy);   // maple Y grows downward, the GameCube stick upward
        p->substickX = axis(st->joy2x);
        p->substickY = axis(-st->joy2y);
        p->triggerLeft = (u8) st->ltrig;
        p->triggerRight = (u8) st->rtrig;
        p->err = PAD_ERR_NONE;
    }
    return connected;
}

void PADClamp(PADStatus* status)
{
    (void) status;  // maple already reports calibrated ranges
}

}  // extern "C"
