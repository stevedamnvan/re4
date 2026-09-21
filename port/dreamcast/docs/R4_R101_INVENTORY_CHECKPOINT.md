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

Two further hard limits in the current runtime:

* `kRoomStaticLightingVertexCapacity` is **45,000** (`main.cpp:2821`), and
  `prepare_room_static_lighting()` refuses any room above it. r101 has 177,032
  vertices, 3.9x over. Raising the cap to fit r101 costs 14 bytes per vertex in
  `.bss`: 2,478,448 instead of 630,000, another 1,848,448 bytes against the same
  budget.
* `kRoomBatchSlotCapacity` is 1,024 against r101's 3,811 batches and
  `kRoomVertexCacheCapacity` 2,048 against 177,032 vertices. Both are caches, so
  they degrade rather than fail, but they would thrash.

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

r101 and r100 share **no** enemy id, so nothing carries over. The archives are
`em15.drs` 5,970,784, `em26.drs` 363,712 and `em28.drs` 228,928 on disc; at
r100's own em12 conversion ratio (5,664,736 archive to 1,278,152 converted
model plus textures) that is roughly 1.5 MB converted, the bottom of D4's range
— but only for one model each, and r101's fight is 43 simultaneous em15
entries with reset waves.

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
   left them embedded. Removing them frees about 2.6 MB of `.text` and raises
   the budget toward the 13,790,208 ceiling. r101's 12.03 MB plus 1.85 MB of
   extra static-lighting arrays plus enemies still exceeds it.
2. **Reduce r101's fidelity.** A 128-pixel texture limit takes 2.99 MB to about
   0.9 MB. Geometry has no equivalent lever short of partitioning.
3. **Partition the room and load part of it**, which is intra-room streaming —
   the asynchronous work this checkpoint was told not to make a prerequisite.
4. **Pick a different first transition.** r101 is r100's only authored
   neighbour, so this means abandoning "the smallest real connected transition"
   in favour of a pair that fits, which contradicts the D4 instruction to use
   the authored relationships.

Option 2 alone is the only one that fits without new machinery, and it buys
2.1 MB against a 0.84 MB overshoot plus 1.85 MB of lighting arrays — that is,
it is close but needs measuring rather than assuming.

## What was built

`Makefile.host` gains `room-r101-source`, `collision-r101-source`, `route-r101`,
`texture-r101-source` and the aggregate `room-r101`. They use the same
converters and the same settings as r100, with none of r100's per-material
overrides, which are r100 geometry decisions. The r101 chunks live under
`orig/G4BE08/rooms/r101/`, extracted from the private disc and ignored like the
rest of it.
