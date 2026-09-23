# PS2-inspired Dreamcast visual profile

Authorized by the user, 2026-09-22. **The bounded r100 static-render replacement
is now active by explicit user correction after D362.** Finish the measured UV
candidate, then replace qualified source-owned static normals/lighting using the
existing baking/conversion machinery and compare to D361~1.368s. Do not require
another lossless optimization campaign or further cache tuning first. Actors
remain dynamic; source ownership/gameplay and explicit dynamic/camera-light
handling remain mandatory. This scoped activation supersedes earlier "do not
start prelighting" text below for this candidate only. The remaining catalogue
and hardware/gameplay acceptance gates are unchanged.
This extends the existing playable/performance/residency backlogs. It does not
replace the current renderer integration or the menu-plus-three-room objective.

## Authority and current priority

The preferred hierarchy is:

1. **GameCube source = behavioral/fidelity authority.** Gameplay, AI, collision,
   camera, animation decisions, events, inventory/progression, required objects
   and room semantics remain source-controlled.
2. **PS2 = lower-spec compromise reference / optional visual source.** Its assets
   and presentation provide candidates, not a replacement gameplay engine or
   proof of lower Dreamcast cost.
3. **Dreamcast-native asset = final optimized representation.** Offline conversion
   and the existing native backend determine target layout and execution.

After the historical optimized r100 renderer's prepare-once/reuse-many
architecture is correctly integrated and the remaining Dreamcast hardware cost
is measured, the project is explicitly authorized to adopt a PS2-inspired /
Dreamcast-specific visual profile to reach the performance target. Visual
representation may change substantially. This is broader authorization than
requiring every candidate to be visually equivalent to GameCube rendering.

**Current priority remains the complete historical optimized renderer integration
and elimination of accidental repeated CPU work.** Keep the full default-off
D349 stack as the acceptance unit. Preserve source pose, current selected lights,
normal matrices, material/channel state, camera and ownership while completing
shared preparation. Do not start fixed lighting, prelighting, asset replacement,
water or effects work merely because this brief exists.

## Explicit activation gate

**Do not begin PS2-derived asset/effect substitution merely to hide an unresolved
renderer integration bug. Activate this phase after repeated-work/lifetime issues
are substantially eliminated and the residual CPU/RAM/PVR costs are measured.**

Before activation, the checkpoint must identify:

- The integrated renderer baseline, executable, source overlay, assets,
  configuration, fixture and evidence. Preserve the accepted Dreamcast reference
  and original GameCube behavior as separate authorities.
- Preparation reuse coverage and remaining justified work: references versus
  unique position/normal/lit inputs; selected-light preparation; part/pass reuse;
  batch capacity/retirements; packet packing, flushes and fallback counts.
- Remaining renderer correctness or lifetime defects and why they are not being
  concealed by a lower-detail candidate. Account for queues, warm-up uploads,
  allocation failures, dropped/discarded frames and source-state/tick matching.
- Residual CPU stages, actual presentation intervals, PVR work, source and native
  RAM, VRAM/AICA and loading/transition peaks. Do not add overlapping CPU/GPU spans
  or treat file size as resident cost. Keep profiler overhead explicit.
- What ran in Flycast and what ran on stock Dreamcast hardware. Emulator timing
  is not physical-hardware acceptance. If hardware is unavailable, record that
  gate as open; continue the current integration and other already-authorized
  work without claiming the hardware measurement was completed.

No arbitrary date, historical FPS number or completion of the entire campaign
opens the gate. Record its evidence and decision in the existing checkpoint and
handoff before starting this phase. Earlier isolated candidate evidence remains
available; its existence is neither automatic activation nor default promotion.

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

This authorization is durable project direction. Future resumptions must retain
both the activation gate and the three-level authority hierarchy; do not reduce
it to either "GameCube visuals must remain identical" or "use PS2 to hide bugs."
