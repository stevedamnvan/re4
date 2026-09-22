#!/usr/bin/env python3
"""Exercise the actual native DVD guard and recovered borrow/completion bodies.

Synthetic scheduling forces request completion, reuse and a competing pump at
ownership boundaries. No private assets, emulator, or replacement loader.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    native = (ROOT / "port/dreamcast/game/platform/dvd.cpp").read_text()
    guard = native[native.index("namespace {"):native.index("typedef signed char s8;")]
    source = (ROOT / "src/game/dvd.cpp").read_text()
    bodies = "\n".join(function(source, name) for name in
                        ("void cDvd::ReadProc()", "void cDvd::blockRead(cDvdQueue* q)"))
    fixture = r"""
#include <cassert>
#include <cstring>
#include <functional>
#include <cstdio>
#include <stdexcept>
#include "native_io.h"
struct kthread_t { unsigned io=0; } main_thread, worker_thread;
kthread_t* thd_current=&main_thread;
int irq_mask=0, sleeps=0, violations=0, exits=0;
std::function<void()> sleeping;
int irq_disable(){int old=irq_mask;irq_mask=1;return old;}
void irq_restore(int old){irq_mask=old;}
void thd_sleep(int){assert(!irq_mask);++sleeps;if(sleeping)sleeping();}
extern "C" void* re4dc_io_begin(){assert(irq_mask);++thd_current->io;return thd_current;}
extern "C" void re4dc_io_end(void* p){assert(irq_mask && p==thd_current && thd_current->io);--thd_current->io;}
extern "C" int re4dc_io_busy(const void* p){return static_cast<const kthread_t*>(p)->io!=0;}
void re4dc_missing(const char*){++violations;}
""" + guard + r"""
using u8=unsigned char;
using u32=unsigned;
unsigned header_buff[32],header_save[32];
void* pFilehead[2];void* pFilehead_save[2];
unsigned tick=0;
unsigned OSGetTick(){return ++tick;}
unsigned OSTicksToMilliseconds(unsigned t){return t;}
void OSReport(const char*,...){}
void TaskExit(){assert(!thd_current->io);++exits;}
void iTaskExit(){TaskExit();}
struct cDvdQueue {
    unsigned m_be_flag=1;unsigned m_Id=1;unsigned startTick=0;
    int chk(unsigned bit)const{return (m_be_flag&bit)!=0;}
    void PushQueue(){m_be_flag&=~1U;}
    unsigned reads=0;
    int Read(){
        auto* token=re4dc_dvd_step_begin();if(!token)return 1;
        ++reads;m_be_flag&=~0x20U;
        re4dc_dvd_step_end(token);return 0;
    }
};
struct cDvd {
    cDvdQueue* pCur_queue=nullptr;
    std::function<void(cDvdQueue*)> pump;
    void readProcMain(cDvdQueue* q){assert(pump);pump(q);}
    void ReadProc();void blockRead(cDvdQueue*);
};
""" + bodies + r"""
void idle(){assert(!main_thread.io && !worker_thread.io && !dvd_step_owner && !dvd_step_depth && !irq_mask);}
int main(){
    // Same-thread steps nest inside a whole borrow; foreign steps cannot enter.
    {
        Re4dcDvdBorrowScope outer;assert(main_thread.io==1);
        {Re4dcDvdBorrowScope inner;assert(main_thread.io==2);}
        auto* token=re4dc_dvd_step_begin();assert(main_thread.io==2);
        re4dc_dvd_step_end(token);assert(main_thread.io==1);
        thd_current=&worker_thread;
        assert(re4dc_dvd_step_begin()==nullptr && worker_thread.io==0 && sleeps==1);
        re4dc_dvd_step_end(token);assert(violations==1 && dvd_step_depth==1);
        thd_current=&main_thread;
    }
    idle();
    // Busy acquisition waits without IRQ masking and then acquires after release.
    thd_current=&worker_thread;auto* busy=re4dc_dvd_step_begin();thd_current=&main_thread;
    bool released=false;
    sleeping=[&](){if(released)return;released=true;thd_current=&worker_thread;re4dc_dvd_step_end(busy);thd_current=&main_thread;};
    {Re4dcDvdBorrowScope acquired;assert(released && main_thread.io==1 && !worker_thread.io);}
    sleeping={};idle();
    try{Re4dcDvdBorrowScope scope;throw std::runtime_error("unwind");}catch(const std::runtime_error&){}
    idle();

    // Actual source borrow preserves an unfinished request and its header state.
    cDvd dvd;cDvdQueue old,borrower;old.m_Id=7;old.m_be_flag=1|0x20|0x100;
    borrower.m_Id=8;borrower.m_be_flag=1|0x40000000U;
    std::memset(header_buff,0x31,sizeof(header_buff));
    pFilehead[0]=&header_buff[1];pFilehead[1]=&header_buff[3];
    dvd.pCur_queue=&old;
    dvd.pump=[&](cDvdQueue* q){
        assert(q==&borrower && main_thread.io==1);
        auto* nested=re4dc_dvd_step_begin();assert(nested && main_thread.io==2);
        std::memset(header_buff,0x62,sizeof(header_buff));pFilehead[0]=&header_buff[9];
        thd_current=&worker_thread;assert(re4dc_dvd_step_begin()==nullptr);thd_current=&main_thread;
        re4dc_dvd_step_end(nested);q->m_be_flag|=0x20000;
    };
    dvd.blockRead(&borrower);
    assert(dvd.pCur_queue==&old && old.reads==1 && header_buff[0]==0x31313131U &&
           pFilehead[0]==&header_buff[1] && borrower.chk(0x800));idle();

    // Finished, freed and recycled saved slots must never be resurrected.
    for(unsigned kind=0;kind<3;++kind){
        old.m_Id=17;old.m_be_flag=1|0x100;borrower.m_be_flag=1|0x40000000U;
        dvd.pCur_queue=&old;
        dvd.pump=[&](cDvdQueue* q){
            q->m_be_flag|=0x20000;
            if(kind==0)old.m_be_flag|=0x800;
            if(kind==1)old.PushQueue();
            if(kind==2){old.m_Id=18;old.m_be_flag=1|0x100;}
        };
        dvd.blockRead(&borrower);assert(!dvd.pCur_queue);idle();
    }
    // A foreign completion must not clear a currently borrowed pCur identity.
    old.m_be_flag=1|0x100;dvd.pCur_queue=&old;thd_current=&worker_thread;
    dvd.pump=[&](cDvdQueue* q){assert(q==&old);dvd.pCur_queue=&borrower;q->m_be_flag|=0x20000;};
    dvd.ReadProc();assert(dvd.pCur_queue==&borrower && old.chk(0x800) && exits==1);
    thd_current=&main_thread;idle();

    // Old request completes while the new borrower waits for its active step.
    old.m_Id=30;old.m_be_flag=1|0x100;dvd.pCur_queue=&old;
    thd_current=&worker_thread;busy=re4dc_dvd_step_begin();thd_current=&main_thread;
    bool completed=false;
    sleeping=[&](){
        if(completed)return;
        completed=true;thd_current=&worker_thread;
        re4dc_dvd_step_end(busy);
        auto next_pump=dvd.pump;
        dvd.pump=[&](cDvdQueue* q){assert(q==&old);q->m_be_flag|=0x20000;};
        dvd.ReadProc();old.PushQueue();old.m_Id=31;old.m_be_flag=1|0x100;
        dvd.pump=next_pump;thd_current=&main_thread;
    };
    borrower.m_be_flag=1|0x40000000U;
    dvd.pump=[&](cDvdQueue* q){assert(q==&borrower);q->m_be_flag|=0x20000;};
    dvd.blockRead(&borrower);sleeping={};
    assert(completed && !dvd.pCur_queue && old.m_Id==31 && !old.chk(0x800));idle();
    std::puts("DVD borrow ownership: nested/busy/release, unfinished/complete/recycled save, foreign completion PASS");
}
"""
    with tempfile.TemporaryDirectory(prefix="re4-dvd-borrow-") as tmp:
        tmp=Path(tmp)
        (tmp/"fixture.cpp").write_text(fixture)
        command=["g++","-std=c++17","-Wall","-Wextra","-Werror","-DRE4DC_GAME",
                 "-I"+str(ROOT/"port/dreamcast/game/platform/include"),str(tmp/"fixture.cpp")]
        subprocess.run(command+["-O2","-o",str(tmp/"fixture")],check=True)
        subprocess.run([str(tmp/"fixture")],check=True)
        subprocess.run(command+["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer",
                                "-no-pie","-o",str(tmp/"sanitized")],check=True)
        subprocess.run([str(tmp/"sanitized")],check=True)


if __name__ == "__main__":
    main()
