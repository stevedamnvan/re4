#include <kos.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <new>
#include <fcntl.h>

#include "character_package.hpp"
#include "collision_package.hpp"
#include "room_package.hpp"
#include "texture_package.hpp"

KOS_INIT_FLAGS(INIT_DEFAULT);

struct DemoTelemetry {
    std::uint32_t magic;
    std::uint32_t version;
    std::uint32_t frame;
    std::uint32_t autoplay_phase;
    std::uint32_t flags;
    std::int32_t player_health;
    std::int32_t ammo;
    std::int32_t enemy_health;
    std::uint32_t loops;
    float player_x;
    float player_z;
    float player_yaw;
    float enemy_x;
    float enemy_z;
    std::uint32_t visible_groups;
    std::uint32_t transformed_vertices;
    std::uint32_t room_triangles;
    std::uint32_t actor_triangles;
    std::uint32_t frame_us;
    std::uint32_t submit_us;
};

extern "C" {
volatile DemoTelemetry g_re4dc_demo_telemetry = {
    0x52453444U, 1U, 0U, 0U, 0U, 0, 0, 0, 0U, 0.0f, 0.0f, 0.0f, 0.0f,
    0.0f, 0U, 0U, 0U, 0U, 0U, 0U,
};
}

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
constexpr float kGoalX = 32.0f;
constexpr float kGoalY = -7.98f;
constexpr float kGoalZ = -284.0f;
constexpr float kEnemySpawnX = 0.0f;
constexpr float kEnemySpawnY = -7.98f;
constexpr float kEnemySpawnZ = -265.0f;
constexpr float kEnemyMoveSpeed = 1.9f;
constexpr float kEnemyAttackRange = 2.4f;
constexpr float kEnemyTurnSpeed = 0.15707964f * 30.0f;
constexpr float kFarClipDistance = 35.0f;
constexpr int kMagazineSize = 6;
constexpr int kPlayerMaxHealth = 100;
constexpr int kEnemyMaxHealth = 3;

enum class EnemyState : std::uint8_t {
    Chase,
    Attack,
    Hit,
    Dead,
};

struct Player {
    float x = kSpawnX;
    float y = kSpawnY;
    float z = kSpawnZ;
    float yaw = kPi;
    std::uint32_t wall_hits = 0;
    std::uint32_t completed_loops = 0;
    std::uint32_t animation_clip = 0;
    float animation_frame = 0.0f;
    int health = kPlayerMaxHealth;
    int ammo = kMagazineSize;
    float reload_seconds = 0.0f;
    bool aiming = false;
    bool dead = false;
};

struct Enemy {
    float x = kEnemySpawnX;
    float y = kEnemySpawnY;
    float z = kEnemySpawnZ;
    float yaw = 0.0f;
    EnemyState state = EnemyState::Chase;
    int health = kEnemyMaxHealth;
    std::uint32_t animation_clip = 1;
    float animation_frame = 0.0f;
    bool attack_landed = false;
};

struct Input {
    float move = 0.0f;
    float turn = 0.0f;
    bool aim = false;
    bool fire = false;
    bool reload = false;
    bool restart = false;
    bool exit = false;
};

enum class AutoplayPhase : std::uint8_t {
    WaitForDeath,
    Restart,
    WasteMagazine,
    StartReload,
    WaitForReload,
    Fight,
    Exit,
    Complete,
};

struct Autoplay {
    bool enabled = false;
    bool observed_death = false;
    bool observed_reload = false;
    AutoplayPhase phase = AutoplayPhase::WaitForDeath;
    float fire_cooldown = 0.0f;
    std::uint32_t exit_waypoint = 0;
};

struct FrameStats {
    std::uint32_t groups = 0;
    std::uint32_t triangles = 0;
    std::uint32_t transformed_vertices = 0;
    std::uint32_t character_triangles = 0;
    std::uint64_t wait_us = 0;
    std::uint64_t submit_us = 0;
    std::uint64_t finish_us = 0;
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
    input.aim = state->rtrig > 24 || (state->buttons & CONT_Y) != 0;
    input.fire = (state->buttons & CONT_A) != 0;
    input.reload = (state->buttons & CONT_X) != 0;
    input.restart = (state->buttons & CONT_B) != 0;
    input.exit = (state->buttons & CONT_START) != 0;
    return input;
}

bool file_exists(const char* path) {
    const file_t file = fs_open(path, O_RDONLY);
    if(file == FILEHND_INVALID) {
        return false;
    }
    fs_close(file);
    return true;
}

void write_autoplay_result(const Autoplay& autoplay,
                           const Player& player) {
    const char* result = autoplay.observed_death && autoplay.observed_reload &&
                                 player.completed_loops > 0
                             ? "RE4DC_AUTOPLAY_PASS death=1 reload=1 loop=1\n"
                             : "RE4DC_AUTOPLAY_FAIL\n";
    const file_t file = fs_open("/vmu/a1/RE4DEMO", O_WRONLY | O_CREAT | O_TRUNC);
    if(file != FILEHND_INVALID) {
        fs_write(file, result, std::strlen(result));
        fs_close(file);
    }
    std::printf("%s", result);
}

void reset_player(Player& player) {
    const std::uint32_t loops = player.completed_loops;
    player = {};
    player.completed_loops = loops;
}

void reset_encounter(Player& player, Enemy& enemy) {
    reset_player(player);
    enemy = {};
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
    player.aiming = input.aim && !player.dead;
    if(player.dead) {
        return;
    }
    player.yaw += input.turn * kTurnSpeed * delta_seconds;
    const float movement = player.aiming ? 0.0f : input.move;
    const float old_x = player.x;
    const float old_z = player.z;
    player.x += std::sin(player.yaw) * movement * kMoveSpeed * delta_seconds;
    player.z += std::cos(player.yaw) * movement * kMoveSpeed * delta_seconds;
    player.wall_hits += resolve_walls(collision, player);
    float floor_y = player.y;
    if(find_floor(collision, player.x, player.z, player.y, floor_y)) {
        player.y = floor_y;
    } else {
        player.x = old_x;
        player.z = old_z;
    }
}

void update_animation(Player& player, const re4dc::character::Package& character,
                      const Input& input, float delta_seconds) {
    const std::uint32_t desired_clip =
        !player.aiming && std::fabs(input.move) > 0.05f &&
                character.header().clip_count > 1U
            ? 1U
            : 0U;
    if(player.animation_clip != desired_clip) {
        player.animation_clip = desired_clip;
        player.animation_frame = 0.0f;
    }
    const auto& clip = character.clips()[player.animation_clip];
    player.animation_frame += clip.frames_per_second * delta_seconds;
    while(player.animation_frame >= static_cast<float>(clip.frame_count)) {
        player.animation_frame -= static_cast<float>(clip.frame_count);
    }
}

float wrap_angle(float angle) {
    while(angle > kPi) {
        angle -= 2.0f * kPi;
    }
    while(angle < -kPi) {
        angle += 2.0f * kPi;
    }
    return angle;
}

Input autoplay_input(Autoplay& autoplay, const Player& player,
                     const Enemy& enemy, float delta_seconds) {
    Input input{};
    autoplay.fire_cooldown = std::max(0.0f, autoplay.fire_cooldown - delta_seconds);
    switch(autoplay.phase) {
    case AutoplayPhase::WaitForDeath:
        if(player.dead) {
            autoplay.observed_death = true;
            autoplay.phase = AutoplayPhase::Restart;
        }
        break;
    case AutoplayPhase::Restart:
        input.restart = true;
        autoplay.phase = AutoplayPhase::WasteMagazine;
        break;
    case AutoplayPhase::WasteMagazine:
        input.aim = true;
        input.turn = 1.0f;
        if(player.ammo == 0) {
            autoplay.phase = AutoplayPhase::StartReload;
        } else if(autoplay.fire_cooldown <= 0.0f) {
            input.fire = true;
            autoplay.fire_cooldown = 0.3f;
        }
        break;
    case AutoplayPhase::StartReload:
        input.reload = true;
        autoplay.phase = AutoplayPhase::WaitForReload;
        break;
    case AutoplayPhase::WaitForReload:
        if(player.reload_seconds <= 0.0f && player.ammo == kMagazineSize) {
            autoplay.observed_reload = true;
            autoplay.phase = AutoplayPhase::Fight;
        }
        break;
    case AutoplayPhase::Fight: {
        input.aim = true;
        const float target_yaw = std::atan2(enemy.x - player.x,
                                            enemy.z - player.z);
        const float angle = wrap_angle(target_yaw - player.yaw);
        input.turn = std::clamp(angle * 2.0f, -1.0f, 1.0f);
        if(std::fabs(angle) < 0.07f && autoplay.fire_cooldown <= 0.0f) {
            input.fire = true;
            autoplay.fire_cooldown = 0.35f;
        }
        if(enemy.state == EnemyState::Dead) {
            autoplay.phase = AutoplayPhase::Exit;
        }
        break;
    }
    case AutoplayPhase::Exit: {
        static constexpr float waypoints[][2] = {
            {0.0f, -238.0f},
            {32.0f, -238.0f},
            {kGoalX, kGoalZ},
        };
        const std::uint32_t waypoint = std::min<std::uint32_t>(
            autoplay.exit_waypoint, 2U);
        const float waypoint_x = waypoints[waypoint][0];
        const float waypoint_z = waypoints[waypoint][1];
        const float dx = waypoint_x - player.x;
        const float dz = waypoint_z - player.z;
        if(dx * dx + dz * dz < 4.0f &&
           autoplay.exit_waypoint < 2U) {
            ++autoplay.exit_waypoint;
        }
        const float target_yaw = std::atan2(dx, dz);
        const float angle = wrap_angle(target_yaw - player.yaw);
        input.turn = std::clamp(angle * 2.0f, -1.0f, 1.0f);
        if(std::fabs(angle) < 0.18f) {
            input.move = 1.0f;
        }
        if(player.completed_loops > 0) {
            autoplay.phase = AutoplayPhase::Complete;
        }
        break;
    }
    case AutoplayPhase::Complete:
        input.exit = true;
        break;
    }
    return input;
}

void set_enemy_clip(Enemy& enemy, std::uint32_t clip) {
    if(enemy.animation_clip != clip) {
        enemy.animation_clip = clip;
        enemy.animation_frame = 0.0f;
    }
}

void advance_enemy_animation(Enemy& enemy,
                             const re4dc::character::Package& character,
                             float delta_seconds, bool loop) {
    const auto& clip = character.clips()[enemy.animation_clip];
    enemy.animation_frame += clip.frames_per_second * delta_seconds;
    if(loop) {
        while(enemy.animation_frame >= static_cast<float>(clip.frame_count)) {
            enemy.animation_frame -= static_cast<float>(clip.frame_count);
        }
    } else {
        enemy.animation_frame = std::min(
            enemy.animation_frame, static_cast<float>(clip.frame_count - 1U));
    }
}

void update_enemy(Enemy& enemy, Player& player,
                  const re4dc::character::Package& character,
                  const re4dc::collision::Package& collision,
                  float delta_seconds) {
    if(enemy.health <= 0) {
        enemy.state = EnemyState::Dead;
    }
    if(enemy.state == EnemyState::Dead) {
        set_enemy_clip(enemy, 4);
        advance_enemy_animation(enemy, character, delta_seconds, false);
        return;
    }
    if(enemy.state == EnemyState::Hit) {
        set_enemy_clip(enemy, 3);
        advance_enemy_animation(enemy, character, delta_seconds, false);
        const auto& clip = character.clips()[enemy.animation_clip];
        if(enemy.animation_frame >= static_cast<float>(clip.frame_count - 1U)) {
            enemy.state = EnemyState::Chase;
            set_enemy_clip(enemy, 1);
        }
        return;
    }

    const float dx = player.x - enemy.x;
    const float dz = player.z - enemy.z;
    const float distance = std::sqrt(dx * dx + dz * dz);
    const float target_yaw = std::atan2(dx, dz);
    const float turn = std::clamp(wrap_angle(target_yaw - enemy.yaw),
                                  -kEnemyTurnSpeed * delta_seconds,
                                  kEnemyTurnSpeed * delta_seconds);
    enemy.yaw = wrap_angle(enemy.yaw + turn);
    if(player.dead || distance > kEnemyAttackRange) {
        enemy.state = EnemyState::Chase;
        set_enemy_clip(enemy, 1);
        if(!player.dead && distance > 0.001f) {
            const float step = std::min(kEnemyMoveSpeed * delta_seconds,
                                        distance - kEnemyAttackRange * 0.85f);
            enemy.x += dx / distance * std::max(step, 0.0f);
            enemy.z += dz / distance * std::max(step, 0.0f);
            float floor_y = enemy.y;
            if(find_floor(collision, enemy.x, enemy.z, enemy.y, floor_y)) {
                enemy.y = floor_y;
            }
        }
        advance_enemy_animation(enemy, character, delta_seconds, true);
        return;
    }

    if(enemy.state != EnemyState::Attack) {
        enemy.state = EnemyState::Attack;
        enemy.attack_landed = false;
        set_enemy_clip(enemy, 2);
    }
    const auto& clip = character.clips()[enemy.animation_clip];
    const float previous = enemy.animation_frame;
    advance_enemy_animation(enemy, character, delta_seconds, false);
    const float strike_frame = static_cast<float>(clip.frame_count) * 0.52f;
    if(!enemy.attack_landed && previous < strike_frame &&
       enemy.animation_frame >= strike_frame) {
        enemy.attack_landed = true;
        player.health = std::max(0, player.health - 25);
        std::printf("re4dc-room: ganado attack player_hp=%d\n", player.health);
        if(player.health == 0) {
            player.dead = true;
        }
    }
    if(enemy.animation_frame >= static_cast<float>(clip.frame_count - 1U)) {
        enemy.animation_frame = 0.0f;
        enemy.attack_landed = false;
    }
}

bool shot_hits_enemy(const Player& player, const Enemy& enemy) {
    if(enemy.state == EnemyState::Dead) {
        return false;
    }
    const float dx = enemy.x - player.x;
    const float dz = enemy.z - player.z;
    const float distance_squared = dx * dx + dz * dz;
    if(distance_squared > 35.0f * 35.0f) {
        return false;
    }
    const float target_yaw = std::atan2(dx, dz);
    return std::fabs(wrap_angle(target_yaw - player.yaw)) < 0.12f;
}

void update_combat(Player& player, Enemy& enemy, const Input& input,
                   bool fire_pressed, bool reload_pressed,
                   float delta_seconds) {
    if(player.dead) {
        return;
    }
    if(player.reload_seconds > 0.0f) {
        player.reload_seconds -= delta_seconds;
        if(player.reload_seconds <= 0.0f) {
            player.reload_seconds = 0.0f;
            player.ammo = kMagazineSize;
            std::printf("re4dc-room: reload complete ammo=%d\n", player.ammo);
        }
        return;
    }
    if(reload_pressed && player.ammo < kMagazineSize) {
        player.reload_seconds = 1.0f;
        std::printf("re4dc-room: reload start\n");
        return;
    }
    if(!fire_pressed || !input.aim || player.ammo <= 0) {
        return;
    }
    --player.ammo;
    const bool hit = shot_hits_enemy(player, enemy);
    std::printf("re4dc-room: fire ammo=%d hit=%d\n", player.ammo, hit ? 1 : 0);
    if(hit) {
        --enemy.health;
        if(enemy.health <= 0) {
            enemy.state = EnemyState::Dead;
            set_enemy_clip(enemy, 4);
            std::printf("re4dc-room: ganado defeated\n");
        } else {
            enemy.state = EnemyState::Hit;
            set_enemy_clip(enemy, 3);
        }
    }
}

std::uint32_t shade_color(float light) {
    const std::uint32_t channel = static_cast<std::uint32_t>(
        std::clamp(light * 255.0f, 0.0f, 255.0f));
    return 0xff000000U | (channel << 16U) | (channel << 8U) | channel;
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
        beyond_far &= z < (1.0f / kFarClipDistance);
        left &= x < 0.0f;
        right &= x > 320.0f;
        above &= y < 0.0f;
        below &= y > 240.0f;
    }
    return !(behind || beyond_far || left || right || above || below);
}

bool transform_triangle(const re4dc::room::Vertex* source,
                        const std::uint32_t* indices, pvr_vertex_t* output,
                        ProjectedVertex* projected,
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
        beyond_far &= z < (1.0f / kFarClipDistance);
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
            .argb = shade_color(light),
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
    pvr_prim(vertices, sizeof(vertices));
}

std::uint32_t character_color(std::uint32_t material) {
    static constexpr std::uint32_t colors[8] = {
        0xffc08a68U, 0xff9d7559U, 0xff25292cU, 0xff35404aU,
        0xff121518U, 0xff6e5139U, 0xff8d6748U, 0xff59402dU,
    };
    return colors[material & 7U];
}

std::uint32_t draw_character(const re4dc::character::Package& character,
                             float actor_x, float actor_y, float actor_z,
                             float actor_yaw, std::uint32_t animation_clip,
                             float animation_frame, ProjectedVertex* projected,
                             std::uint32_t color_bias) {
    const auto& clip = character.clips()[animation_clip];
    const std::uint32_t local_frame =
        static_cast<std::uint32_t>(animation_frame) % clip.frame_count;
    const auto* source = character.frame_positions(clip.first_frame + local_frame);
    const float scale = character.header().position_quantum_m;
    const float sine = std::sin(actor_yaw);
    const float cosine = std::cos(actor_yaw);
    for(std::uint32_t index = 0; index < character.header().vertex_count; ++index) {
        const float local_x = static_cast<float>(source[index * 3U]) * scale;
        const float local_y = static_cast<float>(source[index * 3U + 1U]) * scale;
        const float local_z = static_cast<float>(source[index * 3U + 2U]) * scale;
        float x = actor_x + local_x * cosine + local_z * sine;
        float y = actor_y + local_y;
        float z = actor_z - local_x * sine + local_z * cosine;
        mat_trans_single(x, y, z);
        projected[index] = {x, y, z};
    }

    const auto* indices = character.indices();
    std::uint32_t triangles = 0;
    for(std::uint32_t batch_index = 0;
        batch_index < character.header().batch_count; ++batch_index) {
        const auto& batch = character.batches()[batch_index];
        const std::uint32_t color = character_color(batch.material + color_bias);
        const std::uint32_t end = batch.first_index + batch.index_count;
        for(std::uint32_t index = batch.first_index; index < end; index += 3U) {
            const ProjectedVertex& a = projected[indices[index]];
            const ProjectedVertex& b = projected[indices[index + 1U]];
            const ProjectedVertex& c = projected[indices[index + 2U]];
            if(a.z <= 0.0f || b.z <= 0.0f || c.z <= 0.0f) {
                continue;
            }
            const bool beyond_far =
                a.z < (1.0f / kFarClipDistance) &&
                b.z < (1.0f / kFarClipDistance) &&
                c.z < (1.0f / kFarClipDistance);
            const bool left = a.x < 0.0f && b.x < 0.0f && c.x < 0.0f;
            const bool right = a.x > 320.0f && b.x > 320.0f && c.x > 320.0f;
            const bool above = a.y < 0.0f && b.y < 0.0f && c.y < 0.0f;
            const bool below = a.y > 240.0f && b.y > 240.0f && c.y > 240.0f;
            const float signed_area =
                (b.x - a.x) * (c.y - a.y) -
                (b.y - a.y) * (c.x - a.x);
            if(beyond_far || left || right || above || below ||
               signed_area >= 0.0f) {
                continue;
            }
            const ProjectedVertex source_triangle[3] = {a, b, c};
            pvr_vertex_t output[3]{};
            for(unsigned corner = 0; corner < 3; ++corner) {
                const auto& vertex = source_triangle[corner];
                output[corner] = {
                    .flags = corner == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
                    .x = vertex.x,
                    .y = vertex.y,
                    .z = vertex.z,
                    .u = 0.0f,
                    .v = 0.0f,
                    .argb = color,
                    .oargb = 0,
                };
            }
            pvr_prim(output, sizeof(output));
            ++triangles;
        }
    }
    return triangles;
}

void submit_screen_quad(float left, float top, float right, float bottom,
                        std::uint32_t color) {
    const pvr_vertex_t vertices[4] = {
        {.flags = PVR_CMD_VERTEX, .x = left, .y = top, .z = 1.0f,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
        {.flags = PVR_CMD_VERTEX, .x = right, .y = top, .z = 1.0f,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
        {.flags = PVR_CMD_VERTEX, .x = left, .y = bottom, .z = 1.0f,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
        {.flags = PVR_CMD_VERTEX_EOL, .x = right, .y = bottom, .z = 1.0f,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
    };
    pvr_prim(vertices, sizeof(vertices));
}

void draw_hud(const Player& player, const Enemy& enemy) {
    submit_screen_quad(8.0f, 8.0f, 108.0f, 14.0f, 0xff381818U);
    submit_screen_quad(8.0f, 8.0f, 8.0f + static_cast<float>(player.health),
                       14.0f, 0xffe2463fU);
    for(int bullet = 0; bullet < kMagazineSize; ++bullet) {
        const std::uint32_t color = bullet < player.ammo ? 0xffffd65aU : 0xff463e32U;
        const float left = 8.0f + static_cast<float>(bullet) * 8.0f;
        submit_screen_quad(left, 20.0f, left + 5.0f, 27.0f, color);
    }
    if(enemy.state != EnemyState::Dead) {
        submit_screen_quad(212.0f, 8.0f, 312.0f, 14.0f, 0xff321a18U);
        submit_screen_quad(212.0f, 8.0f,
                           212.0f + 100.0f * static_cast<float>(enemy.health) /
                                      static_cast<float>(kEnemyMaxHealth),
                           14.0f, 0xffd26937U);
    }
    if(player.aiming) {
        submit_screen_quad(156.0f, 119.0f, 164.0f, 121.0f, 0xffff4040U);
        submit_screen_quad(159.0f, 116.0f, 161.0f, 124.0f, 0xffff4040U);
    }
    if(player.dead) {
        submit_screen_quad(70.0f, 104.0f, 250.0f, 136.0f, 0xff7a1111U);
    } else if(enemy.state == EnemyState::Dead) {
        submit_screen_quad(92.0f, 106.0f, 228.0f, 116.0f, 0xff36c85cU);
    }
}

void draw_goal(bool unlocked) {
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
                              unlocked ? 0xff45ff78U : 0xff8b2525U);
    }
}

FrameStats render_scene(const re4dc::room::Package& room,
                        const re4dc::character::Package& leon,
                        const re4dc::character::Package& ganado,
                        const Player& player, const Enemy& enemy,
                        const pvr_poly_hdr_t& untextured_header,
                        const pvr_poly_hdr_t* material_headers,
                        const bool* material_alpha,
                        ProjectedVertex* projected, std::uint32_t* transformed_at,
                        ProjectedVertex* leon_projected,
                        ProjectedVertex* ganado_projected,
                        std::uint32_t frame_token) {
    FrameStats stats{};
    const auto* groups = room.groups();
    const auto* batches = room.batches();
    const auto* vertices = room.vertices();
    const auto* indices = room.indices();
    const std::uint64_t wait_start = timer_us_gettime64();
    pvr_wait_ready();
    const std::uint64_t submit_start = timer_us_gettime64();
    stats.wait_us = submit_start - wait_start;
    pvr_scene_begin();
    pvr_list_begin(PVR_LIST_OP_POLY);
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
            if(material_alpha[batch.material]) {
                continue;
            }
            pvr_prim(&material_headers[batch.material], sizeof(pvr_poly_hdr_t));
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; index += 3) {
                pvr_vertex_t triangle[3];
                if(transform_triangle(vertices, indices + index, triangle,
                                      projected, transformed_at,
                                      frame_token, stats)) {
                    pvr_prim(triangle, sizeof(triangle));
                    ++stats.triangles;
                }
            }
        }
    }
    pvr_prim(&untextured_header, sizeof(untextured_header));
    stats.character_triangles = draw_character(
        leon, player.x, player.y, player.z, player.yaw, player.animation_clip,
        player.animation_frame, leon_projected, 0U);
    stats.character_triangles += draw_character(
        ganado, enemy.x, enemy.y, enemy.z, enemy.yaw, enemy.animation_clip,
        enemy.animation_frame, ganado_projected, 3U);
    draw_goal(enemy.state == EnemyState::Dead);
    draw_hud(player, enemy);
    pvr_list_finish();

    pvr_list_begin(PVR_LIST_PT_POLY);
    for(std::uint32_t group_index = 0; group_index < room.header().group_count;
        ++group_index) {
        const auto& group = groups[group_index];
        if(!group_visible(group)) {
            continue;
        }
        for(std::uint32_t local_batch = 0; local_batch < group.batch_count;
            ++local_batch) {
            const auto& batch = batches[group.first_batch + local_batch];
            if(!material_alpha[batch.material]) {
                continue;
            }
            pvr_prim(&material_headers[batch.material], sizeof(pvr_poly_hdr_t));
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; index += 3) {
                pvr_vertex_t triangle[3];
                if(transform_triangle(vertices, indices + index, triangle,
                                      projected, transformed_at,
                                      frame_token, stats)) {
                    pvr_prim(triangle, sizeof(triangle));
                    ++stats.triangles;
                }
            }
        }
    }
    pvr_list_finish();
    const std::uint64_t finish_start = timer_us_gettime64();
    stats.submit_us = finish_start - submit_start;
    pvr_scene_finish();
    stats.finish_us = timer_us_gettime64() - finish_start;
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
    re4dc::character::Package leon;
    if(!leon.open("/rd/leon.re4chr")) {
        std::printf("re4dc-room: Leon load failed: %s\n", leon.error());
        return 1;
    }
    re4dc::character::Package ganado;
    if(!ganado.open("/rd/ganado.re4chr")) {
        std::printf("re4dc-room: Ganado load failed: %s\n", ganado.error());
        return 1;
    }
    re4dc::texture::Package textures;
    if(!textures.open("/rd/r10d.re4tex")) {
        std::printf("re4dc-room: texture load failed: %s\n", textures.error());
        return 1;
    }
    std::printf(
        "re4dc-room: loaded room=%lu/%lu/%lu collision=%lu/%lu/%lu "
        "leon=%lu/%lu/%lu ganado=%lu/%lu/%lu\n",
        static_cast<unsigned long>(room.header().vertex_count),
        static_cast<unsigned long>(room.header().index_count / 3U),
        static_cast<unsigned long>(room.header().group_count),
        static_cast<unsigned long>(collision.header().floor_count),
        static_cast<unsigned long>(collision.header().slope_count),
        static_cast<unsigned long>(collision.header().wall_count),
        static_cast<unsigned long>(leon.header().vertex_count),
        static_cast<unsigned long>(leon.header().index_count / 3U),
        static_cast<unsigned long>(leon.header().frame_count),
        static_cast<unsigned long>(ganado.header().vertex_count),
        static_cast<unsigned long>(ganado.header().index_count / 3U),
        static_cast<unsigned long>(ganado.header().frame_count));
    if(ganado.header().clip_count < 5U) {
        std::printf("re4dc-room: Ganado package needs idle/walk/attack/hit/death\n");
        return 1;
    }

    vid_set_mode(DM_320x240, PM_RGB565);
    pvr_init_params_t pvr_params = pvr_default_params;
    pvr_params.opb_sizes[PVR_LIST_PT_POLY] = PVR_BINSIZE_16;
    if(pvr_init(&pvr_params) < 0) {
        std::printf("re4dc-room: PVR initialization failed\n");
        return 1;
    }
    pvr_set_bg_color(0.055f, 0.07f, 0.09f);
    const std::size_t vram_before_textures = pvr_mem_available();
    if(!textures.upload()) {
        std::printf("re4dc-room: texture upload failed: %s\n", textures.error());
        return 1;
    }
    pvr_poly_cxt_t context{};
    pvr_poly_hdr_t untextured_header{};
    pvr_poly_cxt_col(&context, PVR_LIST_OP_POLY);
    context.gen.culling = PVR_CULLING_NONE;
    pvr_poly_compile(&untextured_header, &context);
    pvr_poly_hdr_t* material_headers =
        new(std::nothrow) pvr_poly_hdr_t[room.header().material_count];
    std::unique_ptr<bool[]> material_alpha(
        new(std::nothrow) bool[room.header().material_count]);
    if(material_headers == nullptr || material_alpha == nullptr) {
        std::printf("re4dc-room: material header allocation failed\n");
        return 1;
    }
    for(std::uint32_t material = 0; material < room.header().material_count;
        ++material) {
        const auto* texture = textures.find(room.materials()[material].name);
        if(texture == nullptr) {
            std::printf("re4dc-room: no texture for material %s\n",
                        room.materials()[material].name);
            return 1;
        }
        const std::uint32_t texture_index =
            static_cast<std::uint32_t>(texture - textures.textures());
        material_alpha[material] =
            (texture->flags & re4dc::texture::kAlpha) != 0;
        const pvr_list_t list = material_alpha[material]
                                    ? PVR_LIST_PT_POLY
                                    : PVR_LIST_OP_POLY;
        const int format = texture->format == re4dc::texture::kRgb565
                               ? PVR_TXRFMT_RGB565
                               : PVR_TXRFMT_ARGB1555;
        pvr_poly_cxt_txr(&context, list, format, texture->width,
                         texture->height, textures.pvr_texture(texture_index),
                         PVR_FILTER_BILINEAR);
        context.gen.culling = PVR_CULLING_NONE;
        if(material_alpha[material]) {
            context.txr.alpha = PVR_TXRALPHA_ENABLE;
        }
        pvr_poly_compile(&material_headers[material], &context);
    }
    std::printf(
        "re4dc-room: textures=%lu bytes=%lu pvr_free_before=%lu pvr_free_after=%lu\n",
        static_cast<unsigned long>(textures.header().texture_count),
        static_cast<unsigned long>(textures.vram_bytes()),
        static_cast<unsigned long>(vram_before_textures),
        static_cast<unsigned long>(pvr_mem_available()));

    // mat_perspective maps positive view Y toward the bottom of the PVR screen.
    const vector_t up = {0.0f, -1.0f, 0.0f, 0.0f};
    Player player{};
    Enemy enemy{};
    Autoplay autoplay{};
    autoplay.enabled = file_exists("/rd/autoplay.flag");
    if(autoplay.enabled) {
        enemy.z = player.z - kEnemyAttackRange * 0.85f;
        player.health = 25;
    }
    float initial_floor = player.y;
    if(!find_floor(collision, player.x, player.z, player.y, initial_floor)) {
        std::printf("re4dc-room: spawn is not on collision floor\n");
        return 1;
    }
    player.y = initial_floor;
    std::uint32_t frame = 0;
    std::uint64_t previous_time = timer_us_gettime64();
    bool fire_was_down = false;
    bool reload_was_down = false;
    bool restart_was_down = false;
    std::unique_ptr<ProjectedVertex[]> projected(
        new(std::nothrow) ProjectedVertex[room.header().vertex_count]);
    std::unique_ptr<std::uint32_t[]> transformed_at(
        new(std::nothrow) std::uint32_t[room.header().vertex_count]());
    std::unique_ptr<ProjectedVertex[]> leon_projected(
        new(std::nothrow) ProjectedVertex[leon.header().vertex_count]);
    std::unique_ptr<ProjectedVertex[]> ganado_projected(
        new(std::nothrow) ProjectedVertex[ganado.header().vertex_count]);
    if(projected == nullptr || transformed_at == nullptr ||
       leon_projected == nullptr || ganado_projected == nullptr) {
        std::printf("re4dc-room: transform cache allocation failed\n");
        return 1;
    }
    std::printf(
        "re4dc-room: stick=turn/move RT/Y=aim A=fire X=reload B=restart "
        "START=exit; defeat Ganado then reach green marker\n");
    if(autoplay.enabled) {
        std::printf("re4dc-room: deterministic autoplay enabled\n");
    }
    while(true) {
        const std::uint64_t now = timer_us_gettime64();
        const std::uint64_t frame_us = now - previous_time;
        const float delta_seconds = std::clamp(
            static_cast<float>(frame_us) / 1000000.0f, 0.0f, 0.1f);
        previous_time = now;
        const Input input = autoplay.enabled
                                ? autoplay_input(autoplay, player, enemy,
                                                 delta_seconds)
                                : read_input();
        g_re4dc_demo_telemetry.frame = frame;
        g_re4dc_demo_telemetry.autoplay_phase =
            static_cast<std::uint32_t>(autoplay.phase);
        g_re4dc_demo_telemetry.flags =
            (autoplay.enabled ? 1U : 0U) |
            (autoplay.observed_death ? 2U : 0U) |
            (autoplay.observed_reload ? 4U : 0U) |
            (enemy.state == EnemyState::Dead ? 8U : 0U) |
            (player.dead ? 16U : 0U);
        g_re4dc_demo_telemetry.player_health = player.health;
        g_re4dc_demo_telemetry.ammo = player.ammo;
        g_re4dc_demo_telemetry.enemy_health = enemy.health;
        g_re4dc_demo_telemetry.loops = player.completed_loops;
        g_re4dc_demo_telemetry.player_x = player.x;
        g_re4dc_demo_telemetry.player_z = player.z;
        g_re4dc_demo_telemetry.player_yaw = player.yaw;
        g_re4dc_demo_telemetry.enemy_x = enemy.x;
        g_re4dc_demo_telemetry.enemy_z = enemy.z;
        if(input.exit) {
            if(autoplay.enabled) {
                write_autoplay_result(autoplay, player);
            }
            break;
        }
        const bool fire_pressed = input.fire && !fire_was_down;
        const bool reload_pressed = input.reload && !reload_was_down;
        if(input.restart && !restart_was_down) {
            reset_encounter(player, enemy);
            std::printf("re4dc-room: encounter restarted\n");
        }
        fire_was_down = input.fire;
        reload_was_down = input.reload;
        restart_was_down = input.restart;
        update_player(player, collision, input, delta_seconds);
        update_animation(player, leon, input, delta_seconds);
        update_combat(player, enemy, input, fire_pressed, reload_pressed,
                      delta_seconds);
        update_enemy(enemy, player, ganado, collision, delta_seconds);
        const float goal_dx = player.x - kGoalX;
        const float goal_dz = player.z - kGoalZ;
        if(enemy.state == EnemyState::Dead && !player.dead &&
           goal_dx * goal_dx + goal_dz * goal_dz < 16.0f) {
            ++player.completed_loops;
            std::printf("re4dc-room: demo loop complete loops=%lu\n",
                        static_cast<unsigned long>(player.completed_loops));
            reset_encounter(player, enemy);
        }

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
        const FrameStats stats = render_scene(
            room, leon, ganado, player, enemy, untextured_header,
            material_headers, material_alpha.get(), projected.get(),
            transformed_at.get(), leon_projected.get(), ganado_projected.get(),
            frame + 1U);
        g_re4dc_demo_telemetry.visible_groups = stats.groups;
        g_re4dc_demo_telemetry.transformed_vertices =
            stats.transformed_vertices;
        g_re4dc_demo_telemetry.room_triangles = stats.triangles;
        g_re4dc_demo_telemetry.actor_triangles = stats.character_triangles;
        g_re4dc_demo_telemetry.frame_us = static_cast<std::uint32_t>(
            std::min<std::uint64_t>(frame_us, 0xffffffffU));
        g_re4dc_demo_telemetry.submit_us = static_cast<std::uint32_t>(
            std::min<std::uint64_t>(stats.submit_us, 0xffffffffU));
        ++frame;
        if(frame % 120U == 0U) {
            std::printf(
                "re4dc-room: frame=%lu pos=%.2f,%.2f,%.2f groups=%lu vertices=%lu "
                "triangles=%lu actors_triangles=%lu wall_hits=%lu loops=%lu "
                "hp=%d ammo=%d enemy_hp=%d state=%u frame_us=%llu wait_us=%llu "
                "submit_us=%llu finish_us=%llu\n",
                static_cast<unsigned long>(frame), player.x, player.y, player.z,
                static_cast<unsigned long>(stats.groups),
                static_cast<unsigned long>(stats.transformed_vertices),
                static_cast<unsigned long>(stats.triangles),
                static_cast<unsigned long>(stats.character_triangles),
                static_cast<unsigned long>(player.wall_hits),
                static_cast<unsigned long>(player.completed_loops),
                player.health, player.ammo, enemy.health,
                static_cast<unsigned>(enemy.state),
                static_cast<unsigned long long>(frame_us),
                static_cast<unsigned long long>(stats.wait_us),
                static_cast<unsigned long long>(stats.submit_us),
                static_cast<unsigned long long>(stats.finish_us));
        }
    }
    delete[] material_headers;
    std::printf("re4dc-room: clean exit\n");
    return 0;
}
