// D367 quality picker (QUALITY=1; design-lowmode DESIGN.md A2, user decisions 2026-09-23):
// once per boot, at the first title main menu, "Graphics quality / Standard / Original" in the
// game's own message window and font, the same mechanism as the boot progressive-scan prompt
// (tv_mode.cpp: MesData table + cMes.MesSet + poll m_sel). Test builds (QUALITY_DEBUG=1) add a
// per-feature submenu behind X or L+R+A. Render state only: the title flow is unchanged
// except for the frames the picker is open, and fixtures skip it with /cd/dc/quality.txt.
#include "types.h"
#include "global.h"
#include "main.h"
#include "mes.h"
#include "joy.h"
#include "id_sys.h"
#include "cockpit.h"
#include "texture.h"
#include "platform/quality.h"
#include <stddef.h>
#include <string.h>

#ifndef RE4DC_QUALITY_DEBUG
#define RE4DC_QUALITY_DEBUG 0
#endif

extern "C" void re4dc_log(const char* fmt, ...);
extern cTexSys* g_pIdTexSys;  // id_tex.cpp (at file scope: inside the unnamed namespace it would
                              // name a different, internal variable)

namespace {
// Glyph codes of the English common_p.fnt (design-lowmode tools/mestbl.py, verified against the
// r100/r101 English MDT messages): space 0x80, 'A'-'Z' = ch + 0x66, 'a'-'z' = ch + 0x60.
// Control codes: 00 page, 01 end, 03 new line, 07 choice line, 08 wait for a choice.
enum : u16 { PAGE = 0x00, END = 0x01, NL = 0x03, CHOICE = 0x07, WAIT = 0x08 };

// MessageData::getAddr layout: u32 header, u32 block offset per language, then the block
// {x0, count, ofs[count]} and u16 text. Every language points at the same English block.
struct Table {
    u32 hdr;
    u32 lang[8];
    u32 x0, count, ofs[2];
    u16 text[240];
};
alignas(4) Table table;
unsigned text_n;

void put(u16 w) { if (text_n < sizeof(table.text) / 2) table.text[text_n++] = w; }
void put(const char* s)
{
    for (; *s; ++s) {
        const char c = *s;
        if (c == ' ') put(u16(0x80));
        else if (c >= 'A' && c <= 'Z') put(u16(c + 0x66));
        else if (c >= 'a' && c <= 'z') put(u16(c + 0x60));
        // other characters have no verified glyph code: never used in these strings
    }
}

// Displayed strings (user wording 2026-09-23; it may change, so edit here only; letters and
// spaces only, see put()). Choice 0 is "Standard", the budget-first mode and the default;
// choice 1 is "Original", the faithful GameCube look.
constexpr const char* kTitle = "Graphics quality";
constexpr const char* kChoice[2] = {"Standard", "Original"};
constexpr int kChoiceMode[2] = {RE4DC_QUALITY_STANDARD, RE4DC_QUALITY_ORIGINAL};
int cursor_of(int mode) { return mode == kChoiceMode[0] ? 0 : 1; }

// Message 0: the picker. Message 1: the test-build feature menu (one choice line per wired
// feature, then "Done"; values as words because the digit glyph codes are not verified).
void build()
{
    const Re4dcQuality* q = re4dc_quality();
    text_n = 0;
    const u32 block = offsetof(Table, x0);
    const u32 text0 = offsetof(Table, text) - block;
    table.hdr = 8;
    for (u32& l : table.lang) l = block;
    table.x0 = 0;
    table.count = 2;
    table.ofs[0] = text0;
    put(PAGE); put(kTitle); put(NL);
    put(CHOICE); put(kChoice[0]); put(NL);
    put(CHOICE); put(kChoice[1]); put(WAIT); put(END);
    table.ofs[1] = text0 + 2 * text_n;
    put(PAGE); put("Test settings"); put(NL);
    put(CHOICE); put("Mesh detail "); put((q->features & RQ_LOD_COARSE) ? "coarse" : "fine"); put(NL);
    put(CHOICE); put("Done"); put(WAIT); put(END);
}

// Slot 0 in the system layout, as the progressive-scan prompt; attr: file 4 (0x10, which also
// keeps the game running), instant (0x40), kept after the end code (0x01000000), left-aligned
// at the card prompts' position (0x20000; x 0x64, y 0x6E), and vertical choices (0x00800000:
// code 08 moves the cursor with up/down instead of left/right).
constexpr u32 kAttr = 0x01820050;
u8* saved_ptr4;
int state;          // 0 closed, 1 picker, 2 feature menu
int debug_cursor;

void show(int no, int cursor)
{
    build();
    cMes.Delete(0);
    cMes.setLayout(0, LAYOUT_SYSTEM);
    cMes.MesSet(no, 0x64, 0x6E, kAttr, 0, 0, 4);
    cMes.mes[0].m_cur = s8(cursor);
}

// The window backdrop. The cockpit id textures share ids with the title's (0x00, 0x0a, 0x0d, 0x13,
// 0x6f..: IdTexDataLoad logs "id already used" and keeps the title's), so the backdrop unit (texture
// 0x0a) drew the title's texture of that id and no window showed. The window's own units (ID_MSG)
// are pointed at a copy of the cockpit texture registered under a free id instead; the title's
// textures and units are untouched. The copy is registered to the cockpit owner, so close()'s
// IdTexRelease frees it, and msgWindow(0) removes the units.
constexpr u8 kIdMsg = 0x2F;  // cockpit.cpp ID_MSG (Cckpt.msgWindow)

void remap_window_ids()
{
    // Cockpit IdTexData (version 0xB): id table at +0x04, TPL table at +0x18, TexAnm table at +0x1C.
    const u32 base = pG->pArc->ofs_74 + (u32) pG->pArc;
    const u32* hdr = (const u32*) base;
    if (hdr[0] != 0xB) return;
    TexIdTbl* ids = (TexIdTbl*) (base + hdr[1]);
    TexOfsTbl* tpls = (TexOfsTbl*) (base + hdr[6]);
    TexOfsTbl* anms = (TexOfsTbl*) (base + hdr[7]);
    u8 from[4], to[4];
    int n = 0;
    IdUnit* u = IdSys.pUnit;
    for (int i = 0; i < IdSys.m_maxId; i++, u++) {
        if (u->be_flag == 0xFF || u->classNo != kIdMsg) continue;
        for (int m = 0; m < 2; m++) {
            if (m && !(u->tex_flag & 1)) continue;
            u8& id = m ? u->maskId : u->texId;
            if (id == 0xFF) continue;
            const u32 owner = g_pIdTexSys->wk[id].owner;
            if (owner == 0 || owner == TEX_OWNER_ID_COCKPIT) continue;  // the cockpit's own texture
            int j = 0;
            while (j < n && from[j] != id) j++;
            if (j == n) {
                u32 k = 0;
                while (k < ids->num && (u8) ids->ent[k].id != id) k++;
                int f = 0xFE;
                while (f > 0 && (f == 0x80 || g_pIdTexSys->wk[f].owner != 0)) f--;
                if (n == 4 || k == ids->num || f == 0 ||
                    !g_pIdTexSys->TexRegist((TEXPalette*) ((u8*) tpls + tpls->ofs[k]),
                                            (TexAnm*) ((u8*) anms + anms->ofs[k]), u8(f), TEX_OWNER_ID_COCKPIT, 0, 1))
                    continue;
                from[n] = id;
                to[n] = u8(f);
                n++;
                re4dc_log("quality: picker window texture %02x (owner %u) drawn from a cockpit copy at %02x\n", id,
                          unsigned(owner), f);
            }
            id = to[j];
        }
    }
}

void close()
{
    cMes.Delete(0);
    cMes.setLayout(0, 0);
    MesData.ptr[4] = saved_ptr4;
    Cckpt.msgWindow(0);
    IdTexRelease(TEX_OWNER_ID_COCKPIT);
    state = 0;
}
}  // namespace

// Title main menu, first arrival this boot (title.cpp Rno1 0 -> 9). Opens the window.
extern "C" void re4dc_quality_picker_open(void)
{
    saved_ptr4 = MesData.ptr[4];
    MesData.ptr[4] = (u8*) &table;
    IdTexDataLoad((void*) (pG->pArc->ofs_74 + (u32) pG->pArc), TEX_OWNER_ID_COCKPIT);
    Cckpt.msgWindow(1);
    remap_window_ids();
    state = 1;
    show(0, cursor_of(re4dc_quality()->mode));
    re4dc_log("quality: picker open (highlight %s)\n", kChoice[cursor_of(re4dc_quality()->mode)]);
}

// Per frame while open; 1 when the picker has closed (the title then builds its menu).
extern "C" int re4dc_quality_picker_move(void)
{
    MesWork* w = cMes.getWork();
    const s8 sel = w->m_sel;
    if (state == 1) {
#if RE4DC_QUALITY_DEBUG
        const bool lr = (Joy[0].on & (JOY_L | JOY_R)) == (JOY_L | JOY_R);
        if ((Joy[0].trg & JOY_X) || (lr && sel > 0)) {
            state = 2;
            debug_cursor = 0;
            show(1, 0);
            return 0;
        }
#endif
        if (sel == 0) return 0;
        if (sel == 1 || sel == 2) re4dc_quality_set_mode(kChoiceMode[sel - 1], RE4DC_QSRC_PICKER);
        re4dc_quality_picker_done();
        close();
        return 1;
    }
    if (state == 2) {
        if (sel == 0) return 0;
        if (sel == 1) {                  // "Mesh detail": toggle and redraw on the same line
            re4dc_quality_toggle(RQ_LOD_COARSE);
            show(1, 0);
            return 0;
        }
        state = 1;                       // "Done" or B: back to the picker
        show(0, cursor_of(re4dc_quality()->mode));
        return 0;
    }
    return 1;
}
