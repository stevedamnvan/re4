"""Execute the actual Dreamcast TaskExit body with a stale scheduling cursor."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which("g++"), "host g++ required")
class TaskExitOwnershipTests(unittest.TestCase):
    def test_native_exit_uses_os_thread_owner(self):
        source = (ROOT / "src/game/scheduler.cpp").read_text()
        begin = source.index("void TaskExit()")
        end = source.index("// Kills the task in slot", begin)
        helper_start = source.index('#if !defined(__PPC__)\n#include "native_io.h"')
        helper_end = source.index("void TaskKill(TASK* t);", helper_start)
        sleep_start = source.index("void TaskSleep(int frames)")
        dispatch_start = source.index("void TaskSchedulerMain(TASK* t)")
        dispatch_end = source.index("// Debug: prints how much", dispatch_start)
        body = (source[helper_start:helper_end] + source[dispatch_start:dispatch_end] + source[sleep_start:end]).replace('#include "native_io.h"', '')
        fixture = r'''
#include <cassert>
#include <cstddef>
using u32 = unsigned;
constexpr unsigned TASK_NUM = 18, TASK_ISR = 4, TASK_NONE = 0, TASK_SLEEP = 2, TASK_EXEC = 1, TASK_SUSPEND = 128, TASK_RUN = 3;
using TaskFunc = void(*)();
struct OSThread { int id; };
struct TASK { OSThread Thread; int Status, suspend_cnt, Priority, SleepCtr, Queue, arg, flag, StackSize; void* pStack; void* (*hook)(void*); void (*pFunc)(int); };
TASK Task[TASK_NUM];
TASK* pCTask;
#define CTASK pCTask
struct Global { unsigned Status_flg[2]; } global;
Global* pG=&global;
OSThread* pParentThread;
OSThread outsider, parent, *actual;
int Sema, resumes, signals, exits, panics, sleeps, suspends;
bool switch_parent_on_wake;void change_dispatch_on_sleep();
void* TaskExec_hook(void*) { return nullptr; }
void GXSetCurrentGXThread() {}
void OSSuspendThread(OSThread* p) { assert(p == &parent); ++suspends; }
void OSSleepThread(int* q) { assert(q == &Task[actual->id].Queue); pCTask = reinterpret_cast<TASK*>(-1); ++sleeps; if(switch_parent_on_wake)change_dispatch_on_sleep(); }
void OSWakeupThread(int*) {}
void OSWaitSemaphore(int*) {}
void OSCreateThread(OSThread*,void*(*)(void*),void*,void*,int,int,int) {}
void StackOverflowCheck(TASK*) {}
OSThread* OSGetCurrentThread() { return actual; }
OSThread* ParentThread() { return &parent; }
void OSResumeThread(OSThread* p) { if(p==&parent)++resumes;else assert(p==&Task[15].Thread || p==&Task[1].Thread); }
void OSSignalSemaphore(int*) { ++signals; }
void OSExitThread(void* p) { assert(p == actual); ++exits; }
void OSPanic(const char*, int, const char*) { ++panics; }
'''
        checks = r'''
void change_dispatch_on_sleep(){nativeTaskParents[actual->id]=nullptr;}
int main() {
    for(unsigned i=0;i<TASK_NUM;++i)Task[i].Thread.id=i;
    nativeTaskParents[1] = &parent;
    // The captured failure: interrupt task returns after native I/O yielded,
    // while the main scheduler has restored its sentinel cursor.
    pCTask = reinterpret_cast<TASK*>(-1);
    actual = &Task[TASK_ISR].Thread;
    Task[TASK_ISR].Status = 3;
    Task[TASK_ISR].suspend_cnt = 2;
    TaskExit();
    assert(Task[TASK_ISR].Status == TASK_NONE);
    assert(Task[TASK_ISR].suspend_cnt == 0);
    assert(exits == 1 && resumes == 0 && signals == 0 && panics == 0);
    // A regular task owns its own completion and parent/semaphore effects,
    // even if the cursor names a different active slot.
    pCTask = &Task[2];
    Task[2].Status = 3;
    Task[1].Status = 3;
    Task[1].Priority = 16;
    actual = &Task[1].Thread;
    TaskExit();
    assert(Task[1].Status == TASK_NONE && Task[2].Status == 3);
    assert(exits == 2 && resumes == 1 && signals == 1 && panics == 0);
    // Sleep must retain its queue and parent even when a yield changes cursor.
    pCTask = reinterpret_cast<TASK*>(-1);
    Task[1].Status = TASK_SUSPEND | 3;
    TaskSleep(3);
    assert(Task[1].SleepCtr == 3 && Task[1].Status == (TASK_SUSPEND | TASK_SLEEP));
    assert(sleeps == 1 && suspends == 1 && resumes == 2 && signals == 2);
    TaskSleep(0);
    assert(sleeps == 1);
    TaskChain(nullptr, 42);
    assert(Task[1].Status == TASK_EXEC && Task[1].arg == 42);
    assert(exits == 3 && resumes == 3 && signals == 3);
    // Actual source dispatcher: root task binds main, but cSceSys's nested
    // dispatch intentionally has no parent. Repeated sleeps must not change
    // the main suspend balance, even if an interrupt changes the global cursor.
    Task[1].Priority=15;Task[1].Status=TASK_SLEEP;Task[1].SleepCtr=1;
    pCTask=&Task[1];pParentThread=&parent;TaskSchedulerMain(&Task[1]);
    assert(nativeTaskParents[1]==&parent);
    Task[15].Priority=14;Task[15].Status=TASK_EXEC;
    pCTask=&Task[15];pParentThread=nullptr;TaskSchedulerMain(&Task[15]);
    assert(nativeTaskParents[15]==nullptr&&nativeTaskParents[1]==&parent);
    actual=&Task[15].Thread;int prior_resumes=resumes,prior_suspends=suspends;
    for(int i=0;i<100;++i){
        TaskSleep(1);assert(resumes==prior_resumes&&suspends==prior_suspends);
        pCTask=&Task[15];TaskSchedulerMain(&Task[15]);
    }
    // A later source dispatch can change parent; use its current binding.
    pParentThread=&parent;pCTask=&Task[15];Task[15].Status=TASK_SLEEP;Task[15].SleepCtr=1;
    TaskSchedulerMain(&Task[15]);TaskSleep(1);
    assert(resumes==prior_resumes+1&&suspends==prior_suspends+1);
    // The parent after a queue wake belongs to the new dispatch, not the
    // invocation that originally slept. Do not add an unmatched main suspend.
    switch_parent_on_wake=true;prior_resumes=resumes;prior_suspends=suspends;
    TaskSleep(1);assert(resumes==prior_resumes+1&&suspends==prior_suspends);
    switch_parent_on_wake=false;prior_resumes=resumes;TaskExit();
    assert(exits==4&&resumes==prior_resumes&&Task[15].Status==TASK_NONE);
    // A foreign thread cannot silently retire any game task.
    actual = &outsider;
    TaskExit();
    assert(panics == 1 && exits == 4 && Task[2].Status == 3);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "owner.cpp"
            exe = pathlib.Path(tmp) / "owner"
            src.write_text(fixture + body + checks)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra",
                            str(src), "-o", str(exe)], check=True,
                           capture_output=True, text=True)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
