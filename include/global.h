#ifndef GLOBAL_H
#define GLOBAL_H

#include "types.h"
#include "vec.h"
#include "camera.h"

// Archive header at pG->pArc: a table of file offsets to the sub-files. Only the entries that
// matched units use are named.
struct ArcFile {
    u8 pad_0[0x10];
    u32 ofs_10;   // 0x10  specular data (read: CoreDataRead -> SpecularInit)
    u32 ofs_14;   // 0x14  core effect data (eff_sys: EspDataLoad owner 0)
    u32 ofs_18;   // 0x18  room texture data (room_tex)
    u32 ofs_1C;   // 0x1C  vibration pattern table (pl_dmg: VibSetData)
    u32 ofs_20;   // 0x20  obstacle model bin (obj20 SetObaModel)
    u32 ofs_24;   // 0x24  obstacle model tpl
    u32 ofs_28;   // 0x28  message tables (mes: MesData.ptr[0..2])
    u32 ofs_2C;   // 0x2C  core light data (game: cLightMgr::roomInit core cLit)
    u32 ofs_30;   // 0x30  core camera data (game: CameraControl::CoreDataRead)
    u32 ofs_34;   // 0x34
    u32 ofs_38;   // 0x38
    u32 ofs_3C;   // 0x3C  light path data (game: cLightMgr::initPath)
    u32 ofs_40;   // 0x40  global illumination texture (read: CoreDataRead -> GlobalIlmTexInit)
    u32 ofs_44;   // 0x44  specular data 2..4 (SpecularInit)
    u32 ofs_48;   // 0x48
    u32 ofs_4C;   // 0x4C
    u32 ofs_50;   // 0x50  debug effect data (eff_sys: EspDataLoad owner 0xD1)
    u32 ofs_54;   // 0x54  message table type 3 (mes: MesData.ptr[3])
    u32 ofs_58;   // 0x58  item examine light cuts 0..4 (examine ItemExamine::init)
    u32 ofs_5C;   // 0x5C
    u32 ofs_60;   // 0x60
    u32 ofs_64;   // 0x64
    u32 ofs_68;   // 0x68
    u32 ofs_6C;   // 0x6C  system message table (dvd: MesData.ptr[4])
    u32 ofs_70;   // 0x70  TV-mode message table (tv_mode)
    u32 ofs_74;   // 0x74  HUD id textures (cockpit: IdTexDataLoad(.., 4))
    u32 ofs_78;   // 0x78
    u32 ofs_7C;   // 0x7C  life meter id data (cockpit, type 0x21)
    u32 ofs_80;   // 0x80  action button id data (cockpit, type 0x20)
    u32 ofs_84;   // 0x84  count-down id data (cockpit, type 0x23)
    u32 ofs_88;   // 0x88  HUD id data type 0x30 (cockpit)
    u32 ofs_8C;   // 0x8C
    u32 ofs_90;   // 0x90
    u32 ofs_94;   // 0x94  message window id data (cockpit, type 0x2F)
    u32 ofs_98;   // 0x98  bullet icon id data (cockpit, type 0x32)
    u32 ofs_9C;   // 0x9C  sub-mission widget id data (stage)
};

// Player archive at pG->pPlArc: a table of byte offsets to the player's sub-files (models, textures,
// motions, faces...). The pl_* units index it directly; the pointer is `ofs + (u32) arc`.
struct PlArc {
    u32 ofs[0x100];   // pl_knife indexes up to 0x87
};
#define PL_ARC_PTR(arc, no) ((void*) ((arc)->ofs[no] + (u32) (arc)))

// Room archive at pG->pRoomArc: offsets to its sub-files (GetDataExt finds them by tag; ctrl14 indexes it).
struct RoomArc {
    u32 ofs[0x10];
};
#define ROOM_ARC_PTR(arc, no) ((void*) (((RoomArc*) (arc))->ofs[no] + (u32) (arc)))

// TEV stage / texture map / texture coord counters the model renderer allocates from (pG+0x184).
struct GxStageWork {
    s32 tevStage;  // 0x00
    s32 texMap;    // 0x04
    s32 texCoord;  // 0x08
};

// Item left in a room (pG->save_item[256], game/sce_at.cpp), 16 bytes.
struct ITEM_SAVE_WORK {
    u8 item_type;          // 0x00  0 item area, 1 item handed to an area
    u8 item_at;          // 0x01
    s8 item_eff;       // 0x02
    u8 pad_3;
    u16 room_no;         // 0x04  0 = free
    u16 item_id;           // 0x06
    u16 item_num;          // 0x08
    s16 pos[3];       // 0x0A  / 10
};

// Global game work (`pG`, game/main.cpp). Offsets come from the cam_ctrl unit; extend the
// pads as other units reveal more fields, never rewrite.
struct GlobalWork {
    s32 dev_mode;          // 0x00  1 = development hardware (main: OSGetConsoleType & 0xF0000000)
    u8 shooting_mode;      // 0x04  shooting range mode (title: shoot_mode[] name table; em10/em39: 9999 damage, marker lines)
    u8 save_no;            // 0x05  save file number last loaded/saved (card dataSelect)
    u8 pad_6[2];
    u32 CardStatus;                // 0x08  card flags (card: 4 loaded, 8/0x10/0x20/0x40/0x80 CardSave modes, bit 31 first check done; main: bit 31 saved into pRK->x3C)
    u8 pad_C[4];
    u64 card_serial;       // 0x10  serial of the card the save file came from (card)
    void* pFont;           // 0x18  ROM font header (dvd: RomFontSetting)
    s32 IsMessageInit;     // 0x1C  1 = the message system is usable (mes sets it; dvd error screen tests it)
    union {
        u32 mode32;        // 0x20  x20..x23 as one word (game: gameOption saves/restores it in Game.mode_bak)
        struct {
            u8 Rno0;        // 0x20  game task step (game_func_tbl index; main_sub: 3/4/6 allow the blur filter)
            u8 Rno1;        // 0x21  sub step (room_jmp roomJumpExit clears x21..x23 with x20 = 4)
            u8 Rno2;
            u8 Rno3;
        };
    };
    u32 vtx_buf_no;        // 0x24  double-buffer index into cModelInfo::pPosBuf/pNrmBuf (mirror)
    union {
        u16 next_room;     // 0x28  room id (stage << 8 | room) being entered (snd: room BGM / door tables)
        struct {
#if defined(__PPC__)
            u8 next_stage; // 0x28  (sce_at sceAtFunc_door stores the door destination byte by byte)
            u8 next_room_no;  // 0x29
#else
            // Little-endian: the halfword's high byte (the stage) is the second byte. The GC order
            // made a 1:03 door read as next_room 0x301 (warp-r101-pbdoor2: HALT, no r301 container);
            // symmetric ids such as 0x101 hid it.
            u8 next_room_no;
            u8 next_stage;
#endif
        };
    };
    u8 next_point;         // 0x2A  spawn point in the next room (room_jmp CRoomInfo::setNextPos clears it)
    u8 pad_2B;
    Vec NextPos;          // 0x2C  player position in the next room (room_jmp)
    f32 NextY;        // 0x38
    void* pStFnt;      // 0x3C  stage/event font buffer (mes: MessageControl::stageInit)
    void* pRoom;        // 0x40  current room archive (GetDataExt(pG->pRoomArc, "STB", 0))
    void* pWep;         // 0x44  weapon data (read: ReadWepData)
    struct ArcFile* pArc;       // 0x48  current archive: offsets to its sub-files (room_tex, tv_mode)
    void* pOption;     // 0x4C  SS/<lang>/option.dat (read: OptionDataRead)
    struct PlArc* pPlayer;       // 0x50  player archive (pl_leon/pl_push: model, motion, face data offsets)
    u32 System_flg;          // 0x54
    u32 Disp_flg;          // 0x58
    u32 game_start_time;         // 0x5C  OSTicksToSeconds at the last InitGameTime/SetGameTime
    u32 Debug_flg[4];      // 0x60  debug option bits ([2] 0x04000000 / [3] 0x00200000 shown in the title debug page)
    f32 mot_speed;         // 0x70  motion frame step per game frame (MotionSequenceCtrl: speed * mot_speed)
    Camera Cam;            // 0x74 .. 0x16C  (Cam.param at 0x118)
    u8 pad_16C[4];
    u32 Stop_flg;          // 0x170  stop flags (debug tools save/restore it)
    u32 Room_flg[4];       // 0x174  per-room flag words: [0] room scripts (pl_sub joyFireOn 0x20000000 in room 11C), [1] objRobo WalkHitCk bit31 = the statue caught the player, [2]/[3] cleared by SceAtWorkLoopInit every frame
    GxStageWork gxStage;   // 0x184  TEV stage / texmap / texcoord counters of the model renderer (mirror)
    Mtx mtxPalette[0xF8];  // 0x190  skinning matrix palette (trans.cpp calcWeightMat / MakeWeightPalette)
    u8 pad_3010[0x4F10 - 0x3010];  // 0x3010  GXTexObj texObj[0xF8] (trans.cpp GxWork view of 0x184..0x4F14)
    s32 prim_base;         // 0x4F10  primitive buffer: first entry of the current frame (debug PrimitiveBuffDisp)
    f32 prim_rate;         // 0x4F14  worst free ratio of the primitive buffer seen so far
    s32 prim_cnt;          // 0x4F18  entries used so far this frame
    s32 nPrim;          // 0x4F1C  entries per frame (game: ConsGetRoomValue(8), 0x8000 while stopped)
    void* RoomMes;        // 0x4F20  room message table (mes: MesData.ptr[1])
    void* pCamCore;    // 0x4F24  core camera data ("B40x")
    void* pCamRoom;    // 0x4F28  room camera data ("B40x")
    void* Rtp;        // 0x4F2C  room "RTP" data (read: ReadAreaData)
    void* pEmi;        // 0x4F30  room "EMI" data
    void* pOsd;        // 0x4F34  room "OSD" data
    s8 AreaNo;            // 0x4F38  block trigger area the player stands in (block.cpp), -1 = none
    u8 pad_4F39[3];
    Vec bell_pos;          // 0x4F3C  floor point under the rung bell (obj14; flags_5010 bit29)
    u8 bell_stat;          // 0x4F48  2 = bell rung
    u8 pad_4F49[0x4F70 - 0x4F49];
    Vec quake_ofs;         // 0x4F70
    u8 weapon_no_old;
    u8 door_no;            // 0x4F7D  door used to enter the room (index into the DSE door SE table)
    u16 cdown_add_sec;     // 0x4F7E  seconds to add to the count-down (cockpit CountDown::move consumes it)
    u8 save_data_start_addr[4];  // 0x4F80  start of the save block (game: cGameSave copies 0x4F80..0x8678)
    s32 point;             // 0x4F84  difficulty point (game GameAddPoint, 0..0x2AF7)
    u8 Game_level;         // 0x4F88  adaptive difficulty rank 1..10 = point / 1000 (em2d/em10 branch on > 1/3/6/== 10)
    u8 x4F89;
    u8 chapter;            // 0x4F8A  chapters ended (sce_com SceChapterEnd: SceSys chapter + 1)
    u8 pad_4F8B;
    u16 save_cnt;          // 0x4F8C  times saved (card makeSaveData increments it)
    u16 game_cnt;          // 0x4F8E  games cleared: nonzero = new round (merchant full tables; 1 = Merchant2ndRoundInit on load)
    u16 r_continue_cnt;    // 0x4F90  continues in this room (GameContinue increments; room jump / scene change clear it)
    u8 snd_tbl_no;         // 0x4F92  room BGM/stream table row (0..4) selected by the game flow
    u8 language;           // 0x4F93  game language (main: pSys->language; title: language_tbl[])
    u32 play_time;         // 0x4F94  seconds (SetGameTime accumulates into it)
    u32 peseta;            // 0x4F98  money (ss_shop buy/sell, item pickups; PlSelect swaps it with peseta_bak)
    union {
        u32 room_id32;     // 0x4F9C  stage/room and the two bytes after them as one word (em_set EmSetDie: `& 0xFFFF0000`)
        u16 room_id;       // 0x4F9C  stage << 8 | room as one halfword (obj14: room 004 test)
        struct {
            u8 stage_no;   // 0x4F9C
            u8 room_no;    // 0x4F9D
            u8 Part;       // 0x4F9E  spawn point in the current room (copied to Part_old / next_point)
            u8 JumpPoint;  // 0x4F9F  room jump point (title/room_jmp debug jump; room scripts branch on 1/2)
        };
    };
    union {
        u16 room_id_prev;  // 0x4FA0  room_id of the previous room (room_jmp CRoomInfo::setNextPos)
        struct {
            u8 stage_prev; // 0x4FA0  stage the current room data was loaded for (stage.cpp)
            u8 room_prev;  // 0x4FA1
        };
    };
    u8 Part_old;              // 0x4FA2  copy of x4F9E (room_jmp)
    s8 em_list_no;          // 0x4FA3  enemy list currently loaded (stage.cpp), -1 = none
    u16 pl_life;           // 0x4FA4  (compared as s16 by the debug tools)
    u16 pl_life_max;       // 0x4FA6
    u16 ashley_life;          // 0x4FA8  Ashley
    u16 ashley_life_max;      // 0x4FAA
    u8 pad_4FAC[4];
    u8 weapon_no;             // 0x4FB0  equipped weapon (cPlayer::weaponLoad(no, type))
    u8 weapon_type;           // 0x4FB1
    u8 bullet_type;        // 0x4FB2  equipped weapon slot num >> 13 (sscrn SubScreenExit re-arms when it changed)
    u8 weapon_lv_power;    // 0x4FB3  firepower tune level (em_dm_val: WeaponLevelTbl column, clamped to 7)
    u8 weapon_lv_speed;    // 0x4FB4  firing speed tune level (PlShotFrameTbl column; item cItemMgr::arm)
    u8 weapon_lv_blt;      // 0x4FB5  capacity tune level (item cItemMgr::arm)
    u8 pad_4FB6[2];
    union {
        u32 x4FB8_32;      // 0x4FB8  the four bytes as one word (title: `& 0xFF0000FF` == 0 -> Leon with the default Ashley)
        struct {
            u8 pl_type;      // 0x4FB8  player character: 0 Leon, 1 Ashley, 2 Ada, 3 HUNK, 4 Krauser, 5 Wesker, 6 Leon+Ashley
            u8 pl_costume;    // 0x4FB9  player costume (pl_leon: 2 = no cloth simulation)
            u8 weapon_lv_reload;      // 0x4FBA
            u8 game_costume;   // 0x4FBB  Ashley costume (pl_cloth: 1 = ribbon + lapels instead of skirt + sweater)
        };
    };
    u8 pad_4FBC[2];
    u16 pl_flag;        // 0x4FBE  bit0: player data changed (pl_sub PlSelect/PlSetCostume/PlChangeData)
    Vec sub_pos;           // 0x4FC0  sub character start position (sce_sys ScenarioRoomInit)
    f32 sub_angle;         // 0x4FCC
    u8 pad_4FD0[0x500C - 0x4FD0];
    u32 Status_flg[4];     // 0x500C  game status bits ([3] 0x10000000: main_sub letterbox scissor)
    u32 em_dead[12][8];    // 0x501C  per enemy list (emlist_no): one bit per list entry, set when the enemy died (em_set)
    u32 item_flags[8];     // 0x519C  "ITEM_SET" flag words (t_flag; merchant: [0] bit 0x10000000 = item 0x40 sold)
    u32 Item_find_flg;        // 0x51BC  (stage: 0x4 stage-1 loaded, 0x40000 sub-mission 1 done)
    u32 Scenario_flg[2];   // 0x51C0  scenario progress bits set by the room scripts ([0]: stage route flags)
    u32 door_flags_51C8;   // 0x51C8  (game DoorFlagInit presets bits of these three words)
    u32 door_flags_51CC;   // 0x51CC
    u32 door_flags_51D0;   // 0x51D0
    u8 pad_51D4[0x51DC - 0x51D4];
    u32 door_unlock[2];    // 0x51DC  one bit per locked door (sce_at: SceAtWork::lockFlag)
    u32 Frame_cnt;         // 0x51E4  frame counter (em: `& 3` vs emset_no staggers per-enemy work; tools blink on % 30)
    u32 save_free_work[64];      // 0x51E8  scenario free words (sce_com SetFree/GetFree)
    u8 Em_list[0x2000];     // 0x52E8  enemy list (ESL file) read by stage.cpp
    ITEM_SAVE_WORK item_save[0x100];  // 0x72E8  items left in rooms (sce_at SceAtSetSaveItem)
    u32 ope_x82E8;         // 0x82E8  sub screen "Ope" block (sscrn: memset(&pG->ope_x82E8, 0, 0x44) in SubScreenGameInit)
    u8 ope_ow_type;        // 0x82EC  (sscrn OpeOwTypeSet)
    u8 pad_82ED[3];
    u32 ope_mdt_bits[3];   // 0x82F0  one bit per mdt number (sscrn OpeSetMdtNo)
    u32 ope_x82FC;         // 0x82FC  (sscrn OpeOwTypeSet clears it)
    s32 ope_mdt_no;        // 0x8300  (sscrn OpeGetMdtNo / OpeSetMdtNo; SubScreenGameInit: 0x18)
    u8 pad_8304[0x832C - 0x8304];
    u32 peseta_bak;        // 0x832C  the other character's money (PlSelect swaps it with peseta; r206 adds it back)
    s16 shootingScore[4];  // 0x8330  shooting range scores (game clearGlobalSaveData keeps 0x8330..0x8338 across the clear)
    u16 c_continue_cnt;             // 0x8338  (sce_com SceChapterEnd clears it with the kill/shot counters)
    u16 g_continue_cnt;             // 0x833A  (option: result screen counter next to x8338)
    u32 c_kill_cnt;        // 0x833C  enemies killed (em_set EmSetDieCnt)
    u32 g_kill_cnt;       // 0x8340
    u32 c_hit_cnt;           // 0x8344  (pl_wep PlWepHitCheck2: shots that hit something)
    u32 g_hit_cnt;          // 0x8348
    u32 c_shot_cnt;         // 0x834C  shots fired
    u32 g_shot_cnt;        // 0x8350
    u8 game_mode;          // 0x8354  difficulty: 1 VERY_EASY, 3 EASY, 5 NORMAL, 6 HARD (title game_mode_tbl; main systemWorkInit: 5)
    u8 pad_8355[3];
    s32 SaveKind;          // 0x8358  save kind passed to cGameSave::save (stage: 3 = no enemy list reload; -1 on continue)
    u8 pad_835C[0x8678 - 0x835C];
    s8 debug_mode;         // 0x8678  debug page number (t_page), 0xF = camera rail debug draw
    s8 debug_disp;         // 0x8679  debug page shown by the game (0 = off); t_page/t_sc_shot edit it
    u8 pad_867A[0x8680 - 0x867A];  // sizeof == 0x8680 (main: memclr_asm(pG, sizeof(GlobalWork)))
};

extern GlobalWork* pG;
extern GlobalWork Global;  // the instance pG points at (game/main.cpp); static initializers take its address

// System save block (game/main.cpp `SystemSave`, 0x38 bytes; layout partially known).
struct SystemSaveWork {
    u32 Config_flg;  // 0x00  CFG_* bits
    u32 Extra_flg;   // 0x04
    u8 pad_8[0x38 - 0x08];
};
extern SystemSaveWork SystemSave;

// stage_no/room_no read as one u16 (stage << 8 | room), as cRoomData::getRoomSavePtr wants it.
#define G_ROOM_ID (*(u16*) &pG->stage_no)

// Flag helpers. The original sets/clears bits through an inline helper taking a reference: the
// store is then a plain scalar access, so GCC 2.95 assumes it may clobber `pG` and reloads it
// (and does not merge consecutive updates). A direct `pG->flags |= x` compiles differently.
static inline void BitOn(u32& f, u32 b) { f |= b; }
static inline void BitOff(u32& f, u32 b) { f &= ~b; }

// Same mechanism for a plain float store. The original compiler never hoisted a load of a
// global (pG, a static float) above a store made through `this`/a member pointer; ProDG 3.9.3
// does, unless the store goes through a scalar reference. Use where the target asm shows the
// global load after such a store (esp10, esp15, esp17 ...).
static inline void FSet(f32& d, f32 v) { d = v; }
static inline void BitOn16(u16& f, u16 b) { f |= b; }
// `f &= ~b` with b a parameter keeps the 32-bit mask: `rlwinm` instead of the folded `andi.` (pl_sub).
static inline void BitOff16(u16& f, u16 b) { f &= ~b; }
// Plain store through the same kind of reference (debug tools restoring saved flag words).
static inline void BitSet(u32& f, u32 v) { f = v; }

// Struct-member view of pG (the pLog trick, db_log.h): a load through it is not hoisted above a
// preceding struct-member store (esp15 SetFreeWork: `w->floorY = ...; if (pGS->flags ...)`), where
// FSet would fold the address into `this` and a plain `pG` load moves above the store.
struct GlobalWorkPtr {
    GlobalWork* p;
};
#define pGS (((GlobalWorkPtr*) &pG)->p)

// Same effect for the room camera data pointer store in CameraControl::RoomDataRead.
#define G_ROOM_CAM_DATA (*(void**) ((u8*) pG + 0x4F28))

#endif
