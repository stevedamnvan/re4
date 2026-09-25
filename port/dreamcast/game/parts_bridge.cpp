// Selectable backing for the reviewed source managers. Logical slots, source
// constructors/destructors and model-local contiguous arrays remain authoritative.
#include "model.h"
#include "obj.h"
#include "em.h"
#include "global.h"
#include "main_mem.h"
#include "re4dc_platform.h"
#include <stdlib.h>
#include <string.h>
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
template<> constexpr bool demand<cEm> = RE4DC_ENEMY_DEMAND;
// Source lights and indexed clients can retain even an unconstructed/dead
// object slot. Once exposed, its address stays valid until source pool teardown.
template<class T> constexpr bool retain_slots=false;
template<> constexpr bool retain_slots<cObj> = true;
template<> constexpr bool retain_slots<cEm> = true;
template<class T> bool sparse(cManager<T>* m) { return demand<T> && !m->pArrayPush; }
#if defined(RE4DC_WORKAT_INLINE) && RE4DC_WORKAT_INLINE
// GAME_WORKAT_INLINE: include/cManager.h reads the slot table of a sparse cObj / cEm pool itself.
static_assert(demand<cObj> && demand<cEm>, "GAME_WORKAT_INLINE needs OBJECT_DEMAND=1 ENEMY_DEMAND=1");
static_assert(sizeof(Pool<cObj>) == 64 && sizeof(Pool<cEm>) == 64, "cManager.h: the slot table at +64");
#endif
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

#if defined(RE4DC_WORKAT_INLINE) && RE4DC_WORKAT_INLINE
extern "C" {
u32 re4dc_frozen_pools;   // pools frozen while the sub screen is open (cManager.h's inline workAt)
}
#endif
#if RE4DC_SUBSCREEN
// Sub screen swap (sscrn_bridge.cpp). While the sub screen is open its data occupies the game's
// 3 MiB window at pG->pStFnt, where the room allocated some of these pools (the cEm pool in heap
// 4, for one). On the GameCube the window is swapped to ARAM and an indexed lookup into a
// plain array there is pointer arithmetic: callers get the slot's address (its bytes are not
// the game's until the window is restored). A demand pool instead reads its slot table and chunk
// list from the window, and growing it wrote a heap cell and slot pointers through sub screen
// bytes into image memory. So at open every pool whose header is in the window is frozen: its
// slot table is copied out (KOS heap), lookups use the copy, and a slot never prepared gets a
// zeroed stand-in work instead of an allocation. Close drops the copies.
template<class T> struct Frozen { cManager<T>* m; void* pool; u32 n; T** slots; u32 nArray; };
template<class T> struct Registry {
    static cManager<T>* mgr[8]; static unsigned nmgr;
    static Frozen<T> fz[8]; static unsigned nfz;
};
template<class T> cManager<T>* Registry<T>::mgr[8];
template<class T> unsigned Registry<T>::nmgr;
template<class T> Frozen<T> Registry<T>::fz[8];
template<class T> unsigned Registry<T>::nfz;
void* frozen_dummy;
#if defined(RE4DC_WORKAT_INLINE) && RE4DC_WORKAT_INLINE
#define RE4DC_FROZEN_ADD(n) (re4dc_frozen_pools += (n))
#else
#define RE4DC_FROZEN_ADD(n) ((void) 0)
#endif
template<class T> void register_pool(cManager<T>* m) {
    for(unsigned i=0;i<Registry<T>::nmgr;++i) if(Registry<T>::mgr[i]==m) return;
    if(Registry<T>::nmgr<8) Registry<T>::mgr[Registry<T>::nmgr++]=m;
    else re4dc_log("work backing: pool registry full (size=%u)\n",(unsigned)sizeof(T));
}
template<class T> Frozen<T>* frozen(cManager<T>* m) {
    for(unsigned i=0;i<Registry<T>::nfz;++i)
        if(Registry<T>::fz[i].m==m && Registry<T>::fz[i].pool==m->pArray) return &Registry<T>::fz[i];
    return 0;
}
template<class T> unsigned freeze_type(u32 lo,u32 hi) {
    unsigned n=0;
    for(unsigned i=0;i<Registry<T>::nmgr;++i) {
        cManager<T>* m=Registry<T>::mgr[i];
        if(!sparse(m) || !m->pArray || u32(m->pArray)<lo || u32(m->pArray)>=hi) continue;
        Pool<T>* p=pool(m);
        const u32 count=m->nArray<p->capacity?m->nArray:p->capacity;
        T** copy=(T**)malloc(count*sizeof(T*)+4);
        if(!copy) { re4dc_missing("sub screen pool freeze allocation"); return n; }
        memcpy(copy,p->slots(),count*sizeof(T*));
        Registry<T>::fz[Registry<T>::nfz++]={m,m->pArray,count,copy,m->nArray};
        RE4DC_FROZEN_ADD(1);
        re4dc_log("work backing: size=%u pool %p frozen while the sub screen is open (%u slots)\n",
            (unsigned)sizeof(T),(void*)m->pArray,(unsigned)count);
        ++n;
    }
    return n;
}
template<class T> void thaw_type() {
    // The window holds the game's bytes again, so the pool header is valid. A manager the sub
    // screen re-allocated meanwhile pointed into heap 12 (gone now) and gets its room pool back.
    for(unsigned i=0;i<Registry<T>::nfz;++i) {
        Frozen<T>& f=Registry<T>::fz[i];
        if(f.m->pArray!=(T*)f.pool || f.m->nArray!=f.nArray) {
            re4dc_log("work backing: size=%u manager moved while frozen (%p -> %p), room pool restored\n",
                (unsigned)sizeof(T),f.pool,(void*)f.m->pArray);
            f.m->pArray=(T*)f.pool;f.m->nArray=f.nArray;
        }
        free(f.slots);
    }
    RE4DC_FROZEN_ADD(0u - Registry<T>::nfz);
    Registry<T>::nfz=0;
}
#else
template<class T> void register_pool(cManager<T>*) {}
template<class T> struct Frozen { u32 n; T** slots; };
template<class T> Frozen<T>* frozen(cManager<T>*) { return 0; }
#endif
template<class T> int array_free(cManager<T>* m) {
    RE4DC_ALIVE_BUMP();
    if(!m->pArray) return 0;
    if(frozen(m)) { re4dc_log("work backing: size=%u frozen pool kept (freed while the sub screen is open)\n",(unsigned)sizeof(T));return 0; }
    if(!sparse(m)) { m->memFree(m->pArray);m->pArray=0;return 1; }
    Pool<T>* p=pool(m);
    // As in the source arrayFree, callers own destruction/order. This releases
    // backing after those consumers finish; roomInit instead forgets the old
    // pointer after the owning room heap has been reset by the source.
    while(p->chunks) discard(p,&p->chunks);
    OSFreeToHeap(p->handle,p);m->pArray=0;return 1;
}
template<class T> int array_alloc(cManager<T>* m,u32 n) {
    RE4DC_ALIVE_BUMP();
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
    m->pArray=(T*)p;register_pool(m);report(p,"init");return 1;
}
template<class T> T* work_at(cManager<T>* m,u32 no) {
    if(Frozen<T>* f=frozen(m)) return no<f->n?f->slots[no]:0;
    if(!m->pArray || no>=m->nArray)return 0;
    return sparse(m)?pool(m)->slots()[no]:(T*)((u8*)m->pArray+m->size*no);
}
template<class T> bool prepare_work(cManager<T>* m,u32 first,u32 count) {
#if RE4DC_SUBSCREEN
    if(Frozen<T>* f=frozen(m)) {
        if(!count || first>=f->n || count>f->n-first) return false;
        for(u32 j=first;j<first+count;++j) if(!f->slots[j]) f->slots[j]=(T*)frozen_dummy;
        return true;
    }
#endif
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
#if defined(RE4DC_WORKAT_INLINE) && RE4DC_WORKAT_INLINE
cObj* re4dc_work_at_obj(cManager<cObj>* m, u32 n){return work_at(m,n);}
#else
template<> cObj* cManager<cObj>::workAt(u32 n){return work_at(this,n);}
#endif
template<> bool cManager<cObj>::prepareWork(u32 i,u32 n){
    if(i>=nArray || n!=1)return false;
    const u32 first=i&~7U, count=nArray-first<8?nArray-first:8;
    return prepare_work(this,first,count);
}
template<> cObj* cManager<cObj>::getPrevWork(cObj* p){return previous_work(this,p);}

// Enemy creation uses source first-free order. Keep two-slot pages stable until
// the room owner tears down; dead slots and deferred deletion are not evictions.
template<> int cManager<cEm>::arrayAlloc(u32 n){return array_alloc(this,n);}
template<> int cManager<cEm>::arrayFree(){return array_free(this);}
#if defined(RE4DC_WORKAT_INLINE) && RE4DC_WORKAT_INLINE
cEm* re4dc_work_at_em(cManager<cEm>* m, u32 n){return work_at(m,n);}
#else
template<> cEm* cManager<cEm>::workAt(u32 n){return work_at(this,n);}
#endif
template<> bool cManager<cEm>::prepareWork(u32 i,u32 n){
    if(i>=nArray || n!=1)return false;
    const u32 first=i&~1U, count=nArray-first<2?nArray-first:2;
    return prepare_work(this,first,count);
}
template<> cEm* cManager<cEm>::getPrevWork(cEm* p){return previous_work(this,p);}

#if RE4DC_SUBSCREEN
// sscrn_bridge.cpp: before the window [lo, hi) is cleared for the sub screen / after it is back.
extern "C" unsigned re4dc_parts_freeze(u32 lo, u32 hi) {
    constexpr u32 kDummy = sizeof(cEm) > sizeof(cParts) ? sizeof(cEm) : sizeof(cParts);
    static_assert(sizeof(cObj) <= 0x2000 && sizeof(cModelInfo) <= 0x2000 && kDummy <= 0x2000, "stand-in size");
    const u32 bytes = (sizeof(cObj) > kDummy ? sizeof(cObj) : kDummy) > sizeof(cModelInfo)
        ? (sizeof(cObj) > kDummy ? sizeof(cObj) : kDummy) : sizeof(cModelInfo);
    frozen_dummy = calloc(1, bytes);
    if (!frozen_dummy) re4dc_missing("sub screen pool stand-in allocation");
    return freeze_type<cParts>(lo, hi) + freeze_type<cModelInfo>(lo, hi) + freeze_type<cObj>(lo, hi) +
           freeze_type<cEm>(lo, hi);
}
extern "C" void re4dc_parts_thaw() {
    thaw_type<cParts>(); thaw_type<cModelInfo>(); thaw_type<cObj>(); thaw_type<cEm>();
    free(frozen_dummy); frozen_dummy = 0;
}
#endif
