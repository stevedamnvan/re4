"""Immutable event transport and actual source-unit lifetime; no event-play acceptance."""
from pathlib import Path
import importlib.util, shutil, struct, subprocess, sys, tempfile, unittest, zlib
ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / 'port/dreamcast/tools'
sys.path.insert(0, str(TOOLS))
import le_mirror as le

def event_source(size=65568):
    b=bytearray(size);b[:6]=b'event\0'
    struct.pack_into('>4I',b,64,80,16,0,96)
    struct.pack_into('>II4H',b,80,27,0,0,0,16,0)
    return b

def function(text, name):
    start=text.index(name); brace=text.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

class EventPreparation(unittest.TestCase):
    def test_certificate_binds_actual_qualified_conversion(self):
        original=event_source();data,cert=le.prepare_event_reference('evd/test.evd',original)
        self.assertEqual(struct.unpack_from('<I',data,80)[0],27)
        self.assertEqual(cert[:8],b'R4EVDREF')
        self.assertEqual(struct.unpack_from('<6I',cert,8),
                         (1,len(data),65536,2,zlib.crc32(b'evd/test.evd'),zlib.crc32(cert[32:])))
        self.assertEqual(struct.unpack_from('<2I',cert,32),
                         (zlib.crc32(data[:65536]),zlib.crc32(data[65536:])))
        before=list(le.REPORT)
        for name,source in [('evd/../test.evd',original),('evd/test.evd',original[:-1]),
                            ('evd/test.evd',bytes(len(original)))]:
            with self.assertRaises(ValueError):le.prepare_event_reference(name,source)
        unknown=bytearray(original);struct.pack_into('>I',unknown,80,999)
        with self.assertRaises(ValueError):le.prepare_event_reference('evd/test.evd',unknown)
        self.assertEqual(le.REPORT,before)

@unittest.skipUnless(shutil.which('g++'),'host C++ compiler required')
class EventRuntime(unittest.TestCase):
    def test_native_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'kos').mkdir();(p/'evd').mkdir()
            data,cert=le.prepare_event_reference('evd/test.evd',event_source())
            (p/'evd/test.evd').write_bytes(data);(p/'evd/test.evd.evq').write_bytes(cert)
            (p/'kos/fs.h').write_text('''#pragma once
#include <cstddef>
#include <sys/types.h>
#include <fcntl.h>
using file_t=int;
#define FILEHND_INVALID -1
file_t fs_open(const char*,int);int fs_close(file_t);ssize_t fs_total(file_t);ssize_t fs_read(file_t,void*,size_t);
''')
            (p/'kos.h').write_text('#pragma once\n#include "kos/fs.h"\n#include <cstdint>\nuint64_t timer_us_gettime64();\n')
            (p/'kos/net.h').write_text('#pragma once\n#include <cstddef>\nunsigned net_crc32le(const unsigned char*,size_t);\n')
            code=r'''
#include "native_event_file.h"
#include "kos.h"
#include <zlib.h>
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#include <unistd.h>
#include <sys/stat.h>
#include <fstream>
#include <stdexcept>
std::string root;int handles=0;bool truncate_read=false;
file_t fs_open(const char* p,int f){int r=open(p,f);if(r>=0)++handles;return r;}
int fs_close(file_t f){--handles;return close(f);}
ssize_t fs_total(file_t f){struct stat s;fstat(f,&s);return s.st_size;}
ssize_t fs_read(file_t f,void* p,size_t n){if(truncate_read)return 0;return read(f,p,n>257?257:n);}
uint64_t timer_us_gettime64(){static uint64_t t;return t+=10;}
unsigned net_crc32le(const unsigned char* p,size_t n){return crc32(0,p,n);}
extern "C" void* re4dc_io_begin(){return nullptr;}
extern "C" void re4dc_io_end(void*){}
extern "C" void re4dc_log(const char*,...){}
extern "C" void re4dc_missing(const char*){throw std::runtime_error("explicit rejection");}
extern "C" int re4dc_dvd_native_path(const char* n,char* p,unsigned cap){auto s=root+"/"+n;if(s.size()>=cap)return 0;strcpy(p,s.c_str());return 1;}
std::vector<char> load(std::string n){std::ifstream f(root+"/"+n,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
void save(std::string n,const std::vector<char>& b){std::ofstream f(root+"/"+n,std::ios::binary|std::ios::trunc);f.write(b.data(),b.size());}
int main(int,char** argv){
 root=argv[1];auto data=load("evd/test.evd"),cert=load("evd/test.evd.evq");std::vector<char> out(data.size());
 assert(re4dc_event_file_prepare("evd/test.evd",data.size()));
 assert(re4dc_event_file_install("evd/test.evd",data.size(),out.data()) && out==data);
 auto s=re4dc_event_file_stats();assert(s->prepared==1 && s->installed==1 && s->bytes_read==data.size() && s->metadata_bytes_read==2*cert.size());
 assert(!re4dc_event_file_prepare("evd/../test.evd",data.size()));
 assert(!re4dc_event_file_prepare("evd/absent.evd",data.size()));
 auto corrupt=data;corrupt.back()^=1;save("evd/test.evd",corrupt);
 // Preload validates offline qualification/size. Full content validation is
 // deferred until install; a successful preload never activates these bytes.
 assert(re4dc_event_file_prepare("evd/test.evd",data.size()));
 assert(!re4dc_event_file_install("evd/test.evd",data.size(),out.data()));
 corrupt.pop_back();save("evd/test.evd",corrupt);assert(!re4dc_event_file_prepare("evd/test.evd",data.size()));
 save("evd/test.evd",data);
 for(unsigned i:{8u,12u,16u,20u,24u,28u,32u}){auto bad=cert;bad[i]^=1;save("evd/test.evd.evq",bad);assert(!re4dc_event_file_prepare("evd/test.evd",data.size()));}
 save("evd/test.evd.evq",cert);truncate_read=true;assert(!re4dc_event_file_prepare("evd/test.evd",data.size()));truncate_read=false;
 assert(re4dc_event_file_prepare("evd/test.evd",data.size()));assert(handles==0);
 bool rejected=false;try{re4dc_event_file_reject_swap();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
}
'''
            self.compile_run(p,code,[ROOT/'port/dreamcast/game/platform/native_event_file.cpp',ROOT/'port/dreamcast/room/room_storage.cpp'],['-lz'],[tmp])

    def compile_run(self,p,code,extra=(),flags=(),args=()):
        (p/'test.cpp').write_text(code)
        subprocess.run(['g++','-std=c++20','-fno-pie','-no-pie','-fsanitize=address,undefined','-g',
                        '-I'+str(p),'-I'+str(ROOT/'port/dreamcast/game/platform/include'),
                        str(p/'test.cpp'),*[str(x) for x in extra],*flags,'-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test'),*args],check=True)

    def test_source_unit_lifetime_and_relocation(self):
        source=(ROOT/'src/game/datactrl.cpp').read_text()
        header=r'''
#define RE4DC_GAME 1
#define RE4DC_EVENT_FILES 1
#include "native_event_file.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <stdexcept>
using u32=uintptr_t;using u8=unsigned char;
#define ALIGN32(x) (((x)+31)&~u32(31))
u8 DVD_BUFF[65536],DVD_BUFF2[65536];
enum {CMND_ARAM_LOAD=2};
struct cDataUnit {
 int m_condition=0,m_command=0,m_err=0;u8 m_be_flag=1,wait=0,m_wait=0,m_malloc_heap=0;
 void* m_addr=nullptr;u32 arg=0;void* m_malloc_addr=nullptr;u32 dest=0,m_fix_addr=0,m_size=32;
 char m_name[32]="evd/test.evd";int m_id=-1;
 int chk(u32 b){return !!(m_be_flag&b);}
 void checkMallocRelease();void setMallocInfo(int,void*);void setLoadToAram();void setLoadToMram();int setClear();int setDelete();
 void checkLoadToMram(){assert(false);}void checkLoadToAram(){assert(false);}void checkAramToMram(){assert(false);}void checkMramToAram(){assert(false);}
 void setCommand(int,u32,u8){assert(false);}
};
struct Ctrl {cDataUnit m_DataUnit[32];int dbgHeap=0;void* m_DummyDataMem=nullptr;u32 getAramFree(u32){return 0x900000;}void setDummyId(int){assert(false);}} DC;
struct Global{int dev_mode=0;} global,*pG=&global;
struct Log{void err(int,int,const char*,...){assert(false);}} test_log,*pLog=&test_log;
struct FakeQueue{bool chk(int){assert(false);return false;}void Read(){assert(false);}};
struct DvdStub{FakeQueue* pCur_queue=nullptr;void ReadCancel(int,int){assert(false);}int ReadCheck(int,void*,void*,void*){assert(false);return 0;}} Dvd;
struct AramStub{int DmaTransReq(int,u32,u32,u32,int){assert(false);return -1;}void DmaCancel(int){assert(false);}} Aram;
unsigned allocs=0,frees=0,prepares=0,installs=0,moves=0;bool fail_alloc=false,fail_io=false;
void* MemAlloc(u32 n){if(fail_alloc)return nullptr;++allocs;return malloc(n);}
#define MEM_ALLOC(n,a,b) MemAlloc(n)
void* Debug_alloc(u32 n,int){return MemAlloc(n);}
void Mem_free_h(void* p,int){++frees;free(p);}void Debug_free_h(void* p,int h){Mem_free_h(p,h);}
int MemGetCurrentDbgHeap(){return 0;}int MemGetCurrentHeap(){return 0;}
void OSReport(const char*,...){}void DCFlushRange(void*,u32){}
int DvdReadN(const char*,void*,u32,int,int,int,const char*,int){assert(false);return -1;}
extern "C" int re4dc_event_file_name(const char* n){return !strncmp(n,"evd/",4);}
extern "C" int re4dc_event_file_prepare(const char*,unsigned){++prepares;return !fail_io;}
extern "C" int re4dc_event_file_install(const char*,unsigned n,void* p){++installs;if(fail_io)return 0;memset(p,0x42,n);return 1;}
extern "C" void re4dc_event_file_moved(){++moves;}
extern "C" void re4dc_event_file_reject_swap(){throw std::runtime_error("mutable backing required");}
'''
        names=['extern "C" int re4dc_event_file_range','void cDataUnit::checkMallocRelease','void cDataUnit::setMallocInfo',
               'void cDataUnit::setLoadToMram','void cDataUnit::setLoadToAram','int cDataUnit::setClear','int cDataUnit::setDelete']
        swap=function((ROOT/'src/game/dvd.cpp').read_text(),'void MemorySwap')
        code=header+'\n'+'\n'.join(function(source,n) for n in names)+'\n'+swap+r'''
int main(){
 auto& u=DC.m_DataUnit[0];for(auto& v:DC.m_DataUnit)v.m_be_flag=0;u.m_be_flag=1;
 u.setLoadToAram();assert(u.m_condition==4 && u.m_be_flag==5 && prepares==1 && !allocs);
 assert(re4dc_event_file_range(0x900000,32));assert(!re4dc_event_file_range(0x900020,32));
 assert(re4dc_event_file_range(0x8fffff,2));assert(!re4dc_event_file_range(0x8fffff,1));
 unsigned char untouched[64];memset(untouched,0x35,sizeof(untouched));bool rejected=false;
 try{MemorySwap(untouched,0x900000,32);}catch(const std::runtime_error&){rejected=true;}
 assert(rejected);for(auto c:untouched)assert(c==0x35);
 // Rounding must not sneak across the boundary after the preflight.
 rejected=false;try{MemorySwap(untouched,0x8fffff,1);}catch(const std::runtime_error&){rejected=true;}assert(rejected);
 for(int i=0;i<100;++i){u.arg=0x800000+i*32;u.m_command=2;u.setLoadToAram();assert(u.m_command==0);}
 assert(prepares==1 && !installs && !allocs && moves==100 && !re4dc_event_file_range(0x900000,32));
 u.arg=0;fail_alloc=true;u.setLoadToMram();assert(u.m_err==1 && u.m_condition==4 && !allocs);fail_alloc=false;u.m_err=0;
 fail_io=true;u.setLoadToMram();assert(u.m_err==2 && u.m_condition==4 && frees==allocs);fail_io=false;u.m_err=0;
 u.setLoadToMram();assert(u.m_condition==2 && ((char*)u.m_addr)[31]==0x42);void* retained=u.m_addr;
 u.setLoadToAram();assert(u.m_err==3 && u.m_addr==retained && u.m_condition==2 && allocs==frees+1);
 u.setClear();assert(!u.m_condition && !u.m_addr && u.m_be_flag==1 && frees==allocs);
 u.m_err=0;u.wait=1;u.setLoadToAram();assert(u.m_condition==4 && prepares==2);u.setDelete();assert(!u.m_be_flag && !u.m_size);
 // Fixed/caller-owned backing survives failed reads and clear/retry.
 unsigned char borrowed[32];u=cDataUnit{};u.setLoadToAram();u.m_fix_addr=(u32)borrowed;
 unsigned prior_frees=frees;fail_io=true;u.setLoadToMram();assert(u.m_condition==4 && frees==prior_frees);
 fail_io=false;u.m_err=0;u.setLoadToMram();assert(u.m_addr==borrowed && !(u.m_be_flag&2));
 u.setClear();assert(frees==prior_frees && borrowed[0]==0x42);
 u=cDataUnit{};fail_io=true;u.setLoadToAram();assert(u.m_condition==0 && !(u.m_be_flag&4));
}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile_run(Path(tmp),code)

if __name__=='__main__':unittest.main()
