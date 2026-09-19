#include <kos.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <new>

#include "room_package.hpp"

KOS_INIT_FLAGS(INIT_DEFAULT);

namespace {

constexpr float kPi = 3.14159265358979323846f;

struct Camera {
    float yaw = kPi;
    float pitch = 0.28f;
    float distance = 140.0f;
};

struct FrameStats {
    std::uint32_t groups = 0;
    std::uint32_t triangles = 0;
    std::uint32_t transformed_vertices = 0;
};

struct ProjectedVertex {
    float x;
    float y;
    float z;
};

std::uint32_t material_color(std::uint32_t material, float light) {
    const std::uint32_t value = material * 0x9e3779b9U + 0x7f4a7c15U;
    const float red = static_cast<float>(80U + (value & 0x7fU)) * light;
    const float green = static_cast<float>(80U + ((value >> 8U) & 0x7fU)) * light;
    const float blue = static_cast<float>(80U + ((value >> 16U) & 0x7fU)) * light;
    const auto clamp = [](float channel) {
        return static_cast<std::uint32_t>(std::clamp(channel, 0.0f, 255.0f));
    };
    return 0xff000000U | (clamp(red) << 16U) | (clamp(green) << 8U) |
           clamp(blue);
}

bool update_camera(Camera& camera) {
    maple_device_t* controller = maple_enum_type(0, MAPLE_FUNC_CONTROLLER);
    if(controller == nullptr) {
        return false;
    }
    const auto* state = static_cast<const cont_state_t*>(maple_dev_status(controller));
    if(state == nullptr) {
        return false;
    }
    camera.yaw += static_cast<float>(state->joyx) * 0.0007f;
    camera.pitch -= static_cast<float>(state->joyy) * 0.00035f;
    camera.pitch = std::clamp(camera.pitch, -0.35f, 0.9f);
    camera.distance +=
        static_cast<float>(static_cast<int>(state->ltrig) - state->rtrig) * 0.12f;
    camera.distance = std::clamp(camera.distance, 160.0f, 900.0f);
    return (state->buttons & CONT_START) != 0;
}

bool group_visible(const re4dc::room::Group& group) {
    bool behind = true;
    bool beyond_far = true;
    bool left = true;
    bool right = true;
    bool above = true;
    bool below = true;
    for(unsigned corner = 0; corner < 8; ++corner) {
        float x = group.bounds_min[0];
        float y = group.bounds_min[1];
        float z = group.bounds_min[2];
        if((corner & 1U) != 0) {
            x = group.bounds_max[0];
        }
        if((corner & 2U) != 0) {
            y = group.bounds_max[1];
        }
        if((corner & 4U) != 0) {
            z = group.bounds_max[2];
        }
        mat_trans_single(x, y, z);
        if(z <= 0.0f) {
            continue;
        }
        behind = false;
        beyond_far &= z < (1.0f / 240.0f);
        left &= x < 0.0f;
        right &= x > 320.0f;
        above &= y < 0.0f;
        below &= y > 240.0f;
    }
    return !(behind || beyond_far || left || right || above || below);
}

bool transform_triangle(const re4dc::room::Vertex* source,
                        const std::uint32_t* indices, pvr_vertex_t* output,
                        std::uint32_t material, ProjectedVertex* projected,
                        std::uint32_t* transformed_at, std::uint32_t frame_token,
                        FrameStats& stats) {
    bool left = true;
    bool right = true;
    bool above = true;
    bool below = true;
    bool beyond_far = true;
    for(unsigned corner = 0; corner < 3; ++corner) {
        const std::uint32_t vertex_index = indices[corner];
        const re4dc::room::Vertex& input = source[vertex_index];
        if(transformed_at[vertex_index] != frame_token) {
            float x = input.x;
            float y = input.y;
            float z = input.z;
            mat_trans_single(x, y, z);
            projected[vertex_index] = {x, y, z};
            transformed_at[vertex_index] = frame_token;
            ++stats.transformed_vertices;
        }
        const float x = projected[vertex_index].x;
        const float y = projected[vertex_index].y;
        const float z = projected[vertex_index].z;
        if(z <= 0.0f) {
            return false;
        }
        beyond_far &= z < (1.0f / 240.0f);
        left &= x < 0.0f;
        right &= x > 320.0f;
        above &= y < 0.0f;
        below &= y > 240.0f;
        const float light = std::clamp(
            0.48f + 0.18f * input.nx + 0.28f * input.ny + 0.12f * input.nz,
            0.25f, 1.0f);
        output[corner] = {
            .flags = corner == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
            .x = x,
            .y = y,
            .z = z,
            .u = input.u,
            .v = input.v,
            .argb = material_color(material, light),
            .oargb = 0,
        };
    }
    const float signed_area =
        (output[1].x - output[0].x) * (output[2].y - output[0].y) -
        (output[1].y - output[0].y) * (output[2].x - output[0].x);
    if(signed_area >= 0.0f) {
        return false;
    }
    return !(beyond_far || left || right || above || below);
}

FrameStats render_room(const re4dc::room::Package& room,
                       const pvr_poly_hdr_t& polygon_header,
                       ProjectedVertex* projected, std::uint32_t* transformed_at,
                       std::uint32_t frame_token) {
    FrameStats stats{};
    const auto* groups = room.groups();
    const auto* batches = room.batches();
    const auto* vertices = room.vertices();
    const auto* indices = room.indices();

    pvr_wait_ready();
    pvr_scene_begin();
    pvr_list_begin(PVR_LIST_OP_POLY);
    pvr_prim(&polygon_header, sizeof(polygon_header));
    for(std::uint32_t group_index = 0; group_index < room.header().group_count;
        ++group_index) {
        const auto& group = groups[group_index];
        if(!group_visible(group)) {
            continue;
        }
        ++stats.groups;
        for(std::uint32_t local_batch = 0; local_batch < group.batch_count;
            ++local_batch) {
            const auto& batch = batches[group.first_batch + local_batch];
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; index += 3) {
                pvr_vertex_t triangle[3];
                if(transform_triangle(vertices, indices + index, triangle,
                                      batch.material, projected, transformed_at,
                                      frame_token, stats)) {
                    for(const auto& vertex : triangle) {
                        auto* target = static_cast<pvr_vertex_t*>(pvr_dr_target());
                        *target = vertex;
                        pvr_dr_commit(target);
                    }
                    ++stats.triangles;
                }
            }
        }
    }
    pvr_list_finish();
    pvr_scene_finish();
    return stats;
}

} // namespace

int main() {
    re4dc::room::Package room;
    if(!room.open("/rd/r10d.re4room")) {
        std::printf("re4dc-room: load failed: %s\n", room.error());
        return 1;
    }
    std::printf(
        "re4dc-room: loaded vertices=%lu triangles=%lu groups=%lu batches=%lu\n",
        static_cast<unsigned long>(room.header().vertex_count),
        static_cast<unsigned long>(room.header().index_count / 3U),
        static_cast<unsigned long>(room.header().group_count),
        static_cast<unsigned long>(room.header().batch_count));

    vid_set_mode(DM_320x240, PM_RGB565);
    pvr_init_defaults();
    pvr_set_bg_color(0.055f, 0.07f, 0.09f);
    pvr_poly_cxt_t context{};
    pvr_poly_hdr_t polygon_header{};
    pvr_poly_cxt_col(&context, PVR_LIST_OP_POLY);
    context.gen.culling = PVR_CULLING_NONE;
    pvr_poly_compile(&polygon_header, &context);

    const point_t center = {
        0.0f,
        10.0f,
        -180.0f,
        1.0f,
    };
    const vector_t up = {0.0f, 1.0f, 0.0f, 0.0f};
    Camera camera{};
    std::uint32_t frame = 0;
    std::unique_ptr<ProjectedVertex[]> projected(
        new(std::nothrow) ProjectedVertex[room.header().vertex_count]);
    std::unique_ptr<std::uint32_t[]> transformed_at(
        new(std::nothrow) std::uint32_t[room.header().vertex_count]());
    if(projected == nullptr || transformed_at == nullptr) {
        std::printf("re4dc-room: transform cache allocation failed\n");
        return 1;
    }
    std::printf("re4dc-room: stick=orbit triggers=zoom START=exit\n");
    while(!update_camera(camera)) {
        const float horizontal = std::cos(camera.pitch) * camera.distance;
        const point_t eye = {
            center.x + std::sin(camera.yaw) * horizontal,
            center.y + std::sin(camera.pitch) * camera.distance,
            center.z + std::cos(camera.yaw) * horizontal,
            1.0f,
        };
        mat_identity();
        mat_perspective(160.0f, 120.0f, 1.0f / std::tan(kPi / 6.0f), 1.0f,
                        1400.0f);
        mat_lookat(&eye, &center, &up);
        const std::uint64_t start = timer_us_gettime64();
        const FrameStats stats = render_room(room, polygon_header, projected.get(),
                                             transformed_at.get(), frame + 1U);
        const std::uint64_t elapsed = timer_us_gettime64() - start;
        ++frame;
        if(frame % 120U == 0U) {
            std::printf(
                "re4dc-room: frame=%lu groups=%lu vertices=%lu triangles=%lu "
                "render_us=%llu\n",
                static_cast<unsigned long>(frame),
                static_cast<unsigned long>(stats.groups),
                static_cast<unsigned long>(stats.transformed_vertices),
                static_cast<unsigned long>(stats.triangles),
                static_cast<unsigned long long>(elapsed));
        }
    }
    std::printf("re4dc-room: clean exit\n");
    return 0;
}
