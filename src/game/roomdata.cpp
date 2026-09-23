// game/roomdata: cRoomData — the per-stage room tables (St0..St4_data_tbl: which rooms have a save
// record, their room REL file and init / main functions), the room save buffer (one 0xD8-byte
// RoomSave per room with "passed" bits and the room's own flags, copied into the save game), and
// the room REL handling (linkRelData / stopRelData / restartRelData).
#include "types.h"
#include "atari.h"
#include "global.h"
#include "room_data.h"
#include "main_mem.h"
#include "main_sub.h"
#include "scheduler.h"
#include "dvd.h"
#include "db_log.h"

extern "C" {
void* memcpy(void* dst, const void* src, unsigned int n);
}

#line 40 "D:/Bio4/Prog/roomdata.cpp"

RoomTblEntry St0_data_tbl[67] = {
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0}, {0, 0, 66, 0, 0},
    {0, 0, 66, 0, 0},
};

RoomTblEntry St1_data_tbl[33] = {
    {1, 0, 146, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0},
    {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0}, {1, 0, 149, 0, 0},
    {1, 0, 152, 0, 0}, {1, 0, 152, 0, 0}, {1, 0, 152, 0, 0}, {1, 0, 165, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 165, 0, 0},
    {1, 0, 165, 0, 0}, {1, 0, 165, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 165, 0, 0},
    {1, 0, 165, 0, 0}, {1, 0, 152, 0, 0}, {1, 0, 152, 0, 0}, {1, 0, 152, 0, 0}, {1, 0, 165, 0, 0}, {1, 0, 165, 0, 0},
    {1, 0, 165, 0, 0}, {1, 0, 165, 0, 0}, {0, 0, 146, 0, 0},
};

RoomTblEntry St2_data_tbl[46] = {
    {1, 0, 147, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 159, 0, 0}, {1, 0, 159, 0, 0},
    {1, 0, 159, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 159, 0, 0}, {1, 0, 159, 0, 0}, {1, 0, 159, 0, 0},
    {1, 0, 159, 0, 0}, {1, 0, 159, 0, 0}, {1, 0, 159, 0, 0}, {1, 0, 159, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 160, 0, 0},
    {1, 0, 160, 0, 0}, {1, 0, 160, 0, 0}, {1, 0, 160, 0, 0}, {1, 0, 160, 0, 0}, {1, 0, 160, 0, 0}, {1, 0, 160, 0, 0},
    {1, 0, 160, 0, 0}, {1, 0, 160, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 187, 0, 0},
    {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 147, 0, 0}, {1, 0, 187, 0, 0},
    {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0},
    {1, 0, 187, 0, 0}, {1, 0, 187, 0, 0}, {1, 0, 243, 0, 0}, {0, 0, 0, 0, 0},
};

RoomTblEntry St3_data_tbl[52] = {
    {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0},
    {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 148, 0, 0},
    {1, 0, 148, 0, 0}, {1, 0, 201, 0, 0}, {1, 0, 148, 0, 0}, {1, 0, 201, 0, 0}, {1, 0, 201, 0, 0}, {1, 0, 201, 0, 0},
    {1, 0, 201, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 202, 0, 0}, {1, 0, 202, 0, 0}, {1, 0, 202, 0, 0},
    {1, 0, 202, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 202, 0, 0}, {1, 0, 202, 0, 0}, {1, 0, 202, 0, 0}, {1, 0, 202, 0, 0},
    {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0},
    {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}, {0, 0, 0, 0, 0},
    {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0}, {1, 0, 203, 0, 0},
};

RoomTblEntry St4_data_tbl[18] = {
    {1, 0, 186, 0, 0}, {0, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0},
    {1, 0, 186, 0, 0}, {0, 0, 186, 0, 0}, {0, 0, 186, 0, 0}, {0, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0},
    {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0}, {1, 0, 186, 0, 0},
};

static StageTbl Room_data_tbl[10] = {
    {St0_data_tbl, 67, 0}, {St1_data_tbl, 33, 0}, {St2_data_tbl, 46, 0}, {St3_data_tbl, 52, 0}, {St4_data_tbl, 18, 0},
    {0, 0, 0}, {0, 0, 0}, {0, 0, 0}, {0, 0, 0}, {0, 0, 0},
};

static inline void U32Set(u32& d, u32 v) { d = v; }

cRoomData RoomData;

// Boot: counts the rooms of the five stage tables (total) and those with a save record (stat 1,
// num), allocates the save buffer (header + one 0xD8-byte RoomSave per room) and stamps each
// record with its stage / room id.
void cRoomData::init()
{
    u32 stage;
    int i;
    u32 ofs;
    u8* rec;

    pModule = 0;
    m_pModule_bss = 0;
    m_RelNo = 0;
    total = 0;
    for (stage = 0; stage <= 9; stage++) {
        if (Room_data_tbl[stage].tbl != 0) {
            total += Room_data_tbl[stage].num;
        }
    }
    num = 0;
    for (stage = 0; stage <= 9; stage++) {
        for (i = 0; checkRoomRange(stage, i) == 1; i++) {
            if (Room_data_tbl[stage].tbl[i].stat == 1) {
                num++;
            }
        }
    }
#line 306
    pSaveBuf = (RoomSaveHdr*) MEM_CALLOC(num * sizeof(RoomSave) + sizeof(RoomSaveHdr), 1, 13);
    pSaveBuf->size = num * sizeof(RoomSave) + sizeof(RoomSaveHdr);
    U32Set(pSaveBuf->num, num);
    pSave = (u8*) pSaveBuf + sizeof(RoomSaveHdr);
    stage = 0;
    ofs = 0;
    for (; stage <= 9; stage++) {
        for (i = 0; checkRoomRange(stage, i) == 1; i++) {
            if (Room_data_tbl[stage].tbl[i].stat == 1) {
                *(u8*) (ofs + (u32) pSave) = stage;
                rec = (u8*) (ofs + (u32) pSave);
                rec[1] = i;
                ofs += sizeof(RoomSave);
            }
        }
    }
}

// Nothing (room-set hook).
void cRoomData::initRoomSet()
{
}

// Copies the whole room save buffer into the save game image.
void cRoomData::save(void* dst)
{
    RoomSaveHdr* h = (RoomSaveHdr*) dst;

    memcpy(h, pSaveBuf, num * sizeof(RoomSave) + sizeof(RoomSaveHdr));
}

// Restores the room records from a save game image, matched by id (records of rooms the build no
// longer has are dropped).
void cRoomData::load(void* src)
{
    RoomSaveHdr* h = (RoomSaveHdr*) src;
    RoomSave* rec = (RoomSave*) ((u8*) src + sizeof(RoomSaveHdr));
    RoomSave* dst;
    u32 j;
    int i;

    for (j = 0; j < h->num; j++, rec++) {
        for (i = 0; i < num; i++) {
            dst = (RoomSave*) (i * sizeof(RoomSave) + (u32) pSave);
            if (rec->id == dst->id) {
                *dst = *rec;
                break;
            }
        }
    }
}

// Zeroes the records named in the image (keeping their ids) — the "new game from this data" case.
void cRoomData::clear(void* src)
{
    RoomSaveHdr* h = (RoomSaveHdr*) src;
    RoomSave* rec = (RoomSave*) ((u8*) src + sizeof(RoomSaveHdr));
    RoomSave* dst;
    u32 j;
    int i;
    u16 id;

    for (j = 0; j < h->num; j++, rec++) {
        // The loop with the call in its body is only rotated (entry test + bottom test) when written
        // as an explicitly guarded do/while; a `for` keeps the initial jump to the test.
        i = 0;
        if (i < num) {
            do {
                dst = (RoomSave*) (i * sizeof(RoomSave) + (u32) pSave);
                id = rec->id;
                if (id == dst->id) {
                    memclr_asm(dst, sizeof(RoomSave));
                    ((RoomSave*) (i * sizeof(RoomSave) + (u32) pSave))->id = id;
                    break;
                }
                i++;
            } while (i < num);
        }
    }
}

#if defined(RE4DC_ROOM_INDEX) && RE4DC_ROOM_INDEX
// GAME_ROOM_INDEX (game30.mk): the record index the scan below computes is a pure function of the
// static stage tables (stat / num / tbl are never written at run time; the stage modules only
// store the init / main function pointers), so it is tabulated once on first use:
// k = number of stat == 1 entries before (stage, no) in stage-then-room order, 0xFF = no record.
// The scan cost ~70 entries (each a checkRoomRange call) per lookup and the scenario / sound code
// looks the current room up many times per frame (~1.2 ms/frame at r100). Identical results for
// all 65,536 inputs (tools/roomdata_check.py); pSave is still read at call time.
static u8 s_roomRecord[67 + 33 + 46 + 52 + 18];
static u8 s_stageBase[10];
static bool s_roomRecordReady;

static void roomRecordBuild()
{
    u32 k = 0;
    u32 slot = 0;
    for (u32 s = 0; s <= 9; s++) {
        s_stageBase[s] = (u8) slot;
        for (u32 i = 0; Room_data_tbl[s].tbl != 0 && i < Room_data_tbl[s].num; i++) {
            s_roomRecord[slot++] = Room_data_tbl[s].tbl[i].stat == 1 ? (u8) k++ : (u8) 0xFF;
        }
    }
    s_roomRecordReady = true;
}

u8* cRoomData::getRoomSavePtr(u16 room)
{
    u32 stage = room >> 8;
    u32 no = room & 0xFF;
    u32 k;

    if (stage > 9 || Room_data_tbl[stage].tbl == 0 || no >= Room_data_tbl[stage].num) {
        return 0;
    }
    if (!s_roomRecordReady) {
        roomRecordBuild();
    }
    k = s_roomRecord[s_stageBase[stage] + no];
    if (k == 0xFF) {
        return 0;
    }
    return pSave + k * sizeof(RoomSave);
}
#else
// The RoomSave record of room `room` (stage << 8 | no); 0 when the room is out of range or has no
// record.
u8* cRoomData::getRoomSavePtr(u16 room)
{
    u32 stage = room >> 8;
    u8 no = room;
    u32 s;
    int i;
    int k;
    StageTbl* p;

    if (!checkRoomRange(stage, no)) {
        return 0;
    }
    if (Room_data_tbl[stage].tbl[no].stat == 0) {
        return 0;
    }
    k = 0;
    p = Room_data_tbl;
    for (s = 0; s <= 9; s++, p++) {
        for (i = 0; checkRoomRange(s, i) == 1; i++) {
            if (p->tbl[i].stat == 1) {
                if (stage == s && no == i) {
                    return pSave + k * sizeof(RoomSave);
                }
                k++;
            }
        }
    }
    return 0;
}
#endif

// Runs the room's init function from its stage table entry, if any (room entry).
void cRoomData::execInitFunc(u16 room)
{
    u8 no = room;
    u32 stage = room >> 8;
    void (*func)();

    if (checkRoomRange(stage, no) == 1) {
        func = Room_data_tbl[stage].tbl[no].init;
        if (func != 0) {
            func();
        }
    }
}

// Runs the room's per-frame main function, if any.
void cRoomData::execMainFunc(u16 room)
{
    u8 no = room;
    u32 stage = room >> 8;
    void (*func)();

    if (checkRoomRange(stage, no) == 1) {
        func = Room_data_tbl[stage].tbl[no].main;
        if (func != 0) {
            func();
        }
    }
}

// 1 when stage / room index exists in the stage tables.
int cRoomData::checkRoomRange(u8 stage, u8 no)
{
    if (stage <= 9 && no < Room_data_tbl[stage].num && Room_data_tbl[stage].tbl != 0) {
        return 1;
    }
    return 0;
}

// 1 when the room uses a room REL (rel_no) other than the one currently linked (m_RelNo): the
// stage loader must fetch it.
int cRoomData::checkRelRead(u16 room)
{
    u8 no = room;
    u32 stage = room >> 8;
    u16 rel;

    if (checkRoomRange(stage, no) == 1) {
        rel = Room_data_tbl[stage].tbl[no].rel_no;
        if (rel != 0 && rel != m_RelNo) {
            return 1;
        }
    }
    return 0;
}

// Loads the room's REL (FileTbl[rel_no]) from disc, allocates its bss (plus a backup copy for
// stop/restart), links it and runs its prolog. m_RelNo remembers which is linked.
void cRoomData::linkRelData(u16 room)
{
    u8 no = room;
    u32 stage = room >> 8;
    int id;
    int ret;

    if (checkRoomRange(stage, no) != 1) {
        return;
    }
    // The target stores x1C only after the zero test (`sth` behind the `beq`). Left: the promoted
    // value reaches the compare and the DvdRead argument as `clrlwi r3,r0,16` in the target, ours
    // folds the extension (`mr`) and compares the halfword register (#2 family).
    if (Room_data_tbl[stage].tbl[no].rel_no == 0) {
        return;
    }
    m_RelNo = Room_data_tbl[stage].tbl[no].rel_no;
#line 484
    id = DvdRead(m_RelNo, 0, 0, 0, 0, 0x104, __FILE__, __LINE__);
    while ((ret = Dvd.ReadCheck(id, 0, 0, (void**) &pModule)) != 1) {
        if (ret < 0) {
            pLog->err(0, 0, "cRoomData::readRelData(): RelDataReadError! %s", FileTbl[m_RelNo]);
            m_RelNo = 0;
            pModule = 0;
            return;
        }
        TaskSleep(1);
    }
    BitOff16(flag, 1);
    if (pModule->bssSize == 0) {
        m_pModule_bss = 0;
    } else {
#line 503
        m_pModule_bss = MEM_ALLOC(pModule->bssSize, 1, 13);
        m_pModule_bss_bak = MEM_ALLOC(pModule->bssSize, 1, 13);
    }
    DLL_Link(pModule, m_pModule_bss);
    pModule->prolog();
}

// Temporarily unlinks the room REL (flag bit0), saving its bss to the backup.
void cRoomData::stopRelData()
{
    if ((flag & 1) == 0 && pModule != 0) {
        flag |= 1;
        if (m_pModule_bss != 0) {
            memcpy(m_pModule_bss_bak, m_pModule_bss, pModule->bssSize);
        }
        DLL_Unlink(pModule);
    }
}

// Re-links a stopped room REL and restores its bss from the backup.
void cRoomData::restartRelData()
{
    if ((flag & 1) && pModule != 0) {
        BitOff16(flag, 1);
        DLL_Link(pModule, m_pModule_bss);
        if (m_pModule_bss != 0) {
            memcpy(m_pModule_bss, m_pModule_bss_bak, pModule->bssSize);
        }
    }
}

// "Passed" bit `bit` (0..7, from the top) of the room's save record; 0 without a record.
int cRoomData::checkPassed(u16 room, int bit)
{
    u8* p = getRoomSavePtr(room);

    if (p == 0) {
        return 0;
    }
    return p[2] & (0x80 >> bit);
}

// Sets "passed" bit `bit` of the room's save record.
void cRoomData::setPassed(u16 room, int bit)
{
    u8* p = getRoomSavePtr(room);

    if (p != 0) {
        p[2] |= 0x80 >> bit;
    }
}
