# Resident Evil 4 Dreamcast port

This directory contains the new Dreamcast target. It is deliberately separate
from the byte-matching GameCube build: the upstream build remains the behavior
and asset reference, while this target is compiled for SH-4 with KallistiOS.

**Current objective (2026-09-20): the source-derived r100 encounter with measured
real-time performance and responsive input, preserving its authored presentation.**
The [current plan](docs/REALTIME_PATH.md) prioritizes correct profiling, bounded
room-vertex reuse, original light selection, SAT hierarchy, model/weight-palette
structure, and hardware measurement. Approximately 30 fps at current fidelity is
a target whose feasibility remains unproven.

The textured native 640x480 slice at `fed3e91` is frozen as an integration
reference with source HUD, combat audio, and controller-path traces. Reported
0.78-0.84-second frames do not establish real-time playability. Physical hardware,
peak memory, human responsiveness and full source fidelity remain open. The
[integration record and source ownership ledger](docs/PLAYABLE_PATH.md) retain
exact artifact identities and remaining adaptations.

## Current checkpoint

- RE4 source baseline: `9dcd989370be7f083a9b66cfd19907fda627c893`
- Branch: `dreamcast-port`
- Authoritative checkout: `/root/work/re4-dreamcast` in Ubuntu 24.04 WSL2
- KallistiOS baseline: `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`
- kos-ports baseline: `f4faacc42faaf552625777b7709e871a827e1055`
- G4BE08 debug Disc 1: locally supplied, header-verified, hashed, and kept
  outside Git (SHA-256 `b7fcbf121cf7c527aae23838e9c3f0818e31115bb597eb77a2c49c9e8fa46492`)
- `sh-elf` toolchain: GCC 15.2.0 installed at `/opt/toolchains/dc/sh-elf`
- KallistiOS: built successfully from the pinned revision (reports v2.3.0)
- Native smoke ELF: built and booted past frame 300 in an isolated Flycast run
- RE4 motion/IK slice: upstream game functions compile for SH-4 and pass both
  the synthetic fixture and a private real-data fixture from Leon's `pl00.drs`
- Historical walkable r10d prototype: disc SAT floor/wall collision, tank movement, a
  shoulder follow camera, reset/exit controls, and a visible route marker run
  together in the native room executable
- Disc-derived Leon prototype: the original 1,484-vertex body is skinned
  offline with the source motion evaluator and plays the starting-handgun idle
  and walk cycles in the native room executable
- Small combat loop: one disc-derived village Ganado approaches, turns, attacks,
  reacts to aimed shots, and dies; Leon has a reticle, health, six-round ammo,
  timed reload, death/restart, and a defeat-gated room exit
- Historical experimental performance profile: coarse offline LOD, a 35 m horizon, and
  triangle rejection reduced one Flycast spawn sample from 117.1 to 29.4 ms.
  A later normal-boot sample was 26.8 ms; the recorded end-of-route sample was
  37.8 ms. The automated loop passes, but these point samples do not establish
  sustained 30 fps or acceptable visual quality.

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
Character package v6 now removes the redundant baked mesh poses and reuses one
prepared source palette for both positions and normals. Its 5.34 MiB live-RAM
gain and matched performance result are in
[the R3i source position-palette checkpoint](docs/R3I_SOURCE_POSITION_PALETTES_CHECKPOINT.md).
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

1. Keep the 30-second r100 cabin encounter on source camera, placement, room,
   actor, motion, collision, and sound data.
2. Validate the recovered source object/cull/mask/volume path and ordered
   per-model light selection against a matched debug-game trace. The R1c cache
   reuses the current source-derived fixed contribution without reducing visible
   assets; R0, R1a, and the target-side R1b/R1c implementations are complete,
   while source-trace acceptance remains open.
3. Complete source SAT primitive/query parity on top of the recovered hierarchy.
   Character package version 6 now preserves source positions, normals,
   draw-corner identities, and reusable weight palettes. Next integrate or
   behaviorally trace the source motion/state path rather than adding another
   animation representation.
4. Complete human-controller combat, reload, death, disconnect, and repeated
   reset acceptance on the independent input service; its short-edge and
   autoplay tests are complete in Flycast.
5. Package the private Flycast demo and validate loading, timing, memory, audio,
   controller, and output on physical Dreamcast.

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
