// Selectable backing policy for the existing cPartsMgr. Logical slots, source
// constructors/destructors and model-local contiguous arrays remain authoritative.
#include "model.h"
#include "global.h"
#include "main_mem.h"
#include "re4dc_platform.h"
extern "C" void OSFreeToHeap(int, void*);

namespace {
struct alignas(32) Chunk {
    Chunk* next;
    u32 first, count, bytes;
    u32 reserved[4];
    cParts* parts() { return (cParts*)(this + 1); }
};
struct alignas(32) Pool {
    Chunk* chunks;
    u32 capacity, bytes, peak, chunks_count, reclaims, failures;
    int heap, handle;
    u32 reserved[7];
    cParts** slots() { return (cParts**)(this + 1); }
};
static_assert(sizeof(Chunk) % 32 == 0);
static_assert(sizeof(Pool) % 32 == 0);
constexpr bool demand = RE4DC_PARTS_DEMAND;
bool sparse(cManager<cParts>* m) { return demand && !m->pArrayPush; }
Pool* pool(cManager<cParts>* m) { return (Pool*)m->pArray; }
void report(Pool* p, const char* why) {
    re4dc_log("parts backing: %s capacity=%u resident=%u peak=%u chunks=%u reclaimed=%u failures=%u heap=%d\n",
        why,p->capacity,p->bytes,p->peak,p->chunks_count,p->reclaims,p->failures,p->heap);
}
bool alive(Chunk* c) {
    for(u32 i=0;i<c->count;++i) if(c->parts()[i].be_flag & 0x601) return true;
    return false;
}
void discard(Pool* p, Chunk** link) {
    Chunk* c=*link;
    for(u32 i=0;i<c->count;++i) p->slots()[c->first+i]=0;
    *link=c->next;p->bytes-=c->bytes;--p->chunks_count;++p->reclaims;
    OSFreeToHeap(p->handle,c);
}
}

template<> int cManager<cParts>::arrayFree() {
    if(!pArray) return 0;
    if(!sparse(this)) { memFree(pArray);pArray=0;return 1; }
    Pool* p=pool(this);
    // As in the source arrayFree, callers own destruction/order. This releases
    // backing after those consumers finish; roomInit instead forgets the old
    // pointer after the owning room heap has been reset by the source.
    while(p->chunks) discard(p,&p->chunks);
    OSFreeToHeap(p->handle,p);pArray=0;return 1;
}
template<> int cManager<cParts>::arrayAlloc(u32 n) {
    arrayFree();nArray=n;
    if(!demand || pArrayPush) {
        pArray=(cParts*)memAlloc(size*n);
        if(n && pArray)memClear(pArray,size*n);
        return !n || pArray!=0;
    }
    // Tool-memory bulk sweeping needs a separate ownership qualification. Normal
    // room and subscreen managers use explicit source heap ownership below.
    if(pG->Debug_flg[3] & 0x200000) { re4dc_missing("parts demand debug heap unqualified");return 0; }
    if(size!=sizeof(cParts) || n>(0xffffffffU-sizeof(Pool)-31)/sizeof(cParts*) ||
       n>(0xffffffffU-sizeof(Chunk)-31)/sizeof(cParts)) {
        re4dc_missing("parts capacity overflow");return 0;
    }
    const u32 bytes=(sizeof(Pool)+n*sizeof(cParts*)+31)&~31U;
    Pool* p=(Pool*)mem_alloc(bytes,"native parts slots",0,1,MEM_HEAP_CURRENT);
    if(!p) { re4dc_missing("parts slot allocation");return 0; }
    memclr_asm(p,bytes);p->capacity=n;p->bytes=bytes+64;p->peak=p->bytes;
    p->heap=MemGetCurrentHeap();p->handle=Heap[p->heap].handle;
    pArray=(cParts*)p;report(p,"init");return 1;
}
template<> cParts* cManager<cParts>::workAt(u32 no) {
    if(!pArray || no>=nArray)return 0;
    return sparse(this)?pool(this)->slots()[no]:(cParts*)((u8*)pArray+size*no);
}
template<> bool cManager<cParts>::prepareWork(u32 first,u32 count) {
    if(!pArray || !count || first>=nArray || count>nArray-first)return false;
    if(!sparse(this))return true;
    Pool* p=pool(this);cParts** slots=p->slots();
    // Reusing an existing physical run does not allocate or move anything.
    for(Chunk* c=p->chunks;c;c=c->next)
        if(first>=c->first && first-c->first<c->count && count<=c->count-(first-c->first))return true;
    for(Chunk* c=p->chunks;c;c=c->next) {
        if(c->first<first+count && c->first+c->count>first && alive(c))return false;
    }
    // Only fully dead chunks can be replaced. Deferred-deletion flags count as
    // live. Partial releases cannot invalidate the surviving model's pointers.
    for(Chunk** c=&p->chunks;*c;) {
        if((*c)->first<first+count && (*c)->first+(*c)->count>first)discard(p,c);
        else c=&(*c)->next;
    }
    const u32 bytes=(sizeof(Chunk)+count*size+31)&~31U;
    Chunk* c=(Chunk*)mem_alloc(bytes,"native parts run",0,0,p->heap);
    if(!c) {
        // Keep dead runs reusable normally; under heap pressure reclaim them.
        for(Chunk** q=&p->chunks;*q;) { if(!alive(*q))discard(p,q);else q=&(*q)->next; }
        c=(Chunk*)mem_alloc(bytes,"native parts run",0,1,p->heap);
    }
    if(!c) { ++p->failures;report(p,"allocation failed");return false; }
    memclr_asm(c,bytes);c->first=first;c->count=count;c->bytes=bytes+64;
    c->next=p->chunks;p->chunks=c;
    for(u32 j=0;j<count;++j)slots[first+j]=c->parts()+j;
    p->bytes+=c->bytes;++p->chunks_count;if(p->bytes>p->peak)p->peak=p->bytes;
    report(p,"grow");return true;
}
template<> cParts* cManager<cParts>::getPrevWork(cParts* p) {
    if(!pArray || !p)return 0;
    for(u32 i=1;i<nArray;++i)if(workAt(i)==p)return workAt(i-1);
    return 0;
}