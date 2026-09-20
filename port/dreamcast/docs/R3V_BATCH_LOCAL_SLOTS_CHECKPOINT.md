# R3v batch-local vertex slots checkpoint

Date: 2026-09-20

Decision: **accepted.** The direct-strip room path now resolves each strip
vertex reference through a batch-local slot table instead of the hashed
2,048-entry room vertex cache. Against R3u over matched simulation ticks
165-1194, CPU frame p50 falls from 71.369 ms to 68.789 ms and p95 from
71.463 ms to 68.883 ms. No room pixel changes. Static main RAM rises by
413,696 bytes, which a converter-side table can later recover.

## Why

The R3t profile put 12.35 ms of the room pass in cache-hit lookups, 809 ns per
reference, and the R3s result had already shown the transform-and-light body is
only 836 ns. Each hashed lookup multiplies, xors, masks, loads the entry and
compares three keys; the direct-strip path then re-verifies every entry to
catch an intra-strip eviction. A gated probe (`d246`) measured how much of the
cache's reuse crosses batch boundaries: 592 of 4,467 hits per frame, 13%. The
other 87% is a vertex referenced more than once inside one batch, which needs
no hash to find.

## Change

At load, `prepare_room_batch_locals()` walks every batch's strips once and
renumbers each vertex reference into a batch-local index in first-seen order,
writing a 16-bit local index per strip vertex and, per batch, a table from
local index back to package vertex. The package arrays are untouched; the
strip bounds, the cull audit, the triangle path and the blended path keep
using them.

`submit_room_strips()` takes a fresh serial per call. For a batch whose
distinct vertex count fits the 1,024-entry slot table, each reference reads
the local index, checks `slot.serial == serial`, and either uses the entry or
fills it with the same transform-and-light body, now split out as
`fill_room_entry()`. There is no hash, no key compare and no eviction; the
verify pass is skipped because a slot cannot be overwritten within a call.
Batches with more than 1,024 distinct vertices, three in the production
package (two unpartitioned alpha materials and one opaque cell), take the
hashed path unchanged, as do the strip fallback path and the triangle path.

The tables are 131,072 bytes of local indices, 114,688 bytes of batch vertex
tables, 24,576 bytes of per-batch offsets and counts, and 73,728 bytes of
slots, plus a transient 242,514-byte scratch at load. The production package
uses 44,844 batch-local entries and 56,145 local indices; the largest batch
has 2,760 distinct vertices.

## Matched Flycast result

| p50 unless stated | R3u | R3v |
|---|---:|---:|
| CPU frame | 71.369 ms | **68.789 ms** |
| CPU frame p95 | 71.463 ms | 68.883 ms |
| CPU frame p99 | 73.929 ms | 71.326 ms |
| `submit_us` | 44.413 ms | 41.832 ms |
| opaque room | 27.810 ms | 25.320 ms |
| punch-through plus blended room | 3.000 ms | 2.908 ms |
| room index references | 14,871 | 14,871 |
| room cache hits | 4,467 | 3,863 |
| transformed and lit vertices | 10,404 | 11,008 |
| room strip evictions | 0 | 0 |
| direct strips / fallbacks | 2,963 / 88 | 2,963 / 88 |
| immediate PVR calls / bytes | 370 / 972,928 | 370 / 972,928 |
| free main RAM | 5,738,496 B | 5,324,800 B |

The 604 extra transforms per frame are the cross-batch reuse the hashed cache
had captured, within 2% of the 592 the probe predicted; at 836 ns each they
cost 0.5 ms, and the frame still gains 2.580 ms. Zero simulation overruns and
zero discarded simulation time. Actor stages are unchanged to the microsecond.

## Visual result

Framebuffers were read from emulated VRAM against the R3u reference in
`d244-r3u-cell-4-visual`. Every differing pixel at ticks 250, 450 and 700 lies
inside Leon's bounding box, (343,242)-(519,420) and (298,194)-(431,420), and is
his render-time animation phase, which follows the frame interval; tick 450
landed on the same simulation tick in both runs and differs by 337 such
pixels. **No pixel outside the actor differs**, as expected: the slot path
evaluates the same transform and light body on the same vertex for the same
light selection.

## Manual build

The manual ELF was built from the same tree without the autoplay flag and
smoked in `d249-r3v-manual-smoke`: it reached simulation tick 2,618, sampled
input 8,720 times, and reported zero queue drops, simulation overruns or
discarded simulation time. Its maximum input sample gap was 19.962 ms, one
long sample against the usual 12.485 ms; the queue absorbed it without a drop.
Post-load free main RAM was 5,324,800 bytes in both builds.

## Retained evidence

- `d246-r3v-cross-batch-probe` — gated profile build with the cross-batch hit
  counter, ELF
  `eb97f50118910438f0034fb25c806c8457e316e33e1d3e4bde4557e37f342d6c`;
  the probe code was not retained
- `d247-r3v-batch-local-slots` — accepted timing, ELF
  `b75940e042b0e9c7f233802567c1a697cf06bcf6c4e10f8e56f8ae0a7dc151bc`
- `d248-r3v-visual` — framebuffers at ticks 250, 450 and 700
- `d249-r3v-manual-smoke` — manual build smoke, ELF
  `7cf43e0e976138f2d29a0b692a60994a28cfa0c24db329bff7397de5a4ec9260`

## Follow-up

The local index and batch vertex tables are pure functions of the package and
belong in it. A converter-side layout would replace the 32-bit strip index
array with 16-bit local indices and add the batch vertex table, which is
smaller than the current runtime copy and removes the load-time pass; that
would recover most of the 413,696 bytes. It is a package-format change and is
queued as memory work, not frame work.

## Limits

Flycast measurements of the autoplay route and one manual smoke. The slot
path was exercised only by this package; a package with more than 4,096
batches, 65,536 strip vertices, 57,344 batch-local entries or 65,535 vertices
disables it at load and falls back to the hashed cache with a console message.
Physical Dreamcast timing remains pending.
