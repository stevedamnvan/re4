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


class StandardDiscTests(unittest.TestCase):
    """s16: the Standard index (stdindex.py) and its staging (tools/d367/stage_std.py)."""

    def build(self, tmp):
        import struct
        from assetpipe import stdindex
        tmp = pathlib.Path(tmp)
        std_blob, _ = package(bump=200.0)
        orig_blob, _ = package(bump=100.0)
        pk_std, pk_orig = r4im.Package(std_blob), r4im.Package(orig_blob)
        (tmp / "std").mkdir()
        (tmp / "orig").mkdir()
        (tmp / "std" / "MAINSCENARIO.re4mesh").write_bytes(std_blob)
        (tmp / "orig" / "MAINSCENARIO.re4mesh").write_bytes(orig_blob)
        tex = tmp / "0000000a-0000000b.re4tex"
        tex.write_bytes(texture.HEADER.pack(b"RE4DCTX\0", 2, 48, 96, 1, 48, 144, 32, 0, 1, 0) +
                        texture.TEXTURE.pack(b"t", 128, 128, 0, 144, 32, 3, 2, 0) + bytes(32))
        (tmp / "plan.json").write_text("{}")
        m = pk_std.meshes[0]
        b, common = m[0], bool(m[1])
        bins = {"MAINSCENARIO/0xff:%d" % b: {"cull_mm": 6000.0, "imp_mm": 3000.0}}
        imp = {(0xff, b): dict(key=["0000000a", "0000000b"], views=16, cols=8, cell=[128, 128], atlas=[1024, 256],
                               centre=[1.0, -0.0004, 3.25], half_w=10.0, half_h=20.0, tex_file=str(tex))}
        shell = [dict(owner="0xff", bin=b, common=common, part=0, key=["0000000a", "0000000b"], width=128, height=128)]
        used = sorted(stdindex.used_textures(pk_orig))
        keys = ["%08x-%08x" % (i, i) for i in range(max(used) + 1)]
        out = tmp / "out"
        rep = stdindex.write_low(out, "r101", 5.0, [("MAINSCENARIO", 0xff, False)], {"MAINSCENARIO": pk_std},
                                 {"MAINSCENARIO": tmp / "std" / "MAINSCENARIO.re4mesh"},
                                 {"MAINSCENARIO": tmp / "orig" / "MAINSCENARIO.re4mesh"}, {"MAINSCENARIO": pk_orig},
                                 bins, imp, shell, [tex], keys, tmp / "plan.json")
        return out, rep, pk_std, b, keys, used

    def test_index_records(self):
        from assetpipe import stdindex
        with tempfile.TemporaryDirectory() as tmp:
            out, rep, pk, b, keys, used = self.build(tmp)
            ix = stdindex.parse((out / "low" / "index.txt").read_text())
            self.assertEqual(ix["room"], "r101")
            self.assertEqual(ix["lod_px"], 5.0)
            self.assertEqual([r[0] for r in ix["mesh"]], ["MAINSCENARIO"])
            self.assertEqual(ix["cull"], [["MAINSCENARIO", "0", str(b), "0", "6000"]])
            self.assertEqual(ix["imp"][0][:12], ["MAINSCENARIO", "0", str(b), "0", "3000", "0000000a-0000000b", "16",
                                                 "8", "128", "128", "1024", "256"])
            self.assertEqual(ix["imp"][0][12:], ["1.000", "0.000", "3.250", "10.000", "20.000"])
            self.assertEqual(ix["ptex"], [["MAINSCENARIO", str(pk.meshes[0][6]), str(b), "0", "0000000a-0000000b",
                                           "128", "128"]])
            self.assertEqual(ix["tex"], [["0000000a-0000000b", "128", "128", "32", "176"]])
            # the shelled part's source image is no longer drawn: dropped from the room preload
            if len(list(pk.mesh_parts(0))) == 1:
                self.assertEqual([d[0] for d in ix["drop"]], [keys[i] for i in used])
            self.assertEqual(sorted(p.name for p in (out / "low").iterdir()),
                             ["MAINSCENARIO.re4mesh", "index.txt", "plan.json"])
            self.assertEqual(rep["low"], ["MAINSCENARIO"])

    def test_identical_owner_not_in_low(self):
        from assetpipe import stdindex
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            blob, _ = package()
            (tmp / "a.re4mesh").write_bytes(blob)
            lines, low, _, _ = stdindex.build("r103", 5, [("MAINSCENARIO", 0xff, False)],
                                              {"MAINSCENARIO": r4im.Package(blob)}, {"MAINSCENARIO": tmp / "a.re4mesh"},
                                              {"MAINSCENARIO": tmp / "a.re4mesh"}, {}, {}, [], [], [])
            self.assertEqual(low, [])
            self.assertEqual([x.split()[0] for x in lines], ["re4dc-std", "lod_px", "orig"])

    def test_parse_rejects_truncation(self):
        from assetpipe import stdindex
        text = stdindex.finish(["re4dc-std 1 r100", "lod_px 5", "mesh COMMON 1 0"], ["00000001-00000002"])
        self.assertTrue(text.endswith("end 4\n"))
        self.assertEqual(stdindex.parse(text)["drop"], [["00000001-00000002"]])
        for bad in (text.replace("end 4", "end 3"), "\n".join(text.splitlines()[:-1]) + "\n",
                    text.replace("re4dc-std 1", "re4dc-std 2")):
            with self.assertRaises(ValueError):
                stdindex.parse(bad)

    def test_image_key_is_the_runtime_identity(self):
        import prepare_native_ui
        from assetpipe import stdindex

        class Im:
            width, height, format, palette_format = 8, 4, 9, 2
            data, palette_data = bytes(range(32)), bytes(range(32, 64))
        self.assertEqual(stdindex.image_key(Im), prepare_native_ui.image_identity(Im)[0])
        Im.palette_format, Im.palette_data = None, None
        self.assertEqual(stdindex.image_key(Im), prepare_native_ui.image_identity(Im)[0])

    def test_stage(self):
        sys.path.insert(0, str(ROOT / "tools" / "d367"))
        import stage_std
        with tempfile.TemporaryDirectory() as tmp:
            out, rep, pk, b, keys, used = self.build(tmp)
            fx = pathlib.Path(tmp) / "fixtures"
            (fx / "native" / "r101").mkdir(parents=True)
            orig = pathlib.Path(tmp) / "orig" / "MAINSCENARIO.re4mesh"
            (fx / "native" / "r101" / "MAINSCENARIO.re4mesh").write_bytes(orig.read_bytes())
            line = stage_std.stage_room(fx, "r101", out, tex_resident=True)
            self.assertIn("STDROOM r101", line)
            for rel in ("native/r101/low/index.txt", "native/r101/low/MAINSCENARIO.re4mesh",
                        "native/r101/low/plan.json", "texlow/0/0000000a-0000000b.re4tex"):
                self.assertTrue((fx / rel).is_file(), rel)
            self.assertEqual((fx / "native/r101/low/MAINSCENARIO.re4mesh").read_bytes(),
                             (out / "low" / "MAINSCENARIO.re4mesh").read_bytes())
            # a staged Original the set was not built against stops staging
            (fx / "native" / "r101" / "MAINSCENARIO.re4mesh").write_bytes(b"x" + orig.read_bytes()[1:])
            with self.assertRaises(SystemExit):
                stage_std.stage_room(fx, "r101", out, tex_resident=False)
            (fx / "native" / "r101" / "MAINSCENARIO.re4mesh").write_bytes(orig.read_bytes())
            # an unlisted file in low/, or a Standard key that is also an Original key
            (out / "low" / "FILE_00.re4mesh").write_bytes(b"?")
            with self.assertRaises(SystemExit):
                stage_std.stage_room(fx, "r101", out, tex_resident=False)
            (out / "low" / "FILE_00.re4mesh").unlink()
            (fx / "tex").mkdir()
            (fx / "tex" / "0000000a-0000000b.re4tex").write_bytes(b"")
            with self.assertRaises(SystemExit):
                stage_std.stage_room(fx, "r101", out, tex_resident=False)


class GroveSplitTests(unittest.TestCase):
    """s16.5: split groves priced per tree (camera.py) and written as impt records (stdindex.py)."""

    def setUp(self):
        self.trunk = LT.C.TREE_TRUNK_MM
        LT.C.TREE_TRUNK_MM = 3.0      # the synthetic trees are 5 units tall
        blob, self.summary = LT.convert([LT.grove_bin([0.0, 10.0, 20.0])], cluster_trees={(1, 0)})
        self.blob = blob
        self.pk = r4im.Package(blob)
        self.cfg = Config()
        self.w = dict(owner="X", code=1, bin=0, common=False, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0),
                      scale=(1000.0, 1000.0, 1000.0))
        # tree centres (model units) placed at increasing depth from the camera below
        self.table = {("X", 0, False): [dict(part=0, first=k, count=1, centre=(10.0 * k + 0.5, 2.5, 10.0 * k),
                                             radius=3.0) for k in range(3)]}

    def tearDown(self):
        LT.C.TREE_TRUNK_MM = self.trunk

    def test_converter_rows(self):
        rows = self.summary["meshes_detail"][0]["parts"][0]["trees"]
        self.assertEqual([(r["first"], r["clusters"]) for r in rows], [(0, 1), (1, 1), (2, 1)])

    def test_per_tree_pricing(self):
        inst = build_instances({"X": self.pk}, [self.w], lambda w: "g", trees=self.table)
        view = [dict(eye=(10000.0, 1600.0, -15000.0), yaw=0.0, pitch=0.0)]
        opts = {"g": [dict(id="mesh", bias=1.0), dict(id="t20", bias=1.0, imp_mm=20000.0, split=True, views=8)]}
        pr = price(inst, view, opts, self.cfg.cost, far=100000.0, jobs=1)
        c = pr.counts["g"]
        self.assertEqual(c[0]["imps"], 0)
        self.assertEqual(c[1]["imps"], 2)                 # the two trees beyond 20 m are quads
        self.assertLess(c[1]["meshlets"], c[0]["meshlets"])
        self.assertGreater(c[0]["meshlets"], 0)
        self.assertEqual(c[0].get("extra_clusters"), 2)  # 3 clusters drawn in one part: 2 extra, priced
        self.assertNotIn("extra_clusters", c[1])
        self.assertGreater(pr.quality["g"][1], 0.0)
        # the same package without the tree table: no per-tree decisions, no extra-cluster charge
        plain = build_instances({"X": self.pk}, [self.w], lambda w: "g")
        pr0 = price(plain, view, {"g": [dict(id="mesh", bias=1.0)]}, self.cfg.cost, far=100000.0, jobs=1)
        self.assertNotIn("extra_clusters", pr0.counts["g"][0])
        self.assertLess(pr0.ms["g"][0][0], pr.ms["g"][0][0])

    def test_impt_records(self):
        from assetpipe import stdindex
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "std.re4mesh").write_bytes(self.blob)
            orig, _ = LT.convert([LT.grove_bin([0.0, 10.0, 20.0])])
            (tmp / "orig.re4mesh").write_bytes(orig)
            recs = []
            for k in range(3):
                f = tmp / ("0000000%d-0000000%d.re4tex" % (k, k))
                f.write_bytes(texture.HEADER.pack(b"RE4DCTX\0", 2, 48, 96, 1, 48, 144, 32, 0, 1, 0) +
                              texture.TEXTURE.pack(b"t", 512, 128, 3, 144, 32, 3, 2, 0) + bytes(32))
                recs.append(dict(common=False, part=0, first=k, count=1, tex_file=str(f),
                                 key=["0000000%d" % k, "0000000%d" % k], views=8, cols=8, cell=[64, 128],
                                 atlas=[512, 128], centre=[10.0 * k, 2.5, 0.0], half_w=1.5, half_h=3.0))
            lines, low, texlow, _ = stdindex.build(
                "r101", 5, [("MAINSCENARIO", 0xff, False)], {"MAINSCENARIO": self.pk},
                {"MAINSCENARIO": tmp / "std.re4mesh"}, {"MAINSCENARIO": tmp / "orig.re4mesh"},
                {"MAINSCENARIO/0xff:0": {"imp_mm": 20000.0, "split": True}}, {}, [], [r["tex_file"] for r in recs],
                [], tree_recs={(0xff, 0): recs})
            impt = [x.split() for x in lines if x.startswith("impt ")]
            self.assertEqual([r[5:9] for r in impt], [["0", "0", "1", "20000"], ["0", "1", "1", "20000"],
                                                     ["0", "2", "1", "20000"]])
            self.assertEqual(impt[1][9:16], ["00000001-00000001", "8", "8", "64", "128", "512", "128"])
            self.assertEqual(impt[1][16:], ["10.000", "2.500", "0.000", "1.500", "3.000"])
            self.assertFalse([x for x in lines if x.startswith("imp ")])
            text = stdindex.finish(lines, [])
            self.assertEqual(len(stdindex.parse(text)["impt"]), 3)


if __name__ == "__main__":
    unittest.main()
