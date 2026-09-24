// REL modules: on the GameCube the stage, enemy, weapon and sub-screen code
// lives in relocatable modules the game reads from disc, links (OSLink) and
// enters through the header's prolog. Here every module in the Makefile's
// MODULES list is a partially linked object in the image (tools/gen_modules.py)
// and this table maps a REL header id to its entry points; OSLink (os.cpp)
// rewrites the header the game read so pModule->prolog() / epilog() reach
// the compiled code and the loader's control flow (readRelData, DLL_Link,
// prolog) stays as recovered.
//
// Link-time state follows the GameCube loader. A fresh link (the header was
// just read from disc) starts from the module's pristine .data and a zeroed
// .bss, exactly what a newly read REL has; the pristine .data is captured at
// the module's first link, before any of its code has run. A relink of the
// same header after OSUnlink (cRoomData::stopRelData / restartRelData around
// the sub screen) keeps the state: the source restores its bss backup there.
// tools/gen_modules.py bounds each module's .data/.bss span and rejects
// modules with static constructors, so the empty _ctors list the prologs walk
// is also what a per-link constructor pass would run.

#include "re4dc_platform.h"

typedef unsigned long u32;

extern "C" {
// The stage entry objects (src/st<N>/st<N>.cpp) walk the linker-script
// ctor / dtor label lists renamed to these; no module has constructors
// (checked when the module object is linked), so both lists are empty.
void (*re4dc_module_ctors[])(void) = {0};
void (*re4dc_module_dtors[])(void) = {0};
#define MODULE(name) void name##_prolog(void); void name##_epilog(void); \
    extern char re4dc_mod_##name##_data[], re4dc_mod_##name##_data_end[], re4dc_mod_##name##_bss[], \
        re4dc_mod_##name##_bss_end[], re4dc_mod_##name##_pristine[];
MODULE(st1_0)
MODULE(st1_1)
MODULE(st1_2)
MODULE(st1_3)
MODULE(wep02)
MODULE(em12)
MODULE(em23)
MODULE(em15)
MODULE(em26)
MODULE(em28)
MODULE(em21)
#if RE4DC_SUBSCREEN && !RE4DC_SUBSCREEN_OVL
MODULE(Sscrn)
#endif
#undef MODULE
}

struct Re4dcModule {
    u32 id;             // REL header id (config/G4BE08/modules/<mod>/rel.json module_id)
    const char* name;
    void (*prolog)(void);
    void (*epilog)(void);
    char* data;         // writable state span (gen_modules.py state.ld)
    char* data_end;
    char* bss;
    char* bss_end;
    char* pristine;     // .data as linked, captured before the first prolog
};

#define MODULE(id, name) {id, #name, name##_prolog, name##_epilog, re4dc_mod_##name##_data, \
    re4dc_mod_##name##_data_end, re4dc_mod_##name##_bss, re4dc_mod_##name##_bss_end, re4dc_mod_##name##_pristine}
#if RE4DC_SUBSCREEN_OVL
// SUBSCREEN_OVL=1: the Sscrn entry is filled by re4dc_module_overlay() each time sscrn_bridge.cpp
// has read and relocated sscrn.ovl; the image holds no pointer into the overlay.
static Re4dcModule g_modules[] = {
#else
static const Re4dcModule g_modules[] = {
#endif
    MODULE(74, st1_0),
    MODULE(73, st1_1),
    MODULE(78, st1_2),
    MODULE(86, st1_3),
    MODULE(4, wep02),
    MODULE(18, em12),
    MODULE(7, em23),
    MODULE(19, em15),
    MODULE(14, em26),
    MODULE(17, em28),
    MODULE(6, em21),
#if RE4DC_SUBSCREEN_OVL
    {71, "Sscrn", 0, 0, 0, 0, 0, 0, 0},  // sub screen overlay (entry points set per load)
#elif RE4DC_SUBSCREEN
    MODULE(71, Sscrn),  // sub screen (SUBSCREEN=1; linked into the ARAM-swapped area while open)
#endif
};
#undef MODULE

#if RE4DC_SUBSCREEN
// The sub screen's per-link constructors (tools/gen_modules.py PER_LINK_CTORS) register the
// destructors of its static objects here instead of KOS's __cxa_atexit list, where one entry
// per open would accumulate. Its _epilog (DLL_Unlink) walks re4dc_mod_Sscrn_dtors.
namespace {
struct ModuleExit { void (*fn)(void*); void* arg; };
ModuleExit sscrn_exits[16];
unsigned sscrn_nexit;
void sscrn_run_exits()
{
    while (sscrn_nexit) {
        const ModuleExit e = sscrn_exits[--sscrn_nexit];
        e.fn(e.arg);
    }
}
}
extern "C" int re4dc_mod_Sscrn_atexit(void (*fn)(void*), void* arg, void* dso)
{
    (void) dso;
    if (sscrn_nexit >= sizeof(sscrn_exits) / sizeof(sscrn_exits[0])) re4dc_missing("Sscrn atexit table full");
    sscrn_exits[sscrn_nexit++] = {fn, arg};
    return 0;
}
extern "C" { void (*re4dc_mod_Sscrn_dtors[])(void) = {sscrn_run_exits, 0}; }
#endif

namespace {
constexpr unsigned kModules = sizeof(g_modules) / sizeof(g_modules[0]);
// OSUnlink leaves this in the header's (OS-owned) link.next word; a header
// read fresh from disc has 0 there, so a restart is told from a new read
// even when the new REL lands at the address of the old one.
constexpr u32 kUnlinkedMark = 0x57365552;  // "W6UR"
struct ModuleState {
    const void* header;     // header of the current link (nullptr when unlinked)
    const void* stopped;    // header unlinked by OSUnlink, eligible for restart
    bool captured;
    unsigned fresh_links, restarts, unlinks;
};
ModuleState g_state[kModules];
}

static int moduleIndex(u32 id)
{
    for (unsigned i = 0; i < kModules; i++) {
        if (g_modules[i].id == id) return int(i);
    }
    return -1;
}

// RELs linked as one group object (gen_modules.py group_rules, EM10_SHARED=1) share one state
// span: the pristine .data is captured once for the span, at the first link of any member, and
// a member linked while another is still linked resets the state that member is using.
static bool sameSpan(const Re4dcModule& a, const Re4dcModule& b)
{
    return a.data == b.data && a.data_end == b.data_end && a.bss == b.bss && a.bss_end == b.bss_end &&
           a.pristine == b.pristine && (a.data_end != a.data || a.bss_end != a.bss);
}

// Fresh link: pristine .data, zero .bss (the GameCube OSLink of a newly read REL).
static void freshState(unsigned i)
{
    const Re4dcModule& m = g_modules[i];
    ModuleState& s = g_state[i];
    const unsigned data = unsigned(m.data_end - m.data);
    for (unsigned j = 0; j < kModules; j++) {
        if (j == i || !sameSpan(m, g_modules[j])) continue;
        if (g_state[j].captured) s.captured = true;
        if (g_state[j].header)
            re4dc_log("module state: %s shares its state span with linked %s (reset)\n", m.name, g_modules[j].name);
    }
    const bool capture = !s.captured;
    if (capture) {
        __builtin_memcpy(m.pristine, m.data, data);
        s.captured = true;
    } else {
        __builtin_memcpy(m.data, m.pristine, data);
    }
    __builtin_memset(m.bss, 0, unsigned(m.bss_end - m.bss));
    ++s.fresh_links;
    re4dc_log("module state: %s fresh link %u data=%u bss=%u %s\n", m.name, s.fresh_links, data,
              unsigned(m.bss_end - m.bss), capture ? "captured" : "restored");
}

// Binds the header the game read (include/main_sub.h OSModuleHeader: id at 0,
// prolog at 0x34, epilog at 0x38) to the compiled module; 1 = known module.
extern "C" int re4dc_module_bind(void* header)
{
    if (header == 0) {
        re4dc_log("module: null header; link failed\n");
        return 0;
    }
    u32* h = (u32*) header;
    const int index = moduleIndex(h[0]);
    // Relink of the header this module last unlinked: state is kept.
    const bool restart = h[1] == kUnlinkedMark && index >= 0 && g_state[index].stopped == header;
    if (h[1] == kUnlinkedMark) h[1] = 0;
    if (h[0x1c / 4] == 0xDC000001) {
        // Compact offline descriptor: no section, name, import or raw code fields.
        for (unsigned i = 1; i < 16; ++i) {
            if (i != 0x1c / 4 && i != 0x20 / 4 && i != 0x34 / 4 && i != 0x38 / 4 && h[i] != 0) {
                re4dc_log("module: malformed native descriptor; link failed\n");
                h[0x34 / 4] = h[0x38 / 4] = 0;
                return 0;
            }
        }
    }
    const Re4dcModule* m = index >= 0 ? &g_modules[index] : 0;
    void (**prolog)(void) = (void (**)(void)) &h[0x34 / 4];
    void (**epilog)(void) = (void (**)(void)) &h[0x38 / 4];
    if (m == 0) {
        re4dc_log("module: id %lu not in the image; link failed\n", h[0]);
        *prolog = 0;
        *epilog = 0;
        return 0;
    }
    if (h[0x1c / 4] == 0xDC000001 &&
        ((h[0x34 / 4] && *prolog != m->prolog) || (h[0x38 / 4] && *epilog != m->epilog))) {
        re4dc_log("module: invalid native entry points; link failed\n");
        *prolog = 0;
        *epilog = 0;
        return 0;
    }
#if RE4DC_SUBSCREEN_OVL
    if (m->prolog == 0) {
        re4dc_log("module: %s is an overlay that is not loaded; link failed\n", m->name);
        *prolog = 0;
        *epilog = 0;
        return 0;
    }
#endif
    ModuleState& s = g_state[index];
    if (s.header && s.header != header) {
        re4dc_log("module: %s linked again without unlink\n", m->name);
    }
    if (restart) {
        ++s.restarts;
        re4dc_log("module: id %lu -> %s (static, restart %u keeps state)\n", h[0], m->name, s.restarts);
    } else {
        re4dc_log("module: id %lu -> %s (static)\n", h[0], m->name);
#if RE4DC_SUBSCREEN
        if (m->id == 71 && sscrn_nexit) {  // the last link was not left through DLL_Unlink
            re4dc_log("module: Sscrn fresh link drops %u stale destructors\n", sscrn_nexit);
            sscrn_nexit = 0;
        }
#endif
        freshState(unsigned(index));
    }
    s.header = header;
    s.stopped = 0;
    *prolog = m->prolog;
    *epilog = m->epilog;
    return 1;
}

#if RE4DC_SUBSCREEN_OVL
// sscrn_bridge.cpp, after reading and relocating an overlay: its entry points and state span.
// The bytes came fresh from disc (pristine .data, zero .bss): the next link captures them.
extern "C" void re4dc_module_overlay(u32 id, void (*prolog)(void), void (*epilog)(void), char* data, char* data_end,
                                     char* bss, char* bss_end, char* pristine)
{
    const int index = moduleIndex(id);
    if (index < 0) re4dc_missing("overlay module id not in the table");
    Re4dcModule& m = g_modules[index];
    m.prolog = prolog;
    m.epilog = epilog;
    m.data = data;
    m.data_end = data_end;
    m.bss = bss;
    m.bss_end = bss_end;
    m.pristine = pristine;
    ModuleState& s = g_state[index];
    s.header = 0;
    s.stopped = 0;
    s.captured = false;
}
#endif

// OSUnlink: the module's code stays resident; mark the header so a relink of
// this very header (restartRelData) is a restart rather than a fresh read.
extern "C" int re4dc_module_unbind(void* header)
{
    if (header == 0) return 0;
    u32* h = (u32*) header;
    const int index = moduleIndex(h[0]);
    if (index < 0 || g_state[index].header != header) {
        re4dc_log("module: unlink of id %lu that is not linked\n", h[0]);
        return 1;
    }
    ModuleState& s = g_state[index];
    s.header = 0;
    s.stopped = header;
    ++s.unlinks;
    h[1] = kUnlinkedMark;
    return 1;
}

// Room-lifecycle audit: fresh links / restarts / unlinks summed over modules.
extern "C" void re4dc_module_counts(unsigned* fresh, unsigned* restarts, unsigned* unlinks, unsigned* linked)
{
    unsigned f = 0, r = 0, u = 0, l = 0;
    for (const auto& s : g_state) { f += s.fresh_links; r += s.restarts; u += s.unlinks; l += s.header != 0; }
    *fresh = f; *restarts = r; *unlinks = u; *linked = l;
}
