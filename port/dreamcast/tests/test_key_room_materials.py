"""Material source keys: offline keying/BIN verification and the native reader."""
import importlib.util
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('room_v4_converter', ROOT / 'tools/convert_room_obj.py')
C = importlib.util.module_from_spec(spec); sys.modules[spec.name] = C; spec.loader.exec_module(C)
import key_room_materials as K

NAME = 'FILE_01#SMD_1#SMX_4#model#BIN_2#'
OBJ = """
v 1.25 2.5 -3.75
v 4.5 5.125 6.75
v -1.5 -2.25 -4.0
vn 0.2 0.3 0.4
vt 0.25 0.5
vt 0.75 0.5
vt 0.5 1.0
g FILE_01#SMD_1#SMX_4#model#BIN_2#
usemtl ROOM_MATERIAL_007
f 1/1/1 2/2/1 3/3/1
"""
MTL = """newmtl ROOM_MATERIAL_007
map_Kd R100.TPL/R100.TPL-5.png
map_d R100.TPL/R100.TPL-6.png
"""


def package():
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'x.obj'; p.write_text(OBJ); parsed = C.parse_obj(p)
    v3, _ = C.build_package(parsed, {NAME: C.SourceGroupData(0xffffffff, 4, 0, 3, 2, 0)})
    data = bytearray(v3); struct.pack_into('<I', data, 96, 3)
    n = struct.unpack_from('<I', data, 12)[0]
    struct.pack_into('<I', data, 92, zlib.crc32(data[n:]) & 0xffffffff)
    compact, _ = C.compact_prelit_package(bytes(data), [NAME], 'aos20')
    return compact


def model_bin(texture, alpha):
    header = bytearray(0x48)
    struct.pack_into('>H', header, 0x1A, 1); struct.pack_into('>I', header, 0x1C, 0x48)
    part = bytearray(0x20)
    part[0x0B] = 4 if alpha is not None else 0
    part[0x0C] = texture; part[0x0E] = alpha or 0
    struct.pack_into('>II', part, 0x18, 0, 1)
    return bytes(header + part)


class KeyRoomMaterialsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = pathlib.Path(cls.temp.name)
        inc = cls.root / 'kos'; inc.mkdir()
        (inc / 'fs.h').write_text("""
#pragma once
#include <sys/types.h>
using file_t=int;
#define FILEHND_INVALID (-1)
inline file_t fs_open(const char*,int){return -1;}
inline ssize_t fs_total(file_t){return -1;}
inline void* fs_mmap(file_t){return nullptr;}
inline void fs_close(file_t){}
""")
        (cls.root / 'read.cpp').write_text(r"""
#include "room_package.hpp"
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>
int main(int,char**argv){
  std::ifstream f(argv[1],std::ios::binary);
  std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),{});
  std::vector<unsigned char> aligned(b.size()+16);
  unsigned char* data=aligned.data()+(16-reinterpret_cast<std::uintptr_t>(aligned.data())%16)%16;
  std::copy(b.begin(),b.end(),data);
  re4dc::room::Package p;
  if(!p.adopt(data,b.size())){std::puts(p.error());return 1;}
  std::printf("keyed=%d",p.material_keys());
  for(unsigned m=0;m<p.header().material_count;++m){
    re4dc::room::MaterialSourceKey key{};
    if(re4dc::room::material_source_key(p.materials()[m],key))std::printf(" %u:%u",key.texture,key.alpha);
  }
  std::puts("");return 0;
}
""")
        cls.exe = cls.root / 'reader'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-I' + str(cls.root),
                        '-I' + str(ROOT / 'room'), str(cls.root / 'read.cpp'),
                        str(ROOT / 'room/room_package.cpp'), '-o', str(cls.exe)], check=True)
        (cls.root / 'room.mtl').write_text(MTL)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, data):
        path = self.root / 'input.re4room'; path.write_bytes(data)
        return subprocess.run([str(self.exe), str(path)], text=True, capture_output=True)

    def test_keys_only_material_tail_flags_and_crc(self):
        source = package()
        keyed, keys = K.key_package(source, K.parse_materials(self.root / 'room.mtl'))
        self.assertEqual(keys, [{'material': 'ROOM_MATERIAL_007', 'texture': 5, 'alpha': 6}])
        changed = [i for i, (a, b) in enumerate(zip(source, keyed)) if a != b]
        fields = K.HEADER.unpack_from(keyed, 0)
        tail = range(fields[15] + 60, fields[15] + 64)
        # Only the material key tail, the payload CRC (92) and header flags (96).
        self.assertTrue(all(i in tail or i in range(92, 100) for i in changed), changed)
        self.assertEqual(fields[23], K.FLAG_SOURCE_GROUPS | K.FLAG_PRELIT | K.FLAG_MATERIAL_KEYS)
        self.assertEqual(self.read(source).stdout.strip(), 'keyed=0')
        self.assertEqual(self.read(keyed).stdout.strip(), 'keyed=1 5:6')

    def test_reader_rejects_a_damaged_key(self):
        keyed, _ = K.key_package(package(), K.parse_materials(self.root / 'room.mtl'))
        data = bytearray(keyed); offset = K.HEADER.unpack_from(data, 0)[15]
        data[offset + 60] = ord('X')
        struct.pack_into('<I', data, 92, zlib.crc32(bytes(data[160:])) & 0xffffffff)
        run = self.read(bytes(data))
        self.assertEqual(run.returncode, 1); self.assertIn('material source key', run.stdout)

    def test_bin_verification(self):
        keyed, keys = K.key_package(package(), K.parse_materials(self.root / 'room.mtl'))
        sources = K.source_materials(keyed)
        self.assertEqual([(s['owner'], s['work'], s['bin'], s['common']) for s in sources], [(1, 1, 2, False)])
        bins = self.root / 'FILE_01'; bins.mkdir(exist_ok=True)
        (bins / '0002.BIN').write_bytes(model_bin(5, 6))
        report = K.verify(sources, keys, {'FILE_01': bins})
        self.assertEqual(report[0]['status'], 'verified')
        (bins / '0002.BIN').write_bytes(model_bin(5, None))
        with self.assertRaisesRegex(ValueError, 'package keys'):
            K.verify(sources, keys, {'FILE_01': bins})
        self.assertIn('unverified', K.verify(sources, keys, {})[0]['status'])

    def test_unbound_material_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no MTL texture binding'):
            K.key_package(package(), {(1, None): 'OTHER'})


if __name__ == '__main__':
    unittest.main()
