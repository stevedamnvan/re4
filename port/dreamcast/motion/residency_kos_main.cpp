// Extend the existing real-motion fixture with actual KOS/CD cache I/O.
// Diagnostic only: KOS-owned fixture allocations do not prove source-heap fit.
#include <kos.h>
#include <kos/net.h>
#include <malloc.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "native_motion.h"
#include "native_effect.h"
#include "re4dc_platform.h"
#include "re4_host_stub.h"
#include "real_motion_checks.hpp"
#include "../room/room_storage.hpp"
KOS_INIT_FLAGS(INIT_DEFAULT);
namespace {
unsigned char* archive;
unsigned char* records;
unsigned count, failures, live_bytes, peak_bytes;
void* selected;
unsigned cold[3];
unsigned word(const unsigned char* p) { unsigned v;std::memcpy(&v,p,4);return v; }
void require(bool ok,const char* why) { if(!ok) { ++failures;re4dc_missing(why); } }
void check_keys(const unsigned char* proxy,unsigned* table) {
    unsigned n=proxy[2],head=((3+3*n+3)&~3U)+4+4*n;
    const auto* base=reinterpret_cast<unsigned char*>(table)-head+4*n;
    for(unsigned j=0;j<n;++j)
        require(table[j]==reinterpret_cast<unsigned>(base)+word(proxy+head-4*n+4*j),"fixture relocated key");
}
void evaluate(unsigned i) {
    auto* proxy=archive+word(records+20*i);unsigned* table=nullptr;
    int lease=re4dc_motion_acquire(proxy,&table);
    require(lease!=0,"fixture missing lease");check_keys(proxy,table);re4dc_motion_release(lease);
}
void after_evaluation(void* object) {
    auto* model=static_cast<cEm*>(object);auto* p=static_cast<unsigned char*>(selected);
    unsigned n=p[2],head=((3+3*n+3)&~3U)+4+4*n;
    require(model->Motion.pMot==selected && model->Motion.pJoint_kind==reinterpret_cast<unsigned short*>(p+3) &&
        model->Motion.pJoint_no==p+3+2*n && model->Motion.pHermite_data==reinterpret_cast<u32*>(p+head-4*n),
        "fixture retained source pointer");
    auto saved=model->Motion;Vec position{},rotation{};
    MotionGetSpeed(model,&model->Motion,0,&position,&rotation);
    require(model->Motion.pHermite_data==saved.pHermite_data,"fixture speed retained pointer");
    model->Motion=saved;
    for(auto i:cold)evaluate(i); // deliberate pressure, NOT the warm working-set test
}
// Optional compact effects use this same resource fixture, not a second game.
// Expected FNVs are emitted from the unchanged source sequences, not candidate
// records. Target decode timing is diagnostic and does not include effect draw.
void check_effects(re4dc::storage::Arena& arena,unsigned bytes) {
    unsigned index=0,n=word(archive);
    for(unsigned i=0;i<n;++i)if(!std::memcmp(archive+16+4*n+4*i,"ESQ",4))index=word(archive+16+4*i);
    if(!index)return;
    require(re4dc_effect_bind(archive,bytes),"fixture effect bind");
    const auto mark=arena.mark();
    auto expected=re4dc::storage::read_file(arena,"/cd/effects-checks.bin");
    require(!expected.error && expected.size>=4,"fixture effect expectations");
    unsigned count=word(expected.data);require(expected.size==4+12*count && count==word(archive+index+12),"fixture effect count");
    unsigned reads=0;const auto begin=timer_us_gettime64();
    for(unsigned repeat=0;repeat<100;++repeat)for(unsigned i=0;i<count;++i) {
        const auto* e=expected.data+4+12*i;auto* head=archive+word(e);unsigned n=word(e+4),hash=2166136261U;
        for(unsigned b=0;b<48;++b)hash=(hash^head[b])*16777619U;
        for(unsigned j=0;j<n;++j) {
            alignas(4) unsigned char scratch[300];
            void* retained=re4dc_effect_record_ref(head,j);
            auto* record=static_cast<unsigned char*>(re4dc_effect_record_read(retained,scratch));
            for(unsigned b=0;b<300;++b)hash=(hash^record[b])*16777619U;
            ++reads;
        }
        require(hash==word(e+8),"fixture effect source byte mismatch");
    }
    const auto elapsed=timer_us_gettime64()-begin;Re4dcEffectStats stats{};re4dc_effect_get_stats(&stats);
    re4dc_log("effect-fixture PASS: records=%u repeats=100 total_us=%llu decode_worst_us=%llu allocations=0 io_bytes_after_load=0\n",reads,elapsed,stats.worst_decode_us);
    re4dc_effect_unbind(archive);arena.rewind(mark);
}
void report(const char* phase) {
    Re4dcMotionStats s{};re4dc_motion_get_stats(&s);
    re4dc_log("motion-fixture %s: hits=%u misses=%u loads=%u evictions=%u bytes=%llu worst_us=%llu\n",
        phase,s.hits,s.misses,s.loads,s.evictions,s.bytes_read,s.worst_wait_us);
    re4dc_log("motion-fixture %s: cache=%u peak=%u pinned=%u peak_pinned=%u metadata=%u hot=%u payload_peak=%u\n",
        phase,s.resident_bytes,s.peak_cache_bytes,s.pinned_bytes,s.peak_pinned_bytes,s.metadata_bytes,s.hot_bytes,peak_bytes);
}
}
extern "C" int re4dc_motion_current_heap() { return 4; } // fixture allocator only
extern "C" void* re4dc_motion_alloc(unsigned bytes) {
    auto* p=static_cast<unsigned*>(memalign(32,bytes+32));if(!p)return nullptr;
    p[0]=bytes;live_bytes+=bytes;if(live_bytes>peak_bytes)peak_bytes=live_bytes;return p+8;
}
extern "C" void re4dc_motion_free(void* p) { if(p) { auto* base=static_cast<unsigned*>(p)-8;live_bytes-=base[0];free(base); } }
int main() {
    re4dc_set_stage(325);
    re4dc_log("motion-fixture start: diagnostic KOS allocator; not source-heap acceptance\n");
    // 2 MiB fixture backing. The actual archive size and its CRC are recorded.
    auto* backing=static_cast<unsigned char*>(memalign(32,2*1024*1024));
    require(backing!=nullptr,"fixture archive allocation");
    re4dc::storage::Arena arena;arena.init(backing,2*1024*1024);
    auto loaded=re4dc::storage::read_file(arena,"/cd/em12.arc");
    require(!loaded.error,"fixture archive read");archive=const_cast<unsigned char*>(loaded.data);
    const unsigned n=word(archive),offset=word(archive+16+4*(n-1));
    records=archive+offset+32;count=word(archive+offset+12);
    check_effects(arena,loaded.size);
    require(re4dc_motion_bind(archive,loaded.size),"fixture bind");report("prefetch");
    unsigned found=0;
    for(unsigned i=0;i<count;++i)if(!word(records+20*i+16)) {
        if(found<3)cold[found++]=i;
        else { unsigned smallest=0;for(unsigned j=1;j<3;++j)if(word(records+20*cold[j]+4)<word(records+20*cold[smallest]+4))smallest=j;
            if(word(records+20*i+4)>word(records+20*cold[smallest]+4))cold[smallest]=i; }
    }
    require(found==3,"fixture cold coverage");
    Re4dcMotionStats before{},after{};re4dc_motion_get_stats(&before);
    for(unsigned repeat=0;repeat<100;++repeat)for(unsigned i=0;i<count;++i)if(word(records+20*i+16))evaluate(i);
    re4dc_motion_get_stats(&after);
    require(after.misses==before.misses && after.bytes_read==before.bytes_read,"fixture warm hot reload");
    report("steady100");
    selected=archive+word(archive+16+4); // supplied real fixture: em12 model440 / motion1
    // Separate stress phase: make the sampled motion cold to force its reload.
    // This modifies fixture metadata only, never the game candidate or clip.
    re4dc_motion_unbind(archive);
    bool changed=false;
    for(unsigned i=0;i<count;++i)if(archive+word(records+20*i)==selected) {
        unsigned zero=0;std::memcpy(records+20*i+16,&zero,4);changed=true;
    }
    require(changed,"fixture sampled key identity");
    unsigned crc=net_crc32le(records,count*20);std::memcpy(archive+offset+20,&crc,4);
    const unsigned pristine=net_crc32le(archive,loaded.size);
    require(re4dc_motion_bind(archive,loaded.size),"fixture pressure bind");
    auto result=run_real_motion_checks(selected,after_evaluation);
    require(net_crc32le(archive,loaded.size)==pristine,"fixture retained archive mutated");
    re4dc_log("motion-fixture source: failures=%d parts=%d joints=%d samples=%d root=%.8f angle=%.8f world=%.8f\n",
        result.failures,result.part_count,result.joint_count,result.frames_tested,result.max_root_error,result.max_angle_error,result.max_world_error);
    report("pressure");
    re4dc_motion_retire_all();require(!live_bytes,"fixture allocation leak");free(backing);
    re4dc_set_stage(result.failures ? 0xdead : 326);
    re4dc_log("motion-fixture %s; diagnostic, not encounter or hardware acceptance\n",result.failures?"FAIL":"PASS");
    for(;;)thd_sleep(1000);
}
