# r100 R3h source normal-palette checkpoint

Recorded 2026-09-20 after the packed actor-color checkpoint. The previous
runtime reconstructed actor normals from the already deformed triangle mesh on
every rendered frame. That discarded two useful pieces of the original BIN
representation: authored normal vectors and the weight-palette identity stored
with each normal.

Character package version 5 now preserves both. Compressed BIN normals are
expanded exactly from signed Q6 to Q14; uncompressed BIN normals retain their
source Q14 values. Each source normal references its original weight palette.
For every sampled pose, the converter stores each palette's blended 3x3 linear
matrix in signed Q15. The runtime transforms each source normal through the
current and next source-derived palettes, applies the existing pose blend and
actor yaw, then feeds the result to the existing selected-light evaluator.

The path follows the source renderer's reuse boundary: prepare a blended matrix
once, then reuse it for every normal that references that weight combination.
The old triangle-normal path remains available for version-4 and clustered
engineering packages. The loader normalizes version-4 headers into the current
view rather than invalidating private historical assets.

## Recovered representation

| Actor | Normal work items | Source normals | Palette matrices per pose | Sampled poses |
|---|---:|---:|---:|---:|
| Leon assembly | 6,535 | 5,860 | 394 | 108 |
| Ganado assembly | 1,900 | 1,818 | 112 | 282 |

The v5 character packages add 1,412,784 bytes in total because baked position
frames are still present alongside the normal palettes. Production main-RAM
headroom falls from 2,441,216 to 1,028,096 bytes. This is acceptable for the
bounded experiment but is not the final residency design. Replacing baked
positions with the same source palette architecture is now the highest-value
memory task.

The reproducible `characters-r100` host target emits these v5 packages and the
same 128-pixel actor texture packages used by the accepted r100 presentation.
The pre-v5 private packages were retained under
`*-v4-before-source-normals.re4chr` names.

## Correctness evidence

The converter compares every quantized palette against its unquantized
source-derived matrix for every source normal and sampled pose:

| Actor | Maximum matrix-element error | Maximum normal-direction error |
|---|---:|---:|
| Leon | 0.000015260 | 0.005088 degrees |
| Ganado | 0.000015260 | 0.001964 degrees |

The production packages are:

- Leon SHA-256:
  `130b67a894eb2efdedc3d283515dfe0c204896e103e07b51d748ef4eb5d50db7`
- Ganado SHA-256:
  `577684669c5ec845b8983d19306859278e349236fd6db78568b3fd20a645569f`

The complete quantized position-frame payloads are byte-identical to the
preserved v4 packages. Their SHA-256 values are
`e62e42727b7101875a4db268cd4f41ecc0d09b81b2d6edb2bb17c83a211c5c47`
for Leon and
`0f22a157e35c4f1a51e1554a5329bffdbf90d4813c0ed7a8cdf8b6f1f4186091`
for the Ganado. The converter refactor therefore changes normal handling
without moving the accepted actor geometry.

A Flycast comparison at nearby autoplay ticks 278 and 280 shows coherent actors
and the expected authored-normal shading change, especially across Leon's back
and clothing seams. It is useful visual review, not a same-tick pixel proof or
an original GameCube comparison.

Comparison image:
`C:\Flycast-Evidence\re4-dreamcast\r3h-normal-comparison.png`.

## Controlled Flycast result

The baseline uses equal-size v5 packages with only the source-normal counts
disabled, forcing the old triangle reconstruction while preserving executable
layout and memory pressure. Medians cover simulation ticks 220 through 474.

| Measure | Triangle-rebuilt normals | Source normal palettes | Change |
|---|---:|---:|---:|
| Outer frame work | 123.363 ms | 120.704 ms | -2.659 ms (-2.2%) |
| Total render work | 123.039 ms | 120.376 ms | -2.663 ms (-2.2%) |
| Actor normal preparation | 9.726 ms | 7.003 ms | -2.723 ms (-28.0%) |
| Actor lighting and color preparation | 19.205 ms | 19.237 ms | +0.032 ms |
| Opaque actor pass | 12.049 ms | 12.051 ms | +0.002 ms |
| Translucent actor and HUD pass | 1.735 ms | 1.735 ms | unchanged |
| Free main RAM | 1,028,096 bytes | 1,028,096 bytes | unchanged |

The standard production build repeats the result at 120.706 ms, approximately
8.3 Flycast frames per second. A 30-second capture reached simulation tick 931
with no reported simulation overruns or dropped ticks. It remained in the
autoplay death-wait phase, so this capture is not full-encounter acceptance.

Evidence:

- Equal-size triangle-normal baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d173-r3h-equal-size-triangle-normal-baseline`
- Integrated source-normal candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d172-r3h-source-normal-palette-integration`
- Standard production capture:
  `C:\Flycast-Evidence\re4-dreamcast\d174-r3h-source-normal-palette-production`
- Version-4 package compatibility smoke:
  `C:\Flycast-Evidence\re4-dreamcast\d175-r3h-v4-package-compatibility-smoke`
- Production ELF SHA-256:
  `bd25852834fe7803c5b1c34eed648f19a95cd73776be345cf8dab9e990846e26`

## Acceptance boundary

This replaces an invented normal-reconstruction step with authored BIN normals
and source weight-palette reuse. It does not yet prove an exact original-game
lighting image, integrate the original live motion evaluator, reclaim baked
position-frame memory, reach 30 fps, establish responsive manual control, or
measure physical Dreamcast timing. Package v5 currently reduces RAM headroom;
the next actor representation must remove the redundant baked positions rather
than adding another parallel animation payload.
