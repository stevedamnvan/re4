// Qualified immutable preloads use existing disc transport, without a pretend
// ARAM copy. Preparation validates the offline qualification certificate and
// file size. Installation checks every payload chunk before source activation.
#include "native_event_file.h"
#include "native_io.h"
#include "re4dc_platform.h"
#include "../../room/room_storage.hpp"
#include <kos.h>
#include <kos/net.h>
#include <cstring>
#include <cstdio>

namespace {
Re4dcEventFileStats stats{};
constexpr unsigned chunk_bytes=65536, max_bytes=4*1024*1024;
unsigned word(const unsigned char* p) { unsigned v;std::memcpy(&v,p,4);return v; }
bool exact(file_t f,void* dst,unsigned n) {
    auto* p=static_cast<unsigned char*>(dst);
    while(n) { auto got=fs_read(f,p,n);if(got<=0 || unsigned(got)>n)return false;p+=got;n-=got; }
    return true;
}
struct Copy { const unsigned char* crc; unsigned index; unsigned char* out; };
bool consume(const unsigned char* p,std::size_t n,void* opaque) {
    auto& c=*static_cast<Copy*>(opaque);
    stats.bytes_read+=n;
    if(net_crc32le(p,n)!=word(c.crc+4*c.index++))return false;
    if(c.out) { std::memcpy(c.out,p,n);c.out+=n; }
    return true;
}
bool transfer(const char* name,unsigned bytes,void* dst) {
    if(!re4dc_event_file_name(name) || !bytes || bytes>max_bytes || (bytes&31))return false;
    Re4dcIoScope io;
    char path[96],sidecar[104];
    if(!re4dc_dvd_native_path(name,path,sizeof(path)))return false;
    snprintf(sidecar,sizeof(sidecar),"%s.evq",path);
    file_t q=fs_open(sidecar,O_RDONLY);if(q<0)return false;
    unsigned char table[32+4*(max_bytes/chunk_bytes)];
    const unsigned count=(bytes+chunk_bytes-1)/chunk_bytes, length=32+4*count;
    bool ok=fs_total(q)==static_cast<ssize_t>(length) && exact(q,table,length);
    if(ok)stats.metadata_bytes_read+=length;
    fs_close(q);
    if(!ok || std::memcmp(table,"R4EVDREF",8) || word(table+8)!=1 ||
       word(table+12)!=bytes || word(table+16)!=chunk_bytes || word(table+20)!=count ||
       word(table+24)!=net_crc32le(reinterpret_cast<const unsigned char*>(name),std::strlen(name)) ||
       word(table+28)!=net_crc32le(table+32,4*count))return false;
    file_t f=fs_open(path,O_RDONLY);if(f<0)return false;
    Copy c{table+32,0,static_cast<unsigned char*>(dst)};
    ok=fs_total(f)==static_cast<ssize_t>(bytes);
    // A preload is a qualified immutable reference, not a wasted full-file
    // read into the bounce buffer. Data becomes usable only after install.
    if(ok && dst)ok=re4dc::storage::read_chunks(f,bytes,consume,&c) && c.index==count;
    fs_close(f);
    return ok;
}
int run(const char* name,unsigned bytes,void* dst) {
    const auto start=timer_us_gettime64();
    bool ok=transfer(name,bytes,dst);
    const auto elapsed=timer_us_gettime64()-start;
    const unsigned us=elapsed>0xffffffffULL?0xffffffffU:unsigned(elapsed);
    if(us>stats.worst_wait_us)stats.worst_wait_us=us;
    if(!ok)++stats.failures;
    else if(dst)++stats.installed;
    else ++stats.prepared;
    re4dc_log("event file: %s %s bytes=%u wait_us=%u success=%u\n",dst?"install":"prepare",name,bytes,us,ok);
    return ok;
}
}
extern "C" int re4dc_event_file_name(const char* name) {
    if(!name)return 0;
    const auto n=std::strlen(name);
    if(n<9 || n>=32 || std::strncmp(name,"evd/",4) || std::strcmp(name+n-4,".evd"))return 0;
    // Exact canonical identity; reject traversal, aliases and truncated names.
    for(unsigned i=4;i<n-4;++i)if(!((name[i]>='a' && name[i]<='z') ||
        (name[i]>='0' && name[i]<='9') || name[i]=='_'))return 0;
    return 1;
}
extern "C" int re4dc_event_file_prepare(const char* n,unsigned b) { return run(n,b,nullptr); }
extern "C" int re4dc_event_file_install(const char* n,unsigned b,void* dst) { return dst?run(n,b,dst):0; }
extern "C" void re4dc_event_file_moved() { ++stats.moves; }
extern "C" const Re4dcEventFileStats* re4dc_event_file_stats() { return &stats; }
extern "C" void re4dc_event_file_reject_swap() {
    ++stats.failures;
    re4dc_missing("MemorySwap: immutable EVD requires mutable snapshot backing");
    __builtin_trap();
}
