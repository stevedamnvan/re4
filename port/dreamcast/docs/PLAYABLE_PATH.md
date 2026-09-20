# A source-accurate 30-second RE4 Dreamcast slice

Replanned 2026-09-19 around the shortest credible port: **the exact post-s03
`r100_Sce_look` encounter, today in Flycast first; physical Dreamcast next**.
Low frame rate is acceptable for this milestone. Source ownership and a
recognizable native image take priority over expanding scope or tuning toward a
frame-rate claim. The previous P0-P3 records are engineering checkpoints, not
acceptance of a presentation-ready game.

## What we are delivering

A roughly 30-second, manually playable excerpt beginning at the positions written
by `r100_Sce_look` after event s03: textured source scenery, Leon at
`(-82910, 860, -38480)`, the id-0x12 Ganado at
`(-79116, 860, -38890)`, and the room's source gameplay camera. The exact source
view is the visual acceptance reference. This is the opening cabin encounter,
not a reconstruction of the outdoor truck screenshot.

The program remains native SH-4/KallistiOS code running in Flycast under normal
Dreamcast settings. The presentation build uses 640x480 because image clarity is
currently more important than frame rate. Use native output for acceptance;
display scaling does not stand in for correct assets. Physical hardware testing
follows today's Flycast presentation and is separately reported.

Today's scope is one source encounter, one handgun, one enemy, and the resident
r100 room blocks that the GameCube keeps for this area. It must allow the
presenter to turn, aim, fire, reload, survive or die, and retry. A fixed-input
capture is useful visual evidence, but the presentation package remains manually
controlled.

## Source ownership ledger

| Subsystem | Current classification | Today's boundary |
|---|---|---|
| Room and material selection | Original data, converted offline | Main/shared SMD plus BLK-resident FILE_00/01/02; retain intact selected meshes and repair material IDs from ModelPart headers. Opaque source textures use RGB565. Textures carrying source alpha use ARGB4444 and the PVR translucent list with source-alpha/inverse-source-alpha blending, matching the common source `blend_mode == 0` path instead of collapsing soft masks into opaque one-bit cutouts. Source per-part alpha reference is retained as format metadata but the current selected r100 parts use alpha reference zero. |
| World scale and collision | Behavior-preserving adaptation | SMD OBJ positions receive the exporter's remaining `0.1` scale; raw SAT and game positions receive `0.001`, so both occupy metres. |
| Player/enemy placement | Original code/data | Values and yaw come directly from `r100_Sce_look`. |
| Camera and fog | Original data with Dreamcast projection adaptation | `r100_000.CAM` (`cb47bb28471becf834f6ddfef32826cc48c7cf99f20a1656929d279ef66aa6a5`) area 2 cut 2 supplies the exact normal camera, target, close point, and FOV at the encounter. The global handgun-ready table supplies the equivalent three values while aiming. `CameraQuasiFPS::calcOffset` is preserved as a linear blend across its exact up/mid/down entries, driven by the same pitch value as Leon's weapon motion. The Dreamcast runtime now ports the source center/left/right SAT wall probes and near-plane correction from `CameraQuasiFPS::hitCheck`; character and movable-object camera blockers remain fidelity debt. r100 LIT supplies fog/background values. |
| Lighting | Original data with Dreamcast shading adaptation | `r100_002.LIT` cut 0 (`a846aab52d2cd39d6d0266059e1f5728644b988be4c8c10531699409c54883a2`) supplies the scenery/enemy ambient colours and nine non-empty cabin lights. The native renderer evaluates their source type, colour, position/direction, radius, and intensity as per-vertex RGB; animated normals are rebuilt from each sampled pose. Exact GX light-list selection and source skinned normals remain fidelity debt. |
| Enemy HP and handgun body damage | Original data | Ganado starts at 500 HP; weapon 1 body damage is 150 x the starting 0.9 multiplier = 135. |
| Character geometry/motion | Original data, converted offline | Preserve complete source batches, materials, and sampled original motion; Leon now uses the handgun archive's complete aim `0x26`/`0x27`/`0x28` and fire `0x29`/`0x2A`/`0x2B` triplets, starting reload `0x2D`, and `pl00` left-hit `0x4A` and death `0x4C` motions. Baked frames remain a Dreamcast memory/runtime adaptation. Level, locomotion, reload, hit, and death clips keep every fourth authored pose; the four pitch endpoints keep every sixteenth pose to fit main RAM. Every clip includes its true terminal frame, interpolates between poses, and preserves exact source duration. The native renderer blends level and endpoint vertices with the source `cMot3` sign/rate, including gun and hit-capsule markers. FCV kind-1 root translation is retained in each clip, so the exact walk motions drive Leon at 1.7409 m/s and the r100 Ganado at 0.6087 m/s instead of prototype movement constants. |
| Player and Ganado state machines | Mixed adaptation and temporary approximation | Both actors resolve against the shared source SAT walls. Ganado walk targets now come from r100's exact 66-point RTP graph, 160 links, and 66 x 66 source next-hop table. The native `RouteCkToPos` subset preserves the direct visibility and midpoint-floor tests, the ten nearest visible route-point search, the 0.25-metre point threshold, next-hop selection, and `em10_R1_Walk` turn cap; the SAT line test is a Dreamcast collision adaptation. A handgun shot now starts at the exact source muzzle offset on Leon's animated part 10, follows that part's local -X basis for the source 50-metre line with the original `Rnd` / `fRand1_1` spread algorithm, tests the type-0 Ganado's ten exact animated `YARARE_INFO` capsules, then rejects hits behind intervening wall triangles. Vertical aim preserves `PlWepLockCtrl`'s digital 0.035 step, stick repeat ramp from 1 through 7, 0.8 positive-pitch multiplier, and -1..1 clamp; the blended fire marker drives the same shot ray as the visible gun. Because the reduced demo does not yet consume every random call made by the full game, its RNG sequence remains a documented adaptation even though the generator and boot seed are source values. The starting handgun accepts held fire again at source `PlShotFrameTbl[1][0] - 2`, frame 12, and a fresh empty trigger starts reload; reload refills at source frame 44 and stays locked through the source frame-55 pin event. The r100 type-0 Ganado now comes from `em12.drs` with its source head, gripping hands, and hatchet; acquires its normal hatchet attack at the source 1.7-metre limit; plays motion `0x80`; plays source cue `0x3d` at sequence `0x81` frame 37; evaluates the sequence hit window at source frames 50-72; checks the two exact weapon-space endpoints authored by `em10_R1_AxeAtk` as source 250-unit attack spheres; removes the source 380 life from Leon's 1200; and uses the rank-5 15-frame post-hit wait. Torso hits use the source Dm_Small front-body motion `0x26`, while a lethal standing body hit uses Die_Normal motion `0x67`. Walk and attack translation now follow the actor yaw at the selected source clips' FCV root-motion rates. Leon now uses the five source `YARARE_INFO` damage capsules attached to their exact animated parts, offsets, heights, and radii. Source waist-yaw limits, the broader Ganado decision tree, and the reduced input/state layer remain explicit port debt. |
| HUD and sound | Original data with Dreamcast presentation adaptation | `convert_core_hud.py` reads the original `core.das` frame, life, and bullet `IdData2` tables plus their cockpit texture block. The r100 runtime now draws their 640x480 hierarchy, colours, masks, life rotations, and handgun digits from 25 converted source rasters; the former hand-drawn meter is not used in this slice. The source game-over raster/transition and room ambience remain open. The GameCube archives' original DSP-ADPCM cues are converted offline: `cObjMauser::moveFire` cues 0 and 2 play together, the starting reload uses cue `0x16`, and the normal hatchet swing uses `em12` cue `0x3d`. A torso hit plays source body-impact cue `0x0c`; a surviving type-0 male villager plays damage voice `0x47` after the source two-frame delay; Die_Normal starts death voice `0x16`. Leon's surviving normal damage path uses `pl00` hurt cues 9-11, and the lethal path uses death cue 13. |

## Why the previous finish line was insufficient

At source checkpoint `a3f0b39c48817a12fc17b35344dcd7dd5929cc57`:

- The actors and scenery use flat colors. Room material records contain names
  but no texture bindings. Character packages do not contain UVs or complete
  attachments; Leon has only idle and walk clips in this path.
- Room simplification averages UVs across position/normal clusters. The 8 m
  setting is an experiment, not accepted art for a textured scene. Character
  clustering also has no visual acceptance evidence.
- The 35 m cutoff and missing near-plane clipping are unreviewed visual costs.
  An improved spawn sample does not establish an acceptable horizon or camera.
- The enemy uses direct pursuit and floor sampling without wall resolution;
  shots use a horizontal angle/range check without wall occlusion. Damage can
  therefore be inconsistent with what the audience sees.
- Existing proof is an automated state trace and VMU pass marker. Manual input,
  uninterrupted audiovisual output, and appearance have not been accepted.
- Reported frame samples span 26.8-37.8 ms, including a sample over the 33.33 ms
  budget. They are not route percentiles or proof of sustained 30 fps.

The prior goal completion records a functional prototype only. The convincing
demo remains open until the visible, interactive, and delivery gates below pass.

## Today's order and stop rules

These are bounded work passes, not a promise that every unknown will fit today.
Keep a bootable candidate after each pass. Review the actual rendered output
before expanding scope. Reserve the final 45 minutes before presentation for
testing and packaging; no new renderer features enter that window.

| Order | Work | Reviewable result / exit condition |
|---|---|---|
| D0 - complete | Extract the source-streamed r100 geometry, identify the BLK residency at the encounter, recover material bindings from the BIN ModelPart headers, and correct all coordinate scales. | Native Flycast frame shows Leon, Ganado, collision, camera, and intact textured architecture in one coherent world. |
| D1 - complete | Lock the exact normal and aiming camera, source placements, source HP/damage, fog, restart behavior, and a bounded 30-second route. Remove any invented exit marker from r100. | Manual build begins at the post-s03 state, supports aim/fire/reload/death/retry, and remains in the encounter after a kill. |
| D2 - complete in Flycast | Inspect the actual normal, aiming, firing, hit, death, and retry views. Source-cut RGB lighting, near-plane clipping, complete actor attachments, pose-derived smooth actor normals, and soft source alpha blending are now in the native path. Correct remaining material or motion faults before adding features. | Captured native frames and a 30-second moving capture are visibly coherent and use the same executable as the manual demo. |
| D3 - complete for this slice | Shared SAT wall resolution, wall-occluded shots, exact attack/damage timing, and source weapon, enemy, impact, and player cues are implemented. Room ambience remains later fidelity work. | No visible through-wall shot or movement in the permitted route; each combat action has matching visible and audible feedback. |
| D4 - complete in Flycast | Freeze and package the private Flycast candidate. Record exact executable/package hashes, controls, memory use, and observed frame rate without turning performance into today's acceptance gate. | Launchable manual demo, death/retry and kill/retry checked, private assets excluded from Git, code/tools/tests/docs pushed and remote SHA verified. |

The Flycast presentation slice has passed D2-D4. Preserve this frozen visual
baseline while moving to physical Dreamcast validation; future work must not
trade away the source camera, intact nearby geometry, actor completeness, or
combat feedback merely to improve frame rate.

The D1 loss-path check used the same manual 640x480 ELF as the presentation
candidate. Flycast recorded axe contacts at source frame 50 and health
`1200 -> 820 -> 440 -> 60 -> 0`, hurt cues 9/10/11, death cue 13, the terminal
death pose before the game-over prompt, and a manual B restart back to 1200 HP.
This is emulator evidence; physical Dreamcast loading and timing remain open.

The 2026-09-20 source-detail pass keeps the selected meshes and lighting model
intact while removing redundant Dreamcast work: the SH-4 build now uses `-O2`,
room and actor lighting is evaluated once per unique vertex per frame, room
vertices are submitted in material batches, and a conservative world-space
AABB/frustum test rejects only complete source groups outside the exact camera.
The 640x480 Flycast capture emitted 3,396 room and 6,399 actor triangles in its
measured result frame. It presented 52 distinct frames during a 29.8-second
desktop capture (1.71 fps); one representative native frame took 554,687 us,
including 446,629 us in transform/lighting/submission. The fixed 30 Hz source
simulation reported zero dropped catch-up events and the trace defeated the
500-HP Ganado. This is a large improvement over the 0.13-fps unoptimized path,
but remains intentionally low-frame-rate emulator evidence rather than physical
Dreamcast performance acceptance.

The subsequent source-HUD checkpoint corrected the private build recipe to use
the same metre-space assets as the decompiled placements and camera:
`r100-encounter-source-meters.re4room`
(`88b9de4c83187b67cb9a7e14f0aa41eea4afb4a7d1c864472c9126932f1669b0`)
and `r100-meters.re4sat`
(`ebb286360896217ce739001720eade0ebef15cc57be33f91ab65213df34438e4`).
The similarly named unscaled entry package is ten times too large for this
runtime coordinate system and produced no visible architecture. The new
`make r100` and `make r100-autoplay` targets pin the correct private inputs.
The converted HUD layout hash is
`c46d0151a5eb9ef8bd2604a79597f1fb2f2caeede8689bab5e8fc6306fd0659b`;
its texture package hash is
`5c57b9903c9e932fa89ed498e57d2844137d2e86146d98d38efb7738be52ca99`.

Flycast visibly rendered the intact cabin, source actors, handgun, and source
HUD from the native SH-4 build. One post-kill result frame emitted 7,215 room
and 6,774 actor triangles in 849,418 us, with 735,466 us spent in submission.
The fixed 30 Hz trace resets at tick 900; a later sample at tick 2,401 had again
defeated the 500-HP Ganado and reported 66 bounded catch-up overruns. This low
frame rate is accepted for the 30-second fidelity milestone and remains a later
optimization target rather than a claim of final Dreamcast performance.

The frozen Flycast presentation candidate is the normal-controller ELF
`re4dc-r100-source-hud-manual-v3.elf`, SHA-256
`b70858d412876496f740a8bea3e5cf2752203210d952d97d04d77a268db13c36`.
Its private launch package is
`C:\Flycast-Evidence\re4-dreamcast\d110-exact-r100-manual-v3`. The exact ELF's
30-second 640x480 capture includes loopback audio and has SHA-256
`c8dc6a0825f71b0a21b8b6a783d809987542e01d7ae47805a920ebdb4a6a65ad`.
The repeatable capture was driven through Flycast's normal Xbox-controller path;
the game-side autoplay flag was absent, and the packaged build remains directly
playable with a controller.

Telemetry version 3 records stock-pool headroom after all textures and source
combat cues load. The frozen candidate retained 1,892,352 bytes between the
main heap break and reserved kernel stack, with another 205,368 free bytes
inside the heap arena; PVR VRAM retained 1,488,296 bytes and AICA RAM retained
1,378,336 bytes. A 39-second controller-path trace, SHA-256
`1087a8603c97328cfdc2b41e865c4ac372cd4c80190f586cd8a030a5146eeaed`,
recorded the exact state sequence: kill, magazine `6 -> 0`, reload `0 -> 6`,
restart, source damage `1200 -> 820 -> 440 -> 60 -> 0`, and restart to 1200.
Representative complete frames remained 0.78-0.84 seconds; this is disclosed
low-rate Flycast evidence, not a physical-console timing result.

## Shortest asset and renderer path

The source r100 runtime streams five DAT archives. At the post-s03 encounter,
the BLK table keeps blocks 0, 1, and 2 resident alongside the shared room data.
The official SMD exporter preserves geometry and UVs but labels some streamed
Type08 parts `UNKNOWN_MATERIAL`; `prepare_streamed_room_obj.py` restores their
exact diffuse/alpha texture IDs from the original BIN ModelPart headers before
the normal room conversion.

Start with simple offline 16-bit color/alpha conversion and native PVR textured
batches. Use RGB565 for opaque materials and appropriate alpha formats for
cutout/blended materials; preserve UV wrapping and source sidedness. The pinned
[KallistiOS PVR API][pvr] supports these formats. VQ compression, atlasing, full
mip coverage, and a generalized texture cache are added only when measured
memory or visible sampling requires them. They are not prerequisites for the
first convincing frame.

The character package now carries per-corner UV/material mapping and complete
source batches, with original motion evaluated offline into bounded animated
frames. Keep the source part map and timing manifest beside each private build.
Any missing handgun, hand, hair, or face element is a converter defect, not an
acceptable model simplification.

Use the unsimplified source meshes as the visual reference. For today's small
area, retain foreground geometry and omit only objects outside every permitted
view, with coherent scene boundaries. Where simplification is necessary,
preserve UV islands, silhouettes, hard edges, materials, and animated joints.
Do not promote the 8 m cluster or the current actor cluster merely because it
was faster. Source LOD variants may save work, but their presence/compatibility
in this debug disc must be verified. Capcom's [developer postmortem][postmortem]
describes prioritizing nearby model quality and using multiple geometry and
texture tiers; this informs the approach, not a claim about our selected files.

Fix near-plane clipping and camera obstruction in the encounter view. Record
camera/FOV and visibility settings. Fog may hide an intentionally bounded
backdrop when the transition looks natural; an abrupt cutoff or a zoomed-in
camera chosen only to conceal missing work does not pass visual review.

Profile transforms, shading, submission, and PVR wait separately. Cached static
lighting, shared transforms, and object rejection are candidates when measured.
Stripification, a general portal/PVS builder, renderer replacement, and global
fast-math changes are not today's default work. No speedup is assumed before
the same scene is measured again.

## Presentation acceptance

All of these are required before calling the demo convincing:

1. **Recognizable appearance:** complete textured Leon and Ganado, a visible
   handgun, original scene materials, readable faces/silhouettes, and correct
   visible cutouts. Judge the actual native image and moving footage.
2. **Coherent interaction:** matching aiming/fire/reload/contact feedback,
   player/enemy wall behavior and shot occlusion, stable camera, reachable end
   condition, clear HUD, sound, and manual retry. A state counter alone cannot
   establish any of these visible properties.
3. **Measured performance:** capture complete frame intervals and phase timings
   over the 30-second route. Report observed rate and overruns. Frame rate is not
   an acceptance gate for this milestone, but the fixed simulation step and
   dropped-catch-up count must keep slow rendering visible rather than silently
   changing gameplay behavior.
4. **Bounded memory:** record main RAM, PVR/VRAM, and AICA allocation peaks with
   textures and audio loaded, including framebuffers, tile/parameter buffers,
   baked animation, conversion/staging copies, and safety headroom. The stock
   16/8/2 MiB pools remain constraints even when showing it in Flycast.
5. **Usable delivery:** a normal manually controlled build with autoplay off,
   isolated Flycast configuration, known controller mapping, private asset pack,
   launch instructions, and a 30-second recording from that exact candidate.
   Backup footage is labeled as footage. Physical Dreamcast is a later gate.

Use the Soulcalibur evidence discipline already documented in
[SOULCALIBUR_REUSE.md](SOULCALIBUR_REUSE.md): retain a known-good visual baseline,
protect HUD composition, compare exact asset/build identities, and inspect
motion. Keep its dirty checkout read-only. RTX Remix and AI-generated appearance
are not part of the native Dreamcast presentation path.

## If time runs short today

Reduce the walkable area and encounter duration first: 30-45 seconds in one
finished combat space is preferable for this brief to a longer unfinished tour.
Remove extra props/effects before degrading the main actors, textures, sound,
weapon interaction, or camera. One enemy remains sufficient.

If textured scenery and complete actors cannot be integrated and visibly
verified, explicitly report the result as an intermediate prototype. Do not
substitute emulator-enhanced graphics, an offline render, or autoplay telemetry
for the requested native playable demonstration. Do not describe the deadline
as met before a reviewable candidate exists.

After today's showing: physical Dreamcast loading route and controller test,
hardware timing/memory/audio checks, better source-aligned LODs, broader views,
and then more gameplay. Campaign systems, movies, full inventory/save systems,
additional rooms, extra enemies, and a complete graphics compatibility layer
stay outside today's scope.

[pvr]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/include/dc/pvr.h
[postmortem]: https://www.gamedeveloper.com/design/postmortem-i-resident-evil-4-i-
