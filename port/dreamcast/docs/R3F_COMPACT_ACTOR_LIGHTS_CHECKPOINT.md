# r100 R3f compact actor-light checkpoint

Recorded 2026-09-20 after the compact dynamic room-light checkpoint. The
source-derived actor selection already limits a model to at most eight lights,
but the per-normal evaluator still scanned all nine room-light records and
tested the selection bit for every entry. Leon and the Ganado together evaluate
8,435 animated normal identities per rendered frame.

The new path converts each actor's source selection mask into an ascending
source-index list once per frame. The per-normal loop consumes only that list.
It retains the original selection result, source iteration order, prepared
camera-relative directions, point and spot calculations, attenuation, diffuse
clamp, ambient term, accumulation order, final clamp, and packed-color path.
The eight-entry bound matches the recovered source model-light-list capacity.

## Correctness comparison

A verification ELF ran the compact and general calculations from the same
unmodified animated normals, then compared their final packed 8-bit colors.
Across 67 sampled frames, covering simulation ticks 1 through 298, it reported
zero mismatches. The dual calculation and temporary telemetry override are
absent from the production build.

Actor poses, normal construction, selected-light masks, geometry, textures,
camera, room work, and draw submission are unchanged.

## Matched Flycast result

Medians cover simulation ticks 220 through 474.

| Measure | General mask scan | Compact selected list | Change |
|---|---:|---:|---:|
| Outer frame work | 130.046 ms | 125.552 ms | -4.494 ms (-3.5%) |
| Total render work | 129.664 ms | 125.221 ms | -4.443 ms (-3.4%) |
| Actor lighting | 20.469 ms | 15.870 ms | -4.599 ms (-22.5%) |
| Actor normal construction | 9.727 ms | 9.727 ms | unchanged |
| Actor pose projection | 5.179 ms | 5.178 ms | unchanged |
| Opaque actor pass | 16.667 ms | 16.666 ms | unchanged |
| Opaque room pass | 44.933 ms | 45.017 ms | +0.084 ms |
| Translucent room pass | 27.552 ms | 27.601 ms | +0.049 ms |

The matched Flycast rate moves from about 7.7 to 8.0 frames per second. The
submission-interval median moved from 91.805 to 94.428 ms even though its
individually timed room and actor passes were effectively unchanged; it is
reported as run variation rather than credited to this CPU-lighting change.
This result does not predict stock Dreamcast timing.

Evidence:

- General-mask baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d163-r3e-compact-dynamic-room-lights-production`
- Production candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d167-r3f-compact-actor-light-lists-production`
- Packed-color verification:
  `C:\Flycast-Evidence\re4-dreamcast\d166-r3f-actor-light-packed-verify-corrected`
- Production ELF SHA-256:
  `25dc86d411cc7f4444da9fc160b54f0d51f998e636621431a863fc80e15d7c84`

## Acceptance boundary

This closes redundant light-mask scanning in the current source-selected actor
lighting path. It does not establish original-game selected-light traces,
source-authored animated normals, 30 fps, physical-hardware timing, or complete
source material behavior. The remaining median costs are about 72.6 ms for
both room passes, 16.7 ms for opaque actors, 15.9 ms for actor lighting, 9.7 ms
for actor normal construction, and 5.2 ms for actor pose projection.
