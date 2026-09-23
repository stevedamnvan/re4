"""Synthetic v4 ownership/range/seam contracts using the actual native reader."""
import importlib.util
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT=pathlib.Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('room_v4_converter',ROOT/'tools/convert_room_obj.py')
C=importlib.util.module_from_spec(spec);sys.modules[spec.name]=C;spec.loader.exec_module(C)
NAME='FILE_01#SMD_1#SMX_4#model#BIN_2#'
OBJ="""
v 1.25 2.5 -3.75
v 4.5 5.125 6.75
v -1.5 -2.25 -4.0
v 7.0 8.0 9.0
vn 0.2 0.3 0.4
vt -44.56078 3.25
vt 1.432 19.36862
vt 0.0 -0.5
vt 1.0 1.0
g FILE_01#SMD_1#SMX_4#model#BIN_2#
usemtl real_texture_identity
f 1/1/1 2/2/1 3/3/1
f 1/4/1 3/3/1 4/4/1
"""

def fixture():
    with tempfile.TemporaryDirectory() as d:
        p=pathlib.Path(d)/'x.obj';p.write_text(OBJ);parsed=C.parse_obj(p)
    v3,_=C.build_package(parsed,{NAME:C.SourceGroupData(0xffffffff,4,0,3,2,0)})
    data=bytearray(v3);struct.pack_into('<I',data,96,3)
    return bytes(data)

def crc(data):
    n=struct.unpack_from('<I',data,12)[0]
    struct.pack_into('<I',data,92,zlib.crc32(data[n:])&0xffffffff)
    return bytes(data)

class RoomPackageV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=pathlib.Path(cls.temp.name)
        inc=cls.root/'kos';inc.mkdir()
        (inc/'fs.h').write_text("""
#pragma once
#include <sys/types.h>
using file_t=int;
#define FILEHND_INVALID (-1)
inline file_t fs_open(const char*,int){return -1;}
inline ssize_t fs_total(file_t){return -1;}
inline void* fs_mmap(file_t){return nullptr;}
inline void fs_close(file_t){}
""")
        (cls.root/'read.cpp').write_text(r"""
#include "room_package.hpp"
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdio>
int main(int argc,char**argv){
  if(argc!=2 && argc!=3)return 3;
  std::ifstream f(argv[1],std::ios::binary);
  std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),{});
  const unsigned offset=argc==3?4:0;
  if(offset)b.insert(b.begin(),offset,0);
  re4dc::room::Package p;
  if(!p.adopt(b.data()+offset,b.size()-offset)){std::puts(p.error());return 1;}
  if(p.compact() && (p.vertices()||p.indices()||p.groups()||p.batches()||p.source_groups()||p.primitive_indices()))return 2;
  std::printf("%u %u\n",p.header().version,p.header().vertex_count);
  p.close();if(p.compact()||p.compact_vertices())return 2;
  return 0;
}
""")
        cls.exe=cls.root/'reader'
        subprocess.run(['g++','-std=c++17','-O2','-fno-fast-math','-Wall','-Wextra','-Werror',
                        '-I'+str(cls.root),'-I'+str(ROOT/'room'),str(cls.root/'read.cpp'),
                        str(ROOT/'room/room_package.cpp'),'-o',str(cls.exe)],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def read(self,data,valid,misaligned=False):
        p=self.root/'input.re4room';p.write_bytes(data)
        run=subprocess.run([str(self.exe),str(p)]+(["misaligned"] if misaligned else []),text=True,capture_output=True)
        self.assertEqual(run.returncode,0 if valid else 1,run.stdout+run.stderr)
    def test_legacy_and_both_compact_readers(self):
        v3=fixture();self.read(v3,True)
        for layout in ('aos20','split24'):
            data,m=C.compact_prelit_package(v3,[NAME],layout)
            self.read(data,True);self.assertEqual(sum(m['sections_after'].values()),len(data))
            self.assertEqual(m['source_identities'][0]['work'],1)
            self.assertEqual(m['source_identities'][0]['bin'],2)
    def test_positions_seams_strip_order_and_uv_error(self):
        old=fixture();h=C.HEADER.unpack_from(old)
        old_vertices=[C.VERTEX.unpack_from(old,h[18]+i*32) for i in range(h[8])]
        old_indices=struct.unpack_from('<%dI'%h[14],old,h[21])
        for layout in ('aos20','split24'):
            data,m=C.compact_prelit_package(old,[NAME],layout);q=C.HEADER.unpack_from(data)
            ex=C.COMPACT_EXTENSION.unpack_from(data,128);batch=C.COMPACT_BATCH.unpack_from(data,q[17])
            new_indices=struct.unpack_from('<%dH'%q[14],data,q[21])
            self.assertEqual(h[13:15],q[13:15])
            for a,b in zip(old_indices,new_indices):
                v=old_vertices[a]
                if layout=='aos20':
                    x=C.COMPACT_VERTEX.unpack_from(data,q[18]+b*20);xyz=x[:3];u,w,color=x[3:]
                else:
                    xyz=C.COMPACT_POSITION.unpack_from(data,q[18]+b*16)[:3]
                    u,w,color=C.COMPACT_ATTRIBUTE.unpack_from(data,ex[1]+b*8)
                self.assertEqual(struct.pack('<3f',*v[:3]),struct.pack('<3f',*xyz))
                for axis,quant in enumerate((u,w)):
                    value=C._f32(batch[9+axis]+C._f32(quant*batch[11+axis]))
                    self.assertLessEqual(abs(value-v[6+axis]),.5/1024)
                packed=0xff000000|(int(C._f32(v[3]*255))<<16)|(int(C._f32(v[4]*255))<<8)|int(C._f32(v[5]*255))
                self.assertEqual(color,packed)
            self.assertNotIn(NAME.encode(),data) # identity retained numerically
            self.assertIn(b'real_texture_identity',data) # binding name is not debug
    def test_crc_truncation_and_local_range_rejected(self):
        data,_=C.compact_prelit_package(fixture(),[NAME]);h=C.HEADER.unpack_from(data)
        self.read(data[:-1],False)
        b=bytearray(data);b[-1]^=1;self.read(bytes(b),False)
        b=bytearray(data);struct.pack_into('<H',b,h[21],65535);self.read(crc(b),False)
    def test_aligned_backing_required_for_vector_loads(self):
        for layout in ('aos20','split24'):
            data,_=C.compact_prelit_package(fixture(),[NAME],layout)
            self.read(data,False,misaligned=True)
        self.read(fixture(),True,misaligned=True) # historical 4-byte contract

    def test_nonfinite_vertex_and_wrong_layout_rejected(self):
        data,_=C.compact_prelit_package(fixture(),[NAME]);h=C.HEADER.unpack_from(data)
        b=bytearray(data);struct.pack_into('<f',b,h[18],float('nan'));self.read(crc(b),False)
        b=bytearray(data);struct.pack_into('<I',b,128,99);self.read(bytes(b),False)
        b=bytearray(data);struct.pack_into('<I',b,8,9);self.read(bytes(b),False)
    def test_group_identity_overlap_and_ranges_rejected(self):
        data,_=C.compact_prelit_package(fixture(),[NAME]);h=C.HEADER.unpack_from(data)
        b=bytearray(data);struct.pack_into('<H',b,h[16]+6,3);self.read(crc(b),False)
        b=bytearray(data);struct.pack_into('<I',b,h[17]+28,1);self.read(crc(b),False)
        b=bytearray(data);struct.pack_into('<I',b,72,160);self.read(bytes(b),False)
    def test_unqualified_bake_identity_and_precision_rejected(self):
        b=bytearray(fixture());struct.pack_into('<I',b,96,1)
        with self.assertRaises(ValueError):C.compact_prelit_package(bytes(b),[NAME])
        with self.assertRaises(ValueError):C.compact_prelit_package(fixture(),[NAME.replace('SMX_4','SMX_5')])
        with self.assertRaises(ValueError):C.compact_prelit_package(fixture(),[NAME],max_uv_error=1e-10)

if __name__=='__main__':unittest.main()
