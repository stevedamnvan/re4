#include "real_motion_checks.hpp"

#include <cstdio>

int main() {
    const RealMotionCheckResult result = run_real_motion_checks();
    std::printf(
        "{\"failures\":%d,\"parts\":%d,\"joints\":%d,\"frames_tested\":%d,"
        "\"max_frame\":%.9g,\"max_root_error\":%.9g,"
        "\"max_angle_error\":%.9g,\"max_world_error\":%.9g}\n",
        result.failures,
        result.part_count,
        result.joint_count,
        result.frames_tested,
        result.max_frame,
        result.max_root_error,
        result.max_angle_error,
        result.max_world_error);
    return result.failures == 0 ? 0 : 1;
}
