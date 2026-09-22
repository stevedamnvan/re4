#include "real_motion_checks.hpp"

#include "re4_host_stub.h"
#include "re4dc_real_motion_fixture.hpp"

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>

#if defined(__linux__) && defined(__x86_64__)
#include <sys/mman.h>
#endif

namespace {

using namespace re4dc_real_fixture;

struct FixtureModel {
    cEm model;
    cEm* parts;
    u8* image;
    bool image_is_mapped;
};

void coord_init(cCoord* coordinate) {
    std::memset(coordinate, 0, sizeof(*coordinate));
    PSMTXIdentity(coordinate->mat);
    PSMTXIdentity(coordinate->l_mat);
    coordinate->scale = {1.0f, 1.0f, 1.0f};
    coordinate->r_scale = {1.0f, 1.0f, 1.0f};
}

u8* allocate_motion_image(std::size_t bytes, bool* mapped) {
    *mapped = false;
#if defined(__linux__) && defined(__x86_64__)
    void* mapped_memory = mmap(nullptr, bytes, PROT_READ | PROT_WRITE,
                               MAP_PRIVATE | MAP_ANONYMOUS | MAP_32BIT, -1, 0);
    if(mapped_memory != MAP_FAILED) {
        *mapped = true;
        return static_cast<u8*>(mapped_memory);
    }
#endif
    u8* heap_memory = static_cast<u8*>(std::malloc(bytes));
    if(reinterpret_cast<std::uintptr_t>(heap_memory) > UINT32_MAX) {
        std::free(heap_memory);
        return nullptr;
    }
    return heap_memory;
}

void release_motion_image(u8* image, std::size_t bytes, bool mapped) {
    if(image == nullptr) {
        return;
    }
#if defined(__linux__) && defined(__x86_64__)
    if(mapped) {
        munmap(image, bytes);
        return;
    }
#else
    (void) bytes;
    (void) mapped;
#endif
    std::free(image);
}

bool create_fixture_model(FixtureModel* fixture) {
    std::memset(fixture, 0, sizeof(*fixture));
    fixture->parts = static_cast<cEm*>(std::calloc(kPartCount, sizeof(cEm)));
    fixture->image = allocate_motion_image(sizeof(kMotionImage), &fixture->image_is_mapped);
    if(fixture->parts == nullptr || fixture->image == nullptr) {
        release_motion_image(fixture->image, sizeof(kMotionImage), fixture->image_is_mapped);
        std::free(fixture->parts);
        fixture->image = nullptr;
        fixture->parts = nullptr;
        return false;
    }
    std::memcpy(fixture->image, kMotionImage, sizeof(kMotionImage));

    cEm* model = &fixture->model;
    coord_init(model);
    model->nParts = static_cast<u8>(kPartCount);
    model->pParts = &fixture->parts[0];
    model->Motion.Seq_speed = 1.0f;
    for(int i = 0; i < kPartCount; ++i) {
        cEm* part = &fixture->parts[i];
        coord_init(part);
        part->pParts = i + 1 < kPartCount ? &fixture->parts[i + 1] : nullptr;
        part->pParent = kParents[i] < 0
            ? static_cast<cCoord*>(model)
            : static_cast<cCoord*>(&fixture->parts[kParents[i]]);
        part->pos = {
            kRestPosition[3 * i],
            kRestPosition[3 * i + 1],
            kRestPosition[3 * i + 2],
        };
    }

    model->partsMatCalc();
    model->partsWorldCalc();
    for(int i = 0; i < kPartCount; ++i) {
        cEm* part = &fixture->parts[i];
        PSMTXIdentity(part->ik.bindMat);
        part->ik.bindMat[0][3] = -part->mat[0][3];
        part->ik.bindMat[1][3] = -part->mat[1][3];
        part->ik.bindMat[2][3] = -part->mat[2][3];
    }
    model->partsMatCalc();
    model->partsWorldCalc();
    for(int i = 0; i < kPartCount; ++i) {
        fixture->parts[i].world_old = fixture->parts[i].world;
        fixture->parts[i].world_old2 = fixture->parts[i].world;
    }
    model->Motion.blendTbl = const_cast<u16*>(kBlendWords);
    return true;
}

void destroy_fixture_model(FixtureModel* fixture) {
    release_motion_image(fixture->image, sizeof(kMotionImage), fixture->image_is_mapped);
    std::free(fixture->parts);
}

void update_max_error(float actual, float expected, float* maximum, bool* finite) {
    if(!std::isfinite(actual)) {
        *finite = false;
        return;
    }
    const float error = std::fabs(actual - expected);
    if(error > *maximum) {
        *maximum = error;
    }
}

} // namespace

RealMotionCheckResult run_real_motion_checks(void* motion_override, void (*after_evaluation)(void*)) {
    RealMotionCheckResult result{};
    result.part_count = kPartCount;
    result.frames_tested = kSampleCount;

    FixtureModel fixture{};
    if(!create_fixture_model(&fixture)) {
        result.failures = 1;
        return result;
    }

    cEm* model = &fixture.model;
    model->Motion.Mot_flag = 0;
    MotionSetCore(model, &model->Motion, motion_override ? motion_override : fixture.image, 0, 0, 0, 0);
    if(after_evaluation) after_evaluation(model);
    result.joint_count = model->Motion.Joint_num;
    result.max_frame = model->Motion.Mot_frame_max;
    if(result.joint_count != kJointCount ||
       std::fabs(result.max_frame - kMaxFrame) > 0.0001f) {
        ++result.failures;
    }

    bool finite = true;
    for(int sample = 0; sample < kSampleCount; ++sample) {
        model->Motion.Mot_attr |= 0x8000;
        model->Motion.Mot_attr &= ~1u;
        model->Motion.Seq_frame = kSampleFrames[sample];
        MotionMove(model);
        if(after_evaluation) after_evaluation(model);

        Vec root_position{};
        Vec root_rotation{};
        MotionGetPosition(model, &root_position, &root_rotation);
        if(after_evaluation) after_evaluation(model);
        const float* root_pos = &root_position.x;
        const float* root_rot = &root_rotation.x;
        for(int axis = 0; axis < 3; ++axis) {
            update_max_error(root_pos[axis], kExpectedRootPosition[3 * sample + axis],
                             &result.max_root_error, &finite);
            update_max_error(root_rot[axis], kExpectedRootRotation[3 * sample + axis],
                             &result.max_root_error, &finite);
        }

        for(int part_no = 0; part_no < kPartCount; ++part_no) {
            const cEm* part = &fixture.parts[part_no];
            const float* angle = &part->ang.x;
            const float* world = &part->world.x;
            const int base = (sample * kPartCount + part_no) * 3;
            for(int axis = 0; axis < 3; ++axis) {
                update_max_error(angle[axis], kExpectedAngles[base + axis],
                                 &result.max_angle_error, &finite);
                update_max_error(world[axis], kExpectedWorld[base + axis],
                                 &result.max_world_error, &finite);
            }
        }
    }

    if(!finite || result.max_root_error > 0.001f ||
       result.max_angle_error > 0.0002f || result.max_world_error > 0.05f) {
        ++result.failures;
    }
    destroy_fixture_model(&fixture);
    return result;
}
