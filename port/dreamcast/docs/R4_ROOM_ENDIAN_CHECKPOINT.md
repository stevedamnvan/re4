# D297: decoded room mirror and source collision layout


## D305: qualified r100 reaches source room allocation (2026-09-21)

Keep the existing prepared-room boundary. All required r100 archive entries now
qualify; the recovered game consumes its 4,669,568-byte archive through normal
ReadAreaData/gameRoomInit. The original DVD container still dispatches ROOM and
FOOT MRAM/ARAM sound blocks. No compressed geometry or decode scratch buffer is
loaded beside the archive. Sound transport is not proof of audible output.

The mirror now handles source ETS placements, EAR/SAR volumes, AEV/ITA triggers,
RTP routes, STB curves/reverb, ESE emitters, DSE door sound IDs and bounded EMI
records. Effect model/motion bodies reuse existing BIN/TPL/FCV handlers. Source
EspGenPrm word/halfword/byte views and EtcSetData's slot/type union retain their
numeric meanings on SH-4; the PowerPC declarations are unchanged.

Qualification remains conservative. Only the observed 1408-byte all-zero OSD
and authored empty DRA lists qualify; this is not general OSD/DRA support.
Unknown trigger types, nonzero runtime pointers, extra EMI work and effect
shape bodies remain rejected. r101 still has an incomplete EVS region, so its
native DAR stays absent. Two legacy core SAT errors remain explicit.

EAR uses area_no 255 on interior volumes. The original DOL's EffAreaUpdate and
AreaSstSet use PPC slw: low six shift-count bits, zero for counts 32..63. Native
code reproduces that rule instead of relying on undefined C++ shifts. Original
instruction inspection and a PPC execution fixture cover all 256 byte counts;
255 contributes no effect bitmap bit, while the interior flag still applies.

Validation: 40 room-format, nine mirror, two native-loader and two opening-skip
tests pass; the recovered game builds with six pre-existing missing-symbol
stubs. Tests cover mixed union views, sharing/bounds, signed route sentinels,
malformed data rollback, trigger pointer rejection and unsupported variants.
PowerPC preprocessing of the two changed source functions matches the prior
checkpoint; this is not a fresh full ProDG object comparison.

The 55-second scripted Flycast replay reaches the next exact failure:
- Room heap: 0x8c8cfa60..0x8cf9a200 (7,120,800 bytes).
- Two collision-manager requests: 0x1680 bytes each, 0x1120 free.
- Event data-table request: 0x4b00 bytes, 0x6a0 free.
- Later allocations also fail; successful room initialization is not established.

Next: account for initialization allocations, primitive-buffer demand and
resource lifetimes, then fix demonstrated target overhead. Do not arbitrarily
halve gameplay pools or bypass missing source systems. `read_us=0` is an invalid
stopwatch result, not a loading-time measurement. No visible recovered-game
room, manual play, real-time performance or physical-hardware acceptance yet.

Private evidence: `C:\Flycast-Evidence\re4-dreamcast\d305-qualified-r100` contains
paired ELF/disc/assets, mirror report, build/package logs, exact dirty patch,
symbol offsets, scripted capture and identity manifests. Fixture:
`/root/probe/d292-fixtures`; disc build: `/root/probe/d305-disc`.
Toolchain: SH GCC 15.2.0; KOS 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3.

| Artifact | SHA-256 |
|---|---|
| ELF | c0d18deb88a70c8573d4cf8c7cf843430448ee6adf69fbc3236fb721e1c6ef09 |
| Disc | 0dd3c281fc22ee83e4cccb6a48e3ed1a44e6c5b9d1023b8d90ea42680fc15daa |
| r100.dar | 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739 |
| Flycast | 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a |

## D304: source model packs, residency and motion conversion (2026-09-21)

Offline qualification advances the normal r100 loading dependency without
changing the recovered executable or accepting incomplete data. Added ITM
item-id/BIN/TPL tables and BLK authored area/link/working-set records to the
existing mirror. Both r100 and r101 ITM/BLK regions qualify. ITM shares the
existing model and texture handlers, bounds each resource to its table region,
and preserves shared offsets. BLK retains signed byte lists, original area
ordering/priorities and source residency choices; this is not a new streamer.

ETM named object archives now dispatch their BIN/TPL/EFF/FCV/SEQ members through
existing handlers. An unknown or incomplete member keeps the archive and room
unqualified. This exposes the exact remaining effect dependencies instead of
leaving the whole container opaque. No texture, model, collision or gameplay
substitution was made.

FCV conversion reuses `tools/motion/fcv.py`, the existing codec used by the
real-motion fixture. It requires a byte-identical big-endian parse/serialize
roundtrip before emitting the same-layout little-endian image. All ten source
key encodings remain intact; no resampling, key reduction or precision change.
The existing codec now preserves uniform zero alignment padding found in named
ETM members, alongside the existing 0xCD variant. Other unexpected trailing
bytes are rejected. Motion SEQ conversion swaps only counts/frame values;
sound/event bytes remain unchanged. SMD motion references use the same handler.

Validation:
- 31 room-format tests, nine mirror tests and two native-loader boundary tests
  pass. Fixtures cover shared resources, bounded offsets/counts, malformed
  references, all key types, non-joint file order, both padding forms, sequence
  event bytes, and incomplete nested members.
- Real mirror qualifies all 163 tagged FCVs. An independent raw-width check
  compared 2,103,153 scalar fields across those and 21 named motions; numeric
  bits reverse exactly and untouched bytes agree. Five named motion sequences
  retain their frame/sound/event values. This checks file interpretation, not
  live pose evaluation or gameplay.
- r120.dar is byte-identical to the frozen D302 reference. r100.dar/r101.dar
  remain absent. r100 incomplete tagged regions decrease from 24 to 14.
- No game-source change, new ELF, emulator replay, performance measurement or
  manual-play acceptance in D304. Last executable/replay remains D303. A replay
  of the still-rejected r100 package would not advance that frontier.

Keep this conversion work. Next required r100 regions are EFF and ETM effect
payloads, ETS placements, EAR/SAR areas, AEV interactions, RTP routes, STB/ESE/DSE
audio data, OSD, DRA, ITA and EMI. ETM's remaining blockers are effect parameter
unions/model bodies, not motion conversion. Inspect current source consumers;
keep every unsupported required field rejected. Once qualified, build its DAR
through the existing path and replay source gameRoomInit. Visible menu/native
rendering/audio, memory fit, manual play and three-room completion remain open.

Private evidence: `C:\Flycast-Evidence\re4-dreamcast\d304-room-model-motion`:
conversion report/log, source/native asset hashes, independent verification
script/results and exact candidate patch. No private asset bytes are committed.

## D303: first-play cinematic completion reaches r100 (2026-09-21)

The native game now handles the authorized first-play opening skip before
r120 room allocation, after normal New Game initialization, costume choice,
stage setup and REL loading. This is a bounded completion adaptation of the
source opening-movie skip path: R120Event's Sofdec bit 0x20 sets Scenario[0]
0x10, skips both car events, then sets System 0x400 and requests r100 at
(-109450,-515,820), yaw0/part0. No EVD commands execute on that source branch.

The native helper preserves the persistent completion/transition state:
r120 passed marker, previous room/part, intro skip flag, authored next/current
room and player position, transition counters, and cleared entry flags. It
returns to gameStageInit, so r100 uses normal stage/module/enemy-list/save and
prepared-room loading. It never creates r120 scene objects, event nesting,
locked controls or temporary camera/light state, so it does not invoke teardown
on absent objects. GameCube code is unchanged behind the target guard. Health,
inventory and pesetas remain with normal gameInit; no gameplay system is stubbed.

Scope guard: room120, first play (game_cnt0), New Game flag0x2000, Leon. New
Game Plus's preceding merchant interaction and existing-save entry are unchanged
and remain outside this adaptation. These paths are not newly accepted. D302's
frozen ELF remains the direct qualified-r120 transport/initialization reference.

D303 55-second Flycast fixture confirms:

```
-- R120 ----------
module: id 74 -> st1_0 (static)
Native opening skip: r120 -> r100 at (-109450,-515,820); source completion
-- R100 ----------
Native room load failed: st1/r100.dar status=-1
RE4DC MISSING: qualified native room container missing or invalid called; halting
```

No r120 archive is read in this run. The next dependency is r100's remaining
source-format conversion (not a new loader or another r120 allocation fix).
Its incomplete archive is still rejected before use. The route has not reached
completed playable initialization, visible output, combat or retry acceptance.

Two focused tests execute the actual helper, test nonmatching room/NG+/load/
character guards, repeated-call behavior, persistent handoff and untouched
player values, plus pin the source skip/position contract. Game build passes
with the same six pre-existing stubs. This is not a dual-emulator state oracle
or a full ProDG comparison. Source cutscene completion beyond this opening
still needs individual contracts.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d303-opening-skip`, with boot log,
ELF/disc hashes, build log and unchanged D302 asset manifest. Toolchain/Flycast
identities remain those of D301/D302. ELF SHA256 `433d91447da686745f09b1892897b2c83c20df5c64519f0d0f8925f27f96cc16`.

## D302: recovered game consumes the prepared r120 room (2026-09-21)

The existing offline decoder and mirror are retained. Added source-layout SHD
placement/model, TEX texture-table, FSE area/BGM and EFF sequence conversion.
SHD reuses fmt_bin and TEX reuses fmt_tpl. Unknown nonzero effect parameter
unions remain explicitly incomplete without rolling back already handled EFF
fields. r120 FSE is the source's zero-header sentinel. Its two type-0 SMX work
blocks remain opaque: obj02::moveNormal does nothing and r120 installs no scroll
callback or work reader. This contract applies only to r120; other rooms retain
callback rejection. Native SstList byte-id order now agrees with numeric no;
PPC member order is unchanged.

All 13 r120 tagged entries and its archive qualify. r100/r101 still reject
incomplete formats. A 55-second replay through the existing title/New Game
fixture logs:

```
DVD: Read File: st1/r120.dar
DVD: Mem Alloc: 8c8cfa40 Size:005ce020
DVD: Trans MRAM addr: 8c8cfa40 size:005ce020
DVD: Read Ok 801
Native room: st1/r120.dar bytes=6086688 read_us=0
alloc[69f20]:free[1b0e0] main_mem.cpp(646)
...
cDatTbl::init : memory failed
EventMgr::init : memory failed
```

This establishes actual prepared-archive transport and entry into the recovered
`gameRoomInit` consumers (constants/scene metadata and manager initialization).
It does not establish completed initialization, rendering or manual gameplay.
The first failed allocation matches ObjMgr: 241 SMD objects + 200 default extra
objects, each 0x3d8 bytes, rounded request 0x69f20 (433,952), while reported free
heap is 0x1b0e0 (110,816). Subsequent sprite/controller/light pools fail, the
source primitive buffer repeatedly shrinks, and DatTbl::init's 0x4b00 request
fails with 0x840 free. Do not count these failing consumers as working systems.

Heap 4 spans 8c8cfa20..8cf9a1c0 = 7,120,800 bytes. The room consumes 6,086,688
payload bytes once, plus allocator overhead; at most 1,034,112 remain before
subsequent allocations. Compressed geometry is retained only on disc, never in
the heap. This is a measured load footprint/exhaustion boundary, not a complete
loading/restart peak certification. The printed read_us=0 is invalid timing:
shared stopwatch/layout behavior needs correction before using it as a metric.
The queue's elapsed counter is supporting evidence only.

Sound dispatch remains the original DVD path. This r120 container has only a
type-0 room entry and no sound blocks; the replay still dispatches earlier
player/core/title sound loads. Nested room-sound semantics have structural
fixture coverage, not an r120 sound claim. A room containing sound must exercise
that path later. Retry, GPU retirement and peak residency remain open. The
existing room/ arena, transient texture upload and GPU fence implementations
were inspected and remain the reuse reference; source archives keep source heap
ownership and are not replaced by viewer package formats.

Checks: 22 room-format, 9 mirror and 2 native-loader tests pass; game build
passes (six pre-existing stubs). KOS/GCC/Flycast identities unchanged from D301.
Private evidence: `C:\Flycast-Evidence\re4-dreamcast\d302-qualified-room`
contains boot log, ELF/disc, qualified archive, full asset manifest, hashes and
build/conversion logs. The source comparison here preserves guarded PPC member
layout; no new full ProDG comparison or physical-hardware run is claimed.

Next main work: resolve the source initialization memory demand, preserving
required systems. r120 is cinematic staging, so trace the authorized source
cutscene-skip/completion path before committing a large cinematic working set.
Do not reduce default gameplay pools arbitrarily or import PS2 gameplay.

ELF SHA256 `63c17a503d33ccd5fe3c53eebaa028d4372c17273397d4f1a3bedf553c4baa7e`; archive SHA256 `870a05c972ce00ec197fcac227ca8f710c2598b0273cd308a68ea764b57c0457`.

## D301: native room loading boundary (2026-09-21)

The non-PPC `ReadAreaData` now reads prepared `stX/rNNN.dar` containers with
source DVD mode `0x8104`: headered, interrupt-task, main-heap allocation. The
queue allocates the final room payload and dispatches the original nested
sound blocks in order. No compressed-room allocation or YZ2 scratch/decode is
needed. `ReadCheckInfo` supplies the room entry's own pointer/size, not the
aggregate transfer size (which includes sound). Allocation/read errors fail
explicitly rather than entering the old endless poll. The existing resident
room flag still bypasses reading and resolves the four source subfiles.

`le_mirror.py --native-rooms` extends the existing builder (implies decoded
sidecars). It emits `.dar` only when all decoded archive and sound dependencies
report explicit complete coverage. It replaces the first type-0 header with
an appended, aligned converted archive; nested sound headers, offsets and bytes
stay unchanged. Old compressed bytes remain on disc only, never loaded. Later
disc-space repacking is optional. A rejected rebuild removes the exact older
generated `.dar`, preventing stale packages from hiding conversion failures.

Validation: 17 room-format tests, 9 mirror tests, 2 native-loader tests passed.
The loader tests compile its actual body and exercise delayed completion,
request/read failures and already-resident state. The PPC-preprocessed room
body equals d75144c (not a full ProDG comparison). Native game build passes;
six pre-existing generated stubs remain. GCC 15.2.0, KOS
`804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`.

55-second scripted Flycast replay reaches source R120 module 74 and player
loading, then logs `Native room load failed: st1/r120.dar status=-1` and the
explicit missing-qualified-container halt. This verifies the failure boundary
and preserves the previous boot frontier, **not successful room loading**.
All three current `.dar` packages are correctly rejected. r120 still needs
SHD, EFF, TEX, FSE and two SMX callback-work records qualified. Source cutscene
completion adaptation remains in scope; r120 is cinematic staging, not counted
as one of the three playable rooms. GX/audio placeholder coverage remains open.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d301-native-room-load`, including
boot log, exact ELF/disc, asset SHA256 manifest, conversion report and build log.
Fixture `/root/probe/d292-fixtures`; staged disc `/root/probe/d301-disc`.
ELF SHA256 `3ad2846530c9b938e6b28b2b89b9a4ffae27e3ad8aecf56a9953aa7eab57c36f`;
disc `da4db4b8cf604195b4a05355f2d6044ff8f5cf00677ffaaaee5cf3416c085b7e`.
Flycast `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
No manual-play, render-performance or physical-hardware acceptance is claimed.

Keep the boundary. Next qualify remaining required room formats, emit a real
`.dar`, replay the normal entry and measure final allocation/room initialization.
Do not rebuild a decoder or bypass sound. Retry/residency remain unverified.

## D300: camera, lighting and source light paths (2026-09-21)

The mirror converts CameraData B402/B403/B404 record links, hit polygons,
authored positions/targets, roll/FOV, floor ratio and interpolation times.
All three room CAM blocks pass. The core EMPT sentinel stays bytes. Only
Hermite types 6/7 consume frame-key arrays: source shoulder type 8 contains
stale debug pointers in that unused field. Those values are preserved, not
followed as arrays. Empty cuts do not dereference empty arrays.

All 16 available LIT blocks convert using cLightEnv/cLightWork and light01..08 /
foot_shadow layouts. Colors, flags and source-defined opaque padding remain
bytes; numeric fields and known per-type work are swapped. LightFuncTbl static
types do not consume their work tails. Type16 remains explicit unsupported work.
The native light parent union preserves numeric ParentNo and named parent/part
halves; PowerPC preprocessing is unchanged. This corrects data interpretation,
not source light-selection or runtime rendering behavior.

Correction to D299: `etc/core.das:0#11` is not a legacy model. ArcFile.ofs_3C and
cLightMgr::getPathPtr identify it as light brightness paths despite its BIN tag.
Its byte count, offset table and terminated byte sequences now have a scoped
consumer-specific handler. The two legacy core SAT layout errors remain open.

Sixteen room-endian tests and nine mirror tests pass; the game builds. The
existing read_env/read_light field comparison matched 97 cuts / 724 lights
between original and converted files. Source NaN bit patterns in unused spot
fields were preserved (numeric NaN equality alone is not a valid comparison).
This is a data comparison, not a rendered or runtime selection test.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d300-light-camera` contains
archive identities/copies, mirror report, light comparison results and refreshed
build log. Current sources/tests survived a temporary-directory cleanup; focused
checks and build were rerun before committing. Last target replay remains D295.

Next: native room loading and remaining required formats (SHD/EFF/TEX/FSE,
SMX callback data and source animation/FCV). Keep original nested sound handling.
Do not gate gameplay on unused padding, but do not reinterpret live unknown
fields or treat the incomplete whole-room archive as qualified. The main-menu,
three playable rooms, rendering/audio, transitions/retry and hardware gates
remain open; this checkpoint does not narrow that objective.

## D299: original model arrays and morph deltas (2026-09-21)

The mirror now converts source ModelData/BIN versions 0x20010801 and 0x20030818:
section offsets, joint centers, compact position/normal arrays, weight palettes,
texture coordinates, part lengths/statistics, motion blend/flip tables and morph
delta lists. Byte joint identities, ordinary weights, RGBA8 colors, signed-byte
normals and GX command streams remain bytes. Original position, normal, UV,
weight, part and primitive identities remain separate. No mesh reduction,
flattening or baked-pose replacement is introduced.

SMD invokes the model converter within each resource's own bounds, including
referenced textures. All nine available SMD regions now report complete for the
known data layouts. Of 422 tagged BIN regions, 421 convert; one legacy core BIN
(`etc/core.das:0#11`, version word 0x2c020202) remains rejected and raw. The two
legacy core SAT errors remain. SMX callback work and other room formats still
block full archive qualification. Model/morph data conversion does not implement
missing animation runtime or native GX draw integration.

Do not bound an attached model's weight joint IDs by its local nParts: these IDs
can address the owning model's rig. Influence counts remain checked. Source
morph lists preserve every vertex index and signed delta; animation curves that
select/blend them are separate FCV/shape-animation coverage work.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d299-model-data` contains
converted room archive identities/copies, conversion report, comparison script
and results. An independent field/byte comparison of all 421 successfully
converted tagged BINs verified 230,385 positions, 218,257 normals and 1,401
material/draw streams against original data. It checks numeric array equality
and unchanged command/material bytes; it is not a rendered-image or skeletal
behavior comparison. Nested SMD models passed bounded conversion but were not
included in that independent tagged-BIN count.

Twelve room-endian, nine mirror and two offline decoder tests pass. This change
is offline tooling only; the most recent game build is D298 and the most recent
Flycast replay is D295. No new frame/input/performance or manual acceptance.

Next: remaining room formats (especially LIT/CAM), source animation/FCV data,
and the native loading boundary. Preserve nested sound reads from the original
DVD container when replacing only its compressed room payload. A `.arc` with
unhandled tags must continue to fail the required-dependency check. Keep the
r120 source-completion skip and full menu/three-room backlog active.

## D298: scene registration metadata (2026-09-21)

The normal mirror now converts SMD headers, placement transforms, source IDs,
flags, group reservation counts and table-relative resource offsets, plus the
referenced TPL palettes through the existing handler. BIN and FCV payloads stay
explicitly incomplete. All nine available SMD regions pass metadata conversion
without handler errors. Do not equate this with a complete renderable model.

A real-data correction matters: r100's grouped SMD has 13 inline placements;
the five group counts reserve 297 additional runtime slots for separately loaded
blocks. They are not 297 extra records in that SMD. cSmd::getWorkNum and
getWorkPtr distinguish these meanings; the converter preserves both.

SMX conversion covers display/light masks, numeric colors, UV scrolling and
source obj02 rotate/swing work. r100/r101 SMX records convert completely for the
current fixture. Two r120 type-zero records carry nonzero callback work with an
unestablished layout; they remain explicit raw coverage debt. No guess or silent
zeroing is used. SMD's low-byte flag union and SMX's packed 0xRRGGBBAA writes are
adapted on native builds so their byte views match the source meanings. PowerPC
preprocessing is unchanged for these new source/header changes. Existing dirty
pointer-range adaptations in scroll.cpp are preserved but not staged here.

Ten room-endian tests and nine mirror tests pass, and the recovered game target
builds. Tests include deferred group counts, preserved raw model payloads,
rotate/swing floats and byte flags, unresolved callback reporting, and compiled
native flag/color views. Private evidence is at
`C:\Flycast-Evidence\re4-dreamcast\d298-scene-metadata` (mirror report,
converted archive identities/copies and build log). No new Flycast replay;
last runtime evidence is D295. Core legacy SAT errors remain unchanged.

Next: source ModelData/BIN conversion including original position/normal,
weight/part and display-list identities, then FCV/remaining room formats and
the native loading boundary. Inspect mixed byte/word unions and GX byte streams
rather than swapping every 32-bit word. Reuse the existing native draw backend.
The unconverted resources still prevent claiming room or gameplay acceptance.

## D297 historical checkpoint

2026-09-21. Asset preparation/build checkpoint; last Flycast replay remains D295.

The existing `le_mirror.py --decode-rooms` now extracts the single type-0 YZ2
payload of each st*/r*.das, uses the D296 source decoder, and converts the decoded
archive through the normal tagged handlers into a sibling `.arc`. It preserves
the original DVD container, including its nested sound blocks. No runtime reader
is redirected yet: these sidecars are incomplete and must not be interpreted as
fully converted game structures. Use the existing `--require` gate on each `.arc`
to expose all remaining formats. The sidecar option decodes each requested room
on every invocation; caching is not needed for the three current fixtures.

CNS conversion follows ConsRoom in src/game/cons.cpp, including the extra bitmap
word when count crosses a 32-bit boundary. SAT/EAT conversion follows cSatFile,
cSatHeader, AtPoly and cSatBlock in include/atari.h and include/at_sub.h. It keeps
coordinates, vector bits, polygon order, attributes, relative block links,
child/leaf layout, duplicate polygon references and resource separation intact.
No new collision tree is introduced. Unsupported/invalid regions roll back raw.

AtPoly uses both numeric attr and named attrHi/attrLo in source collision code.
The native member order now preserves both views on little-endian SH-4; PowerPC
keeps its original layout. Its preprocessed header matches the prior HEAD exactly.
This is not a new full ProDG object-comparison result.

## Evidence and limits

- Recovered game target builds successfully after the header change.
- Seven synthetic room-format tests pass, including hierarchy/attributes,
  duplicate section offsets, invalid-reference rollback, bitmap boundaries,
  sidecar container preservation, incomplete-data rejection and compiled native
  AtPoly layout/half-word semantics.
- Nine pre-existing mirror tests pass. This commit also checkpoints their
  previously dirty bounded conversion/rollback, EFF, roominfo and REL-header
  support; it does not accept the remaining dirty runtime implementations.
- All nine CNS/SAT/EAT regions across decoded r100/r101/r120 convert successfully.
- Full mirror: 780 source files converted, 1281 tagged regions, 403 handled.
  Two core SAT regions (`etc/core.das:0#9` and `#10`) remain raw with explicit
  layout errors. Their 0x10 legacy headers differ from these room structures;
  do not suppress those failures or claim universal SAT support.
- Private artifacts/hashes, mirror report and build log are at
  `C:\Flycast-Evidence\re4-dreamcast\d297-room-endian`.
- No new target run or manual/physical gameplay acceptance is claimed.

Command: `python3 port/dreamcast/tools/le_mirror.py /root/re4data /root/re4data-le --decode-rooms`.
The standalone decoder still requires the pinned external tools documented in D296.

## Next

Continue the native room loader boundary and conversion in consumer order.
CNS is ready; SMD/SMX and their referenced model/texture/motion payloads are next
for gameRoomInit's scene registration. Keep byte views and packed colors distinct
from numeric words (SMX colors and SMD flags have mixed consumers). LIT/CAM and
other required room blocks remain explicit coverage debt. Full .arc dependency
checks must remain failing until these are converted. Preserve sound processing
from the original container when switching only the geometry archive to offline
preparation. Do not run the stub YZ2 decoder on an uncompressed sidecar.

The authorized r120 cinematic completion adaptation remains open alongside these
loader dependencies. The actual first-three-playable-room sequence, visible
menu/native rendering/audio integration, transitions and retry remain unaccepted.
