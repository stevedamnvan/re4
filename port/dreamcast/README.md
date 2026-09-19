# Resident Evil 4 Dreamcast port

This directory contains the new Dreamcast target. It is deliberately separate
from the byte-matching GameCube build: the upstream build remains the behavior
and asset reference, while this target is compiled for SH-4 with KallistiOS.

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
- Walkable r10d prototype: disc SAT floor/wall collision, tank movement, a
  shoulder follow camera, reset/exit controls, and a visible route marker run
  together in the native room executable
- Disc-derived Leon prototype: the original 1,484-vertex body is skinned
  offline with the source motion evaluator and plays the starting-handgun idle
  and walk cycles in the native room executable

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

Prepare the private `r10d` and Leon packages, then build the native room demo:

```sh
make -C port/dreamcast -f Makefile.host demo-r10d
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room
```

The executable validates the room, collision, and character packages, culls
room groups, submits flat-shaded PVR geometry, and supports analog-stick or
D-pad tank movement, SAT floor/wall collision, a shoulder follow camera,
A-button reset, START exit, route telemetry, and idle/walk animation selection.
The generated packages stay ignored. The first broad orbit proof and the
current close gameplay view both miss the frame budget; their timer includes
PVR wait time. See
[the room SH-4 baseline](docs/ROOM_SH4_BASELINE.md).
The integrated movement/collision evidence and its remaining P0 limits are in
[the walkable r10d checkpoint](docs/WALKABLE_R10D_BASELINE.md).

## Near-term sequence

1. Add the minimum aim, fire, reload, damage, and one-Ganado paths for a small
   combat loop, using the same private offline character conversion boundary.
2. Trim the measured room submission bottleneck enough for readable combat;
   add near-plane clipping only if the combat route demonstrates the need.
3. Add the essential Leon, handgun, and Ganado attachments or textures needed
   for combat readability, without expanding into a general asset renderer.
   Audit existing cheaper model variants before making new simplified art.
4. Measure the combined runtime, add essential textures/cutouts, and validate
   it on stock Dreamcast. Continue useful Flycast iteration while hardware
   validation is pending, without claiming hardware acceptance.

The authoritative next-task order and acceptance criteria are in
[the playable backlog](docs/PLAYABLE_PATH.md). The
[hardware/source assessment](docs/HARDWARE_TRANSLATION.md) documents the
GameCube differences, real-time scenes, SFD movies, and render-to-texture work.
See also [the r10d asset boundary](docs/R10D_VERTICAL_SLICE.md).

General room streaming, menus, complete audio, story events, and campaign
progression stay behind that playable gate.

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
