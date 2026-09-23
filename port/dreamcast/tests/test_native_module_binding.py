"""Exercise the actual static binder with the target's 32-bit pointer layout.
Linux i386 freestanding fixture needs no 32-bit libc or installed multilib SDK.

Link-time module state follows the GameCube loader: a fresh link (a header
just read from disc) restores the module's pristine .data and zeroes its
.bss; a relink of the header OSUnlink released (stopRelData/restartRelData)
keeps both, even when the next fresh read lands at the same address.
"""
from pathlib import Path
import shutil
import platform
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++') and platform.system() == 'Linux' and platform.machine() in ('x86_64', 'i686'), 'Linux x86 host compiler required')
class NativeModuleBinding(unittest.TestCase):
    def test_compact_reference_rebind_and_rejection(self):
        fixture = r'''#include "re4dc_platform.h"
extern "C" {
void re4dc_log(const char*, ...) {}
void* memcpy(void* d, const void* s, __SIZE_TYPE__ n) {
    volatile char* o = (volatile char*) d; const volatile char* i = (const volatile char*) s;
    while (n--) *o++ = *i++;
    return d;
}
void* memset(void* d, int v, __SIZE_TYPE__ n) {
    volatile char* o = (volatile char*) d;
    while (n--) *o++ = (char) v;
    return d;
}
// Each module's state span as gen_modules.py lays it out: .data, then .bss
// followed by the pristine .data copy.
struct State { char data[8]; char bss[4]; char pristine[8]; };
#define ENTRY(n) void n##_prolog(){} void n##_epilog(){} State n##_state; \
    asm(".globl re4dc_mod_" #n "_data\n.set re4dc_mod_" #n "_data, " #n "_state\n" \
        ".globl re4dc_mod_" #n "_data_end\n.set re4dc_mod_" #n "_data_end, " #n "_state+8\n" \
        ".globl re4dc_mod_" #n "_bss\n.set re4dc_mod_" #n "_bss, " #n "_state+8\n" \
        ".globl re4dc_mod_" #n "_bss_end\n.set re4dc_mod_" #n "_bss_end, " #n "_state+12\n" \
        ".globl re4dc_mod_" #n "_pristine\n.set re4dc_mod_" #n "_pristine, " #n "_state+12\n");
ENTRY(st1_0) ENTRY(st1_1) ENTRY(st1_2) ENTRY(st1_3) ENTRY(wep02) ENTRY(em12) ENTRY(em23) ENTRY(em15) ENTRY(em26) ENTRY(em28) ENTRY(em21)
#undef ENTRY
int re4dc_module_bind(void*);
int re4dc_module_unbind(void*);
void re4dc_module_counts(unsigned*, unsigned*, unsigned*, unsigned*);
}
static_assert(sizeof(void*) == 4 && sizeof(unsigned long) == 4);
int check() {
    unsigned long h[16] = {};
    if (re4dc_module_bind(0)) return 1;
    h[0]=18; h[7]=0xDC000001; h[8]=52;
    if (!re4dc_module_bind(h)) return 2;
    if (h[13]!=(unsigned long)em12_prolog || h[14]!=(unsigned long)em12_epilog) return 3;
    if (!re4dc_module_bind(h)) return 4; // a second link without unlink is a fresh link
    h[3]=2;
    if (re4dc_module_bind(h) || h[13] || h[14]) return 5;
    h[3]=0; h[13]=1;
    if (re4dc_module_bind(h) || h[13] || h[14]) return 6;
    h[0]=999;
    if (re4dc_module_bind(h) || h[13] || h[14]) return 7;
    h[0]=4; h[7]=3; h[13]=123; h[14]=456; // full reference REL remains supported
    if (!re4dc_module_bind(h) || h[13]!=(unsigned long)wep02_prolog) return 8;
    h[0]=7;
    if (!re4dc_module_bind(h) || h[13]!=(unsigned long)em23_prolog ||
        h[14]!=(unsigned long)em23_epilog) return 9;
    for (unsigned i=1;i<16;++i) h[i]=0;
    h[7]=0xDC000001;
    if (!re4dc_module_bind(h) || h[13]!=(unsigned long)em23_prolog) return 10;

    // Link-time state: st1_0 as linked has data 1..8 and a zero bss.
    for (int i = 0; i < 8; ++i) st1_0_state.data[i] = char(i + 1);
    unsigned long r[16] = {};
    r[0]=74; r[7]=0xDC000001;
    if (!re4dc_module_bind(r)) return 11;             // first link captures pristine data
    st1_0_state.data[0] = 99; st1_0_state.bss[0] = 42; // the room runs
    if (!re4dc_module_unbind(r) || r[1] == 0) return 12;
    r[13]=r[14]=0;                                     // restartRelData relinks the same header
    if (!re4dc_module_bind(r) || r[1] != 0) return 14;
    if (r[13]!=(unsigned long)st1_0_prolog) return 13;
    if (st1_0_state.data[0] != 99 || st1_0_state.bss[0] != 42) return 15;  // state kept
    if (!re4dc_module_unbind(r)) return 16;
    for (int i = 0; i < 16; ++i) r[i] = 0;             // next REL read lands at the same address
    r[0]=74; r[7]=0xDC000001;
    if (!re4dc_module_bind(r)) return 17;
    if (st1_0_state.data[0] != 1 || st1_0_state.data[7] != 8 || st1_0_state.bss[0] != 0) return 18;
    st1_0_state.data[3] = 77; st1_0_state.bss[3] = 5;
    unsigned long other[16] = {};                     // a fresh read elsewhere, without unlink
    other[0]=74; other[7]=0xDC000001;
    if (!re4dc_module_bind(other) || st1_0_state.data[3] != 4 || st1_0_state.bss[3] != 0) return 19;
    if (!re4dc_module_unbind(r)) return 20;           // stale header: reported, harmless
    unsigned fresh, restarts, unlinks, linked;
    re4dc_module_counts(&fresh, &restarts, &unlinks, &linked);
    // em12 x2, wep02, em23 x2, st1_0 x3 fresh; one st1_0 restart.
    if (fresh != 8 || restarts != 1 || unlinks != 2 || linked != 4) return 21;
    return 0;
}
extern "C" void _start() {
    int result=check();
    asm volatile("int $0x80" : : "a"(1), "b"(result) : "memory");
    __builtin_unreachable();
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'fixture.cpp';exe=Path(tmp)/'fixture';cpp.write_text(fixture)
            subprocess.run(['g++','-m32','-nostdlib','-fno-pie','-no-pie',
                            '-fno-stack-protector','-fno-exceptions','-fno-rtti',
                            '-I'+str(ROOT/'port/dreamcast/game/platform/include'),
                            str(ROOT/'port/dreamcast/game/platform/modules.cpp'),
                            str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
