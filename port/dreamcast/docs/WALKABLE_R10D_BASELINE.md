# r10d walkable SH-4 checkpoint

This checkpoint integrates the first controllable room path in the native
KallistiOS executable. It is a P0 implementation and Flycast validation step,
not accepted RE4 gameplay or physical Dreamcast evidence.

## Integrated behavior

- Private `r10d_001.SAT` conversion into a validated 6,860-byte `RE4DCSAT`
  package with 212 vertices, 83 normals, 38 floors, 12 slopes, and 219 walls.
- Analog-stick and D-pad tank movement with time-based speed and dead-zone.
- Floor selection near the current height, slope support, wall-circle
  resolution, and cancellation when no reachable floor exists.
- Upright shoulder follow camera, orange placeholder player, green exit marker,
  automatic exit reset, A-button manual reset, and START exit.
- Telemetry for player position, room groups/vertices/triangles, wall contacts,
  completed loops, and the existing combined render-call timer.

The collision package keeps the source polygon attributes and classification.
The runtime directly scans the 269 polygons; importing the 77-node source block
tree is unnecessary for this room-sized checkpoint.

## Flycast result

The final executable built as a 5,769,432-byte SH-4 ELF with SHA-256
`69652ee2a898587c00389c4fc8cde1717aceaa2686e78bda10ae9cf6adfe4105`.
It loaded the unchanged room package
`588e5dc48253828dd1348a623c2c967eea52832a9fd64a0f0a60e3a5a3caf13a`
and collision package
`f208721edc9d3e2b616e4f2a787826ed58a673497db75e3ce68d53e94f332b5f`.

A keyboard-driven D-pad capture in Flycast demonstrated turning, floor
following, wall blocking, and two automatic exit resets. The run was retained
privately at
`C:\Flycast-Evidence\re4-dreamcast\walkable-p0-20260919-161631`.
A third fixed-duration replay continued sending movement after an early reset,
so it drifted away from the route; the required clean three-loop record remains
open rather than being inferred from that run.

At the initial close camera, the ten-unit cell package transformed 58,217
vertices and the combined render call took about 114 ms. The source-group
comparison transformed 47,966 vertices, submitted the same 11,592 triangles,
and took about 110 ms, so source groups are now the default. Views deeper in the room ranged
from roughly 10,000 to 34,000 transformed vertices and 16-68 ms. These are
Flycast samples, include `pvr_wait_ready()`, and remain over or too close to the
33.3 ms target. They confirm that a gameplay camera helps but does not close
performance. Timing phases are now instrumented; near-plane clipping and the
clean three-loop record remain before closing P0.

The first split-timing sample at the unchanged spawn reported a 109,427 us
frame interval: 1 us in `pvr_wait_ready`, 109,294 us in bounds tests,
transforms, and direct PVR submission, and 21 us finishing the scene. This
locates the current bottleneck in CPU geometry work and per-triangle submission,
not waiting for the PVR. It is one Flycast sample rather than a percentile or
physical-hardware result.

## Boundary

The temporary marker and flat-shaded room make traversal inspectable. They do
not substitute for visible skinned Leon, source camera parity, textures, combat,
audio, or a stock Dreamcast run. P1 should begin after the bounded P0 renderer
work and clean three-loop capture; scenery-only optimization must not delay it.
