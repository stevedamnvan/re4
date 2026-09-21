"""Exercise native Package lifetime and the new source-image identity boundary.
Host fixtures compile the real shared implementation, following the existing
native_room_load/native_module_binding fixture pattern. No emulator substitute.
"""
import pathlib
import shutil
import subprocess
import sys
import struct
import zlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "port/dreamcast/tools"))
import prepare_native_ui as UI
import convert_tpl as TPL
from test_convert_tpl import make_tpl

def vq_fixture(width=16,height=16,fmt=1):
    mode=(1<<30)|(fmt<<27)|((width.bit_length()-4)<<3)|(height.bit_length()-4)
    payload=bytes((i*37+11)&255 for i in range(2048+width*height//4))
    size=(32+len(payload)+31)&~31
    header=struct.pack('<4sIBBBBHHI12x',b'DcTx',size,0,0,255,0,width,height,mode)
    return header+payload+bytes(size-32-len(payload)),payload

class NativeUi(unittest.TestCase):
    def test_existing_vq_wrap_preserves_payload_and_rejects_unsupported_layouts(self):
        for width,height in [(8,8),(16,16),(256,512)]:
            for fmt,native in [(0,TPL.FORMAT_ARGB1555),(1,TPL.FORMAT_RGB565),(2,TPL.FORMAT_ARGB4444)]:
                encoded,payload=vq_fixture(width,height,fmt)
                package,meta=TPL.package_existing_vq(encoded)
                descriptor=TPL.TEXTURE.unpack_from(package,TPL.HEADER.size)
                self.assertEqual(descriptor[3],native)
                self.assertEqual(descriptor[7],TPL.PAYLOAD_VQ)
                self.assertEqual(package[descriptor[4]:],payload)
                self.assertEqual(meta['vram_bytes'],len(payload))
                self.assertFalse(meta['reencoded'])
        encoded,_=vq_fixture()
        malformed=[]
        for bit in [31,26,25,11]: # mips, nontwiddled, stride, small codebook
            bad=bytearray(encoded);mode=struct.unpack_from('<I',bad,16)[0]
            struct.pack_into('<I',bad,16,mode|(1<<bit));malformed.append(bad)
        for offset,value in [(0,0),(8,1),(9,1),(10,254),(12,32),(20,1)]:
            bad=bytearray(encoded);bad[offset]=value;malformed.append(bad)
        for fmt in [3,4,5,6,7]:
            bad=bytearray(encoded);mode=struct.unpack_from('<I',bad,16)[0]
            struct.pack_into('<I',bad,16,(mode&~(7<<27))|(fmt<<27));malformed.append(bad)
        malformed.extend([encoded[:-1],encoded+bytes(32)])
        for bad in malformed:
            with self.assertRaises(ValueError):TPL.package_existing_vq(bad)

    def test_preparation_is_qualified_and_refuses_stale_destination(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);source=root/"source";source.mkdir()
            (source/"valid.tpl").write_bytes(make_tpl([(8,4,1,bytes([128])*32)]))
            out=root/"out"
            report=UI.prepare(source,["valid.tpl"],out)
            self.assertEqual(report["errors"],[])
            self.assertEqual(report["unique_images"],1)
            with self.assertRaises(FileExistsError):
                UI.prepare(source,["valid.tpl"],out)
            rejected=UI.prepare(source,["missing.tpl"],root/"rejected")
            self.assertTrue(rejected["errors"])

    def test_source_empty_palette_is_not_a_missing_image(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);source=root/"source";source.mkdir()
            (source/"empty.tpl").write_bytes(struct.pack('>3I',TPL.TPL_MAGIC,0,12))
            report=UI.prepare(source,["empty.tpl"],root/"out")
            self.assertEqual(report["errors"],[])
            self.assertEqual(report["unique_images"],0)
            self.assertEqual(len(report["empty_palettes"]),1)
            (source/"bad.tpl").write_bytes(struct.pack('>3I',TPL.TPL_MAGIC,0,900))
            report=UI.prepare(source,["bad.tpl"],root/"bad")
            self.assertTrue(report["errors"])

    @unittest.skipUnless(shutil.which("g++"), "host compiler required")
    def test_actual_package_release_failure_sharing_and_fences(self):
        image=TPL.TplImage(8,4,1,bytes([128])*32)
        other=TPL.TplImage(8,4,1,bytes([64])*32)
        package,_=TPL.build_package([image,other],[
            TPL.MaterialBinding("one",0,None),TPL.MaterialBinding("alias",0,None),
            TPL.MaterialBinding("two",1,None)],pad_to_power_of_two=True)
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);(root/"dc/pvr").mkdir(parents=True);(root/"kos").mkdir()
            (root/"dc/pvr.h").write_text("#pragma once\nusing pvr_ptr_t=void*;\n#define PVR_TXRFMT_RGB565 (1U<<27)\n#define PVR_TXRFMT_ARGB1555 0U\n#define PVR_TXRFMT_ARGB4444 (2U<<27)\n#define PVR_TXRFMT_VQ_ENABLE (1U<<30)\nint pvr_wait_ready();int pvr_wait_render_done();\n")
            (root/"dc/pvr/pvr_mem.h").write_text("#include <cstddef>\nvoid* pvr_mem_malloc(std::size_t);void pvr_mem_free(void*);\n")
            (root/"dc/pvr/pvr_txr.h").write_text("#include <cstddef>\n#define PVR_TXRLOAD_16BPP 0\nvoid pvr_txr_load_ex(const void*,void*,unsigned,unsigned,unsigned);void pvr_txr_load(const void*,void*,std::size_t);\n")
            (root/"kos/fs.h").write_text("#pragma once\n#include <sys/types.h>\nusing file_t=int;\n#define FILEHND_INVALID -1\nint fs_open(const char*,int);int fs_close(int);ssize_t fs_total(int);void* fs_mmap(int);\n")
            (root/"asset").write_bytes(package)
            vq,payload=vq_fixture();compact,_=TPL.package_existing_vq(vq)
            (root/"vq").write_bytes(compact)
            # Valid CRC isolates runtime layout validation from corruption rejection.
            for name,field,value in [('unknown',7,3),('oversized',5,16*16*2),('palette',3,5)]:
                bad=bytearray(compact);descriptor=list(TPL.TEXTURE.unpack_from(bad,TPL.HEADER.size))
                descriptor[field]=value;TPL.TEXTURE.pack_into(bad,TPL.HEADER.size,*descriptor)
                header=list(TPL.HEADER.unpack_from(bad));header[9]=zlib.crc32(bad[TPL.HEADER.size:])&0xffffffff
                TPL.HEADER.pack_into(bad,0,*header);(root/name).write_bytes(bad)
            fixture=r"""
#include "texture_package.hpp"
#include "gpu_lifecycle.hpp"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <vector>
#include <iterator>
unsigned allocs=0,last_alloc=0,raw_bytes=0,raw_calls=0,linear_calls=0;int ta=0,render=0,render_calls=0;
void* pvr_mem_malloc(std::size_t n){++allocs;last_alloc=n;return malloc(n);}
void pvr_mem_free(void* p){assert(allocs);--allocs;free(p);}
void pvr_txr_load_ex(const void* p,void* q,unsigned w,unsigned h,unsigned){++linear_calls;memcpy(q,p,w*h*2);}
void pvr_txr_load(const void* p,void* q,std::size_t n){++raw_calls;raw_bytes=n;memcpy(q,p,n);}
int fs_open(const char*,int){return -1;} int fs_close(int){return 0;}
ssize_t fs_total(int){return -1;} void* fs_mmap(int){return nullptr;}
int pvr_wait_ready(){return ta;}
int pvr_wait_render_done(){++render_calls;return render;}
int main(int argc,char**argv){
std::ifstream f(argv[1],std::ios::binary);
std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(f)),{});
re4dc::texture::Package p;
assert(p.adopt(bytes.data(),bytes.size()));
assert(!p.release_payload());
p.inject_upload_failure_after(1);
assert(!p.upload());assert(allocs==2);assert(!p.upload());assert(!p.release_payload());
p.close();p.close();assert(!allocs);
assert(p.adopt(bytes.data(),bytes.size()));assert(p.upload());
assert(allocs==2 && p.shared_textures()==1 && p.pvr_texture(0)==p.pvr_texture(1));
assert(p.release_payload());assert(p.released_bytes()==bytes.size());
auto vram=p.vram_bytes();auto metadata=p.metadata_bytes();
memset(bytes.data(),0xdd,bytes.size()); // caller actually reclaims/reuses backing
assert(p.header().texture_count==3 && p.find("two") && p.vram_bytes()==vram);
assert(metadata==sizeof(re4dc::texture::Header)+3*sizeof(re4dc::texture::Texture));
assert(p.release_payload());assert(p.upload());p.close();assert(!allocs);
std::ifstream vf(argv[2],std::ios::binary);
std::vector<unsigned char> vq((std::istreambuf_iterator<char>(vf)),{});
assert(p.adopt(vq.data(),vq.size()));
const auto descriptor=p.textures()[0];
std::vector<unsigned char> expected(vq.begin()+descriptor.data_offset,vq.end());
auto old_linear=linear_calls,old_raw=raw_calls;
assert(p.upload());assert(allocs==1 && last_alloc==2112 && raw_bytes==2112);
assert(raw_calls==old_raw+1 && linear_calls==old_linear);
assert(p.vram_bytes()==2112 && re4dc::texture::pvr_format(descriptor)==0x48000000U);
assert(!memcmp(p.pvr_texture(0),expected.data(),expected.size()));
assert(p.release_payload());memset(vq.data(),0xcc,vq.size());
assert(p.textures()[0].payload==re4dc::texture::kPayloadVq);
assert(re4dc::texture::pvr_format(p.textures()[0])==0x48000000U);
assert(!memcmp(p.pvr_texture(0),expected.data(),expected.size()));p.close();assert(!allocs);
for(int arg=3;arg<argc;++arg){
 std::ifstream bf(argv[arg],std::ios::binary);
 std::vector<unsigned char> bad((std::istreambuf_iterator<char>(bf)),{});
 assert(!p.adopt(bad.data(),bad.size()));assert(!allocs);
}
using re4dc::gpu::FenceResult;
ta=-1;assert(re4dc::gpu::quiesce()==FenceResult::ta_timeout && !render_calls);
ta=0;render=-1;assert(re4dc::gpu::quiesce()==FenceResult::render_timeout);
render=0;assert(re4dc::gpu::quiesce()==FenceResult::ready);
}
"""
            cpp=root/"fixture.cpp";cpp.write_text(fixture)
            scene=ROOT/"port/dreamcast/room";exe=root/"fixture"
            subprocess.run(["g++","-std=c++17","-I"+str(root),"-I"+str(scene),str(cpp),
                            str(scene/"texture_package.cpp"),str(scene/"gpu_lifecycle.cpp"),"-o",str(exe)],check=True)
            subprocess.run([str(exe)]+[str(root/name) for name in ("asset","vq","unknown","oversized","palette")],check=True)

    @unittest.skipUnless(shutil.which("g++"), "host compiler required")
    def test_runtime_key_matches_offline_key(self):
        source=(ROOT/"port/dreamcast/game/platform/native_ui.cpp").read_text()
        a=source.index("unsigned image_size(");b=source.index("void close_entry(",a)
        body=source[a:b]
        image=TPL.TplImage(8,4,9,bytes(range(32)),0,bytes(range(16)))
        key,_=UI.image_identity(image);crc,fnv=[int(x,16) for x in key.split("-")]
        fixture='#include "native_ui.h"\n#include <cassert>\n'
        fixture+='struct Key{unsigned crc,fnv;};struct Source{Re4dcUiImage image;Key key;};Source sources[256];unsigned nsource;\n'
        fixture+=body
        fixture+=r"""
int main(){
unsigned char pixels[32],palette[16];
for(unsigned i=0;i<32;++i)pixels[i]=i;
for(unsigned i=0;i<16;++i)palette[i]=i;
Re4dcUiImage image{pixels,palette,8,4,9,0,16};auto key=image_key(image);
assert(image_size(image)==32);
"""
        fixture+=f"assert(key.crc=={crc}U && key.fnv=={fnv}U);"
        fixture+='assert(nsource==1);image_key(image);assert(nsource==1);}\n'
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);cpp=root/"key.cpp";cpp.write_text(fixture);exe=root/"key"
            subprocess.run(["g++","-std=c++17","-I"+str(ROOT/"port/dreamcast/game/platform/include"),str(cpp),"-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__=="__main__":unittest.main()
