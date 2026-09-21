"""Run the native arena carver against bounded/failing host allocations."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('g++'), 'host compiler required')
class NativeMemoryLayout(unittest.TestCase):
    def test_live_regions_fallback_and_exhaustion(self):
        platform = ROOT / 'port/dreamcast/game/platform'
        fixture = r'''
#include <cassert>
#include <cstring>
#include <stdexcept>
#include "re4dc_platform.h"
alignas(32) unsigned char arena[13 * 1024 * 1024];
static unsigned long ceiling = sizeof(arena), calls;
extern "C" void* __wrap_memalign(unsigned long align, unsigned long size) {
    assert(align == 32); ++calls;
    return size <= ceiling ? arena : nullptr;
}
extern "C" void arch_exit() { throw std::runtime_error("no arena"); }
extern "C" void thd_sleep(int) {}
static void check(unsigned long capacity) {
    re4dc_mem_init();
    assert(re4dc_mem.arena_lo == (unsigned long)arena);
    assert(re4dc_mem.arena_hi - re4dc_mem.arena_lo == capacity);
    assert(re4dc_mem.dvd == re4dc_mem.sound); // marker only
    assert(re4dc_mem.sound == re4dc_mem.arena_lo);
    assert(re4dc_mem.core - re4dc_mem.sound == 0x80000);
    assert(re4dc_mem.option - re4dc_mem.core == 0x234000);
    assert(re4dc_mem.player - re4dc_mem.option == 0x40000);
    assert(re4dc_mem.weapon - re4dc_mem.player == 0x118000);
    assert(re4dc_mem.heap - re4dc_mem.weapon == 0x70000);
    assert(re4dc_mem.heap_end == re4dc_mem.arena_hi);
    assert(re4dc_mem.heap_end - re4dc_mem.heap >= 0x300000);
    // Full source sound capacity remains writable without touching core data.
    memset(arena, 0x5a, sizeof(arena));
    memset((void*)re4dc_mem.sound, 0xa5, 0x80000);
    assert(*(unsigned char*)re4dc_mem.core == 0x5a);
    assert(*(unsigned char*)(re4dc_mem.core - 1) == 0xa5);
    // Native DVD staging must stay outside every carved arena region.
    auto dvd = (unsigned long)re4dc_dvd_buff;
    assert(dvd + 0x20000 <= re4dc_mem.arena_lo || dvd >= re4dc_mem.arena_hi);
    auto before = calls; re4dc_mem_init(); assert(calls == before);
}
int main() {
    check(sizeof(arena)); assert(calls == 1);
    assert(re4dc_mem.heap_end - re4dc_mem.heap == 8720 * 1024);
    re4dc_mem = {}; calls = 0; ceiling = sizeof(arena) - 0x40000;
    check(ceiling); assert(calls == 2);
    re4dc_mem = {}; calls = 0; ceiling = 0;
    try { re4dc_mem_init(); assert(false); } catch (const std::runtime_error&) {}
    assert(!re4dc_mem.arena_lo && calls > 1);
}
'''
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            (work / 'kos.h').write_text(
                'extern "C" void arch_exit();\nextern "C" void thd_sleep(int);\n')
            (work / 'test.cpp').write_text(fixture)
            executable = work / 'test'
            subprocess.run(['g++', '-std=c++17', '-I'+str(work),
                            '-I'+str(platform/'include'), str(platform/'mem.cpp'),
                            str(work/'test.cpp'), '-Wl,--wrap=memalign',
                            '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
