#pragma once
// D367 vertex-path prototype: transform-once meshlet cache for R4IM meshes.
//
// Per visible meshlet: classify the meshlet's grid box once (inside / crosses a
// screen edge / crosses near or far), transform every meshlet vertex exactly
// once through the loaded XMTRX into a 32-byte PVR-ready cache entry, then
// assemble strips by copying cache entries. Strip accept / cull / clip
// decisions are the existing Emitter's (depth in [near,far] -> direct,
// all-outside-one-edge -> culled, otherwise the shared clipper), evaluated on
// per-vertex outcodes instead of on freshly transformed corners.
//
// Positions and 1/w come from the same ftrv, the same XMTRX (load_screen) and
// the same 1.0f/w and x*inv as prepare_static_vertex(), so accepted vertices
// are bit-identical in x/y/z, colour and flags. UV: transform_c<> keeps the
// current operation order (bit-identical); the SH4 assembly loop folds
// bias/offset/native scale into one fmac per axis (<= ~1 ulp difference).
//
// Storage: none of its own. The cache is the tail of the packet range the
// Emitter already owns between re4dc_model_packet_begin() and commit (the
// frame owner's slab); the 2 KiB colour LUT lives in the mesh view's heap-4
// allocation. No BSS/rodata growth beyond code.
#include <cstdint>
#include <cstring>
#include <dc/pvr.h>
// Test builds may substitute VP_FTRV / VP_ASM_FTRV (qemu-sh4 has no ftrv).
#if defined(__sh__)
#include <dc/matrix.h>
#ifndef VP_FTRV
#define VP_FTRV(x,y,z,w) mat_trans_nodiv(x,y,z,w)
#endif
#define VP_PREF(p) __builtin_prefetch(p)
#else
// Host model of the SH4 XMTRX for logic tests only (see host_equiv_test.cpp).
extern float vp_host_xmtrx[4][4]; // [column][row], like KOS matrix_t
#define VP_FTRV(x,y,z,w) do{ const float _x=(x),_y=(y),_z=(z),_w=(w); \
    (x)=vp_host_xmtrx[0][0]*_x+vp_host_xmtrx[1][0]*_y+vp_host_xmtrx[2][0]*_z+vp_host_xmtrx[3][0]*_w; \
    (y)=vp_host_xmtrx[0][1]*_x+vp_host_xmtrx[1][1]*_y+vp_host_xmtrx[2][1]*_z+vp_host_xmtrx[3][1]*_w; \
    (z)=vp_host_xmtrx[0][2]*_x+vp_host_xmtrx[1][2]*_y+vp_host_xmtrx[2][2]*_z+vp_host_xmtrx[3][2]*_w; \
    (w)=vp_host_xmtrx[0][3]*_x+vp_host_xmtrx[1][3]*_y+vp_host_xmtrx[2][3]*_z+vp_host_xmtrx[3][3]*_w; }while(0)
#define VP_PREF(p) ((void)0)
#endif
#ifndef VP_ASM_FTRV
#define VP_ASM_FTRV "ftrv    xmtrx,fv0\n\t"
#define VP_ASM_FTRV_CLOBBER
#endif

namespace re4dc::vp {
// Field layout shared with room::CompactVertex12 (12 bytes, 4-byte aligned in
// an R4IM vertex section: 4-aligned offset, 12-byte stride).
struct Vertex12 { std::uint16_t x,y,z,u,v,color; };
static_assert(sizeof(Vertex12)==12);

constexpr unsigned kCacheEntries=256;                           // R4IM meshlet bound
constexpr unsigned kCacheSlots=kCacheEntries+kCacheEntries/32U; // 32-byte packet slots: entries + outcode bytes

// Per-meshlet checks the transform performs (classify()).
constexpr unsigned kChecksNone=0, kChecksScreen=1, kChecksDepth=2, kChecksAll=3;
// Outcode byte layout, built MSB-first like the assembly's 'rotcl' chain:
//   screen only : bit3 x<0, bit2 x>640, bit1 y<0, bit0 y>480
//   with depth  : bits 5..2 as above, bit1 depth<near, bit0 depth>far
// Bits above the defined ones are don't-care (masked).
constexpr unsigned screen_mask(unsigned checks){return (checks&kChecksDepth)?0x3cU:(checks?0x0fU:0U);}
constexpr unsigned depth_mask(unsigned checks){return (checks&kChecksDepth)?0x03U:0U;}

// UV constants. Exact: u' = ((bias + u*scale) + offset) * native (the current
// Emitter order). Folded (assembly): u' = u*a + b.
// Assembly constant block, loaded into fr7..fr15 in this order.
struct AsmConstants { float zero,au,bu,av,bv,width,height,near_distance,far_distance; };
struct Constants {
    float su,bu,off_u,scale_u, sv,bv,off_v,scale_v;
    float near_distance,far_distance;
    std::uint32_t and_mask,or_bits; // !vertex_alpha: and 0x00ffffff, or material alpha<<24
    const std::uint32_t* lut;       // [0,256) high byte, [256,512) low byte
    AsmConstants f;                 // finish(): once per part, after bind()
    void finish(){
        f={0.0f,su*scale_u,(bu+off_u)*scale_u,sv*scale_v,(bv+off_v)*scale_v,
           640.0f,480.0f,near_distance,far_distance};
    }
};

// ARGB1555 -> ARGB8888 exactly as Emitter::argb1555(): every output bit is a
// copy of one input bit, so the high- and low-byte halves OR together.
inline std::uint32_t argb1555(std::uint32_t c){
    const std::uint32_t r=(c>>10)&31U,g=(c>>5)&31U,b=c&31U;
    return ((c&0x8000U)?0xff000000U:0U)|(((r<<3)|(r>>2))<<16)|(((g<<3)|(g>>2))<<8)|((b<<3)|(b>>2));
}
inline void build_lut(std::uint32_t* lut){
    for(unsigned i=0;i<256;++i){lut[i]=argb1555(i<<8);lut[256+i]=argb1555(i);}
}

// Conservative interior test of a grid box (m already contains the grid).
// Same support-radius form and planes as render::group_visible() (bias 0),
// with a one-pixel inner margin and a 0.1% depth margin, so no vertex of a
// 'none' meshlet can reach an Emitter outside or depth test through rounding.
inline unsigned classify(const float bmin[3],const float bmax[3],const float m[12],
                         const float p[7],const float vp[6],float near_distance,float far_distance){
    float center[3],extent[3],view[3],radius[3];
    for(unsigned a=0;a<3;++a){center[a]=(bmin[a]+bmax[a])*0.5f;extent[a]=(bmax[a]-bmin[a])*0.5f;}
    for(unsigned r=0;r<3;++r){const float* v=m+4*r;
        view[r]=v[0]*center[0]+v[1]*center[1]+v[2]*center[2]+v[3];
        radius[r]=__builtin_fabsf(v[0])*extent[0]+__builtin_fabsf(v[1])*extent[1]+__builtin_fabsf(v[2])*extent[2];}
    const float zmin=-view[2]-radius[2],zmax=-view[2]+radius[2];
    if(!(zmin>=near_distance*1.001f) || !(zmax<=far_distance*0.999f))return kChecksAll;
    const auto inside=[&](float a,float b,float c){
        return a*view[0]+b*view[1]+c*view[2]-
            (__builtin_fabsf(a)*radius[0]+__builtin_fabsf(b)*radius[1]+__builtin_fabsf(c)*radius[2])>0.0f;};
    const float ox=2*vp[0]/vp[2],oy=2*vp[1]/vp[3],mx=2.0f/640.0f,my=2.0f/480.0f;
    const bool in=inside(p[1],0,p[2]-1-ox+mx) && inside(-p[1],0,-p[2]-1+ox+mx) &&
                  inside(0,-p[3],-p[4]-1-oy+my) && inside(0,p[3],p[4]-1+oy+my);
    return in?kChecksNone:kChecksScreen;
}

// Portable transform (host tests; SH4 reference). Writes x,y,z,u,v,argb of
// count cache entries (flags/oargb words are set once by prime()) and, when
// Checks != none, one outcode byte per vertex.
template<unsigned Checks,bool Fold=false>
inline void transform_c(const Vertex12* __restrict in,unsigned count,
    pvr_vertex_t* __restrict cache,std::uint8_t* __restrict oc,const Constants& k){
    const AsmConstants& f=k.f;
    do{
        VP_PREF(in+3);
        float x=float(in->x),y=float(in->y),z=float(in->z),w=1.0f;
        VP_FTRV(x,y,z,w);
        // w<=0 only happens in depth-checked meshlets; those strips reach the
        // clipper, which never reads the cache. classify(): otherwise w>=near>0.
        const float inverse=1.0f/w;
        const float sx=x*inverse,sy=y*inverse;
        const std::uint32_t c=in->color;
        cache->x=sx;cache->y=sy;cache->z=inverse;
        if(Fold){cache->u=float(in->u)*f.au+f.bu;cache->v=float(in->v)*f.av+f.bv;}
        else {cache->u=((k.bu+float(in->u)*k.su)+k.off_u)*k.scale_u;cache->v=((k.bv+float(in->v)*k.sv)+k.off_v)*k.scale_v;}
        cache->argb=((k.lut[c>>8]|k.lut[256+(c&255U)])&k.and_mask)|k.or_bits;
        if(Checks!=kChecksNone){
            unsigned code=(sx<0.0f?8U:0U)|(sx>640.0f?4U:0U)|(sy<0.0f?2U:0U)|(sy>480.0f?1U:0U);
            if(Checks&kChecksDepth)code=(code<<2)|(w<k.near_distance?2U:0U)|(w>k.far_distance?1U:0U);
            *oc++=std::uint8_t(code);
        }
        ++in;++cache;
    }while(--count);
}

#if defined(__sh__)
// Hand-scheduled SH4 transform: one dynarec block per vertex, 3 longword
// loads, every store through one pre-decrementing pointer, constants resident
// in fr7..fr15, no calls. Same outcode layout as transform_c<>.
#define VP_ASM_SCREEN \
    "fcmp/gt fr0,fr7\n\t"  "rotcl r1\n\t"   /* x<0   */ \
    "fcmp/gt fr12,fr0\n\t" "rotcl r1\n\t"   /* x>640 */ \
    "fcmp/gt fr1,fr7\n\t"  "rotcl r1\n\t"   /* y<0   */ \
    "fcmp/gt fr13,fr1\n\t" "rotcl r1\n\t"   /* y>480 */
#define VP_ASM_DEPTH \
    "fcmp/gt fr3,fr14\n\t" "rotcl r1\n\t"   /* w<near */ \
    "fcmp/gt fr15,fr3\n\t" "rotcl r1\n\t"   /* w>far  */
#define VP_ASM_STORE_CODE "mov.b r1,@%[oc]\n\t" "add #1,%[oc]\n\t"
#define VP_ASM_TRANSFORM(CODES) \
    "fmov.s  @%[k]+,fr7\n\t" "fmov.s @%[k]+,fr8\n\t"  "fmov.s @%[k]+,fr9\n\t" \
    "fmov.s  @%[k]+,fr10\n\t" "fmov.s @%[k]+,fr11\n\t" "fmov.s @%[k]+,fr12\n\t" \
    "fmov.s  @%[k]+,fr13\n\t" "fmov.s @%[k]+,fr14\n\t" "fmov.s @%[k]+,fr15\n" \
    "1:\n\t" \
    "mov.l   @%[in]+,r1\n\t"      /* x | y<<16      */ \
    "mov.l   @%[in]+,r2\n\t"      /* z | u<<16      */ \
    "mov.l   @%[in]+,r3\n\t"      /* v | colour<<16 */ \
    "mov     r2,r0\n\t"  "shlr16 r0\n\t" "lds r0,fpul\n\t" "float fpul,fr0\n\t" \
    "fmov    fr9,fr5\n\t" "fmac fr0,fr8,fr5\n\t"     /* u' = u*au+bu */ \
    "extu.w  r3,r0\n\t"  "lds r0,fpul\n\t" "float fpul,fr0\n\t" \
    "fmov    fr11,fr6\n\t" "fmac fr0,fr10,fr6\n\t"   /* v' = v*av+bv */ \
    "extu.w  r1,r0\n\t"  "lds r0,fpul\n\t" "float fpul,fr0\n\t" \
    "shlr16  r1\n\t"     "lds r1,fpul\n\t" "float fpul,fr1\n\t" \
    "extu.w  r2,r0\n\t"  "lds r0,fpul\n\t" "float fpul,fr2\n\t" \
    "fldi1   fr3\n\t" \
    VP_ASM_FTRV \
    "shlr16  r3\n\t"     "extu.b r3,r0\n\t" "shll2 r0\n\t" "mov.l @(r0,%[lo]),r1\n\t" \
    "shlr8   r3\n\t"     "mov r3,r0\n\t"    "shll2 r0\n\t" "mov.l @(r0,%[hi]),r2\n\t" \
    "or      r2,r1\n\t"  "and %[andm],r1\n\t" "or %[orb],r1\n\t" \
    "fldi1   fr4\n\t"    "fdiv fr3,fr4\n\t"             /* 1/w */ \
    "mov.l   r1,@-%[dst]\n\t"                            /* argb @24 */ \
    "fmov.s  fr6,@-%[dst]\n\t"                           /* v    @20 */ \
    "fmov.s  fr5,@-%[dst]\n\t"                           /* u    @16 */ \
    "pref    @%[pf]\n\t" "add #12,%[pf]\n\t" \
    "fmov.s  fr4,@-%[dst]\n\t"                           /* z    @12 */ \
    "fmul    fr4,fr0\n\t" "fmul fr4,fr1\n\t" \
    "fmov.s  fr1,@-%[dst]\n\t"                           /* y    @8  */ \
    "fmov.s  fr0,@-%[dst]\n\t"                           /* x    @4  */ \
    CODES \
    "dt      %[count]\n\t" \
    "bf/s    1b\n\t" \
    "add     #56,%[dst]\n\t"                             /* entry+4 -> next entry+28 */

template<unsigned Checks>
inline void transform(const Vertex12* in,unsigned count,pvr_vertex_t* cache,std::uint8_t* oc,
                      const Constants& k){
    const AsmConstants& f=k.f;
    const float* kp=&f.zero;
    auto* dst=reinterpret_cast<std::uint32_t*>(cache)+7; // entry + 28
    const Vertex12* pf=in+3;
    const std::uint32_t* hi=k.lut;const std::uint32_t* lo=k.lut+256;
    const std::uint32_t andm=k.and_mask,orb=k.or_bits;
#define VP_ASM_OPERANDS \
        : [in]"+r"(in),[count]"+r"(count),[dst]"+r"(dst),[oc]"+r"(oc),[pf]"+r"(pf),[k]"+r"(kp) \
        : [lo]"r"(lo),[hi]"r"(hi),[andm]"r"(andm),[orb]"r"(orb),"m"(f) \
        : "r0","r1","r2","r3","fpul","fr0","fr1","fr2","fr3","fr4","fr5","fr6","fr7", \
          "fr8","fr9","fr10","fr11","fr12","fr13","fr14","fr15","t","memory" VP_ASM_FTRV_CLOBBER
    if constexpr(Checks==kChecksNone)
        __asm__ __volatile__(VP_ASM_TRANSFORM("") VP_ASM_OPERANDS);
    else if constexpr(Checks==kChecksScreen)
        __asm__ __volatile__(VP_ASM_TRANSFORM(VP_ASM_SCREEN VP_ASM_STORE_CODE) VP_ASM_OPERANDS);
    else
        __asm__ __volatile__(VP_ASM_TRANSFORM(VP_ASM_SCREEN VP_ASM_DEPTH VP_ASM_STORE_CODE) VP_ASM_OPERANDS);
#undef VP_ASM_OPERANDS
}
#else
template<unsigned Checks>
inline void transform(const Vertex12* in,unsigned count,pvr_vertex_t* cache,std::uint8_t* oc,const Constants& k){
    transform_c<Checks,true>(in,count,cache,oc,k);
}
#endif

// Constant words of every cache entry; the transform never rewrites them.
inline void prime(pvr_vertex_t* cache,unsigned count){
    for(unsigned i=0;i<count;++i){cache[i].flags=PVR_CMD_VERTEX;cache[i].oargb=0;}
}

// AND / OR of the outcodes a strip references.
struct StripCodes { unsigned all, any; };
__attribute__((always_inline)) inline StripCodes codes(const std::uint8_t* __restrict oc,
                                                       const std::uint8_t* __restrict index,unsigned n){
    unsigned all=0xff,any=0;
#if defined(__sh__)
    __asm__(
        "1:\n\t"
        "mov.b   @%[index]+,r0\n\t"
        "extu.b  r0,r0\n\t"
        "mov.b   @(r0,%[oc]),r0\n\t"
        "dt      %[n]\n\t"
        "and     r0,%[all]\n\t"
        "bf/s    1b\n\t"
        "or      r0,%[any]\n\t"
        : [all]"+r"(all),[any]"+r"(any),[index]"+r"(index),[n]"+r"(n)
        : [oc]"r"(oc),"m"(*(const std::uint8_t(*)[256])oc)
        : "r0","t");
#else
    do{const unsigned c=oc[*index++];all&=c;any|=c;}while(--n);
#endif
    return {all,any};
}

// Copy n (>=1) cache entries selected by index into 32-byte aligned packet
// storage and mark the last one EOL. 64-bit FPU moves (FPSCR.SZ), as in
// sq_fast_cpy(); returns the slot after the last vertex.
__attribute__((always_inline)) inline pvr_vertex_t* emit(pvr_vertex_t* __restrict dst,const pvr_vertex_t* __restrict cache,
                          const std::uint8_t* __restrict index,unsigned n){
#if defined(__sh__)
    __asm__ __volatile__(
        "fschg\n"
        "1:\n\t"
        "mov.b   @%[index]+,r0\n\t"
        "extu.b  r0,r0\n\t"
        "shld    %[five],r0\n\t"
        "add     %[cache],r0\n\t"
        "fmov    @r0+,dr0\n\t"
        "fmov    @r0+,dr2\n\t"
        "fmov    @r0+,dr4\n\t"
        "fmov    @r0+,dr6\n\t"
        "add     #32,%[dst]\n\t"
        "fmov    dr6,@-%[dst]\n\t"
        "fmov    dr4,@-%[dst]\n\t"
        "fmov    dr2,@-%[dst]\n\t"
        "fmov    dr0,@-%[dst]\n\t"
        "dt      %[n]\n\t"
        "bf/s    1b\n\t"
        "add     #32,%[dst]\n\t"
        "fschg\n"
        : [dst]"+r"(dst),[index]"+r"(index),[n]"+r"(n)
        : [cache]"r"(cache),[five]"r"(5)
        : "r0","fr0","fr1","fr2","fr3","fr4","fr5","fr6","fr7","t","memory");
    dst[-1].flags=PVR_CMD_VERTEX_EOL;
    return dst;
#else
    for(unsigned k=0;k<n;++k)dst[k]=cache[index[k]];
    dst[n-1].flags=PVR_CMD_VERTEX_EOL;
    return dst+n;
#endif
}

#if defined(__sh__)
// Phase B: the same copy straight into the TA through the store queues. The
// caller holds sq_lock() and has already sent the packet header; sq points
// into SQ_MASK_DEST(PVR_TA_INPUT) (32-byte aligned). EOL is written into the
// last vertex before its burst leaves: nothing can be patched after 'pref'.
inline std::uint32_t* emit_sq(std::uint32_t* sq,const pvr_vertex_t* __restrict cache,
                              const std::uint8_t* __restrict index,unsigned n){
    const std::uint32_t eol=PVR_CMD_VERTEX_EOL;
    __asm__ __volatile__(
        "fschg\n"
        "1:\n\t"
        "mov.b   @%[index]+,r0\n\t"
        "extu.b  r0,r0\n\t"
        "shld    %[five],r0\n\t"
        "add     %[cache],r0\n\t"
        "fmov    @r0+,dr0\n\t"
        "fmov    @r0+,dr2\n\t"
        "fmov    @r0+,dr4\n\t"
        "fmov    @r0+,dr6\n\t"
        "add     #32,%[sq]\n\t"
        "fmov    dr6,@-%[sq]\n\t"
        "fmov    dr4,@-%[sq]\n\t"
        "fmov    dr2,@-%[sq]\n\t"
        "dt      %[n]\n\t"
        "bf/s    2f\n\t"
        "fmov    dr0,@-%[sq]\n\t"
        "mov.l   %[eol],@%[sq]\n"      /* last vertex: EOL replaces the flags word */
        "2:\n\t"
        "pref    @%[sq]\n\t"
        "tst     %[n],%[n]\n\t"
        "bf/s    1b\n\t"
        "add     #32,%[sq]\n\t"
        "fschg\n"
        : [sq]"+r"(sq),[index]"+r"(index),[n]"+r"(n)
        : [cache]"r"(cache),[five]"r"(5),[eol]"r"(eol)
        : "r0","fr0","fr1","fr2","fr3","fr4","fr5","fr6","fr7","t","memory");
    return sq;
}
#endif
} // namespace re4dc::vp
