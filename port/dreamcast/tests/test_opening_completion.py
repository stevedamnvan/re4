"""Execute native pre-allocation opening completion and test its scope."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class OpeningCompletion(unittest.TestCase):
 def test_first_play_only_and_source_handoff(self):
  source=(ROOT/'src/game/game.cpp').read_text()
  start=source.index('static bool nativeSkipOpeningRoom()')
  body=source[start:source.index('\n#endif',start)]
  fixture=r'''
#include <cassert>
#include <cstring>
struct Vec { float x,y,z; };
struct Global {
 unsigned room_id=0x120,game_cnt=0,System_flg=0x2000,pl_type=0,Part=0;
 unsigned Scenario_flg[1]={0x80},room_id_prev=0,Part_old=0;
 Vec NextPos{},sub_pos{}; float NextY=9,sub_angle=9;
 unsigned next_room=0,next_point=3,JumpPoint=4,r_continue_cnt=7;
 unsigned Rno0=2,Rno1=3,Rno2=4,Rno3=5;
 unsigned life=900,pesetas=1000,weapon=35;
} state,*pG=&state;
int marks;
struct Rooms { void setPassed(unsigned r,unsigned p) {assert(r==0x120 && p==0);++marks;} } RoomData;
void OSReport(const char*,...) {}
'''
  checks=r'''
int main(){
 for(int guard=0;guard<4;++guard){ state=Global{};
 if(guard==0)state.room_id=0x101;
 if(guard==1)state.game_cnt=1;
 if(guard==2)state.System_flg=0x100;
 if(guard==3)state.pl_type=2;
 Global before=state;assert(!nativeSkipOpeningRoom());assert(!memcmp(&before,&state,sizeof(state)));
 } assert(marks==0);
 state=Global{}; assert(nativeSkipOpeningRoom());assert(marks==1);
 assert(state.room_id==0x100 && state.room_id_prev==0x120 && state.next_room==0x100);
 assert(state.sub_pos.x==-109450 && state.sub_pos.y==-515 && state.sub_pos.z==820);
 assert(state.NextPos.x==state.sub_pos.x && state.sub_angle==0 && state.NextY==0);
 assert(state.Scenario_flg[0]==0x90 && state.System_flg==0x400);
 assert(state.Rno0==1 && !state.Rno1 && !state.Rno2 && !state.Rno3);
 assert(!state.Part && !state.JumpPoint && !state.next_point && !state.r_continue_cnt);
 assert(state.life==900 && state.pesetas==1000 && state.weapon==35);
 assert(!nativeSkipOpeningRoom() && marks==1);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'test.cpp';out=Path(d)/'test';p.write_text(fixture+body+checks)
   subprocess.run(['g++','-std=c++17',str(p),'-o',str(out)],check=True)
   subprocess.run([str(out)],check=True)
 def test_source_movie_skip_bypasses_car_events(self):
  source=(ROOT/'src/st1/r120.cpp').read_text()
  self.assertIn('if (Sofdec.m_be_flag & 0x20)',source)
  self.assertIn('pG->Scenario_flg[0] |= 0x10;',source)
  self.assertIn('Vec pos = {-109450.0f, -515.0f, 820.0f}',source)
  self.assertIn('SceAtExecRoomJump(0x100, &pos, &rot, 0)',source)
  # Numeric handoff comes from this source, not debug roominfo jump points.