#include "motion_checks.hpp"

#include "re4_host_stub.h"

#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace {

Global global_state = {{0, 0, 0, 0}, 1.0f};
Log game_log;

void write_u16(u8* destination, u16 value) {
    std::memcpy(destination, &value, sizeof(value));
}

void write_f32(u8* destination, f32 value) {
    std::memcpy(destination, &value, sizeof(value));
}

void write_axis(u8* destination, f32 first, f32 second) {
    write_u16(destination, 2);
    write_u16(destination + 2, 0);
    write_u16(destination + 4, 10);
    write_f32(destination + 6, first);
    write_f32(destination + 10, second);
}

bool near(f32 value, f32 expected, f32 tolerance = 0.0005f) {
    return isfinite(value) && fabsf(value - expected) <= tolerance;
}

} // namespace

Global* pG = &global_state;
cModel* pPL = nullptr;
Log* pLog = &game_log;
CamCtrlStub CamCtrl;
SatMgrStub SatMgr;
extern const Vec vecZero = {0.0f, 0.0f, 0.0f};

void Log::err(int, int, const char* format, ...) {
    std::fputs("[game log] ", stderr);
    va_list arguments;
    va_start(arguments, format);
    std::vfprintf(stderr, format, arguments);
    va_end(arguments);
    std::fputc('\n', stderr);
}

void CamCtrlStub::registAttachCamera(AttachCamera*, cModel*) {}
void CamCtrlStub::deleteAttachCamera(AttachCamera*, cModel*) {}

f32 SatMgrStub::getFloor(Vec*, f32, f32, u32*, int) {
    return -100000.0f;
}

extern "C" void OSReport(const char* format, ...) {
    va_list arguments;
    va_start(arguments, format);
    std::vfprintf(stderr, format, arguments);
    va_end(arguments);
}

extern "C" void eprintf(int, int, int, int, const char*, ...) {}

extern "C" void memclr_asm(void* destination, u32 bytes) {
    std::memset(destination, 0, bytes);
}

extern "C" void cModel_matBlend(cModel* model, f32 rate) {
    model->matBlend(rate);
}

f32 SQRTF(f32 value) {
    return value <= 0.00001f ? 0.0f : sqrtf(value);
}

f32 LIMIT_ANGLE(f32 value) {
    while(value >= PI) {
        value -= PI2;
    }
    while(value < -PI) {
        value += PI2;
    }
    return value;
}

MotionCheckResult run_motion_checks() {
    MotionCheckResult result{};

    alignas(4) u8 keys[42]{};
    write_axis(keys, 1.0f, 2.0f);
    write_axis(keys + 14, -3.0f, 4.0f);
    write_axis(keys + 28, 6.0f, 8.0f);
    HermitePrm parameters{};
    parameters.frame = 10.0f;
    parameters.maxFrame = 20.0f;
    parameters.type = 15;
    parameters.key = keys;
    u16 history[3]{};
    Vec interpolated{};
    const int hermite_status = HermiteInterpolation(&parameters, &interpolated, history);
    result.hermite[0] = interpolated.x;
    result.hermite[1] = interpolated.y;
    result.hermite[2] = interpolated.z;
    if(hermite_status != 0 || !near(interpolated.x, 2.0f) ||
       !near(interpolated.y, 4.0f) || !near(interpolated.z, 8.0f)) {
        ++result.failures;
    }

    cModel root{};
    cModel joint{};
    cModel effector{};
    PSMTXIdentity(root.mat);
    PSMTXIdentity(root.ik.mat);
    PSMTXIdentity(joint.mat);
    PSMTXIdentity(joint.ik.mat);
    root.world = {0.0f, 0.0f, 0.0f};
    root.ik.axis = {0.0f, 0.0f, 1.0f};
    root.ik.len = 5.0f;
    joint.pParent = &root;
    joint.pos = {5.0f, 0.0f, 0.0f};
    joint.ik.len = 4.0f;
    effector.world = {6.0f, 2.0f, 0.0f};
    ikCalc(&root, &joint, &effector);
    result.ik_joint[0] = joint.world.x;
    result.ik_joint[1] = joint.world.y;
    result.ik_joint[2] = joint.world.z;
    result.ik_joint_distance = GetDistance3(&root.world, &joint.world);
    if(!near(result.ik_joint_distance, 5.0f, 0.002f) ||
       !isfinite(joint.world.x) || !isfinite(joint.world.y) ||
       !isfinite(joint.world.z)) {
        ++result.failures;
    }

    return result;
}
