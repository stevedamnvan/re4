# Active persistent architecture goal: productionize D349 for r100

User-directed architecture, 2026-09-22. Status: source-block budget qualification
and implementation in progress; no native static cutover acceptance yet.
Current primary reference is D362
62414dc39feccc949af4b3ed29053be9fde4d5fc; preserve all newer/inherited work.
Historical optimized renderer: 5f42caa634c0e6124c48842e21570033738adfda (D349).
The app persistent goal was reset to this r100 milestone on 2026-09-22. This
document is its durable architecture/acceptance contract. The broader menu and
r100 -> r101 -> r103 playable objective remains open in PLAYABLE_PATH.md.

Implementation is assigned to GPT-6 Sol at Max reasoning after Astra commits the
architecture lock. Continue through the complete target candidate and measured
acceptance; do not stop at an isolated adapter or restart architecture selection.

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

Compare 20-byte AoS with a split/aligned XYZ + UV/color representation using
the actual SH-4 preparation/packet path. Select on resident bytes + transform
CPU + packet CPU; do not lock the default from file size alone. Preserve the
D349 renderer/control. SH4ZAM is an authorized, measured target-backend
candidate, not a new renderer. Inspect/pin its current implementation and PVR
DMA example. Initial candidates: batch XYZ through XMTRX, positive-depth
`shz_invf_fsrra`, equivalent near-plane interpolation, and aligned remaining
packet/header copies. Preserve clipping, error bounds, XMTRX state, DMA/SQ
ownership and the existing frame owner. Do not replace a proven mechanism
merely because SH4ZAM also provides it. Keep GCC 15.2 and pinned KOS unchanged.
After static cutover, evaluate vector normalization/dot for residual dynamic
lighting and `shz_xmtrx_blend` for native actor skinning. These are later bounded
backend candidates; current source pose/animation authority is unchanged.

Record package sections, SH-4/compiler/emulator identities, numerical error and
timings separately from game-frame acceptance. A CPU fixture does not establish
GPU throughput, physical-hardware cache cost or recovered-game heap recovery.

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
PVR calls/bytes; whole render/presentation distributions against D361/D362; matched
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
active set cannot fit after replacing corresponding source render backing.

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
