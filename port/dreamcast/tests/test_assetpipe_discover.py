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

    def test_source_size_and_room_container(self):
        class Iso:
            files = {"Em/em18.drs": bytes(0x24) + struct.pack(">I", 633120) + bytes(8), "St1/r102.das": b"x"}

            def find(self, rel):
                return next((k for k in self.files if k.lower() == rel.lower()), None)

            def read(self, rel):
                return self.files[self.find(rel)]
        iso = Iso()
        self.assertEqual(d.source_heap4_bytes(iso, "em/em18.drs"), 633120)
        self.assertIsNone(d.source_heap4_bytes(iso, "em/em99.drs"))
        self.assertIsNone(d.source_heap4_bytes(None, "em/em18.drs"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "st1").mkdir()
            self.assertEqual(d.room_container(tmp, iso, 0x102), {"dar": False, "arc": False, "source": True})
            (Path(tmp) / "st1/r102.dar").write_bytes(b"d")
            (Path(tmp) / "st1/r102.arc").write_bytes(b"arc")
            self.assertEqual(d.room_container(tmp, iso, 0x102), {"dar": True, "arc": True, "source": True, "arc_bytes": 3})
            self.assertFalse(d.room_container(tmp, iso, 0x1ff)["source"])


if __name__ == "__main__":
    unittest.main()
