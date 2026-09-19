#pragma once

struct MotionCheckResult {
    int failures;
    float hermite[3];
    float ik_joint[3];
    float ik_joint_distance;
};

MotionCheckResult run_motion_checks();
