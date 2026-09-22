# Performance policy for the boot-forward RE4 Dreamcast port

D329 adds selectable demand backing for the source parts manager, without
reducing its **1,310 logical slots** or moving live model parts. At the matched
block/enemy allocation points it recovers **540,352 actual source-heap bytes**.
Further source block creation consumes 98,496 of those bytes: the sustained
saving before motion prefetch is **441,856 bytes**, with 319 live parts in 198
stable runs using **176,544 bytes** including metadata, alignment and allocator
costs. The original full pool cost 618,400 bytes including allocator overhead.

The enemy archive remains **1,105,152 bytes** (D328); it is not smaller again.
The unchanged diagnostic hot profile reaches **63 clips / 793,984 cached bytes**
before the next required key fails. The selected cache/metadata/conservative
allocator budget still lacks **220,256 bytes**, before later actor/event/audio
allocations, additional model parts or broader source-required hot clips.
No evaluation-release eviction or smaller response set was used to force a fit.

The source title/menu, required block pool, enemy body, texture identities and
sound-container dispatch survive. D324 remains the accepted integration reference;
D325-D329 are selectable residency candidates. Enemy initialization, full native
3D, audible/manual gameplay, transitions/retry and hardware acceptance remain
open. The D328 SH-4 fixture's 7,500 warm evaluations with no extra misses/reads
remains the cache reference; this game still cannot finish warm-up. Preserve the
source prefetch/concurrency audit and validate repeated-use/response coverage.
See [D329](R4_NATIVE_PRIMITIVE_LIFETIME_CHECKPOINT.md#d329-demand-backed-source-parts).


Updated 2026-09-21; accepted integration D324; selectable residency experiment D329.

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
| Validated in normal gameplay | Not yet established: the game still links GX/audio placeholders. D312 passes player/weapon startup but required block/enemy allocations fail. Viewer timings are not its gameplay frame budget. |

Qualified `.dar` -> source DVD queue/heap ownership -> recovered initialization
and behavior differs from native scene/texture packages -> existing rendering
and resource mechanisms. Adapt those through explicit interfaces; never replace
the archive behind `pG->pRoom` with a viewer `.re4room` package.

Latest primary evidence is [D312](R4_EVENT_ENEMY_CHECKPOINT.md): the required
block-model pool and em12 body do not fit; recover actual resource capacity next.
D307's earlier 458,752-byte recovery remains valid but insufficient. EVD ARAM
and sound dispatch are not playback; `read_us=0` is invalid timing. Measure
integrated rendering when connected.
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
