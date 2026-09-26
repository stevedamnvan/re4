// COARSE_WORLD (coarse.cpp <-> coarse_world.cpp): the view of a coarse image as coarse.cpp's
// setup_camera() computes it, for the world passes that draw beyond the collision pieces.
#pragma once
#include <cstdint>

struct CoarseView {
    float S[3][4];              // screen rows: X' Y' W' of a world point (screen = X'/W', Y'/W'; depth 1/W')
    float eye[3];               // eye (world mm)
    float dir[2];               // horizontal view direction (x, z)
    float n0[2], n1[2];         // inward side-plane normals (x, z) through the eye
    float focal;                // pixels per unit x at W' = 1
    float far;                  // cull distance: the fog's far plane (FOG_FAR), all fog beyond it
    float det;                  // det of S's 3x3: a front face's screen area has the opposite sign
    float fog_rgb[3];           // the fog table's colour (0..255), for the sky's horizon
};

extern "C" {
// Draws the world objects (house shells, sky) with their own texture headers; the caller has closed
// its header before and opens a new one after, and calls it only in the data's room (coarse_world.h
// kRoom, piece 0 with kPolys polygons). Returns the TA vertices written.
unsigned re4dc_coarse_world_draw(const CoarseView* view);
// A per-120-image stats line (called with coarse.cpp's).
void re4dc_coarse_world_log(unsigned images);
}
