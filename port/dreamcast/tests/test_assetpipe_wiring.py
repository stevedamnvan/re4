"""assets.sh discover round 2: the porting-trap lint and the module wiring writer."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from assetpipe import wiring as w  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

TRAPS = '''static Camera cut_cam = { 0 };
extern Camera cut_cam_v asm("cut_cam");
extern Camera other_v asm("global_cam");
static inline cEm* work(u32 no)
{
#if !defined(__PPC__)
    return (cEm*) EmMgr.workAt(no);
#else
    return (cEm*) ((u8*) EmMgr.pArray + EmMgr.size * no);
#endif
}
void EmXXInit(cEm* em)
{
#if defined(RE4DC_GAME) && !defined(__PPC__)
    new (em) cEmXX;
#else
    new (em) cEmXX();
#endif
    new (em) cEmYY();
    u8* p = (u8*)this + 4 + 2 * sizeof(int);
    int n = EmMgr.size * 2;  // raw slot arithmetic
}
'''


class Lint(unittest.TestCase):
    def lint(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.cpp").write_text(text)
            return [(f["rule"], f["line"]) for f in w.lint_file(tmp, "a.cpp")]

    def test_traps_in_dreamcast_code_only(self):
        self.assertEqual(self.lint(TRAPS), [("asm-alias", 2), ("value-init", 19), ("vptr-offset", 20), ("slot-math", 21)])

    def test_conditions(self):
        self.assertFalse(w._cond(" defined(__PPC__)"))
        self.assertTrue(w._cond(" defined(RE4DC_GAME) && !defined(__PPC__)"))
        self.assertFalse(w._cond(" RE4DC_UNKNOWN_KNOB"))
        self.assertTrue(w._cond(" 0x10u > 1"))

    def test_route_modules_are_clean(self):
        for mod in ("em12", "em15", "em21", "em23", "em26", "em28", "em2a", "st1_0"):
            self.assertEqual([f for f in w.lint_module(REPO, mod) if f["severity"] == "error"], [], mod)


class Wire(unittest.TestCase):
    def test_wire_writes_the_four_edits_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            dc = Path(tmp) / w.GAME
            (dc / "platform").mkdir(parents=True)
            for f in ("Makefile", "platform/modules.cpp"):
                shutil.copy(REPO / w.GAME / f, dc / f)
            mk0 = (dc / "Makefile").read_text()
            done = w.wire(tmp, "em99", 99, "r1ff: entry", audit=False)
            self.assertEqual(done, ["Makefile MODULES += em99", "modules.cpp MODULE(em99)", "modules.cpp MODULE(99, em99)"])
            mc = (dc / "platform/modules.cpp").read_text()
            self.assertIn("MODULE(em99)\n#if RE4DC_SUBSCREEN && !RE4DC_SUBSCREEN_OVL", mc)
            self.assertIn("    MODULE(99, em99),  // r1ff: entry\n#if RE4DC_SUBSCREEN_OVL", mc)
            self.assertEqual(w.wire(tmp, "em99", 99, "", audit=True), ["ENEMY_DEMAND audit list += em99"])
            self.assertEqual(w.wire(tmp, "em99", 99, "", audit=True), [])
            mk = (dc / "Makefile").read_text()
            self.assertEqual(len(mk.splitlines()), len(mk0.splitlines()))
            self.assertRegex(mk, r"filter-out [^,]* em99,\$\(MODULES\)")


if __name__ == "__main__":
    unittest.main()
