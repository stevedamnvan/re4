"""Synthetic contracts for whole-BIN render replacement (convert_room_bins.py
--lod-substitute DIR / manifest "replace", tools/export_room_bins_obj.py):
the replacement's triangles fill the source parts, levels are generated from
them, empty levels are dropped for replaced BINs only, and every source
identity the runtime checks stays the source's."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('room_bins_lod_tests', HERE / 'test_room_bins_lod.py')
LT = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = LT
spec.loader.exec_module(LT)
T, C = LT.T, LT.C
import export_room_bins_obj as X  # noqa: E402  (tools/ is on sys.path via test_room_bins_lod)

OWNER = 1  # LT.convert() entries use owner 1 -> replacement name FILE_01_<bin>


def grid_obj(path, n, size, y=0.0, material='p0_grid', normals=True, flip=False):
    """n x n vertex grid over [0, size]^2 in xz, faces +y (source winding), planar UV x/4, z/4."""
    lines = []
    for j in range(n):
        for i in range(n):
            x, z = i * size / (n - 1), j * size / (n - 1)
            lines.append('v %.6f %.6f %.6f' % (x, y, z))
            lines.append('vt %.6f %.6f' % (x / 4, z / 4))
    if normals:
        lines.append('vn 0 1 0')
    lines.append('usemtl ' + material)
    for j in range(n - 1):
        for i in range(n - 1):
            a, b, d, e = j * n + i + 1, j * n + i + 2, (j + 1) * n + i + 1, (j + 1) * n + i + 2
            for t in ((a, d, b), (b, d, e)):
                t = t[::-1] if flip else t
                lines.append('f ' + ' '.join(('%d/%d/1' if normals else '%d/%d') % (k, k) for k in t))
    pathlib.Path(path).write_text('\n'.join(lines) + '\n')


def levels_of(blob):
    """-> decoded package, [[level triangles per level] per cluster] of part 0."""
    d = LT.decode(blob)
    first, count = d['part_lods'][0]
    out = []
    for cl in d['clusters'][first:first + count]:
        out.append([LT.level_triangles(blob, d, lv) for lv in d['levels'][cl[6]:cl[6] + cl[7]]])
    return d, out


class RoomBinsReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_unedited_export_reproduces_the_source(self):
        data = LT.grid_bin(12)
        src_bin = self.dir / '0000.BIN'
        src_bin.write_bytes(data)
        rep = self.dir / 'rep'
        rep.mkdir()
        tris = X.export_bin(src_bin, rep / 'FILE_01_0.obj')
        self.assertEqual(tris, 2 * 11 * 11)
        kw = dict(eps_world=(0.05, 0.5, 2.0), cluster_world=1000.0)
        plain, _ = LT.convert([data], **kw)
        replaced, summary = LT.convert([data], replacements=C.load_replacements(rep), **kw)
        self.assertEqual(summary['replaced_bins'], 1)
        d, per = levels_of(replaced)
        got = Counter(C.canonical(tuple(zip(*t))) for cl in per for t in cl[0])
        self.assertEqual(got, T.expected(data, replaced)[d['parts'][0][0]])
        # Same source part identity, same levels as the source path.
        self.assertEqual([p[:6] for p in d['parts']], [p[:6] for p in LT.decode(plain)['parts']])
        self.assertEqual([len(l) for l in levels_of(plain)[1][0]], [len(l) for l in per[0]])

    def test_replacement_triangles_get_generated_levels_and_source_identity(self):
        data = LT.grid_bin(4)                     # source: 18 triangles over [0, 3]^2
        grid_obj(self.dir / 'FILE_01_0.obj', 21, 3.0)   # replacement: 800 triangles, same square
        blob, _ = LT.convert([data], eps_world=(0.05, 0.5, 2.0), cluster_world=1000.0,
                             replacements=C.load_replacements(self.dir))
        d, per = levels_of(blob)
        self.assertEqual(self.read_ok(blob), True)
        self.assertEqual(len(per), 1)
        self.assertEqual(len(per[0][0]), 2 * 20 * 20)
        self.assertGreater(len(per[0]), 1)                # QEM levels built from the replacement
        self.assertLess(len(per[0][-1]), len(per[0][0]) // 8)
        step = d['meshes'][0][11:14]
        area = sum(LT.area_y(t[0], step) for t in per[0][0])
        self.assertAlmostEqual(area, 9.0, delta=1e-3)
        for level in per[0][1:]:
            self.assertTrue(all(LT.area_y(t[0], step) > 0 for t in level))
            self.assertAlmostEqual(sum(LT.area_y(t[0], step) for t in level), area, delta=area * 1e-3)
        src = C.parse_bin(data)
        part = d['parts'][0]
        self.assertEqual((part[0], part[1], part[2], part[3], part[4]),
                         tuple(src['parts'][0][k] for k in ('offset', 'size', 'texture', 'alpha', 'flags')))
        mesh = d['meshes'][0]
        self.assertEqual((mesh[0], mesh[2], mesh[3], mesh[4]), (0, OWNER, src['nvtx'], src['nparts']))
        # Colour slot: the source part's CLR0 palette entry over the vn normal (+y).
        self.assertEqual({v[5] for v in d['verts']}, {C.oct12((0.0, 1.0, 0.0))})

    def test_face_normals_when_the_replacement_has_none(self):
        data = LT.grid_bin(4)
        grid_obj(self.dir / 'FILE_01_0.obj', 3, 3.0, normals=False, flip=True)   # faces -y
        blob, _ = LT.convert([data], eps_world=(0.05,), cluster_world=1000.0,
                             replacements=C.load_replacements(self.dir))
        d = LT.decode(blob)
        self.assertEqual({v[5] for v in d['verts']}, {C.oct12((0.0, -1.0, 0.0))})

    def test_empty_levels_dropped_for_replaced_bins_only(self):
        data = LT.grid_bin(2)                     # one quad: collapses to nothing at a large error
        kw = dict(eps_world=(0.01, 100.0), cluster_world=1000.0, min_gain=0.9)
        plain, _ = LT.convert([data], **kw)
        levels = levels_of(plain)[1][0]
        self.assertEqual([len(l) for l in levels][-1], 0)   # source BINs keep their empty level
        rep = self.dir / 'rep'
        rep.mkdir()
        X.export_bin(self.write_bin(data), rep / 'FILE_01_0.obj')
        replaced, _ = LT.convert([data], replacements=C.load_replacements(rep), **kw)
        levels = levels_of(replaced)[1][0]
        self.assertTrue(levels and all(levels))
        self.assertEqual(self.read_ok(replaced), True)

    def test_part_without_faces_draws_nothing_but_keeps_its_identity(self):
        data = T.fixture()                        # two parts (textures 3 and 7)
        rep = self.dir / 'rep'
        rep.mkdir()
        grid_obj(rep / 'FILE_01_0.obj', 3, 1.0, material='p1_only')
        blob, _ = LT.convert([data], eps_world=(0.05,), cluster_world=1000.0, replacements=C.load_replacements(rep))
        d = LT.decode(blob)
        src = C.parse_bin(data)
        self.assertEqual([(p[0], p[1], p[2]) for p in d['parts']],
                         [(p['offset'], p['size'], p['texture']) for p in src['parts']])
        self.assertEqual(d['parts'][0][7], 0)     # no meshlets
        self.assertGreater(d['parts'][1][7], 0)
        self.assertEqual(self.read_ok(blob), True)

    def test_rejects_unassigned_faces_missing_bins_and_double_sources(self):
        data = LT.grid_bin(4)
        grid_obj(self.dir / 'FILE_01_0.obj', 3, 1.0, material='bark')
        with self.assertRaisesRegex(ValueError, 'names no source part'):
            LT.convert([data], replacements=C.load_replacements(self.dir))
        grid_obj(self.dir / 'FILE_01_0.obj', 3, 1.0, material='p5_bark')
        with self.assertRaisesRegex(ValueError, 'names no source part'):
            LT.convert([data], replacements=C.load_replacements(self.dir))
        grid_obj(self.dir / 'FILE_01_0.obj', 3, 1.0)
        with self.assertRaisesRegex(ValueError, 'missing BINs'):
            LT.convert([data], replacements={(OWNER, 9): self.dir / 'FILE_01_0.obj'})
        # Another owner's replacement is not this package's business.
        LT.convert([data], replacements={(0xFE, 9): self.dir / 'FILE_01_0.obj'})
        subs = {(OWNER, 0, 0): dict(offset=None, levels=[(3.0, C.read_obj(self.dir / 'FILE_01_0.obj'))])}
        with self.assertRaisesRegex(ValueError, 'both replaced'):
            LT.convert([data], replacements=C.load_replacements(self.dir), substitutes=subs)
        (self.dir / 'tree.obj').write_text('v 0 0 0\n')
        with self.assertRaisesRegex(ValueError, 'OWNER'):
            C.load_replacements(self.dir)

    def test_replacement_names_and_manifest_form(self):
        for name in ('COMMON_3', 'MAINSCENARIO_10', 'FILE_01_17', 'FILE_4_2'):
            (self.dir / (name + '.obj')).write_text('v 0 0 0\n')
        got = C.load_replacements(self.dir)
        self.assertEqual(sorted(got), sorted([(0xFE, 3), (0xFF, 10), (1, 17), (4, 2)]))
        self.assertEqual(C.load_substitutes(self.dir), {})
        (self.dir / 'm.json').write_text(json.dumps({'replace': [{'owner': '0xfe', 'bin': 3, 'obj': 'COMMON_3.obj'}]}))
        self.assertEqual(C.load_replacements(self.dir / 'm.json'), {(0xFE, 3): self.dir / 'COMMON_3.obj'})
        self.assertEqual(C.load_substitutes(self.dir / 'm.json'), {})
        self.assertEqual(C.owner_name(0xFE), 'COMMON')
        self.assertEqual(C.owner_name(1), 'FILE_01')

    def test_cli_directory_replacement_matches_the_library(self):
        data = LT.grid_bin(6)
        bins = self.dir / 'bins'
        bins.mkdir()
        (bins / '0000.BIN').write_bytes(data)
        rep = self.dir / 'rep'
        rep.mkdir()
        grid_obj(rep / 'FILE_01_0.obj', 9, 5.0)
        out = self.dir / 'x.re4mesh'
        subprocess.run([sys.executable, str(ROOT / 'tools/convert_room_bins.py'), str(out), '--owner', '1',
                        '--bins', str(bins), '--lod', '--lod-eps', '0.05,0.5', '--lod-cluster', '1000',
                        '--lod-substitute', str(rep)], check=True, capture_output=True)
        want, _ = C.convert_lod([(1, False, 0, bins / '0000.BIN')], 1.0, eps_world=(0.05, 0.5),
                                cluster_world=1000.0, replacements=C.load_replacements(rep))
        self.assertEqual(out.read_bytes(), want)
        side = json.loads(pathlib.Path(str(out) + '.json').read_text())
        self.assertEqual((side['replaced_bins'], side['lod_substitute']), (1, [str(rep)]))

    def test_read_obj_is_unchanged_by_the_indexed_parser(self):
        p = self.dir / 'q.obj'
        p.write_text('# c\nv 0 0 0\nv 1 0 0\nv 1 0 1\nv 0 0 1\nvt 0 0\nvt 1 1\nvn 0 1 0\n'
                     'g a\nusemtl p0_x\nf 1/1/1 2/2/1 3/1/1 -1/2/-1\no b\nf 1 2 3\n')
        faces = C.read_obj(p)
        self.assertEqual(len(faces), 3)
        self.assertEqual(faces[1][2], ((0.0, 0.0, 1.0), (1.0, 1.0), (0.0, 1.0, 0.0)))
        self.assertEqual(faces[2][0], ((0.0, 0.0, 0.0), None, None))
        obj = C.parse_obj(p)
        self.assertEqual((obj['groups'], obj['face_groups']), (['a', 'b'], [0, 0, 1]))
        self.assertEqual([f[0] for f in obj['faces']], ['p0_x', 'p0_x', 'p0_x'])

    # helpers
    def write_bin(self, data):
        p = self.dir / '0000.BIN'
        p.write_bytes(data)
        return p

    def read_ok(self, blob):
        """The native reader (built by the LOD tests) adopts the package as v2."""
        if not hasattr(LT.RoomBinsLodTests, 'exe'):
            LT.RoomBinsLodTests.setUpClass()
            self.addClassCleanup(LT.RoomBinsLodTests.tearDownClass)
        reader = LT.RoomBinsLodTests.__new__(LT.RoomBinsLodTests)
        return reader.read(blob, 'lod').startswith('ok v2')


if __name__ == '__main__':
    unittest.main()
