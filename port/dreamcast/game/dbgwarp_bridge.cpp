// D367 test warp rig (DBG_WARP=1, test builds only; compiled out otherwise, and a disc without
// /cd/dc/warp.txt boots normally). Starts the game in a chosen room with Leon placed and the
// scenario state an event needs, within seconds of boot:
//  - Title: once the title data is loaded (title state 2) the title, picker and menus are skipped;
//    titleExit takes the debug-start path (cRoomJmp over debug/roomInfo.dat, the same path as
//    config.txt [STAGE]/[ROOM] + START) with the warp room, so the room loads normally
//    (GameTask -> gameInit new game -> gameStageInit -> gameRoomInit). Quality comes from
//    RE4DCCFG / quality.txt as usual (re4dc_quality_freeze in titleExit).
//  - Position: `pos` / `dir` replace the jump point's NextPos / NextY (-> sub_pos / sub_angle).
//  - Flags: applied once, at the first room entry (re4dc_room_enter: after gameInit cleared the
//    new-game state, before the room's init function reads them): room save flags (RsfSet),
//    Scenario_flg, Item_find_flg, door_unlock.
//  - Actions: `act <room frame> <button> <hold>` presses a button / pushes the stick in the first
//    room (door test mode). Every room entry and action is logged with vblank and wall time.
//  - Boot: the VMU_SAVE card screen (card=8/1) is answered Up+A, so a warp disc needs no padscript.
// A warp start is NOT STRICT against continued play (fresh room entry with synthesized flags; the
// RNG, timers and enemy state are those of a new game). It is for iteration and bring-up only.
//
// /cd/dc/warp.txt (tools/d367/warp.py writes it from a named preset):
//   room 0x100 | jp 0 | pos x y z | dir 0x8000 | ang <rad> | rsf <room> <bit>... |
//   scenario <0|1> <hex> | find <hex> | unlock <0|1> <hex> | inv default | area <no> [dx dz] |
//   act <frame> <a|b|x|y|start|fwd|back|none> <hold> | dump | name <preset>
#if RE4DC_DBG_WARP
#include "types.h"
#include "global.h"
#include "player.h"
#include "room_data.h"
#include "flag_rsf.h"
#include "sce_at.h"
#include "area.h"
#include "re4dc_platform.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <arch/timer.h>

extern "C" {
u32 re4dc_vi_retrace_count(void);

int re4dc_fixture_read(const char* path, char* buffer, unsigned size);
void re4dc_fixture_state(const char* name, int a, int b);  // pad.cpp fixture anchors (overlay)
}

namespace {
struct Act { u32 frame; u16 buttons; s8 stick; u16 hold; };
struct Rsf { u16 room; u8 bit; };
struct Warp {
    bool loaded, active, placed_logged, applied, dump;
    char name[32];
    u16 room;
    int jp;
    bool has_pos, has_dir, has_area;
    f32 pos[3], dir;
    int area_no;
    f32 area_dx, area_dz;
    Rsf rsf[32];
    unsigned n_rsf;
    u32 scenario[2], find, unlock[2];
    Act act[16];
    unsigned n_act;
    // runtime
    u32 room_frames, first_room_gen, rooms;
    int cur_act;
    u32 cur_until;
    unsigned next_act;
    unsigned long long boot_us;
    u32 card_frames;
    u32 last_pad_vbl;
};
Warp wp;

u32 num(const char* s) { return (u32) strtoul(s, nullptr, 0); }

void load()
{
    wp.loaded = true;
    static char text[2048];
    const int len = re4dc_fixture_read("/cd/dc/warp.txt", text, sizeof(text) - 1);
    if (len <= 0) return;
    text[len] = 0;
    for (char* line = text; line && *line;) {
        char* next = strchr(line, '\n');
        if (next) *next++ = 0;
        char* hash = strchr(line, '#');
        if (hash) *hash = 0;
        char* tok[12];
        int n = 0;
        for (char* t = strtok(line, " \t\r"); t && n < 12; t = strtok(nullptr, " \t\r")) tok[n++] = t;
        line = next;
        if (!n) continue;
        const char* k = tok[0];
        if (!strcmp(k, "room") && n >= 2) {
            wp.room = (u16) num(tok[1]);
            wp.active = true;
        } else if (!strcmp(k, "name") && n >= 2) {
            strncpy(wp.name, tok[1], sizeof(wp.name) - 1);
        } else if (!strcmp(k, "jp") && n >= 2) {
            wp.jp = (int) num(tok[1]);
        } else if (!strcmp(k, "pos") && n >= 4) {
            for (int i = 0; i < 3; ++i) wp.pos[i] = (f32) strtod(tok[1 + i], nullptr);
            wp.has_pos = true;
            if (n >= 6 && !strcmp(tok[4], "dir")) {
                wp.dir = (f32) (s16) num(tok[5]) * (3.14159265f / 32768.0f);
                wp.has_dir = true;
            }
        } else if (!strcmp(k, "dir") && n >= 2) {
            wp.dir = (f32) (s16) num(tok[1]) * (3.14159265f / 32768.0f);
            wp.has_dir = true;
        } else if (!strcmp(k, "ang") && n >= 2) {
            wp.dir = (f32) strtod(tok[1], nullptr);
            wp.has_dir = true;
        } else if (!strcmp(k, "rsf") && n >= 3) {
            const u16 room = (u16) num(tok[1]);
            for (int i = 2; i < n && wp.n_rsf < 32; ++i) {
                const u32 bit = num(tok[i]);
                if (bit < 32) wp.rsf[wp.n_rsf++] = {room, (u8) bit};
            }
        } else if (!strcmp(k, "scenario") && n >= 3) {
            wp.scenario[num(tok[1]) & 1] |= num(tok[2]);
        } else if (!strcmp(k, "find") && n >= 2) {
            wp.find |= num(tok[1]);
        } else if (!strcmp(k, "unlock") && n >= 3) {
            wp.unlock[num(tok[1]) & 1] |= num(tok[2]);
        } else if (!strcmp(k, "inv") && n >= 2) {
            if (strcmp(tok[1], "default")) re4dc_log("warp: inv %s not supported (new-game inventory kept)\n", tok[1]);
        } else if (!strcmp(k, "area") && n >= 2) {
            wp.area_no = (int) num(tok[1]);
            wp.area_dx = n >= 3 ? (f32) strtod(tok[2], nullptr) : 0.0f;
            wp.area_dz = n >= 4 ? (f32) strtod(tok[3], nullptr) : 0.0f;
            wp.has_area = true;
        } else if (!strcmp(k, "act") && n >= 4 && wp.n_act < 16) {
            Act& a = wp.act[wp.n_act++];
            a.frame = num(tok[1]);
            a.hold = (u16) num(tok[3]);
            a.buttons = 0;
            a.stick = 0;
            const char* b = tok[2];
            if (!strcmp(b, "a")) a.buttons = 0x0100;
            else if (!strcmp(b, "b")) a.buttons = 0x0200;
            else if (!strcmp(b, "x")) a.buttons = 0x0400;
            else if (!strcmp(b, "y")) a.buttons = 0x0800;
            else if (!strcmp(b, "start")) a.buttons = 0x1000;
            else if (!strcmp(b, "fwd")) a.stick = 80;
            else if (!strcmp(b, "back")) a.stick = -80;
        } else if (!strcmp(k, "dump")) {
            wp.dump = true;
        } else {
            re4dc_log("warp: unknown line '%s'\n", k);
        }
    }
    re4dc_log("warp: /cd/dc/warp.txt %s room=%03x jp=%d pos=%s rsf=%u scenario=%08x/%08x find=%08x unlock=%08x/%08x acts=%u\n",
              wp.name[0] ? wp.name : "-", (unsigned) wp.room, wp.jp, wp.has_pos ? "set" : "jump point", wp.n_rsf,
              (unsigned) wp.scenario[0], (unsigned) wp.scenario[1], (unsigned) wp.find, (unsigned) wp.unlock[0],
              (unsigned) wp.unlock[1], wp.n_act);
}

void stamp(const char* what)
{
    re4dc_log("warp: %s vbl=%u wall_ms=%u\n", what, (unsigned) re4dc_vi_retrace_count(),
              (unsigned) (timer_us_gettime64() / 1000));
}

void dump_areas()
{
    for (int no = 0; no < 256; ++no) {
        SceAtWork* w = SceAtPtr(no);
        if (!w) continue;
        Vec c = {0.0f, 0.0f, 0.0f};
        AreaData area;
        sceAtGetArea(&area, w);
        AreaGetCenterPos(&c, &area);
        if (w->type == 1) {
            re4dc_log("warp: area %02x type=%u flag=%02x trig=%02x shape=%u center=%d,%d,%d door->%u:%02x dst=%d,%d,%d lock=%u/%u\n",
                      no, w->type, w->flag, w->trigger, area.type, (int) c.x, (int) c.y, (int) c.z, w->dstStage,
                      w->dstRoom, (int) w->dstPos.x, (int) w->dstPos.y, (int) w->dstPos.z, w->lockType, w->lockFlag);
        } else {
            re4dc_log("warp: area %02x type=%u flag=%02x trig=%02x shape=%u center=%d,%d,%d\n", no, w->type, w->flag,
                      w->trigger, area.type, (int) c.x, (int) c.y, (int) c.z);
        }
    }
}
}  // namespace

extern "C" {

// title.cpp Title_task: 1 = skip the title screens and go to titleExit.
int re4dc_warp_title(void)
{
    if (!wp.loaded) load();
    if (wp.active && !wp.boot_us) {
        wp.boot_us = 1;
        stamp("title skipped");
    }
    return wp.active;
}

// title.cpp titleExit, before the debug start menu: the room to start in. 1 = warp (no menu).
int re4dc_warp_title_exit(void)
{
    if (!wp.active) return 0;
    pG->stage_no = (u8) (wp.room >> 8);
    pG->room_no = (u8) wp.room;
    pG->JumpPoint = (u8) wp.jp;
    return 1;
}

// title.cpp titleExit, after the jump point's setNextPos: the warp position.
void re4dc_warp_next_pos(void)
{
    if (!wp.active) return;
    if (wp.has_pos) {
        pG->NextPos.x = wp.pos[0];
        pG->NextPos.y = wp.pos[1];
        pG->NextPos.z = wp.pos[2];
    }
    if (wp.has_dir) pG->NextY = wp.dir;
    re4dc_log("warp: start room=%03x next_room=%03x pos=%d,%d,%d ang=%d/1000\n", (unsigned) wp.room,
              (unsigned) pG->next_room, (int) pG->NextPos.x, (int) pG->NextPos.y, (int) pG->NextPos.z,
              (int) (pG->NextY * 1000.0f));
}

// ui_bridge.cpp re4dc_room_enter (every room entry).
void re4dc_warp_room_enter(void)
{
    if (!wp.active) return;
    ++wp.rooms;
    wp.room_frames = 0;
    char what[48];
    snprintf(what, sizeof(what), "room enter %03x (#%u)", (unsigned) pG->room_id, (unsigned) wp.rooms);
    stamp(what);
    if (wp.applied) return;
    wp.applied = true;
    for (unsigned i = 0; i < wp.n_rsf; ++i) {
        if (RoomData.getRoomSavePtr(wp.rsf[i].room)) RsfSet(wp.rsf[i].room, wp.rsf[i].bit);
    }
    pG->Scenario_flg[0] |= wp.scenario[0];
    pG->Scenario_flg[1] |= wp.scenario[1];
    pG->Item_find_flg |= wp.find;
    pG->door_unlock[0] |= wp.unlock[0];
    pG->door_unlock[1] |= wp.unlock[1];
    re4dc_log("warp: flags applied rsf[%03x]=%08x scenario=%08x/%08x find=%08x unlock=%08x/%08x\n",
              (unsigned) pG->room_id,
              RoomData.getRoomSavePtr(pG->room_id) ? (unsigned) RsfFlags(pG->room_id)[0] : 0u,
              (unsigned) pG->Scenario_flg[0], (unsigned) pG->Scenario_flg[1], (unsigned) pG->Item_find_flg,
              (unsigned) pG->door_unlock[0], (unsigned) pG->door_unlock[1]);
}

// ui_bridge.cpp re4dc_room_cycle_poll (top of gameMainLoop, game thread).
void re4dc_warp_poll(void)
{
    if (!wp.active) return;
    ++wp.room_frames;
    if (wp.rooms != 1) return;
    if (wp.room_frames == 1) {
        if (wp.has_area && pPL) {
            Vec c = {0.0f, 0.0f, 0.0f};
            if (SceAtPtr(wp.area_no)) {
                SceAtGetCenterPos(&c, wp.area_no);
                c.x += wp.area_dx;
                c.z += wp.area_dz;
                c.y = pPL->pos.y;
                pPL->setPos(&c);
            } else {
                re4dc_log("warp: area %02x not found\n", wp.area_no);
            }
        }
        if (pPL) {
            re4dc_log("warp: placed room=%03x pl=%d,%d,%d ang=%d/1000 vbl=%u wall_ms=%u\n", (unsigned) pG->room_id,
                      (int) pPL->pos.x, (int) pPL->pos.y, (int) pPL->pos.z, (int) (pPL->ang.y * 1000.0f),
                      (unsigned) re4dc_vi_retrace_count(), (unsigned) (timer_us_gettime64() / 1000));
        }
        re4dc_fixture_state("warp", 1, -1);
    }
    if (wp.dump && wp.room_frames == 2) dump_areas();
    if ((wp.room_frames % 300) == 0 && pPL) {
        re4dc_log("warp: frame %u room=%03x pl=%d,%d,%d status1=%08x rsf=%08x vbl=%u\n", (unsigned) wp.room_frames,
                  (unsigned) pG->room_id, (int) pPL->pos.x, (int) pPL->pos.y, (int) pPL->pos.z,
                  (unsigned) pG->Status_flg[1],
                  RoomData.getRoomSavePtr(pG->room_id) ? (unsigned) RsfFlags(pG->room_id)[0] : 0u,
                  (unsigned) re4dc_vi_retrace_count());
    }
}

// A route movie or an event started (movies pause PADRead): the running action ends there.
static void re4dc_warp_cut(const char* why)
{
    if (!wp.active || wp.rooms != 1 || wp.room_frames >= wp.cur_until) return;
    wp.cur_until = wp.room_frames;
    char what[48];
    snprintf(what, sizeof(what), "act cut by %s", why);
    stamp(what);
}

// platform/pad.cpp PADRead, port A after the real / scripted bits: the scheduled warp actions.
void re4dc_warp_pad(unsigned short* buttons, signed char* stickY)
{
    if (!wp.loaded) load();
    if (!wp.active) return;
    const u32 vbl = re4dc_vi_retrace_count();
    const u32 gap = wp.last_pad_vbl ? vbl - wp.last_pad_vbl : 0;
    wp.last_pad_vbl = vbl;
    if (!wp.boot_us) {
        // Before the title skip only the boot screens run: the VMU_SAVE card screen ("create the
        // system file?") is answered Up (Yes) then A, repeated every second while it waits. No
        // padscript needed; on the other boot screens the pulses are harmless.
        const u32 t = wp.card_frames++ % 60;
        if (t == 10) stamp("card pulse: Up+A");
        if (t >= 10 && t < 13) *buttons |= 0x0008;
        if (t >= 30 && t < 33) *buttons |= 0x0100;
        return;
    }
    if (gap > 30) re4dc_warp_cut("hold");  // a movie or a load held the frame
    if (wp.rooms != 1) return;
    // An event took the game (Status_flg[1] 0x10000000): the running action ends there, so a
    // held stick never walks Leon back into the trigger after the event (movies pause PADRead).
    if (pG->Status_flg[1] & 0x10000000) {
        re4dc_warp_cut("event");
        return;
    }
    if (wp.cur_act >= 0 && wp.cur_act < (int) wp.n_act && wp.room_frames < wp.cur_until) {
        const Act& a = wp.act[wp.cur_act];
        *buttons |= a.buttons;
        if (a.stick) *stickY = a.stick;
        return;
    }
    if (wp.next_act < wp.n_act && wp.room_frames >= wp.act[wp.next_act].frame) {
        const Act& a = wp.act[wp.next_act];
        wp.cur_act = (int) wp.next_act++;
        wp.cur_until = wp.room_frames + a.hold;
        char what[48];
        snprintf(what, sizeof(what), "act %u buttons=%04x stick=%d hold=%u", (unsigned) wp.cur_act,
                 (unsigned) a.buttons, (int) a.stick, (unsigned) a.hold);
        stamp(what);
        *buttons |= a.buttons;
        if (a.stick) *stickY = a.stick;
    }
}

}  // extern "C"
#endif  // RE4DC_DBG_WARP
