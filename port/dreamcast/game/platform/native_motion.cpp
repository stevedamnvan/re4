// Narrow source-motion key residency adapter. Original FCV/SEQ evaluation stays
// in motion.cpp; original archive and whole-clip paths remain selectable.
#include "native_motion.h"
#include "re4dc_platform.h"
#include "../../room/room_storage.hpp"
#ifndef RE4DC_IO_PROBE
#define RE4DC_IO_PROBE 0
#endif
#if RE4DC_IO_PROBE
// Total time spent in motion-key misses (read + check + relocate); room-entry telemetry.
extern "C" { unsigned long long re4dc_motion_wait_total_us; }
#endif
#include <kos.h>
#include <kos/net.h>
#include <kos/mutex.h>
#include <cstdio>
#include <cstring>
#include <cstdint>

namespace {
constexpr unsigned kArchives=4, kEntries=255, kClipLimit=32768;
struct Slot { unsigned char* data; unsigned pins; std::uint64_t used; };
struct Binding {
    unsigned char* archive; unsigned bytes;
    const unsigned char* records; unsigned count;
    Slot* slots; unsigned budget, hot_bytes, resident;
};
struct Owner { const void* thread; unsigned leases; };
Binding bindings[kArchives]{};
Owner owners[32]{};
Re4dcMotionStats stats{};
std::uint64_t stamp;
mutex_t lock=MUTEX_INITIALIZER;
unsigned word(const unsigned char* p) { unsigned n;std::memcpy(&n,p,4);return n; }
unsigned aligned(unsigned n) { return (n+31)&~31U; }
#ifndef RE4DC_MOTION_FAST_READ
#define RE4DC_MOTION_FAST_READ 0
#endif
#if RE4DC_MOTION_FAST_READ
// MOTION_FAST_READ=1: read a key (<= 32 KiB) straight into its 32-byte-aligned residency
// block. KOS fs_iso9660 reads a misaligned destination (storage::read_file's bounce copy
// path) one sector per GD command: ~98 ms per key in Flycast, 75 keys per r100 entry. An
// aligned destination at offset 0 takes one stream command for the 32-byte multiple; the
// <32-byte tail is then read through the block cache after a seek moves the fd off the
// stream (KOS's own sub-32-byte stream request is the one that never returns, R4_5A).
// Returns bytes read, -1 on open/size failure, -2 when dst is not 32-byte aligned.
int fast_key_read(const char* path, unsigned char* dst, unsigned size) {
    if(reinterpret_cast<std::uintptr_t>(dst)&31U)return -2;
    const file_t f=fs_open(path,O_RDONLY);
    if(f==FILEHND_INVALID)return -1;
    if(fs_total(f)!=ssize_t(size)) { fs_close(f);return -1; }
    const unsigned body=size&~31U;unsigned got=0;
    while(got<body) { const ssize_t n=fs_read(f,dst+got,body-got);if(n<=0)break;got+=unsigned(n); }
    if(got==body && got<size) {
        if(got) { fs_seek(f,0,SEEK_SET);fs_seek(f,got,SEEK_SET); }   // pointer moves: stream aborted
        alignas(32) unsigned char tail[64];                         // tail+16: misaligned on purpose
        const unsigned start=got;
        while(got<size) { const ssize_t n=fs_read(f,tail+16+(got-start),size-got);if(n<=0)break;got+=unsigned(n); }
        std::memcpy(dst+start,tail+16,got-start);
    }
    fs_close(f);
    return int(got);
}
#endif
unsigned prefix(const unsigned char* p) { unsigned n=p[2];return ((3+3*n+3)&~3U)+4+4*n; }
[[noreturn]] void fail(const char* reason) {
    ++stats.failures;re4dc_log("motion residency failure: %s\n",reason);
    re4dc_missing(reason); __builtin_trap();
}
// Called with IRQ exclusion for ownership, independent of the I/O mutex. The
// native OS cancellation hook drains these scopes before destroying a thread.
void owner_add() {
    int old=irq_disable();const void* me=thd_current;
    for(auto& o:owners) if(o.thread==me) { ++o.leases;irq_restore(old);return; }
    for(auto& o:owners) if(!o.leases) { o={me,1};irq_restore(old);return; }
    irq_restore(old);fail("motion owner capacity");
}
void owner_drop() {
    int old=irq_disable();
    for(auto& o:owners) if(o.thread==thd_current && o.leases) {
        if(!--o.leases)o.thread=nullptr;
        irq_restore(old);return;
    }
    irq_restore(old);fail("motion lease owner mismatch");
}
struct Locked {
    Locked() { owner_add();mutex_lock(&lock); }
    ~Locked() { mutex_unlock(&lock);owner_drop(); }
};
const unsigned char* record(const Binding& b,unsigned i) { return b.records+20*i; }
void discard(Binding& b,unsigned i) {
    auto& s=b.slots[i];if(!s.data)return;
    if(s.pins)fail("motion discard pinned");
    const unsigned bytes=aligned(word(record(b,i)+4));
    re4dc_motion_free(s.data);s={};b.resident-=bytes;stats.resident_bytes-=bytes;
}
void release_binding(Binding& b) {
    for(unsigned i=0;i<b.count;++i) if(b.slots[i].pins)fail("motion archive retired while pinned");
    for(unsigned i=0;i<b.count;++i)discard(b,i);
    stats.metadata_bytes-=aligned(b.count*sizeof(Slot));stats.hot_bytes-=b.hot_bytes;
    re4dc_motion_free(b.slots);b={};
}
unsigned* load(Binding& b,unsigned i) {
    const auto* e=record(b,i);auto& s=b.slots[i];
    if(s.data) { ++stats.hits;s.used=++stamp; }
    else {
        ++stats.misses;const auto started=timer_us_gettime64();
        const unsigned size=word(e+4),bytes=aligned(size);
        while(b.resident+bytes>b.budget) {
            unsigned victim=b.count;std::uint64_t oldest=~std::uint64_t(0);
            for(unsigned j=0;j<b.count;++j) {
                const auto& q=b.slots[j];
                if(q.data && !q.pins && !word(record(b,j)+16) && q.used<oldest) { oldest=q.used;victim=j; }
            }
            if(victim==b.count)fail("motion working set exceeds qualified budget");
            discard(b,victim);++stats.evictions;
        }
        if(re4dc_motion_current_heap()!=4)fail("motion miss outside owning room heap");
        auto* data=static_cast<unsigned char*>(re4dc_motion_alloc(bytes));
        if(!data)fail("motion key allocation");
        re4dc::storage::Arena arena;arena.init(data,bytes);
        char path[64];snprintf(path,sizeof(path),"/cd/dc/mot/%08x-%08x.fcv",word(e+8),word(e+12));
#if RE4DC_MOTION_FAST_READ
        const int fast=fast_key_read(path,data,size);
        if(fast>=0) {
            if(unsigned(fast)!=size) { re4dc_motion_free(data);fail("motion key read"); }
            stats.bytes_read+=size;
        } else {
#endif
        auto result=re4dc::storage::read_file(arena,path);
        while(result.error && !std::strcmp(result.error,"storage reader re-entry") &&
              timer_us_gettime64()-started<5000000) {
            thd_pass();result=re4dc::storage::read_file(arena,path);
        }
        if(result.error || result.size!=size) { re4dc_motion_free(data);fail("motion key read"); }
        stats.bytes_read+=result.size;
#if RE4DC_MOTION_FAST_READ
        }
#endif
        unsigned fnv=2166136261U;for(unsigned j=0;j<size;++j)fnv=(fnv^data[j])*16777619U;
        const auto* proxy=b.archive+word(e);const unsigned head=prefix(proxy);
        if(net_crc32le(data,size)!=word(e+8) || fnv!=word(e+12) || std::memcmp(proxy,data,head)) {
            re4dc_motion_free(data);fail("motion identity/header mismatch");
        }
        auto* table=reinterpret_cast<unsigned*>(data+head-4*data[2]);
        for(unsigned j=0;j<data[2];++j) {
            const unsigned offset=table[j];
            if(offset<head || offset>=size) { re4dc_motion_free(data);fail("motion key offset"); }
            table[j]=static_cast<unsigned>(reinterpret_cast<std::uintptr_t>(data)+offset);
        }
        s.data=data;s.used=++stamp;b.resident+=bytes;stats.resident_bytes+=bytes;
        if(stats.resident_bytes>stats.peak_cache_bytes)stats.peak_cache_bytes=stats.resident_bytes;
        ++stats.loads;const auto wait=timer_us_gettime64()-started;
#if RE4DC_IO_PROBE
        re4dc_motion_wait_total_us+=wait;
#endif
        if(wait>stats.worst_wait_us)stats.worst_wait_us=wait;
    }
    return reinterpret_cast<unsigned*>(s.data+prefix(s.data)-4*s.data[2]);
}
}
extern "C" int re4dc_motion_thread_busy(const void* owner) {
    int old=irq_disable();unsigned busy=0;
    for(const auto& o:owners) if(o.thread==owner)busy=o.leases;
    irq_restore(old);return busy!=0;
}
extern "C" void re4dc_motion_get_stats(Re4dcMotionStats* out) { Locked guard;*out=stats; }
extern "C" int re4dc_motion_bind(void* archive,unsigned bytes) {
    Locked guard;auto* a=static_cast<unsigned char*>(archive);
    if(!a || bytes<16)return 0;
    const unsigned n=word(a),rel=word(a+4);if(n>(bytes-16)/8)return 0;
    const unsigned char* mtc=nullptr;unsigned mtc_offset=0;
    for(unsigned i=0;i<n;++i)if(!std::memcmp(a+16+4*n+4*i,"MTC",4)) {
        if(mtc || i!=n-1)return 0;
        mtc_offset=word(a+16+4*i);
        if(mtc_offset>bytes || bytes-mtc_offset<32)return 0;
        mtc=a+mtc_offset;
    }
    if(!mtc)return 1; // ordinary source archive, no cache allocated
    // D325 qualifies room-owned em12, before heap4 reset. Frozen stage heaps
    // and the ARAM/shooting-range swap require a distinct ownership audit.
    if(re4dc_motion_current_heap()!=4)return 0;
    if(rel>bytes || bytes-rel!=64 || mtc_offset<16+8*n ||
       mtc_offset>=rel || rel-mtc_offset<32 || (mtc_offset&31) ||
       std::memcmp(mtc,"R4MOTBL\0",8) || word(mtc+8)!=2 || word(mtc+16)!=20 ||
       word(mtc+24)!=bytes || word(mtc+28)!=kClipLimit)return 0;
    const unsigned count=word(mtc+12);
    if(!count || count>kEntries || count>(rel-mtc_offset-32)/20 ||
       net_crc32le(mtc+32,count*20)!=word(mtc+20))return 0;
    unsigned hot=0,largest=0,prev=0;
    for(unsigned i=0;i<count;++i) {
        const auto* e=mtc+32+20*i;const unsigned off=word(e),size=word(e+4),flags=word(e+16);
        if(off<16+8*n || off>=mtc_offset || (off&31) || off<=prev ||
           size>kClipLimit || size<32 || (size&31) || flags>1 || !a[off+2])return 0;
        unsigned head=prefix(a+off);if(head>size || head>mtc_offset-off)return 0;
        bool found=false;unsigned end=mtc_offset;
        for(unsigned j=0;j<n;++j) {
            unsigned p=word(a+16+4*j);if(p>off && p<end)end=p;
            if(p==off) { if(std::memcmp(a+16+4*n+4*j,"FCV",4))return 0;found=true; }
        }
        if(!found || aligned(head)!=end-off || head>=size)return 0;
        if(flags)hot+=size;else if(size>largest)largest=size;
        const auto* table=a+off+head-4*a[off+2];
        for(unsigned j=0;j<a[off+2];++j)if(word(table+4*j)<head || word(table+4*j)>=size)return 0;
        prev=off;
    }
    Binding* b=nullptr;
    for(auto& q:bindings) { if(q.archive==a)return 0;if(!q.archive && !b)b=&q; }
    if(!b)return 0;
    const unsigned meta=aligned(count*sizeof(Slot));auto* slots=static_cast<Slot*>(re4dc_motion_alloc(meta));
    if(!slots)return 0;
    std::memset(slots,0,meta);
    // Selected recurring/response set plus two largest cold clips. D325 is
    // diagnostic until the source prefetch/concurrency closure is complete.
    // Hot entries are never LRU victims; a budget miss is explicit, not thrash.
    *b={a,bytes,mtc+32,count,slots,hot+2*largest,hot,0};
    stats.metadata_bytes+=meta;stats.hot_bytes+=hot;
    for(unsigned i=0;i<count;++i)if(word(record(*b,i)+16))load(*b,i);
    re4dc_log("motion bind: archive=%u entries=%u hot=%u cache-budget=%u metadata=%u\n",bytes,count,hot,b->budget,meta);
    return 1;
}
extern "C" int re4dc_motion_acquire(const void* header,unsigned** table) {
    if(!header)return 0;
    const auto started=timer_us_gettime64();
    Locked guard;
    if(!stats.metadata_bytes)return 0;
    const auto p=reinterpret_cast<std::uintptr_t>(header);
    for(unsigned bno=0;bno<kArchives;++bno) {
        auto& b=bindings[bno];auto base=reinterpret_cast<std::uintptr_t>(b.archive);
        if(!base || p<base || p-base>=b.bytes)continue;
        for(unsigned i=0;i<b.count;++i)if(word(record(b,i))==p-base) {
            *table=load(b,i);auto& s=b.slots[i];
            if(!s.pins++) { stats.pinned_bytes+=word(record(b,i)+4);if(stats.pinned_bytes>stats.peak_pinned_bytes)stats.peak_pinned_bytes=stats.pinned_bytes; }
            owner_add();
            const auto wait=timer_us_gettime64()-started;
            if(wait>stats.worst_wait_us)stats.worst_wait_us=wait;
            return bno*256+i+1;
        }
    }
    return 0;
}
extern "C" void re4dc_motion_release(int token) {
    Locked guard;if(token<=0 || token>int(kArchives*256))fail("motion lease token");
    unsigned t=token-1;auto& b=bindings[t/256];unsigned i=t%256;
    if(!b.archive || i>=b.count || !b.slots[i].pins)fail("motion unbalanced release");
    if(!--b.slots[i].pins)stats.pinned_bytes-=word(record(b,i)+4);
    owner_drop(); // retain loaded bytes and relocated table until actual eviction
}
extern "C" void re4dc_motion_unbind(void* archive) {
    Locked guard;for(auto& b:bindings)if(b.archive==archive && archive)release_binding(b);
}
extern "C" void re4dc_motion_retire_all() {
    Locked guard;for(auto& b:bindings)if(b.archive)release_binding(b);
}
