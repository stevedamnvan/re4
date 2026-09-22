#pragma once
// Resident, lossless EST adapter. A tagged record reference is opaque and may
// outlive a call, but never its source archive. Only record_read may dereference
// it. Ordinary archives and retained/unqualified record kinds remain ordinary.
#include <stdint.h>
struct Re4dcEffectStats { unsigned sequences, records, reads, raw_reads, failures; uint64_t worst_decode_us; };
extern "C" {
int re4dc_effect_bind(void* archive, unsigned bytes);
void re4dc_effect_unbind(void* archive);
void* re4dc_effect_record_ref(void* head, unsigned index);
void* re4dc_effect_record_read(void* reference, void* scratch300);
void re4dc_effect_get_stats(Re4dcEffectStats* out);
}
