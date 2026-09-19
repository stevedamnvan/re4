# Portability baseline — 2026-09-19

Baseline source: `9dcd989370be7f083a9b66cfd19907fda627c893`.

The host audit scanned 1,015 C/C++ source and header files. Counts below are
lexical occurrences used to size and route the work; they are not counts of
unique functions and include matching/research comments where those comments
share the source file.

| Boundary | Occurrences | Files |
|---|---:|---:|
| Nintendo SDK headers | 457 | 244 |
| GX calls | 4,858 | 110 |
| Direct GX FIFO references | 75 | 7 |
| OS calls | 2,405 | 253 |
| DVD/ARAM calls or symbols | 924 | 38 |
| CARD calls or symbols | 588 | 19 |
| REL/module references | 204 | 18 |
| Assembly constructs | 1,241 | 327 |
| Explicit register pins | 127 | 63 |
| Fixed `0x80`–`0x82` GameCube addresses | 1,218 | 285 |
| Pointer-to-`u32` casts | 3,313 | 424 |

The generated JSON contains per-file counts and up to 100 example locations per
category. Re-run it with:

```sh
make -C port/dreamcast -f Makefile.host audit
```

## First portable core

Upstream's motion-host path successfully compiles these source portions on
x86-64 without editing the game tree:

- motion evaluation from `motion.cpp`;
- inverse kinematics from `ik.cpp`;
- selected model hierarchy and blend functions from `model.cpp`;
- core transform/interpolation functions from `math_sub.cpp` and `sub2.cpp`;
- SDK matrix, vector, and quaternion operations through portable C versions;
- the game's `sinf`, `cosf`, and `acosf` implementation.

That path is now part of the Dreamcast host check. It establishes a bounded
starting set for SH-4 compilation, and upstream documents Dolphin comparisons
within one or a few floating-point ULPs for the tested motion. It does not yet
show SH-4 equivalence.

`rnd.cpp` and `ik.cpp` contain no constructs classified by the first audit and
are candidates for early direct compilation. `motion.cpp` and the selected
model/math functions need the same explicit pointer-width, register-pin, and
paired-single replacements already isolated by the upstream host preparation.

## Platform-heavy boundaries

| Source | Classified pressure | Treatment |
|---|---|---|
| `trans.cpp` | 470 GX calls plus pointer/layout dependencies | New PowerVR renderer consuming a narrow model/material contract. |
| `main_mem.cpp` | Fixed memory map, OS heap calls, pointer truncation | New named arenas and telemetry; preserve lifetime semantics. |
| `scheduler.cpp` | Nintendo threads, GX ownership, pointer assumptions | Controlled KOS task adapter with deterministic execution order. |
| `datactrl.cpp` | DVD/ARAM ownership and pointer-sized destinations | Versioned room/actor cache with bounded main-RAM staging. |
| `pad.cpp` | PAD ABI, matching constructs, module references | Maple action-level input adapter. |
| `yz2asm.cpp` | PPC assembly decoder | Portable byte-verified decoder, then offline Dreamcast packaging. |

## ABI result

The host probe confirms the Linux build host is little-endian with 8-byte
pointers and 8-byte `long`. Upstream's `types.h` therefore cannot define `u32`
as `unsigned long` for host tools. The new target uses `<cstdint>` types and
requires explicit big-endian decoding for GameCube data.
