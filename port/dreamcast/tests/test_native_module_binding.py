"""Exercise the actual static binder with the target's 32-bit pointer layout.
Linux i386 freestanding fixture needs no 32-bit libc or installed multilib SDK.
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
#define ENTRY(n) void n##_prolog(){} void n##_epilog(){}
ENTRY(st1_0) ENTRY(st1_1) ENTRY(st1_2) ENTRY(st1_3) ENTRY(wep02) ENTRY(em12) ENTRY(em23)
#undef ENTRY
int re4dc_module_bind(void*);
}
static_assert(sizeof(void*) == 4 && sizeof(unsigned long) == 4);
int check() {
    unsigned long h[16] = {};
    if (re4dc_module_bind(0)) return 1;
    h[0]=18; h[7]=0xDC000001; h[8]=52;
    if (!re4dc_module_bind(h)) return 2;
    if (h[13]!=(unsigned long)em12_prolog || h[14]!=(unsigned long)em12_epilog) return 3;
    if (!re4dc_module_bind(h)) return 4; // stop/restart rebinds this descriptor
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
