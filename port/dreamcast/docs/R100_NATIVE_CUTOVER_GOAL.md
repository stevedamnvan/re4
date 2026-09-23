# Persistent architecture goal: beat D349 with the recovered game

**Superseded 2026-09-23 by [D367_THIRTY_FPS_ROUTE.md](D367_THIRTY_FPS_ROUTE.md)**
(30 fps on hardware, three-room route, frame time leads every decision). The
contract below is kept as history; where they conflict, D367 wins.

User-directed architecture and roadmap, updated 2026-09-23. Status: **paused by
user request**, not complete. The four-owner v4 format/CPU fixture is qualified
at D364; recovered-game cutover remains unaccepted. Resume from
[R4_D366_CLAUDE_HANDOFF.md](R4_D366_CLAUDE_HANDOFF.md) only when instructed. The architecture and accepted implementation sequence remain unchanged while paused.
Current primary reference is D362
62414dc39feccc949af4b3ed29053be9fde4d5fc; preserve all newer/inherited work.
Historical optimized renderer: 5f42caa634c0e6124c48842e21570033738adfda (D349).
The app persistent goal was reset to this r100 milestone on 2026-09-22. This
document is its durable architecture/acceptance contract. The broader menu and
r100 -> r101 -> r103 playable objective remains open in PLAYABLE_PATH.md.

Implementation is assigned to GPT-6 Sol at Max reasoning after Astra commits the
architecture lock. Continue through the complete target candidate and measured
acceptance; do not stop at an isolated adapter or restart architecture selection.

## North star and execution order

Make the real recovered RE4 game drive a Dreamcast-native visual workload that
is cheaper than historical D349 while preserving the real GameCube gameplay and
state systems that the prototype simplified. D349 is the proven presentation
architecture, not a storage ceiling or an equivalent-workload performance promise.

The immediate milestone remains the complete r100 static cutover. Continue in
this order: **AoS20 reader/integration qualification -> source-backing replacement
accounting -> FILE_01 PS2/DC reduction -> complete r100 static cutover -> measure
residual CPU/PVR workload -> native actors -> broader PS2/DC visual reductions
-> SH-4-specific tuning.** Do not restart work already qualified at D364.

The durable roadmap within this architecture is:

1. **Native static world.** Finish and integrate the four source-owner-aligned
   v4 packages. Offline strips/batches/material IDs and qualified prelit color
   replace GC render-only backing. Source object visibility, activation,
   transforms and current material state drive native SourceGroups directly.
   Require zero converted-static GX decode, normal transforms where normals are
   removed, general static light evaluation where baked, and corner remapping.
2. **Reduce final PVR work.** Emit fewer useful vertices and passes through
   native strips, early group/batch culling, fewer material splits, no duplicate
   source/native drawing, qualified reduced geometry/alpha and native actors.
   Do not attempt to compress PVR packets. Track native static room, dynamic
   actors, effects, HUD and generic fallback traffic separately.
3. **Native actor visuals.** Replace visual ModelPart translation with native
   Leon/Ganado/weapon packages consuming current GC skeleton/bone matrices,
   animation decisions and combat state. Preserve attachments/hit transforms.
   Prefer qualified PS2/custom lower-cost meshes and D349 prepared actor lights.
4. **PS2/DC visual budget.** GC and PS2 are first-class offline inputs now.
   Qualify lower-poly static/actor meshes, fewer materials, simpler alpha,
   smaller/native textures, matched PS2 COLOR, simpler shadows/water/effects,
   and prerecorded movies under GC event/skip/completion authority. Every final
   runtime resource uses the existing Dreamcast-native representation.
5. **SH-4 optimization after workload removal.** Once generic visual bridge work
   has largely disappeared and residual costs justify it, benchmark SH4ZAM/
   XMTRX, useful actor skinning, positive-depth reciprocal, dynamic-light math,
   direct versus DMA transfer and compiler tuning. Faster math is not a
   substitute for removing avoidable GC work. Keep the pinned GCC15.2/KOS;
   a toolchain-wide change remains a separate measured decision.

Historical reference thresholds, not workload-equivalent acceptance promises:

| Reference | Historical cost |
|---|---:|
| D349 whole-trace CPU p50 | about 57.6 ms |
| D349 mean presentation interval | about 55.2 ms / 18.1 presented FPS |
| D349 PVR traffic | about 0.97 MB/frame |
| D353 settled prelit historical room pass | about 17.6 ms |

The strategic stretch objective is to make the real source-driven game cost no
more than that historical workload, then pursue 33.3 ms / 30 FPS if measured
hardware limits permit. Retain the historical fixture/workload distinction.

## Architecture, not another bridge optimization

Recovered GameCube source is the authoritative simulation/state engine.
D349-style Dreamcast-native packages and renderer are the intended presentation
architecture. The generic live
`commonModelTrans -> re4dc_draw_model_part -> native_model.cpp` GX/ModelPart path
is a compatibility fallback for unconverted content, not the final renderer.

Source remains authoritative for gameplay/AI/collision/camera, room/event/object
activation and visibility, inventory/health/flags/progression, r100 -> r101 -> r103
transitions, animation decisions and current skeletal pose, Leon/enemy/weapon
attachments and hit transforms, owner generations/lifetime/retirement, current
material/texture animation, required alpha/depth/cull, dynamic actor and genuinely
changing lighting, audio/event completion/death/retry, and the one PVR/frame owner.
These systems drive native visual assets; they do not require retaining the
GameCube rendering representation. No historical prototype gameplay/camera or
sampled animation; keep current corrected facing.

## Required reuse chain

Inspect historical `5f42caa` read-only and reuse these paths under
`port/dreamcast/` (use current descendants and their fixes):

- tools/prepare_streamed_room_obj.py: authored streamed OBJ, original BIN material
  repairs, source grouping/identity and source/spatial selection.
- tools/convert_room_obj.py: deduplicated corners, source object/material groups,
  SMX/SMD placement/identity, group bounds and select/cull/flag/light volumes,
  spatial partitioning, offline stripification with triangle order/winding checks,
  and strip-only backing where proven equivalent.
- room/room_package.hpp and room/room_package.cpp: existing .re4room Material/Group/Batch/Primitive/
  SourceGroup contract. Extend/adapt it and its identity metadata.
- Historical port/dreamcast/room/Makefile: r100-source-cell-4.re4room plus separate existing native
  textures, collision, character/HUD/audio resources. Reuse applicable mechanisms;
  recovered source still owns gameplay, current pose and collision.
- docs/R4_R100_REFERENCE_RECOVERY_CHECKPOINT.md: preserved artifacts and D349 pass,
  actor assembly, prepared lighting, visibility, strip emission, material headers,
  and load/upload/retire/fence contracts.
- `d928ad6` / `experiment/r100-prelit-d353` and its `docs/R4_PRELIT_R100_CHECKPOINT.md`:
  existing GC-derived bake is the safe reference/fallback. PS2 RGB transfer is
  not already qualified. Worktree: /root/work/re4-r100-prelit-d353.
- room/texture_package.*, room/room_storage.*, room/gpu_lifecycle.* and the
  existing native_ui/ui_bridge frame owner: reuse install/upload/reclaim and
  load/retire/fence ownership; do not create another cache or PVR owner.

The intended production chain remains source geometry -> existing preparation/
convert_room_obj.py -> .re4room or its budgeted successor -> D349 native renderer.
Extend source object identity so current recovered objects directly select and
transform native SourceGroup/batches. Replace corresponding source render-only
backing after adapting its remaining CPU readers. Keep live material selection.
Do not retain full GC and DC scenes together or create another general framework.

## Modernize storage while retaining the proven architecture

D349's approximately 1.195 MB auxiliary footprint is not mandatory. Eliminate its
static RGB/owner arrays where D353 baking qualifies; use compact actual-count or
selective bounds and batch/index metadata. Qualify compact XYZ/UV/packed-RGB
vertices in the existing package. No new general runtime cache simulating offline
preparation. Converted scenery must have zero per-frame GX topology decode,
static normal transforms, general static vertex-light evaluations where baked,
and runtime source/native corner remapping. Strips/batches/material IDs are
prepared offline. Source visibility/activation and transforms stay live. Explicitly
handle changing/camera-relative lighting; never conceal it in a fixed bake.

## Accepted residency basis

The four reproduced packages MAINSCENARIO, FILE_00, FILE_01 and FILE_02 are the
accepted current cutover residency basis. Continue these exact owner-aligned
packages, price source backing replacement, and qualify v4 on target. Do not
return to the all-block monolith or invent finer streaming unless measured
source ownership requires it. PS2 geometry/material substitutions enter where
these measured packages remain too expensive after v4 or materially reduce
runtime work. The historical spatial subset is not complete r100 acceptance;
remaining source-controlled content remains an explicit fallback.

## Approved package-v4 and target-kernel qualification

Extend the existing `.re4room` contract, retaining a selectable historical v3
reader/build. The production static candidate keeps float XYZ, compact UV and
packed prelit RGB (20-byte AoS target), 16-bit batch-local indices, and only
useful resident identity/bounds metadata. Remove diagnostic names only after
preserving their source owner/work/BIN mapping. Do not quantize positions in
this pass. Count duplicated local vertices, padding, metadata and scratch, not
just the nominal vertex-stride reduction.

D364 completed the initial target layout comparison. Freeze **AoS20 as the
leading v4 layout** unless integrated target evidence disproves it. The four
packages are 1,992,824 B in v3, 1,299,298 B in AoS20 and 1,478,690 B in Split24.
AoS20 saves 179,392 B versus Split24 and was slightly faster in that CPU fixture.
SH4ZAM transform/reciprocal did not improve it; D349/KOS math stays default.
Stop Split24, SH4ZAM and layout micro-tuning as the primary activity. Preserve
their reader/tests, pinned source and negative results; do not rerun the initial
comparison without new integrated evidence. See R4_ROOM_PACKAGE_V4_CHECKPOINT.md.

The native source binding, actual ownership replacement and moving visual checks
remain open. Fixture preparation/packet time is not game-frame, GPU, physical
hardware or source-heap acceptance. Keep exact package sections and identities.

## Active FILE_01 cost reduction

The four-owner known-span replacement model leaves **746,816 B** beyond D362's
free/largest block, before adapter and staging costs. This is modeled, not an
actual failed candidate allocation. It activates authorized PS2/DC asset reduction
inside the established architecture now; v4 alone is insufficient.

Use FILE_01 as the first explicit cost target. For its exact accepted asset set,
decompose geometry, textures, material metadata, alpha/translucency, normals/
colors, owner/lifetime and actual opening residency. Record source backing that
can really be removed and attributable prepared vertices, passes, PVR traffic
and CPU. Texture savings in VRAM do not automatically recover source heap.

Compare GC-derived v4, correspondence-qualified PS2 geometry/materials, and a
custom DC-reduced representation through the same v4/D349 contract. Reuse prior
inventories/candidates. Investigate lower-cost meshes, verified PS2 RGB, native
smaller/VQ/16-bit textures, fewer material groups, reviewed simpler alpha and
removal of unnecessary visual-only detail. Preserve GC identity, pivots/
transforms, collision, events, activation/visibility, gameplay and owner lifetime.

Aim for roughly **900 KB-1 MB gross reduction/headroom**, if feasible, rather
than erasing the modeled gap exactly. Show net allocator recovery, loading
overlap and remaining runtime margin; do not turn this target into a claimed
saving or a new reservation. Measure whether geometry reduction also removes
emitted vertices, material passes, packet bytes and preparation work.

Do not create another renderer, general converter, streaming system, ownership
model, cache campaign or package family. If FILE_01 plus authorized substitutions
cannot close the measured gap under these existing owners, preserve evidence
and emit **ASTRA/MAX ARCHITECTURE ESCALATION REQUIRED**. Do not invent a replacement.

## Definitive visual input policy

GameCube recovered source = behavior/state authority.
GC and PS2 assets = candidate visual-source inputs.
Dreamcast-native package = final runtime representation.

PS2 is a first-class option inside the existing offline pipeline, not a later
parallel renderer or merely an oracle. For expensive assets, qualify GC versus
PS2 during conversion once the native contract exists; do not first perfect
every GC-derived asset.

- Static geometry: verified PS2 object correspondence is an authorized preferred
  candidate when actual processed vertices/materials/alpha/runtime costs improve.
  Preserve GC object identity, pivot/placement and state.
- Static lighting: PS2 COLOR geometry may compete with the D353 GC-derived bake;
  qualify matched correspondence before claiming authored RGB transfer.
- Textures/artwork: select GC or PS2 per asset; output existing offline PVR-native
  twiddled/VQ/16-bit packages. Never add a PS2 runtime texture decoder.
- Leon/Ganado/weapons: after establishing the native actor interface, prefer
  qualified lower-cost PS2/custom visual meshes consuming current GC skeleton/
  pose/animation decisions. No imported PS2 gameplay or animation logic.
- Cutscenes: PS2 prerecorded presentation is authorized, with GC source event/
  skip/completion state authoritative.
- Water/shadows/effects: PS2 is a lower-spec presentation precedent; custom native
  Dreamcast implementation may be preferable to literal PS2 code/assets.

## Immediate cutover and measured acceptance

Build one complete qualified r100 static cutover using this converter/package/
renderer architecture and current recovered-game owner/state boundaries. Genuinely
dynamic or unconverted content may remain on an explicit fallback list. No new
broad inventory, cache ranking or duplicate/unused-array campaign.

Retain D361 `1039667` (128 KiB preparation, matched 1563 -> 1368 ms improvement) and
D362 `62414dc` (34,016 B actual heap recovery, no material CPU improvement). D362 ends
lossless scavenging. Control evidence is under C:/Flycast-Evidence/re4-dreamcast/
d361-retained-model and d362-shared-uv; selected UV mirror: /root/probe/d362-mirror.
D349's 49-58 ms is proof of its architecture, not a promise for the full source game.

Report converted static percentage/identities and native-package coverage;
remaining static GX bytes/frame (zero for converted work); normal transforms and
static light evaluations (zero where baked); actual backing removed; package,
metadata and workspace bytes; loading/transition overlap and largest free block;
PVR calls/bytes split into native static, actors, effects, HUD and generic
fallback; whole render/presentation distributions against D361/D362; matched
source state, reviewed visuals and deliberate differences; all generic fallback
content. Keep required source boot/menu/encounter and one frame owner intact.
Qualify the measured window with matched source ticks/state, no discarded frames
or allocation failures, no texture uploads after warm-up and stable queue usage
below capacity. Do not fund persistent pressure by growing the queue. Keep nested
wall-time spans on TMU2; PRFC1 is a separate optional diagnostic. Actor/skin costs
remain secondary until the complete static cutover's residual work is measured.

Separate Flycast evidence from physical hardware; static cutover alone does not
accept the full encounter or three rooms. Dynamic visual-package cutover follows,
then r101/r103, preserving existing stage-audit/gameplay/audio/residency backlogs.

## Astra/Max escalation rule

Astra decides architecture. Sol executes architecture. Sol escalates to
**GPT-6 Astra / Max** when new evidence invalidates or materially changes the
approved architecture, including any of these conditions:

- The D349-derived representation cannot fit measured RAM, VRAM or loading peaks.
- Replacing source render backing exposes an unknown consumer or lifetime that
  may break, or existing D349/native mechanisms appear unsuitable and a
  replacement is being considered.
- Required source state/semantics cannot be represented by the native package,
  or source object identity cannot safely control the converted representation.
- PS2 geometry, lighting or animation correspondence conflicts with GameCube
  behavior, or actor conversion requires changing skeleton/pose authority.
- Measured performance materially contradicts the architectural model.
- Meeting the target appears to require a new renderer, package format, cache,
  streaming architecture or ownership model, or materially increasing a locked
  memory budget.
- A proposed change would alter gameplay, collision, AI, progression or events.

Ordinary bugs, converter implementation details, compatible format extensions,
tests, room conversion and performance tuning within the established contract
remain Sol work. Do not escalate merely because implementation is difficult.

At a trigger, preserve the working candidate/evidence and do not invent the
replacement. Record the precise blocker, affected source/native contract,
measured evidence, memory/performance implications, investigated existing
mechanisms and 2-3 viable options if known. Commit safe completed work when
appropriate. Produce a handoff headed exactly:

**ASTRA/MAX ARCHITECTURE ESCALATION REQUIRED**

Use the supported model handoff to GPT-6 Astra / Max; if unavailable, stop and
request the operator switch models. Astra resolves the question, records the
decision in this durable goal/handoff, and hands implementation back to
GPT-6 Sol / Max. A queued model change is not evidence the decision is resolved.

Current qualification: [D349 slices and source-block budget](R4_R100_SOURCE_BLOCK_BUDGET.md).
The 14,577,304-byte monolithic conversion is not the target representation and
does not trigger escalation by itself. Reconstruct the existing D349 source/
spatial slices and map them to the source block create/retire lifetime. Continue
in Sol/Max if those owners can directly hold bounded native packages. Escalate
only if a different residency/ownership architecture is required or the measured
active set cannot fit after replacing corresponding source render backing and
qualifying the explicitly authorized FILE_01/PS2/DC asset reductions. D364's
modeled v4-only shortfall activates that work; it is not itself an instruction
to stop or design a different owner model.

## Anti-reinvention rule (carry across compactions and future agents)

Before designing a new Dreamcast rendering structure, converter, cache, package
or lifecycle mechanism, inspect the preserved D349 implementation and existing
port/dreamcast/tools, port/dreamcast/room, native texture/storage/lifecycle code,
and isolated completed experiments. Reuse or extend the proven mechanism unless
a documented source semantic or measured budget makes it unsuitable. Record why
an existing mechanism cannot be used before introducing a replacement.

The uncommitted D363 embedded-native-BIN draft is rejected as a production
architecture: it bypassed the existing .re4room chain and expanded loaded geometry.
Its private experiments remain evidence, not the next implementation path. Keep
only useful existing-baker adaptation when resuming the approved chain.
