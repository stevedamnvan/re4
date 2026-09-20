# r100 R3b native room-strip checkpoint

Recorded 2026-09-20 on top of the source-child culling and source
attribute-identity checkpoints. Room package version 2 now retains the original
triangle stream and adds deterministic, winding-preserving strips prepared
offline inside each material batch. The opaque Dreamcast path submits eligible
strips directly to the PVR with the source SMX cull mode.

## Fidelity boundary

The converter does not weld vertices, change UVs, change normals, merge
materials, or drop triangles. It starts strips only between triangles that
share the required directed edge. All 30,895 accepted r100 triangles were
reconstructed from the generated strips and compared as winding-preserving
cyclic index triples; all 119 source batches matched with no missing or extra
triangles.

The runtime keeps the previous indexed triangle array. Translucent batches
continue to use that exact order and the existing CPU clipping path. An opaque
strip crossing the near or far bound also falls back to CPU-clipped triangles.
This preserves correct near-plane behavior instead of rejecting a complete
primitive. Source cull-none, front, back, and all modes map to separate native
PVR header paths; cull-all objects are skipped.

The accepted 24 m source-child package contains:

| Measure | Value |
|---|---:|
| Source triangles / triangle index records | 30,895 / 92,685 |
| Native strips | 11,234 |
| Strip vertex records | 53,363 |
| Longest strip | 34 vertices |
| Triangle-record reduction represented by strips | 42.4% |
| Version 1 package | 1,711,412 bytes |
| Version 2 package | 2,017,240 bytes |

The package grows by 305,828 bytes because both representations remain
resident. This is deliberate at this checkpoint: original order remains
available for transparency, clipping fallback, and comparison. A later
residency pass may split opaque and translucent records after the source
material classification is complete.

## Matched Flycast result

The comparison uses the same 640x480 room, source camera, actors, textures,
lighting, simulation, and autoplay route. Medians cover simulation ticks 220
through 474.

| Measure | Version 1 triangles | Version 2 native strips | Change |
|---|---:|---:|---:|
| Outer frame work | 179.279 ms | 155.421 ms | -23.858 ms (-13.3%) |
| Total render work | 178.839 ms | 155.035 ms | -23.804 ms (-13.3%) |
| Submission interval | 142.471 ms | 117.401 ms | -25.070 ms (-17.6%) |
| Opaque room pass | 83.779 ms | 59.936 ms | -23.843 ms (-28.5%) |
| Translucent room pass | 38.189 ms | 38.211 ms | +0.022 ms |
| Room index references | 46,068 | 33,154 | -12,914 (-28.0%) |
| Room transforms/light evaluations | 25,417 | 25,417 | unchanged |
| Main-RAM headroom | 2,842,624 bytes | 2,494,464 bytes | -348,160 bytes |

The candidate median submitted 3,187 direct room strips and used 911 strip
fallbacks. `room_triangles` no longer has the same meaning in the two builds:
the old counter records CPU-accepted triangles, while a direct strip records
its candidate triangles before PVR culling and screen tiling. The new
`room_vertex_records`, `room_direct_strips`, and `room_strip_fallbacks`
telemetry fields make the native path explicit.

Actor pose, normal, lighting, and submission medians remain within measurement
noise. The isolated translucent pass is unchanged. That confines the measured
gain to the intended opaque room path rather than a camera, asset, lighting, or
actor reduction.

## Visual and input check

The manual candidate reached the same source camera and player-death state as
the accepted version 4 build. Three static-background regions covering 113,070
pixels were byte-identical: the left lit wall, upper room, and right wall. The
actors differ in captured animation phase, so they were excluded from this
room-surface comparison. Manual input remained on the independent controller
service with no queue drops; this was a path check, not a measured human-input
latency test.

Evidence:

- Version 1 baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d150-r2b-attribute-identities-autoplay`
- Version 2 autoplay:
  `C:\Flycast-Evidence\re4-dreamcast\d152-r3b-native-room-strips-autoplay`
- Version 2 manual image and trace:
  `C:\Flycast-Evidence\re4-dreamcast\d153-r3b-native-room-strips-manual`
- Autoplay ELF SHA-256:
  `fac64cd0a95c29c50f4af1e3a18af427c98202536d14d5d4fb7cefb67329cf5b`
- Manual ELF SHA-256:
  `d17498480619f0352136e37903c634d2f0a07493c46a99172a8cd6bfaa0e68f0`
- r100 room package SHA-256:
  `86f9a4efca955ebc1f242e67ac6c2d1c44a3e41b30ff0f947faf1a6318bdbdaa`

## Acceptance boundary

This reduces the matched Flycast interval from about 5.6 to 6.4 frames per
second. It is a substantial fidelity-preserving renderer improvement, but it
does not establish real-time playability, stock Dreamcast timing, physical
output, full source material semantics, or original-game pixel parity. The
largest measured costs remain opaque room processing, transparent room
processing, actor lighting, and actor submission. Physical hardware remains a
separate gate.
