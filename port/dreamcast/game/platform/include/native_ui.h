#pragma once
// Narrow source-ID adapter, not a GX command interpreter.
struct Re4dcUiImage {
    const void* pixels;
    const void* palette;
    unsigned width, height, format, palette_format, palette_bytes;
};
struct Re4dcUiQuad {
    Re4dcUiImage image;
    float xy[8], uv[8];
    unsigned color, blend, masked;
};
extern "C" {
void re4dc_ui_init();
void re4dc_ui_begin();
void re4dc_ui_present();
// Always called at source Render_swap, including a held picture.
void re4dc_ui_end_frame(int present);
void re4dc_ui_submit(const Re4dcUiQuad*);
void re4dc_ui_invalidate_sources();
int re4dc_ui_bind_core(void*,unsigned);
int re4dc_ui_bind_option(void*,unsigned);
void re4dc_ui_unbind_option();
int re4dc_ui_bind_room(void*,unsigned);
void re4dc_ui_retire_room();
int re4dc_ui_bind_player(void*,unsigned);
int re4dc_ui_bind_weapon(void*,unsigned);
void re4dc_ui_unbind_player();
void re4dc_ui_unbind_weapon();
int re4dc_ui_bind_enemy(void*,unsigned);
void re4dc_ui_unbind_enemy(void*);
void* re4dc_ui_stage_alloc(unsigned bytes);
void re4dc_ui_stage_free(void* data);
int re4dc_ui_heap_free();
}
