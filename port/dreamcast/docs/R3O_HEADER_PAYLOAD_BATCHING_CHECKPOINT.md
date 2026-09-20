# R3o header/payload batching checkpoint

Date: 2026-09-20

Decision: **keep as a small equivalent optimization**.

The immediate PVR path previously submitted each polygon header separately from
its first vertex payload. This checkpoint copies the 32-byte header into the
front of the existing aligned command buffer, preserving the exact TA command
order while issuing one store-queue submission for the initial header/payload
pair. HUD header/quads use the same representation. No geometry, material,
lighting, alpha, clipping, simulation, or asset data changes.

## Exact candidate

- base commit: `1e15ee54b937273e56b419b8e3ae8f9cd2e86930`
- candidate autoplay ELF SHA-256:
  `191676ca573aaaec9aed99bb33c88fca3102b1d90344a8e7c4020455bf1dfbdc`
- Flycast evidence:
  `C:\Flycast-Evidence\re4-dreamcast\d209-header-payload-batching-candidate`

## Matched result

Two candidate runs were compared with R3n over ticks 165-1194.

| Metric | R3n | R3o run 1 | R3o run 2 |
|---|---:|---:|---:|
| immediate PVR calls p50 | 1,219 | 617 | 617 |
| submitted bytes p50 | 1,071,840 | 1,071,840 | 1,071,840 |
| TA registration p50 | 58.854 ms | 58.731 ms | 58.731 ms |
| CPU frame p50 | 87.739 ms | 87.615 ms | 87.615 ms |
| render total p50 | 87.464 ms | 87.342 ms | 87.342 ms |
| PVR render p50 | 7.502 ms | 7.502 ms | 7.502 ms |

The 49.4% call-count reduction saves only about 0.12 ms at the median. Tail
frame time is statistically unchanged across these emulator traces. The result
is retained because it uses the existing command buffer, adds no allocation,
preserves byte count and command order, and produces the same small median
reduction in both runs. It is not evidence that further call-count work will
close the real-time gap.

Both candidates keep 327 visible groups, 9,155 room triangles, 11,900 actor
triangles, zero simulation overruns, and zero discarded simulation time at the
settled view. The 12/20/28-second captures retain the accepted room, complete
characters, source lighting, transparency, HUD, and camera.

## Consequence

Per-call setup is not a major remaining bottleneck. The approximately 58.7 ms
registration interval mostly contains generation and transfer of 1.07 MiB of
dynamic commands plus the CPU preparation wrapped around it. The next task must
measure or reduce that work itself, or target the independent 18.96 ms actor
lighting stage. A DMA buffer should not be adopted from this result alone.
