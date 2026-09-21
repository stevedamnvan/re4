// REL modules: on the GameCube the stage, enemy, weapon and sub-screen code
// lives in relocatable modules the game reads from disc, links (OSLink) and
// enters through the header's prolog. Here every module in the Makefile's
// MODULES list is a partially linked object in the image (tools/gen_modules.py)
// and this table maps a REL header id to its entry points; OSLink (os.cpp)
// rewrites the header the game read so pModule->prolog() / epilog() reach
// the compiled code and the loader's control flow (readRelData, DLL_Link,
// prolog) stays as recovered.
//
// Differences from a real link, by design: the modules' static constructors
// ran once at image start instead of at every prolog, and a module's .bss
// keeps its values between loads instead of being re-zeroed.
#include "re4dc_platform.h"

typedef unsigned long u32;

extern "C" {
// The stage entry objects (src/st<N>/st<N>.cpp) walk the linker-script
// ctor / dtor label lists renamed to these; the image ran its constructors
// before main, so both lists are empty.
void (*re4dc_module_ctors[])(void) = {0};
void (*re4dc_module_dtors[])(void) = {0};
#define MODULE(name) void name##_prolog(void); void name##_epilog(void);
MODULE(st1_0)
MODULE(st1_1)
MODULE(st1_2)
MODULE(st1_3)
MODULE(wep02)
MODULE(em12)
#undef MODULE
}

struct Re4dcModule {
    u32 id;             // REL header id (config/G4BE08/modules/<mod>/rel.json module_id)
    const char* name;
    void (*prolog)(void);
    void (*epilog)(void);
};

#define MODULE(id, name) {id, #name, name##_prolog, name##_epilog}
static const Re4dcModule g_modules[] = {
    MODULE(74, st1_0),
    MODULE(73, st1_1),
    MODULE(78, st1_2),
    MODULE(86, st1_3),
    MODULE(4, wep02),
    MODULE(18, em12),
};
#undef MODULE

// Binds the header the game read (include/main_sub.h OSModuleHeader: id at 0,
// prolog at 0x34, epilog at 0x38) to the compiled module; 1 = known module.
extern "C" int re4dc_module_bind(void* header)
{
    if (header == 0) {
        re4dc_log("module: null header; link failed\n");
        return 0;
    }
    u32* h = (u32*) header;
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
    const Re4dcModule* m = 0;
    for (unsigned i = 0; i < sizeof(g_modules) / sizeof(g_modules[0]); i++) {
        if (g_modules[i].id == h[0]) m = &g_modules[i];
    }
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
    re4dc_log("module: id %lu -> %s (static)\n", h[0], m->name);
    *prolog = m->prolog;
    *epilog = m->epilog;
    return 1;
}
