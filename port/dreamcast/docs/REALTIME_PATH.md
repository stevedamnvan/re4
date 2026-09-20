# Fidelity-preserving real-time r100 plan

Updated 2026-09-20 from the corrected character build at `dba07e2` and the
measured R3m source punch-through candidate. This is the authoritative execution
plan. Earlier R0-R3 checkpoint documents remain evidence records; their letter
sequence no longer determines the next task.

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
cache, conservative one-metre opaque child cells, and source-authorized binary
punch-through. Do not propose these again as unimplemented work.

R3m is retained because it satisfies its bounded acceptance test: material 029
is binary alpha and carries the source SMX `alpha_omit = 0x80` override; all
gradient alpha stays blended. It preserves all source triangles and improves the
same full encounter route. See
[R3M_SOURCE_PUNCHTHROUGH_CHECKPOINT.md](R3M_SOURCE_PUNCHTHROUGH_CHECKPOINT.md).

## Current measured budget

Flycast measurements use the pinned 640x480 build and stock Dreamcast memory
sizes. They are emulator evidence. The comparison spans simulation ticks 30-1198
and includes source-timed turn, aim, fire, reload, enemy kill, the held result
view, and timed retry. The current autoplay does not cover free movement, aim
extremes, enemy contact, Leon death, or a human controller; those cases must be
added to the benchmark set and remain separate acceptance gates.

| Full-route metric | corrected-character baseline | R3m candidate |
|---|---:|---:|
| CPU frame p50 / p95 / p99 | 99.00 / 101.50 / 102.57 ms | 92.23 / 94.72 / 95.83 ms |
| presented ready-to-ready p50 / p95 / p99 | 100.09 / 102.59 / 102.60 ms | 83.41 / 100.10 / 102.60 ms |
| PVR registration p50 | 72.03 ms | 65.29 ms |
| PVR render p50 | 7.50 ms | 7.50 ms |
| dropped simulation time / overruns | 0 / 0 | 0 / 0 |

The candidate still presents at roughly 10-12 distinct frames per second. A
33.33 ms CPU frame needs another 58.9 ms median reduction and 61.4 ms at p95.
PVR raster time is not the dominant measured cost; SH-4 preparation and TA
registration are.

The R3m candidate median CPU stages are shown without adding the overlapping
`submit_us` aggregate to its children:

| Stage | p50 |
|---|---:|
| opaque room transform/light/clip/submit | 29.19 ms |
| binary plus blended alpha room work | 22.50 ms |
| actor lighting | 18.96 ms |
| opaque actor draw | 11.78 ms |
| actor pose palettes/projection | 5.82 ms |
| actor normals | 1.83 ms |
| translucent actors and HUD | 1.75 ms |
| simulation | 0.17 ms |
| camera | 0.15 ms |

`submit_us` is 65.30 ms p50 and contains room transform, lighting, clipping,
packet construction, and immediate TA submission. It is not a transfer-only
number. The next profiler revision must separate visibility, packet construction,
bytes submitted, TA registration, render completion, and presentation while
retaining render/simulation snapshot IDs.

A 25-second manual-build virtual-controller trace delivered five action edges,
with zero queue drops, a maximum queue depth of one, a 19.96 ms worst sampling
gap, and no discarded simulation time. A focused host-timestamped run observed
the fire state 158 ms after button-down and restart state 218 ms after button-down.
Those bounds include the current slow render cadence and host observation error;
they are not a human-controller or physical Dreamcast latency result.

Post-load observed memory for R3m is 5,640,192 bytes of main-RAM break-to-stack
headroom, 121,884 heap bytes used, 176,592 heap bytes free, 1,521,128 PVR bytes
free, and the KOS AICA query value of 1,378,336 bytes. R3m costs 94,208 bytes of
main-RAM headroom and 4,168 heap bytes versus the corrected-character baseline;
PVR and AICA values are unchanged. These are steady-state snapshots, not loading,
restart, stack, TA-overflow, or fragmentation peaks. Add explicit high-water
records before calling the memory budget accepted.

Exact identities:

- source: `9dcd989370be7f083a9b66cfd19907fda627c893`
- KallistiOS: `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`
- kos-ports: `f4faacc42faaf552625777b7709e871a827e1055`
- compiler: `sh-elf-g++ 15.2.0`
- Flycast SHA-256: `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`
- corrected-character ELF: `c5ae9de436fd7b9f3770ce3e7cc40d1f37b8e2c000b3b9dfb9be5d46ce7c0e68`
- R3m autoplay ELF: `1feacc30cdd072b3ca03ff976892013e6c21d4966d6eac1e7303cf12e9cb7ae4`
- R3m manual ELF: `1a45de49b10711fe83762b263dfe5fc91edac9daa6fbc5aaa3c4ac98f5c56688`

Evidence is retained in `d202` through `d207` under
`C:\Flycast-Evidence\re4-dreamcast`. Physical Dreamcast timing remains pending.

## Measured bottleneck queue

Choose each next experiment from the current trace. Every candidate must boot,
retain a reference path where appropriate, pass its correctness check, record
before/after timing and memory, and end in a keep-or-revert decision.

1. **Visibility and pass preparation.** Build one conservative visible source-child
   list per render snapshot, cache static bounds, source cull mode, light selection,
   and material pass classification, then reuse it across opaque, punch-through,
   and blended passes. Measure visibility separately. Preserve surviving alpha
   order and do not stop off-screen gameplay or event updates.
2. **Room and packet work.** With the visibility list in place, measure unique
   transforms, light evaluations, clipping crossings, headers, vertices, bytes,
   and TA calls per list. Reduce packet reconstruction/copying and exploit tighter
   native strips only where winding, clipping, and alpha order remain valid.
3. **Actor preparation and lighting.** Add conservative render eligibility before
   pose work. Cache settled death poses and other unchanged inputs using explicit
   animation, transform, camera-relative light, selected-light, component, and
   material dependencies. Inspect SH-4 assembly and benchmark batch palette/
   selected-light kernels against the portable reference with numerical bounds.
4. **Submission transport.** The current KOS `pvr_prim` path already uses store
   queues. Benchmark direct SQ against bounded KOS DMA buffers only after byte and
   call counts exist; DMA adds main-RAM buffers and pipeline latency. Preserve list
   ownership, clipping fallbacks, synchronization, and presentation ordering.
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

The current Dreamcast regression reference is the accepted R3m build and its
exact room, texture, character, and toolchain identities. The original G4BE08
debug game is the authority for behavior and authored presentation. A pure target
optimization must match the accepted build at equivalent simulation snapshots;
a source-correctness fix may intentionally change it and must instead be checked
against the original game.

Keep the audio video at
`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2`
as the corrected-character presentation checkpoint. Keep the full timing traces
at `d204` and `d205`, the R3m visual sequence at `d203`, and manual input traces
at `d206` and `d207`. New candidates use new directories and exact hashes. The
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