"""Execute actual native task bodies with both dispatch/completion orderings."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which("g++"), "host g++ required")
class TaskExitOwnershipTests(unittest.TestCase):
    def test_native_counted_handoff_and_actual_owner(self):
        source = (ROOT / "src/game/scheduler.cpp").read_text()
        helper = source[source.index('#if !defined(__PPC__)\n#include "native_io.h"'):source.index("void TaskKill(TASK* t);")]
        dispatch = source[source.index("void TaskSchedulerMain(TASK* t)"):source.index("// Debug: prints how much")]
        hook = source[source.index("void* TaskExec_hook(void* value)"):source.index("// Starts `func(arg)`")]
        operations = source[source.index("void TaskSleep(int frames)"):source.index("// Kills the task in slot")]
        body = (helper + dispatch + hook + operations).replace('#include "native_io.h"', '')
        fixture = r'''
#include <cassert>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <cstddef>
#include <initializer_list>
using u32=unsigned;
constexpr unsigned TASK_NUM=18,TASK_ISR=4,TASK_NONE=0,TASK_SLEEP=2,TASK_EXEC=1,TASK_SUSPEND=128,TASK_RUN=3;
using TaskFunc=void(*)();
struct OSSemaphore { std::mutex m;std::condition_variable cv;int count=0; };
struct OSThread { int id; };
struct TASK { OSThread Thread;int Status,suspend_cnt,Priority,SleepCtr,Queue,arg,flag,StackSize;void* pStack;void*(*hook)(void*);void(*pFunc)(int); };
TASK Task[TASK_NUM];TASK* pCTask;
#define CTASK pCTask
struct Global { unsigned Status_flg[2]{}; } global;
Global* pG=&global;OSThread* pParentThread;
OSSemaphore Sema;
OSThread outsider{-1};thread_local OSThread* actual=&outsider;
std::thread workers[TASK_NUM];bool early_completion=false;
std::atomic<int> enters{0},finishes{0},panics{0},exits{0},queue_sleeps{0},queue_wakes{0};
std::atomic<int> phase[TASK_NUM];
struct ThreadExit{};
void* TaskExec_hook(void*);
void GXSetCurrentGXThread(){}
void StackOverflowCheck(TASK*){}
OSThread* OSGetCurrentThread(){return actual;}
void OSPanic(const char*,int,const char*){++panics;}
void OSInitSemaphore(OSSemaphore* s,int n){std::lock_guard<std::mutex> l(s->m);s->count=n;}
void OSWaitSemaphore(OSSemaphore* s){std::unique_lock<std::mutex> l(s->m);s->cv.wait(l,[&]{return s->count>0;});--s->count;}
void OSSignalSemaphore(OSSemaphore* s){{std::lock_guard<std::mutex> l(s->m);++s->count;}s->cv.notify_one();}
void OSExitThread(void* p){assert(p==actual);++exits;throw ThreadExit{};}
void OSSleepThread(int* q){assert(q==&Task[TASK_ISR].Queue);++queue_sleeps;}
void OSWakeupThread(int* q){assert(q==&Task[TASK_ISR].Queue);++queue_wakes;}
void OSCreateThread(OSThread*,void*(*)(void*),void*,void*,int,int,int);
void OSResumeThread(OSThread*);
'''
        checks = r'''
void OSCreateThread(OSThread* t,void*(*)(void*),void*,void*,int,int,int){
    if(workers[t->id].joinable())workers[t->id].join();
}
void OSResumeThread(OSThread* t){
    assert(t->id>=0 && t->id<(int)TASK_NUM);
    int id=t->id;
    // Force the original failing order: caller continues before hook enters.
    workers[id]=std::thread([=]{
        actual=t;
        if(!early_completion)std::this_thread::sleep_for(std::chrono::milliseconds(3));
        try{TaskExec_hook((void*)(size_t)Task[id].arg);}catch(ThreadExit){}
    });
    if(early_completion && id!=(int)TASK_ISR){
        // The reverse race: child yields before caller even starts its wait.
        auto& s=nativeTaskYielded[id];std::unique_lock<std::mutex> l(s.m);
        s.cv.wait(l,[&]{return s.count>0;});
    }
}
void start(int id,void(*fn)(int)){
    Task[id].Thread.id=id;Task[id].Status=TASK_EXEC;Task[id].pFunc=fn;
    Task[id].Priority=14;Task[id].arg=17;Task[id].flag=6;
    pCTask=&Task[id];TaskSchedulerMain(&Task[id]);
}
void awake(int id){pCTask=&Task[id];TaskSchedulerMain(&Task[id]);}
void sleeper(int arg){
    assert(arg==17);int id=actual->id;++enters;
    for(int i=0;i<50;++i){
        phase[id]=i+1;
        TaskSleep(2);
    }
    ++finishes;
}
void nested(int){
    start(15,sleeper);
    for(int i=0;i<50;++i){
        assert(Task[15].Status==TASK_SLEEP && phase[15]==i+1);
        awake(15);assert(Task[15].Status==TASK_SLEEP && Task[15].SleepCtr==1);
        awake(15);
    }
    assert(Task[15].Status==TASK_RUN && finishes==1);
    workers[15].join();
    TaskExit();
}
int main(){
    for(unsigned i=0;i<TASK_NUM;++i)Task[i].Thread.id=i;
    for(bool early:{false,true}){
        early_completion=early;enters=0;finishes=0;
        // Nested cSceSys caller cannot mistake an unstarted/yielding child for
        // a normally returned TASK_RUN. Delay and resume tokens are per slot.
        start(1,nested);workers[1].join();
        assert(Task[1].Status==TASK_NONE && enters==1 && finishes==1);
        assert(nativeTaskYielded[1].count==0 && nativeTaskYielded[15].count==0);
        assert(nativeTaskResume[15].count==0);
        // Slot reuse must not consume stale completion or resume tokens.
        start(1,[](int){TaskSleep(0);TaskChain(nullptr,42);});workers[1].join();
        assert(Task[1].Status==TASK_EXEC && Task[1].arg==42);
        start(1,[](int){TaskExit();});workers[1].join();assert(Task[1].Status==TASK_NONE);
    }
    // Source hold leaves a task unstarted and does not consume any semaphore.
    global.Status_flg[1]=0x10000000;Task[2].flag=0;Task[2].Status=TASK_EXEC;
    TaskSchedulerMain(&Task[2]);assert(!workers[2].joinable());global.Status_flg[1]=0;
    // Self operations retain actual owner when source cursor is stale.
    pCTask=(TASK*)-1;actual=&Task[3].Thread;Task[3].Status=TASK_RUN;
    try{TaskExit();assert(false);}catch(ThreadExit){}
    assert(Task[3].Status==TASK_NONE && nativeTaskYielded[3].count==1);
    // ISR remains independent: it never publishes a regular dispatch token.
    actual=&Task[TASK_ISR].Thread;Task[TASK_ISR].Status=TASK_RUN;
    TaskSleep(1);assert(queue_sleeps==1);awake(TASK_ISR);assert(queue_wakes==1);
    try{TaskExit();assert(false);}catch(ThreadExit){}
    assert(nativeTaskYielded[TASK_ISR].count==0 && nativeTaskResume[TASK_ISR].count==0);
    actual=&outsider;int e=exits;TaskExit();assert(panics==1 && exits==e);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "owner.cpp"
            exe = pathlib.Path(tmp) / "owner"
            src.write_text(fixture + body + checks)
            result = subprocess.run(["g++", "-std=c++17", "-fpermissive", "-pthread",
                                     "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                                     str(src), "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(exe)], check=True, timeout=20)


if __name__ == "__main__":
    unittest.main()
