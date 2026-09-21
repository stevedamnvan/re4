# Transient CPU texture payloads

Status: **accepted.** The room's texture texels are no longer resident. The
arena's high water falls from 5,671,872 to 3,572,256 bytes, its reservation
follows it down, and the machine gets 2,093,056 bytes of main RAM back with the
presentation, the VRAM allocation and the frame time unchanged.

## What was actually wrong

A texture package was one object with two lifetimes inside it. The header, the
descriptors, the material names and the VRAM pointers those bind to are needed
for as long as the room is resident. The texels are needed between validation
and `pvr_txr_load`, and never again — the runtime only ever asks a texture
package for `find()`, `pvr_texture()`, `header()` and `textures()[i]` after
upload, all of which read the descriptor prefix.

Both lifetimes were the room's, so r100 kept 2,099,616 bytes of texel data in
the arena for the whole time the PVR was already holding it.

`Package::close()` could not be used to end the shorter lifetime, because it
also frees the texture memory and the ownership flags — precisely what has to
survive.

## The change

`Package::release_payload()` copies the header and descriptor array out of the
adopted bytes into an allocation of their own, points the package at that copy,
and leaves `pvr_textures_` and `owns_texture_` untouched. It refuses, changing
nothing, if the package has not uploaded, if any texture's `data_offset` falls
inside the prefix, if the descriptor range runs past the package, or if the copy
cannot be allocated. `close()` frees the copy.

That alone would have saved nothing. The texels only stop costing anything if
they never coexist with the largest allocation the room makes, so
`load_room_texture()` marks the arena, reads, uploads, releases and rewinds —
and the two room texture packages are loaded **before** the geometry, collision,
route and character packages rather than after. In `main()` that reordering
needs the PVR up before the first package is read, so `vid_set_mode` and
`pvr_init` moved ahead of the loads; they depend on nothing that is loaded
below.

`kRoomArenaCapacity` then dropped from 5.5 MB to 3.5 MB. That is not
housekeeping — it is the measurement. A released pointer proves nothing; a room
that loads out of a reservation **2,097,152 bytes below its own previous high
water** proves the bytes genuinely came back.

## Measured

Three captures, one sitting, same host, same emulator build, sequential and
non-overlapping, 240 s each. Baseline is `1e71167` built from a worktree with
the benchmark assets copied rather than reconverted — the room-owned disc files
are byte-identical across all three (`r10d.re4room`, `r10d.re4sat`,
`r10d.re4tex`, `route.re4rtp`, `ganado.re4chr`, `ganado.re4tex`, five wavs).

| | baseline | transient, 5.5 MB arena | transient, 3.5 MB arena |
|---|---:|---:|---:|
| arena high water | 5,671,872 | 3,572,256 | 3,572,256 |
| arena steady state | 5,671,872 | 3,572,256 | 3,572,256 |
| arena reservation (`.bss`) | 5,767,168 | 5,767,168 | 3,670,016 |
| main RAM free | 5,345,280 | 5,341,184 | **7,438,336** |
| heap used | 133,236 | 139,780 | 139,780 |
| VRAM free after textures | 3,030,856 | 3,030,856 | 3,030,856 |
| frame `frame_us` p50 | 48,886 | 48,887 | 48,886 |
| loads / retirements | 19 / 34 | 17 / 30 | 17 / 30 |
| injected failures | 15 | 13 | 13 |
| failure points exercised | all four | all four | all four |
| retire fence failures | 0 | 0 | 0 |
| distinct memory tuples | 1 | 1 | 1 |

The middle column is the honest half of the result and the reason it is printed
here. With the payload released but the reservation unchanged, **main RAM free
went down by 4,096 bytes.** The arena is a fixed `.bss` array; reclaiming space
inside it recovers nothing until the array shrinks. Reporting the 2.1 MB as a
saving at that point would have been false.

Section sizes, baseline to candidate: `.bss` 7,904,756 → 5,807,508
(−2,097,248), resident image 10,915,117 → 8,818,021.

### Where the 2,099,616 bytes go

Computed from the package headers on the host, and matching the guest exactly:

| | bytes |
|---|---:|
| `r10d.re4tex` in the arena (1,983,504, padded to 32) | 1,983,520 |
| `ganado.re4tex` in the arena (116,080, padded) | 116,096 |
| **temporary installation bytes released** | **2,099,616** |
| metadata kept: 48 + 53×96, and 48 + 14×96 | −6,528 |
| measured heap growth (metadata + allocator overhead) | 6,544 |
| measured arena high-water reduction | 2,099,616 |
| measured main RAM recovered | 2,093,056 |

2,093,056 = 2,097,152 of reservation minus the 4,096 the heap growth rounds to.
The reclaimed figure is the net after metadata, alignment and staging, not the
raw texel payload.

## Correctness

Everything below held across 17 load/retire/reload generations with 13 injected
failures interleaved, in the 3.5 MB build.

* **VRAM is byte-identical.** `pvr_free_after_textures` is 3,030,856 in all
  three runs, so R4e's within-package sharing still folds the same descriptors
  onto the same allocations and single ownership still frees each one once.
* **One distinct memory tuple** across every generation — arena used, arena high
  water, VRAM free, AICA free, main RAM free and heap used. The metadata copies
  are freed and re-made identically, so `release_payload()` does not leak into
  the heap across reloads.
* **Failure rollback is unchanged.** All four injection points fire and each is
  followed by a clean retirement and a successful retry. The points now sit on a
  monotonic ladder of ownership: nothing yet, texture memory owned, persistent
  packages adopted, derived state allocated. On an upload failure
  `load_room_texture()` deliberately does *not* rewind the arena — the package
  still points into it and retirement owns that decision.
* **Pixels.** 60 of 64 frozen snapshots are identical to the baseline's
  corresponding frame. The four that differ are all in generation 3, which is
  also the generation that differs from its own siblings **in the baseline
  run**, independently, at the same ticks. Cross-reload stability is unchanged
  or slightly better: tick 120 is 11/11 in both, ticks 220 and 270 are 10/10 in
  the candidate against 9/10 in the baseline. The instability is simulation
  phase after an injected failure, not material binding — a binding broken by
  losing its texels would differ everywhere, not in one generation.
* Frame time is unchanged: p50 48,886 against 48,886.

Still owed, and not claimed here: the representative human gameplay check
(`make r100-cycle`) and physical-hardware evidence.

## What this does and does not do for r101

r101's texture payload measured 2,981,888 raw. By the same arithmetic its
metadata prefix is 48 + `count`×96, so the reclaim is close to but under three
megabytes, and it is **temporary installation bytes**, not persistent ones. It
lowers r101's loading peak. It does not change the persistent geometry, which
is where r101's 8,894,704 bytes are, nor the 65,535 global-vertex restriction,
which no amount of texture lifetime work touches.

The residency ledger in the r101 checkpoint has been corrected alongside this:
the batch capacities were misread, the static-light arrays are an option rather
than a mandatory cost, romdisk-to-RAM moves are not savings, and the ESL entry
count is not a simultaneous actor count.

## Evidence

`C:\Flycast-Evidence\re4-dreamcast\d276-r4-transient-textures` — three
telemetry captures, two frame sets, both discs and both executables, with
`run.ps1` amended so a collector kills only the process it started instead of
every Flycast on the machine.
