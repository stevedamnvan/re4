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
  re4dc::room::CompactSourceRange range{99,99,99};
  unsigned groups=0;
  if(p.compact()) {
    for(unsigned i=0;i<p.compact_header()->source_count;++i) {
      const auto& s=p.compact_sources()[i];
      if(!p.resolve_source(s.owner,s.work,s.bin,s.common,range) ||
         range.source!=i || range.first_group!=groups || !range.group_count)return 4;
      for(unsigned g=0;g<range.group_count;++g)
        if(p.compact_groups()[range.first_group+g].source!=i)return 5;
      groups+=range.group_count;
      if(p.resolve_source(s.owner,s.work,s.bin^1,s.common,range) || range.group_count ||
         p.resolve_source(s.owner,s.work,s.bin,!s.common,range) || range.group_count)return 6;
    }
    if(groups!=p.header().group_count)return 7;
  } else if(p.resolve_source(1,1,2,false,range) || range.group_count)return 8;
  std::printf("%u %u groups=%u\n",p.header().version,p.header().vertex_count,groups);
  p.close();if(p.compact()||p.compact_vertices() ||
      p.resolve_source(1,1,2,false,range) || range.group_count)return 2;
  // Re-adoption at a different aligned address must resolve by offsets; there
  // are no persistent source pointers/cached ranges inside the package reader.
  std::vector<unsigned char> moved(b);
  if(!p.adopt(moved.data()+offset,moved.size()-offset))return 9;
  if(p.compact()) {
    const auto& s=p.compact_sources()[0];
    if(!p.resolve_source(s.owner,s.work,s.bin,s.common,range) || range.source!=0)return 10;
  }
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
        for layout in ('aos20','split24','aos12'):
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
    def test_aos12_grid_palette_and_bounds(self):
        old=fixture();h=C.HEADER.unpack_from(old)
        old_vertices=[C.VERTEX.unpack_from(old,h[18]+i*32) for i in range(h[8])]
        old_indices=struct.unpack_from('<%dI'%h[14],old,h[21])
        data,m=C.compact_prelit_package(old,[NAME],'aos12');q=C.HEADER.unpack_from(data)
        ex=C.COMPACT_EXTENSION.unpack_from(data,128)
        self.assertEqual((q[3],ex[0]),(12,3))
        *origin_step,count,reserved=C.COMPACT_QUANTIZATION.unpack_from(data,ex[1])
        origin,step=origin_step[:3],origin_step[3:]
        palette=struct.unpack_from('<%dI'%count,data,ex[1]+C.COMPACT_QUANTIZATION.size)
        new_indices=struct.unpack_from('<%dH'%q[14],data,q[21])
        group=C.COMPACT_GROUP.unpack_from(data,q[16])
        for a,b in zip(old_indices,new_indices):
            v=old_vertices[a];x=C.COMPACT_VERTEX12.unpack_from(data,q[18]+b*12)
            for axis in range(3):
                decoded=C._f32(origin[axis]+C._f32(x[axis]*step[axis]))
                self.assertLessEqual(abs(decoded-v[axis]),step[axis]*.5+1e-6)
                self.assertTrue(group[3+axis]<=decoded<=group[6+axis])
            packed=0xff000000|(int(C._f32(v[3]*255))<<16)|(int(C._f32(v[4]*255))<<8)|int(C._f32(v[5]*255))
            self.assertEqual(palette[x[5]],packed)
        self.assertEqual(m['vertices'],(q[8]));self.assertLessEqual(m['max_position_error'],max(step))
        # An index past the palette, or a translucent palette entry, is rejected.
        bad=bytearray(data);struct.pack_into('<H',bad,q[18]+10,count)
        struct.pack_into('<I',bad,92,C.zlib.crc32(bad[160:])&0xffffffff);self.read(bytes(bad),False)
        bad=bytearray(data);struct.pack_into('<I',bad,ex[1]+C.COMPACT_QUANTIZATION.size,0x7f000000)
        struct.pack_into('<I',bad,92,C.zlib.crc32(bad[160:])&0xffffffff);self.read(bytes(bad),False)
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
    def test_source_registration_requires_unambiguous_contiguous_owner_work(self):
        # Reused SMX ID and repeated BIN across owners are legitimate source
        # instances; owner/work, not either shared field, distinguishes them.
        names=[NAME,NAME.replace('SMD_1','SMD_2').replace('BIN_2','BIN_3'),
               NAME.replace('FILE_01','FILE_02')]
        obj=OBJ+''.join('\ng '+n+'\nusemtl real_texture_identity\nf 1/1/1 2/2/1 3/3/1\n' for n in names[1:])
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'objects.obj';path.write_text(obj)
            raw,_=C.build_package(C.parse_obj(path),
                {n:C.SourceGroupData(0xffffffff,4,0,3,2,0) for n in names})
        raw=bytearray(raw);struct.pack_into('<I',raw,96,3)
        data,_=C.compact_prelit_package(bytes(raw),names);self.read(data,True)
        h=C.HEADER.unpack_from(data);ex=C.COMPACT_EXTENSION.unpack_from(data,128)
        b=bytearray(data)
        # Same owner/work with a different BIN must not publish two bindings.
        struct.pack_into('<H',b,ex[2]+84+78,1);self.read(crc(b),False)
        b=bytearray(data);struct.pack_into('<H',b,h[16]+32+6,0)
        self.read(crc(b),False) # an orphan/skipped source is not silently lost
        b=bytearray(data);struct.pack_into('<H',b,h[16]+64+6,0)
        self.read(crc(b),False) # interleaving must not reorder alpha work
        conflicting=[names[0],names[1].replace('SMD_2','SMD_1'),names[2]]
        # The converter's source name lookup must see the same renamed source
        # records too, so update the v3 diagnostic group name in this fixture.
        bad=bytearray(raw);rh=C.HEADER.unpack_from(bad)
        bad[rh[16]+96:rh[16]+160]=conflicting[1].encode().ljust(64,b'\0')
        bad=crc(bad)
        with self.assertRaisesRegex(ValueError,'conflicting source owner/work'):
            C.compact_prelit_package(bad,conflicting)

    def test_unqualified_bake_identity_and_precision_rejected(self):
        b=bytearray(fixture());struct.pack_into('<I',b,96,1)
        with self.assertRaises(ValueError):C.compact_prelit_package(bytes(b),[NAME])
        with self.assertRaises(ValueError):C.compact_prelit_package(fixture(),[NAME.replace('SMX_4','SMX_5')])
        with self.assertRaises(ValueError):C.compact_prelit_package(fixture(),[NAME],max_uv_error=1e-10)

if __name__=='__main__':unittest.main()
