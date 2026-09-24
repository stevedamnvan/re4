// D367 VMU saves: the RE4DCDBG debug slot (VMU_DEBUG_SLOT=1, test builds only; compiled out of
// release). Game side of design-vmu section 4.
//  - Chord: hold L + START for 60 polls in play (platform/pad.cpp reports the port-A bits; START is
//    masked from the game while L is held, as re4dcBlockDebugChords already does for real input).
//  - Refused (logged "dbg: busy") unless the game is at a clean point: in play (Rno0 3 / Rno1 0),
//    no event holding the game, no sub screen / card screen / option screen, no stop flags, not in
//    a door or room transition, at least 60 room frames since the room was entered.
//  - Serializes a save image exactly as the game's own room checkpoint would (SaveKind -1,
//    sub_pos / sub_angle = Leon now) into a COPY: pG, RoomData, the sub screen word, the merchant
//    and ItemMgr.save are read, nothing in the game is written. No GameSaveSave / SetGameTime /
//    makeSaveData (they change SaveKind, sub_pos, save_cnt and play_time).
//  - Writes RE4DCDBG synchronously on the game thread at that frame boundary: the file is the
//    save stream + 256 B of extras (build, RNG state, vblank, room, position) + a last block with
//    the diagnostic ring. Memory: one transient game-heap block (freed before returning); the
//    KOS heap has no room for it on the m1 recipe (design 4.3 assumed a background write from
//    KOS memory; see STATE.md). Play pauses for the write (Flycast ~2 s, console ~1.5-3.5 s).
//  - Load: FILE 20 in the normal Load list (platform/card.cpp maps bh4_data19 to RE4DCDBG); after
//    the load the first room entry restores the RNG and switches the start to continue semantics,
//    so Leon appears at the saved position.
//  - Ring: 15 x 32 B records in RAM (debug save, halt, fault, panic, room enter, busy), written as
//    the file's last block by the next debug save.
#if RE4DC_VMU_DEBUG_SLOT
#include "types.h"
#include "global.h"
#include "main_mem.h"
#include "sscrn.h"
#include "item.h"
#include "player.h"
#include "merchant.h"
#include "room_data.h"
#include "re4dc_platform.h"
#include "vmu_store.h"
#include "lz_small.h"
extern "C" int OSCheckHeap(int);
#include <string.h>
#include <stdio.h>

typedef s64 OSTime;
extern "C" {
OSTime OSGetTime();
void OSTicksToCalendarTime(OSTime ticks, void* td);
u32 CRCCalc(u8* data, u32 len);
u32 re4dc_vi_retrace_count(void);
unsigned short re4dc_rnd_state(void);  // src/game/rnd.cpp (vmusave.mk builds it with the accessor)
unsigned long long re4dc_ssb_us();
}
void RndInit(u16 seed);

namespace {
// Image and file layout (card.cpp / platform/card.cpp).
constexpr u32 kSaveHdr = 0x2000, kPayload = 0x2200, kSaveCrc = 0xEAF8, kRaw = kSaveCrc - kPayload;
constexpr u32 kGame = 0x2034, kItems = 0x572C, kRoom = 0x6930, kSscrn = 0xE7D0, kMerchant = 0xE7D4;
constexpr u32 kVms = 640, kR4 = 32, kInfo = kVms + kR4, kStream = kInfo + 512, kExtras = 256;
constexpr u32 kOutBytes = 24 * 1024;  // file buffer: 1184 B prefix + stream + extras + ring
constexpr u32 kHeld = 60;

struct RingRec {  // 32 B
    u8 kind, source;
    u16 room;
    u32 frame, vbl, a, b;
    u16 heap_kb, stage;
    u32 seq;
    u16 pad, crc;
};
struct Ring {
    char magic[4];  // "R4RG"
    u32 next;
    RingRec rec[15];
    u8 pad[512 - 8 - 15 * 32];
};
static_assert(sizeof(RingRec) == 32 && sizeof(Ring) == 512, "ring layout");
Ring ring = {{'R', '4', 'R', 'G'}, 0, {}, {}};

struct Extras {  // 256 B, little-endian (SH-4)
    char magic[4];  // "R4DX"
    u32 version;
    char build[24];  // __DATE__ " " __TIME__
    u32 vbl, frame;
    u16 random, room;
    u8 part, source, pad[2];
    f32 pos[3], angle;
    u32 heap4_free;
    char fixture[16];
    u8 rest[256 - 4 - 4 - 24 - 8 - 4 - 4 - 16 - 4 - 16];
};
static_assert(sizeof(Extras) == kExtras, "extras layout");

u16 crc16(const u8* p, unsigned n)
{
    u16 c = 0xFFFF;
    while (n--) {
        c ^= (u16) (*p++ << 8);
        for (int i = 0; i < 8; ++i) c = (c & 0x8000) ? (u16) ((c << 1) ^ 0x1021) : (u16) (c << 1);
    }
    return c;
}

volatile u32 held, armed = 1, request;
u32 saves;
bool load_pending;
u16 load_random;

void put_be32(u8* p, u32 v) { p[0] = (u8) (v >> 24); p[1] = (u8) (v >> 16); p[2] = (u8) (v >> 8); p[3] = (u8) v; }

// The clean point (design 4.3): the conditions the game uses before it lets the player open the
// sub screen or options, plus no stop / transition flags.
const char* busy_reason(u32 room_frames)
{
    if (!pG || !pPL) return "no game";
    if (pG->Rno0 != 3 || pG->Rno1 != 0) return "not in play";
    if (pG->Status_flg[1] & 0x10000000) return "event";
    if (pG->Status_flg[2] & 0x80000) return "event";
    if (SubScreenWk.type) return "sub screen";
    if (pG->System_flg & (0x1000 | 0x100000 | 0x1000000)) return "card screen / transition";
    if (pG->Stop_flg) return "stopped";
    if (room_frames < 60) return "room entry";
    return nullptr;
}

int do_save(u32 source)
{
    const unsigned long long t0 = re4dc_ssb_us();
    const u32 bytes = 0xEB00 + kOutBytes + LZS_TABLE_BYTES + 512 + 512 + 13 * 512;
    // Heap 4 (the room heap) at the frame boundary: nothing in the game is mid-way through an
    // allocation here. A failure refuses the save (DBG: NOMEM, ring kind 7) and never halts.
    const int heap4_before = Heap[4].handle >= 0 ? OSCheckHeap(Heap[4].handle) : -1;
    u8* mem = (u8*) MEM_ALLOC(bytes, 0, 4);
    if (!mem) {
        re4dc_log("dbg: NOMEM (%u B, heap4 free %d): save refused\n", (unsigned) bytes, heap4_before);
        RingRec& r = ring.rec[ring.next % 15];
        memset(&r, 0, sizeof(r));
        r.kind = 7;
        r.room = pG->room_id;
        r.vbl = re4dc_vi_retrace_count();
        r.a = bytes;
        r.seq = ++ring.next;
        r.crc = crc16((const u8*) &r, 30);
        return -1;
    }
    u8* img = mem;
    u8* out = img + 0xEB00;
    unsigned short* hash = (unsigned short*) (out + kOutBytes);
    u8* root = (u8*) hash + LZS_TABLE_BYTES;
    u8* fat = root + 512;
    u8* dir = fat + 512;
    memset(img, 0, 0xEB00);
    // --- the save image, read-only from the game (card.cpp makeSaveData order)
    *(u32*) (img + 0x2004) = 0x116;
    OSTicksToCalendarTime(OSGetTime(), img + 0x2008);
    *(u32*) (img + 0x2030) = 1;
    memcpy(img + kGame, (u8*) pG + 0x4F80, 0x36F8);
    const u32 base = (u32) pG + 0x4F80;
    memcpy(img + kGame + ((u32) &pG->sub_pos - base), &pPL->pos, sizeof(Vec));
    memcpy(img + kGame + ((u32) &pG->sub_angle - base), &pPL->ang.y, sizeof(f32));
    const s32 kind = -1;  // the room checkpoint kind (r101.cpp etc.): continue at sub_pos
    memcpy(img + kGame + ((u32) &pG->SaveKind - base), &kind, sizeof(kind));
    ItemMgr.save(img + kItems);
    RoomData.save(img + kRoom);
    SscrnDataSave((u32*) (img + kSscrn));
    MerchantDataSave(img + kMerchant);
    img[0x203D] = img[0x5408];
    *(u32*) (img + kSaveHdr) = CRCCalc(img + 0x2004, 0x1FC);
    // --- file: VMS header + icon, R4DC header, SaveInfo, LZ stream, extras; ring block last
    const int comp = lzs_encode(img + kPayload, kRaw, out + kStream, kOutBytes - kStream - kExtras - 1024, hash);
    int rc = -1, blocks = 0, inplace = 0;
    if (comp > 0 && lzs_verify(out + kStream, (unsigned) comp, img + kPayload, kRaw) == (int) kRaw) {
        memset(out + kVms, 0, kR4);
        memcpy(out + kVms, "R4DC", 4);
        out[kVms + 4] = 1;
        out[kVms + 5] = 4;   // kind: debug
        out[kVms + 6] = 19;  // FILE 20
        put_be32(out + kVms + 8, ++saves);
        put_be32(out + kVms + 12, kRaw);
        put_be32(out + kVms + 16, (u32) comp);
        put_be32(out + kVms + 20, CRCCalc(img + kSaveHdr, kSaveCrc - kSaveHdr));
        memcpy(out + kInfo, img + kSaveHdr, 512);
        Extras xs;  // built aligned, copied to its unaligned place after the stream
        Extras* x = &xs;
        memset(x, 0, sizeof(*x));
        memcpy(x->magic, "R4DX", 4);
        x->version = 1;
        snprintf(x->build, sizeof(x->build), "%s %s", __DATE__, __TIME__);
        x->vbl = re4dc_vi_retrace_count();
        x->frame = pG->Frame_cnt;
        x->random = re4dc_rnd_state();
        x->room = pG->room_id;
        x->part = pG->Part;
        x->source = (u8) source;
        memcpy(x->pos, &pPL->pos, sizeof(x->pos));
        x->angle = pPL->ang.y;
        memcpy(out + kStream + comp, &xs, sizeof(xs));
        char desc[33];
        snprintf(desc, sizeof(desc), "DEBUG SLOT  R%03X", (unsigned) pG->room_id);
        // ring record for this save goes in before the ring is copied
        RingRec& r = ring.rec[ring.next % 15];
        memset(&r, 0, sizeof(r));
        r.kind = 1;
        r.source = (u8) source;
        r.room = pG->room_id;
        r.frame = pG->Frame_cnt;
        r.vbl = x->vbl;
        r.a = (u32) comp;
        r.seq = ++ring.next;
        r.crc = crc16((const u8*) &r, 30);
        const u32 size = vmus_package(out, desc, kR4 + 512 + (u32) comp + kExtras);
        memcpy(out + size, &ring, sizeof(ring));
        blocks = (int) (size / 512 + 1);
        VmuStore st{};
        rc = vmus_pick(&st);
        if (!rc) rc = vmus_mount(&st, root, fat, dir);
        if (!rc && vmus_find(&st, "RE4DCDBG") >= 0) rc = vmus_delete(&st, "RE4DCDBG");  // the debug slot alone is at risk
        if (!rc) rc = vmus_write(&st, "RE4DCDBG", out, (unsigned) blocks, nullptr, &inplace);
    }
    Mem_free(mem);
    const int heap4_after = Heap[4].handle >= 0 ? OSCheckHeap(Heap[4].handle) : -1;
    re4dc_log("dbg: save %u %s comp=%d blocks=%d room=%03x rng=%04x frame=%u us=%u rc=%d heap4=%d->%d\n",
              (unsigned) saves, rc ? "ERR" : "OK", comp, blocks, (unsigned) pG->room_id,
              (unsigned) re4dc_rnd_state(), (unsigned) pG->Frame_cnt, (unsigned) (re4dc_ssb_us() - t0), rc,
              heap4_before, heap4_after);
    return rc;
}
}  // namespace

extern "C" {

// platform/pad.cpp, every poll: port A buttons (real | scripted). Returns the bits to clear from
// the scripted input (START while L is held), as the pad layer already does for real input.
unsigned re4dc_dbgslot_pad(unsigned buttons)
{
    const unsigned chord = 0x0040 | 0x1000;  // PAD_TRIGGER_L | PAD_BUTTON_START
    if ((buttons & chord) == chord) {
        if (++held == kHeld && armed) {
            request = 1;
            armed = 0;
        }
    } else {
        held = 0;
        armed = 1;
    }
    return (buttons & 0x0040) ? 0x1000 : 0;
}

// Test fixture /cd/dc/dbgslot.txt: "save <room frames>" lines (up to 4) request a debug save
// as the chord would, once each, in the first room that reaches that frame count.
int re4dc_fixture_read(const char* path, char* buffer, unsigned size);

// Top of gameMainLoop (ui_bridge.cpp re4dc_room_cycle_poll), game thread.
void re4dc_dbgslot_poll(unsigned generation, unsigned room_frames)
{
    static bool loaded;
    static unsigned at[4], n, fired;
    (void) generation;
    if (!loaded) {
        loaded = true;
        char text[128];
        const int len = re4dc_fixture_read("/cd/dc/dbgslot.txt", text, sizeof(text) - 1);
        if (len > 0) {
            text[len] = 0;
            for (char* line = text; line && *line && n < 4;) {
                char* next = strchr(line, '\n');
                if (next) *next++ = 0;
                unsigned f;
                if (sscanf(line, "save %u", &f) == 1) at[n++] = f;
                line = next;
            }
            re4dc_log("dbg: fixture %u saves\n", n);
        }
    }
    unsigned source = 1;
    if (fired < n && room_frames == at[fired]) {
        ++fired;
        request = 1;
        source = 2;
    }
    if (!request) return;
    request = 0;
    const char* why = busy_reason(room_frames);
    if (why) {
        re4dc_log("dbg: busy (%s)\n", why);
        RingRec& r = ring.rec[ring.next % 15];
        memset(&r, 0, sizeof(r));
        r.kind = 6;
        r.room = pG ? pG->room_id : 0;
        r.vbl = re4dc_vi_retrace_count();
        r.seq = ++ring.next;
        r.crc = crc16((const u8*) &r, 30);
        return;
    }
    do_save(source);
}

// Diagnostic ring entry (kind 2 halt, 3 fault, 4 panic, 5 room enter; 1 save, 6 busy, 7 nomem). IRQ-safe: BSS only.
void re4dc_dbgslot_ring(unsigned kind, unsigned a, unsigned b)
{
    RingRec& r = ring.rec[ring.next % 15];
    r.kind = (u8) kind;
    r.source = 0;
    r.room = pG ? pG->room_id : 0;
    r.frame = pG ? pG->Frame_cnt : 0;
    r.vbl = re4dc_vi_retrace_count();
    r.a = a;
    r.b = b;
    r.heap_kb = 0;
    r.stage = 0;
    r.seq = ++ring.next;
    r.pad = 0;
    r.crc = crc16((const u8*) &r, 30);
}

// platform/card.cpp, after FILE 20 (RE4DCDBG) was loaded into the game's buffer.
void re4dc_dbgslot_loaded(const void* extras)
{
    Extras xs;
    memcpy(&xs, extras, sizeof(xs));
    const Extras* x = &xs;
    if (memcmp(x->magic, "R4DX", 4)) return;
    load_pending = true;
    load_random = x->random;
    re4dc_log("dbg: FILE 20 loaded (build %.24s, room %03x, rng %04x)%s\n", x->build, (unsigned) x->room,
              (unsigned) x->random, strncmp(x->build, __DATE__, 11) ? " build mismatch" : "");
}

// ui_bridge.cpp re4dc_room_enter (gameRoomMemInit, after heap 4 was replaced).
void re4dc_dbgslot_room_enter()
{
    re4dc_dbgslot_ring(5, pG ? pG->room_id : 0, 0);
    if (!load_pending || !pG) return;
    load_pending = false;
    // Continue semantics (GameContinue with SaveKind -1): start at sub_pos / sub_angle.
    pG->System_flg = (pG->System_flg & ~0x100u) | 0x80000u;
    pG->NextPos = pG->sub_pos;
    pG->NextY = pG->sub_angle;
    RndInit(load_random);
    re4dc_log("dbg: FILE 20 start at (%d,%d,%d) rng %04x\n", (int) pG->sub_pos.x, (int) pG->sub_pos.y,
              (int) pG->sub_pos.z, (unsigned) load_random);
}

}  // extern "C"
#endif  // RE4DC_VMU_DEBUG_SLOT
