#ifndef RE4DC_RESIDENT_BOUNDS_HPP
#define RE4DC_RESIDENT_BOUNDS_HPP
#include "re4dc_platform.h"
// The original request owns a fixed region even when a later part begins at
// its end. Checking only the current destination would misclassify that part
// as belonging to the next region. Sizes here are unrounded transfer bytes;
// the source queue separately advances each part by ALIGN32(size).
static inline bool re4dc_resident_read_fits(unsigned long request,
    unsigned long destination, unsigned long bytes, bool shared_player,
    const char** owner, unsigned long* capacity)
{
    const unsigned long starts[4]={re4dc_mem.core,re4dc_mem.option,re4dc_mem.player,re4dc_mem.weapon};
    const unsigned long ends[4]={re4dc_mem.option,re4dc_mem.player,
        shared_player?re4dc_mem.heap:re4dc_mem.weapon,re4dc_mem.heap};
    static const char* names[4]={"core","option","player","weapon"};
    for(unsigned i=0;i<4;++i) {
        // Use physical start boundaries for owner classification; shared player
        // mode may legitimately use the adjacent weapon region, as in source.
        unsigned long physical_end=i==3?re4dc_mem.heap:starts[i+1];
        if(request>=starts[i] && request<physical_end) {
            *owner=names[i];*capacity=ends[i]-request;
            return destination>=request && destination<=ends[i] && bytes<=ends[i]-destination;
        }
    }
    *owner=0;*capacity=0;return true; // heap/sound allocations keep existing owners
}
#endif
