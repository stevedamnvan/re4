# R4 deliverable 4: the authored residency model for r100 and its connected room

Status: measurement and design only. No runtime change, no streaming. The
accepted build is untouched and still reproduces `68f720cd...b412c296`.

Three results decide the shape of deliverable 5.

1. **r100 connects to exactly one room, r101, and the pair is symmetric.**
   There is no choice of first transition to make and no synthetic room is
   involved.
2. **The source never holds two rooms resident.** A room change frees the room
   heap wholesale and then loads the next room behind a fade. Transition overlap
   in the original is zero by construction, not by budget.
3. **Nothing in the current Dreamcast build can be reclaimed at all**, because
   every package is memory-mapped out of a romdisk linked into `.rodata`. The
   transition does not fit today, and the blocker is architectural rather than
   arithmetic. Single-room residency fits with about 5.1 MB to spare once
   deliverable 5 removes the embedded romdisk.

## The connection, from the authored data

The door table is the room archive's `AEV` sub-file, which
`src/game/game.cpp` hands to `SceAtInit`. Records are `SceAtWork`, stride
0x9C, big-endian; area type is the byte at +0x35 and type 1 is the door
handler `sceAtFunc_door`, whose payload carries `dstStage` at +0x6C and
`dstRoom` at +0x6D. Every stage-1 `AEV` parses to exactly its byte length.

| | |
|---|---|
| r100 doors out | exactly one, to r101, part 0, door 0, unlocked |
| doors into r100 | exactly one, r101 area 0, part 0, door 0, unlocked |
| r100's place in the graph | a leaf: one entrance, one exit, both r101 |

The full stage-1 door graph was decoded as a cross-check. Stage 1 holds 28
rooms with an `AEV`; `r120` has none and is not navigable. The only authored
locks in the whole stage are r108→r117, r117→r118 and r118→r117, and the only
cross-stage door is r10f→r200. r100 is the simplest possible case in the stage.

A caveat worth keeping: this is the authored `AEV` data. A room script could in
principle create a door at run time through `SceAtSetDoorFunc`. For r100 this
does not happen; `src/st1/r100.cpp` sets door **flags** and a door message but
creates no new door area.

## The authored active, staged and evict sets

Intra-room residency is the `BLK` file, described by `include/block.h`:
a link table of blocks, trigger areas, and a connect record per area. **r100 is
the only room on the entire disc with streamed block files.** Its five blocks
are `St1/r100_00.dat` through `r100_04.dat`, each an uncompressed tagged
archive holding a single `SMD` chunk, so the on-disc size is the resident size.

The sets are *derived*, not stored. `cBlock::checkBlockConnect` puts the area's
own block plus its link-table neighbours in MRAM, then everything one hop
beyond that in ARAM minus whatever MRAM already holds. The per-area `mram[8]`
and `aram[8]` arrays are **overrides applied to the ARAM set**, and their names
are misleading: entries in `mram[]` are switched *on* in ARAM and entries in
`aram[]` are switched *off*. All four of r100's connect records leave every
override at -1, so r100's sets are purely derived.

r100's link table is a plain corridor, 0-1-2-3-4, with four trigger areas.

| block | bytes |
|---|---:|
| `r100_00.dat` | 28,448 |
| `r100_01.dat` | 530,208 |
| `r100_02.dat` | 224,448 |
| `r100_03.dat` | 371,616 |
| `r100_04.dat` | 382,624 |
| total | 1,537,344 |

| trigger area at block | active (MRAM) | bytes | staged (ARAM) | bytes | evictable |
|---|---|---:|---|---:|---|
| 1 | 0, 1, 2 | 783,104 | 3 | 371,616 | 4 |
| 2 | 1, 2, 3 | **1,126,272** | 0, 4 | 411,072 | none |
| 3 | 2, 3, 4 | 978,688 | 1 | **530,208** | 0 |
| 4 | 3, 4 | 754,240 | 2 | 224,448 | 0, 1 |

`cBlock::checkBlockMemory()` is the source's own peak calculation: it walks
every trigger area, sums that area's MRAM blocks and allocates one pool of the
maximum. For r100 that pool is **1,126,272 bytes**, and the staged tier peaks at
530,208 bytes.

r101's `BLK` is a 32-byte stub with `nBlock` 0, so r101 is a single-block room
and `checkBlockMemory()` allocates nothing for it. So does r10d, and so does
every other room on the disc.

**The consequence for the Dreamcast is favourable and should be stated
plainly.** The staged tier exists to hide GameCube ARAM, which the Dreamcast
does not have, and the plan already forbids treating AICA memory as its
substitute. But the whole of r100's block data is 1,537,344 bytes, and the port
already holds all of it resident inside a single converted room package. The
block model is therefore a latency optimisation we do not need at this size; it
becomes relevant only for rooms larger than r100, of which there are none in
stage 1 by this measure.

## Always-resident against room-specific

Classified from how each resource is used, not from its name.

| always-resident | romdisk bytes | VRAM | AICA |
|---|---:|---:|---:|
| Leon character and animation | 1,717,480 | - | - |
| Leon textures | 228,528 | 221,184 | - |
| weapon | baked into Leon | - | - |
| weapon audio, 3 cues | 193,950 | - | 193,856 |
| player voice, 4 cues | 164,240 | - | 164,096 |
| HUD layout | 4,680 | - | - |
| HUD glyph atlas | 290,192 | 287,744 | - |
| **total** | **2,599,070** | **508,928** | **357,952** |

The weapon deserves a note: it is not a separate package. The handgun is a
rigid attachment baked into Leon's mesh with its own muzzle and axis markers, so
it is inseparable from Leon's residency and cannot be swapped on its own.

| room-specific | romdisk bytes | VRAM | AICA |
|---|---:|---:|---:|
| room geometry | 2,220,388 | - | - |
| room textures | 1,983,504 | 1,978,368 | - |
| room collision | 183,600 | - | - |
| room navigation route | 6,128 | - | - |
| Ganado character and animation | 1,162,072 | - | - |
| Ganado textures | 116,080 | 114,688 | - |
| Ganado audio, 4 cues | 164,346 | - | 164,256 |
| **total** | **5,836,118** | **2,093,056** | **164,256** |

Room-specific content is 69.2% of the romdisk, 80.4% of unique VRAM payload and
31.5% of AICA. The room texture package alone is 76% of texture memory.

## Current converted sizes and VRAM payload

Romdisk total 8,435,196 file bytes in a 8,436,736-byte image. Texture payloads
after the R4e sharing change:

| package | descriptors | unique payloads | per-descriptor bytes | unique bytes |
|---|---:|---:|---:|---:|
| room | 53 | 53 | 1,978,368 | 1,978,368 |
| Leon | 76 | 11 | 1,417,216 | 221,184 |
| Ganado | 14 | 4 | 425,984 | 114,688 |
| HUD | 25 | 25 | 287,744 | 287,744 |
| **total** | **168** | **93** | **4,109,312** | **2,601,984** |

93 unique payloads matches the 93 recorded allocations exactly. All 93 have
distinct content hashes, so cross-package sharing is still worth nothing. Every
payload ships twiddled, so upload is a raw copy.

Free VRAM is reproduced exactly by `payload + 32 × allocations + 24` at both
the pre-sharing and post-sharing measurements, which pins the PVR allocator's
per-block cost at 32 bytes and validates the whole texture accounting.

## Working-set estimates and the headroom question

The measured RAM map of the accepted build sums to 16,777,216 bytes exactly.
The decisive line in it is that the romdisk is 8,436,736 bytes of `.rodata`,
77.3% of the loaded image. Every package is opened with `fs_open` plus
`fs_mmap` and accessed through `reinterpret_cast` over the mapping; nothing is
copied and nothing is freed, in all six package classes. **So today no room
byte is reclaimable, and a second room cannot be installed at any size.**

Once deliverable 5 reads packages into an arena and the romdisk leaves the
image, the budget becomes:

| | bytes |
|---|---:|
| image without the romdisk | 2,478,548 |
| RAM left for heap and arena | 14,167,596 |
| arena ceiling at today's heap | 13,790,208 |
| always-resident | 2,599,070 |
| **budget for room content** | **11,191,138** |

r100's room-specific set is 5,836,118, or 52% of that budget.

r101's converted size is estimated from its source chunks using r100's own
measured conversion ratios, geometry 0.658, textures 1.294, collision 1.072 and
route 1.008:

| | r100 source | r100 converted | r101 source | r101 estimate |
|---|---:|---:|---:|---:|
| geometry | 3,375,424 | 2,220,388 | 3,076,288 | 2,024,000 |
| textures | 1,533,216 | 1,983,504 | 252,512 | 327,000 |
| collision | 171,232 | 183,600 | 122,880 | 132,000 |
| route | 6,080 | 6,128 | 12,544 | 13,000 |
| **room archive part** | | **4,393,620** | | **~2,496,000** |

r101 carries far less texture data than r100 despite 1.7× the geometry, which
is the single most useful number here. Its enemy set is not yet estimable: enemy
packages come from `em/`, not from the room archive, and r101's enemy tables are
2.35× r100's, so budget 1.5 to 3.5 MB and treat the range as open until r101's
enemy list is read. That puts r101's room-specific total at roughly 4.0 to
6.0 MB, comparable to r100's 5.8 MB.

| scenario | resident RAM | verdict |
|---|---:|---|
| single room, always-resident plus r100 | 8,435,188 | fits, 5,355,020 spare |
| single room, always-resident plus r101 | ~6.6 to 8.6 MB | fits comfortably |
| both complete rooms resident | 12.6 to 14.6 MB | **marginal to over**, ceiling 13,790,208 |

VRAM and AICA are not the constraint. Both rooms' textures at r100's full size
would consume 4,695,040 of 5,635,840 bytes, and two room audio sets plus the
always-resident set reach 686,464 of 1,900,544. Main RAM is the binding limit,
and dual full-room residency sits right on it.

## Reclaim and sharing at the transition

Reclaimable immediately once the previous room is left: the entire
room-specific table above, 5,836,118 RAM bytes, 2,093,056 VRAM bytes and
164,256 AICA bytes for r100. There is no partial case, because r100's only
neighbour shares none of its room-specific resources: all 93 texture payloads
across all four current packages have distinct content hashes, so no room
texture survives into r101 by identity.

Must remain resident: the always-resident table, 2,599,070 RAM bytes, 508,928
VRAM bytes and 357,952 AICA bytes. Leon, his baked weapon, his voice set and
the HUD atlas persist across every transition by definition.

So the answer to the headroom question is yes, and without dual residency:
**peak = always-resident + max(room A, room B) + one bounded read buffer**,
which for this pair is about 8.6 MB against a 13.79 MB ceiling. Keeping both
rooms resident is neither necessary nor reliably affordable, and the source
does not do it.

## The storage path the source intends

Room content is one compressed `.das` archive per room under `St1/`, read
through the data controller, plus uncompressed per-block `.dat` files named
`st%x/r%03x_%02x.dat` for the one room that has them. Inside an archive a
resource is addressed by `GetDataExt(archive, tag, ordinal)` over a tag table,
so **the source's own resource identity is (archive, three-letter tag,
ordinal)**, not a filename.

That is the identity the residency model should adopt, paired with the content
digest the plan already requires for sharing and reference counting. It
generalises to every room without a bespoke loader, because every room archive
has the same tag vocabulary; r100 and r101 differ only in which tags are
present and how large they are.

The heap model reinforces it. `main_mem` carves nested logical heaps, system,
game, stage, DLL, then room, and `gameRoomMemInit` re-carves the room heap from
its parent at every transition. Always-resident content lives outside the room
heap entirely. A Dreamcast arena with the same nesting, one region released in
a single operation at the transition, reproduces the authored lifetime exactly.

## What this settles for deliverable 5

The transition fits, so deliverable 5 is unblocked, with its shape now fixed by
measurement rather than by choice:

- Target the r100 → r101 transition, and get r101 → r100 almost free, since the
  door pair is symmetric and unlocked.
- Size the staging arena for one room, not two. Free the outgoing room's
  region before installing the incoming one, behind the authored fade, exactly
  as `gameDoordemo` does.
- Key resources by (archive, tag, ordinal) plus a content digest.
- Do not implement the ARAM staged tier. It has no Dreamcast counterpart, and
  r100's entire block set is 1,537,344 bytes, which the port already holds
  resident in one package.
- The first real work is removing the romdisk from `.rodata`. Until that
  happens no room byte is reclaimable and no measurement of a transition is
  meaningful.

## Corrections and open items

- The romdisk filenames `r10d.re4room` and `r10d.re4sat` are legacy labels from
  an earlier slice. The `r100-autoplay` target overrides every package variable
  and ships r100 content. Renaming them is a small, separate cleanup.
- `tools/asset_residency_report.py` is stale: it rejects the shipped v2
  96-byte texture record and fails on every accepted package. It needs updating
  before deliverable 5 relies on it.
- r101's enemy set is unread. Reading its enemy list closes the only open range
  in the budget table above.
- r101's geometry has no large paired texture chunk, unlike r100 and r10d. The
  chunk inventory sums to within 320 bytes of the archive's unpacked length, so
  nothing is missing, but the reason r101 needs so little texture data is worth
  confirming before its conversion is sized for real.
