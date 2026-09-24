"""Synthetic contracts for TREE_IMPOSTOR / MESH_TEXTURES packaging (tools/mesh_annotate.py,
tools/tree_impostors.py): the impostor table is appended without changing any
byte the geometry path reads, records match instanced_mesh.hpp MeshImpostor,
and the kPal4 texture package matches texture_package.cpp's layout checks."""
import importlib.util
import pathlib
import struct
import sys
import unittest
import zlib

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('room_bins_lod_tests', HERE / 'test_room_bins_lod.py')
LT = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = LT
spec.loader.exec_module(LT)
C = LT.C
import mesh_annotate as A  # noqa: E402  (tools/ is on sys.path via test_room_bins_lod)
import tree_impostors as TI  # noqa: E402


def record(bin_no, **kw):
    r = dict(owner='0x01', bin=bin_no, common=False, key=['01234567', '89abcdef'], views=16, cols=8,
             cell=[128, 128], atlas=[1024, 256], centre=[1.0, 2.0, 3.0], half_w=4.0, half_h=5.0)
    r.update(kw)
    return r


class TreeImpostorTests(unittest.TestCase):
    def setUp(self):
        self.blob, _ = LT.convert([LT.grid_bin(4), LT.grid_bin(5, bump=0.5)])

    def test_annotate_appends_only(self):
        out, report = A.annotate(self.blob, dict(records=[record(1), record(0, key=['00000001', '00000002'])]))
        self.assertEqual(report['impostors'], 2)
        h = C.HEADER.unpack_from(out, 0)
        self.assertEqual(h[2], len(out))
        self.assertEqual(h[3], zlib.crc32(out[C.HEADER.size:]) & 0xFFFFFFFF)
        self.assertEqual(len(out) % 32, 0)
        # every byte but the header's size/CRC and LOD word 7 is the source package's
        lod_reserved = C.HEADER.size + 7 * 4
        same = bytearray(out[:len(self.blob)])
        same[8:16] = self.blob[8:16]
        same[lod_reserved:lod_reserved + 4] = self.blob[lod_reserved:lod_reserved + 4]
        self.assertEqual(bytes(same), self.blob)
        lod = C.LOD_HEADER.unpack_from(out, C.HEADER.size)
        self.assertEqual(lod[5:7], (0, 0))  # W9b class/rule offsets untouched
        self.assertEqual(lod[7] % 32, 0)
        head = struct.unpack_from('<8I', out, lod[7])
        self.assertEqual((head[1], head[2:]), (2, (0, 0, 0, 0, 0, 0)))
        self.assertEqual(head[0] % 32, 0)
        rows = [A.IMPOSTOR.unpack_from(out, head[0] + i * A.IMPOSTOR.size) for i in range(2)]
        self.assertEqual([r[0] for r in rows], [0, 1])  # ascending mesh index
        self.assertEqual(rows[0][1:3], (1, 2))
        self.assertEqual(rows[1][3:9], (16, 8, 128, 128, 1024, 256))
        self.assertEqual(rows[1][-1], 0)  # runtime colour slot starts empty
        self.assertEqual(A.IMPOSTOR.size, 48)

    def test_unknown_bins_skipped_and_refuses_twice(self):
        out, report = A.annotate(self.blob, dict(records=[record(7)]))
        self.assertEqual(report['impostors'], 0)
        once, _ = A.annotate(self.blob, dict(records=[record(0)]))
        with self.assertRaises(ValueError):
            A.annotate(once, dict(records=[record(1)]))
        with self.assertRaises(ValueError):
            A.annotate(self.blob, dict(records=[record(0), record(0)]))

    def test_texture_records(self):
        """MESH_TEXTURES: u32 count + MeshTexture records at runtime-table word 2, by package part index."""
        tex = dict(textures=[dict(owner=1, bin=1, common=False, part=0, key=['0000000a', '0000000b'],
                                  width=512, height=256),
                             dict(owner=1, bin=0, common=False, part=0, key=['00000001', '00000002'],
                                  width=1024, height=1024),
                             dict(owner=1, bin=9, common=False, part=0, key=['0', '0'], width=8, height=8)])
        out, report = A.annotate(self.blob, dict(records=[record(1)]), tex)
        self.assertEqual((report['impostors'], report['textures']), (1, 2))
        lod = C.LOD_HEADER.unpack_from(out, C.HEADER.size)
        head = struct.unpack_from('<8I', out, lod[7])
        self.assertEqual(head[2] % 32, 0)
        self.assertGreater(head[2], head[0])
        self.assertGreater(lod[7], head[2])
        self.assertEqual(struct.unpack_from('<I', out, head[2])[0], 2)
        rows = [A.TEXTURE.unpack_from(out, head[2] + 4 + i * A.TEXTURE.size) for i in range(2)]
        firsts = [m[6] for m in A.meshes(out)]
        self.assertEqual(rows, [(firsts[0], 1024, 1024, 1, 2), (firsts[1], 512, 256, 10, 11)])
        self.assertEqual(A.TEXTURE.size, 16)
        h = C.HEADER.unpack_from(out, 0)
        self.assertEqual(h[3], zlib.crc32(out[C.HEADER.size:]) & 0xFFFFFFFF)
        with self.assertRaises(ValueError):  # no such part
            A.annotate(self.blob, None, dict(textures=[dict(tex['textures'][0], part=99)]))

    def test_pal4_package_layout(self):
        w, h = 64, 32
        data = bytes(range(256)) * 8 + bytes(w * h // 16)
        mode = (1 << 30) | (5 << 27) | (3 << 3) | 2  # VQ, PAL4BPP, 8<<3=64 wide, 8<<2=32 high
        dt = b'DcTx' + struct.pack('<I', (32 + len(data) + 31) & ~31) + bytes([0, 0, 255, 15]) + \
            struct.pack('<HHI', w, h, mode) + bytes(12) + data
        dt += bytes(len(dt) % 32 and 32 - len(dt) % 32)
        pal = b'DPAL' + struct.pack('<I', 2) + struct.pack('<2I', 0xFF102030, 0x00FFFFFF)
        blob, key, meta = TI.package_pal4(dt, pal, 'x')
        header = TI.tpl.HEADER.unpack_from(blob, 0)
        tex = TI.tpl.TEXTURE.unpack_from(blob, TI.tpl.HEADER.size)
        self.assertEqual(tex[1:4], (w, h, TI.FORMAT_PAL4))
        self.assertEqual(tex[5], 2048 + w * h // 16 + 32)  # texture_package.cpp expected kPal4 size
        self.assertEqual(tex[7], TI.tpl.PAYLOAD_VQ)
        payload = blob[tex[4]:tex[4] + tex[5]]
        self.assertEqual(payload[:len(data)], data)
        self.assertEqual(struct.unpack_from('<2H', payload, len(data)), (0x8000 | 2 << 10 | 4 << 5 | 6, 0x7FFF))
        self.assertEqual(header[8], zlib.crc32(blob[TI.tpl.HEADER.size:]) & 0xFFFFFFFF)
        self.assertEqual(key, (zlib.crc32(payload) & 0xFFFFFFFF, TI.fnv1a(payload)))
        self.assertEqual(meta['vram_bytes'], len(payload))


if __name__ == '__main__':
    unittest.main()
