# A convincing RE4 Dreamcast demo

Replanned 2026-09-19 following the user's requirement for a much more convincing
demo **today, in Flycast first; physical Dreamcast next**. This is the authoritative
execution queue. The previous P0-P3 records are engineering checkpoints, not
acceptance of a presentation-ready game.

## What we are delivering

A roughly 60-second, manually playable encounter in a small, recognizable part
of r10d: textured scenery, complete textured Leon with his handgun, one complete
textured Ganado, a stable shoulder camera, visible weapon and damage animations,
gunfire/reload/impact sounds, a readable HUD, and a clear ending and retry.

The program remains native SH-4/KallistiOS code running in Flycast under normal
Dreamcast settings. The working presentation target is 320x240 at a paced 30 fps.
Use native-resolution capture for acceptance; display scaling is allowed but
does not stand in for correct assets. Physical hardware testing follows today's
Flycast presentation and is separately reported.

Today's scope is one encounter, one handgun, one enemy, one coherent location.
It must allow the presenter to move, turn, aim, miss, reload, fight, win, and
retry with a controller. A replay or video is useful backup evidence but cannot
replace that live interaction.

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
| D0 - first 30 minutes | Establish the current native image and three representative views: entry, shoulder aiming, and close enemy. Choose a small reachable r10d encounter area with a visually coherent backdrop. Check a local GameCube reference if accessible; do not let reference setup consume the pass. | Saved current images and an explicit route/camera/asset list. Known visual omissions are recorded; no claim of source-image parity without a matching reference. |
| D1 - first visual pass, review within 60-90 minutes | Decode the local room TPL, bind materials using the exported MTL, preserve UVs, and render original textures on the nearby environment. Keep intact foreground meshes within the bounded scene. Handle alpha masks for any visible cutouts. | A native Flycast image of the chosen textured area, followed by a short moving-camera capture. No random material colors, melted foreground silhouettes, incorrect UVs, or disappearing surfaces in the presentation path. If still blocked, reduce the visible material/scene subset rather than starting a general asset system. |
| D2 - second visual pass, review within 60-90 minutes | Complete Leon's head/hair/hands/handgun and the Ganado's visible parts; add original texture coordinates and bindings. Use verified source attachments and motions for aiming, firing/recoil, reload, hit reaction, and death. | Moving native footage shows recognizable complete actors, a held weapon aligned with the hands, correct cutouts, and animation matching input. Discovery of a suitable cheaper source model is useful but timeboxed; a general model-variant audit is not a dependency. |
| D3 - encounter and sound | Put both actors in the same reachable combat space. Resolve enemy wall motion, block shots at walls, align the reticle with the actual hit test, and recheck attack range/contact at the strike. Add muzzle flash, impact response, footsteps, gunshot, reload, enemy vocal/hit sound, and a restrained ambience loop. | The player can move away, aim, miss, hit, reload, take visibly explained damage, win, and retry. No through-wall hits or pursuit, invisible gunfire, frozen reload, or unexplained long-range contact damage. Audio comes from the running demo. |
| D4 - presentation and measured tuning | Add legible health/ammo, a brief control prompt, a completion/retry screen, basic actor lighting/grounding shadows, and fog only where needed to make the chosen backdrop coherent. Measure the full textured encounter. | A continuous 60-second live-input run looks and sounds coherent. Tune the measured bottleneck while protecting Leon, enemy faces, weapon, nearby architecture, collision, and aim readability. |
| D5 - final verification and handoff | Freeze the candidate, run the manual route and three win/retry cycles plus death/retry, capture synchronized video/audio, and prepare a private launch folder with instructions. Commit/push only code, tools, tests, and documentation. | Launchable native demo, verified controller mapping, clean replay/restart, exact executable/assets/config identities, footage, and a concise honest list of remaining limits. Verify remote SHA and keep all disc art and audio private. |

D1-D2 are the highest-risk work: the texture binding path and complete actor
assembly are not implemented yet. Report an early visible result or the precise
blocker at each review; do not spend today's window accumulating tests without
a native picture. Implementation may interleave actor and room work to get a
recognizable frame sooner, but neither visual gate is optional.

## Shortest asset and renderer path

The private room already contains `r10d_004.TPL` (903,008 bytes), an exported
OBJ with UVs, and `r10d_004.scenario.mtl` with 59 material entries. The MTL names
color PNGs and some separate alpha images, but those PNGs are not present in
the inspected room tree. Decode the existing TPL and verify material-to-image
and alpha mappings rather than treating MTL filenames as available textures.

Start with simple offline 16-bit color/alpha conversion and native PVR textured
batches. Use RGB565 for opaque materials and appropriate alpha formats for
cutout/blended materials; preserve UV wrapping and source sidedness. The pinned
[KallistiOS PVR API][pvr] supports these formats. VQ compression, atlasing, full
mip coverage, and a generalized texture cache are added only when measured
memory or visible sampling requires them. They are not prerequisites for the
first convincing frame.

The character format needs a versioned extension: per-corner UV/material
mapping, vertex splits at seams, texture identity, and attachment transforms
consistent with the baked pose. Keep an offline source-to-output mapping and
retain source clip timing. The runtime currently has only the primary bodies;
adding a texture file alone cannot complete the actors.

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
3. **Whole-route performance:** capture complete frame intervals and phase
   timings over the manual route and three loops. Target a paced 30 fps; report
   median, p95, p99, worst frame and count of missed 33.33 ms budgets, with the
   VBlank cadence made explicit. A strict 30 fps claim requires no recurring
   gameplay misses; a result that falls short is disclosed, not relabeled a pass.
4. **Bounded memory:** record main RAM, PVR/VRAM, and AICA allocation peaks with
   textures and audio loaded, including framebuffers, tile/parameter buffers,
   baked animation, conversion/staging copies, and safety headroom. The stock
   16/8/2 MiB pools remain constraints even when showing it in Flycast.
5. **Usable delivery:** a normal manually controlled build with autoplay off,
   isolated Flycast configuration, known controller mapping, private asset pack,
   launch instructions, and a 60-second recording from that exact candidate.
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
