# R3x slim room slots checkpoint

Date: 2026-09-20

Decision: **accepted.** The batch-local room slot is now a 32-byte record
holding exactly the seven words the direct-strip packet needs, filled by the
same transform and lighting arithmetic, and the direct-strip path resolves,
fills and packs each vertex in one pass. Against R3w over matched simulation
ticks 165-1194, CPU frame p50 falls from 64.758 ms to 61.229 ms and p95 from
64.809 ms to 61.289 ms. Every counter is identical, no room pixel changes,
and static main RAM falls by 32,768 bytes.

## Why

Under the Flycast cost model measured in R3w, loads and stores are the price.
The R3v slot fill wrote a full 68-byte `RoomVertexCacheEntry` (17 words,
including the world position and the three lighting floats that only the
fallback and triangle paths read), the gather loop stored a pointer per
vertex, and a second loop read the pointer and seven words back to build the
packet. Per reference the path also performed three read-modify-write stat
increments.

## Change

`RoomBatchSlot` is `{serial, x, y, z, u, v, depth, argb}`. The lighting of a
room vertex is factored into `light_room_vertex()`, used unchanged by both
`fill_room_entry()` for the hashed cache and the new `fill_room_slot()`, so
the two paths produce the same bits. In `submit_room_strips()` the slot path
flushes if the strip cannot fit, then for each vertex resolves the slot,
fills it on a serial miss, tests the depth window and writes the packet
directly into the submit buffer. A vertex outside the window rewinds the
submit count to the strip start and takes the existing fallback path; slots
filled on the way stay valid for the batch. Reference, hit, miss, transform
and light-evaluation counts are accumulated in registers and added to the
frame stats once per strip, so the telemetry values are unchanged.

The hashed path, used by batches larger than the slot table, by the fallback
strips and by the triangle path, is untouched.

## Matched Flycast result

| p50 unless stated | R3w | R3x |
|---|---:|---:|
| CPU frame | 64.758 ms | **61.229 ms** |
| CPU frame p95 | 64.809 ms | 61.289 ms |
| CPU frame p99 | 67.294 ms | 63.781 ms |
| `submit_us` | 41.832 ms | 38.319 ms |
| opaque room | 25.320 ms | 21.981 ms |
| punch-through plus blended room | 2.908 ms | 2.735 ms |
| actor lighting / opaque actor draw | 14.189 / 11.789 ms | 14.189 / 11.789 ms |
| room index references / hits / misses | 14,871 / 3,863 / 11,008 | 14,871 / 3,863 / 11,008 |
| direct strips / fallbacks | 2,963 / 88 | 2,963 / 88 |
| immediate PVR calls / bytes | 370 / 972,928 | 370 / 972,928 |
| free main RAM | 5,324,800 B | 5,357,568 B |

Zero simulation overruns and zero discarded simulation time. The 3.529 ms
gain is 237 ns per reference, close to the static estimate of ten fewer
stores and four fewer read-modify-writes per fill plus the removed second
pass.

## Visual result

Framebuffers were read from emulated VRAM against the R3v reference in
`d248-r3v-visual`. Every differing pixel at ticks 250, 450 and 700 lies inside
Leon's bounding box, (343,244)-(517,420) and (298,194)-(431,420), and is his
render-time animation phase; tick 450 landed on the same simulation tick in
both runs and differs by 337 such pixels. **No pixel outside the actor
differs.**

## Manual build

`d257-r3x-manual-smoke`: the manual ELF reached simulation tick 2,616,
sampled input 8,715 times, and reported zero queue drops, simulation overruns
or discarded simulation time. Its maximum input sample gap was 19.959 ms, the
same single long sample the R3v smoke showed; the queue absorbed it.

## Retained evidence

- `d255-r3x-slim-slots` — accepted timing, ELF
  `4ca5ab47734d936d5ac6e95e7cca48e2ce01c1720e0676da6a354601ddf42c97`
- `d256-r3x-visual` — framebuffers at ticks 250, 450 and 700
- `d257-r3x-manual-smoke` — manual build smoke, ELF
  `73793fb4c8e04e9153a35fed433ffe2e40c16a960b4c21b8801d473543e8e957`

## Limits

Flycast measurements of the autoplay route and one manual smoke. The gain is
a memory-instruction reduction, which hardware also rewards, by less. The
profile build's `pack` bracket no longer covers the slot path, which packs
inside the gather bracket. Physical Dreamcast timing remains pending.
