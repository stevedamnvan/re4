"""Room-change lifecycle of the native adapters (frontier W6).

Source order: native room owners retire at StageSet entry, before the stage
reload / room-REL relink recreates heaps 2 and 3 over the live heap 4, and a
new heap-4 generation opens only after gameRoomMemInit replaced heap 4.
REL state: each resident module's writable sections form one span with a
pristine copy (tools/gen_modules.py), so a fresh OSLink can restore them.
ARAM: the SDK stack allocator (ARInit entries, ARFree pops), run on the host.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
GAME = ROOT / "port/dreamcast/game"


def function(text, signature):
    begin = text.index(signature)
    brace = text.index("{", begin)
    end, depth = brace + 1, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[begin:end]


class SourceOrder(unittest.TestCase):
    def test_retire_before_any_heap_replacement(self):
        stage = function((ROOT / "src/game/stage.cpp").read_text(), "void StageSet()\n{")
        leave = stage.index("re4dc_room_leave();")
        self.assertLess(leave, stage.index("MemReplaceHeap(1, 2);"))
        self.assertLess(leave, stage.index("MemReplaceHeap(2, 3);"))
        self.assertLess(leave, stage.index("RoomData.stopRelData();"))

    def test_new_generation_after_room_heap_rebuild(self):
        game = (ROOT / "src/game/game.cpp").read_text()
        mem = function(game, "void gameRoomMemInit()\n{")
        enter = mem.index("re4dc_room_enter();")
        self.assertLess(mem.index("re4dc_ui_retire_room();"), mem.index("MemReplaceHeap(3, 4);"))
        self.assertGreater(enter, mem.rindex("MemReplaceHeap(3, 4);"))
        self.assertGreater(enter, mem.rindex("MemSetCurrentHeap(4);"))
        self.assertLess(enter, mem.index("memclr_asm(pG->pad_16C"))
        loop = function(game, "void gameMainLoop()\n{")
        self.assertLess(loop.index("re4dc_room_cycle_poll()"), loop.index("UpdateNearClipDist();"))

    def test_heap4_cells_free_by_handle(self):
        bridge = (GAME / "ui_bridge.cpp").read_text()
        self.assertNotIn("Mem_free_h(", bridge)
        self.assertIn("OSFreeToHeap(Heap[4].handle,cell);", bridge)
        # Orchestration stays ahead of the unit-tested tail (test_model_preparation_storage).
        split = bridge.index('#include "native_model.h"')
        self.assertLess(bridge.index('extern "C" void re4dc_room_leave()'), split)
        self.assertGreater(bridge.index("void* room_alloc4("), split)


class ModuleState(unittest.TestCase):
    def test_state_span_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            mk = Path(tmp) / "modules.mk"
            subprocess.run([sys.executable, str(GAME / "tools/gen_modules.py"),
                            str(ROOT / "config/G4BE08/modules"), str(ROOT), tmp, str(mk),
                            "st1_0", "em12"], check=True)
            rules = mk.read_text()
            for mod in ("st1_0", "em12"):
                script = (Path(tmp) / "mod" / mod / "state.ld").read_text()
                data = script.index("_re4dc_mod_%s_data = .;" % mod)
                self.assertLess(data, script.index("*(.data .data.*)"))
                self.assertLess(script.index("*(.data .data.*)"), script.index("_re4dc_mod_%s_data_end = .;" % mod))
                bss = script.index("*(.bss .bss.* COMMON)")
                self.assertLess(script.index("_re4dc_mod_%s_bss = .;" % mod), bss)
                self.assertLess(bss, script.index("_re4dc_mod_%s_bss_end = .;" % mod))
                self.assertIn(". += SIZEOF(.data.re4dc_module.%s);" % mod, script)
                self.assertIn("sh-elf-ld -r -d --force-group-allocation -EL -T $(OBJDIR)/mod/%s/state.ld" % mod, rules)
                for symbol in ("data", "data_end", "bss", "bss_end", "pristine"):
                    self.assertIn("-G _re4dc_mod_%s_%s" % (mod, symbol), rules)
            self.assertIn("REL static constructors/destructors need per-link execution", rules)
            self.assertIn("common symbols escape the REL state span", rules)

    def test_link_semantics_documented_in_os(self):
        os_cpp = (GAME / "platform/os.cpp").read_text()
        self.assertIn("return re4dc_module_unbind(module);", function(os_cpp, "BOOL OSUnlink(void* module)"))


@unittest.skipUnless(shutil.which("g++"), "host g++ required")
class AramStack(unittest.TestCase):
    def test_sdk_stack_allocator(self):
        audio = (GAME / "platform/audio_stub.cpp").read_text()
        allocator = audio[audio.index("static const u32 kAramSize"):]
        allocator = allocator[:allocator.index("\n}", allocator.index("void re4dc_aram_state")) + 2]
        code = r'''
#include <cassert>
#include <stdexcept>
typedef unsigned long u32;
static u32 g_aramNext = 0x4000;
static int irq_disable(){return 0;} static void irq_restore(int){}
static void re4dc_log(const char*,...){}
static void re4dc_missing(const char*){throw std::runtime_error("halt");}
''' + allocator + r'''
int main(){
    u32 blocks[3]; u32 sp, free_blocks, length=0;
    assert(ARInit(blocks,3)==0x4000 && ARCheckInit());
    assert(ARAlloc(0x6FC000)==0x4000);                 // SndInit's one block
    re4dc_aram_state(&sp,&free_blocks); assert(sp==0x700000 && free_blocks==2);
    for(int room=0;room<4;++room){                     // a stack user pairs its alloc/free
        assert(ARAlloc(0x40000)==0x700000);
        assert(ARFree(&length)==0x700000 && length==0x40000);
    }
    re4dc_aram_state(&sp,&free_blocks); assert(sp==0x700000 && free_blocks==2);
    assert(ARInit(blocks,3)==0x4000);                  // a second init keeps the stack
    re4dc_aram_state(&sp,&free_blocks); assert(sp==0x700000);
    assert(ARAlloc(0x100)==0x700000 && ARAlloc(0x20)==0x700100);
    bool halted=false; try{ARAlloc(0x20);}catch(const std::exception&){halted=true;}
    assert(halted);                                    // out of blocks: halt, no overlap
    ARFree(0); ARFree(0);
    halted=false; try{ARAlloc(0x1000000);}catch(const std::exception&){halted=true;}
    assert(halted);                                    // out of ARAM
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp = Path(tmp) / "aram.cpp"; exe = Path(tmp) / "aram"
            cpp.write_text(code)
            subprocess.run(["g++", "-std=c++17", "-O1", "-fsanitize=address,undefined", str(cpp), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
