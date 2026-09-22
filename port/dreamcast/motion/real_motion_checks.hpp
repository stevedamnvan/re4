#pragma once

struct RealMotionCheckResult {
    int failures;
    int part_count;
    int joint_count;
    int frames_tested;
    float max_frame;
    float max_root_error;
    float max_angle_error;
    float max_world_error;
};

RealMotionCheckResult run_real_motion_checks(void* motion_override = nullptr,
    void (*after_evaluation)(void*) = nullptr);
