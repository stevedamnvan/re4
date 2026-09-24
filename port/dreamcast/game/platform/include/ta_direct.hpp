#pragma once
// Emitter-side helpers for the direct TA submission API in native_model.h
// (re4dc_model_direct_begin/end). SH4 KOS only: 'sq' is a store-queue
// address returned by the frame owner with the TA input window locked.
#include <cstdint>
#include <dc/pvr.h>
#include <dc/sq.h>
#include "native_model.h"

// n prepared, 8-byte aligned vertices (e.g. clipped triangles, a qualified
// strip built in a small register/stack buffer) -> TA. Returns the next slot.
inline std::uint32_t* re4dc_ta_put(std::uint32_t* sq,const pvr_vertex_t* v,unsigned n){
#if RE4DC_TA_HASH
    re4dc_ta_hash(v,n*32);
#endif
    if(n){sq_fast_cpy(sq,v,n);sq+=8*n;}
    return sq;
}
// One vertex computed in registers. Flags go in the same burst, so an EOL
// decision must be made before the call.
inline std::uint32_t* re4dc_ta_vertex(std::uint32_t* sq,std::uint32_t flags,float x,float y,float z,
                                      float u,float v,std::uint32_t argb,std::uint32_t oargb=0){
    auto* f=reinterpret_cast<float*>(sq);
    sq[0]=flags;f[1]=x;f[2]=y;f[3]=z;f[4]=u;f[5]=v;sq[6]=argb;sq[7]=oargb;
#if RE4DC_TA_HASH
    {const float b[8]={0,x,y,z,u,v,0,0};std::uint32_t w[8];__builtin_memcpy(w,b,32);w[0]=flags;w[6]=argb;w[7]=oargb;re4dc_ta_hash(w,32);}
#endif
    sq_flush(sq);
    return sq+8;
}
