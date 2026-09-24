"""assets.sh discover round 2: Standard budgets and VRAM."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from assetpipe import standard as st  # noqa: E402

INDEX = """re4dc-std 1 r1ff
lod_px 5
mesh MAINSCENARIO 600 0123456789abcdef
orig MAINSCENARIO 1000 0123456789abcdef
tex 00000001-00000002 512 128 6176 6320
tex 00000003-00000004 1024 128 10272 10416
drop 00000005-00000006
end 7
"""

LOG = """native UI VRAM: frame=120 budget=900 used=0 free=900 rejects=0 retries=0 evicted=0
native UI: load /cd/dc/tex/0/07cbd425-58874830.re4tex 32x32 fmt=14
native UI: package rejected: open failed
native UI: upload FAILED vram=0
native UI VRAM: frame=240 budget=900 used=850 free=50 rejects=0 retries=0 evicted=0
native UI VRAM: frame=360 budget=900 used=800 free=100 rejects=2 retries=0 evicted=0
"""


class Standard(unittest.TestCase):
    def test_std_set_and_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "out/standard/r1ff/low"
            p.mkdir(parents=True)
            (p / "index.txt").write_text(INDEX)
            s = st.std_set(tmp, "r1ff")
        self.assertEqual((s["heap_delta"], s["tex"], s["tex_vram"], s["drops"]), (-400, 2, 16448, 1))
        out, problems = st.budgets(s, 5000, {"vram": {"pool": 30000, "original_used": 5000, "source": "x"}})
        self.assertEqual(out["enemy_heap4_bytes"], 5400)
        self.assertEqual(out["vram"]["standard_free_min"], 30000 - 5000 - 16448)
        self.assertEqual(problems, [])
        self.assertEqual(len(st.budgets(s, None, {"vram": {"pool": 30000, "original_used": 20000}})[1]), 1)
        self.assertEqual(st.budgets(None, 1, {})[0]["verdict"], "no Standard set built for this room")

    def test_vram_log(self):
        v, problems = st.vram_log(LOG)
        self.assertEqual((v["min_free"], v["max_used"], v["rejects"]), (50, 850, 2))
        self.assertEqual(v["missing_textures"], ["/cd/dc/tex/0/07cbd425-58874830.re4tex"])
        self.assertEqual(len(problems), 2)


if __name__ == "__main__":
    unittest.main()
