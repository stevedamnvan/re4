// Asset-lifetime adapter for the source's accepted model registrations.
// Reuses the original OT and archive owner; no second visibility/model registry.
#include "model.h"
#include "trans.h"
#include "trans_ot.h"
#include "native_model.h"
#include "re4dc_platform.h"
#include <cstdint>
#ifndef RE4DC_COPY_LEAN
#define RE4DC_COPY_LEAN 0 // obj/frontend30.h (D367 frontend30)
#endif
#ifndef RE4DC_FRONT_LEAN
#define RE4DC_FRONT_LEAN 0
#endif
#if RE4DC_FRONT_LEAN && RE4DC_D349_RENDERER_STACK
extern "C" int re4dc_model_asset_update_idle();
namespace {
// Identity of what the registration walk below would visit: every accepted
// model registration and drawn info in walk order, with the words that decide
// a part's plan request (static eligibility). Part streams are immutable per
// ModelData. Equal signature + an idle plan owner = the walk installs nothing.
struct WalkSignature { unsigned a,b,n; bool operator==(const WalkSignature& o)const{return a==o.a&&b==o.b&&n==o.n;} };
WalkSignature last_walk{0,0,~0U};
WalkSignature walk_signature(){
    WalkSignature s{2166136261U,0x9e3779b9U,0};
    auto mix=[&](unsigned w){s.a=(s.a^w)*16777619U;s.b=(s.b+w)*0x85ebca6bU;s.b^=s.b>>13;++s.n;};
    for(unsigned priority=0;priority<2;++priority)for(unsigned table=0;table<OT_MAX;++table){
        const auto& ot=g_OtWork[table];
        if(!ot.list || !ot.max)continue;
        for(auto* node=&ot.list[ot.max-1];node;node=node->next){
            if(!node->data || node->func!=(void (*)(void*))ModelRender)continue;
            auto* model=static_cast<cModel*>(node->data);
            if((model->kindid<=1)!=(priority==0) || model->invisible_factor*model->invisible_factor2==0.f)continue;
            mix(unsigned(reinterpret_cast<std::uintptr_t>(model)));mix(model->be_flag&0x4000);mix(model->kindid);
            for(auto* info=model->pModelInfo;info;info=info->pList){
                if(!(info->be_flag&8))continue;
                mix(unsigned(reinterpret_cast<std::uintptr_t>(info)));
                mix(unsigned(reinterpret_cast<std::uintptr_t>(info->pData)));mix(info->be_flag&2);
            }
        }
    }
    return s;
}
}
#endif
extern "C" void re4dc_prepare_model_assets(){
#if RE4DC_D349_RENDERER_STACK
    if(!re4dc_model_diagnostic_enabled())return;
#if RE4DC_FRONT_LEAN
    // Same registrations as the last walk and nothing pending in the plan
    // owner: every part would hit (or keep its negative admission) again.
    {
        const WalkSignature now=walk_signature();
        const bool idle=re4dc_model_asset_update_idle()!=0;
        const bool same=now==last_walk;
        last_walk=now;
        if(idle && same)return;
    }
#endif
    re4dc_model_begin_asset_update(); // acknowledge source owner/publication changes
    const auto previous=*re4dc_model_draw_plan_stats();
    unsigned models=0,parts=0,prepared=0,rejected=0;
    // main.cpp: Render_before -> Render -> ClearOt -> tasks -> Trans. These are
    // the already accepted registrations for this render, not all resident BINs.
    // Prefer measured actor working sets for finite metadata admission only;
    // source draw order, update eligibility and resource ownership are unchanged.
    for(unsigned priority=0;priority<2;++priority)for(unsigned table=0;table<OT_MAX;++table){
        const auto& ot=g_OtWork[table];
        if(!ot.list || !ot.max)continue;
        for(auto* node=&ot.list[ot.max-1];node;node=node->next){
            // Empty bucket sentinels do not initialize func. Check data first.
            if(!node->data || node->func!=(void (*)(void*))ModelRender)continue;
            auto* model=static_cast<cModel*>(node->data);
            if((model->kindid<=1)!=(priority==0) || model->invisible_factor*model->invisible_factor2==0.f)continue;
            for(auto* info=model->pModelInfo;info;info=info->pList){
                if(!(info->be_flag&8))continue;
                const auto* d=info->pData;
                if(!re4dc_model_owned_source(d,sizeof(ModelData)))continue;
                if(d->shift>30 || !d->nVtx || !d->nNrm)continue;
                ++models;
                auto* part=d->pParts;
#if RE4DC_COPY_LEAN
                // Every word the plan request reads is assigned per part below:
                // one zero-initialised view instead of a ~300-byte memset per part.
                Re4dcModelPart p{};
#endif
                for(unsigned i=0;i<d->displist_num;++i){
                    if(!re4dc_model_owned_source(part,sizeof(ModelPart))){++rejected;break;}
                    if(part->size>1024*1024 || !re4dc_model_owned_source(part+1,part->size)){++rejected;break;}
#if !RE4DC_COPY_LEAN
                    Re4dcModelPart p{};
#endif
                    p.part=part;p.stream=(const unsigned char*)(part+1);
                    p.stream_bytes=part->size;p.position_count=d->nVtx;p.normal_count=d->nNrm;
                    p.flags=d->flags;p.positions=(const unsigned char*)d->vtxOrig;
                    p.position_stride=8;p.shift=d->shift;
                    // Bounds qualify only when the eventual rigid draw uses
                    // these immutable positions and this quantization scale.
                    const bool rigid=(model->be_flag&0x4000) ||
                        (d->weight_palette_num<=1 && d->weight_ext_num<=0xff && !(info->be_flag&2) && d->nParts==1);
                    p.static_geometry=rigid && model->kindid==2 && !d->shapeOfs && !(info->be_flag&2);
                    const int result=re4dc_model_prepare_draw_plan(&p);
                    ++parts;if(result>0)++prepared;else if(result<0)++rejected;
                    part=(ModelPart*)((unsigned char*)(part+1)+part->size);
                }
            }
        }
    }
    re4dc_model_finish_asset_update(); // publish local admission after every accepted registration
    const auto* stats=re4dc_model_draw_plan_stats();
    if(stats->installs!=previous.installs || stats->invalid!=previous.invalid)re4dc_log("native source OT asset update: models=%u parts=%u prepared=%u rejected=%u metadata=%u/%u decoded_total=%u\n",
              models,parts,prepared,rejected,stats->used,stats->capacity,stats->source_bytes);
#endif
}
