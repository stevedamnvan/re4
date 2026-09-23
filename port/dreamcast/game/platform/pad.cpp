// Controller interface over maple: the four GameCube channels map to the four
// Dreamcast ports; each controller fills the PADStatus the game's PadRead
// (src/game/pad.cpp) translates into its JOY words (mapping: re4dcMapPad).
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

// ---- Controller mapping (platform adapter only) ----------------------------
// The game's PadRead / Key_type_tbl stay source-authoritative: this layer only
// decides which GameCube PADStatus a Dreamcast controller produces.
//
// Ranges: the GameCube SDK's PADClamp (called by PadRead right after PADRead)
// leaves stick 0..72 (octagon corner 40), C-stick 0..59 (corner 31) and
// triggers 0..150, each past a 15 / 15 / 30 dead zone; game code is tuned to
// those numbers (cam_qfps C_RANGE 59, pl0f /72, PadRead's 30-unit direction
// threshold, and any nonzero analog trigger counts as L / R held). Maple axes
// (-128..127) are scaled to the GameCube's raw span (about +-100) and pushed
// through the same clamp here, so PADClamp itself stays a no-op.
//
// Pad kinds (per port, like dca3-game's IsDualAnalog):
//   dual   - the device advertises a second analog stick or C / Z buttons
//            (twin-analog pads, arcade sticks), or reports second-stick axes
//            beyond +-64 on two consecutive polls, or a C / Z press is seen.
//            Native: joy2 -> C-stick, C or Z -> Z, D-pad -> D-pad.
//   standard - A/B/X/Y/Start, stick, triggers as on the GameCube; the D-pad
//            (a pure duplicate of the stick in Key_type_tbl) is reused by
//            game context (re4dc_pad_context, port/dreamcast/game/ui_bridge.cpp):
//     LOOK   free movement, where CameraQuasiFPS reads Key.substick: the
//            D-pad is an 8-way C-stick (59 cardinal, 31/31 diagonal: a fully
//            deflected GameCube C-stick after PADClamp) and sends no D-pad
//            bits. A lone D-pad-down tap (released within Z_TAP_POLLS polls,
//            no other direction) sends Z (map) for Z_PULSE_POLLS polls.
//     ZOOM   rifle scope / binoculars (Status_flg[0] 0x40 / 0x400), where the
//            C-stick Y zooms: D-pad up / down -> C-stick Y +-ZOOM_MAG, left /
//            right stay D-pad (fine pan).
//     NATIVE everything else (menus, sub screen, aiming, knife, events, QTEs):
//            D-pad -> D-pad, no C-stick, no Z.
//
// Debug chords the source leaves live on pad 0 are blocked here by default
// (re4dcBlockDebugChords; RE4DC_DEBUG_PAD=1, Makefile DEBUG_PAD=1, restores them):
//   L + START  gameDebug (game.cpp) opens DbMenuExec whenever Debug_flg[0]
//              bit 31 is clear: START is masked for a press that starts with
//              L held, only while that flag would open the menu (options stay
//              closed with L held anyway: gameMainLoop tests !Key 0x400000).
//   Z          inside the sub screen (any open type except the Z-opened map,
//              where Z closes it) the raw Joy Z toggles the item-make / puzzle
//              debug menus (ss_item.cpp SsItemMain::move, ss_pzzl.cpp): masked.
// Fixture (padscript) bits are ORed in after both and are never filtered.
// Cost: a few dozen integer ops per port per frame plus two field-read calls.
enum { RE4DC_PAD_CTX_NATIVE = 0, RE4DC_PAD_CTX_LOOK = 1, RE4DC_PAD_CTX_ZOOM = 2 };
enum { RE4DC_PAD_DBG_MENU = 1, RE4DC_PAD_DBG_SUBSCREEN_Z = 2 };  // re4dc_pad_debug_state bits
enum { LOOK_MAG = 59, LOOK_DIAG = 31, ZOOM_MAG = 30, Z_TAP_POLLS = 10, Z_PULSE_POLLS = 2, DUAL_AXIS = 64 };
#ifndef RE4DC_DEBUG_PAD
#define RE4DC_DEBUG_PAD 0
#endif

struct Re4dcPadIn { u32 buttons; int ltrig, rtrig, joyx, joyy, joy2x, joy2y; };  // maple units, joyy grows downward
struct Re4dcPadMap { u8 dual, dualVotes, tapPolls, tapClean, zPulse, startHeld, startBlocked; };

// Dolphin SDK ClampStick: dead zone `min`, octagon of radius `max` with corner `xy`.
static void gcClampStick(int* px, int* py, int max, int xy, int min)
{
    int x = *px, y = *py, sx = 1, sy = 1, d;
    if (x < 0) { sx = -1; x = -x; }
    if (y < 0) { sy = -1; y = -y; }
    x = x <= min ? 0 : x - min;
    y = y <= min ? 0 : y - min;
    if (x == 0 && y == 0) { *px = *py = 0; return; }
    d = xy * y <= xy * x ? xy * x + (max - xy) * y : xy * y + (max - xy) * x;
    if (xy * max < d) {
        x = xy * max * x / d;
        y = xy * max * y / d;
    }
    *px = sx * x;
    *py = sy * y;
}

static int gcRaw(int maple) { return maple * 100 / 128; }  // maple -128..127 -> GameCube raw -100..99

static u8 gcClampTrigger(int t)  // SDK ClampTrigger(30, 180)
{
    if (t <= 30) return 0;
    if (t > 180) t = 180;
    return (u8) (t - 30);
}

static u16 gcDpad(u32 buttons)
{
    u16 b = 0;
    if (buttons & CONT_DPAD_UP) b |= PAD_BUTTON_UP;
    if (buttons & CONT_DPAD_DOWN) b |= PAD_BUTTON_DOWN;
    if (buttons & CONT_DPAD_LEFT) b |= PAD_BUTTON_LEFT;
    if (buttons & CONT_DPAD_RIGHT) b |= PAD_BUTTON_RIGHT;
    return b;
}

// One poll of one port: `in` (maple), `ctx` (RE4DC_PAD_CTX_*), `capsDual` (the
// device advertises C / Z / a second stick) -> button, sticks and triggers of `p`.
static void re4dcMapPad(const Re4dcPadIn* in, int ctx, int capsDual, Re4dcPadMap* m, PADStatus* p)
{
    const u32 dirs = CONT_DPAD_UP | CONT_DPAD_DOWN | CONT_DPAD_LEFT | CONT_DPAD_RIGHT;
    u32 dpad = in->buttons & dirs;
    u16 b = 0;
    int sx, sy, cx = 0, cy = 0;

    if (!m->dual) {
        if (capsDual || (in->buttons & (CONT_C | CONT_Z))) {
            m->dual = 1;
        } else if (in->joy2x > DUAL_AXIS || in->joy2x < -DUAL_AXIS || in->joy2y > DUAL_AXIS || in->joy2y < -DUAL_AXIS) {
            if (++m->dualVotes >= 2) m->dual = 1;
        } else {
            m->dualVotes = 0;
        }
    }

    if (in->buttons & CONT_A) b |= PAD_BUTTON_A;
    if (in->buttons & CONT_B) b |= PAD_BUTTON_B;
    if (in->buttons & CONT_X) b |= PAD_BUTTON_X;
    if (in->buttons & CONT_Y) b |= PAD_BUTTON_Y;
    if (in->buttons & CONT_START) b |= PAD_BUTTON_START;
    p->triggerLeft = gcClampTrigger(in->ltrig);
    p->triggerRight = gcClampTrigger(in->rtrig);
    if (p->triggerLeft) b |= PAD_TRIGGER_L;    // PadRead ORs JOY_L / JOY_R for any nonzero analog value anyway
    if (p->triggerRight) b |= PAD_TRIGGER_R;
    sx = gcRaw(in->joyx);
    sy = -gcRaw(in->joyy);                     // maple Y grows downward, the GameCube stick upward
    gcClampStick(&sx, &sy, 72, 40, 15);

    if (m->dual) {
        cx = gcRaw(in->joy2x);
        cy = -gcRaw(in->joy2y);
        gcClampStick(&cx, &cy, 59, 31, 15);
        if (in->buttons & (CONT_C | CONT_Z)) b |= PAD_TRIGGER_Z;   // six-button pads: C = Z
        b |= gcDpad(dpad);
        m->tapPolls = 0;
        m->tapClean = 0;
        m->zPulse = 0;
    } else {
        if (ctx == RE4DC_PAD_CTX_LOOK) {
            int dx = ((dpad & CONT_DPAD_RIGHT) != 0) - ((dpad & CONT_DPAD_LEFT) != 0);
            int dy = ((dpad & CONT_DPAD_UP) != 0) - ((dpad & CONT_DPAD_DOWN) != 0);
            int mag = dx && dy ? LOOK_DIAG : LOOK_MAG;
            cx = dx * mag;
            cy = dy * mag;
        } else if (ctx == RE4DC_PAD_CTX_ZOOM) {
            cy = (dpad & CONT_DPAD_UP) ? ZOOM_MAG : (dpad & CONT_DPAD_DOWN) ? -ZOOM_MAG : 0;
            b |= gcDpad(dpad & (CONT_DPAD_LEFT | CONT_DPAD_RIGHT));
        } else {
            b |= gcDpad(dpad);
        }
        // Z: a lone D-pad-down tap, every poll of it in LOOK.
        if (dpad == 0) {
            if (m->tapClean && m->tapPolls && m->tapPolls <= Z_TAP_POLLS) m->zPulse = Z_PULSE_POLLS;
            m->tapPolls = 0;
            m->tapClean = 1;
        } else if (dpad == CONT_DPAD_DOWN && ctx == RE4DC_PAD_CTX_LOOK && m->tapClean) {
            if (m->tapPolls < 255) m->tapPolls++;
        } else {
            m->tapClean = 0;
        }
        if (m->zPulse) {
            m->zPulse--;
            b |= PAD_TRIGGER_Z;
        }
    }
    p->button = b;
    p->stickX = (s8) sx;
    p->stickY = (s8) sy;
    p->substickX = (s8) cx;
    p->substickY = (s8) cy;
}

// Pad 0's mapped buttons with the source's debug chords removed (`dbg`: RE4DC_PAD_DBG_* from
// re4dc_pad_debug_state). A START press that begins with L held stays masked until released.
static u16 re4dcBlockDebugChords(u16 b, int dbg, Re4dcPadMap* m)
{
    if (b & PAD_BUTTON_START) {
        if (!m->startHeld && (dbg & RE4DC_PAD_DBG_MENU) && (b & PAD_TRIGGER_L)) m->startBlocked = 1;
        m->startHeld = 1;
    } else {
        m->startHeld = 0;
        m->startBlocked = 0;
    }
    if (m->startBlocked) b &= (u16) ~PAD_BUTTON_START;
    if (dbg & RE4DC_PAD_DBG_SUBSCREEN_Z) b &= (u16) ~PAD_TRIGGER_Z;
    return b;
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
int re4dc_pad_context(void);      // ui_bridge.cpp: RE4DC_PAD_CTX_* from the game state of the last frame
int re4dc_pad_debug_state(void);  // ui_bridge.cpp: RE4DC_PAD_DBG_* (which debug chords would fire)

u32 PADRead(PADStatus* status)
{
    // The sound driver's audio-frame callback (audio_stub.cpp): once per game
    // frame from the frame loop, the earliest point on the game's own thread.
    re4dc_audio_frame();
    static Re4dcPadMap maps[4];
    static maple_device_t* lastDev[4];
    int ctx0 = re4dc_pad_context();
    u32 connected = 0;
    for (int i = 0; i < 4; i++) {
        PADStatus* p = &status[i];
        memset(p, 0, sizeof(*p));
        u16 scripted = i == 0 ? scriptButtons() : 0;
        maple_device_t* dev = maple_enum_type(i, MAPLE_FUNC_CONTROLLER);
        const cont_state_t* st = dev ? (const cont_state_t*) maple_dev_status(dev) : NULL;
        static const cont_state_t idle = {};
        if (dev != lastDev[i]) {  // plugged / unplugged / swapped: classify the pad again
            lastDev[i] = dev;
            memset(&maps[i], 0, sizeof(maps[i]));
        }
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
        int capsDual = dev && (cont_has_capabilities(dev, CONT_CAPABILITIES_SECONDARY_ANALOG) ||
                               cont_has_capabilities(dev, CONT_CAPABILITY_C) || cont_has_capabilities(dev, CONT_CAPABILITY_Z));
        Re4dcPadIn in = {(u32) st->buttons, st->ltrig, st->rtrig, st->joyx, st->joyy, st->joy2x, st->joy2y};
        PADStatus mapped;
        u8 wasDual = maps[i].dual;
        re4dcMapPad(&in, i == 0 ? ctx0 : RE4DC_PAD_CTX_NATIVE, capsDual, &maps[i], &mapped);
        if (maps[i].dual != wasDual) re4dc_log("pad %d: dual-analog mapping (C-stick = joy2, Z = C/Z)\n", i);
        u16 b = mapped.button;
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
        if (i == 0 && !RE4DC_DEBUG_PAD) {  // debug chords come off the real bits only; fixture bits pass
            u16 real = mapped.button | ((st->buttons & CONT_Z) ? PAD_TRIGGER_Z : 0);
            p->button = (u16) (re4dcBlockDebugChords(real, re4dc_pad_debug_state(), &maps[0]) | scripted);
        }
        p->stickX = mapped.stickX;       // SDK-clamped; maple Y already flipped
        p->stickY = mapped.stickY;
        p->substickX = mapped.substickX;
        p->substickY = mapped.substickY;
        p->triggerLeft = mapped.triggerLeft;
        p->triggerRight = mapped.triggerRight;
        p->err = PAD_ERR_NONE;
    }
    return connected;
}

void PADClamp(PADStatus* status)
{
    (void) status;  // PADRead already applied the SDK clamp regions (re4dcMapPad)
}

}  // extern "C"
