# Fidelity-preserving real-time r100 plan

Updated 2026-09-20 from the corrected R3p actor-normal build and the R3q
submission profile. This is the authoritative execution plan. Earlier R0-R3 checkpoint documents remain evidence
records; their letter sequence no longer determines the next task.

## Current status

The accepted visual baseline is the native 640x480 r100 cabin encounter with the
source room, camera/FOV, selected lighting, complete handgun Leon assembly,
right-handed Ganado assembly, source-facing actor culling, HUD, combat events,
and audio. The original GameCube build remains the behavioral and presentation
authority when that baseline contains a known approximation or defect.

Implemented target optimizations include fixed-step/input telemetry, independent
controller sampling, source light selection, prepared static room-light terms,
source SAT hierarchy traversal, source position/normal palette reuse, native
actor and room strips, ordered-alpha strip protection, packed actor colors,
validated room normals, compact selected-light evaluators, a bounded room vertex
cache, conservative one-metre opaque child cells, source-authorized binary
punch-through, one source-ordered visible-room list reused by every material
pass, combined header/first-payload submissions, and separate immutable actor
normal scratch. Do not propose these again as unimplemented work.

R3m preserves source-authorized binary alpha while retaining gradient blend.
R3n reuses visibility, cull state, and room-light selection across material
passes. R3o combines each PVR header with its first payload, halving immediate
call count but saving only 0.12 ms. R3p fixes a source-normal identity defect by
separating transformed normals from lighting output. R3q changes no accepted
code; it profiles the room submission path and closes two candidates. See the
corresponding checkpoint records, most recently
[R3P_ACTOR_NORMAL_ALIAS_FIX_CHECKPOINT.md](R3P_ACTOR_NORMAL_ALIAS_FIX_CHECKPOINT.md)
and
[R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md](R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md).

The rejected R3p subexperiment used KallistiOS `frsqrt`. A valid dual-path run
found a worst observed difference of one channel value in one packed color, but
the fast path was 0.822 ms slower at actor-lighting p50. It has been removed.

## Current measured budget

Flycast measurements use the pinned 640x480 build and stock Dreamcast memory
sizes. They are emulator evidence. R3o and R3p are matched over simulation ticks
165-1194 and include source-timed turn, aim, fire, reload, enemy kill, held result
view, and timed retry. The current autoplay does not cover free movement, aim
extremes, enemy contact, Leon death, or a human controller; those remain separate
acceptance gates.

| Matched metric, ticks 165-1194 | R3o aliasing baseline | R3p corrected normals |
|---|---:|---:|
| CPU frame p50 / p95 / p99 | 87.615 / 90.116 / 90.209 ms | 86.217 / 88.719 / 88.836 ms |
| presented ready-to-ready p50 / p95 | 83.411 / 100.096 ms | 83.409 / 100.096 ms |
| PVR registration p50 | 58.731 ms | 58.096 ms |
| actor lighting p50 | 18.959 ms | 18.198 ms |
| main-RAM break-to-stack headroom | 5,668,864 B | 5,570,560 B |
| dropped simulation time / overruns | 0 / 0 | 0 / 0 |

The accepted candidate still presents at roughly 11-12 distinct frames per
second. A 33.33 ms CPU frame needs another 52.9 ms median reduction and 55.4 ms
at p95. PVR raster time was 7.50 ms p50 in the preceding matched R3n trace; SH-4
preparation and TA registration remain the dominant measured costs.

R3p median CPU stages are shown without adding the overlapping `submit_us`
aggregate to its children:

| Stage | p50 |
|---|---:|
| opaque room transform/light/clip/submit | 26.687 ms |
| binary plus blended alpha room work | 17.820 ms |
| actor lighting | 18.198 ms |
| opaque actor draw | 11.792 ms |
| actor pose palettes/projection | 5.820 ms |
| actor normals | 1.831 ms |
| translucent actors and HUD | 1.760 ms |
| room visibility and light selection | 1.959 ms |

`submit_us` is 58.103 ms p50 and contains room transform, lighting, clipping,
packet construction, and immediate TA submission. It is not a transfer-only
number. The trace records median values of 617 immediate PVR calls carrying
1,071,840 bytes, 327 visible groups, 9,155 room triangles, and 11,900 actor
triangles.

R3q answered the packet-construction-versus-copy question with a calibrated
nanosecond bracket around every `pvr_prim()` call. Real store-queue transport is
1.331 ms for the room and 1.249 ms for actors, 2.580 ms in total, which is 4.4%
of `submit_us` and 3.0% of the room path. R3q also showed the 2,048-entry room
vertex cache misses 15,350 times against a floor of 15,317 distinct vertex
indices, so only 33 misses per frame are evictions. The room path is close to
3.1 us per transformed and lit vertex across 15,350 of them; per-pass costs are
29.456 ms for 7,437 opaque triangles at 9,117 transforms, 0.135 ms for an empty
punch-through list, and 18.917 ms for 1,718 blended triangles at 6,233
transforms. Full method, overhead accounting, and limits are in
[R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md](R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md).

The R3p manual smoke reached simulation tick 558, sampled input 1,860 times with
a 12.484 ms maximum gap, and reported zero queue drops, simulation overruns, or
discarded simulation time. It did not inject combat controls and is not full
manual acceptance or a physical-controller latency result.

Post-load observed R3p main-RAM break-to-stack headroom is 5,570,560 bytes,
98,304 bytes below R3o because the two immutable normal buffers are fixed-size.
Heap used remains 159,268 bytes and observed heap free is 110,376 bytes. These
are steady-state snapshots, not loading, restart, stack, TA-overflow, or
fragmentation peaks. Add explicit high-water records before accepting memory.

Exact identities:

- source: `9dcd989370be7f083a9b66cfd19907fda627c893`
- KallistiOS: `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`
- kos-ports: `f4faacc42faaf552625777b7709e871a827e1055`
- compiler: `sh-elf-g++ 15.2.0`
- Flycast SHA-256: `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`
- corrected-character ELF: `c5ae9de436fd7b9f3770ce3e7cc40d1f37b8e2c000b3b9dfb9be5d46ce7c0e68`
- R3o autoplay ELF: `191676ca573aaaec9aed99bb33c88fca3102b1d90344a8e7c4020455bf1dfbdc`
- R3o manual ELF: `13857924539cec27012e1d6cdd46c9ec44ee17a5db942281b2f3caedaa3267ea`
- R3p autoplay ELF: `4fd89b4e929aca49a9cdc8b7e231c9a1e33ff387cac81466d42e0d49b686a44f`
- R3p manual ELF: `b265872f40b74f8fbe3cd5e7be28e4bcb73e8af2e54717d8cc5076f9ef91dd0a`

The R3q diagnostic option added preprocessor lines to `room/main.cpp`, so the
two R3p ELF hashes above reproduce only from the pre-R3q tree. The executable
code is unchanged: with `SUBMIT_PROFILE` unset the preprocessed translation unit
is byte-identical and the debug-stripped ELFs are
`932c1647a1901157474f238988167a49a5a84cdac9fe99d2b3b079fa4b84b7ad` for autoplay
and `570c36bdda2e440bc69eca4d573f4e89e0cad316063aa3b386db6eca1e7b042c` for
manual in both trees.

Evidence is retained in `d202` through `d224` under
`C:\Flycast-Evidence\re4-dreamcast`. Timing evidence for R3p is in `d219`,
the manual smoke in `d220`, and the qualitative framebuffer check in `d221`.
The R3q profile captures are `d222`, `d223`, and `d224`.
Physical Dreamcast timing remains pending.

## Measured bottleneck queue

Choose each next experiment from the current trace. Every candidate must boot,
retain a reference path where appropriate, pass its correctness check, record
before/after timing and memory, and end in a keep-or-revert decision.

1. **Per-strip bounds culling for unpartitioned alpha.** R3q measured the blended
   list at 18.917 ms for 1,718 triangles, transforming 3.63 vertices per triangle
   against 1.23 for the opaque list. All 22 blended batches already carry
   certified strips, so this is not a strip-coverage problem. R3k deliberately
   left the alpha materials unpartitioned to protect source draw order, so
   blended geometry sits in 17 groups with extents up to 273.83 m against a 35 m
   horizon. The pass references 77% of the package's blended strip vertices and
   emits 40% of its blended triangles; the depth and clip tests that discard the
   rest run only after the transform and lighting are already paid.
   Attach bounds to each strip and reject the strip before touching its vertices.
   Skipping a strip removes work without reordering any triangle that is still
   drawn, so the R3c blend-order certificate holds by construction; finer alpha
   cells would not. Bounds for the 2,067 blended primitives cost about 33 KB.
   Skipping the empty punch-through list is correct but worth only 0.135 ms; do
   not confuse the two.
2. **The per-vertex transform and light kernel.** R3q showed room cost is close
   to a constant 3.1 us per transformed and lit vertex, and that caching cannot
   reduce the 15,317 distinct vertices a frame touches. After the blended-list
   work, the remaining room lever is the kernel itself: inspect the SH-4 output of
   `mat_trans_single` plus the selected-light evaluator, consider batching
   transforms through the matrix unit, and keep the portable evaluator as the
   numerical reference with explicit bounds. Reducing the distinct vertex count
   is a package-level question about the one-metre child cells, which duplicate
   boundary vertices; it must be measured against the culling those cells buy.

3. **Actor preparation and lighting.** Add conservative render eligibility before
   pose work. Cache settled death poses and other unchanged inputs using explicit
   animation, transform, camera-relative light, selected-light, component, and
   material dependencies. Inspect SH-4 assembly and benchmark batch palette/
   selected-light kernels against the portable reference with numerical bounds.
4. **Submission transport: closed by R3q.** The KOS `pvr_prim` store-queue path
   costs 1.331 ms for the room and 2.580 ms in total. Bounded KOS DMA buffers
   cannot recover more than that even if they made the copy free, and they would
   add main-RAM buffers and pipeline latency. Do not revisit DMA without a trace
   in which transport is a materially larger share. Enlarging or re-hashing the
   room vertex cache is closed for the same reason: it can save at most 33
   evaluations per frame.
5. **Native texture/resource layout.** Extend the current package with offline
   twiddled payloads, explicit layout metadata, and one uploaded handle per deduped
   payload. Credit this to load time and memory unless a frame trace changes. Then
   evaluate `pvrtex` VQ, palette, and mip candidates per texture with native upload,
   previews, moving-scene review, and uncompressed fallbacks. Alpha edges, HUD,
   faces, and nearby architecture receive separate quality decisions.
6. **Gameplay/source parity in parallel.** Continue bounded source checks for
   collision narrow phase, camera blockers, state/RNG/event behavior, expressions,
   and cloth where they affect this encounter. They do not block independent
   renderer experiments, and known prototype defects are corrected against the
   GameCube reference rather than preserved.

The benchmark set must grow into repeatable movement, camera turns, aim extremes,
fire/reload, enemy attacks, Leon death, kill, and retry segments. Track p50/p95/
p99/max presented intervals, simulation debt/drops, input sample/edge latency,
audio-event timing, and memory high-water marks. Autoplay is engineering evidence;
final acceptance requires responsive human control and stock physical hardware.

## Targeted Dreamcast references

Use mechanisms, not borrowed performance claims:

- Pinned KallistiOS immediate `pvr_prim` already copies aligned packets through
  store queues; its optional DMA mode copies per-list packets into double-buffered
  main-RAM buffers before TA DMA. Benchmark the exact RE4 packet mix before choosing.
- The pinned KallistiOS `pvrtex` tool emits twiddled native payloads, mip chains,
  palette formats, VQ with adjustable codebooks, preview images, and a DMA-aligned
  `.DT` container. Reuse the mature encoder or its format rather than writing a
  compressor.
- SH4ZAM provides MIT-licensed SH-4 matrix/vector kernels and is available through
  kos-ports. Adopt only individual kernels that beat the current FTRV path on an
  RE4 fixture while satisfying the reference error bound; pin the adopted source.
- QuakeSpasm-DC demonstrates a native PVR renderer, direct geometry streaming,
  SH4ZAM math, fog, lighting, and mipmapped textures. Doom 64 DC demonstrates
  level-time texture caching and 8bpp world textures. Their layouts are study
  cases, not RE4 quality or frame-rate targets.

Primary references: [KallistiOS PVR scene path][kos-scene],
[KallistiOS pvrtex][kos-pvrtex], [SH4ZAM][sh4zam],
[QuakeSpasm-DC][quakespasm-dc], and [Doom 64 DC][doom64-dc].
## Objective and boundaries

Make the same post-s03 cabin encounter responsive and measure its cost on a
stock Dreamcast. The target is approximately 30 distinct presented game frames
per second at the current 640x480 presentation, with source-timed simulation,
responsive controls, and bounded memory. Feasibility at this fidelity remains
unproven. Do not promise 30 fps from the current data or a deadline for it.

Preserve camera coordinates/FOV, placements, selected geometry, texture detail,
lighting behavior, alpha, collision, combat timing, and audio events while
removing duplicated work. Recover the original decisions about which work to do
before designing replacement systems. Do not change the camera, horizon, meshes, resolution,
or light count to claim an optimization win. No new room, enemy, weapon, engine
framework, or primary ambience/game-over polish work enters this milestone.

The frozen build establishes native integration and a recognizable source-derived
presentation. It does not establish real-time playability or exact original-game
behavior. Its reduced state machines, RNG call sequence, sampled poses, rebuilt
normals, light selection, and incomplete camera blockers remain source-port debt.
Preserving current behavior is a regression check, not proof that it is correct.

## Two references and regression rules

The current Dreamcast regression reference is the accepted R3p build and its
exact room, texture, character, and toolchain identities. The original G4BE08
debug game is the authority for behavior and authored presentation. A pure target
optimization must match the accepted build at equivalent simulation snapshots;
a source-correctness fix may intentionally change it and must instead be checked
against the original game.

Keep the audio video at
`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2`
as the corrected-character presentation checkpoint. Keep the full timing traces
at `d204` and `d205`, the R3m visual sequence at `d203`, manual input traces at
`d206` and `d207`, R3n timing/visual evidence at `d208`, and R3o repeated timing
and visual evidence at `d209`. Keep corrected validation and candidate evidence
at `d216` through `d218`, accepted R3p timing at `d219`, the manual smoke at
`d220`, and the qualitative framebuffer check at `d221`. New candidates use
new directories and exact hashes. The
older `fed3e91`/manual-v3 package remains historical evidence, not the performance
baseline.

Use `tools/evidence_manifest.py` and the exact-identity discipline in
[SOULCALIBUR_REUSE.md](SOULCALIBUR_REUSE.md). Keep that other checkout read-only.
## Source architecture status

The original audit identified valuable GameCube mechanisms. Current disposition:

| Source mechanism | Dreamcast status | Remaining fidelity question |
|---|---|---|
| SAT block traversal and duplicate suppression | hierarchy, edges, traversal, and measured candidate integrated | original narrow-phase primitives, attributes, manager split, and matched query results |
| per-model light filtering and eight-entry order | target-side room/actor selection and compact evaluators integrated | matched original selected IDs/order and event-dependent changes |
| shared position/normal weight palettes | package v6 and runtime pose-palette reuse integrated | live source motion/state path and SH-4 kernel alternatives |
| render eligibility before preparation | source child bounds exist; actor preparation is still unconditional | source parent registration/visibility rules and conservative actor eligibility |
| authored BLK residency | source policy understood, current slice remains ROM-disk resident | converted active/staged working sets and intended storage path |
| source material/cull/alpha state | cull and SMX alpha-omit paths integrated; gradient order protected | remaining part alpha references, depth/blend variants, and matched images |

The decompilation determines behavior and authored state. Compiler-matching
constructs, PowerPC assembly, GX display-list execution, pointer ranges, and
fixed scratch addresses do not enter the SH-4 hot path unless they carry a
verified semantic requirement.

Keep original position, normal, UV-corner, material, weight, part, instance,
and source-object identities through conversion. Optimize their storage and
execution without welding by coordinate or flattening a source distinction that
changes deformation, shading, material state, or visibility.
## Completed checkpoint index

These records explain the current implementation and negative results; they are
not the task scheduler:

- R0/R1a: corrected frame/debt accounting, input service, bounded room cache,
  and transform/light reuse.
- R1b/R1c/R3e/R3f: source-selected and prepared room/actor lighting paths.
- R2a: source SAT hierarchy traversal with narrow-phase parity still open.
- R2b/R3h/R3i: source position/normal identities and shared pose palettes.
- R3b/R3c/R3g: native strips, protected alpha order, and packed actor colors.
- R3d/R3j/R3k: validated room normals, measured cache bound, and conservative
  source-child spatial cells.
- R3l: corrected complete character assembly and actor culling.
- R3m: source-authorized binary punch-through and alpha-child rejection.
- R3n: one source-ordered visibility/light-selection list reused across all
  room passes, plus immediate-call and byte telemetry.
- R3o: PVR polygon headers combined with their first payload; call count halves
  but the repeated median saving is only 0.12 ms.
- R3p: immutable actor-normal scratch fixes non-monotonic source-normal reuse;
  the `frsqrt` candidate is rejected because it is 0.822 ms slower.

Choose the next task from the measured bottleneck queue at the top of this file.
## 30 fps acceptance, separately from image/state comparison

Lock the reference route and additional stress cases before final measurement.
At stock 60 Hz output the target is one new game frame per two refreshes
(approximately 30 fps; use the measured refresh period rather than assuming an
exact 33.333 ms boundary). Report 50 Hz or other modes separately.

Require:

- At least a continuous 30-second encounter and three repeated runs, covering
  free movement, both aim extremes, near-wall views, fire/reload, kill, death,
  and retry across the runs. Include a live human controller check.
- Presentation IDs and simulation-snapshot IDs show new game updates at the
  target cadence, not repeated scanouts or an encoded-video frame rate.
  Report p50/p95/p99/max intervals, counts and durations of missed deadlines,
  and the warm-up/loading window separately. The accepted measured route has
  no missed two-refresh presentation deadlines.
- No discarded simulation time or input queue overflow. Record sample gaps,
  observed-input-to-tick and observed-input-to-present latency distributions.
  Input service should run at least once per refresh and the simulation consume
  eligible samples on the next fixed tick; verify these bounds on hardware.
  Report device polling uncertainty instead of calling observations physical
  button-contact timestamps.
- Audio events stay tied to simulation events, with measured audiovisual
  alignment in live output, including catch-up/restart cases. A loopback recording
  or post-edited capture offset alone does not prove synchronization.
- Native images remain faithful at matched simulation ticks; simulation state,
  source event order, and RNG/input identities remain equivalent for pure
  optimizations. Image-diff views include temporal motion/alpha/clipping review.
- Measured main RAM, VRAM, AICA, stacks, trace storage, and TA buffer peaks fit
  stock pools with a declared reserve and no allocation/overflow failures.

Use CPU/PVR overlap correctly when setting sub-budgets from the R0 baseline.
If any unavoidable stage alone exceeds the target interval, document it and
re-plan that stage. Do not multiply isolated speedups into a promised 24x result.
If the intact scene still misses the budget after these passes, present measured
remaining costs and options; a fidelity concession needs a separate decision.

## Scale after the same-encounter work

Start from authored BLK active/staged/remove sets and `checkBlockMemory`, recomputing
the largest active set and transition overlap using converted sizes and shared
resource identities. Do not introduce a guessed loading radius. Preserve original
load-stop behavior where applicable; seamless loading everywhere is not a source
requirement. Map staging/prefetch onto the selected Dreamcast storage/cache policy;
GameCube ARAM is not spare Dreamcast AICA memory.

Move from embedded ROM disk and mandatory `fs_mmap()` to bounded read buffers,
active room blocks, immutable shared resources, texture handles, and reclaimable
upload staging for the intended storage medium. A path change from `/rd/` is
insufficient; closing an embedded mapped file does not remove its payload from
the executable. Pre-twiddle textures offline for loading efficiency, without
crediting startup work as a per-frame saving. Expand residency now only if the
measured R1-R3 memory budget requires it.

Progress source ownership along the existing encounter: camera interactions,
player/enemy state transitions, random-call order, motion/IK, then events.
Separate source-fidelity fixes from optimization comparisons when they properly
change the frozen build's behavior or appearance. Keep the ledger classification
(original code, behavior-preserving adaptation, temporary approximation) current.
No expanded content until the runtime and resource model support it.

[kos-scene]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/hardware/pvr/pvr_scene.c
[kos-stats]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/hardware/pvr/pvr_misc.c
[kos-perf]: https://kos-docs.dreamcast.wiki/group__perf__counters.html
[kos-snd]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/sound/snd_mem.c

[re4-atari]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/atari.cpp
[re4-light]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/light.cpp
[re4-trans]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/trans.cpp
[re4-scroll]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/scroll.cpp
[re4-block]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/block.cpp

[kos-pvrtex]: https://github.com/KallistiOS/KallistiOS/tree/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/utils/pvrtex
[sh4zam]: https://github.com/gyrovorbis/sh4zam
[quakespasm-dc]: https://github.com/maximqaxd/quakespasm
[doom64-dc]: https://github.com/jnmartin84/doom64-dc
