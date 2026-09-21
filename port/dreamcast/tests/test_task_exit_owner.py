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
        helper_start = source.index("#if !defined(__PPC__)\n// KOS file I/O")
        helper_end = source.index("void TaskKill(TASK* t);", helper_start)
        sleep_start = source.index("void TaskSleep(int frames)")
        body = source[helper_start:helper_end] + source[sleep_start:end]
        fixture = r'''
#include <cassert>
#include <cstddef>
using u32 = unsigned;
constexpr unsigned TASK_NUM = 18, TASK_ISR = 4, TASK_NONE = 0, TASK_SLEEP = 2, TASK_EXEC = 1, TASK_SUSPEND = 128;
using TaskFunc = void(*)();
struct OSThread { int id; };
struct TASK { OSThread Thread; int Status, suspend_cnt, Priority, SleepCtr, Queue, arg; void* (*hook)(void*); void (*pFunc)(int); };
TASK Task[TASK_NUM];
TASK* pCTask;
OSThread outsider, parent, *actual;
int Sema, resumes, signals, exits, panics, sleeps, suspends;
void* TaskExec_hook(void*) { return nullptr; }
void GXSetCurrentGXThread() {}
void OSSuspendThread(OSThread* p) { assert(p == &parent); ++suspends; }
void OSSleepThread(int* q) { assert(q == &Task[1].Queue); pCTask = reinterpret_cast<TASK*>(-1); ++sleeps; }
OSThread* OSGetCurrentThread() { return actual; }
OSThread* ParentThread() { return &parent; }
void OSResumeThread(OSThread* p) { assert(p == &parent); ++resumes; }
void OSSignalSemaphore(int*) { ++signals; }
void OSExitThread(void* p) { assert(p == actual); ++exits; }
void OSPanic(const char*, int, const char*) { ++panics; }
'''
        checks = r'''
int main() {
    nativeSchedulerThread = &parent;
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
    // A foreign thread cannot silently retire any game task.
    actual = &outsider;
    TaskExit();
    assert(panics == 1 && exits == 3 && Task[2].Status == 3);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "owner.cpp"
            exe = pathlib.Path(tmp) / "owner"
            src.write_text(fixture + body + checks)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra",
                            str(src), "-o", str(exe)], check=True,
                           capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
