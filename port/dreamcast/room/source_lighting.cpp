#include "source_lighting.hpp"
#include <algorithm>
#include <cmath>
namespace re4dc::render {
namespace {
void normalize_vector(float& x,float& y,float& z){
    const float l=std::sqrt(x*x+y*y+z*z);
    if(l<=0.000001f){x=0;y=1;z=0;return;}
    x/=l;y/=l;z/=l;
}
}
void evaluate_prepared_actor_lighting(
    float px, float py, float pz, float nx, float ny, float nz,
    const PreparedActorLights& lights, const float ambient[3],
    float& out_red, float& out_green, float& out_blue) {
    normalize_vector(nx, ny, nz);
    float red = ambient[0];
    float green = ambient[1];
    float blue = ambient[2];
    const PreparedActorLight* light = lights.lights;
    const PreparedActorLight* const end = light + lights.count;
    for(; light != end; ++light) {
        float lx = 0.0f;
        float ly = 0.0f;
        float lz = 0.0f;
        float attenuation = light->intensity;
        if(light->type == 5U) {
            lx = light->x;
            ly = light->y;
            lz = light->z;
        } else {
            lx = light->x - px;
            ly = light->y - py;
            lz = light->z - pz;
            const float distance = std::sqrt(lx * lx + ly * ly + lz * lz);
            if(distance <= 0.000001f) {
                continue;
            }
            lx /= distance;
            ly /= distance;
            lz /= distance;
            if(light->type == 1U) {
                attenuation = light->radius > 0.0f
                                  ? light->intensity * std::max(
                                        0.0f, 1.0f - distance / light->radius)
                                  : light->intensity;
            } else {
                attenuation = light->intensity /
                              std::max(1.0f, 1.0f +
                                                light->quadratic_attenuation *
                                                    distance * distance);
            }
            if(light->type == 3U) {
                const float cone_cosine =
                    light->direction_x * -lx +
                    light->direction_y * -ly +
                    light->direction_z * -lz;
                if(cone_cosine <= light->spot_cutoff) {
                    continue;
                }
                attenuation *= (cone_cosine - light->spot_cutoff) *
                               light->spot_scale;
            }
        }
        const float diffuse = std::max(0.0f, nx * lx + ny * ly + nz * lz);
        red += light->red * attenuation * diffuse;
        green += light->green * attenuation * diffuse;
        blue += light->blue * attenuation * diffuse;
    }
    out_red = std::clamp(red, 0.0f, 1.0f);
    out_green = std::clamp(green, 0.0f, 1.0f);
    out_blue = std::clamp(blue, 0.0f, 1.0f);
}

PreparedSourceLights prepare_actor_lights(const SourceLighting& source){
    PreparedSourceLights out;
    if(source.enable)for(unsigned i=0;i<8;++i)
        if(source.mask&(1U<<i))out.lights[out.count++]=source.lights[i];
    return out;
}
void evaluate_prepared_source_lighting(float px,float py,float pz,float nx,float ny,float nz,
    const SourceLighting& state,const PreparedSourceLights& lights,
    const std::uint8_t color[4],float out[3]){
    const auto* ambient=state.ambient_vertex?color:state.ambient;
    const auto* material=state.material_vertex?color:state.material;
    for(unsigned i=0;i<3;++i)out[i]=state.enable?ambient[i]/255.f:1.f;
    for(const SourceLight* light=lights.lights;light!=lights.lights+lights.count;++light){
        float lx=light->position[0]-px,ly=light->position[1]-py,lz=light->position[2]-pz;
        const float distance2=lx*lx+ly*ly+lz*lz,distance=std::sqrt(distance2);
        if(distance>0){lx/=distance;ly/=distance;lz/=distance;}
        else {lx=nx;ly=ny;lz=nz;}
        float attenuation=1;
        if(state.attenuation==1){
            const float cosine=std::max(0.f,lx*light->direction[0]+ly*light->direction[1]+lz*light->direction[2]);
            const float angular=std::max(0.f,light->a[0]+light->a[1]*cosine+light->a[2]*cosine*cosine);
            const float denominator=light->k[0]+light->k[1]*distance+light->k[2]*distance2;
            attenuation=denominator>0?angular/denominator:0;
        }
        float diffuse=state.diffuse?nx*lx+ny*ly+nz*lz:1.f;
        if(state.diffuse==2)diffuse=std::max(0.f,diffuse);
        for(unsigned i=0;i<3;++i)out[i]+=light->color[i]/255.f*attenuation*diffuse;
    }
    for(unsigned i=0;i<3;++i)
        out[i]=material[i]/255.f*std::clamp(out[i],0.f,1.f)*state.tev_scale;
}
} // namespace re4dc::render
