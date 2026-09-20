# Resident Evil 4 Dreamcast port

This directory contains the native SH-4/KallistiOS target. The GameCube build is
the behavioral and authored-presentation authority; Dreamcast-native data,
precomputation, visibility, math, texture, and PVR paths determine how that work
runs on the target.

**Current objective (2026-09-20): sustain a responsive 30 fps at 640x480 for the
accepted r100 cabin encounter without reducing its room, lighting, complete
characters, camera/FOV, transparency, source-timed gameplay, or audio.** The
[real-time plan](docs/REALTIME_PATH.md) is scheduled from measured bottlenecks.
Historical R0-R3 labels are checkpoint records rather than the task order.

## Current status

The corrected-character presentation at commit `dba07e2` remains the audiovisual
reference. Its 32-second Flycast video with game audio is retained at
`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2`.
Leon uses the source body, costume, head, hair, eyes, Red9 hands and handgun;
the Ganado uses the correct right-handed hand/hatchet assembly. Room, source
camera, selected lighting, HUD, transparency, collision, and combat remain intact.

R3p is now the Dreamcast regression and performance baseline. It fixes a real
actor-lighting defect: the old runtime overwrote transformed source normals with
lighting output while later work items could still reference those normals.
The corrected path keeps immutable normal scratch separate from per-work-item
lighting. The converted packages prove the traversal was unsafe: Leon has only
5 identity entries in 6,413 lighting work items and Ganado has only 5 in 1,900.

Against R3o over matched ticks 165-1194, R3p reduces CPU frame
p50/p95/p99 from 87.615/90.116/90.209 ms to 86.217/88.719/88.836 ms.
TA registration p50 falls from 58.731 to 58.096 ms and actor-lighting p50
falls from 18.959 to 18.198 ms. It preserves the same medians of 327 visible
room groups, 9,155 room triangles, 11,900 actor triangles, 617 PVR calls, and
1,071,840 submitted bytes. Presented cadence remains roughly 11-12 fps, far
from the 30 fps acceptance target.

The separate normal buffers cost exactly 98,304 bytes: measured post-load
main-RAM headroom falls from 5,668,864 to 5,570,560 bytes. Both matched traces
report zero simulation overruns and zero discarded simulation time. A clean
manual smoke sampled input 1,860 times with a 12.484 ms maximum gap and no queue
drops, but did not inject combat controls and is not full manual acceptance.

A corrected dual-path build established that a KallistiOS `frsqrt` candidate
changed at most one channel value in one packed actor color over 330 captured
frames. It was rejected because it made actor-lighting p50 0.822 ms slower than
the portable square-root path. The fast path and validation build options do
not remain in production source.

The final framebuffer check is in
`C:\Flycast-Evidence\re4-dreamcast\d221-actor-normal-alias-fix-visual`.
It retains the accepted room, complete Leon and Ganado assemblies, HUD, camera,
transparency, and coherent lighting. Full-framebuffer emulation was enabled only
for that image extraction; performance results use the pinned normal Flycast
configuration. Physical Dreamcast timing and human-controller acceptance remain
pending.

Exact active identities:

- source `9dcd989370be7f083a9b66cfd19907fda627c893`
- KallistiOS `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`
- kos-ports `f4faacc42faaf552625777b7709e871a827e1055`
- `sh-elf-g++ 15.2.0`
- Flycast SHA-256 `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`
- corrected visual ELF `c5ae9de436fd7b9f3770ce3e7cc40d1f37b8e2c000b3b9dfb9be5d46ce7c0e68`
- R3o autoplay ELF `191676ca573aaaec9aed99bb33c88fca3102b1d90344a8e7c4020455bf1dfbdc`
- R3o manual ELF `13857924539cec27012e1d6cdd46c9ec44ee17a5db942281b2f3caedaa3267ea`
- R3p autoplay ELF `4fd89b4e929aca49a9cdc8b7e231c9a1e33ff387cac81466d42e0d49b686a44f`
- R3p manual ELF `b265872f40b74f8fbe3cd5e7be28e4bcb73e8af2e54717d8cc5076f9ef91dd0a`

R3q profiled that room path without changing any accepted code. With
`SUBMIT_PROFILE` unset the room build is byte-identical to R3p once DWARF line
tables are stripped; only the unstripped hashes above moved. Real store-queue
transport is 1.331 ms for the room and 2.580 ms in total, so submission
transport and KOS DMA are closed. The 2,048-entry room vertex cache misses
15,350 times against a floor of 15,317 distinct vertex indices, so enlarging it
is closed too. Room cost is close to 3.1 us per transformed and lit vertex, and
the blended list spends 18.917 ms on 1,718 triangles because it transforms 3.63
vertices per triangle against 1.23 for the opaque list. Every blended batch
already carries certified strips; the cost comes from R3k leaving the alpha
materials unpartitioned, so blended geometry sits in 17 groups reaching 273.83 m
against a 35 m horizon and is transformed before the depth and clip tests
discard it. Order-safe per-strip bounds culling is the next experiment and the
largest identified saving; see
[the R3q submission profile checkpoint](docs/R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md).
The next actor experiment should still target the stable selected-light work,
especially Leon's 13.960 ms median, while retaining the portable evaluator as a
reference. Do not retry the rejected reciprocal-square-root path without new
evidence.

Rebuild the diagnostic with:

```sh
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room r100-autoplay-profile
```
The Linux checkout is required because upstream contains distinct `src/Tools`
and `src/tools` paths. A normal Windows checkout collapses three filename pairs.
The incomplete Windows checkout created during bootstrap was retained as
`C:\Game Dev\Emulators\re4-dreamcast-WINDOWS-INCOMPLETE` and is not a build
source.

## First runnable checks

From the repository root:

```sh
make -C port/dreamcast -f Makefile.host test
```

This builds a small host ABI probe, runs the port-blocker inventory against the
current tree, and executes the tool tests. It does not claim Dreamcast runtime
compatibility.

The generated inventory is written to
`port/dreamcast/build/host/portability-audit.json`. It is the starting worklist
for separating portable game code from Nintendo SDK, GX, PowerPC assembly,
fixed-address, and REL-module dependencies.

`tools/evidence_manifest.py` creates and validates hashed capture manifests.
Every reference/candidate comparison must include the relevant room, simulation
tick, RNG/input identity, executable, and asset-package identity rather than
relying on matching filenames.

The synthetic motion artifact is
`build/motion-sh4/re4dc-motion-smoke.elf`. It compiles prepared functions from
upstream `motion.cpp` and `ik.cpp`, the selected original model/math functions,
the SDK's portable matrix/vector routines, and the game's fdlibm. A shared
fixture runs `HermiteInterpolation` and `ikCalc` on both x86-64 and SH-4. The
host and Flycast results agree to the displayed six decimal places, and the
Dreamcast target reports `PASS` beyond frame 300. See
[the motion SH-4 baseline](docs/MOTION_SH4_BASELINE.md) for exact results and
limits.

With a verified Disc 1 image at `orig/G4BE08/re4_debug_disc1.iso`, run:

```sh
make -C port/dreamcast -f Makefile.host motion-real-host
source port/dreamcast/kos-env.sh
make -C port/dreamcast/motion real
```

The first command privately generates an ignored fixture from `pl00.drs`
model entry 0 and motion entry 117, then evaluates four frames through the
original game motion code on the host. The second build produces
`port/dreamcast/build/motion-sh4/re4dc-real-motion.elf`. No disc-derived bytes
are tracked by Git. See
[the real-motion SH-4 baseline](docs/REAL_MOTION_SH4_BASELINE.md).

Prepare the private `r10d`, Leon, and Ganado packages, then build the native
room demo:

```sh
make -C port/dreamcast -f Makefile.host demo-r10d
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room
```

The executable validates the room, collision, and character packages, culls
room groups, submits textured PVR geometry, and supports analog-stick or D-pad
tank movement, SAT floor/wall collision, a shoulder follow camera,
source-derived actor animation, source-cut RGB lighting for r100, and the combat
loop. The r100 path evaluates the non-empty cabin lights from
`r100_002.LIT` cut 0, including its separate scenery/enemy ambient colours and
view-relative parallel lights. Character package v6 retains source positions,
authored normals, UV draw corners, and weight-palette identities; the runtime
interpolates each pose palette once and reuses it for position and normal work.
Source textures with alpha are preserved as
ARGB4444 and drawn through the PVR translucent list using the source default
alpha blend, so the cabin's soft shadow and cutout masks do not become opaque
black geometry. The r100 camera uses the room CAM file's area-2 camera, target,
close point, and FOV plus the original three-ray SAT wall correction; aiming
uses the matching global handgun-ready offsets. The character converter also retains the FCV
kind-1 root-motion rate used by the original `MotionMove`, so the selected Leon
and Ganado walk clips drive world movement at their authored speeds. Controls are
stick/D-pad move and turn, right trigger or Y aim, stick/D-pad vertical while
aiming, A fire, X reload, B restart, and START exit. Defeat the Ganado before
the route marker unlocks.

For the r100 build, convert the private room route graph and pass it to the
native build:

```sh
make -C port/dreamcast -f Makefile.host route-r100
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room DEMO_SCENE=r100 \
  ROUTE_PACKAGE=../build/private/r100.re4rtp
```

The `r100` presentation build defaults to native 640x480 Dreamcast VGA output;
the older `r10d` engineering fixture remains 320x240. Pass
`DEMO_RESOLUTION=240p` or `DEMO_RESOLUTION=480p` to override either profile.

The converted package preserves all 66 source waypoints, 160 links, and the
complete next-hop table. The native enemy walk path follows the decompiled
`RouteCkToPos` selection rules over those data while reusing the port's SAT
line and floor queries.

The generated packages stay ignored. The first broad orbit proof and the
unoptimized gameplay view miss the frame budget. Full source meshes are the
default acceptance build; coarse clustering remains an explicit experiment.
The runtime uses a declared 35 m horizon for this bounded route, not as a
claim about the GameCube draw distance. See
[the room SH-4 baseline](docs/ROOM_SH4_BASELINE.md).
The integrated movement/collision evidence and its remaining P0 limits are in
[the walkable r10d checkpoint](docs/WALKABLE_R10D_BASELINE.md).
The source mappings, deliberate behavior bounds, controls, and full-loop
Flycast evidence are in [the Ganado P2 checkpoint](docs/GANADO_P2_BASELINE.md).
The measured LOD experiment, complete-loop replay, and remaining hardware and
presentation limits are in [the P3 prototype checkpoint](docs/P3_PLAYABLE_BASELINE.md).
The current measured optimization results are in
[the r100 R1a performance checkpoint](docs/R1A_PERFORMANCE_CHECKPOINT.md) and
[the R1b source-selection checkpoint](docs/R1B_SOURCE_SELECTION_CHECKPOINT.md).
The source collision broad-phase recovery is measured in
[the R2a SAT hierarchy checkpoint](docs/R2A_SAT_HIERARCHY_CHECKPOINT.md). The
source-selected fixed room-light contribution is prepared once and measured in
[the R1c static room-lighting checkpoint](docs/R1C_STATIC_ROOM_LIGHTING_CHECKPOINT.md).
Character package version 4 now separates sampled source positions, authored
normal identities, and UV draw corners; its fidelity, memory, and Flycast timing
results are recorded in
[the R2b source attribute-identity checkpoint](docs/R2B_SOURCE_ATTRIBUTE_IDENTITIES_CHECKPOINT.md).
The opaque room path now consumes offline winding-preserving strips while
retaining the original triangle stream for transparency and clipping fallback;
its representation, matched image check, and 23.8 ms render reduction are in
[the R3b native room-strip checkpoint](docs/R3B_NATIVE_ROOM_STRIPS_CHECKPOINT.md).
Order-certified translucent batches now use the same native path without
changing source blend order; the additional 2.3 ms reduction is recorded in
[the R3c ordered alpha-strip checkpoint](docs/R3C_ORDERED_ALPHA_STRIPS_CHECKPOINT.md).
The room-lighting path now validates its authored unit normals once and avoids
renormalizing them per frame; the packed-color proof and bounded result are in
[the R3d room-normal checkpoint](docs/R3D_VALIDATED_ROOM_NORMALS_CHECKPOINT.md).
The two source-selected camera-relative room lights now bypass the general
nine-light evaluator with an exact packed-color fallback gate; the 22.7 ms
matched reduction is recorded in
[the R3e compact room-light checkpoint](docs/R3E_COMPACT_DYNAMIC_ROOM_LIGHTS_CHECKPOINT.md).
Actor light masks are now converted to the source-ordered, eight-entry model
light list once per frame; the exact packed-color proof and 4.5 ms matched
frame reduction are recorded in
[the R3f compact actor-light checkpoint](docs/R3F_COMPACT_ACTOR_LIGHTS_CHECKPOINT.md).
Actor colors are now packed once per normal and reused by native strips while
the float clipping fallback remains intact; the 2.6 ms matched frame reduction
and 48 KiB memory cost are recorded in
[the R3g packed actor-color checkpoint](docs/R3G_PACKED_ACTOR_COLORS_CHECKPOINT.md).
Character package v5 now preserves source BIN normals and their reusable weight
palettes instead of rebuilding normals from deformed triangles. Its bounded
direction error, 2.7 ms normal-stage reduction, and temporary RAM cost are in
[the R3h source normal-palette checkpoint](docs/R3H_SOURCE_NORMAL_PALETTES_CHECKPOINT.md).
The R3p runtime now keeps transformed source normals separate from lighting
output; its correctness proof, 98,304-byte scratch cost, measured speedup, and
rejected `frsqrt` subexperiment are recorded in
[the R3p actor-normal alias-fix checkpoint](docs/R3P_ACTOR_NORMAL_ALIAS_FIX_CHECKPOINT.md).
Character package v6 now removes the redundant baked mesh poses and reuses one
prepared source palette for both positions and normals. Its 5.34 MiB live-RAM
gain and matched performance result are in
[the R3i source position-palette checkpoint](docs/R3I_SOURCE_POSITION_PALETTES_CHECKPOINT.md).
The recovered memory also permits a measured 2,048-entry room vertex cache;
larger candidates were rejected after reaching the same reuse ceiling in
[the R3j cache-bound checkpoint](docs/R3J_ROOM_VERTEX_CACHE_BOUND_CHECKPOINT.md).
The r100 production room now uses conservative one-metre opaque child cells
while retaining source-order alpha batches and every source triangle. The
20.6% matched frame reduction and the rejected finer split are recorded in
[the R3k source-child cell checkpoint](docs/R3K_SOURCE_CHILD_CELL_CHECKPOINT.md).
The source handgun character assembly now uses the weapon-specific Leon hands,
the source-neutral hidden expression overlay, the right-handed Ganado hand pair,
and source-facing actor culling. The defect evidence and remaining character-system
boundary are recorded in
[the R3l source character-assembly checkpoint](docs/R3L_SOURCE_CHARACTER_ASSEMBLY_CHECKPOINT.md).
The room renderer now maps the source SMX `alpha_omit = 0x80` rule to Dreamcast
punch-through only for a verified binary-alpha material. This preserves all
soft-alpha materials while reducing the matched complete-frame interval by 8.1%
in [the R3m source punch-through checkpoint](docs/R3M_SOURCE_PUNCHTHROUGH_CHECKPOINT.md).
Room visibility, source cull state, and source-selected room lights are now
computed once per render snapshot and reused by all material passes. The matched
4.9% frame reduction and PVR call/byte telemetry are recorded in
[the R3n visibility-reuse checkpoint](docs/R3N_VISIBILITY_REUSE_CHECKPOINT.md).
Polygon headers and their first payload now share one immediate PVR submission;
the repeated small result and unchanged command-byte evidence are recorded in
[the R3o header/payload batching checkpoint](docs/R3O_HEADER_PAYLOAD_BATCHING_CHECKPOINT.md).
The manual controller is now sampled independently of long render frames in
[the R0 input-service checkpoint](docs/R0_INPUT_SERVICE_CHECKPOINT.md).

The source audio targets privately extract `wep02.drs`, `em12.drs`, and
`pl00.drs` from
Disc 1 and decode their GameCube DSP-ADPCM cues. The handgun fire event plays
cues 0 and 2 together exactly as `cObjMauser::moveFire` requests; the starting
reload uses cue `0x16`; the r100 hatchet swing plays cue `0x3d` on source
sequence frame 37; and Leon's normal damage path selects hurt cues 9-11 before
death cue 13. No DRS, encoded sample, or decoded WAV is tracked by Git:

```sh
make -C port/dreamcast -f Makefile.host \
  source-weapon-audio source-enemy-audio source-player-audio
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room \
  FIRE_SOUND_0=../build/private/source-audio/wep02-cue00.wav \
  FIRE_SOUND_2=../build/private/source-audio/wep02-cue02.wav \
  RELOAD_SOUND=../build/private/source-audio/wep02-cue16.wav \
  ENEMY_SWING_SOUND=../build/private/source-enemy-audio/em12-cue3d.wav \
  PLAYER_DAMAGE_VOICE_9=../build/private/source-player-audio/pl00-cue09.wav \
  PLAYER_DAMAGE_VOICE_10=../build/private/source-player-audio/pl00-cue10.wav \
  PLAYER_DAMAGE_VOICE_11=../build/private/source-player-audio/pl00-cue11.wav \
  PLAYER_DEATH_VOICE_13=../build/private/source-player-audio/pl00-cue13.wav
```

## Near-term sequence

1. Reuse one conservative visibility/draw-state list across all room passes and
   add separate visibility, packet, byte, TA-registration, render, and present
   measurements.
2. Attack the next largest measured room/actor cost with an explicit cache or
   SH-4 kernel dependency contract; retain and compare the reference path.
3. Benchmark packet aggregation and KOS DMA only after exact list byte/call
   counts exist. Immediate submission already uses store queues.
4. Add offline native texture layout and shared upload handles, then evaluate
   VQ/palette/mipmap candidates per texture with previews and moving-scene
   quality acceptance.
5. Expand the repeatable route to movement, aim extremes, enemy contact, death,
   and retry; complete human-controller and physical Dreamcast acceptance.

Source collision, camera, state/event, expression, and cloth parity continue as
bounded encounter fixes, but they do not block independently verifiable target
optimizations.
The authoritative real-time task order and acceptance criteria are in
[the real-time path](docs/REALTIME_PATH.md). The presentation history and
ownership ledger remain in [the playable backlog](docs/PLAYABLE_PATH.md). The
[hardware/source assessment](docs/HARDWARE_TRANSLATION.md) documents the
GameCube differences, real-time scenes, SFD movies, and render-to-texture work.
See also [the r10d asset boundary](docs/R10D_VERTICAL_SLICE.md).

General room streaming, full menu systems, complete audio coverage, story
events, and campaign progression stay behind that demo gate. Minimal start,
completion/retry presentation and core gameplay sound are required today.

See [Soulcalibur reuse](docs/SOULCALIBUR_REUSE.md) for the local Flycast lessons
that govern evidence, resource identity, and visual validation.

The first native artifact is `kos/re4dc-smoke.elf`: a 320×240 RGB565 PVR
triangle with Maple START handling. It deliberately proves only toolchain,
video, primitive submission, and input. The current ELF is a statically linked,
little-endian SH-4 executable with a 224,636-byte linked footprint and SHA-256
`8a1db88ed9d784e0f45a093e742b918e5cfbeb9f69cba404b38ce21eef2160fa`.
Build it after sourcing KOS with `make -C port/dreamcast/kos`.

The first Flycast candidate run is retained under
`C:\Flycast-Evidence\re4-dreamcast\smoke-20260919-141209`. Its console capture
shows KOS startup, the 320×240 RGB565 mode, controller discovery, and frame 300;
its render capture shows the expected moving gradient triangle. This is emulator
evidence. It is not a physical Dreamcast, timing, or input acceptance result.

The reproducible bootstrap is:

```sh
port/dreamcast/tools/bootstrap_kos.sh --build
```

It verifies the three revisions in `toolchain.lock`, builds only the required
SH-4 toolchain, builds KOS, and then builds the platform and motion smoke
executables. The optional ARM toolchain is intentionally excluded until custom
AICA firmware is needed.
