from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class NativeRenderProfile(unittest.TestCase):
 def test_exclusive_nested_clock_and_wrap(self):
  code=r'''#define RE4DC_NATIVE_RENDER_PROFILE 1
#define RE4DC_PROFILE_TEST 1
#include "native_render_profile.hpp"
#include <cassert>
namespace re4dc::profile { State state;unsigned test_clock=0; }
using namespace re4dc::profile;
int main(){
 Source source{};source.tick=32;Snapshot out{};begin();
 test_clock=250;
 {Scope a(Topology);test_clock=500;
  {Scope b(TransformProject);test_clock=1000;}
  test_clock=1250;
 }
 test_clock=1500;finish(out,7,source);
 assert(out.clock_valid==1 && out.frame==7 && out.source.tick==32 && !(out.sequence&1));
 assert(out.stage_us[Outside]==40 && out.stage_us[Topology]==40 && out.stage_us[TransformProject]==40);
 unsigned total=0;for(auto t:out.stage_us)total+=t;assert(total==120);
 // Rollover and a same-category nested scope must not double-charge elapsed time.
 test_clock=0xfffffff0U;begin();
 {Scope a(PacketPack);test_clock+=250;{Scope same(PacketPack);test_clock+=250;}}
 finish(out,8,source);assert(out.stage_us[PacketPack]==40);
 assert(out.calls[PacketPack]==1 && out.sequence==4);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'check.cpp').write_text(code)
   subprocess.run(['g++','-std=c++20','-I'+str(ROOT/'game/platform/include'),str(p/'check.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)

 def test_disabled_profile_retains_frame_source_without_clock(self):
  code=r'''#define RE4DC_NATIVE_RENDER_PROFILE 0
#include "native_render_profile.hpp"
#include <cassert>
using namespace re4dc::profile;
int main(){
 Source source{};source.tick=2387;source.room=0x100;source.player[0]=3.5f;
 Snapshot out{};begin();{Scope a(Topology);a.move(TransformProject);count(TextureUploads,2);}
 finish(out,2388,source);
 assert(out.sequence==2 && out.frame==2388 && out.source.tick==2387);
 assert(out.source.room==0x100 && out.source.player[0]==3.5f);
 assert(out.clock_valid==0 && out.clock_reads==0);
 for(auto t:out.stage_us)assert(t==0);for(auto v:out.metrics)assert(v==0);
 source.tick++;finish(out,2389,source);assert(out.sequence==4 && out.source.tick==2388);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'check.cpp').write_text(code)
   subprocess.run(['g++','-std=c++20','-I'+str(ROOT/'game/platform/include'),str(p/'check.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
