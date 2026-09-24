"""Asset pipeline (tools/assetpipe): formulas, package reader, camera pricing, cache
determinism. Synthetic data only (no game files)."""
import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("assetpipe_lod_tests", pathlib.Path(__file__).with_name(
    "test_room_bins_lod.py"))
LT = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = LT
spec.loader.exec_module(LT)

from assetpipe import r4im, texture, util  # noqa: E402
from assetpipe.cache import Cache  # noqa: E402
from assetpipe.camera import build_instances, price, screen_k  # noqa: E402
from assetpipe.config import Config  # noqa: E402


def package(n=24, bump=200.0, spacing=40.0):
    blob, summary = LT.convert([LT.grid_bin(n, spacing=spacing, bump=bump, uv_scale=0.01)], eps_world=(1.0, 4.0, 16.0),
                               min_gain=0.9)
    return blob, summary


class FormulaTests(unittest.TestCase):
    def test_screen_constant(self):
        cfg = Config()
        self.assertAlmostEqual(screen_k(cfg.cost), 415.692, places=3)

    def test_texture_bytes(self):
        self.assertEqual(texture.vram_bytes("vq", 256, 256), 2048 + 256 * 256 // 4)
        self.assertEqual(texture.vram_bytes("rgb16", 528, 132), 2 * 1024 * 256)   # padded power of two
        self.assertEqual(texture.vram_bytes("pal4", 128, 128), 128 * 128 // 2)

    def test_needed_scale(self):
        # rho 1 texel/mm seen no closer than 1 m: m = 415.7/1000 < 1/2 -> half size is invisible
        f, m = texture.needed_scale(1.0, 1000.0)
        self.assertEqual(f, 0.5)
        self.assertAlmostEqual(m, 0.4157, places=3)
        self.assertEqual(texture.needed_scale(0.1, 1000.0)[0], 1.0)

    def test_impostor_rule_reproduces_12m(self):
        cfg = Config()
        k = screen_k(cfg.cost)
        d = cfg.cost["impostor"]["view_error"] * 3000.0 * k / cfg.cost["impostor"]["p_imp_px"]
        self.assertTrue(11000 < d < 13000, d)

    def test_canonical_json(self):
        self.assertEqual(util.canon({"b": 0.1 + 0.2, "a": (1, 2.0)}), b'{"a":[1,2],"b":0.3}')
        self.assertEqual(util.ranges([5, 0, 1, 2, 9]), "0-2,5,9")
        self.assertEqual(util.parse_ranges("0-2,5"), [0, 1, 2, 5])


class ReaderTests(unittest.TestCase):
    def test_levels_match_converter(self):
        blob, summary = package()
        pk = r4im.Package(blob)
        self.assertEqual(pk.version, 2)
        self.assertEqual(pk.counts["meshlets"], summary["meshlets"])
        lv = pk.mesh_summary(0)
        self.assertEqual(lv[0]["tris"], summary["level0_triangles"])
        self.assertTrue(all(a["tris"] >= b["tris"] for a, b in zip(lv, lv[1:])))
        tris = pk.level_triangles(0, 0)
        self.assertEqual(len(tris), summary["level0_triangles"])

    def test_bytes_formula_close(self):
        blob, s = package()
        pred = r4im.predicted_bytes(s["meshes"], s["parts"], s["meshlets"], s["clusters"], s["levels"],
                                    s["vertices"], s["strip_bytes"], palette=s["palette"])
        self.assertLess(abs(pred - len(blob)) / len(blob), 0.05)


class PricingTests(unittest.TestCase):
    def setUp(self):
        blob, _ = package()
        self.pk = r4im.Package(blob)
        self.cfg = Config()
        w = dict(owner="X", code=1, bin=0, common=False, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0),
                 scale=(10.0, 10.0, 10.0))
        self.inst = build_instances({"X": self.pk}, [w], lambda w: "a")

    def views(self, dists):
        return [dict(eye=(4600.0, 1600.0, -d), yaw=0.0, pitch=0.0) for d in dists]

    def test_bias_never_costs_more(self):
        opts = {"a": [dict(id="b1", bias=1.0), dict(id="b05", bias=0.5), dict(id="b025", bias=0.25)]}
        pr = price(self.inst, self.views([500.0, 3000.0, 8000.0, 20000.0]), opts, self.cfg.cost, jobs=1)
        c = pr.counts["a"]
        self.assertGreaterEqual(c[0]["records"], c[1]["records"])
        self.assertGreaterEqual(c[1]["records"], c[2]["records"])
        self.assertEqual(pr.quality["a"][0], 0.0)
        self.assertGreaterEqual(pr.quality["a"][2], pr.quality["a"][1])

    def test_fog_far_culls(self):
        opts = {"a": [dict(id="b1", bias=1.0)]}
        pr = price(self.inst, self.views([30000.0]), opts, self.cfg.cost, far=25000.0, jobs=1)
        self.assertEqual(pr.counts["a"][0]["records"], 0)

    def test_parallel_equals_serial(self):
        opts = {"a": [dict(id="b1", bias=1.0), dict(id="b05", bias=0.5)]}
        views = self.views([float(d) for d in range(500, 20000, 700)])
        a = price(self.inst, views, opts, self.cfg.cost, jobs=1)
        b = price(self.inst, views, opts, self.cfg.cost, jobs=4)
        self.assertEqual(a.ms, b.ms)
        self.assertEqual(a.quality, b.quality)


class CacheTests(unittest.TestCase):
    def test_hit_and_normalised_text(self):
        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d) / "in.txt"
            src.write_text("x")
            c = Cache(pathlib.Path(d) / "root", log=lambda *a: None)
            calls = []

            def fn(out, work):
                calls.append(1)
                (out / "a.json").write_text(json.dumps({"work": str(work), "root": str(c.root)}))
                (out / "b.bin").write_bytes(b"\x01\x02")
                return {"n": 1}
            o1 = c.step("t", {"p": 1}, {"src": src}, {"tool": "1"}, fn)
            o2 = c.step("t", {"p": 1}, {"src": src}, {"tool": "1"}, fn)
            self.assertEqual(len(calls), 1)
            self.assertTrue(o2.hit)
            self.assertEqual(o1.key, o2.key)
            self.assertEqual(json.loads(o1.path("a.json").read_text()), {"work": "$WORK", "root": "$ROOT"})
            src.write_text("y")
            o3 = c.step("t", {"p": 1}, {"src": src}, {"tool": "1"}, fn)
            self.assertNotEqual(o3.key, o1.key)

    def test_verify_detects_nondeterminism(self):
        with tempfile.TemporaryDirectory() as d:
            c = Cache(pathlib.Path(d), log=lambda *a: None)
            n = [0]

            def fn(out, work):
                n[0] += 1
                (out / "x").write_bytes(bytes([n[0]]))
            c.step("t", {}, {}, {}, fn)
            v = Cache(pathlib.Path(d), verify=True, log=lambda *a: None)
            v.step("t", {}, {}, {}, fn)
            self.assertEqual(len(v.mismatches), 1)


class VanishGuardTests(unittest.TestCase):
    """An empty LOD level (no meshlets) makes the object vanish; a Standard bias must not bring
    that nearer than Original (budget._vanish_min, camera vanish_min, generators.vanish_guard)."""

    def setUp(self):
        blob, _ = LT.convert([LT.grid_bin(4, spacing=40.0, bump=200.0, uv_scale=0.01)], eps_world=(50.0, 400.0, 3000.0),
                             min_gain=0.5)
        self.blob = blob
        self.pk = r4im.Package(blob)
        lv = [(e, l) for p in self.pk.mesh_parts(0) for cl in self.pk.part_levels(p) for e, l in cl["levels"]]
        self.assertFalse(lv[-1][1], "fixture needs an empty last level")
        self.empty_err = lv[-1][0]
        self.cfg = Config()
        w = dict(owner="X", code=1, bin=0, common=False, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0),
                 scale=(1.0, 1.0, 1.0))
        self.inst = build_instances({"X": self.pk}, [w], lambda w: "a")

    def test_pricing_keeps_original_vanish_distance(self):
        px_o, px_s = 3.0, 5.0
        vm = self.empty_err * px_s / px_o
        views = [dict(eye=(60.0, 100.0, -10000.0), yaw=0.0, pitch=0.0)]
        orig = price(self.inst, views, {"a": [dict(id="o", bias=1.0)]}, self.cfg.cost, px=px_o, jobs=1)
        std = price(self.inst, views, {"a": [dict(id="s", bias=0.25), dict(id="g", bias=0.25, vanish_min=vm)]},
                    self.cfg.cost, px=px_s, jobs=1)
        self.assertGreater(orig.counts["a"][0]["records"], 0)
        self.assertEqual(std.counts["a"][0]["records"], 0)          # unguarded: gone at 10 m
        self.assertGreater(std.counts["a"][1]["records"], 0)        # guarded: drawn, as in Original
        self.assertGreater(std.quality["a"][0], std.quality["a"][1])

    def test_package_patch(self):
        from assetpipe.generators import Gen
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "X.re4mesh").write_bytes(self.blob)
            (d / "X.re4mesh.json").write_text(json.dumps({"sha256": "old"}))

            class Obj:
                info = {"package_bytes": len(self.blob)}

                def path(self, rel):
                    return d / rel

            class R:
                name = "t"
            g = Gen(self.cfg, Cache(d / "c", log=lambda *a: None))
            out = g.vanish_guard(R(), "X", Obj(), {(0, False): 1234.5})
            pk = r4im.Package(out.path("X.re4mesh").read_bytes())
            errs = [(e, bool(l)) for p in pk.mesh_parts(0) for cl in pk.part_levels(p) for e, l in cl["levels"]]
            before = [(e, bool(l)) for p in self.pk.mesh_parts(0) for cl in self.pk.part_levels(p)
                      for e, l in cl["levels"]]
            self.assertEqual([x for x in errs if x[1]], [x for x in before if x[1]])   # drawn levels untouched
            self.assertTrue(all(abs(e - 1234.5) < 0.01 for e, full in errs if not full))
            self.assertEqual(len(out.path("X.re4mesh").read_bytes()), len(self.blob))


class ImpostorTests(unittest.TestCase):
    def test_bake_frame_and_views(self):
        """A vertical 400 x 2000 textured quad in the x-y plane: cells 1:2, 16 views in one 1024 row;
        view 0 looks along -x (edge on), view 4 along +z (face on)."""
        from assetpipe import impostor
        img = texture.Image(8, 8, bytes([200, 150, 100, 255]) * 64)
        a, b, c, e = (-200.0, 0.0, 0.0), (200.0, 0.0, 0.0), (200.0, 2000.0, 0.0), (-200.0, 2000.0, 0.0)
        col = (128, 128, 128)
        tris = [(a, b, c, (0, 1), (1, 1), (1, 0), col, col, col, img, None),
                (a, c, e, (0, 1), (1, 0), (0, 0), col, col, col, img, None)]
        atlas, info = impostor.bake(tris, views=16, cell=64, ss=2)
        self.assertEqual(info["cell"], [32, 64])
        self.assertEqual(info["atlas"], [512, 64])
        self.assertAlmostEqual(info["centre"][1], 1000.0)

        def cover(k):
            x0 = k * 32
            return sum(1 for y in range(64) for x in range(x0, x0 + 32) if atlas.rgba[4 * (y * 512 + x) + 3])
        self.assertGreater(cover(4), 10 * max(1, cover(0)))
        o = 4 * (32 * 512 + 4 * 32 + 16)                     # centre of the face-on cell: texture colour only
        self.assertEqual(tuple(atlas.rgba[o:o + 3]), (200, 150, 100))


class VendorTests(unittest.TestCase):
    def test_vendored_files_unmodified(self):
        from assetpipe import util
        from assetpipe.vendor import FILES, HERE
        for name, (_, _, sha) in FILES.items():
            self.assertEqual(util.sha256_file(HERE / name), sha, name)


if __name__ == "__main__":
    unittest.main()
