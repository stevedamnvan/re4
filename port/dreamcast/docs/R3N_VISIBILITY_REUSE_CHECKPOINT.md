# R3n room visibility reuse checkpoint

Date: 2026-09-20

Decision: **keep**.

This checkpoint removes repeated room eligibility and light-selection work
without changing the room, camera, lighting result, material classification, or
draw order. The renderer now builds one conservative visible source-child list
per render snapshot. Each record carries the original group index, source cull
mode, and source-selected light mask. Opaque, punch-through, and blended passes
consume that list in the original ascending group order.

The implementation does not change gameplay updates for invisible objects. It
only avoids repeating render preparation for the same camera snapshot.

## Exact candidate

- base commit: `ebb99579c20d7b7b8a331c10787c1f88d82664b4`
- candidate autoplay ELF SHA-256:
  `e44e19b1e98fd4bac496e81007d791a7a532f65afb6495c2647dff73e9bf2140`
- telemetry ABI: version 9, 344 bytes
- source/toolchain/emulator identities: unchanged from
  [REALTIME_PATH.md](REALTIME_PATH.md)
- Flycast evidence:
  `C:\Flycast-Evidence\re4-dreamcast\d208-visibility-reuse-candidate`

## Matched result

The comparison below uses simulation ticks 165-1198 from both the kept R3m
trace and this candidate. Both runs contain 342 sampled frames over that window.

| Metric | R3m | R3n | Change |
|---|---:|---:|---:|
| CPU frame p50 | 92.23 ms | 87.74 ms | -4.49 ms |
| CPU frame p95 | 94.71 ms | 89.89 ms | -4.83 ms |
| CPU frame p99 | 94.80 ms | 90.30 ms | -4.50 ms |
| render total p50 | 91.92 ms | 87.46 ms | -4.45 ms |
| TA registration p50 | 65.29 ms | 58.85 ms | -6.44 ms |
| PVR render p50 | 7.50 ms | 7.50 ms | unchanged |
| opaque room stage p50 | 29.19 ms | 27.24 ms | -1.95 ms |
| alpha room stage p50 | 22.50 ms | 18.03 ms | -4.47 ms |
| explicit visibility stage p50 | included repeatedly | 1.96 ms | one pass |

The net CPU-frame reduction is 4.9%. PVR ready-to-ready presentation remains
quantized by the slow workload: 83.41/100.10/102.60 ms at p50/p95/p99. The
candidate still misses the 33.33 ms target by 54.4 ms at the median.

At the settled view, both traces report 327 visible groups, 9,155 room
triangles, and 11,900 actor triangles. The candidate evaluates 327 room light
selections once per frame. It submits approximately 1,219 immediate PVR calls
and 1,071,840 bytes at the median. Those new counts make packet/state batching
the next bounded target.

Both traces report zero simulation overruns and zero discarded simulation
time. The candidate post-load snapshot reports 5,668,864 bytes of main-RAM
break-to-stack headroom, 159,268 heap bytes used, 110,504 heap bytes free,
1,521,128 PVR bytes free, and the same 1,378,336-byte AICA diagnostic. These are
steady-state observations, not high-water measurements.

## Fidelity check

All package identities and triangle streams are unchanged. The visible list is
generated in source-group order and each pass preserves its previous iteration
order, including surviving blended strips. Captures at 12, 20, and 28 seconds
retain the accepted room, complete characters, source lighting, alpha, HUD, and
camera. A host-time screenshot comparison has small temporal/dither differences
because the faster build reaches different animation frames; it is not claimed
as a matched-tick pixel identity test.

## Next measured question

The renderer emits about 1.07 MiB through roughly 1,219 immediate calls per
settled frame. The next candidate should preserve the exact command stream while
combining each polygon header with its first vertex payload, then measure call
count, registration time, and the same fidelity counters. This tests command
granularity before introducing KOS DMA buffers or changing geometry.
