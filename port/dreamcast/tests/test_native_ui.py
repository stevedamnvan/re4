"""Exercise native Package lifetime and the new source-image identity boundary.
Host fixtures compile the real shared implementation, following the existing
native_room_load/native_module_binding fixture pattern. No emulator substitute.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "port/dreamcast/tools"))
import prepare_native_ui as UI
import convert_tpl as TPL
from test_convert_tpl import make_tpl

class NativeUi(unittest.TestCase):
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

    @unittest.skipUnless(shutil.which("g++"), "host compiler required")
    def test_actual_package_release_failure_sharing_and_fences(self):
        image=TPL.TplImage(8,4,1,bytes([128])*32)
        other=TPL.TplImage(8,4,1,bytes([64])*32)
        package,_=TPL.build_package([image,other],[
            TPL.MaterialBinding("one",0,None),TPL.MaterialBinding("alias",0,None),
            TPL.MaterialBinding("two",1,None)])
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);(root/"dc/pvr").mkdir(parents=True);(root/"kos").mkdir()
            (root/"dc/pvr.h").write_text("#pragma once\nusing pvr_ptr_t=void*;\nint pvr_wait_ready();int pvr_wait_render_done();\n")
            (root/"dc/pvr/pvr_mem.h").write_text("#include <cstddef>\nvoid* pvr_mem_malloc(std::size_t);void pvr_mem_free(void*);\n")
            (root/"dc/pvr/pvr_txr.h").write_text("#include <cstddef>\n#define PVR_TXRLOAD_16BPP 0\nvoid pvr_txr_load_ex(const void*,void*,unsigned,unsigned,unsigned);void pvr_txr_load(const void*,void*,std::size_t);\n")
            (root/"kos/fs.h").write_text("#pragma once\n#include <sys/types.h>\nusing file_t=int;\n#define FILEHND_INVALID -1\nint fs_open(const char*,int);int fs_close(int);ssize_t fs_total(int);void* fs_mmap(int);\n")
            (root/"asset").write_bytes(package)
            fixture=r"""
#include "texture_package.hpp"
#include "gpu_lifecycle.hpp"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <vector>
#include <iterator>
unsigned allocs=0;int ta=0,render=0,render_calls=0;
void* pvr_mem_malloc(std::size_t n){++allocs;return malloc(n);}
void pvr_mem_free(void* p){assert(allocs);--allocs;free(p);}
void pvr_txr_load_ex(const void* p,void* q,unsigned w,unsigned h,unsigned){memcpy(q,p,w*h*2);}
void pvr_txr_load(const void* p,void* q,std::size_t n){memcpy(q,p,n);}
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
            subprocess.run([str(exe),str(root/"asset")],check=True)

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
