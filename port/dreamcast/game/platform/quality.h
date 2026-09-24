// D367 quality modes (QUALITY=1; design: design-lowmode DESIGN.md section A).
//
// One render-side state, written only before gameplay (title picker, VMU file RE4DCCFG,
// /cd/dc/quality.txt) and frozen when the game starts (titleExit, or the first room entry
// for paths that skip the title). Readers are render-side code only; nothing on the logic
// side may branch on it, so the logic trace stays STRICT across modes.
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Mode names are the user's: STANDARD is the budget-first mode and the default; ORIGINAL is the
// faithful GameCube look. The values are stored in the RE4DCCFG record.
enum {
    RE4DC_QUALITY_ORIGINAL = 0,
    RE4DC_QUALITY_STANDARD = 1,
};

// Where the mode came from.
enum {
    RE4DC_QSRC_DEFAULT = 0,   // build default (QUALITY_DEFAULT)
    RE4DC_QSRC_VMU = 1,       // RE4DCCFG on the first VMU
    RE4DC_QSRC_FILE = 2,      // /cd/dc/quality.txt
    RE4DC_QSRC_PICKER = 3,    // the title picker this boot
};

// Feature bits (render-only switches). Only RQ_LOD_COARSE is wired today; the other bits are
// reserved for the Standard-mode options as their owners land them (records, occlusion, FTRV matrices,
// light cap, Leon merge, low-poly Ganados, crowd ladder, effect draw cap).
enum {
    RQ_LOD_COARSE = 1u << 0,   // native static meshlet LOD threshold 5 px instead of MESH_LOD_PX
    RQ_RECORDS = 1u << 1,
    RQ_OCC_AGGR = 1u << 2,
    RQ_FTRV_MTX = 1u << 3,
    RQ_LIGHT_CAP = 1u << 4,
    RQ_LEON_MERGE = 1u << 5,
    RQ_GANADO_LOW = 1u << 6,
    RQ_CROWD = 1u << 7,
    RQ_FX_DRAWCAP = 1u << 8,
    RQ_WIRED = RQ_LOD_COARSE,
};

typedef struct Re4dcQuality {
    uint8_t mode;       // RE4DC_QUALITY_*
    uint8_t frozen;     // 1 once the game has started: later writes are ignored (logged)
    uint8_t source;     // RE4DC_QSRC_*
    uint8_t chosen;     // picker shown (or skipped) this boot
    uint32_t features;  // RQ_* (mode preset, then quality.txt / debug overrides)
    float lod_px;       // native static LOD threshold in projected pixels
} Re4dcQuality;

// RE4DCCFG record (design-vmu DESIGN.md: 2-block VMS file, header + icon, then this 32-byte
// record; written only when the picker's choice changes). crc = CRC-32 of the first 28 bytes.
typedef struct Re4dcQualityCfg {
    char magic[4];      // "R4CF"
    uint8_t version;    // 1
    uint8_t mode;       // RE4DC_QUALITY_*
    uint8_t pad[2];
    uint32_t features;  // feature override word (RQ_*)
    uint8_t reserved[16];
    uint32_t crc;
} Re4dcQualityCfg;
// Persistence, owned by the VMU layer (design-vmu S5, vmu_store). quality.cpp defines weak
// in-memory versions (this boot only, never touches a card) until the VMU shim links strong
// ones. load: 1 and *out filled when a record exists (the caller checks magic/version/crc);
// store: 1 when saved.
int re4dc_quality_cfg_load(Re4dcQualityCfg* out);
int re4dc_quality_cfg_store(const Re4dcQualityCfg* rec);

const Re4dcQuality* re4dc_quality(void);
// Reads /cd/dc/quality.txt and the stored record once (idempotent). Called at the title.
void re4dc_quality_init(void);
// Picker: 1 when it should open now (first main menu this boot, no file override).
int re4dc_quality_picker_wanted(void);
// Mode preset (+ file overrides). Ignored once frozen. `source` = RE4DC_QSRC_*.
void re4dc_quality_set_mode(int mode, int source);
// Debug submenu: toggle one feature bit on top of the preset. Ignored once frozen.
void re4dc_quality_toggle(uint32_t feature);
// Picker done: marks chosen, stores the record when the choice changed.
void re4dc_quality_picker_done(void);
// Game start (titleExit / first room entry): freezes the state and logs it.
void re4dc_quality_freeze(const char* where);
// PERF_HUD: v[0] = mode, v[1] = feature word. Returns 2.
int re4dc_quality_hud(unsigned v[2]);

#ifdef __cplusplus
}
#endif
