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

## Authorized future phase - gated visual profile

User authorization (2026-09-22) is preserved in
[PS2_INSPIRED_DREAMCAST_PROFILE.md](port/dreamcast/docs/PS2_INSPIRED_DREAMCAST_PROFILE.md).
After prepare-once/reuse-many integration and measured residual Dreamcast cost,
substantial PS2-inspired/Dreamcast-specific visual changes are authorized to meet
performance goals. GameCube gameplay/AI/collision/camera/animation decisions,
events, progression and room semantics remain authoritative; PS2 is a compromise
reference/optional visual input, and Dreamcast-native assets are the final form.
Do not activate substitutions to conceal renderer/lifetime defects. This is a
future gated phase, not a new active experiment; continue the integrated D349
preparation/reuse work now. Preserve this rule in subsequent handoffs alongside
the existing menu/three-room persistent goal and deferred backlogs.

## Carry forward completed side-agent work

The PS2/prelighting deliverable is isolated at `d928ad6` on
`experiment/r100-prelit-d353`, worktree `/root/work/re4-r100-prelit-d353`.
Read its `port/dreamcast/docs/R4_PRELIT_R100_CHECKPOINT.md` when the future
visual-profile gate above opens. The runnable candidate bakes the existing D349
GameCube-selected static lighting into vertex RGB and keeps actors dynamic; it
does not qualify transfer of authored PS2 RGB. Its historical room-target result
saved 634,880 bytes of main-memory headroom and matched six sampled images.
Those results are not recovered-game memory/FPS acceptance. Reuse that converter,
representation and existing native modulation path as one selectable candidate;
do not rerun the inventory or merge its historical room loop/gameplay. The earlier
stove experiment `14dd633` remains rejected and is a separate result.

The first-stage audit already feeds the current execution backlog in
[PLAYABLE_PATH.md](port/dreamcast/docs/PLAYABLE_PATH.md#current-execution-priority-after-the-first-stage-audit).
Its verified opening route is r100 -> r101 -> r103. Converter fix `961c51e` is
already in primary history; the private qualified r101 DAR remains uninstalled
and target loading unproved. Read-only reconciliation at `ee7f6c7` confirmed the
selected r101 DAR, matching r103 DAS, r101 s00/s21/s30 EVDs and em15 DRS are still
absent from their selected locations, and native em15/em26 bindings remain absent.
Use the existing private `next-room-dependency-brief.md` and source exit/event
contracts to qualify these exact dependencies and room retirement, preserving
inventory/health/flags. Earlier audit wording that the empty-EVS converter is
unpromoted is superseded by `961c51e`; do not repeat that fix. The 29-room source
inventory is forward planning, not proof every listed system is missing today
or that whole-stage implementation must precede the three-room objective.

## Active course correction - integrated D349 stack (D352, in progress)

User instruction supersedes individual renderer-component promotion. One
`D349_RENDERER_STACK=0/1` build selector controls the integrated experiment.
Build exactly two target arms from the same recovered source/input/assets:
A latest recovered baseline, B complete compatible native stack. Internal host
checks cover mechanisms; target acceptance applies to the complete stack.
Bisect only after the integrated candidate is visually wrong or unexpectedly slow.
Do not resume separate keep/revert FPS gates for every component.

Snapshot `/root/probe/d352-before` records base7afde16 plus inherited work and
hashes before this implementation. Source camera, current pose/motion, material,
texture animation, cull/facing, visibility and gameplay remain authoritative.
No old room loop, sidecar duplicate scene or sampled animation is permitted.
The shared PVR owner, storage/texture ownership and completed source skinning
remain the boundaries. Source lighting state and native pass organization are
part of this candidate, not deferred post-performance polish.

## D361 current - retained preparation measured; asset budget still unresolved

Commit candidate extends the existing PreparedModelBatch with a room-owned
128KiB direct-source-index workspace:896 positions,2560 normals/complete lit
values. Model/frame generations survive local-span changes. Pose/camera,
normal-matrix, selected lights, channels and mutable source colors retain their
existing invalidation. Shared normals still check their position/color identity;
no corner remap, hash probing, fixed lighting or topology-budget growth.

Same selected D360 assets,106 exact source snapshots at ticks2387-2492:
render p50/p95 improves1562.865/1564.571 ->1368.078/1370.789ms (12.5% median),
presentation p50/p95 improves1589.783/1606.466 ->1389.601/1406.282ms.
Packets/VRAM/queue/212 flushes/171strip fallbacks are unchanged. Source free and
largest block=82,688B after the131,136B actual cell, versus213,824 in D360;
this still leaves16,096B more than pre-D360. Heap capacity and required large
block/enemy allocations are unchanged. The current renderer remains unusably slow.

Evidence: C:/Flycast-Evidence/re4-dreamcast/d361-retained-model;
private disc is on D: via that directory's disc-output junction. Existing
capture tooling and fixture are reused. Capture ended at its340s deadline,
not a game crash. Both selector/asset candidates remain default-off. Source
menu/outdoor Leon/cabin/HUD were observed; no new combat/audio/retry acceptance.
Allocation/failure counters disabled in normal builds remain unmeasured; see
[R4_NATIVE_PREPARATION_CHECKPOINT.md#d361---retained-modelframe-preparation-2026-09-22](port/dreamcast/docs/R4_NATIVE_PREPARATION_CHECKPOINT.md#d361---retained-modelframe-preparation-2026-09-22)
for exact evidence, upload brackets, allocator and host qualification.

Do not restart slot/admission tuning. This proves a useful reuse correction,
not full D349-equivalent costs.841,824 fallback GX bytes/frame and3,578,720
median packet bytes remain. The user has asked about making the render assets
fit the available budget offline instead of preserving expensive layouts. Use
the existing native converters/ownership and isolated prelighting deliverable
for that representation decision; price replacements against actual retained
source consumers and CPU/RAM/VRAM costs. No new inventory, parallel renderer or
automatic PS2 substitution is authorized by this result. Preserve the future
visual-profile gate and distinguish remaining avoidable work from intended
quality changes. The next boundary must replace costly loaded render backing,
not merely add another cached representation. Three-room gameplay is unfinished.

## Previous D360 - actual room memory recovered

A default-off `--compact-room-palettes` extension to the existing compact/native
path releases three immutable r100 EFF index images while retaining checked CLUTs,
descriptors, animation, packed effects and sound. The real loaded room allocation
falls 3,754,592->3,607,360 bytes; captured source heap free AND largest block rise
66,592->213,824. The required block/enemy bodies remain allocated, with 422 live
allocations and unchanged heap capacity. Existing native textures/VRAM are unchanged;
this is not native PAL support or a rendering speedup.

Private candidate `/root/probe/d360-mirror` and capture
`C:/Flycast-Evidence/re4-dreamcast/d360-indexed-room` preserve the visible source
menu and outdoor Leon/cabin/HUD. The three new effect uploads are not sampled in
that route. Focused host tests cover identity, retained palettes and owner cycles.
Same-global-tick comparison fails by one loading update; do not call it a matched
performance pass. Full rendering remains ~1.56 seconds. Current assets stay default.

Next: use the measured 147,232-byte replacement to fund genuinely retained D349
static preparation at the existing owner boundary, preserving net source headroom,
source-selected light dependencies and the 8 KiB metadata cap. No admission tuning
or PS2-profile activation. The next renderer A/B must use the same selected assets
in both arms. See [D360](port/dreamcast/docs/R4_NATIVE_PREPARATION_CHECKPOINT.md#d360---selectable-indexed-texture-backing-release-2026-09-22)
for recipes, exact identities, failed gates and remaining qualification. Inherited
dirty integration edits remain separate; HEAD alone is not the captured executable.

## Previous D359 - implementation committed; stop admission tuning

Renderer cohort `8bdb4dd` is pushed. Both selector arms link from a separate clean
snapshot; focused correctness checks pass. The inherited source/fixture/event
integration overlay is preserved separately, so HEAD alone still does not
reproduce the recorded boot-to-room build.

The first current normal-build A/B disables detailed profiling/audit and retains
only existing frame/source/work observations.107 matched ticks2387-2493 have
identical recorded source snapshots, consecutive presentation, zero measured
queue drops/discards and unchanged66,592B source free. B render p50/p95 is
1562.056/1564.143ms; presentation p50/p95 is1589.783/1606.466ms. Old~1973ms
profiling results included~975k clock reads/frame. Normal cost is still unusable;
removing diagnostics is not the missing preparation architecture. Disabled
allocation/upload metrics remain unmeasured, not zero-failure assertions.

Qualified replay of53 static parts (43% of references) proves the hybrid cache
adds827 position transforms and avoids only732 shade evaluations compared with
the existing fallback. End admission-ranking work. Next is one meaningful
source-to-native preparation/ownership replacement for qualified static render
backing, including the retained-data budget and source light invalidation. Use
existing resource code; do not add another cache, grow metadata/source budgets,
or import the prototype loop. Restore prepare-once/reuse-many as a resource
contract, then judge the complete stack. If it cannot fit, report the exact
replacement/net-budget limit rather than extending the tuning loop.

See [D359](port/dreamcast/docs/R4_NATIVE_PREPARATION_CHECKPOINT.md#d359---committed-stack-real-build-cost-end-admission-tuning-2026-09-22)
for exact builds/evidence, attribution and limits. Both captures have ended; no
emulator window remains owned. The PS2 visual-profile gate and three-room goal
are unchanged.

## Previous D358 - admission improved, actual reuse still incomplete

Full D358v2 A/B passes the measured stability/source-snapshot gates for
78 matched ticks2387-2464, but B render p50/p95 is
1,972.755/1,974.568ms: no meaningful improvement over D357v3.
Global installation-time descriptor admission replaces first-arrival local
allocation within the same 8 KiB;256 descriptors use 5,984 B. Dense position coverage
rises 12.95%->34.09%, yet actual transforms 133,147->133,111 and individual-light
evaluations 387,402->384,223 barely change. Packet flushes 212/fallbacks 171,
source free 66,592B and VRAM are unchanged. Presentation remains accepted for now.

The historical next check (completed in D359) was hit/loss attribution in the existing captured-source
replay: existing 64-slot fallback tables already reuse positions and complete
lighting across strips; short dense-domain generations can replace those hits
or lose them. The local score counts gross repetition, not additional work
avoided. Count hit-in-both/dense-only/fallback-only/miss-in-both with actual
admission; include both RGB-pack branches. normal_hits and color_packs are
conditional counters, not total work. Correct the same preparation architecture,
not another keyed cache or per-feature promotion. Full-stack A/B remains the unit.

The historical review and D358 source classification reject broad group-bounds
admission as current priority (only 0.761 ms of whole-part work conservatively
rejects in this view). Invariant room lighting still needs source light
identity/provenance/lifetime; PS2/prelighting substitution remains gated.

Initial D358 B failed native metadata allocation. Cold qsort reuse removed 2,636 B
of duplicate code; corrected v2 is 692 B smaller than D357v3 and passes. No source
capacity/compiler changes. Current implementation remains in the preserved dirty
integration overlay; do not imply clean HEAD reproduces it or stage unrelated
inherited source changes. Runtime commit cohort was reviewed separately, including
isolated Makefile/model/trans hunks; clean-checkout link qualification is pending.
See [D358](port/dreamcast/docs/R4_NATIVE_PREPARATION_CHECKPOINT.md#d358---global-admission-and-remaining-reuse-gap-2026-09-22)
for recipes, exact identities, tests, counters, rejected run and limits. Both v2
captures have ended; no emulator window remains owned.

## Previous D357 - source-backed index spans

The user's 314 KiB versus 8 KiB decision rejects persistent per-corner remaps.
Current `DrawLocalPlan` contains only 20-byte legal span descriptors; immutable
source corner/index streams remain backing. Dense channels use source index
minus batch base, with independent position/normal and qualified exact shade
identity. Whole strips/fans remain intact; uncovered work uses the reference.
The existing 8 KiB local metadata and 12 KiB frame workspace do not grow.
Finite admission ranks reusable spans within available space, not whole parts.
Do not describe D356's explicit per-corner mapping as the active implementation.

Focused host fixtures pass; tick2382 replay retains all 262 part counts, both
ordered-reference hashes and 40,374 expanded triangles/byte hashes. This host
replay regenerates unbounded local metadata: it does not prove target coverage
or performance. Current capture reads 19-word sealed preparation telemetry,
including normal/shade dense references. Audit mode3 samples five source ticks
2382-2386; exclude those logging frames from steady timing.

Initial D357 B is rejected before comparison: native texture-metadata allocation
fails, warm-up never qualifies. Detailed audit + duplicated load-time builder
grew the resident executable by 11,732 bytes over D356v4 B; disabling the optional
audit alone still added 8,004 bytes. One shared non-template install walker
removes 4,038 bytes of duplicate code, with unchanged algorithm/budgets and
passing focused tests. No compiler policy or source-heap capacity was cut.
D357v3 now completes 78 matching recorded source snapshots/ticks
2387-2464. Both arms have zero measured discards/queue drops,
native allocation/texture failures and warm uploads, with queue high-water below
capacity. Render p50/p95: A 1,211.301/1,213.904 ms,
B 1,971.792/1,973.605 ms; presentation p50:
A 1,236.963 ms, B 2,006.830 ms.
This is an instrumented settled-view comparison, not release FPS, full source/RNG
parity, manual combat or hardware acceptance. A remains material/lighting limited;
B retains the intended richer source presentation. The complete candidate stays
default-off and performance is not accepted.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d357v3[a|b]-integrated-stack`,
`d357v3-comparison.json`; recipes `/root/probe/d357v3-build-arm.sh` and
`d357v3-prepare-arm.py`. B ELF
`d9e9b103e34852aa072550433b0ae42ad734bfd39cd50b4ac622794e43d45ddb`, A
`cfe5673749cf0d58f71e71215c97d681c2df14b983c35790c74e86fd42442d71`.
Dense position coverage is 25,985/200,643 (12.95%), normal 27,212 (13.56%) and
shade 27,301 (13.61%). Light builds/hits remain114/149; packet flushes 212 and
strip fallbacks 171. Metadata/workspace/source capacity have not grown.
Three complete current audit frames (2382/2385/2386,263 parts each) identify167
fully position-fallback parts with159,163 references and whole-part transform/
light/packet cost380.83/607.26/371.07 ms. Historical D355 ordinal/hash qualification
does not apply to this changed263-part record; two other witness frames lost two
records each and are excluded. Do not label those whole-part spans fallback-only.

The simultaneous history audit identifies the next integration issue: qualified
coverage, not another math kernel. Structural-plan rejection currently withholds
local slots AND early bounds; first-arrival part admission and sparse source
indices further limit coverage. D349's full dense renumbering and large prepared
bounds cannot be copied into the current budget. Classify the dominant uncovered
streams by structural budget, index range/distinct count, and bounds eligibility;
then adapt existing admission/bounds under the same budget. Historical invariant
room-light reuse also remains unadapted: the bridge lacks pre-camera light
identity/provenance/change serials, and the old tiny static cache is disabled.
Restoring that source-faithful lifetime is distinct from the gated PS2 compromise.
See the D357 section in R4_NATIVE_PREPARATION_CHECKPOINT.md for exact commits,
current seams, limitations and the supporting current-work report. Do not start
another cache framework or restore per-corner maps. Initial D357 discs are
SHA-verified deltas; accepted D356v4 B stays whole. Both v3 captures have ended.

## Previous D356 - load-time local indices and generation slots (2026-09-22)

The user accepts D356v4 B's current visual presentation as accurate for now.
Do not resume the A/B visual-gap investigation. Preserve that appearance while
completing preparation reuse; performance acceptance is still open.

Keep the whole default-off D349 renderer stack as the acceptance unit. The user
rejected hot keyed lookup/retirement, consistent with historical R3s. Do not tune
that cache or abandon the measured reuse opportunity. R3v/R3x means asset-lifetime
local indices, direct slot arrays and boundary-qualified generations.

D355's source audit qualifies five exact ticks, 2382-2386 (1,310 part records).
Positions: 132,776 transforms / 70,118 distinct inputs; normals: 156,075 / 82,717;
vertex lighting: 156,075 / 100,531 distinct position-normal/lit inputs. There are
262 light preparations but 115 model/info light states. Most reuse is within
parts/strips, not across parts. `/root/probe/d355-checkpoint.md` and private
`d355b-reuse-audit/reuse-report.json` retain the full key definitions and top-ten
model/batch tables. Do not claim all 70 audit ticks qualify.

The D355v2 keyed variant is rejected: about 2,318 ms instrumented render p50,
slower despite reduced arithmetic. D355v3 completed as an obsolete keyed variant;
do not run its A arm or promote it. Both private discs are verified xdelta3.

D356 replaces lookup/retirement with `DrawLocalPlan` in existing
`room/native_draw_plan.*` and the existing source archive owner. Load-time records
contain local corner IDs and separate position/normal links; live source arrays,
UV/color references and source display lists remain authoritative backing. No
geometry/pose copy. Qualified slots use a generation comparison and direct index.
Pose, light list, channel and normal-matrix dependencies are checked at the source
submission/batch boundary. Mutable vertex RGB invalidates its shade generation
at that boundary until a source publication serial exists. Frame/owner changes
invalidate generations. Oversize strips and uncovered data stay explicit fallbacks.

Memory stays within the existing 64 KiB native slab: 12 KiB packets, 12 KiB shared
preparation workspace, 8 KiB queue spill and 32 KiB metadata. Local mappings have
an 8 KiB partition of metadata; compact owner records retain their source keys.
No source-heap cut, queue growth or new allocator. Mapping/structural coverage and
packet/fallback costs must be reported; finite admission is not full-scene reuse.

Thirteen focused host checks pass (including actual source OT admission); the
native-model fixture additionally exercises seven forced serial-wrap boundaries.
Captured tick2382's 262 source parts retain the reference expanded-triangle byte
hashes in host replay. This does not qualify target images or full gameplay.
Admission now visits the source's accepted OT registrations at the pre-render
boundary, actors first for bounded metadata admission only. It reuses existing
plans each boundary and installs only newly encountered assets; later visibility
is not gated solely by an asset-dirty flag. Source draw/update order is unchanged.

D356v1 was an admission-negative diagnostic: its local mappings covered zero
visible references. D356v2 packaging failed during WSL I/O trouble; the normal
WSL utility-VM restart recovered the unchanged source/ELF. Neither is accepted.
D356v3 A completed 159 contiguous measured source ticks 2382-2540, with zero
measured discards/queue drops/native allocation failures/warm uploads; render
p50/p95 1191.811/1194.388 ms, pageflip p50 1220.280 ms. B stalled before its first
model submission, so these are NOT a qualified pair or a dense-slot FPS result.
The exact B diagnostic is preserved at
C:/Flycast-Evidence/re4-dreamcast/d356v3b-admission-diagnostic: GameTask waits in
readEmData for em/em23.drs request 32; pCur_queue and pending-list head both point
to the same PUSH slot, while both DVD workers are stopped. Saved/active nested
headers still describe completed em12. The borrowed synchronous DVD request
could restore a completed/recycled slot after native I/O yielded.

The current v4 candidate extends the existing native DVD step owner across the
source blockRead borrow and ReadProc completion publication. Same-thread nested
steps reuse that guard; foreign pumps yield, with no IRQ held over I/O. Restore
requires the same live, unpublished request ID. Completion only clears its own
current pointer; scope ends before task exit. Original PowerPC preprocessing is
unchanged; full ProDG object comparison was not rerun. Focused actual-body tests
pass optimized and ASAN/UBSAN completion/reuse/ownership/header-lifetime cases.
Do not fix orphaned requests by forcing source flags or skipping em23.

Full-stack v4 recipes are /root/probe/d356v4-build-arm.sh and
/root/probe/d356v4-prepare-arm.py, output
C:/Flycast-Evidence/re4-dreamcast/d356v4[a|b]-integrated-stack.
Both use the same source/assets/fixture and corrected DVD boundary. B ELF SHA256
ac75515e925c89b60c544e92b0bd744504ff0d163d9e0c4f5c7ccf2170b82dba;
A 4c71d4d52e8eeba66915c48379755e76283f01a1743d5843c8b2948599743d36.
Both v4 arms completed:85 matching recorded source snapshots/ticks 2382-2466,
with zero measured discards/drops/native allocation or texture failures/warm
uploads and stable queue occupancy. Matched render p50/p95:A 1192.463/1195.034 ms,
B 1948.184/1950.040 ms; pageflip p50:A 1220.280 ms,B 1973.462 ms. Not promoted.
B light preparation is 114 builds/149 hits, but dense slots cover only 2,970 of
200,643 references (1.48%). Final local metadata is 8192/8192 bytes (12 parts,
22 batches), with structural metadata also full. The current explicit mapping
formula needs 314,429 B across 239 tracked streams; several costly parts cannot
ever fit8 KiB. Do not solve this with more source heap or keyed lookup. Continue
the source-backed compact batch representation, preserving whole strips/order;
implicit range qualification helps some batches but does not cover the largest
costly parts yet. Full analysis is in the D356 native preparation checkpoint and
/root/probe/d356v4-admission-review.md. Capture/report tools remain
the existing adapted fixture and matched sealed telemetry. Do not overwrite
outputs. D356v3 discs are preserved as SHA-verified xdelta3 against the existing
D351c base; all logs, snapshots, captures and source identities remain private.
Snapshot /root/probe/d356-before retains the pre-edit patch and owned files.

## Previous qualified reference - D354 stable integrated profile, not promoted

Primary runtime checkpoint is f2ed3dc (native DVD borrow ownership; e698b98 preserves the gated future profile; 73f4af3 owns the earlier profiler/checkpoint), with inherited/D352/D354 changes in the
working tree. Do not stage them wholesale. D353 is isolated at d928ad6 on
experiment/r100-prelit-d353, not merged. The persistent three-room goal is active;
wholesale D349 renderer integration is the immediate priority. Profiling informs
that one candidate, not independent promotion of historical mechanisms.

D354v8 completes the first stable exact-tick comparison: 70 identical recorded
source snapshots at ticks 2382-2451, native frames 2383-2452 and 70 consecutive
presentations 2349-2418. Zero measured aborts/queue drops/texture or native allocation
failures and zero post-warm-up uploads. Source heap stays 66,592 bytes in both;
B queue high-water 25,536 < 26,624. The fixture is a settled opening view, not combat,
manual responsiveness, death/retry or full state/RNG parity. One warm-up discard
and the initial oversized-arena probe remain explicit in the checkpoint.

Instrumented render-wall p50/p95: A 1191.831/1194.561 ms;
B 1842.358/1844.195 ms. Presented interval p50: A 1220.281 ms, B 1873.373 ms.
B's dominant exclusive stages are lighting 723.596 ms, packet preparation 456.764 ms
and transform/project 377.852 ms; topology 40.108 ms, clipping 159.034 ms, transfer~10 ms.
Source preparation remains~9.9 ms: do not optimize it next. A is unlit/material
limited; B does more source-selected work, so this is not equal visual coverage.
Scope overhead is substantial (~185/329 ms empty-scope estimates); do not subtract
these as exact corrections or call the figures release FPS. Timers use existing
TMU2, never PRFC0/PRFC1 configuration; PVR asynchronous render time is separate.

Direct strips and hardware culling already work: B 10,411-10,428 intact strips,
zero reconstructed qualified strips, 192 depth fallbacks, 153 OP hardware-cull
headers,81 TR; no qualified PT. Do not rebuild FTRV, native compiler policy or OP
submission. Compact metadata is full at 32 KiB, 543,200 GX bytes/frame still decoded,
and dense local-slot coverage is only 2.4%. Prepared source-light records do not
yet recover the historical invariant preparation/reuse. This is the integrated
input-contract gap to address next: bounded shared position/normal preparation,
selected lighting and packet assembly, preserving source backing/generations.
Do not turn that into another per-subfeature target promotion sequence or add a
fourth cache/geometry copy. No queue growth or source capacity cut is authorized.

The D354 reference 64 KiB slab retained 24 KiB packets, 8 KiB deferred spill, 32 KiB metadata.
A common metadata rebalance (80 texture handles/128 source-key entries) serves
B's 70 pinned textures and removes 2,048 static bytes versus 64/256. Nine qualified
pairs were prepared through existing converters; private d354v7-fixtures inherits
them. Source texels/geometry/collision/actors are not removed to obtain the run.

Evidence: C:/Flycast-Evidence/re4-dreamcast/d354v8a-integrated-stack and
.../d354v8b-integrated-stack. Parent d354v8-comparison.json/report.py contain the
matched data/analysis. Recipes: /root/probe/d354v8-build-arm.sh a|b and
/root/probe/d354v8-prepare-arm.py a|b; do not overwrite existing outputs. Build
snapshots: /root/probe/d354v8-arm-a/b. KOS d336/GCC 15.2 and d343-mirror unchanged.
Both use NATIVE_RENDER_PROFILE=1 and fixture /root/probe/d354v7-fixtures; this is
not reproducible from clean HEAD. Per-arm manifests preserve exact dirty source,
ELF/disc/assets/config/capture identities. The existing pad parser now supports
optional source-clock scheduling and CRLF. Three optional logo-skip requests
expire, while card/menu/START reach normal GameTask at matched source ticks.

See [D354 checkpoint](port/dreamcast/docs/R4_NATIVE_PREPARATION_CHECKPOINT.md#d354---stable-integrated-profile-not-performance-acceptance-2026-09-22)
for full stage/work/memory tables, source snapshot limits, tests and rejected
v4-clock/v5-handle/v6-tick/v7-CRLF results. All owned v1-v7 discs were preserved
as verified xdelta3; v8 A is now also a verified delta and accepted v8 B remains whole. Final imagery still does not qualify full
materials/sky/fog/complete enemy encounter. The candidate remains default-off.
Keep source events, audio, inventory, transitions/retry, manual play and physical
hardware open. Preserve the separate D349 reference and corrected source facing.

## Active uncommitted work after D346

The [execution priority](port/dreamcast/docs/PLAYABLE_PATH.md#current-execution-priority-after-the-first-stage-audit)
now reflects the completed first-stage audit. Event/combat remains pending behind the user-directed renderer integration; movie-owned cleanup proceeds in its isolated
worktree. The auditor established r100 -> r101 -> r103 and identified the
required exit/event/data contracts. Water is queued behind the demonstrated movie-to-room allocation
failure. No experimental movie/water code has been promoted into this checkout.

Local `R100_DEFER_EVENTS=1` is built and host-tested, with target acceptance still
pending. It narrowly certifies r100 s03/s20 presentation references and retains
their original source wrapper continuations; it is default-off. Reproduce with
`/root/probe/d347-build.sh`; focused tests are `test_event_file.py`,
`test_event_borrow.py`, and `test_r100_event_completion.py`. ELF text/data/BSS is
2,311,908 / 77,016 / 673,464 (+972 text versus D346). R100 PowerPC tokens and all
63 inherited tracked dirty-file hashes are unchanged, recorded in
`/root/probe/d347-source-check.json`. D347a/b target runs preserve normal
menu/room initialization and cached motion, but their controller routes hit
collision before the event. No event acceptance or memory saving is claimed.
D347c also missed the event: route timing was aligned to host time rather
than logged input retraces. The D347e keyboard route was subsequently stopped at the user's request to prioritize native room-renderer reuse. No event acceptance was reached. Keep `/root/probe/d347-before` as the pre-edit ownership snapshot;
do not commit inherited edits or call these host checks playable acceptance.

The movie A6 candidate decodes all 1,971 pictures and restores source heap/VRAM
and its owned stream service, but post-movie em12 loading stalls with DVD queue
step=4 where the handler implements only 0..3. Reentry remains a hypothesis; the A7 stack-linked diagnostic must be revised
because native thread cancellation does not unwind its scope. A4's later 65,536-byte native packet allocation
failure remains an independent KOS-heap limit; source free bytes are not that
budget. Audio starvation remains audible/unaccepted. A7 is a separate pending
ownership diagnostic, not a qualified replacement.

The base before this D350/D351 checkpoint was
`ed9165bc7069232df840aba5a70150166b21989b`, pushed and remote-verified
D349 reference/status documentation. Use git log/status for the current commit. Previous reviewed
converter commit `961c51ef3e2ee51b2fd583cd213a0302705bccb7` qualifies r101's
bounded empty EVS; 30 focused converter tests pass. Its private qualified DAR
is `/root/probe/r101-empty-evs-nxv127uu/r101.dar`, 10,499,648 transport bytes,
not heap demand. It has not been loaded
by the target or installed in `/root/probe/d343-mirror`. R103 data, r101 s00/s21/
s30 events, em15 data and em15/em26 native bindings remain explicit next-room
requirements. See `R4_R101_EMPTY_EVS_CHECKPOINT.md` and the private
`/root/probe/re4-opening-gap-audit-20260922/next-room-dependency-brief.md`.

D347's runtime ELF is unchanged by this converter commit: it was built from
D346 plus its recorded inherited overlay and the local event candidate. Its
SHA256 is `f5f984abc1c3a2b1733614a3ef4f8bea2f2590a90b2e5cb021b136fb9490ddf6`.
Keep executable identity separate from the later source HEAD.

All agents require exclusive emulator windows. The user has released the
historical manual window for root integration tests; check live ownership before
launching. The completed D347a/b diagnostics were moved to the matching D:
evidence suffixes; C: junctions preserve the original paths. All 1,697 files
were hash-verified, 1,668,954,190 bytes relocated; manifests are in
`/root/probe/d347-evidence-relocation.json` and per-run relocation hashes.
No accepted evidence was deleted. Current audit reports are in
`/root/probe/re4-opening-gap-audit-20260922`; reuse these, not a new inventory.

## Ended manual observation session - D347e (historical)

The primary candidate was opened for keyboard control and then stopped
at the user's explicit request to prioritize renderer reuse
in `C:/Flycast-Evidence/re4-dreamcast/d347e-manual-keyboard`, PID 20588 at launch.
Verify that PID and executable path before interacting; it may change/exit.
This D347e window and the later D349 manual reference are closed.
`attach-observer.py` reuses the existing observer for up to one hour and
leave Flycast open when observation ends. Do not apply the historical automatic
240-second stop. Startup-only `padscript.txt` navigates card/title/New Game;
there are no automated gameplay inputs. The existing model diagnostic flag is
present, with source-state/material/lighting/audio acceptance limits unchanged.

Private `mappings/SDL_Keyboard.cfg` explicitly supplies the standard keyboard
mapping: arrows movement/turn, C run/cancel, X action/fire, V right trigger/aim,
F left trigger/knife, Enter Start. No shared emulator preferences were changed.
All delivered real pad edges are logged separately from the startup fixture.
User flagged unacceptable slowness: current observed frame interval~1.62s,
registration interval~1.58s, GPU interval~7.5 ms. These overlapping/source-spanning
intervals are not a precise stage profile. Earlier~58 ms/17fps was the optimized
room/ reference, not current recovered game/. Auditor has a read-only bounded
follow-up on repeated work and existing timing/counter access. The run is ended. Four asynchronous saved source timer samples place RENDER
SETUP at about 1.54 seconds of a 1.60-second CPU loop; see its private
`manual-stop-profile.json`. Overlapping PVR registration is not pure draw CPU.

This ELF is `3d56e49f1b3164c16a3aec52589002604e2f10945f9a0f40e3673d45f5ebdb92`,
same 2,311,908 / 77,016 / 673,464 sizes, disc SHA256
`ff35ec0127a53ccf0a4ed1c1965e8fe49558cedcc439b73f7cc3532e3390669e`.
It additionally moves the s20 guard after the original event-availability wait.
The focused sanitizer test includes a busy existing event and passes. This
ordering fix is not present in D347a/b/c; keep their identities separate.
Reproduction: `/root/probe/d347-build.sh`, `/root/probe/d347d-prepare.py`, then
correct the private legacy keyboard mapping to version=2 (the D347d recipe
mistakenly wrote version=3 with legacy fields, producing no keyboard bindings).
D347d ended deliberately for that correction with no real input delivered.
D347e uses hardlinks to the same immutable ELF/disc/emulator to avoid duplicate
storage. Its initial RAM observer lost a startup race (600 ms discovery versus
~717 ms RAM log); Flycast continued normally. `attach-observer.py` attaches the
existing reader to that live PID without rebooting or writing game state.
Attachment-relative sample times are not boot-relative. The game has now logged
real keyboard Up (0008) and source movement from approximately
(-99690,-454,-1344) to (-98900,-341,-1963). Manual event acceptance remains pending.
No manual encounter result is claimed yet. Monitor source s03 completion,
actual delivered keyboard input, enemy activation, memory and the next failure.
Movie A7 and water bridge2 OFF/ON candidates are packaged in their separate
worktrees, quiet and awaiting a later exclusive emulator window.

## Current resumption point - D346 counted task handoff

D346 replaces the timing-dependent native task handoff with counted dispatch
and resume signals using the existing semaphores. A faster diagnostic exposed a
live window scenario wrongly marked finished; it now advances through the house
approach and qualified s03/s20 preloads. The 3D-enabled 240-second run preserves
visible source title/menu, room, Leon and HUD at 640x480. This remains diagnostic
presentation, not full/manual encounter, material/lighting or audio acceptance.

Required block/em12 allocations retain 2,921,856 / 1,806,336 free bytes. The
visible run finishes with 66,592 free/largest; the farther diagnostic reaches
43,232. D346 recovers **zero additional heap**. Hot motion stays cached at
952,768 bytes with no later reloads. Event-borrow preflight now rejects a bad
destination/load/immutable transport before unregistering Ganado effects; actual
activation and writable snapshots remain unimplemented. The straight approach
fixture stops at collision before that new rejection is exercised on target.

Source masks/no-image materials, lighting, event activation, audio/inventory,
manual combat, transitions/retry and hardware acceptance remain open. Simpler
water stays an unimplemented selectable quality candidate, with no measured
saving or verified PS2 equivalence.

Selected visible evidence: `D:/Flycast-Evidence/re4-dreamcast/d346d-visible-handoff`
(also reachable at the same `C:/Flycast-Evidence/re4-dreamcast/` suffix via a
junction). Diagnostic with 3D disabled: `C:/Flycast-Evidence/re4-dreamcast/
d346b-counted-handoff`. Both end at the 240-second harness deadline. No emulator
is left running. The selected ELF SHA256 is
`c2047abf138bcc3570272a10d7243f279a685ee150bf50f25260bd4c99b8bbff`;
text/data/BSS 2,310,936 / 77,016 / 673,464 (+144 / 0 / +352 versus D345).
Source heap capacity remains 8,840,576. Five focused tests pass, including
actual threaded source task bodies in both completion orders, source event
borrow/restore, immutable transport and source-unit relocation under sanitizers.
Both edited source files have identical PowerPC preprocessed tokens; no new
ProDG comparison. All 63 inherited tracked edits remain byte-preserved.

Reuse `/root/probe/d346-build.sh`, `d346b-prepare.py`, `d346d-prepare.py`,
`d346-analyze.py`, `d346-pointer-proofs.py` and `d346-check.py`; create fresh
outputs. Build options/KOS/mirror remain D345's. D346b uses
`/root/probe/d346a-fixtures` (only the existing model diagnostic opt-in removed);
D346d uses unchanged `/root/probe/d344b-fixtures`. D346d reused the exact C ELF
and disc after the C capture ran out of host storage. C's partial 65-second RAM
snapshot is invalid, not a game failure. D346a is the reproduced scheduler
failure, not an accepted run. It now resides on D: with its original C: path
preserved by junction; all 837 moved files were hash-verified. Do not overwrite
these runs or the D345 reference. Source parent is
`0c2e9397ffe8e4bf947656b08ca03964d9f7f679`.

Next source-event boundary: the qualified s03 request is 1,341,504 bytes,
exceeding the compact em12 body (1,105,152) by 236,352 before accounting for a
writable enemy snapshot. S20's 689,632-byte MRAM activation also does not fit
current headroom. Retain hot keys and source prefetch/concurrency ownership;
immutable preload is not activation. Continue a justified event lifetime or
source-completion adaptation under the authorized cutscene deferral, and the
separate native mask/lighting connections. Do not use a failed read as a skip.
The D346 mask audit finds model alpha_omit=128 overrides in addition to soft
mask texels, so part alphaRef=0 does not qualify binary punch-through.
See [D346](port/dreamcast/docs/R4_EVENT_ENEMY_CHECKPOINT.md#d346-counted-task-handoff-and-event-borrow-preflight).

## Previous D345 checkpoint - source alpha and nested handoff

D345 connects source-selected material/vertex alpha to the existing native model
path and fixes a native nested-task handoff exposed by the changed render timing.
The selected 240-second run preserves visible title/menu, HUD and source-controlled
640x480 diagnostic room movement. The opening scenario finishes normally; no
source allocation failures occur. This is not complete material/lighting,
encounter, audio, manual-play or performance acceptance.

D344's memory result remains intact: free heap after required block/em12
allocations is 2,921,856 / 1,806,336 bytes, final free/largest is 66,592, and all
five crows retain valid 24-part chains. D345 recovers **zero additional heap**.
Hot motion remains cached (952,768 bytes; no later reloads). Source mask materials
(flag 0x04), a no-image part, lighting and event activation/mutable snapshots
remain exact integration boundaries; retain their explicit checks. Simpler water
is an unimplemented selectable quality candidate, not a current saving or a
verified PS2 match.

See [D345](port/dreamcast/docs/R4_EVENT_ENEMY_CHECKPOINT.md#d345-source-alpha-and-nested-handoff).
Selected evidence: `C:/Flycast-Evidence/re4-dreamcast/d345c-alpha-handoff`.
ELF SHA256 `9ffca465bdd5dbeee34da6e5ceb19c2f0a65dc095f74d0d464e77f40008c48f0`.
Text/data/BSS 2,310,792 / 77,016 / 673,112 (+1,136 / +4 / +32 versus D344).
Reuse D344's build options, `/root/work/kos-re4dc-d336`, `/root/probe/d343-mirror`
and `/root/probe/d344b-fixtures` unchanged. Reproduction scripts are
`/root/probe/d345-build.sh`, `d345c-prepare.py`, `d345-analyze.py` and
`d345-test.py`; create fresh output directories. Parent commit is
`e0dc0da78e6039465ba4815410a50977eda96fcb`; all 63 inherited tracked edits remain
byte-preserved. Exact build patch, assets, tools and capture identities accompany
the evidence. The harness ends at 240 seconds; no emulator remains running.

D345a exposed a live scenario unlinked during native I/O; D345b fixed that
handoff but stranded the caller when the scenario returned normally. Both are
failed black-output candidates, retained for diagnosis. D345c reuses the existing
thread-owned handoff for the actual nested caller, including normal return,
TaskSleep and TaskExit. No source flags or scenario completion were forced.
PowerPC scheduler tokens are unchanged; no new ProDG comparison. Thirteen
focused tests pass, including sanitizer geometry and scheduler ownership checks.

Source alpha is captured after source material/fade selection, preserving the
independent color-corner index through near clipping. Native base texture alpha
is ignored as the source regular material requires; separate soft mask semantics
are still unimplemented. The shared RenderVertex remains 52 bytes and the
existing room clip path remains packet-identical for tested opaque cases.
Target observations exercise register and vertex alpha; no faded register draw
was observed, so runtime fade acceptance remains pending despite host coverage.

Next: connect the separate source alpha mask through the existing texture and
material path, preserving intermediate alpha and source threshold/blend behavior;
continue EVD activation/destination lifetime in parallel priority as demonstrated
source consumers require it. Neither missing masks nor immutable event
preparation is complete scene/event acceptance. Lighting, audio/inventory,
combat, transitions/retry, frame budget and hardware checks remain open.

## Previous D344 checkpoint - stable enemy work pages

D344 keeps all 60 source enemy work slots but allocates stable two-slot pages
through the existing `parts_bridge` owner. With `ENEMY_DEMAND=1`, source heap
free rises **169,600 bytes** at the required block and Ganado body allocations,
to 2,921,856 / 1,806,336 bytes. After initialization, 20 backed slots (19 live)
use 72,384 bytes including metadata, versus 213,184 for the original array.

The bounded run now has **no source allocation failures**, and all five required
crows have validated 24-part chains. Final free/largest source heap is 66,592
bytes. Existing conversion prepares the missing crow packages; the observed
128x128 body texture uploads into 32,768 VRAM bytes. Neither archive sizes nor
motion residency change. This establishes initialization progress, not complete
encounter fit, visual equivalence, working audio or manual play.

Keep the selectable candidate; the default remains contiguous backing. Continue
source event activation and native presentation: the diagnostic renderer still
rejects material flag 0x04 and a source part with no image. Do not clear those
checks without implementing their source semantics. Hot motion remains cached;
mutable event snapshots, lighting, audio/inventory, combat, transitions/retry
and physical-hardware acceptance remain open. Simpler water is still an
unimplemented visual candidate, with no claimed saving or verified PS2 match.

See [D344](port/dreamcast/docs/R4_EVENT_ENEMY_CHECKPOINT.md#d344-stable-enemy-work-pages).

Selected ELF SHA256 `e13254ffdc7da81e439dfc5ed13d18369f5bcd388528439ddb9d43a53c5043a6`.
Text/data/BSS: 2,309,656 / 77,012 / 673,080; +3,636 text versus D343,
unchanged aligned data/BSS and source heap capacity; five prior missing stubs.
Use the patched KOS `/root/work/kos-re4dc-d336` with the existing reservations
1360608 / 149920 / 846656 / 247776 for core/option/player/weapon, all prior
PARTS/MODELINFO/OBJECT demand options, `PVR_STREAM=1 MODEL_POSITION_CACHE=1
EVENT_FILES=1`, and now `ENEMY_DEMAND=1`. Current module allowlist prevents
unreviewed new RELs from enabling sparse enemy backing. Do not lower slot counts.

Selected mirror `/root/probe/d343-mirror` is unchanged. Use the new private
`/root/probe/d344b-fixtures`, which retains the approach input and existing
native packages and adds 19 verified em23 image packages. Reproduce with
`prepare_native_ui.py /root/re4data port/dreamcast/fixtures/crow-native-deps.txt
<fresh-private-output>` and verify duplicate identities before merging fixtures.
This is package completion, not texture compression or source-archive recovery.

Evidence `C:/Flycast-Evidence/re4-dreamcast/d344b-crow-textures` is selected;
`d344a-enemy-work` retains the initial missing-texture observation. Both 240-second
runs end at the harness deadline. No emulator is left running. Sealed manifests
include exact executable/disc/assets/config/tool identities and inherited edits.
Private reproduction scripts are `/root/probe/d344-*.py`, `d344b-prepare.py`;
do not overwrite their existing output directories. Parent commit is
87c0e1f155f0ab589696523ac3b1ec9e8fae4998; 63 inherited tracked changes preserved.

Tests cover all 16 demand/reference combinations under ASan/UBSan, real manager
reuse/deferred deletion/indexed pointers/full capacity/push-pop/owner teardown,
and the actual ladder query's zeroed-slot behavior. All 334 current module input
units pass the direct-reader check; 33 touched source/header PPC token streams
are unchanged. Actual SH-4 layout assertions pass. No new ProDG comparison.
Target checks validate all four pool directories and live enemy/parts lists.
Motion: 952,768 resident/peak/read, 22,400 peak pinned, 2,336 metadata,
75 loads/misses, 6 hits, zero evictions/failures, worst wait 270,939 us. All 145
headers and 1,904 relocated keys validate; later/final counters match.

Next exact presentation consumers: `re4dc_model_packet_reserve` in native_ui.cpp
rejects `part->flags & 4` (9,845 accumulated rejections) and the same no-image
part (109) in this run. There are zero texture/capacity/overflow/invalid rejections
once the crow package is supplied. Trace those flags through model_bridge and
`commonModelTrans`; don't discard geometry or simply remove the rejection.
The 66,592-byte headroom is not an event/transition budget: immutable EVD
preparation is qualified, but target activation and the s03 mutable snapshot/
final destination still need source-lifetime integration. Keep both work tracks
visible; do not repeat the resolved crow or block allocation work.

## Previous D343 checkpoint - persistent option compaction

D343 externalizes the persistent option archive's 23 verified upload-only
textures through the existing native identity/package path. The file loads
directly into a149,920-byte reservation (full file259,648, old reservation262,144).
Target source-heap free increases **112,224 bytes** at both required block-pool
and em12-body points, now2,752,256 /1,636,736. Net archive reduction109,728 plus
2496 existing slack; metadata/alignment included. No new texture encoding,
geometry reduction, duplicate full archive, motion eviction or gameplay omission.

The corrected room still fails required allocations: four crows fail model
initialization (previously five);11360 bytes are requested with 10720 free,
followed by 512-byte part, collision/object and path-scratch failures. Source
title/menu and 640x480 diagnostic room remain visible. This is not full-room,
complete-character, performance, audio, inventory or manual-play acceptance.

A source-input Options round trip resolves discarded images through native
packages, returns to the title, then reaches room loading. Its colour-bars/EXIT
capture matches the pinned full-archive reference byte-for-byte; this preserves
an existing incomplete presentation, not accepted complete options UI. The
unimplemented mutable card/ARAM fallback now stops before live backing can be
overwritten; normal separately allocated card scratch remains unchanged.

Keep the selectable saving and continue the complete initialization working-set
audit. Room SST pricing21952 gross remains unimplemented and insufficient by
itself to accept the encounter. Hot motion stays cached after evaluation;
prefetch/concurrency, event activation/mutable snapshots, source presentation,
audio and three-room progression remain open. Simpler water remains a selectable
candidate; no PS2-equivalence or current memory saving is claimed.

See [D343](port/dreamcast/docs/R4_EVENT_ENEMY_CHECKPOINT.md#d343-persistent-option-textures).

Selected ELF SHA256 `34771144e0f4475cfe24c11da590f52ce4152d8a90b0944f4107074ba5093ed3`.
Patched KOS and D342 flags retained; additionally `OPTION_RESIDENT_BYTES=149920`.
Text/data/BSS2306020 /77012 /673080; +456 text, unchanged aligned BSS/data;
five prior missing stubs. Default option reservation remains the full0x40000.
Private mirror `/root/probe/d343-mirror`, producer `/root/probe/d343-option`.
Evidence `C:/Flycast-Evidence/re4-dreamcast/d343a-option-residency` uses the
unchanged approach fixture; `d343b-option-menu` uses the committed
`port/dreamcast/fixtures/option-roundtrip.txt`. Both240-second integration runs
end at their harness deadline. `d343c-option-reference` uses the pinned D342b
ELF/full option archive with the same option fixture,100-second deadline.
No concurrent emulator runs; no physical-hardware or frame-budget claim.

Reproduce with existing `prepare_native_ui.py --compact-option
/root/re4data/ss/eng/option.dat --textures /root/probe/d327-fixtures/tex --output
<fresh-private-directory>`; replace only `ss/eng/option.dat` in a fresh mirror.
The plain tagged archive is not a .dar. Preserve all current room/enemy/event
inputs. Validation scripts `/root/probe/d343-validate.py`, `d343-analyze.py`;
capture preparers d343-prepare/d343b-prepare/d343c-prepare must not overwrite
their existing directories. Sealed evidence records exact disc/tool identities.

14 focused tests pass; all23 private identity descriptors survive source-header
relocation under ASan/UBSan, and 10 unaffected families compare exactly (including
all10 death palette images). Shared read/cDataSwap PPC tokens unchanged; no new
ProDG object comparison. Motion remains952768 resident/peak/read,22400 peak pinned,
2336 metadata,75 loads/misses,6 hits,0 evictions/failures; worst observed wait270941us.
145 headers/1904 relocated keys validate; warm-up and final counters match.
Failed actors/unvisited reactions still prevent full working-set qualification.

## Previous D342 checkpoint - native crow and room effect compaction

D342 binds the required crow module through the existing static registry and
preserves its source-manager archive pointer using the Em12 constructor fix.
Rejected native DLL links now stop through `re4dc_missing`; the PowerPC path is
unchanged. Crow construction reaches real model allocation, which still fails.

Selectable `--compact-room-est` reuses the existing resident effect codec and
qualified room builder: r100's loaded body falls from3,812,576 to 3,754,592 bytes.
The target has **57,984 more heap bytes** at both the required block-pool and
em12 allocation points (now2,640,032 /1,524,512 free). Existing static REL
compaction removes another15,968 bytes from the crow body (239,904 ->223,936).
These are real smaller final allocations, with original sound transport retained.

The full corrected room still does not fit: a512-byte part request fails with 256
free, then all five crows fail their11,360-byte part requests; later collision,
object and path scratch allocations fail. Retry logs are not extra allocations.
The title/menu and diagnostic source-controlled scene remain visible; this is
not complete characters, a playable encounter, accepted lighting or an FPS result.

Keep this bounded compaction and continue the initialization working-set audit.
Option upload-only textures price at 109,728 net archive bytes, but their fixed
owner/card-swap lifetime is not yet adapted; reservation slack alone is only 2496.
Room SST packing prices at 21,952 gross and remains unimplemented. Neither is
counted as recovered heap. Preserve hot motion keys and the immediate-response/
prefetch audit. Event activation/mutable snapshots, source presentation/audio,
inventory, three-room progression and physical-hardware gates remain open.
Simpler water remains selectable and unimplemented; PS2 equivalence is unverified.

Current selected ELF SHA256 `61485913ebbf3ca3e6a2a4a6e48d91bd418d658b9185136f81bfa08dad3944d6`.
Build options remain D340/D341 (`EVENT_FILES=1`, all three demand pools,
PVR_STREAM and MODEL_POSITION_CACHE enabled; core/player/weapon reservations
1360608/846656/247776). Patched KOS `/root/work/kos-re4dc-d336` remains required.
ELF text/data/BSS2,305,564 /77,012 /673,080; five pre-existing missing stubs.
78 focused tests pass, plus actual SH-4 crow-layout compilation and bit-exact
checks of 345 room effect records/216 delayed references with ASan/UBSan.
No new ProDG object comparison; touched shared-source PPC tokens are unchanged.

Evidence `C:/Flycast-Evidence/re4-dreamcast/d342b-room-effects` is the kept
integration candidate, still blocked at required memory. `d342a-crow-module`
preserves the initial module-only failure (null crow archive then exhaustion).
The180/240-second runs ended at harness deadlines; no guest reboot observed.
No active emulator remains. Private mirror `/root/probe/d342-mirror`, room
producer output `/root/probe/d342-room`, disc `/root/probe/d342b-room-effects-disc`,
fixtures `/root/probe/d341a-fixtures`. Original references remain untouched.
Private reproducibility: `/root/probe/d342-validate.py`, `d342b-prepare.py`,
`d342-analyze.py`, `d342-stats.py`; do not overwrite their existing outputs.

Room packing is opt-in through existing `prepare_native_ui.py --compact-room
/root/re4data/st1/r100.das --compact-room-est --textures /root/probe/d327-fixtures/tex
--output <fresh-private-directory>`. Crow uses existing `compact_static_rel`
after whole-file qualification with the now-registered module7. No new encoder,
loader, renderer or cache. The added16-byte room effect binding borrows metadata;
source room-heap replacement retires it. Target binds all37 packed sequences,
but this trace performs no packed record reads; delayed decoding is host-tested.

Hot motion remains952,768 resident/peak/read,22,400 peak pinned,2336 metadata,
75 misses/loads,6 hits,0 evictions/failures; worst observed wait270,941us.
All145 headers/1904 key pointers validate in the final snapshot. Counts stay
unchanged after warm-up; missing crow/gameplay work limits coverage. Do not
interpret this as complete repeated-response/concurrency or event qualification.

## Previous D341 checkpoint - corrected list exposes required crow dependency

D341 corrects the opening enemy-list conversion in the existing mirror tool.
The old native list interpreted the house entry as room0x001/HP59395 instead of
room0x100/HP1000. All255 original records compare field-for-field after conversion;
target snapshots verify the corrected house entry. Required byte fields, indices,
record count and reserved bytes remain intact. Thirty-four focused tests pass.

This exposes required content previously suppressed by the bad room checks:
the authored crow archive now requests 239,904 bytes, and its REL module7 is not
in the image. The first cold boot allocates that body, leaving147,168 free at
that point, but subsequent model-info requests 4704 fail with 4064 free. Required
block pool/em12 early points remain2,582,048/1,466,528 free. This is **zero new
heap recovery**, not a fit for the corrected encounter. After a guest reboot,
crow retries fail with 75,936 free; do not combine those separate boot states.

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
worst observed wait270,939us. All145 headers and 1,904 relocated pointers validate.
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
source 3D connection. Do not replace this with one replay's simultaneous calls.
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
no claim of full effect behavior/presentation. Source frame 1234/Rno0=3/System0x800
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
OSWakeupThread/TaskSchedulerMain (frame 1223, Rno0=3, System0x800); both required
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

Implementation bf85bd2 is committed/pushed; D320c now directly loads r100 at 3,812,576 versus 4,669,568 bytes, recovering
856,992 real source-heap bytes. The required 1,126,272-byte block pool ALLOCATES;
blocks0-2 load/create. First enemy3,577,728 still fails with 147,360 free (shortfall
3,430,368 before overhead). 97 offline identities replace upload-only source
texels; mip/palette/CPU-noise/unreviewed payloads remain. Shared Package/storage
now uploads native textures in bounded chunks through the existing 64 KiB bounce,
with no whole-package source-heap allocation. Title menu stays visible. Ten
room uploads succeed; the snapshot has 435 output triangles/8512 peak packet
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
CPU/RAM/quality gates. 66% enemy-body target is about 2,361,300 bytes, not66% saved.
PS2 enemy audit /root/probe/ps2-enemy-audit shows mesh substitution alone cannot
reach it: all GC meshes are 415,040 bytes (11.60%), PS2 top-level BINs are slightly
larger. FCV/SEQ dominate at 1,864,928 bytes; texture backing remains another lead.
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
