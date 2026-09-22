#ifndef EM_H
#define EM_H

#include "types.h"
#include "cManager.h"
#include "model.h"
#include "atariInfo.h"
#include "main_mem.h"

// The player classes derive from cEm, so the player-only fields the pl_* units touch live in
// cEm too (they all sit below 0xDE0).
// Hit box ("yarare") / damage part info (cEm+0x33C for the player; GetWepTargetList returns
// pointers to these per target), 0x34 bytes; extra boxes are chained through `next` (at_mod.cpp
// YarareAdd / YarareAddCube).
struct YARARE_INFO {
    Vec ofs;              // 0x00  box centre offset from the model / parts (yarareInit0 x, y, z)
    Vec pos;              // 0x0C  hit position in the parts (obj1b: the spear sticks here)
    f32 width;            // 0x18
    f32 height;           // 0x1C
    f32 depth;            // 0x20  cube depth (YarareInitCube / YarareAddCube set it with flags bit3)
    u16 flags;            // 0x24  bit3 (0x8): cube, bit5 (0x20): the hit sets cDmgInfo bit5 too (pl_wep PlWepHitCheck2)
    s16 partsNo;          // 0x26  parts the effect is placed at (0 = the model itself), 1-based
    f32 rad;              // 0x28  squared distance hit point -> line start (em_sub emLineAtCk / emBoxAtCk)
    f32 dist;             // 0x2C  squared distance of the hit from the aim line (em_sub GetWepTargetList sorts on it)
    YARARE_INFO* next;      // 0x30  next hit box of the model (YarareAdd)
};

// Damage info at cEm+0x324 (game/em.cpp), 0x18 bytes. set(0, 10, kind, pos, rad, part) registers a hit.
class cDmgInfo {
public:
    u8 m_Flag;
    u8 m_Timer;
    u8 m_Wep;      // 0x02  set() kind
    u8 m_Padding03;
    Vec m_PosFrom;              // 0x04  hit position
    f32 m_Dist;              // 0x10
    YARARE_INFO* m_pDamageYarare;      // 0x14  hit part

    cDmgInfo();
    void set(int flag, int timer, u8 kind, Vec* pos, f32 rad, YARARE_INFO* part);
    void set(int flag, int timer);   // stores the two bytes at 0/1 (pl_sub: set(0, 10), set(0, 0x80))
    void clear();
    void move();              // counts x1 down; clears stat when it reaches 0
};

// Room water effect table registered at cEm::pRoomEff (pl_sub PlRegistRoomEff): 3 entries of
// {u32 id; u8 pad[3]; u8 type;} used as EstSet(..., id, type, ...) for the ripple / splash effects.
struct PlRoomEff {
    u32 id;
    u8 pad_4[3];
    u8 type;
};

// Blend motion work (0xD0 bytes): a MotionWork (model.h) without the trailing blend/flip/blendTbl
// pointers. cEm::neckMot (0x42C) and cMot3::work are one; MotionWork::blend points at it.
struct MotionWorkSub {
    void* data;           // 0x00  MotionData*, NULL = no motion
    u8 pad_4[0x44 - 0x4];
    u32 flags2;           // 0x44  MotionWork::flags2 (bit28: no IK, bit31)
    u8 pad_48[0xC0 - 0x48];
    f32 speedRate;        // 0xC0  MotionWork::speedRate (em38 shell motion: 1.0 before every MotionSetCore)
    u8 pad_C4[4];
    f32 blendRate;        // 0xC8  weight of this work in the owner's MotionMove blend
    u8 pad_CC[4];
};

struct PlArc;      // global.h
struct EmiEntry;   // embarrel.h
class cSubChar;    // pl_npc.h
class cLight;      // light.h

enum EM_STATUS {
    EM_STATUS_ATTACKING = 0,
    EM_STATUS_LOCKOFF = 1,
    EM_STATUS_MIST_ON = 2,
    EM_STATUS_IK_OFF = 3,
    EM_STATUS_ALERT = 4,
    EM_STATUS_ACTIVE = 5,
    EM_STATUS_DOGCK = 6,
    EM_STATUS_DOGATK = 7,
    EM_STATUS_ITEMSET = 8,
    EM_STATUS_LOOK_ME = 9,
    EM_STATUS_DONT_FIRE = 10,
    EM_STATUS_ASHLEY_NO_HELP = 11
};

// Character work (game/em.cpp), sizeof 0xDE0: the cModel (0x320, which carries the motion work,
// the cAtariInfo, pFootShadowTbl and the light area) plus the fields below.
class cEm : public cModel {
public:
    s16 hp;               // 0x320
    s16 hp_max;            // 0x322
    cDmgInfo dmg;     // 0x324  (obj08: dmg.set on a hit target)
    YARARE_INFO hitInfo;    // 0x33C .. 0x370  (obj08: the player's hit part for the damage effect)
    f32 plDist2;          // 0x370  squared distance to the player (db_work prints its sqrt)
    f32 l_sub;             // 0x374  (em_set: 1e16 at creation)  squared distance to the partner (em30/em34/em38: closer than plDist2 -> target it) (PS2 l_sub)
    PlArc* subArc;          // 0x378  cSubChar: motion archive the routines index (pl_npc.cpp)
    PlArc* subArc2;         // 0x37C  cSubChar: the archive restored after a damage routine
    Vec lockOfs;          // 0x380  lock-on point offset in the lockParts' matrix (pl_wep)
    u8 lockParts;         // 0x38C  parts the lock-on point follows (pl_wep; AutoTrack uses the low 3 bits)
    u8 set;              // 0x38D  (db_cam "set=")
    u8 pad_38E[2];
    void (*pScenario)(cEm*);  // 0x390  em_sub EmScenario: called with the enemy when set
    u8 pad_394[4];
    u8 emset_no;           // 0x398
    u8 pad_399[3];
    union {
        struct {
            u8 x39C;
            u8 x39D;      // 0x39D  (obj16: the type 1 head is drawn at half scale while set)
            u8 pad_39E[0x3A8 - 0x39E];
        };
        Vec catchOfs;     // 0x39C  em_sub EmCatchPLSet: offset the caught model keeps to the catcher
    };
    Vec x3A8;             // 0x3A8  (objTrolley objTrolleySetAdjust adds the car movement to it)
    f32 catchTurn;        // 0x3B4  em_sub EmCatchPLSet: rot.y left to turn (EmCatchMotionMove eats it)
    int dmgType;          // 0x3B8  (pl_sub SetPlDamage/SetSubDamage first argument)
    u8 RckStat;           // 0x3BC  route_ck: bit0 = RckNear valid this frame (RouteCk clears it)
    s8 RckMy;             // 0x3BD  route_ck: way point the enemy heads to (-1 = none)
    s8 RckTo;             // 0x3BE  route_ck: way point nearest to the target
    s8 RckNear;           // 0x3BF  route_ck: way point nearest to the enemy
    u8 pad_3C0[4];
    u32 status;           // 0x3C4  setStatus / clearStatus / checkStatus bits (bit0 = in battle, bit1, bit11)
    u32 flag;        // 0x3C8  (db_cam "Flag=")  (PS2 cEm::flag; EM_LIST.flag)
    f32 Guard_r;             // 0x3CC  (em_set: list entry s16 x1A * 1000)  guard radius (em10: L_guard vs Guard_r) (PS2 Guard_r)
    u8 Character;              // 0x3D0  (em_set: list entry byte 0xB)  (PS2 Character)
    u8 itemFlag;          // 0x3D1  setItem 5th argument (setNoItem: 0)
    u8 pad_3D2[4];
    u16 Item_id;           // 0x3D6  setItem a (setNoItem: 0xFFFF)
    u16 Item_num;          // 0x3D8  setItem b
    u16 Item_flg;          // 0x3DA  setItem c
    u16 Auto_item_flg;          // 0x3DC  setItem d
    u8 pad_3DE[2];
    union {
        u32 x3E0;            // 0x3E0  anchor of the per-enemy work overlays (EMxx_WK(em) = &em->x3E0)
        u32 m_Work0;         // 0x3E0  player: event walk flag / damage timer (PS2 cPlayer::m_Work0)
        cSubChar* subSelf;         // 0x3E0  cSubChar: the model the routines animate (itself)
    };
    // 0x3E4 .. 0x400: player fields, and the partner's neck control (cSubChar::neckCtrl) on the same bytes
    union {
        struct {
            int m_Work1;             // 0x3E4  player damage: 1 = turning towards x400  (PS2 cPlayer::m_Work1)
            u32 m_Work2;             // 0x3E8  player damage (blow): water splash done  (PS2 cPlayer::m_Work2)
            int m_Work3;             // 0x3EC  player damage (emrock plemRockEscape): EMI route point run to (-1 = none)  (PS2 cPlayer::m_Work3)
            int m_Work4;             // 0x3F0  emrock escape: frames since the last button press  (PS2 cPlayer::m_Work4)
            int m_Work5;             // 0x3F4  emrock escape: EMI goal sub type (plemRockEscapeCk)  (PS2 cPlayer::m_Work5)
            int m_Work6;             // 0x3F8  emrock escape: goal reached  (PS2 cPlayer::m_Work6)
            int m_Work7;             // 0x3FC  emrock escape: Rnd() & 1 (action button variant)  (PS2 cPlayer::m_Work7)
        };
        struct {
            int subNeckOn;        // 0x3E4  cSubChar: neckSet() called this frame
            f32 subNeckX;         // 0x3E8
            f32 subNeckAng;       // 0x3EC  cSubChar: current neck angle (parts 3)
            f32 subNeckZ;         // 0x3F0
            Vec subNeckPos;       // 0x3F4  cSubChar: position looked at
        };
    };
    union {
        f32 m_Fwork0;         // 0x400  player: event turn limit / damage direction angle (123.0 = none)  (PS2 cPlayer::m_Fwork0)
        struct {
            u16 subFlags;   // 0x400  sub character (cSubChar): bit7 (0x80) manual control, bit6 (0x40) ok to control, bit4 (0x10), bit3 (0x8) move-to, bit0
            u16 subFlags2;  // 0x402  cSubChar (pl_sub SubCharMoveTo clears 0x60)
        };
    };
    // 0x404 .. 0x520: player fields, and the same bytes as the partner (cSubChar, pl_npc.cpp) uses them
    union {
        struct {
            Vec evTarget;         // 0x404  player event: walk-to position
            Vec evTarget2;        // 0x410  player: position setPos'd while flags_420 bit7 is set (objRobo R0WaitGondola)
            u32 m_Flag;        // 0x41C  player: bit8 (0x100) event motion done -> reset routine  (PS2 cPlayer::m_Flag)
            u32 flags_420;        // 0x420  player: bit6 (0x40) knife routine ends into routine 0x11
            void** pMotTbl;       // 0x424  player: motion data table ([0] walk, [2] turn, [0x5F..0x6C] set by setMotion)
            void** pRegistMot;    // 0x428  player: registered motion table (pl_sub PlRegistMotion fills [0..11])
            MotionWorkSub neckMot;   // 0x42C .. 0x4FC  player: neck turn motion (pl_class cPlNeck::motSet), blended via blendMot
            u8 x4FC;              // 0x4FC  (pl_sub PlChangeData/PlMotionReset clear it)
            u8 x4FD;              // 0x4FD
            u8 m_BbtnCnt;              // 0x4FE  (PS2 cPlayer::m_BbtnCnt)
            u8 m_CmdTimer;       // 0x4FF  player: frames until the X button (partner command) is accepted again  (PS2 cPlayer::m_CmdTimer)
            f32 blendRate500;     // 0x500  player: em2b plBlendMotSet: neckMot blend rate source (the strangle button mash 0..255)
            u32 m_SeId;         // 0x504  player: SndCall handle cPlayer::interrupt stops  (PS2 cPlayer::m_SeId)
            cModel* pLockEm;      // 0x508  player: locked-on enemy (pl_wep lock, knife aim)
            cEm* m_pBoat;           // 0x50C  player: the jet ski the player rides (pl0e cPl0e::setRide / PlBoatMove)
            class cObjSpear* pSpear;  // 0x510  player: the harpoon in hand (pl0f plboatSetSpear / plboatSpearThrow)
            f32 sightRate;        // 0x514  player: pl0f harpoon aim: vertical sight rate (-0.3927 .. 0.3927)
            int gachaCnt;         // 0x518  player: button mash counter (pl_sub PlGacha*)
            u8 m_SplashCtr;       // 0x51C  (PS2 cPlayer::m_SplashCtr; unused on GC)
            u8 m_OCMode;          // 0x51D  (PS2 cPlayer::m_OCMode; unused on GC)
            u8 eyeMode;           // 0x51E  player (pl_sub PlSetEyeMode)
            u8 binoMode;          // 0x51F  player: binocular step (cPlayer::moveBinocular 1 -> 2 -> 3 -> 0)
            u8 m_ConDmFlag;        // 0x520  player: 1 once setDamage ran  (PS2 cPlayer::m_ConDmFlag)
            u8 pad_521;
            u16 m_ConDmTimer;        // 0x522  player: accumulated setDamage counts; a damage reaction starts past 0xFE  (PS2 cPlayer::m_ConDmTimer)
        };
        struct {
            u8 m_BackRno;            // 0x404  cSubChar  (PS2 cSubChar::m_BackRno)
            u8 m_BackRno2;            // 0x405
            u16 m_BackTime;           // 0x406  frame counter
            u8 m_Frame;            // 0x408
            u8 m_Hokan;            // 0x409
            u8 m_Timer;            // 0x40A  timer
            u8 pad_40B;
            f32 m_Blend;     // 0x40C  cSubChar: blend rate of subBackMot (pl0e subBlendMotSet, like the player's blendRate500)
            f32 dir;           // 0x410  angle to the player (analyze)
            f32 dist;          // 0x414  distance to the player (analyze)
            Vec distPos;        // 0x418  position to walk to
            f32 fyBak;           // 0x424  (PS2 cSubChar::fyBak)
            Vec subOfs;           // 0x428  offset behind the player (atckPos)
            u32 plStat;      // 0x434  PlGetStatus() of the frame
            u32 satAttr;           // 0x438  scenario attribute of the wall in front (anaSatInfo)
            Vec satCross;           // 0x43C  hit point of the action wall check (actionCheck)
            Vec satNorm;           // 0x448  its normal
            MotionWorkSub subBackMot;   // 0x454 .. 0x524  look-back motion blended in (backCheckSet -> blendMot)
        };
    };
    cModelInfo* subHand[2];   // 0x524  cSubChar: hand model infos (pl11 cSubAshley::setHand)
    f32 fWork0;           // 0x52C  cSubChar: fence / window action direction  (PS2 cSubChar::fWork0)
    int subHideMode;      // 0x530  cSubChar (pl_sub SubCharCtrlHide); pl_npc: general step counter
    int subX534;          // 0x534  cSubChar (SubCharCtrlHide mode 0 sets 1)
    int sub538;           // 0x538  cSubChar: step counter
    int sub53C;           // 0x53C  cSubChar: the catch action button is set (moveFallWait)
    int sub540;           // 0x540  cSubChar: frames waiting for the player
    Vec subHidePos;       // 0x544  cSubChar hide position
    u8 m_FallWaitTimer;            // 0x550  cSubChar: frames until the route is re-checked  (PS2 cSubChar::m_FallWaitTimer)
    u8 pad_551[3];
    struct EmiEntry* pAnotherRoute;   // 0x554  cSubChar: EMI route entry (type 0xB) walked to (embarrel.h)  (PS2 cSubChar::pAnotherRoute, EMINFO_WK*)
    Vec m_PlActPos;           // 0x558  cSubChar: ledge position to wait at (catchOn / actionCheck)  (PS2 cSubChar::m_PlActPos)
    f32 m_PlActAngY;           // 0x564  cSubChar: angle to turn to while waiting to be caught  (PS2 cSubChar::m_PlActAngY)
    int subAux0;          // 0x568  cSubChar (SetSubAux/SetSubBulldozer arguments)
    int subAux1;          // 0x56C
    f32 subMoveTo[4];     // 0x570  cSubChar (SubCharMoveTo x, y, z, w)
    u8 m_PlActTime;            // 0x580  cSubChar: timer  (PS2 cSubChar::m_PlActTime)
    u8 m_PlActType;            // 0x581  (PS2 cSubChar::m_PlActType)
    u8 pad_582[2];
    void* subMot0;        // 0x584  cSubChar registered motions (SubCharRegistMotion, SetSubDamage)
    void* subMot1;        // 0x588
    // 0x58C .. 0x5C4 is the partner's cMotBase (pl_npc.cpp / obj13: `(cMotBase*) &subFlags58C`)
    u8 subFlags58C;       // 0x58C  cSubChar (SetSubDamage sets 0x40)
    u8 pad_58D[0x5C4 - 0x58D];
    u32 subSndId;         // 0x5C4  cSubChar: SndCall handle of the bulldozer SEs (objBull Sub_bull_*)
    f32 subX5C8;          // 0x5C8  cSubChar (obj13 SubLadderClimbCk: the partner climbs only while >= 1000)
    YARARE_INFO subHit[3];  // 0x5CC .. 0x668  cSubChar: extra hit boxes (YarareAdd in cSubChar::init)
    u8 pad_668[0x738 - 0x668];
    int m_pSatMask;     // 0x738  player: SatMgr.check flag (player.cpp startUp / move)
    void (*pFuncAux)(class cPlayer*);  // 0x73C  player: routine 1/0xA (pl_R1_Aux) handler
    struct PlRoomEff* m_pEffRoom;  // 0x740  player: room water effect table (pl_sub PlRegistRoomEff/PlWaterProc)
    void* m_pBoss;          // 0x744  player (pl_sub PlRegistBoss)
    void* m_pBossRmf;          // 0x748
    Vec m_FallVec;          // 0x74C  player: -wallNrm of the ledge to drop from (pl_class fallCheck)
    Vec m_JumpVec;          // 0x758  player: -normal of the jump-over wall (pl_class jumpCheck)
    f32 m_JumpAdjY;       // 0x764  player: floor height behind the jump wall minus pos.y
    Vec m_ActCross;       // 0x768  player: hit point of the action wall check (pl_class actWallCheck)
    Vec m_ActNorm;       // 0x774  player: its normal
    u32 m_ActAttr;      // 0x780  player: its scenario attribute (0 = no wall in front)
    u8 pad_784[4];
    class cPlWep* Wep;   // 0x788  player: weapon control (pl_wep.cpp, 0x44 bytes)
    class cPlNeck* Neck; // 0x78C  player: neck control (pl_class.cpp, 0x1C bytes)
    class cPlWaist* Waist;  // 0x790  player: waist control (pl_class.cpp, 0xC bytes)
    class cPlBody* Body; // 0x794  player: body / face / hand model set (pl_body.cpp, 0xF0 bytes)
    u8 pad_798[8];
    class cPlPush* Push; // 0x7A0  player: push-object control (pl_push.cpp, 0x10 bytes)
    class cMotBase* MotBase;  // 0x7A4  (0x38 bytes)
    u8 pad_7A8[4];
    union {
        Vec bustBase[3];      // 0x7AC  Ashley: rest positions of parts 0x1D, 0x1E, 0x1A (pl_ashley moveBust)
        struct {              // Krauser (pl0a pl_klauser.cpp): the three fading model infos and their state
            cModelInfo* krModel[3];   // 0x7AC  [0]/[1] arm models faded against each other, [2] the tex-render one
            int krX7B8;               // 0x7B8  (ctor: 0)
            int krX7BC;               // 0x7BC
            int krX7C0;               // 0x7C0  (ctor: 0)
            u8 krPad_7C4[0x7D0 - 0x7C4];
        };
    };
    u8 pad_7D0[4];
    cLight* subLight;         // 0x7D4  cSubChar: back light (cLightMgr::createBack)
    void* subShape;       // 0x7D8  cSubChar: ShapeMove work (NULL = none)
    void (*subFunc)();        // 0x7DC  cSubChar: routine 4 (damage) handler (cSubChar::move)
    Vec subBustBase[3];   // 0x7E0  cSubChar: rest positions of parts 0x1D, 0x1E, 0x1A (moveBust)
    u8 pad_804[0x880 - 0x804];
    f32 x880;             // 0x880  player (Krauser): ctor 1.0
    u8 pad_884[0x890 - 0x884];
    int x890;             // 0x890  player (Krauser): cleared by cPlayer::interrupt with pG->flags_5018 bit23
    int x894;             // 0x894  player (Krauser): -1 -> 1 there
    int x898;             // 0x898  player (Krauser): tex-render model alpha pulse counter (0..0x1F, transMove)
    u8 pad_89C[0x9BC - 0x89C];
    f32 x9BC;             // 0x9BC  (objTrolley objTrolleyFallEM: rot.y when thrown off the car)
    u8 pad_9C0[0xD60 - 0x9C0];
    Mtx rackMat;          // 0xD60  cEmRack push range matrix (setRange: rot * trans of the rack)
    Mtx rackInvMat;       // 0xD90  its inverse (adjustRange transforms the position into range space)
    f32 rackRange[4];     // 0xDC0  cEmRack push limits (adjustRange dir 0: [1], 1: -[2], 2: [0], 3: -[3])
    u8 rackFlags;         // 0xDD0  cEmRack: bit4 (0x10) range set; SetRack initialises it to 0xF
    u8 pad_DD1[0xDE0 - 0xDD1];

    cEm();
    virtual ~cEm() {}
    virtual void move();
    virtual void setItem(u16 item_id, u16 num, u16 item_flg, u16 auto_item_flg, u8 item_eff);  // 0x3D6.. item drop (0x3D1 flag)
    virtual void setNoItem();
    virtual int checkThrow();
    void setStatus(int bit);     // status |= 1 << bit
    void clearStatus(int bit);
    int checkStatus(int stat);
    int initWork();              // be_flag = 0x21, x12E = 0 (the constructor)
};

// Enemy manager (game/em.cpp). The construct id selects the class: 0 player, 1..0xE / others a
// read-table enemy (EmInitFunc), 0x40.. the object enemies (cEmObj, cEmDoor, ...), 0xFF a plain cEm.
class cEmMgr : public cManager<cEm> {
public:
    u32 Guid;              // 0x34  next cModel::serial (construct)

    static const char* idName[96];   // debug names per construct id

    cEmMgr();
    // no user destructor: the synthesized one (and cManager<cEm>'s) land after the other inlines
    virtual void* memAlloc(u32 size) { return MemAlloc(size, 1); }
    virtual void memFree(void* p) { MemFree(p); }
    virtual void memClear(cEm* p, u32 size) { memclr_asm(p, size); }
    virtual void log(const char* fmt, ...);
    virtual void destroy(cEm* p);   // em.cpp overrides the cManager one (pl_sub SubCharCtrl / PlDataRelease)
    virtual int construct(cEm* p, u32 id);

    int arrayAlloc(u32 n);        // cManager<cEm>::arrayAlloc + pPL = pSUB = 0; returns 1
    void move();                  // dieCheck, RouteCk, emMove for every alive work (or only pSUB when stopped)
    // first alive enemy with model id `id`, searching from `start->next` (or the list head)
    cEm* getEmPtr(int id, cEm* start);
    int isBattle();               // 1 when any alive enemy has status bit0
    void destroyAll();            // killEm on every alive work (id != 0)
};

extern cEmMgr EmMgr;

#if !defined(__PPC__)
extern "C" void re4dc_missing(const char*);
#endif

// Work `no` of the enemy manager, NULL when out of range. A free function: a cEmMgr member (even an
// out-of-class inline) is emitted out of line into em.cpp, which owns the vtable (ctrl.h CtrlMgrWork).
static inline cEm* EmMgrWork(u32 no)
{
    if (no >= EmMgr.nArray) {
        return 0;
    }
#if !defined(__PPC__)
    // Indexed callers may retain dead/unconstructed slots. Never evict them.
    if (!EmMgr.prepareWork(no, 1)) {
        re4dc_missing("enemy indexed backing allocation");
        return 0;
    }
    return EmMgr.workAt(no);
#else
    return (cEm*)((u8*)EmMgr.pArray + EmMgr.size * no);
#endif
}

// Pushable rack/crate enemy (game/emrack.cpp); only what pl_push calls.
class cEmRack : public cEm {
public:
    virtual void move();   // key function: keeps the vtable in emrack.o (cEmMgr::construct stores it)

    void setBreak();
    void setDown(Vec* pos);
    void setShock();
    void setEff(u8 eff);
    void setRange(f32 x_low, f32 x_up, f32 y_low, f32 y_up);
    int adjustRange(u8 dir);
};

extern "C" {
void emMove(cEm* em);        // per-frame update of one alive work: distance to the player, damage info, move()
void battleCheck(cEm* em);
void killEm(cEm* em);
}

#endif
