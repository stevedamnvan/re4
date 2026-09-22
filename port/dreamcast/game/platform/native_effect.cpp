// D328: no new I/O/cache or effect selection. Borrowed metadata and packed data
// share the source archive lifetime; callers own one 300-byte decode scratch.
#include "native_effect.h"
#include "re4dc_platform.h"
#include <kos.h>
#include <kos/net.h>
#include <cstring>
#include <cstdint>
namespace {
struct Binding { unsigned char* archive; unsigned bytes; const unsigned char* entries; unsigned count; };
Binding bindings[6]{}; // four module owners, persistent core, current room
Re4dcEffectStats stats{};
unsigned word(const unsigned char* p) { unsigned v;std::memcpy(&v,p,4);return v; }
unsigned half(const unsigned char* p) { unsigned short v;std::memcpy(&v,p,2);return v; }
const unsigned char* entry(const Binding& b,unsigned i) { return b.entries+12*i; }
[[noreturn]] void fail(const char* why) { ++stats.failures;re4dc_missing(why);__builtin_trap(); }
bool eligible(const unsigned char* r) {
    bool copy=false;
    switch(r[1]) { case 0:case 1:case 2:case 3:case 7:case 9:case 11:case 16:case 17:
        case 22:case 26:case 64:case 69:case 70:case 74:case 254:copy=true; }
    return copy && (r[264]==0 || (r[264]==1 && r[265]==0));
}
bool decode(const unsigned char* p,unsigned bytes,void* out) {
    if(bytes<12 || (bytes&3) || word(p+8)>>11)return false;
    unsigned count=0;for(unsigned i=0;i<3;++i)count+=__builtin_popcount(word(p+4*i));
    if(bytes!=12+4*count)return false;
    auto* dst=static_cast<unsigned char*>(out);unsigned at=12;
    for(unsigned i=0;i<75;++i) {
        unsigned value=0;
        if(word(p+4*(i/32))&(1U<<(i%32))) { value=word(p+at);at+=4; }
        std::memcpy(dst+4*i,&value,4);
    }
    return true;
}
// Last sequence whose head is <= offset. Packed heads are sorted by converter.
unsigned sequence(const Binding& b,unsigned off) {
    unsigned lo=0,hi=b.count;
    while(lo<hi) { unsigned mid=lo+(hi-lo)/2;if(word(entry(b,mid))<=off)lo=mid+1;else hi=mid; }
    return lo?lo-1:b.count;
}
}
static int bind_archive(void* archive,unsigned bytes,unsigned owner) {
    auto* a=static_cast<unsigned char*>(archive);if(!a || bytes<16)return 0;
    const unsigned n=word(a),rel=word(a+4);if(n>(bytes-16)/8)return 0;
    const unsigned char* table=nullptr;unsigned table_off=0;
    for(unsigned i=0;i<n;++i)if(!std::memcmp(a+16+4*n+4*i,"ESQ",4)) {
        if(table)return 0;
        table_off=word(a+16+4*i);
        if(table_off>bytes || bytes-table_off<32)return 0;
        table=a+table_off;
    }
    if(!table)return 1;
    const unsigned end=owner>=4?bytes:rel;
    if((owner>=4?rel!=0:(rel>bytes || bytes-rel!=64)) || (table_off&31) || table_off<16+8*n || table_off>=end ||
       end-table_off<32 || std::memcmp(table,"R4ESQTBL",8) || word(table+8)!=1 ||
       word(table+16)!=12 || word(table+24)!=bytes || word(table+28))return 0;
    const unsigned count=word(table+12);
    if(!count || count>4096 || count>(end-table_off-32)/12 ||
       net_crc32le(table+32,12*count)!=word(table+20))return 0;
    unsigned previous_end=16+8*n,records=0;
    alignas(4) unsigned char scratch[300];
    for(unsigned i=0;i<count;++i) {
        const auto* e=table+32+12*i;unsigned off=word(e),span=word(e+4),nr=word(e+8);
        if(off<previous_end || off>table_off || span>table_off-off || span<48 ||
           (off&3) || (span&31) || nr!=half(a+off) || !nr || nr>(span-48)/4)return 0;
        const auto* head=a+off;unsigned expected=48+4*nr;
        for(unsigned j=0;j<nr;++j) {
            unsigned v=word(head+48+4*j),start=v&~1U;
            if(start!=expected || start>span || (start&3))return 0;
            unsigned end=j+1<nr?(word(head+48+4*(j+1))&~1U):span;
            if(end<=start || end>span)return 0;
            unsigned len=300;
            if(v&1) {
                if(end-start<12 || word(head+start+8)>>11)return 0;
                len=12;for(unsigned k=0;k<3;++k)len+=4*__builtin_popcount(word(head+start+4*k));
                if(len>=300 || len>end-start || !decode(head+start,len,scratch) || !eligible(scratch))return 0;
            }
            if(len>end-start || (j+1<nr && len!=end-start))return 0;
            expected=start+len;
        }
        for(unsigned p=expected;p<span;++p)if(head[p])return 0;
        if(span-expected>=32)return 0;
        previous_end=off+span;records+=nr;
    }
    Binding* free=nullptr;
    for(auto& b:bindings)if(b.archive==a)return 0;
    for(unsigned i=owner;i<(owner>=4?owner+1:4);++i)if(!bindings[i].archive && !free)free=&bindings[i];
    if(!free)return 0;
    *free={a,bytes,table+32,count};stats.sequences+=count;stats.records+=records;
    re4dc_log("effect bind: archive=%u sequences=%u records=%u metadata=borrowed scratch=300 no-io\n",bytes,count,records);
    return 1;
}
extern "C" int re4dc_effect_bind(void* a,unsigned n) { return bind_archive(a,n,0); }
extern "C" int re4dc_effect_bind_core(void* a,unsigned n) { return bind_archive(a,n,4); }
extern "C" int re4dc_effect_bind_room(void* a,unsigned n) { return bind_archive(a,n,5); }
extern "C" void re4dc_effect_unbind(void* archive) {
    // Retain the original source archive lifetime and teardown suspension.
    // The REL epilog runs first; no decoded allocation or global scratch.
    for(auto& b:bindings)if(b.archive==archive && archive) {
        stats.sequences-=b.count;for(unsigned i=0;i<b.count;++i)stats.records-=word(entry(b,i)+8);
        b={};return;
    }
}
extern "C" void re4dc_effect_retire_room() {
    // The source has suspended room updates before replacing the room heap.
    re4dc_effect_unbind(bindings[5].archive);
}
extern "C" void* re4dc_effect_record_ref(void* head,unsigned index) {
    auto* h=static_cast<unsigned char*>(head);if(!h || index>=half(h))fail("effect record index");
    const auto ptr=reinterpret_cast<std::uintptr_t>(head);
    for(const auto& b:bindings) {
        const auto base=reinterpret_cast<std::uintptr_t>(b.archive);
        if(!b.archive || ptr<base || ptr-base>=b.bytes)continue;
        unsigned s=sequence(b,ptr-base);
        if(s<b.count && word(entry(b,s))==ptr-base) {
            unsigned ref=word(h+48+4*index);
            return reinterpret_cast<void*>((ptr+(ref&~1U))|(ref&1));
        }
    }
    return h+48+300*index;
}
extern "C" void* re4dc_effect_record_read(void* reference,void* scratch) {
    auto ptr=reinterpret_cast<std::uintptr_t>(reference);
    if(!(ptr&1)) { ++stats.raw_reads;return reference; }
    auto started=timer_us_gettime64();ptr&=~std::uintptr_t(1);
    for(const auto& b:bindings) {
        const auto base=reinterpret_cast<std::uintptr_t>(b.archive);
        if(!b.archive || ptr<base || ptr-base>=b.bytes)continue;
        unsigned s=sequence(b,ptr-base);if(s==b.count)break;
        const auto* e=entry(b,s);const auto* h=b.archive+word(e);unsigned off=ptr-(base+word(e));
        unsigned lo=0,hi=word(e+8);
        while(lo<hi) { unsigned m=lo+(hi-lo)/2;if((word(h+48+4*m)&~1U)<off)lo=m+1;else hi=m; }
        if(lo==word(e+8) || word(h+48+4*lo)!=(off|1))break;
        unsigned len=12;for(unsigned k=0;k<3;++k)len+=4*__builtin_popcount(word(h+off+4*k));
        if(!scratch || !decode(h+off,len,scratch))break;
        ++stats.reads;const auto elapsed=timer_us_gettime64()-started;
        if(elapsed>stats.worst_decode_us)stats.worst_decode_us=elapsed;
        return scratch;
    }
    fail("effect record outside live qualified archive");
}
extern "C" void re4dc_effect_get_stats(Re4dcEffectStats* out) { *out=stats; }
