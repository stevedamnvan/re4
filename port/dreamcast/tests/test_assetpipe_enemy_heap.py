"""assets.sh discover round 2: heap-4 options per enemy archive."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from assetpipe import enemy_heap as h  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def archive(entries, rel=0):
    """A prepared (LE) .drs: record 0 = body at 0x400; entries = [(tag, bytes)]."""
    n = len(entries)
    head = 16 + 8 * n
    head = (head + 31) & ~31
    offs, o = [], head
    for _, size in entries:
        offs.append(o)
        o += size
    body = bytearray(o + rel)
    struct.pack_into("<2I", body, 0, n, o if rel else 0)
    struct.pack_into("<%dI" % n, body, 16, *offs)
    for i, (tag, _) in enumerate(entries):
        body[16 + 4 * (n + i):20 + 4 * (n + i)] = tag.encode().ljust(4, b"\0")
    d = bytearray(0x400)
    struct.pack_into("<4I", d, 0x20, 0, len(body), 0, 0x400)
    struct.pack_into("<I", d, 0x40, 0xFFFFFFFF)
    return bytes(d + body)


class EnemyHeap(unittest.TestCase):
    def test_breakdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "em99.drs"
            p.write_bytes(archive([("BIN", 0x100), ("TPL", 0x2000), ("FCV", 0x400)], rel=0x60))
            br = h.breakdown(p)
        self.assertEqual((br["BIN"], br["TPL"], br["FCV"], br["REL"]), (0x100, 0x2000, 0x400, 0x60))
        self.assertEqual(br["body"], 0x40 + 0x100 + 0x2000 + 0x400 + 0x60)

    def test_contracts_follow_the_tool(self):
        c = h.contracts(REPO)
        self.assertIn("em12.drs", c["GANADO"])
        self.assertIn("em21.drs", c["SMALL"])
        self.assertNotIn("em23.drs", c["SMALL"] + c["GANADO"])

    def test_options_and_plan(self):
        br = {"TPL": 24736, "FCV": 132576, "EFF": 36480, "REL": 17216, "body": 223936}
        o = {(x["option"], x["status"], x["bytes"]) for x in h.options("em/em23.drs", br, None, None)}
        self.assertEqual(o, {("rel-strip", "needs-contract", 17152), ("tex-upload", "needs-contract", 24736),
                             ("motion-stream", "needs-contract", 132576), ("effect-compact", "needs-contract", 0)})
        small = h.options("em/em21.drs", {"TPL": 192, "FCV": 294240}, "SMALL", {"textures_selected": 2})
        self.assertEqual([(x["option"], x["status"]) for x in small], [("motion-stream", "needs-contract")])
        ganado = h.options("em/em15.drs", {"TPL": 3904, "FCV": 153056}, "GANADO", {"hot_payload_bytes": 1})
        self.assertEqual([(x["option"], x["status"]) for x in ganado], [("motion-stream", "applied")])
        q = [{"archive": "a", "option": "tex-upload", "bytes": 5000, "status": "qualified"},
             {"archive": "b", "option": "motion-stream", "bytes": 90000, "status": "needs-contract"},
             {"archive": "c", "option": "motion-stream", "bytes": 60000, "status": "needs-contract"}]
        p = h.plan(100000, q)
        self.assertEqual([x["archive"] for x in p["chosen"]], ["a", "b", "c"])
        self.assertEqual((p["covered"], p["remaining"]), (155000, 0))
        self.assertEqual(h.plan(200000, q)["remaining"], 45000)


if __name__ == "__main__":
    unittest.main()
