"""Synthetic R4IM v2 contracts: levels of detail (convert_room_bins.py --lod,
tools/mesh_lod.py) checked against the source triangles and the native reader."""
import importlib.util
import json
import math
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('room_bins_v1_tests', pathlib.Path(__file__).with_name('test_room_bins.py'))
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)
C = T.C
import mesh_lod as L  # noqa: E402


def grid_bin(n, spacing=1.0, bump=0.0, uv_scale=0.25):
    """n x n vertex grid in xz (y up, optional central bump), loose triangles
    wound so their normals face +y, planar UV = (x, z) * uv_scale."""
    positions, uvs = [], []
    c = (n - 1) * spacing / 2
    for j in range(n):
        for i in range(n):
            x, z = i * spacing, j * spacing
            r2 = ((x - c) ** 2 + (z - c) ** 2) / max(c * c, 1e-9)
            positions.append((x, bump * max(0.0, 1.0 - r2), z))
            uvs.append((x * uv_scale, z * uv_scale))
    corners = []
    for j in range(n - 1):
        for i in range(n - 1):
            a, b, d, e = j * n + i, j * n + i + 1, (j + 1) * n + i, (j + 1) * n + i + 1
            for t in ((a, d, b), (b, d, e)):
                corners += [(k, 0, 0, k) for k in t]
    return T.synth_bin([(1, [(0x90, corners)])], positions, [(0, 1, 0)], [(255, 255, 255, 255)], uvs, shift=5)


def convert(bins, **kw):
    with tempfile.TemporaryDirectory() as d:
        entries = []
        for n, data in enumerate(bins):
            p = pathlib.Path(d) / f'{n:04d}.BIN'
            p.write_bytes(data)
            entries.append((1, False, n, p))
        return C.convert_lod(entries, 1.0, **kw)


def decode(blob):
    h, meshes, parts, lets, verts, os_ = T.decode(blob)
    ncl, nlv, opl, ocl, olv = C.LOD_HEADER.unpack_from(blob, C.HEADER.size)[:5]
    part_lods = [C.PART_LOD.unpack_from(blob, opl + i * C.PART_LOD.size) for i in range(len(parts))]
    clusters = [C.CLUSTER.unpack_from(blob, ocl + i * C.CLUSTER.size) for i in range(ncl)]
    levels = [C.LEVEL.unpack_from(blob, olv + i * C.LEVEL.size) for i in range(nlv)]
    return dict(h=h, meshes=meshes, parts=parts, lets=lets, verts=verts, os=os_, part_lods=part_lods,
                clusters=clusters, levels=levels, lod_offsets=(opl, ocl, olv))


def level_triangles(blob, d, level):
    """Oriented triangles of one level: [((grid xyz) * 3, (quantised uv) * 3)]."""
    out = []
    first, count, _ = level
    for fv, fs, sb, vc, sc, *_ in d['lets'][first:first + count]:
        data = blob[d['os'] + fs:d['os'] + fs + sb]
        i = 0
        while i < len(data):
            n = data[i]
            strip = list(data[i + 1:i + 1 + n])
            i += 1 + n
            for t in C.strip_triangles(strip):
                if len(set(t)) == 3:
                    vs = [d['verts'][fv + k] for k in t]
                    out.append((tuple(v[0:3] for v in vs), tuple(v[3:5] for v in vs)))
    return out


def area_y(tri, step):
    """Signed area of the xz projection (positive = normal +y, source winding)."""
    (a, b, c) = [(p[0] * step[0], p[2] * step[2]) for p in tri]
    return 0.5 * ((c[0] - a[0]) * (b[1] - a[1]) - (b[0] - a[0]) * (c[1] - a[1]))


class RoomBinsLodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.temp.name)
        (cls.root / 'kos').mkdir()
        (cls.root / 'kos/fs.h').write_text('#pragma once\n#include <sys/types.h>\nusing file_t=int;\n'
                                           '#define FILEHND_INVALID (-1)\n')
        (cls.root / 'read.cpp').write_text(r'''
#include "instanced_mesh.hpp"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>
int main(int,char** argv){
    std::ifstream in(argv[1],std::ios::binary);
    std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)),{});
    std::vector<std::uint32_t> words((raw.size()+3)/4);std::memcpy(words.data(),raw.data(),raw.size());
    re4dc::room::MeshPackage p;
    if(!p.adopt(reinterpret_cast<const std::uint8_t*>(words.data()),std::uint32_t(raw.size()),std::strcmp(argv[2],"lod")==0)){
        std::printf("reject %s\n",p.error());return 1;}
    unsigned levels=0;
    if(p.lod())for(unsigned c=0;c<p.header().part_count;++c)
        for(unsigned k=0;k<p.part_lods()[c].cluster_count;++k)levels+=p.clusters()[p.part_lods()[c].first_cluster+k].level_count;
    std::printf("ok v%u levels=%u\n",p.header().version,levels);
    return 0;
}
''')
        cls.exe = cls.root / 'read'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(cls.root),
                        '-I', str(ROOT / 'room'), str(cls.root / 'read.cpp'), '-o', str(cls.exe)], check=True)
        cls.flat_data = grid_bin(12)
        cls.flat, cls.flat_summary = convert([cls.flat_data], eps_world=(0.05, 0.5, 2.0), cluster_world=1000.0)
        cls.hill_data = grid_bin(40, bump=3.0)
        cls.hill, _ = convert([cls.hill_data], eps_world=(0.02, 0.1, 0.5, 2.0), cluster_world=12.0,
                              cluster_tris_max=400, min_gain=0.7)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, blob, mode):
        p = self.root / 'x.re4mesh'
        p.write_bytes(blob)
        return subprocess.run([str(self.exe), str(p), mode], text=True, capture_output=True).stdout.strip()

    def test_v2_is_only_adopted_by_a_lod_reader(self):
        d = decode(self.flat)
        self.assertEqual(d['h'][1], C.VERSION_LOD)
        self.assertEqual(self.read(self.flat, 'lod'), 'ok v2 levels=%d' % len(d['levels']))
        self.assertEqual(self.read(self.flat, 'v1'), 'reject header')
        v1 = T.package([self.flat_data])
        self.assertEqual(self.read(v1, 'lod'), 'ok v1 levels=0')
        self.assertEqual(self.read(v1, 'v1'), 'ok v1 levels=0')

    def test_level_zero_is_the_source_and_levels_stay_in_the_part(self):
        for blob, data in ((self.flat, self.flat_data), (self.hill, self.hill_data)):
            d = decode(blob)
            want = T.expected(data, blob)
            for pi, part in enumerate(d['parts']):
                first, count = d['part_lods'][pi]
                got = Counter()
                for cl in d['clusters'][first:first + count]:
                    lv = d['levels'][cl[6]:cl[6] + cl[7]]
                    self.assertEqual(lv[0][2], 0.0)
                    self.assertEqual([l[2] for l in lv], sorted(l[2] for l in lv))
                    for f, n, _ in lv:
                        self.assertTrue(part[6] <= f and f + n <= part[6] + part[7])
                    for tri in level_triangles(blob, d, lv[0]):
                        got[C.canonical(tuple(zip(*tri)))] += 1
                    # Cluster bounds cover every level.
                    for level in lv:
                        for tri in level_triangles(blob, d, level):
                            for p in tri[0]:
                                self.assertTrue(all(cl[a] <= p[a] <= cl[3 + a] for a in range(3)))
                self.assertEqual(got, want[part[0]])

    def test_coarse_levels_keep_source_vertices_winding_and_coverage(self):
        d = decode(self.flat)
        step = d['meshes'][0][11:14]
        src = {p for tri in level_triangles(self.flat, d, d['levels'][0]) for p in tri[0]}
        base = level_triangles(self.flat, d, d['levels'][0])
        total = sum(area_y(t[0], step) for t in base)
        self.assertGreater(len(d['levels']), 1)
        last = level_triangles(self.flat, d, d['levels'][-1])
        self.assertLessEqual(len(last), len(base) // 8)
        for level in d['levels'][1:]:
            tris = level_triangles(self.flat, d, level)
            self.assertTrue({p for t in tris for p in t[0]} <= src)       # half-edge collapses only
            self.assertTrue(all(area_y(t[0], step) > 0 for t in tris))    # no flipped triangle
            self.assertAlmostEqual(sum(area_y(t[0], step) for t in tris), total, delta=total * 1e-3)
            # Planar UV (x, z) / 4 survives collapse (quantisation tolerance).
            ub, us = d['parts'][0][8:10], d['parts'][0][10:12]
            for pos, uv in tris:
                for p, q in zip(pos, uv):
                    self.assertAlmostEqual(ub[0] + q[0] * us[0], p[0] * step[0] * 0.25, delta=1e-3)
                    self.assertAlmostEqual(ub[1] + q[1] * us[1], p[2] * step[2] * 0.25, delta=1e-3)

    def test_clusters_lock_shared_borders_so_levels_mix_without_cracks(self):
        d = decode(self.hill)
        step = d['meshes'][0][11:14]
        first, count = d['part_lods'][0]
        self.assertGreater(count, 2)
        per = []
        for cl in d['clusters'][first:first + count]:
            lv = d['levels'][cl[6]:cl[6] + cl[7]]
            per.append([level_triangles(self.hill, d, l) for l in lv])
        self.assertTrue(any(len(p) > 1 for p in per))
        # Every mix of per-cluster levels (finest everywhere, coarsest
        # everywhere, alternating) covers the same xz area with no flips, and
        # every vertex on a border between clusters is kept by every level.
        base_area = sum(area_y(t[0], step) for p in per for t in p[0])
        for pick in (lambda n, k: 0, lambda n, k: k - 1, lambda n, k: (k - 1) * (n & 1)):
            tris = [t for n, p in enumerate(per) for t in p[pick(n, len(p))]]
            # Border-locked collapses may leave zero-area (edge-on) slivers
            # between a coarse chord and the kept border vertices: the seam.
            self.assertTrue(all(area_y(t[0], step) >= 0 for t in tris))
            self.assertAlmostEqual(sum(area_y(t[0], step) for t in tris), base_area, delta=base_area * 1e-3)
        owners = {}
        for n, p in enumerate(per):
            for t in p[0]:
                for v in t[0]:
                    owners.setdefault(v, set()).add(n)
        shared = {v for v, s in owners.items() if len(s) > 1}
        self.assertTrue(shared)
        for n, p in enumerate(per):
            mine = {v for t in p[0] for v in t[0]} & shared
            for level in p[1:]:
                self.assertTrue(mine <= {v for t in level for v in t[0]})

    def test_reader_rejects_bad_lod_tables(self):
        d = decode(self.flat)
        opl, ocl, olv = d['lod_offsets']

        def bad(offset, fmt, value):
            b = bytearray(self.flat)
            struct.pack_into(fmt, b, offset, value)
            return self.read(bytes(b), 'lod')
        self.assertEqual(bad(olv + C.LEVEL.size + 8, '<f', -1.0), 'reject level error')
        self.assertEqual(bad(olv + C.LEVEL.size + 8, '<f', float('nan')), 'reject level error')
        self.assertEqual(bad(olv, '<I', len(d['lets']) + 1), 'reject level meshlets')
        self.assertEqual(bad(olv + 4, '<I', len(d['lets']) + 1), 'reject level meshlets')
        self.assertEqual(bad(ocl + 12, '<I', len(d['levels']) + 1), 'reject cluster levels')
        self.assertEqual(bad(ocl + 16, '<I', 0), 'reject cluster levels')
        self.assertEqual(bad(opl + 4, '<I', len(d['clusters']) + 1), 'reject part clusters')
        self.assertEqual(bad(C.HEADER.size + 16, '<I', len(self.flat)), 'reject lod section')
        self.assertEqual(bad(C.HEADER.size + 8, '<I', 4), 'reject lod section')

    def test_stripify_preserves_every_triangle_and_its_winding(self):
        n = 9
        tris = []
        for j in range(n - 1):
            for i in range(n - 1):
                a, b, c, e = j * n + i, j * n + i + 1, (j + 1) * n + i, (j + 1) * n + i + 1
                for t in ((a, c, b), (b, c, e)):
                    if (i * 7 + j * 3 + t[2]) % 11:  # holes, so strips must restart
                        tris.append(t)
        tris.append((100, 101, 102))  # isolated triangle
        strips = L.stripify(tris)
        got = Counter(C.canonical(t) for s in strips for t in C.strip_triangles(s) if len(set(t)) == 3)
        self.assertEqual(got, Counter(C.canonical(t) for t in tris))
        self.assertLess(sum(len(s) for s in strips), 2.0 * len(tris))

    def test_card_fields_thin_as_nested_even_subsets(self):
        positions, tris = {}, []
        for j in range(16):
            for i in range(16):
                b = len(positions)
                for k, (dx, dz) in enumerate(((0, 0), (0.3, 0), (0, 0.3), (0.3, 0.3))):
                    positions[b + k] = (i + dx, 0.0, j + dz)
                uv = ((0, 0), (1, 0), (0, 1))
                tris.append(((b, b + 2, b + 1), uv))
                tris.append(((b + 1, b + 2, b + 3), uv))
        self.assertTrue(L.is_card_field(tris, True))
        self.assertFalse(L.is_card_field(tris, False))
        full, half, quarter = L.card_levels(tris, positions, (1.0, 0.5, 0.25))
        self.assertEqual(len(full), len(tris))
        self.assertEqual(len(half), len(tris) // 2)
        self.assertEqual(len(quarter), len(tris) // 4)
        self.assertTrue(set(quarter) <= set(half) <= set(full))
        for qx in range(4):          # every 4x4 block of cards keeps some
            for qz in range(4):
                kept = {t[0][0] for t in quarter
                        if 4 * qx <= positions[t[0][0]][0] < 4 * qx + 4 and 4 * qz <= positions[t[0][0]][2] < 4 * qz + 4}
                self.assertGreaterEqual(len(kept), 2)

    def test_bias_scales_stored_errors_only(self):
        biased, _ = convert([self.flat_data], eps_world=(0.05, 0.5, 2.0), cluster_world=1000.0, bias={(1, 0): 0.375})
        a, b = decode(self.flat), decode(biased)
        self.assertEqual([l[:2] for l in a['levels']], [l[:2] for l in b['levels']])
        for la, lb in zip(a['levels'], b['levels']):
            self.assertAlmostEqual(lb[2], la[2] * 0.375, delta=1e-6 * max(1.0, la[2]))
        self.assertEqual(self.flat[C.HEADER.size + C.LOD_HEADER.size:][:64], biased[C.HEADER.size + C.LOD_HEADER.size:][:64])

    def test_substitution_hook_takes_exported_and_external_levels(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            convert([self.flat_data], eps_world=(0.05,), cluster_world=1000.0, export_dir=d)
            exported = json.loads((d / 'parts.json').read_text())['parts']
            l0 = next(p for p in exported if p['level'] == 0)
            self.assertEqual((l0['owner'], l0['bin'], l0['part'], l0['triangles']), ('0x1', 0, 0, 2 * 11 * 11))
            # An external coarse level: the same square as two triangles, source winding and planar UV.
            (d / 'coarse.obj').write_text('v 0 0 0\nv 11 0 0\nv 0 0 11\nv 11 0 11\n'
                                          'vt 0 0\nvt 2.75 0\nvt 0 2.75\nvt 2.75 2.75\n'
                                          'f 1/1 3/3 2/2\nf 2/2 3/3 4/4\n')
            (d / 'm.json').write_text(json.dumps({'parts': [{'owner': '0x01', 'bin': 0, 'part': 0, 'offset': l0['offset'],
                                                             'levels': [{'error': 0, 'obj': l0['obj']},
                                                                        {'error': 3.0, 'obj': 'coarse.obj'}]}]}))
            subs = C.load_substitutes(d / 'm.json')
            blob, summary = convert([self.flat_data], cluster_world=1000.0, substitutes=subs)
            bad = json.loads((d / 'm.json').read_text())
            bad['parts'][0]['offset'] = l0['offset'] + 32
            (d / 'bad.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                convert([self.flat_data], substitutes=C.load_substitutes(d / 'bad.json'))
        self.assertEqual(summary['substituted_parts'], 1)
        self.assertEqual(self.read(blob, 'lod'), 'ok v2 levels=2')
        d = decode(blob)
        self.assertEqual(len(d['clusters']), 1)
        self.assertEqual([l[2] for l in d['levels']], [0.0, 3.0])
        base = level_triangles(blob, d, d['levels'][0])
        got = Counter(C.canonical(tuple(zip(*t))) for t in base)
        self.assertEqual(got, T.expected(self.flat_data, blob)[d['parts'][0][0]])   # exported level 0 == source
        coarse = level_triangles(blob, d, d['levels'][1])
        step = d['meshes'][0][11:14]
        self.assertEqual(len(coarse), 2)
        self.assertTrue(all(area_y(t[0], step) > 0 for t in coarse))
        self.assertAlmostEqual(sum(area_y(t[0], step) for t in coarse), sum(area_y(t[0], step) for t in base), places=3)
        self.assertEqual({v[5] >> 12 for v in d['verts']}, {0})                         # source palette colour

    def test_meshlets_hold_256_vertices_and_levels_shrink(self):
        d = decode(self.hill)
        self.assertTrue(all(l[3] <= 256 for l in d['lets']))
        first, count = d['part_lods'][0]
        for cl in d['clusters'][first:first + count]:
            lv = d['levels'][cl[6]:cl[6] + cl[7]]
            sizes = [len(level_triangles(self.hill, d, l)) for l in lv]
            self.assertEqual(sizes, sorted(sizes, reverse=True))


def grove_bin(xs):
    """A grove: per x in xs one tree = a 5-unit tall trunk quad plus a separate leaf quad
    beside it (two components, not sharing vertices)."""
    positions, corners = [], []

    def quad(a, b, c, d):
        k = len(positions)
        positions.extend((a, b, c, d))
        for t in ((k, k + 1, k + 2), (k, k + 2, k + 3)):
            corners.extend((i, 0, 0, i) for i in t)
    for x in xs:
        quad((x, 0.0, 0.0), (x, 5.0, 0.0), (x + 0.25, 5.0, 0.0), (x + 0.25, 0.0, 0.0))
        quad((x + 0.5, 3.0, 0.5), (x + 0.5, 4.0, 0.5), (x + 1.5, 4.0, 0.5), (x + 1.5, 3.0, 0.5))
    uvs = [(p[0] * 0.1, p[1] * 0.1) for p in positions]
    return T.synth_bin([(1, [(0x90, corners)])], positions, [(0, 0, 1)], [(255, 255, 255, 255)], uvs, shift=5)


class GroveClusterTests(unittest.TestCase):
    """--lod-cluster-trees: per-tree clusters for grove BINs, and no change anywhere else."""

    def setUp(self):
        self.trunk = C.TREE_TRUNK_MM
        C.TREE_TRUNK_MM = 3.0      # the synthetic trees are 5 units tall

    def tearDown(self):
        C.TREE_TRUNK_MM = self.trunk

    def test_trees_get_their_own_contiguous_clusters(self):
        data = grove_bin([0.0, 10.0, 20.0])
        blob, summary = convert([data], cluster_trees={(1, 0)})
        rows = summary['meshes_detail'][0]['parts'][0]['trees']
        self.assertEqual([r['triangles'] for r in rows], [4, 4, 4])
        self.assertEqual([r['first'] for r in rows], [0, 1, 2])
        self.assertEqual(summary['grove_parts'], 1)
        d = decode(blob)
        first, count = d['part_lods'][0]
        self.assertEqual(count, sum(r['clusters'] for r in rows))
        step, lo = d['meshes'][0][11], d['meshes'][0][8]
        spans = []
        for c in d['clusters'][first:first + count]:
            spans.append((lo + c[0] * step, lo + c[3] * step))
        for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
            self.assertLess(a1, b0)   # no cluster reaches into the next tree
        # unsplit, the same BIN is one cluster
        plain, s0 = convert([data])
        self.assertEqual(decode(plain)['part_lods'][0][1], 1)
        self.assertNotIn('trees', s0['meshes_detail'][0]['parts'][0])
        self.assertNotIn('grove_parts', s0)

    def test_off_and_single_trees_are_byte_identical(self):
        grove, single = grove_bin([0.0, 10.0]), grove_bin([0.0])
        flat = grid_bin(9, spacing=1.0, bump=0.5)
        base, s0 = convert([grove, single, flat])
        other, s1 = convert([grove, single, flat], cluster_trees={(1, 7)})     # a BIN not in the package
        self.assertEqual(base, other)
        # the option on BINs with fewer than two trunks (a single tree, a flat grid) changes nothing
        same, s2 = convert([grove, single, flat], cluster_trees={(1, 1), (1, 2)})
        self.assertEqual(base, same)
        self.assertEqual(s2['grove_parts'], 0)
        split, _ = convert([grove, single, flat], cluster_trees={(1, 0)})
        self.assertNotEqual(base, split)


if __name__ == '__main__':
    unittest.main()
