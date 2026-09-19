#include "motion_checks.hpp"

#include <cstdio>

int main() {
    const MotionCheckResult result = run_motion_checks();
    std::printf(
        "{\"failures\":%d,\"hermite\":[%.9g,%.9g,%.9g],"
        "\"ik_joint\":[%.9g,%.9g,%.9g],\"ik_joint_distance\":%.9g}\n",
        result.failures,
        result.hermite[0], result.hermite[1], result.hermite[2],
        result.ik_joint[0], result.ik_joint[1], result.ik_joint[2],
        result.ik_joint_distance);
    return result.failures == 0 ? 0 : 1;
}
