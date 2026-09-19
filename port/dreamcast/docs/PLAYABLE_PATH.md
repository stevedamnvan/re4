# Fastest path to a playable Dreamcast translation

Reassessed 2026-09-19 against the source renderer and current native targets.
This is the execution backlog for the next slice. It supersedes the earlier
decision to replace r10d scenery with a collision proxy after the orbit-view
benchmark. The broader engineering plan remains the campaign roadmap.
See [the hardware/source findings](HARDWARE_TRANSLATION.md) for the researched
hardware constraints and distinction between real-time scenes and SFD movies.

## Decision

Keep the native KallistiOS target, offline asset conversion, r10d, and the
already exercised RE4 motion code. Build one integrated, controllable room
next. SAT supplies collision; a visible SAT proxy is an optional temporary
development view, not the selected final scenery. Preserve the room artwork
until representative gameplay measurements identify what actually needs LOD.

Do not wait for a complete renderer, exact camera port, all original modules,
or general platform compatibility before connecting movement and collision.
Use a source-informed shoulder follow camera initially and record deviations.
An approximate camera can establish traversal, but cannot establish matched
GameCube visibility or image parity.

## What changed in the assessment

- `src/game/scroll.cpp::setObj` creates separate scenery objects.
  `trans.cpp::ModelTrans` passes object spheres to the ordering table;
  `trans_ot.cpp::AddOtWorldPosRadius` and `AddOtModelPosRadius` reject spheres
  outside the camera frustum. `commonModelTrans` submits accepted models via
  GX display lists. Some flags and ordering modes bypass ordinary rejection.
  This establishes culling support, not the number drawn in a specific r10d
  frame, and does not establish general occlusion culling behind walls.
- The current viewer uses an arbitrary orbit camera and material batches in
  centroid-assigned X/Z cells. It transformed 73,340 of 75,009 vertices (97.8%)
  in the recorded frame. That workload does not establish the gameplay view.
- Its `render_us=171688` covers `render_room`, including `pvr_wait_ready`.
  It is an emulator render-call measurement, not isolated SH-4 transform time,
  GPU time, or a complete gameplay frame. Keep the failure for that viewer;
  withdraw the inference that original room art must therefore be replaced.
- The original Leon body is now decoded, skinned offline with the verified
  source evaluator, and rendered in the collision-controlled room with the
  source-mapped starting-handgun idle and walk clips. Combat remains unbuilt.
- The existing converter already preserves exported OBJ groups when invoked
  with `--cell-size 0`. A private comparison package was generated: 226 groups,
  311 batches, 3,197,028 bytes, with the same 63,745 triangles and 75,009 vertices.
  The old cell package has 389 groups and 1,147 batches. This comparison
  package has not been rendered or timed. Exported groups still need mapping
  to source SMD objects; they are not automatically the original culling spheres.

## Ordered implementation backlog

| Order | Deliverable | Done when |
|---|---|---|
| P0 - walkable room | **Runtime integrated.** Maple analog/D-pad movement, a shoulder follow camera, SAT floor/wall collision, spawn, A reset, START exit, and a visible route marker now run in one native executable with an orange placeholder actor. The source-group comparison is complete and timing phases are instrumented. The remaining bounded work is near-plane clipping and a clean three-loop record. | A recorded controller route moves, turns, stops at walls, follows the intended floor, reaches the exit, and resets three times without drift or growing allocations. This is the walkable checkpoint, not accepted RE4 gameplay. |
| P1 - visible Leon | **Runtime integrated.** The converter decodes the 1,484-vertex primary body and 2,519 source triangles, evaluates the source-mapped 91-frame idle and 29-frame walk clips, applies the original weighted skinning rules offline, and emits a 1.1 MB private package. The room runtime places and rotates the animated body on SAT collision and switches clips from controller movement. | An isolated Flycast route shows the disc-derived animated body positioned on the floor while idle and moving. This closes the visible-body bridge; face/hair/hands/weapon attachments, textures, combined performance, and physical hardware remain P2/P3 work rather than being implied by this checkpoint. |
| P2 - small combat loop | Link only the source player/handgun/Ganado behavior required for aim, fire, reload/ammo, hit reaction, enemy approach/attack, player damage/death, enemy death, and restart. Hard-code one encounter and exit; add only the scheduler dependencies exercised by these paths. | A controller can aim, defeat one attacking Ganado, take damage, die/restart, and complete the route. Source behavior deviations are recorded; a generic substitute AI is not accepted as translated RE4 behavior. |
| P3 - playable validation | Add the basic textures/cutouts needed for scene readability, measure the combined runtime, trim only measured visual costs, and package it for a named stock Dreamcast loading route. | Repeatable walk/combat/reset runs at the 320x240, 30 fps target within all stock memory pools. Flycast and physical Dreamcast results are reported separately; physical acceptance remains open until run. |

P0 includes one bounded renderer correction/comparison pass below. Then move
to P1/P2 rather than iterating a standalone scenery viewer indefinitely.
Flat shading and temporary placeholders are allowed at intermediate checkpoints;
P3 requires the real animated actor and the declared room presentation.

## Renderer work allowed on this critical path

1. Establish coordinates and scale between the OBJ, SAT, character positions,
   and source camera data. Record a spawn and short traversal route with camera
   position, target, FOV/aspect, and clipping distances. A smaller field of view
   or arbitrary far cutoff is not an acceptable way to hide a performance miss.
2. Compare the preserved exported groups with the existing cell package at the
   same camera positions, using conservative bounds. Preserve source object
   IDs/flags where available. Use the existing converter before writing another
   archive/scene system; retaining all geometry need not mean drawing it all.
3. Correct frustum rejection and near-plane clipping for a close camera. The
   current viewer drops a whole triangle if any projected vertex is behind the
   camera. Crossing triangles must be clipped; bounds crossing the near plane
   must not cause visible objects to disappear.
4. Separate PVR wait, bounds tests, transforms/skinning, submission, and complete
   frame intervals. Record route percentiles plus visible groups, transformed
   vertices, submitted vertices/triangles, and RAM/VRAM peaks. Include room,
   Leon, and then the enemy in combined measurements; package size is not total
   resident memory and `render_us` is not CPU-only time.
5. If the representative view is too expensive, optimize the measured cost:
   fewer material changes/strips for submission, reduced visible mesh detail
   for geometry/skin cost, or smaller textures for residency. Keep the source
   geometry and an explicit per-asset LOD mapping. A full stripifier, portal/PVS
   system, or exact copy of the GX renderer is not a prerequisite for P0.

The source only proves the culling algorithm exists. A bounded Dolphin run of
the verified GameCube build can supply camera and draw-list reference evidence;
a physical GameCube is not a prerequisite for that comparison. Stock Dreamcast
is required for final performance, controller, storage, and memory acceptance.
Continue useful Flycast development while hardware validation is pending.

## Work deferred until the slice requires it

Campaign-wide conversion; Disc 2 completion; a native YZ2 decoder; a GX emulator;
general room streaming; full OS/REL compatibility; inventory UI; VMU saves;
movies; complete audio; elaborate lighting/shadows; and additional rooms.
Bring back only a dependency that demonstrably blocks an accepted slice path.
No enemy-count or AI-cadence reduction is hidden inside a renderer optimization.

Reuse Soulcalibur's Flycast runner, short reproducible captures, resource
identities, and separation of fixture/emulator/hardware claims. RTX Remix,
neural rendering, and material generation do not accelerate the native gameplay
milestone and are outside this backlog.

## Next concrete work item

Begin P2 with the smallest complete interaction contract: aim state and reticle,
six-round ammo, fire/hit test, timed reload, one approaching damage source,
player/enemy health and death, then restart and exit. Map each state to the
existing source routines and constants before replacing temporary presentation
with the matching Leon, handgun, and Ganado clips.

Before converting the P2 Ganado, inspect existing model variants and source
selection logic for a compatible cheaper mesh. Preserve necessary
material/vertex-colour data, and keep the P0 near-plane/clean-loop work bounded
to failures that appear on the combat route.

Only tools, source changes, tests, and documentation are committed and pushed
to `origin/dreamcast-port`. The disc, converted art, and captures stay private.
