# Motion and IK SH-4 baseline — 2026-09-19

This checkpoint compiles a bounded slice of the reconstructed RE4 game code for
Dreamcast SH-4. The compiled ELF contains the original prepared implementations
of `HermiteInterpolation`, `Fcc_next_axis_addr`, `ikCalc`, and
`GetDistance3`, together with the selected original model/math functions, the
SDK's portable matrix/vector routines, and the game's fdlibm.

The source preparation is upstream's existing `tools/motion/host/prepare.py`.
It removes compiler-matching PowerPC register pins and widens pointer casts in a
generated copy; it does not edit the original game files.

## Shared fixture

The same `motion_checks.cpp` is compiled for x86-64 and SH-4. It performs:

1. A three-axis type-15 motion-key evaluation at frame 10. Expected output:
   `(2, 4, 8)`.
2. A two-bone `ikCalc` solve with lengths 5 and 4 and a target at `(6, 2, 0)`.
   The first bone must retain length 5 and every resulting coordinate must be
   finite.

Recorded results:

| Target | Hermite | IK joint | IK joint distance | Result |
|---|---|---|---:|---|
| x86-64 host | `2, 4, 8` | `-0.999687552, 2.99906278, 3.87379026` | `5.00000048` | PASS |
| SH-4 in Flycast | `2, 4, 8` | `-0.999688, 2.999063, 3.873790` | `5.000000` | PASS |

The SH-4 ELF is a statically linked 32-bit little-endian Renesas SH executable.
Its linked footprint is 238,308 bytes and its first recorded SHA-256 is
`c4435af73f425c4c22856e9df7ee6c7cdbd3c56b67fe6ef174cbf745326eeda5`.
The ELF symbol table confirms that the four named RE4 functions are retained.

Evidence is retained under
`C:\Flycast-Evidence\re4-dreamcast\motion-20260919-142609`. The serial capture
shows the numeric result, `PASS`, and frame 300. The render capture is green on
pass and red on failure.

## Acceptance boundary

This verifies compilation and a synthetic numerical fixture through Flycast.
It does not yet evaluate a real RE4 character motion, prove byte-order handling
for an original archive on Dreamcast, compare against Dolphin, measure physical
Dreamcast performance, or establish complete motion-system portability. Those
claims require the locally supplied G4BE08 data and later hardware evidence.

## Commands

```sh
make -C port/dreamcast/motion -f Makefile.host clean run
source port/dreamcast/kos-env.sh
make -C port/dreamcast/motion clean all
```
