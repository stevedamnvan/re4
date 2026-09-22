#pragma once
#include "native_model.h"
#include "native_render_profile.hpp"
#include <cstring>
#ifndef RE4DC_NATIVE_REUSE_AUDIT
#define RE4DC_NATIVE_REUSE_AUDIT 0
#endif
// Bounded diagnostic of the existing renderer. No geometry/unique-key table is
// retained on target. The existing RAM log transports source views to the host
// fixture, which verifies its reference-order hashes before counting identities.
namespace re4dc::reuse_audit {
#if RE4DC_NATIVE_REUSE_AUDIT
struct Scope;
inline Scope* current=nullptr;
#if RE4DC_NATIVE_REUSE_AUDIT==2
void host_begin(const Re4dcModelPart*,const void*,const void*,const Re4dcModelPacket*,unsigned);
void host_reference(unsigned,unsigned,unsigned,unsigned);
void host_end(const unsigned*);
#else
#if !RE4DC_NATIVE_RENDER_PROFILE
#error Reuse audit needs the existing TMU2 stage profile
#endif
static_assert(sizeof(Re4dcModelPart)==272 && sizeof(re4dc::render::SourceLighting)==500);
static_assert(sizeof(Re4dcModelWorkStats)==120);
extern "C" unsigned re4dc_fixture_source_frame();
extern "C" void re4dc_log_raw(const char*,unsigned long);
inline void dump(char kind,unsigned frame,unsigned call,const void* ptr,unsigned bytes){
    const auto* words=static_cast<const unsigned char*>(ptr);
    for(unsigned first=0;first<bytes/4;first+=16){
        char line[180];unsigned n=0;
        const auto word=[&](unsigned value){
            static const char digits[]="0123456789abcdef";
            for(int shift=28;shift>=0;shift-=4)line[n++]=digits[(value>>shift)&15];
            line[n++]=' ';
        };
        line[n++]='r';line[n++]='u';line[n++]=' ';line[n++]=kind;line[n++]=' ';
        word(frame);word(call);word(first);
        for(unsigned i=first;i<bytes/4 && i<first+16;++i){unsigned v;std::memcpy(&v,words+4*i,4);word(v);}
        line[n-1]='\n';re4dc_log_raw(line,n);
    }
}
#endif
struct Scope {
    const Re4dcModelPart& part;const Re4dcModelPacket& packet;
    Re4dcModelWorkStats before{};
    std::uint64_t times[3]{};
    unsigned record[20]{};bool active=false;
    Scope(const Re4dcModelPart& p,const void* plan,const void* bounds,const Re4dcModelPacket& pk,unsigned lights):part(p),packet(pk){
#if RE4DC_NATIVE_REUSE_AUDIT==2
        active=true;host_begin(&p,plan,bounds,&pk,lights);
#else
        static unsigned last=0,ordinal=0;
        const unsigned frame=re4dc_fixture_source_frame();
#if RE4DC_NATIVE_REUSE_AUDIT==3
        active=frame>=2382 && frame<=2386;
#else
        active=frame>=2382 && frame<=2451;
#endif
        if(active){
            if(frame!=last){last=frame;ordinal=0;}
            record[0]=frame;record[1]=++ordinal;
            record[2]=unsigned(reinterpret_cast<std::uintptr_t>(plan));
            record[3]=unsigned(reinterpret_cast<std::uintptr_t>(bounds));
            times[0]=profile::state.cycles[profile::TransformProject];
            times[1]=profile::state.cycles[profile::Lighting];
            times[2]=profile::state.cycles[profile::PacketPack];
        }
#endif
        if(active){
            before=*re4dc_model_work_stats();record[9]=2166136261U;record[10]=0x9e3779b9U;
            std::memcpy(record+11,&pk.u_scale,4);std::memcpy(record+12,&pk.v_scale,4);
            record[18]=lights;record[19]=p.lighting?1:0;current=this;
        }
    }
    ~Scope(){
        if(!active)return;
        current=nullptr;
#if RE4DC_NATIVE_REUSE_AUDIT==2
        host_end(record);
#else
        record[15]=unsigned((profile::state.cycles[profile::TransformProject]-times[0])*2/25);
        record[16]=unsigned((profile::state.cycles[profile::Lighting]-times[1])*2/25);
        record[17]=unsigned((profile::state.cycles[profile::PacketPack]-times[2])*2/25);
        std::memcpy(record+13,&packet.u_scale,4);std::memcpy(record+14,&packet.v_scale,4);
        Re4dcModelWorkStats delta=*re4dc_model_work_stats();
        unsigned now[30],old[30];std::memcpy(now,&delta,sizeof(now));std::memcpy(old,&before,sizeof(old));
        for(unsigned i=0;i<30;++i)now[i]-=old[i];
        dump('v',record[0],record[1],&part,sizeof(part));
        if(part.lighting)dump('l',record[0],record[1],part.lighting,sizeof(*part.lighting));
        dump('w',record[0],record[1],now,sizeof(now));
        dump('h',record[0],record[1],record,sizeof(record)); // seals the record
#endif
    }
};
inline void reference(unsigned vi,unsigned ni,unsigned ti,unsigned ci){
    if(!current)return;
    auto& r=current->record;++r[4];if(current->part.lighting)++r[5];
    r[9]=(r[9]^(vi|(ni<<16)))*16777619U;
    r[9]=(r[9]^(ti|(ci<<16)))*16777619U;
    r[10]=(r[10]+vi*31U+ni*131U+ti*257U+ci*65537U)*33U+1U;
#if RE4DC_NATIVE_REUSE_AUDIT==2
    host_reference(vi,ni,ti,ci);
#endif
}
inline void light(){if(current)++current->record[6];}
inline void pack(){if(current)++current->record[7];}
inline void commit(unsigned count){if(current)current->record[8]+=count;}
#else
struct Scope {Scope(const Re4dcModelPart&,const void*,const void*,const Re4dcModelPacket&,unsigned){}};
inline void reference(unsigned,unsigned,unsigned,unsigned){}
inline void light(){}inline void pack(){}inline void commit(unsigned){}
#endif
}
