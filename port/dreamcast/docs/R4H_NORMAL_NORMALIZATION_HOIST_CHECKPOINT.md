# R4h: hoisting normal normalization out of the lighting loop

Status: reverted. The candidate built, was proved bit-exact against the
reference evaluator over 15.8 million lighting entries, and made the frame
0.240 ms slower.

The conclusion in one line: **the transformed source normal is reused 1.095
times on average, and materializing a cache with that reuse factor costs more
memory traffic than the duplicate normalizations it removes.**

This is the first experiment against the 2.018 ms actor-lighting regression that
attacks the loop rather than the build. R4f closed the per-function attribute
and the `-O3` sub-flag arms; R4g closed the translation-unit split and showed
the kernel's `-O2` advantage is interprocedural context, not the optimization
level. What remained was the source dataflow.

## The census, before writing any code

`build_character_lighting()` runs once per lighting entry, resolves
`normal_sources[entry]`, and the evaluator normalizes that normal every time.
Entries outnumber distinct source normals, so some normalizations are repeats.
Read straight out of the accepted packages:

| | Leon | Ganado | both |
|---|---:|---:|---:|
| lighting entries | 6,413 | 1,900 | 8,313 |
| distinct referenced source normals | 5,774 | 1,818 | 7,592 |
| normalizations eliminated | 639 | 82 | 721 |
| share of entries | 10.0% | 4.3% | 8.7% |
| most references to one source normal | 27 | 4 | - |
| reuse factor | 1.111 | 1.045 | 1.095 |

721 saved normalizations out of 8,313 is a small arithmetic saving, and that was
understood before building. The experiment was worth running for the second
reason: a normalization removed from an already-inflated loop body might simplify
the `-O3` code shape by more than the arithmetic it takes with it.

## The candidate

`evaluate_prepared_actor_lighting()` was split into a body taking an
already-unit normal and a wrapper that normalizes and calls it. Not one
floating-point operation moved relative to another: same `normalize_vector()`,
same order, same accumulation, same light order, no `frsqrt`, no approximation.
`build_character_lighting()` then normalized every referenced source normal once
into a scratch buffer before the entry loop and the loop read that buffer.
Leon and Ganado are lit one after the other, so one 73,728-byte buffer sized to
the larger actor serves both.

The SUBMIT_PROFILE reference path still receives the **raw** normal and
normalizes it internally, so the dual-path comparison tests exactly the thing
the change risks: that a normal normalized once outside the loop is bit-for-bit
the normal the old code produced inside it.

## Code generation

The normalization did leave the hot loop. Counting inside the kernel, the entry
loop drops from two `fsqrt` and eight `fdiv` to one and five, and the missing
one of each reappears in the new preparation loop.

| | R4f accepted | R4h candidate |
|---|---:|---:|
| whole function | 728 insns, 200 mem | 804 insns, 228 mem |
| outermost loop range | 654 insns, 166 mem | 732 insns, 189 mem |
| inner per-entry range | 390 insns, 86 mem | 361 insns, 80 mem |

The per-entry body does get smaller, by 29 instructions and 6 memory
operations. The function as a whole gets larger, because the preparation loop is
new code. The hoped-for collapse of the `-O3` code shape did not happen: the
body is 7% smaller, not 54% smaller, and nothing like the 297-instruction shape
`-O2` produces inside `main.cpp`.

## Correctness

Bit-identical, and this is worth recording because it is the one unambiguous
success here. Over a 1,900-frame SUBMIT_PROFILE run comparing every entry
against the reference evaluator:

| | |
|---|---:|
| lighting entries compared | 15,786,387 |
| entries compared per frame at p50 | 8,313 |
| RGB mismatches | 0 |
| worst frame | 0 mismatches |

8,313 per frame is the census figure exactly, so every entry of both actors was
compared on every frame.

## The result

Both builds captured back to back on the same host. The accepted build
reproduces its recorded p50 to the microsecond, which is what makes the
comparison trustworthy.

| Stage p50 (us) | R4f accepted | R4h candidate | delta |
|---|---:|---:|---:|
| frame | 57,565 | 57,805 | **+240** |
| frame p95 | 57,632 | 57,866 | +234 |
| frame p99 | 60,126 | 60,364 | +238 |
| actor lighting | 16,207 | 16,449 | +242 |
| Leon lighting | 12,489 | 12,627 | +138 |
| Ganado lighting | 3,714 | 3,817 | +103 |
| actor normals | 1,831 | 1,831 | 0 |
| actor pose | 5,494 | 5,494 | 0 |
| opaque room | 19,432 | 19,432 | 0 |
| opaque actor | 9,595 | 9,595 | 0 |
| `submit_us` | 33,006 | 33,006 | 0 |

Every stage the change does not touch is identical to the microsecond, and the
whole regression lands in actor lighting, so the change was correctly scoped and
the measurement is clean. Free main RAM falls by exactly 73,728 bytes, the
scratch buffer. No simulation overruns, dropped ticks or input-queue drops in
either arm.

## Why it lost

Count the memory the cache costs against the arithmetic it saves. Building the
cache reads three floats and writes three floats for each of 7,592 source
normals, 45,552 memory operations per frame that did not exist before. The entry
loop reads the same three floats it always read, just from a different array. In
return, 721 normalizations disappear.

At the Flycast cost model's 13.3 ns per memory operation the added traffic is
worth roughly 0.6 ms and the removed arithmetic well under 0.1 ms. The measured
0.242 ms is smaller than that estimate, because the preparation loop is a tight
sequential stream and the smaller loop body claws some back, but the sign is
never in doubt.

The general rule this establishes for the lighting loop: **a cache between the
transform and the shade only pays at a high reuse factor.** At 1.095 it cannot.

## The proposed follow-up, measured rather than built

The next experiment suggested was per-position reuse of the point and spot
terms, on the reasoning that light direction, distance, attenuation and cone
factor depend on the transformed position and are recomputed for every entry
sharing that position. The same census answers that before any code is written:

| | Leon | Ganado |
|---|---:|---:|
| distinct transformed positions | 5,673 | 1,667 |
| position reuse factor | 1.130 | 1.140 |
| evaluations saved | 740 (11.5%) | 233 (12.3%) |
| most entries sharing one position | 4 | 4 |
| contiguous runs of equal position | 6,404 | 1,895 |

The reuse factor is 1.133, barely above the 1.095 that just failed, while the
payload is several times larger: four floats per light per position against
three floats per position. Entries sharing a position are also not adjacent,
6,404 runs across 6,413 entries, so the cache would be written and read at
scattered addresses rather than streamed.

That is the same losing trade as R4h with a worse constant, so it is recorded
here rather than built. Caching per-entry inputs is now a closed line of attack
on this loop for the same reason the build-policy line is closed.

## What this leaves

The 2.018 ms regression stands. Three of the four obvious routes are now closed
with explanations rather than guesses: the build policy in R4f, the
translation-unit split in R4g, and per-entry input caching here.

What the measurements keep pointing at is untouched. The `-O3` loop body carries
166 memory operations against `-O2`'s 66 for identical floating-point work, and
the loads are of `PreparedActorLight` fields, re-read for every light on every
entry. Those are loop-invariant across the whole actor, and the per-light branch
on `type` is invariant per light. Splitting the prepared lights into
type-specific lists once per actor, so each entry runs a straight-line
directional pass and a point pass with no type test and no loads of fields that
type does not use, attacks the memory traffic directly and has no reuse factor
to depend on. That is the recommended next experiment.

## Evidence

`d271-r4h-normal-hoist` holds `baseline.elf` and `candidate.elf` with their
timing captures, `candidate-profile.elf` with the 1,900-frame dual-path capture,
and the 512-byte SUBMIT_PROFILE telemetry layout added to the reader. The
accepted build was restored by checking out `main.cpp`; it rebuilds to
`68f720cd...b412c296`, matching R4f bit for bit.
