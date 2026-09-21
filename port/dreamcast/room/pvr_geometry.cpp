#include "pvr_geometry.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
namespace re4dc::render {
void begin_pvr_packet(pvr_vertex_t* commands, std::uint32_t& command_count,
                      const pvr_poly_hdr_t& header) {
    static_assert(sizeof(pvr_vertex_t) == sizeof(pvr_poly_hdr_t));
    std::memcpy(commands, &header, sizeof(header));
    command_count = 1U;
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

RenderVertex interpolate_vertex(const RenderVertex& a, const RenderVertex& b,
                                float t, const ClipParameters& parameters) {
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
    parameters.project(x, y, z, parameters.context);
    result.position.x = x;
    result.position.y = y;
    result.position.z = z;
    return result;
}

std::uint32_t clip_projected_triangle(const RenderVertex* source,
                                       pvr_vertex_t* output,
                                       std::uint8_t cull_mode,
                                       const ClipParameters& parameters,
                                       ClipStats* stats) {
    RenderVertex clipped[4]{};
    unsigned clipped_count = 0;
    unsigned inside_count = 0;
    for(unsigned corner = 0; corner < 3; ++corner) {
        inside_count +=
            source[corner].position.depth >= parameters.near_distance ? 1U : 0U;
    }
    if(inside_count == 3U) {
        if(stats != nullptr) {
            ++stats->accepts;
        }
        clipped[0] = source[0];
        clipped[1] = source[1];
        clipped[2] = source[2];
        clipped_count = 3U;
    } else if(inside_count == 0U) {
        if(stats != nullptr) {
            ++stats->rejects;
        }
        return 0;
    } else {
        if(stats != nullptr) {
            ++stats->crossings;
        }
        RenderVertex previous = source[2];
        bool previous_inside =
            previous.position.depth >= parameters.near_distance;
        for(unsigned corner = 0; corner < 3; ++corner) {
            const RenderVertex current = source[corner];
            const bool current_inside =
                current.position.depth >= parameters.near_distance;
            if(current_inside != previous_inside) {
                const float t =
                    (parameters.near_distance - previous.position.depth) /
                    (current.position.depth - previous.position.depth);
                clipped[clipped_count++] =
                    interpolate_vertex(previous, current, t, parameters);
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
            triangle[0].position.depth > parameters.far_distance &&
            triangle[1].position.depth > parameters.far_distance &&
            triangle[2].position.depth > parameters.far_distance;
        const bool left = triangle[0].position.x < 0.0f &&
                          triangle[1].position.x < 0.0f &&
                          triangle[2].position.x < 0.0f;
        const bool right = triangle[0].position.x > parameters.width &&
                           triangle[1].position.x > parameters.width &&
                           triangle[2].position.x > parameters.width;
        const bool above = triangle[0].position.y < 0.0f &&
                           triangle[1].position.y < 0.0f &&
                           triangle[2].position.y < 0.0f;
        const bool below = triangle[0].position.y > parameters.height &&
                           triangle[1].position.y > parameters.height &&
                           triangle[2].position.y > parameters.height;
        const bool culled =
            cull_mode == 3U ||
            (cull_mode == 2U && signed_area >= 0.0f) ||
            (cull_mode == 1U && signed_area <= 0.0f) ||
            (cull_mode == 0U &&
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


void submit_pvr(const void* data, std::size_t byte_count) {
    pvr_prim(data, byte_count);
}
} // namespace re4dc::render
