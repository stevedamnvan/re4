// ACTOR_SWAP=1 (benchmark only, version A; game30.mk): the old renderer draws Leon and the Ganados
// with the same reduced meshes as the coarse view (the COARSE_LEON / COARSE_GANADO adapters and
// their native actor submission) instead of their source infos, so the two renderers can be timed
// with the same character models. ModelRender (trans.cpp) asks here for every model OT entry: a
// model the adapters accept is drawn once per frame and both of its OT passes skip the source
// draw; a model they decline draws its source infos on both passes as before. Presentation only:
// no game state is written.
#include "global.h"
#include "player.h"
#include "model.h"
#include "camera.h"

extern "C" int re4dc_coarse_leon(cModel*);
extern "C" int re4dc_coarse_ganado(cModel*);
extern "C" void re4dc_coarse_ganado_begin();
extern "C" void re4dc_coarse_ganado_end();
extern "C" void re4dc_log(const char*, ...);

namespace {
struct Seen {
    cModel* model;
    int handled;
};
unsigned frame = ~0U;
bool frame_open;
Seen seen[64];
unsigned seen_count;
unsigned swapped_leon, swapped_ganado, declined, frames;
}

extern "C" int re4dc_actor_swap(cModel* m)
{
    const bool leon = m == (cModel*) pPL;
    const bool ganado = !leon && m->id >= 0x10 && m->id <= 0x20;
    if (!leon && !ganado) {
        return 0;
    }
    if (frame != pG->Frame_cnt) {
        if (frame_open) {
            re4dc_coarse_ganado_end();
        }
        if (frames % 120 == 0) {
            re4dc_log("ACTOR_SWAP t=%u frames=%u leon=%u ganado=%u declined=%u\n", (unsigned) pG->Frame_cnt, frames,
                      swapped_leon, swapped_ganado, declined);
        }
        ++frames;
        frame = pG->Frame_cnt;
        seen_count = 0;
        re4dc_coarse_ganado_begin();
        frame_open = true;
    }
    // The model's second OT pass (commonModelTrans' bit 0x40 group) repeats the first answer.
    for (unsigned i = 0; i < seen_count; ++i) {
        if (seen[i].model == m) {
            return seen[i].handled;
        }
    }
    CameraCurrentProjection();   // the adapters read the projection and viewport from GX
    const int handled = leon ? re4dc_coarse_leon(m) : re4dc_coarse_ganado(m);
    if (handled) {
        ++(leon ? swapped_leon : swapped_ganado);
    } else {
        ++declined;
    }
    if (seen_count < 64) {
        seen[seen_count++] = Seen{m, handled};
    }
    return handled;
}
