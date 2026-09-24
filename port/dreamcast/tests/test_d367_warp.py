"""tools/d367/warp.py: presets expand to the warp.txt lines dbgwarp_bridge.cpp parses."""
import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).resolve().parents[1] / "tools" / "d367" / "warp.py"
spec = importlib.util.spec_from_file_location("warp", TOOL)
warp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warp)

KEYS = {"name", "room", "jp", "pos", "dir", "ang", "rsf", "scenario", "find", "unlock", "inv", "area", "act", "dump"}


class WarpPresets(unittest.TestCase):
    def test_every_line_is_a_known_key(self):
        for name, p in warp.PRESETS.items():
            if p.get("pos", 0) is None:
                continue
            for line in warp.lines_for(p, door=True, dump=True, name=name).splitlines():
                if line.startswith("#"):
                    continue
                self.assertIn(line.split()[0], KEYS, (name, line))

    def test_east_door_actions_and_after_state_variant(self):
        text = warp.lines_for(warp.PRESETS["r100-east-door"], door=True)
        self.assertIn("room 0x100", text)
        self.assertIn("act 60 a 4", text)
        after = warp.lines_for(warp.PRESETS["r100-east-door-after"])
        rsf = [l for l in after.splitlines() if l.startswith("rsf 0x100")][0].split()[2:]
        for bit in ("3", "4", "10", "13"):
            self.assertIn(bit, rsf)

    def test_house_door_keeps_s03_armed(self):
        text = warp.lines_for(warp.PRESETS["r100-house-door"])
        rsf = [l for l in text.splitlines() if l.startswith("rsf 0x100")][0].split()[2:]
        self.assertNotIn("3", rsf)
        self.assertNotIn("10", rsf)
        self.assertIn("13", rsf)

    def test_explicit(self):
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            warp.main(["--room", "0x101", "--pos", "1", "2", "3", "--rsf", "0x101:6,7", "--act", "a:10:4"])
        text = out.getvalue()
        self.assertIn("room 0x101", text)
        self.assertIn("rsf 0x101 6 7", text)
        self.assertIn("act 10 a 4", text)


if __name__ == "__main__":
    unittest.main()
