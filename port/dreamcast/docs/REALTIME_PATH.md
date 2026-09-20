# Fidelity-preserving real-time r100 plan

Revised 2026-09-20 after auditing `fed3e91aa18a246b027b8291fa0b1f41b9a9dda0`.
The follow-up source-engine audit is incorporated below. This is the current
execution order. [PLAYABLE_PATH.md](PLAYABLE_PATH.md)
retains the presentation milestone, source ownership ledger, and historical
evidence. Keep the native SH-4/KallistiOS target and direct PVR renderer.

R0 telemetry and the R1a renderer pass are implemented and measured in
[R1A_PERFORMANCE_CHECKPOINT.md](R1A_PERFORMANCE_CHECKPOINT.md). The first R1b
implementation now carries source object/cull/mask/volume data and applies the
source-derived room and actor selection in
[R1B_SOURCE_SELECTION_CHECKPOINT.md](R1B_SOURCE_SELECTION_CHECKPOINT.md).
The matched original-game selected-light trace and image comparison required to
close R1b remain pending. The first R2a implementation also preserves and uses
the authored SAT block graph, edges, and duplicate suppression in
[R2A_SAT_HIERARCHY_CHECKPOINT.md](R2A_SAT_HIERARCHY_CHECKPOINT.md); source
narrow-phase/query-trace parity remains open. R1c now prepares the fixed
world-space part of source-selected room lighting once while retaining the
camera-relative lights, with the measured result in
[R1C_STATIC_ROOM_LIGHTING_CHECKPOINT.md](R1C_STATIC_ROOM_LIGHTING_CHECKPOINT.md).

## Objective and boundaries

Make the same post-s03 cabin encounter responsive and measure its cost on a
stock Dreamcast. The target is approximately 30 distinct presented game frames
per second at the current 640x480 presentation, with source-timed simulation,
responsive controls, and bounded memory. Feasibility at this fidelity remains
unproven. Do not promise 30 fps from the current data or a deadline for it.

Preserve camera coordinates/FOV, placements, selected geometry, texture detail,
lighting behavior, alpha, collision, combat timing, and audio events while
removing duplicated work. Recover the original decisions about which work to do
before designing replacement systems. Do not change the camera, horizon, meshes, resolution,
or light count to claim an optimization win. No new room, enemy, weapon, engine
framework, or primary ambience/game-over polish work enters this milestone.

The frozen build establishes native integration and a recognizable source-derived
presentation. It does not establish real-time playability or exact original-game
behavior. Its reduced state machines, RNG call sequence, sampled poses, rebuilt
normals, light selection, and incomplete camera blockers remain source-port debt.
Preserving current behavior is a regression check, not proof that it is correct.

## Two references and a reproducible baseline

1. Preserve `fed3e91` and the existing private manual-v3 package unchanged as the
   Dreamcast regression reference. New runs get separate directories.
2. Use the original G4BE08 debug game, with the same post-s03 state and camera,
   as the source-fidelity reference. Record matching tick/state/camera/RNG/input
   identities; an unrelated outdoor retail screenshot is not an exact reference
   for this cabin. Build paired reference captures where these do not yet exist.

Frozen artifacts were hash-checked during this audit:

| Artifact | SHA-256 |
|---|---|
| Manual ELF | `b70858d412876496f740a8bea3e5cf2752203210d952d97d04d77a268db13c36` |
| 30-second recording with audio | `c8dc6a0825f71b0a21b8b6a783d809987542e01d7ae47805a920ebdb4a6a65ad` |
| Controller-path state trace | `1087a8603c97328cfdc2b41e865c4ac372cd4c80190f586cd8a030a5146eeaed` |
| Packaged Flycast executable | `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a` |

Private directory:
`C:\Flycast-Evidence\re4-dreamcast\d110-exact-r100-manual-v3`.
The trace used a virtual controller through the normal input path; it is not a
human responsiveness test. A video encoded at 30 fps is not 30 new game frames.
No executable was run or physical hardware tested in this planning audit.

Record the compiler commands, KOS revision/local patches, all package hashes,
ELF, emulator executable/settings, controller/input trace, video mode, and capture
configuration for each comparison. The packaged Flycast settings do not explicitly
pin every CPU/memory/renderer option: verify effective settings, stock memory
sizes and clock, and disable enhancements for acceptance. Do not infer the packaged
binary's source revision from the separate, modified Soulcalibur checkout.

Use `tools/evidence_manifest.py` and the exact-identity discipline in
[SOULCALIBUR_REUSE.md](SOULCALIBUR_REUSE.md). Keep that other checkout read-only.

## What the code audit confirms

Locations below refer to `room/main.cpp` at `fed3e91`.

| Finding | Evidence | Consequence |
|---|---|---|
| Room processing is per triangle corner | `transform_triangle`, lines 2329-2381, transforms and lights each indexed corner; `render_scene` calls it per triangle | Restore reuse with bounded scratch storage; the current room path is not a unique-vertex cache |
| Lighting repeats invariant math and omits source selection | `evaluate_source_lighting`, 2040-2121; nine global lights at 134-161, two view-relative | Recover per-model source light lists before baking; prepare constants and reuse only proven invariants |
| Actor preparation is outside the named submission interval | Projection, normal rebuild, and lighting at 3109-3126 precede timing at 3128 | Measure those stages before assigning bottleneck percentages |
| Existing frame statistics are not one paired frame | Prior outer-loop `frame_us` is stored with current render counters at 3867-3878 | Associate frame, render snapshot, simulation, and presentation IDs explicitly |
| Fixed step is not real-time scheduling | Input once at 3659, up to 24 reused-input ticks, then accumulator truncation at 3718 | Queue observed input transitions; count all discarded time and service input regularly |
| Source SAT structure was dropped | Runtime scans at 617-725; `convert_sat.py` keeps the block count only as metadata and discards edge references | Preserve and adapt the authored hierarchy and original query rules before considering a new tree |
| Basic target optimizations are already present | `-O2`, `mat_trans_single`, material headers, 768-vertex batches; KOS immediate submission uses SQ | No generic compiler/assembly/store-queue rewrite without a measured reason |

Reported 780-840 ms frames imply about 1.19-1.28 fps and a 23.4-25.2x interval
reduction to reach 33.33 ms. These are emulator observations, not a measured stock
hardware budget or GPU duration. The CPU-preparation bottleneck is a strong
hypothesis, not a measured percentage.

The intact room package has 40,419 vertices and 92,685 indices. Its whole-package
index/vertex ratio is about 2.29, not a predicted frame speedup: actual visible
reuse, clipping, actor work, and simulation cost matter. A whole-room array of the
current 52-byte `RenderVertex` would require 2,101,788 bytes before cache metadata.
That exceeds the reported uncommitted heap-to-stack gap. Do not restore an
unbounded cache or assume the previous HUD-era memory tradeoff disappeared.

## Source architecture recovered by this audit

The decomp provides executable algorithms, not only constants. These mechanisms
were checked in the source bodies; their actual r100 workload is still untraced.

| Source path | Confirmed mechanism | Plan consequence |
|---|---|---|
| `atari.cpp::blkPolySphereCk/Core`, `blkPolyLineCk/Core` | Child/sibling block traversal, query filtering, per-query polygon duplicate suppression, position mutation during contact processing | Export the hierarchy and adapt the source queries, preserving order and separate SatMgr/EatMgr ownership |
| `light.cpp::cLightMgr::setModel2`, `lightHitCheck*` | Active/mask/kind/parent/color/volume filtering in engine order; eight slots; an additional qualifying light triggers error handling | Recover model masks and lighting volumes, validate selected IDs, then cache selected contributions |
| `trans.cpp::calcWeightMat`, `MakeWeightPalette/Ext` | Shared blended palettes feed CPU position/normal skinning; source remainder-weight rule and rigid shortcut | Retain palette references and separate attribute identities; benchmark against baked poses |
| `trans.cpp::ModelTrans`, `scroll.cpp::setObj/SmdSetParam` | Model registration precedes expensive preparation; authored objects retain placement/shared-model/block identity | Recover source object ownership before adding child render clusters |
| `block.cpp::checkBlockConnect/checkBlockMemory` | Authored active/staged sets and maximum main-memory pool calculation; required loads can stop gameplay | Recalculate those sets using converted resource costs, with Dreamcast storage replacing ARAM staging |

Primary source: [collision][re4-atari], [lighting][re4-light],
[transform/draw][re4-trans], [object placement][re4-scroll],
[block residency][re4-block]. These confirm architecture, not a speedup.

The current r100 SAT manifest lists 1,157 source blocks and 1,507 polygons; the
runtime package has no block records. It exports section 0 of a two-section
container. Establish each section's original manager/use before assigning the
other one to bullet or effect queries. `convert_sat.py` also drops the three
source edge references per polygon and the edge-vector table; retain the fields
needed by the original narrow phase instead of rebuilding an approximate solver.

Preserve BIN/SMD/SMX identities in the next package revision. Count original
positions, normals, render corners, matrix-palette entries, instances, and emitted
PVR vertices separately. A UV seam needs another corner, not necessarily another
position transform. Reuse keys include source identity, weight/rigid-part
association, morph state, instance transform, and (for shading) selected-light
context. Never weld by coordinate equality. Use a small direct source-model
converter for this encounter; an OBJ export is a visual aid, not the authority for
engine semantics. Version packages and fail on missing required semantics rather
than silently substituting guessed flags.

Source correctness can properly change the frozen image or collision response.
Such changes need a separate fidelity checkpoint against the original game;
do not insist on preserving an identified prototype error, or report its correction
as an image-identical optimization.

## Ordered work packages

Each change gets its own baseline/candidate result, including negative results.
Keep the reference executable bootable; no asset simplification is bundled into
an optimization commit.

| Order | Bounded work | Required exit evidence |
|---|---|---|
| R0 | Freeze references; instrument target and matched original-game workload; correct input/debt and memory accounting; establish hardware route | Frame-associated trace, source-object/light/query inventory, CPU/PVR/presentation separation, complete debt counters; hardware result or explicitly pending status |
| R1a | Bounded unique room-vertex cache and trivial clip classification | Same draw/state output, reduced transform/light counts, measured stage cost, fixed scratch ceiling |
| R1b | Recover source object identity and per-model light selection; prepare constants; only then cache/bake static contributions | **In progress:** target package/runtime implemented and measured; selected light IDs/order and changed image still need the matched source trace |
| R1c | Reuse selected fixed room-light contributions while retaining view-relative lights | **Target-side complete:** prior packed vertex colors matched at the checked camera; original-game image/light trace and hardware timing remain open |
| R2a | Export source SAT blocks/edges and adapt source traversal/filtering/primitives | **In progress:** hierarchy/edges/traversal are implemented and measured; source primitive, attribute, manager, and matched query-result parity remain open |
| R2b | Retain source attribute/weight-palette structure; source eligibility before preparation; benchmark skinning | Selected clip, normal, attachment and event parity; separate position/normal/corner counts and measured target cost |
| R3 | Native draw templates from source cull/material state; child clusters; clipping/packet improvements | Same authored draw meaning; no missing surfaces, alpha/order regressions, clipping failures, or TA buffer overflow |
| R4 | Qualify the unchanged encounter against the stock hardware frame budget | Live presentation/input/audio distributions and peak memory meet the acceptance section below |
| R5 | Explicit residency and source-runtime integration before expanding content | Bounded loading/restart/transition peaks; original behavior coverage grows instead of a second gameplay implementation |

R0 input service and the texture-sharing fix below are small supporting tracks.
R2a/R2b priority follows measured cost, without creating a new collision tree or
animation framework. Source traces can begin while R1a proceeds; unavailable
traces must not be replaced with invented per-model light lists.
Hardware setup begins at R0 and hardware reruns follow meaningful changes.
Unavailable hardware does not prevent R1-R3 implementation, but Flycast results
cannot close R4. Do not wait for a generalized streamer or full skeletal rewrite
before removing the demonstrated repeated room work.

The first implementation patch is R0 target telemetry/input-debt accounting plus
a bounded source-workload inventory, with no renderer or gameplay change. Start
source probes on Leon, Ganado, one cabin object, and one sphere/line query, then
extend coverage. R1a follows as its own measurable renderer patch. No full engine
port is a prerequisite, and no phase is complete on static code inspection alone.

### R0: measure the right work and capture input

Reuse the original `Trans()`/game subsystem timing boundaries and collision query
counters where useful. Collect paired snapshots from the original debug binary
or a verified matching source build in Dolphin, using a separate instrumentation
build or read-only probes. Source timings explain structure; they cannot predict
Dreamcast milliseconds. Begin with spawn, normal/aim extremes, a shot, wall contact,
reload, and death/retry before extending to the full route.

| Matched source/target record | Question answered |
|---|---|
| Object ID, model/instance/block ID, eligibility result and bounds | Are we preparing source-rejected models? |
| Ordered light IDs, model masks/volumes, active light state | Are we shading with extra or wrong lights? |
| Position/normal/corner/palette counts, rigid/skinned path | Which independent transforms can be shared? |
| Query manager/flags, block visits, polygon IDs/tests/hits | What work and behavior did SAT flattening change? |
| Draw part, cull/depth/blend/alpha state, passes | What native material templates are actually needed? |
| Active/staged block IDs and converted byte totals | What working set does the encounter require? |
| Actor states, motion times, contacts, camera, input, RNG | Does a change preserve the authored encounter? |

Trace actual values rather than inferring that actors use only two or three
lights or that all off-screen animation work is unnecessary. Before source traces
exist, mark recovered algorithms as source-derived and encounter behavior as
unverified. Preserve source game-update/render-registration separation.

Use fixed-size trace storage with completion/sequence markers so host reads do
not combine half-written frames. Record `frame_id`, render `snapshot_tick`,
simulation tick range, input sequence IDs, and the presented-buffer identity.
Measure overhead with tracing enabled/disabled. Export traces outside the hot
loop; avoid per-triangle timers and serial printing during timed intervals.

Record separate spans for input/simulation, collision/route/camera queries, actor
pose interpolation/transforms, actor normals, actor lighting, room visibility,
room transforms/lighting, clipping, packet construction, transfer, audio/storage,
TA readiness, render completion, and presentation. Nested timings must not be
summed twice, and overlapping CPU/PVR timelines are not additive.

KOS `pvr_scene_finish()` completes submission work and returns before the
asynchronous render completes. Immediate `pvr_prim()` already uses store queues.
Preserve overlap; do not insert a blocking render wait just to simplify the
profiler. [Pinned scene implementation][kos-scene].

KOS records render completion separately from page-flip intervals and page-flip
counts. Associate those events with the submitted snapshot; sampling last-value
statistics alone can mix frames. Use a minimal, documented SDK trace hook if
necessary, with a bounded event ring and no heavy interrupt work.
[Pinned statistics implementation][kos-stats].

On physical hardware use PRFC1 for one event class per repeatable run, such as
cache misses or pipeline stalls. Leave PRFC0's timer role intact. Verify support
before interpreting emulator counter output as hardware measurements.
[KOS performance-counter API][kos-perf].

Retain fixed 1/30-second source updates. Timestamp observed button transitions
and analog samples using the same monotonic clock. Add a small periodic input
service in normal thread context, independent of render completion; measure its
worst service gap. Keep simulation state single-owned and render from a stable
snapshot. Do not put controller API calls or gameplay in an interrupt handler.

Define the timestamp-to-tick policy and consume each edge once, in order. New
input must not be applied retroactively to every overdue tick. Retain bounded
catch-up and count accumulator clamping, dropped whole ticks, dropped microseconds,
maximum debt, input queue overflow, and observed sample gaps. The current
`simulation_overruns` event count misses the initial wall-time clamp and does not
quantify lost time. Extra threads or a larger catch-up limit cannot create CPU
capacity. Test short presses/releases at different render phases, held fire,
simultaneous controls, disconnect, and retry; compare against the selected
source input-sampling semantics.

Run diagnostic builds with constant lighting, actor drawing/preparation disabled
while simulation continues, and 320x240 versus 640x480 at the same camera/FOV.
Report stage deltas. A lower-resolution run changes pixel and buffer costs; it
does not isolate the GPU by itself. Restore the full presentation for acceptance.

### Memory correction and a narrow early fix

The frozen telemetry is a post-load snapshot, not measured peak headroom:

| Field | Bytes | Interpretation |
|---|---:|---|
| Heap break to reserved kernel stack | 1,892,352 | About 1.80 MiB address-space gap; not a measured largest successful allocation |
| Free within heap arena | 205,368 | Separate from the gap; fragmentation and other stacks still matter |
| PVR allocator free bytes | 1,488,296 | About 1.42 MiB after loading; not peak/contiguous-block evidence |
| `snd_mem_available()` result | 1,378,336 | About 1.31 MiB raw API result; free-space semantics require correction |

The pinned sound allocator's query selects the largest block without testing its
`inuse` flag. It is not a reliable total-free or largest-free metric. Audit/fix
the diagnostic in a separately recorded SDK patch or obtain equivalent verified
allocator accounting; retain the original raw value in historical evidence.
[Pinned sound allocator][kos-snd].

Read-only package inspection found another concrete opportunity:

| Current actor texture package | Descriptors | Distinct referenced payloads | Redundant uploaded payload bytes |
|---|---:|---:|---:|
| `leon-source-r100-gunhitcaps-pitch.re4tex` | 78 | 11 | 1,228,800 |
| `ganado-source-r100-hitcaps.re4tex` | 14 | 4 | 311,296 |

Their hashes are respectively
`563145f7a8cd88372426dd2f5de9f27a6a3e4a360439f955c714503836e8de58` and
`bb8bb7175da2300682dac038351544f2fe5d714cabc61f7a25e30f77b2ef1d54`.
`room/texture_package.cpp::upload` currently allocates every descriptor; the
converter has already shared these payloads on disk. Sharing immutable uploads
with identical payload range, dimensions, and pixel format could save 1,540,096
bytes (about 1.47 MiB) of VRAM payload before allocator overhead. This is a
calculated opportunity, not an implemented saving or frame-rate gain.

Preserve distinct material headers/sampler/blend settings while sharing texture
storage. Track allocation ownership so close, failure cleanup, and retry free
each allocation exactly once. Keep scope within each package initially.

Measure main RAM/VRAM/AICA current usage, peaks, largest free blocks, stack
high-water marks, PVR parameter-buffer maxima, and failed allocations during boot,
play, death, repeated restart, and later transitions. Include trace/cache/input
buffers. Reserve a documented safety margin before approving larger caches.

### R1: room reuse, source light selection, and prepared lighting

Partition existing indexed work into bounded chunks without welding positions or
losing UV/normal/material seams. Start with capped scratch sizes (for example,
512 vertices, then compare 256/1024); enforce the actual byte budget at build/load.
Preserve triangle order, especially for translucent work. Avoid per-frame heap
allocation. Cache original-index identity, projected position, pre-divide depth,
RGB, and clip flags. Count input index references, per-cluster unique vertices,
cache misses/retransforms, light evaluations by class, accepted/rejected triangles,
and triangles entering the full clipper. Reuse group visibility across passes.

Trivially accept/reject using cached plane flags; keep the existing correct
near-plane fallback for crossing triangles. Preserve depth directly where the
matrix path allows it, rather than computing a reciprocal and then reversing it.
Do not replace SH-4 FTRV with slower generic transforms merely to obtain depth.
Validate near-plane crossings, far limits, screen edges, extreme aim, and wall
camera probes against the reference before changing packet topology.

Before baking, port the relevant `setModel2` selection with source model masks,
volumes, active/parent/event state, kind filtering, iteration order, and overflow
handling. Its eight slots are not a nearest-light selector or permission to
silently truncate nine candidates. Compare selected IDs for Leon, Ganado, and
each cabin object against the original-game trace. Selection may correct the
reference image: accept that as source-fidelity work separately.

Then prepare normalized directions, cutoff terms, attenuation constants, and
normal invariants once. Cache only selected world-space contributions for static
models; update selected view-relative directions once per camera change. The
current nine-light approximation contains seven world-space and two view-space
lights, but that is not the source-selected list for every model. Actors still
need pose/position-dependent terms. Invalidate on selection, masks, parent/event
state, lighting cut, geometry, normal, or transform changes.

Retain source radius-based model-volume selection. That is separate from the
attenuation equation: do not invent a hard per-vertex radius cutoff. Do not bake
camera-relative terms into static room colors.

Keep partial lighting unclamped; apply the original final clamp after accumulation.
Summing the static subset changes floating-point addition order, even without
early clamping. First compare a version preserving per-light order, then quantify
any aggregate-cache difference before accepting it. Report max/RMS RGB error,
affected pixels and annotated views; do not assume bit identity or choose an
error tolerance after seeing the result. Initial fidelity-preserving target is
identical packed color; any exception needs an explicit comparison and disposition.

Float RGB for all 40,419 current room vertices costs 485,028 bytes before metadata.
Account for that residency and loading peak, not only the small transform scratch.
Prefer room-load computation first to compare on the same SH-4 arithmetic path;
offline baking is a later measured representation choice.

### R2-R3: reduce remaining work without changing the encounter

Recover source `ModelTrans` eligibility, bounds, ordering-table acceptance, and
normal-path preparation order. Keep source model instances/shared data/block and
SMX identity as the first visibility level, with smaller Dreamcast clusters below.
Reject only conservatively invisible actors before render preparation, including
blended poses, attachments, and effects. Continue off-screen gameplay, motion
events, root motion, and hit-volume updates required by the original. Cache
unchanged object-space poses/normals (including a settled death pose), while still
updating camera projection and applicable lighting.
Remove duplicate normalization only with verified unit/degenerate-normal contracts.
The current normal and lighting arrays alias: caching requires explicit ownership.

Use [REAL_MOTION_SH4_BASELINE.md](REAL_MOTION_SH4_BASELINE.md) as the starting point
for source motion/IK integration. Its four sampled poses do not prove full selected
clip coverage, source-normal skinning, or runtime cost. Benchmark the existing
source motion code plus `calcWeightMat`,
`MakeWeightPalette/Ext`, and source position/normal skinning against the baked path
using actual Leon/Ganado clips. Prepare each weight-combination matrix once and
reuse its references; retain the final remainder weight, quantization, morph and
rigid/single-part conditions. Keep original positions, normals, and UV corners
separate and assemble native PVR vertices at emission. Packed sampled normals are
an optional memory/performance experiment; interpolating them is not equivalent
to reconstructing face normals.
Do not introduce a second animation system.

SAT work starts with the source block records, sibling/child relationships, leaf
polygon references, attributes, edge data, and manager/instance transforms. Convert
endianness and units explicitly, replacing pointers with validated offsets/IDs.
Bound depth, traversal scratch and per-query duplicate bits by package counts.
Adapt `blkPolySphereCk`, `blkPolyLineCk` and relevant `at_sub` primitives with their
filter flags, manager distinctions, order, tolerances and contact mutations.
The source traversal order, not a sorted global polygon list, is authoritative.

Validate against source query/contact traces; keep brute-force checks as candidate
coverage diagnostics and the old solver as a regression aid. A source correction
need not reproduce the old approximate solver. Test corners, slopes, steps,
overlapping floors, long sweeps, behind-wall hits and camera probes, including
a first contact that changes later block tests. A new grid/BVH is considered only
if the recovered source hierarchy is unavailable or measurably unsuitable.

Recover authored cull, blend, depth-write/test, and alpha-test semantics from
BIN/GX source records. Texture alpha alone cannot classify a material. Preserve
double-sided and soft-alpha surfaces. Then subdivide large source groups spatially
without dropping triangles. Test free camera turns, windows/doors, unseen-to-seen
actors, and near-wall views. General portal/PVS work is conditional on a measured
visibility bottleneck and recoverable source semantics, not mandatory infrastructure.

Build native draw templates for the observed r100 material operations; some can
map to one PVR pass, others need offline preparation or an explicitly measured
extra pass/approximation. Do not build a general GX command interpreter. Texture
`min_lod`/`max_lod` in this source path control mip levels, not mesh simplification.
PowerPC assembly, fixed scratch addresses, and compiler-matching constructs have
no automatic place in the portable hot path; preserve semantics, not those mechanisms.

Evaluate strips/native packets within compatible material boundaries after the
cache/clip path is correct. Keep winding, attributes, transparency ordering, and
clipped-triangle fallback; measure actual transferred bytes and TA buffer peaks.
Benchmark current SQ against a bounded buffered/DMA alternative only if transfer
or overlap costs justify it. Buffering consumes RAM; it is not a free switch.
Inspect effective compiler output and hot-loop assembly; keep global fast-math
away from source simulation and fidelity comparisons.

### R4: real-time acceptance, separately from image/state comparison

Lock the reference route and additional stress cases before final measurement.
At stock 60 Hz output the target is one new game frame per two refreshes
(approximately 30 fps; use the measured refresh period rather than assuming an
exact 33.333 ms boundary). Report 50 Hz or other modes separately.

Require:

- At least a continuous 30-second encounter and three repeated runs, covering
  free movement, both aim extremes, near-wall views, fire/reload, kill, death,
  and retry across the runs. Include a live human controller check.
- Presentation IDs and simulation-snapshot IDs show new game updates at the
  target cadence, not repeated scanouts or an encoded-video frame rate.
  Report p50/p95/p99/max intervals, counts and durations of missed deadlines,
  and the warm-up/loading window separately. The accepted measured route has
  no missed two-refresh presentation deadlines.
- No discarded simulation time or input queue overflow. Record sample gaps,
  observed-input-to-tick and observed-input-to-present latency distributions.
  Input service should run at least once per refresh and the simulation consume
  eligible samples on the next fixed tick; verify these bounds on hardware.
  Report device polling uncertainty instead of calling observations physical
  button-contact timestamps.
- Audio events stay tied to simulation events, with measured audiovisual
  alignment in live output, including catch-up/restart cases. A loopback recording
  or post-edited capture offset alone does not prove synchronization.
- Native images remain faithful at matched simulation ticks; simulation state,
  source event order, and RNG/input identities remain equivalent for pure
  optimizations. Image-diff views include temporal motion/alpha/clipping review.
- Measured main RAM, VRAM, AICA, stacks, trace storage, and TA buffer peaks fit
  stock pools with a declared reserve and no allocation/overflow failures.

Use CPU/PVR overlap correctly when setting sub-budgets from the R0 baseline.
If any unavoidable stage alone exceeds the target interval, document it and
re-plan that stage. Do not multiply isolated speedups into a promised 24x result.
If the intact scene still misses the budget after these passes, present measured
remaining costs and options; a fidelity concession needs a separate decision.

### R5: scale the port after the same-encounter work

Start from authored BLK active/staged/remove sets and `checkBlockMemory`, recomputing
the largest active set and transition overlap using converted sizes and shared
resource identities. Do not introduce a guessed loading radius. Preserve original
load-stop behavior where applicable; seamless loading everywhere is not a source
requirement. Map staging/prefetch onto the selected Dreamcast storage/cache policy;
GameCube ARAM is not spare Dreamcast AICA memory.

Move from embedded ROM disk and mandatory `fs_mmap()` to bounded read buffers,
active room blocks, immutable shared resources, texture handles, and reclaimable
upload staging for the intended storage medium. A path change from `/rd/` is
insufficient; closing an embedded mapped file does not remove its payload from
the executable. Pre-twiddle textures offline for loading efficiency, without
crediting startup work as a per-frame saving. Expand residency now only if the
measured R1-R3 memory budget requires it.

Progress source ownership along the existing encounter: camera interactions,
player/enemy state transitions, random-call order, motion/IK, then events.
Separate source-fidelity fixes from optimization comparisons when they properly
change the frozen build's behavior or appearance. Keep the ledger classification
(original code, behavior-preserving adaptation, temporary approximation) current.
No expanded content until the runtime and resource model support it.

[kos-scene]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/hardware/pvr/pvr_scene.c
[kos-stats]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/hardware/pvr/pvr_misc.c
[kos-perf]: https://kos-docs.dreamcast.wiki/group__perf__counters.html
[kos-snd]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/sound/snd_mem.c

[re4-atari]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/atari.cpp
[re4-light]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/light.cpp
[re4-trans]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/trans.cpp
[re4-scroll]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/scroll.cpp
[re4-block]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/block.cpp
