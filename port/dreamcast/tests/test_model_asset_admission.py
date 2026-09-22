"""Actual asset adapter with synthetic source OT registrations, no disc assets."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class ModelAssetAdmission(unittest.TestCase):
 def test_source_registration_visibility_and_info_chain(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   (p/'model.h').write_text(r"""
#pragma once
struct ModelPart {unsigned size;char padding[28];};
struct ModelData {unsigned shift=0,nVtx=4,nNrm=4,displist_num=1,flags=0,shapeOfs=0,weight_palette_num=1,weight_ext_num=0,nParts=1;ModelPart* pParts;void* vtxOrig=nullptr;};
struct cModelInfo {unsigned be_flag=8;ModelData* pData; cModelInfo* pList=nullptr; cModelInfo* pNext=nullptr;};
struct cModel {unsigned kindid=0,be_flag=0;float invisible_factor=1,invisible_factor2=1;cModelInfo* pModelInfo;};
""")
   (p/'trans.h').write_text('#include "model.h"\nvoid ModelRender(cModel*);\n')
   (p/'trans_ot.h').write_text(r"""
#pragma once
constexpr unsigned OT_MAX=23;
struct OtData {void* data=nullptr;void (*func)(void*)=nullptr;OtData* next=nullptr;};
struct OtWork {OtData* list=nullptr;unsigned max=0;};
extern OtWork g_OtWork[OT_MAX];
""")
   (p/'check.cpp').write_text(r"""
#include "model.h"
#include "trans_ot.h"
#include "native_model.h"
#include <cassert>
#include <vector>
#include <set>
OtWork g_OtWork[OT_MAX]{};void ModelRender(cModel*){assert(false);}
void other(void*){assert(false);}
std::vector<Re4dcModelPart> seen;std::set<const void*> installed;Re4dcDrawPlanStats stats{};
unsigned begins=0,finishes=0,expected_parts=3,stats_reads=0;bool updating=false,enabled=true;
extern "C" int re4dc_model_diagnostic_enabled(){return enabled;}
extern "C" int re4dc_model_begin_asset_update(){assert(!updating);updating=true;++begins;stats_reads=0;return 0;}
extern "C" void re4dc_model_finish_asset_update(){assert(updating&&seen.size()==expected_parts&&stats_reads==1);updating=false;++finishes;} // visibility can change without dirty assets
extern "C" int re4dc_model_owned_source(const void* p,unsigned){return p!=nullptr;}
extern "C" const Re4dcDrawPlanStats* re4dc_model_draw_plan_stats(){assert(stats_reads==0?updating:!updating);++stats_reads;return &stats;}
extern "C" int re4dc_model_prepare_draw_plan(const Re4dcModelPart* p){assert(updating&&begins==finishes+1);seen.push_back(*p);if(installed.insert(p->stream).second)++stats.installs;return 1;}
extern "C" void re4dc_log(const char*,...){}
int main(){
 ModelPart parts[4]{};for(auto& p:parts)p.size=0;
 ModelData data[4];for(unsigned i=0;i<4;++i)data[i].pParts=parts+i;
 cModelInfo first{},hidden{},attachment{},scenery_info{};
 first.pData=data;hidden.pData=data+1;hidden.be_flag=0;attachment.pData=data+2;scenery_info.pData=data+3;
 first.pList=&hidden;hidden.pList=&attachment;first.pNext=&scenery_info; // wrong registry link must never be followed
 cModel actor{};actor.pModelInfo=&first;cModel scenery{};scenery.kindid=2;scenery.pModelInfo=&scenery_info;
 OtData heads[2];OtData actor_node{&actor,(void(*)(void*))ModelRender,&heads[0]};
 heads[1].func=(void(*)(void*))ModelRender;heads[1].next=&actor_node; // empty sentinel callback is ignored
 OtData unrelated{&scenery,other,nullptr};heads[0].next=&unrelated;
 g_OtWork[13]={heads,2};OtData late[1],scenery_node{&scenery,(void(*)(void*))ModelRender,nullptr};
 late[0].next=&scenery_node;g_OtWork[22]={late,1}; // include after-render source table
 re4dc_prepare_model_assets();assert(seen.size()==3 && stats.installs==3);
 assert(seen[0].part==parts && seen[1].part==parts+2 && seen[2].part==parts+3);
 assert(!seen[0].static_geometry && seen[2].static_geometry);
 assert(heads[1].next==&actor_node && actor_node.next==&heads[0]);
 seen.clear();re4dc_prepare_model_assets();assert(seen.size()==3 && stats.installs==3);
 hidden.be_flag=8;expected_parts=4;seen.clear();re4dc_prepare_model_assets();assert(seen.size()==4 && stats.installs==4);
 actor.invisible_factor2=0;expected_parts=1;seen.clear();re4dc_prepare_model_assets();assert(seen.size()==1 && seen[0].part==parts+3);
 scenery_info.be_flag=10;seen.clear();re4dc_prepare_model_assets();assert(seen.size()==1 && !seen[0].static_geometry);
 assert(begins==5&&finishes==5&&!updating&&stats_reads==2);
 enabled=false;re4dc_prepare_model_assets();assert(begins==5&&finishes==5);
}
""")
   inc=ROOT/'port/dreamcast/game/platform/include'
   subprocess.run(['g++','-std=c++20','-O2','-DRE4DC_D349_RENDERER_STACK=1','-fsanitize=address,undefined','-I'+str(p),'-I'+str(inc),str(p/'check.cpp'),str(ROOT/'port/dreamcast/game/model_asset_bridge.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
if __name__=='__main__':unittest.main()
