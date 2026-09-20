# R4f: chasing the actor-lighting regression (DCA3 audit item A2b)

Status: partly kept. `-fno-predictive-commoning` adopted, worth 0.386 ms. The
actor-lighting regression R4d introduced is **not** explained and **not**
recovered; three routes were tried and all failed, which is recorded here so
they are not tried again.

## The question

R4d took 2.839 ms off the frame with `-O3` and link-time optimization, but actor
lighting went 2.018 ms the other way, from 14.189 ms to 16.207 ms. The audit's
A2 text says that if file-level policy is useful, extract the hot kernels into
their own translation unit. Before paying for that refactor, this checkpoint
asked the cheaper question: what in `-O3` actually hurts the lighting kernel?

## Route one: per-function optimization attribute. Rejected, made it worse.

`__attribute__((optimize("O2")))` on `evaluate_prepared_actor_lighting()` and
`build_character_lighting()` did not restore the `-O2` cost. It made the stage
considerably worse:

| | actor lighting p50 | frame p50 |
|---|---:|---:|
| `-O2` everywhere | 14,189 us | 60,790 us |
| `-O3` everywhere (R4e) | 16,206 us | 57,950 us |
| `-O3` with the two kernels attributed `O2` | **19,174 us** | 60,924 us |

The attribute creates an optimization boundary between the caller and the
callee, so the evaluator stops being inlined into the per-normal loop and
becomes a real call for every normal. That is worse than either uniform
setting. GCC also documents this attribute as behaving differently from the
command-line option and discourages it in production, which the measurement
agrees with.

The useful consequence: a translation-unit split would have to move the caller
and the callee together, or it will reproduce exactly this failure.

## Route two: bisect the `-O3` sub-flags. The regression is in none of them.

Seven arms, each `-O3` plus link-time optimization with one group disabled.
Actor lighting is **identical to the microsecond in every one**:

| Arm | actor lighting p50 | frame p50 | vs R4e |
|---|---:|---:|---:|
| R4e, plain `-O3` | 16,206 | 57,950 | - |
| `-fno-tree-vectorize` | 16,207 | 57,624 | -326 |
| `-fno-tree-slp-vectorize` | 16,207 | 57,953 | +3 |
| `-fno-predictive-commoning` | 16,207 | **57,565** | **-385** |
| loop-transform group | 16,207 | 58,043 | +93 |
| IPA and partial-PRE group | 16,367 | 58,137 | +187 |
| `-fno-tree-vectorize -fno-predictive-commoning` | 16,207 | 57,620 | -330 |

The loop-transform group is `-fno-peel-loops -fno-unswitch-loops
-fno-split-loops -fno-loop-interchange -fno-version-loops-for-strides
-fno-tree-loop-distribute-patterns`; the IPA group is `-fno-ipa-cp-clone
-fno-tree-partial-pre -fno-gcse-after-reload -fno-split-paths`.

Actor lighting sits at 16,207 us under every combination. Whatever `-O3` does to
that kernel is not controlled by any individual pass flag tested here, so it is
most likely an inlining or register-allocation consequence of the optimization
level itself. That is the hypothesis the translation-unit split would test, and
it remains untested.

Note also that the two useful flags are **not additive**: together they give
-330 us, worse than `-fno-predictive-commoning` alone at -385 us. Flag effects
here interact, so each combination has to be measured rather than reasoned about.

## Route three: what was adopted

`-O3 -fno-predictive-commoning` with link-time optimization. Predictive
commoning hoists loads across loop iterations; on these loops it buys nothing
and costs registers.

| Stage p50 (us) | R4e | R4f | change |
|---|---:|---:|---:|
| frame | 57,951 | 57,565 | -386 |
| frame p95 | 58,011 | 57,641 | -370 |
| frame p99 | 60,509 | 60,127 | -382 |
| opaque actor draw | 9,900 | 9,595 | -305 |
| `submit_us` | 33,391 | 33,006 | -385 |
| opaque room | 19,464 | 19,432 | -32 |
| actor lighting | 16,207 | 16,207 | 0 |

Two independent runs of the candidate both give 57,565 us to the microsecond,
against 57,951 for the baseline, so this is reproducible rather than a sample.
Memory is unchanged: free PVR memory after textures 3,030,856 B, free main RAM
5,353,472 B.

## Correctness, and a correction to how the digest must be used

The stream digest found 512 mismatches on the first attempt, against the `-O2`
baseline recorded in R4c. That baseline was invalid, not the build.

The digest covers every byte submitted to the tile accelerator, and polygon
headers are submitted through the same path as vertices. A polygon header
carries its texture address. R4e changed those addresses by sharing one
allocation per distinct payload, so every frame's digest legitimately changed at
R4e even though the image did not. Byte counts were identical throughout, which
was the clue.

Rebuilt against an R4e-era digest baseline, isolating the flag as the only
difference: **560 shared simulation ticks, zero mismatches.** The emitted stream
is byte-identical, and since R4e's framebuffers were already proved identical to
R4d's, the image is unchanged.

The general rule this establishes: a digest baseline must come from the same
texture-allocation regime as the candidate. The digest is a stream-identity
check including header state, not a geometry-only check.

## What is still open

The 2.018 ms actor-lighting regression stands. The remaining route is the audit's
own: move `prepare_actor_lights()`, `evaluate_prepared_actor_lighting()` and
`build_character_lighting()` into one translation unit compiled at `-O2`, caller
and callee together, as a movement-only patch first. That needs the types they
share with `main.cpp` promoted to a header, so it is a real refactor and is not
scheduled here.

Weigh it honestly before starting: the prize is up to 2 ms if the stage returns
to its `-O2` cost, but route one shows the split can just as easily make things
worse, and the mechanism is still unidentified. Reading the generated SH-4 for
the kernel at both levels would cost less than the refactor and would say
whether the hypothesis is even right.

## Evidence

`d269-a2b-lighting-opt` holds all seven flag arms, the attribute probe and the
bracketed repeat runs. `d265-r4c-a1a-digest` holds the digest comparison and the
invalid-baseline attempt that preceded it.
