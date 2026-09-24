"""assets.sh discover round 2: event actors (evd files)."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from assetpipe import events as ev  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def evd(actors, assets):
    """A minimal big-endian evd: header, kind-3 packets + EndPac (27), asset table, payloads."""
    pk = b""
    for name, model in actors:
        p = struct.pack(">2I4H", 3, 0, 0xFFFF, 0, 128, 0) + name.encode().ljust(12, b"\0") + \
            model.encode().ljust(48, b"\0") + b"\0" * 48 + b"\0" * 4
        pk += p
    pk += struct.pack(">2I4H", 27, 0, 0, 0, 16, 0)
    po, ps = 80, len(pk)
    bo = po + ps
    data_start = bo + 64 * len(assets)
    table, payload, o = b"", b"", data_start
    for name, size in assets:
        table += name.encode().ljust(48, b"\0") + struct.pack(">I", o) + b"\0" * 12
        payload += b"\0" * size
        o += size
    head = b"event/evd/r1ffs00.evd".ljust(32, b"\0") + b"r1ff".ljust(8, b"\0") + b"s00".ljust(12, b"\0") + \
        b"\0" * 12 + struct.pack(">4I", po, ps, len(assets), bo)
    return head + pk + table + payload


class Events(unittest.TestCase):
    def test_parse(self):
        d = evd([("em1000", "em/em10/em1000.bin"), ("pl0000", "em/pl00/pl000a.bin"), ("obm0200", "obj/o.bin")],
                [("a.bin", 0x100), ("a.tpl", 0x40), ("b.bin", 0x20)])
        r = ev.parse(d)
        self.assertEqual([a["name"] for a in r["actors"]], ["em1000", "pl0000", "obm0200"])
        self.assertEqual(r["actor_groups"], {"em10": 1, "obm": 1, "pl00": 1})
        self.assertEqual(r["asset_bytes"], {"BIN": 0x120, "TPL": 0x40})

    def test_script_events(self):
        self.assertEqual(ev.script_events(REPO, 0x101), ["r101s00", "r101s21", "r101s30"])
        self.assertIn("r100s40", ev.script_events(REPO, 0x100))

    def test_events_need_movie_or_qualified_evd(self):
        d = evd([("pl0000", "em/pl00/pl000a.bin")], [("a.bin", 0x20)])

        class Iso:
            def find(self, rel):
                return rel if rel.lower() == "evd/r101s00.evd" else None

            def read(self, rel):
                return d
        with tempfile.TemporaryDirectory() as tmp:
            rows, problems = ev.events(REPO, 0x101, Iso(), tmp, None)
            self.assertEqual([r["on_disc"] for r in rows], [True, False, False])
            self.assertEqual(problems, ["event r101s00: no route movie and no prepared evd"])
            (Path(tmp) / "evd").mkdir()
            (Path(tmp) / "evd/r101s00.evd").write_bytes(b"x")
            self.assertEqual(ev.events(REPO, 0x101, Iso(), tmp, None)[1], ["event r101s00: no route movie and no qualified .evq sidecar"])
            (Path(tmp) / "m/r101s00").mkdir(parents=True)
            (Path(tmp) / "m/r101s00/r101s00.seq").write_bytes(b"x")
            self.assertEqual(ev.events(REPO, 0x101, Iso(), tmp, Path(tmp) / "m")[1], [])


if __name__ == "__main__":
    unittest.main()
