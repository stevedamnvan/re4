// Private object from the unchanged pinned KOS source, never a shared SDK write.
// KOS BSD-like license/provenance remains in the included SDK source.
// -Os selects KOS's supported cache-purge implementation without16KiB scratch.
#if RE4DC_ROUTE_MOVIES
#include <stdlib.h>
#include <malloc.h>
#include <stdint.h>
// The stereo separation buffer (snd_stream_init_ex) is the service's only heap
// use. It is staged from the current source heap like the rest of the player,
// because the in-room KOS heap has under 4 KiB free; it is returned on
// snd_stream_shutdown. The filter path (malloc/free of filter_t) is unused.
void* re4dc_ui_stage_alloc(unsigned bytes);
void re4dc_ui_stage_free(void* data);
static void* movie_sep_raw;
static void* movie_sep;
unsigned re4dc_movie_stream_staged;
static void* re4dc_movie_sep_alloc(size_t alignment, size_t bytes) {
    if(movie_sep || alignment > 32) return NULL;
    movie_sep_raw = re4dc_ui_stage_alloc((unsigned)(bytes + 32));
    if(!movie_sep_raw) return NULL;
    re4dc_movie_stream_staged = (unsigned)(bytes + 32);
    movie_sep = (void*)(((uintptr_t)movie_sep_raw + 31) & ~(uintptr_t)31);
    return movie_sep;
}
static void re4dc_movie_sep_free(void* p) {
    if(p && p == movie_sep) {
        re4dc_ui_stage_free(movie_sep_raw);
        movie_sep = movie_sep_raw = NULL;
        re4dc_movie_stream_staged = 0;
        return;
    }
    free(p);
}
#define aligned_alloc(a, n) re4dc_movie_sep_alloc((a), (n))
#define free(p) re4dc_movie_sep_free(p)
#include "snd_stream.c"
#undef free
#undef aligned_alloc
int re4dc_movie_stream_initialized(void) { return max_channels != 0; }
unsigned re4dc_movie_stream_active(void) {
    unsigned n=0;
    for(unsigned i=0;i<SND_STREAM_MAX;++i) if(streams[i].initted) ++n;
    return n;
}
#endif
