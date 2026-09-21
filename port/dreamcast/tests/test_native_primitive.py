"""Execute the source primitive allocator at capacity, across reset and fallback.
Host lifetime/bounds evidence only; does not qualify future 3D/DMA consumers.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which("g++"), "host compiler required")
class NativePrimitive(unittest.TestCase):
    def test_capacity_reset_guards_and_allocation_failure(self):
        game = (ROOT / "src/game/game.cpp").read_text()
        trans = (ROOT / "src/game/trans.cpp").read_text()
        bodies = game[game.index("void primInit()\n{"):game.index("// Debug: prints the primitive buffer usage")]
        bodies += trans[trans.index("void SetPrimBuffPtr()\n{"):trans.index("// Resets the TEV / indirect")]
        fixture = r"""
#include <cassert>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include "native_primitive.h"
using u8=unsigned char;using u32=uintptr_t;using s32=intptr_t;
struct Global { s32 prim_cnt=0; int nPrim=1024; u32 vtx_buf_no=0; } state,*pG=&state;
struct GxWork { u8* prim=nullptr; } gxState;
#define GXWORK() (&gxState)
#define RE4_MEM_LO 0
#define RE4_MEM_HI UINTPTR_MAX
#define PTR_INVALID(p) (!(p))
template<class T,class U> void S32Set(T& dst,U src){dst=src;}
template<class T,class U> void U32Set(T& dst,U src){dst=src;}
alignas(32) u8 memory[8192];
unsigned allocated,ceiling=4096,attempts,errors;
void* allocation(unsigned bytes){
 ++attempts;if(bytes>ceiling)return nullptr;
 assert(bytes+64<=sizeof(memory));allocated=bytes;
 memset(memory,0xcc,sizeof(memory));return memory+32;
}
#define MEM_ALLOC(bytes,kind,heap) allocation(bytes)
void memclr_asm(void* p,unsigned size){memset(p,0,size);}
void Mem_free(void* p){assert(p==memory+32);allocated=0;}
void OSReport(const char*,...){}
struct Log{void err(int,int,const char*,...){++errors;}} logState,*pLog=&logState;
void SetPrimBuffPtr();
void guards(){
 for(unsigned i=0;i<32;++i)assert(memory[i]==0xcc);
 for(unsigned i=32+allocated;i<sizeof(memory);++i)assert(memory[i]==0xcc);
}
"""
        checks = r"""
int main(){
 primInit();assert(state.nPrim==1024);
 assert(allocated==1024*RE4DC_PRIMITIVE_BUFFERS);
 for(unsigned epoch=0;epoch<4;++epoch){
  unsigned prior=state.vtx_buf_no;
  SetPrimBuffPtr();
  assert(state.vtx_buf_no==(RE4DC_PRIMITIVE_BUFFERS==1?0:(prior^1)));
  auto* first=static_cast<u8*>(GetPrimBuff(1));
  auto* second=static_cast<u8*>(GetPrimBuff(33));
  assert(second==first+32);
  auto* remainder=static_cast<u8*>(GetPrimBuff(928));
  assert(remainder==first+96);
  assert(!GetPrimBuff(1)); // exact frame capacity, no overwrite of the next region
  memset(first,epoch+1,1024);
  assert(first==memory+32+state.nPrim*state.vtx_buf_no);
  guards();
 }
 assert(errors==4);
 primFree();assert(!state.prim_cnt && !allocated);
 // Source allocation fallback retains its per-frame halving behavior.
 state=Global{};ceiling=512*RE4DC_PRIMITIVE_BUFFERS;attempts=errors=0;
 primInit();assert(attempts==2 && state.nPrim==512);
 assert(allocated==512*RE4DC_PRIMITIVE_BUFFERS);
 assert(GetPrimBuff(512) && !GetPrimBuff(32));guards();primFree();
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "test.cpp").write_text(fixture + bodies + checks)
            for buffers in (1, 2):
                with self.subTest(buffers=buffers):
                    exe = path / f"test{buffers}"
                    subprocess.run(["g++", "-std=c++17", "-DRE4DC_GAME",
                                    f"-DRE4DC_PRIMITIVE_BUFFERS={buffers}",
                                    "-I" + str(ROOT / "port/dreamcast/game/platform/include"),
                                    str(path / "test.cpp"), "-o", str(exe)], check=True)
                    subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()