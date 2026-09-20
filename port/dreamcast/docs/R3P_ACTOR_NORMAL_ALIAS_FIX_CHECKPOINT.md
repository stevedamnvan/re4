# R3p actor-normal alias fix checkpoint

Date: 2026-09-20

Decision: **keep the separate actor-normal scratch and reject the SH-4
`frsqrt` experiment**.

## Correctness defect

The r100 actor path previously used the same float buffer first for transformed
source normals and then for per-work-item lighting. `build_character_lighting()`
read `normals[normal_sources[i]]` while writing `lighting[i]`. Because those
pointers aliased, each completed lighting item could replace a source normal
needed by a later item.

The private accepted packages prove that in-place traversal is unsafe:

| Actor | lighting work items | source normals | identity entries | future references | non-monotonic steps |
|---|---:|---:|---:|---:|---:|
| Leon | 6,413 | 5,774 | 5 | 575 | 2,453 |
| Ganado | 1,900 | 1,818 | 5 | 572 | 868 |

Leon has 639 repeated work-item references and Ganado has 82. This is intended
reuse of source normals across position/normal identities, not a safe output
order. The old result was therefore a known target defect rather than an
authoritative visual reference.

R3p adds bounded immutable normal scratch sized for the accepted packages:
6,144 Leon normals and 2,048 Ganado normals. Per-work-item floating-point RGB
lighting remains separate because the generic near-plane clipper interpolates
those values before packing. This preserves the existing clipping and shading
semantics and costs exactly 98,304 bytes of main-RAM headroom.

## Bounded math experiment

After separating the buffers, a validation build compared the portable
square-root normalizer with a KallistiOS `frsqrt` candidate at every packed actor
color. Across 330 captured frames, almost all frames were identical; the worst
observed difference was one channel value in one packed color. The comparison
was valid only after the alias was removed.

The candidate was still rejected because it was slower. Over matched ticks
165-1194, the `frsqrt` production build spent 19.514 ms p50 in actor lighting;
the portable square-root reference spent 18.692 ms. That 0.822 ms regression is
larger than any plausible benefit, so no fast-normal code or build option remains
in the accepted source.

Diagnostic evidence is retained privately:

- corrected dual-path validation: `d216-actor-lighting-alias-fix-validation`
- `frsqrt` production candidate: `d217-actor-lighting-alias-fix-production`
- portable reference production run: `d218-actor-lighting-reference-production`
- clean accepted autoplay run: `d219-actor-normal-alias-fix-final`
- clean manual smoke: `d220-actor-normal-alias-fix-manual`
- framebuffer visual check: `d221-actor-normal-alias-fix-visual`

## Accepted result

The clean R3p autoplay build has SHA-256
`4fd89b4e929aca49a9cdc8b7e231c9a1e33ff387cac81466d42e0d49b686a44f`.
The manual build has SHA-256
`b265872f40b74f8fbe3cd5e7be28e4bcb73e8af2e54717d8cc5076f9ef91dd0a`.
The manual ROM-disk staging contained no autoplay flag.

R3o and R3p were compared over ticks 165-1194:

| Metric | R3o aliasing baseline | R3p separate normals | Delta |
|---|---:|---:|---:|
| CPU frame p50 | 87.615 ms | 86.217 ms | -1.398 ms |
| CPU frame p95 | 90.116 ms | 88.719 ms | -1.397 ms |
| CPU frame p99 | 90.209 ms | 88.836 ms | -1.374 ms |
| render total p50 | 87.342 ms | 85.944 ms | -1.398 ms |
| actor lighting p50 | 18.959 ms | 18.198 ms | -0.761 ms |
| TA registration p50 | 58.731 ms | 58.096 ms | -0.635 ms |
| main-RAM headroom | 5,668,864 B | 5,570,560 B | -98,304 B |

The corrected path keeps the same medians of 327 visible groups, 9,155 room
triangles, 11,900 actor triangles, 617 PVR submissions, and 1,071,840 submitted
bytes. Both traces have zero discarded simulation time and zero simulation
overruns. The accepted trace selects lights `0x00000053` for Leon and
`0x00000126` for Ganado throughout the captured route. Median actor-lighting
cost splits into 13.960 ms for Leon and 4.232 ms for Ganado.

The 12-second framebuffer capture retains the accepted room, complete Leon and
Ganado assemblies, HUD, camera, transparency, and coherent lighting. Its
SHA-256 is
`658ae4dbb1f6a13e80fd4c48eda5124b7a7a0f36f0ab2e2ff5940c7b0e8236f9`.
Full-framebuffer emulation was enabled only to extract that image; all timing
figures above use the normal pinned Flycast configuration.

The manual smoke reached simulation tick 558, sampled input 1,860 times with a
12.484 ms maximum gap, and reported zero queue drops, simulation overruns, or
discarded simulation time. It did not inject combat controls and is not a full
manual acceptance run.

## Consequence

R3p becomes the Dreamcast regression and performance baseline. It fixes a real
source-normal identity bug and is faster despite its bounded scratch cost. The
next actor-lighting experiment should attack the stable selected-light work,
especially Leon's 13.96 ms, while retaining the portable evaluator as the
reference. Physical Dreamcast timing remains pending.
