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

## D342 crow module and resident room effects

2026-09-22; baseline4279bc57672de89ab46033e7dec6d122c5b05f5a plus preserved
inherited integration work. Both runs retain corrected D341 ESL and event inputs.

Connections delivered:

| Existing mechanism | Source producer/consumer | Small new connection |
| --- | --- | --- |
| gen_modules.py / module registry / compact_static_rel | em23 REL ID7, Em23Init, cEmMgr::construct | register compiled crow; default-initialize as Em12 does so subArc survives; retain PPC construction |
| re4dc_missing | DLL_Link/Unlink after rejected OSLink/Unlink | native fail-stop instead of ineffective invalid bus write |
| compact_effect_records / compact_spans / qualified .dar builder | room EFF and five nested ETM EFF owners, EspDataLoad, EspGetEstAddr, existing Espgen10/01/00 adapters | opt-in room EST selection; observe ETM member-relative end offsets |
| native_effect bind/read/unbind | ReadAreaData before effects initialize; gameRoomMemInit before heap replacement | one borrowed room slot independent of core and four enemy slots |

The room keeps every48-byte sequence head and all345 records.320 eligible
records pack losslessly;25 retaining/unreviewed records remain raw.37 sequences
use480 bytes of index metadata; net archive saving57,984 bytes. Nested ETM
member lengths must change with their contents for GetEtcAddr traversal. All15
named members remain;10 unaffected members compare byte-identically. No texture,
geometry, camera, collision, source effect timing, RNG or gameplay data removed.
SST/path/model data stay raw. No new I/O or cache for these resident records.

The original room body4669568 -> D320 texture-compacted3812576 -> D3423754592.
The existing DVD queue reads the selected smaller type0 directly into its final
allocation; no full original room copy or full decoded effect bank is allocated.
Added binding16 bytes plus existing caller-owned300-byte decode scratch; ELF
BSS grows32 bytes due layout/alignment. No additional VRAM. Source MRAM/ARAM
sound blocks are retained as transport, not proof of audio/storage implementation.
Crow static code removal239904 ->223936 saves15968 in its actual loaded body.
Crow sound2016 MRAM /166759 ARAM bytes remain separately required.

Measured Flycast allocation points:

| Point | D342a module-only | D342b compact room/crow + constructor fix |
| --- | ---: | ---: |
| r100 final body |3812576 |3754592 |
| free after required1126272 block pool |2582048 |2640032 |
| free after required1105152 em12 body |1466528 |1524512 |
| crow body request |239904 |223936 |
| free immediately after crow body |147168 |210848 |

Early block/em12 deltas match57984 exactly. The crow-point free difference is
63680, not73952: interleaved object allocations differ there. Do not add
overlapping/concurrent snapshots or call it a matched total-heap delta. Combined
final archive bytes removed73952; later source allocations consume the recovery.

D342a binds crow and runs its prolog, but modern value-initialization clears
subArc, producing five NULL/model failures. D342b preserves the pointer and
reaches the real11360-byte part request for each crow. Earlier scene part
allocation512 fails with256 free; source block object creation is incomplete.
All five crow initializations then fail, followed by required collision/object
and32-byte path scratch failures. OS heap snapshot retains64 bytes, while source
allocatable free is0; different accounting. These are failed requests/retries,
not allocated additional bytes. No full-room or complete-character acceptance.

Title/main menu and640x480 source-controlled diagnostic scene remain visible.
Scripted UP+B moves Leon to approximately(-92626,-18,-4534), source frame1385
at the final snapshot. Material/lighting deficiencies remain. No paired FPS
claim with different failed workload/state, manual play, audio, event activation,
retry/transition or physical-hardware acceptance. Runs stop at180/240s harness
deadlines; no guest reboot observed. Exact capture identities retained.

Validation:78 focused tests (compact_room, effect_residency, enemy_construction,
native_dll_failure, native_module_binding, le_mirror, room_endian). Actual native
effect adapter reconstructs all345 private records and216 delayed generator
references under ASan/UBSan. Synthetic tests exercise full owner-slot coexistence,
stale room-reference rejection, retirement/rebinding and nested-member traversal.
Actual SH-4 compilation verifies cEm/cEm23/subArc/work layout. PowerPC token
streams for changed recovered paths remain unchanged; no new ProDG object run.
Target binds37 room sequences; aggregate effect stats341 sequences/2990 records,
0 packed reads /745 raw reads /0 failures. This trace does not exercise decoding
the newly packed room records; that remains covered by the private host fixture.

Motion caches are unchanged:952768 resident/peak/read;22400 peak pinned;
2336 metadata;75 misses/loads,6 hits,0 evictions/failures; worst wait270941us.
Loading-later and final counters match.145 source headers and1904 relocated keys
validate. Keep the source-derived prefetch/concurrency audit open; failed actors
and unvisited reactions do not qualify the full immediate-response working set.

Keep the module/failure/constructor corrections and selectable resident packing.
Continue required initialization-memory recovery before event activation. Priced
but not implemented: option nonpalette upload-only texture compaction109728 net
archive bytes (110048 gross minus320 metadata), only2496 option reservation slack;
room SST packing21952 gross. Option card-swap/owner semantics require an audit.
Neither pricing result is heap recovery. s03/event mutable-snapshot/final-buffer
capacity remains open. Do not reclaim hot motion data after every evaluation or
remove required crows/blocks. Simpler water is unimplemented and cannot be counted
against this memory deficit; PS2 visual equivalence remains unverified.

Evidence: C:/Flycast-Evidence/re4-dreamcast/d342a-crow-module and
d342b-room-effects; private candidate inputs /root/probe/d342-mirror and
/root/probe/d342-room. Build flags/toolchain remain recorded D340/D341 choices.
D342b ELF text/data/BSS2305564/77012/673080, +10364/+176/+32 versus D340c;
five pre-existing missing stubs remain. Original KOS and accepted assets untouched.

d342a-crow-module ELF SHA256 `ebf366884633572052d9defab02bf0656f84984e9416dd78416dddf276e97a58`; disc SHA256 `c96b6951397ff65a73d89dd1907fb6d64864630457782271444cd549f76e48a0`.

d342b-room-effects ELF SHA256 `61485913ebbf3ca3e6a2a4a6e48d91bd418d658b9185136f81bfa08dad3944d6`; disc SHA256 `d818b0688f209a738e49f035ffcdff4a6aeb021d5bbd58834082d9fc2566f831`.

## D343 persistent option textures

2026-09-22; baseline0a320fcbcf77943f56e5a6924e9cea2d647351e9 plus preserved
63 inherited tracked changes. Keep the selectable candidate, with presentation
and complete-room acceptance still open.

| Reused mechanism | Recovered producer/consumer | New adapter |
| --- | --- | --- |
| le_mirror qualification/offset observers; select_upload_only; compact_spans/NTR index | SS/eng/option.dat, option/death EFF #0/#4, IdTexDataLoad and UWF consumers | --compact-option, whole-file qualification and exact unaffected-family validation |
| SourceIdentityTable; image_key; Package::open_streamed/upload/release_payload; shared fences | OptionDataRead before TPL relocation, option/death native quads | one borrowed option identity view, invalidated before overwrite, retained across room retirement |
| fixed-region budget header; DVD resident_bounds | plain option.dat read into re4dc_mem.option | selectable exact reservation; existing pre-transfer guard rejects original oversized file |
| cDataSwap source scratch-heap path | card initialize type0/1 and other mutable swap callers | fail explicitly before the unsupported ARAM fallback touches live bytes |

The original tagged file has11 entries, including EFF0/4 and9 UWF families.
23 nonpalette/nonmip images are replaced by32-byte identities, with a320-byte
index:736 record bytes plus320 index bytes retained. All10 death palette images
and all UWF data remain byte-identical after qualified endian conversion. Only
family4 changes; source indices and relative references remain valid. Native
packages are verified against the existing converter without generating new
texture encodings. Original archive and default0x40000 budget remain selectable.

| Actual boundary | D342b | D343a |
| --- | ---: | ---: |
| Option file bytes |259648 |149920 |
| Option reservation |262144 |149920 |
| Source heap free after1126272 block allocation |2640032 |2752256 |
| Source heap free after1105152 em12 body |1524512 |1636736 |
| Source heap free after223936 crow body |210848 |323072 |

All three matched allocation-point deltas are112224. Archive saving109728 plus
2496 slack; not a new reduction in the enemy archive itself. Direct bounded
DVD read into the final smaller owner avoids original/candidate overlap. The
existing128KiB DVD staging and64KiB streamed texture reader remain; no new full
payload buffer or VRAM reservation. The borrowed identity view is16 bytes on
SH-4; aligned BSS does not grow. ELF text grows456 bytes to2306020, data77012,
BSS673080. These are stage/allocation observations, not complete loading peaks.

The MRAM-success cDataSwap path creates heap11 over a separately allocated
scratch block; it does not overwrite pOption. When that allocation fails, the
original path parks a live range in ARAM and reuses it. Native ARQ has no real
mutable storage, so this fallback is now explicitly rejected before DMA or heap
mutation. No general swap system is implemented or save/load acceptance claimed.
Boot card type2 does not use this swap. Source PPC token streams are unchanged.

D343a preserves the existing approach fixture. Title/main menu and640x480
diagnostic room remain visible, with source-controlled Leon reaching approximately
(-96176,-175,-2439), source frame1308. First failed11360-byte crow part request
has10720 free; individual fallback512 fails at352. Four crow model failures
remain, followed by required672/928-byte collision,7904-byte object-part and
32-byte path scratch failures. One fewer crow model fails, but that is not
complete crow/room acceptance. Final OS heap free/largest64; source allocatable0.
Later allocations consume the recovered space. Do not sum failed retries.

D343b exercises source title Options: Down at retrace2510, A2570 -> title5/4;
START2930 ->5/0 ->5/1 at2962; Up3050/A3110 then title7 and START3310 reach room
loading. Five externalized option textures load successfully; three sampled
identity logs explicitly avoid source-texel hashing. No upload failure in this
segment. Existing shared VRAM used4048896 at sampled option frame1200, peak4192256;
bounded upload source-heap6076928->6076928, retained144-byte package metadata per
load, staging released. These uploads share the pre-existing cache, not a new
option VRAM bank. Menu input is scripted, not manual acceptance.

The option image shows colour bars and EXIT, not a fully accepted options UI.
Pinned D342b ELF/full option archive, using the same input fixture in D343c,
produces byte-identical captured fb0 PNG SHA256
`f3efa27e64c7da92681c547812d67d105eba4fc551187d7c6f8c42e3b673eb84`.
This rules out the compaction as the cause of this sampled presentation; source
UI/material/order correctness remains open. No unrelated rendering fix added.

Checks:14 tests (compact_option, data_swap, resident_bounds, compact_room,
native_ui). Actual source cDataSwap executes under ASan/UBSan: separate scratch
preserves live bytes and restores heap ownership, rejected fallback never calls
ARAM or mutates heaps. Private actual SourceIdentityTable methods validate all23
descriptors before/after source header relocation, interior-pointer rejection and
clear.10 unaffected archive families compare byte-identically. No new ProDG run.

Motion unchanged952768 resident/peak/read,22400 peak pinned,2336 metadata;
75 misses/loads,6 hits,0 eviction/failure, worst wait270941us. All145 source heads
and1904 retained/relocated keys validate; loading-later and final counters match.
No post-evaluation eviction introduced. Required failed actors, combat responses,
event transitions and prefetch/concurrency audit remain unqualified.

Evidence directories C:/Flycast-Evidence/re4-dreamcast/d343a-option-residency,
d343b-option-menu, d343c-option-reference. First two use the same new ELF;
reference uses exact accepted D342b ELF, not a rebuilt old checkout. Durations
240/240/100 seconds; harness deadlines, no guest reboot observed. Captures are
emulator integration evidence, not paired performance or hardware acceptance.
Same pinned KOS/manual-flip patch,SH GCC15.2,O1,Flycast and corrected reader.
Original references and63 inherited tracked changes preserved.

Candidate ELF SHA256 `34771144e0f4475cfe24c11da590f52ce4152d8a90b0944f4107074ba5093ed3`.
Option SHA256 `b56409dee1d1d504c54e129490fcab1f7cb27a8afe0107c7695bbc99d795a3db`.
Approach disc SHA256 `adbbd62b9b25f5b57689c2d69329f26df0097c3a4526e029bfce9a6bdf06e4d4`.
Options disc SHA256 `8fccad838e6242a157d192c480302f2d0f1e1ecf1ed293171f98a3524c36ed37`.

Next: price the remaining required model/effect initialization lifetimes at the
new failed allocation, preserving complete actors and collision. Existing room
SST pricing21952 gross is only a bounded candidate, not enough evidence of full
fit; retain hot motion data and do not disable crows/blocks. Event s03 mutable
snapshot/final-buffer capacity, source lighting, audio, inventory, progression,
retry and performance remain explicit. Simplified water stays selectable and
unimplemented; PS2 equivalence must be checked before promotion.

## D344 stable enemy work pages

2026-09-22; parent 87c0e1f155f0ab589696523ac3b1ec9e8fae4998 plus the preserved
63 inherited tracked changes. Keep selectable `ENEMY_DEMAND=1` and the missing
crow packages. Default enemy backing remains the source-sized contiguous array.

| Reused mechanism | Source connection | Small new adapter |
| --- | --- | --- |
| parts_bridge Pool/Chunk, workAt/prepareWork and source heap handles | cEmMgr create/createBack, indexed references and source room teardown | cEm specializations, stable two-slot pages, no dead-slot eviction |
| Existing native manager scans and lifecycle methods | source game/st1/shared em10/em_wrap readers | nonallocating sparse lookup; explicit retained indexed access; module qualification guard |
| prepare_native_ui, convert_tpl, le_mirror qualification; shared Package/upload/fence | em23 model/effect TPLs selected by recovered game | asset-free crow-native-deps selector and private generated packages; no new converter or backend |

The source first-free and last-free creation order, all 60 logical slots,
constructors/destructors, active-list order, delayed deletion and source IDs stay
intact. Exposed slots retain their addresses until owning room teardown, even
after deletion. Scans cannot allocate backing. Indexed callers commit stable
slots; allocation failure is explicit. The ladder query intentionally reads
position even on never-used zeroed slots: preserve that result without allocating
the entire array. Other live-work scans skip unbacked slots. Debug push/pop keeps
its separate original contiguous array. Later RELs are not silently qualified:
the build rejects ENEMY_DEMAND with modules outside the reviewed current set.

| Actual source boundary | D343a | D344a/b |
| --- | ---: | ---: |
| Heap free after 1,126,272-byte block pool | 2,752,256 | 2,921,856 |
| Heap free after 1,105,152-byte em12 body | 1,636,736 | 1,806,336 |
| Enemy work owning allocation after initialization, including overhead | 213,184 | 72,384 |
| Final OS heap free / largest free block | 64 / 64 | 66,592 / 66,592 |
| Crow ModelInit failures | 4 | 0 |

The early saving is 169,600 bytes (12 slots backed); the final work-array saving
is **140,800 bytes** (20 backed, 19 live). It is not another reduction of the
1,105,152-byte enemy archive or the motion cache. Directory is 384 bytes, ten
pages are 7,200 bytes each, total/peak 72,384; no allocation retry/reclaim/failure.
At all 60 slots backed, capacity remains intact but total becomes 216,384,
3,200 above the original contiguous allocation. Include that maximum overhead
in future room budgets. Growing cannot require a second full array or move live
actors. The original effect pool was inspected but left unchanged: its rotating
allocation order would eventually touch every slot, defeating retained lazy pages.

More required work now fits: parts resident/peak 334,112 (647 backed/live),
model-info 78,272 (256 backed/242 live), objects 212,704 (212/206); no pool
failures or reclaim attempts. Actual heap lists validate size 8,840,576 with one
66,592-byte free block. This is a bounded initialization/loading observation,
not proof that every later event, reaction, audio request or transition fits.
ELF text/data/BSS 2,309,656 / 77,012 / 673,080 (+3,636 text versus D343);
aligned source heap capacity is unchanged, not zero overall platform cost.

D344a still lacked native em23 textures now reachable after successful model
creation. D344b adds 19 packages from the existing converter and qualified source
archive; the observed body key 3d9d333a-125fadf1 uploads successfully, 128x128,
32,768 VRAM bytes, 144 retained package metadata bytes, existing 64KiB staging,
zero source allocation for upload. Source dimensions, original archive, palette/
effect CPU consumers and sound transport remain intact. This uses the existing
16-bit conversion policy; no VQ/PAL saving or visual equivalence is claimed.
Only the private selectable fixture changes; no source texels are externalized.

Both 240-second runs finish at their harness deadline, with no observed guest
reboot and no source allocation failure. Source title/menu, HUD and moving
640x480 diagnostic world remain visible. D344b reaches source frame 1334 and
Leon position about (-95317,-131,-2761) through the existing approach input.
Five crow list identities 15/16/17/32/33 each have 24 linked parts and valid model
metadata in both later/final snapshots; active-list membership and all four
pool directories validate. RAM model completeness is not accepted animated
rendering, combat, audio, inventory, retry, a full room or manual play.

Presentation remains explicitly diagnostic: zero texture, capacity, invalid or
overflow rejection counters in D344b, but 9,845 material-flag0x04 rejections and
109 no-image-part rejections remain. Inspect the source material consumers at
model_bridge/commonModelTrans before adapting native_ui's packet-reserve guard.
Do not remove guards as a substitute for implementing the material. No new
frame-budget claim; runs differ in rendered workload and source frame reached.

Motion preserves the complete currently classified hot set: 952,768 bytes
resident/peak/read, 22,400 peak pinned, 2,336 metadata, 75 loads/misses, 6 hits,
zero evictions/failures, worst wait 270,939 us in D344b. All 145 persistent source
heads and 1,904 relocated keys validate. Warmed and final counters are unchanged;
no repeated disc reads for an unchanged set. This slice changes no motion
policy. Source-derived prefetch/concurrency and immediate-response coverage
remain open for unvisited combat/event states; evaluation pinning is a minimum
lifetime, not an eviction command. Earlier net warmed enemy-family recovery
1,510,176 remains separate from the new 140,800 work-array saving.

Checks: two focused tests, one running 16 demand/reference combinations with
ASan/UBSan. They exercise stable retained references, 100 create/destroy reuse
cycles, deferred deletion, first/last/indexed selection, all slots, allocation
failure, logical predecessor, debug push/pop and owning-heap reset/free. The
actual source ladder query is tested for unused-slot origin and live-slot
results. Native preprocessing checks 334 configured input units including shared
em10 in em12; 33 changed recovered source/header PPC token streams unchanged.
Actual SH-4 assertions retain cEm/cEm23 size0xde0, manager/field offsets and crow
work layout. No new ProDG object comparison or hardware run.

Selected evidence: C:/Flycast-Evidence/re4-dreamcast/d344b-crow-textures;
d344a-enemy-work retains the initial missing-package finding. Asset mirror is
/root/probe/d343-mirror; selected fixtures /root/probe/d344b-fixtures. Exact ELF,
assets, fixture, KOS/compiler, emulator/config and capture-tool identities are
sealed with the evidence. Original/accepted directories are not mutated.
ELF SHA256 `e13254ffdc7da81e439dfc5ed13d18369f5bcd388528439ddb9d43a53c5043a6`.
Selected disc SHA256 `b1b8e879d6dfda9e4161b79294aeea0aae885fc02b9e5957b69eb2d7634ddb0e`.

Next: continue the two demonstrated source integration boundaries: qualified
EVD activation/mutable event destination lifetime, and the native source material
rejections above. Preserve working menu, complete allocated actors and hot keys.
Do not call this the cabin restored, full encounter fit or a first-room skill
qualification. Water simplification remains a separate selectable candidate;
no water code/asset change or PS2-equivalence claim was made.
