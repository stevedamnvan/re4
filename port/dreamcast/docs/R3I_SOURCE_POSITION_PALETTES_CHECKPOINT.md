# r100 R3i source position-palette checkpoint

Recorded 2026-09-20 after the source normal-palette checkpoint. Character
package v5 retained a complete quantized position for every source vertex in
every sampled pose. That made the renderer cheap to implement, but duplicated
the original BIN positions and the same source weight-palette matrices already
needed for authored normals.

Character package version 6 now stores each source position once with its
original palette identity. Every sampled pose stores one Q15 3x3 linear matrix
and float translation per source weight combination. The runtime interpolates
each palette matrix once and reuses the prepared result for all positions and
normals that reference it. This follows the source `MakeWeightPalette` boundary
instead of independently blending bones for every vertex. Only the small
gameplay marker tracks remain as baked quantized positions.

The v4 and v5 readers remain available for private historical packages. The
r100 production build requires v6 packages; clustered engineering packages
continue to use the triangle-normal and baked-position fallback.

## Recovered representation

| Actor | Source positions | Gameplay markers | Palette matrices per pose | Sampled poses |
|---|---:|---:|---:|---:|
| Leon assembly | 5,731 | 14 | 394 | 108 |
| Ganado assembly | 1,667 | 23 | 112 | 282 |

The two v6 packages total 2,887,976 bytes, down from 8,265,940 bytes for v5.
This removes 5,377,964 package bytes. Runtime palette scratch consumes about
30 KiB; measured production main-RAM headroom rises from 1,028,096 to
6,369,280 bytes, a gain of 5,341,184 bytes.

The reproducible `characters-r100` target emits v6 packages. The accepted v5
private packages are retained under `*-v5-before-source-positions.re4chr`
names.

## Correctness evidence

The converter rebuilds the complete legacy position-frame stream as a
validation oracle without storing it in v6. Its SHA-256 is byte-identical to
the v5 payload for both actors:

- Leon: `e62e42727b7101875a4db268cd4f41ecc0d09b81b2d6edb2bb17c83a211c5c47`
- Ganado: `0f22a157e35c4f1a51e1554a5329bffdbf90d4813c0ed7a8cdf8b6f1f4186091`

The marker-only payloads extracted from v5 are also byte-identical to v6:

- Leon: `0efc18c0e58ebb33dbe6e72c743d6232db8a018a476c08250a0c80238eb33a6a`
- Ganado: `d68dd5fb0aa53bae8eace410383ac185c1b42b9fb45a6b74042d2b6c8d736c7b`

| Actor | Maximum transformed-position error | Exact legacy quantized positions | Maximum normal-direction error |
|---|---:|---:|---:|
| Leon | 0.054668 mm | 468,919 / 618,948 | 0.005088 degrees |
| Ganado | 0.049769 mm | 364,482 / 470,094 | 0.001964 degrees |

The remaining position differences are bounded Q15 matrix quantization, below
one quarter of the legacy 0.25 mm position quantum. The gameplay sampler reads
v6 marker tracks directly and can also transform a source position through its
pose palette. This is required for gun rays, hit capsules, and axe sweeps; an
early render-only candidate exposed and corrected that integration gap.

Production packages:

- Leon SHA-256:
  `bfabcd1746cbe490159d957a3dcaebf09f2482f701ecb8471d14caa5e328c1b8`
- Ganado SHA-256:
  `0fa2e9d46c7b3a5460f1c9724203791cef648096229ae5c17f5e9f3099bd9dd7`

A Flycast capture at the source camera shows coherent source geometry,
attachments, animation, authored-normal shading, and HUD after the position
replacement:
`C:\Flycast-Evidence\re4-dreamcast\d178-r3i-v6-marker-gameplay-fix\source-position-palette-frame.png`.
This is target-side visual review, not a same-tick original GameCube pixel
comparison.

## Matched Flycast result

The v5 production reference and v6 candidate use the same dead-enemy,
handgun-ready state over simulation ticks 273 through 348. Room visibility,
transformed room vertices, triangle counts, camera, actor placement, and combat
state match in the compared samples.

| Measure | v5 baked positions | v6 source position palettes | Change |
|---|---:|---:|---:|
| Outer frame work | 118.258 ms | 113.749 ms | -4.509 ms (-3.8%) |
| Total render work | 117.879 ms | 113.414 ms | -4.465 ms (-3.8%) |
| Actor position preparation | 5.179 ms | 5.863 ms | +0.684 ms |
| Actor normal preparation | 7.003 ms | 1.852 ms | -5.151 ms (-73.6%) |
| Actor lighting and color preparation | 19.236 ms | 19.236 ms | unchanged |
| Opaque room pass | 45.005 ms | 45.005 ms | unchanged |
| Opaque actor pass | 12.052 ms | 12.050 ms | -0.002 ms |
| Translucent room pass | 27.633 ms | 27.632 ms | -0.001 ms |
| Free main RAM | 1,028,096 bytes | 6,369,280 bytes | +5,341,184 bytes |

The candidate is approximately 8.8 Flycast frames per second in this matched
state. The 32-second production capture reached simulation tick 904, completed
the scripted kill, held the source ready camera, and exercised the tick-900
manual-retry path. Its median was 119.005 ms across the whole route, with a
121.516 ms 95th percentile. It reported no simulation overrun, dropped tick,
dropped simulation time, or input-queue drop.
The first integration run that left combat on the old accessor is retained as
negative evidence rather than counted as acceptance.

Evidence:

- Initial render-only candidate and negative gameplay trace:
  `C:\Flycast-Evidence\re4-dreamcast\d177-r3i-prepared-position-palette`
- Corrected gameplay and matched performance:
  `C:\Flycast-Evidence\re4-dreamcast\d178-r3i-v6-marker-gameplay-fix`
- Production 30-second run:
  `C:\Flycast-Evidence\re4-dreamcast\d179-r3i-source-position-palette-production-30s`
- Version-4 package compatibility smoke:
  `C:\Flycast-Evidence\re4-dreamcast\d180-r3i-v4-loader-compatibility-smoke`
- Production ELF SHA-256:
  `f2aa58d5bdfc5d71fdb9255661015960fcb1f11400a0586b810f7417c4185474`

## Acceptance boundary

This removes redundant baked mesh poses, preserves the source position and
weight-palette relationships, restores the marker consumers used by combat,
improves Flycast frame time, and recovers enough main RAM for subsequent
runtime work. It does not integrate the original live motion evaluator, prove
source animation-state or RNG parity, reach 30 fps, establish responsive manual
control, provide a same-state original-game image comparison, or measure a
physical Dreamcast.
