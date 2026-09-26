// COARSE_GANADO_CAST=1 (with COARSE_GANADO=1; render only): the Ganados draw the external cast's
// per-appearance meshes instead of the one retargeted 874-triangle mesh of coarse_ganado.cpp, which this
// file replaces in the link. Input: ganado_cast_runtime.h from a private bundle in COARSE_ACTOR_ASSET_DIR
// (generated outside the repository from the cast packs): per appearance four chunks in the source info
// order (body, head, right hand, left hand), the appearance's inverse bind, the source infos' signatures
// and the atlas key. An actor draws the appearance whose body and head signatures its source infos carry;
// a hand info with any cast hand-pose signature draws that appearance's default hand for its side (hand
// poses are not integrated yet). The game owns the pose, part visibility and simulation; nothing here
// reaches game logic. =2 (check build): the 874 adapter's matcher runs beside every attempt and "GCAST"
// lines count both / cast only / 874 only / neither, per-role disagreements, the appearances drawn and
// skeletons whose rest translations differ from the appearance's bind.
#include "global.h"
#include "model.h"
#include "native_actor.hpp"
#include "ganado_cast_runtime.h" // private generated bundle, outside the repository
#include <cstring>
#include <kos/fs.h>
#if RE4DC_COARSE_GANADO_CAST == 2
#include <cstdio>
#include "ganado874_runtime.h"
#include "ganado874_variants.h"
#endif
#if RE4DC_COARSE_SKIN_FTRV
#include "coarse_skin.h"
#endif

extern "C" void re4dc_log(const char*, ...);
extern "C" void GXGetProjectionv(float*);
extern "C" void GXGetViewportv(float*);
extern "C" void re4dc_bind_actor_frame();
extern "C" int re4dc_coarse_leon_texture_ready(const Re4dcUiImage*,unsigned,unsigned);

namespace {
namespace gc = ganadocast;
constexpr unsigned kApps = gc::appearance_count, kBones = gc::bone_count;
static_assert(kBones == 34, "the coarse Ganado skeleton");
unsigned texture_token[gc::texture_count];
Re4dcUiImage image_of(unsigned t){return Re4dcUiImage{&texture_token[t],nullptr,gc::textures[t].width,gc::textures[t].height,6,0xffffffffU,0};}
struct Binding { cModel* owner; unsigned serial; cParts* list; cParts* parts[kBones]; unsigned appearance;
                 cModelInfo* infos[4]; const ModelData* qualified[4]; unsigned short signature[4]; };
Binding bindings[32];
Binding* bound;
unsigned replacement;
int mesh_limit=RE4DC_COARSE_GANADO_LIMIT;
bool config_read;
int stress_layout;
unsigned frame_meshes, frame_emitted, frame_candidates, frame_fallback, frame_triangles;
Mtx local_skin[kBones];
alignas(32) float palette[256][12]; // one synchronous opaque info at a time
re4dc::render::SourceLighting light; // constant texture colour for this proof
unsigned attempts, drawn, fallback, rejected, missing_texture;
#if RE4DC_COARSE_SKIN_FTRV
// FTRV palettes: each appearance's entries built once (on its first draw) from the generated weights.
alignas(32) unsigned char skin_stream[(gc::skin_stream_bytes + 31) & ~31U];
alignas(32) float bone_T[kBones][12];
CoarseBoneJob skin_jobs[kBones];
unsigned char skin_bone[kApps][kBones];
unsigned skin_first[kApps][4], skin_groups[kApps][4], skin_used[kApps], skin_state[kApps], skin_next;
#if RE4DC_COARSE_SKIN_FTRV == 2
CoarseSkinCheck skin_chk;
#endif
bool skin_init(unsigned a) {
    if (skin_state[a]) return skin_state[a] == 1;
    unsigned n = 0, bytes = skin_next; unsigned char used[kBones] = {};
    for (unsigned i = 0; i < 4; ++i) {
        const auto& c = gc::chunks[a][i];
        for (unsigned j = 0; j < c.palette_count; ++j)
            for (unsigned k = 0; k < c.weights[j].count; ++k)
                if (c.weights[j].bone[k] >= kBones) { skin_state[a] = 2; return false; }
        skin_first[a][i] = bytes;
        const unsigned b = coarse_group_build(c.weights, c.palette_count, skin_stream + bytes, sizeof(skin_stream) - bytes, &skin_groups[a][i], used);
        if (!b) { skin_state[a] = 2; re4dc_log("COARSE_GANADO_CAST %s skin palette does not fit\n", gc::appearance_names[a]); return false; }
        bytes += b; n += c.palette_count;
    }
    skin_next = bytes;
    skin_used[a] = 0;
    for (unsigned b = 0; b < kBones; ++b) if (used[b]) skin_bone[a][skin_used[a]++] = (unsigned char)b;
    re4dc_log("COARSE_GANADO_CAST skin ftrv=%d %s entries=%u bones=%u stream=%u/%u\n", RE4DC_COARSE_SKIN_FTRV,
              gc::appearance_names[a], n, skin_used[a], skin_next, (unsigned)sizeof(skin_stream));
    skin_state[a] = 1;
    return true;
}
#endif

unsigned fingerprint(const void* data) {
    const auto* p=(const unsigned char*)data;unsigned h=2166136261U;
    for(unsigned i=0;i<64;++i)h=(h^p[i])*16777619U;
    return h;
}
// The source infos' roles and the appearance from the signature table. A ModelData that passed a
// signature's hash stays qualified for that signature (the fingerprint runs once per new ModelData).
bool match_infos(cModel* m, Binding& b, unsigned& app) {
    auto& infos=b.infos;
    std::memset(infos,0,sizeof(infos));
    app=~0U;
    unsigned count=0;
    constexpr unsigned kSigs=sizeof(gc::signatures)/sizeof(gc::signatures[0]);
    for(cModelInfo* info=m->pModelInfo;info && count<32;info=info->pList,++count){
        const ModelData* d=info->pData;if(!d || !d->vtxOrig)continue;
        const unsigned n=d->weight_ext_num>255?d->weight_ext_num:d->weight_palette_num;
        unsigned k=kSigs;
        for(unsigned r=0;r<4;++r)if(b.qualified[r]==d){k=b.signature[r];break;}
        if(k==kSigs){
            unsigned h=0;bool hashed=false;
            for(unsigned s=0;s<kSigs;++s){
                const auto& g=gc::signatures[s];
                if(d->nVtx!=g.positions || d->nNrm!=g.normals || n!=g.palette)continue;
                if(!hashed){h=fingerprint(d->vtxOrig);hashed=true;}
                if(h==g.vertex_hash){k=s;break;}
            }
            if(k==kSigs)continue;
            b.qualified[gc::signatures[k].role]=d;b.signature[gc::signatures[k].role]=(unsigned short)k;
        }
        const auto& g=gc::signatures[k];
        if(infos[g.role])return false;
        if(g.appearance!=0xFF){if(app!=~0U && app!=g.appearance)return false;app=g.appearance;}
        infos[g.role]=info;
    }
    for(unsigned i=0;i<4;++i)if(!infos[i])return false;
    return app<kApps;
}
bool bind_source(cModel* m) {
    if(!m || (m->id<0x10 || m->id>0x20) || m->nParts!=kBones || !m->pList || (m->be_flag&0x4000))return false;
    bound=nullptr;
    for(auto& entry:bindings)if(entry.owner==m && entry.serial==m->serial && entry.list==m->pList){bound=&entry;break;}
    if(!bound){
        Binding& entry=bindings[replacement++%32];
        std::memset(&entry,0,sizeof(entry));
        cParts* p=m->pList;
        for(unsigned i=0;i<kBones;++i){if(!p)return false;entry.parts[i]=p;p=p->pList;}
        if(p)return false;
        for(unsigned i=0;i<kBones;++i){
            const int parent=gc::parents[i];
            const cCoord* want=parent<0?(const cCoord*)m:(const cCoord*)entry.parts[parent];
            if(entry.parts[i]->pParent!=want)return false;
        }
        entry.owner=m;entry.serial=m->serial;entry.list=m->pList;entry.appearance=~0U;bound=&entry;
    }
    unsigned app;
    if(!match_infos(m,*bound,app))return false;
    if(bound->appearance!=app){
        // The appearance's mesh is retargeted with its own inverse bind (as the 874 mesh is): the bone
        // axes must agree; rest translations may differ (=2 counts those skeletons).
        for(unsigned i=0;i<kBones;++i)for(unsigned row=0;row<3;++row)for(unsigned col=0;col<3;++col)
            if(__builtin_fabsf(bound->parts[i]->lt_inv_mat[row][col]-gc::bind[app][i][row*4+col])>.001f)return false;
        bound->appearance=app;
    }
    return true;
}
bool visible(const cModelInfo* info) {
    // ModelTrans queues ot_type 7 twice; commonModelTrans selects bit 0x40
    // in its second pass (and sets model bit 0x08000000 after the first).
    // Coarse submits each actor once, so include both source pass groups here.
    // Bit 8 and invisible_factor remain the actual presentation visibility.
    return (info->be_flag&8) && info->invisible_factor>0;
}

#if RE4DC_COARSE_GANADO_CAST == 2
// The 874 adapter's acceptance (coarse_ganado.cpp's bind_source without its caches) for the same actor.
unsigned chk_both, chk_cast_only, chk_old_only, chk_neither, chk_role_mismatch, chk_bind_off, chk_app[kApps];
bool old_match(cModel* m, cModelInfo* (&infos)[4]) {
    std::memset(infos,0,sizeof(infos));
    if(!m || (m->id<0x10 || m->id>0x20) || m->nParts!=34 || !m->pList || (m->be_flag&0x4000))return false;
    cParts* parts[34];cParts* p=m->pList;
    for(unsigned i=0;i<34;++i){
        if(!p)return false;parts[i]=p;
        for(unsigned row=0;row<3;++row)for(unsigned col=0;col<3;++col)
            if(__builtin_fabsf(p->lt_inv_mat[row][col]-ganado874::bind[i][row*4+col])>.001f)return false;
        p=p->pList;
    }
    if(p)return false;
    for(unsigned i=0;i<34;++i){
        const int parent=ganado874::parents[i];
        const cCoord* want=parent<0?(const cCoord*)m:(const cCoord*)parts[parent];
        if(parts[i]->pParent!=want)return false;
    }
    unsigned count=0;
    for(cModelInfo* info=m->pModelInfo;info && count<32;info=info->pList,++count){
        const ModelData* d=info->pData;if(!d || !d->vtxOrig)continue;
        const unsigned n=d->weight_ext_num>255?d->weight_ext_num:d->weight_palette_num;
        for(const auto& s:ganado874::variants){
            if(d->nVtx!=s.positions || d->nNrm!=s.normals || n!=s.palette || fingerprint(d->vtxOrig)!=s.vertex_hash)continue;
            if(infos[s.role])return false;
            infos[s.role]=info;break;
        }
    }
    for(unsigned i=0;i<4;++i)if(!infos[i])return false;
    return true;
}
void check_attempt(cModel* m, bool cast_ok) {
    cModelInfo* old[4];
    const bool old_ok=old_match(m,old);
    if(cast_ok && old_ok){
        ++chk_both;
        for(unsigned i=0;i<4;++i)if(old[i]!=bound->infos[i])++chk_role_mismatch;
    }
    else if(cast_ok)++chk_cast_only;
    else if(old_ok)++chk_old_only;
    else ++chk_neither;
    if(cast_ok){
        ++chk_app[bound->appearance];
        for(unsigned i=0;i<kBones;++i)for(unsigned row=0;row<3;++row)
            if(__builtin_fabsf(bound->parts[i]->lt_inv_mat[row][3]-gc::bind[bound->appearance][i][row*4+3])>.01f){++chk_bind_off;return;}
    }
}
#endif
}

// These hooks are called before model_bridge casts a cModelInfo pointer.
extern "C" int re4dc_coarse_ganado_source(const void* info,Re4dcActorSource* out) {
    for(const auto& a:gc::chunks)for(const auto& c:a)if(info==&c){
        *out={c.positions,c.normals,c.position_count,c.normal_count,c.palette_count,0};return 1;
    }
    return 0;
}
extern "C" int re4dc_coarse_ganado_texture_key(const Re4dcUiImage* i,unsigned* c,unsigned* f) {
    for(unsigned t=0;t<gc::texture_count;++t){
        if(i->pixels!=&texture_token[t] || i->width!=gc::textures[t].width || i->height!=gc::textures[t].height || i->format!=6 || i->palette_bytes)continue;
        *c=gc::textures[t].crc;*f=gc::textures[t].fnv;return 1;
    }
    return 0;
}

// Called with coarse store queues closed. Opaque submissions complete here;
// none borrow the shared palette after the next info overwrites it.
extern "C" int re4dc_coarse_ganado(cModel* m) {
    ++frame_candidates;
    if(mesh_limit>=0 && frame_meshes>=unsigned(mesh_limit))return stress_layout?1:0;
    ++attempts;
    const bool ok=bind_source(m);
#if RE4DC_COARSE_GANADO_CAST == 2
    check_attempt(m,ok);
#endif
    if(!ok){
        ++frame_fallback;
        if(++fallback<=12)re4dc_log("COARSE_GANADO_CAST unsupported id=%u parts=%u\n",m?m->id:255,m?m->nParts:0);
        return 0;
    }
    auto& infos=bound->infos;auto& parts=bound->parts;const unsigned app=bound->appearance;
    const Re4dcUiImage image=image_of(gc::appearance_texture[app]);
    const auto& tex=gc::textures[gc::appearance_texture[app]];
    if(m->invisible_factor*m->invisible_factor2<=0)return 1;
    if(m->invisible_factor*m->invisible_factor2<.999f)return 0;
    for(unsigned i=0;i<4;++i)if(visible(infos[i])) {
        if(infos[i]->blend_mode || infos[i]->invisible_factor<.999f)return 0;
        // As coarse_ganado.cpp: bone-driven info 3 only; other morphing geometry and animated
        // materials remain unsupported.
        if(((infos[i]->be_flag&2) && i!=3) || infos[i]->flagsDC)return 0;
    }
    if(!re4dc_coarse_leon_texture_ready(&image,tex.crc,tex.fnv)){
        if(++missing_texture<=3)re4dc_log("COARSE_GANADO_CAST texture unavailable\n");return 0;
    }
    re4dc_bind_actor_frame();
    Mtx inv,relative,mv,pm;
    if(!PSMTXInverse(m->pParts->mat,inv))return 0;
    const float (*bind)[12]=gc::bind[app];
#if RE4DC_COARSE_SKIN_FTRV
    if(!skin_init(app))return 0;
    {
        alignas(32) float invx[16];coarse_inv_xmtrx(inv,invx);
        for(unsigned u=0;u<skin_used[app];++u){
            const unsigned b=skin_bone[app][u];
            skin_jobs[u]={&parts[b]->mat[0][0],bind[b],bone_T[b]};
        }
        re4dc_coarse_skin_bones(invx,skin_jobs,skin_used[app]);
    }
#endif
#if RE4DC_COARSE_SKIN_FTRV != 1
    for(unsigned i=0;i<kBones;++i){
        PSMTXConcat(inv,parts[i]->mat,relative);
        PSMTXConcat(relative,(const float (*)[4])bind[i],local_skin[i]);
    }
#endif
    unsigned triangles=0,mask=0;
    const unsigned emitted_before=re4dc_actor_stats()->triangles;
    for(unsigned i=0;i<4;++i){
        auto& c=gc::chunks[app][i];cModelInfo* src=infos[i];
        if(!visible(src))continue;
        if(c.palette_count>256)return 0;
#if RE4DC_COARSE_SKIN_FTRV
        re4dc_coarse_skin_groups(skin_stream+skin_first[app][i],skin_groups[app][i],&bone_T[0][0],&palette[0][0],c.palette_count);
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
        if(stress_layout){
            // Arrange the existing live poses in camera space for a bounded
            // renderer stress test. Source positions, bones, AI and camera
            // remain untouched. This placement must never ship as gameplay.
            const unsigned slot=frame_meshes%7,row=frame_meshes/7;
            const int order[7]={0,-1,1,-2,2,-3,3};
            mv[0][3]=float(order[slot])*(row?850.f:650.f);
            mv[1][3]=row?-350.f:-1100.f;
            mv[2][3]=row?-6500.f:-4200.f;
        }
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
    ++drawn;++frame_meshes;frame_triangles+=triangles;
    frame_emitted+=re4dc_actor_stats()->triangles>emitted_before;
#if RE4DC_COARSE_SKIN_FTRV == 2
    if(drawn<=3 || drawn%120==0)skin_chk.log("ganado",pG->Frame_cnt);
#endif
    if(drawn<=3 || drawn%120==0)re4dc_log("COARSE_GANADO_CAST t=%u draws=%u app=%s tris=%u mask=%02x fallback=%u rejected=%u texture_miss=%u\n",
        pG->Frame_cnt,drawn,gc::appearance_names[app],triangles,mask,fallback,rejected,missing_texture);
    return 1;
}

extern "C" void re4dc_coarse_ganado_begin(){
    if(!config_read){
        config_read=true;
        const file_t file=fs_open("/cd/dc/coarse-crowd.txt",O_RDONLY);
        if(file>=0){
            char text[16]={};const int size=fs_read(file,text,15);fs_close(file);
            int value=0;unsigned i=0;const bool neg=text[0]=='-';if(neg)i=1;
            const unsigned start=i;
            while(i<unsigned(size>0?size:0) && text[i]>='0' && text[i]<='9'){value=value*10+text[i++]-'0';}
            if(i>start && value<=64){if(neg)value=-value;if(value>=-1)mesh_limit=value;}
            while(i<unsigned(size>0?size:0) && (text[i]==' ' || text[i]=='\t'))++i;
            if(i<unsigned(size>0?size:0) && text[i]=='1')stress_layout=1;
        }
        re4dc_log("COARSE_CROWD config mesh_limit=%d layout=%d source=diagnostic-file ACT_CAP=0\n",mesh_limit,stress_layout);
        re4dc_log("COARSE_GANADO_CAST=%d appearances=%u signatures=%u textures=%u skin_stream=%u\n",RE4DC_COARSE_GANADO_CAST,kApps,
            (unsigned)(sizeof(gc::signatures)/sizeof(gc::signatures[0])),gc::texture_count,gc::skin_stream_bytes);
    }
    frame_meshes=frame_emitted=frame_candidates=frame_fallback=frame_triangles=0;
}
extern "C" void re4dc_coarse_ganado_end(){
#if defined(RE4DC_COARSE_FREEZE_AT) && RE4DC_COARSE_FREEZE_AT
    // Diagnostic (COARSE_FREEZE_AT=N, captures only): stop the CPU inside frame N's actor pass. Frame N-1,
    // already submitted, stays on screen, so every capture after the marker shows exactly that frame.
    if(pG->Frame_cnt>=RE4DC_COARSE_FREEZE_AT){
        re4dc_log("COARSE_FREEZE t=%u: the screen holds frame %u\n",pG->Frame_cnt,pG->Frame_cnt-1);
        for(;;)__asm__ volatile("nop");
    }
#endif
    if(pG->Frame_cnt%120==0)re4dc_log("COARSE_CROWD t=%u limit=%d layout=%d candidates=%u meshes=%u emitted=%u tris=%u unsupported=%u rejected=%u texture_miss=%u\n",
        pG->Frame_cnt,mesh_limit,stress_layout,frame_candidates,frame_meshes,frame_emitted,frame_triangles,frame_fallback,rejected,missing_texture);
#if RE4DC_COARSE_GANADO_CAST == 2
    if(pG->Frame_cnt%120==0){
        char apps[64];unsigned n=0;
        for(unsigned a=0;a<kApps && n+12<sizeof(apps);++a)n+=sprintf(apps+n,"%s%u",a?"/":"",chk_app[a]);
        re4dc_log("GCAST t=%u both=%u cast_only=%u old_only=%u neither=%u role_mismatch=%u bind_translation_off=%u app=%s\n",
            pG->Frame_cnt,chk_both,chk_cast_only,chk_old_only,chk_neither,chk_role_mismatch,chk_bind_off,apps);
    }
#endif
#if defined(RE4DC_DECISION_TRACE) && RE4DC_DECISION_TRACE
    // Trace builds only (never a timing arm): per-frame Ganado submission and Leon's life for the
    // scripted village-fight fixture, so a timing window and visible-versus-submitted counts are
    // chosen from exact frames. Read-only; logic_trace_diff / dtcmp ignore this line.
    re4dc_log("CROWDF t=%u c=%u m=%u e=%u fb=%u tri=%u hp=%d/%d\n",pG->Frame_cnt,frame_candidates,frame_meshes,
        frame_emitted,frame_fallback,frame_triangles,(int)(short)pG->pl_life,(int)pG->pl_life_max);
#endif
}

extern "C" int re4dc_coarse_ganado_layout(){return stress_layout;}
