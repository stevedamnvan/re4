#pragma once
#include <cstdint>
namespace re4dc::render {
// R3w's contiguous selected-light layout/evaluator, extracted from room/main.cpp.
struct PreparedActorLight {
    float x;
    float y;
    float z;
    float red;
    float green;
    float blue;
    float intensity;
    float radius;
    float quadratic_attenuation;
    float direction_x;
    float direction_y;
    float direction_z;
    float spot_cutoff;
    float spot_scale;
    std::uint32_t type;
};

struct PreparedActorLights {
    PreparedActorLight lights[8]{};
    std::uint32_t count = 0U;
};

void evaluate_prepared_actor_lighting(float,float,float,float,float,float,
    const PreparedActorLights&,const float ambient[3],float&,float&,float&);
// Native source bridge captures the actual GX coefficients AFTER source light
// selection, object-volume attenuation, enemy fades and camera transformation.
struct SourceLight { float position[3],direction[3],a[3],k[3]; std::uint8_t color[4]; };
struct SourceLighting {
    SourceLight lights[8]{};
    float normal_matrix[12]{};
    std::uint8_t ambient[4]{},material[4]{255,255,255,255};
    unsigned mask=0,enable=0,ambient_vertex=0,material_vertex=0,diffuse=2,attenuation=1;
    float tev_scale=1;
};
struct PreparedSourceLights { SourceLight lights[8]{}; unsigned count=0; };
PreparedSourceLights prepare_actor_lights(const SourceLighting&);
// Unclamped partial accumulation permits invariant world-light caching without
// changing the final clamp. No invented hard radius cutoff is applied.
void evaluate_prepared_source_lighting(float px,float py,float pz,float nx,float ny,float nz,
    const SourceLighting&,const PreparedSourceLights&,const std::uint8_t color[4],float out[3]);
} // namespace re4dc::render
