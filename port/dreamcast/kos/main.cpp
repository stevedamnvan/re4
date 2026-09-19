#include <kos.h>

#include <cstdint>
#include <cstdio>

#include "re4dc/abi.hpp"

KOS_INIT_FLAGS(INIT_DEFAULT);

namespace {

bool start_pressed() {
    maple_device_t* controller = maple_enum_type(0, MAPLE_FUNC_CONTROLLER);
    if(controller == nullptr) {
        return false;
    }
    auto* state = static_cast<cont_state_t*>(maple_dev_status(controller));
    return state != nullptr && (state->buttons & CONT_START) != 0;
}

void submit_vertex(float x, float y, float z, std::uint32_t color, bool last) {
    const pvr_vertex_t vertex = {
        .flags = last ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
        .x = x,
        .y = y,
        .z = z,
        .u = 0.0f,
        .v = 0.0f,
        .argb = color,
        .oargb = 0,
    };
    pvr_prim(&vertex, sizeof(vertex));
}

void render_frame(const pvr_poly_hdr_t& header, std::uint32_t frame) {
    const float offset = static_cast<float>((frame / 2) % 120);
    pvr_wait_ready();
    pvr_scene_begin();
    pvr_list_begin(PVR_LIST_OP_POLY);
    pvr_prim(&header, sizeof(header));
    submit_vertex(40.0f + offset, 40.0f, 1.0f, 0xffffc44d, false);
    submit_vertex(20.0f + offset, 160.0f, 1.0f, 0xff2b72d6, false);
    submit_vertex(140.0f + offset, 160.0f, 1.0f, 0xffda3b46, true);
    pvr_list_finish();
    pvr_scene_finish();
}

} // namespace

int main() {
    static_assert(sizeof(re4dc::u32) == 4);
    static_assert(re4dc::kNativeLittleEndian);

    vid_set_mode(DM_320x240, PM_RGB565);
    pvr_init_defaults();
    pvr_set_bg_color(0.035f, 0.045f, 0.065f);

    pvr_poly_cxt_t context{};
    pvr_poly_hdr_t header{};
    pvr_poly_cxt_col(&context, PVR_LIST_OP_POLY);
    context.gen.culling = PVR_CULLING_NONE;
    pvr_poly_compile(&header, &context);

    std::printf("re4dc: smoke boot; 320x240 RGB565; press START to exit\n");
    for(std::uint32_t frame = 0; !start_pressed(); ++frame) {
        render_frame(header, frame);
        if(frame != 0 && frame % 300 == 0) {
            std::printf("re4dc: frame=%lu\n", static_cast<unsigned long>(frame));
        }
    }
    std::printf("re4dc: clean exit\n");
    return 0;
}
