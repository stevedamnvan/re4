# r100 R3e compact dynamic room-light checkpoint

Recorded 2026-09-20 after the validated room-normal checkpoint. The static
room-light cache still needs the two source-authored camera-relative lights on
every visible unique vertex. The previous implementation sent that two-light
mask through the general nine-light point/spot/directional evaluator, rejecting
seven entries and rebuilding unused setup on every cache miss.

The new room-only path evaluates source light 1 followed by source light 5
directly. Both are type-5 view-space directional lights in r100 cut 0. It keeps
the source selection bits, prepared camera-relative directions, intensity,
color, diffuse clamp, accumulation order, final clamp, and packed-color path.
Initialization enables the specialization only when the recovered dynamic mask
is exactly `{1, 5}`; any other light set retains the general evaluator. Actors
continue to use their general source-selected lists.

## Correctness comparison

A verification ELF ran the specialized and general calculations for every
visible room cache miss, then compared their final packed 8-bit colors. Across
38 sampled frames it reported zero mismatches. The dual calculation and its
temporary telemetry override are absent from the production build.

Room transforms, light-evaluation count, cache behavior, submitted strip count,
geometry, textures, camera, source group selection, and actor work are unchanged.
The production capture remains visually coherent; autoplay animation phase is
not used as a pixel-identity reference because the faster build reaches render
snapshots at different wall-clock times.

## Matched Flycast result

Medians cover simulation ticks 220 through 474.

| Measure | General nine-light loop | Compact dynamic room list | Change |
|---|---:|---:|---:|
| Outer frame work | 152.774 ms | 130.046 ms | -22.728 ms (-14.9%) |
| Total render work | 152.390 ms | 129.664 ms | -22.726 ms (-14.9%) |
| Submission interval | 116.996 ms | 91.805 ms | -25.191 ms (-21.5%) |
| Opaque room pass | 59.243 ms | 44.933 ms | -14.310 ms (-24.2%) |
| Translucent room pass | 35.965 ms | 27.552 ms | -8.413 ms (-23.4%) |
| Actor lighting | 20.470 ms | 20.469 ms | unchanged |
| Room transforms/light evaluations | 25,417 | 25,417 | unchanged |
| Room index references | 28,398 | 28,398 | unchanged |

The matched Flycast rate moves from about 6.6 to 7.7 frames per second. This
result shows that general light dispatch was a major room CPU cost; it does not
predict stock Dreamcast timing.

Evidence:

- General-loop baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d160-r3d-validated-unit-room-normals-autoplay`
- Production candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d163-r3e-compact-dynamic-room-lights-production`
- Packed-color verification:
  `C:\Flycast-Evidence\re4-dreamcast\d162-r3e-dynamic-light-packed-color-verify`
- Production ELF SHA-256:
  `05ad127cc7bb99ee3287a354c95c0004079136bb695c94d674779084318f8eab`

## Acceptance boundary

This is a source-specific specialization with a verified general fallback. It
does not prove original-game selected-light traces, 30 fps, physical-hardware
timing, or complete source material behavior. The remaining median costs are
about 72.5 ms for both room passes, 20.5 ms for actor lighting, 16.7 ms for
opaque actors, 9.7 ms for actor normal construction, and 5.2 ms for actor pose
projection.
