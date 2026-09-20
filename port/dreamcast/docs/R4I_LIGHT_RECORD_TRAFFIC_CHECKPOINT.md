# R4i: type-specific prepared-light records

Status: reverted. The candidate built, was bit-identical to the reference
evaluator over 16.1 million lighting entries, and made the frame 0.487 ms
slower.

The conclusion in one line: **the 15-field record was never causing loads of
irrelevant fields, so giving each light type its own record removed no memory
traffic and the ordered dispatch it needs costs a load and a branch per light
per entry.**

The premise under test came from R4h's closing observation, that the
`PreparedActorLight` fields are re-read for every light on every entry. The
re-reading is real. What is not real is the idea that a directional light was
paying for the radius, attenuation, cone and spot fields it never touches.

## The candidate

`PreparedActorLight` was replaced by two records. `PreparedDirectionalLight`
holds six floats, the direction and the colour premultiplied by intensity.
`PreparedPositionalLight` keeps the original fifteen fields, because point and
spot lights genuinely need them and their distance, attenuation, cone,
normalization, branch and accumulation semantics had to stay exactly as they
were.

Order was preserved with an ordered code stream rather than by grouping. A
one-byte code per selected light names the pool in its high bit and the slot in
its low bits, so the evaluator walks the lights in selection order. Ganado's
directional, point, directional, point interleave is still evaluated and
accumulated in that order; nothing is grouped by type.

The one arithmetic change is the premultiplication. The evaluator computed
`(red * attenuation) * diffuse` with `attenuation` holding `intensity`
unchanged for a directional light, so folding `red * intensity` into preparation
is the same multiply on the same operands, associated the same way. That was
verified rather than assumed.

## Code generation, before timing

| | R4f accepted | R4i candidate |
|---|---:|---:|
| whole function, instructions | 728 | 780 |
| whole function, memory instructions | 200 | 200 |
| whole function, branches | 67 | 73 |
| hot loop, instructions | 654 | 720 |
| hot loop, memory instructions | 166 | 169 |

Record bytes touched per light, counting only the fields each path reads:

| light type | R4f | R4i |
|---|---:|---:|
| directional (5) | 32 | 25 |
| radius point (1) | 36 | 37 |
| quadratic point (2) | 36 | 37 |
| spot (3) | 56 | 57 |

The directional case does touch 22% fewer bytes. Every other case touches one
byte more, the sequence code. And the loop's memory instruction count does not
fall at all: 166 becomes 169.

That is the whole result in one line of the table. The old code was already
loading only the fields its branch needed; a 60-byte record does not force a
load of a field the code never mentions. Record size affected addressing, not
the number of loads, so shrinking it could not remove the traffic it was
supposed to remove. What the restructure did add is real: a code byte load and a
pool test per light per entry, plus the address arithmetic for a computed slot
into a second pool, which is 52 more instructions and 6 more branches.

## Correctness

Bit-identical, and this is the useful part to keep. Over a 1,941-frame
SUBMIT_PROFILE run against the unchanged reference evaluator:

| | |
|---|---:|
| lighting entries compared | 16,127,220 |
| RGB mismatches | 0 |
| worst frame | 0 mismatches |

So premultiplying colour by intensity for directional lights is bit-exact in
practice, not just in argument, and the ordered code stream preserves the
accumulation sequence exactly. Both facts survive the revert and can be reused.

## The result

| Stage p50 (us) | R4f accepted | R4i candidate | delta |
|---|---:|---:|---:|
| frame | 57,565 | 58,052 | **+487** |
| frame p95 | 57,626 | 58,125 | +499 |
| frame p99 | 60,127 | 60,614 | +487 |
| actor lighting | 16,207 | 16,695 | +488 |
| Leon lighting | 12,489 | 12,728 | +239 |
| Ganado lighting | 3,714 | 3,962 | +248 |
| actor normals | 1,831 | 1,831 | 0 |
| actor pose | 5,494 | 5,494 | 0 |
| opaque room | 19,432 | 19,432 | 0 |
| `submit_us` | 33,006 | 33,006 | 0 |

Every untouched stage is identical to the microsecond, free main RAM is
unchanged, and there were no simulation overruns, dropped ticks or input-queue
drops in either arm. Preparation cost is included: it runs inside the measured
stage.

The split between the actors is the most informative number here. Leon pays
37 ns per entry and Ganado 130 ns. Leon's four lights are three directional and
one spot; Ganado's are two directional and two point. The cost tracks the number
of **positional** lights per entry, which is exactly where the candidate added
indirection and nothing else, while the directional path it was meant to
improve is close to free either way.

## What this closes, and what it leaves

The general compact representation lost on indirection, so by the rule agreed
before building it, this does not get iterated into another cache. Four routes
to the 2.018 ms actor-lighting regression are now closed with explanations:
build policy in R4f, the translation-unit split in R4g, per-entry input caching
in R4h, and general per-type records here.

The remaining idea is narrower and does not rely on a general representation.
Both actors run exactly four lights, from a single selection mask each that
does not change for the whole route: Leon is directional, directional,
directional, spot; Ganado is directional, point, directional, point. A bounded
specialization of those observed ordered sequences, straight-line code with the
light data addressed directly and no dispatch at all, with the general evaluator
retained as a fallback whenever the selection does not match a specialized
shape, is the next branch. It keeps accumulation order by construction, because
the sequence is written out in order.

## Evidence

`d272-r4i-light-records` holds `baseline.elf` and `candidate.elf` with their
timing captures and `candidate-profile.elf` with the dual-path capture. The
accepted build was restored by checking out `main.cpp`; it rebuilds to
`68f720cd...b412c296`, matching R4f bit for bit.
