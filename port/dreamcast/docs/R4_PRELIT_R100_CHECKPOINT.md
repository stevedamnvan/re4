# D353: selectable static-room prelighting (isolated diagnostic)

Decision: promising for review; default off, not promoted to the recovered game.
Branch `experiment/r100-prelit-d353` starts from the untouched D349 reference
`5f42caa634c0e6124c48842e21570033738adfda`. Primary recovered-game HEAD is
`06567b3ac35e1409117170cf2999096b0f81e839` plus uncommitted D352 integration.
This experiment neither accepts that bridge nor completes source gameplay.

## Representation and source qualification

All 1,093 D349 r100 source groups select only world-space lights. The two
camera-relative lights have enable masks 0x47/0x06, excluding scenery bit0x10.
The existing renderer already prepares static contributions at room installation.
`bake_room_prelit.py` compiles the existing D349 evaluator, preserving selected
lights, accumulation and final clamp; it rejects camera-relative selection and
conflicting shared-vertex colors. Candidate RGB replaces the three normal floats
in the same 32-byte vertex. Flag bit1 declares that layout; both build arms reject
the wrong package. Geometry, UVs, textures, topology, source identities and actors
are unchanged. No second full color/geometry representation is resident.

This is **PS2-inspired prelighting, not transferred PS2 authored RGB**. The native
reference still has its documented historical facing/gameplay limitations; this
change neither fixes nor promotes those. Recovered source state remains authority.

40,419 vertices, 1,991,864-byte package in both arms. Reference SHA256
`a71c1ff16109ed8551697082e2f6ff8fc9f67eb4357f58f7fb40305e132e3a63`;
candidate `6a8355af1e1e651dc25cd51820f30da7f6483dc7c3146b8fd5ef4ac1c5cc5618`.
The bake reuses 485,028 bytes of normal fields, adds zero vertex storage, and finds
zero shared-color disagreement. Dynamic actor lighting remains enabled.

## PS2 inventory and limits

Private USA PS2 image and existing AFS inventory supplied six r100 scenario
members. The complete bounded inventory has 270 BIN entries: 142 COLOR, 6 NORMAL,
72 NORMAL_WITH_COLOR (rigid32), 50 NORMAL_GC_LAYOUT. Main COLOR entries have
92,838 records; rigid32 entries have 51,853 records; the GC-layout block has
16,431 source positions and 18,267 normals. Unique meshes and placed instances
are recorded separately. Per-entry offsets, materials, counts, instances and raw
RGB/normal/UV records are private in `inventory-v3`.

Reuse: JADERLINK RE4_PS2_SCENARIO_SMD_TOOL 1.3.0, source39fd0f, executable SHA256
`9fc3d21b164b2e7930eab4ec7e2eb93752758b811314c3c194101cfd7e19b610`;
existing DAT tool1.0.4 (4480c91) and existing GC bounds parser. The C# adapter calls
the pinned tool. Its decoder omits rigid32 records and mislabels six short cases;
the narrow inventory audit checks node/segment extents and attribute ranges, but
VIF qword fields price24-byte records versus actual32. Those 72 entries are NOT
qualified for repacking/runtime use. The mixed-endian GC-layout block is also
inventory, not proof of PS2 runtime residency. No new compression/export system.

Forest-ground correspondence: SMD000/SMX000/BIN129, matched D349 source_000.
Cabin spatial candidates include SMD024/SMX021/BIN090 (3,931 records, 80 native
batch correspondences) and SMD217/SMX078/BIN103 (2,299 records, 21 correspondences),
plus SMD218/BIN104 and SMD219/BIN105. These are geometric region identifications,
not certified wall/roof material names; event-switched objects are not silently
classified static.

At 0.2mm matched-position tolerance, 12,927 native vertices have unambiguous PS2
RGB correspondence; 7,943 have conflicting coincident colors and 19,549 no match.
9,359 matched RGB values require handling above1. Raw RGB channel mean absolute
differences from D349 final lighting are 1.17791/1.17632/1.16642. These are NOT
final PS2 image errors: texture/material modulation and edition differences are
unresolved. No averaging, clipping or direct PS2 transfer was promoted.

## Measured Flycast result

Ordinary 60-second autoplay arms use the same source, fixture, 640x480, textures,
KOS d336 and GCC15.2; no capture pauses or lifecycle runs in timing. CPU stage
intervals and PVR/presentation overlap are reported separately, not summed.

| Measure | A: D349 lighting | B: prelit room |
|---|---:|---:|
| Active-route CPU p50 / p95 | 48.880 / 57.627 ms | 46.387 / 53.312 ms |
| Active room-pass p50 / p95 | 13.356 / 21.939 ms | 10.861 / 17.620 ms |
| Settled CPU p50 / p95 | 57.569 / 57.625 ms | 53.245 / 53.324 ms |
| Settled room-pass p50 / p95 | 21.902 / 21.939 ms | 17.610 / 17.645 ms |
| Presentation p50 / p95 | about50.05 /66.73 ms | about50.05 /66.73 ms |
| Reported main free | 7,667,712 B | 8,302,592 B |
| ELF BSS | 5,578,132 B | 4,948,180 B |
| ELF text | 3,004,273 B | 3,000,797 B |
| Settled room vertex-light evaluations | 11,008 | 0 |

Reported main headroom grows634,880B; BSS shrinks629,952B and text3,476B.
This is the room target's native budget, not recovered source-heap recovery.
Room arena used/high-water3,343,712B and reservation3,440,640B are unchanged.
VRAM free3,030,856B and AICA free1,378,336B are unchanged. Settled8,315 room and
11,901 actor triangles,973,024 PVR bytes and370 calls are unchanged. B still
performs142 source-group light-selection queries; it performs zero room vertex
lighting. Actor lighting remains about16.2ms. No simulation time was discarded.
No material page-flip distribution gain or 30FPS acceptance is established.

Six exact-tick RGB565 captures (40,80,120,170,220,270) have equal actor state and
zero changed pixels across the full640x480 image. Visual runs are separate:
capture-only logic stops catch-up at the requested tick and freezes readback;
it is compiled out of timing builds. Reused corrected D314 VRAM address decoder.
V2 PrintWindow captures produced no images; V3 mostly missed matching ticks and
are excluded. V4 is the matched visual evidence. This is sampled image acceptance,
not all views, source-game integration, physical hardware or audio acceptance.

## Reproduction and private evidence

Worktree `/root/work/re4-r100-prelit-d353`; private inputs/output
`/root/probe/d353-ps2-r100-prelit`. Run the baker against the pinned D349 source
and reference package; run inventory with the pinned C# decoder and assembly.
Private `/root/probe/d353-build.sh a|b` builds serially (parallel staging races
are not qualified), using `r100-autoplay R100_PRELIT=0|1` plus historical disc
target. B supplies `R100_ROOM_PACKAGE=.../bake-v1/r100-prelit.re4room`.
Visual recipe `/root/probe/d353-build-visual-v4.sh a|b` uses the snapshot target.

Evidence under `D:/Flycast-Evidence/re4-dreamcast/`:
- `d353v2-a-prelit`, `d353v2-b-prelit`: timing ELF/disc/config/telemetry/identities.
- `d353v4-a-prelit-visual`, `d353v4-b-prelit-visual`: exact-tick images and reader.
- `d353-v4-comparison.json`: distributions and full-frame pixel differences.
Flycast SHA256 `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
Per-arm identities record exact binaries and selected assets; do not confuse
timing and capture ELFs. No source/derived artwork, packages or captures in Git.

Next primary work remains the complete recovered-game renderer stack: direct
strips/PVR cull, bounded local preparation, the two CPU-only pose flushes, and
resolving the observed presentation handoff. This modest lighting result is not
an explanation for its roughly one-second unlit baseline. No roadmap change.
