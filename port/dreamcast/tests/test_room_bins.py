"""Synthetic R4IM contracts: GX BIN -> instanced native mesh, checked by the native reader."""
import importlib.util
import math
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

ROOT = pathlib.Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('room_bins_converter', ROOT / 'tools/convert_room_bins.py')
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)


def synth_bin(parts, positions, normals, colors, uvs, pad=0, shift=6):
    """Big-endian GX ModelData: parts = [(opcode, [(pos, nrm, clr, uv), ...]), ...] per part."""
    head = 0x48
    pos_off = head
    nrm_off = pos_off + 8 * len(positions)
    clr_off = nrm_off + 8 * len(normals)
    uv_off = clr_off + 4 * len(colors)
    part_off = uv_off + 4 * len(uvs) + pad
    body = bytearray(part_off)
    for i, p in enumerate(positions):
        struct.pack_into('>4h', body, pos_off + 8 * i, *(round(v * (1 << shift)) for v in p), 0)
    for i, n in enumerate(normals):
        struct.pack_into('>3hH', body, nrm_off + 8 * i, *(round(v * 16384) for v in n), 0)
    for i, c in enumerate(colors):
        body[clr_off + 4 * i:clr_off + 4 * i + 4] = bytes(c)
    for i, t in enumerate(uvs):
        struct.pack_into('>2h', body, uv_off + 4 * i, *(round(v * 256) for v in t))
    for texture, prims in parts:
        stream = bytearray()
        for op, corners in prims:
            stream += struct.pack('>BH', op, len(corners))
            for p, n, c, t in corners:
                stream += struct.pack('>4H', p, n, c, t)
        stream += b'\0' * (-len(stream) % 32)
        header = bytearray(0x20)
        header[0x0C] = texture
        struct.pack_into('>I', header, 0x18, len(stream))
        body += header + stream
    struct.pack_into('>I', body, 0x0C, clr_off)
    struct.pack_into('>I', body, 0x10, uv_off)
    body[0x19] = 1
    struct.pack_into('>H', body, 0x1A, len(parts))
    struct.pack_into('>I', body, 0x1C, part_off)
    struct.pack_into('>I', body, 0x20, 0x80000000)
    body[0x28] = shift
    struct.pack_into('>I', body, 0x30, pos_off)
    struct.pack_into('>I', body, 0x34, nrm_off)
    struct.pack_into('>2H', body, 0x38, len(positions), len(normals))
    struct.pack_into('>I', body, 0x3C, 0x20030818)
    return bytes(body)


def fixture(pad=0):
    positions = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (2, 0, 0), (2, 1, 0), (3, 0.5, -1)]
    normals = [(0, 0, 1), (0, 1, 0)]
    colors = [(255, 255, 255, 255), (90, 90, 90, 0)]
    uvs = [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (2, 1), (-3.5, 7.25)]
    strip = [(0, 0, 0, 0), (1, 0, 0, 1), (2, 0, 0, 2), (3, 0, 0, 3), (4, 1, 1, 4), (5, 1, 1, 5)]
    tris = [(1, 0, 0, 1), (4, 0, 0, 4), (6, 1, 0, 6), (4, 0, 0, 4), (5, 0, 0, 5), (6, 1, 0, 6)]
    quad = [(0, 0, 0, 0), (1, 0, 0, 1), (3, 0, 0, 3), (2, 0, 1, 2)]
    return synth_bin([(3, [(0x98, strip)]), (7, [(0x90, tris), (0x80, quad)])],
                     positions, normals, colors, uvs, pad=pad)


def package(bins, cell=0.0):
    with tempfile.TemporaryDirectory() as d:
        entries = []
        for n, data in enumerate(bins):
            p = pathlib.Path(d) / f'{n:04d}.BIN'
            p.write_bytes(data)
            entries.append((1, False, n, p))
        return C.convert(entries, 1.0, cell, 16)[0]


def decode(blob):
    h = C.HEADER.unpack_from(blob, 0)
    nm, np_, nl, nv, ns, npal, om, op, ol, ov, os_, opal = h[4:16]
    meshes = [C.MESH.unpack_from(blob, om + i * C.MESH.size) for i in range(nm)]
    parts = [C.PART.unpack_from(blob, op + i * C.PART.size) for i in range(np_)]
    lets = [C.MESHLET.unpack_from(blob, ol + i * C.MESHLET.size) for i in range(nl)]
    verts = [C.VERTEX.unpack_from(blob, ov + i * 12) for i in range(nv)]
    return h, meshes, parts, lets, verts, os_


def triangles(blob, mesh_index=0):
    """Per part offset: Counter of rotation-canonical triangles in package units."""
    h, meshes, parts, lets, verts, os_ = decode(blob)
    m = meshes[mesh_index]
    out = {}
    for part in parts[m[6]:m[6] + m[7]]:
        got = Counter()
        for fv, fs, sb, vc, sc, *_ in lets[part[6]:part[6] + part[7]]:
            data = blob[os_ + fs:os_ + fs + sb]
            i = strips = 0
            while i < len(data):
                n = data[i]
                strip = list(data[i + 1:i + 1 + n])
                assert 3 <= n <= 255 and max(strip) < vc <= 256
                i += 1 + n
                strips += 1
                for t in C.strip_triangles(strip):
                    if len(set(t)) == 3:
                        got[C.canonical(tuple((verts[fv + l][0:3], verts[fv + l][3:5]) for l in t))] += 1
            assert strips == sc
        out[part[0]] = got
    return out


def expected(data, blob, mesh_index=0):
    h, meshes, parts, *_ = decode(blob)
    m = meshes[mesh_index]
    origin, step = m[8:11], m[11:14]
    src = C.parse_bin(data)
    pos = src['positions']
    out = {}
    for part in parts[m[6]:m[6] + m[7]]:
        ub, us = part[8:10], part[10:12]
        key = lambda k: (tuple(min(65535, max(0, round((pos[k[0]][a] - origin[a]) / step[a]))) for a in range(3)),
                         tuple(min(65535, max(0, round((src['uv'](k[2])[a] - ub[a]) / us[a]))) for a in range(2)))
        sp = next(p for p in src['parts'] if p['offset'] == part[0])
        want = Counter()
        for s in sp['strips']:
            for t in C.strip_triangles(s):
                if len(set(t)) == 3:
                    want[C.canonical(tuple(key(k) for k in t))] += 1
        for t in sp['loose']:
            if len(set(t)) == 3:
                want[C.canonical(tuple(key(k) for k in t))] += 1
        out[part[0]] = want
    return out


class RoomBinsTests(unittest.TestCase):
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
#include <fstream>
#include <iterator>
#include <vector>
int main(int,char** argv){
    std::ifstream in(argv[1],std::ios::binary);
    std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)),{});
    std::vector<std::uint32_t> words((raw.size()+3)/4);std::memcpy(words.data(),raw.data(),raw.size());
    re4dc::room::MeshPackage p;
    if(!p.adopt(reinterpret_cast<const std::uint8_t*>(words.data()),std::uint32_t(raw.size()))){
        std::printf("reject %s\n",p.error());return 1;}
    std::printf("ok %u %u\n",p.find(0,false),p.part(0,0,p.parts()[0].source_size)!=nullptr);
    return 0;
}
''')
        cls.exe = cls.root / 'read'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(cls.root),
                        '-I', str(ROOT / 'room'), str(cls.root / 'read.cpp'), '-o', str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, blob):
        p = self.root / 'x.re4mesh'
        p.write_bytes(blob)
        return subprocess.run([str(self.exe), str(p)], text=True, capture_output=True).stdout.strip()

    def test_strips_lists_and_quads_round_trip_with_winding(self):
        data = fixture()
        blob = package([data])
        self.assertEqual(self.read(blob), 'ok 0 1')
        got, want = triangles(blob), expected(data, blob)
        self.assertEqual(got, want)
        self.assertEqual(sum(sum(c.values()) for c in got.values()), 4 + 2 + 2)

    def test_part_identity_is_relative_to_first_part(self):
        moved = package([fixture(pad=96)])
        self.assertEqual(moved, package([fixture()]))
        _, _, parts, *_ = decode(moved)
        self.assertEqual(parts[0][0], 0)

    def test_colour_slot_carries_palette_and_octahedral_normal(self):
        h, meshes, parts, lets, verts, _ = decode(package([fixture()]))
        self.assertEqual(h[16], C.COLOR_OCT_NORMAL)
        pal = {v[5] >> 12 for v in verts}
        self.assertLessEqual(max(pal), h[9] - 1)
        for n in [(0, 0, 1), (0, 1, 0), (0.6, -0.8, 0), (-0.48, 0.6, -0.64)]:
            code = C.oct12(n)
            x = (code & 63) * 2 / 63 - 1
            y = ((code >> 6) & 63) * 2 / 63 - 1
            z = 1 - abs(x) - abs(y)
            if z < 0:
                x, y = (1 - abs(y)) * math.copysign(1, x), (1 - abs(x)) * math.copysign(1, y)
            length = math.sqrt(x * x + y * y + z * z)
            self.assertGreater(sum(a * b / length for a, b in zip((x, y, z), n)), 0.995)

    def test_long_strips_split_and_meshlets_hold_256_vertices(self):
        count = 700
        positions = [(i * 0.25, (i & 1) * 1.0, 0.0) for i in range(count)]
        uvs = [(i / 64, i & 1) for i in range(count)]
        strip = [(i, 0, 0, i) for i in range(count)]
        data = synth_bin([(1, [(0x98, strip)])], positions, [(0, 0, 1)], [(255, 255, 255, 255)], uvs)
        blob = package([data])
        self.assertEqual(self.read(blob), 'ok 0 1')
        _, _, _, lets, *_ = decode(blob)
        self.assertGreater(len(lets), 2)
        self.assertTrue(all(l[3] <= 256 for l in lets))
        self.assertEqual(triangles(blob), expected(data, blob))

    def test_spatial_meshlets_keep_triangles_and_bound_extent(self):
        count = 700
        positions = [(i * 0.25, (i & 1) * 1.0, 0.0) for i in range(count)]
        uvs = [(i / 64, i & 1) for i in range(count)]
        strip = [(i, 0, 0, i) for i in range(count)]
        data = synth_bin([(1, [(0x98, strip)])], positions, [(0, 0, 1)], [(255, 255, 255, 255)], uvs)
        cell = 8.0
        blob = package([data], cell)
        self.assertEqual(self.read(blob), 'ok 0 1')
        self.assertEqual(triangles(blob), expected(data, blob))
        _, meshes, _, lets, *_ = decode(blob)
        self.assertGreater(len(lets), len(decode(package([data]))[3]))
        step = meshes[0][11]
        # One cell's restripped run (<= cell plus a triangle) closes each meshlet.
        self.assertTrue(all((l[8] - l[5]) * step <= cell + 1.0 for l in lets))

    def test_reader_rejects_bad_indices_state_and_encoding(self):
        blob = bytearray(package([fixture()]))
        h = C.HEADER.unpack_from(blob, 0)
        bad = bytearray(blob)
        bad[h[14] + 1] = 255
        self.assertEqual(self.read(bytes(bad)), 'reject strip index')
        bad = bytearray(blob)
        bad[h[11] + 11] = 1
        self.assertEqual(self.read(bytes(bad)), 'reject part state')
        bad = bytearray(blob)
        struct.pack_into('<I', bad, 64, 0)
        self.assertEqual(self.read(bytes(bad)), 'reject color encoding')
        bad = bytearray(blob)
        struct.pack_into('<H', bad, h[13] + 10, 15 << 12)
        self.assertEqual(self.read(bytes(bad)), 'reject color')
        self.assertEqual(self.read(bytes(blob[:-4])), 'reject header')


if __name__ == '__main__':
    unittest.main()
