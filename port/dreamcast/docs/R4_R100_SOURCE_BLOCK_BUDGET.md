# R100 four-owner residency and replacement budget

Updated 2026-09-23. The user accepts the four reproduced owner-aligned packages
as the residency basis: MAINSCENARIO, FILE_00, FILE_01, FILE_02. Do not return to
the all-block conversion or invent finer streaming. This record is subordinate
to R100_NATIVE_CUTOVER_GOAL.md, not a new roadmap. The layout/target checkpoint is
[D364](R4_ROOM_PACKAGE_V4_CHECKPOINT.md).

## Existing source lifetime, confirmed from code and D362 RAM

`prepare_streamed_room_obj.py` selects whole source groups whose XZ bounds
intersect radius 180 at (-829.1,-384.8), limited to the four owner prefixes.
`convert_room_obj.py` then uses scale 0.1, source-unit scale 0.001 and 4-metre
cells, preserving the historical unpartitioned material list. Cells partition
triangles; they do not reduce geometry. Reproduction selects the same 58 source
objects and 30,895 triangles. The per-owner sum of v3 packages is 1,992,824 bytes;
the old combined 1,991,864-byte file shares more headers/material names.

`scroll.cpp::setObj(blk)` supplies the source SMD work index before model creation;
`SmdSetParam` selects local versus common BIN. The native stable key is owner /
work index / BIN / common, plus the runtime owner generation. SMX ID alone is
not unique. All 1,093 child groups have been mapped to those source identities.
The v4 source table stores them explicitly; diagnostic names are no longer RAM.

`checkBlockLoadToMram` binds the existing draw owner, then calls BlockCreate.
Destruction unbinds after destroying its objects. `moveBlockData` unbinds, copies,
rebases source object pointers and rebinds; a native package view must rebase on
that same boundary. A pointer into the old block must not survive compaction.
`checkCondition` retires/moves old data before required new MRAM loads and may
hold gameplay while loading. Do not create another streamer or overlap policy.

| Source connection | MRAM blocks | Authored source bytes |
|---|---|---:|
| 0 | 0, 1, 2 | 783,104 |
| 1 | 1, 2, 3 | 1,126,272 |
| 2 | 2, 3, 4 | 978,688 |
| 3 | 3, 4 | 754,240 |

D362 final RAM confirms blocks 0/1/2 in BLOCK_CREATE/MRAM_OK, 783,104 used
inside the 1,126,272-byte pool. Block 3's ARAM state is not proof of backing an
ARAM placeholder. The native package owners follow these exact sets; main is
room-owned. Blocks 3/4 and other unconverted source objects remain fallback.

## Source render backing opportunity, not yet a heap saving

The selected local BINs have no shape/flip dependency in the examined headers.
Only BINs whose source users are all converted were included in this span count:

| Owner | GX + position + normal bytes identified | v4 AoS package bytes |
|---|---:|---:|
| MAINSCENARIO | 28,604 | 106,724 |
| FILE_00 | 13,900 | 46,980 |
| FILE_01 | 349,168 | 1,000,874 |
| FILE_02 | 4,992 | 144,720 |
| Common BIN 11/13 | 6,136 | included in placed native objects above |

Common BIN 0/1/3/10/12 still have unconverted users and cannot be freed just
because selected objects no longer need them. UV, part/material descriptors,
source bounds and other remaining CPU readers are excluded from these savings.
`model.cpp::getBoundingBox/calcModelAddr`, shadow/mirror presentation and
diagnostic consumers still need qualified native handling before removing data.

Pricing those known spans out of the existing source blocks, with each native
owner rounded to 32 bytes, gives this conservative **model**, not a target heap
measurement or permission to allocate more:

| MRAM set | Modeled retained source | Native bytes (rounded) | Combined |
|---|---:|---:|---:|
| 0/1/2 | 415,072 | 1,192,640 | 1,607,712 |
| 1/2/3 | 772,128 | 1,145,632 | 1,917,760 |
| 2/3/4 | 973,696 | 144,736 | 1,118,432 |
| 3/4 | 754,240 | 0 | 754,240 |

The modeled peak block pool is 791,488 bytes larger than the current pool.
Main adds 106,752 rounded native bytes while 34,740 candidate main/common source
bytes are removed (34,720 after rounding the smaller source archive). Total
modeled increase is 863,520 bytes before additional adapters or staging.
D362's recorded 116,704 free/largest does not fund it: the modeled remaining
shortfall is 746,816 bytes. This is **not** an actual failed candidate allocation,
and it does not account for unrelated lifetimes or unqualified additional source
removal. Actual recovered-game source backing removed by D364 is **zero**.

The v4 saving is real encoded/native payload saving against these same four v3
packages; it is not a claim that the recovered game now fits. Keep the same four
owners. FILE_01 dominates the residual cost. The user authorizes qualifying
lower-cost GC/PS2 geometry/material inputs at this measured expensive boundary;
do not start another lossless-array hunt or change ownership to hide the gap.
Before activation, complete the source-reader replacement and exact pool/staging
measurement. Escalate only if this accepted representation/lifetime still cannot
fit after justified replacements/authorized assets, or a new ownership/streaming
architecture is required. Do not silently enlarge the source heap or budgets.

## Current asset-budget decision

The user activates FILE_01 reduction on this modeled deficit. AoS20 is the
leading v4 layout; no more Split24/SH4ZAM layout tuning is scheduled. Keep the
four accepted owners. Compare the exact FILE_01 set as GC v4, qualified PS2
geometry/materials and custom DC reduction, using the existing conversion path.
Decompose its geometry/color, textures, materials/alpha, opening residency,
removable source backing and emitted/prepared work before selecting reductions.
Target roughly 900 KB-1 MB gross reduction/headroom if feasible, then price
actual source-pool sizing, archive recovery, staging and remaining margin.
The detailed sequence and escalation boundary live in R100_NATIVE_CUTOVER_GOAL.md.
No texture/VRAM saving may be counted as source-heap recovery without its actual
CPU ownership change. This decision changes no accepted evidence or allocation.

## Evidence

Private `/root/probe/d364-native-r100/source-block-trace/trace.json` records BLK
sets, source SMD/BIN mapping and the captured RAM state; `selected-backing.json`
records source spans and common users. `slices-v1/reproduction.json` records
the exact original converter commands and hashes. D362 RAM SHA256:
32d363cd666f1e5516a2dacd0868c467e18a11f0e64d74023d33f1ee424ac0c5.
No full reference/native scene was installed alongside the recovered game.
No new source loader or streamer was introduced.
