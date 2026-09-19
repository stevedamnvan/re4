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
- Original G4BE08 disc images: not found during the initial local search
- `sh-elf` toolchain: GCC 15.2.0 installed at `/opt/toolchains/dc/sh-elf`
- KallistiOS: built successfully from the pinned revision (reports v2.3.0)
- Native smoke ELF: built and booted past frame 300 in an isolated Flycast run

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

## Near-term sequence

1. Build the pinned KallistiOS SH-4 toolchain and KallistiOS in WSL.
2. Obtain and hash the user's G4BE08 debug-disc images, reproduce the upstream
   reference hashes, and keep all extracted assets out of Git.
3. Use upstream's `tools/motion_export.py` and byte-round-trip checks as the
   first verified asset path. Extend the same parse/serialise/compare pattern to
   room data, models, and textures.
4. Compile a KOS executable containing fixed-width types, logging, timing,
   allocation telemetry, and the controlled cooperative scheduler boundary.
5. Convert and render one real room and one animated actor before expanding the
   gameplay dependency set.

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
SH-4 toolchain, builds KOS, and then builds the smoke executable. The optional
ARM toolchain is intentionally excluded until custom AICA firmware is needed.
