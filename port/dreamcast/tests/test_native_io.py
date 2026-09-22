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
if __name__=='__main__':unittest.main()
