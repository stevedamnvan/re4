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
            (root/"kos/fs.h").write_text("#pragma once\n#include <sys/types.h>\nusing file_t=int;\n#define FILEHND_INVALID -1\nint fs_open(const char*,int);int fs_close(int);ssize_t fs_total(int);void* fs_mmap(int);ssize_t fs_read(int,void*,size_t);off_t fs_seek(int,off_t,int);\n")
            (root/"kos.h").write_text('#include <kos/fs.h>\n#include <fcntl.h>\n#include <cstdint>\nstd::uint64_t timer_us_gettime64();\n')
            (root/"asset").write_bytes(package)
            large=TPL.TplImage(256,256,1,bytes((i*17)&255 for i in range(65536)))
            streamed,_=TPL.build_package([large],[TPL.MaterialBinding('one',0,None),TPL.MaterialBinding('alias',0,None)],twiddle=True)
            (root/"stream").write_bytes(streamed)
            bad_crc=bytearray(streamed);bad_crc[-1]^=1;(root/"bad_crc").write_bytes(bad_crc)
            small_vq,_=TPL.package_existing_vq(vq_fixture(8,8)[0]);(root/"small_vq").write_bytes(small_vq)
            vq,payload=vq_fixture();compact,_=TPL.package_existing_vq(vq)
            (root/"vq").write_bytes(compact)
            # Valid CRC isolates runtime layout validation from corruption rejection.
            for name,field,value in [('unknown',7,3),('oversized',5,16*16*2),('palette',3,5)]:
                bad=bytearray(compact);descriptor=list(TPL.TEXTURE.unpack_from(bad,TPL.HEADER.size))
                descriptor[field]=value;TPL.TEXTURE.pack_into(bad,TPL.HEADER.size,*descriptor)
                header=list(TPL.HEADER.unpack_from(bad));header[9]=zlib.crc32(bad[TPL.HEADER.size:])&0xffffffff
                TPL.HEADER.pack_into(bad,0,*header);(root/name).write_bytes(bad)
            table=bytearray(224)
            struct.pack_into('<I',table,0,2);struct.pack_into('<2I',table,16,64,160)
            table[24:32]=b'TPL\0NTR\0'
            struct.pack_into('<3I',table,64,TPL.TPL_MAGIC,1,12)
            struct.pack_into('<2I',table,76,24,0)
            struct.pack_into('<HHII',table,88,8,8,14,64)
            table[128:160]=struct.pack('<8s6I',b'R4NREF\0\0',0x12345678,0xabcdef01,8,8,14,32)
            entries=struct.pack('<3I',128,88,64)
            table[160:192]=struct.pack('<8s6I',b'R4NTBL\0\0',1,1,12,zlib.crc32(entries)&0xffffffff,1024,224)
            table[192:204]=entries;(root/"identities").write_bytes(table)
            pal=bytes(range(32));pf=2166136261
            for v in pal:pf=((pf^v)*16777619)&0xffffffff
            indexed=bytearray(256);indexed[:128]=table[:128]
            struct.pack_into('<I',indexed,20,192)
            struct.pack_into('<HHI',indexed,88,16,16,8)
            indexed[128:192]=struct.pack('<8s14I',b'R4PREF\0\0',0x12345678,0xabcdef01,16,16,8,128,2,32,zlib.crc32(pal)&0xffffffff,pf,0,0,0,0)
            indexed[192:224]=struct.pack('<8s6I',b'R4NTBL\0\0',1,1,12,zlib.crc32(entries)&0xffffffff,1024,256)
            indexed[224:236]=entries;(root/"indexed").write_bytes(indexed)
            fixture=r"""
#include "texture_package.hpp"
#include "gpu_lifecycle.hpp"
#include "room_storage.hpp"
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <vector>
#include <iterator>
extern "C" void re4dc_model_bind_draw_owner(const void*,void*,unsigned,unsigned){}
extern "C" void re4dc_model_unbind_draw_owner(const void*){}
extern "C" void re4dc_prepare_model_assets(){}
extern "C" void re4dc_model_retire_draw_plans(){}
extern "C" void re4dc_model_preparation_owner(void*){}
unsigned allocs=0,last_alloc=0,raw_bytes=0,raw_calls=0,linear_calls=0;int ta=0,render=0,render_calls=0;
void* pvr_mem_malloc(std::size_t n){++allocs;last_alloc=n;return malloc((n+31)&~std::size_t(31));}
void pvr_mem_free(void* p){assert(allocs);--allocs;free(p);}
void pvr_txr_load_ex(const void* p,void* q,unsigned w,unsigned h,unsigned){++linear_calls;memcpy(q,p,w*h*2);}
void pvr_txr_load(const void* p,void* q,std::size_t n){assert(n%32==0);++raw_calls;raw_bytes=n;memcpy(q,p,n);}
bool fail_reads=false;size_t read_cap=37,max_read=0;unsigned open_files=0;
int fs_open(const char* path,int flags){int fd=open(path,flags);if(fd>=0)++open_files;return fd;}
int fs_close(int fd){--open_files;return close(fd);}
ssize_t fs_total(int fd){struct stat s;return fstat(fd,&s)?-1:s.st_size;}
void* fs_mmap(int){return nullptr;}
ssize_t fs_read(int fd,void* p,size_t n){max_read=std::max(n,max_read);return fail_reads?0:read(fd,p,std::min(n,read_cap));}
off_t fs_seek(int fd,off_t off,int whence){return lseek(fd,off,whence);}
std::uint64_t timer_us_gettime64(){return 0;}
int pvr_wait_ready(){return ta;}
int pvr_wait_render_done(){++render_calls;return render;}
int main(int argc,char**argv){
 // The game's smaller bounce keeps the original final allocation and <64K
 // unaligned transport policy, including files larger than one bounce.
 for(unsigned size: {1U,2048U,16383U,16384U,16385U,32769U,65535U,65536U,98305U}){
   std::vector<unsigned char> original(size),owned(size+32);
   for(unsigned n=0;n<size;++n)original[n]=(n*13+n/97)&255;
   const std::string path=std::string(argv[1])+".read";
   {std::ofstream out(path,std::ios::binary);out.write((const char*)original.data(),size);}
   re4dc::storage::Arena arena;arena.init(owned.data(),owned.size());
   read_cap=37;max_read=0;
   auto result=re4dc::storage::read_file(arena,path.c_str());
   assert(result.data && result.size==size && !memcmp(result.data,original.data(),size));
   assert(max_read <= (size<65536 ? 16384U : 65536U));
   assert(!open_files);
   arena.reset();fail_reads=true;result=re4dc::storage::read_file(arena,path.c_str());
   assert(!result.data && arena.used()==0 && !open_files);fail_reads=false;
   unlink(path.c_str());
 }
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
assert(p.upload());assert(allocs==1 && (last_alloc==2112 || (RE4DC_UI_VRAM && last_alloc==2112+2016)) && raw_bytes==2112);
assert(!RE4DC_UI_VRAM || !(reinterpret_cast<std::uintptr_t>(p.pvr_texture(0))&2047)); // UI_VRAM: codebook on one 2 KiB page
assert(raw_calls==old_raw+1 && linear_calls==old_linear);
assert(p.vram_bytes()==2112 && re4dc::texture::pvr_format(descriptor)==0x48000000U);
assert(!memcmp(p.pvr_texture(0),expected.data(),expected.size()));
assert(p.release_payload());memset(vq.data(),0xcc,vq.size());
assert(p.textures()[0].payload==re4dc::texture::kPayloadVq);
assert(re4dc::texture::pvr_format(p.textures()[0])==0x48000000U);
assert(!memcmp(p.pvr_texture(0),expected.data(),expected.size()));p.close();assert(!allocs);
for(int arg=3;arg<6;++arg){
 std::ifstream bf(argv[arg],std::ios::binary);
 std::vector<unsigned char> bad((std::istreambuf_iterator<char>(bf)),{});
 assert(!p.adopt(bad.data(),bad.size()));assert(!allocs);
}
std::ifstream rf(argv[6],std::ios::binary);
std::vector<unsigned char> room((std::istreambuf_iterator<char>(rf)),{});
std::vector<unsigned char> core(room);
re4dc::texture::SourceIdentityTable identities,core_identities;
assert(core_identities.adopt(core.data(),core.size()));
assert(identities.adopt(room.data(),room.size()) && identities.count()==1);
unsigned crc=0,fnv=0;
assert(identities.lookup(room.data()+128,8,8,14,crc,fnv));
assert(crc==0x12345678U && fnv==0xabcdef01U);
assert(identities.lookup(room.data()+129,8,8,14,crc,fnv)==-1);
assert(identities.lookup(room.data()+128,16,8,14,crc,fnv)==-1);
identities.clear();assert(!identities.lookup(room.data()+128,8,8,14,crc,fnv));
assert(core_identities.lookup(core.data()+128,8,8,14,crc,fnv)==1); // room retirement leaves persistent core binding intact
assert(core_identities.lookup(room.data()+128,8,8,14,crc,fnv)==0);
// Actual recovered-game binder: four independent module owners, no extra
// payload allocation, reject overflow/duplicate/corruption and invalidate views
// before the caller reuses/frees backing. Rebind recycled addresses safely.
std::vector<unsigned char> owners[5];for(auto& o:owners)o=core;
for(unsigned i=0;i<4;++i){nsource=9;assert(re4dc_ui_bind_enemy(owners[i].data(),owners[i].size()));assert(!nsource);}
assert(!re4dc_ui_bind_enemy(owners[0].data(),owners[0].size()));
assert(!re4dc_ui_bind_enemy(owners[4].data(),owners[4].size()));
memset(owners[1].data()+96,0xcd,4); // source TPL pointer relocation
assert(enemy_identities[1].table.lookup(owners[1].data()+128,8,8,14,crc,fnv)==1);
re4dc_ui_unbind_enemy(owners[0].data());assert(!enemy_identities[0].archive);
assert(!enemy_identities[0].table.lookup(owners[0].data()+128,8,8,14,crc,fnv));
memset(owners[0].data(),0xee,owners[0].size());
assert(enemy_identities[1].table.lookup(owners[1].data()+128,8,8,14,crc,fnv)==1);
assert(re4dc_ui_bind_enemy(owners[4].data(),owners[4].size()));
for(auto& o:owners)re4dc_ui_unbind_enemy(o.data());
for(auto& e:enemy_identities)assert(!e.archive && !e.table.count());
owners[0]=core;owners[0][160]^=0x80;
assert(!re4dc_ui_bind_enemy(owners[0].data(),owners[0].size()));
owners[0]=core;assert(re4dc_ui_bind_enemy(owners[0].data(),owners[0].size()));
assert(enemy_identities[0].table.lookup(owners[0].data()+128,8,8,14,crc,fnv)==1);
re4dc_ui_unbind_enemy(owners[0].data());

// Actual room retirement fences/closes cached uploads but must retain the
// fixed player/weapon descriptor views when source reload flags are unchanged.
assert(re4dc_ui_bind_player(core.data(),core.size()));
assert(re4dc_ui_bind_weapon(room.data(),room.size()));
assert(::room_identities.adopt(room.data(),room.size()));
ready=true;re4dc_ui_retire_room();assert(closed==1 && render_calls==1);
assert(!::room_identities.count());
assert(player_identities.lookup(core.data()+128,8,8,14,crc,fnv)==1);
assert(weapon_identities.lookup(room.data()+128,8,8,14,crc,fnv)==1);
re4dc_ui_unbind_player();assert(!player_identities.count() && weapon_identities.count()==1);
re4dc_ui_unbind_weapon();assert(!weapon_identities.count());
ready=false;render_calls=0;
for(unsigned byte:{0U,160U,168U,172U,176U,180U,188U,192U,128U,144U,96U,121U}){
 room[byte]^=0x80;assert(!identities.adopt(room.data(),room.size()));assert(!identities.count());room[byte]^=0x80;
}
assert(identities.adopt(room.data(),room.size()));
// Binding precedes source relocation; later header mutation cannot change keys.
memset(room.data()+96,0xab,4);
assert(identities.lookup(room.data()+128,8,8,14,crc,fnv));
identities.clear();room[28]='X';assert(identities.adopt(room.data(),room.size()) && !identities.count());
// New indexed record keeps source palette bytes and rejects changes even after
// successful lookup. No source texel read or native palette allocation occurs.
std::ifstream ip(argv[10],std::ios::binary);
std::vector<unsigned char> ir((std::istreambuf_iterator<char>(ip)),{});
unsigned char palette[32];for(unsigned i=0;i<32;++i)palette[i]=i;
for(unsigned cycle=0;cycle<3;++cycle){
 assert(identities.adopt(ir.data(),ir.size()));
 assert(identities.lookup(ir.data()+128,16,16,8,crc,fnv,palette,2,32)==1);
 assert(crc==0x12345678U && fnv==0xabcdef01U);
 assert(identities.lookup(ir.data()+160,16,16,8,crc,fnv,palette,2,32)==-1);
 assert(identities.lookup(ir.data()+128,16,16,8,crc,fnv)==-1);
 assert(identities.lookup(ir.data()+128,16,16,8,crc,fnv,palette,1,32)==-1);
 assert(identities.lookup(ir.data()+128,16,16,8,crc,fnv,palette,2,30)==-1);
 palette[4]^=1;assert(identities.lookup(ir.data()+128,16,16,8,crc,fnv,palette,2,32)==-1);palette[4]^=1;
 identities.clear();assert(!identities.lookup(ir.data()+128,16,16,8,crc,fnv,palette,2,32));
}
for(unsigned byte:{152U,160U,164U,176U,180U,184U,188U}){
 ir[byte]^=0x80;assert(!identities.adopt(ir.data(),ir.size()));ir[byte]^=0x80;
}
// Real shared storage: short reads, unchanged native bytes, sharing, and no
// whole-file allocation/release accounting. CRC rejection precedes any VRAM.
std::ifstream sf(argv[7],std::ios::binary);
std::vector<unsigned char> stream((std::istreambuf_iterator<char>(sf)),{});
assert(p.open_streamed(argv[7]));assert(open_files==1);
assert(p.metadata_bytes()==48+2*96 && p.released_bytes()==0);
const auto td=p.textures()[0];assert(p.upload() && allocs==1 && p.shared_textures()==1);
assert(!memcmp(p.pvr_texture(0),stream.data()+td.data_offset,td.data_size));
assert(p.release_payload() && !open_files && !p.released_bytes());
assert(p.upload());p.close();assert(!allocs);
assert(!p.open_streamed(argv[8]) && !allocs && !open_files); // corrupt CRC
assert(!p.open_streamed(argv[1]) && !open_files); // linear layout unchanged/rejected
assert(p.open_streamed(argv[7]));fail_reads=true;
assert(!p.upload() && !p.upload_complete() && !p.release_payload());
assert(!p.upload());p.close();fail_reads=false;assert(!allocs && !open_files);
assert(!p.open_streamed("/missing/no-texture"));
for(int arg:{2,9}) { // normal VQ and its 8x8, 16-byte SQ tail
 std::ifstream f(argv[arg],std::ios::binary);
 std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),{});
 assert(p.open_streamed(argv[arg]));const auto d=p.textures()[0];assert(p.upload());
 assert(p.vram_bytes()==d.data_size && (last_alloc==d.data_size || (RE4DC_UI_VRAM && last_alloc==d.data_size+2016)));
 assert(!RE4DC_UI_VRAM || !(reinterpret_cast<std::uintptr_t>(p.pvr_texture(0))&2047));
 assert(!memcmp(p.pvr_texture(0),b.data()+d.data_offset,d.data_size));
 assert(p.release_payload() && !p.released_bytes());p.close();assert(!allocs);
}
assert(max_read<=65536);
int fd=fs_open(argv[7],O_RDONLY);
assert(!re4dc::storage::read_chunks(fd,32,[](const unsigned char*,size_t,void* ctx){
 int handle=*static_cast<int*>(ctx);char b[1];assert(!re4dc::storage::read_exact(handle,b,1));return false;
},&fd));
char byte;assert(re4dc::storage::read_exact(fd,&byte,1));fs_close(fd);assert(!open_files);
using re4dc::gpu::FenceResult;
ta=-1;assert(re4dc::gpu::quiesce()==FenceResult::ta_timeout && !render_calls);
ta=0;render=-1;assert(re4dc::gpu::quiesce()==FenceResult::render_timeout);
render=0;assert(re4dc::gpu::quiesce()==FenceResult::ready);
}
"""
            source=(ROOT/"port/dreamcast/game/platform/native_ui.cpp").read_text()
            first=source.index('extern "C" int re4dc_ui_bind_player(')
            last=source.index('extern "C" void re4dc_ui_init(',first)
            bindings=source[first:last]
            setup='struct EnemyIdentity {void* archive=nullptr;re4dc::texture::SourceIdentityTable table;};\nEnemyIdentity enemy_identities[4];unsigned nsource;void re4dc_log(const char*,...){}\n'
            setup+='re4dc::texture::SourceIdentityTable player_identities,weapon_identities,room_identities;bool ready;unsigned nquad,model_used,identity_hits,closed;struct Entry{};Entry entries[1];Entry* model_handle;void close_entry(Entry&){assert(render_calls);++closed;}void re4dc_missing(const char*){assert(false); }\n'
            fixture=fixture.replace('int main(',setup+bindings+'int main(',1)
            cpp=root/"fixture.cpp";cpp.write_text(fixture)
            scene=ROOT/"port/dreamcast/room";exe=root/"fixture"
            # Default package layout, then game UI_VRAM=1 (2 KiB page placement).
            for knob in ("0","1"):
                subprocess.run(["g++","-std=c++17","-DRE4DC_STORAGE_BOUNCE_BYTES=16384","-DRE4DC_UI_VRAM="+knob,"-fsanitize=address,undefined","-fno-omit-frame-pointer","-I"+str(root),"-I"+str(scene),str(cpp),
                                str(scene/"texture_package.cpp"),str(scene/"gpu_lifecycle.cpp"),str(scene/"room_storage.cpp"),"-o",str(exe)],check=True)
                subprocess.run([str(exe)]+[str(root/name) for name in ("asset","vq","unknown","oversized","palette","identities","stream","bad_crc","small_vq","indexed")],check=True)


    @unittest.skipUnless(shutil.which("g++"), "host compiler required")
    def test_texture_pin_matches_committed_packet_ownership(self):
        source=(ROOT/"port/dreamcast/game/platform/native_ui.cpp").read_text()
        # close_entry() and load() through load's closing brace (the anonymous
        # namespace closes next; PVR_PIPELINE fence glue may follow it).
        first=source.index("void close_entry(")
        loader=source[first:source.index("\n}\n}\n",source.index("Entry* load(",first))+3]
        commit=source[source.index('extern "C" void re4dc_model_packet_commit('):source.index('extern "C" void re4dc_model_result(')]
        fixture=r"""
#include "native_ui.h"
#include "native_render_profile.hpp"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <algorithm>
#define re4dc_log(...) ((void)0)
unsigned uploads=0,closes=0,alloc_fails=0;bool upload_fails=false;const char* upload_error="fixture";
namespace re4dc::texture {
constexpr unsigned kPayloadVq=1;
struct Header{unsigned texture_count=1,data_size=32;};
struct Texture{unsigned payload=0,data_size=32,width=8,height=8;};
struct Package{
 Header h;Texture t;unsigned bytes=0;
 bool open_streamed(const char*){return true;}
 bool upload(){if(upload_fails)return false;if(alloc_fails){--alloc_fails;upload_error="PVR texture allocation failed";return false;}upload_error=nullptr;++uploads;bytes=32;return true;}
 bool release_payload(){return true;}void close(){if(bytes)++closes;bytes=0;}
 unsigned vram_bytes()const{return bytes;}unsigned metadata_bytes()const{return 0;}
 const Header& header()const{return h;}const Texture* textures()const{return &t;}
 const char* error()const{return upload_error;}void* pvr_texture(int){return nullptr;}
};
unsigned pvr_format(const Texture&){return 0;}
}
struct Key{unsigned crc=0,fnv=0;bool operator==(const Key& b)const{return crc==b.crc&&fnv==b.fnv;}};
struct Entry{re4dc::texture::Package package;Key key;unsigned frame=0;bool valid=false;};
Entry entries[2],*model_handle=nullptr;unsigned frame=5,used=0,peak=0,loads=0;
unsigned model_used=0,model_pending=1,model_peak=0;
constexpr unsigned kVramBudget=128;
unsigned vram_budget=1000,vram_retries=0,vram_rejects=0,reclaimed=0;
unsigned image_size(const Re4dcUiImage&){return 32;}
bool image_key(const Re4dcUiImage& i,Key& k){k.crc=(uintptr_t)i.pixels;k.fnv=k.crc;return true;}
int re4dc_ui_heap_free(){return 1000;}unsigned pvr_mem_available(){return 1000;}
"""+loader+commit+r"""
int main(){
 Re4dcUiImage a{};a.width=a.height=8;a.pixels=(void*)1;
 auto* first=load(a,false);assert(first&&first->valid&&first->frame!=frame&&used==32&&uploads==1);
 // Releasing an evaluation does not evict its upload. Reuse stays warm.
 for(unsigned i=0;i<500;++i)assert(load(a,false)==first);
 assert(uploads==1);model_handle=first;re4dc_model_packet_commit(3);
 assert(first->frame==frame&&model_used==4&&model_peak==128);
 a.pixels=(void*)2;auto* failed_part=load(a,false);assert(failed_part&&failed_part!=first);
 model_handle=failed_part;re4dc_model_packet_commit(0);
 assert(failed_part->frame!=frame&&model_used==4); // no packet, no current-frame pin
 a.pixels=(void*)3;auto* third=load(a,false);assert(third==failed_part&&first->frame==frame);
 // UI pins immediately because its quad is queued immediately.
 a.pixels=(void*)4;auto* ui=load(a);assert(ui==third&&ui->frame==frame);
 assert(load(a,false)==ui&&ui->frame==frame); // tentative model use cannot unpin UI
 a.pixels=(void*)5;assert(!load(a,false)); // both committed owners survive pressure
 // Actual caller fences before advancing frame. Old uploads become eligible.
 ++frame;auto* next=load(a,false);assert(next&&next->frame!=frame&&used==64);
 model_handle=next;re4dc_model_packet_commit(3);assert(next->frame==frame);
 a.pixels=(void*)6;upload_fails=true;assert(!load(a,false));assert(next->valid&&next->frame==frame&&used==32);
 upload_fails=false;upload_error="fixture";assert(load(a));assert(used==64);
#if RE4DC_UI_VRAM
 // Fragmented pool: an allocation failure evicts one more unreferenced upload
 // (never a current-frame one) and retries the reopened package.
 ++frame;alloc_fails=1;a.pixels=(void*)7;auto* retried=load(a);
 assert(retried&&retried->frame==frame&&vram_retries==1&&reclaimed==1&&used==32);
 alloc_fails=1;a.pixels=(void*)8;assert(!load(a)&&retried->valid&&used==32); // nothing evictable
 alloc_fails=0;
 // A texture that cannot fit beside this frame's pinned uploads is refused
 // before eviction or file I/O (no package open, nothing closed).
 ++frame;assert(load(a)&&used==64);retried->frame=frame-1; // one pinned, one evictable
 auto uploads_before=uploads;vram_budget=150;a.pixels=(void*)9; // 32 pinned + 128 (8x8 16-bit) > 150
 assert(!load(a)&&vram_rejects==1&&uploads==uploads_before&&retried->valid&&used==64);
 vram_budget=1000;
#endif
}
"""
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);cpp=p/"pin.cpp";cpp.write_text(fixture);exe=p/"pin"
            for knob in ("0","1"): # default cache, then UI_VRAM=1 (pool budget, retry, fail-fast)
                subprocess.run(["g++","-std=c++17","-DRE4DC_STORAGE_BOUNCE_BYTES=16384","-DRE4DC_UI_VRAM="+knob,"-fsanitize=address,undefined","-I"+str(ROOT/"port/dreamcast/game/platform/include"),str(cpp),"-o",str(exe)],check=True)
                subprocess.run([str(exe)],check=True)

    @unittest.skipUnless(shutil.which("g++"), "host compiler required")
    def test_runtime_key_matches_offline_key(self):
        source=(ROOT/"port/dreamcast/game/platform/native_ui.cpp").read_text()
        a=source.index("unsigned image_size(");b=source.index("void close_entry(",a)
        body=source[a:b]
        image=TPL.TplImage(8,4,9,bytes(range(32)),0,bytes(range(16)))
        key,_=UI.image_identity(image);crc,fnv=[int(x,16) for x in key.split("-")]
        fixture='#include "native_ui.h"\n#include <cassert>\n'
        fixture+='struct Key{unsigned crc,fnv;};struct Source{Re4dcUiImage image;Key key;};constexpr unsigned kSourceCount=128;Source sources[kSourceCount];unsigned nsource;\n'
        fixture+='struct Identity {int state=0;int lookup(const void*,unsigned,unsigned,unsigned,unsigned&,unsigned&,const void* =nullptr,unsigned =0xffffffffU,unsigned =0)const{return state;}} room_identities,core_identities,option_identities,player_identities,weapon_identities; unsigned identity_hits; void re4dc_log(const char*,...){}\n'
        fixture+='struct EnemyIdentity {void* archive=nullptr;Identity table;};EnemyIdentity enemy_identities[4];\n'
        fixture+=body
        fixture+=r"""
int main(){
unsigned char pixels[32],palette[16];
for(unsigned i=0;i<32;++i)pixels[i]=i;
for(unsigned i=0;i<16;++i)palette[i]=i;
Re4dcUiImage image{pixels,palette,8,4,9,0,16};Key key{};assert(image_key(image,key));
assert(image_size(image)==32);
"""
        fixture+=f"assert(key.crc=={crc}U && key.fnv=={fnv}U);"
        fixture+='assert(nsource==1);assert(image_key(image,key));assert(nsource==1);nsource=0;room_identities.state=-1;image.pixels=(void*)1;assert(!image_key(image,key));assert(nsource==0);room_identities.state=0;core_identities.state=-1;assert(!image_key(image,key));assert(nsource==0);core_identities.state=1;image.format=14;image.palette=nullptr;image.palette_bytes=0;assert(image_key(image,key));assert(nsource==1);nsource=0;room_identities.state=-1;assert(!image_key(image,key));}\n'
        fixture=fixture.rsplit('}',1)[0]+r"""
room_identities.state=core_identities.state=0;nsource=0;
option_identities.state=-1;assert(!image_key(image,key) && !nsource);
option_identities.state=1;assert(image_key(image,key) && nsource==1);
option_identities.state=0;nsource=0;
enemy_identities[2].archive=(void*)2;enemy_identities[2].table.state=-1;
assert(!image_key(image,key) && !nsource); // invalid payload cannot fall back to texel hashing
enemy_identities[2].table.state=1;assert(image_key(image,key) && nsource==1);
// Cache pressure may reduce hits, never replace descriptor-owner qualification.
for(unsigned i=0;i<kSourceCount+8;++i){image.pixels=(void*)(unsigned long)(0x1000+i);assert(image_key(image,key));}
assert(nsource==kSourceCount);
}
"""
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);cpp=root/"key.cpp";cpp.write_text(fixture);exe=root/"key"
            subprocess.run(["g++","-std=c++17","-I"+str(ROOT/"port/dreamcast/game/platform/include"),str(cpp),"-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__=="__main__":unittest.main()
