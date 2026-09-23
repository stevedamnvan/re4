"""Actual room allocation adapter: budgets, failure, and detach-before-free.
The source UI translation unit tail is compiled unchanged with a small fake
source allocator; no renderer or allocation policy is reimplemented here.
Room heap-4 cells are freed to heap 4 by handle (never to the OS current
heap), only while the heap generation they came from is live.
"""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which("g++"),"host compiler required")
class PreparationStorage(unittest.TestCase):
 def test_room_owner_budget_and_retirement(self):
  game=ROOT/"port/dreamcast/game"
  implementation=(game/"ui_bridge.cpp").read_text().split('#include "native_model.h"',1)[1]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   code=r"""
#include "native_model.h"
#include <cassert>
#include <cstdarg>
#include <cstring>
#include <cstdint>
constexpr unsigned kCell=32;
alignas(32) unsigned char storage[131072+kCell];
struct MemHeap {int handle;std::uintptr_t start,end;}; MemHeap Heap[13];
int current=4,active=1,free_bytes=213824,allocations=0,frees=0,detaches=0;
bool fail=false,live=false;
int MemGetCurrentHeap(){return current;}
int memCheckHeapActive(int heap){assert(heap==4);return active;}
extern "C" int OSCheckHeap(int){return free_bytes;}
void* mem_calloc(unsigned bytes,const char*,int,int flag,int heap){
 assert(bytes==sizeof(storage) && !flag && heap==4 && !live);
 ++allocations;if(fail)return nullptr;
 free_bytes-=bytes+64;live=true;std::memset(storage,0xA5,bytes);std::memset(storage,0,bytes);return storage;
}
void* mem_alloc(unsigned,const char*,int,int,int){assert(!"static packages are not built here");return nullptr;}
extern "C" void OSFreeToHeap(int handle,void* p){
 assert(handle==Heap[4].handle && p==storage && live && detaches>frees);++frees;live=false;free_bytes+=sizeof(storage)+64;
}
extern "C" void re4dc_model_detach_retained_storage(){++detaches;}
extern "C" void re4dc_log(const char*,...){}
"""+'#include "native_model.h"'+implementation+r"""
unsigned char* const payload=storage+kCell;
int main(){unsigned bytes=1,generation,cells,cell_bytes,stale,refused;
 Heap[4]={7,reinterpret_cast<std::uintptr_t>(storage),reinterpret_cast<std::uintptr_t>(storage)+sizeof(storage)};
 // No room heap yet (boot, title): nothing may be carved from heap 4.
 re4dc_model_preparation_owner((void*)1);
 assert(!re4dc_model_retained_storage(&bytes) && bytes==0 && allocations==0);
 re4dc_model_preparation_owner(nullptr);
 re4dc_room4_open();
 assert(!re4dc_model_retained_storage(&bytes) && bytes==0 && allocations==0);
 re4dc_model_preparation_owner((void*)1);current=3;
 assert(!re4dc_model_retained_storage(&bytes) && !allocations);
 current=4;active=0;assert(!re4dc_model_retained_storage(&bytes) && !allocations);active=1;
 for(unsigned cycle=0;cycle<3;++cycle){
  re4dc_model_preparation_owner(reinterpret_cast<void*>(std::uintptr_t(1+cycle)));
  assert(re4dc_model_retained_storage(&bytes)==payload && bytes==131072 && free_bytes==82656);
  const int count=allocations;payload[0]=7;
  assert(re4dc_model_retained_storage(&bytes)==payload && payload[0]==7 && allocations==count);
  assert(re4dc_room4_state(&generation,&cells,&cell_bytes,&stale,&refused) && cells==1 && cell_bytes==131072);
  re4dc_model_preparation_owner(nullptr);assert(!live && free_bytes==213824);
  re4dc_model_preparation_owner(nullptr);assert(!live);
  assert(re4dc_room4_state(&generation,&cells,&cell_bytes,&stale,&refused) && cells==0 && !stale);
 }
 assert(allocations==3 && frees==3);
 free_bytes=66592;re4dc_model_preparation_owner((void*)4);
 assert(!re4dc_model_retained_storage(&bytes) && bytes==0 && allocations==3);
 free_bytes=213824;assert(!re4dc_model_retained_storage(&bytes) && allocations==3);
 re4dc_model_preparation_owner(nullptr);re4dc_model_preparation_owner((void*)5);
 fail=true;assert(!re4dc_model_retained_storage(&bytes) && allocations==4);
 fail=false;assert(!re4dc_model_retained_storage(&bytes) && allocations==4);
 re4dc_model_preparation_owner(nullptr);re4dc_model_preparation_owner((void*)6);
 assert(re4dc_model_retained_storage(&bytes)==payload && allocations==5);
 re4dc_model_preparation_owner((void*)7);assert(!live && frees==4);
 assert(re4dc_model_retained_storage(&bytes)==payload && allocations==6);
 re4dc_model_preparation_owner(nullptr);assert(!live && free_bytes==213824);
 // StageSet closed the room heap: the next room's owner gets nothing until
 // gameRoomMemInit rebuilt heap 4.
 re4dc_room4_close();re4dc_model_preparation_owner((void*)8);
 assert(!re4dc_model_retained_storage(&bytes) && allocations==6);
 re4dc_model_preparation_owner(nullptr);
 // A cell that outlives its heap generation (heap 4 rebuilt without the
 // retirement) is dropped, never freed into the rebuilt heap.
 re4dc_room4_open();re4dc_model_preparation_owner((void*)9);
 assert(re4dc_model_retained_storage(&bytes)==payload && allocations==7);
 re4dc_room4_close();re4dc_room4_open();
 live=false;free_bytes=213824; // the source rebuilt heap 4 over the old cell
 re4dc_model_preparation_owner(nullptr);
 assert(frees==5 && re4dc_room4_state(&generation,&cells,&cell_bytes,&stale,&refused) && stale==1 && refused==2);
}
"""
   (root/"fixture.cpp").write_text(code)
   exe=root/"check"
   subprocess.run(["g++","-std=c++20","-O2","-DRE4DC_D349_RENDERER_STACK=1","-fsanitize=address,undefined","-fno-omit-frame-pointer","-I"+str(game/"platform/include"),str(root/"fixture.cpp"),"-o",str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=="__main__":unittest.main()
