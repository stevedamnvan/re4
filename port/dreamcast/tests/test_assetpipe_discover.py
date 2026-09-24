"""assets.sh discover: source-table parsing and the stage-1 list rules (no private data needed)."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from assetpipe import discover as d  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


class Discover(unittest.TestCase):
    def test_tables_map_route_enemies(self):
        t = d.Tables(REPO)
        self.assertEqual(t.enemy(0x2a), {"archive": "em/em2a.drs", "rel": "rel/em2a.rel", "module": "em2a"})
        self.assertEqual(t.enemy(0x12)["module"], "em12")
        self.assertIsNone(t.enemy(0x40))   # cEmObj: no file

    def test_stage1_lists(self):
        self.assertEqual(d.esl_list_numbers(0x100), [(0, "always")])
        self.assertEqual(d.esl_list_numbers(0x10C), [(1, "always")])
        self.assertEqual(d.esl_list_numbers(0x10E)[0][0], 1)

    def test_esl_record(self):
        rec = bytearray(0x40)
        d.ESL_REC.pack_into(rec, 0x20, 1, 0x2a, 0, 0, 0x20, 100, 0, 0, 1, 2, 3, 0, 0, 0, 0x100, 0)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.esl"
            p.write_bytes(bytes(rec))
            e = d.esl_entries(p, 0x100)
        self.assertEqual([(x["no"], x["id"], x["alive"], x["pos_mm"]) for x in e], [(1, 0x2a, True, [10, 20, 30])])

    def test_heap4_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "em").mkdir()
            (Path(tmp) / "em/em23.drs").write_bytes(bytes(0x24) + struct.pack("<I", 0x36ac0) + bytes(8))
            self.assertEqual(d.heap4_bytes(tmp, "em/em23.drs"), 0x36ac0)
            self.assertIsNone(d.heap4_bytes(tmp, "em/none.drs"))


if __name__ == "__main__":
    unittest.main()
