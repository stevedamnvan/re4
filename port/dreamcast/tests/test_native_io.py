"""Source ISR timeslicing must not park the owner of native filesystem locks."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
class NativeIo(unittest.TestCase):
    def test_actual_dvd_io_scope_defers_suspend_until_locks_and_callback_finish(self):
        os=(ROOT/'port/dreamcast/game/platform/os.cpp').read_text()
        hooks=os[os.index('void* re4dc_io_begin()'):os.index('void OSExitThread(void* val)')]
        scheduler=(ROOT/'src/game/scheduler.cpp').read_text()
        suspend=scheduler[scheduler.index('void iTaskSuspend()'):scheduler.index('// 1 while an ISR task runs.')]
        setup=r"""
#include <cassert>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include "native_io.h"
using u32=unsigned long;
struct OSThread {int state=2;unsigned nativeIoDepth=0;};
struct TASK {OSThread Thread;unsigned Status=3;};
constexpr int TASK_ISR=4,TASK_SUSPEND=128;
TASK Task[5];int iTask_exec_flg=1;void* thd_current=&Task[4].Thread;
int irq_disable(){return 0;}void irq_restore(int){}
void thd_sleep(int){}
OSThread* threadOf(void* p){return static_cast<OSThread*>(p);}
void re4dc_missing(const char* s){throw std::runtime_error(s);}
unsigned suspended,fs_calls;bool fail_open,fail_read,lock_held;
void OSSuspendThread(OSThread*){assert(!lock_held);++suspended;}
void re4dc_set_stage(unsigned long){}void re4dc_log(const char*,...){}
"""
        fs=r"""
void probe(){assert(re4dc_io_busy(thd_current));unsigned before=suspended;iTaskSuspend();assert(before==suspended);++fs_calls;}
int fs_open(const char*,int){lock_held=true;probe();lock_held=false;return fail_open?-1:1;}
long fs_total(int){probe();return 64;}
int fs_close(int){lock_held=true;probe();lock_held=false;return 0;}
long fs_seek(int,long,int){probe();return 0;}
long fs_read(int,void* p,unsigned long n){lock_held=true;probe();lock_held=false;if(fail_read)return -1;memset(p,7,n);return n;}
"""
        main=r"""
unsigned callbacks;long result;
void complete(long n,DVDFileInfo*){probe();++callbacks;result=n;}
int main(){
 DVDFileInfo f{};assert(DVDOpen("em/test.drs",&f));assert(!re4dc_io_busy(thd_current));
 char bytes[64];DVDReadAsyncPrio(&f,bytes,64,0,complete,2);
 assert(result==64 && callbacks==1 && bytes[0]==7 && !suspended && !lock_held);
 assert(!re4dc_io_busy(thd_current));iTaskSuspend();assert(suspended==1);
 Task[4].Status=3;fail_open=true;DVDReadAsyncPrio(&f,bytes,64,0,complete,2);
 assert(result==-1 && callbacks==2 && !re4dc_io_busy(thd_current));
 fail_open=false;fail_read=true;DVDReadAsyncPrio(&f,bytes,64,0,complete,2);
 assert(result==0 && callbacks==3 && !re4dc_io_busy(thd_current));
 {Re4dcIoScope a;{Re4dcIoScope b;assert(Task[4].Thread.nativeIoDepth==2);}
  assert(re4dc_io_busy(thd_current));}assert(!re4dc_io_busy(thd_current));
 assert(fs_calls>10);
}
"""
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'kos.h').write_text('#pragma once\n#include <cstdio>\nusing file_t=int;\n#define O_RDONLY 0\nint fs_open(const char*,int);long fs_total(int);int fs_close(int);long fs_seek(int,long,int);long fs_read(int,void*,unsigned long);\n')
            (p/'re4dc_platform.h').write_text('')
            cpp=p/'check.cpp';cpp.write_text(setup+hooks+suspend+fs+'\n'+(ROOT/'port/dreamcast/game/platform/dvd.cpp').read_text()+main)
            exe=p/'check';subprocess.run(['g++','-std=c++17','-I'+str(p),'-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    def test_source_queue_step_reentry_control_and_guard(self):
        source=(ROOT/'src/game/dvd.cpp').read_text()
        step=source[source.index('int cDvdQueue::Read()'):source.index('// Fills the slot')]
        platform=(ROOT/'port/dreamcast/game/platform/dvd.cpp').read_text()
        guard=platform[platform.index('namespace { void* dvd_step_owner; }'):platform.index('typedef signed char s8;')]
        os=(ROOT/'port/dreamcast/game/platform/os.cpp').read_text()
        hooks=os[os.index('void* re4dc_io_begin()'):os.index('void OSExitThread(void* val)')]
        setup=r"""
#include <cassert>
#include <stdexcept>
#include "native_io.h"
struct OSThread {unsigned nativeIoDepth=0;};
OSThread workers[2];void* thd_current=&workers[0];unsigned waits=0;
OSThread* threadOf(void* p){return (OSThread*)p;}
int irq_disable(){return 0;}void irq_restore(int){}
void thd_sleep(int){++waits;}
void re4dc_missing(const char* s){throw std::runtime_error(s);}
struct Global {unsigned System_flg=0;} global,*pG=&global;
struct cDvdQueue {
 unsigned m_Rno0=1,step=1,flags=1,reads=0;bool pcMode=false;
 void readInit(){} void readCancelWait(){} void readExit(){}
 int chk(unsigned mask){return (flags&mask)!=0;}
 void readMain();int Read();
};
bool in_read=false;
"""
        run=r"""
void cDvdQueue::readMain(){
 switch(step){
 case 1:
  ++reads;
  if(!in_read){
   in_read=true;
#ifdef RE4DC_GAME
   assert(re4dc_io_busy(thd_current));
#endif
   // The actual KOS read can yield before the source's step++ below.
   // The foreground block-read path also pumps this same background queue.
   thd_current=&workers[1];assert(Read()==1);assert(Read()==1);
   thd_current=&workers[0];in_read=false;
  }
  ++step;break;
 case 2:++step;break;
 case 3:step=0;flags=0;break;
 }
}
int main(){
 cDvdQueue q;assert(q.Read()==1);
#ifdef RE4DC_GAME
 assert(q.step==2 && q.reads==1 && waits==2);
 assert(!workers[0].nativeIoDepth && !workers[1].nativeIoDepth);
 assert(q.Read()==1 && q.step==3);assert(q.Read()==0 && q.step==0);
 // Reuse after completion must acquire normally, including a different worker.
 thd_current=&workers[1];q.step=2;q.flags=1;assert(q.Read()==1);
 assert(q.step==3 && !workers[1].nativeIoDepth && !dvd_step_owner);
#else
 // Demonstrates the precise invalid step seen in target em12 snapshots.
 assert(q.step==4 && q.reads==2);
#endif
 assert(pG->System_flg==0);
}
"""
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);cpp=p/'check.cpp';cpp.write_text(setup+hooks+guard+step+run)
            for enabled in (False,True):
                exe=p/('guard' if enabled else 'control')
                subprocess.run(['g++','-std=c++17','-fsanitize=address,undefined',
                  '-I'+str(ROOT/'port/dreamcast/game/platform/include'),
                  *(['-DRE4DC_GAME=1'] if enabled else []),str(cpp),'-o',str(exe)],check=True)
                subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
