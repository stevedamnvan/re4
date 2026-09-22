"""Real manager + native backing, synthetic parts; host ABI shims only."""
from pathlib import Path
import subprocess,tempfile,unittest,re,runpy
ROOT=Path(__file__).resolve().parents[3]

class PartsStorage(unittest.TestCase):
 def test_linked_enemy_readers(self):
  """New linked modules must not silently reintroduce contiguous-slot readers."""
  make=(ROOT/'port/dreamcast/game/Makefile').read_text()
  modules=re.search(r'^MODULES = (.+)$',make,re.M)[1].split()
  units=runpy.run_path(str(ROOT/'port/dreamcast/game/tools/gen_modules.py'))['units']
  paths=set((ROOT/'src/game').glob('*.cpp'))
  for module in modules:
   paths.update(ROOT/p for p in units(str(ROOT/'config/G4BE08/modules'),module)[1])
  for p in sorted(paths):
   s='\n'.join(x for x in p.read_text().splitlines() if not re.match(r'\s*#\s*include',x))
   native=subprocess.check_output(['g++','-E','-P','-x','c++','-'],input=s,text=True)
   self.assertNotIn('EmMgr.pArray',native,str(p))
   for alias in re.finditer(r'cEmMgr\* (\w+) = &EmMgr;',native):
    self.assertNotIn(alias[1]+'->pArray',native[alias.end():native.find('\n}',alias.end())],str(p))

 def test_lifetimes_and_capacity(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp)
   # Use the actual template algorithms. Only placement/delete signatures need
   # host size_t rather than the recovered 32-bit compiler's unsigned int.
   s=(ROOT/'include/cManager.h').read_text().replace('unsigned int','__SIZE_TYPE__')
   (d/'cManager.h').write_text('#include <new>\n#define PLACEMENT_NEW_DEFINED\n'+s)
   (d/'types.h').write_text('''#pragma once
using u32=unsigned long;using u8=unsigned char;
#define RE4_MEM_LO 1UL
#define RE4_MEM_HI (~0UL)
void* Debug_alloc(u32,int);void Debug_free(void*);
''')
   (d/'model.h').write_text('''#pragma once
#include "cManager.h"
class cParts : public cUnit { public: cParts* pList; unsigned value;
 cParts(){be_flag=1;pList=0;value=0x1234;} };
class cModelInfo:public cUnit {public: unsigned value; cModelInfo(){be_flag=1;value=91;} };
class cModInfoMgr:public cManager<cModelInfo>{public:
 cModInfoMgr():cManager<cModelInfo>(sizeof(cModelInfo),0){}
 void* memAlloc(u32);void memFree(void*);void memClear(cModelInfo*,u32);
 int construct(cModelInfo* p,u32){new(p)cModelInfo;return 1;}
};
class cPartsMgr:public cManager<cParts>{public:
 cPartsMgr():cManager<cParts>(sizeof(cParts),0){}
 void* memAlloc(u32);void memFree(void*);void memClear(cParts*,u32);
 int construct(cParts* p,u32){new(p)cParts;return 1;}
 cParts* createSequential(u32);
};
''')
   # Use the real indexed helper: a light may keep its result before create.
   obj=(ROOT/'include/obj.h').read_text();a=obj.index('static inline cObj* ObjMgrWork');b=obj.index('\nstruct EspGenWork;',a)
   (d/'obj.h').write_text(OBJECT_HEADER+obj[a:b])
   em=(ROOT/'include/em.h').read_text();a=em.index('static inline cEm* EmMgrWork');b=em.index('// Pushable rack/crate',a)
   (d/'em.h').write_text(ENEMY_HEADER+em[a:b])
   (d/'global.h').write_text('#pragma once\nstruct Global{unsigned Debug_flg[4];};extern Global* pG;\n')
   (d/'main_mem.h').write_text('''#pragma once
#include "types.h"
#define MEM_HEAP_CURRENT 13
struct HeapEntry{int handle;};extern HeapEntry Heap[13];
void* mem_alloc(u32,const char*,int,int,int);void memclr_asm(void*,u32);int MemGetCurrentHeap();
''')
   (d/'re4dc_platform.h').write_text('#pragma once\nvoid re4dc_log(const char*,...);extern "C" void re4dc_missing(const char*);\n')
   s=(ROOT/'src/game/model.cpp').read_text();a=s.index('static inline cParts* PartsMgrWork');b=s.index('\ncPartsMgr PartsMgr;',a)
   (d/'sequence.cpp').write_text('#include "model.h"\n'+s[a:b])
   # Exercise the real ladder query: it intentionally reads position even on
   # unused zeroed slots, unlike ordinary live-enemy scans.
   s=(ROOT/'src/game/sce_at.cpp').read_text();a=s.index('int sceAtCheckLadderUp(');b=s.index('\n// Type 0x11',a)
   (d/'main.cpp').write_text(CHECKS.replace('int main(){',ENEMY_CHECKS+s[a:b]+ '\nint main(){\n check_enemies();'))
   for mode in range(16):
    exe=d/f'check{mode}'
    subprocess.run(['g++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-sanitize=vptr','-fno-omit-frame-pointer','-fno-pie','-no-pie',f'-DRE4DC_PARTS_DEMAND={mode&1}',f'-DRE4DC_MODELINFO_DEMAND={(mode>>1)&1}',f'-DRE4DC_OBJECT_DEMAND={(mode>>2)&1}',f'-DRE4DC_ENEMY_DEMAND={(mode>>3)&1}',f'-I{d}',str(ROOT/'port/dreamcast/game/parts_bridge.cpp'),str(d/'sequence.cpp'),str(d/'main.cpp'),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

OBJECT_HEADER = r'''
#pragma once
#include "model.h"
class cObj: public cUnit { public: unsigned value; cObj(){be_flag=1;value=73;} };
class cObjMgr:public cManager<cObj>{public:
 cObjMgr():cManager<cObj>(sizeof(cObj),2){}
 void* memAlloc(u32);void memFree(void*);void memClear(cObj*,u32);
 int construct(cObj* p,u32){new(p)cObj;return 1;}
};
extern cObjMgr ObjMgr;
'''
ENEMY_HEADER = r'''
#pragma once
#include "model.h"
using f32=float;
struct Vec{float x,y,z;};
class cEm:public cUnit {public: unsigned id; Vec pos; unsigned value;
 cEm(){be_flag=1;id=0;pos={0,0,0};value=123;} };
using cModel=cEm;
class cEmMgr:public cManager<cEm>{public:
 cEmMgr():cManager<cEm>(sizeof(cEm),2){}
 void* memAlloc(u32);void memFree(void*);void memClear(cEm*,u32);
 int construct(cEm* p,u32 id){new(p)cEm;p->id=id;return 1;}
};
extern cEmMgr EmMgr;
extern "C" void re4dc_missing(const char*);
'''
ENEMY_CHECKS = r'''
void* cEmMgr::memAlloc(u32 n){return mem_alloc(n,0,0,0,13);}
void cEmMgr::memFree(void* p){OSFreeToHeap(allocations.at(p).owner,p);}
void cEmMgr::memClear(cEm* p,u32 n){memclr_asm(p,n);}
cEmMgr EmMgr;
struct SceAtLadder{Vec pos;};struct AreaData{Vec pos;};
void sceAtGetLadderPos(SceAtLadder* l,Vec* p,float* a){*p=l->pos;*a=0;}
void AreaDataInit(AreaData* a,Vec* p,int,float,float){a->pos=*p;}
int AreaHitCheck(AreaData* a,Vec* p){return a->pos.x==p->x&&a->pos.y==p->y&&a->pos.z==p->z;}
int sceAtCheckLadderUp(SceAtLadder*,cModel*);
void check_enemies(){
 assert(EmMgr.arrayAlloc(60));unsigned before=calls;
 // Unused slots preserve the source ladder result without committing a pool.
 SceAtLadder ladder{{0,0,0}};assert(!sceAtCheckLadderUp(&ladder,nullptr));
 ladder.pos.x=100;assert(sceAtCheckLadderUp(&ladder,nullptr));assert(calls==before);
 if(RE4DC_ENEMY_DEMAND){for(unsigned i=0;i<60;++i)assert(!EmMgr.workAt(i));assert(calls==before);}
 auto retained=EmMgrWork(17);assert(retained&&!retained->be_flag);
 auto player=EmMgr.create(0);assert(player==EmMgr.workAt(0));
 auto first=EmMgr.create(0x12);assert(first==EmMgr.workAt(1));
 assert(EmMgr.create(0x23,17)==retained);
 retained->pos.x=100;assert(sceAtCheckLadderUp(&ladder,nullptr)); // source tests id <= 0x20 only
 retained->id=0x12;assert(!sceAtCheckLadderUp(&ladder,nullptr));
 assert(sceAtCheckLadderUp(&ladder,retained));
 EmMgr.destroy(first);auto second=EmMgr.create(0x23);assert(second==EmMgr.workAt(2));
 EmMgr.dieCheck();assert(first->be_flag&0x400);EmMgr.dieCheck();assert(!first->be_flag);
 assert(EmMgr.create(0x12)==first);before=calls;
 for(int i=0;i<100;++i){EmMgr.destroy(first);EmMgr.dieCheck();EmMgr.dieCheck();assert(EmMgr.create(0x12)==first);}
 assert(calls==before&&EmMgrWork(17)==retained&&retained->pos.x==100);
 if(RE4DC_ENEMY_DEMAND){deny=true;bool rejected=false;try{EmMgrWork(40);}catch(const std::runtime_error&){rejected=true;}
 assert(rejected&&EmMgr.workAt(17)==retained&&!EmMgr.workAt(40));deny=false;}
 auto rear=EmMgr.createBack(0x23);assert(rear==EmMgr.workAt(59)&&EmMgr.getPrevWork(rear)==EmMgrWork(58));
 std::vector<cEm*> slots;for(unsigned i=0;i<60;++i){auto p=EmMgr.workAt(i);if(!p||!(p->be_flag&0x601))p=EmMgr.create(0x12,i);assert(p);slots.push_back(p);}
 assert(EmMgr.countActiveWork()==60&&!EmMgr.create());for(unsigned i=0;i<60;++i)assert(EmMgrWork(i)==slots[i]);
 assert(!EmMgrWork(60)&&!EmMgr.prepareWork(0,2));
 assert(EmMgr.arrayPush(4)&&EmMgr.create());EmMgr.destroyAll();EmMgr.dieCheck();EmMgr.dieCheck();assert(EmMgr.arrayPop());
 assert(EmMgrWork(17)==retained&&EmMgr.countActiveWork()==60);
 EmMgr.destroyAll();EmMgr.dieCheck();EmMgr.dieCheck();current=5;EmMgr.arrayFree();assert(allocations.empty());current=4;
 assert(EmMgr.arrayAlloc(3)&&EmMgr.create());for(auto [p,info]:allocations)free(p);allocations.clear();EmMgr.roomInit();
 assert(EmMgr.arrayAlloc(3)&&EmMgr.createBack(0));EmMgr.destroyAll();EmMgr.dieCheck();EmMgr.dieCheck();EmMgr.arrayFree();assert(allocations.empty());
}
'''
CHECKS=r'''
#include "model.h"
#include "obj.h"
#include "em.h"
#include "global.h"
#include "main_mem.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <map>
#include <stdexcept>
#include <vector>
Global global{};Global* pG=&global;HeapEntry Heap[13]={{0},{1},{2},{3},{4},{5}};int current=4;
struct Allocation{unsigned long bytes;int owner;};std::map<void*,Allocation> allocations;
unsigned calls;bool deny;int MemGetCurrentHeap(){return current;}
void* mem_alloc(u32 n,const char*,int,int,int h){if(deny)return 0;void* p;assert(!posix_memalign(&p,32,(n+31)&~31UL));allocations[p]={n,h==13?current:h};++calls;return p;}
extern "C" void OSFreeToHeap(int h,void* p){assert(allocations.count(p)&&allocations.at(p).owner==h);allocations.erase(p);free(p);}
void memclr_asm(void* p,u32 n){memset(p,0,n);}
void re4dc_log(const char*,...){}void re4dc_missing(const char* s){throw std::runtime_error(s);}
void* Debug_alloc(u32 n,int){auto p=mem_alloc(n,0,0,0,13);memclr_asm(p,n);return p;}void Debug_free(void* p){OSFreeToHeap(allocations.at(p).owner,p);}
void* cPartsMgr::memAlloc(u32 n){return mem_alloc(n,0,0,0,13);}void cPartsMgr::memFree(void* p){OSFreeToHeap(allocations.at(p).owner,p);}void cPartsMgr::memClear(cParts* p,u32 n){memclr_asm(p,n);}
void* cModInfoMgr::memAlloc(u32 n){return mem_alloc(n,0,0,0,13);}void cModInfoMgr::memFree(void* p){OSFreeToHeap(allocations.at(p).owner,p);}void cModInfoMgr::memClear(cModelInfo* p,u32 n){memclr_asm(p,n);}
void release(cPartsMgr& m,cParts* p){while(p){auto next=p->pList;m.destroy(p);p=next;}}
void* cObjMgr::memAlloc(u32 n){return mem_alloc(n,0,0,0,13);}void cObjMgr::memFree(void* p){OSFreeToHeap(allocations.at(p).owner,p);}void cObjMgr::memClear(cObj* p,u32 n){memclr_asm(p,n);}
cObjMgr ObjMgr;
int main(){
 // An indexed reference can exist before its object. No construction, moving,
 // eager scan commitment, dead-page eviction, or ID reuse may invalidate it.
 assert(ObjMgr.arrayAlloc(35));unsigned start_calls=calls;
 if(RE4DC_OBJECT_DEMAND){for(int i=0;i<35;++i)assert(!ObjMgr.workAt(i));assert(calls==start_calls);}
 cObj* parent=ObjMgrWork(17);assert(parent&&!parent->be_flag);
 auto object=ObjMgr.create(0,17);assert(object==parent&&parent->value==73);
 auto rear=ObjMgr.createBack(0);assert(rear&&rear==ObjMgr.workAt(34));
 ObjMgr.destroy(object);ObjMgr.dieCheck();assert(parent->be_flag&0x400);
 ObjMgr.dieCheck();assert(!parent->be_flag&&ObjMgr.workAt(17)==parent);
 if(RE4DC_OBJECT_DEMAND){deny=true;assert(!ObjMgr.prepareWork(0,1));deny=false;assert(ObjMgr.workAt(17)==parent);}
 assert(ObjMgr.create(0,17)==parent);start_calls=calls;
 for(int i=0;i<100;++i){ObjMgr.destroy(parent);ObjMgr.dieCheck();ObjMgr.dieCheck();assert(ObjMgr.create(0,17)==parent);}assert(calls==start_calls);
 // Logical predecessor, including across a physical page and a dead slot.
 auto at32=ObjMgr.create(0,32);assert(at32&&ObjMgr.getPrevWork(at32)==ObjMgrWork(31));
 auto at0=ObjMgr.create(0,0);assert(at0&&!ObjMgr.getPrevWork(at0));
 std::vector<cObj*> objects;for(unsigned i=0;i<35;++i){auto p=ObjMgrWork(i);if(!(p->be_flag&0x601))p=ObjMgr.create(0,i);assert(p);objects.push_back(p);}
 assert(ObjMgr.countActiveWork()==35&&!ObjMgr.create());for(unsigned i=0;i<35;++i)assert(ObjMgrWork(i)==objects[i]);
 assert(!ObjMgrWork(35)&&!ObjMgr.prepareWork(35,1)&&!ObjMgr.prepareWork(0,2));
 assert(ObjMgr.arrayPush(4));auto obj_debug=ObjMgr.create();assert(obj_debug);ObjMgr.destroy(obj_debug);ObjMgr.dieCheck();ObjMgr.dieCheck();assert(ObjMgr.arrayPop());assert(ObjMgrWork(17)==parent&&ObjMgr.countActiveWork()==35);
 ObjMgr.destroyAll();ObjMgr.dieCheck();ObjMgr.dieCheck();assert(!parent->be_flag);current=5;ObjMgr.arrayFree();assert(allocations.empty());current=4;
 // Source heap reset then manager roomInit forgets prior pages, not double-free.
 ObjMgr.arrayAlloc(17);assert(ObjMgrWork(16));for(auto [p,info]:allocations)free(p);allocations.clear();ObjMgr.roomInit();ObjMgr.arrayAlloc(9);assert(ObjMgr.create());ObjMgr.destroyAll();ObjMgr.dieCheck();ObjMgr.dieCheck();ObjMgr.arrayFree();assert(allocations.empty());

 // Model-info keeps pointer-bearing source records stable across page growth,
 // reuse, deferred deletion, subscreen ownership and an incomplete last page.
 cModInfoMgr info;assert(info.arrayAlloc(35));auto first=info.create();assert(first);
 first->value=123;unsigned page_calls=calls;
 for(unsigned i=1;i<16;++i)assert(info.create(0,i));assert(calls==page_calls);
 auto last=info.create(0,34);assert(last&&first==info.workAt(0)&&first->value==123);
 if(RE4DC_MODELINFO_DEMAND){deny=true;assert(!info.create(0,16));deny=false;assert(first->value==123);}
 auto middle=info.create(0,16);assert(middle&&first==info.workAt(0)&&last==info.workAt(34));
 page_calls=calls;for(int i=0;i<100;++i){info.destroy(middle);middle=info.create(0,16);assert(middle);}assert(calls==page_calls);
 info.flag=2;info.destroy(first);info.dieCheck();assert(first->be_flag&0x400);info.dieCheck();assert(!first->be_flag);info.flag=0;
 for(unsigned i=0;i<35;++i){auto p=info.workAt(i);if(!p||!(p->be_flag&0x601))assert(info.create(0,i));}
 assert(info.countActiveWork()==35&&!info.create()&&last==info.workAt(34));
 assert(info.arrayPush(4));auto tool=info.create();assert(tool);info.destroy(tool);assert(info.arrayPop());assert(info.countActiveWork()==35&&last==info.workAt(34));
 current=5;cModInfoMgr ssinfo;assert(ssinfo.arrayAlloc(17)&&ssinfo.create());ssinfo.destroyAll();current=4;ssinfo.arrayFree();
 info.destroyAll();current=5;info.arrayFree();assert(allocations.empty());current=4;

 cPartsMgr m;assert(m.arrayAlloc(32));auto zero=m.createSequential(0);assert(zero);m.destroy(zero);auto a=m.createSequential(5);auto b=m.createSequential(4);assert(a&&b&&m.countActiveWork()==9);
 for(int j=0;j<4;++j)assert(a[j].pList==a+j+1);for(int j=0;j<3;++j)assert(b[j].pList==b+j+1);
 // A partial model release must not permit relocation of its surviving parts.
 m.destroy(a+1);auto kept=a+3;kept->value=77;unsigned before=calls;
 auto reused=m.create(0,1);assert(reused==a+1&&calls==before&&kept->value==77);
 m.destroy(a);m.destroy(a+1);a[2].pList=0;
 if(RE4DC_PARTS_DEMAND)assert(!m.prepareWork(0,8));
 assert(kept==m.workAt(3)&&kept->value==77&&b==m.workAt(5));
 m.destroy(a+2);m.destroy(a+3);m.destroy(a+4);
 auto c=m.createSequential(5);assert(c&&b==m.workAt(5)&&m.countActiveWork()==9);
 // Stable repeated-use backing: no allocation on destruction/recreation.
 before=calls;for(int i=0;i<100;++i){release(m,c);c=m.createSequential(5);assert(c);}assert(calls==before);
 // Delayed deletion remains reserved through dieCheck, with original ordering.
 m.flag=2;m.destroy(c);assert(c->be_flag&0x200);m.dieCheck();assert(c->be_flag&0x400);m.dieCheck();assert(!c->be_flag);m.flag=0;
 // Room parts park safely while the debug tool uses a separate raw array.
 before=m.countActiveWork();auto saved=m.pAlive;assert(m.arrayPush(8));auto debug=m.create();assert(debug);m.destroy(debug);assert(m.arrayPop());assert(m.pAlive==saved&&m.countActiveWork()==before&&b==m.workAt(5));
 // Fill every source logical slot; no reduced capacity, stable live pointers.
 std::vector<cParts*> stable;for(unsigned i=0;i<32;++i){auto p=m.workAt(i);if(!p||!(p->be_flag&0x601))p=m.create(0,i);assert(p);stable.push_back(p);}
 assert(m.countActiveWork()==32&&!m.create());for(unsigned i=0;i<32;++i)assert(m.workAt(i)==stable[i]);
 m.destroyAll();assert(m.countActiveWork()==0);current=5;m.arrayFree();assert(allocations.empty());
 // Independent subscreen owner and pressure/failure: no dangling live run.
 current=4;m.roomInit();m.arrayAlloc(12);auto live=m.createSequential(3);assert(live);live->value=123;
 if(RE4DC_PARTS_DEMAND){deny=true;assert(!m.prepareWork(8,2));deny=false;assert(live->value==123&&m.workAt(0)==live);}
 cPartsMgr ss;current=5;ss.arrayAlloc(10);assert(ss.createSequential(2));ss.destroyAll();current=4;ss.arrayFree();
 release(m,live);m.arrayFree();assert(allocations.empty());
 // roomInit follows the source heap reset; it must not free stale old backing.
 m.arrayAlloc(16);assert(m.createSequential(2));for(auto [p,info]:allocations)free(p);allocations.clear();m.roomInit();m.arrayAlloc(8);m.arrayFree();assert(allocations.empty());
}
'''
if __name__=='__main__':unittest.main()
