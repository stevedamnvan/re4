"""Exercise the actual native room loader with delayed/error queue results."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'), 'host compiler required')
class NativeRoomLoader(unittest.TestCase):
    def test_queue_ownership_and_failures(self):
        s=(ROOT/'src/game/read.cpp').read_text()
        begin=s.index('void ReadAreaData()\n{')
        end=s.index('// Boot:', begin)
        body=s[begin:end]
        fixture=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <stdexcept>
using u32=unsigned;
struct Global { int stage_no=1, room_id=0x120; u32 System_flg=0; void *pRoom=nullptr,*Rtp,*RoomMes,*pOsd,*pEmi; } global, *pG=&global;
char storage[128]; int fail, polls, sleeps, requests, lookups; u32 out_data_size;
struct DvdReadInfo { unsigned long addr[2][32]; unsigned size[2][32]; };
struct Queue { int ReadCheckInfo(int req,DvdReadInfo* info) {
assert(req==7); if (++polls<3) return 0;
if(fail==2) return -1;
info->size[0][0]=sizeof(storage); info->addr[0][0]=(unsigned long)storage; return 1;
} } Dvd;
int readRequest(const char* name,void* dst,int a,int b,int c,int mode) {
++requests; assert(!strcmp(name,"st1/r120.dar")); assert(dst==nullptr && !a && !b && !c); assert(mode==0x8104); return fail==1 ? -1 : 7;
}
#define DVD_READ_N readRequest
void TaskSleep(int n) { assert(n==1); ++sleeps; }
void StopwatchStart() {}
u32 StopwatchStop(void*) { return 123; }
void OSReport(const char*,...) {}
void re4dc_missing(const char*) { throw std::runtime_error("rejected"); }
int re4dc_ui_bind_room(void* p,unsigned size){assert(p==storage && size==sizeof(storage));return fail!=3;}
void PSet(void*& dst,void* src) { dst=src; }
void* GetDataExt(void* room,const char*,int n) { assert(room==storage && !n); ++lookups; return storage; }
'''
        checks=r'''
int main() {
ReadAreaData(); assert(polls==3 && sleeps==2 && requests==1 && lookups==4);
assert(pG->pRoom==storage && out_data_size==sizeof(storage));
// Source already-resident flag bypasses I/O but still resolves subfiles.
pG->System_flg=0x02000000; ReadAreaData(); assert(!pG->System_flg && requests==1 && lookups==8);
for(fail=1;fail<=2;++fail) { polls=0; pG->pRoom=nullptr;
try { ReadAreaData(); assert(false); } catch(const std::runtime_error&) {}
assert(pG->pRoom==nullptr && lookups==8);
}
fail=3;polls=0;try{ReadAreaData();assert(false);}catch(const std::runtime_error&){}
assert(lookups==8); // bad native identities never activate archive consumers

}
'''
        with tempfile.TemporaryDirectory() as d:
            cpp=Path(d)/'loader.cpp';exe=Path(d)/'loader'
            cpp.write_text(fixture+body+checks)
            subprocess.run(['g++','-std=c++17',str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_powerpc_room_body_unchanged(self):
        current=(ROOT/'src/game/read.cpp').read_text()
        original=subprocess.check_output(['git','show','d75144c:src/game/read.cpp'],cwd=ROOT,text=True)
        def preprocess(s):
            a=s.index('void ReadAreaData()\n{');b=s.index('// Boot:',a)
            return subprocess.check_output(['g++','-E','-P','-x','c++','-D__PPC__','-'],input=s[a:b],text=True)
        self.assertEqual(preprocess(current),preprocess(original))