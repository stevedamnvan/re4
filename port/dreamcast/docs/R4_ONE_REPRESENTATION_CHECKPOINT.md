# One primitive representation per batch

Status: **accepted.** r100's room package loses 228,524 bytes, r101's 791,432,
and the runtime renders the identical image.

## The duplication

`build_package()` wrote every batch twice: an ordered triangle index range, and
a strip set built by `stripify_triangles()` from that same range. Both were
resident for the room's life.

`strip_triangle_order_preserved()` already proved, per batch, whether the strips
reproduce the source triangle order and winding, and recorded the answer as
`BATCH_STRIP_ORDER_PRESERVED`. Where that holds, the triangle range carries
nothing the strips do not.

Measured on the built packages before changing anything: the strips expand to
the same canonical triangle multiset — same triangles, same winding — for
**every** batch in both rooms, 1421/1421 and 3811/3811. What the flag adds on
top is that the *order* matches too.

| | r100 | r101 |
|---|---:|---:|
| package | 2,220,388 | 8,894,704 |
| vertices | 1,293,408 (58.3%) | 5,665,024 (63.7%) |
| triangle indices | 370,740 (16.7%) | 1,629,756 (18.3%) |
| strip descriptors + indices | 325,580 (14.7%) | 1,409,316 (15.8%) |
| groups / batches / materials | 147,468 | 190,484 |
| source groups | 83,068 | 0 |
| batches order-preserved | 1,246 of 1,421 (87.7%) | 2,776 of 3,811 (72.8%) |
| triangle bytes in those batches | **228,528** | **791,436** |

## What changed

Package **version 3**. A batch gains `kBatchTrianglesResident`; the header gains
`triangle_count`, because `index_count` no longer counts the room's triangles.
An order-preserved batch stores strips alone, with `first_index` and
`index_count` zeroed so nothing can read a stale range. A batch without the
proof keeps its authoritative ordered triangles beside the strips the opaque and
punch-through passes draw it with. `--keep-triangle-indices` and
`room-r100-production-compat` still produce the accepted layout for comparison.

Consumers, all checked rather than assumed:

* **static lighting** walked the triangle range to collect the set of vertices
  each group touches. It never read order or winding, so it walks whichever
  table the batch has; strips reference exactly the same vertices, which is the
  1421/1421 and 3811/3811 measurement above. The per-vertex body became a
  lambda so both walks share it.
* **the translucent pass** is the one pass where alpha order is source triangle
  order, so it already refused strips without the proof. It now checks that a
  batch it is about to read triangles from actually has them, and counts it
  rather than rendering a hole if that ever fails. It did not fail.
* **opaque and punch-through** already drew from strips whenever a batch had
  them, without consulting the flag. Unchanged — and worth recording, because
  it means those two passes were never a reason to keep a triangle range.
* **bounds** and **batch-local preparation** already walked strips only.
  Unchanged.
* **validation** gained the flag-consistency rules, and now cross-checks that
  the batches' triangles add up to the header's `triangle_count`. The strip
  table is validated before the batch loop reads through it.

Nothing reconstructs a triangle table at load time and nothing moved into
`.bss`. The only reconstruction is the one that already existed: a strip that
cannot be submitted directly is re-walked within `submit_room_strips` from the
strip itself, into the existing bounded scratch.

## Measured, r100

Same host, same emulator, 240–300 s captures.

| | both representations | one representation |
|---|---:|---:|
| room package | 2,220,388 | 1,991,864 |
| arena high water = steady state | 3,572,256 | 3,343,712 |
| arena reservation (`.bss`) | 3,670,016 | 3,440,640 |
| main RAM free | 7,438,336 | **7,667,712** |
| `.bss` | 5,807,508 | 5,578,132 |
| resident image | 8,818,021 | 8,589,889 |
| VRAM free after textures | 3,030,856 | 3,030,856 |
| heap used | 139,780 | 139,780 |
| frame `frame_us` p50 | 48,886 | 48,879 |
| loads / retirements | 22 / 37 | 18 / 30 |
| injected failures reached | 18 | 15 |
| retire fence failures | 0 | 0 |
| distinct memory tuples | 1 | 1 |

**Net resident saving 229,376 bytes of main RAM**, which is the reservation the
arena gives up. Loading peak and steady state are the same number here, because
the texture texels are already transient and load first, so the peak is the
persistent set.

Installation costs, unchanged and reported for completeness: the texture
metadata copies are 6,528 bytes of heap, and `prepare_room_batch_locals()`
allocates 6 bytes per vertex of transient scratch during install — 242,514 for
r100 — which is freed before the next sample and is bounded by the room's
vertex count, not multiplied into `.bss`.

Loading and frame time:

| per load | before | after |
|---|---:|---:|
| read | 50,619 µs | 50,148 µs |
| validate | 1,673,437 µs | 1,575,812 µs |
| install (last) | 1,667,535 µs | 1,600,803 µs |
| retire | bimodal 1.2–16.2 ms | bimodal 1.2–18.5 ms |

Validation is 5.8% faster because there are fewer indices to bound-check. No
regression to quantify: frame p50 moved 7 µs out of 48,886 in the direction of
faster.

### Pixels

64 frozen snapshots against the accepted texture-lifetime build. 58 are
identical. All six differences fall in a generation that is **already
non-reproducible within its own run**, in both builds and in the `1e71167`
baseline — the generations after an injected failure resume at a different
simulation phase, which 5B recorded.

Restricting to frames whose generation is stable in both builds:
**48 of 48 are pixel-identical.** Room materials, characters, HUD and
transparency all land on the same pixels.

## Measured, r101

The package drops 8,894,704 → **8,103,272**. 1,035 of its 3,811 batches keep a
triangle range; 2,776 do not.

Runtime tables r101 would need, measured rather than assumed:

| table | capacity | r101 needs | fits | `.bss` to grow |
|---|---:|---:|---|---:|
| `kRoomBatchTableCapacity` | 4,096 | 3,811 | yes | — |
| `kRoomLocalIndexCapacity` | 65,536 | 244,071 | no | 357,070 |
| global vertex index width | 65,535 | 177,032 | no | element type, not a constant |
| `kRoomPrimitiveBoundsCapacity` | 16,384 | 54,129 | no | 603,920 |
| `kRoomStaticLightingVertexCapacity` | 45,000 | 177,032 | no | 1,848,448 |
| `kRoomBatchVertexCapacity` | 57,344 | 244,071 | no | 373,454 |

### r101's remaining deficit, recomputed

Its persistent set is now geometry 8,103,272 + collision 129,938 + route 12,589
= **8,245,799**, and its textures are transient, so its loading peak is the same
8,245,799 rather than the 12,027,903 the inventory recorded. Against the
3,440,640 the arena reserves plus the 7,667,712 of free main RAM — 11,108,352
together — **the room itself now fits**, with about 2.86 MB spare.

That spare does not cover what would have to come out of it: the static-lighting
arrays alone are 1,848,448, the three other table growths another 1,334,444, and
r101's converted enemy set is roughly 1.5 MB on top. So the deficit is no longer
the room; it is the whole-room derived state and the enemies. Bounding those by
a working set rather than by whole-room capacities is the next question, and
this checkpoint does not answer it.

Unchanged and still true: r101 is a loading-and-rendering question here, not a
playable village. The reset waves, the three events, `cEmDoor`, the ladders and
the em15/em26/em28 modules are still absent.

## Not done here

No vertex quantization, no coordinate welding, no geometry reduction, no texture
change, no strip reordering. Positions, normals, UVs, material assignment,
source-group metadata, culling, alpha order, depth behaviour and near-plane
output are all as they were, which the 48/48 pixel result is the evidence for.

A further 142,212 bytes (r100) and 777,660 (r101) sit in batches that are *not*
order-preserved but are never drawn in the translucent pass, so their triangle
range is unread. Removing it needs the converter to know which materials are
alpha, which lives in the texture package. Recorded with its measurement rather
than attempted here.

## Correction to the failure coverage claimed here

Both captures above were described as exercising "all six points". That was
wrong in two ways, found afterwards and fixed separately.

There are **five injected failure sites**, not six: `kFailPointCount` is 6
because it counts `kFailNone`, the clean load the cycle driver also rotates
through.

And the fifth site was not being exercised at all. It was armed in
`load_room()` before `load_room_texture()` read the package; reading it calls
`adopt()`, `adopt()` calls `close()`, and `close()` clears the hook, so every
upload ran to completion. What the telemetry recorded was the *request* being
noted, not a failure being taken. The four earlier sites were unaffected --
for those, being requested and being taken are the same instant.

Corrected, the counters mean failures reached: the arming moved inside
`load_room_texture()`, after adoption and immediately before upload, and
`failed_loads` now grows only at a failing branch. The focused re-test is in
`R4_TRANSIENT_TEXTURE_PAYLOAD_CHECKPOINT.md`. The memory and pixel results
above are unaffected -- they never depended on the fifth site.

## Evidence

`C:\Flycast-Evidence\re4-dreamcast\d278-r4-one-representation` — two telemetry
captures and a frame set, with `d276`'s frames as the comparison.


## Historical reference recovered on 2026-09-22

[D349](R4_R100_REFERENCE_RECOVERY_CHECKPOINT.md) preserves fresh clean
`r100-autoplay` and manual `r100` builds at `5f42caa`, using all 22 inputs
recovered from the original corrected disc, the pinned KOS/toolchain and the
historical external-file disc target. The early CPU median is 48.880 ms;
whole-trace CPU median 57.559 ms and mean page-flip interval 55.158 ms are
separately reported. No lifecycle loading, snapshot or digest cost is timed.
The user accepts the overall appearance but flags the historical character-facing
defect; the newer native correction must be retained. This is a historical
renderer reference, not recovered-game or complete character-pose acceptance.
