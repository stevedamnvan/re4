# r101 resource inventory and conversion

Status: **r101 is converted and measured. It does not fit.** The r100 → r101
transition cannot be implemented as a straight swap on the current
representation, and the decision about what to change is a scope decision, not
an implementation detail.

## What r101 actually is

r101 is **the village** — `src/st1/r101.cpp`: the first fight, the tower siege
and the enemy reset waves, the church bell event (s30), the house event (s20),
the binocular view (s00) and the door messages. D4 identified it correctly as
r100's only authored neighbour; it did not identify what was on the other side
of that door.

`St1/r101.das` (5,033,632 bytes) was extracted from the disc and decompressed
to 37 chunks. Unlike r100 it is **not** a streamed room: the disc carries
`r100_00.dat` through `r100_04.dat` but no `r101_NN.dat`, so the whole room is
one scenario SMD.

## Correction to D4

D4 estimated r101's converted size from the standalone chunks and concluded it
"carries far less texture data than r100 despite 1.7x the geometry". That was
wrong in both directions.

**r101's texture data is embedded inside the scenario SMD**, not shipped as its
own chunk. The SMD tool extracts `r101_004.TPL`, 1,437,824 bytes, which the
chunk listing never showed. D4 counted the three standalone TPL chunks
(252,512) and missed it.

| | D4 estimate | measured |
|---|---:|---:|
| geometry | 2,024,000 | **8,894,704** |
| textures | 327,000 | **2,990,672** |
| collision | 132,000 | **129,938** |
| route | 13,000 | **12,589** |
| **room content** | **~2,496,000** | **12,027,903** |

The conversion ratios D4 borrowed from r100 do not transfer: r100's geometry
converts at 0.658 of its source SMD, r101's at 2.89. Both packages cost about
72 bytes per triangle, so the ratio difference is not a conversion difference —
it is that r100's source SMD is dense and r101's is a much larger room.

## Measured against the memory map

| | r100 accepted | r101 | note |
|---|---:|---:|---|
| geometry | 2,220,388 | 8,894,704 | cell size 4, same converter, no r100 material overrides |
| collision | 183,600 | 129,938 | |
| route | 6,128 | 12,589 | |
| textures | 1,983,504 | 2,990,672 | max dimension 256, twiddled, same as r100 |
| **room content** | **4,393,620** | **12,027,903** | |
| triangles | 30,895 | 135,813 | |
| vertices | 40,419 | 177,032 | |
| materials | 43 | 91 | |
| groups | 1,093 | 812 | |
| batches | 1,421 | 3,811 | |

Against the budget D4 established — 11,191,138 bytes for room content, with the
persistent packages still embedded in the romdisk — **r101's room content is
836,765 bytes over on its own**, before a single enemy.

That budget mixes categories that behave differently, and the rest of this
document is easier to read against them kept apart:

| category | what it is | r100 today |
|---|---|---:|
| disc bytes | what the image carries; costs no RAM | 4,393,620 room-owned |
| persistent CPU bytes | package bytes resident for the room's life | 3,572,256 in the arena |
| temporary installation bytes | read and released during loading | 2,099,616 texture texels |
| derived state | `.bss` and heap compiled from packages | 630,000 static lighting + headers |
| VRAM | texture memory | 2,604,984 of 5,635,840 |
| AICA | sound memory | 1,378,336 free |
| safety margin | arena slack over the measured high water | 97,760 |

Two things that follow, and that earlier drafts got wrong: moving a persistent
package out of the executable's romdisk and into RAM **is not a RAM saving** --
it is the same bytes in a different place, and 5A measured exactly that
(resident image 10,908,585 to 10,913,841, parity). What it buys is
reclaimability, which is a different property. And temporary installation bytes
only stop costing RAM once the reservation that holds them shrinks; until then
they are reclaimed on paper only.

Vertex-count limits in the current runtime. An earlier draft of this section
read two of them wrongly; corrected:

* **A 65,535 global-vertex restriction**, independent of everything else.
  `prepare_room_batch_locals()` refuses a room whose `vertex_count` exceeds
  `0xffff`, because `g_room_batch_vertices` stores global vertex indices as
  `std::uint16_t`. r101's 177,032 vertices are 2.7x over it. This is the
  binding limit on r101's geometry and no constant raises it: the array's
  element type would have to widen. The refusal is a refusal rather than a
  failure -- the renderer keeps working through the hashed-cache fallback, so
  the cost is the direct-strip path, not correctness.
* `kRoomStaticLightingVertexCapacity` is **45,000** (`main.cpp:2821`), and
  `prepare_room_static_lighting()` refuses any room above it. Growing it to
  177,032 costs 14 bytes per vertex in `.bss`, 2,478,448 instead of 630,000, a
  further 1,848,448 bytes. That is **an option with a price, not a mandatory
  cost**: whether whole-room static-light arrays are the right representation
  for a room this size is exactly the question the geometry and residency work
  has to answer, and bounding them by a working set instead would cost less.
* `kRoomBatchSlotCapacity` is **1,024 local vertices within one batch**, not a
  count of the room's batches. The room's batch count is bounded by
  `kRoomBatchTableCapacity`, which is 4,096 and **does** fit r101's 3,811
  batches. `kRoomVertexCacheCapacity` (2,048) is a cache over 177,032 vertices
  and would thrash, which degrades rather than fails.

VRAM and AICA are not the constraint, as D4 said. r101's texture payload is
2,981,888 against 5,635,840 usable, leaving room for the always-resident
508,928. r101's sound chunk is 1,868,608 on disc against r100's 951,712; the
port loads a handful of samples rather than the chunk, so this is a ceiling, not
a requirement.

## r101's enemy set, which was the open range

D4 left r101's enemies as an open 1.5 to 3.5 MB range. The authored list is in
`etc/emleon00.esl`, keyed by `room = stage << 8 | room` at offset 0x18 of each
0x20-byte entry:

| room | entries | enemy ids |
|---|---:|---|
| r100 (0x0100) | 25 | em12 x12, em21 x1, em23 x5, em2a x7 |
| r101 (0x0101) | **46** | **em15 x43**, em26 x1, em28 x2 |

These are **authored entries in the enemy list**, which is not the same thing
as simultaneous live actors. Four distinct quantities are involved and this
document should not conflate them:

* *authored entries* -- rows in `emleon00.esl` for the room: 46 for r101.
* *source-controlled live instances* -- how many the room's own code has alive
  at once. `R101Work` tracks ten reset slots and `r101_checkEmNum` gates
  spawning, so the authored 43 em15 rows are a pool the room draws from over
  the fight, not a simultaneous population. What the real ceiling is has not
  been read out of the source yet and is not claimed here.
* *shared resource variants* -- one converted em15 model and texture set serves
  every em15 instance, so resource cost scales with distinct ids (three), not
  with entries.
* *per-instance state* -- pose palettes, transforms and AI state, which do
  scale with live instances.

**No claim of 43 simultaneous em15 actors is made or supported by the ESL
count.**

r101 and r100 share **no** enemy id, so nothing carries over. The archives are
`em15.drs` 5,970,784, `em26.drs` 363,712 and `em28.drs` 228,928 on disc; at
r100's own em12 conversion ratio (5,664,736 archive to 1,278,152 converted
model plus textures) that is roughly 1.5 MB converted for one model each. Since
instances share their model, that figure is close to the whole resource cost;
what it does not cover is per-instance state.

It is also worth recording that **the accepted r100 build runs a slice, not the
room**: r100 is authored with 25 enemies of four types and the port ships one
em12. r101's authored content is not comparable to what the port does today.

## Missing source systems for a real r101

Recorded rather than substituted:

* the enemy reset waves (`R101Work::em[10]`, `r101_checkEmReset`), the tower
  siege check, `r101_checkEmNum`
* the three events, `evd/r101s00.evd` 453,984, `r101s21.evd` 2,181,600 and
  `r101s30.evd` 2,373,792, none of which the port has any system for
* `cEmDoor` with `setCloseLock`, the door-message and key-use paths
  (`r101_checkDoor102KeyUse`, `r101_DoorDontOpen*`)
* the ladders (etc models 5/6/7), the chicken flag, the operator scripts
* em15, em26 and em28 runtime modules; the port has no enemy but em12

## What this blocks, and the options

The transition cannot be implemented as written: the runtime would refuse
r101's geometry at `prepare_room_static_lighting()` and the arena would not hold
it. The ways forward are materially different and the choice is not mine to
make:

1. **Take the persistent packages out of the romdisk as well.** 5A deliberately
   left them embedded. Removing them moves about 2.6 MB out of the executable
   and into reclaimable storage. Note that this is a move, not a saving: it
   does not reduce the resident image, it makes those bytes releasable. r101's 12.03 MB plus 1.85 MB of
   extra static-lighting arrays plus enemies still exceeds it.
2. **Reduce r101's fidelity.** A 128-pixel texture limit takes 2.99 MB to about
   0.9 MB. Geometry has no equivalent lever short of partitioning.
3. **Partition the room and load part of it**, which is intra-room streaming —
   the asynchronous work this checkpoint was told not to make a prerequisite.
4. **Pick a different first transition.** r101 is r100's only authored
   neighbour, so this means abandoning "the smallest real connected transition"
   in favour of a pair that fits, which contradicts the D4 instruction to use
   the authored relationships.

Option 2 was the only one that needed no new machinery, so it was measured
rather than assumed. At a 128-pixel limit r101's textures convert to 1,608,272
bytes instead of 2,990,672, saving 1,382,400:

| | bytes |
|---|---:|
| room content at 128 px | 10,645,503 |
| extra static lighting arrays for 177,032 vertices | +1,848,448 |
| **total against an 11,191,138 budget** | **12,493,951** |

**It does not fit either**, by 1,302,813, and that is still before the enemy
set. Options 1 and 2 together raise the budget toward 13,790,208 and leave
about 12.5 MB of room plus roughly 1.5 MB of converted enemy, near 14 MB —
marginal to over again.

So the honest position is that no combination of the levers available to this
checkpoint lands r101 comfortably. Either the room is partitioned and loaded in
parts, which is the intra-room streaming this checkpoint was told not to make a
prerequisite, or its fidelity is cut further than a 128-pixel texture limit.
That is the scope decision.

## What was built

`Makefile.host` gains `room-r101-source`, `collision-r101-source`, `route-r101`,
`texture-r101-source` and the aggregate `room-r101`. They use the same
converters and the same settings as r100, with none of r100's per-material
overrides, which are r100 geometry decisions. The r101 chunks live under
`orig/G4BE08/rooms/r101/`, extracted from the private disc and ignored like the
rest of it.
