"""Focused source-GX light-state capture and selected prepared evaluator."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class SourceLighting(unittest.TestCase):
 def test_actual_source_state_is_copied_selected_and_evaluated(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   code=r'''
#include <cassert>
#include <cmath>
#include "GX_IMPLEMENTATION"
int main(){
 using namespace re4dc::render;
 GXLightObj lamp{};
 GXInitLightPos(&lamp,0,0,20);GXInitLightDir(&lamp,0,0,-1);
 GXInitLightColor(&lamp,{255,0,0,255});
 GXInitLightSpot(&lamp,60,0);GXInitLightDistAttn(&lamp,20,.5f,3);
 GXLoadLightObjImm(&lamp,128);
 GXSetChanCtrl(0,1,0,0,128,2,1);
 GXSetChanAmbColor(0,{10,0,0,255});GXSetChanMatColor(0,{255,255,255,255});
 GXSetTevColorOp(0,0,0,0,1,0);
 const float m[3][4]={{1,0,0,0},{0,0,1,0},{0,-1,0,0}};
 GXLoadNrmMtxImm(m,0);
 SourceLighting state{};re4dc_gx_model_lighting(&state);
 assert(state.mask==128 && state.normal_matrix[6]==1 && state.normal_matrix[9]==-1);
 assert(state.lights[7].direction[2]==1 && state.lights[7].k[2]==.0025f);
 GXInitLightColor(&lamp,{0,255,0,255}); // pointer to caller's stack is never retained
 auto lights=prepare_actor_lights(state);assert(lights.count==1);
 unsigned char white[]={255,255,255,255};float rgb[3];
 evaluate_prepared_source_lighting(0,0,0,0,0,1,state,lights,white,rgb);
 assert(std::abs(rgb[0]-(.5f+10.f/255))<.000001f && rgb[1]==0 && rgb[2]==0);
 GXLoadLightObjImm(&lamp,1); // non-selected lights must not affect this model
 re4dc_gx_model_lighting(&state);lights=prepare_actor_lights(state);
 evaluate_prepared_source_lighting(0,0,0,0,0,1,state,lights,white,rgb);assert(rgb[1]==0);
 GXLoadLightObjImm(&lamp,128);re4dc_gx_model_lighting(&state);
 evaluate_prepared_source_lighting(0,0,0,0,0,1,state,prepare_actor_lights(state),white,rgb);
 assert(std::abs(rgb[0]-10.f/255)<.000001f && std::abs(rgb[1]-.5f)<.000001f);
 GXSetChanCtrl(0,0,0,1,0,2,2);GXSetChanMatColor(2,{0,0,0,37});
 re4dc_gx_model_lighting(&state);
 unsigned char color[]={64,128,255,255};
 evaluate_prepared_source_lighting(0,0,0,0,0,1,state,prepare_actor_lights(state),color,rgb);
 assert(rgb[0]==64.f/255 && rgb[1]==128.f/255 && rgb[2]==1);
 assert(re4dc_gx_model_alpha()==37);
}
'''.replace('GX_IMPLEMENTATION',str(ROOT/'port/dreamcast/game/platform/gx_stub.cpp'))
   (p/'test.cpp').write_text(code)
   result=subprocess.run(['g++','-std=c++20','-O2','-w','-fpermissive','-DRE4DC_D349_RENDERER_STACK=1','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fsanitize=address,undefined','-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(p/'test.cpp'),str(ROOT/'port/dreamcast/room/source_lighting.cpp'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
