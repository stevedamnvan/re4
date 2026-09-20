# R3t room packets from cache entries checkpoint

Date: 2026-09-20

Decision: **accepted.** The direct-strip room path now writes PVR vertex
packets straight from the room vertex cache entries instead of copying each
52-byte `RenderVertex` into a strip scratch buffer first, and the packed vertex
colour is computed once per cache fill rather than once per emitted record.
Against R3r over matched simulation ticks 165-1194, CPU frame p50 falls from
74.139 ms to 73.247 ms and p95 from 74.238 ms to 73.378 ms. Nothing drawn
changes.

## Change

`RoomVertexCacheEntry` gains a packed `argb` word, filled by `shade_color()` at
the same time as the transformed vertex. `cached_room_entry()` returns the entry;
`cached_room_vertex()` is now a thin wrapper over it for the triangle and
fallback paths.

The direct-strip path in `submit_room_strips()` keeps only a pointer to each
entry and the vertex index it was looked up with. It stops at the first vertex
outside the depth window, exactly as before. Because the cache is direct-mapped,
a later lookup in the same strip can evict an earlier entry, so before reading
through the pointers the path re-checks every entry's generation, source index
and light selection. An evicted entry sends the strip to the existing fallback
path, which re-looks-up each vertex, and increments a new telemetry counter,
`room_strip_evictions`. The counter was zero at every sample in every capture.
The fallback path no longer reads from a scratch copy; it always re-looks-up.

The 768-entry scratch buffer of `RenderVertex` (39,936 bytes) is replaced by a
pointer array and an index array (6,144 bytes), so static main RAM falls by
33,792 bytes. Production telemetry grows to 376 bytes, version 12.

## Matched Flycast result

| p50 unless stated | R3r | R3t |
|---|---:|---:|
| CPU frame | 74.139 ms | **73.247 ms** |
| CPU frame p95 | 74.238 ms | 73.378 ms |
| CPU frame p99 | 76.701 ms | 75.838 ms |
| `submit_us` | 45.901 ms | 45.008 ms |
| opaque room | 29.244 ms | 28.243 ms |
| punch-through plus blended room | 3.053 ms | 3.163 ms |
| room index references | 15,050 | 15,270 |
| transformed and lit vertices | 10,156 | 10,156 |
| room strip evictions | n/a | 0 |
| free main RAM | 5,308,416 B | 5,332,992 B |

Zero simulation overruns and zero discarded simulation time. The reference
count is reported per sample and differs slightly between runs because the
captures do not land on identical frames; the miss count, which is per frame, is
identical.

## Visual result

Framebuffers were read from emulated VRAM at matched ticks against the R3r
reference in `d233-r3r-group-fix-visual`. Ticks 250 and 450 landed on the same
simulation tick in both runs and are **byte-identical**. The tick-700 capture
landed one tick later than the reference and differs by 1,104 pixels, all inside
Leon's silhouette, which is what one animation tick moves.

## Calibrated profile of the remaining room cost

Two gated `SUBMIT_PROFILE=1` builds bracket the room path with
`timer_ns_gettime64()`, whose measured cost is 337.5 ns per read in this
configuration; every bracket below subtracts two probe reads per bracket and,
for nested brackets, the probes of the brackets inside it. The profile builds
are slower than production because of the probes; only the subtracted figures
are meaningful. Room passes total 31.4 ms at p50 inside the whole
`submit_room_strips()` bracket.

| Component | per frame | per unit |
|---|---:|---:|
| cache hit lookups, direct-strip gather loop | 12.35 ms | 809 ns per reference, 15,270 |
| cache miss body: transform, light, colour pack | 8.49 ms | 836 ns per miss, 10,156 |
| strip loop residual outside the gather/verify/pack brackets | 7.58 ms | 2,242 ns per strip, 3,379 |
| packet write | 1.36 ms | 409 ns per direct strip |
| store-queue submission | 1.14 ms | 572 calls |
| batch and group traversal | 0.81 ms | 572 batches |
| eviction verify pass | 0.42 ms | 3,379 strips |
| per-strip sphere test | below probe resolution | 5,212 tests |

The components are attributions from nested brackets and sum to within 1 ms of
the whole-call bracket. The transform-and-light miss body is 836 ns, which
confirms the R3s finding that it is not the dominant term. The two largest terms
scale with the number of references and the number of strips, and the strips
are short: 8,208 triangles over 3,379 strips is 2.4 triangles per strip,
because one-metre cells split the source strips into batches of about seven
triangles. The next lever is therefore the package partition, not the kernel;
see [R3U_CELL_SIZE_RESWEEP_CHECKPOINT.md](R3U_CELL_SIZE_RESWEEP_CHECKPOINT.md).

## Retained evidence

- `d237-r3t-packet-from-cache` — accepted timing, ELF
  `ec841178108c67a1b607e2b7130091b33478e1abd6b8e55d0bb8b8986cc74c10`
- `d238-r3t-visual` — framebuffers at ticks 250, 450 and 700
- `d239-r3t-miss-profile` — miss-body and sphere-test brackets, ELF
  `49a0a286d31ffb8675a34967561e1d49c1afc8ddebdbf2c629f27eee4d573207`
- `d240-r3t-loop-profile` — gather/verify/pack and whole-call brackets, ELF
  `792e2a02e4e497dd483d96f0010602161fb383ee41a3c385a67c74522bc43c1a`

The profile brackets are retained in `room/main.cpp` under
`RE4DC_SUBMIT_PROFILE` and are compiled out of production; the production
translation unit is unchanged by them. No R3t manual smoke was run on its own;
the R3u manual smoke covers the same code.

## Limits

Flycast does not model the SH-4 data cache, so the profile is an
instruction-volume attribution. The 809 ns hit lookup includes the loop
overhead of the gather loop and the depth test, not only the hash and compare.
Physical Dreamcast timing remains pending.
