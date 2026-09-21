// Controller interface over maple: the four GameCube channels map to the four
// Dreamcast ports; a standard controller fills the PADStatus the game's
// PadRead (src/game/pad.cpp) translates into its JOY words.
#include <kos.h>
#include <dc/maple.h>
#include <dc/maple/controller.h>
#include <string.h>

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
        maple_device_t* dev = maple_enum_type(i, MAPLE_FUNC_CONTROLLER);
        if (dev == NULL) {
            p->err = PAD_ERR_NO_CONTROLLER;
            continue;
        }
        const cont_state_t* st = (const cont_state_t*) maple_dev_status(dev);
        if (st == NULL) {
            p->err = PAD_ERR_NO_CONTROLLER;
            continue;
        }
        connected |= 0x80000000u >> i;
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
