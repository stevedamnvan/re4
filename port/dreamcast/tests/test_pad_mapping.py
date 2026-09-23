"""Host-compile platform/pad.cpp's controller mapping (re4dcMapPad) and check it."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class PadMapping(unittest.TestCase):
 def test_standard_and_dual_mapping(self):
  code=(ROOT/'game/platform/pad.cpp').read_text()
  body=code[code.index('typedef signed char s8;'):code.index('// Scripted input fixture:')]
  prefix=r'''#include <cstring>
#include <cassert>
#include <cstdio>
#define BIT(n) (1u<<(n))
#define CONT_C BIT(0)
#define CONT_B BIT(1)
#define CONT_A BIT(2)
#define CONT_START BIT(3)
#define CONT_DPAD_UP BIT(4)
#define CONT_DPAD_DOWN BIT(5)
#define CONT_DPAD_LEFT BIT(6)
#define CONT_DPAD_RIGHT BIT(7)
#define CONT_Z BIT(8)
#define CONT_Y BIT(9)
#define CONT_X BIT(10)
'''
  suffix=r'''
static Re4dcPadMap m; static PADStatus p;
static void poll(u32 buttons,int ctx,int caps=0,int lt=0,int rt=0,int jx=0,int jy=0,int j2x=0,int j2y=0){
 Re4dcPadIn in={buttons,lt,rt,jx,jy,j2x,j2y};memset(&p,0,sizeof(p));re4dcMapPad(&in,ctx,caps,&m,&p);}
enum{L=RE4DC_PAD_CTX_LOOK,N=RE4DC_PAD_CTX_NATIVE,Zm=RE4DC_PAD_CTX_ZOOM};
int main(){
 // idle: nothing, whatever the context (fixture runs stay bit-identical)
 for(int c=0;c<3;c++){poll(0,c);assert(p.button==0&&!p.stickX&&!p.stickY&&!p.substickX&&!p.substickY&&!p.triggerLeft&&!p.triggerRight);}
 // face buttons and start as on the GameCube
 poll(CONT_A|CONT_B|CONT_X|CONT_Y|CONT_START,L);assert(p.button==(PAD_BUTTON_A|PAD_BUTTON_B|PAD_BUTTON_X|PAD_BUTTON_Y|PAD_BUTTON_START));
 // stick: SDK clamp ranges (72 on the axis, 40/40 corner, 15 dead zone), maple Y flipped
 poll(0,N,0,0,0,127,0);assert(p.stickX==72&&p.stickY==0);
 poll(0,N,0,0,0,-128,-128);assert(p.stickX==-40&&p.stickY==40);
 poll(0,N,0,0,0,0,-128);assert(p.stickY==72);
 poll(0,N,0,0,0,18,-18);assert(p.stickX==0&&p.stickY==0);
 // triggers: 30 dead zone, 150 max, digital bit with any analog value (PadRead's own rule)
 poll(0,N,0,25,30);assert(!p.triggerLeft&&!p.triggerRight&&p.button==0);
 poll(0,N,0,255,100);assert(p.triggerLeft==150&&p.triggerRight==70&&p.button==(PAD_TRIGGER_L|PAD_TRIGGER_R));
 // standard pad, NATIVE: D-pad is the D-pad
 poll(CONT_DPAD_UP|CONT_DPAD_LEFT,N);assert(p.button==(PAD_BUTTON_UP|PAD_BUTTON_LEFT)&&!p.substickX&&!p.substickY);
 poll(0,N);
 // LOOK: 8-way C-stick, no D-pad bits
 poll(CONT_DPAD_UP,L);assert(p.button==0&&p.substickX==0&&p.substickY==59);
 poll(CONT_DPAD_UP|CONT_DPAD_RIGHT,L);assert(p.substickX==31&&p.substickY==31);
 poll(CONT_DPAD_LEFT,L);assert(p.substickX==-59&&p.substickY==0);
 poll(CONT_DPAD_DOWN|CONT_DPAD_LEFT,L);assert(p.substickX==-31&&p.substickY==-31);
 poll(0,L);assert(!(p.button&PAD_TRIGGER_Z));  // that press touched other directions: no Z
 // ZOOM: up/down -> C-stick Y, left/right stay D-pad
 poll(CONT_DPAD_UP|CONT_DPAD_RIGHT,Zm);assert(p.substickY==30&&p.substickX==0&&p.button==PAD_BUTTON_RIGHT);
 poll(CONT_DPAD_DOWN,Zm);assert(p.substickY==-30&&p.button==0);
 poll(0,Zm);assert(p.button==0);
 // Z: lone D-pad-down tap in LOOK -> Z for 2 polls after release
 poll(CONT_DPAD_DOWN,L);assert(p.substickY==-59&&p.button==0);
 poll(CONT_DPAD_DOWN,L);poll(CONT_DPAD_DOWN,L);
 poll(0,L);assert(p.button==PAD_TRIGGER_Z);
 poll(0,L);assert(p.button==PAD_TRIGGER_Z);
 poll(0,L);assert(p.button==0);
 // held longer than the tap window: look only
 for(int i=0;i<Z_TAP_POLLS+1;i++)poll(CONT_DPAD_DOWN,L);
 poll(0,L);assert(p.button==0);
 // started outside LOOK (menu, aiming): no Z
 poll(CONT_DPAD_DOWN,N);assert(p.button==PAD_BUTTON_DOWN);poll(CONT_DPAD_DOWN,L);poll(0,L);assert(p.button==0);
 // tap across a context change: no Z
 poll(CONT_DPAD_DOWN,L);poll(CONT_DPAD_DOWN,Zm);poll(0,L);assert(p.button==0);
 assert(!m.dual);
 // dual detection: one far joy2 poll is not enough, two consecutive are
 poll(0,L,0,0,0,0,0,0,100);assert(!m.dual&&p.substickY==0);
 poll(0,L);poll(0,L,0,0,0,0,0,0,100);assert(!m.dual);
 poll(0,L,0,0,0,0,0,0,100);assert(m.dual&&p.substickY==-59);
 // dual: D-pad native in every context, joy2 clamped, C / Z -> Z
 poll(CONT_DPAD_UP,L);assert(p.button==PAD_BUTTON_UP&&p.substickY==0);
 poll(CONT_C,L);assert(p.button==PAD_TRIGGER_Z);
 poll(0,L,0,0,0,0,0,127,0);assert(p.substickX==59);
 // capabilities or a C / Z press classify immediately
 memset(&m,0,sizeof(m));poll(0,L,1);assert(m.dual);
 memset(&m,0,sizeof(m));poll(CONT_Z,L);assert(m.dual&&p.button==PAD_TRIGGER_Z);
 // debug chords (pad 0): L+START masked only while the debug menu is armed, for the whole press
 enum{M=RE4DC_PAD_DBG_MENU,SZ=RE4DC_PAD_DBG_SUBSCREEN_Z};const u16 S=PAD_BUTTON_START,TL=PAD_TRIGGER_L,TZ=PAD_TRIGGER_Z;
 memset(&m,0,sizeof(m));
 assert(re4dcBlockDebugChords(S,M,&m)==S);assert(re4dcBlockDebugChords(0,M,&m)==0);          // plain START: options
 assert(re4dcBlockDebugChords(TL,M,&m)==TL);assert(re4dcBlockDebugChords(TL|S,M,&m)==TL);    // L then START: masked
 assert(re4dcBlockDebugChords(S,M,&m)==0);                                                    // L released, same press: still masked
 assert(re4dcBlockDebugChords(0,M,&m)==0);assert(re4dcBlockDebugChords(S,M,&m)==S);           // next press passes
 assert(re4dcBlockDebugChords(S|TL,M,&m)==(S|TL));                                            // START first, then L: no trigger edge, untouched
 re4dcBlockDebugChords(0,0,&m);assert(re4dcBlockDebugChords(TL|S,0,&m)==(TL|S));              // menu not armed: untouched
 re4dcBlockDebugChords(0,0,&m);
 assert(re4dcBlockDebugChords(TZ|PAD_BUTTON_A,SZ,&m)==PAD_BUTTON_A);assert(re4dcBlockDebugChords(TZ,0,&m)==TZ);  // Z only in the sub screen
 puts("pad mapping ok");
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.cpp').write_text(prefix+body+suffix)
   subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wno-unused-function',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
