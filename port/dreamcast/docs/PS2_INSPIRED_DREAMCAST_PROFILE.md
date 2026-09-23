# PS2-inspired Dreamcast visual profile

Active user authorization, 2026-09-22. The current implementation unit and
acceptance contract are [the r100 native cutover](R100_NATIVE_CUTOVER_GOAL.md).
This document defines visual choices; it is not a second roadmap.

## Authority and active scope

GameCube recovered source is behavior/state authority. GC and PS2 assets are
first-class candidate visual inputs. The final runtime representation is the
existing Dreamcast-native package/renderer pipeline.

The r100 static phase is active now. Qualify GC-derived baking, verified PS2
COLOR/geometry/artwork and custom native representations during conversion of
costly assets. There is no requirement to finish a perfect live GX bridge or
every GC-derived mesh before considering PS2. D353's GC bake is the existing
reference/fallback; PS2 RGB transfer still needs matched correspondence.

Keep current source gameplay, object/owner state, camera, current pose and
required material/lighting dependencies. A lower-cost representation must not
conceal missing source-system integration or a lifetime defect. That is a
correctness boundary, not a gate postponing authorized static replacement.
Dynamic actor packages follow the static cutover and consume the GC skeleton/
pose/animation decisions; movies, water and effects use the existing scoped work.

The first explicit current cost target is the accepted FILE_01 owner package.
D364's AoS20-plus-known-source-replacement model leaves 746,816 B of shortfall;
compare GC v4, qualified PS2 and custom DC input for that exact set. Aim for
900 KB-1 MB gross reduction/headroom if feasible and account for actual retained
source allocation, load overlap and runtime work. This is not authorization to
split owners, launch a broad inventory or silently alter required source state.

## Authorized candidate compromises

| Area | Candidate representation | Contracts to retain / qualification |
|---|---|---|
| Static environment lighting | Prefer prelit/baked vertex RGB or texture lighting for qualified scenery instead of general per-frame GameCube room-light evaluation. | Preserve object/room identity and intended readability; account for camera-relative or changing lights and avoid baking then applying the same light twice. Label the visual compromise explicitly. |
| Dynamic lighting | Selective runtime lighting for Leon, enemies and important dynamic objects, using bounded prepared light sets. | Source actor state and animation remain authoritative. Identify any changed visual light-selection policy instead of silently claiming source-equivalent lighting. |
| Static geometry | PS2-derived or custom Dreamcast visual meshes. | Keep GameCube collision, events, object state, room layout, pivots, required openings and interaction semantics. A visual substitute must replace the actual expensive backing. |
| Character geometry | PS2-derived/custom reduced Leon and Ganado meshes mapped to the current GameCube/source skeleton and animation state. | Do not import PS2 gameplay or animation logic. Preserve required components, attachments, weapon/hit alignment, source motion decisions and pose/event timing. Test deformation and supported influences. |
| Materials | Reduce material/pass count, bake detail where useful; favor opaque and binary punch-through over soft translucency. | This is an authorized visual trade, not an equivalent blend conversion. Inspect alpha edges, ordering, depth and changed soft effects in motion. Preserve gameplay visibility and required surfaces. |
| Textures | PS2 artwork may be an input; prepare offline Dreamcast-native twiddled/VQ/RGB565/ARGB1555/ARGB4444 packages through the existing converters and shared loader. | No PS2 runtime texture path. Keep the chosen representation native through upload/sampling; price descriptors, palettes, staging and actual VRAM. VQ is not automatically lossless. |
| Water/reflections | Simpler animated/tinted water without a reflection render target. | Preserve the water surface, room geometry/height, shoreline and required gameplay interactions; retire only effect-owned target/pass resources safely. |
| Shadows/effects | Simpler shadows, fewer particles, reduced light shafts, refraction and other expensive visual effects. | Separate presentation from damage, visibility rules, collision, event completion and effect-owned resources. Do not drop gameplay effects with their visual emitters. |
| Secondary animation | Drop non-gameplay-critical hair, cloth, eye or other secondary motion when needed. | Retain source gameplay animation choices, hit/weapon transforms, required facial/event state and animation events. Qualify which work is actually secondary. |
| Cutscenes | PS2 prerecorded cinematics as an authorized presentation source/candidate. | Source event completion and gameplay state remain authoritative. Preserve skip/EOF/error distinctions, necessary scripted effects, audio and cleanup. Do not auto-complete QTE/gameplay through a prerecorded substitute. |
| Loading/residency | More explicit room-level loading/fades instead of reproducing GameCube memory concurrency where it reduces working-set pressure. | Preserve required state, pointer/resource lifetimes, hot immediate-response assets, transitions, retry and correct audio/input behavior. Measure loading overlap and waits; do not silently stream out a live dependency. |
| Draw distance/detail | Shorter draw distance and more aggressive LOD. | Authorized before changing encounter logic. Keep source AI, collision, activation, progression and room semantics; assess missing visual context and transitions from accessible camera positions. |

## Qualification and selection

PS2 assets are **candidate representations and proven lower-spec visual
precedent, not automatically cheaper**. A PS2 mesh or texture can be more expensive
on Dreamcast after conversion, seams, passes, blending or lighting are counted.
Do not accept an asset based only on polygon count, archive compression or disk
size. Do not substitute visual content to bypass missing source systems.

For each bounded candidate, compare a selectable reference and candidate at
matched source states/cameras, including relevant movement and near/oblique
views. Preserve the original inputs. Record:

- Source identity/version and affected objects, materials, instances and owners;
  the exact visual changes, independent of unchanged gameplay contracts.
- Unique processed positions/normals, render corners, submitted geometry,
  materials/passes, alpha coverage/order, lighting work and CPU stages.
- Actual loaded CPU allocation, retained metadata, staging/overlap, largest free
  block, peak RAM, VRAM/AICA and executable growth. Count shared data once. A
  smaller file inside an unchanged reservation is not recovered heap.
- Whole-frame/presentation distributions and packet/PVR cost on the qualified
  workload; hardware versus emulator evidence. No FPS promise from geometry or
  file-size reduction alone.
- Images and moving-scene review at the declared target output. Sensitive alpha,
  character completeness/deformation, silhouettes, openings and readability must
  be inspected. Quantify differences where useful without claiming equivalence.
- Cold loading, source progression, cleanup/re-entry, death/retry and affected
  ownership behavior. Remove expensive backing only after remaining readers are
  adapted. Never retain complete reference and candidate representations in the
  measured residency arm and claim only the smaller one's cost.

Record keep-for-review / revise / reject and the reason. Keep candidate profiles
selectable; default promotion requires recorded quality and compatibility
acceptance. Use existing conversion, texture, storage, GPU lifetime, source model
and capture mechanisms. No second renderer, generic GX interpreter, PS2 runtime
asset backend or campaign-wide streaming framework is authorized by this brief.
Keep private source/derived assets and captures outside Git; commit reproducible
owned scripts, synthetic tests, asset-free manifests and decisions.

## Existing work to reuse, not restart

- [PLAYABLE_PATH.md](PLAYABLE_PATH.md): source menu, r100 -> r101 -> r103,
  completion/transition contracts and existing PS2 extraction toolbox.
- [REALTIME_PATH.md](REALTIME_PATH.md) and
  [R4_NATIVE_PREPARATION_CHECKPOINT.md](R4_NATIVE_PREPARATION_CHECKPOINT.md):
  integrated D349 candidate, profiling/reuse evidence and acceptance limits.
- [R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md): compact qualified
  archives, externalized textures, native formats, demand lifetimes and costs.
- [R4_R100_REFERENCE_RECOVERY_CHECKPOINT.md](R4_R100_REFERENCE_RECOVERY_CHECKPOINT.md):
  preserved historical native r100 reference; keep the newer source-facing fix.
- Existing isolated PS2 asset/prelighting, movie, water and Blender work: inspect
  their live branches/checkpoints before reuse. Do not relaunch their experiments,
  repeat inventories or assume an old candidate was accepted. The local Blender
  optimization skill remains available after residency is stable.

Detailed acceptance and the anti-reinvention rule live in the cutover goal.
Earlier future-only activation wording is superseded and remains in Git history;
no additional permission or per-subcomponent target promotion is required to
implement the authorized complete candidate.
