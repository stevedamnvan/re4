# Performance policy for the boot-forward RE4 Dreamcast port

Current D362 (2026-09-22): final lossless asset step is complete. Exact source UV
sharing recovers34016 actual heap bytes (free/largest82688->116704 B) but leaves
render~1368ms unchanged across127 matched ticks. Stop duplicate/unused-array and
strip-repacking hunts; existing stripifier found zero order-preserving savings.

The user explicitly activates one substantial r100 static-render replacement:
reuse existing D349/D353 baking/native representation machinery with current
source-owned assets; replace qualified normals/runtime lighting rather than add
a second scene. Actors remain dynamic. Preserve source ownership, activation and
gameplay; handle dynamic/camera-relative lights and intentional visual differences
explicitly. Compare the whole candidate to D361 retained preparation (~1.368s),
with actual loaded memory, work counts, packet/VRAM costs and appearance. The
next milestone is materially cheaper rendering, not another handful of KiB.
[D362 evidence and exact scope](R4_NATIVE_PREPARATION_CHECKPOINT.md#d362---final-lossless-uv-sharing-static-replacement-activated-2026-09-22).
This targeted activation is recorded in [the visual profile](PS2_INSPIRED_DREAMCAST_PROFILE.md);
it does not accept unrelated substitutions or claim hardware/gameplay completion.

Previous D361: retained model/frame preparation reduced render cost12.5% with
unchanged source behavior/packets; the128KiB workspace remains in the baseline.

Previous D360 storage prerequisite:
 a selectable source-index externalization
recovers 147,232 actual source heap bytes (free/largest66,592->213,824) while
preserving the integrated renderer, current native textures and required large
block/enemy allocations. It is not a speedup: render remains ~1.56 seconds.
The source timing comparison differs by one loading update, so it is not a
matched performance pass. Use identical selected assets in the next full-stack
A/B. Keep the candidate default-off; source CLUT/mip/CPU semantics and unsampled
effect presentation limits are recorded in [D360](R4_NATIVE_PREPARATION_CHECKPOINT.md#d360---selectable-indexed-texture-backing-release-2026-09-22).
The next task remains retained preparation at the existing owner boundary, now
with a measured net storage replacement; do not return to admission tuning or
enlarge the topology metadata budget.


Current D359 priority (2026-09-22): stop admission-ranking changes and restore
retained preparation at the existing native asset/resource boundary. The current
full candidate is committed as8bdb4dd. A normal-build paired capture, with detailed
profiling/audit disabled, matches107 source ticks without measured drops:
B render p50/p95=1562.056/1564.143ms, pageflip p50=1589.783ms. This remains far
from playable. Do not use the former~1973ms instrumented result as normal cost,
or interpret disabled failure/upload counters as passing gates.

Qualified actual-descriptor replay of53 static parts covers43% of references but
finds827 extra transforms and only732 shade evaluations saved over the existing
fallback. Higher coverage is not progress. Recover a materially useful native
preparation lifetime by replacing qualified render-only backing and measuring
its real storage/overlap, without another representation copy or metadata growth.
Preserve source light/camera/material dependencies and the full-stack acceptance
unit. Do not activate PS2 visual compromises to mask the unresolved contract.
See [D359](R4_NATIVE_PREPARATION_CHECKPOINT.md#d359---committed-stack-real-build-cost-end-admission-tuning-2026-09-22).

Previous D358 priority (2026-09-22): finish the same D349 prepare-once/reuse-many
integration. Whole-registration local admission is implemented within 8 KiB and
passes a78-tick full-stack A/B stability gate, but B render p50/p95
1,972.755/1,974.568ms is unchanged in practical terms. Coverage34.09%
does not mean avoided work: transforms 133,111 and individual-light evaluations
384,223 remain near D357. Existing fallback already caches positions/complete
lighting across strips, while dense domains reset independently. Attribute actual
hits/losses in the existing captured-source replay before changing those lifetimes;
report both RGB-pack paths. Preserve the full stack and fixed budgets; no new
cache, source-heap cut, or per-component target promotion. Broad group bounds are
low-yield in this measured view; invariant room-light source provenance remains
an open separate contract. See [D358](R4_NATIVE_PREPARATION_CHECKPOINT.md#d358---global-admission-and-remaining-reuse-gap-2026-09-22).


Previous D357 priority (2026-09-22): retain the integrated D349 candidate and
accepted presentation; complete the missing preparation input/lifetime contracts.
The source-backed legal span implementation passes a78-tick system A/B stability
gate, but performance remains unaccepted: B render p50/p95
1971.792/1973.605 ms versus A1211.301/1213.904 ms. Dense position coverage is
12.95%, normal13.56%, shade13.61%;114 prepared-light builds/149 reuse hits.
No metadata/workspace/source-capacity growth.212 packet flushes/171 strip
fallbacks persist. The five-witness diagnostic is separate from steady timing;
only three complete current263-part witness frames support its ranked timings.

The simultaneous history audit confirms coverage is the immediate gap, not a
missing FTRV, compiler, direct-list or packet primitive. Structural-plan rejection
also denies early bounds/local reuse; part-arrival allocation and sparse original
index domains limit the admitted work. Classify the dominant uncovered streams
before changing the existing bounded admission/bounds path. Historical invariant
room-light reuse is another missing contract: selected GX parameters lose original
light provenance/identity, and the ineffective tiny static cache is disabled.
Restoring source-faithful invariant accumulation is distinct from activating the
gated PS2 visual compromise. Do not import historical large tables, grow metadata,
cut source heap, resume keyed lookup or promote per-component target experiments.
See [D357](R4_NATIVE_PREPARATION_CHECKPOINT.md#d357---source-backed-spans-and-historical-input-contract-audit-2026-09-22)
for exact history anchors, current seams, measurements and limitations.

Previous D356 priority (2026-09-22): continue wholesale D349 architecture integration.
The user accepts v4 B's current appearance as accurate for now. Preserve it and
stop investigating the A/B visual gap; the open gate is performance.
The dense generation-slot candidate completed a stable 85-tick full-stack A/B,
but is not promoted: B render p50/p951948.184/1950.040 ms versus A 1192.463/1195.034 ms.
Prepared-light sharing works (114 builds/149 hits); dense vertex mapping covers
only 1.48% of live references. Both metadata partitions are full. The present
per-corner companion encoding requires 314,429 B across tracked streams and cannot
deliver scene-wide reuse inside its8 KiB budget. Correct that source-backed
representation/admission boundary; do not add a keyed cache, cut source heap,
grow queues, or hide the integration gap with visual substitutions. Full-stack
acceptance remains the unit. Preserve the measured packet cost of borrowing
workspace:212 flushes/~470PVR calls,171strip fallbacks, source heap 66,592 B.
The source-preserving DVD borrow correction f2ed3dc is in both arms; the earlier
v3 B loading stall is not a renderer timing result. See the
[D356 checkpoint](R4_NATIVE_PREPARATION_CHECKPOINT.md#d356---dense-local-indices-measured-admission-limit-2026-09-22)
for exact identities, spans, coverage limits and the next representation boundary.

Previous qualified D354 reference:
The stable diagnostic A/B now has 70 matching source snapshots/ticks and passes the
zero-discard/allocation-failure/post-warm-upload and bounded-queue gates. It is not
performance or full appearance acceptance. B's instrumented p50 render span is
1842.358 ms: lighting 723.596 ms, packet preparation 456.764 ms, transform 377.852 ms and
clipping 159.034 ms. Source preparation ~9.9 ms is secondary. Profiling overhead is
substantial and explicitly reported. [D354](R4_NATIVE_PREPARATION_CHECKPOINT.md#d354---stable-integrated-profile-not-performance-acceptance-2026-09-22)
contains exact work, queue, RAM/VRAM, strip/cull and clock data.

Use those findings to complete the same asset/frame/material-light preparation
contracts. Do not restart per-mechanism target promotion, skinning, prelighting or
store-queue experiments. TMU2 remains the nested wall clock; PRFC1 is a separate
possible follow-up for the dominant stage. Earlier sequences below are supporting
backlog, not permission to optimize a measured sub-20 ms component first.

## Current native preparation - D352/D354 integrated candidate, 2026-09-22

The current default-off `D349_RENDERER_STACK` experiment is accepted or rejected
as one system. Build two arms from the same latest recovered source, assets,
configuration and input: A baseline, B complete compatible stack. Internal tests
guard mechanisms; do not target-measure/promote them one at a time. Bisect only
a demonstrated whole-stack visual/performance failure.

The integration boundary is source asset lifetime -> compact native structural
metadata -> current source pose/camera/material/light state -> shared native
kernels/frame owner. `model_asset_bridge.cpp` visits source-accepted OT registrations before
render submission and installs only new asset/lifetime plans; draw lookup does
not construct plans. Source display lists and
arrays remain backing under their resource generation. Metadata shares the
existing 64 KiB native slab, with no additional source-heap reservation or full
geometry copy. Historical prepared-light, visibility, direct-strip, clipping,
texture and packet mechanisms remain the implementation references. Preserve
source behavior where historical inputs/lighting assumptions do not match.

[D352 evidence and limits](R4_NATIVE_PREPARATION_CHECKPOINT.md#d352-integrated-stack-and-asset-lifetime-boundary)
records current measurements. Earlier D350/D351 values are historical diagnostic
results, not current FPS or a recommendation to keep their copied-corner cache.
D352 also addresses the measured KOS staging limit and reproduced source DVD
queue reentry in both target arms. Source free/largest and native allocation
headroom are distinct budgets. A loader stall has no renderer timing result.

Full acceptance still requires complete current-facing characters/cabin/HUD,
source-selected lighting/materials/alpha, meaningful CPU p50/p95 and presentation
improvement, zero duplicated rendering, actual decode/transform/light/clip/PVR/
fallback counts, RAM/VRAM and responsive encounter controls. Settled outdoor
views do not qualify combat, free-camera movement, death or retry. Do not add
overlapping CPU/GPU intervals or call native submission-wall time whole-game CPU.

[D349](R4_R100_REFERENCE_RECOVERY_CHECKPOINT.md) remains the preserved visual and
performance reference: historical `5f42caa`, early CPU p50 48.880 ms, whole trace
57.559 ms, mean presented interval 55.158 ms (~18.13 FPS). Its workload differs;
the user rejects its old facing defect. Historical inputs remain unchanged.

## Previous D344 memory checkpoint

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

See [D344](R4_EVENT_ENEMY_CHECKPOINT.md#d344-stable-enemy-work-pages).


### Previous D340 checkpoint

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
See [D340](R4_EVENT_ENEMY_CHECKPOINT.md#d340-qualified-immutable-event-backing).

D339's part-local position cache and D338's source cull correction remain.
D339's prior matched-frame emulator interval median was 1,437.144 ms; D340
does not supersede that with a controlled performance comparison. Do not repeat
the cache, strip/chunk or cull work, or mistake the unlit diagnostic backend for
the complete accepted cabin presentation.


Updated 2026-09-22; accepted integration D324; integration experiment D340.

Historical renderer measurements retain their original revision identities.
**Execution priority belongs to [PLAYABLE_PATH.md](PLAYABLE_PATH.md).** This file
is the supporting performance/validation policy, not a separate scene-first
roadmap. Historical R0-R4 experiment labels do not determine the next task.

D314 connects common ID quads to existing native texture/storage/PVR, with
verified warning/title/menu images. Peak aligned staging is 1,048,736 bytes;
each measured upload restores source heap free bytes. Source archive storage
is not reclaimed. UI VRAM peaks at 4,192,256 bytes. ELF grows 129,776 bytes;
source arena loses 262,144 versus D313. This is integration cost, not a
performance win. D315 corrects the native file-I/O stack underrun (+96,256 resident bytes)
and returns to required block/enemy allocation failures. Subscreen preload is
not working inventory; native ARAM storage and data/module qualification remain.
See [D314](R4_SOURCE_UI_CONNECTION_CHECKPOINT.md) and
[D315](R4_SUBSCREEN_BOOT_CHECKPOINT.md). Continue measured resource integration;
no gameplay FPS/hardware acceptance is claimed.

Historically, D313's selectable static-module compaction reclaims 46,464 live heap bytes and
reduces em12 demand by 428,288; neither required allocation fit at that checkpoint; D320 supersedes the block failure. Source
base-texture inventory is a next capacity lead, not a measured active set or
license to upload everything. See [the exact checkpoint](R4_STATIC_MODULE_STORAGE_CHECKPOINT.md).

## Corrective execution policy

The primary workstream is continuous source-driven play from boot. Do not finish
or optimize r100, r101, every camera, or every graphics effect before integrating
the next required gameplay system. Do not attempt to complete every game/debug
system before producing a playable opening sequence either.

**The former 20-FPS-plus-transition Scale Gate is not an integration gate.**
Approximately 20 FPS remains an intermediate playability milestone. It must be
qualified with representative frame tails, input/simulation behavior, and actual
presentation, not a CPU median or one quiet scene. Source-system and boot-forward
integration may proceed below that milestone when execution is safe and testing
remains useful.

Retain approximately 30 distinct presented game frames per second at 640x480 on
stock Dreamcast as the final performance target, unless the user explicitly
approves another fidelity/performance policy based on evidence. Neither the
current emulator trace nor the complete decompilation proves that target across
Disc 1. Preserve source-time behavior while adapting execution to the target.

During integration, performance work is justified when it:

- Removes a demonstrated memory, loading, or execution failure.
- Makes the current authentic sequence usable enough to test and advance.
- Reduces a substantial measured cost without displacing the integration slice.

A speculative sub-millisecond lighting/compiler/cache experiment is not the
primary task while source progression, scheduling, camera, and events are still
missing. Keep rejected branches closed absent new workload evidence.

## Component status versus gameplay integration

| Status | Current meaning and evidence |
|---|---|
| Implemented in native scene runtime | `port/dreamcast/room/` owns measured visibility, prepared lighting, strips, texture sharing/upload, transient payload and retirement work. Reuse these components. |
| Connected to recovered game | `port/dreamcast/game/` uses qualified source-layout DAR through the DVD queue/source heap and reaches r100 allocation. This does not connect every scene-runtime optimization. |
| Validated in normal gameplay | Not yet established: GX/audio placeholders and diagnostic scene limits remain. D338 passes required block/enemy allocations and restores ground/Leon head surfaces; alpha/material/lighting and full source gameplay remain unaccepted. Viewer timings are not its gameplay frame budget. |

Qualified `.dar` -> source DVD queue/heap ownership -> recovered initialization
and behavior differs from native scene/texture packages -> existing rendering
and resource mechanisms. Adapt those through explicit interfaces; never replace
the archive behind `pG->pRoom` with a viewer `.re4room` package.

D312 allocation failures are historical, superseded by the current residency
work above. EVD ARAM and sound dispatch still do not establish stored events or
playback. Use current source/native measurements; earlier `read_us=0` is invalid
timing, and sampled diagnostic rendering is not a gameplay frame budget.
Historical workload measurements below remain component-reuse references.

## Historical evidence and necessary corrections

| Revision / evidence | Planning consequence |
|---|---|
| R3/R4 cabin optimization checkpoints | Retain the implemented work and matched comparisons as historical evidence. Their fixed-camera/encounter costs are not a whole-game performance model. |
| `a00d967` | Transient room texture backing plus a smaller reservation recovered 2,093,056 bytes of real main RAM in the measured r100 build, with paired frame time unchanged. A capacity win is not an FPS win. |
| `8a44852` | Removing proven duplicate connectivity recovered further resident memory; this does not establish how the full source village executes. |
| `17f6ae2` | The first village sweep was an actor-free 320x240 diagnostic. Do not compare its memory or timing as a 640x480 playable workload. |
| `fbd0012` | Leon in r101 at 640x480; reported diagnostic sweep CPU-frame median about 87 ms, p90 about 200 ms, loading low mark 1,757,184 bytes free. Source entry/camera/progression still require integration. |
| `b7d29e3` | The snapshot collector had frozen after crossing the requested tick. It now stops at the exact tick. The six tested states and corresponding fallback/local batch records match; the earlier d281 pixel ratios measured different actual states. |

Do not continue an investigation justified only by the invalidated 5/21 or
11/22 comparisons. Do not claim universal renderer parity from the corrected
six-state test. Reopen a specific issue only with a new same-state reproduction.
The correction did not establish an independent simulation defect: distinguish
late snapshot selection from actual per-tick nondeterminism.

These are repository-reported historical measurements, not newly run tests.
The [pre-amendment ledger](https://github.com/stevedamnvan/re4/blob/b7d29e3fe9ba58b807ef2146776b09caf1acbaea/port/dreamcast/docs/REALTIME_PATH.md)
preserves R3p-R4f timing tables, identities, closed candidates, and evidence
locations. Individual checkpoint files remain unchanged and available.

## Workload before optimization

Verify game/room state, actual player entry, evaluated camera, active objects,
source display rules, collision, and event state before declaring a diagnostic
sweep representative. Read the data and its consuming code. Do not infer source
visibility from exported asset count, light masks, or a high triangle count.

A realistic source view may be broad. Do not narrow FOV, change camera offsets,
shorten the horizon, hide buildings/interiors, reduce enemy activation, or skip
script work to make a graph look faster. Alternative render assets are separately
reviewed under [R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md).

Representative performance fixtures increasingly use the source-authored
jump/state configurations of the recovered debug tooling (`roominfo.dat` jump
points through `CRoomInfo::setNextPos` and the normal room change, the title
debug-start fields, a `config.txt`-style developer configuration; see the
fixture track in [PLAYABLE_PATH.md](PLAYABLE_PATH.md)) rather than cabin-only
autoplay or invented sweeps. A timing run names its stage, room, jump point,
player/camera state and scenario state.

Alternate representations have two evidence levels:

- Early diagnostic comparison: one equivalent static environment object/small
  group in the existing native scene runtime, with exactly matched camera,
  lighting, render state and resolution. This may establish asset compatibility
  and preliminary cost before full source-fixture integration.
- Gameplay qualification: representative recovered-game source-controlled state,
  including room/jump, player/camera, scenario/events and actual tick. Required
  before claiming a route-level benefit or promoting an alternative selection.

Keep the GameCube reference selectable. Record converted bytes, persistent/load
RAM, VRAM, geometry/batches/materials, lighting work, frame distributions and
appearance differences. Unrelated views or altered states are not a comparison.
Early viewer results are not village FPS claims. Character substitution and movie
mapping are later/separately assigned work, not the current helper's scope. See
[R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md) for conversion requirements.

Grow the fixture set from the opening sequence: title/new game, movement and
camera turns, aim extremes, fire/reload, enemy contact, interaction/inventory,
event transitions, death/retry, and room changes. Exercise both quiet and busy
views from the same source-controlled state. Keep r100 as a regression fixture;
do not make it the only workload or require perfect source parity there before
all independent game integration.

## Measurement contract

Record commit, executable/disc and private asset hashes, converter options,
compiler/KOS versions, output resolution, emulator configuration, room/state,
input source, camera, requested and actual simulation ticks, and capture window.
Keep generated outputs and evidence directories isolated. Concurrent emulator
runs or drifting assets invalidate a paired timing comparison.

Time production-like builds. Keep digest, full tracing, fault-injection and
snapshot instrumentation separate. Collect the smallest diagnostic needed to
answer the question, then time without its overhead. Do not redesign telemetry
or repeat all historic captures as a prerequisite for each implementation step.

**A requested tick is not an observed state.** For comparison builds, stop the
simulation exactly on the requested tick and record actual player, animation,
camera, input/RNG/event state. Do not freeze after a catch-up batch and label it
with an earlier target tick. Use the `b7d29e3` mechanism and validate its identity.

Separate these costs instead of summing overlapping aggregates:

| Measurement | Required distinction |
|---|---|
| Source simulation | Input consumption, task/event ordering, collision, actors, camera; no silently discarded time. |
| CPU rendering | Visibility, deformation, lighting, clipping, packet preparation, and actual transfer costs. |
| PVR / presentation | Registration/render duration, waits and distinct presented updates; zero wait alone is not proof that GPU cost is zero. |
| Loading | Read, validation, installation, texture/audio transfers, and retirement measured separately. |
| Memory | Code/data/reservations, persistent resources, temporary install scratch, heap/stack, VRAM/AICA, and safety margin at simultaneous peak. |

Report p50/p95/p99/max frame and presentation intervals where available, sample
counts, missed deadlines, input queues/gaps, simulation debt/drops, and route
coverage. A reciprocal CPU-frame median is not sustained FPS. Do not add stage
medians from different populations and call the result a frame budget.

Compare unchanged baseline and candidate in the same sitting/configuration.
An old baseline also becoming faster in a new session is not a new-code gain.
Load-time savings are not resident-frame savings. Emulator memory arithmetic and
functional evidence do not establish physical SH-4 timing or real media rates.

## Change selection

Select one substantive change from the integrated workload's current profile.
Prefer eliminating work that should not execute, reusing immutable data at the
correct identity, preserving source variants/selection, and improving memory
layout or bounded execution before instruction-level tuning.

Keep source object, instance, position, normal, UV-corner, material, skinning,
and selected-light identities. A smaller cache or table must fall back correctly,
never omit geometry, truncate global indices, or reuse stale state. Measure
recomputation and hit rate when coverage is partial; a bounded prefix is only a
bring-up policy until representative measurements justify it.

Inspect emitted SH-4 and target-specific kernels where the profile warrants it.
`tools/sh4_loop_cost.py` is a diagnostic proxy, not a hardware oracle. Preserve
operation order when a pure optimization promises bit equivalence; classify a
reviewed numerical or asset approximation explicitly instead of hiding it.

Historical negative results remain useful boundaries:

- R4f/g/h/i did not recover the actor-lighting compiler regression through flags,
  a translation-unit split, input-normal caching, or general compact light
  records. Do not repeat those routes without a changed mechanism/workload.
- The deferred four-light specialization requires broad source-play evidence,
  not the two cabin actors' fixed selections.
- R3q measured small actual transport cost in its fixture. Do not infer that all
  time called `submit_us` is DMA/store-queue time; remeasure before a rewrite.
- R3u settled a cell-size comparison for that renderer/fixture, not every room.
  Do not rerun it by rote or impose its material exceptions on other rooms.

Use [DCA3_SOURCE_AUDIT.md](DCA3_SOURCE_AUDIT.md), pinned KallistiOS, and other
community implementations as source-linked mechanism references. Their old
recommendation order is subordinate to PLAYABLE_PATH. Verify revision, license,
semantics, and costs; do not copy their world policy or promise their FPS.

## Correctness and test scope

Maintain three distinct statuses: execution-safe diagnostic; source-correct
integration; performance-qualified gameplay. Unsafe resources or memory block
execution. An identified visual mismatch blocks promotion to fidelity acceptance,
not every diagnostic or independent integration task.

Use focused host/boundary tests for layouts, counts, overflow, partial preparation,
and indices above 65,535. In fault tests, distinguish requests from reached
failures and assert ownership while the failure stands before cleanup/retry.

For a rendering mismatch, reproduce one complete state and locate the first
divergent batch, packet, primitive grouping, or effective state. Do not repeat
multi-minute pixel runs before isolating that state. A common helper name is not
proof of emitted equality; an aggregate counter is not proof of identical pixels.

Pure optimizations compare against the accepted matching target state. Source
behavior corrections may intentionally change it and must use the source game
as authority. Alternative assets receive explicit fidelity/performance review,
not a false claim of losslessness. Never preserve a known prototype bug solely
to retain an old digest.

## Performance qualification, not permission to integrate

For the completed representative sequence, target one new game update per two
refreshes in the selected 60-Hz mode; use measured cadence and report 50-Hz or
other modes separately. Include stressful gameplay and transitions, repeated
runs, native-resolution moving images, audio alignment, and responsive human
control. Report missed deadlines and stalls rather than hiding them in averages.

No hidden simulation/input loss, allocation failure, TA overflow, or memory
corruption is acceptable. Preserve source pause/loading semantics so transition
waits neither accumulate catch-up debt nor replay queued gameplay inputs.

Physical Dreamcast validation is required for final performance, controller,
audio, storage, and memory conclusions. Prepare runnable hardware candidates
without blocking useful software integration solely because hardware is absent.
If intact source workload cannot meet the target, present measured options for
review under the asset policy instead of quietly altering camera or gameplay.

The next task remains the dependency needed for the boot-forward playable slice,
not the next letter in a graphics experiment series.

## SH4ZAM reuse decision (2026-09-22)

SH4ZAM can save implementation time on residual native kernels; it does not
supply source resource lifetimes or D349 local-index preparation. Current native
transforms already use KOS mat_trans_nodiv/FTRV, and KOS pvr_prim already uses
store queues. No SH4ZAM dependency is linked or newly installed by this review.
The shared selected-light evaluator still has scalar distance/normalization/dot
work. After dense reuse is corrected, prefer a pinned mature implementation
over writing new assembly if the measured residual stage justifies it.

| Mechanism | Existing insertion point | Qualification |
| --- | --- | --- |
| shz_inv_sqrtf, dot/magnitude helpers | source_lighting.cpp prepared evaluator | Preserve zero-distance, attenuation, channel and selected-light semantics; bound numerical/color error against reference and measure full candidate. |
| Reciprocal helpers | native_model.cpp projection | Only if residual projection is material; respect signed camera depth, near clipping and finite/depth accuracy. Positive-only FSRRA forms cannot receive arbitrary signed z. |
| memcpy32 / SQ copy helpers, PVR examples | Existing packet copy/submission | Only if measured transport matters; current OP/PT/TR submission is about 10 ms. Preserve alignment, locking, buffer ownership and matrix registers; XMTRX variants can clobber the loaded transform. |

Primary references:[SH4ZAM](https://sh4zam.com/),
[scalar API](https://sh4zam.com/shz__scalar_8h.html),
[memory API](https://sh4zam.com/shz__mem_8h.html),
[implementation and MIT license](https://github.com/gyrovorbis/sh4zam),
[native PVR examples](https://github.com/dfchil/sh4zam_pvr).
The website currently advertises 0.9.0 and tuning for GCC 16; the pinned project
uses GCC 15.2. Pin the exact revision, retain notices and verify that compiler/API
combination before adoption. Do not silently upgrade the shared SDK or infer that
GCC 16 is a hard requirement. No FPS saving is claimed by this source review.
