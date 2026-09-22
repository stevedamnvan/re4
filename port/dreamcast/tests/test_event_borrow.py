"""Exercise r100's actual event-borrow boundary, without emulating ARAM DMA."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which("g++"), "host g++ required")
class EventBorrowTests(unittest.TestCase):
    def test_required_borrow_preflight_and_round_trip(self):
        source = (ROOT / "src/st1/r100.cpp").read_text()
        begin = source.index("static char* r100_evtName")
        end = source.index("// The ambush after", begin)
        body = source[begin:end]
        fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <cstdarg>
#include <cstdio>
using u32 = uint32_t;
constexpr int CMND_CLEAR_DATA=0, CMND_MRAM_LOAD=1, CMND_ARAM_LOAD=2;
struct Rejected {};
struct DataUnit {
    u32 m_size=64; void* m_addr=(void*)0x1000;
    bool loaded=true, usable=true; int clears=0, commands=0;
    int waitLoadOk() { return loaded; }
    int waitUseOk() { return usable; }
    void setCommand(int c, int, int) { ++commands; if(c==CMND_CLEAR_DATA)++clears; }
} unit;
struct Work { DataUnit* evt[10]{}; } work, *W=&work;
struct DataCtrl { bool available=true; DataUnit* setData(const char*) { return available?&unit:nullptr; } } DC;
struct EventMgr { const char* NameChange(const char* n) { return n; } } EvtMgr;
struct ReadModule { void* pArc; u32 size; } module;
unsigned char enemy[64], event[64];
int pushes, pops, swaps, depth, range_checks;
bool present=true, immutable=false;
u32 range_size;
std::string rejection;
ReadModule* SearchEmModule(int id) { assert(id==0x12); return present?&module:nullptr; }
void EspEmDataSwapPush(int id) { assert(id==0x12 && depth==0); ++pushes; ++depth; }
void EspEmDataSwapPop(int id) { assert(id==0x12 && depth==1); ++pops; --depth; }
int re4dc_event_file_range(u32 addr,u32 bytes) { assert(addr==0x1000); ++range_checks; range_size=bytes; return immutable; }
void re4dc_log(const char* fmt,...) { char s[512];va_list v;va_start(v,fmt);vsnprintf(s,sizeof s,fmt,v);va_end(v);rejection=s; }
void re4dc_missing(const char*) { throw Rejected{}; }
struct Logger { void err(int,int,const char*,...) {} } logger,*pLog=&logger;
// Transport mock checks ownership sequencing and exact byte restoration.
// Passing this test is not a claim of working target mutable event transport.
void MemorySwap(void* p,u32 a,u32 bytes) {
    assert(p==enemy && a==0x1000 && depth==1 && bytes<=64);
    assert(!immutable && unit.loaded); ++swaps;
    for(u32 i=0;i<bytes;++i){auto t=enemy[i];enemy[i]=event[i];event[i]=t;}
}
void reset() {
    unit=DataUnit{};work=Work{};DC.available=true;module={enemy,64};
    present=true;immutable=false;pushes=pops=swaps=depth=range_checks=0;range_size=0;rejection.clear();
    for(int i=0;i<64;++i){enemy[i]=i;event[i]=255-i;}
}
void untouched() {
    assert(pushes==0 && pops==0 && swaps==0 && depth==0);
    for(int i=0;i<64;++i){assert(enemy[i]==i);assert(event[i]==255-i);}
}
'''
        checks = r'''
int main() {
    // All source borrow IDs reject before unregistering effects or changing data.
    for(int no : {0,4,9}) {
        for(int failure=0;failure<6;++failure) {
            reset();
            if(failure==0)present=false;
            if(failure==1)module.pArc=nullptr;
            if(failure==2)unit.m_size=65;
            if(failure==3)unit.loaded=false;
            if(failure==4)immutable=true;
            if(failure==5){unit.m_size=0xffffffffU;module.size=0xffffffffU;}
            void* out=(void*)0xdead;
            bool caught=false;try{readEvent(no,1,&out);}catch(Rejected){caught=true;}
            assert(caught && out==nullptr);untouched();
            assert(unit.clears==0);
            assert(rejection.find("effects_unchanged=1")!=std::string::npos);
            const char* reason=failure<2?"missing destination":failure==2?"capacity":failure==3?"load incomplete":"mutable snapshot backing";
            assert(rejection.find(reason)!=std::string::npos);
        }
        // Evaluation/release preserves every byte and balances effect ownership.
        for(int cycle=0;cycle<3;++cycle) {
            reset();void* out=nullptr;assert(readEvent(no,1,&out)==1 && out==enemy);
            assert(pushes==1 && depth==1 && swaps==1 && range_size==64);
            for(int i=0;i<64;++i){assert(enemy[i]==255-i);assert(event[i]==i);}
            freeEvent(no,1);
            assert(pops==1 && depth==0 && swaps==2 && unit.clears==1);
            for(int i=0;i<64;++i){assert(enemy[i]==i);assert(event[i]==255-i);}
        }
        // Preload stays asynchronous; no borrow, effect release or range query.
        reset();assert(readEvent(no,0,nullptr)==1);untouched();
        assert(unit.commands==1 && range_checks==0);
        reset();DC.available=false;assert(readEvent(no,0,nullptr)==0);untouched();
    }
    // A non-borrowed source event retains the existing MRAM ownership path.
    reset();void* out=nullptr;assert(readEvent(3,1,&out)==1 && out==unit.m_addr);
    assert(unit.commands==1 && range_checks==0);untouched();
    freeEvent(3,0);assert(unit.clears==1);untouched();
    // Exact production failure size: no mock transfer is reached.
    reset();module.size=1105152;unit.m_size=1341504;
    try{readEvent(0,1,nullptr);assert(false);}catch(Rejected){}untouched();
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "event.cpp"
            exe = pathlib.Path(tmp) / "event"
            src.write_text(fixture + body + checks)
            result = subprocess.run(["g++", "-std=c++17", "-DRE4DC_GAME", "-fpermissive",
                                     "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                                     str(src), "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
