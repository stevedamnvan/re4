"""Use the real pre-transfer guard to exercise fixed-region ownership."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class ResidentBounds(unittest.TestCase):
    def test_owner_and_multi_part_bounds(self):
        cpp=r"""
#include "resident_bounds.hpp"
#include <cassert>
Re4dcMemLayout re4dc_mem{};
int main(){
 re4dc_mem.core=0x1000;re4dc_mem.option=0x3000;re4dc_mem.player=0x4000;
 re4dc_mem.weapon=0x6000;re4dc_mem.heap=0x7000;
 const char* owner;unsigned long cap;
 for(unsigned long start:{0x1000UL,0x3000UL,0x4000UL,0x6000UL}){
  unsigned long size=(start==0x1000 || start==0x4000)?0x2000:0x1000;
  assert(re4dc_resident_read_fits(start,start,size,false,&owner,&cap) && cap==size);
  assert(!re4dc_resident_read_fits(start,start,size+1,false,&owner,&cap));
  assert(re4dc_resident_read_fits(start,start+size-32,32,false,&owner,&cap));
  assert(!re4dc_resident_read_fits(start,start+size,32,false,&owner,&cap));
  assert(!re4dc_resident_read_fits(start,start-1,1,false,&owner,&cap));
  assert(!re4dc_resident_read_fits(start,start,~0UL,false,&owner,&cap));
 }
 assert(re4dc_resident_read_fits(0x4000,0x4000,0x3000,true,&owner,&cap));
 assert(!re4dc_resident_read_fits(0x4000,0x4000,0x3001,true,&owner,&cap));
 assert(re4dc_resident_read_fits(0x8000,0x8000,0x4000,false,&owner,&cap) && !owner);
 // A compact option file is read directly; the old full file must not reach
 // the adjacent persistent player region through the plain-file DVD path.
 re4dc_mem.option=0x100000;re4dc_mem.player=0x100000+149920;
 re4dc_mem.weapon=re4dc_mem.player+846656;re4dc_mem.heap=re4dc_mem.weapon+247776;
 assert(re4dc_resident_read_fits(re4dc_mem.option,re4dc_mem.option,149920,false,&owner,&cap) && cap==149920);
 assert(!re4dc_resident_read_fits(re4dc_mem.option,re4dc_mem.option,259648,false,&owner,&cap));
}
"""
        cpp=cpp.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'test.cpp';p.write_text(cpp);exe=root/'test'
            subprocess.run(['g++','-std=c++17','-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(p),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
