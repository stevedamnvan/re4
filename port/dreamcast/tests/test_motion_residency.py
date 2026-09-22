"""Real native cache/storage implementation; synthetic assets remain redistributable."""
from pathlib import Path
import json, os, shutil, struct, subprocess, sys, tempfile, unittest, zlib
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'port/dreamcast/tools'))
from prepare_native_ui import compact_spans

def fixture(root, clips=None, hot=None):
    if clips is None:
        clips=[]
        for i in range(5):
            clip=bytearray([i+1]*128);struct.pack_into('<HB',clip,0,10,2)
            struct.pack_into('<2H',clip,3,0,0);clip[7:9]=bytes([0,1])
            clip[9:12]=bytes(3);struct.pack_into('<3I',clip,12,128,32,64)
            clips.append(bytes(clip))
    hot=hot or {0}
    n=len(clips)+1;first=(16+8*n+31)&~31
    a=bytearray(first);struct.pack_into('<I',a,0,n);entries=[];proxies=[]
    (root/'mot').mkdir()
    for i,clip in enumerate(clips):
        off=len(a);proxies.append(off);parts=clip[2]
        head=((3+3*parts+3)&~3)+4+4*parts
        a+=clip[:head]+bytes((-head)%32)
        struct.pack_into('<I',a,16+4*i,off);a[16+4*n+4*i:20+4*n+4*i]=b'FCV\0'
        crc=zlib.crc32(clip)&0xffffffff;fnv=2166136261
        for b in clip:fnv=((fnv^b)*16777619)&0xffffffff
        (root/'mot'/('%08x-%08x.fcv'%(crc,fnv))).write_bytes(clip)
        entries.append((off,len(clip),crc,fnv,int(i in hot)))
    table=len(a);records=b''.join(struct.pack('<5I',*e) for e in entries)
    size=(32+len(records)+31)&~31;total=len(a)+size+64
    a+=struct.pack('<8s6I',b'R4MOTBL\0',2,len(clips),20,zlib.crc32(records)&0xffffffff,total,32768)+records+bytes(size-32-len(records))+bytes(64)
    struct.pack_into('<I',a,4,len(a)-64);struct.pack_into('<I',a,16+4*(n-1),table)
    a[16+4*n+4*(n-1):20+4*n+4*(n-1)]=b'MTC\0'
    (root/'archive').write_bytes(a)
    return a,proxies

def headers(root):
    (root/'kos').mkdir(exist_ok=True)
    (root/'kos/fs.h').write_text('#pragma once\n#include <sys/types.h>\nusing file_t=int;\n#define FILEHND_INVALID -1\nint fs_open(const char*,int);int fs_close(int);ssize_t fs_total(int);ssize_t fs_read(int,void*,size_t);\n')
    (root/'kos.h').write_text('#pragma once\n#include <kos/fs.h>\n#include <fcntl.h>\n#include <cstdint>\nextern thread_local void* thd_current;\nint irq_disable();void irq_restore(int);void thd_pass();std::uint64_t timer_us_gettime64();\n')
    (root/'kos/net.h').write_text('#pragma once\n#include <cstdint>\nstd::uint32_t net_crc32le(const std::uint8_t*,int);\n')
    (root/'kos/mutex.h').write_text('#pragma once\n#include <mutex>\nusing mutex_t=std::mutex;\n#define MUTEX_INITIALIZER {}\ninline int mutex_lock(mutex_t* p){p->lock();return 0;}\ninline int mutex_unlock(mutex_t* p){p->unlock();return 0;}\n')

SUPPORT=r"""
#include "native_motion.h"
#include <kos.h>
#include <zlib.h>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <thread>
#include <atomic>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
thread_local void* thd_current=reinterpret_cast<void*>(1);
std::recursive_mutex irq;thread_local unsigned irq_depth;
int irq_disable(){irq.lock();++irq_depth;return 0;}void irq_restore(int){--irq_depth;irq.unlock();}
void thd_pass(){std::this_thread::yield();}
std::uint64_t timer_us_gettime64(){return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
std::uint32_t net_crc32le(const std::uint8_t* p,int n){return ::crc32(0,p,n);}
std::string root;
std::map<void*,unsigned> allocations;unsigned heap_live,heap_peak,reads;std::uint64_t read_bytes;
std::atomic<bool> block_read{},read_entered{},let_read_finish{};
extern "C" void re4dc_log(const char*,...){}
extern "C" void re4dc_missing(const char* reason){throw std::runtime_error(reason);}
extern "C" int re4dc_motion_current_heap(){return 4;}
extern "C" void* re4dc_motion_alloc(unsigned n){
 auto p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);
 if(p==MAP_FAILED)return nullptr;allocations[p]=n;heap_live+=n;if(heap_live>heap_peak)heap_peak=heap_live;return p;
}
extern "C" void re4dc_motion_free(void* p){assert(allocations.count(p));unsigned n=allocations.at(p);heap_live-=n;allocations.erase(p);munmap(p,n);}
int fs_open(const char* p,int f){std::string path(p);if(path.rfind("/cd/dc/",0)==0)path=root+path.substr(6);return open(path.c_str(),f);}
int fs_close(int f){return close(f);}ssize_t fs_total(int f){struct stat s;return fstat(f,&s)?-1:s.st_size;}
ssize_t fs_read(int f,void* p,size_t n){
 if(block_read){read_entered=true;while(!let_read_finish)std::this_thread::yield();}
 auto got=read(f,p,n);if(got>0){++reads;read_bytes+=got;}return got;
}
unsigned word(const unsigned char* p){unsigned v;memcpy(&v,p,4);return v;}
std::vector<unsigned char> read_bytes_file(const std::string& p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
void* proxy(std::vector<unsigned char>& a,unsigned i){return a.data()+word(a.data()+16+4*i);}
void verify_keys(const void* p,unsigned* t){
 const auto* h=static_cast<const unsigned char*>(p);unsigned n=h[2],head=((3+3*n+3)&~3U)+4+4*n;
 auto* cached=reinterpret_cast<unsigned char*>(t)-head+4*n;
 for(unsigned j=0;j<n;++j)assert(t[j]==reinterpret_cast<std::uintptr_t>(cached)+word(h+head-4*n+4*j));
}
"""
CHECKS=r"""
int main(int argc,char** argv){
 assert(argc==2);root=argv[1];auto a=read_bytes_file(root+"/archive");auto pristine=a;
 // Header corruption is rejected before native consumers or allocation.
 auto bad=a;bad[word(a.data()+16+4*(word(a.data())-1))+8]=1;
 assert(!re4dc_motion_bind(bad.data(),bad.size()) && !heap_live);
 // Invalid counts/ranges/flags/relative key offsets must fail before prefetch.
 const unsigned mtc=word(a.data()+16+4*(word(a.data())-1));
 for(unsigned test=0;test<7;++test){
  auto broken=a;auto put=[&](unsigned at,unsigned v){memcpy(broken.data()+at,&v,4);};
  switch(test){
   case 0:put(mtc+12,0xffffffffU);break;
   case 1:put(mtc+24,broken.size()+32);break;
   case 2:put(mtc+32,32);break;
   case 3:put(mtc+32+16,2);break;
   case 4:put(mtc+32+4,32769);break;
   case 5:put(word(broken.data()+mtc+32)+16,1);break;
   case 6:put(4,mtc+16);break;
  }
  if(test>=2 && test<=4)put(mtc+20,net_crc32le(broken.data()+mtc+32,word(a.data()+mtc+12)*20));
  assert(!re4dc_motion_bind(broken.data(),broken.size()) && !heap_live);
 }

 assert(re4dc_motion_bind(a.data(),a.size()));Re4dcMotionStats warm{};
 re4dc_motion_get_stats(&warm);assert(warm.loads==1 && warm.resident_bytes==128);
 // A complete unchanged set fits: hot clip plus two cold clips, repeated 100x.
 for(unsigned cycle=0;cycle<100;++cycle)for(unsigned i=0;i<3;++i){
  unsigned* keys=nullptr;auto p=proxy(a,i);unsigned n=static_cast<unsigned char*>(p)[2];
  auto* restored=reinterpret_cast<unsigned*>(static_cast<unsigned char*>(p)+((3+3*n+3)&~3U)+4);
  { Re4dcMotionLease lease(p,&keys,restored);assert(lease.external());verify_keys(p,keys); }
  assert(keys==restored && re4dc_motion_thread_busy(thd_current)==0);
 }
 Re4dcMotionStats steady{};re4dc_motion_get_stats(&steady);
 assert(steady.loads==3 && steady.misses==3 && reads==3 && steady.evictions==0);
 // Keep one cold entry pinned while replacement needs space; it survives.
 unsigned* held=nullptr;int token=re4dc_motion_acquire(proxy(a,1),&held);verify_keys(proxy(a,1),held);
 unsigned* temp=nullptr;int next=re4dc_motion_acquire(proxy(a,3),&temp);re4dc_motion_release(next);
 verify_keys(proxy(a,1),held);re4dc_motion_release(token);
 assert(a==pristine); // no pointer fixup leaks into the stable archive
 // Evict/reload every cold clip, checking ALL relocated pointers on every load.
 for(unsigned cycle=0;cycle<4;++cycle)for(unsigned i=1;i<5;++i){int t=re4dc_motion_acquire(proxy(a,i),&temp);verify_keys(proxy(a,i),temp);re4dc_motion_release(t);}
 unsigned before=reads;for(unsigned k=0;k<100;++k){int t=re4dc_motion_acquire(proxy(a,0),&temp);re4dc_motion_release(t);}assert(reads==before);
 // Cross-thread observation remains busy during a yielding miss AND evaluation.
 re4dc_motion_unbind(a.data());assert(!heap_live);assert(re4dc_motion_bind(a.data(),a.size()));
 block_read=true;std::atomic<bool> pinned{},finish{};
 std::thread worker([&]{thd_current=reinterpret_cast<void*>(2);unsigned* t=nullptr;int lease=re4dc_motion_acquire(proxy(a,4),&t);pinned=true;while(!finish)std::this_thread::yield();verify_keys(proxy(a,4),t);re4dc_motion_release(lease);});
 while(!read_entered)std::this_thread::yield();assert(re4dc_motion_thread_busy(reinterpret_cast<void*>(2)));
 let_read_finish=true;while(!pinned)std::this_thread::yield();assert(re4dc_motion_thread_busy(reinterpret_cast<void*>(2)));
 finish=true;worker.join();assert(!re4dc_motion_thread_busy(reinterpret_cast<void*>(2)));block_read=false;
 Re4dcMotionStats out{};re4dc_motion_get_stats(&out);
 re4dc_motion_retire_all();assert(!heap_live && allocations.empty() && a==pristine);
 printf("{\"steady_loads\":%u,\"steady_repetitions\":100,\"loads\":%u,\"misses\":%u,\"bytes_read\":%llu,\"peak_cache_bytes\":%u,\"peak_pinned_bytes\":%u,\"worst_host_wait_us\":%llu}\n",steady.loads,out.loads,out.misses,out.bytes_read,out.peak_cache_bytes,out.peak_pinned_bytes,out.worst_wait_us);
}
"""

def compile_fixture(root, extra=(), main=CHECKS):
    headers(root);src=root/'cache.cpp';src.write_text(SUPPORT+main);exe=root/'check'
    command=['g++','-std=c++20','-O1','-g','-pthread','-fno-pie','-no-pie','-I'+str(root),'-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(src),str(ROOT/'port/dreamcast/game/platform/native_motion.cpp'),str(ROOT/'port/dreamcast/room/room_storage.cpp'),*map(str,extra),'-lz','-o',str(exe)]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return exe

@unittest.skipUnless(shutil.which('g++'),'host compiler needed')
class MotionResidency(unittest.TestCase):
    def test_retention_eviction_pointers_and_yielding_owner(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixture(root);exe=compile_fixture(root)
            result=subprocess.run([str(exe),str(root)],check=True,capture_output=True,text=True)
            report=json.loads(result.stdout);self.assertEqual(report['steady_loads'],3)
            self.assertEqual(report['peak_cache_bytes'],384);self.assertEqual(report['peak_pinned_bytes'],256)

    def test_actual_cancel_hook_drains_io_and_pin_before_destroy(self):
        # Compile the actual source cancellation function with observed KOS
        # boundary substitutes, together with the real cache/storage code.
        source=(ROOT/'port/dreamcast/game/platform/os.cpp').read_text()
        start=source.index('void OSCancelThread(OSThread* thread)')
        stop=source.index('\nOSPriority OSGetThreadPriority',start)
        hook=source[start:stop]
        scheduler=(ROOT/'src/game/scheduler.cpp').read_text()
        start=scheduler.index('void TaskKill(TASK* t)\n{')
        stop=scheduler.index('\n// Suspends slot',start)
        kill=scheduler[start:stop]
        setup=r"""
constexpr int STATE_WAIT=3,STATE_READY=1,OS_THREAD_STATE_MORIBUND=8;
struct NativeThread { int state=STATE_WAIT;void* wait_obj; };
struct OSThread { NativeThread* kt;int suspend=1,gateCount=1,state=0;unsigned nativeIoDepth=0; };
int g_gate;std::atomic<bool> destroyed{};unsigned unparks;
constexpr int TASK_NONE=0,TASK_EXEC=1,TASK_SLEEP=2,TASK_RUN=3,TASK_SUSPEND=128;
struct TASK { OSThread Thread;int Status=TASK_RUN,suspend_cnt=0; };
OSThread current_thread{};unsigned self_exits;
OSThread* OSGetCurrentThread(){return &current_thread;}
void TaskExit(){++self_exits;}
void unpark(OSThread* t){++unparks;t->kt->state=STATE_READY;}
void thd_add_to_runnable(NativeThread*,bool){}
void thd_destroy(NativeThread* t){assert(irq_depth && !re4dc_motion_thread_busy(t));destroyed=true;}
"""
        main=r"""
int main(int argc,char**argv){
 assert(argc==2);root=argv[1];auto a=read_bytes_file(root+"/archive");
 assert(re4dc_motion_bind(a.data(),a.size()));NativeThread native{STATE_WAIT,&g_gate};TASK task{{&native}};auto& target=task.Thread;
 block_read=true;std::atomic<bool> lease_checked{};
 std::thread worker([&]{thd_current=&native;unsigned* t=nullptr;int token=re4dc_motion_acquire(proxy(a,4),&t);
  assert(!destroyed);verify_keys(proxy(a,4),t);lease_checked=true;re4dc_motion_release(token);});
 while(!read_entered)std::this_thread::yield();
 std::thread completion([&]{std::this_thread::sleep_for(std::chrono::milliseconds(5));assert(!destroyed);let_read_finish=true;});
 TaskKill(&task);worker.join();completion.join();
 assert(!self_exits && task.Status==TASK_NONE);
 assert(destroyed && lease_checked && unparks && !target.kt && target.state==OS_THREAD_STATE_MORIBUND);
 assert(!target.suspend && !target.gateCount);re4dc_motion_retire_all();assert(!heap_live);
 // DVD-only ownership must drain too, even with no motion pin or cache lock.
 target.kt=&native;target.nativeIoDepth=1;task.Status=TASK_RUN;destroyed=false;
 std::thread dvd_completion([&]{std::this_thread::sleep_for(std::chrono::milliseconds(5));
  int old=irq_disable();assert(!destroyed);target.nativeIoDepth=0;irq_restore(old);});
 TaskKill(&task);dvd_completion.join();assert(destroyed && !target.kt && !target.nativeIoDepth);

}
"""
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fixture(root);exe=compile_fixture(root,main="#define RE4DC_GAME 1\n"+setup+hook+kill+main)
            subprocess.run([str(exe),str(root)],check=True,capture_output=True,text=True,timeout=20)

    def test_span_insertion_and_rejection(self):
        original=bytearray(128);struct.pack_into('<I',original,16,64)
        out,mapped=compact_spans(original,[(16,0,64)],[(32,32,bytes(32)),(64,96,bytes(16))])
        self.assertEqual(mapped(32),64);self.assertEqual(struct.unpack_from('<I',out,16)[0],96)
        self.assertEqual(len(out),144)
        with self.assertRaises(ValueError):compact_spans(original,[(16,0,80)],[(64,96,bytes(16))])

    def test_powerpc_evaluation_and_loader_unchanged(self):
        for path in ['src/game/motion.cpp','src/game/read.cpp','src/game/dvd.cpp','src/game/cam_motion.cpp','src/game/shape.cpp','src/game/scheduler.cpp']:
            original=subprocess.check_output(['git','show','0518c93:'+path],cwd=ROOT,text=True)
            current=(ROOT/path).read_text()
            def pp(s):
                s='\n'.join(x for x in s.splitlines() if not x.startswith('#include'))
                return subprocess.check_output(['g++','-E','-P','-x','c++','-D__PPC__','-'],input=s,text=True)
            self.assertEqual(pp(current),pp(original),path)

if __name__=='__main__':unittest.main()
