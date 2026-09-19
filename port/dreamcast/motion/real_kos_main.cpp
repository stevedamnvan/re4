#include <kos.h>

#include <cstdint>
#include <cstdio>

#include "real_motion_checks.hpp"

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

void render_status(const pvr_poly_hdr_t& header, bool passed) {
    const std::uint32_t color = passed ? 0xff25c26e : 0xffdc3545;
    const pvr_vertex_t vertices[] = {
        {PVR_CMD_VERTEX, 44.0f, 38.0f, 1.0f, 0.0f, 0.0f, color, 0},
        {PVR_CMD_VERTEX, 44.0f, 202.0f, 1.0f, 0.0f, 0.0f, color, 0},
        {PVR_CMD_VERTEX, 276.0f, 38.0f, 1.0f, 0.0f, 0.0f, color, 0},
        {PVR_CMD_VERTEX_EOL, 276.0f, 202.0f, 1.0f, 0.0f, 0.0f, color, 0},
    };
    pvr_wait_ready();
    pvr_scene_begin();
    pvr_list_begin(PVR_LIST_OP_POLY);
    pvr_prim(&header, sizeof(header));
    for(const pvr_vertex_t& vertex : vertices) {
        pvr_prim(&vertex, sizeof(vertex));
    }
    pvr_list_finish();
    pvr_scene_finish();
}

} // namespace

int main() {
    const RealMotionCheckResult result = run_real_motion_checks();
    const bool passed = result.failures == 0;
    std::printf(
        "re4dc-real-motion: failures=%d parts=%d joints=%d samples=%d max_frame=%.1f\n"
        "re4dc-real-motion: root_err=%.7f angle_err=%.7f world_err=%.7f\n",
        result.failures, result.part_count, result.joint_count, result.frames_tested,
        result.max_frame, result.max_root_error, result.max_angle_error,
        result.max_world_error);
    std::printf("re4dc-real-motion: %s; press START to exit\n", passed ? "PASS" : "FAIL");

    vid_set_mode(DM_320x240, PM_RGB565);
    pvr_init_defaults();
    pvr_set_bg_color(0.035f, 0.045f, 0.065f);
    pvr_poly_cxt_t context{};
    pvr_poly_hdr_t header{};
    pvr_poly_cxt_col(&context, PVR_LIST_OP_POLY);
    context.gen.culling = PVR_CULLING_NONE;
    pvr_poly_compile(&header, &context);
    for(std::uint32_t frame = 0; !start_pressed(); ++frame) {
        render_status(header, passed);
        if(frame != 0 && frame % 300 == 0) {
            std::printf("re4dc-real-motion: frame=%lu status=%s\n",
                        static_cast<unsigned long>(frame), passed ? "PASS" : "FAIL");
        }
    }
    return passed ? 0 : 1;
}
