// Selectable backing for the reviewed source managers. Logical slots, source
// constructors/destructors and model-local contiguous arrays remain authoritative.
#include "model.h"
#include "obj.h"
#include "global.h"
#include "main_mem.h"
#include "re4dc_platform.h"
extern "C" void OSFreeToHeap(int, void*);

namespace {
template<class T> struct alignas(32) Chunk {
    Chunk<T>* next;
    u32 first, count, bytes;
    u32 reserved[4];
    T* parts() { return (T*)(this + 1); }
};
template<class T> struct alignas(32) Pool {
    Chunk<T>* chunks;
    u32 capacity, bytes, peak, chunks_count, reclaims, failures;
    int heap, handle;
    u32 reserved[7];
    T** slots() { return (T**)(this + 1); }
};
static_assert(sizeof(Chunk<cParts>) % 32 == 0 && sizeof(Chunk<cModelInfo>) % 32 == 0);
static_assert(sizeof(Pool<cParts>) % 32 == 0 && sizeof(Pool<cModelInfo>) % 32 == 0);
template<class T> constexpr bool demand=false;
template<> constexpr bool demand<cParts> = RE4DC_PARTS_DEMAND;
template<> constexpr bool demand<cModelInfo> = RE4DC_MODELINFO_DEMAND;
template<> constexpr bool demand<cObj> = RE4DC_OBJECT_DEMAND;
// Source lights and indexed clients can retain even an unconstructed/dead
// object slot. Once exposed, its address stays valid until source pool teardown.
template<class T> constexpr bool retain_slots=false;
template<> constexpr bool retain_slots<cObj> = true;
template<class T> bool sparse(cManager<T>* m) { return demand<T> && !m->pArrayPush; }
template<class T> Pool<T>* pool(cManager<T>* m) { return (Pool<T>*)m->pArray; }
template<class T> void report(Pool<T>* p, const char* why) {
    re4dc_log("work backing: %s size=%u capacity=%u resident=%u peak=%u chunks=%u reclaimed=%u failures=%u heap=%d\n",
        why,(unsigned)sizeof(T),p->capacity,p->bytes,p->peak,p->chunks_count,p->reclaims,p->failures,p->heap);
}
template<class T> bool alive(Chunk<T>* c) {
    for(u32 i=0;i<c->count;++i) if(c->parts()[i].be_flag & 0x601) return true;
    return false;
}
template<class T> void discard(Pool<T>* p, Chunk<T>** link) {
    Chunk<T>* c=*link;
    for(u32 i=0;i<c->count;++i) p->slots()[c->first+i]=0;
    *link=c->next;p->bytes-=c->bytes;--p->chunks_count;++p->reclaims;
    OSFreeToHeap(p->handle,c);
}
}

template<class T> int array_free(cManager<T>* m) {
    if(!m->pArray) return 0;
    if(!sparse(m)) { m->memFree(m->pArray);m->pArray=0;return 1; }
    Pool<T>* p=pool(m);
    // As in the source arrayFree, callers own destruction/order. This releases
    // backing after those consumers finish; roomInit instead forgets the old
    // pointer after the owning room heap has been reset by the source.
    while(p->chunks) discard(p,&p->chunks);
    OSFreeToHeap(p->handle,p);m->pArray=0;return 1;
}
template<class T> int array_alloc(cManager<T>* m,u32 n) {
    array_free(m);m->nArray=n;
    if(!demand<T> || m->pArrayPush) {
        m->pArray=(T*)m->memAlloc(m->size*n);
        if(n && m->pArray)m->memClear(m->pArray,m->size*n);
        return !n || m->pArray!=0;
    }
    // Tool-memory bulk sweeping needs a separate ownership qualification. Normal
    // room and subscreen managers use explicit source heap ownership below.
    if(pG->Debug_flg[3] & 0x200000) { re4dc_missing("parts demand debug heap unqualified");return 0; }
    if(m->size!=sizeof(T) || n>(0xffffffffU-sizeof(Pool<T>)-31)/sizeof(T*) ||
       n>(0xffffffffU-sizeof(Chunk<T>)-31)/sizeof(T)) {
        re4dc_missing("parts capacity overflow");return 0;
    }
    const u32 bytes=(sizeof(Pool<T>)+n*sizeof(T*)+31)&~31U;
    Pool<T>* p=(Pool<T>*)mem_alloc(bytes,"native parts slots",0,1,MEM_HEAP_CURRENT);
    if(!p) { re4dc_missing("parts slot allocation");return 0; }
    memclr_asm(p,bytes);p->capacity=n;p->bytes=bytes+64;p->peak=p->bytes;
    p->heap=MemGetCurrentHeap();p->handle=Heap[p->heap].handle;
    m->pArray=(T*)p;report(p,"init");return 1;
}
template<class T> T* work_at(cManager<T>* m,u32 no) {
    if(!m->pArray || no>=m->nArray)return 0;
    return sparse(m)?pool(m)->slots()[no]:(T*)((u8*)m->pArray+m->size*no);
}
template<class T> bool prepare_work(cManager<T>* m,u32 first,u32 count) {
    if(!m->pArray || !count || first>=m->nArray || count>m->nArray-first)return false;
    if(!sparse(m))return true;
    Pool<T>* p=pool(m);T** slots=p->slots();
    // Reusing an existing physical run does not allocate or move anything.
    for(Chunk<T>* c=p->chunks;c;c=c->next)
        if(first>=c->first && first-c->first<c->count && count<=c->count-(first-c->first))return true;
    for(Chunk<T>* c=p->chunks;c;c=c->next) {
        if(c->first<first+count && c->first+c->count>first && (retain_slots<T> || alive(c)))return false;
    }
    // Only fully dead chunks can be replaced. Deferred-deletion flags count as
    // live. Partial releases cannot invalidate the surviving model's pointers.
    for(Chunk<T>** c=&p->chunks;*c;) {
        if((*c)->first<first+count && (*c)->first+(*c)->count>first)discard(p,c);
        else c=&(*c)->next;
    }
    const u32 bytes=(sizeof(Chunk<T>)+count*m->size+31)&~31U;
    Chunk<T>* c=(Chunk<T>*)mem_alloc(bytes,"native parts run",0,0,p->heap);
    if(!c) {
        // Keep dead runs reusable normally; under heap pressure reclaim them.
        for(Chunk<T>** q=&p->chunks;*q;) { if(!retain_slots<T> && !alive(*q))discard(p,q);else q=&(*q)->next; }
        c=(Chunk<T>*)mem_alloc(bytes,"native parts run",0,1,p->heap);
    }
    if(!c) { ++p->failures;report(p,"allocation failed");return false; }
    memclr_asm(c,bytes);c->first=first;c->count=count;c->bytes=bytes+64;
    c->next=p->chunks;p->chunks=c;
    for(u32 j=0;j<count;++j)slots[first+j]=c->parts()+j;
    p->bytes+=c->bytes;++p->chunks_count;if(p->bytes>p->peak)p->peak=p->bytes;
    report(p,"grow");return true;
}
template<class T> T* previous_work(cManager<T>* m,T* p) {
    if(!m->pArray || !p)return 0;
    for(u32 i=1;i<m->nArray;++i)if(m->workAt(i)==p) {
        if(retain_slots<T> && !m->prepareWork(i-1,1))return 0;
        return m->workAt(i-1);
    }
    return 0;
}
// Only these reviewed managers use this backing implementation. Parts keep
// model-sized runs; model-info has no cross-slot arithmetic/contiguity contract
// and uses bounded pages to avoid one heap allocation per material/model record.
template<> int cManager<cParts>::arrayAlloc(u32 n){return array_alloc(this,n);}
template<> int cManager<cParts>::arrayFree(){return array_free(this);}
template<> cParts* cManager<cParts>::workAt(u32 n){return work_at(this,n);}
template<> bool cManager<cParts>::prepareWork(u32 i,u32 n){return prepare_work(this,i,n);}
template<> cParts* cManager<cParts>::getPrevWork(cParts* p){return previous_work(this,p);}
template<> int cManager<cModelInfo>::arrayAlloc(u32 n){return array_alloc(this,n);}
template<> int cManager<cModelInfo>::arrayFree(){return array_free(this);}
template<> cModelInfo* cManager<cModelInfo>::workAt(u32 n){return work_at(this,n);}
template<> bool cManager<cModelInfo>::prepareWork(u32 i,u32 n){
    if(i>=nArray || n!=1)return false;
    const u32 first=i&~15U, count=nArray-first<16?nArray-first:16;
    return prepare_work(this,first,count);
}
template<> cModelInfo* cManager<cModelInfo>::getPrevWork(cModelInfo* p){return previous_work(this,p);}

// Fixed object pages never overlap and are never reclaimed under pressure.
// Scans use workAt without committing; ObjMgrWork commits stable indexed slots.
template<> int cManager<cObj>::arrayAlloc(u32 n){return array_alloc(this,n);}
template<> int cManager<cObj>::arrayFree(){return array_free(this);}
template<> cObj* cManager<cObj>::workAt(u32 n){return work_at(this,n);}
template<> bool cManager<cObj>::prepareWork(u32 i,u32 n){
    if(i>=nArray || n!=1)return false;
    const u32 first=i&~7U, count=nArray-first<8?nArray-first:8;
    return prepare_work(this,first,count);
}
template<> cObj* cManager<cObj>::getPrevWork(cObj* p){return previous_work(this,p);}
