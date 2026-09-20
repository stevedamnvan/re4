# R4g: the actor-lighting translation unit (DCA3 audit item A2b)

Status: reverted. The candidate built, ran and was correct, and it made the
frame 0.160 ms slower. The route is now closed with an explanation rather than
a guess, which is the useful part.

The conclusion in one line: **the `-O2` advantage on this kernel is not an
advantage of `-O2`. It is an advantage of being compiled inside `main.cpp`, and
no optimization level recovers it once the kernel is moved out.**

## What R4d left open

`-O3` took 2.839 ms off the frame but made actor lighting 2.018 ms worse. R4f
ruled out a per-function attribute and seven `-O3` sub-flag groups. The audit's
remaining route was its own A2 suggestion: extract the hot kernels into a
translation unit and compile that unit differently.

## The code generation, before building anything

Disassembling `build_character_lighting()` in two otherwise-identical builds,
`-O2` against the accepted `-O3 -fno-predictive-commoning` with link-time
optimization:

| | `-O2` | accepted `-O3` |
|---|---:|---:|
| instructions | 551 | 714 |
| memory instructions | 153 | 195 |
| `fmov` | 99 | 135 |
| `fcmp` | 16 | 28 |
| branches | 49 | 68 |
| `fdiv` / `fsqrt` / `fmac` | 8 / 2 / 12 | 8 / 2 / 12 |
| stack frame | 540 B | 560 B |
| `cmp/eq` against light types 5, 1, 3 | 2 / 1 / 1 | 2 / 1 / 1 |

Several things this rules out immediately. `evaluate_prepared_actor_lighting()`
and `prepare_actor_lights()` are inlined in **both** builds; there is one symbol
either way, so the regression is not a lost inline. The light-type dispatch is
not duplicated, so it is not loop unswitching. The floating-point core is
identical operation for operation, so the arithmetic is untouched: the same two
`fsqrt` for the two normalizations, the same eight `fdiv` for the normalize
divides and the attenuation terms, the same twelve `fmac` for the diffuse dot
products. The stack frame grows by 20 bytes, so it is not a spill explosion.

What `-O3` adds is 163 instructions and 42 memory operations of scheduling and
control flow around unchanged arithmetic. `tools/sh4_loop_cost.py` puts that
where it hurts, in the per-normal loop body:

| | whole function | hot loop body | modelled cost |
|---|---|---|---:|
| `-O2` | 560 insns, 159 mem | 297 insns, 66 mem | ~1,640 ns/iter |
| accepted `-O3` | 728 insns, 200 mem | 654 insns, 166 mem | ~3,818 ns/iter |

The hot loop body more than doubles. Against Leon's per-frame normal count that
is the right order to explain 1.541 ms, so the hypothesis looked sound and the
candidate was worth building.

## The candidate

`room/actor_lighting.hpp` and `room/actor_lighting.cpp`, holding
`prepare_actor_lights()`, `evaluate_prepared_actor_lighting()`, the
SUBMIT_PROFILE reference evaluator and `build_character_lighting()`, with the
shared types, the source light tables, `shade_color()` and `normalize_vector()`
promoted into the header. Compiled `-O2 -fno-lto` while everything else kept
`-O3 -fno-predictive-commoning` with link-time optimization. `-fno-lto` matters:
without it the link could re-plan the kernel back into the regime the unit
exists to avoid, and with it the unit reaches the linker as an ordinary object
file rather than as GIMPLE.

Two things had to be got right, and the first attempt got one of them wrong.
Exporting the helpers from the header gave them external linkage, GCC emitted
them out of line, and `-O2` then declined to inline them into
`build_character_lighting()`: the kernel split into a 420-byte caller and a
588-byte callee. That is precisely the boundary R4f measured with the
optimization attribute. Giving them internal linkage inside the unit restored
the single 1,416-byte inlined kernel.

## The result

| Stage p50 (us) | `-O2` everywhere | R4f accepted | R4g split at `-O2` |
|---|---:|---:|---:|
| frame | 60,790 | 57,565 | 57,725 |
| frame p95 | - | 57,641 | 57,793 |
| actor lighting | 14,189 | 16,207 | **16,367** |
| Leon lighting | 10,948 | 12,489 | 12,649 |
| Ganado lighting | 3,235 | 3,714 | 3,714 |
| opaque room | - | 19,432 | 19,432 |
| opaque actor | - | 9,595 | 9,595 |
| `submit_us` | - | 33,006 | 33,006 |

Every other stage is unchanged to the microsecond, which confirms the change was
correctly scoped. Actor lighting is 160 us worse than R4f, not 2 ms better, and
the frame follows it. Free main RAM falls 4,096 bytes because the unit is no
longer folded into the rest of the image.

## Why, and this is the part worth keeping

Compiling the same unit at both levels shows the level barely matters once the
kernel is outside `main.cpp`:

| context | instructions | memory instructions |
|---|---:|---:|
| inside `main.cpp`, `-O2` | 560 | 159 |
| inside `main.cpp`, `-O3` | 728 | 200 |
| own unit, `-O2` | 708 | 194 |
| own unit, `-O3` | 704 | 191 |

In its own unit the two levels produce the same code to within four
instructions, and both land on the `-O3` shape. So the 560-instruction version
is not what `-O2` does to this function; it is what `-O2` does to this function
**when the compiler can see the whole of `main.cpp` around it**. In that
setting the kernel has internal linkage, both call sites are visible, and GCC
emits an `.isra.0` clone specialized against the arguments those call sites
actually pass. Moving the kernel out gives it a fixed external signature and
destroys that context, and `-fno-lto`, which the split needs in order to hold
its optimization level, also guarantees the context cannot be rebuilt at link
time.

The route is therefore self-defeating, not merely unsuccessful. Any version of
this split that keeps the kernel's `-O2` code generation must also cut it off
from the interprocedural information that made that code generation good.

## Correctness

Not established, and deliberately so. The candidate built cleanly with
`-Wall -Wextra -Werror`, ran the full route, and produced identical per-frame
geometry counters, 1,333 direct strips and 972,928 submitted bytes at p50, with
free PVR memory unchanged at 3,030,856 bytes. The stream digest and framebuffer
comparisons were not run, because the frame time already failed the acceptance
rule and correctness evidence for a reverted candidate has no use.

The accepted build was restored by checking out `main.cpp` and the room
Makefile and deleting the two new files; it rebuilds to
`68f720cd...b412c296`, matching R4f bit for bit.

## What this leaves

The 2.018 ms actor-lighting regression stands, and both routes to it are now
closed: the per-function attribute in R4f and the translation-unit split here.
Anything further has to attack the loop itself rather than the build. The
measured target is concrete: the per-normal loop body is 654 instructions and
166 memory operations at `-O3` against 297 and 66 at `-O2`, doing identical
floating-point work, so a hand-restructured loop that the optimizer cannot
inflate is the remaining idea. That is a source change with a real correctness
obligation, and it belongs in the memory-instruction queue item rather than in
the build-policy one.

## Evidence

`d270-r4g-lighting-unit` holds the candidate's telemetry. The disassembly and
loop-cost comparisons were taken from purpose-built `-O2` and accepted-policy
ELFs and are reproduced in the tables above.
