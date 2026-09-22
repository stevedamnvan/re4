"""Execute source cDataSwap: separate scratch succeeds; fake ARAM never owns data."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class DataSwap(unittest.TestCase):
    def test_scratch_lifetime_and_rejected_mutable_fallback(self):
        source=(ROOT/'src/game/cDataSwap.cpp').read_text()
        source='\n'.join(s for s in source.splitlines() if not s.startswith('#include'))
        header=(ROOT/'include/cDataSwap.h').read_text().replace('#include "types.h"','')
        harness=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
using u32=std::uintptr_t;
unsigned char live[4096],scratch[4096];
bool fail=false;int current=3,suspend=0,create=0,destroy=0,freed=0,signal=0,aram_calls=0;
u32 MemGetCurrentHeap(){return current;}
void* alloc(u32 n){assert(n==sizeof(scratch));return fail?nullptr:scratch;}
#define MEM_ALLOC(n,a,b) alloc(n)
void MemSuspendHeap(u32 h){assert(h==3);++suspend;}
void MemCreateHeap(u32 h,u32 a,u32 b){assert(h==11 && a==(u32)scratch && b-a==sizeof(scratch));++create;}
void MemSetCurrentHeap(u32 h){current=h;}
void MemDestroyHeap(u32 h){assert(h==11);++destroy;}
void MemSignalHeap(u32 h){assert(h==3);++signal;}
void Mem_free(void* p){assert(p==scratch);++freed;}
struct DCStub {u32 getAramFree(u32){++aram_calls;return 0x1000;}} DC;
struct AramStub {void DmaTransReq(int,u32,u32,u32,int){++aram_calls;}} Aram;
extern "C" void SubScreenAramRead(){++aram_calls;}
void re4dc_missing(const char*){throw 42;}
'''
        main=r'''
int main(){
 memset(live,0xa7,sizeof(live));cDataSwap swap;
 assert(swap.SwapOut((u32)live,sizeof(live),0)==1);
 assert(swap.m_be_flag==1 && swap.m_SwapMaddr==(u32)scratch && current==11);
 assert(swap.SwapOut((u32)live,sizeof(live),0)==0);
 memset(scratch,0x11,sizeof(scratch));for(auto x:live)assert(x==0xa7);
 swap.SwapIn();assert(current==3 && freed==1 && destroy==1 && signal==1 && !swap.m_be_flag);
 swap.SwapIn();assert(freed==1 && destroy==1);
 fail=true;try{swap.SwapOut((u32)live,sizeof(live),0x1234);assert(false);}catch(int code){assert(code==42);}
 assert(!aram_calls && suspend==1 && create==1 && current==3 && !swap.m_be_flag);
 for(auto x:live)assert(x==0xa7);
}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);cpp=p/'swap.cpp';cpp.write_text(harness+header+source+main)
            subprocess.run(['g++','-std=c++20','-DRE4DC_GAME','-fsanitize=address,undefined','-fno-pie','-no-pie',str(cpp),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

if __name__=='__main__':unittest.main()
