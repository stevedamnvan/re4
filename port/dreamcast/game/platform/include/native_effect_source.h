#pragma once
#include "native_effect.h"
// Include after esp.h: no source ABI or original file-layout changes.
static_assert(sizeof(EspGenWork)==300, "effect record ABI");
static_assert(__builtin_offsetof(EspSeqData,rec)==48, "effect sequence ABI");
inline EspGenWork* re4dc_effect_ref(EspSeqData* head,unsigned index) {
    return static_cast<EspGenWork*>(re4dc_effect_record_ref(head,index));
}
inline EspGenWork* re4dc_effect_read(EspGenWork* ref,EspGenWork& scratch) {
    return static_cast<EspGenWork*>(re4dc_effect_record_read(ref,&scratch));
}
