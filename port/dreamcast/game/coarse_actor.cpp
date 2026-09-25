// COARSE_LEON=1: isolated, opaque 4K Leon presentation proof. The game owns
// the pose, part visibility and simulation. Input is the offline-qualified
// native actor representation; no source game data is overwritten.
#include "global.h"
#include "model.h"
#include "native_actor.hpp"
#include "leon4k_runtime.h" // private generated asset, outside the repository
#include <cstring>
#if RE4DC_COARSE_SKIN_FTRV
#include "coarse_skin.h"
#endif

extern "C" void re4dc_log(const char*, ...);
extern "C" void GXGetProjectionv(float*);
extern "C" void GXGetViewportv(float*);
extern "C" void re4dc_bind_actor_frame();
extern "C" int re4dc_coarse_leon_texture_ready(const Re4dcUiImage*,unsigned,unsigned);

#if RE4DC_COARSE_GANADO
extern "C" int re4dc_coarse_ganado_source(const void*,Re4dcActorSource*);
extern "C" int re4dc_coarse_ganado_texture_key(const Re4dcUiImage*,unsigned*,unsigned*);
#endif

namespace {
unsigned texture_token;
const Re4dcUiImage image{&texture_token,nullptr,512,512,6,0xffffffffU,0};
constexpr unsigned crc=0xec255e66U, fnv=0x76812316U;
cParts* parts[119];
cModelInfo* infos[8];
const ModelData* qualified[8];
cModel* owner;
unsigned owner_serial;
cParts* owner_parts;
Mtx local_skin[119];
alignas(32) float palette[256][12]; // one synchronous opaque info at a time
re4dc::render::SourceLighting light; // constant texture colour for this proof
unsigned attempts, drawn, fallback, rejected, missing_texture;
#if RE4DC_COARSE_SKIN_FTRV
// FTRV palettes: entries built once from the generated weights; T only for the bones they use.
constexpr unsigned kSkinStream = 24576;
alignas(32) unsigned char skin_stream[kSkinStream];
alignas(32) float bone_T[119][12];
CoarseBoneJob skin_jobs[119];
unsigned char skin_bone[119];
unsigned skin_first[8], skin_groups[8], skin_used, skin_state;  // first: byte offset; state: 0 not built, 1 ready, 2 does not fit
#if RE4DC_COARSE_SKIN_FTRV == 2
CoarseSkinCheck skin_chk;
#endif
bool skin_init() {
    if (skin_state) return skin_state == 1;
    unsigned n = 0, bytes = 0; unsigned char used[119] = {};
    for (unsigned i = 0; i < 8; ++i) {
        const auto& c = leon4k::chunks[i];
        for (unsigned j = 0; j < c.palette_count; ++j)
            for (unsigned k = 0; k < c.weights[j].count; ++k)
                if (c.weights[j].bone[k] >= 119) { skin_state = 2; return false; }
        skin_first[i] = bytes;
        const unsigned b = coarse_group_build(c.weights, c.palette_count, skin_stream + bytes, kSkinStream - bytes, &skin_groups[i], used);
        if (!b) { skin_state = 2; re4dc_log("COARSE_LEON skin palette does not fit\n"); return false; }
        bytes += b; n += c.palette_count;
    }
    skin_used = 0;
    for (unsigned b = 0; b < 119; ++b) if (used[b]) skin_bone[skin_used++] = (unsigned char)b;
    re4dc_log("COARSE_LEON skin ftrv=%d entries=%u bones=%u stream=%u\n", RE4DC_COARSE_SKIN_FTRV, n, skin_used, bytes);
    skin_state = 1;
    return true;
}
#endif

unsigned fingerprint(const void* data) {
    const auto* p=(const unsigned char*)data;unsigned h=2166136261U;
    for(unsigned i=0;i<64;++i)h=(h^p[i])*16777619U;
    return h;
}
bool bind_source(cModel* m) {
    if(!m || m->id!=0 || m->nParts!=119 || !m->pList || (m->be_flag&0x4000))return false;
    if(owner!=m || owner_serial!=m->serial || owner_parts!=m->pList) {
        owner=nullptr;std::memset(qualified,0,sizeof(qualified));
        cParts* p=m->pList;
        for(unsigned i=0;i<119;++i){
            if(!p)return false;parts[i]=p;
            for(unsigned j=0;j<12;++j)
                if(__builtin_fabsf((&p->lt_inv_mat[0][0])[j]-leon4k::bind[i][j])>.01f)return false;
            p=p->pList;
        }
        if(p)return false;
        owner=m;owner_serial=m->serial;owner_parts=m->pList;
    }
    std::memset(infos,0,sizeof(infos));
    unsigned count=0;
    for(cModelInfo* info=m->pModelInfo;info && count<32;info=info->pList,++count){
        const ModelData* d=info->pData;if(!d || !d->vtxOrig)continue;
        const unsigned n=d->weight_ext_num>255?d->weight_ext_num:d->weight_palette_num;
        for(unsigned i=0;i<8;++i){
            const auto& s=leon4k::signatures[i];
            if(d->nVtx!=s.positions || d->nNrm!=s.normals || n!=s.palette)continue;
            if(qualified[i]!=d){if(fingerprint(d->vtxOrig)!=s.vertex_hash)continue;qualified[i]=d;}
            if(infos[i])return false;
            infos[i]=info;
        }
    }
    for(unsigned i=0;i<8;++i)if(!infos[i])return false;
    return true;
}
bool visible(const cModelInfo* info) {
    // ModelTrans queues ot_type 7 twice; commonModelTrans selects bit 0x40
    // in its second pass (and sets model bit 0x08000000 after the first).
    // Coarse submits Leon once, so include both source pass groups here.
    // Bit 8 and invisible_factor remain the actual presentation visibility.
    return (info->be_flag&8) && info->invisible_factor>0;
}
}

// These hooks are called before model_bridge casts a cModelInfo pointer.
extern "C" int re4dc_coarse_actor_source(const void* info,Re4dcActorSource* out) {
#if RE4DC_COARSE_GANADO
    if(re4dc_coarse_ganado_source(info,out))return 1;
#endif
    for(const auto& c:leon4k::chunks)if(info==&c){
        *out={c.positions,c.normals,c.position_count,c.normal_count,c.palette_count,0};return 1;
    }
    return 0;
}
extern "C" int re4dc_coarse_actor_texture_key(const Re4dcUiImage* i,unsigned* c,unsigned* f) {
#if RE4DC_COARSE_GANADO
    if(re4dc_coarse_ganado_texture_key(i,c,f))return 1;
#endif
    if(i->pixels!=image.pixels || i->width!=512 || i->height!=512 || i->format!=6 || i->palette_bytes)return 0;
    *c=crc;*f=fnv;return 1;
}

// Called with coarse store queues closed. Opaque submissions complete here;
// none borrow the shared palette after the next info overwrites it.
extern "C" int re4dc_coarse_leon(cModel* m) {
    ++attempts;
    if(!bind_source(m)){
        if(++fallback<=3)re4dc_log("COARSE_LEON unsupported id=%u parts=%u\n",m?m->id:255,m?m->nParts:0);
        return 0;
    }
    if(m->invisible_factor*m->invisible_factor2<=0)return 1;
    if(m->invisible_factor*m->invisible_factor2<.999f)return 0;
    for(unsigned i=0;i<8;++i)if(visible(infos[i])) {
        if(infos[i]->blend_mode || infos[i]->invisible_factor<.999f)return 0;
        // The approved face is a bone-driven expression simplification (info 3).
        // Other morphing geometry and animated materials remain unsupported.
        if(((infos[i]->be_flag&2) && i!=3) || infos[i]->flagsDC)return 0;
    }
    if(!re4dc_coarse_leon_texture_ready(&image,crc,fnv)){
        if(++missing_texture<=3)re4dc_log("COARSE_LEON texture unavailable\n");return 0;
    }
    re4dc_bind_actor_frame();
    Mtx inv,relative,mv,pm;
    if(!PSMTXInverse(m->pParts->mat,inv))return 0;
#if RE4DC_COARSE_SKIN_FTRV
    if(!skin_init())return 0;
    {
        alignas(32) float invx[16];coarse_inv_xmtrx(inv,invx);
        for(unsigned u=0;u<skin_used;++u){
            const unsigned b=skin_bone[u];
            skin_jobs[u]={&parts[b]->mat[0][0],&parts[b]->lt_inv_mat[0][0],bone_T[b]};
        }
        re4dc_coarse_skin_bones(invx,skin_jobs,skin_used);
    }
#endif
#if RE4DC_COARSE_SKIN_FTRV != 1
    for(unsigned i=0;i<119;++i){
        PSMTXConcat(inv,parts[i]->mat,relative);
        PSMTXConcat(relative,parts[i]->lt_inv_mat,local_skin[i]);
    }
#endif
    unsigned triangles=0,mask=0;
    for(unsigned i=0;i<8;++i){
        auto& c=leon4k::chunks[i];cModelInfo* src=infos[i];
        if(!visible(src))continue;
        if(c.palette_count>256)return 0;
#if RE4DC_COARSE_SKIN_FTRV
        re4dc_coarse_skin_groups(skin_stream+skin_first[i],skin_groups[i],&bone_T[0][0],&palette[0][0],c.palette_count);
#if RE4DC_COARSE_SKIN_FTRV == 2
        for(unsigned j=0;j<c.palette_count;++j)skin_chk.entry(c.weights[j],local_skin,palette[j]);
#endif
#else
        for(unsigned j=0;j<c.palette_count;++j){
            const auto& w=c.weights[j];
            for(unsigned col=0;col<4;++col)for(unsigned row=0;row<3;++row){
                float value=0;
                for(unsigned k=0;k<w.count;++k)value+=local_skin[w.bone[k]][row][col]*w.value[k];
                palette[j][col*3+row]=value;
            }
        }
#endif
        if(!re4dc_actor_skin_register(pG->Frame_cnt,&c,nullptr,&palette[0][0],c.palette_count)){
            ++rejected;continue;
        }
        PSMTXConcat(m->pParts->mat,src->mat,pm);
        PSMTXConcat(pG->Cam.v_mat,pm,mv);
        Re4dcModelPart p{};
        p.model=m;p.info=&c;p.part=&c;p.position_count=c.position_count;p.normal_count=c.normal_count;
        p.position_stride=6;p.normal_stride=6;p.normal_shift=14;p.shift=4;
        p.stream=c.stream;p.stream_bytes=c.stream_bytes;p.uv=c.uv;
        p.lighting=&light;p.image=image;p.source_key[2]=1;
        p.depth_mode=m->z_mode;p.cull=0;p.alpha_state=255;
        std::memcpy(p.modelview,mv,sizeof(mv));GXGetProjectionv(p.projection);GXGetViewportv(p.viewport);
        if(!re4dc_actor_submit(&p)){++rejected;continue;}
        triangles+=c.triangles;mask|=1U<<i;
    }
    ++drawn;
#if RE4DC_COARSE_SKIN_FTRV == 2
    if(drawn<=3 || drawn%120==0)skin_chk.log("leon",pG->Frame_cnt);
#endif
    if(drawn<=3 || drawn%120==0)re4dc_log("COARSE_LEON t=%u draws=%u tris=%u mask=%02x fallback=%u rejected=%u texture_miss=%u\n",
        pG->Frame_cnt,drawn,triangles,mask,fallback,rejected,missing_texture);
    return 1;
}
