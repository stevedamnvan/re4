// Asset-lifetime adapter for the source's accepted model registrations.
// Reuses the original OT and archive owner; no second visibility/model registry.
#include "model.h"
#include "trans.h"
#include "trans_ot.h"
#include "native_model.h"
#include "re4dc_platform.h"
extern "C" void re4dc_prepare_model_assets(){
#if RE4DC_D349_RENDERER_STACK
    if(!re4dc_model_diagnostic_enabled())return;
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
                for(unsigned i=0;i<d->displist_num;++i){
                    if(!re4dc_model_owned_source(part,sizeof(ModelPart))){++rejected;break;}
                    if(part->size>1024*1024 || !re4dc_model_owned_source(part+1,part->size)){++rejected;break;}
                    Re4dcModelPart p{};p.part=part;p.stream=(const unsigned char*)(part+1);
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
