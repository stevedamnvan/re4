# R4 deliverable 5A — reclaimable r100 load → retire → reload

Status: **kept.** The accepted r100 encounter now loads from reclaimable
storage, retires, and reloads, sixteen times in a row, returning to a
byte-identical memory state every time. Frame time is unchanged.

Branch `dreamcast-port`, on top of `431f650`. Evidence:
`C:\Flycast-Evidence\re4-dreamcast\d274-r4-5a-room-lifecycle\`.

## What was built

Room-owned package bytes have left the linked romdisk. They are read from the
disc into an owned arena, validated in that memory by the existing parsers, and
released as a unit when the room retires. Persistent resources — Leon, his
textures, the HUD and its atlas, weapon and player audio — stay embedded, as
this checkpoint allows.

* `room_storage.{hpp,cpp}` — `re4dc::storage::Arena` (init / allocate / reset /
  mark / rewind, 32-byte alignment, usage and high-water accounting) and a
  bounded synchronous `read_file()` that reads in 64 KiB chunks, rejects a short
  file or an unexpected EOF, and rewinds the arena on any failure.
* Each package gained `adopt(data, size)` beside `open(path)`. The validation
  body is unchanged and now shared by both: `open()` still mmaps, `adopt()`
  takes bytes the caller owns. No parser was duplicated and no format,
  validation rule or alignment requirement changed.
* `load_room()` / `retire_room()` in `main.cpp`, plus a resource manifest that
  keeps source identity — `(archive, tag, ordinal)` as the original names it —
  with the path as a storage location only.
* `port/dreamcast/tools/mkdisc.sh` builds the bootable image; the Makefile's
  `split-room-disk` *moves* the room-owned files out of the romdisk staging
  directory, so an embedded duplicate cannot survive by accident.

A load becomes visible to gameplay only after every read, validation, texture
upload and derived-state rebuild has succeeded. A failure at any point returns
false, and the arena and the derived state are left ready for a retry.

Retirement takes explicit ownership of all three memories: enemy audio is
stopped on every channel and unloaded sample by sample (never
`snd_sfx_unload_all`, which would take persistent samples with it), texture
packages are closed so R4e's within-package sharing frees each unique VRAM
allocation exactly once, and the arena is reset. `pvr_wait_ready()` runs before
anything is freed, so the wait is for the GPU to finish reading, not merely for
submission to return. Everything derived from the room is invalidated by hand:
compiled material and strip headers, punch-through headers, the visible-group
list, the vertex cache and its generation, batch slots and serial, primitive
bounds, batch-local tables, static-light ownership and the unit-normal flag.

## Measured

Sizes, r100 production configuration:

| | accepted (`431f650`) | 5A | change |
|---|---|---|---|
| executable | 11,592,728 | 5,813,988 | −5,778,740 |
| linked romdisk image | 8,436,736 | 2,599,936 | −5,836,800 |
| `.text` | 8,829,393 | 3,001,461 | −5,827,932 |
| `.bss` | 2,071,796 | 7,904,660 | +5,832,864 |
| resident image (text+data+bss) | 10,908,585 | 10,913,841 | +5,256 |

Bytes moved out of the romdisk stage: **5,836,118** across ten files (six
packages and four enemy samples). The arena is **5,767,168** bytes, sized from
the measured high water rather than guessed.

The honest reading of that table: resident RAM is unchanged. What changed is
that 5.8 MB of it is now reclaimable instead of permanent, and the executable
that has to be read off the disc at boot is 5.8 MB smaller.

Lifecycle, sixteen reloads with seven injected failures (Flycast):

| | value |
|---|---|
| arena capacity / used / high water | 5,767,168 / 5,671,872 / 5,671,872 |
| bytes read per load | 5,671,772 |
| read | 38–52 ms |
| validation | 1,163,600 µs |
| texture upload | 5,607 µs |
| install (headers, static light, bounds, batch locals) | 1,673,290 µs |
| retirement | 1,240–1,406 µs |
| VRAM free / AICA free / heap free, after every cycle | 3,030,856 / 1,378,336 / 245,656 |

Across all seventeen generations the tuple (heap used, heap free, VRAM free,
AICA free, arena used) took exactly **one** distinct value. Nothing accumulates
in the CPU heap, in VRAM, in AICA memory or in the arena. Arena reset makes the
capacity genuinely reusable: every load starts from used = 0 and lands on the
same 5,671,872.

Read, validation, upload and install are reported separately from general-heap
free memory, and separately from the arena.

Failure path: every third cycle injects an unreadable package. Seven failures,
seven clean retirements, seven successful retries, no leak and no drift — the
memory tuple above covers the failed cycles too. A load is a deliberate stop,
so the clock is re-seeded afterwards and queued input is discarded; no
catch-up debt accumulates and no transition-screen input is replayed.

## Correctness

Frame time, production build from the disc with cycling off, against accepted
R4f measured in the same harness:

| | p50 | p95 | p99 |
|---|---|---|---|
| accepted R4f | 57,565 | — | — |
| 5A production | 57,569 | 57,635 | 60,123 |

Unchanged — 4 µs at p50, well inside run-to-run noise.

Presentation was compared at equivalent simulation state rather than by
submission digest, because texture addresses change with the allocation layout.
Over 3,038 matched simulation ticks, all of `visible_groups`,
`transformed_vertices`, `room_triangles`, `actor_triangles`, player and enemy
position and yaw, health, ammo, room index references, light evaluations,
room and actor vertex records, direct strips, strip fallbacks, culled strips,
near-plane accepts and rejects, `pvr_submit_calls`, `pvr_submit_bytes` and both
light selections are **identical**.

Two counters differ on 252 of those ticks: `collision_queries` and
`collision_block_tests`. On every one of those ticks `simulation_ticks_run`
differs as well — the frame bundled a different number of simulation steps —
and per step the counts line up. Positions match on every matched tick, so this
is frame bundling, not a behavioural or rendering difference.

## Two findings worth recording

**KOS mounts `/cd` from the low-density table of contents.**
`fs_iso9660.c` calls `cdrom_read_toc(&toc, false)` and takes the last data
track it finds there. In a GD-ROM image (GDI) the payload track lives in the
high-density area, so KOS never sees it: the image boots — the bootstrap reads
the high-density track directly — and then every `fs_open("/cd/...")` returns
−1. The image is therefore a single-session CD-R (CUE/BIN), which is also what
homebrew actually burns. A CD-R bootstrap expects `1ST_READ.BIN` *scrambled*
and descrambles it on load, the opposite of the GDI case; shipping it
unscrambled produces a machine that runs but is not running your program.

**KOS's GD-ROM streaming read does not return for a package smaller than one
chunk.** A sector-aligned request into a 32-byte-aligned buffer makes KOS start
a stream; a request whose length is not a multiple of 32 is finished with a
separate small stream request. For every package larger than one 64 KiB chunk
this is fine. For the 6,128-byte route it never returns, wherever it sits in the
load order and however the request is split. A destination that is not 32-byte
aligned takes the block-cache path instead, which reads the same bytes a sector
at a time and returns, so a package smaller than a chunk is read through a
bounce buffer and copied. Reads are also kept to whole sectors while more than
one sector remains, which is the natural request size for optical media.

## Not done, and deliberately

* **Manual gameplay check — deferred, needs a human.** `make r100-cycle` builds
  the same lifecycle with autoplay off for exactly this. Every number above
  comes from the autoplay route; a representative hands-on pass is still owed.
* **Physical hardware — not run.** Everything here is Flycast. Read and
  validation timings in particular are emulator timings and should not be read
  as Dreamcast figures.
* `room_loads` counts lifecycle reloads; the boot load goes through `main()`
  rather than `load_room()`, so it reports zero upload and install time in a
  production capture. The cycle capture supplies those.
* Validation at 1.16 s and install at 1.67 s dominate a load and are worth
  attacking, but not during 5A.
* No r101, no asynchronous worker, no VQ, no palette conversion, no PS2
  comparison, no moving VRAM allocator, no performance experiment. r101's
  budget stays provisional.
