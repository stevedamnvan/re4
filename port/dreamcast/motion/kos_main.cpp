#include <kos.h>

#include <cstdint>
#include <cstdio>

#include "motion_checks.hpp"

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
        {PVR_CMD_VERTEX, 64.0f, 48.0f, 1.0f, 0.0f, 0.0f, color, 0},
        {PVR_CMD_VERTEX, 64.0f, 192.0f, 1.0f, 0.0f, 0.0f, color, 0},
        {PVR_CMD_VERTEX, 256.0f, 48.0f, 1.0f, 0.0f, 0.0f, color, 0},
        {PVR_CMD_VERTEX_EOL, 256.0f, 192.0f, 1.0f, 0.0f, 0.0f, color, 0},
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
    const MotionCheckResult result = run_motion_checks();
    const bool passed = result.failures == 0;
    std::printf(
        "re4dc-motion: failures=%d hermite=%.6f,%.6f,%.6f "
        "ik_joint=%.6f,%.6f,%.6f ik_distance=%.6f\n",
        result.failures,
        result.hermite[0], result.hermite[1], result.hermite[2],
        result.ik_joint[0], result.ik_joint[1], result.ik_joint[2],
        result.ik_joint_distance);
    std::printf("re4dc-motion: %s; press START to exit\n", passed ? "PASS" : "FAIL");

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
            std::printf("re4dc-motion: frame=%lu status=%s\n",
                        static_cast<unsigned long>(frame), passed ? "PASS" : "FAIL");
        }
    }
    return passed ? 0 : 1;
}
