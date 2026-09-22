# RE4 Dreamcast working handoff

Updated 2026-09-22. Read and follow [AGENTS.md](AGENTS.md), the shared instruction
entry point for Sol, Astra and Claude. It defines scope, implementation workflow,
acceptance and preservation rules. This file records where to resume.

## Active objective

Cold boot -> required startup prompts -> visible, controllable title/main menu
-> New Game -> the first three source-authored opening rooms, fully playable
with normal transitions, combat/events where applicable, audio, death and retry.
Cutscene presentation is deferred for now; required source completion effects
and restoration of player control are still necessary. Verify the actual room
sequence from source/data. The room-120 debug start is only a dependency fixture.

## Current resumption point - D341 corrected list exposes required crow dependency

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

Current ELF remains byte-identical D340c (`c482b23419c3feba2a96b43cba791bb8e1678eba9e294e6d49514adfd5a38539`).
There are no new native code/layout/toolchain changes. The original primary mirror
and accepted evidence are untouched. D341c selectable inputs are
`/root/probe/d341c-mirror`, disc `/root/probe/d341c-disc`, fixtures
`/root/probe/d341a-fixtures`. Evidence is
`C:/Flycast-Evidence/re4-dreamcast/d341c-enemy-list`: blocked, not promoted.
The reference900-second run `d341a-cabin-approach` reboots twice; its later images
are not uninterrupted progression. `d341b-opening-events` was staged but never
run: superseded when raw ESL data was discovered. The candidate was deliberately
stopped after the reproduced dependency (209.853 seconds), not its600-second deadline.
No emulator run remains active at this checkpoint.

Private preparation/validation: `/root/probe/d341-events.py`,
`d341c-prepare.py`, `d341-source-check.py`, `d341-analyze.py`.
Do not rerun preparation scripts against their existing output directories.
Use `port/dreamcast/fixtures/r100-event-deps.txt` with the existing qualification
check; it adds reached dependencies, not a complete room manifest. Only required
`etc/emleon00.esl` was regenerated. Other mirrors/lists are not implicitly qualified.
Keep the source-derived hot-motion/prefetch audit and retained-pointer checks:
this new dependency does not justify evicting hot keys after each evaluation.

## Previous D340 checkpoint - immutable event preloads; activation remains

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

Keep `EVENT_FILES=1` selectable (default0), on top of the current D339 build:
`CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1 PVR_STREAM=1 MODEL_POSITION_CACHE=1`.
Use patched KOS `/root/work/kos-re4dc-d336`; original KOS remains clean.
Current ELF is the D340c candidate. Both EVENT_FILES choices build and the
candidate is reproduced byte-identically after the toggle check. Thirty focused
tests pass, including actual source-unit methods and native reader fixtures with
ASan/UBSan. PowerPC preprocessing of datactrl.cpp/dvd.cpp is unchanged; no new
ProDG object comparison is claimed. Five pre-existing missing stubs remain.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d340a-event-progression` (same D339
ELF/assets, longer run); `d340b-event-files` (rejected whole-preload verification);
`d340c-event-install` (kept metadata-preload candidate, controller diagnostic).
Private assets `/root/probe/d340-mirror`, disc `/root/probe/d340c-disc`, fixtures
`/root/probe/d340c-fixtures`. D330 source mirror/core and D327 fixtures remain
unchanged. D340c fixtures add two controller holds; no source-state writes.
ELF SHA256 `c482b23419c3feba2a96b43cba791bb8e1678eba9e294e6d49514adfd5a38539`.
See [D340](port/dreamcast/docs/R4_EVENT_ENEMY_CHECKPOINT.md#d340-qualified-immutable-event-backing).

Continue the normal source-controlled approach to the cabin and first event.
This run activates no EVD and reaches no new resource rejection after the
compaction fix. Do not invent a freshly observed failure. The known next storage
boundary is `cDataUnit::setLoadToMram`'s final event allocation and
`MemorySwap`'s mutable enemy/event snapshot. The latter is guarded before any
copy for file-backed units; general ARQ and mutable byte storage are still
unimplemented. Source EVD consumers must retain relocated motion/texture/effect
ownership and source completion effects. s40 remains 2,227,072 bytes versus
the compact enemy body's1,105,152; file backing does not solve activation capacity.

Motion hot-cache behavior remains unchanged in this run:952,768 cached/peak/read,
22,400 peak pinned,2,336 metadata,75 misses/loads,6 hits,0 evictions/failures;
worst observed wait270,939us. All145 headers and1,904 relocated pointers validate.
Do not claim completed combat/reaction/concurrency coverage; retain the existing
prefetch audit and keep hot data cached beyond evaluation-time pinning.

Continue source material/lighting integration through the existing backend.
Separate-alpha and texture-blend flags differ; preserve multiplication,
thresholds, UV choice, order and depth. No water simplification is implemented.

D335c remains the default bounded regression (`d335c-admission`); its sparse
branches/HUD are not a complete scene reference. D334 background-depth and D333
nested-task ownership corrections remain. No manual/FPS/audio/hardware acceptance.

Historical D338/D339 event compaction failures are now reproduced in D340a
and avoided by the selectable D340c immutable-file path. The original ARQ path
still lacks bytes; this is not general ARAM/audio or mutable-swap acceptance.

D333 evidence `C:/Flycast-Evidence/re4-dreamcast/d333-scenario-parent`, disc
`/root/probe/d333-disc`, preserves the task-parent correction and host/source
checks. Its black output is explained in part by D334; remaining geometry and
material omissions are still real. No manual/FPS/audio/water/hardware acceptance.

D332 reference remains `C:/Flycast-Evidence/re4-dreamcast/d332b-object-pages`,
disc `/root/probe/d332b-disc`. Its parent-handoff stall is resolved by D333;
object/parts/model-info allocations and pointer checks remain valid.

D331 evidence: `C:/Flycast-Evidence/re4-dreamcast/d331-water-size`, disc
`/root/probe/d331-disc`, unchanged D330 mirror/core and D327 fixtures below.
Two host tests cover guarded allocation/copy, target identity, failure/reuse and
unchanged PPC preprocessing. Target RAM verifies the 64x64 descriptor and owning
buffer. Build options are unchanged. Simpler Dreamcast water is authorized as a
selectable candidate, but has not been implemented or compared with PS2.


D330 final evidence: `C:/Flycast-Evidence/re4-dreamcast/d330b-core-modelinfo`;
initial candidate retained as`d330-core-modelinfo`. Private core`/root/probe/d330-core`,
mirror`/root/probe/d330-mirror`,disc`/root/probe/d330b-disc`,unchanged fixtures
`/root/probe/d327-fixtures`. Build:
`CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1`.
Core producer adds`--compact-core-est` to the existing`--compact-core --core-effects`
path with existing reference textures;143 sequences compact, five unexplained
trailers retained raw. No texture encoding, motion profile or sound dispatch
change. Default producer reproduces D324 bytes. Both manager options default0.

D331's 64x64 source water allocation remains; native render-to-texture and
multi-texture material semantics are still unconnected. The user authorizes a
selectable simpler water candidate, with actual visual review and unchanged
collision/events. No PS2 equivalence is established.

D332 extends `parts_bridge.cpp`, with fixed eight-slot object pages. Indexed
`ObjMgrWork` commits backing without constructing an object; scans use `workAt`
without committing. Object pages are never evicted, even when dead, until source
pool retirement/reset. This is stricter than parts/model-info pressure reclaim.
No capacity reduction or moved object pointer. Host fixtures cover pre-construction
retention, death/reuse, pressure failure, logical predecessor across pages,
full capacity, debug park/restore and owning-heap reset. Actual target validates
all slot mappings; played retry/subscreen is still open. Snapshot has no active
type-4 object light parents, so that lifetime is fixture/source-audit evidence.
EmMgr stays contiguous. Full event/ARAM/audio costs and encounter peak remain.

D329 reference remains`C:/Flycast-Evidence/re4-dreamcast/d329b-parts-demand`.
D330 reuses its demand-backed parts owner/run rules for model-info16-slot pages.
Logical capacities remain1,310/460. Target pointers and all four option combinations
are checked; played retry/subscreen and tool-memory sweeping remain unqualified.

Prior D328 reference evidence: `C:/Flycast-Evidence/re4-dreamcast/d328-resident-effects` (normal-game
loading, corrected menu capture, exact ELF/disc/assets, RAM, source heap/counters)
and `d328b-residency-fixture` (separate SH-4 effect/motion resource qualification).
Game cache:30 misses,29 successful loads,0 evictions/pins,356,416 cached/read bytes,
210,286 us worst successful wait. Warm-up did not complete in the game. The fixture
reaches warm/pressure tests: peak cached981,440, peak pinned32,416, cumulative
pressure185 misses/2,743,392 read bytes, worst wait273,518 us.100 repetitions of
all1,854 effect records are bit-exact with no post-load I/O. O2 fixture timings
are not the O1 live-game frame budget, and neither is physical hardware evidence.

Private inputs `/root/probe/d328-effects`, existing `/root/probe/d327-pl00` and
`d327-wep02`; mirror `/root/probe/d328-mirror`, unchanged fixtures
`/root/probe/d327-fixtures`, game disc `/root/probe/d328-disc`.
Build `CORE_RESIDENT_BYTES=1501312 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776`.
For effects use existing `prepare_enemy_motions.py --compact-effects`, retaining
its texture selection and diagnostic hot-audit flags. Original producer defaults
and D327 output remain selectable. Effects use the existing qualified converter,
archive offset compactor and DVD loader; the native adapter borrows one ESQ index.
No additional full archive, decoded bank, I/O cache or renderer was introduced.

Source key audit `/root/probe/d325-prefetch-final.json` remains required:75 hot
clips/952,768 bytes plus two-largest cold reserve55,168 are diagnostic. Close
repeated-use/immediate-response, indirect R1/event/Work aliases and full instance,
blend/shape/camera concurrency alongside the remaining resource recovery and
source3D connection. Do not replace this with one replay's simultaneous calls.
Required enemy/effect/audio/hold/presentation/retry gates remain visible.

D327's 511,200-byte player/weapon recovery and bounded native DVD/ISR I/O fix
remain in force; do not reopen the resolved lock stall without a new reproduction.
Effect references retain the original source archive lifetime: Espgen00 stores
an opaque archive reference, and EspSeqSet reconstructs it when emitted later.
Unqualified generators, pointer-retaining sprite0x0e, other owners and debug
editor writes remain ordinary; this is not a generic effect-file replacement.
Do not expand families without their consumer/mutation audit. Preserve inherited
dirty files and private generated data. The source PPC path is unchanged.

The later-FPS Blender skill is installed at
`C:/Users/lambd/.codex/skills/re4-blender-model-optimization/SKILL.md`; invoke
`$re4-blender-model-optimization`. Asset-free backup branch
`experiment/r100-environment-blender` is pushed at `fa6a536`. The skill preserves
the rejected D323 pilot and does not promote its assets or supersede residency.

D324 source-menu replay passes with core EFF #1 Path conversion and selectable
externalized effect/HUD texture backing. Actual core reservation 1,501,312;
source heap 9,475,968. Required 1,126,272-byte block pool succeeds, leaving
966,496. First enemy 3,577,728 still fails with 956,192 free: 2,621,536 short
before overhead. Gain vs D322 is 473,696 actual heap bytes. Core identities 59;
CPU noise/palette/mips and unreviewed readers remain. VIB #3 and SAT #9/#10
remain explicitly unqualified. Prior effect-path error absent from this replay;
no claim of full effect behavior/presentation. Source frame1234/Rno0=3/System0x800
still has zero model presentations. Do not clear hold or call room accepted.

Read D324 in R4_NATIVE_PRIMITIVE_LIFETIME_CHECKPOINT.md and current memory targets
in R4_ASSET_RESIDENCY_PLAN.md. Candidate /root/probe/d324-mirror,
core /root/probe/d324-core, disc /root/probe/d324-disc-kos,
fixtures /root/probe/d324-fixtures. Build CORE_RESIDENT_BYTES=1501312.
Evidence C:/Flycast-Evidence/re4-dreamcast/d324-core-effects, validated manifest
and exact dirty-source/executable/assets. D322/full-core references retained;
default still full0x234000 with existing pre-transfer guard. Runtime native backend
unchanged in D324. No physical-hardware or full peak/performance acceptance.

D325/D326 implement selectable motion/texture residency; do not repeat the old
1,823,552 FCV /488,960 texture inventory as if it were untouched recovery.
Preserve active/blending clip lifetime, headers/direct source readers/events and
complete enemy components. Room/player/weapon native backing can supply the rest;
calculate net metadata/scratch/VRAM costs, don't promise a fit from raw ceilings.
The isolated Blender task lives in /root/work/re4-environment-blender, branch
experiment/r100-environment-blender, private Windows re4_helpers/experiments/
r100-environment-d323. Main branch/assets untouched by that subagent. Coordinate
emulator windows. Geometry savings are secondary to the measured multi-megabyte
gap; preserve failed reduction candidates and their reasons without promotion.

D314 remains the first verified source-driven warning/main-menu UI presentation
checkpoint. Adapter 4123a85 and focused capture/interaction validation 8f1578b
are committed/pushed. Corrected images and exact identities are linked from
[R4_SOURCE_UI_CONNECTION_CHECKPOINT.md](port/dreamcast/docs/R4_SOURCE_UI_CONNECTION_CHECKPOINT.md).
Blue D314e captures are invalid. Original archives remain resident; only native
upload staging was reclaimed. No full manual menu/audio/room acceptance.

D315 fixes the boot-forward failure: KOS file opening uses >8 KiB of stack,
exceeding source 6/8 KiB task slots. Native tasks now use the existing stack pool
with a 12 KiB floor (+96,256 resident bytes). The same fixture completes
SubScreenGameInit and returns to r100's block/enemy allocation failures.
Read [R4_SUBSCREEN_BOOT_CHECKPOINT.md](port/dreamcast/docs/R4_SUBSCREEN_BOOT_CHECKPOINT.md).
Evidence: C:/Flycast-Evidence/re4-dreamcast/d315d-stack-budget, 90-second
harness deadline; no native fault, sampled guards intact, 9,272-byte peak use.

D316 reuses one native source primitive buffer after synchronous draw consumption,
retaining full per-frame capacity. Actual r100 heap recovery: 319,488 bytes.
See [D316](port/dreamcast/docs/R4_NATIVE_PRIMITIVE_LIFETIME_CHECKPOINT.md).
The source menu remains visible; both required room allocations still fail:
block pool 1,126,272 versus 427,008 free; em12 3,577,728 versus 416,704.
Both failed, so the combined lower-bound deficit is 4,276,992 before allocator
overhead/intervening allocations. This is not source-archive reclamation.

D317 extracts room/main.cpp clipping/interpolation/color packing and packet
helpers into room/pvr_geometry.hpp/.cpp, compiled into both targets. Native UI
uses the shared packets; the new source menu image and boot-forward replay pass.
The clipper matches the pinned original in 40,000 host comparisons; no source
model/world draw is connected yet. Evidence and limits are in the D316 checkpoint's
D317 section. Current ELF is +128 bytes, with unchanged heap/frontier values.

D318 adds an opt-in commonModelTrans source-model transport adapter using the
shared clipper, texture cache and UI frame owner. Three source-selected room
textures upload and staging is freed, but the matched snapshot has zero emitted
triangles: no visible 3D acceptance. Main parks in the existing scheduler at
OSWakeupThread/TaskSchedulerMain (frame1223, Rno0=3, System0x800); both required
room allocations still fail. Read the D318 section of the lifetime checkpoint
and d318d-source-model / d318e-model-boundary evidence. Scratch is 64 KiB KOS-owned
only with model-diagnostic.flag; unlit/base-material output is explicitly diagnostic.

D319 reuses existing D258 ROOM_MATERIAL_001.dt, with no new encoder run. Shared
Package validation/upload and all material-header consumers now retain native VQ.
Flycast proves18432 resident payload bytes (18464 actual allocation including32
allocator overhead), byte identity c804e363 and VQ sampling flag48000000. Upload
staging18592 is freed; source archives are unchanged. No visible world/VQ quality
acceptance: D318's zero-output scheduler frontier remains. PAL4/PAL8 stay inventory
proposals. Read the D319 addendum in R4A_TEXTURE_INVENTORY_CHECKPOINT.md and
C:/Flycast-Evidence/re4-dreamcast/d319-existing-vq. Preserve the uncompressed fixture.

Implementation bf85bd2 is committed/pushed; D320c now directly loads r100 at3,812,576 versus4,669,568 bytes, recovering
856,992 real source-heap bytes. The required 1,126,272-byte block pool ALLOCATES;
blocks0-2 load/create. First enemy3,577,728 still fails with147,360 free (shortfall
3,430,368 before overhead). 97 offline identities replace upload-only source
texels; mip/palette/CPU-noise/unreviewed payloads remain. Shared Package/storage
now uploads native textures in bounded chunks through the existing64 KiB bounce,
with no whole-package source-heap allocation. Title menu stays visible. Ten
room uploads succeed; the snapshot has435 output triangles/8512 peak packet
bytes but zero model presentations under source System0xc00 hold. Do not clear
that flag to manufacture a scene. Existing effect-path errors continue.
Read the D320 section of R4_NATIVE_PRIMITIVE_LIFETIME_CHECKPOINT.md. Final evidence:
C:/Flycast-Evidence/re4-dreamcast/d320c-qualified-compact, exact identities/manifest.
Candidate mirror /root/probe/d320b-mirror, disc /root/probe/d320c-disc, unchanged
uncompressed textures/input /root/probe/d318d-fixtures. D320a is retained as the
failed full-texture-staging diagnostic. No new world/playability acceptance.

User-authorized next asset strategy: compact or reviewed smaller Dreamcast render
assets, optionally compatible PS2 geometry, must replace costly loaded backing;
retain source gameplay, complete components, original references and measured
CPU/RAM/quality gates. 66% enemy-body target is about2,361,300 bytes, not66% saved.
PS2 enemy audit /root/probe/ps2-enemy-audit shows mesh substitution alone cannot
reach it: all GC meshes are415,040 bytes (11.60%), PS2 top-level BINs are slightly
larger. FCV/SEQ dominate at1,864,928 bytes; texture backing remains another lead.
Structural skeleton correspondence is promising but not deformation acceptance.
Keep source hold/enemy/event requirements visible while pursuing these savings.
The follow-up source-codec check /root/probe/d321-motion-cost.json rejects key-block
dedup as a major win (14,208 within-clip;22,667 global upper-bound bytes). Zlib
per-clip pricing saves437,440 on disc only, with no native cache/CPU acceptance.
Do not implement a new decoder on that estimate alone or drop authored motion.


**Immediate frontier:** bring the existing native cabin mechanisms into the
recovered-game executable. Connect commonModelTrans/ModelRender source-owned
pose, camera, selected lights, materials and model identity; extract applicable
room/main.cpp helpers into shared units. Extend the existing UI PVR frame owner,
with no second scene/backend, copied prototype gameplay or duplicate preparation.
Join that consumer to real resource backing recovery so required block/enemy
creation fits. The single primitive buffer requires synchronous source-array
consumption; future deferred/DMA readers must finish before reset or select two.
Do not restart the resolved stack/subscreen crash or a historical capture campaign.

Subscreen preload control flow passes; inventory does not. Existing ARAM calls
still copy nothing, FNT #0 in ss_cmmn and the ss_pzzl file fail qualification,
and Sscrn module ID 71 is unbound (not invoked during preload). Keep these
requirements explicit before enabling inventory consumers. The new checkpoint
records each request, read/conversion result, ownership and last consumer.

Follow b303de1's whole resource/render correction. Reuse texture_package.*,
room_storage.*, extracted gpu_lifecycle.* and existing draw mechanisms.
Common ID output does not accept fonts/effects/3D/audio or manual menu control.

D313 compact mirror /root/re4data-le-static remains selectable; full reference
/root/re4data-le is preserved. D313 historical block/enemy failures are superseded by D320: the required block
pool fits, but the Ganado body still does not. EVD ARAM dispatch is a placeholder;
r101 EVS remains unqualified and the third opening room unverified.
Preserve inherited dirty source/platform edits; do not broadly stage.

The Astra light helper finished its isolated static-object experiment at
`/root/work/re4-ps2-experiment`, branch `experiment/ps2-asset`, commit `14dd633`.
Result: not worthwhile for this stove/support path; no candidate is promoted.
Its report is `port/dreamcast/docs/PS2_COMPLETE_ASSET_EXPERIMENT.md` on that
branch. The main resource backlog records the negative result. No helper capture
is active; keep the primary task on recovered-game integration.

Once the first room is fully working, create the proven Astra light skill under
AGENTS.md's acceptance requirement. Archive loading alone does not trigger it.

## Working paths

| Purpose | Path |
|---|---|
| Authoritative repository | `/root/work/re4-dreamcast` |
| Windows access to repository | `\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast` |
| Active recovered game executable | `port/dreamcast/game/re4dc-game.elf` |
| Existing native renderer and scene fixtures | `port/dreamcast/room` |
| Extracted private source data | `/root/re4data` |
| Converted little-endian private mirror | `/root/re4data-le` |
| KallistiOS / ports | `/root/work/kos`, `/root/work/kos-ports` |
| Private evidence | `C:\Flycast-Evidence\re4-dreamcast` (`/mnt/c/Flycast-Evidence/re4-dreamcast`) |
| Source disc | `C:\Game Dev\Emulators\Resident Evil 4 Debug (Disc 1)\Resident Evil 4 Debug (Disc 1).iso` |
| Read-only Soulcalibur/Flycast reference | `C:\Game Dev\Emulators\flycast` |

Branch is `dreamcast-port`; origin is `https://github.com/stevedamnvan/re4.git`,
upstream is `https://github.com/adonis-singh/re4.git`. Recheck live Git; the current
resumption point above takes precedence over every historical checkpoint below.

## Historical boot evidence - old next steps superseded

All historical "next" directions below describe that checkpoint's state, not
today's queue. Preserve their hashes and measurements with the original artifact.

The user's completion report for `7d03ad5` matches the inspected 14-file commit:
Dreamcast DVD staging-buffer fix (PowerPC address retained), sound MRAM mirror
handler, fixture-aware disc packaging, scripted pad input, and boot diagnostics.
It records card-check completion, title.dat loading and entry into the ID system.
The reported ProDG comparison was 438 same / 0 different; it was not rerun for
this documentation update and does not qualify subsequent dirty source edits.
The reported clean tree was immediately after that commit, not the current tree.
No source assets or evidence were included; launcher changes stayed private.

At that checkpoint EFF was the next dependency. Subsequent conversion, module,
scheduler and archive-loading work superseded it; use the current resumption
point above. This remains historical boot evidence, not a current task assignment.

## Historical bounded result: D305 (2026-09-21)

The qualified r100 archive now passes the existing mirror gate and is consumed
by recovered ReadAreaData/gameRoomInit. The 55-second scripted Flycast capture
in `C:\Flycast-Evidence\re4-dreamcast\d305-qualified-r100` records the
4,669,568-byte archive and ROOM/FOOT sound-block dispatch. Initialization then
exhausts the room heap: two 0x1680 collision-manager requests see 0x1120 free;
the 0x4b00 event-table request sees 0x6a0 free. Loading is not playable acceptance.
Sound dispatch is not proof of audible output. `read_us=0` is not valid timing.

Next main task: account for source pool/primitive-buffer allocations and loading
lifetimes, then remove demonstrated target overhead without arbitrary gameplay
pool cuts. Preserve the qualified loader and required sound semantics. See the D305 detailed checkpoint for conversion limits, verification and exact
build identities.
r101 remains unqualified because EVS is incomplete. No visible recovered-game
room, manual-play, performance or physical-hardware acceptance is claimed.

Required follow-up after the first room is fully working: create and validate a
reusable agent skill for Astra light (`gpt-6-astra`, low), as specified in
AGENTS.md. Capture the proven procedure and evidence, not this incomplete state.
Keep the existing three-room objective and backlogs active.

## Historical bounded result: D304 (2026-09-21)

The existing mirror now converts source ITM model packs, BLK residency tables,
and named ETM members. FCV/SEQ support reuses the established motion codec;
184 real motions and five named event/sound sequences pass independent wire
checks. r100 has 14 remaining incomplete regions (previously 24), principally
effects, placements/areas, interaction/routes and sound/source tables. No r100
DAR is emitted yet. r120's accepted package remains byte-identical.

See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md)
for exact coverage, remaining tags and evidence. Last ELF/replay is D303; D304
is offline conversion only. Continue required r100 handlers, then replay its
normal initialization once qualified. Do not reimplement motion conversion.

A separately assigned Astra Low sub-agent is investigating one complete PS2
geometry/texture/authored-shading candidate in `/root/work/re4-ps2-experiment`.
Its earlier texture-only commit a6edcba is not the full experiment and is not
promoted. Keep primary boot-forward work independent and coordinate captures.

## Historical bounded result: D303 (2026-09-21)

First-play New Game now follows the source opening-movie skip effects into
r100 before allocating r120 cinematic resources. Flycast confirms normal stage
entry and the explicit rejection of still-unqualified r100.dar. D302 remains
the successful full r120 prepared-archive consumption reference. Next main work:
finish r100 required conversions, emit its qualified container, and replay
normal gameRoomInit. No arbitrary gameplay-pool reduction or alternate assets.
See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md).
Last build/replay D303; no playable/rendering acceptance yet.

## Historical bounded result: D302 (2026-09-21)

The recovered game loads the qualified 6,086,688-byte r120 archive through its
own ReadAreaData/gameRoomInit path. Next failure is source-pool memory demand:
ObjMgr's 433,952-byte request sees only 110,816 free, followed by effect/light
and event-table failures. All 13 r120 entries qualify; r100/r101 remain rejected.
See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md)
for exact evidence and limitations. Next: source initialization residency and
source cutscene completion adaptation; do not arbitrarily shrink gameplay pools.
Last build/replay D302. No playable-room or rendering acceptance yet.

## Historical bounded result: D301 (2026-09-21)

Native ReadAreaData now consumes qualified `.dar` DVD containers directly,
with source sound dispatch and final-buffer allocation. The builder's
`--native-rooms` mode refuses incomplete packages. The D301 Flycast replay
preserves startup/module/player progress and explicitly rejects the missing
qualified r120 package; successful room loading is still pending. See
[R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md).
Next: remaining r120 SHD/EFF/TEX/FSE and SMX callback coverage, then real native
room loading; preserve source cutscene completion effects. Last build/replay D301.

## Historical bounded result: D300 (2026-09-21)

Room cameras, light cuts and the core source brightness-path table now convert.
The apparent legacy core BIN failure was a consumer-specific light-path format;
see [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md)
for the correction, native parent-layout fix, tests and evidence. Next: native
room loading and remaining SHD/EFF/TEX/FSE, callback and animation data coverage.
Sidecars are not wholly qualified. Latest build D300; last target replay D295.

## Historical bounded result: D299 (2026-09-21)

Source ModelData/BIN arrays, palettes, draw identities and morph deltas now
convert; 421 tagged BINs and all nine SMD regions pass. Original numeric arrays
and byte draw streams were independently compared for those tagged models.
One legacy core BIN remains rejected. See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md).
Next: remaining room LIT/CAM and other coverage, FCV animation, and native loading
while preserving original sound-container handling. Entire room sidecars remain
incomplete. Most recent game build D298; most recent target replay D295.

## Historical bounded result: D298 (2026-09-21)

SMD registration metadata and referenced textures now convert across all nine
available regions. SMX masks/colors/UV and known mover layouts convert; two r120
callback work records remain unresolved. Native source flags/colors retain their
GameCube byte meanings. See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md)
for tests, real-data group-count correction and limits. Next: ModelData/BIN
payload conversion, then remaining room data and the native loading boundary.
Sidecars are still incomplete. Last target replay remains D295.

## Historical bounded result: D297 (2026-09-21)

The existing mirror now writes decoded `.arc` sidecars with `--decode-rooms`.
CNS and full source-layout SAT/EAT (including block hierarchy) convert for all
three decoded room fixtures. Native AtPoly word/half-word views agree; the game
build and focused tests pass. See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md).
The sidecars are not runtime-ready: scene/model, lighting/camera and other
formats remain unconverted; two legacy core SAT blocks explicitly fail layout
checks. Next: SMD/SMX and the native loader boundary, preserving sound-container
handling. Last target replay remains D295; no new gameplay acceptance.

## Historical bounded result: D296 (2026-09-21)

The missing r120 archive is now extracted from the source disc. The new offline
`port/dreamcast/tools/decode_yz2.py` executes the recovered PowerPC decoder during
asset preparation; r100, r101 and r120 decode with structurally valid archives.
See [R4_OFFLINE_ROOM_DECODE_CHECKPOINT.md](port/dreamcast/docs/R4_OFFLINE_ROOM_DECODE_CHECKPOINT.md)
for exact outputs, tool identities, tests, limitations and the next implementation.
The runtime YZ2 path is still a stub; decoded archives need endian conversion and
an explicit native loading contract. The last target replay is D295. Do not
rerun the now-present compressed archive and mistake the decoder stub for data
conversion. Working extracted/mirror data changed; preserve D295's exact disc.

## Historical bounded result: D295 (2026-09-21)

The native scheduler now resolves self-directed entry, sleep, chain and exit from
OSGetCurrentThread rather than the mutable pCTask scheduling cursor, and retains
the main scheduler parent separately from the interrupt-task cursor. D293 proved
TaskExit ran with pCTask=-1; D294 exposed TaskSleep waiting on address 0x32f.
D295 clears both observed stalls, finishes em/pl00.drs, and reaches the next
explicit failure: `DVD: File not found : st1/r120.das`. Neither the extracted
source tree nor the little-endian mirror contains that file at this checkpoint.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d295-task-owner`, 55-second scripted
Flycast run using `/root/probe/d292-fixtures`; disc `/root/probe/d295b-disc`.
Build and host execution of the actual native sleep/chain/exit bodies passed.
The scheduler's PowerPC-preprocessed source is identical to HEAD before this
change; this is not a new ProDG object-comparison result. Keep this correction.
Broader KOS suspension semantics, task reuse and transitions remain unqualified.

Next: locate/extract the source room archive from the private disc, inspect its
consumer and mirror coverage, package it, and replay. Do not fabricate room data
or treat r120 cinematic staging as one of the three playable rooms. Visible menus,
rendered recovered-game gameplay, audio and manual acceptance are still open.

ELF SHA-256: `7127776f2d0620f703e64b7fddc8460810ad60062a075bc40b6b9234a1b24041`.
Disc SHA-256: `2ba7625bda9a9e89901a4a5263d6d6a58ba01057c3568f215948304ba4665ed3`.
Flycast SHA-256: `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
The evidence folder retains the tracked dirty patch; other runtime integration
changes remain uncommitted and are not accepted by this scheduler checkpoint.

## Historical bounded implementation result: D291 (2026-09-21)

The current dirty game target now links real stage entry points. The generator
uses `--force-group-allocation` during the partial link before symbol localization;
otherwise duplicate C++ COMDAT selection discarded a module-local definition.
`OSLink` now propagates registry failure; an unknown module clears its entry
pointers and fails instead of executing a placeholder. The link script rejects
missing registered stage prolog/epilog symbols before generating stubs.

Fresh Flycast replay in `C:\Flycast-Evidence\re4-dreamcast\d291-static-stage`
reached `module: id 74 -> st1_0 (static)`, followed by `prolog...`, then read
`etc/emleon00.esl`. The previous raw-REL execution crash was not reproduced.
The new frontier is `TASK DON'T EXEC : level 4` after heap-4 creation; vblank
continues to 3000 without further progress in the 55-second capture. Investigate
DVD/background-task slot ownership and termination before changing scheduler
behavior. Room init/update, light-path correctness and visible gameplay remain
unproved. Title ID-unit-not-found messages remain open too.

Build passed; the nine focused little-endian mirror tests passed. The mirror
reported 779 up-to-date files, with LIT/CAM/SAT/BIN and other raw coverage still
open. Final ELF SHA-256:
`1bee895481958c037e21a5202da481aeb50fd9629613cada81ad076c01841888`.
Disc SHA-256:
`9e5e6b04e440ebf3d0b6a485515e6608a1355fe9daad721ecfb1524ff19a2beb`.
The evidence folder retains the log, ELF, disc, symbols, tracked worktree patch
and module generator/registry snapshots. Runtime integration edits remain dirty;
this is not three-room, visual, manual or hardware acceptance.

Source `src/st1/r120.cpp` confirms r120 is opening cinematic staging and jumps
to r100 through `SceAtExecRoomJump(0x100, ...)`. Do not count r120 as one of three
playable rooms. Preserve the source completion effects when implementing the
user-authorized cinematic skip. Module reload/BSS/constructor limitations remain.

## Historical pre-D291 working-tree report - superseded

At that inspection the tree was dirty across recovered source, platform shims,
module/build tooling, fixtures and endian conversion. Preserve it. New files
include `game/platform/modules.cpp`, `game/tools/gen_modules.py`,
`fixtures/boot-deps.txt`, and `tests/test_le_mirror.py`, under `port/dreamcast`.
They are in-flight work, not an accepted three-room implementation.

The preceding implementor reports New Game reaching room-120 initialization,
then failing at stage REL linkage and light-path/ID data. The registry/generator
now exist and retain `_st1_*_prolog` / `_st1_*_epilog` symbols across partial
links. This report needs a fresh final-ELF symbol check and emulator replay.
At inspection, `OSLink` still returned success regardless of registry failure;
unknown IDs received placeholder entries. Static-module BSS persisted and
constructor execution differed from per-load source semantics. These are open
correctness issues, particularly for retries and transitions.

The historical boot checkpoint describes missing GX/audio implementations. Do
not infer that the recovered game's menu or room is visibly playable from a
frame-loop trace or from the separate room viewer's graphics. Inspect current
adapters and integrate the existing renderer/audio paths as needed.

That report's instruction to resume at the D295 missing archive is superseded
by D296-D306. Follow the single current resumption point above. The remaining
normal menu, gameplay and transition acceptance requirements still apply.

## Existing backlog map

| Document | Role and how to use it |
|---|---|
| [PLAYABLE_PATH.md](port/dreamcast/docs/PLAYABLE_PATH.md) | Authoritative execution order, menu/three-room milestone and source/debug integration backlog. |
| [REALTIME_PATH.md](port/dreamcast/docs/REALTIME_PATH.md) | Supporting performance/fidelity gates. Integration first; representative bottlenecks when they block useful play/testing. |
| [R4_ASSET_RESIDENCY_PLAN.md](port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md) | Existing load/retire/transition infrastructure, native texture handling and explicit alternate-asset policy. |
| [R4_GAME_BOOT_CHECKPOINT.md](port/dreamcast/docs/R4_GAME_BOOT_CHECKPOINT.md) | Dated boot/capture procedure and known source/platform dependencies. Current dirty work may be ahead. |
| [R4_GAME_TARGET_CENSUS.md](port/dreamcast/docs/R4_GAME_TARGET_CENSUS.md) | Compile/platform inventory; compiled symbols are not behavior acceptance. |
| [R4_R101_SOURCE_ENTRY_CHECKPOINT.md](port/dreamcast/docs/R4_R101_SOURCE_ENTRY_CHECKPOINT.md) | Existing source entry/camera fixture and its explicit missing events/enemies/progression. |
| R3*/R4* checkpoint files in `port/dreamcast/docs` | Accepted implementations, corrections and rejected experiments; read only those relevant to the active dependency. |

Do not reimplement completed visibility, strips, light preparation, native texture
layout, ownership or upload-lifetime work because an old handoff calls it next.
The former R3p metrics and 49-test count are historical. The latest room-viewer
measurements do not establish recovered-game performance. Keep the wider chapter,
Disc 1, cutscene, performance and hardware backlogs; they are not prerequisites
to implementing every small opening-route dependency.

## Build and evidence workflow

Run from WSL. This is the bounded D305/D306 diagnostic route, not a qualified
three-room presentation build. Its actual input directory is
`/root/probe/d292-fixtures` (`padscript.txt` plus `diag.txt`). Scripted New Game
still confirms the source title debug menu defaults; it is not manual acceptance.

The real `port/dreamcast/fixtures/boot-deps.txt` is the cold-boot/title manifest
and remains an untracked local integration file. It does not require a room.
Copy it and append r100 ARC/DAR, Leon and the now-observed weapon dependency as
below, including em12 and the four now-observed event archives. D309 passed
through the weapon; the expanded gate fails until event conversion is qualified.
With `set -e`, that failure prevents packaging. The actual saved expanded manifest
is `/root/probe/d312-required.txt`. Also verify native module availability; archive
conversion does not compile enemy code or establish all future consumer coverage.

```bash
set -e
cd /root/work/re4-dreamcast
source port/dreamcast/kos-env.sh
test -f port/dreamcast/fixtures/boot-deps.txt
test -f /root/probe/d292-fixtures/padscript.txt
required=$(mktemp /root/probe/re4-r100-required.XXXXXX)
cat port/dreamcast/fixtures/boot-deps.txt > "$required"
printf '\nst1/r100.arc\nst1/r100.dar\nem/pl00.drs\nem/wep02.drs\nem/em12.drs\nevd/r100s40.evd\nevd/r100s41.evd\nevd/r100s43.evd\nevd/r100s44.evd\n' >> "$required"
mirror_out=$(mktemp -d /root/probe/re4-le-r100.XXXXXX)
python3 port/dreamcast/tools/le_mirror.py /root/re4data "$mirror_out" --native-rooms --require "$required"
make -C port/dreamcast/game -j4
disc_out=$(mktemp -d /root/probe/re4-disc-r100.XXXXXX)
bash port/dreamcast/tools/mkdisc.sh port/dreamcast/game/re4dc-game.elf "$mirror_out" "$disc_out" /root/probe/d292-fixtures
```

Record the generated paths, manifest contents and hashes in evidence. A fresh
mirror avoids stale output. `--native-rooms` emits only qualified DARs and removes
a rejected room's old DAR. Without `--require`, conversion exit zero can coexist
with explicit handler errors: that is inventory, not qualification. Intentional
rejection tests require an incomplete room and expect failure; never package
that as a successful build. Use focused tests for the boundary being changed.
This recipe was inspected, not rerun to rebuild assets for this doc amendment.

Inspect the mirror inputs/output and active processes before rebuilding shared
private data. Choose a new capture folder for each candidate. Existing launcher
and log-reading helpers are under
`C:\Flycast-Evidence\re4-dreamcast\d290-game-boot`; inspect hardcoded paths and
regenerate log symbol addresses from the candidate ELF before using them. Keep
prior `game.bin`, logs, symbols and captures paired with their exact build.
A padscript fixture must be identified in evidence; verify human controls in the
presentation build without automated input.

For runtime work, record exact source/dirty patch, ELF/assets, toolchain/emulator,
fixture and capture identity; reached normal-boot frontier; required stubs hit;
manual checks; frame/input/memory results; keep/revert and next blocker. Keep
PowerPC source-comparison checks for shared-source changes. No new runtime tests
or performance claims were made by this handoff update.

## Preserved audiovisual reference

Keep the existing capture with game audio:
`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2\re4dc-dba07e2-current-progress-32s-with-audio.mp4`.
Later renderer/resource checkpoints retain their own exact comparisons. These
are source-derived presentation references, not proof of current boot-forward
menu, three-room gameplay or physical hardware. Preserve audio in new captures.
