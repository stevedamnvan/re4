# D312: source event qualification and native enemy module

Historical D312 checkpoint (2026-09-21); later D320-D340 supersede the
allocation and immutable-preload failures below. Kept as integration progress; enemy creation and room residency
still fail for insufficient main RAM. No playable/rendered acceptance.

## Change and verification

R100Em's ignored constructor asm name now aliases the existing cEm constructor.
An actual SH-4 layout fixture verifies the compact 0x3e0 object, 0x320 cModel,
and damage/subArc layout before reusing that constructor. The em12 module uses
the existing shared em10 source and static module generator/registry (REL ID 18).
Native-only symbol visibility/spelling fixes preserve the PowerPC token stream.
Five explicit missing-function stubs remain, including cEm27::setWaterHeight;
linking em12 is not proof every enemy branch works.

The existing mirror now handles the required EVD header, bounded packet records,
named asset table and its BIN/TPL/EFF/FCV/LIT/MDT dependencies. Unsupported packet
kinds and malformed bounds remain rejected. Existing FCV codec support now
preserves observed empty fills, zero size-word variants and aligned key padding;
every source FCV must roundtrip exactly before conversion. Native EVD magic is
compared as ASCII, retaining the original PowerPC numeric check.

20 mirror and 40 room-format tests pass. Source-vs-native checks cover all 161
packets and 133 named assets in r100s40/41/43/44, preserving strings and offsets.
The expanded /root/probe/d312-required.txt gate passes. Seven mirror errors
outside this fixture remain; r101 EVS remains unqualified. Three changed source
files have identical preprocessed PowerPC tokens against the pre-slice working
source; this is not a full ProDG comparison.

## Replay and exact next failures

The 55-second scripted replay passes the R100Em stub and starts the authored
r100 door/window/stream-check tasks. It is not a successful encounter:

- Block::checkBlockMemory requests 1,126,272 bytes with 419,456 free, fails,
  and disables its block data. This must be fixed before room acceptance.
- em12 body requests 4,006,016 bytes with 409,152 free, then repeats with
  343,552 free. DVD allocation fails, EmSetEvent fails and R100Init logs failure.
- EVD names register and reach ARAM_LOAD. The current ARAM/audio placeholders
  do not establish actual event resource residency or audio playback.
- IDSystem missing units and ESP_CTRL02 range errors remain. Sleeping source
  tasks do not establish correctly advancing gameplay or successful initialization.

The next slice must account for archives, source pools and block/enemy working
sets, then remove redundant target residency without cutting required content.
Static module BSS/reload behavior, native rendering/audio, title/UI, manual
character/camera/combat verification and normal three-room progression remain
open. Preserve both source behavior and the accepted native viewer reference.

## Reproduction and identities

Private evidence: C:\Flycast-Evidence\re4-dreamcast\d312-event-enemy.
Build: source port/dreamcast/kos-env.sh; make -C port/dreamcast/game -j4.
Mirror: python3 port/dreamcast/tools/le_mirror.py /root/re4data /root/re4data-le
--native-rooms --require /root/probe/d312-required.txt.
Disc staging: /root/probe/d312-disc, existing /root/probe/d292-fixtures.
Evidence retains build/package/mirror logs, all asset hashes, dirty source patch,
scripted boot log, SH layout fixture, source token check and EVD verification.

- ELF SHA256: 79f10b18e0f319f955f24cfcc5f84b9a59ab054fc02ec3ec72cccc2972c6988f
- Disc SHA256: 5649f9ff5839b2de58d407e4ffec6af95ce8a3edfd1b7c2b456d81cbb749f167
- Flycast SHA256: 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a
- r100 DAR unchanged: 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739
- KOS: 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3; SH GCC 15.2.0.

Memory figures are failed-request snapshots, not measured gameplay peaks.
No presented frame rate, visual/audio correctness or physical-hardware result.

## D340: qualified immutable event backing

2026-09-22, baseline `7cc02f3223835fc9c24aaf7b7ee4bd67ac08c09e` plus preserved
inherited integration work. This changes transport/ownership, not event scripts,
gameplay flags, collision, geometry, camera or water.

D340 adds selectable `EVENT_FILES=1` backing for qualified immutable EVD
preloads. It reuses `le_mirror` qualification, the native DVD root, existing
64 KiB storage reader, and source `cDataUnit` ownership. Source compaction moves
the file reference without allocating a whole-event scratch buffer. Actual
installation validates each payload chunk into the caller's final allocation;
mutable parking/swaps are explicitly rejected, not silently restored from disc.

A 450-second reference run reproduces the 694,560 /669,248 /309,632-byte
compaction failures with 41,472 bytes free. The kept candidate completes all
three moves without these failures. Four preparations read 372 metadata bytes,
zero EVD payload bytes, with worst observed preparation wait 16,384 us. No event
installation occurs in this run; that transport is host-tested, not yet exercised
by target event activation. The rejected full-preload-read variant took up to
18,228,242 us. These are emulator integration observations, not an FPS benchmark.

Required block/enemy allocation points remain 2,582,048 /1,466,528 free. Later
heap free and largest block both remain 41,472: **zero additional heap recovered**.
The change avoids failed scratch demands rather than freeing previously allocated
storage. No new payload arena or VRAM allocation; ELF text/data/BSS are
2,295,200 /76,836 /673,048 (+2,896 text, +32 BSS versus D339). The 540-byte
compiler-reported transfer stack excludes callees and is not a total stack peak.

Source title/menu and diagnostic room output remain visible. Delivered UP at
retrace 9011 moves Leon from approximately (-99,692,-454,-1,344) to
(-94,864,-123,-3,059); R at 21025 exercises the source aim path. These are
scripted controller observations, not manual encounter acceptance. Source frame
1483 is reached; the capture stops at its 450-second deadline, not a game crash.
Materials/lighting, event activation and mutable snapshots, full audio, inventory,
combat, transitions/retry, performance and hardware acceptance remain open.
Simpler water remains a selectable, unimplemented candidate.

### Concrete source-to-native connection

| Reused mechanism | Source producer/consumer | Small new adapter |
|---|---|---|
| `le_mirror.convert_file/fmt_evd` and existing nested handlers | Original EVD packets, named assets and pointers | `prepare_event_reference` returns the actual qualified LE payload and an `.evq` chunk-CRC certificate. Unknown/incomplete conversion rejects. |
| Native DVD root plus `room_storage::read_chunks` | `cDataUnit::setLoadToAram/setLoadToMram` | `native_event_file.cpp` checks certificate/name/size; installation checks every64KiB chunk while copying to final destination. No second full representation. |
| Existing DC unit array, sort and clear/delete rules | `checkAramSort` and room lifecycle | A previously unused native flag marks immutable file backing. Logical rebase retains its source filename/size and clears the command. Clear/delete removes the flag. No duplicate range registry. |
| Source DMA and `MemorySwap` entry points | Raw range access and mutable exchange | Reject overlapping immutable ranges, including aligned spans, before a destructive copy. MRAM-to-ARAM parking keeps the owned MRAM on failure. |

Only immutable EVD preloads use this selectable path. Other ARAM users, including
block/subscreen/audio and mutable snapshots, are not qualified by this adapter.
Preparation validates the converter-produced certificate and file length; it does
**not** claim payload CRC verification at that moment. Only successful install
publishes MRAM condition2. Truncation/corruption/read failure leaves the consumer
inactive, and caller-owned destination storage is never freed by the unit.
Installed bytes may be mutated/relocated: raw-file reload cannot replace them.

Four certificates total372 bytes on disc; payloads remain byte-identical to D330.
Files are r100s40/s41/s43/s44 (2,227,072 /694,560 /669,248 /309,632 bytes).
After s40's source clear, three file-backed units remain ready at source-selected
logical addresses, with zero pending commands/errors. The linked native adapter
adds no source allocation and reuses the existing64KiB bounce buffer. New stats
are28 bytes, with32 bytes total BSS growth from alignment. Native transfer's
288-byte certificate array and other locals use the existing calling stack.
KOS file-cache overhead/loading peaks are not separately instrumented as a new
whole-encounter peak; do not report only these metadata bytes as total game cost.

### Evidence and keep/reject decision

Three sequential450s Flycast runs preserve exact executable/disc/config/fixture/
capture-tool hashes and snapshots under `C:/Flycast-Evidence/re4-dreamcast/`:

- `d340a-event-progression`: D339 ELF/input unchanged; reproduces all three
  compaction failures. Final source frame1484; source free/largest41,472.
- `d340b-event-files`: full-preload payload verification is rejected. It fixes
  scratch allocation but adds up to18.228242s synchronous preload waiting.
- `d340c-event-install`: keep selectable. Four prepared files, three logical
  moves, zero EVD installs/failures,372 metadata bytes read, zero payload bytes
  read. Worst observed preparation16.384ms. This is a reference availability
  result; it does not prove event-play bytes were consumed on target.

Candidate controller fixture adds UP at retrace9000 (delivered9011, held10800)
and R at21000 (delivered21025, held1800). Snapshots145/200/340/395s and final
show source movement/pose/camera changes and preserved room/HUD output. No forced
hold/black/player state. Source Rno0=3/System0x800 at final frame1483. No EVD
activation or new resource failure is reached; no first encounter acceptance.

Required block pool1,126,272 and compact em12 body1,105,152 both allocate, at
2,582,048 and1,466,528 free. Later snapshots validate the OSAlloc linked lists:
one free block41,472. All manager pointer maps remain valid, with resident/peak
parts276,992, modelinfo73,504, objects212,704. Motion cache peak952,768,
peak pinned22,400,metadata2,336,75 misses/loads,6 hits,0 evictions/failures,
952,768 payload bytes read and worst observed wait270,939us. All145 source
headers/75 payloads/1,904 relocated key pointers validate. Earlier net warmed
enemy-family recovery1,510,176 remains; D340 adds zero enemy-allocation saving.
The repeated-use/immediate-response/concurrency audit remains incomplete.

Moving/aimed candidate texture use3,260,416, peak4,192,256,98 uploads,0 missing.
Maximum observed complete-frame model commands2,487,488; Flycast TA high-water
still invalidzero and physical capacity unqualified. Different camera/pose
states prevent pixel-equivalence/FPS comparison. Host compilation/checks also
overlapped parts of these integration runs; do not treat them as isolated timing
benchmarks or add overlapping PVR/CPU intervals. Room output remains a base-
material diagnostic with incomplete lighting/material behavior.

Thirty focused event/mirror tests pass, using real source-unit method bodies,
real native reader, synthetic short reads/corruption,100 moves with no reread,
fixed and allocated destinations, failures/clear/retry, and swap preflight.
Both EVENT_FILES choices build; toggling back reproduces the kept ELF exactly.
PowerPC preprocessed tokens of both shared source units are identical to the
baseline; no new ProDG object comparison. Original KOS tree remains clean.

### Reproduction and next consumer

Use `/root/work/re4-dreamcast`, patched KOS `/root/work/kos-re4dc-d336` (base
804b3195 plus existing D336 patch), SH GCC15.2, nativeO1. Build:

```sh
export RE4DC_KOS_BASE=/root/work/kos-re4dc-d336
source port/dreamcast/kos-env.sh
make -C port/dreamcast/game -j4 CORE_RESIDENT_BYTES=1360608 \
  PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 \
  PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1 \
  PVR_STREAM=1 MODEL_POSITION_CACHE=1 EVENT_FILES=1
```

Private generated mirror `/root/probe/d340-mirror`, fixtures
`/root/probe/d340c-fixtures`, disc `/root/probe/d340c-disc`; original D330/D327
directories are unchanged. Reproducible private preparation scripts are copied
into evidence. They call the existing mirror module's bounded
`prepare_event_reference(rel, original_bytes)`, compare the returned LE bytes
exactly with the accepted mirror, and install only its certificate alongside the
same payload. Never generate a certificate from an unrelated stale report.

Kept ELF SHA256 `c482b23419c3feba2a96b43cba791bb8e1678eba9e294e6d49514adfd5a38539`.
Disc SHA256 `6b59bae61bbeabdd280bc025741e5a384817b74ab289a0784f6ed1a085275323`.
`identities.json`, `event-assets.json`, `result.json`, `event-state.json`, motion
pointer checks and the evidence manifest retain exact observations and limits.

Next: reach the first event through actual player progression, trace its required
final allocation and source completion/skip effects, and connect that activation
without unqualified data. Implement mutable snapshots only with native motion,
texture/effect bindings and capacity handled together. Do not blindly re-read
the original archive over live pointers. General ARQ still does not store bytes;
this adapter does not turn all source ARAM into backed memory. Keep lighting/
materials, audio, inventory, combat, retry/transitions and physical gates visible.

## D341: opening enemy list and event inputs

2026-09-22. Keep the converter correction; the selectable full-input candidate
is blocked and is not a new accepted scene. Original source data remains private.

D341 corrects the opening enemy-list conversion in the existing mirror tool.
The old native list interpreted the house entry as room0x001/HP59395 instead of
room0x100/HP1000. All255 original records compare field-for-field after conversion;
target snapshots verify the corrected house entry. Required byte fields, indices,
record count and reserved bytes remain intact. Thirty-four focused tests pass.

This exposes required content previously suppressed by the bad room checks:
the authored crow archive now requests239,904 bytes, and its REL module7 is not
in the image. The first cold boot allocates that body, leaving147,168 free at
that point, but subsequent model-info requests4704 fail with4064 free. Required
block pool/em12 early points remain2,582,048/1,466,528 free. This is **zero new
heap recovery**, not a fit for the corrected encounter. After a guest reboot,
crow retries fail with75,936 free; do not combine those separate boot states.

The longer old-data approach also reaches missing r100s03/r100s20 requests.
Both files now pass the existing EVD converter/certificate producer (156 complete
records), but the corrected-list run stops earlier at crow initialization. Their
target preload/installation is not newly accepted. No event, combat, visual,
performance, audio, manual-play or hardware acceptance is claimed by D341.

Continue with the existing static module generator/registry for em23 (module7)
and the additional source working set. The module failure logs HALT and then
continues/reboots: the PPC invalid-address halt is not a reliable native stop.
Close that failure path before accepting new module consumers. Keep the corrected
list; do not regain the old image by suppressing required crows. EVENT_FILES
activation/mutable snapshots, source lighting/materials and all existing backlogs
remain. Simpler water is selectable and unimplemented; PS2 equivalence is unverified.

Existing connection: `stage.cpp::readEmList` reads directly into `pG->Em_list`;
`em_set.cpp::EmSetFromList/EmSetFromList2` consumes `EmListData`. The new code is
only `le_mirror.fmt_esl`, dispatched through its existing guarded converter.
Files have no header: require a nonzero whole number of32-byte records, at most
256. Convert flags, HP, six signed position/rotation values, numeric room ID and
signed guard radius; preserve byte fields and four reserved bytes. The actual
opening list contains255 records/8160 bytes and remains exactly that size.
No gameplay workaround, model change, new loader, renderer or runtime allocation.

Old target entry37: flags603979776, HP59395, position(13791,21248,8435),
rotation(0,768,0), room1. New target entry37: flags36, HP1000,
position(-8395,83,-3296), rotation(0,3,0), room256, matching source. The old room
check returns `errEm` (null); the house event later invokes a virtual method on
that result. This is a source-traced explanation candidate for the old approach
reboot, not a captured fault-PC proof. The new list independently exposes earlier
crow loading, so D341 does not prove the later house event fixed end-to-end.

The reference uses existing controller fixture plus raw UP+B0208 at retrace9000,
held60000 retraces. At340s it reaches(-86262,-12,-8610); at800s, after a reboot,
it reaches(-81697,29,-12288). Flycast REIOS logs corroborate guest reboot rather
than treating log-head decrease alone as proof. Missing s03/s20 are requested by
`R100Main` area6 -> `readEvent(0/3)`. The existing original-disc reader and
`prepare_event_reference` produce the added qualified files:1341504 and689632
bytes. No new decoder or conversion framework is introduced. These additions
remain on disc; no event installation/read payload saving is claimed.

Corrected list restores five initially enabled r100 crow entries (IDs15,16,17,
32,33; enemy ID0x23). `em/em23.drs` already exists and has complete conversion
records, including its raw REL descriptor requiring static binding. Its main
payload is239904 bytes; its2016-byte MRAM and166759-byte ARAM sound payloads
remain distinct. The current generic ARQ path does not prove those ARAM bytes
resident or audible. Do not count the whole410752-byte file as main-heap usage.

First candidate cold boot: required block/em12 still allocate. Crow body then
allocates239904; model-info backing requests4704 fail with4064 free, blocking
complete block objects. Module7 fails binding; source `DLL_Link` logs HALT,
then incorrectly logs completion and the guest reboots. After reboot the crow
body instead fails with75936 free. Those retries are not additional allocations.
Stopped deliberately after209.853 seconds; stopped/title/room snapshots after
reset do not establish successful cold-boot progression. No frame-time comparison.

Validation: `python3 -m unittest -v test_esl test_event_file test_le_mirror`
(34 passed); all255 private records compare source BE against native LE scalar
values; actual target entry37 verified before initialization and after reset.
The new required-dependency fixture passes against the selected mirror.
No C++/PowerPC source changed, so no new ProDG comparison or native build claimed.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d341a-cabin-approach` and
`d341c-enemy-list`, with exact source/executable/assets/toolchain/input/capture
identities. `d341b-opening-events/NOT-RUN.txt` labels the unexecuted intermediate.
Prior accepted references and63 inherited tracked edits remain preserved.

Next bounded connection: reuse `gen_modules.py`, MODULES and `modules.cpp` to
bind recovered em23; establish a reliable native failed-link stop. Account for
the newly active crow body plus actors/effects and remaining complete room
objects through existing resource ownership/compaction. Do not silently disable
the birds, lower capacities, trim hot enemy motions or call old raw ESL safe.
Then resume source-controller movement to qualified event preload/activation.

d341a-cabin-approach disc SHA256 `ad70958b9cc0db8979a78307e9be665107f25556163ad39308bf1ffd2c818c00`.

d341c-enemy-list disc SHA256 `37853c6293767e56b811c74be3ef7ad89fff4175b2d1dfd4a38a66597d768aa4`.
