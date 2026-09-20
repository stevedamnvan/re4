# R3q room submission profile checkpoint

Date: 2026-09-20

Decision: **no production behaviour change.** R3q is a measurement pass that
answers the open question in [REALTIME_PATH.md](REALTIME_PATH.md) — packet
construction versus store-queue copy time — and closes two candidate
optimizations with measured evidence. It keeps a compile-gated diagnostic
option and changes no accepted code.

## What R3q measures

`SUBMIT_PROFILE=1` adds `-DRE4DC_SUBMIT_PROFILE` to the room build. Off, the
option is inert: the preprocessed translation unit is byte-identical to R3p and
both production ELFs match R3p exactly once DWARF line tables are stripped.

- autoplay, debug-stripped: `932c1647a1901157474f238988167a49a5a84cdac9fe99d2b3b079fa4b84b7ad`
- manual, debug-stripped: `570c36bdda2e440bc69eca4d573f4e89e0cad316063aa3b386db6eca1e7b042c`

Unstripped hashes moved because the added `#if` lines shift `.debug_line`. The
R3p hashes `4fd89b4e…` and `b265872f…` therefore reproduce only from the
pre-R3q tree; the executable code is unchanged.

The diagnostic adds three things:

1. a nanosecond bracket around every `pvr_prim()` call, split into room and
   actor buckets, plus a startup calibration of the timer read itself;
2. per-pass room counters for the opaque, punch-through, and blended lists —
   time, triangles, vertex index references, and vertex-cache misses;
3. a per-frame bitmap of distinct referenced room vertex indices, which bounds
   what any room vertex cache can save.

All three are diagnostic instruments, not candidate optimizations. They are
retained so the measurement is repeatable; they never compile into an accepted
build.

## Store-queue transport is not the bottleneck

Evidence `d222-r3q-submit-profile`, matched over simulation ticks 165-1194,
411 samples. The calibrated timer read costs 335.03 ns, so each bracketed call
carries 670.06 ns of measurement overhead that is subtracted below.

| Measured p50 | Value |
|---|---:|
| CPU frame | 87.054 ms |
| `submit_us` | 58.936 ms |
| opaque room | 27.331 ms |
| punch-through room | 0.149 ms |
| blended room | 17.773 ms |
| room `pvr_prim` bracket | 1.671 ms over 508 calls and 565,120 B |
| actor `pvr_prim` bracket | 1.322 ms over 109 calls and 506,720 B |

Subtracting the calibrated overhead gives **1.331 ms of real room store-queue
transport and 1.249 ms for actors, 2.580 ms in total.** That is 4.4% of
`submit_us` and 3.0% of the 44.507 ms R3p room path. The remaining room cost is
transform, lighting, clipping, and packet construction.

**Queue item 3 (submission transport) is therefore closed.** Bounded KOS DMA
buffers cannot recover more than about 1.3 ms of room time even if they made
the copy free, and they would add main-RAM buffers and pipeline latency. Do not
revisit DMA without a trace in which transport is a materially larger share.

Whole-build profiling overhead is +0.837 ms of CPU frame p50 against R3p
(87.054 against 86.217 ms). The timer brackets account for 0.413 ms of that;
the rest is the phase branch and the counters.

## The room vertex cache is already effectively optimal

Evidence `d223-r3q-room-reference-probe` and `d224-r3q-room-pass-split`. The
probe build carries the distinct-reference bitmap, so its timings are inflated
and only its counts are authoritative.

| Per-frame p50 | Value |
|---|---:|
| room vertex index references | 20,178 |
| room vertex cache hits | 4,828 |
| room vertex cache misses | 15,350 |
| **distinct room vertex indices touched** | **15,317** |
| distinct room light selections | 8 |

The direct-mapped 2,048-entry cache misses 15,350 times against a floor of
15,317 distinct indices. Only 33 misses per frame, 0.22%, are evictions rather
than genuinely new work.

**Enlarging or re-hashing the room vertex cache is therefore closed.** A
perfect cache of any size would save at most 33 transform-and-light evaluations
per frame. The cost is not cache behaviour; it is that the frame genuinely
touches 15,317 distinct room vertices to draw 9,155 triangles.

## Per-pass split: the blended list is the outlier

Evidence `d224-r3q-room-pass-split`, matched ticks 165-1194, 396 samples.

| Room pass | p50 time | triangles | index references | transforms (misses) | transforms per triangle |
|---|---:|---:|---:|---:|---:|
| opaque | 29.456 ms | 7,437 | 13,704 | 9,117 | 1.23 |
| punch-through | 0.135 ms | 0 | 0 | 0 | — |
| blended | 18.917 ms | 1,718 | 6,474 | 6,233 | 3.63 |

Cost tracks transformed vertices almost exactly: 3.23 µs per transform in the
opaque pass and 3.03 µs in the blended pass. Across both lists the room path is
close to **3.1 µs × 15,350 transformed and lit vertices**, which accounts for
the whole measured room budget.

Two consequences:

- The blended list spends 18.917 ms to draw 1,718 triangles because it
  transforms 3.63 vertices per triangle at a 3.7% cache hit rate. The opaque
  list transforms 1.23 per triangle at a 33.5% hit rate. The cause is stated in
  the next section; it is not a missing strip stream.
- The punch-through pass draws nothing under this camera and still walks 327
  visible groups and their batches for 0.135 ms. Skipping an empty list is
  correct but small; do not confuse it with the blended result.

## Why the blended list is inefficient

A first reading blamed missing strips, because the package reports 3,570 batches
of which 3,333 carry ordered strips. Reading the package directly disproves
that. The 237 batches without the order certificate are all opaque, and the
opaque pass never tests the certificate. **All 22 blended batches already carry
certified strips.**

The real cause is the deliberate R3k boundary: alpha-bearing materials were left
unpartitioned so their source draw order stayed intact. Opaque geometry is split
into 2,988 groups with a median extent of 4.00 m, but the blended geometry sits
in 17 groups whose extents reach 273.83 m, against a declared 35 m horizon.
Group visibility therefore barely culls it.

| Package totals | opaque | punch-through | blended |
|---|---:|---:|---:|
| batches | 3,439 | 109 | 22 |
| groups | 2,988 | 109 | 17 |
| triangles | 24,985 | 1,612 | 4,298 |
| strip vertices | 48,887 | 3,708 | 8,432 |

Against the measured frame: the opaque pass references 13,704 of its 48,887
strip vertices, 28%, and emits 7,437 of 24,985 triangles, 30% — culling tracks
the work. The blended pass references 6,474 of its 8,432 strip vertices, 77%,
and emits 1,718 of 4,298 triangles, 40%. It pays a full transform and lighting
for most of the room's alpha geometry, then discards well over half of it in the
per-vertex depth test and the clipper, because those tests run only after
`cached_room_vertex()` has already done the work.

The order-safe fix is per-strip bounds culling rather than finer partitioning:
skipping a whole strip before touching its vertices removes work without
reordering any triangle that is still drawn, so the R3c blend-order certificate
continues to hold by construction. Finer alpha cells would reorder across cell
boundaries and would need a new order argument. Bounds for the 2,067 blended
primitives cost about 33 KB.

## Retained evidence

- `C:\Flycast-Evidence\re4-dreamcast\d222-r3q-submit-profile` — transport split,
  candidate `648b2c6fdd4be47dcd8af6c0fd8347d6d2bd5fb2ebcb5afed13f294401cf3323`
- `C:\Flycast-Evidence\re4-dreamcast\d223-r3q-room-reference-probe` — distinct
  references, candidate `a9b30afb5733978bf851dcc095c80d6b0c9532aa15a478efeb7bbfb1e29caed9`
- `C:\Flycast-Evidence\re4-dreamcast\d224-r3q-room-pass-split` — per-pass split,
  candidate `aa93a78730c48e3b933ae8e32608d2b6bfb702d26bd8116361596c3fa478c635`

Each directory keeps its telemetry reader, `telemetry.jsonl`, the pinned
Flycast build, and `emu.cfg`. The telemetry struct grows with the diagnostic:
version 10 and 360 bytes in production, 392, 408, and 424 bytes in the three
profile builds. Production capture tooling is unaffected.

## Limits

These are Flycast measurements of the autoplay route only. They do not cover
free movement, aim extremes, enemy contact, Leon death, or a human controller,
and no physical Dreamcast timing exists yet. The blended-list conclusion is a
measured cost attribution; the proposed 12 ms is an estimate from the measured
per-vertex rate, not a demonstrated result.
