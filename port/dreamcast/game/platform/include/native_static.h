#pragma once
// Recovered scroll objects -> D349 native static room packages (.re4room v4).
//
// Source authority is unchanged: setObj binds each placed object by its SMD
// owner/work/BIN/common identity, and the object's own draw (every source
// visibility gate, the current part material, blend, cull and alpha) decides
// when a native batch is drawn. A bound part draws the package batches with
// its (texId, alphaTex) key instead of decoding its GX display list. There is
// no second object registry: each package source slot records the one live
// object bound to it, checked against that object's creation serial.
struct Re4dcModelPart;
struct Re4dcStaticStats {
    unsigned owners_open, open_failures, alloc_rejects, package_bytes;
    unsigned binds, bind_misses, bind_conflicts, stale_bindings;
    unsigned parts_native, parts_skipped, parts_fallback, key_misses;
    unsigned groups_visible, groups_culled, batches, strips, strips_culled;
    unsigned strips_clipped, triangles_clipped, vertices, moved_objects;
    unsigned vertex_alpha, reserve_rejects, bind_rejects, aborts;
    unsigned vertex_opaque, vertex_alpha_min, vertex_alpha_unused;
    int heap_before, heap_after;
    unsigned unowned_binds, locate_misses, parts_lit;
};
extern "C" {
// Called by scroll.cpp setObj after the object's placement matrix is final.
// room is (stage_no << 8) | room_no; block is -1 for the main scenario.
void re4dc_static_bind(const void* object, unsigned room, int block,
                       unsigned work, unsigned bin, unsigned common,
                       unsigned serial, const float world[12]);
// Block/room retirement: the source destroyed every object of this owner.
void re4dc_static_retire_owner(int block);
void re4dc_static_retire_all();
// Returns one when the part was drawn, queued or deliberately skipped
// natively; zero leaves it to the generic ModelPart path.
int re4dc_static_submit(const Re4dcModelPart*);
const Re4dcStaticStats* re4dc_static_stats();
// Existing frame owner's frame number (native_ui.cpp).
unsigned re4dc_ui_frame();
// Guarded heap-4 storage, same reserve policy as retained preparation.
void* re4dc_static_alloc(unsigned bytes);
void re4dc_static_free(void*);
int re4dc_static_heap_free();
}
