# R3u cell-size re-sweep checkpoint

Date: 2026-09-20

Decision: **accepted; the r100 production room now uses four-metre opaque child
cells.** R3k chose one-metre cells when the group test was the only culling in
the room path and that test was too tight. R3r added per-strip culling and
corrected the projection bias, which changes what the cell size buys. Re-sweeping
2 m, 4 m and 8 m with the current converter against the R3t one-metre baseline
gives a 1.878 ms frame reduction at 4 m, a 405,504-byte main-RAM gain, and
byte-identical room pixels. Nothing else changed: no code, geometry, texture,
light rule, camera, alpha order, or resolution.

## Why re-sweep

The R3t profile showed the two largest room terms scale with references and
strips. One-metre cells cut the source strips into 3,570 batches of about seven
triangles, which is why the frame draws 8,208 triangles as 3,379 strips. Coarser
cells make longer strips and fewer batches and groups, at the cost of coarser
group culling. Before R3r that trade lost, because the group test was the only
cull; after R3r the strip test catches most of what the group test misses, and
the group test was also rejecting on-screen groups.

## Packages

All four were regenerated with `make -f Makefile.host room-r100-production
R100_PRODUCTION_CELL_SIZE=N` from the same source OBJ, SMX and converter
options. The regenerated one-metre package is byte-identical to the accepted
R3k package, which confirms the sweep differs only in cell size. Every package
keeps all 40,419 vertices and 30,895 triangles and leaves the 14 alpha-bearing
materials unpartitioned in source order.

| Cell | Groups | Batches | Strips | Strip vertices | Package bytes |
|---:|---:|---:|---:|---:|---:|
| 1 m | 3,113 | 3,570 | 15,066 | 61,027 | 2,667,056 |
| 2 m | 1,870 | 2,303 | 13,612 | 58,119 | 2,394,520 |
| 4 m | 1,093 | 1,421 | 12,625 | 56,145 | 2,220,388 |
| 8 m | 652 | 854 | 11,902 | 54,699 | 2,117,092 |

Accepted 4 m package SHA-256
`6b2bbf8f18a254d18abb773e511889798c9df0f5ad7d1337c49ad0104f05ac28`.

## Matched Flycast result

Simulation ticks 165-1194, same autoplay route, pinned build and configuration,
R3t code in every column.

| p50 unless stated | 1 m (R3t) | 2 m | **4 m** | 8 m |
|---|---:|---:|---:|---:|
| CPU frame | 73.247 ms | 71.889 ms | **71.369 ms** | 71.321 ms |
| CPU frame p95 | 73.378 ms | 72.039 ms | 71.463 ms | 71.440 ms |
| CPU frame p99 | 75.838 ms | 74.482 ms | 73.929 ms | 73.886 ms |
| `submit_us` | 45.008 ms | 44.476 ms | 44.413 ms | 44.667 ms |
| opaque room | 28.243 ms | 27.817 ms | 27.810 ms | 28.102 ms |
| punch-through plus blended room | 3.163 ms | 3.057 ms | 3.000 ms | 2.961 ms |
| room visibility and light selection | 2.089 ms | 1.264 ms | 0.806 ms | 0.505 ms |
| visible groups | 362 | 215 | 142 | 90 |
| room triangles | 8,208 | 8,266 | 8,315 | 8,359 |
| room index references | 15,270 | 14,975 | 14,871 | 14,841 |
| transformed and lit vertices | 10,156 | 10,284 | 10,404 | 10,524 |
| direct strips / fallbacks | 3,325 / 54 | 3,098 / 73 | 2,963 / 88 | 2,867 / 97 |
| strips culled | 1,833 | 2,147 | 2,437 | 3,059 |
| immediate PVR calls | 681 | 484 | 370 | 299 |
| submitted bytes | 1,002,656 | 983,680 | 972,928 | 965,984 |
| free main RAM | 5,332,992 B | 5,619,712 B | 5,738,496 B | 5,849,088 B |

Actor stages are identical across the columns to the microsecond. Zero
simulation overruns and zero discarded simulation time in all four runs.

4 m and 8 m are within 48 us of each other at p50. 4 m is taken because it has
the lowest opaque-room time and p95, submits fewer triangles and bytes, and is
the smaller step from the accepted partition; 8 m's extra 110,592 bytes of RAM
does not buy frame time. Most of the gain is the visibility pass (2.089 ms to
0.806 ms, 362 to 142 groups) plus fewer references and records; the strip loop
itself did not shorten much, because the strips are still short: 8,315
triangles over 3,051 strips is 2.7 per strip. The converter's strip split, not
only the cell size, now bounds this term.

## Visual result

Framebuffers were read from emulated VRAM against the R3t reference in
`d238-r3t-visual`. At tick 250 both runs landed on the same simulation tick;
the 14,813 differing pixels all lie inside Leon's bounding box (346,242)-(519,420)
and are his render-time animation phase, which depends on the frame interval.
Ticks 450 and 700 landed one and two ticks later than the reference and differ
only inside Leon's box, (298,194)-(432,420), for the same reason. **No pixel
outside the actor differs at any of the three ticks**, so the room, its
lighting and its alpha order are unchanged by the repartition. The room
light-selection change is exercised by this: light selection is per group, and
1,093 groups select the same lights the 3,113 groups did on this route.

## Manual build

The manual ELF was built from the same tree without the autoplay flag and
smoked in `d245-r3u-manual-smoke`: it reached simulation tick 2,617, sampled
input 8,720 times with a 12.485 ms maximum gap, and reported zero queue drops,
simulation overruns or discarded simulation time. Post-load free main RAM was
5,738,496 bytes in both builds.

## Retained evidence

- `d241-r3u-cell-2` — ELF
  `91e873f98cc92196333ab0b00814668ce1ba006ec4e88217f0329b52f65ecc50`
- `d242-r3u-cell-4` — accepted timing, ELF
  `a7d6d00093a640ee61e385b07af4bfc4fc25f98ca751164e1fc50d2d4505ebb9`
- `d243-r3u-cell-8` — ELF
  `f3de09a6ce0d5327f95943e031ff21d0b41747c74aa15aaab1387b541b39dc3a`
- `d244-r3u-cell-4-visual` — framebuffers and `compare-vs-d238.png`
- `d245-r3u-manual-smoke` — manual build smoke

Accepted autoplay ELF SHA-256
`a7d6d00093a640ee61e385b07af4bfc4fc25f98ca751164e1fc50d2d4505ebb9`, rebuilt
byte for byte by `make -C port/dreamcast/room r100-autoplay` with the new
defaults. Accepted manual ELF SHA-256
`ba897fe1e27dd9fd7365597400a7e5feb504f66a088346033c29082cf7fb24d8`.

## Limits

These are Flycast measurements of the autoplay route and one manual smoke. The
pixel check covers three near-static ticks; the moving-camera guarantee rests on
the fact that no cull test, geometry or order changed, only the grouping.
Coarser groups mean each visible group carries more off-screen strips, so a
camera that looks along a long wall may shift cost from the group test to the
strip test; that is bounded by the strip test, which R3r audited. Physical
Dreamcast timing remains pending.
