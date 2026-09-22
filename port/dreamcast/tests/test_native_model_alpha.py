"""Source model alpha selection; no full GX or mask rendering claim."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class ModelAlpha(unittest.TestCase):
 def test_actual_source_channel_state(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);game=ROOT/'port/dreamcast/game'
   (p/'check.cpp').write_text(r'''#include <cassert>
struct GXColor{unsigned char r,g,b,a;};
extern "C" {
void GXSetChanCtrl(int,unsigned char,int,int,unsigned long,int,int);
void GXSetChanMatColor(int,GXColor);
unsigned re4dc_gx_model_alpha();
}
int main(){
 assert(re4dc_gx_model_alpha()==255);
 for(unsigned n=0;n<256;++n){
  GXSetChanCtrl(2,0,0,0,0,2,2);GXSetChanMatColor(4,{7,11,13,(unsigned char)n});
  assert(re4dc_gx_model_alpha()==n);
  for(int unrelated:{0,1,3,5}){
   GXSetChanCtrl(unrelated,1,0,1,255,2,1);GXSetChanMatColor(unrelated,{9,19,29,31});
   assert(re4dc_gx_model_alpha()==n);
  }
  GXSetChanCtrl(2,0,1,1,0,2,2);assert(re4dc_gx_model_alpha()==(n|256));
  GXSetChanCtrl(4,1,0,0,1,2,1);assert(re4dc_gx_model_alpha()==(n|512));
  GXSetChanCtrl(4,0,0,0,0,0,2);assert(re4dc_gx_model_alpha()==n);
 }
 GXSetChanMatColor(2,{0,0,0,33});assert(re4dc_gx_model_alpha()==33);
 GXSetChanCtrl(2,0,0,2,0,0,0);assert(re4dc_gx_model_alpha()==(512|33));
}
'''.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>'))
   subprocess.run(['g++','-std=c++17','-O2','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined','-Wl,--gc-sections','-I'+str(game/'platform/include'),str(p/'check.cpp'),str(game/'platform/gx_stub.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
if __name__=='__main__':unittest.main()
