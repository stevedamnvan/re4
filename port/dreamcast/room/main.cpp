#include <kos.h>
#include <arch/arch.h>
#include <arch/stack.h>
#include <dc/sound/sfxmgr.h>
#include <dc/sound/sound.h>
#include <kos/mm.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <malloc.h>
#include <new>
#include <fcntl.h>

#include "character_package.hpp"
#include "collision_package.hpp"
#include "room_package.hpp"
#include "route_package.hpp"
#include "source_hud_package.hpp"
#include "texture_package.hpp"

KOS_INIT_FLAGS(INIT_DEFAULT);

struct DemoTelemetry {
    std::uint32_t magic;
    std::uint32_t version;
    std::uint32_t byte_size;
    // Odd while the runtime is publishing a snapshot, even when complete.
    // Readers must accept a snapshot only when two sequence reads match and
    // both are even.
    std::uint32_t sequence;
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
    std::uint32_t simulation_tick;
    std::uint32_t simulation_overruns;
    std::uint32_t pvr_free_before_textures;
    std::uint32_t pvr_free_after_textures;
    std::uint32_t aica_free_after_audio;
    std::uint32_t heap_arena_bytes;
    std::uint32_t heap_used_bytes;
    std::uint32_t heap_free_bytes;
    std::uint32_t main_ram_free_bytes;
    std::uint32_t simulation_tick_begin;
    std::uint32_t simulation_ticks_run;
    std::uint32_t simulation_dropped_ticks;
    std::uint32_t simulation_dropped_us;
    std::uint32_t simulation_clamped_us;
    std::uint32_t simulation_catchup_dropped_us;
    std::uint32_t simulation_debt_us;
    std::uint32_t simulation_debt_us_max;
    std::uint32_t outer_interval_us;
    std::uint32_t input_samples;
    std::uint32_t input_sample_gap_us;
    std::uint32_t input_sample_gap_us_max;
    std::uint32_t input_us;
    std::uint32_t simulation_us;
    std::uint32_t camera_us;
    std::uint32_t render_total_us;
    std::uint32_t actor_pose_us;
    std::uint32_t actor_normals_us;
    std::uint32_t actor_lighting_us;
    std::uint32_t pvr_wait_us;
    std::uint32_t opaque_room_us;
    std::uint32_t opaque_actor_us;
    std::uint32_t translucent_room_us;
    std::uint32_t translucent_actor_hud_us;
    std::uint32_t scene_finish_us;
    std::uint32_t pvr_sample_frame_count;
    std::uint32_t pvr_sample_vblank_count;
    std::uint32_t pvr_sample_last_present_ns;
    std::uint32_t pvr_sample_last_registration_ns;
    std::uint32_t pvr_sample_last_render_ns;
    std::uint32_t pvr_sample_vertex_bytes;
    std::uint32_t pvr_sample_vertex_bytes_max;
    std::uint32_t room_index_references;
    std::uint32_t room_cache_hits;
    std::uint32_t room_cache_misses;
    std::uint32_t room_light_evaluations;
    std::uint32_t room_near_trivial_accepts;
    std::uint32_t room_near_trivial_rejects;
    std::uint32_t room_near_crossings;
    std::uint32_t collision_queries;
    std::uint32_t collision_block_tests;
    std::uint32_t collision_polygon_candidates;
    std::uint32_t input_queue_drops;
    std::uint32_t input_queue_depth;
    std::uint32_t input_edges_delivered;
    std::uint32_t actor_vertex_records;
    std::uint32_t actor_direct_strips;
    std::uint32_t actor_strip_fallbacks;
    std::uint32_t room_vertex_records;
    std::uint32_t room_direct_strips;
    std::uint32_t room_strip_fallbacks;
    std::uint32_t room_visibility_us;
    std::uint32_t room_light_selection_evaluations;
    std::uint32_t pvr_submit_calls;
    std::uint32_t pvr_submit_bytes;
};

static_assert(sizeof(DemoTelemetry) == 344U);

constexpr DemoTelemetry initial_demo_telemetry() {
    DemoTelemetry telemetry{};
    telemetry.magic = 0x52453444U;
    telemetry.version = 9U;
    telemetry.byte_size = sizeof(DemoTelemetry);
    return telemetry;
}

extern "C" {
volatile DemoTelemetry g_re4dc_demo_telemetry = initial_demo_telemetry();
}

namespace {

constexpr float kPi = 3.14159265358979323846f;
// GameCube ZNEAR is 100 source units; room coordinates are metres here.
constexpr float kNearClipDistance = 0.1f;
#if defined(RE4DC_480P)
constexpr float kScreenWidth = 640.0f;
constexpr float kScreenHeight = 480.0f;
constexpr float kHudScale = 2.0f;
#else
constexpr float kScreenWidth = 320.0f;
constexpr float kScreenHeight = 240.0f;
constexpr float kHudScale = 1.0f;
#endif
constexpr float kPlayerRadius = 0.42f;
constexpr float kPlayerHeight = 1.8f;
constexpr float kStepUp = 0.55f;
constexpr float kStepDown = 2.5f;
constexpr float kFallbackPlayerMoveSpeed = 6.0f;
constexpr float kTurnSpeed = 2.4f;
#if defined(RE4DC_SCENE_R100)
// r100_Sce_look in src/st1/r100.cpp places Leon in the opening cabin encounter.
// Room, collision, actor, camera, and light coordinates use metres (source * 0.001).
constexpr float kSpawnX = -82.910f;
constexpr float kSpawnY = 0.860f;
constexpr float kSpawnZ = -38.480f;
#if defined(RE4DC_DEMO_YAW)
constexpr float kSpawnYaw = RE4DC_DEMO_YAW;
#else
constexpr float kSpawnYaw = 1.75f;
#endif
constexpr float kGoalX = -82.910f;
constexpr float kGoalY = 0.860f;
constexpr float kGoalZ = -38.480f;
// The first Ganado and Leon placements written by r100_Sce_look after s03.
constexpr float kEnemySpawnX = -79.116f;
constexpr float kEnemySpawnY = 0.860f;
constexpr float kEnemySpawnZ = -38.890f;
constexpr float kEnemySpawnYaw = -1.39f;
// r100_002.LIT cut 0: fog end 106857 and far-play ratio 0.6. Room
// coordinates use the source 0.001 metre scale; cLightMgr shortens the gameplay
// far plane to fogEnd * (1 - farPlayRatio) + 1 in source coordinates.
constexpr float kSourceFogStartDistance = -1.089f;
constexpr float kFogEndDistance = 106.857f;
constexpr float kFarClipDistance = 42.7438f;
constexpr float kBackgroundRed = 141.0f / 255.0f;
constexpr float kBackgroundGreen = 135.0f / 255.0f;
constexpr float kBackgroundBlue = 117.0f / 255.0f;
// r100_002.LIT, cut 0. These are the source-authored lights that can affect
// the opening cabin. Positions/radii are converted from source units to
// metres; directions, colours, intensity and type are preserved.
struct SourceLight {
    std::uint8_t type;
    bool view_space;
    float x;
    float y;
    float z;
    float radius;
    float red;
    float green;
    float blue;
    float intensity;
    float nx;
    float ny;
    float nz;
    float cutoff_degrees;
    std::uint8_t source_index;
    std::uint8_t enable_mask;
};
constexpr SourceLight kSourceLights[] = {
    {5, false, 0.0f, 0.0f, 0.0f, 179.7135f, 199.0f / 255.0f,
     197.0f / 255.0f, 188.0f / 255.0f, 0.84f, -49568.6875f,
     70909.6641f, 50147.4258f, 0.0f, 0U, 0x51U},
    {5, true, 0.0f, 0.0f, 0.0f, 177.214f, 139.0f / 255.0f,
     141.0f / 255.0f, 138.0f / 255.0f, 1.0f, 99898.3125f,
     3739.939f, 2518.0386f, 0.0f, 1U, 0x47U},
    {2, false, -77.214f, 1.5135f, -36.840f, 4.8475f,
     128.0f / 255.0f, 113.0f / 255.0f, 60.0f / 255.0f, 7.18f,
     0.0f, 0.0f, 0.0f, 0.0f, 2U, 0x57U},
    {3, false, -116.726f, 1.243f, 3.824f, 3.606f,
     143.0f / 255.0f, 143.0f / 255.0f, 136.0f / 255.0f, 1.0f,
     0.3989f, -0.9074f, -0.1324f, 84.87f, 3U, 0x10U},
    {5, false, 0.0f, 0.0f, 0.0f, 179.7135f, 139.0f / 255.0f,
     137.0f / 255.0f, 125.0f / 255.0f, 0.44f, 62716.7891f,
     51430.25f, -58493.8828f, 0.0f, 4U, 0x51U},
    {5, true, 0.0f, 0.0f, 0.0f, 179.7135f, 139.0f / 255.0f,
     137.0f / 255.0f, 125.0f / 255.0f, 0.94f, -153.8383f,
     53135.0898f, 84715.0391f, 0.0f, 5U, 0x06U},
    {3, false, -85.380f, 4.043f, -37.774f, 4.5955f,
     150.0f / 255.0f, 148.0f / 255.0f, 137.0f / 255.0f, 3.57001f,
     0.187246f, -0.979425f, 0.075267f, 90.0f, 6U, 0x57U},
    {3, false, -78.237f, 3.1425f, -30.843f, 3.108f,
     94.0f / 255.0f, 92.0f / 255.0f, 80.0f / 255.0f, 1.057f,
     -0.1899f, -0.5198f, -0.8329f, 90.0f, 7U, 0x57U},
    {2, false, -74.423f, 4.6765f, -35.026f, 8.1795f,
     124.0f / 255.0f, 122.0f / 255.0f, 110.0f / 255.0f, 1.26f,
     0.0f, 0.0f, 0.0f, 0.0f, 8U, 0x57U},
    {2, false, 45.6436f, 1.220f, -9.4145f, 1.5155f,
     139.0f / 255.0f, 139.0f / 255.0f, 139.0f / 255.0f, 1.20f,
     0.0f, 0.0f, 0.0f, 0.0f, 19U, 0x10U},
};
constexpr float kSourceRoomAmbientRed = 2.0f / 255.0f;
constexpr float kSourceRoomAmbientGreen = 2.0f / 255.0f;
constexpr float kSourceRoomAmbientBlue = 2.0f / 255.0f;
constexpr float kSourceActorAmbientRed = 26.0f / 255.0f;
constexpr float kSourceActorAmbientGreen = 26.0f / 255.0f;
constexpr float kSourceActorAmbientBlue = 24.0f / 255.0f;
#else
constexpr float kSpawnX = 0.0f;
constexpr float kSpawnY = -7.98f;
constexpr float kSpawnZ = -245.0f;
constexpr float kSpawnYaw = kPi;
constexpr float kGoalX = 32.0f;
constexpr float kGoalY = -7.98f;
constexpr float kGoalZ = -284.0f;
constexpr float kEnemySpawnX = 0.0f;
constexpr float kEnemySpawnY = -7.98f;
constexpr float kEnemySpawnZ = -256.0f;
constexpr float kEnemySpawnYaw = 0.0f;
constexpr float kFarClipDistance = 35.0f;
#endif
constexpr float kFallbackEnemyMoveSpeed = 1.9f;
// em10AxeAtkCk admits the normal hatchet attack at sqrt(2890000) source
// units. Room and actor coordinates use the port's 0.001 metre scale.
constexpr float kEnemyAttackAcquireRange = 1.7f;
// The standard axe attack is motion 0x80 with sequence 0x81. Sequence bit 1
// drives em10AtkCk from source frames 50 through 72. The source motion is
// authored at 30 Hz even though the baked package may sample every other pose.
constexpr float kEnemyAttackHitStartSeconds = 50.0f / 30.0f;
constexpr float kEnemyAttackHitEndSeconds = 72.0f / 30.0f;
// Normal starts at adaptive rank 5. A connected axe swing receives the
// source default 15-frame Atk_wait after motion 0x80 completes.
constexpr float kEnemyAttackCooldownSeconds = 15.0f / 30.0f;
constexpr float kEnemyTurnSpeed = 0.15707964f * 30.0f;
constexpr std::uint32_t kAxeSweepMarkerCount = 3;
constexpr float kAxeSweepRadius = 0.250f;
// The type-0 em10 initializer registers ten active YARARE_INFO capsules.
// Bottom/top markers precede the three axe markers in the converted package.
constexpr std::uint32_t kEnemyHitCapsuleCount = 10;
constexpr std::uint32_t kEnemyHitMarkerCount = kEnemyHitCapsuleCount * 2U;
constexpr float kEnemyHitCapsuleRadii[kEnemyHitCapsuleCount] = {
    0.160f, 0.210f, 0.150f, 0.150f, 0.100f,
    0.100f, 0.170f, 0.170f, 0.120f, 0.120f};
// pl_handgun fires from player part 10 at local (234.5, -24, 38.33),
// along the part's local -X axis. Four baked markers recover the animated
// muzzle and its three source-space basis vectors on SH-4.
constexpr std::uint32_t kPlayerFireMarkerCount = 4;
// cPlayer::init1 registers five YARARE_INFO capsules on source parts
// 2, 3, 5, 0x13, and 0x17. The converter appends bottom/top markers for
// each capsule after Leon's indexed render vertices.
constexpr std::uint32_t kPlayerHitCapsuleCount = 5;
constexpr std::uint32_t kPlayerHitMarkerCount = kPlayerHitCapsuleCount * 2U;
constexpr float kPlayerHitCapsuleRadii[kPlayerHitCapsuleCount] = {
    0.200f, 0.210f, 0.120f, 0.170f, 0.170f};
constexpr float kHandgunRayLength = 50.0f;
constexpr float kHandgunSpread = 0.200f;
constexpr int kMagazineSize = 6;
// PlayerLifeReset gives Leon 1200 life. Em10AtkTbl[0] gives the type-0 r100
// hatchet Ganado 380 damage; rank 5 applies a 1.0 LifeDownSet2 multiplier.
constexpr int kPlayerMaxHealth = 1200;
constexpr int kEnemyAttackDamage = 380;
constexpr std::uint32_t kPlayerIdleClip = 0;
constexpr std::uint32_t kPlayerWalkClip = 1;
// pl_handgun's cMot3 triplets. Positive pitch blends the level pose toward
// the first motion, while negative pitch blends it toward the third motion.
constexpr std::uint32_t kPlayerAimPositiveClip = 2;
constexpr std::uint32_t kPlayerAimLevelClip = 3;
constexpr std::uint32_t kPlayerAimNegativeClip = 4;
constexpr std::uint32_t kPlayerFirePositiveClip = 5;
constexpr std::uint32_t kPlayerFireLevelClip = 6;
constexpr std::uint32_t kPlayerFireNegativeClip = 7;
constexpr std::uint32_t kPlayerReloadClip = 8;
constexpr std::uint32_t kPlayerHitLeftClip = 9;
constexpr std::uint32_t kPlayerDeathClip = 10;
#if defined(RE4DC_SCENE_R100)
// R100Init creates this exact id-0x12 Ganado with 500 HP. Weapon 1 uses the
// em10 base value 150 at the starting 0.9 power multiplier: 135 body damage.
// Preserve those source values even while the wider enemy state machine is
// still being integrated.
constexpr int kEnemyMaxHealth = 500;
constexpr int kHandgunBodyDamage = 135;
#else
constexpr int kEnemyMaxHealth = 3;
constexpr int kHandgunBodyDamage = 1;
#endif
constexpr std::uint64_t kSimulationStepUs = 33333U;
// The presentation build deliberately favors source-detail over frame rate.
// Keep the 30 Hz source simulation current through a sub-2-fps render while
// retaining a finite catch-up bound for pathological stalls.
constexpr unsigned kMaxSimulationCatchupTicks = 24U;
constexpr float kSimulationDeltaSeconds = 1.0f / 30.0f;
// cObjMauser::moveReload refills the starting handgun at motion frame 44 and
// ejects its stripper clip at frame 55. Keep the action locked through that
// second source event instead of using the prototype's one-second timer.
constexpr float kStartingReloadRefillSeconds = 44.0f / 30.0f;
constexpr float kStartingReloadFinishSeconds = 55.0f / 30.0f;
// PlShotFrameTbl[1][0] is 14 for the starting handgun. pl_handgun returns
// from fire step 1 when motion frame (14 - 2) is crossed; a held fire input
// may then enter fire step 0 again.
constexpr float kStartingHandgunShotReadySeconds = 12.0f / 30.0f;

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
    float yaw = kSpawnYaw;
    std::uint32_t wall_hits = 0;
    std::uint32_t completed_loops = 0;
    std::uint32_t animation_clip = 0;
    float animation_frame = 0.0f;
    int health = kPlayerMaxHealth;
    int ammo = kMagazineSize;
    float reload_seconds = 0.0f;
    bool reload_refilled = false;
    float fire_animation_seconds = 0.0f;
    float aim_pitch = 0.0f;
    float aim_repeat = 0.0f;
    bool aiming = false;
    bool hit_reaction = false;
    bool dead = false;
    bool death_complete = false;
    std::uint32_t damage_voice_cycle = 0;
};

struct Enemy {
    float x = kEnemySpawnX;
    float y = kEnemySpawnY;
    float z = kEnemySpawnZ;
    float yaw = kEnemySpawnYaw;
    EnemyState state = EnemyState::Chase;
    int health = kEnemyMaxHealth;
    std::uint32_t animation_clip = 1;
    float animation_frame = 0.0f;
    float attack_cooldown_seconds = 0.0f;
    bool attack_landed = false;
    bool attack_sound_played = false;
    bool hit_voice_played = false;
};

struct DemoAudio {
    sfxhnd_t fire_0 = SFXHND_INVALID;
    sfxhnd_t fire_2 = SFXHND_INVALID;
    sfxhnd_t reload_16 = SFXHND_INVALID;
    sfxhnd_t enemy_swing_3d = SFXHND_INVALID;
    sfxhnd_t enemy_body_hit_0c = SFXHND_INVALID;
    sfxhnd_t enemy_damage_voice_47 = SFXHND_INVALID;
    sfxhnd_t enemy_death_voice_16 = SFXHND_INVALID;
    sfxhnd_t player_damage_voice[3] = {
        SFXHND_INVALID, SFXHND_INVALID, SFXHND_INVALID};
    sfxhnd_t player_death_voice_13 = SFXHND_INVALID;
    bool initialized = false;
};

struct Input {
    float move = 0.0f;
    float turn = 0.0f;
    float aim_pitch_stick = 0.0f;
    int aim_pitch_dpad = 0;
    bool aim = false;
    bool fire = false;
    bool reload = false;
    bool restart = false;
    bool exit = false;
};

struct TickInput {
    Input input{};
    bool fire_pressed = false;
    bool reload_pressed = false;
    bool restart_pressed = false;
    bool exit_pressed = false;
};

struct TimedInput {
    std::uint64_t timestamp_us = 0U;
    Input input{};
};

constexpr std::uint32_t kInputQueueCapacity = 128U;

struct InputService {
    mutex_t mutex{};
    TimedInput queue[kInputQueueCapacity]{};
    std::uint32_t head = 0U;
    std::uint32_t count = 0U;
    Input producer_state{};
    Input consumer_state{};
    bool producer_valid = false;
    bool running = false;
    kthread_t* thread = nullptr;
    std::uint64_t samples = 0U;
    std::uint64_t last_sample_us = 0U;
    std::uint64_t sample_gap_us = 0U;
    std::uint64_t sample_gap_us_max = 0U;
    std::uint64_t queue_drops = 0U;
    std::uint64_t edges_delivered = 0U;
};

struct InputServiceSnapshot {
    std::uint64_t samples = 0U;
    std::uint64_t sample_gap_us = 0U;
    std::uint64_t sample_gap_us_max = 0U;
    std::uint64_t queue_drops = 0U;
    std::uint64_t edges_delivered = 0U;
    std::uint32_t queue_depth = 0U;
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
    std::uint32_t tick = 0;
};

struct FrameStats {
    std::uint32_t groups = 0;
    std::uint32_t triangles = 0;
    std::uint32_t transformed_vertices = 0;
    std::uint32_t character_triangles = 0;
    std::uint64_t wait_us = 0;
    std::uint64_t submit_us = 0;
    std::uint64_t finish_us = 0;
    std::uint64_t total_us = 0;
    std::uint64_t actor_pose_us = 0;
    std::uint64_t actor_normals_us = 0;
    std::uint64_t actor_lighting_us = 0;
    std::uint64_t opaque_room_us = 0;
    std::uint64_t opaque_actor_us = 0;
    std::uint64_t translucent_room_us = 0;
    std::uint64_t translucent_actor_hud_us = 0;
    std::uint64_t room_visibility_us = 0;
    std::uint32_t room_index_references = 0;
    std::uint32_t room_cache_hits = 0;
    std::uint32_t room_cache_misses = 0;
    std::uint32_t room_light_evaluations = 0;
    std::uint32_t room_near_trivial_accepts = 0;
    std::uint32_t room_near_trivial_rejects = 0;
    std::uint32_t room_near_crossings = 0;
    std::uint32_t character_vertex_records = 0;
    std::uint32_t character_direct_strips = 0;
    std::uint32_t character_strip_fallbacks = 0;
    std::uint32_t room_vertex_records = 0;
    std::uint32_t room_direct_strips = 0;
    std::uint32_t room_strip_fallbacks = 0;
    std::uint32_t room_light_selection_evaluations = 0;
    std::uint32_t pvr_submit_calls = 0;
    std::uint32_t pvr_submit_bytes = 0;
};

void submit_pvr(FrameStats& stats, const void* data, std::size_t byte_count) {
    pvr_prim(data, byte_count);
    ++stats.pvr_submit_calls;
    stats.pvr_submit_bytes += static_cast<std::uint32_t>(byte_count);
}

void begin_pvr_packet(pvr_vertex_t* commands, std::uint32_t& command_count,
                      const pvr_poly_hdr_t& header) {
    static_assert(sizeof(pvr_vertex_t) == sizeof(pvr_poly_hdr_t));
    std::memcpy(commands, &header, sizeof(header));
    command_count = 1U;
}

std::uint32_t saturate_u32(std::uint64_t value) {
    return static_cast<std::uint32_t>(
        std::min<std::uint64_t>(value, 0xffffffffU));
}

struct ProjectedVertex {
    float x;
    float y;
    float z;
    float world_x;
    float world_y;
    float world_z;
    float depth;
};

struct PreparedPoseMatrix {
    float linear[9];
    float translation[3];
};

struct RenderVertex {
    ProjectedVertex position;
    float u;
    float v;
    float light_red;
    float light_green;
    float light_blue;
    std::uint32_t offset_color;
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
    input.aim = state->rtrig > 24 || (state->buttons & CONT_Y) != 0;
    input.turn = analog_axis(state->joyx);
    input.move = -analog_axis(state->joyy);
    if((state->buttons & CONT_DPAD_LEFT) != 0) {
        input.turn = -1.0f;
    } else if((state->buttons & CONT_DPAD_RIGHT) != 0) {
        input.turn = 1.0f;
    }
    if(input.aim) {
        // Keep the signed raw source range for PlWepLockCtrl's acceleration
        // formula. Dreamcast and GameCube both report roughly -128..127.
        input.aim_pitch_stick = static_cast<float>(state->joyy);
        input.move = 0.0f;
        if((state->buttons & CONT_DPAD_UP) != 0) {
            input.aim_pitch_dpad = 1;
        } else if((state->buttons & CONT_DPAD_DOWN) != 0) {
            input.aim_pitch_dpad = -1;
        }
    } else if((state->buttons & CONT_DPAD_UP) != 0) {
        input.move = 1.0f;
    } else if((state->buttons & CONT_DPAD_DOWN) != 0) {
        input.move = -1.0f;
    }
    input.fire = (state->buttons & CONT_A) != 0;
    input.reload = (state->buttons & CONT_X) != 0;
    input.restart = (state->buttons & CONT_B) != 0;
    input.exit = (state->buttons & CONT_START) != 0;
    return input;
}

bool input_equal(const Input& left, const Input& right) {
    return left.move == right.move && left.turn == right.turn &&
           left.aim_pitch_stick == right.aim_pitch_stick &&
           left.aim_pitch_dpad == right.aim_pitch_dpad &&
           left.aim == right.aim && left.fire == right.fire &&
           left.reload == right.reload && left.restart == right.restart &&
           left.exit == right.exit;
}

void input_service_record(InputService& service, const Input& input,
                          std::uint64_t timestamp_us) {
    mutex_lock(&service.mutex);
    ++service.samples;
    if(service.last_sample_us != 0U) {
        service.sample_gap_us = timestamp_us - service.last_sample_us;
        service.sample_gap_us_max = std::max(
            service.sample_gap_us_max, service.sample_gap_us);
    }
    service.last_sample_us = timestamp_us;
    if(!service.producer_valid ||
       !input_equal(input, service.producer_state)) {
        if(service.count == kInputQueueCapacity) {
            service.head = (service.head + 1U) % kInputQueueCapacity;
            --service.count;
            ++service.queue_drops;
        }
        const std::uint32_t tail =
            (service.head + service.count) % kInputQueueCapacity;
        service.queue[tail] = {timestamp_us, input};
        ++service.count;
        service.producer_state = input;
        service.producer_valid = true;
    }
    mutex_unlock(&service.mutex);
}

void* input_service_thread(void* parameter) {
    auto& service = *static_cast<InputService*>(parameter);
    while(true) {
        mutex_lock(&service.mutex);
        const bool running = service.running;
        mutex_unlock(&service.mutex);
        if(!running) {
            break;
        }
        input_service_record(service, read_input(), timer_us_gettime64());
        thd_sleep(4U);
    }
    return nullptr;
}

bool start_input_service(InputService& service) {
    if(mutex_init(&service.mutex, MUTEX_TYPE_NORMAL) != 0) {
        return false;
    }
    service.running = true;
    input_service_record(service, read_input(), timer_us_gettime64());
    service.thread = thd_create(false, input_service_thread, &service);
    if(service.thread == nullptr) {
        service.running = false;
        mutex_destroy(&service.mutex);
        return false;
    }
    return true;
}

void stop_input_service(InputService& service) {
    if(service.thread == nullptr) {
        return;
    }
    mutex_lock(&service.mutex);
    service.running = false;
    mutex_unlock(&service.mutex);
    thd_join(service.thread, nullptr);
    service.thread = nullptr;
    mutex_destroy(&service.mutex);
}

TickInput consume_input_until(InputService& service,
                              std::uint64_t timestamp_us) {
    TickInput result{};
    Input fire_input{};
    bool have_fire_input = false;
    mutex_lock(&service.mutex);
    while(service.count != 0U &&
          service.queue[service.head].timestamp_us <= timestamp_us) {
        const Input next = service.queue[service.head].input;
        service.head = (service.head + 1U) % kInputQueueCapacity;
        --service.count;
        if(next.fire && !service.consumer_state.fire &&
           !result.fire_pressed) {
            result.fire_pressed = true;
            fire_input = next;
            have_fire_input = true;
        }
        result.reload_pressed |=
            next.reload && !service.consumer_state.reload;
        result.restart_pressed |=
            next.restart && !service.consumer_state.restart;
        result.exit_pressed |= next.exit && !service.consumer_state.exit;
        service.consumer_state = next;
    }
    result.input = service.consumer_state;
    if(have_fire_input) {
        result.input.aim = fire_input.aim;
        result.input.aim_pitch_stick = fire_input.aim_pitch_stick;
        result.input.aim_pitch_dpad = fire_input.aim_pitch_dpad;
        result.input.fire = true;
    }
    service.edges_delivered +=
        static_cast<std::uint64_t>(result.fire_pressed) +
        static_cast<std::uint64_t>(result.reload_pressed) +
        static_cast<std::uint64_t>(result.restart_pressed) +
        static_cast<std::uint64_t>(result.exit_pressed);
    mutex_unlock(&service.mutex);
    return result;
}

void discard_input_until(InputService& service, std::uint64_t timestamp_us) {
    mutex_lock(&service.mutex);
    while(service.count != 0U &&
          service.queue[service.head].timestamp_us <= timestamp_us) {
        service.consumer_state = service.queue[service.head].input;
        service.head = (service.head + 1U) % kInputQueueCapacity;
        --service.count;
    }
    mutex_unlock(&service.mutex);
}

InputServiceSnapshot input_service_snapshot(InputService& service) {
    InputServiceSnapshot snapshot{};
    mutex_lock(&service.mutex);
    snapshot.samples = service.samples;
    snapshot.sample_gap_us = service.sample_gap_us;
    snapshot.sample_gap_us_max = service.sample_gap_us_max;
    snapshot.queue_drops = service.queue_drops;
    snapshot.edges_delivered = service.edges_delivered;
    snapshot.queue_depth = service.count;
    mutex_unlock(&service.mutex);
    return snapshot;
}

bool file_exists(const char* path) {
    const file_t file = fs_open(path, O_RDONLY);
    if(file == FILEHND_INVALID) {
        return false;
    }
    fs_close(file);
    return true;
}

bool load_demo_audio(DemoAudio& audio) {
    constexpr const char* fire_0_path = "/rd/wep02-fire-0.wav";
    constexpr const char* fire_2_path = "/rd/wep02-fire-2.wav";
    constexpr const char* reload_path = "/rd/wep02-reload-16.wav";
    constexpr const char* enemy_swing_path = "/rd/em12-swing-3d.wav";
    constexpr const char* enemy_hit_path = "/rd/em12-body-hit-0c.wav";
    constexpr const char* enemy_damage_voice_path =
        "/rd/em12-damage-voice-47.wav";
    constexpr const char* enemy_death_voice_path =
        "/rd/em12-death-voice-16.wav";
    constexpr const char* player_damage_voice_paths[] = {
        "/rd/pl00-damage-voice-09.wav",
        "/rd/pl00-damage-voice-10.wav",
        "/rd/pl00-damage-voice-11.wav",
    };
    constexpr const char* player_death_voice_path =
        "/rd/pl00-death-voice-13.wav";
    const bool fire_0_exists = file_exists(fire_0_path);
    const bool fire_2_exists = file_exists(fire_2_path);
    const bool reload_exists = file_exists(reload_path);
    const bool enemy_swing_exists = file_exists(enemy_swing_path);
    const bool enemy_hit_exists = file_exists(enemy_hit_path);
    const bool enemy_damage_voice_exists =
        file_exists(enemy_damage_voice_path);
    const bool enemy_death_voice_exists = file_exists(enemy_death_voice_path);
    const bool player_damage_voice_exists[] = {
        file_exists(player_damage_voice_paths[0]),
        file_exists(player_damage_voice_paths[1]),
        file_exists(player_damage_voice_paths[2]),
    };
    const bool player_death_voice_exists = file_exists(player_death_voice_path);
    const bool any_player_reaction_audio =
        player_damage_voice_exists[0] || player_damage_voice_exists[1] ||
        player_damage_voice_exists[2] || player_death_voice_exists;
    if(!fire_0_exists && !fire_2_exists && !reload_exists &&
       !enemy_swing_exists && !enemy_hit_exists &&
       !enemy_damage_voice_exists && !enemy_death_voice_exists &&
       !any_player_reaction_audio) {
        std::printf("re4dc-room: source combat audio not packaged\n");
        return true;
    }
    const bool any_weapon_audio = fire_0_exists || fire_2_exists ||
                                  reload_exists;
    if(any_weapon_audio &&
       (!fire_0_exists || !fire_2_exists || !reload_exists)) {
        std::printf("re4dc-room: incomplete source weapon audio package\n");
        return false;
    }
    const bool any_enemy_reaction_audio =
        enemy_hit_exists || enemy_damage_voice_exists ||
        enemy_death_voice_exists;
    if(any_enemy_reaction_audio &&
       (!enemy_hit_exists || !enemy_damage_voice_exists ||
        !enemy_death_voice_exists)) {
        std::printf("re4dc-room: incomplete enemy reaction audio package\n");
        return false;
    }
    if(any_player_reaction_audio &&
       (!player_damage_voice_exists[0] || !player_damage_voice_exists[1] ||
        !player_damage_voice_exists[2] || !player_death_voice_exists)) {
        std::printf("re4dc-room: incomplete player reaction audio package\n");
        return false;
    }
    snd_init();
    audio.initialized = true;
    if(any_weapon_audio) {
        audio.fire_0 = snd_sfx_load(fire_0_path);
        audio.fire_2 = snd_sfx_load(fire_2_path);
        audio.reload_16 = snd_sfx_load(reload_path);
    }
    if(enemy_swing_exists) {
        audio.enemy_swing_3d = snd_sfx_load(enemy_swing_path);
    }
    if(any_enemy_reaction_audio) {
        audio.enemy_body_hit_0c = snd_sfx_load(enemy_hit_path);
        audio.enemy_damage_voice_47 =
            snd_sfx_load(enemy_damage_voice_path);
        audio.enemy_death_voice_16 =
            snd_sfx_load(enemy_death_voice_path);
    }
    if(any_player_reaction_audio) {
        for(unsigned index = 0; index < 3; ++index) {
            audio.player_damage_voice[index] =
                snd_sfx_load(player_damage_voice_paths[index]);
        }
        audio.player_death_voice_13 = snd_sfx_load(player_death_voice_path);
    }
    if((any_weapon_audio &&
        (audio.fire_0 == SFXHND_INVALID ||
         audio.fire_2 == SFXHND_INVALID ||
         audio.reload_16 == SFXHND_INVALID)) ||
       (enemy_swing_exists &&
        audio.enemy_swing_3d == SFXHND_INVALID) ||
       (any_enemy_reaction_audio &&
        (audio.enemy_body_hit_0c == SFXHND_INVALID ||
         audio.enemy_damage_voice_47 == SFXHND_INVALID ||
         audio.enemy_death_voice_16 == SFXHND_INVALID)) ||
       (any_player_reaction_audio &&
        (audio.player_damage_voice[0] == SFXHND_INVALID ||
         audio.player_damage_voice[1] == SFXHND_INVALID ||
         audio.player_damage_voice[2] == SFXHND_INVALID ||
         audio.player_death_voice_13 == SFXHND_INVALID))) {
        std::printf("re4dc-room: source combat audio load failed\n");
        snd_sfx_unload_all();
        snd_shutdown();
        audio = DemoAudio{};
        return false;
    }
    std::printf("re4dc-room: source combat cues loaded "
                "fire=%d reload=%d enemy_swing=%d reactions=%d\n",
                any_weapon_audio ? 1 : 0, reload_exists ? 1 : 0,
                enemy_swing_exists ? 1 : 0,
                any_enemy_reaction_audio ? 1 : 0);
    std::printf("re4dc-room: source player reactions=%d\n",
                any_player_reaction_audio ? 1 : 0);
    return true;
}
void release_demo_audio(DemoAudio& audio) {
    if(!audio.initialized) {
        return;
    }
    snd_sfx_unload_all();
    snd_shutdown();
    audio = DemoAudio{};
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

enum class CollisionCandidateGroup : std::uint8_t {
    Floors,
    Walls,
};

constexpr std::uint32_t kCollisionPolygonCapacity = 0x2000U;
std::uint16_t g_collision_candidates[kCollisionPolygonCapacity];
std::uint8_t g_collision_visited[kCollisionPolygonCapacity / 8U];

struct CollisionRuntimeStats {
    std::uint32_t queries = 0U;
    std::uint32_t block_tests = 0U;
    std::uint32_t polygon_candidates = 0U;
};

CollisionRuntimeStats g_collision_runtime_stats;

struct CollisionBlockQuery {
    re4dc::collision::Vec3 start;
    re4dc::collision::Vec3 end;
    float radius;
    bool swept_sphere;
};

bool collision_line_cross_xz(const re4dc::collision::Vec3& a,
                             const re4dc::collision::Vec3& b,
                             const re4dc::collision::Vec3& c,
                             const re4dc::collision::Vec3& d) {
    const float denominator =
        (b.x - a.x) * (d.z - c.z) - (b.z - a.z) * (d.x - c.x);
    if(denominator == 0.0f) {
        return false;
    }
    const float ax = a.x - c.x;
    const float az = a.z - c.z;
    const float t = az * (d.x - c.x) - ax * (d.z - c.z);
    const float s = az * (b.x - a.x) - ax * (b.z - a.z);
    const auto within = [denominator](float value) {
        return denominator >= 0.0f
            ? value >= 0.0f && value <= denominator
            : value <= 0.0f && value >= denominator;
    };
    return within(t) && within(s);
}

bool collision_block_line_overlap(const re4dc::collision::Block& block,
                                  const CollisionBlockQuery& query) {
    const float mid_x = (query.start.x + query.end.x) * 0.5f;
    const float mid_z = (query.start.z + query.end.z) * 0.5f;
    const float direction_x = query.start.x - mid_x;
    const float direction_z = query.start.z - mid_z;
    const float abs_direction_x = std::fabs(direction_x);
    const float abs_direction_z = std::fabs(direction_z);
    const float dx = (mid_x - block.minimum[0]) - block.size[0] * 0.5f;
    const float dz = (mid_z - block.minimum[2]) - block.size[2] * 0.5f;
    if(std::fabs(dx) > abs_direction_x + block.size[0] * 0.5f ||
       std::fabs(dz) > abs_direction_z + block.size[2] * 0.5f) {
        return false;
    }
    return std::fabs(dx * direction_z - dz * direction_x) <=
           (block.size[0] * abs_direction_z +
            block.size[2] * abs_direction_x) * 0.5f;
}

bool collision_block_sphere_overlap(const re4dc::collision::Block& block,
                                    const CollisionBlockQuery& query) {
    const float x0 = block.minimum[0];
    const float z0 = block.minimum[2];
    const float x1 = x0 + block.size[0] + query.radius;
    const float z1 = z0 + block.size[2] + query.radius;
    const float center_x = (query.start.x + query.end.x) * 0.5f;
    const float center_z = (query.start.z + query.end.z) * 0.5f;
    const float half_x = std::fabs(query.start.x - query.end.x) * 0.5f +
                         query.radius;
    const float half_z = std::fabs(query.start.z - query.end.z) * 0.5f +
                         query.radius;
    if(x0 + block.size[0] < center_x - half_x ||
       x0 - block.size[0] > center_x + half_x ||
       z0 + block.size[2] < center_z - half_z ||
       z0 - block.size[2] > center_z + half_z) {
        return false;
    }
    const auto inside = [&](const re4dc::collision::Vec3& point) {
        return point.x >= x0 - query.radius && point.x <= x1 &&
               point.z >= z0 - query.radius && point.z <= z1;
    };
    if(inside(query.start) || inside(query.end)) {
        return true;
    }
    re4dc::collision::Vec3 corner_a{x0, 0.0f, z0};
    re4dc::collision::Vec3 corner_b{x1, 0.0f, z0};
    if(collision_line_cross_xz(query.start, query.end,
                               corner_a, corner_b)) {
        return true;
    }
    corner_a.z = corner_b.z = z1;
    if(collision_line_cross_xz(query.start, query.end,
                               corner_a, corner_b)) {
        return true;
    }
    corner_a.z = z0;
    corner_b.x = x0;
    if(collision_line_cross_xz(query.start, query.end,
                               corner_a, corner_b)) {
        return true;
    }
    corner_a.x = corner_b.x = x1;
    return collision_line_cross_xz(query.start, query.end,
                                    corner_a, corner_b);
}

void collect_collision_block_chain(
    const re4dc::collision::Package& collision, std::uint32_t block_index,
    const CollisionBlockQuery& query, CollisionCandidateGroup group,
    std::uint32_t& block_visits, std::uint32_t& candidate_count) {
    const auto* hierarchy = collision.hierarchy();
    const auto* blocks = collision.blocks();
    const auto* indices = collision.block_indices();
    while(block_index != re4dc::collision::kNoBlock &&
          block_visits < hierarchy->block_count) {
        ++block_visits;
        const auto& block = blocks[block_index];
        const bool overlap = query.swept_sphere
            ? collision_block_sphere_overlap(block, query)
            : collision_block_line_overlap(block, query);
        if(overlap) {
            if((block.flags & 1U) != 0U) {
                collect_collision_block_chain(
                    collision, block.child, query, group, block_visits,
                    candidate_count);
            } else {
                const std::uint32_t first = group == CollisionCandidateGroup::Walls
                    ? static_cast<std::uint32_t>(block.floor_count) +
                          block.slope_count
                    : 0U;
                const std::uint32_t end = group == CollisionCandidateGroup::Walls
                    ? first + block.wall_count
                    : static_cast<std::uint32_t>(block.floor_count) +
                          block.slope_count;
                for(std::uint32_t local = first; local < end; ++local) {
                    const std::uint16_t polygon =
                        indices[block.first_polygon + local];
                    const std::uint8_t bit =
                        static_cast<std::uint8_t>(1U << (polygon & 7U));
                    if((g_collision_visited[polygon >> 3U] & bit) != 0U) {
                        continue;
                    }
                    g_collision_visited[polygon >> 3U] |= bit;
                    g_collision_candidates[candidate_count++] = polygon;
                }
            }
        }
        block_index = block.next;
    }
}

std::uint32_t collect_collision_candidates(
    const re4dc::collision::Package& collision,
    const re4dc::collision::Vec3& start,
    const re4dc::collision::Vec3& end, float radius,
    CollisionCandidateGroup group, bool swept_sphere = false) {
    const std::uint32_t first = group == CollisionCandidateGroup::Walls
        ? collision.header().floor_count + collision.header().slope_count
        : 0U;
    const std::uint32_t end_index = group == CollisionCandidateGroup::Walls
        ? collision.header().polygon_count
        : collision.header().floor_count + collision.header().slope_count;
    ++g_collision_runtime_stats.queries;
    if(!collision.has_hierarchy() ||
       collision.header().polygon_count > kCollisionPolygonCapacity) {
        std::uint32_t count = 0U;
        for(std::uint32_t polygon = first; polygon < end_index; ++polygon) {
            g_collision_candidates[count++] =
                static_cast<std::uint16_t>(polygon);
        }
        g_collision_runtime_stats.polygon_candidates += count;
        return count;
    }
    std::memset(g_collision_visited, 0, sizeof(g_collision_visited));
    std::uint32_t block_visits = 0U;
    std::uint32_t candidate_count = 0U;
    collect_collision_block_chain(
        collision, 0U, {start, end, radius, swept_sphere}, group,
        block_visits, candidate_count);
    g_collision_runtime_stats.block_tests += block_visits;
    g_collision_runtime_stats.polygon_candidates += candidate_count;
    return candidate_count;
}

bool find_floor(const re4dc::collision::Package& collision, float x, float z,
                float reference_y, float& floor_y) {
    const auto* vertices = collision.vertices();
    const auto* polygons = collision.polygons();
    const re4dc::collision::Vec3 start{x, reference_y + kStepUp, z};
    const re4dc::collision::Vec3 end{x, reference_y - kStepDown, z};
    const std::uint32_t count = collect_collision_candidates(
        collision, start, end, 0.0f, CollisionCandidateGroup::Floors);
    float best_delta = 1.0e9f;
    bool found = false;
    for(std::uint32_t candidate_index = 0; candidate_index < count;
        ++candidate_index) {
        const std::uint32_t index = g_collision_candidates[candidate_index];
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

std::uint32_t resolve_actor_walls(
    const re4dc::collision::Package& collision, float& actor_x, float actor_y,
    float& actor_z, float actor_radius, float actor_height) {
    const auto* vertices = collision.vertices();
    const auto* normals = collision.normals();
    const auto* polygons = collision.polygons();
    std::uint32_t hits = 0;
    for(unsigned pass = 0; pass < 3; ++pass) {
        bool moved = false;
        const re4dc::collision::Vec3 position{actor_x, actor_y, actor_z};
        const std::uint32_t candidate_count = collect_collision_candidates(
            collision, position, position, actor_radius,
            CollisionCandidateGroup::Walls, true);
        for(std::uint32_t candidate_index = 0;
            candidate_index < candidate_count; ++candidate_index) {
            const std::uint32_t index =
                g_collision_candidates[candidate_index];
            const auto& polygon = polygons[index];
            const auto& a = vertices[polygon.vertex[0]];
            const auto& b = vertices[polygon.vertex[1]];
            const auto& c = vertices[polygon.vertex[2]];
            const float wall_min_y = std::min({a.y, b.y, c.y});
            const float wall_max_y = std::max({a.y, b.y, c.y});
            if(actor_y + actor_height < wall_min_y || actor_y > wall_max_y) {
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
                ((actor_x - start.x) * sx + (actor_z - start.z) * sz) /
                    longest,
                0.0f, 1.0f);
            const float nearest_x = start.x + projection * sx;
            const float nearest_z = start.z + projection * sz;
            float dx = actor_x - nearest_x;
            float dz = actor_z - nearest_z;
            const float distance_squared = dx * dx + dz * dz;
            if(distance_squared >= actor_radius * actor_radius) {
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
            const float correction = (actor_radius - distance) / distance;
            actor_x += dx * correction;
            actor_z += dz * correction;
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
                   const Input& input, float move_speed,
                   float delta_seconds) {
    player.aiming = input.aim && !player.dead && !player.hit_reaction;
    if(player.dead || player.hit_reaction) {
        return;
    }
    if(player.aiming) {
        // PlWepLockCtrl ramps repCtr from 1 through 7 while either main-stick
        // axis is held. KOS reports Y with the opposite sign to the source
        // GameCube pad, so negate it before applying the source equation.
        if(std::fabs(input.aim_pitch_stick) > 0.0f ||
           std::fabs(input.turn) > 0.0f) {
            player.aim_repeat = std::min(7.0f, player.aim_repeat + 1.0f);
        } else {
            player.aim_repeat = 0.0f;
        }
        float pitch_delta =
            static_cast<float>(input.aim_pitch_dpad) * 0.035f;
        pitch_delta -= input.aim_pitch_stick * player.aim_repeat *
                       0.15f / 200.0f / 10.0f;
        if(player.aim_pitch > 0.0f) {
            pitch_delta *= 0.8f;
        }
        player.aim_pitch = std::clamp(
            player.aim_pitch + pitch_delta, -1.0f, 1.0f);
    } else {
        player.aim_repeat = 0.0f;
    }
    player.yaw += input.turn * kTurnSpeed * delta_seconds;
    const float movement = player.aiming ? 0.0f : input.move;
    const float old_x = player.x;
    const float old_z = player.z;
    player.x += std::sin(player.yaw) * movement * move_speed * delta_seconds;
    player.z += std::cos(player.yaw) * movement * move_speed * delta_seconds;
    player.wall_hits += resolve_actor_walls(
        collision, player.x, player.y, player.z, kPlayerRadius,
        kPlayerHeight);
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
    std::uint32_t desired_clip = kPlayerIdleClip;
    bool loop = true;
    if(player.dead) {
        desired_clip = kPlayerDeathClip;
        loop = false;
    } else if(player.hit_reaction) {
        desired_clip = kPlayerHitLeftClip;
        loop = false;
    } else if(player.reload_seconds > 0.0f) {
        desired_clip = kPlayerReloadClip;
        loop = false;
    } else if(player.fire_animation_seconds > 0.0f) {
        desired_clip = kPlayerFireLevelClip;
        loop = false;
        player.fire_animation_seconds = std::max(
            0.0f, player.fire_animation_seconds - delta_seconds);
    } else if(player.aiming) {
        desired_clip = kPlayerAimLevelClip;
    } else if(std::fabs(input.move) > 0.05f) {
        desired_clip = kPlayerWalkClip;
    }
    if(player.animation_clip != desired_clip) {
        player.animation_clip = desired_clip;
        player.animation_frame = 0.0f;
    }
    const auto& clip = character.clips()[player.animation_clip];
    player.animation_frame += clip.frames_per_second * delta_seconds;
    if(loop) {
        while(player.animation_frame >= static_cast<float>(clip.frame_count)) {
            player.animation_frame -= static_cast<float>(clip.frame_count);
        }
    } else {
        player.animation_frame = std::min(
            player.animation_frame, static_cast<float>(clip.frame_count - 1U));
    }
    if(player.hit_reaction &&
       player.animation_frame >= static_cast<float>(clip.frame_count - 1U)) {
        player.hit_reaction = false;
    }
    if(player.dead &&
       player.animation_frame >= static_cast<float>(clip.frame_count - 1U)) {
        player.death_complete = true;
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
#if defined(RE4DC_SCENE_R100)
    // A 30-second fixed-tick presentation trace for visual capture. The normal
    // package omits autoplay.flag and remains fully manual. Keep this trace
    // source-neutral: it only exercises the same public controls a player uses.
    (void)delta_seconds;
    const std::uint32_t tick = autoplay.tick++;
    if(tick >= 900U) {
        input.restart = true;
        autoplay.tick = 0;
        return input;
    }
    if(player.dead) {
        input.restart = true;
        autoplay.tick = 0;
        autoplay.observed_death = true;
        return input;
    }
    if(enemy.state != EnemyState::Dead && tick < 150U) {
        input.aim = true;
        const float target_yaw = std::atan2(enemy.x - player.x,
                                            enemy.z - player.z);
        input.turn = std::clamp(wrap_angle(target_yaw - player.yaw) * 2.0f,
                                -1.0f, 1.0f);
        input.fire = tick == 6U || tick == 20U || tick == 34U ||
                     tick == 48U || tick == 62U;
    } else if(tick >= 150U && tick < 360U) {
        // Hold the source level handgun-ready camera for a readable result
        // shot. Pitch coverage belongs in the technical replay, not footage.
        input.aim = true;
    }
    if(tick == 76U) {
        input.reload = true;
    }
    return input;
#else
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
#endif
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

void move_enemy_forward(Enemy& enemy,
                        const re4dc::collision::Package& collision,
                        float distance) {
    const float old_x = enemy.x;
    const float old_z = enemy.z;
    enemy.x += std::sin(enemy.yaw) * distance;
    enemy.z += std::cos(enemy.yaw) * distance;
    resolve_actor_walls(collision, enemy.x, enemy.y, enemy.z,
                        kPlayerRadius, kPlayerHeight);
    float floor_y = enemy.y;
    if(find_floor(collision, enemy.x, enemy.z, enemy.y, floor_y)) {
        enemy.y = floor_y;
    } else {
        enemy.x = old_x;
        enemy.z = old_z;
    }
}

bool segment_blocked_by_wall(const re4dc::collision::Package& collision,
                             const re4dc::collision::Vec3& start,
                             const re4dc::collision::Vec3& end);

bool source_route_midpoint_has_floor(
    const re4dc::collision::Package& collision,
    const re4dc::collision::Vec3& position) {
    const auto* vertices = collision.vertices();
    const auto* polygons = collision.polygons();
    const std::uint32_t count =
        collision.header().floor_count + collision.header().slope_count;
    float highest = -1.0e9f;
    for(std::uint32_t index = 0; index < count; ++index) {
        const auto& polygon = polygons[index];
        float candidate = 0.0f;
        if(!projected_floor_height(vertices[polygon.vertex[0]],
                                   vertices[polygon.vertex[1]],
                                   vertices[polygon.vertex[2]],
                                   position.x, position.z, candidate) ||
           candidate > position.y + 0.6f ||
           candidate < position.y - 100.0f) {
            continue;
        }
        highest = std::max(highest, candidate);
    }
    return highest > position.y - 2.0f;
}

int nearest_visible_route_point(
    const re4dc::route::Package& route,
    const re4dc::collision::Package& collision,
    const re4dc::collision::Vec3& position) {
    constexpr std::uint32_t kSourceNearCandidateCount = 10U;
    float distances[kSourceNearCandidateCount];
    int indices[kSourceNearCandidateCount];
    const std::uint32_t candidate_count = std::min(
        route.header().point_count, kSourceNearCandidateCount);
    for(std::uint32_t index = 0; index < candidate_count; ++index) {
        distances[index] = 1.0e16f;
        indices[index] = -1;
    }
    for(std::uint32_t point_index = 0;
        point_index < route.header().point_count; ++point_index) {
        const auto& point = route.points()[point_index];
        const float dx = position.x - point.x;
        const float dy = position.y - point.y;
        const float dz = position.z - point.z;
        const float distance = dx * dx + dy * dy + dz * dz;
        std::uint32_t insert = candidate_count;
        while(insert > 0U && distance <= distances[insert - 1U]) {
            --insert;
        }
        if(insert < candidate_count) {
            for(std::uint32_t move = candidate_count - 1U; move > insert;
                --move) {
                distances[move] = distances[move - 1U];
                indices[move] = indices[move - 1U];
            }
            distances[insert] = distance;
            indices[insert] = static_cast<int>(point_index);
        }
    }
    re4dc::collision::Vec3 raised = position;
    raised.y += 0.5f;
    for(std::uint32_t index = 0; index < candidate_count; ++index) {
        const int point_index = indices[index];
        if(point_index < 0) {
            continue;
        }
        const auto& point = route.points()[point_index];
        const re4dc::collision::Vec3 route_position = {
            point.x, point.y, point.z};
        if(!segment_blocked_by_wall(collision, raised, route_position)) {
            return point_index;
        }
    }
    return -1;
}

re4dc::collision::Vec3 source_route_target(
    const Enemy& enemy, const Player& player,
    const re4dc::route::Package& route,
    const re4dc::collision::Package& collision) {
    re4dc::collision::Vec3 enemy_raised = {
        enemy.x, enemy.y + 0.5f, enemy.z};
    re4dc::collision::Vec3 player_raised = {
        player.x, player.y + 0.5f, player.z};
    if(!segment_blocked_by_wall(collision, enemy_raised, player_raised)) {
        const re4dc::collision::Vec3 midpoint = {
            (enemy_raised.x + player_raised.x) * 0.5f,
            (enemy_raised.y + player_raised.y) * 0.5f,
            (enemy_raised.z + player_raised.z) * 0.5f};
        if(source_route_midpoint_has_floor(collision, midpoint)) {
            return {player.x, player.y, player.z};
        }
    }

    const re4dc::collision::Vec3 enemy_position = {
        enemy.x, enemy.y, enemy.z};
    const int current = nearest_visible_route_point(
        route, collision, enemy_position);
    // RouteCkToPos raises the target 500 source units before asking for its
    // nearest visible RTP point.
    const int destination = nearest_visible_route_point(
        route, collision, player_raised);
    if(current < 0 || destination < 0) {
        return {player.x, player.y, player.z};
    }
    const int next = route.next(static_cast<std::uint32_t>(current),
                                static_cast<std::uint32_t>(destination));
    if(next < 0) {
        return {player.x, player.y, player.z};
    }
    int selected = current;
    const auto& current_point = route.points()[current];
    const float point_dx = enemy.x - current_point.x;
    const float point_dz = enemy.z - current_point.z;
    const auto& next_point = route.points()[next];
    const re4dc::collision::Vec3 next_position = {
        next_point.x, next_point.y, next_point.z};
    if(point_dx * point_dx + point_dz * point_dz < 0.0625f ||
       (next != current &&
        !segment_blocked_by_wall(collision, enemy_raised, next_position))) {
        selected = next;
    }
    const auto& point = route.points()[selected];
    return {point.x, point.y, point.z};
}

re4dc::collision::Vec3 sample_character_point(
    const re4dc::character::Package& character, std::uint32_t clip_index,
    float animation_frame, std::uint32_t vertex_index) {
    const auto& clip = character.clips()[clip_index];
    const float frame = std::clamp(
        animation_frame, 0.0f, static_cast<float>(clip.frame_count - 1U));
    const std::uint32_t local_frame = static_cast<std::uint32_t>(frame);
    const std::uint32_t next_frame =
        std::min(local_frame + 1U, clip.frame_count - 1U);
    const float blend = frame - static_cast<float>(local_frame);
    if(character.header().version == re4dc::character::kVersion) {
        if(vertex_index >= character.header().skinned_position_count) {
            const std::uint32_t marker =
                vertex_index - character.header().skinned_position_count;
            const auto* current = character.frame_marker_positions(
                clip.first_frame + local_frame) + marker * 3U;
            const auto* next = character.frame_marker_positions(
                clip.first_frame + next_frame) + marker * 3U;
            const float scale = character.header().position_quantum_m;
            return {
                (static_cast<float>(current[0]) +
                 (static_cast<float>(next[0]) -
                  static_cast<float>(current[0])) * blend) * scale,
                (static_cast<float>(current[1]) +
                 (static_cast<float>(next[1]) -
                  static_cast<float>(current[1])) * blend) * scale,
                (static_cast<float>(current[2]) +
                 (static_cast<float>(next[2]) -
                  static_cast<float>(current[2])) * blend) * scale,
            };
        }
        constexpr float kMatrixScale = 1.0f / 32767.0f;
        constexpr float kMillimetresToMetres = 0.001f;
        const auto& position = character.position_records()[vertex_index];
        const auto transform = [&](std::uint32_t frame_index) {
            const auto& matrix =
                character.frame_pose_matrices(frame_index)[position.matrix];
            return re4dc::collision::Vec3{
                ((static_cast<float>(matrix.linear[0]) * position.x +
                  static_cast<float>(matrix.linear[1]) * position.y +
                  static_cast<float>(matrix.linear[2]) * position.z) *
                     kMatrixScale + matrix.translation[0]) *
                    kMillimetresToMetres,
                ((static_cast<float>(matrix.linear[3]) * position.x +
                  static_cast<float>(matrix.linear[4]) * position.y +
                  static_cast<float>(matrix.linear[5]) * position.z) *
                     kMatrixScale + matrix.translation[1]) *
                    kMillimetresToMetres,
                ((static_cast<float>(matrix.linear[6]) * position.x +
                  static_cast<float>(matrix.linear[7]) * position.y +
                  static_cast<float>(matrix.linear[8]) * position.z) *
                     kMatrixScale + matrix.translation[2]) *
                    kMillimetresToMetres,
            };
        };
        const auto current = transform(clip.first_frame + local_frame);
        const auto next = transform(clip.first_frame + next_frame);
        return {
            current.x + (next.x - current.x) * blend,
            current.y + (next.y - current.y) * blend,
            current.z + (next.z - current.z) * blend,
        };
    }
    const auto* current = character.frame_positions(
        clip.first_frame + local_frame) + vertex_index * 3U;
    const auto* next = character.frame_positions(
        clip.first_frame + next_frame) + vertex_index * 3U;
    const float scale = character.header().position_quantum_m;
    return {
        (static_cast<float>(current[0]) +
         (static_cast<float>(next[0]) - static_cast<float>(current[0])) *
             blend) * scale,
        (static_cast<float>(current[1]) +
         (static_cast<float>(next[1]) - static_cast<float>(current[1])) *
             blend) * scale,
        (static_cast<float>(current[2]) +
         (static_cast<float>(next[2]) - static_cast<float>(current[2])) *
             blend) * scale,
    };
}

struct PlayerPitchBlend {
    std::uint32_t base_clip;
    std::uint32_t secondary_clip;
    float amount;
};

PlayerPitchBlend player_pitch_blend(std::uint32_t animation_clip,
                                    float aim_pitch) {
    if(animation_clip == kPlayerAimLevelClip) {
        return {
            kPlayerAimLevelClip,
            aim_pitch >= 0.0f ? kPlayerAimPositiveClip
                              : kPlayerAimNegativeClip,
            std::fabs(aim_pitch)};
    }
    if(animation_clip == kPlayerFireLevelClip) {
        return {
            kPlayerFireLevelClip,
            aim_pitch >= 0.0f ? kPlayerFirePositiveClip
                              : kPlayerFireNegativeClip,
            std::fabs(aim_pitch)};
    }
    return {animation_clip, animation_clip, 0.0f};
}

re4dc::collision::Vec3 sample_player_point(
    const re4dc::character::Package& character, const Player& player,
    std::uint32_t vertex_index) {
    const auto blend = player_pitch_blend(
        player.animation_clip, player.aim_pitch);
    const auto base = sample_character_point(
        character, blend.base_clip, player.animation_frame, vertex_index);
    if(blend.amount <= 0.0f) {
        return base;
    }
    const auto& base_clip = character.clips()[blend.base_clip];
    const auto& secondary_clip = character.clips()[blend.secondary_clip];
    const float secondary_frame = player.animation_frame *
        secondary_clip.frames_per_second / base_clip.frames_per_second;
    const auto secondary = sample_character_point(
        character, blend.secondary_clip, secondary_frame,
        vertex_index);
    return {
        base.x + (secondary.x - base.x) * blend.amount,
        base.y + (secondary.y - base.y) * blend.amount,
        base.z + (secondary.z - base.z) * blend.amount,
    };
}

template <typename Actor>
re4dc::collision::Vec3 actor_point_to_world(
    const re4dc::collision::Vec3& point, const Actor& actor) {
    const float sine = std::sin(actor.yaw);
    const float cosine = std::cos(actor.yaw);
    return {
        actor.x + point.x * cosine + point.z * sine,
        actor.y + point.y,
        actor.z - point.x * sine + point.z * cosine,
    };
}

float point_segment_distance_squared(const re4dc::collision::Vec3& point,
                                     const re4dc::collision::Vec3& start,
                                     const re4dc::collision::Vec3& end) {
    const float sx = end.x - start.x;
    const float sy = end.y - start.y;
    const float sz = end.z - start.z;
    const float length_squared = sx * sx + sy * sy + sz * sz;
    const float projection = length_squared > 0.000001f
        ? std::clamp(((point.x - start.x) * sx +
                      (point.y - start.y) * sy +
                      (point.z - start.z) * sz) / length_squared,
                     0.0f, 1.0f)
        : 0.0f;
    const float dx = point.x - (start.x + sx * projection);
    const float dy = point.y - (start.y + sy * projection);
    const float dz = point.z - (start.z + sz * projection);
    return dx * dx + dy * dy + dz * dz;
}

bool source_axe_sweep_hits_player(
    const Enemy& enemy, const Player& player,
    const re4dc::character::Package& enemy_character,
    const re4dc::character::Package& player_character) {
    if(enemy_character.header().position_count < kAxeSweepMarkerCount ||
       player_character.header().position_count < kPlayerHitMarkerCount) {
        return false;
    }
    const std::uint32_t first_axe_marker =
        enemy_character.header().position_count - kAxeSweepMarkerCount;
    // em10_R1_AxeAtk checks the two authored weapon endpoints as 250-unit
    // spheres. Its base point chooses the nearest/facing damage part, but does
    // not enlarge the hit volume, so it is intentionally not tested here.
    const auto low = actor_point_to_world(
        sample_character_point(enemy_character, enemy.animation_clip,
                               enemy.animation_frame, first_axe_marker + 1U),
        enemy);
    const auto high = actor_point_to_world(
        sample_character_point(enemy_character, enemy.animation_clip,
                               enemy.animation_frame, first_axe_marker + 2U),
        enemy);
    const std::uint32_t first_player_marker =
        player_character.header().position_count - kPlayerHitMarkerCount;
    for(std::uint32_t capsule = 0; capsule < kPlayerHitCapsuleCount;
        ++capsule) {
        const auto bottom = actor_point_to_world(
            sample_player_point(
                player_character, player,
                first_player_marker + capsule * 2U),
            player);
        const auto top = actor_point_to_world(
            sample_player_point(
                player_character, player,
                first_player_marker + capsule * 2U + 1U),
            player);
        const float radius =
            kAxeSweepRadius + kPlayerHitCapsuleRadii[capsule];
        if(point_segment_distance_squared(low, bottom, top) <=
               radius * radius ||
           point_segment_distance_squared(high, bottom, top) <=
               radius * radius) {
            return true;
        }
    }
    return false;
}

void update_enemy(Enemy& enemy, Player& player,
                  const re4dc::character::Package& character,
                  const re4dc::character::Package& player_character,
                  const re4dc::collision::Package& collision,
                  const re4dc::route::Package* route,
                  const DemoAudio& audio, float delta_seconds) {
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
        const auto& clip = character.clips()[enemy.animation_clip];
        const float previous_hit_seconds = enemy.animation_frame /
                                           clip.frames_per_second;
        advance_enemy_animation(enemy, character, delta_seconds, false);
        const float hit_seconds = enemy.animation_frame /
                                  clip.frames_per_second;
        constexpr float damage_voice_seconds = 2.0f / 30.0f;
        if(!enemy.hit_voice_played &&
           previous_hit_seconds < damage_voice_seconds &&
           hit_seconds >= damage_voice_seconds) {
            enemy.hit_voice_played = true;
            if(audio.enemy_damage_voice_47 != SFXHND_INVALID) {
                snd_sfx_play(audio.enemy_damage_voice_47, 255, 128);
            }
            std::printf("re4dc-room: source Ganado damage voice frame=2\n");
        }
        if(enemy.animation_frame >= static_cast<float>(clip.frame_count - 1U)) {
            enemy.state = EnemyState::Chase;
            set_enemy_clip(enemy, 1);
        }
        return;
    }

    if(enemy.attack_cooldown_seconds > 0.0f) {
        enemy.attack_cooldown_seconds = std::max(
            0.0f, enemy.attack_cooldown_seconds - delta_seconds);
    }

    const float dx = player.x - enemy.x;
    const float dz = player.z - enemy.z;
    const float distance = std::sqrt(dx * dx + dz * dz);
    const float target_yaw = std::atan2(dx, dz);
    const re4dc::collision::Vec3 go_position = route != nullptr
        ? source_route_target(enemy, player, *route, collision)
        : re4dc::collision::Vec3{player.x, player.y, player.z};
    const float go_yaw = std::atan2(go_position.x - enemy.x,
                                    go_position.z - enemy.z);
    const float source_walk_speed =
        std::fabs(character.clips()[1].root_forward_speed_mps) > 0.0001f
            ? std::fabs(character.clips()[1].root_forward_speed_mps)
            : kFallbackEnemyMoveSpeed;

    // Once motion 0x80 starts, the source routine completes it even when the
    // player moves out of reach. Its SEQ hit flag is evaluated throughout the
    // authored window, so a late dodge can make the sweep miss.
    if(enemy.state == EnemyState::Attack) {
        const auto& clip = character.clips()[enemy.animation_clip];
        const float previous_attack_seconds = enemy.animation_frame /
                                              clip.frames_per_second;
        // Rank 5 initializes Timer to 20. The source pre-decrements it and
        // turns through the first 19 ticks by at most pi/16 each tick. This
        // sequence has no Free bit-3 continuation after that timer expires.
        if(previous_attack_seconds < 19.0f / 30.0f) {
            const float attack_turn = std::clamp(
                wrap_angle(target_yaw - enemy.yaw),
                -0.19634955f, 0.19634955f);
            enemy.yaw = wrap_angle(enemy.yaw + attack_turn);
        }
        move_enemy_forward(enemy, collision,
                           clip.root_forward_speed_mps * delta_seconds);
        advance_enemy_animation(enemy, character, delta_seconds, false);
        const float attack_seconds = enemy.animation_frame /
                                     clip.frames_per_second;
        constexpr float swing_sound_seconds = 37.0f / 30.0f;
        if(!enemy.attack_sound_played &&
           previous_attack_seconds < swing_sound_seconds &&
           attack_seconds >= swing_sound_seconds) {
            enemy.attack_sound_played = true;
            if(audio.enemy_swing_3d != SFXHND_INVALID) {
                snd_sfx_play(audio.enemy_swing_3d, 255, 128);
            }
            std::printf("re4dc-room: source axe swing cue frame=37\n");
        }
        if(!enemy.attack_landed && !player.dead &&
           attack_seconds >= kEnemyAttackHitStartSeconds &&
           attack_seconds <= kEnemyAttackHitEndSeconds) {
            const re4dc::collision::Vec3 enemy_chest = {
                enemy.x, enemy.y + 1.5f, enemy.z};
            const re4dc::collision::Vec3 player_chest = {
                player.x, player.y + 1.5f, player.z};
            const bool path_clear = !segment_blocked_by_wall(
                collision, enemy_chest, player_chest);
            if(source_axe_sweep_hits_player(
                   enemy, player, character, player_character) &&
               path_clear) {
                enemy.attack_landed = true;
                player.health = std::max(
                    0, player.health - kEnemyAttackDamage);
                std::printf(
                    "re4dc-room: source axe hit frame=%.1f player_hp=%d\n",
                    attack_seconds * 30.0f, player.health);
                if(player.health == 0) {
                    player.dead = true;
                    player.hit_reaction = false;
                    if(audio.player_death_voice_13 != SFXHND_INVALID) {
                        snd_sfx_play(audio.player_death_voice_13, 255, 128);
                    }
                    std::printf(
                        "re4dc-room: source Leon death voice cue=13\n");
                } else {
                    player.hit_reaction = true;
                    const unsigned voice = player.damage_voice_cycle++ % 3U;
                    if(audio.player_damage_voice[voice] != SFXHND_INVALID) {
                        snd_sfx_play(audio.player_damage_voice[voice], 255, 128);
                    }
                    std::printf(
                        "re4dc-room: source Leon damage voice cue=%u\n",
                        voice + 9U);
                }
            }
        }
        if(enemy.animation_frame >=
           static_cast<float>(clip.frame_count - 1U)) {
            enemy.state = EnemyState::Chase;
            enemy.attack_cooldown_seconds = enemy.attack_landed
                ? kEnemyAttackCooldownSeconds : 0.0f;
            enemy.attack_landed = false;
            enemy.attack_sound_played = false;
            set_enemy_clip(enemy, 1);
        }
        return;
    }

    // em10_R1_Walk feeds 30% of the route angle into Muku2 and caps the
    // result at 0.15707964 radians per source tick.
    const float turn = std::clamp(wrap_angle(go_yaw - enemy.yaw) * 0.3f,
                                  -kEnemyTurnSpeed * delta_seconds,
                                  kEnemyTurnSpeed * delta_seconds);
    enemy.yaw = wrap_angle(enemy.yaw + turn);

    const re4dc::collision::Vec3 enemy_chest = {
        enemy.x, enemy.y + 1.5f, enemy.z};
    const re4dc::collision::Vec3 player_chest = {
        player.x, player.y + 1.5f, player.z};
    const bool attack_path_blocked = segment_blocked_by_wall(
        collision, enemy_chest, player_chest);
    const float player_angle = std::fabs(wrap_angle(target_yaw - enemy.yaw));
    if(player.dead || distance > kEnemyAttackAcquireRange ||
       player_angle > kPi * 0.25f ||
       enemy.attack_cooldown_seconds > 0.0f || attack_path_blocked) {
        enemy.state = EnemyState::Chase;
        set_enemy_clip(enemy, 1);
        if(!player.dead && distance > 0.001f) {
            const float step = std::min(source_walk_speed * delta_seconds,
                                        distance -
                                            kEnemyAttackAcquireRange);
            move_enemy_forward(enemy, collision, std::max(step, 0.0f));
        }
        advance_enemy_animation(enemy, character, delta_seconds, true);
        return;
    }

    if(enemy.state != EnemyState::Attack) {
        enemy.state = EnemyState::Attack;
        enemy.attack_landed = false;
        enemy.attack_sound_played = false;
        set_enemy_clip(enemy, 2);
    }
}

re4dc::collision::Vec3 subtract(const re4dc::collision::Vec3& a,
                                const re4dc::collision::Vec3& b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
}

re4dc::collision::Vec3 cross(const re4dc::collision::Vec3& a,
                             const re4dc::collision::Vec3& b) {
    return {a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x};
}

float dot(const re4dc::collision::Vec3& a,
          const re4dc::collision::Vec3& b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

bool segment_triangle_hit_fraction(
    const re4dc::collision::Vec3& start,
    const re4dc::collision::Vec3& end,
    const re4dc::collision::Vec3& a,
    const re4dc::collision::Vec3& b,
    const re4dc::collision::Vec3& c,
    float& hit_fraction) {
    constexpr float epsilon = 0.00001f;
    const auto direction = subtract(end, start);
    const auto edge1 = subtract(b, a);
    const auto edge2 = subtract(c, a);
    const auto p = cross(direction, edge2);
    const float determinant = dot(edge1, p);
    if(std::fabs(determinant) < epsilon) {
        return false;
    }
    const float inverse = 1.0f / determinant;
    const auto offset = subtract(start, a);
    const float u = dot(offset, p) * inverse;
    if(u < 0.0f || u > 1.0f) {
        return false;
    }
    const auto q = cross(offset, edge1);
    const float v = dot(direction, q) * inverse;
    if(v < 0.0f || u + v > 1.0f) {
        return false;
    }
    hit_fraction = dot(edge2, q) * inverse;
    return hit_fraction > 0.001f && hit_fraction < 0.999f;
}

bool segment_intersects_triangle(
    const re4dc::collision::Vec3& start,
    const re4dc::collision::Vec3& end,
    const re4dc::collision::Vec3& a,
    const re4dc::collision::Vec3& b,
    const re4dc::collision::Vec3& c) {
    float hit_fraction = 0.0f;
    return segment_triangle_hit_fraction(start, end, a, b, c,
                                         hit_fraction);
}

bool segment_blocked_by_wall(const re4dc::collision::Package& collision,
                             const re4dc::collision::Vec3& start,
                             const re4dc::collision::Vec3& end) {
    const auto* vertices = collision.vertices();
    const auto* polygons = collision.polygons();
    const std::uint32_t candidate_count = collect_collision_candidates(
        collision, start, end, 0.0f, CollisionCandidateGroup::Walls);
    for(std::uint32_t candidate_index = 0;
        candidate_index < candidate_count; ++candidate_index) {
        const std::uint32_t index = g_collision_candidates[candidate_index];
        const auto& polygon = polygons[index];
        if(segment_intersects_triangle(
               start, end, vertices[polygon.vertex[0]],
               vertices[polygon.vertex[1]], vertices[polygon.vertex[2]])) {
            return true;
        }
    }
    return false;
}

bool source_camera_wall_hit(
    const re4dc::collision::Package& collision,
    const re4dc::collision::Vec3& start,
    const re4dc::collision::Vec3& end,
    re4dc::collision::Vec3& hit) {
    const auto* vertices = collision.vertices();
    const auto* polygons = collision.polygons();
    float nearest_fraction = 1.0f;
    bool found = false;
    const std::uint32_t candidate_count = collect_collision_candidates(
        collision, start, end, 0.0f, CollisionCandidateGroup::Walls);
    for(std::uint32_t candidate_index = 0;
        candidate_index < candidate_count; ++candidate_index) {
        const std::uint32_t index = g_collision_candidates[candidate_index];
        const auto& polygon = polygons[index];
        float fraction = 0.0f;
        if(segment_triangle_hit_fraction(
               start, end, vertices[polygon.vertex[0]],
               vertices[polygon.vertex[1]], vertices[polygon.vertex[2]],
               fraction) && fraction < nearest_fraction) {
            nearest_fraction = fraction;
            found = true;
        }
    }
    if(found) {
        hit = {
            start.x + (end.x - start.x) * nearest_fraction,
            start.y + (end.y - start.y) * nearest_fraction,
            start.z + (end.z - start.z) * nearest_fraction};
    }
    return found;
}

re4dc::collision::Vec3 add(const re4dc::collision::Vec3& a,
                           const re4dc::collision::Vec3& b) {
    return {a.x + b.x, a.y + b.y, a.z + b.z};
}

re4dc::collision::Vec3 scale(const re4dc::collision::Vec3& value,
                             float amount) {
    return {value.x * amount, value.y * amount, value.z * amount};
}

float length(const re4dc::collision::Vec3& value) {
    return std::sqrt(dot(value, value));
}

re4dc::collision::Vec3 normalized(
    const re4dc::collision::Vec3& value) {
    const float magnitude = length(value);
    if(magnitude <= 0.000001f) {
        return {0.0f, 0.0f, 0.0f};
    }
    return scale(value, 1.0f / magnitude);
}

re4dc::collision::Vec3 player_offset_to_world(
    const Player& player, const re4dc::collision::Vec3& local) {
    const float forward_x = std::sin(player.yaw);
    const float forward_z = std::cos(player.yaw);
    const float right_x = std::cos(player.yaw);
    const float right_z = -std::sin(player.yaw);
    return {
        player.x + local.x * right_x + local.z * forward_x,
        player.y + local.y,
        player.z + local.x * right_z + local.z * forward_z};
}

re4dc::collision::Vec3 world_to_player_offset(
    const Player& player, const re4dc::collision::Vec3& world) {
    const float dx = world.x - player.x;
    const float dy = world.y - player.y;
    const float dz = world.z - player.z;
    const float forward_x = std::sin(player.yaw);
    const float forward_z = std::cos(player.yaw);
    const float right_x = std::cos(player.yaw);
    const float right_z = -std::sin(player.yaw);
    return {dx * right_x + dz * right_z, dy,
            dx * forward_x + dz * forward_z};
}

// Dreamcast adaptation of CameraQuasiFPS::hitCheck for the source SAT walls.
// The three rays preserve the authored close point and camera-frustum edge
// probes. Character/object camera blockers remain outside this 30-second slice.
re4dc::collision::Vec3 correct_source_camera_walls(
    const re4dc::collision::Package& collision, const Player& player,
    const re4dc::collision::Vec3& camera,
    const re4dc::collision::Vec3& close,
    const re4dc::collision::Vec3& target, float fovy_degrees) {
    const re4dc::collision::Vec3 up = {0.0f, 1.0f, 0.0f};
    const float near_width = kNearClipDistance *
        std::tan(fovy_degrees * kPi / 360.0f) * (4.0f / 3.0f);
    const auto close_side = scale(
        normalized(cross(subtract(close, target), up)), near_width);
    const auto camera_side = scale(
        normalized(cross(subtract(camera, target), up)), near_width);
    const auto side_difference = subtract(close_side, camera_side);
    const auto near_offset = scale(normalized(subtract(close, camera)),
                                   kNearClipDistance);

    const auto close_world = player_offset_to_world(player, close);
    const auto camera_world = player_offset_to_world(player, camera);
    re4dc::collision::Vec3 hits[3]{};
    bool collided[3] = {false, false, false};
    re4dc::collision::Vec3 hit_world{};

    collided[0] = source_camera_wall_hit(
        collision, close_world, camera_world, hit_world);
    if(collided[0]) {
        hits[0] = world_to_player_offset(player, hit_world);
    }

    auto edge_start = player_offset_to_world(
        player, subtract(close, close_side));
    auto edge_end = player_offset_to_world(
        player, subtract(camera, camera_side));
    collided[1] = source_camera_wall_hit(
        collision, edge_start, edge_end, hit_world);
    if(collided[1]) {
        const float ray_length = length(subtract(edge_start, edge_end));
        const float distance_from_end = length(subtract(hit_world, edge_end));
        const float ratio = ray_length > 0.000001f
                                ? distance_from_end / ray_length
                                : 0.0f;
        const auto correction = add(
            scale(side_difference, ratio), camera_side);
        hits[1] = add(add(world_to_player_offset(player, hit_world),
                          correction), near_offset);
    }

    edge_start = player_offset_to_world(player, add(close, close_side));
    edge_end = player_offset_to_world(player, add(camera, camera_side));
    collided[2] = source_camera_wall_hit(
        collision, edge_start, edge_end, hit_world);
    if(collided[2]) {
        const float ray_length = length(subtract(edge_start, edge_end));
        const float distance_from_end = length(subtract(hit_world, edge_end));
        const float ratio = ray_length > 0.000001f
                                ? distance_from_end / ray_length
                                : 0.0f;
        const auto correction = add(
            scale(side_difference, ratio), camera_side);
        hits[2] = add(subtract(world_to_player_offset(player, hit_world),
                               correction), near_offset);
    }

    re4dc::collision::Vec3 corrected = camera;
    float nearest_distance = length(subtract(camera, close));
    bool any_collision = false;
    for(unsigned index = 0; index < 3U; ++index) {
        if(!collided[index]) {
            continue;
        }
        any_collision = true;
        const float distance = length(subtract(hits[index], close));
        if(distance < nearest_distance) {
            nearest_distance = distance;
            corrected = hits[index];
        }
    }
    if(!any_collision) {
        const auto left_edge = player_offset_to_world(
            player, subtract(camera, camera_side));
        const auto right_edge = player_offset_to_world(
            player, add(camera, camera_side));
        if(source_camera_wall_hit(collision, camera_world, left_edge,
                                  hit_world) ||
           source_camera_wall_hit(collision, camera_world, right_edge,
                                  hit_world)) {
            corrected = add(camera, near_offset);
        }
    }
    return corrected;
}

bool segment_sphere_first_hit(
    const re4dc::collision::Vec3& start,
    const re4dc::collision::Vec3& direction,
    const re4dc::collision::Vec3& center, float radius, float& hit_t) {
    const auto offset = subtract(start, center);
    const float a = dot(direction, direction);
    const float c = dot(offset, offset) - radius * radius;
    if(c <= 0.0f) {
        hit_t = 0.0f;
        return true;
    }
    if(a <= 0.000001f) {
        return false;
    }
    const float b = dot(offset, direction);
    const float discriminant = b * b - a * c;
    if(discriminant < 0.0f) {
        return false;
    }
    const float candidate = (-b - std::sqrt(discriminant)) / a;
    if(candidate < 0.0f || candidate > 1.0f) {
        return false;
    }
    hit_t = candidate;
    return true;
}

bool segment_capsule_first_hit(
    const re4dc::collision::Vec3& start,
    const re4dc::collision::Vec3& end,
    const re4dc::collision::Vec3& bottom,
    const re4dc::collision::Vec3& top, float radius, float& hit_t) {
    if(point_segment_distance_squared(start, bottom, top) <= radius * radius) {
        hit_t = 0.0f;
        return true;
    }
    const auto direction = subtract(end, start);
    const auto axis = subtract(top, bottom);
    const auto origin = subtract(start, bottom);
    const float axis_squared = dot(axis, axis);
    float best = 2.0f;
    if(axis_squared > 0.000001f) {
        const float ray_squared = dot(direction, direction);
        const float axis_ray = dot(axis, direction);
        const float axis_origin = dot(axis, origin);
        const float ray_origin = dot(direction, origin);
        const float origin_squared = dot(origin, origin);
        const float a = axis_squared * ray_squared - axis_ray * axis_ray;
        const float b = axis_squared * ray_origin - axis_origin * axis_ray;
        const float c = axis_squared * origin_squared -
                        axis_origin * axis_origin -
                        radius * radius * axis_squared;
        const float discriminant = b * b - a * c;
        if(std::fabs(a) > 0.000001f && discriminant >= 0.0f) {
            const float candidate = (-b - std::sqrt(discriminant)) / a;
            const float height = axis_origin + candidate * axis_ray;
            if(candidate >= 0.0f && candidate <= 1.0f &&
               height > 0.0f && height < axis_squared) {
                best = candidate;
            }
        }
    }
    float sphere_t = 0.0f;
    if(segment_sphere_first_hit(start, direction, bottom, radius, sphere_t)) {
        best = std::min(best, sphere_t);
    }
    if(segment_sphere_first_hit(start, direction, top, radius, sphere_t)) {
        best = std::min(best, sphere_t);
    }
    if(best > 1.0f) {
        return false;
    }
    hit_t = best;
    return true;
}

std::uint16_t g_source_random = 0x0d37U;

std::uint8_t source_random_byte() {
    const std::uint16_t old = g_source_random;
    const std::uint32_t next =
        (static_cast<std::uint32_t>(
             static_cast<std::uint8_t>((old >> 1U) + (old >> 8U))) << 8U) |
        static_cast<std::uint8_t>(old >> 1U);
    std::uint32_t value = next & 0xffffU;
    if(value == old) {
        value = next + 0x101U;
    }
    g_source_random = static_cast<std::uint16_t>(value);
    return static_cast<std::uint8_t>(value >> 8U);
}

float source_random_1_1() {
    const std::uint32_t bits =
        static_cast<std::uint32_t>(source_random_byte()) |
        (static_cast<std::uint32_t>(source_random_byte()) << 8U) |
        ((static_cast<std::uint32_t>(source_random_byte()) & 0x7fU) << 16U) |
        0x3f800000U;
    float value = 0.0f;
    std::memcpy(&value, &bits, sizeof(value));
    return value * 2.0f - 3.0f;
}

re4dc::collision::Vec3 normalized_difference(
    const re4dc::collision::Vec3& point,
    const re4dc::collision::Vec3& origin) {
    auto direction = subtract(point, origin);
    const float length = std::sqrt(dot(direction, direction));
    if(length > 0.000001f) {
        direction.x /= length;
        direction.y /= length;
        direction.z /= length;
    }
    return direction;
}

bool shot_hits_enemy(const Player& player, const Enemy& enemy,
                     const re4dc::collision::Package& collision,
                     const re4dc::character::Package& player_character,
                     const re4dc::character::Package& enemy_character) {
    if(enemy.state == EnemyState::Dead ||
       player_character.header().position_count <
           kPlayerFireMarkerCount + kPlayerHitMarkerCount ||
       enemy_character.header().position_count <
           kEnemyHitMarkerCount + kAxeSweepMarkerCount) {
        return false;
    }
    const std::uint32_t first_player_fire_marker =
        player_character.header().position_count - kPlayerHitMarkerCount -
        kPlayerFireMarkerCount;
    const auto fire_blend = player_pitch_blend(
        kPlayerFireLevelClip, player.aim_pitch);
    const auto player_fire_point = [&](std::uint32_t marker) {
        const auto base = sample_character_point(
            player_character, fire_blend.base_clip, 0.0f,
            first_player_fire_marker + marker);
        re4dc::collision::Vec3 point = base;
        if(fire_blend.amount > 0.0f) {
            const auto secondary = sample_character_point(
                player_character, fire_blend.secondary_clip, 0.0f,
                first_player_fire_marker + marker);
            point = {
                base.x + (secondary.x - base.x) * fire_blend.amount,
                base.y + (secondary.y - base.y) * fire_blend.amount,
                base.z + (secondary.z - base.z) * fire_blend.amount,
            };
        }
        return actor_point_to_world(
            point, player);
    };
    const auto muzzle = player_fire_point(0U);
    const auto minus_x = normalized_difference(player_fire_point(1U), muzzle);
    const auto plus_y = normalized_difference(player_fire_point(2U), muzzle);
    const auto plus_z = normalized_difference(player_fire_point(3U), muzzle);
    const float spread_y = source_random_1_1() * kHandgunSpread;
    const float spread_z = source_random_1_1() * kHandgunSpread;
    const re4dc::collision::Vec3 end = {
        muzzle.x + minus_x.x * kHandgunRayLength + plus_y.x * spread_y +
            plus_z.x * spread_z,
        muzzle.y + minus_x.y * kHandgunRayLength + plus_y.y * spread_y +
            plus_z.y * spread_z,
        muzzle.z + minus_x.z * kHandgunRayLength + plus_y.z * spread_y +
            plus_z.z * spread_z};
    const auto direction = subtract(end, muzzle);
    const std::uint32_t first_marker = enemy_character.header().position_count -
        kAxeSweepMarkerCount - kEnemyHitMarkerCount;
    float nearest = 2.0f;
    for(std::uint32_t capsule = 0; capsule < kEnemyHitCapsuleCount;
        ++capsule) {
        const auto bottom = actor_point_to_world(
            sample_character_point(
                enemy_character, enemy.animation_clip, enemy.animation_frame,
                first_marker + capsule * 2U),
            enemy);
        const auto top = actor_point_to_world(
            sample_character_point(
                enemy_character, enemy.animation_clip, enemy.animation_frame,
                first_marker + capsule * 2U + 1U),
            enemy);
        float hit_t = 0.0f;
        if(segment_capsule_first_hit(
               muzzle, end, bottom, top,
               kEnemyHitCapsuleRadii[capsule], hit_t)) {
            nearest = std::min(nearest, hit_t);
        }
    }
    if(nearest > 1.0f) {
        return false;
    }
    const re4dc::collision::Vec3 hit = {
        muzzle.x + direction.x * nearest,
        muzzle.y + direction.y * nearest,
        muzzle.z + direction.z * nearest};
    return !segment_blocked_by_wall(collision, muzzle, hit);
}

void update_combat(Player& player, Enemy& enemy, const Input& input,
                   bool fire_pressed, bool reload_pressed,
                   float delta_seconds,
                   const re4dc::collision::Package& collision,
                   const re4dc::character::Package& character,
                   const re4dc::character::Package& enemy_character,
                   const DemoAudio& audio) {
    if(player.dead || player.hit_reaction) {
        return;
    }
    const auto start_reload = [&]() {
        player.reload_seconds = kStartingReloadFinishSeconds;
        player.reload_refilled = false;
        if(audio.reload_16 != SFXHND_INVALID) {
            snd_sfx_play(audio.reload_16, 255, 128);
        }
        std::printf("re4dc-room: reload start\n");
    };
    if(player.reload_seconds > 0.0f) {
        player.reload_seconds -= delta_seconds;
        const float reload_elapsed =
            kStartingReloadFinishSeconds - player.reload_seconds;
        if(!player.reload_refilled &&
           reload_elapsed >= kStartingReloadRefillSeconds) {
            player.ammo = kMagazineSize;
            player.reload_refilled = true;
            std::printf("re4dc-room: source reload frame 44 ammo=%d\n",
                        player.ammo);
        }
        if(player.reload_seconds <= 0.0f) {
            player.reload_seconds = 0.0f;
            std::printf("re4dc-room: source reload frame 55 complete ammo=%d\n",
                        player.ammo);
        }
        return;
    }
    if(reload_pressed && player.ammo < kMagazineSize) {
        start_reload();
        return;
    }
    if(!input.aim) {
        return;
    }
    if(player.ammo <= 0) {
        if(fire_pressed) {
            start_reload();
        }
        return;
    }
    if(!input.fire || player.fire_animation_seconds > 0.0f) {
        return;
    }
    --player.ammo;
    player.fire_animation_seconds = kStartingHandgunShotReadySeconds;
    if(audio.fire_0 != SFXHND_INVALID) {
        snd_sfx_play(audio.fire_0, 255, 128);
        snd_sfx_play(audio.fire_2, 255, 128);
    }
    const bool hit = shot_hits_enemy(
        player, enemy, collision, character, enemy_character);
    std::printf("re4dc-room: fire ammo=%d hit=%d\n", player.ammo, hit ? 1 : 0);
    if(hit) {
        if(audio.enemy_body_hit_0c != SFXHND_INVALID) {
            snd_sfx_play(audio.enemy_body_hit_0c, 255, 128);
        }
        enemy.health = std::max(0, enemy.health - kHandgunBodyDamage);
        if(enemy.health <= 0) {
            enemy.state = EnemyState::Dead;
            set_enemy_clip(enemy, 4);
            if(audio.enemy_death_voice_16 != SFXHND_INVALID) {
                snd_sfx_play(audio.enemy_death_voice_16, 255, 128);
            }
            std::printf("re4dc-room: ganado defeated\n");
        } else {
            enemy.state = EnemyState::Hit;
            enemy.animation_clip = 3;
            enemy.animation_frame = 0.0f;
            enemy.hit_voice_played = false;
        }
    }
}

std::uint32_t shade_color(float red, float green, float blue) {
    const std::uint32_t r = static_cast<std::uint32_t>(
        std::clamp(red * 255.0f, 0.0f, 255.0f));
    const std::uint32_t g = static_cast<std::uint32_t>(
        std::clamp(green * 255.0f, 0.0f, 255.0f));
    const std::uint32_t b = static_cast<std::uint32_t>(
        std::clamp(blue * 255.0f, 0.0f, 255.0f));
    return 0xff000000U | (r << 16U) | (g << 8U) | b;
}

#if defined(RE4DC_SCENE_R100)
struct SourceLightingBasis {
    float right_x = 1.0f;
    float right_y = 0.0f;
    float right_z = 0.0f;
    float up_x = 0.0f;
    float up_y = 1.0f;
    float up_z = 0.0f;
    float forward_x = 0.0f;
    float forward_y = 0.0f;
    float forward_z = 1.0f;
};

SourceLightingBasis g_source_lighting_basis;
point_t g_source_camera_eye{};
float g_source_half_fov_tangent = 1.0f;

struct PreparedSourceLight {
    float direction_x = 0.0f;
    float direction_y = 1.0f;
    float direction_z = 0.0f;
    float current_direction_x = 0.0f;
    float current_direction_y = 1.0f;
    float current_direction_z = 0.0f;
    float quadratic_attenuation = 0.0f;
    float spot_cutoff = -1.0f;
    float spot_scale = 1.0f;
};

constexpr std::size_t kSourceLightCount =
    sizeof(kSourceLights) / sizeof(kSourceLights[0]);
PreparedSourceLight g_prepared_source_lights[kSourceLightCount]{};
std::uint32_t g_source_dynamic_light_mask = 0U;
bool g_room_dynamic_light_fast_path = false;
constexpr std::uint32_t kRoomStaticLightingVertexCapacity = 45000U;
float g_room_static_lighting[kRoomStaticLightingVertexCapacity * 3U]{};
std::uint16_t g_room_static_lighting_owner[kRoomStaticLightingVertexCapacity]{};
constexpr std::uint16_t kRoomLightingConflicted = 0xfffeU;
constexpr std::uint16_t kRoomLightingUnowned = 0xffffU;
bool g_room_normals_are_unit = false;

void normalize_vector(float& x, float& y, float& z) {
    const float length = std::sqrt(x * x + y * y + z * z);
    if(length <= 0.000001f) {
        x = 0.0f;
        y = 1.0f;
        z = 0.0f;
        return;
    }
    x /= length;
    y /= length;
    z /= length;
}

void prepare_source_lights() {
    g_source_dynamic_light_mask = 0U;
    for(std::size_t index = 0; index < kSourceLightCount; ++index) {
        const SourceLight& light = kSourceLights[index];
        if(light.type == 5U && light.view_space) {
            g_source_dynamic_light_mask |= 1U << index;
        }
        PreparedSourceLight& prepared = g_prepared_source_lights[index];
        prepared.direction_x = light.nx;
        prepared.direction_y = light.ny;
        prepared.direction_z = light.nz;
        if(light.type == 3U || light.type == 5U) {
            normalize_vector(prepared.direction_x, prepared.direction_y,
                             prepared.direction_z);
        }
        prepared.current_direction_x = prepared.direction_x;
        prepared.current_direction_y = prepared.direction_y;
        prepared.current_direction_z = prepared.direction_z;
        if(light.type != 1U && light.type != 5U && light.radius > 0.0f) {
            prepared.quadratic_attenuation =
                (light.intensity - 0.1f) /
                (0.1f * light.radius * light.radius);
        }
        if(light.type == 3U) {
            prepared.spot_cutoff =
                std::cos(light.cutoff_degrees * kPi / 180.0f);
            prepared.spot_scale =
                1.0f / std::max(0.0001f, 1.0f - prepared.spot_cutoff);
        }
    }
    constexpr std::uint32_t kExpectedRoomDynamicLights =
        (1U << 1U) | (1U << 5U);
    g_room_dynamic_light_fast_path =
        g_source_dynamic_light_mask == kExpectedRoomDynamicLights;
}

void set_source_lighting_camera(const point_t& eye, const point_t& target,
                                float half_fov) {
    float fx = target.x - eye.x;
    float fy = target.y - eye.y;
    float fz = target.z - eye.z;
    normalize_vector(fx, fy, fz);
    float rx = fz;
    float ry = 0.0f;
    float rz = -fx;
    normalize_vector(rx, ry, rz);
    float ux = ry * fz - rz * fy;
    float uy = rz * fx - rx * fz;
    float uz = rx * fy - ry * fx;
    normalize_vector(ux, uy, uz);
    g_source_lighting_basis = {rx, ry, rz, ux, uy, uz, fx, fy, fz};
    g_source_camera_eye = eye;
    g_source_half_fov_tangent = std::tan(half_fov);
    for(std::size_t index = 0; index < kSourceLightCount; ++index) {
        const SourceLight& light = kSourceLights[index];
        if(light.type != 5U || !light.view_space) {
            continue;
        }
        PreparedSourceLight& prepared = g_prepared_source_lights[index];
        const float view_x = prepared.direction_x;
        const float view_y = prepared.direction_y;
        const float view_z = prepared.direction_z;
        prepared.current_direction_x =
            g_source_lighting_basis.right_x * view_x +
            g_source_lighting_basis.up_x * view_y +
            g_source_lighting_basis.forward_x * view_z;
        prepared.current_direction_y =
            g_source_lighting_basis.right_y * view_x +
            g_source_lighting_basis.up_y * view_y +
            g_source_lighting_basis.forward_y * view_z;
        prepared.current_direction_z =
            g_source_lighting_basis.right_z * view_x +
            g_source_lighting_basis.up_z * view_y +
            g_source_lighting_basis.forward_z * view_z;
        normalize_vector(prepared.current_direction_x,
                         prepared.current_direction_y,
                         prepared.current_direction_z);
    }
}

void accumulate_source_lighting(float px, float py, float pz,
                                float nx, float ny, float nz,
                                float& red, float& green, float& blue,
                                std::uint32_t light_selection,
                                bool normal_is_unit = false) {
    if(!normal_is_unit) {
        normalize_vector(nx, ny, nz);
    }
    for(std::size_t index = 0; index < kSourceLightCount; ++index) {
        if((light_selection & (1U << index)) == 0U) {
            continue;
        }
        const SourceLight& light = kSourceLights[index];
        const PreparedSourceLight& prepared =
            g_prepared_source_lights[index];
        float lx = 0.0f;
        float ly = 0.0f;
        float lz = 0.0f;
        float attenuation = light.intensity;
        if(light.type == 5U) {
            lx = prepared.current_direction_x;
            ly = prepared.current_direction_y;
            lz = prepared.current_direction_z;
        } else {
            lx = light.x - px;
            ly = light.y - py;
            lz = light.z - pz;
            const float distance = std::sqrt(lx * lx + ly * ly + lz * lz);
            if(distance <= 0.000001f) {
                continue;
            }
            lx /= distance;
            ly /= distance;
            lz /= distance;
            if(light.type == 1U) {
                attenuation = light.radius > 0.0f
                                  ? light.intensity * std::max(
                                        0.0f, 1.0f - distance / light.radius)
                                  : light.intensity;
            } else {
                // lightSetQuadratic reaches 0.1 brightness at Radius.
                attenuation = light.intensity /
                              std::max(1.0f, 1.0f +
                                                prepared.quadratic_attenuation *
                                                    distance * distance);
            }
            if(light.type == 3U) {
                const float cone_cosine =
                    prepared.direction_x * -lx +
                    prepared.direction_y * -ly +
                    prepared.direction_z * -lz;
                if(cone_cosine <= prepared.spot_cutoff) {
                    continue;
                }
                attenuation *= (cone_cosine - prepared.spot_cutoff) *
                               prepared.spot_scale;
            }
        }
        const float diffuse = std::max(0.0f, nx * lx + ny * ly + nz * lz);
        red += light.red * attenuation * diffuse;
        green += light.green * attenuation * diffuse;
        blue += light.blue * attenuation * diffuse;
    }
}

void accumulate_room_dynamic_lighting(float nx, float ny, float nz,
                                      float& red, float& green, float& blue,
                                      std::uint32_t light_selection) {
    const auto apply_directional = [&](std::size_t index) {
        if((light_selection & (1U << index)) == 0U) {
            return;
        }
        const SourceLight& light = kSourceLights[index];
        const PreparedSourceLight& prepared =
            g_prepared_source_lights[index];
        const float diffuse = std::max(
            0.0f, nx * prepared.current_direction_x +
                      ny * prepared.current_direction_y +
                      nz * prepared.current_direction_z);
        red += light.red * light.intensity * diffuse;
        green += light.green * light.intensity * diffuse;
        blue += light.blue * light.intensity * diffuse;
    };
    // r100 cut 0 has exactly two camera-relative type-5 lights. Retain their
    // source iteration order while avoiding seven rejected light tests and
    // the general point/spot setup for every static room vertex.
    apply_directional(1U);
    apply_directional(5U);
}

struct SelectedSourceLights {
    std::uint8_t indices[8]{};
    std::uint8_t count = 0U;
};

SelectedSourceLights selected_source_lights(std::uint32_t selection) {
    SelectedSourceLights result{};
    for(std::size_t index = 0U; index < kSourceLightCount; ++index) {
        if((selection & (1U << index)) == 0U) {
            continue;
        }
        if(result.count == sizeof(result.indices)) {
            break;
        }
        result.indices[result.count++] = static_cast<std::uint8_t>(index);
    }
    return result;
}

void evaluate_selected_actor_lighting(
    float px, float py, float pz, float nx, float ny, float nz,
    const SelectedSourceLights& selection,
    float& red, float& green, float& blue) {
    normalize_vector(nx, ny, nz);
    red = kSourceActorAmbientRed;
    green = kSourceActorAmbientGreen;
    blue = kSourceActorAmbientBlue;
    for(std::uint8_t slot = 0U; slot < selection.count; ++slot) {
        const std::size_t index = selection.indices[slot];
        const SourceLight& light = kSourceLights[index];
        const PreparedSourceLight& prepared =
            g_prepared_source_lights[index];
        float lx = 0.0f;
        float ly = 0.0f;
        float lz = 0.0f;
        float attenuation = light.intensity;
        if(light.type == 5U) {
            lx = prepared.current_direction_x;
            ly = prepared.current_direction_y;
            lz = prepared.current_direction_z;
        } else {
            lx = light.x - px;
            ly = light.y - py;
            lz = light.z - pz;
            const float distance = std::sqrt(lx * lx + ly * ly + lz * lz);
            if(distance <= 0.000001f) {
                continue;
            }
            lx /= distance;
            ly /= distance;
            lz /= distance;
            if(light.type == 1U) {
                attenuation = light.radius > 0.0f
                                  ? light.intensity * std::max(
                                        0.0f, 1.0f - distance / light.radius)
                                  : light.intensity;
            } else {
                attenuation = light.intensity /
                              std::max(1.0f, 1.0f +
                                                prepared.quadratic_attenuation *
                                                    distance * distance);
            }
            if(light.type == 3U) {
                const float cone_cosine =
                    prepared.direction_x * -lx +
                    prepared.direction_y * -ly +
                    prepared.direction_z * -lz;
                if(cone_cosine <= prepared.spot_cutoff) {
                    continue;
                }
                attenuation *= (cone_cosine - prepared.spot_cutoff) *
                               prepared.spot_scale;
            }
        }
        const float diffuse = std::max(0.0f, nx * lx + ny * ly + nz * lz);
        red += light.red * attenuation * diffuse;
        green += light.green * attenuation * diffuse;
        blue += light.blue * attenuation * diffuse;
    }
    red = std::clamp(red, 0.0f, 1.0f);
    green = std::clamp(green, 0.0f, 1.0f);
    blue = std::clamp(blue, 0.0f, 1.0f);
}

void evaluate_source_lighting(float px, float py, float pz,
                              float nx, float ny, float nz,
                              bool actor, float& red, float& green,
                              float& blue,
                              std::uint32_t light_selection = 0x1ffU) {
    red = actor ? kSourceActorAmbientRed : kSourceRoomAmbientRed;
    green = actor ? kSourceActorAmbientGreen : kSourceRoomAmbientGreen;
    blue = actor ? kSourceActorAmbientBlue : kSourceRoomAmbientBlue;
    accumulate_source_lighting(px, py, pz, nx, ny, nz,
                               red, green, blue, light_selection);
    red = std::clamp(red, 0.0f, 1.0f);
    green = std::clamp(green, 0.0f, 1.0f);
    blue = std::clamp(blue, 0.0f, 1.0f);
}
#endif

bool group_visible(const re4dc::room::Group& group) {
#if defined(RE4DC_SCENE_R100)
    // Reject complete source groups in world/view space before transforming
    // their triangles. Projected AABB corners are not conservative when a long
    // wall crosses the frustum without placing a corner inside it, so use the
    // AABB support radius along the exact camera axes instead.
    const float center_x = (group.bounds_min[0] + group.bounds_max[0]) * 0.5f;
    const float center_y = (group.bounds_min[1] + group.bounds_max[1]) * 0.5f;
    const float center_z = (group.bounds_min[2] + group.bounds_max[2]) * 0.5f;
    const float extent_x = (group.bounds_max[0] - group.bounds_min[0]) * 0.5f;
    const float extent_y = (group.bounds_max[1] - group.bounds_min[1]) * 0.5f;
    const float extent_z = (group.bounds_max[2] - group.bounds_min[2]) * 0.5f;
    const float relative_x = center_x - g_source_camera_eye.x;
    const float relative_y = center_y - g_source_camera_eye.y;
    const float relative_z = center_z - g_source_camera_eye.z;
    const auto projected_center = [&](float axis_x, float axis_y,
                                      float axis_z) {
        return relative_x * axis_x + relative_y * axis_y +
               relative_z * axis_z;
    };
    const auto support_radius = [&](float axis_x, float axis_y,
                                    float axis_z) {
        return extent_x * std::fabs(axis_x) +
               extent_y * std::fabs(axis_y) +
               extent_z * std::fabs(axis_z);
    };
    const float view_x = projected_center(
        g_source_lighting_basis.right_x, g_source_lighting_basis.right_y,
        g_source_lighting_basis.right_z);
    const float view_y = projected_center(
        g_source_lighting_basis.up_x, g_source_lighting_basis.up_y,
        g_source_lighting_basis.up_z);
    const float view_z = projected_center(
        g_source_lighting_basis.forward_x, g_source_lighting_basis.forward_y,
        g_source_lighting_basis.forward_z);
    const float radius_x = support_radius(
        g_source_lighting_basis.right_x, g_source_lighting_basis.right_y,
        g_source_lighting_basis.right_z);
    const float radius_y = support_radius(
        g_source_lighting_basis.up_x, g_source_lighting_basis.up_y,
        g_source_lighting_basis.up_z);
    const float radius_z = support_radius(
        g_source_lighting_basis.forward_x, g_source_lighting_basis.forward_y,
        g_source_lighting_basis.forward_z);
    if(view_z + radius_z < kNearClipDistance ||
       view_z - radius_z > kFarClipDistance) {
        return false;
    }
    const float far_depth = std::max(view_z + radius_z, kNearClipDistance);
    const float half_height = far_depth * g_source_half_fov_tangent;
    const float half_width = half_height * (4.0f / 3.0f);
    return view_x - radius_x <= half_width &&
           view_x + radius_x >= -half_width &&
           view_y - radius_y <= half_height &&
           view_y + radius_y >= -half_height;
#else
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
        right &= x > kScreenWidth;
        above &= y < 0.0f;
        below &= y > kScreenHeight;
    }
    return !(behind || beyond_far || left || right || above || below);
#endif
}

constexpr std::uint32_t kCharacterSubmitVertexCapacity = 768U;
constexpr std::uint32_t kLeonVertexCapacity = 8192U;
constexpr std::uint32_t kGanadoVertexCapacity = 4096U;
constexpr std::uint32_t kLeonPoseMatrixCapacity = 512U;
constexpr std::uint32_t kGanadoPoseMatrixCapacity = 128U;
constexpr std::uint32_t kRoomVertexCacheCapacity = 2048U;
static_assert((kRoomVertexCacheCapacity & (kRoomVertexCacheCapacity - 1U)) == 0U);

struct RoomVertexCacheEntry {
    std::uint32_t generation = 0;
    std::uint32_t source_index = 0;
    std::uint32_t light_selection = 0;
    RenderVertex vertex{};
};

ProjectedVertex g_leon_projected[kLeonVertexCapacity];
ProjectedVertex g_ganado_projected[kGanadoVertexCapacity];
PreparedPoseMatrix g_leon_pose_palette[kLeonPoseMatrixCapacity];
PreparedPoseMatrix g_ganado_pose_palette[kGanadoPoseMatrixCapacity];
#if defined(RE4DC_SCENE_R100)
float g_leon_lighting[kLeonVertexCapacity * 3U];
float g_ganado_lighting[kGanadoVertexCapacity * 3U];
std::uint32_t g_leon_colors[kLeonVertexCapacity];
std::uint32_t g_ganado_colors[kGanadoVertexCapacity];
#endif
pvr_vertex_t g_character_submit_vertices[kCharacterSubmitVertexCapacity];
RenderVertex g_room_strip_vertices[kCharacterSubmitVertexCapacity];
RoomVertexCacheEntry g_room_vertex_cache[kRoomVertexCacheCapacity];
std::uint32_t g_room_vertex_cache_generation = 0;

constexpr std::uint8_t kCullNone = 0U;
constexpr std::uint8_t kCullFront = 1U;
constexpr std::uint8_t kCullBack = 2U;
constexpr std::uint8_t kCullAll = 3U;

#if defined(RE4DC_SCENE_R100)
bool source_light_hits_group(const re4dc::room::SourceGroup& group,
                             const SourceLight& light) {
    if((group.metadata_flags & re4dc::room::kSourceGroupHasLightVolume) == 0U ||
       light.radius == 0.0f) {
        return true;
    }
    const float dx = light.x - group.light_center[0];
    const float dy = light.y - group.light_center[1];
    const float dz = light.z - group.light_center[2];
    const float local_x = group.inverse_rotation[0] * dx +
                          group.inverse_rotation[1] * dy +
                          group.inverse_rotation[2] * dz;
    const float local_y = group.inverse_rotation[3] * dx +
                          group.inverse_rotation[4] * dy +
                          group.inverse_rotation[5] * dz;
    const float local_z = group.inverse_rotation[6] * dx +
                          group.inverse_rotation[7] * dy +
                          group.inverse_rotation[8] * dz;
    return !(local_x - light.radius > group.light_size[0] ||
             local_x + light.radius < -group.light_size[0] ||
             local_y - light.radius > group.light_size[1] ||
             local_y + light.radius < -group.light_size[1] ||
             local_z - light.radius > group.light_size[2] ||
             local_z + light.radius < -group.light_size[2]);
}

std::uint32_t source_group_light_selection(
    const re4dc::room::SourceGroup* group) {
    if(group == nullptr ||
       (group->metadata_flags & re4dc::room::kSourceGroupHasLightVolume) == 0U) {
        return 0xffffffffU;
    }
    std::uint32_t selection = 0U;
    for(std::size_t index = 0; index < kSourceLightCount; ++index) {
        const SourceLight& light = kSourceLights[index];
        if((light.enable_mask & 0x10U) == 0U ||
           (group->select_mask & (1U << light.source_index)) == 0U ||
           !source_light_hits_group(*group, light)) {
            continue;
        }
        selection |= 1U << index;
    }
    return selection;
}

std::uint32_t source_actor_light_selection(float x, float y, float z,
                                           std::uint8_t enable_mask) {
    // Player::init1 and the shared em10 Ganado constructor both attach a
    // one-metre-radius, one-metre-half-height capsule to part 0. Their source
    // enable masks are 1 and 2 respectively. With a zero offset and the
    // current upright actors, part 0's up axis is world Y.
    constexpr float radius = 1.0f;
    constexpr float half_height = 1.0f;
    std::uint32_t selection = 0U;
    unsigned selected_count = 0U;
    for(std::size_t index = 0; index < kSourceLightCount; ++index) {
        const SourceLight& light = kSourceLights[index];
        if((light.enable_mask & enable_mask) == 0U) {
            continue;
        }
        bool hit = light.radius == 0.0f;
        if(!hit) {
            const float dx = light.x - x;
            const float dz = light.z - z;
            const float bottom_dy = light.y - (y - half_height);
            const float top_dy = light.y - (y + half_height);
            const float reach = radius + light.radius;
            const float reach_squared = reach * reach;
            hit = dx * dx + bottom_dy * bottom_dy + dz * dz <
                      reach_squared ||
                  dx * dx + top_dy * top_dy + dz * dz < reach_squared;
        }
        if(!hit) {
            continue;
        }
        selection |= 1U << index;
        if(++selected_count == 8U) {
            break;
        }
    }
    return selection;
}

bool prepare_room_static_lighting(const re4dc::room::Package& room) {
    if(room.header().vertex_count > kRoomStaticLightingVertexCapacity ||
       room.header().group_count > kRoomLightingConflicted) {
        return false;
    }
    std::memset(g_room_static_lighting_owner, 0xff,
                static_cast<std::size_t>(room.header().vertex_count) *
                    sizeof(g_room_static_lighting_owner[0]));
    const auto* groups = room.groups();
    const auto* batches = room.batches();
    const auto* indices = room.indices();
    const auto* vertices = room.vertices();
    const auto* source_groups = room.source_groups();
    const std::uint32_t static_mask = ~g_source_dynamic_light_mask;
    g_room_normals_are_unit = true;
    for(std::uint32_t vertex_index = 0U;
        vertex_index < room.header().vertex_count; ++vertex_index) {
        const auto& vertex = vertices[vertex_index];
        const float length_squared = vertex.nx * vertex.nx +
                                     vertex.ny * vertex.ny +
                                     vertex.nz * vertex.nz;
        if(!std::isfinite(length_squared) ||
           std::fabs(length_squared - 1.0f) > 0.00001f) {
            g_room_normals_are_unit = false;
            break;
        }
    }
    for(std::uint32_t group_index = 0U;
        group_index < room.header().group_count; ++group_index) {
        const auto& group = groups[group_index];
        if(group.first_batch > room.header().batch_count ||
           group.batch_count > room.header().batch_count - group.first_batch) {
            return false;
        }
        const std::uint32_t selection = source_group_light_selection(
            source_groups != nullptr ? source_groups + group_index : nullptr);
        for(std::uint32_t local_batch = 0U;
            local_batch < group.batch_count; ++local_batch) {
            const auto& batch = batches[group.first_batch + local_batch];
            if(batch.first_index > room.header().index_count ||
               batch.index_count >
                   room.header().index_count - batch.first_index) {
                return false;
            }
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; ++index) {
                const std::uint32_t vertex_index = indices[index];
                if(vertex_index >= room.header().vertex_count) {
                    return false;
                }
                std::uint16_t& owner =
                    g_room_static_lighting_owner[vertex_index];
                if(owner == kRoomLightingConflicted) {
                    continue;
                }
                if(owner != kRoomLightingUnowned) {
                    const std::uint32_t owner_selection =
                        source_group_light_selection(
                            source_groups != nullptr
                                ? source_groups + owner
                                : nullptr);
                    if(owner_selection != selection) {
                        // A source vertex shared by objects with different
                        // selected-light lists cannot share one baked static
                        // contribution. Leave it on the exact per-use path.
                        owner = kRoomLightingConflicted;
                    }
                    continue;
                }
                owner = static_cast<std::uint16_t>(group_index);
                const auto& vertex = vertices[vertex_index];
                float red = kSourceRoomAmbientRed;
                float green = kSourceRoomAmbientGreen;
                float blue = kSourceRoomAmbientBlue;
                accumulate_source_lighting(
                    vertex.x, vertex.y, vertex.z,
                    vertex.nx, vertex.ny, vertex.nz,
                    red, green, blue, selection & static_mask);
                float* destination =
                    g_room_static_lighting + vertex_index * 3U;
                destination[0] = red;
                destination[1] = green;
                destination[2] = blue;
            }
        }
    }
    return true;
}

unsigned selected_light_count(std::uint32_t selection) {
    unsigned count = 0U;
    while(selection != 0U) {
        selection &= selection - 1U;
        ++count;
    }
    return count;
}
#else
std::uint32_t source_group_light_selection(
    const re4dc::room::SourceGroup*) {
    return 0xffffffffU;
}
#endif

float camera_depth(float reciprocal_depth) {
    if(!std::isfinite(reciprocal_depth) ||
       std::fabs(reciprocal_depth) < 0.000001f) {
        return 0.0f;
    }
    return 1.0f / reciprocal_depth;
}

RenderVertex interpolate_vertex(const RenderVertex& a, const RenderVertex& b,
                                float t) {
    RenderVertex result{};
    result.position.world_x = a.position.world_x +
                              (b.position.world_x - a.position.world_x) * t;
    result.position.world_y = a.position.world_y +
                              (b.position.world_y - a.position.world_y) * t;
    result.position.world_z = a.position.world_z +
                              (b.position.world_z - a.position.world_z) * t;
    result.position.depth = a.position.depth +
                            (b.position.depth - a.position.depth) * t;
    result.u = a.u + (b.u - a.u) * t;
    result.v = a.v + (b.v - a.v) * t;
    result.light_red = a.light_red + (b.light_red - a.light_red) * t;
    result.light_green =
        a.light_green + (b.light_green - a.light_green) * t;
    result.light_blue = a.light_blue + (b.light_blue - a.light_blue) * t;
    result.offset_color = a.offset_color;
    float x = result.position.world_x;
    float y = result.position.world_y;
    float z = result.position.world_z;
    mat_trans_single(x, y, z);
    result.position.x = x;
    result.position.y = y;
    result.position.z = z;
    return result;
}

std::uint32_t clip_projected_triangle(const RenderVertex* source,
                                       pvr_vertex_t* output,
                                       std::uint8_t cull_mode,
                                       FrameStats* stats = nullptr) {
    RenderVertex clipped[4]{};
    unsigned clipped_count = 0;
    unsigned inside_count = 0;
    for(unsigned corner = 0; corner < 3; ++corner) {
        inside_count +=
            source[corner].position.depth >= kNearClipDistance ? 1U : 0U;
    }
    if(inside_count == 3U) {
        if(stats != nullptr) {
            ++stats->room_near_trivial_accepts;
        }
        clipped[0] = source[0];
        clipped[1] = source[1];
        clipped[2] = source[2];
        clipped_count = 3U;
    } else if(inside_count == 0U) {
        if(stats != nullptr) {
            ++stats->room_near_trivial_rejects;
        }
        return 0;
    } else {
        if(stats != nullptr) {
            ++stats->room_near_crossings;
        }
        RenderVertex previous = source[2];
        bool previous_inside =
            previous.position.depth >= kNearClipDistance;
        for(unsigned corner = 0; corner < 3; ++corner) {
            const RenderVertex current = source[corner];
            const bool current_inside =
                current.position.depth >= kNearClipDistance;
            if(current_inside != previous_inside) {
                const float t =
                    (kNearClipDistance - previous.position.depth) /
                    (current.position.depth - previous.position.depth);
                clipped[clipped_count++] =
                    interpolate_vertex(previous, current, t);
            }
            if(current_inside) {
                clipped[clipped_count++] = current;
            }
            previous = current;
            previous_inside = current_inside;
        }
    }
    if(clipped_count < 3) {
        return 0;
    }

    std::uint32_t triangle_count = 0;
    for(unsigned fan = 1; fan + 1 < clipped_count; ++fan) {
        const RenderVertex triangle[3] = {clipped[0], clipped[fan],
                                          clipped[fan + 1]};
        const float signed_area =
            (triangle[1].position.x - triangle[0].position.x) *
                (triangle[2].position.y - triangle[0].position.y) -
            (triangle[1].position.y - triangle[0].position.y) *
                (triangle[2].position.x - triangle[0].position.x);
        const bool beyond_far =
            triangle[0].position.depth > kFarClipDistance &&
            triangle[1].position.depth > kFarClipDistance &&
            triangle[2].position.depth > kFarClipDistance;
        const bool left = triangle[0].position.x < 0.0f &&
                          triangle[1].position.x < 0.0f &&
                          triangle[2].position.x < 0.0f;
        const bool right = triangle[0].position.x > kScreenWidth &&
                           triangle[1].position.x > kScreenWidth &&
                           triangle[2].position.x > kScreenWidth;
        const bool above = triangle[0].position.y < 0.0f &&
                           triangle[1].position.y < 0.0f &&
                           triangle[2].position.y < 0.0f;
        const bool below = triangle[0].position.y > kScreenHeight &&
                           triangle[1].position.y > kScreenHeight &&
                           triangle[2].position.y > kScreenHeight;
        const bool culled =
            cull_mode == kCullAll ||
            (cull_mode == kCullBack && signed_area >= 0.0f) ||
            (cull_mode == kCullFront && signed_area <= 0.0f) ||
            (cull_mode == kCullNone &&
             std::fabs(signed_area) < 0.0001f);
        if(beyond_far || left || right || above || below || culled) {
            continue;
        }
        pvr_vertex_t* destination = output + triangle_count * 3U;
        for(unsigned corner = 0; corner < 3; ++corner) {
            destination[corner] = {
                .flags = corner == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
                .x = triangle[corner].position.x,
                .y = triangle[corner].position.y,
                .z = triangle[corner].position.z,
                .u = triangle[corner].u,
                .v = triangle[corner].v,
                .argb = shade_color(triangle[corner].light_red,
                                    triangle[corner].light_green,
                                    triangle[corner].light_blue),
                .oargb = triangle[corner].offset_color,
            };
        }
        ++triangle_count;
    }
    return triangle_count;
}

const RenderVertex& cached_room_vertex(
    const re4dc::room::Vertex* source, std::uint32_t vertex_index,
    FrameStats& stats, std::uint32_t light_selection) {
    ++stats.room_index_references;
    const std::uint32_t slot =
        ((vertex_index * 2654435761U) ^ (light_selection * 2246822519U)) &
        (kRoomVertexCacheCapacity - 1U);
    RoomVertexCacheEntry& entry = g_room_vertex_cache[slot];
    if(entry.generation == g_room_vertex_cache_generation &&
       entry.source_index == vertex_index &&
       entry.light_selection == light_selection) {
        ++stats.room_cache_hits;
        return entry.vertex;
    }

    ++stats.room_cache_misses;
    ++stats.transformed_vertices;
    const re4dc::room::Vertex& input = source[vertex_index];
    float x = input.x;
    float y = input.y;
    float z = input.z;
    mat_trans_single(x, y, z);
    float light_red = 0.0f;
    float light_green = 0.0f;
    float light_blue = 0.0f;
#if defined(RE4DC_SCENE_R100)
    if(vertex_index < kRoomStaticLightingVertexCapacity &&
       g_room_static_lighting_owner[vertex_index] <
           kRoomLightingConflicted) {
        const float* source = g_room_static_lighting + vertex_index * 3U;
        light_red = source[0];
        light_green = source[1];
        light_blue = source[2];
        const std::uint32_t dynamic_selection =
            light_selection & g_source_dynamic_light_mask;
        if(g_room_dynamic_light_fast_path && g_room_normals_are_unit) {
            accumulate_room_dynamic_lighting(
                input.nx, input.ny, input.nz,
                light_red, light_green, light_blue, dynamic_selection);
        } else {
            accumulate_source_lighting(
                input.x, input.y, input.z,
                input.nx, input.ny, input.nz,
                light_red, light_green, light_blue, dynamic_selection,
                g_room_normals_are_unit);
        }
        light_red = std::clamp(light_red, 0.0f, 1.0f);
        light_green = std::clamp(light_green, 0.0f, 1.0f);
        light_blue = std::clamp(light_blue, 0.0f, 1.0f);
    } else {
        evaluate_source_lighting(input.x, input.y, input.z,
                                 input.nx, input.ny, input.nz, false,
                                 light_red, light_green, light_blue,
                                 light_selection);
    }
    ++stats.room_light_evaluations;
#else
    light_red = light_green = light_blue = std::clamp(
        0.76f + 0.08f * input.nx + 0.12f * input.ny +
            0.04f * input.nz,
        0.58f, 1.0f);
#endif
    entry.generation = g_room_vertex_cache_generation;
    entry.source_index = vertex_index;
    entry.light_selection = light_selection;
    entry.vertex = {
        .position = {
            x,
            y,
            z,
            input.x,
            input.y,
            input.z,
            camera_depth(z),
        },
        .u = input.u,
        .v = input.v,
        .light_red = light_red,
        .light_green = light_green,
        .light_blue = light_blue,
        .offset_color = 0,
    };
    return entry.vertex;
}

std::uint32_t transform_triangle(const re4dc::room::Vertex* source,
                                  const std::uint32_t* indices,
                                  pvr_vertex_t* output,
                                  FrameStats& stats,
                                  std::uint8_t cull_mode,
                                  std::uint32_t light_selection) {
    const RenderVertex triangle[3] = {
        cached_room_vertex(source, indices[0], stats, light_selection),
        cached_room_vertex(source, indices[1], stats, light_selection),
        cached_room_vertex(source, indices[2], stats, light_selection),
    };
    return clip_projected_triangle(triangle, output, cull_mode, &stats);
}

void submit_room_strips(const re4dc::room::Package& room,
                        const re4dc::room::Batch& batch,
                        const pvr_poly_hdr_t& header,
                        pvr_vertex_t* submit_vertices,
                        std::uint32_t submit_capacity,
                        FrameStats& stats, std::uint8_t cull_mode,
                        std::uint32_t light_selection) {
    const auto* source = room.vertices();
    const auto* primitives = room.primitives();
    const auto* primitive_indices = room.primitive_indices();
    std::uint32_t submit_count = 0U;
    begin_pvr_packet(submit_vertices, submit_count, header);
    const auto flush = [&]() {
        if(submit_count == 0U) {
            return;
        }
        submit_pvr(stats, submit_vertices,
                   sizeof(pvr_vertex_t) * submit_count);
        submit_count = 0U;
    };
    const auto append_triangle = [&](const RenderVertex* triangle) {
        if(submit_count + 6U > submit_capacity) {
            flush();
        }
        const std::uint32_t emitted = clip_projected_triangle(
            triangle, submit_vertices + submit_count, cull_mode, &stats);
        submit_count += emitted * 3U;
        stats.room_vertex_records += emitted * 3U;
        stats.triangles += emitted;
    };

    const std::uint32_t primitive_end =
        batch.first_primitive + batch.primitive_count;
    for(std::uint32_t primitive_index = batch.first_primitive;
        primitive_index < primitive_end; ++primitive_index) {
        const auto& primitive = primitives[primitive_index];
        bool direct_strip = primitive.vertex_count <= submit_capacity;
        if(direct_strip) {
            for(std::uint32_t local = 0U; local < primitive.vertex_count;
                ++local) {
                const std::uint32_t vertex_index =
                    primitive_indices[primitive.first_vertex + local];
                g_room_strip_vertices[local] = cached_room_vertex(
                    source, vertex_index, stats, light_selection);
                const float depth =
                    g_room_strip_vertices[local].position.depth;
                if(depth < kNearClipDistance || depth > kFarClipDistance) {
                    direct_strip = false;
                }
            }
        }
        if(direct_strip) {
            if(submit_count + primitive.vertex_count > submit_capacity) {
                flush();
            }
            for(std::uint32_t local = 0U; local < primitive.vertex_count;
                ++local) {
                const auto& vertex = g_room_strip_vertices[local];
                submit_vertices[submit_count++] = {
                    .flags = local + 1U == primitive.vertex_count
                                 ? PVR_CMD_VERTEX_EOL
                                 : PVR_CMD_VERTEX,
                    .x = vertex.position.x,
                    .y = vertex.position.y,
                    .z = vertex.position.z,
                    .u = vertex.u,
                    .v = vertex.v,
                    .argb = shade_color(vertex.light_red,
                                        vertex.light_green,
                                        vertex.light_blue),
                    .oargb = vertex.offset_color,
                };
            }
            stats.room_vertex_records += primitive.vertex_count;
            ++stats.room_direct_strips;
            stats.triangles += primitive.triangle_count;
            continue;
        }

        ++stats.room_strip_fallbacks;
        for(std::uint32_t local = 2U; local < primitive.vertex_count;
            ++local) {
            const std::uint32_t local_indices[3] = {
                (local & 1U) != 0U ? local - 1U : local - 2U,
                (local & 1U) != 0U ? local - 2U : local - 1U,
                local,
            };
            RenderVertex triangle[3]{};
            for(unsigned corner = 0U; corner < 3U; ++corner) {
                const std::uint32_t strip_vertex = local_indices[corner];
                if(primitive.vertex_count <= submit_capacity) {
                    triangle[corner] = g_room_strip_vertices[strip_vertex];
                } else {
                    triangle[corner] = cached_room_vertex(
                        source,
                        primitive_indices[primitive.first_vertex +
                                          strip_vertex],
                        stats, light_selection);
                }
            }
            append_triangle(triangle);
        }
    }
    flush();
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

void transform_pose_position(
    const PreparedPoseMatrix* matrices,
    const re4dc::character::PositionRecord& position,
    float& x, float& y, float& z) {
    const auto& matrix = matrices[position.matrix];
    x = matrix.linear[0] * position.x +
        matrix.linear[1] * position.y + matrix.linear[2] * position.z +
        matrix.translation[0];
    y = matrix.linear[3] * position.x +
        matrix.linear[4] * position.y + matrix.linear[5] * position.z +
        matrix.translation[1];
    z = matrix.linear[6] * position.x +
        matrix.linear[7] * position.y + matrix.linear[8] * position.z +
        matrix.translation[2];
}

void prepare_pose_palette(
    const re4dc::character::PoseMatrix* source,
    const re4dc::character::PoseMatrix* next_source, float frame_blend,
    const re4dc::character::PoseMatrix* secondary_source,
    const re4dc::character::PoseMatrix* secondary_next_source,
    float secondary_frame_blend, float pose_blend,
    std::uint32_t matrix_count, PreparedPoseMatrix* prepared) {
    constexpr float kMatrixScale = 1.0f / 32767.0f;
    for(std::uint32_t matrix = 0U; matrix < matrix_count; ++matrix) {
        for(unsigned element = 0U; element < 9U; ++element) {
            float value =
                (static_cast<float>(source[matrix].linear[element]) +
                 (static_cast<float>(next_source[matrix].linear[element]) -
                  static_cast<float>(source[matrix].linear[element])) *
                     frame_blend) * kMatrixScale;
            if(secondary_source != nullptr) {
                const float secondary_value =
                    (static_cast<float>(
                         secondary_source[matrix].linear[element]) +
                     (static_cast<float>(
                          secondary_next_source[matrix].linear[element]) -
                      static_cast<float>(
                          secondary_source[matrix].linear[element])) *
                         secondary_frame_blend) * kMatrixScale;
                value += (secondary_value - value) * pose_blend;
            }
            prepared[matrix].linear[element] = value;
        }
        for(unsigned element = 0U; element < 3U; ++element) {
            float value =
                source[matrix].translation[element] +
                (next_source[matrix].translation[element] -
                 source[matrix].translation[element]) * frame_blend;
            if(secondary_source != nullptr) {
                const float secondary_value =
                    secondary_source[matrix].translation[element] +
                    (secondary_next_source[matrix].translation[element] -
                     secondary_source[matrix].translation[element]) *
                        secondary_frame_blend;
                value += (secondary_value - value) * pose_blend;
            }
            prepared[matrix].translation[element] = value;
        }
    }
}

void project_palette_character(
    const re4dc::character::Package& character,
    float actor_x, float actor_y, float actor_z, float actor_yaw,
    std::uint32_t animation_clip, float animation_frame, bool loop,
    std::uint32_t secondary_clip, float pose_blend,
    ProjectedVertex* projected, PreparedPoseMatrix* prepared_pose) {
    const auto& clip = character.clips()[animation_clip];
    const float wrapped_frame = std::fmod(
        std::max(animation_frame, 0.0f), static_cast<float>(clip.frame_count));
    const std::uint32_t local_frame = static_cast<std::uint32_t>(wrapped_frame);
    const std::uint32_t next_frame = loop
        ? (local_frame + 1U) % clip.frame_count
        : std::min(local_frame + 1U, clip.frame_count - 1U);
    const float frame_blend = wrapped_frame - static_cast<float>(local_frame);
    const auto* source = character.frame_pose_matrices(
        clip.first_frame + local_frame);
    const auto* next_source = character.frame_pose_matrices(
        clip.first_frame + next_frame);
    const auto* markers = character.frame_marker_positions(
        clip.first_frame + local_frame);
    const auto* next_markers = character.frame_marker_positions(
        clip.first_frame + next_frame);
    const re4dc::character::PoseMatrix* secondary_source = nullptr;
    const re4dc::character::PoseMatrix* secondary_next_source = nullptr;
    const std::int16_t* secondary_markers = nullptr;
    const std::int16_t* secondary_next_markers = nullptr;
    float secondary_frame_blend = 0.0f;
    if(pose_blend > 0.0f && secondary_clip != animation_clip) {
        const auto& secondary = character.clips()[secondary_clip];
        const float secondary_time_frame = std::max(
            animation_frame * secondary.frames_per_second /
                clip.frames_per_second,
            0.0f);
        const float secondary_frame = loop
            ? std::fmod(secondary_time_frame,
                        static_cast<float>(secondary.frame_count))
            : std::min(secondary_time_frame,
                       static_cast<float>(secondary.frame_count - 1U));
        const std::uint32_t secondary_local =
            static_cast<std::uint32_t>(secondary_frame);
        const std::uint32_t secondary_next = loop
            ? (secondary_local + 1U) % secondary.frame_count
            : std::min(secondary_local + 1U, secondary.frame_count - 1U);
        secondary_frame_blend =
            secondary_frame - static_cast<float>(secondary_local);
        secondary_source = character.frame_pose_matrices(
            secondary.first_frame + secondary_local);
        secondary_next_source = character.frame_pose_matrices(
            secondary.first_frame + secondary_next);
        secondary_markers = character.frame_marker_positions(
            secondary.first_frame + secondary_local);
        secondary_next_markers = character.frame_marker_positions(
            secondary.first_frame + secondary_next);
    }
    prepare_pose_palette(
        source, next_source, frame_blend,
        secondary_source, secondary_next_source, secondary_frame_blend,
        pose_blend, character.header().normal_matrix_count, prepared_pose);
    const float sine = std::sin(actor_yaw);
    const float cosine = std::cos(actor_yaw);
    const auto project = [&](std::uint32_t index,
                             float local_x, float local_y, float local_z) {
        local_x *= 0.001f;
        local_y *= 0.001f;
        local_z *= 0.001f;
        float x = actor_x + local_x * cosine + local_z * sine;
        float y = actor_y + local_y;
        float z = actor_z - local_x * sine + local_z * cosine;
        const float world_x = x;
        const float world_y = y;
        const float world_z = z;
        mat_trans_single(x, y, z);
        projected[index] = {
            x, y, z, world_x, world_y, world_z, camera_depth(z)};
    };
    const auto* positions = character.position_records();
    for(std::uint32_t index = 0U;
        index < character.header().skinned_position_count; ++index) {
        float local_x = 0.0f;
        float local_y = 0.0f;
        float local_z = 0.0f;
        transform_pose_position(
            prepared_pose, positions[index], local_x, local_y, local_z);
        project(index, local_x, local_y, local_z);
    }
    const std::uint32_t marker_count =
        character.header().position_count -
        character.header().skinned_position_count;
    const float marker_scale = character.header().position_quantum_m * 1000.0f;
    for(std::uint32_t marker = 0U; marker < marker_count; ++marker) {
        const std::uint32_t offset = marker * 3U;
        float local_x =
            (static_cast<float>(markers[offset]) +
             (static_cast<float>(next_markers[offset]) -
              static_cast<float>(markers[offset])) * frame_blend) * marker_scale;
        float local_y =
            (static_cast<float>(markers[offset + 1U]) +
             (static_cast<float>(next_markers[offset + 1U]) -
              static_cast<float>(markers[offset + 1U])) * frame_blend) * marker_scale;
        float local_z =
            (static_cast<float>(markers[offset + 2U]) +
             (static_cast<float>(next_markers[offset + 2U]) -
              static_cast<float>(markers[offset + 2U])) * frame_blend) * marker_scale;
        if(secondary_markers != nullptr) {
            float secondary_x =
                (static_cast<float>(secondary_markers[offset]) +
                 (static_cast<float>(secondary_next_markers[offset]) -
                  static_cast<float>(secondary_markers[offset])) *
                     secondary_frame_blend) * marker_scale;
            float secondary_y =
                (static_cast<float>(secondary_markers[offset + 1U]) +
                 (static_cast<float>(secondary_next_markers[offset + 1U]) -
                  static_cast<float>(secondary_markers[offset + 1U])) *
                     secondary_frame_blend) * marker_scale;
            float secondary_z =
                (static_cast<float>(secondary_markers[offset + 2U]) +
                 (static_cast<float>(secondary_next_markers[offset + 2U]) -
                  static_cast<float>(secondary_markers[offset + 2U])) *
                     secondary_frame_blend) * marker_scale;
            local_x += (secondary_x - local_x) * pose_blend;
            local_y += (secondary_y - local_y) * pose_blend;
            local_z += (secondary_z - local_z) * pose_blend;
        }
        project(character.header().skinned_position_count + marker,
                local_x, local_y, local_z);
    }
}

void project_character(const re4dc::character::Package& character,
                       float actor_x, float actor_y, float actor_z,
                       float actor_yaw, std::uint32_t animation_clip,
                       float animation_frame, bool loop,
                       std::uint32_t secondary_clip, float pose_blend,
                       ProjectedVertex* projected,
                       PreparedPoseMatrix* prepared_pose) {
    if(character.header().version == re4dc::character::kVersion &&
       character.header().skinned_position_count != 0U) {
        project_palette_character(
            character, actor_x, actor_y, actor_z, actor_yaw,
            animation_clip, animation_frame, loop, secondary_clip,
            pose_blend, projected, prepared_pose);
        return;
    }
    const auto& clip = character.clips()[animation_clip];
    const float wrapped_frame = std::fmod(
        std::max(animation_frame, 0.0f), static_cast<float>(clip.frame_count));
    const std::uint32_t local_frame = static_cast<std::uint32_t>(wrapped_frame);
    const std::uint32_t next_frame = loop
        ? (local_frame + 1U) % clip.frame_count
        : std::min(local_frame + 1U, clip.frame_count - 1U);
    const float frame_blend = wrapped_frame - static_cast<float>(local_frame);
    const auto* source = character.frame_positions(clip.first_frame + local_frame);
    const auto* next_source = character.frame_positions(
        clip.first_frame + next_frame);
    const std::int16_t* secondary_source = nullptr;
    const std::int16_t* secondary_next_source = nullptr;
    float secondary_frame_blend = 0.0f;
    if(pose_blend > 0.0f && secondary_clip != animation_clip) {
        const auto& secondary = character.clips()[secondary_clip];
        const float secondary_time_frame = std::max(
            animation_frame * secondary.frames_per_second /
                clip.frames_per_second,
            0.0f);
        const float secondary_frame = loop
            ? std::fmod(secondary_time_frame,
                        static_cast<float>(secondary.frame_count))
            : std::min(secondary_time_frame,
                       static_cast<float>(secondary.frame_count - 1U));
        const std::uint32_t secondary_local =
            static_cast<std::uint32_t>(secondary_frame);
        const std::uint32_t secondary_next = loop
            ? (secondary_local + 1U) % secondary.frame_count
            : std::min(secondary_local + 1U, secondary.frame_count - 1U);
        secondary_frame_blend =
            secondary_frame - static_cast<float>(secondary_local);
        secondary_source = character.frame_positions(
            secondary.first_frame + secondary_local);
        secondary_next_source = character.frame_positions(
            secondary.first_frame + secondary_next);
    }
    const float scale = character.header().position_quantum_m;
    const float sine = std::sin(actor_yaw);
    const float cosine = std::cos(actor_yaw);
    for(std::uint32_t index = 0;
        index < character.header().position_count; ++index) {
        float local_x =
            (static_cast<float>(source[index * 3U]) +
             (static_cast<float>(next_source[index * 3U]) -
              static_cast<float>(source[index * 3U])) * frame_blend) * scale;
        float local_y =
            (static_cast<float>(source[index * 3U + 1U]) +
             (static_cast<float>(next_source[index * 3U + 1U]) -
              static_cast<float>(source[index * 3U + 1U])) * frame_blend) * scale;
        float local_z =
            (static_cast<float>(source[index * 3U + 2U]) +
             (static_cast<float>(next_source[index * 3U + 2U]) -
              static_cast<float>(source[index * 3U + 2U])) * frame_blend) * scale;
        if(secondary_source != nullptr) {
            const float secondary_x =
                (static_cast<float>(secondary_source[index * 3U]) +
                 (static_cast<float>(secondary_next_source[index * 3U]) -
                  static_cast<float>(secondary_source[index * 3U])) *
                     secondary_frame_blend) * scale;
            const float secondary_y =
                (static_cast<float>(secondary_source[index * 3U + 1U]) +
                 (static_cast<float>(secondary_next_source[index * 3U + 1U]) -
                  static_cast<float>(secondary_source[index * 3U + 1U])) *
                     secondary_frame_blend) * scale;
            const float secondary_z =
                (static_cast<float>(secondary_source[index * 3U + 2U]) +
                 (static_cast<float>(secondary_next_source[index * 3U + 2U]) -
                  static_cast<float>(secondary_source[index * 3U + 2U])) *
                     secondary_frame_blend) * scale;
            local_x += (secondary_x - local_x) * pose_blend;
            local_y += (secondary_y - local_y) * pose_blend;
            local_z += (secondary_z - local_z) * pose_blend;
        }
        float x = actor_x + local_x * cosine + local_z * sine;
        float y = actor_y + local_y;
        float z = actor_z - local_x * sine + local_z * cosine;
        const float world_x = x;
        const float world_y = y;
        const float world_z = z;
        mat_trans_single(x, y, z);
        projected[index] = {
            x, y, z, world_x, world_y, world_z, camera_depth(z)};
    }
}

#if defined(RE4DC_SCENE_R100)
void build_character_normals(const re4dc::character::Package& character,
                             const ProjectedVertex* projected,
                             float* normals) {
    const std::uint32_t normal_count = character.header().normal_count;
    std::fill(normals, normals + normal_count * 3U, 0.0f);
    const auto* indices = character.indices();
    const auto* draw_vertices = character.draw_vertices();
    for(std::uint32_t index = 0; index < character.header().index_count;
        index += 3U) {
        const auto& v0 = draw_vertices[indices[index]];
        const auto& v1 = draw_vertices[indices[index + 1U]];
        const auto& v2 = draw_vertices[indices[index + 2U]];
        const ProjectedVertex& p0 = projected[v0.position];
        const ProjectedVertex& p1 = projected[v1.position];
        const ProjectedVertex& p2 = projected[v2.position];
        const float edge1_x = p1.world_x - p0.world_x;
        const float edge1_y = p1.world_y - p0.world_y;
        const float edge1_z = p1.world_z - p0.world_z;
        const float edge2_x = p2.world_x - p0.world_x;
        const float edge2_y = p2.world_y - p0.world_y;
        const float edge2_z = p2.world_z - p0.world_z;
        const float nx = edge1_y * edge2_z - edge1_z * edge2_y;
        const float ny = edge1_z * edge2_x - edge1_x * edge2_z;
        const float nz = edge1_x * edge2_y - edge1_y * edge2_x;
        for(const std::uint16_t normal : {v0.normal, v1.normal, v2.normal}) {
            normals[normal * 3U] += nx;
            normals[normal * 3U + 1U] += ny;
            normals[normal * 3U + 2U] += nz;
        }
    }
    for(std::uint32_t normal = 0; normal < normal_count; ++normal) {
        normalize_vector(normals[normal * 3U], normals[normal * 3U + 1U],
                         normals[normal * 3U + 2U]);
    }
}

void transform_source_normal(
    const std::int16_t* matrices,
    const re4dc::character::SourceNormal& normal,
    float& x, float& y, float& z) {
    constexpr float kNormalScale = 1.0f / 16384.0f;
    constexpr float kMatrixScale = 1.0f / 32767.0f;
    const float source_x = static_cast<float>(normal.x) * kNormalScale;
    const float source_y = static_cast<float>(normal.y) * kNormalScale;
    const float source_z = static_cast<float>(normal.z) * kNormalScale;
    const std::int16_t* matrix = matrices + normal.matrix * 9U;
    x = (static_cast<float>(matrix[0]) * source_x +
         static_cast<float>(matrix[1]) * source_y +
         static_cast<float>(matrix[2]) * source_z) * kMatrixScale;
    y = (static_cast<float>(matrix[3]) * source_x +
         static_cast<float>(matrix[4]) * source_y +
         static_cast<float>(matrix[5]) * source_z) * kMatrixScale;
    z = (static_cast<float>(matrix[6]) * source_x +
         static_cast<float>(matrix[7]) * source_y +
         static_cast<float>(matrix[8]) * source_z) * kMatrixScale;
}

void transform_source_normal(
    const re4dc::character::PoseMatrix* matrices,
    const re4dc::character::SourceNormal& normal,
    float& x, float& y, float& z) {
    constexpr float kNormalScale = 1.0f / 16384.0f;
    constexpr float kMatrixScale = 1.0f / 32767.0f;
    const float source_x = static_cast<float>(normal.x) * kNormalScale;
    const float source_y = static_cast<float>(normal.y) * kNormalScale;
    const float source_z = static_cast<float>(normal.z) * kNormalScale;
    const auto& matrix = matrices[normal.matrix];
    x = (static_cast<float>(matrix.linear[0]) * source_x +
         static_cast<float>(matrix.linear[1]) * source_y +
         static_cast<float>(matrix.linear[2]) * source_z) * kMatrixScale;
    y = (static_cast<float>(matrix.linear[3]) * source_x +
         static_cast<float>(matrix.linear[4]) * source_y +
         static_cast<float>(matrix.linear[5]) * source_z) * kMatrixScale;
    z = (static_cast<float>(matrix.linear[6]) * source_x +
         static_cast<float>(matrix.linear[7]) * source_y +
         static_cast<float>(matrix.linear[8]) * source_z) * kMatrixScale;
}

void transform_source_normal(
    const PreparedPoseMatrix* matrices,
    const re4dc::character::SourceNormal& normal,
    float& x, float& y, float& z) {
    constexpr float kNormalScale = 1.0f / 16384.0f;
    const float source_x = static_cast<float>(normal.x) * kNormalScale;
    const float source_y = static_cast<float>(normal.y) * kNormalScale;
    const float source_z = static_cast<float>(normal.z) * kNormalScale;
    const auto& matrix = matrices[normal.matrix];
    x = matrix.linear[0] * source_x + matrix.linear[1] * source_y +
        matrix.linear[2] * source_z;
    y = matrix.linear[3] * source_x + matrix.linear[4] * source_y +
        matrix.linear[5] * source_z;
    z = matrix.linear[6] * source_x + matrix.linear[7] * source_y +
        matrix.linear[8] * source_z;
}

void build_character_source_normals(
    const re4dc::character::Package& character, float actor_yaw,
    std::uint32_t animation_clip, float animation_frame, bool loop,
    std::uint32_t secondary_clip, float pose_blend, float* normals,
    const PreparedPoseMatrix* prepared_pose) {
    if(prepared_pose != nullptr) {
        const float sine = std::sin(actor_yaw);
        const float cosine = std::cos(actor_yaw);
        const auto* source_normals = character.source_normals();
        for(std::uint32_t index = 0U;
            index < character.header().source_normal_count; ++index) {
            float local_x = 0.0f;
            float local_y = 0.0f;
            float local_z = 0.0f;
            transform_source_normal(
                prepared_pose, source_normals[index],
                local_x, local_y, local_z);
            normals[index * 3U] = local_x * cosine + local_z * sine;
            normals[index * 3U + 1U] = local_y;
            normals[index * 3U + 2U] =
                -local_x * sine + local_z * cosine;
        }
        return;
    }
    const auto& clip = character.clips()[animation_clip];
    const float wrapped_frame = std::fmod(
        std::max(animation_frame, 0.0f), static_cast<float>(clip.frame_count));
    const std::uint32_t local_frame = static_cast<std::uint32_t>(wrapped_frame);
    const std::uint32_t next_frame = loop
        ? (local_frame + 1U) % clip.frame_count
        : std::min(local_frame + 1U, clip.frame_count - 1U);
    const float frame_blend = wrapped_frame - static_cast<float>(local_frame);
    const std::int16_t* source = character.frame_normal_matrices(
        clip.first_frame + local_frame);
    const std::int16_t* next_source = character.frame_normal_matrices(
        clip.first_frame + next_frame);
    const auto* pose_source = character.frame_pose_matrices(
        clip.first_frame + local_frame);
    const auto* pose_next_source = character.frame_pose_matrices(
        clip.first_frame + next_frame);
    const std::int16_t* secondary_source = nullptr;
    const std::int16_t* secondary_next_source = nullptr;
    const re4dc::character::PoseMatrix* secondary_pose_source = nullptr;
    const re4dc::character::PoseMatrix* secondary_pose_next_source = nullptr;
    float secondary_frame_blend = 0.0f;
    if(pose_blend > 0.0f && secondary_clip != animation_clip) {
        const auto& secondary = character.clips()[secondary_clip];
        const float secondary_time_frame = std::max(
            animation_frame * secondary.frames_per_second /
                clip.frames_per_second,
            0.0f);
        const float secondary_frame = loop
            ? std::fmod(secondary_time_frame,
                        static_cast<float>(secondary.frame_count))
            : std::min(secondary_time_frame,
                       static_cast<float>(secondary.frame_count - 1U));
        const std::uint32_t secondary_local =
            static_cast<std::uint32_t>(secondary_frame);
        const std::uint32_t secondary_next = loop
            ? (secondary_local + 1U) % secondary.frame_count
            : std::min(secondary_local + 1U, secondary.frame_count - 1U);
        secondary_frame_blend =
            secondary_frame - static_cast<float>(secondary_local);
        secondary_source = character.frame_normal_matrices(
            secondary.first_frame + secondary_local);
        secondary_next_source = character.frame_normal_matrices(
            secondary.first_frame + secondary_next);
        secondary_pose_source = character.frame_pose_matrices(
            secondary.first_frame + secondary_local);
        secondary_pose_next_source = character.frame_pose_matrices(
            secondary.first_frame + secondary_next);
    }
    const float sine = std::sin(actor_yaw);
    const float cosine = std::cos(actor_yaw);
    const auto* source_normals = character.source_normals();
    const auto transform = [&](const std::int16_t* legacy_matrices,
                               const re4dc::character::PoseMatrix* pose_matrices,
                               const re4dc::character::SourceNormal& normal,
                               float& x, float& y, float& z) {
        if(pose_matrices != nullptr) {
            transform_source_normal(pose_matrices, normal, x, y, z);
        } else {
            transform_source_normal(legacy_matrices, normal, x, y, z);
        }
    };
    for(std::uint32_t index = 0U;
        index < character.header().source_normal_count; ++index) {
        float current_x = 0.0f;
        float current_y = 0.0f;
        float current_z = 0.0f;
        float next_x = 0.0f;
        float next_y = 0.0f;
        float next_z = 0.0f;
        transform(source, pose_source, source_normals[index],
                  current_x, current_y, current_z);
        transform(next_source, pose_next_source, source_normals[index],
                  next_x, next_y, next_z);
        float local_x = current_x + (next_x - current_x) * frame_blend;
        float local_y = current_y + (next_y - current_y) * frame_blend;
        float local_z = current_z + (next_z - current_z) * frame_blend;
        if(secondary_source != nullptr || secondary_pose_source != nullptr) {
            float secondary_x = 0.0f;
            float secondary_y = 0.0f;
            float secondary_z = 0.0f;
            float secondary_next_x = 0.0f;
            float secondary_next_y = 0.0f;
            float secondary_next_z = 0.0f;
            transform(secondary_source, secondary_pose_source,
                      source_normals[index],
                      secondary_x, secondary_y, secondary_z);
            transform(secondary_next_source, secondary_pose_next_source,
                      source_normals[index],
                      secondary_next_x, secondary_next_y, secondary_next_z);
            secondary_x +=
                (secondary_next_x - secondary_x) * secondary_frame_blend;
            secondary_y +=
                (secondary_next_y - secondary_y) * secondary_frame_blend;
            secondary_z +=
                (secondary_next_z - secondary_z) * secondary_frame_blend;
            local_x += (secondary_x - local_x) * pose_blend;
            local_y += (secondary_y - local_y) * pose_blend;
            local_z += (secondary_z - local_z) * pose_blend;
        }
        normals[index * 3U] = local_x * cosine + local_z * sine;
        normals[index * 3U + 1U] = local_y;
        normals[index * 3U + 2U] = -local_x * sine + local_z * cosine;
    }
}

void build_character_lighting(const re4dc::character::Package& character,
                              const ProjectedVertex* projected,
                              const float* normals, float* lighting,
                              std::uint32_t* colors,
                              const SelectedSourceLights& light_selection) {
    const auto* normal_positions = character.normal_positions();
    const auto* normal_sources = character.normal_sources();
    for(std::uint32_t normal = 0; normal < character.header().normal_count;
        ++normal) {
        const ProjectedVertex& position = projected[normal_positions[normal]];
        const std::uint32_t source_normal = normal_sources != nullptr
            ? normal_sources[normal]
            : normal;
        evaluate_selected_actor_lighting(
            position.world_x, position.world_y, position.world_z,
            normals[source_normal * 3U], normals[source_normal * 3U + 1U],
            normals[source_normal * 3U + 2U], light_selection,
            lighting[normal * 3U],
            lighting[normal * 3U + 1U], lighting[normal * 3U + 2U]);
        colors[normal] = shade_color(
            lighting[normal * 3U], lighting[normal * 3U + 1U],
            lighting[normal * 3U + 2U]);
    }
}
#endif

std::uint32_t draw_character(const re4dc::character::Package& character,
                             const ProjectedVertex* projected,
#if defined(RE4DC_SCENE_R100)
                             const float* lighting,
                             const std::uint32_t* colors,
#endif
                             const pvr_poly_hdr_t* material_headers,
                             const bool* material_alpha, bool alpha_pass,
                             pvr_vertex_t* submit_vertices,
                             std::uint32_t submit_capacity,
                             FrameStats& stats) {
    const auto* indices = character.indices();
    const auto* primitives = character.primitives();
    const auto* primitive_indices = character.primitive_indices();
    const auto* draw_vertices = character.draw_vertices();
    std::uint32_t triangles = 0;
    for(std::uint32_t batch_index = 0;
        batch_index < character.header().batch_count; ++batch_index) {
        const auto& batch = character.batches()[batch_index];
        if(material_alpha[batch_index] != alpha_pass) {
            continue;
        }
        std::uint32_t submit_count = 0;
        begin_pvr_packet(submit_vertices, submit_count,
                         material_headers[batch_index]);
        const auto flush = [&]() {
            if(submit_count == 0U) {
                return;
            }
            submit_pvr(stats, submit_vertices,
                       sizeof(pvr_vertex_t) * submit_count);
            submit_count = 0;
        };
        const auto submit_triangle_range = [&](std::uint32_t first,
                                               std::uint32_t count) {
          const std::uint32_t end = first + count;
          for(std::uint32_t index = first; index < end; index += 3U) {
            if(submit_count + 6U > submit_capacity) {
                flush();
            }
            const std::uint16_t source_indices[3] = {
                indices[index], indices[index + 1U], indices[index + 2U]
            };
            RenderVertex source_triangle[3]{};
            for(unsigned corner = 0; corner < 3; ++corner) {
                const auto& draw = draw_vertices[source_indices[corner]];
#if defined(RE4DC_SCENE_R100)
                const float light_red = lighting[draw.normal * 3U];
                const float light_green = lighting[draw.normal * 3U + 1U];
                const float light_blue = lighting[draw.normal * 3U + 2U];
#else
                float light_red = 1.0f;
                float light_green = 1.0f;
                float light_blue = 1.0f;
#endif
                source_triangle[corner] = {
                    .position = projected[draw.position],
                    .u = draw.u,
                    .v = draw.v,
                    .light_red = light_red,
                    .light_green = light_green,
                    .light_blue = light_blue,
                    .offset_color = 0,
                };
            }
            const std::uint32_t emitted = clip_projected_triangle(
                source_triangle, submit_vertices + submit_count, kCullFront);
            submit_count += emitted * 3U;
            stats.character_vertex_records += emitted * 3U;
            triangles += emitted;
          }
        };
        if(batch.primitive_count == 0U) {
            submit_triangle_range(batch.first_index, batch.index_count);
            flush();
            continue;
        }
        const std::uint32_t primitive_end =
            batch.first_primitive + batch.primitive_count;
        for(std::uint32_t primitive_index = batch.first_primitive;
            primitive_index < primitive_end; ++primitive_index) {
            const auto& primitive = primitives[primitive_index];
            bool direct_strip = primitive.opcode == 0x98U &&
                                primitive.vertex_count <= submit_capacity;
            for(std::uint32_t local = 0;
                direct_strip && local < primitive.vertex_count; ++local) {
                const std::uint16_t vertex =
                    primitive_indices[primitive.first_vertex + local];
                const float depth =
                    projected[draw_vertices[vertex].position].depth;
                if(depth < kNearClipDistance || depth > kFarClipDistance) {
                    direct_strip = false;
                }
            }
            if(!direct_strip) {
                if(primitive.opcode == 0x98U) {
                    ++stats.character_strip_fallbacks;
                }
                submit_triangle_range(
                    primitive.first_index, primitive.index_count);
                continue;
            }
            if(submit_count + primitive.vertex_count > submit_capacity) {
                flush();
            }
            for(std::uint32_t local = 0; local < primitive.vertex_count;
                ++local) {
                const std::uint16_t vertex =
                    primitive_indices[primitive.first_vertex + local];
                const auto& draw = draw_vertices[vertex];
#if defined(RE4DC_SCENE_R100)
                const std::uint32_t color = colors[draw.normal];
#else
                const std::uint32_t color = 0xffffffffU;
#endif
                submit_vertices[submit_count++] = {
                    .flags = local + 1U == primitive.vertex_count
                                 ? PVR_CMD_VERTEX_EOL
                                 : PVR_CMD_VERTEX,
                    .x = projected[draw.position].x,
                    .y = projected[draw.position].y,
                    .z = projected[draw.position].z,
                    .u = draw.u,
                    .v = draw.v,
                    .argb = color,
                    .oargb = 0,
                };
            }
            stats.character_vertex_records += primitive.vertex_count;
            ++stats.character_direct_strips;
            triangles += primitive.index_count / 3U;
        }
        flush();
    }
    return triangles;
}

void submit_screen_quad(float left, float top, float right, float bottom,
                         std::uint32_t color, float depth = 1.0f) {
    left *= kHudScale;
    top *= kHudScale;
    right *= kHudScale;
    bottom *= kHudScale;
    const pvr_vertex_t vertices[4] = {
        {.flags = PVR_CMD_VERTEX, .x = left, .y = top, .z = depth,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
        {.flags = PVR_CMD_VERTEX, .x = right, .y = top, .z = depth,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
        {.flags = PVR_CMD_VERTEX, .x = left, .y = bottom, .z = depth,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
        {.flags = PVR_CMD_VERTEX_EOL, .x = right, .y = bottom, .z = depth,
         .u = 0.0f, .v = 0.0f, .argb = color, .oargb = 0},
    };
    pvr_prim(vertices, sizeof(vertices));
}

const char* glyph_pixels(char glyph) {
    switch(glyph) {
    case '0': return "011101000110001100011000101110";
    case '1': return "001000110000100001000010001110";
    case '2': return "011101000100001001100100011111";
    case '3': return "111100000100001011100000111110";
    case '4': return "000100011001010100101111100010";
    case '5': return "111111000011110000010000111110";
    case '6': return "011101000011110100011000101110";
    case '7': return "111110000100010001000100001000";
    case '8': return "011101000101110100011000101110";
    case '9': return "011101000110001011110000101110";
    case 'A': return "011101000110001111111000110001";
    case 'B': return "111101000111110100011000111110";
    case 'C': return "011111000010000100001000001111";
    case 'D': return "111101000110001100011000111110";
    case 'E': return "111111000011110100001000011111";
    case 'L': return "100001000010000100001000011111";
    case 'N': return "100011100110101100111000110001";
    case 'O': return "011101000110001100011000101110";
    case 'P': return "111101000110001111101000010000";
    case 'R': return "111101000110001111101010010001";
    case 'S': return "011111000001110000010000111110";
    case 'T': return "111110010000100001000010000100";
    case 'U': return "100011000110001100011000101110";
    case 'Y': return "100011000101010001000010000100";
    default: return "000000000000000000000000000000";
    }
}

void draw_text(const char* text, float x, float y, float scale,
               std::uint32_t color) {
    for(const char* character = text; *character != '\0'; ++character) {
        const char* pixels = glyph_pixels(*character);
        for(unsigned row = 0; row < 6; ++row) {
            for(unsigned column = 0; column < 5; ++column) {
                if(pixels[row * 5U + column] == '1') {
                    const float left = x + static_cast<float>(column) * scale;
                    const float top = y + static_cast<float>(row) * scale;
                    submit_screen_quad(left, top, left + scale, top + scale,
                                       color);
                }
            }
        }
        x += 6.0f * scale;
    }
}

[[maybe_unused]] void draw_hud(const Player& player) {
    submit_screen_quad(252.0f, 188.0f, 316.0f, 236.0f, 0xff171917U, 0.95f);
    const float health_fraction = std::clamp(
        static_cast<float>(player.health) / static_cast<float>(kPlayerMaxHealth),
        0.0f, 1.0f);
    constexpr unsigned health_segments = 18;
    for(unsigned segment = 0; segment < health_segments; ++segment) {
        const float angle = -kPi * 0.5f + 2.0f * kPi *
                            static_cast<float>(segment) /
                            static_cast<float>(health_segments);
        const float x = 273.0f + std::cos(angle) * 18.0f;
        const float y = 211.0f + std::sin(angle) * 18.0f;
        const bool filled = static_cast<float>(segment) /
                            static_cast<float>(health_segments) < health_fraction;
        const std::uint32_t color = filled
            ? (health_fraction > 0.35f ? 0xff6bc84bU : 0xffcf3930U)
            : 0xff343832U;
        submit_screen_quad(x - 2.0f, y - 2.0f, x + 2.0f, y + 2.0f, color);
    }
    char ammo_text[4];
    ::snprintf(ammo_text, sizeof(ammo_text), "%d", player.ammo);
    draw_text(ammo_text, player.ammo < 10 ? 299.0f : 287.0f, 199.0f, 2.0f,
              0xffe7e0c8U);
    draw_text("LEON", 285.0f, 226.0f, 1.0f, 0xffc9c6b4U);
    if(player.reload_seconds > 0.0f) {
        draw_text("RELOAD", 142.0f, 137.0f, 1.0f, 0xffe5d36aU);
    }
    if(player.aiming) {
        submit_screen_quad(150.0f, 119.0f, 157.0f, 120.0f, 0xffff4040U);
        submit_screen_quad(163.0f, 119.0f, 170.0f, 120.0f, 0xffff4040U);
        submit_screen_quad(159.0f, 110.0f, 160.0f, 117.0f, 0xffff4040U);
        submit_screen_quad(159.0f, 123.0f, 160.0f, 130.0f, 0xffff4040U);
    }
    if(player.death_complete) {
        submit_screen_quad(72.0f, 100.0f, 248.0f, 140.0f, 0xff310707U,
                           0.95f);
        draw_text("YOU ARE DEAD", 88.0f, 106.0f, 2.0f, 0xffb9211cU);
        draw_text("PRESS B TO RETRY", 113.0f, 130.0f, 1.0f, 0xffd6cfbaU);
    }
}


#if defined(RE4DC_SCENE_R100)
struct HudTransform {
    float xx;
    float xy;
    float yx;
    float yy;
    float x;
    float y;
};

HudTransform hud_multiply(const HudTransform& parent,
                          const HudTransform& child) {
    return {
        parent.xx * child.xx + parent.xy * child.yx,
        parent.xx * child.xy + parent.xy * child.yy,
        parent.yx * child.xx + parent.yy * child.yx,
        parent.yx * child.xy + parent.yy * child.yy,
        parent.xx * child.x + parent.xy * child.y + parent.x,
        parent.yx * child.x + parent.yy * child.y + parent.y,
    };
}

int source_life_state(const Player& player) {
    if(player.health > kPlayerMaxHealth * 2 / 3) {
        return 0;
    }
    if(player.health > kPlayerMaxHealth / 3) {
        return 1;
    }
    return 2;
}

float source_hud_rotation(const re4dc::hud::Unit& unit,
                          const Player& player) {
    if(unit.table != re4dc::hud::kTableLife) {
        return unit.rotation[2];
    }
    const float rate = static_cast<float>(player.health) / 400.0f;
    switch(unit.mark) {
    case 0xFE:
        // lifeLevel(20, 1200, 1200) == 0 in the source opening loadout.
        return -45.0f;
    case 7:
        return rate >= 0.0f ? 180.0f - rate * 45.0f : unit.rotation[2];
    case 8:
        return rate > 2.0f ? 90.0f - (rate - 2.0f) * 45.0f
                           : unit.rotation[2];
    case 9:
        return rate > 4.0f ? -(rate - 4.0f) * 45.0f : unit.rotation[2];
    default:
        return unit.rotation[2];
    }
}

HudTransform source_hud_local_transform(const re4dc::hud::Unit& unit,
                                        const Player& player) {
    const float angle =
        source_hud_rotation(unit, player) * kPi / 180.0f;
    const float cosine = std::cos(angle);
    const float sine = std::sin(angle);
    return {
        cosine, -sine, sine, cosine,
        unit.position[0], unit.position[1],
    };
}

std::uint32_t source_hud_table_start(const re4dc::hud::Header& header,
                                     std::uint8_t table) {
    if(table == re4dc::hud::kTableFrame) {
        return header.frame_start;
    }
    if(table == re4dc::hud::kTableLife) {
        return header.life_start;
    }
    return header.bullet_start;
}

std::uint32_t source_hud_table_count(const re4dc::hud::Header& header,
                                     std::uint8_t table) {
    if(table == re4dc::hud::kTableFrame) {
        return header.frame_count;
    }
    if(table == re4dc::hud::kTableLife) {
        return header.life_count;
    }
    return header.bullet_count;
}

const re4dc::hud::Unit* source_hud_find_number(
    const re4dc::hud::Package& hud, std::uint8_t table,
    std::uint8_t number) {
    const auto& header = hud.header();
    const std::uint32_t start = source_hud_table_start(header, table);
    const std::uint32_t count = source_hud_table_count(header, table);
    for(std::uint32_t index = start; index < start + count; ++index) {
        if(hud.units()[index].number == number) {
            return &hud.units()[index];
        }
    }
    return nullptr;
}

const re4dc::hud::Unit* source_hud_find_mark(
    const re4dc::hud::Package& hud, std::uint8_t table,
    std::uint8_t mark) {
    const auto& header = hud.header();
    const std::uint32_t start = source_hud_table_start(header, table);
    const std::uint32_t count = source_hud_table_count(header, table);
    for(std::uint32_t index = start; index < start + count; ++index) {
        if(hud.units()[index].mark == mark) {
            return &hud.units()[index];
        }
    }
    return nullptr;
}

const re4dc::hud::Unit* source_hud_parent(
    const re4dc::hud::Package& hud, const re4dc::hud::Unit& unit) {
    if(unit.parent != 0xFFU) {
        return source_hud_find_number(hud, unit.table, unit.parent);
    }
    if(unit.table == re4dc::hud::kTableBullet) {
        return source_hud_find_mark(hud, re4dc::hud::kTableLife, 0x30);
    }
    return nullptr;
}

bool source_hud_local_visible(const re4dc::hud::Unit& unit,
                              const Player& player) {
    if((unit.flags & 0x09U) != 0x09U) {
        return false;
    }
    if(unit.table == re4dc::hud::kTableBullet) {
        return unit.kind == 1U || unit.mark == 0x31U;
    }
    if(unit.table != re4dc::hud::kTableLife) {
        return true;
    }
    const float rate = static_cast<float>(player.health) / 400.0f;
    switch(unit.mark) {
    case 1:
    case 3:
    case 0x3F:
    case 0x41:
    case 0x42:
        return false;
    case 7:
        return rate >= 0.0f;
    case 8:
        return rate > 2.0f;
    case 9:
        return rate > 4.0f;
    case 0x13:
        return source_life_state(player) == 1;
    case 0x14:
        return source_life_state(player) == 2;
    case 0x17:
        return player.ammo >= 100;
    case 0x40:
        return true;
    default:
        return true;
    }
}

bool source_hud_visible(const re4dc::hud::Package& hud,
                        const re4dc::hud::Unit& unit,
                        const Player& player, unsigned depth = 0) {
    if(depth > 8U || !source_hud_local_visible(unit, player)) {
        return false;
    }
    if(const auto* parent = source_hud_parent(hud, unit)) {
        return parent != nullptr &&
               source_hud_visible(hud, *parent, player, depth + 1U);
    }
    return true;
}

HudTransform source_hud_transform(const re4dc::hud::Package& hud,
                                  const re4dc::hud::Unit& unit,
                                  const Player& player,
                                  unsigned depth = 0) {
    HudTransform result = source_hud_local_transform(unit, player);
    if(depth > 8U) {
        return result;
    }
    const re4dc::hud::Unit* parent = source_hud_parent(hud, unit);
    if(parent != nullptr) {
        result = hud_multiply(
            source_hud_transform(hud, *parent, player, depth + 1U),
            result);
    }
    return result;
}

std::uint32_t source_hud_color(const re4dc::hud::Package& hud,
                               const re4dc::hud::Unit& unit,
                               const Player& player, unsigned depth = 0) {
    const std::uint8_t* color = unit.color0;
    if(unit.table == re4dc::hud::kTableLife && unit.mark == 0x12U) {
        const std::uint8_t template_mark =
            source_life_state(player) == 0 ? 0x11U
            : source_life_state(player) == 1 ? 0x10U : 0x0FU;
        const auto* source = source_hud_find_mark(
            hud, re4dc::hud::kTableLife, template_mark);
        if(source != nullptr) {
            color = source->color0;
        }
    }
    std::uint32_t alpha = color[3];
    std::uint32_t red = color[0];
    std::uint32_t green = color[1];
    std::uint32_t blue = color[2];
    if(depth <= 8U) {
        if(const auto* parent = source_hud_parent(hud, unit)) {
            const std::uint32_t parent_color =
                source_hud_color(hud, *parent, player, depth + 1U);
            alpha = alpha * ((parent_color >> 24U) & 0xFFU) / 255U;
            red = red * ((parent_color >> 16U) & 0xFFU) / 255U;
            green = green * ((parent_color >> 8U) & 0xFFU) / 255U;
            blue = blue * (parent_color & 0xFFU) / 255U;
        }
    }
    return (alpha << 24U) | (red << 16U) | (green << 8U) | blue;
}

unsigned source_hud_draw_priority(const re4dc::hud::Unit& unit) {
    if(unit.table == re4dc::hud::kTableBullet && unit.mark == 0x31U) {
        return 1U;
    }
    if(unit.table == re4dc::hud::kTableLife && unit.mark == 0x40U) {
        return 2U;
    }
    if(unit.table == re4dc::hud::kTableLife &&
       (unit.mark == 0x0AU || unit.mark == 0x0BU || unit.mark == 0x17U)) {
        return 3U;
    }
    return 0U;
}

std::uint32_t source_hud_texture_frame(const re4dc::hud::Unit& unit,
                                       const Player& player) {
    if(unit.table != re4dc::hud::kTableLife) {
        return 0U;
    }
    switch(unit.mark) {
    case 0x0B:
        return static_cast<std::uint32_t>(player.ammo % 10);
    case 0x0A:
        return static_cast<std::uint32_t>((player.ammo / 10) % 10);
    case 0x17:
        return static_cast<std::uint32_t>((player.ammo / 100) % 10);
    default:
        return 0U;
    }
}

void source_hud_vertices(const re4dc::hud::Unit& unit,
                         float x[4], float y[4]) {
    const float width = unit.size[0];
    const float height = unit.size[1];
    switch(unit.vertex_type & 0x0FU) {
    case 1:
        x[0] = 0.0f; x[1] = width; x[2] = 0.0f; x[3] = width;
        y[0] = 0.0f; y[1] = 0.0f; y[2] = -height; y[3] = -height;
        break;
    case 2:
        x[0] = -width; x[1] = 0.0f; x[2] = -width; x[3] = 0.0f;
        y[0] = 0.0f; y[1] = 0.0f; y[2] = -height; y[3] = -height;
        break;
    case 3:
        x[0] = -width; x[1] = 0.0f; x[2] = -width; x[3] = 0.0f;
        y[0] = height; y[1] = height; y[2] = 0.0f; y[3] = 0.0f;
        break;
    case 4:
        x[0] = 0.0f; x[1] = width; x[2] = 0.0f; x[3] = width;
        y[0] = height; y[1] = height; y[2] = 0.0f; y[3] = 0.0f;
        break;
    case 0:
    default:
        x[0] = -width * 0.5f; x[1] = width * 0.5f;
        x[2] = -width * 0.5f; x[3] = width * 0.5f;
        y[0] = height * 0.5f; y[1] = height * 0.5f;
        y[2] = -height * 0.5f; y[3] = -height * 0.5f;
        break;
    }
}

void draw_source_hud(const re4dc::hud::Package& hud,
                     const pvr_poly_hdr_t* headers,
                     const Player& player, FrameStats& stats) {
    constexpr float source_width = 640.0f;
    constexpr float source_height = 480.0f;
    const float scale_x = kScreenWidth / source_width;
    const float scale_y = kScreenHeight / source_height;
    const auto* units = hud.units();
    for(unsigned priority = 0; priority <= 3U; ++priority) {
      for(std::uint32_t index = 0; index < hud.header().unit_count; ++index) {
        const auto& unit = units[index];
        if(source_hud_draw_priority(unit) != priority || unit.kind == 1U ||
           unit.first_texture == re4dc::hud::kNoTexture ||
           unit.texture_count == 0U ||
           !source_hud_visible(hud, unit, player)) {
            continue;
        }
        const std::uint32_t frame = std::min(
            source_hud_texture_frame(unit, player),
            unit.texture_count - 1U);
        const std::uint32_t texture = unit.first_texture + frame;
        const HudTransform transform =
            source_hud_transform(hud, unit, player);
        float local_x[4];
        float local_y[4];
        source_hud_vertices(unit, local_x, local_y);
        pvr_vertex_t commands[5]{};
        pvr_vertex_t* vertices = commands + 1U;
        constexpr float uv_x[4] = {0.0f, 1.0f, 0.0f, 1.0f};
        constexpr float uv_y[4] = {0.0f, 0.0f, 1.0f, 1.0f};
        const std::uint32_t color = source_hud_color(hud, unit, player);
        for(unsigned corner = 0; corner < 4; ++corner) {
            const float source_x =
                transform.xx * local_x[corner] +
                transform.xy * local_y[corner] + transform.x;
            const float source_y =
                transform.yx * local_x[corner] +
                transform.yy * local_y[corner] + transform.y;
            vertices[corner] = {
                .flags = corner == 3U ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX,
                .x = kScreenWidth * 0.5f + source_x * scale_x,
                .y = kScreenHeight * 0.5f - source_y * scale_y,
                .z = 1.0f,
                .u = uv_x[corner] * unit.uv_max[0],
                .v = uv_y[corner] * unit.uv_max[1],
                .argb = color,
                .oargb = 0,
            };
        }
        std::memcpy(commands, &headers[texture], sizeof(pvr_poly_hdr_t));
        submit_pvr(stats, commands, sizeof(commands));
      }
    }
}
#endif

[[maybe_unused]] void draw_goal(bool unlocked) {
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

bool uses_source_punchthrough(
    const re4dc::room::SourceGroup* source_groups,
    const bool* material_punchthrough, std::uint32_t group_index,
    std::uint32_t material_index) {
    return source_groups != nullptr && material_punchthrough[material_index] &&
           (source_groups[group_index].flags &
           re4dc::room::kSourceGroupAlphaOmit128) != 0U;
}

struct VisibleRoomGroup {
    std::uint32_t group_index;
    std::uint32_t light_selection;
    std::uint32_t cull_mode;
};

static_assert(sizeof(VisibleRoomGroup) == 12U);

FrameStats render_scene(const re4dc::room::Package& room,
                        const re4dc::character::Package& leon,
                        const re4dc::character::Package& ganado,
                        const Player& player, const Enemy& enemy,
                        const pvr_poly_hdr_t& untextured_header,
                        const pvr_poly_hdr_t* material_headers,
                        const pvr_poly_hdr_t* room_strip_headers,
                        const pvr_poly_hdr_t* room_punchthrough_headers,
                        const bool* material_alpha,
                        const bool* material_punchthrough,
                        VisibleRoomGroup* visible_room_groups,
                        std::uint32_t visible_room_group_capacity,
                        const pvr_poly_hdr_t* leon_headers,
                         const bool* leon_alpha,
                         const pvr_poly_hdr_t* ganado_headers,
                         const bool* ganado_alpha,
#if defined(RE4DC_SCENE_R100)
                         const re4dc::hud::Package& source_hud,
                         const pvr_poly_hdr_t* source_hud_headers,
#endif
                        ProjectedVertex* leon_projected,
                        ProjectedVertex* ganado_projected,
#if defined(RE4DC_SCENE_R100)
                        float* leon_lighting, float* ganado_lighting,
#endif
                        pvr_vertex_t* character_submit_vertices) {
    FrameStats stats{};
    ++g_room_vertex_cache_generation;
    if(g_room_vertex_cache_generation == 0U) {
        for(RoomVertexCacheEntry& entry : g_room_vertex_cache) {
            entry.generation = 0U;
        }
        ++g_room_vertex_cache_generation;
    }
    const std::uint64_t render_start = timer_us_gettime64();
    const auto* groups = room.groups();
    const auto* batches = room.batches();
    const auto* vertices = room.vertices();
    const auto* indices = room.indices();
    const auto* source_groups = room.source_groups();
    const auto player_blend = player_pitch_blend(
        player.animation_clip, player.aim_pitch);
    const std::uint64_t actor_pose_start = timer_us_gettime64();
    project_character(
        leon, player.x, player.y, player.z, player.yaw, player_blend.base_clip,
        player.animation_frame,
        player.animation_clip == kPlayerIdleClip ||
            player.animation_clip == kPlayerWalkClip ||
            player.animation_clip == kPlayerAimLevelClip,
        player_blend.secondary_clip, player_blend.amount, leon_projected,
        g_leon_pose_palette);
    project_character(
        ganado, enemy.x, enemy.y, enemy.z, enemy.yaw, enemy.animation_clip,
        enemy.animation_frame, enemy.state == EnemyState::Chase,
        enemy.animation_clip, 0.0f, ganado_projected,
        g_ganado_pose_palette);
    stats.actor_pose_us = timer_us_gettime64() - actor_pose_start;
#if defined(RE4DC_SCENE_R100)
    const std::uint64_t actor_normals_start = timer_us_gettime64();
    if(leon.header().source_normal_count != 0U) {
        build_character_source_normals(
            leon, player.yaw, player_blend.base_clip, player.animation_frame,
            player.animation_clip == kPlayerIdleClip ||
                player.animation_clip == kPlayerWalkClip ||
                player.animation_clip == kPlayerAimLevelClip,
            player_blend.secondary_clip, player_blend.amount, leon_lighting,
            leon.header().version == re4dc::character::kVersion
                ? g_leon_pose_palette
                : nullptr);
    } else {
        build_character_normals(leon, leon_projected, leon_lighting);
    }
    if(ganado.header().source_normal_count != 0U) {
        build_character_source_normals(
            ganado, enemy.yaw, enemy.animation_clip, enemy.animation_frame,
            enemy.state == EnemyState::Chase, enemy.animation_clip, 0.0f,
            ganado_lighting,
            ganado.header().version == re4dc::character::kVersion
                ? g_ganado_pose_palette
                : nullptr);
    } else {
        build_character_normals(ganado, ganado_projected, ganado_lighting);
    }
    stats.actor_normals_us = timer_us_gettime64() - actor_normals_start;
    const std::uint64_t actor_lighting_start = timer_us_gettime64();
    const SelectedSourceLights leon_light_selection = selected_source_lights(
        source_actor_light_selection(player.x, player.y, player.z, 1U));
    const SelectedSourceLights ganado_light_selection = selected_source_lights(
        source_actor_light_selection(enemy.x, enemy.y, enemy.z, 2U));
    build_character_lighting(
        leon, leon_projected, leon_lighting, leon_lighting, g_leon_colors,
        leon_light_selection);
    build_character_lighting(
        ganado, ganado_projected, ganado_lighting, ganado_lighting,
        g_ganado_colors,
        ganado_light_selection);
    stats.actor_lighting_us = timer_us_gettime64() - actor_lighting_start;
#endif
    const std::uint64_t room_visibility_start = timer_us_gettime64();
    std::uint32_t visible_room_group_count = 0U;
    for(std::uint32_t group_index = 0U;
        group_index < room.header().group_count; ++group_index) {
        const auto& group = groups[group_index];
        if(!group_visible(group)) {
            continue;
        }
        if(visible_room_group_count >= visible_room_group_capacity) {
            break;
        }
        VisibleRoomGroup& visible =
            visible_room_groups[visible_room_group_count++];
        visible.group_index = group_index;
        visible.cull_mode = source_groups != nullptr
            ? source_groups[group_index].cull_mode
#if defined(RE4DC_SCENE_R100)
            : kCullNone;
#else
            : kCullBack;
#endif
        visible.light_selection = source_group_light_selection(
            source_groups != nullptr ? source_groups + group_index : nullptr);
        ++stats.room_light_selection_evaluations;
    }
    stats.groups = visible_room_group_count;
    stats.room_visibility_us =
        timer_us_gettime64() - room_visibility_start;
    const std::uint64_t wait_start = timer_us_gettime64();
    pvr_wait_ready();
    const std::uint64_t submit_start = timer_us_gettime64();
    stats.wait_us = submit_start - wait_start;
    pvr_scene_begin();
    pvr_list_begin(PVR_LIST_OP_POLY);
    const std::uint64_t opaque_room_start = timer_us_gettime64();
    for(std::uint32_t visible_index = 0U;
        visible_index < visible_room_group_count; ++visible_index) {
        const VisibleRoomGroup& visible = visible_room_groups[visible_index];
        const std::uint32_t group_index = visible.group_index;
        const auto& group = groups[group_index];
        const std::uint8_t cull_mode =
            static_cast<std::uint8_t>(visible.cull_mode);
        const std::uint32_t light_selection = visible.light_selection;
        for(std::uint32_t local_batch = 0; local_batch < group.batch_count;
            ++local_batch) {
            const auto& batch = batches[group.first_batch + local_batch];
            if(material_alpha[batch.material]) {
                continue;
            }
            if(cull_mode == kCullAll) {
                continue;
            }
            if(batch.primitive_count != 0U) {
                submit_room_strips(
                    room, batch,
                    room_strip_headers[batch.material * 3U + cull_mode],
                    character_submit_vertices,
                    kCharacterSubmitVertexCapacity, stats, cull_mode,
                    light_selection);
                continue;
            }
            std::uint32_t submit_count = 0;
            begin_pvr_packet(character_submit_vertices, submit_count,
                             material_headers[batch.material]);
            const auto flush = [&]() {
                if(submit_count == 0U) {
                    return;
                }
                submit_pvr(stats, character_submit_vertices,
                           sizeof(pvr_vertex_t) * submit_count);
                submit_count = 0;
            };
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; index += 3) {
                if(submit_count + 6U > kCharacterSubmitVertexCapacity) {
                    flush();
                }
                const std::uint32_t emitted = transform_triangle(
                    vertices, indices + index,
                    character_submit_vertices + submit_count, stats,
                    cull_mode, light_selection);
                submit_count += emitted * 3U;
                stats.triangles += emitted;
            }
            flush();
        }
    }
    stats.opaque_room_us = timer_us_gettime64() - opaque_room_start;
    const std::uint64_t opaque_actor_start = timer_us_gettime64();
    submit_pvr(stats, &untextured_header, sizeof(untextured_header));
    stats.character_triangles = draw_character(
        leon, leon_projected,
#if defined(RE4DC_SCENE_R100)
        leon_lighting, g_leon_colors,
#endif
        leon_headers, leon_alpha, false,
        character_submit_vertices, kCharacterSubmitVertexCapacity, stats);
    stats.character_triangles += draw_character(
        ganado, ganado_projected,
#if defined(RE4DC_SCENE_R100)
        ganado_lighting, g_ganado_colors,
#endif
        ganado_headers, ganado_alpha, false,
        character_submit_vertices, kCharacterSubmitVertexCapacity, stats);
#if !defined(RE4DC_SCENE_R100)
    draw_goal(enemy.state == EnemyState::Dead);
#endif
#if !defined(RE4DC_SCENE_R100)
    draw_hud(player);
#endif
    stats.opaque_actor_us = timer_us_gettime64() - opaque_actor_start;
    pvr_list_finish();

    const std::uint64_t translucent_room_start = timer_us_gettime64();
    pvr_list_begin(PVR_LIST_PT_POLY);
    for(std::uint32_t visible_index = 0U;
        visible_index < visible_room_group_count; ++visible_index) {
        const VisibleRoomGroup& visible = visible_room_groups[visible_index];
        const std::uint32_t group_index = visible.group_index;
        const auto& group = groups[group_index];
        const std::uint8_t cull_mode =
            static_cast<std::uint8_t>(visible.cull_mode);
        const std::uint32_t light_selection = visible.light_selection;
        for(std::uint32_t local_batch = 0; local_batch < group.batch_count;
            ++local_batch) {
            const auto& batch = batches[group.first_batch + local_batch];
            if(!uses_source_punchthrough(source_groups, material_punchthrough,
                                         group_index, batch.material) ||
               cull_mode == kCullAll) {
                continue;
            }
            const pvr_poly_hdr_t& header =
                room_punchthrough_headers[batch.material * 3U + cull_mode];
            if(batch.primitive_count != 0U) {
                submit_room_strips(
                    room, batch, header, character_submit_vertices,
                    kCharacterSubmitVertexCapacity, stats, cull_mode,
                    light_selection);
                continue;
            }
            std::uint32_t submit_count = 0;
            begin_pvr_packet(character_submit_vertices, submit_count, header);
            const auto flush = [&]() {
                if(submit_count == 0U) {
                    return;
                }
                submit_pvr(stats, character_submit_vertices,
                           sizeof(pvr_vertex_t) * submit_count);
                submit_count = 0;
            };
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; index += 3) {
                if(submit_count + 6U > kCharacterSubmitVertexCapacity) {
                    flush();
                }
                const std::uint32_t emitted = transform_triangle(
                    vertices, indices + index,
                    character_submit_vertices + submit_count, stats,
                    cull_mode, light_selection);
                submit_count += emitted * 3U;
                stats.triangles += emitted;
            }
            flush();
        }
    }
    pvr_list_finish();

    pvr_list_begin(PVR_LIST_TR_POLY);
    for(std::uint32_t visible_index = 0U;
        visible_index < visible_room_group_count; ++visible_index) {
        const VisibleRoomGroup& visible = visible_room_groups[visible_index];
        const std::uint32_t group_index = visible.group_index;
        const auto& group = groups[group_index];
        const std::uint8_t cull_mode =
            static_cast<std::uint8_t>(visible.cull_mode);
        const std::uint32_t light_selection = visible.light_selection;
        for(std::uint32_t local_batch = 0; local_batch < group.batch_count;
            ++local_batch) {
            const auto& batch = batches[group.first_batch + local_batch];
            if(!material_alpha[batch.material] ||
               uses_source_punchthrough(source_groups, material_punchthrough,
                                        group_index, batch.material)) {
                continue;
            }
            if(cull_mode == kCullAll) {
                continue;
            }
            if(batch.primitive_count != 0U &&
               (batch.flags & re4dc::room::kBatchStripOrderPreserved) != 0U) {
                submit_room_strips(
                    room, batch,
                    room_strip_headers[batch.material * 3U + cull_mode],
                    character_submit_vertices,
                    kCharacterSubmitVertexCapacity, stats, cull_mode,
                    light_selection);
                continue;
            }
            std::uint32_t submit_count = 0;
            begin_pvr_packet(character_submit_vertices, submit_count,
                             material_headers[batch.material]);
            const auto flush = [&]() {
                if(submit_count == 0U) {
                    return;
                }
                submit_pvr(stats, character_submit_vertices,
                           sizeof(pvr_vertex_t) * submit_count);
                submit_count = 0;
            };
            const std::uint32_t end = batch.first_index + batch.index_count;
            for(std::uint32_t index = batch.first_index; index < end; index += 3) {
                if(submit_count + 6U > kCharacterSubmitVertexCapacity) {
                    flush();
                }
                const std::uint32_t emitted = transform_triangle(
                    vertices, indices + index,
                    character_submit_vertices + submit_count, stats,
                    cull_mode, light_selection);
                submit_count += emitted * 3U;
                stats.triangles += emitted;
            }
            flush();
        }
    }
    stats.translucent_room_us =
        timer_us_gettime64() - translucent_room_start;
    const std::uint64_t translucent_actor_hud_start = timer_us_gettime64();
    stats.character_triangles += draw_character(
        leon, leon_projected,
#if defined(RE4DC_SCENE_R100)
        leon_lighting, g_leon_colors,
#endif
        leon_headers, leon_alpha, true,
        character_submit_vertices, kCharacterSubmitVertexCapacity, stats);
    stats.character_triangles += draw_character(
        ganado, ganado_projected,
#if defined(RE4DC_SCENE_R100)
        ganado_lighting, g_ganado_colors,
#endif
        ganado_headers, ganado_alpha, true,
        character_submit_vertices, kCharacterSubmitVertexCapacity, stats);
#if defined(RE4DC_SCENE_R100)
    draw_source_hud(source_hud, source_hud_headers, player, stats);
#endif
    stats.translucent_actor_hud_us =
        timer_us_gettime64() - translucent_actor_hud_start;
    pvr_list_finish();
    const std::uint64_t finish_start = timer_us_gettime64();
    stats.submit_us = finish_start - submit_start;
    pvr_scene_finish();
    stats.finish_us = timer_us_gettime64() - finish_start;
    stats.total_us = timer_us_gettime64() - render_start;
    return stats;
}

} // namespace

int main() {
    g_re4dc_demo_telemetry.flags = 0x10000001U;
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
    re4dc::route::Package route;
    const re4dc::route::Package* route_ptr = nullptr;
#if defined(RE4DC_SCENE_R100)
    if(!route.open("/rd/route.re4rtp")) {
        std::printf("re4dc-room: r100 route load failed: %s\n", route.error());
        return 1;
    }
    route_ptr = &route;
    std::printf("re4dc-room: source RTP points=%lu links=%lu\n",
                static_cast<unsigned long>(route.header().point_count),
                static_cast<unsigned long>(route.header().link_count));
#endif
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
    re4dc::texture::Package leon_textures;
    if(!leon_textures.open("/rd/leon.re4tex")) {
        std::printf("re4dc-room: Leon texture load failed: %s\n",
                    leon_textures.error());
        return 1;
    }
    re4dc::texture::Package ganado_textures;
    if(!ganado_textures.open("/rd/ganado.re4tex")) {
        std::printf("re4dc-room: Ganado texture load failed: %s\n",
                    ganado_textures.error());
        return 1;
    }
#if defined(RE4DC_SCENE_R100)
    re4dc::hud::Package source_hud;
    if(!source_hud.open("/rd/source-hud.re4hud")) {
        std::printf("re4dc-room: source HUD load failed: %s\n",
                    source_hud.error());
        return 1;
    }
    re4dc::texture::Package source_hud_textures;
    if(!source_hud_textures.open("/rd/source-hud.re4tex")) {
        std::printf("re4dc-room: source HUD texture load failed: %s\n",
                    source_hud_textures.error());
        return 1;
    }
#endif
    g_re4dc_demo_telemetry.flags = 0x10000002U;
    std::printf(
        "re4dc-room: loaded room=%lu/%lu/%lu collision=%lu/%lu/%lu "
        "hierarchy=%lu/%lu leon=%lu/%lu/%lu/%lu/%lu "
        "ganado=%lu/%lu/%lu/%lu/%lu "
        "source_groups=%s\n",
        static_cast<unsigned long>(room.header().vertex_count),
        static_cast<unsigned long>(room.header().index_count / 3U),
        static_cast<unsigned long>(room.header().group_count),
        static_cast<unsigned long>(collision.header().floor_count),
        static_cast<unsigned long>(collision.header().slope_count),
        static_cast<unsigned long>(collision.header().wall_count),
        static_cast<unsigned long>(collision.has_hierarchy()
            ? collision.hierarchy()->block_count : 0U),
        static_cast<unsigned long>(collision.has_hierarchy()
            ? collision.hierarchy()->block_index_count : 0U),
        static_cast<unsigned long>(leon.header().position_count),
        static_cast<unsigned long>(leon.header().draw_vertex_count),
        static_cast<unsigned long>(leon.header().normal_count),
        static_cast<unsigned long>(leon.header().index_count / 3U),
        static_cast<unsigned long>(leon.header().frame_count),
        static_cast<unsigned long>(ganado.header().position_count),
        static_cast<unsigned long>(ganado.header().draw_vertex_count),
        static_cast<unsigned long>(ganado.header().normal_count),
        static_cast<unsigned long>(ganado.header().index_count / 3U),
        static_cast<unsigned long>(ganado.header().frame_count),
        room.source_groups() != nullptr ? "yes" : "no");
    g_re4dc_demo_telemetry.flags = 0x10000021U;
    if(leon.header().clip_count < 11U) {
        std::printf(
            "re4dc-room: Leon package needs source aim/fire triplets and actions\n");
        return 1;
    }
    if(ganado.header().clip_count < 5U) {
        std::printf("re4dc-room: Ganado package needs idle/walk/attack/hit/death\n");
        return 1;
    }
#if defined(RE4DC_SCENE_R100)
    if(leon.header().position_count != 5687U) {
        std::printf(
            "re4dc-room: r100 Leon package needs source gun and hit-capsule markers\n");
        return 1;
    }
    if(ganado.header().position_count != 1690U) {
        std::printf(
            "re4dc-room: r100 Ganado package needs source hit capsules and axe markers\n");
        return 1;
    }
    if(leon.header().version != re4dc::character::kVersion ||
       leon.header().skinned_position_count != 5673U ||
       leon.header().source_normal_count != 5774U ||
       leon.header().normal_matrix_count != 393U ||
       ganado.header().version != re4dc::character::kVersion ||
       ganado.header().skinned_position_count != 1667U ||
       ganado.header().source_normal_count != 1818U ||
       ganado.header().normal_matrix_count != 112U) {
        std::printf(
            "re4dc-room: r100 actors need source positions, normals, and pose palettes\n");
        return 1;
    }
#endif

    g_re4dc_demo_telemetry.flags = 0x10000022U;
#if defined(RE4DC_480P)
    vid_set_mode(DM_640x480, PM_RGB565);
#else
    vid_set_mode(DM_320x240, PM_RGB565);
#endif
    g_re4dc_demo_telemetry.flags = 0x10000023U;
    pvr_init_params_t pvr_params = pvr_default_params;
    pvr_params.opb_sizes[PVR_LIST_PT_POLY] = PVR_BINSIZE_16;
    g_re4dc_demo_telemetry.flags = 0x10000024U;
    if(pvr_init(&pvr_params) < 0) {
        std::printf("re4dc-room: PVR initialization failed\n");
        return 1;
    }
    // Match the source SMX alpha-omit reference used by the binary cutout path.
    PVR_SET(PVR_PT_ALPHA_REF, 0x80U);
    g_re4dc_demo_telemetry.flags = 0x10000025U;
#if defined(RE4DC_SCENE_R100)
    // r100_002.LIT cut 0 supplies the background/fog colour and distances.
    pvr_set_bg_color(kBackgroundRed, kBackgroundGreen, kBackgroundBlue);
    pvr_fog_table_color(1.0f, kBackgroundRed, kBackgroundGreen,
                        kBackgroundBlue);
    // GX accepts r100's negative fog start. The PVR table helper does not;
    // clamp it to the visible near plane, which is equivalent for submitted
    // geometry and avoids saturating the entire Dreamcast fog table.
    pvr_fog_table_linear(
        std::max(kSourceFogStartDistance, kNearClipDistance),
        kFogEndDistance);
#else
    pvr_set_bg_color(0.16f, 0.15f, 0.13f);
    pvr_fog_table_color(1.0f, 0.16f, 0.15f, 0.13f);
    pvr_fog_table_linear(14.0f, 48.0f);
#endif
    g_re4dc_demo_telemetry.flags = 0x10000003U;
    const std::size_t vram_before_textures = pvr_mem_available();
    if(!textures.upload()) {
        std::printf("re4dc-room: texture upload failed: %s\n", textures.error());
        return 1;
    }
    if(!leon_textures.upload()) {
        std::printf("re4dc-room: Leon texture upload failed: %s\n",
                    leon_textures.error());
        return 1;
    }
    if(!ganado_textures.upload()) {
        std::printf("re4dc-room: Ganado texture upload failed: %s\n",
                    ganado_textures.error());
        return 1;
    }
#if defined(RE4DC_SCENE_R100)
    if(!source_hud_textures.upload()) {
        std::printf("re4dc-room: source HUD texture upload failed: %s\n",
                    source_hud_textures.error());
        return 1;
    }
#endif
    g_re4dc_demo_telemetry.flags = 0x10000004U;
    pvr_poly_cxt_t context{};
    pvr_poly_hdr_t untextured_header{};
    pvr_poly_cxt_col(&context, PVR_LIST_OP_POLY);
    context.gen.culling = PVR_CULLING_NONE;
    pvr_poly_compile(&untextured_header, &context);
    pvr_poly_hdr_t* material_headers =
        new(std::nothrow) pvr_poly_hdr_t[room.header().material_count];
    pvr_poly_hdr_t* room_strip_headers =
        new(std::nothrow) pvr_poly_hdr_t[room.header().material_count * 3U];
    pvr_poly_hdr_t* room_punchthrough_headers =
        new(std::nothrow) pvr_poly_hdr_t[room.header().material_count * 3U];
    VisibleRoomGroup* visible_room_groups =
        new(std::nothrow) VisibleRoomGroup[room.header().group_count];
    std::unique_ptr<bool[]> material_alpha(
        new(std::nothrow) bool[room.header().material_count]);
    std::unique_ptr<bool[]> material_punchthrough(
        new(std::nothrow) bool[room.header().material_count]);
    if(material_headers == nullptr || room_strip_headers == nullptr ||
       room_punchthrough_headers == nullptr || material_alpha == nullptr ||
       material_punchthrough == nullptr || visible_room_groups == nullptr) {
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
        material_punchthrough[material] =
            (texture->flags & re4dc::texture::kBinaryAlpha) != 0;
        const pvr_list_t list = material_alpha[material]
                                    ? PVR_LIST_TR_POLY
                                    : PVR_LIST_OP_POLY;
        const int format = texture->format == re4dc::texture::kRgb565
                               ? PVR_TXRFMT_RGB565
                               : texture->format == re4dc::texture::kArgb1555
                                     ? PVR_TXRFMT_ARGB1555
                                     : PVR_TXRFMT_ARGB4444;
        pvr_poly_cxt_txr(&context, list, format, texture->width,
                         texture->height, textures.pvr_texture(texture_index),
                         PVR_FILTER_BILINEAR);
        context.gen.culling = PVR_CULLING_NONE;
        context.gen.fog_type = PVR_FOG_TABLE;
        if(material_alpha[material]) {
            context.txr.alpha = PVR_TXRALPHA_ENABLE;
        }
        pvr_poly_compile(&material_headers[material], &context);
        constexpr pvr_cull_mode_t kPvrCullModes[3] = {
            PVR_CULLING_NONE,
            PVR_CULLING_CCW,
            PVR_CULLING_CW,
        };
        for(std::uint32_t cull = 0U; cull < 3U; ++cull) {
            context.gen.culling = kPvrCullModes[cull];
            pvr_poly_compile(&room_strip_headers[material * 3U + cull],
                             &context);
        }
        if(material_punchthrough[material]) {
            pvr_poly_cxt_txr(
                &context, PVR_LIST_PT_POLY, format, texture->width,
                texture->height, textures.pvr_texture(texture_index),
                PVR_FILTER_BILINEAR);
            context.gen.fog_type = PVR_FOG_TABLE;
            context.txr.alpha = PVR_TXRALPHA_ENABLE;
            for(std::uint32_t cull = 0U; cull < 3U; ++cull) {
                context.gen.culling = kPvrCullModes[cull];
                pvr_poly_compile(
                    &room_punchthrough_headers[material * 3U + cull],
                    &context);
            }
        }
    }
    pvr_poly_hdr_t* leon_headers =
        new(std::nothrow) pvr_poly_hdr_t[leon.header().batch_count];
    pvr_poly_hdr_t* ganado_headers =
        new(std::nothrow) pvr_poly_hdr_t[ganado.header().batch_count];
    std::unique_ptr<bool[]> leon_alpha(
        new(std::nothrow) bool[leon.header().batch_count]);
    std::unique_ptr<bool[]> ganado_alpha(
        new(std::nothrow) bool[ganado.header().batch_count]);
    if(leon_headers == nullptr || ganado_headers == nullptr ||
       leon_alpha == nullptr || ganado_alpha == nullptr) {
        std::printf("re4dc-room: character material header allocation failed\n");
        return 1;
    }
    const auto compile_character_headers = [&context](
        const re4dc::character::Package& character,
        const re4dc::texture::Package& character_textures,
        pvr_poly_hdr_t* headers, bool* alpha, const char* label) {
        for(std::uint32_t batch_index = 0;
            batch_index < character.header().batch_count; ++batch_index) {
            char material_name[32];
            ::snprintf(
                material_name, sizeof(material_name), "PART_%03lu",
                static_cast<unsigned long>(character.batches()[batch_index].source_part));
            const auto* texture = character_textures.find(material_name);
            if(texture == nullptr) {
                std::printf("re4dc-room: missing %s material %s\n", label,
                            material_name);
                return false;
            }
            const std::uint32_t texture_index = static_cast<std::uint32_t>(
                texture - character_textures.textures());
            const int format = texture->format == re4dc::texture::kRgb565
                                   ? PVR_TXRFMT_RGB565
                                   : texture->format == re4dc::texture::kArgb1555
                                         ? PVR_TXRFMT_ARGB1555
                                         : PVR_TXRFMT_ARGB4444;
            alpha[batch_index] =
                (texture->flags & re4dc::texture::kAlpha) != 0;
            const pvr_list_t list = alpha[batch_index]
                                        ? PVR_LIST_TR_POLY
                                        : PVR_LIST_OP_POLY;
            pvr_poly_cxt_txr(&context, list, format,
                             texture->width, texture->height,
                             character_textures.pvr_texture(texture_index),
                             PVR_FILTER_BILINEAR);
            // Source Model::CullMode defaults to GX_CULL_FRONT.  The model
            // conversion preserves GX primitive order, so retain that source
            // cull direction for both native strips and clipped triangles.
            context.gen.culling = PVR_CULLING_CCW;
            context.gen.fog_type = PVR_FOG_TABLE;
            context.gen.specular = PVR_SPECULAR_ENABLE;
            if(alpha[batch_index]) {
                context.txr.alpha = PVR_TXRALPHA_ENABLE;
            }
            pvr_poly_compile(&headers[batch_index], &context);
        }
        return true;
    };
    if(!compile_character_headers(leon, leon_textures, leon_headers,
                                  leon_alpha.get(), "Leon") ||
       !compile_character_headers(ganado, ganado_textures, ganado_headers,
                                   ganado_alpha.get(), "Ganado")) {
        return 1;
    }
#if defined(RE4DC_SCENE_R100)
    pvr_poly_hdr_t* source_hud_headers =
        new(std::nothrow)
            pvr_poly_hdr_t[source_hud_textures.header().texture_count];
    if(source_hud_headers == nullptr) {
        std::printf("re4dc-room: source HUD header allocation failed\n");
        return 1;
    }
    for(std::uint32_t texture_index = 0;
        texture_index < source_hud_textures.header().texture_count;
        ++texture_index) {
        const auto& texture = source_hud_textures.textures()[texture_index];
        const int format = texture.format == re4dc::texture::kRgb565
                               ? PVR_TXRFMT_RGB565
                               : texture.format == re4dc::texture::kArgb1555
                                     ? PVR_TXRFMT_ARGB1555
                                     : PVR_TXRFMT_ARGB4444;
        pvr_poly_cxt_txr(
            &context, PVR_LIST_TR_POLY, format, texture.width, texture.height,
            source_hud_textures.pvr_texture(texture_index),
            PVR_FILTER_BILINEAR);
        context.gen.alpha = true;
        context.gen.culling = PVR_CULLING_NONE;
        context.gen.fog_type = PVR_FOG_DISABLE;
        context.depth.comparison = PVR_DEPTHCMP_ALWAYS;
        context.depth.write = false;
        context.blend.src = PVR_BLEND_SRCALPHA;
        context.blend.dst = PVR_BLEND_INVSRCALPHA;
        context.txr.alpha =
            texture.format == re4dc::texture::kRgb565;
        context.txr.uv_clamp = PVR_UVCLAMP_UV;
        pvr_poly_compile(&source_hud_headers[texture_index], &context);
    }
#endif
    g_re4dc_demo_telemetry.flags = 0x10000005U;
    g_re4dc_demo_telemetry.pvr_free_before_textures =
        static_cast<std::uint32_t>(vram_before_textures);
    g_re4dc_demo_telemetry.pvr_free_after_textures =
        static_cast<std::uint32_t>(pvr_mem_available());
    std::printf(
        "re4dc-room: textures=%lu+%lu+%lu bytes=%lu pvr_free_before=%lu "
        "pvr_free_after=%lu\n",
        static_cast<unsigned long>(textures.header().texture_count),
        static_cast<unsigned long>(leon_textures.header().texture_count),
        static_cast<unsigned long>(ganado_textures.header().texture_count),
        static_cast<unsigned long>(textures.vram_bytes() +
                                   leon_textures.vram_bytes() +
                                   ganado_textures.vram_bytes()),
        static_cast<unsigned long>(vram_before_textures),
        static_cast<unsigned long>(pvr_mem_available()));

    // mat_perspective maps positive view Y toward the bottom of the PVR screen.
    const vector_t up = {0.0f, -1.0f, 0.0f, 0.0f};
    Player player{};
    Enemy enemy{};
    const float player_move_speed =
        std::fabs(leon.clips()[kPlayerWalkClip].root_forward_speed_mps) >
                0.0001f
            ? std::fabs(
                  leon.clips()[kPlayerWalkClip].root_forward_speed_mps)
            : kFallbackPlayerMoveSpeed;
    const float enemy_move_speed =
        std::fabs(ganado.clips()[1].root_forward_speed_mps) > 0.0001f
            ? std::fabs(ganado.clips()[1].root_forward_speed_mps)
            : kFallbackEnemyMoveSpeed;
    std::printf(
        "re4dc-room: source root speeds player=%.4f enemy=%.4f m/s\n",
        player_move_speed, enemy_move_speed);
    Autoplay autoplay{};
    autoplay.enabled = file_exists("/rd/autoplay.flag");
    if(autoplay.enabled) {
#if defined(RE4DC_SCENE_R100)
        std::printf("re4dc-room: r100 30-second presentation trace enabled\n");
#else
        enemy.x = player.x + std::sin(player.yaw) *
                   kEnemyAttackAcquireRange * 0.85f;
        enemy.z = player.z + std::cos(player.yaw) *
                   kEnemyAttackAcquireRange * 0.85f;
        player.health = kEnemyAttackDamage;
#endif
    }
    float initial_floor = player.y;
    if(!find_floor(collision, player.x, player.z, player.y, initial_floor)) {
        std::printf("re4dc-room: spawn is not on collision floor\n");
        return 1;
    }
    player.y = initial_floor;
    std::uint32_t frame = 0;
    std::uint64_t simulation_tick = 0;
    std::uint64_t simulation_accumulator_us = kSimulationStepUs;
    std::uint32_t simulation_overruns = 0;
    std::uint64_t simulation_dropped_us = 0;
    std::uint64_t simulation_clamped_us = 0;
    std::uint64_t simulation_catchup_dropped_us = 0;
    std::uint64_t simulation_debt_us_max = simulation_accumulator_us;
    std::uint64_t input_samples = 0;
    std::uint64_t input_sample_gap_us_max = 0;
    std::uint64_t previous_time = 0U;
    std::uint64_t simulation_wall_time_us = 0U;
    bool fire_was_down = false;
    bool reload_was_down = false;
    bool restart_was_down = false;
    InputService input_service{};
    if(leon.header().position_count > kLeonVertexCapacity ||
       leon.header().normal_count > kLeonVertexCapacity ||
       leon.header().source_normal_count > kLeonVertexCapacity ||
       ganado.header().position_count > kGanadoVertexCapacity ||
       ganado.header().normal_count > kGanadoVertexCapacity ||
       ganado.header().source_normal_count > kGanadoVertexCapacity) {
        std::printf("re4dc-room: actor transform capacity exceeded\n");
        return 1;
    }
#if defined(RE4DC_SCENE_R100)
    prepare_source_lights();
    if(!prepare_room_static_lighting(room)) {
        std::printf("re4dc-room: room static-light preparation failed\n");
        return 1;
    }
    std::uint32_t room_light_links = 0U;
    if(room.source_groups() != nullptr) {
        for(std::uint32_t group = 0; group < room.header().group_count;
            ++group) {
            room_light_links += selected_light_count(
                source_group_light_selection(&room.source_groups()[group]));
        }
    }
    const std::uint32_t leon_light_selection =
        source_actor_light_selection(player.x, player.y, player.z, 1U);
    const std::uint32_t ganado_light_selection =
        source_actor_light_selection(enemy.x, enemy.y, enemy.z, 2U);
    std::printf(
        "re4dc-room: source light selection room_links=%lu "
        "leon_mask=%08lx/%u ganado_mask=%08lx/%u\n",
        static_cast<unsigned long>(room_light_links),
        static_cast<unsigned long>(leon_light_selection),
        selected_light_count(leon_light_selection),
        static_cast<unsigned long>(ganado_light_selection),
        selected_light_count(ganado_light_selection));
#endif
    g_re4dc_demo_telemetry.flags = 0x10000006U;
    DemoAudio audio;
    if(!load_demo_audio(audio)) {
        return 1;
    }
    if(!autoplay.enabled && !start_input_service(input_service)) {
        std::printf("re4dc-room: input service start failed\n");
        release_demo_audio(audio);
        return 1;
    }
    g_re4dc_demo_telemetry.aica_free_after_audio = snd_mem_available();
    const struct mallinfo heap_info = mallinfo();
    g_re4dc_demo_telemetry.heap_arena_bytes =
        static_cast<std::uint32_t>(heap_info.arena);
    g_re4dc_demo_telemetry.heap_used_bytes =
        static_cast<std::uint32_t>(heap_info.uordblks);
    g_re4dc_demo_telemetry.heap_free_bytes =
        static_cast<std::uint32_t>(heap_info.fordblks);
    const std::uintptr_t heap_end =
        reinterpret_cast<std::uintptr_t>(mm_sbrk(0));
    const std::uintptr_t main_ram_limit =
        static_cast<std::uintptr_t>(_arch_mem_top - THD_KERNEL_STACK_SIZE);
    g_re4dc_demo_telemetry.main_ram_free_bytes =
        static_cast<std::uint32_t>(
            main_ram_limit > heap_end ? main_ram_limit - heap_end : 0U);
    std::printf(
        "re4dc-room: stick=turn/move RT/Y=aim; stick/dpad Y=pitch; "
        "A=fire X=reload B=restart "
#if defined(RE4DC_SCENE_R100)
        "START=exit; defeat Ganado or retry the source encounter\n");
#else
        "START=exit; defeat Ganado then reach green marker\n");
#endif
    if(autoplay.enabled) {
        std::printf("re4dc-room: deterministic autoplay enabled\n");
    }
    previous_time = timer_us_gettime64();
    simulation_wall_time_us = previous_time - kSimulationStepUs;
    g_re4dc_demo_telemetry.flags = 0x10000007U;
    while(true) {
        const std::uint64_t now = timer_us_gettime64();
        const std::uint64_t current_work_start = now;
        g_collision_runtime_stats = {};
        const std::uint64_t outer_interval_us = now - previous_time;
        previous_time = now;
        const std::uint64_t maximum_accepted_interval =
            kSimulationStepUs * (kMaxSimulationCatchupTicks + 1U);
        const std::uint64_t accepted_interval = std::min<std::uint64_t>(
            outer_interval_us, maximum_accepted_interval);
        const std::uint64_t clamped_interval =
            outer_interval_us - accepted_interval;
        simulation_accumulator_us += accepted_interval;
        simulation_clamped_us += clamped_interval;
        simulation_dropped_us += clamped_interval;
        if(clamped_interval != 0U) {
            simulation_wall_time_us += clamped_interval;
            if(!autoplay.enabled) {
                discard_input_until(input_service, simulation_wall_time_us);
            }
        }
        simulation_debt_us_max =
            std::max(simulation_debt_us_max, simulation_accumulator_us);
        const std::uint64_t simulation_tick_begin = simulation_tick;
        std::uint64_t input_us = 0U;
        std::uint64_t input_sample_gap_us = 0;
        const std::uint64_t simulation_start = timer_us_gettime64();
        bool exit_requested = false;
        unsigned catchup_ticks = 0;
        while(simulation_accumulator_us >= kSimulationStepUs &&
              catchup_ticks < kMaxSimulationCatchupTicks) {
            const std::uint64_t tick_input_time_us =
                simulation_wall_time_us + kSimulationStepUs;
            Input input{};
            bool fire_pressed = false;
            bool reload_pressed = false;
            bool restart_pressed = false;
            bool exit_pressed = false;
            if(autoplay.enabled) {
                input = autoplay_input(autoplay, player, enemy,
                                       kSimulationDeltaSeconds);
                fire_pressed = input.fire && !fire_was_down;
                reload_pressed = input.reload && !reload_was_down;
                restart_pressed = input.restart && !restart_was_down;
                exit_pressed = input.exit;
                fire_was_down = input.fire;
                reload_was_down = input.reload;
                restart_was_down = input.restart;
            } else {
                const std::uint64_t input_start = timer_us_gettime64();
                const TickInput tick_input = consume_input_until(
                    input_service, tick_input_time_us);
                input_us += timer_us_gettime64() - input_start;
                input = tick_input.input;
                fire_pressed = tick_input.fire_pressed;
                reload_pressed = tick_input.reload_pressed;
                restart_pressed = tick_input.restart_pressed;
                exit_pressed = tick_input.exit_pressed;
            }
            if(exit_pressed) {
                exit_requested = true;
                break;
            }
            if(restart_pressed) {
                reset_encounter(player, enemy);
                std::printf("re4dc-room: encounter restarted tick=%llu\n",
                            static_cast<unsigned long long>(simulation_tick));
            }
            update_player(player, collision, input, player_move_speed,
                          kSimulationDeltaSeconds);
            update_animation(player, leon, input, kSimulationDeltaSeconds);
            update_combat(player, enemy, input, fire_pressed, reload_pressed,
                          kSimulationDeltaSeconds, collision, leon, ganado,
                          audio);
            update_enemy(enemy, player, ganado, leon, collision, route_ptr, audio,
                         kSimulationDeltaSeconds);
            const float goal_dx = player.x - kGoalX;
            const float goal_dz = player.z - kGoalZ;
            if(enemy.state == EnemyState::Dead && !player.dead &&
               goal_dx * goal_dx + goal_dz * goal_dz < 16.0f
#if defined(RE4DC_SCENE_R100)
               // The r100 presentation stays in the source encounter after
               // the kill. B explicitly restarts it; there is no invented
               // exit marker at this placement.
               && false
#endif
               ) {
                ++player.completed_loops;
                std::printf("re4dc-room: demo loop complete loops=%lu tick=%llu\n",
                            static_cast<unsigned long>(player.completed_loops),
                            static_cast<unsigned long long>(simulation_tick));
                reset_encounter(player, enemy);
            }
            simulation_accumulator_us -= kSimulationStepUs;
            simulation_wall_time_us = tick_input_time_us;
            ++simulation_tick;
            ++catchup_ticks;
        }
        if(exit_requested) {
            if(autoplay.enabled) {
                write_autoplay_result(autoplay, player);
            }
            break;
        }
        if(simulation_accumulator_us >= kSimulationStepUs) {
            const std::uint64_t catchup_dropped_us =
                simulation_accumulator_us -
                simulation_accumulator_us % kSimulationStepUs;
            simulation_catchup_dropped_us += catchup_dropped_us;
            simulation_dropped_us += catchup_dropped_us;
            simulation_accumulator_us %= kSimulationStepUs;
            simulation_wall_time_us += catchup_dropped_us;
            if(!autoplay.enabled) {
                discard_input_until(input_service, simulation_wall_time_us);
            }
            ++simulation_overruns;
            if(simulation_overruns == 1U || simulation_overruns % 120U == 0U) {
                std::printf(
                    "re4dc-room: simulation catch-up dropped tick=%llu overruns=%lu\n",
                    static_cast<unsigned long long>(simulation_tick),
                    static_cast<unsigned long>(simulation_overruns));
            }
        }
        InputServiceSnapshot input_snapshot{};
        if(!autoplay.enabled) {
            input_snapshot = input_service_snapshot(input_service);
            input_samples = input_snapshot.samples;
            input_sample_gap_us = input_snapshot.sample_gap_us;
            input_sample_gap_us_max = input_snapshot.sample_gap_us_max;
        }
        const std::uint64_t simulation_us =
            timer_us_gettime64() - simulation_start;
        const std::uint64_t simulation_ticks_run =
            simulation_tick - simulation_tick_begin;
        const std::uint64_t render_snapshot_tick = simulation_tick;
        const std::uint64_t camera_start = timer_us_gettime64();
        const bool shoulder_view = player.aiming && !player.dead;
        point_t eye{};
        point_t target{};
        float half_fov = kPi / 6.0f;
        if(shoulder_view) {
            // CameraQuasiFPS::calcOffset blends the authored up/mid/down
            // g_readyOfs[0][0] entries using exactly the weapon pitch that
            // drives pl_handgun's cMot3 motion blend.
            constexpr float camera_mid[3] = {-0.530f, 1.765f, -0.590f};
            constexpr float close_mid[3] = {-0.260f, 1.630f, -0.130f};
            constexpr float target_mid[3] = {-0.065f, 1.340f, 1.480f};
            constexpr float camera_positive[3] = {-0.527f, 0.600f, -0.680f};
            constexpr float close_positive[3] = {-0.265f, 1.280f, -0.350f};
            constexpr float target_positive[3] = {-0.220f, 4.080f, 1.100f};
            constexpr float camera_negative[3] = {-0.393f, 2.058f, -0.005f};
            constexpr float close_negative[3] = {-0.250f, 1.860f, -0.065f};
            constexpr float target_negative[3] = {-0.179f, 0.365f, 0.943f};
            const float pitch_amount = std::fabs(player.aim_pitch);
            const float* camera_extreme = player.aim_pitch >= 0.0f
                ? camera_positive
                : camera_negative;
            const float* target_extreme = player.aim_pitch >= 0.0f
                ? target_positive
                : target_negative;
            const float* close_extreme = player.aim_pitch >= 0.0f
                ? close_positive
                : close_negative;
            const float camera_x = camera_mid[0] +
                (camera_extreme[0] - camera_mid[0]) * pitch_amount;
            const float camera_y = camera_mid[1] +
                (camera_extreme[1] - camera_mid[1]) * pitch_amount;
            const float camera_z = camera_mid[2] +
                (camera_extreme[2] - camera_mid[2]) * pitch_amount;
            const re4dc::collision::Vec3 close = {
                close_mid[0] + (close_extreme[0] - close_mid[0]) * pitch_amount,
                close_mid[1] + (close_extreme[1] - close_mid[1]) * pitch_amount,
                close_mid[2] + (close_extreme[2] - close_mid[2]) * pitch_amount};
            const float target_x = target_mid[0] +
                (target_extreme[0] - target_mid[0]) * pitch_amount;
            const float target_y = target_mid[1] +
                (target_extreme[1] - target_mid[1]) * pitch_amount;
            const float target_z = target_mid[2] +
                (target_extreme[2] - target_mid[2]) * pitch_amount;
            const re4dc::collision::Vec3 camera =
                {camera_x, camera_y, camera_z};
            const re4dc::collision::Vec3 target_offset =
                {target_x, target_y, target_z};
            const auto corrected_camera = correct_source_camera_walls(
                collision, player, camera, close, target_offset, 45.0f);
            const auto eye_world = player_offset_to_world(
                player, corrected_camera);
            const auto target_world = player_offset_to_world(
                player, target_offset);
            eye = {eye_world.x, eye_world.y, eye_world.z, 1.0f};
            target = {target_world.x, target_world.y, target_world.z, 1.0f};
            half_fov = 45.0f * kPi / 360.0f;
        } else {
#if defined(RE4DC_SCENE_R100)
            // r100_000.CAM area 2, neutral middle site (cut 2 entries 7/19).
            // This is the source-authored normal gameplay camera at the
            // r100_Sce_look encounter placement.
            constexpr float camera_x = -0.500f;
            constexpr float camera_y = 1.765f;
            constexpr float camera_z = -1.190f;
            constexpr float target_x = 0.0f;
            constexpr float target_y = 1.340f;
            constexpr float target_z = 1.480f;
            // Entries 19 of the same cut are the source close points used by
            // CameraQuasiFPS::hitCheck, not an extra visible target.
            constexpr re4dc::collision::Vec3 close =
                {0.0f, 1.800f, -0.090f};
            const re4dc::collision::Vec3 camera =
                {camera_x, camera_y, camera_z};
            const re4dc::collision::Vec3 target_offset =
                {target_x, target_y, target_z};
            const auto corrected_camera = correct_source_camera_walls(
                collision, player, camera, close, target_offset, 50.0f);
            const auto eye_world = player_offset_to_world(
                player, corrected_camera);
            const auto target_world = player_offset_to_world(
                player, target_offset);
            eye = {eye_world.x, eye_world.y, eye_world.z, 1.0f};
            target = {target_world.x, target_world.y, target_world.z, 1.0f};
            half_fov = 50.0f * kPi / 360.0f;
#else
            const float fx = std::sin(player.yaw);
            const float fz = std::cos(player.yaw);
            const float rx = std::cos(player.yaw);
            const float rz = -std::sin(player.yaw);
            constexpr float camera_distance = 4.75f;
            constexpr float camera_lateral = 0.85f;
            eye = {
                player.x - fx * camera_distance + rx * camera_lateral,
                player.y + 2.55f,
                player.z - fz * camera_distance + rz * camera_lateral, 1.0f};
            target = {
                player.x + fx * 2.0f,
                player.y + 1.2f,
                player.z + fz * 2.0f, 1.0f};
#endif
        }
#if defined(RE4DC_SCENE_R100)
        set_source_lighting_camera(eye, target, half_fov);
#endif
        mat_identity();
        mat_perspective(kScreenWidth * 0.5f, kScreenHeight * 0.5f,
                        1.0f / std::tan(half_fov), kNearClipDistance,
                        kFarClipDistance);
        mat_lookat(&eye, &target, &up);
        const std::uint64_t camera_us = timer_us_gettime64() - camera_start;
        const FrameStats stats = render_scene(
            room, leon, ganado, player, enemy, untextured_header,
            material_headers, room_strip_headers, room_punchthrough_headers,
            material_alpha.get(), material_punchthrough.get(),
            visible_room_groups, room.header().group_count, leon_headers,
            leon_alpha.get(), ganado_headers, ganado_alpha.get(),
#if defined(RE4DC_SCENE_R100)
            source_hud, source_hud_headers,
#endif
            g_leon_projected, g_ganado_projected,
#if defined(RE4DC_SCENE_R100)
            g_leon_lighting, g_ganado_lighting,
#endif
            g_character_submit_vertices);
        pvr_stats_t pvr_stats{};
        const bool have_pvr_stats = pvr_get_stats(&pvr_stats) == 0;
        const std::uint64_t current_work_us =
            timer_us_gettime64() - current_work_start;
        std::uint32_t publish_sequence = g_re4dc_demo_telemetry.sequence;
        if(publish_sequence & 1U) {
            ++publish_sequence;
        }
        g_re4dc_demo_telemetry.sequence = publish_sequence + 1U;
        __asm__ volatile("" ::: "memory");
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
        g_re4dc_demo_telemetry.visible_groups = stats.groups;
        g_re4dc_demo_telemetry.transformed_vertices =
            stats.transformed_vertices;
        g_re4dc_demo_telemetry.room_triangles = stats.triangles;
        g_re4dc_demo_telemetry.actor_triangles = stats.character_triangles;
        g_re4dc_demo_telemetry.frame_us = saturate_u32(current_work_us);
        g_re4dc_demo_telemetry.submit_us = saturate_u32(stats.submit_us);
        g_re4dc_demo_telemetry.simulation_tick =
            saturate_u32(render_snapshot_tick);
        g_re4dc_demo_telemetry.simulation_overruns = simulation_overruns;
        g_re4dc_demo_telemetry.simulation_tick_begin =
            saturate_u32(simulation_tick_begin);
        g_re4dc_demo_telemetry.simulation_ticks_run =
            saturate_u32(simulation_ticks_run);
        g_re4dc_demo_telemetry.simulation_dropped_ticks =
            saturate_u32(simulation_dropped_us / kSimulationStepUs);
        g_re4dc_demo_telemetry.simulation_dropped_us =
            saturate_u32(simulation_dropped_us);
        g_re4dc_demo_telemetry.simulation_clamped_us =
            saturate_u32(simulation_clamped_us);
        g_re4dc_demo_telemetry.simulation_catchup_dropped_us =
            saturate_u32(simulation_catchup_dropped_us);
        g_re4dc_demo_telemetry.simulation_debt_us =
            saturate_u32(simulation_accumulator_us);
        g_re4dc_demo_telemetry.simulation_debt_us_max =
            saturate_u32(simulation_debt_us_max);
        g_re4dc_demo_telemetry.outer_interval_us =
            saturate_u32(outer_interval_us);
        g_re4dc_demo_telemetry.input_samples = saturate_u32(input_samples);
        g_re4dc_demo_telemetry.input_sample_gap_us =
            saturate_u32(input_sample_gap_us);
        g_re4dc_demo_telemetry.input_sample_gap_us_max =
            saturate_u32(input_sample_gap_us_max);
        g_re4dc_demo_telemetry.input_us = saturate_u32(input_us);
        g_re4dc_demo_telemetry.simulation_us = saturate_u32(simulation_us);
        g_re4dc_demo_telemetry.camera_us = saturate_u32(camera_us);
        g_re4dc_demo_telemetry.render_total_us = saturate_u32(stats.total_us);
        g_re4dc_demo_telemetry.actor_pose_us =
            saturate_u32(stats.actor_pose_us);
        g_re4dc_demo_telemetry.actor_normals_us =
            saturate_u32(stats.actor_normals_us);
        g_re4dc_demo_telemetry.actor_lighting_us =
            saturate_u32(stats.actor_lighting_us);
        g_re4dc_demo_telemetry.pvr_wait_us = saturate_u32(stats.wait_us);
        g_re4dc_demo_telemetry.opaque_room_us =
            saturate_u32(stats.opaque_room_us);
        g_re4dc_demo_telemetry.opaque_actor_us =
            saturate_u32(stats.opaque_actor_us);
        g_re4dc_demo_telemetry.translucent_room_us =
            saturate_u32(stats.translucent_room_us);
        g_re4dc_demo_telemetry.translucent_actor_hud_us =
            saturate_u32(stats.translucent_actor_hud_us);
        g_re4dc_demo_telemetry.scene_finish_us =
            saturate_u32(stats.finish_us);
        g_re4dc_demo_telemetry.pvr_sample_frame_count =
            have_pvr_stats ? static_cast<std::uint32_t>(pvr_stats.frame_count) : 0U;
        g_re4dc_demo_telemetry.pvr_sample_vblank_count =
            have_pvr_stats ? static_cast<std::uint32_t>(pvr_stats.vbl_count) : 0U;
        g_re4dc_demo_telemetry.pvr_sample_last_present_ns =
            have_pvr_stats ? saturate_u32(pvr_stats.frame_last_time) : 0U;
        g_re4dc_demo_telemetry.pvr_sample_last_registration_ns =
            have_pvr_stats ? saturate_u32(pvr_stats.reg_last_time) : 0U;
        g_re4dc_demo_telemetry.pvr_sample_last_render_ns =
            have_pvr_stats ? saturate_u32(pvr_stats.rnd_last_time) : 0U;
        g_re4dc_demo_telemetry.pvr_sample_vertex_bytes =
            have_pvr_stats ? saturate_u32(pvr_stats.vtx_buffer_used) : 0U;
        g_re4dc_demo_telemetry.pvr_sample_vertex_bytes_max =
            have_pvr_stats ? saturate_u32(pvr_stats.vtx_buffer_used_max) : 0U;
        g_re4dc_demo_telemetry.room_index_references =
            stats.room_index_references;
        g_re4dc_demo_telemetry.room_cache_hits = stats.room_cache_hits;
        g_re4dc_demo_telemetry.room_cache_misses = stats.room_cache_misses;
        g_re4dc_demo_telemetry.room_light_evaluations =
            stats.room_light_evaluations;
        g_re4dc_demo_telemetry.room_near_trivial_accepts =
            stats.room_near_trivial_accepts;
        g_re4dc_demo_telemetry.room_near_trivial_rejects =
            stats.room_near_trivial_rejects;
        g_re4dc_demo_telemetry.room_near_crossings =
            stats.room_near_crossings;
        g_re4dc_demo_telemetry.collision_queries =
            g_collision_runtime_stats.queries;
        g_re4dc_demo_telemetry.collision_block_tests =
            g_collision_runtime_stats.block_tests;
        g_re4dc_demo_telemetry.collision_polygon_candidates =
            g_collision_runtime_stats.polygon_candidates;
        g_re4dc_demo_telemetry.input_queue_drops =
            saturate_u32(input_snapshot.queue_drops);
        g_re4dc_demo_telemetry.input_queue_depth =
            input_snapshot.queue_depth;
        g_re4dc_demo_telemetry.input_edges_delivered =
            saturate_u32(input_snapshot.edges_delivered);
        g_re4dc_demo_telemetry.actor_vertex_records =
            stats.character_vertex_records;
        g_re4dc_demo_telemetry.actor_direct_strips =
            stats.character_direct_strips;
        g_re4dc_demo_telemetry.actor_strip_fallbacks =
            stats.character_strip_fallbacks;
        g_re4dc_demo_telemetry.room_vertex_records =
            stats.room_vertex_records;
        g_re4dc_demo_telemetry.room_direct_strips =
            stats.room_direct_strips;
        g_re4dc_demo_telemetry.room_strip_fallbacks =
            stats.room_strip_fallbacks;
        g_re4dc_demo_telemetry.room_visibility_us =
            saturate_u32(stats.room_visibility_us);
        g_re4dc_demo_telemetry.room_light_selection_evaluations =
            stats.room_light_selection_evaluations;
        g_re4dc_demo_telemetry.pvr_submit_calls = stats.pvr_submit_calls;
        g_re4dc_demo_telemetry.pvr_submit_bytes = stats.pvr_submit_bytes;
        __asm__ volatile("" ::: "memory");
        g_re4dc_demo_telemetry.sequence = publish_sequence + 2U;
        ++frame;
        if(frame % 120U == 0U) {
            std::printf(
                "re4dc-room: frame=%lu pos=%.2f,%.2f,%.2f groups=%lu vertices=%lu "
                "triangles=%lu actors_triangles=%lu wall_hits=%lu loops=%lu "
                "hp=%d ammo=%d enemy_hp=%d state=%u work_us=%llu render_us=%llu "
                "wait_us=%llu submit_us=%llu finish_us=%llu sim_tick=%llu "
                "sim_ticks=%llu dropped_us=%llu debt_us=%llu input_gap_us=%llu "
                "visibility_us=%llu light_selects=%lu pvr_calls=%lu "
                "pvr_bytes=%lu cache=%lu/%lu/%lu near=%lu/%lu/%lu "
                "overruns=%lu\n",
                static_cast<unsigned long>(frame), player.x, player.y, player.z,
                static_cast<unsigned long>(stats.groups),
                static_cast<unsigned long>(stats.transformed_vertices),
                static_cast<unsigned long>(stats.triangles),
                static_cast<unsigned long>(stats.character_triangles),
                static_cast<unsigned long>(player.wall_hits),
                static_cast<unsigned long>(player.completed_loops),
                player.health, player.ammo, enemy.health,
                static_cast<unsigned>(enemy.state),
                static_cast<unsigned long long>(current_work_us),
                static_cast<unsigned long long>(stats.total_us),
                static_cast<unsigned long long>(stats.wait_us),
                static_cast<unsigned long long>(stats.submit_us),
                static_cast<unsigned long long>(stats.finish_us),
                static_cast<unsigned long long>(simulation_tick),
                static_cast<unsigned long long>(simulation_ticks_run),
                static_cast<unsigned long long>(simulation_dropped_us),
                static_cast<unsigned long long>(simulation_accumulator_us),
                static_cast<unsigned long long>(input_sample_gap_us),
                static_cast<unsigned long long>(stats.room_visibility_us),
                static_cast<unsigned long>(
                    stats.room_light_selection_evaluations),
                static_cast<unsigned long>(stats.pvr_submit_calls),
                static_cast<unsigned long>(stats.pvr_submit_bytes),
                static_cast<unsigned long>(stats.room_index_references),
                static_cast<unsigned long>(stats.room_cache_hits),
                static_cast<unsigned long>(stats.room_cache_misses),
                static_cast<unsigned long>(stats.room_near_trivial_accepts),
                static_cast<unsigned long>(stats.room_near_trivial_rejects),
                static_cast<unsigned long>(stats.room_near_crossings),
                static_cast<unsigned long>(simulation_overruns));
        }
    }
    if(!autoplay.enabled) {
        stop_input_service(input_service);
    }
    delete[] ganado_headers;
    delete[] leon_headers;
    delete[] room_punchthrough_headers;
    delete[] room_strip_headers;
    delete[] material_headers;
    delete[] visible_room_groups;
    release_demo_audio(audio);
    std::printf("re4dc-room: clean exit\n");
    return 0;
}
