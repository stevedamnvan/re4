# Active persistent architecture goal: productionize D349 for r100

User-directed architecture, 2026-09-22. Status: implementation in progress; no
native static cutover acceptance yet. Current primary reference is D362
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
