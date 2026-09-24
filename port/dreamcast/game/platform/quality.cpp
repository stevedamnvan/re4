// D367 quality modes (QUALITY=1): state, presets, /cd/dc/quality.txt, VMU file RE4DCCFG, freeze.
// Design: design-lowmode DESIGN.md A1/A3/A4. Render-side only; see quality.h.
//
// /cd/dc/quality.txt (test fixture, wins over the VMU; skips the picker unless picker=1):
//   mode=standard|original   features=+lod,-lod   picker=0|1
// Stored choice: the 32-byte RE4DCCFG record (quality.h Re4dcQualityCfg, design-vmu layout),
// read once at the title and stored only when the picker's choice changes, through
// re4dc_quality_cfg_load/store. The VMU layer (design-vmu S5) owns the card file; the weak
// versions here keep the record in memory for this boot and never touch a card.
#include <stdlib.h>
#include <stddef.h>
#include <string.h>

#include "re4dc_platform.h"
#include "quality.h"

#ifndef RE4DC_QUALITY_DEFAULT
#define RE4DC_QUALITY_DEFAULT 1
#endif
#ifndef RE4DC_QUALITY_PICKER
#define RE4DC_QUALITY_PICKER 1
#endif
#ifndef RE4DC_MESH_LOD_PX
#define RE4DC_MESH_LOD_PX 3
#endif

extern "C" int re4dc_fixture_read(const char* path, char* buffer, unsigned size);   // os.cpp
extern "C" void re4dc_kos_heap_state(unsigned* free_chunks, unsigned* used, unsigned* break_room);

namespace {
constexpr uint32_t kPreset[2] = {0u, RQ_LOD_COARSE};

Re4dcQuality q = {RE4DC_QUALITY_DEFAULT, 0, RE4DC_QSRC_DEFAULT, 0, kPreset[RE4DC_QUALITY_DEFAULT],
                  RE4DC_QUALITY_DEFAULT ? 5.0f : float(RE4DC_MESH_LOD_PX)};
bool inited;
int file_picker = -1;              // quality.txt picker= (-1: not given)
uint32_t file_set, file_clear;     // quality.txt feature overrides
uint8_t stored_mode = 0xFF;        // mode in the stored record (0xFF: none)
uint32_t stored_features;

void apply(int mode)
{
    q.mode = uint8_t(mode ? RE4DC_QUALITY_STANDARD : RE4DC_QUALITY_ORIGINAL);
    q.features = (kPreset[q.mode] | file_set) & ~file_clear;
    q.lod_px = (q.features & RQ_LOD_COARSE) ? 5.0f : float(RE4DC_MESH_LOD_PX);
}

uint32_t crc32(const uint8_t* p, unsigned n)
{
    uint32_t c = 0xFFFFFFFFu;
    while (n--) {
        c ^= *p++;
        for (int k = 0; k < 8; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

uint32_t feature_bit(const char* name, unsigned len)
{
    if (len == 3 && !memcmp(name, "lod", 3)) return RQ_LOD_COARSE;
    return 0;
}

// "key=value" tokens separated by whitespace or commas inside features=.
void parse_file(char* t)
{
    int mode = -1;
    for (char* s = strtok(t, " \t\r\n"); s; s = strtok(nullptr, " \t\r\n")) {
        if (!strncmp(s, "mode=", 5)) {
            if (!strcmp(s + 5, "standard")) mode = RE4DC_QUALITY_STANDARD;
            else if (!strcmp(s + 5, "original")) mode = RE4DC_QUALITY_ORIGINAL;
            else re4dc_log("quality: quality.txt unknown mode '%s'\n", s + 5);
        } else if (!strncmp(s, "picker=", 7)) {
            file_picker = atoi(s + 7) ? 1 : 0;
        } else if (!strncmp(s, "features=", 9)) {
            for (const char* f = s + 9; *f;) {
                const char sign = *f;
                if (sign == '+' || sign == '-') ++f;
                const char* e = f;
                while (*e && *e != ',') ++e;
                const uint32_t bit = feature_bit(f, unsigned(e - f));
                if (!bit) re4dc_log("quality: quality.txt unknown feature '%.*s'\n", int(e - f), f);
                else if (sign == '-') { file_clear |= bit; file_set &= ~bit; }
                else { file_set |= bit; file_clear &= ~bit; }
                f = *e ? e + 1 : e;
            }
        }
    }
    if (mode >= 0) { apply(mode); q.source = RE4DC_QSRC_FILE; }
    else apply(q.mode);
}

uint32_t cfg_crc(const Re4dcQualityCfg* r)
{
    return crc32(reinterpret_cast<const uint8_t*>(r), offsetof(Re4dcQualityCfg, crc));
}

void cfg_read()
{
    Re4dcQualityCfg r;
    if (!re4dc_quality_cfg_load(&r)) { re4dc_log("quality: no stored RE4DCCFG record\n"); return; }
    if (memcmp(r.magic, "R4CF", 4) || r.version != 1 || r.mode > 1 || r.crc != cfg_crc(&r)) {
        re4dc_log("quality: RE4DCCFG record invalid; defaults\n");
        return;
    }
    stored_mode = r.mode;
    stored_features = r.features;
    apply(r.mode);
    q.source = RE4DC_QSRC_VMU;
    re4dc_log("quality: RE4DCCFG mode=%s\n", r.mode == RE4DC_QUALITY_STANDARD ? "standard" : "original");
}

void cfg_write()
{
    Re4dcQualityCfg r;
    memset(&r, 0, sizeof(r));
    memcpy(r.magic, "R4CF", 4);
    r.version = 1;
    r.mode = q.mode;
    r.features = q.features;
    r.crc = cfg_crc(&r);
    if (!re4dc_quality_cfg_store(&r)) { re4dc_log("quality: RE4DCCFG not stored (no card, full or removed)\n"); return; }
    stored_mode = q.mode;
    stored_features = q.features;
    re4dc_log("quality: RE4DCCFG stored mode=%s\n", q.mode == RE4DC_QUALITY_STANDARD ? "standard" : "original");
}

void log_state(const char* what)
{
    static const char* const kSrc[] = {"default", "vmu", "file", "picker"};
    re4dc_log("quality: %s mode=%s source=%s features=%08lx lod_px=%u\n", what, q.mode == RE4DC_QUALITY_STANDARD ? "standard" : "original",
              kSrc[q.source & 3], (unsigned long) q.features, unsigned(q.lod_px));
}
}  // namespace

// In-memory persistence until the VMU layer links strong versions (design-vmu S5).
static_assert(sizeof(Re4dcQualityCfg) == 32, "RE4DCCFG record");
static Re4dcQualityCfg g_cfg_mem;
static int g_cfg_mem_valid;
extern "C" __attribute__((weak)) int re4dc_quality_cfg_load(Re4dcQualityCfg* out)
{
    if (!g_cfg_mem_valid) return 0;
    *out = g_cfg_mem;
    return 1;
}
extern "C" __attribute__((weak)) int re4dc_quality_cfg_store(const Re4dcQualityCfg* rec)
{
    g_cfg_mem = *rec;
    g_cfg_mem_valid = 1;
    return 1;
}

extern "C" const Re4dcQuality* re4dc_quality(void) { return &q; }

extern "C" void re4dc_quality_init(void)
{
    if (inited) return;
    inited = true;
    unsigned kos_free0, kos_break0, kos_free1, kos_break1, used;
    re4dc_kos_heap_state(&kos_free0, &used, &kos_break0);
    cfg_read();
    static char text[256];
    const int n = re4dc_fixture_read("/cd/dc/quality.txt", text, sizeof(text) - 1);
    if (n > 0) { text[n] = 0; parse_file(text); }
    re4dc_kos_heap_state(&kos_free1, &used, &kos_break1);
    if (!RE4DC_QUALITY_PICKER || file_picker == 0 || (n > 0 && file_picker != 1)) q.chosen = 1;
    re4dc_log("quality: init kos_free %u->%u break %u->%u file=%d picker=%s\n", kos_free0, kos_free1, kos_break0,
              kos_break1, n, q.chosen ? "skip" : "show");
    log_state("init");
}

extern "C" int re4dc_quality_picker_wanted(void)
{
    re4dc_quality_init();
    return !q.chosen && !q.frozen;
}

extern "C" void re4dc_quality_set_mode(int mode, int source)
{
    if (q.frozen) { re4dc_log("quality: set_mode(%d) after freeze ignored\n", mode); return; }
    apply(mode);
    q.source = uint8_t(source);
}

extern "C" void re4dc_quality_toggle(uint32_t feature)
{
    if (q.frozen) return;
    q.features ^= feature & RQ_WIRED;
    q.lod_px = (q.features & RQ_LOD_COARSE) ? 5.0f : float(RE4DC_MESH_LOD_PX);
}

extern "C" void re4dc_quality_picker_done(void)
{
    q.chosen = 1;
    log_state("picked");
    if (stored_mode != q.mode || stored_features != q.features) cfg_write();
}

extern "C" void re4dc_quality_freeze(const char* where)
{
    if (q.frozen) return;
    re4dc_quality_init();
    q.frozen = 1;
    q.chosen = 1;
    log_state(where);
}

extern "C" int re4dc_quality_hud(unsigned v[2])
{
    v[0] = q.mode;
    v[1] = q.features;
    return 2;
}
