"""Source-backed compact range batches: independent oracle, bounded admission."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class NativeIndexSpans(unittest.TestCase):
 def test_ranges_seams_primitive_boundaries_and_partial_admission(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   (p/'fixture.cpp').write_text(r'''
#include "native_draw_plan.hpp"
#include <cassert>
#include <cstring>
#include <vector>
#include <array>
#include <map>
#include <tuple>
#include <algorithm>
using namespace re4dc::render;
using Corner=std::array<unsigned,3>;
struct Input {
 std::vector<unsigned char> source;
 std::vector<Corner> corners;
 std::vector<unsigned> boundaries{0};
 bool colored=false;
 void put(unsigned n){source.push_back(n>>8);source.push_back(n);}
 void add(unsigned op,std::vector<Corner> values){
  source.push_back(op);put(values.size());
  const unsigned unit=op==0x90?3:op==0x80?4:values.size();
  for(unsigned i=0;i<values.size();++i){const auto& c=values[i];put(c[0]);put(c[1]);if(colored)put(c[2]);put(i%4);
   corners.push_back(c);if((i+1)%unit==0)boundaries.push_back(corners.size());}
 }
};
struct Plans {
 std::vector<unsigned> structural,local;
 const NativeDrawPlan* topology=nullptr;
 const DrawLocalPlan* plan=nullptr;
 size_t full=0,used=0;
 Plans(const Input& in,size_t cap=100000){
  DrawPlanRequirements req;
  assert(inspect_draw_plan(in.source.data(),in.source.size(),in.colored,65536,65536,req));
  structural.resize((req.bytes+3)/4);
  topology=prepare_draw_plan(structural.data(),req.bytes,in.source.data(),in.source.size(),in.colored,req);assert(topology);
  full=prepare_draw_locals(nullptr,0,*topology,in.source.data(),in.colored);
  local.assign((cap+3)/4+8,0xa5a5a5a5);
  used=prepare_draw_locals(local.data(),cap,*topology,in.source.data(),in.colored);
  if(used){plan=(const DrawLocalPlan*)local.data();assert(used==plan->bytes);}
  for(size_t i=(cap+3)/4;i<local.size();++i)assert(local[i]==0xa5a5a5a5);
 }
};
void verify(const Input& in,const Plans& p){
 if(!p.plan)return;
 assert(p.used==12+p.plan->batches*20);
 unsigned covered=0,end=0;
 for(unsigned i=0;i<p.plan->batches;++i){const auto& b=p.plan->entries()[i];
  assert(b.first_corner>=end);end=b.first_corner+b.corner_count;assert(end<=in.corners.size());
  assert(std::find(in.boundaries.begin(),in.boundaries.end(),b.first_corner)!=in.boundaries.end());
  assert(std::find(in.boundaries.begin(),in.boundaries.end(),end)!=in.boundaries.end());
  assert(b.position_count<=160 && b.normal_count<=160 && (b.position_count||b.normal_count));
  std::map<unsigned,unsigned> pos,norm;
  std::map<unsigned,Corner> shade;
  for(unsigned j=b.first_corner;j<end;++j){auto c=in.corners[j];if(!in.colored)c[2]=0;
   if(b.position_count){const unsigned slot=c[0]-b.position_base;assert(slot<b.position_count);
    auto [it,fresh]=pos.emplace(slot,c[0]);assert(fresh||it->second==c[0]);}
   if(b.normal_count){const unsigned slot=c[1]-b.normal_base;assert(slot<b.normal_count);
    auto [it,fresh]=norm.emplace(slot,c[1]);assert(fresh||it->second==c[1]);}
   if(b.shade_mode!=LocalShadeMode::none){const unsigned slot=b.shade_mode==LocalShadeMode::by_position?c[0]-b.position_base:c[1]-b.normal_base;
    assert(slot<160);auto [it,fresh]=shade.emplace(slot,c);assert(fresh||it->second==c);}
  }
  covered+=b.corner_count;
 }
 assert(covered==p.plan->qualified_corners);
}
void verify_visitor(const Input& in){
 const auto source=in.source;
 Plans full(in);
 const auto structural=full.structural;
 std::vector<LocalBatch> visited;
 auto collect=[](void* ctx,const LocalBatch& batch){static_cast<std::vector<LocalBatch>*>(ctx)->push_back(batch);};
 visit_draw_locals(*full.topology,in.source.data(),in.colored,&visited,collect);
 assert(visited.size()==(full.plan?full.plan->batches:0));
 unsigned checksum=2166136261u,expected=2166136261u;
 for(unsigned i=0;i<visited.size();++i){
  if(i)assert(visited[i-1].first_corner<visited[i].first_corner);
  assert(std::memcmp(&visited[i],&full.plan->entries()[i],sizeof(LocalBatch))==0);
  const auto* a=reinterpret_cast<const unsigned char*>(&visited[i]);
  const auto* b=reinterpret_cast<const unsigned char*>(&full.plan->entries()[i]);
  for(unsigned j=0;j<sizeof(LocalBatch);++j){checksum=(checksum^a[j])*16777619u;expected=(expected^b[j])*16777619u;}
 }
 assert(checksum==expected);
 const auto count=visited.size();
 visit_draw_locals(*full.topology,nullptr,in.colored,&visited,collect);
 visit_draw_locals(*full.topology,in.source.data(),in.colored,nullptr,nullptr);
 assert(count==visited.size()&&source==in.source&&structural==full.structural);
}
std::vector<Corner> repeated(Corner a,Corner b,unsigned count){std::vector<Corner> r;for(unsigned i=0;i<count;++i)r.push_back(i%2?a:b);return r;}
int main(){
 // Identical metadata size for four vs 9000 source references; no copied corner
 // table and no modifications to original source bytes.
 Input short_input;short_input.add(0x98,repeated({1000,2000,0},{1001,2001,0},4));
 Input long_input;long_input.add(0x98,repeated({1000,2000,0},{1001,2001,0},9000));
 auto saved=long_input.source;Plans a(short_input),b(long_input);verify(short_input,a);verify(long_input,b);
 assert(a.used==32&&b.used==32&&saved==long_input.source);
 const auto& dense=b.plan->entries()[0];assert(dense.position_base==1000&&dense.position_count==2&&dense.normal_base==2000&&dense.normal_count==2);
 assert(dense.shade_mode==LocalShadeMode::by_position);
 // A whole strip with sparse positions retains normal slots and no invalid
 // position slot. Its exact normal->position/color relation can shade directly.
 Input normal_only;normal_only.add(0xa0,repeated({10,40,0},{65000,41,0},12));Plans n(normal_only);verify(normal_only,n);
 assert(n.plan->batches==1&&n.plan->entries()[0].position_count==0&&n.plan->entries()[0].normal_count==2);
 assert(n.plan->entries()[0].shade_mode==LocalShadeMode::by_normal);
 Input position_only;position_only.add(0x98,repeated({65534,1,0},{65535,65530,0},12));Plans po(position_only);verify(position_only,po);
 assert(po.plan->entries()[0].position_count==2&&po.plan->entries()[0].normal_count==0);
 assert(po.plan->entries()[0].shade_mode==LocalShadeMode::by_position);
 // Both direct ranges can be safe while neither position nor normal uniquely
 // identifies a lit pair. Keep transforms; never alias packed color slots.
 Input seams;seams.add(0x98,{{0,0,0},{0,1,0},{1,0,0},{1,1,0},{0,0,0}});Plans se(seams);verify(seams,se);
 assert(se.plan->entries()[0].position_count==2&&se.plan->entries()[0].normal_count==2&&se.plan->entries()[0].shade_mode==LocalShadeMode::none);
 // Source color identity is part of shade validity even with identical p/n.
 Input colors;colors.colored=true;colors.add(0x98,{{4,9,0},{4,9,1},{4,9,0},{4,9,1}});Plans co(colors);verify(colors,co);
 assert(co.plan->entries()[0].shade_mode==LocalShadeMode::none);
 Input colors_by_n;colors_by_n.colored=true;colors_by_n.add(0x98,{{4,9,0},{4,10,1},{4,9,0},{4,10,1}});Plans cn(colors_by_n);verify(colors_by_n,cn);
 assert(cn.plan->entries()[0].shade_mode==LocalShadeMode::by_normal);
 // Legal independent primitives are separable; whole wide strips/fans are not.
 Input triangles;triangles.add(0x90,{{0,0,0},{0,0,0},{0,0,0},{400,400,0},{400,400,0},{400,400,0}});
 Plans tr(triangles);verify(triangles,tr);assert(tr.plan->batches==2&&tr.plan->qualified_corners==6);
 Input quad;quad.add(0x80,{{1,1,0},{1,1,0},{1,1,0},{1,1,0},{401,401,0},{401,401,0},{401,401,0},{401,401,0}});Plans qu(quad);verify(quad,qu);assert(qu.plan->batches==2);
 Input wide;wide.add(0x98,triangles.corners);Plans wi(wide);assert(wi.full==0&&wi.used==0);
 // Sparse invalid whole primitive makes a real uncovered ordinal gap.
 Input gaps;gaps.add(0x98,repeated({10,10,0},{11,11,0},6));gaps.add(0x98,triangles.corners);gaps.add(0xa0,repeated({400,400,0},{401,401,0},6));
 Plans ga(gaps);verify(gaps,ga);assert(ga.plan->batches==2&&ga.plan->entries()[1].first_corner==12);
 // Bounded metadata selects the highest avoided work, not the first small part;
 // sort survivors back into source order and honor exact capacity fences.
 Input ranked;ranked.add(0x98,repeated({0,0,0},{1,1,0},4));ranked.add(0x98,repeated({1000,1000,0},{1001,1001,0},100));ranked.add(0x98,repeated({3000,3000,0},{3001,3001,0},30));
 Plans all(ranked),one(ranked,32),two(ranked,52),tiny(ranked,31);verify(ranked,all);verify(ranked,one);verify(ranked,two);
 assert(all.plan->batches==3&&one.plan->batches==1&&two.plan->batches==2&&tiny.used==0);
 assert(one.plan->entries()[0].first_corner==4&&one.plan->entries()[0].corner_count==100);
 assert(two.plan->entries()[0].first_corner==4&&two.plan->entries()[1].first_corner==104);
 // Exactly 160 slots accepted, 161 rejected independently; source IDs reach
 // their full unsigned16 range without a sentinel collision or signed wrap.
 Input edge;edge.add(0x98,repeated({65376,65535,0},{65535,65535,0},8));Plans ed(edge);verify(edge,ed);assert(ed.plan->entries()[0].position_count==160);
 Input beyond;beyond.add(0x98,repeated({65375,65535,0},{65535,65535,0},8));Plans be(beyond);verify(beyond,be);assert(be.plan->entries()[0].position_count==0);
 // Repeated primitive span compression changes no source ordinal accounting.
 Input repeated_commands;for(unsigned i=0;i<50;++i)repeated_commands.add(0x90,{{7,8,0},{7,8,0},{7,8,0}});
 Plans re(repeated_commands);verify(repeated_commands,re);assert(re.topology->primitive_count==1&&re.plan->batches==1&&re.plan->qualified_corners==150&&re.used==32);
 // Forced capacity variants on a mixed colored fixture independently verify
 // every admitted source identity and primitive boundary, not builder output.
 Input mixed;mixed.colored=true;
 for(unsigned i=0;i<80;++i){unsigned p=(i%5)*400,n=(i%7)*200;auto cs=repeated({p,n,i%3},{p+1,n+1,(i+1)%3},6+(i%4)*3);mixed.add(i%3==0?0x90:0x98,cs);}
 for(const auto* input:{&short_input,&long_input,&normal_only,&position_only,&seams,&colors,&colors_by_n,&triangles,&quad,&wide,&gaps,&ranked,&edge,&beyond,&repeated_commands,&mixed})verify_visitor(*input);
 for(unsigned cap=0;cap<512;cap+=7){Plans test(mixed,cap);verify(mixed,test);assert(test.used<=cap);}
}
''')
   room=ROOT/'port/dreamcast/room'
   for mode in (['-O2'],['-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer']):
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',*mode,'-I'+str(room),str(p/'fixture.cpp'),str(room/'native_draw_plan.cpp'),'-o',str(p/'check')],check=True)
    subprocess.run([str(p/'check')],check=True)

if __name__=='__main__':unittest.main()
