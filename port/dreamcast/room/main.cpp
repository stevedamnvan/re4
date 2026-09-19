#include <kos.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <new>

#include "collision_package.hpp"
#include "room_package.hpp"

KOS_INIT_FLAGS(INIT_DEFAULT);

namespace {

constexpr float kPi = 3.14159265358979323846f;
constexpr float kPlayerRadius = 0.42f;
constexpr float kPlayerHeight = 1.8f;
constexpr float kStepUp = 0.55f;
constexpr float kStepDown = 2.5f;
constexpr float kMoveSpeed = 6.0f;
constexpr float kTurnSpeed = 2.4f;
constexpr float kSpawnX = 0.0f;
constexpr float kSpawnY = -7.98f;
constexpr float kSpawnZ = -245.0f;
constexpr float kGoalX = 9.0f;
constexpr float kGoalY = -7.98f;
constexpr float kGoalZ = -284.0f;

struct Player {
    float x = kSpawnX;
    float y = kSpawnY;
    float z = kSpawnZ;
    float yaw = kPi;
    std::uint32_t wall_hits = 0;
    std::uint32_t completed_loops = 0;
};

struct Input {
    float move = 0.0f;
    float turn = 0.0f;
    bool reset = false;
    bool exit = false;
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

float analog_axis(std::int8_t value) {
    constexpr int dead_zone = 18;
    const int raw = static_cast<int>(value);
    if(std::abs(raw) <= dead_zone) {
        return 0.0f;
    }
    const float sign = raw < 0 ? -1.0f : 1.0f;
    return sign * static_cast<float>(std::abs(raw) - dead_zone) /
           static_cast<float>(128 - dead_zone);
}

Input read_input() {
    Input input{};
    maple_device_t* controller = maple_enum_type(0, MAPLE_FUNC_CONTROLLER);
    if(controller == nullptr) {
        return input;
    }
    const auto* state = static_cast<const cont_state_t*>(maple_dev_status(controller));
    if(state == nullptr) {
        return input;
    }
    input.turn = analog_axis(state->joyx);
    input.move = -analog_axis(state->joyy);
    if((state->buttons & CONT_DPAD_LEFT) != 0) {
        input.turn = -1.0f;
    } else if((state->buttons & CONT_DPAD_RIGHT) != 0) {
        input.turn = 1.0f;
    }
    if((state->buttons & CONT_DPAD_UP) != 0) {
        input.move = 1.0f;
    } else if((state->buttons & CONT_DPAD_DOWN) != 0) {
        input.move = -1.0f;
    }
    input.reset = (state->buttons & CONT_A) != 0;
    input.exit = (state->buttons & CONT_START) != 0;
    return input;
}

void reset_player(Player& player) {
    const std::uint32_t loops = player.completed_loops;
    player = {};
    player.completed_loops = loops;
}

bool projected_floor_height(const re4dc::collision::Vec3& a,
                            const re4dc::collision::Vec3& b,
                            const re4dc::collision::Vec3& c, float x, float z,
                            float& y) {
    const float denominator =
        (b.z - c.z) * (a.x - c.x) + (c.x - b.x) * (a.z - c.z);
    if(std::fabs(denominator) < 0.00001f) {
        return false;
    }
    const float wa =
        ((b.z - c.z) * (x - c.x) + (c.x - b.x) * (z - c.z)) / denominator;
    const float wb =
        ((c.z - a.z) * (x - c.x) + (a.x - c.x) * (z - c.z)) / denominator;
    const float wc = 1.0f - wa - wb;
    if(wa < -0.0001f || wb < -0.0001f || wc < -0.0001f) {
        return false;
    }
    y = wa * a.y + wb * b.y + wc * c.y;
    return true;
}

bool find_floor(const re4dc::collision::Package& collision, float x, float z,
                float reference_y, float& floor_y) {
    const auto* vertices = collision.vertices();
    const auto* polygons = collision.polygons();
    const std::uint32_t count =
        collision.header().floor_count + collision.header().slope_count;
    float best_delta = 1.0e9f;
    bool found = false;
    for(std::uint32_t index = 0; index < count; ++index) {
        const auto& polygon = polygons[index];
        float candidate = 0.0f;
        if(!projected_floor_height(vertices[polygon.vertex[0]],
                                   vertices[polygon.vertex[1]],
                                   vertices[polygon.vertex[2]], x, z,
                                   candidate)) {
            continue;
        }
        const float delta = candidate - reference_y;
        if(delta > kStepUp || delta < -kStepDown || std::fabs(delta) >= best_delta) {
            continue;
        }
        floor_y = candidate;
        best_delta = std::fabs(delta);
        found = true;
    }
    return found;
}

std::uint32_t resolve_walls(const re4dc::collision::Package& collision,
                            Player& player) {
    const auto* vertices = collision.vertices();
    const auto* normals = collision.normals();
    const auto* polygons = collision.polygons();
    const std::uint32_t first_wall =
        collision.header().floor_count + collision.header().slope_count;
    std::uint32_t hits = 0;
    for(unsigned pass = 0; pass < 3; ++pass) {
        bool moved = false;
        for(std::uint32_t index = first_wall;
            index < collision.header().polygon_count; ++index) {
            const auto& polygon = polygons[index];
            const auto& a = vertices[polygon.vertex[0]];
            const auto& b = vertices[polygon.vertex[1]];
            const auto& c = vertices[polygon.vertex[2]];
            const float wall_min_y = std::min({a.y, b.y, c.y});
            const float wall_max_y = std::max({a.y, b.y, c.y});
            if(player.y + kPlayerHeight < wall_min_y || player.y > wall_max_y) {
                continue;
            }
            const re4dc::collision::Vec3 points[3] = {a, b, c};
            unsigned segment_a = 0;
            unsigned segment_b = 1;
            float longest = -1.0f;
            for(unsigned first = 0; first < 3; ++first) {
                for(unsigned second = first + 1; second < 3; ++second) {
                    const float dx = points[second].x - points[first].x;
                    const float dz = points[second].z - points[first].z;
                    const float length = dx * dx + dz * dz;
                    if(length > longest) {
                        longest = length;
                        segment_a = first;
                        segment_b = second;
                    }
                }
            }
            if(longest < 0.000001f) {
                continue;
            }
            const auto& start = points[segment_a];
            const auto& end = points[segment_b];
            const float sx = end.x - start.x;
            const float sz = end.z - start.z;
            const float projection = std::clamp(
                ((player.x - start.x) * sx + (player.z - start.z) * sz) /
                    longest,
                0.0f, 1.0f);
            const float nearest_x = start.x + projection * sx;
            const float nearest_z = start.z + projection * sz;
            float dx = player.x - nearest_x;
            float dz = player.z - nearest_z;
            const float distance_squared = dx * dx + dz * dz;
            if(distance_squared >= kPlayerRadius * kPlayerRadius) {
                continue;
            }
            float distance = std::sqrt(distance_squared);
            if(distance < 0.0001f) {
                const auto& normal = normals[polygon.normal];
                dx = normal.x;
                dz = normal.z;
                distance = std::sqrt(dx * dx + dz * dz);
                if(distance < 0.0001f) {
                    dx = -sz;
                    dz = sx;
                    distance = std::sqrt(dx * dx + dz * dz);
                }
            }
            const float correction = (kPlayerRadius - distance) / distance;
            player.x += dx * correction;
            player.z += dz * correction;
            ++hits;
            moved = true;
        }
        if(!moved) {
            break;
        }
    }
    return hits;
}

void update_player(Player& player, const re4dc::collision::Package& collision,
                   const Input& input, float delta_seconds) {
    player.yaw += input.turn * kTurnSpeed * delta_seconds;
    const float old_x = player.x;
    const float old_z = player.z;
    player.x += std::sin(player.yaw) * input.move * kMoveSpeed * delta_seconds;
    player.z += std::cos(player.yaw) * input.move * kMoveSpeed * delta_seconds;
    player.wall_hits += resolve_walls(collision, player);
    float floor_y = player.y;
    if(find_floor(collision, player.x, player.z, player.y, floor_y)) {
        player.y = floor_y;
    } else {
        player.x = old_x;
        player.z = old_z;
    }
    const float goal_dx = player.x - kGoalX;
    const float goal_dz = player.z - kGoalZ;
    if(goal_dx * goal_dx + goal_dz * goal_dz < 16.0f) {
        ++player.completed_loops;
        std::printf("re4dc-room: exit reached loops=%lu\n",
                    static_cast<unsigned long>(player.completed_loops));
        reset_player(player);
    }
}

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

bool group_visible(const re4dc::room::Group& group) {
    bool behind = true;
    bool beyond_far = true;
    bool left = true;
    bool right = true;
    bool above = true;
    bool below = true;
    for(unsigned corner = 0; corner < 8; ++corner) {
        float x = (corner & 1U) != 0 ? group.bounds_max[0] : group.bounds_min[0];
        float y = (corner & 2U) != 0 ? group.bounds_max[1] : group.bounds_min[1];
        float z = (corner & 4U) != 0 ? group.bounds_max[2] : group.bounds_min[2];
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

void submit_world_triangle(const point_t& a, const point_t& b, const point_t& c,
                           std::uint32_t color) {
    const point_t source[3] = {a, b, c};
    pvr_vertex_t vertices[3]{};
    for(unsigned index = 0; index < 3; ++index) {
        float x = source[index].x;
        float y = source[index].y;
        float z = source[index].z;
        mat_trans_single(x, y, z);
        if(z <= 0.0f) {
            return;
        }
        vertices[index] = {
            .flags = index == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
            .x = x, .y = y, .z = z, .u = 0.0f, .v = 0.0f,
            .argb = color, .oargb = 0,
        };
    }
    for(const auto& vertex : vertices) {
        auto* target = static_cast<pvr_vertex_t*>(pvr_dr_target());
        *target = vertex;
        pvr_dr_commit(target);
    }
}

void draw_player(const Player& player) {
    const float fx = std::sin(player.yaw);
    const float fz = std::cos(player.yaw);
    const float rx = std::cos(player.yaw);
    const float rz = -std::sin(player.yaw);
    const point_t nose = {player.x + fx * 0.75f, player.y + 0.08f,
                          player.z + fz * 0.75f, 1.0f};
    const point_t left = {player.x - fx * 0.35f - rx * 0.42f,
                          player.y + 0.08f,
                          player.z - fz * 0.35f - rz * 0.42f, 1.0f};
    const point_t right = {player.x - fx * 0.35f + rx * 0.42f,
                           player.y + 0.08f,
                           player.z - fz * 0.35f + rz * 0.42f, 1.0f};
    const point_t top = {player.x, player.y + kPlayerHeight, player.z, 1.0f};
    constexpr std::uint32_t color = 0xffff9b32U;
    submit_world_triangle(nose, left, top, color);
    submit_world_triangle(right, nose, top, color);
    submit_world_triangle(left, right, top, color);
    submit_world_triangle(nose, right, left, color);
}

void draw_goal() {
    constexpr float radius = 0.55f;
    const point_t base[4] = {
        {kGoalX - radius, kGoalY + 0.05f, kGoalZ - radius, 1.0f},
        {kGoalX + radius, kGoalY + 0.05f, kGoalZ - radius, 1.0f},
        {kGoalX + radius, kGoalY + 0.05f, kGoalZ + radius, 1.0f},
        {kGoalX - radius, kGoalY + 0.05f, kGoalZ + radius, 1.0f},
    };
    const point_t top = {kGoalX, kGoalY + 2.4f, kGoalZ, 1.0f};
    for(unsigned index = 0; index < 4; ++index) {
        submit_world_triangle(base[index], base[(index + 1U) % 4U], top,
                              0xff45ff78U);
    }
}

FrameStats render_scene(const re4dc::room::Package& room, const Player& player,
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
    draw_player(player);
    draw_goal();
    pvr_list_finish();
    pvr_scene_finish();
    return stats;
}

} // namespace

int main() {
    re4dc::room::Package room;
    if(!room.open("/rd/r10d.re4room")) {
        std::printf("re4dc-room: room load failed: %s\n", room.error());
        return 1;
    }
    re4dc::collision::Package collision;
    if(!collision.open("/rd/r10d.re4sat")) {
        std::printf("re4dc-room: collision load failed: %s\n", collision.error());
        return 1;
    }
    std::printf(
        "re4dc-room: loaded vertices=%lu triangles=%lu groups=%lu collision=%lu/%lu/%lu\n",
        static_cast<unsigned long>(room.header().vertex_count),
        static_cast<unsigned long>(room.header().index_count / 3U),
        static_cast<unsigned long>(room.header().group_count),
        static_cast<unsigned long>(collision.header().floor_count),
        static_cast<unsigned long>(collision.header().slope_count),
        static_cast<unsigned long>(collision.header().wall_count));

    vid_set_mode(DM_320x240, PM_RGB565);
    pvr_init_defaults();
    pvr_set_bg_color(0.055f, 0.07f, 0.09f);
    pvr_poly_cxt_t context{};
    pvr_poly_hdr_t polygon_header{};
    pvr_poly_cxt_col(&context, PVR_LIST_OP_POLY);
    context.gen.culling = PVR_CULLING_NONE;
    pvr_poly_compile(&polygon_header, &context);

    // mat_perspective maps positive view Y toward the bottom of the PVR screen.
    const vector_t up = {0.0f, -1.0f, 0.0f, 0.0f};
    Player player{};
    float initial_floor = player.y;
    if(!find_floor(collision, player.x, player.z, player.y, initial_floor)) {
        std::printf("re4dc-room: spawn is not on collision floor\n");
        return 1;
    }
    player.y = initial_floor;
    std::uint32_t frame = 0;
    std::uint64_t previous_time = timer_us_gettime64();
    bool reset_was_down = false;
    std::unique_ptr<ProjectedVertex[]> projected(
        new(std::nothrow) ProjectedVertex[room.header().vertex_count]);
    std::unique_ptr<std::uint32_t[]> transformed_at(
        new(std::nothrow) std::uint32_t[room.header().vertex_count]());
    if(projected == nullptr || transformed_at == nullptr) {
        std::printf("re4dc-room: transform cache allocation failed\n");
        return 1;
    }
    std::printf("re4dc-room: stick=turn/move A=reset START=exit; reach green marker\n");
    while(true) {
        const Input input = read_input();
        if(input.exit) {
            break;
        }
        if(input.reset && !reset_was_down) {
            reset_player(player);
        }
        reset_was_down = input.reset;
        const std::uint64_t now = timer_us_gettime64();
        const float delta_seconds = std::clamp(
            static_cast<float>(now - previous_time) / 1000000.0f, 0.0f, 0.1f);
        previous_time = now;
        update_player(player, collision, input, delta_seconds);

        const float fx = std::sin(player.yaw);
        const float fz = std::cos(player.yaw);
        const float rx = std::cos(player.yaw);
        const float rz = -std::sin(player.yaw);
        const point_t eye = {player.x - fx * 6.0f + rx * 0.75f,
                             player.y + 2.8f,
                             player.z - fz * 6.0f + rz * 0.75f, 1.0f};
        const point_t target = {player.x + fx * 2.0f, player.y + 1.25f,
                                player.z + fz * 2.0f, 1.0f};
        mat_identity();
        mat_perspective(160.0f, 120.0f, 1.0f / std::tan(kPi / 6.0f), 1.0f,
                        500.0f);
        mat_lookat(&eye, &target, &up);
        const std::uint64_t start = timer_us_gettime64();
        const FrameStats stats = render_scene(room, player, polygon_header,
                                              projected.get(), transformed_at.get(),
                                              frame + 1U);
        const std::uint64_t elapsed = timer_us_gettime64() - start;
        ++frame;
        if(frame % 120U == 0U) {
            std::printf(
                "re4dc-room: frame=%lu pos=%.2f,%.2f,%.2f groups=%lu vertices=%lu "
                "triangles=%lu wall_hits=%lu loops=%lu render_us=%llu\n",
                static_cast<unsigned long>(frame), player.x, player.y, player.z,
                static_cast<unsigned long>(stats.groups),
                static_cast<unsigned long>(stats.transformed_vertices),
                static_cast<unsigned long>(stats.triangles),
                static_cast<unsigned long>(player.wall_hits),
                static_cast<unsigned long>(player.completed_loops),
                static_cast<unsigned long long>(elapsed));
        }
    }
    std::printf("re4dc-room: clean exit\n");
    return 0;
}
