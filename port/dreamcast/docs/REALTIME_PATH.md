# Fidelity-preserving real-time r100 plan

Updated 2026-09-20 from the accepted R3r strip-culling build. This is the authoritative execution plan. Earlier R0-R3 checkpoint documents remain evidence
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
cache, conservative four-metre opaque child cells, source-authorized binary
punch-through, one source-ordered visible-room list reused by every material
pass, combined header/first-payload submissions, separate immutable actor
normal scratch, per-strip bounds culling, PVR packets written straight from
room cache entries, batch-local room vertex slots, prepared per-actor light
lists, offline-twiddled texture payloads, one-pass actor strip assembly, and
one PVR allocation per distinct texture payload. Do not propose these again as
unimplemented work.

R3m preserves source-authorized binary alpha while retaining gradient blend.
R3n reuses visibility, cull state, and room-light selection across material
passes. R3o combines each PVR header with its first payload, halving immediate
call count but saving only 0.12 ms. R3p fixes a source-normal identity defect by
separating transformed normals from lighting output. R3q changes no accepted
code; it profiles the room submission path and closes two candidates. R3r adds
per-strip bounds culling and corrects a projection error that made every frustum
test in the port too tight. See the corresponding checkpoint records, most
recently
[R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md](R3Q_ROOM_SUBMISSION_PROFILE_CHECKPOINT.md)
and
[R3R_STRIP_CULL_CHECKPOINT.md](R3R_STRIP_CULL_CHECKPOINT.md). R3s keyed the room
vertex cache on vertex identity, removed 21.5% of transform-and-light
evaluations, and was 1.274 ms slower; it is rejected and removed, see
[R3S_ROOM_IDENTITY_CACHE_CHECKPOINT.md](R3S_ROOM_IDENTITY_CACHE_CHECKPOINT.md).
R3t writes room packets straight from cache entries and packs the vertex colour
once per cache fill, 0.892 ms, and its calibrated profile attributes the room
pass to per-reference and per-strip overhead, see
[R3T_ROOM_PACKET_FROM_CACHE_CHECKPOINT.md](R3T_ROOM_PACKET_FROM_CACHE_CHECKPOINT.md).
R3u re-sweeps the opaque cell size now that strip culling exists and moves the
production package from one-metre to four-metre cells, 1.878 ms and 405,504
bytes of main RAM with byte-identical room pixels, see
[R3U_CELL_SIZE_RESWEEP_CHECKPOINT.md](R3U_CELL_SIZE_RESWEEP_CHECKPOINT.md).
R3v replaces the hashed room vertex cache on the direct-strip path with
batch-local slots renumbered at load, 2.580 ms for 413,696 bytes of static
RAM, see
[R3V_BATCH_LOCAL_SLOTS_CHECKPOINT.md](R3V_BATCH_LOCAL_SLOTS_CHECKPOINT.md).
R3w calibrates Flycast's SH-4 cost model and, guided by it, gives each actor a
contiguous prepared light list, 4.031 ms with bit-identical lighting, see
[R3W_PREPARED_ACTOR_LIGHTS_CHECKPOINT.md](R3W_PREPARED_ACTOR_LIGHTS_CHECKPOINT.md).
R3x slims the room slot to the seven words the packet needs and packs in the
same pass, 3.529 ms with identical counters and pixels, see
[R3X_SLIM_ROOM_SLOTS_CHECKPOINT.md](R3X_SLIM_ROOM_SLOTS_CHECKPOINT.md).

**Flycast cost model.** Measured in R3w: about 3.3 ns per non-memory SH-4
instruction including `fdiv` and `fsqrt`, about 13.3 ns per load or store, no
floating-point latency, no cache. Size a candidate by counting memory
instructions in its hot loop with `tools/sh4_loop_cost.py` before capturing
it. Hardware weighs the same code differently, so prefer changes that cut
both memory traffic and divides.

**Projection bias.** KOS `mat_perspective()` leaves `w = 1 - z_view`, so
`mat_trans_single()` divides screen coordinates by `depth + 1`. Any visibility
test that compares a view-space extent against the projected half-width must use
`(depth + 1) * tan(fovy/2)`, not `depth * tan(fovy/2)`. `group_visible()` had
omitted this since R3a and was discarding 35 on-screen groups and 684 triangles
per frame. The constant is `kProjectionDepthBias`; do not write a new visibility
test without it.

The rejected R3p subexperiment used KallistiOS `frsqrt`. A valid dual-path run
found a worst observed difference of one channel value in one packed color, but
the fast path was 0.822 ms slower at actor-lighting p50. It has been removed.

## Current measured budget

Flycast measurements use the pinned 640x480 build and stock Dreamcast memory
sizes. They are emulator evidence. R3p through R3x are matched over
simulation ticks 165-1194 and include source-timed turn, aim, fire, reload, enemy kill, held result
view, and timed retry. The current autoplay does not cover free movement, aim
extremes, enemy contact, Leon death, or a human controller; those remain separate
acceptance gates.

| Matched metric, ticks 165-1194 | R3p corrected normals | R3r | R3t | R3u | R3v | R3w | R3x | R4c | R4d | R4f accepted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CPU frame p50 / p95 / p99 | 86.217 / 88.719 / 88.814 ms | 74.139 / 74.238 / 76.701 ms | 73.247 / 73.378 / 75.838 ms | 71.369 / 71.463 / 73.929 ms | 68.789 / 68.883 / 71.326 ms | 64.758 / 64.809 / 67.294 ms | 61.229 / 61.289 / 63.781 ms | 60.791 / 60.874 / 63.343 ms | 57.951 / 58.015 / 60.509 ms | 57.565 / 57.641 / 60.127 ms |
| `submit_us` p50 | 58.103 ms | 45.901 ms | 45.008 ms | 44.413 ms | 41.832 ms | 41.832 ms | 38.319 ms | 37.890 ms | 33.391 ms | 33.006 ms |
| actor lighting p50 | 18.198 ms | 18.198 ms | 18.198 ms | 18.198 ms | 18.198 ms | 14.189 ms | 14.189 ms | 14.189 ms | 16.207 ms | 16.207 ms |
| opaque actor draw p50 | 11.789 ms | 11.789 ms | 11.789 ms | 11.789 ms | 11.789 ms | 11.789 ms | 11.789 ms | 11.430 ms | 9.900 ms | 9.595 ms |
| visible groups / room triangles | 327 / 9,155 | 362 / 8,208 | 362 / 8,208 | 142 / 8,315 | 142 / 8,315 | 142 / 8,315 | 142 / 8,315 | 142 / 8,315 | 142 / 8,315 | 142 / 8,315 |
| transformed and lit vertices | 15,350 | 10,156 | 10,156 | 10,404 | 11,008 | 11,008 | 11,008 | 11,008 | 11,008 | 11,008 |
| main-RAM break-to-stack headroom | 5,570,560 B | 5,308,416 B | 5,332,992 B | 5,738,496 B | 5,324,800 B | 5,324,800 B | 5,357,568 B | 5,357,568 B | 5,353,472 B | 5,353,472 B |
| dropped simulation time / overruns | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

R3r draws more room geometry than R3p because the corrected group test restores
groups that R3p discarded, and is still 12.078 ms faster at p50. R3u draws the
same room at four-metre cells: fewer groups to test, fewer references and
records, the same triangles, and byte-identical room pixels. R3v transforms
604 more vertices per frame than R3u, the cross-batch reuse the hashed cache
had captured, and is still 2.580 ms faster because each reference no longer
hashes, compares keys or re-verifies. R3w changes no emitted vertex and no
stage but actor lighting. R3x changes no emitted vertex and no stage but the
room passes. R4c changes no emitted byte at all, proved by a per-tick checksum
of the submitted stream, and no stage but the two actor passes. R4d changes no
source line at all: it is `-O3` plus link-time optimization. Note that its
saving is not uniform. Every drawing and submission stage improves and actor
lighting gets 2.018 ms worse, which is why actor lighting rises in this table
while the frame falls, and why a per-file optimization policy is now queued.

The accepted candidate presents at roughly 17 distinct frames per second. A
33.33 ms CPU frame needs another 24.2 ms median reduction and 24.3 ms at p95.
SH-4 preparation remains the dominant measured cost.

R3x median CPU stages are shown without adding the overlapping `submit_us`
aggregate to its children:

| Stage | p50 |
|---|---:|
| opaque room transform/light/clip/submit | 21.981 ms |
| actor lighting | 14.189 ms |
| opaque actor draw | 11.789 ms |
| actor pose palettes/projection | 5.820 ms |
| binary plus blended alpha room work | 2.735 ms |
| actor normals | 1.831 ms |
| translucent actors and HUD | 1.760 ms |
| room visibility and light selection | 0.806 ms |

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
- R3r autoplay ELF: `f3975be3408b2059d9c9557753d16a736d359a21d2d911e47a0d09a397bef35d`
- R3r manual ELF: `7137228e6287394cbec9e12c67438bd06282a19d5410f5dd76346bba50c9859c`
- R3t autoplay ELF: `ec841178108c67a1b607e2b7130091b33478e1abd6b8e55d0bb8b8986cc74c10`
- R3u production room package: `6b2bbf8f18a254d18abb773e511889798c9df0f5ad7d1337c49ad0104f05ac28`
- R3u autoplay ELF: `a7d6d00093a640ee61e385b07af4bfc4fc25f98ca751164e1fc50d2d4505ebb9`
- R3u manual ELF: `ba897fe1e27dd9fd7365597400a7e5feb504f66a088346033c29082cf7fb24d8`
- R3v autoplay ELF: `b75940e042b0e9c7f233802567c1a697cf06bcf6c4e10f8e56f8ae0a7dc151bc`
- R3v manual ELF: `7cf43e0e976138f2d29a0b692a60994a28cfa0c24db329bff7397de5a4ec9260`
- R3w autoplay ELF: `1f49b029e61492419e6e0b75652ba68d34528b7353144c3a6c866b83d9e5fbf3`
- R3w manual ELF: `fa036e868d40d224c5d1eff16a0536b509c8eac2d0e4524934e6db315f47d0e7`
- R3x autoplay ELF: `4ca5ab47734d936d5ac6e95e7cca48e2ce01c1720e0676da6a354601ddf42c97`
- R3x manual ELF: `73793fb4c8e04e9153a35fed433ffe2e40c16a960b4c21b8801d473543e8e957`

The R3q diagnostic option added preprocessor lines to `room/main.cpp`, so the
two R3p ELF hashes above reproduce only from the pre-R3q tree. The executable
code is unchanged: with `SUBMIT_PROFILE` unset the preprocessed translation unit
is byte-identical and the debug-stripped ELFs are
`932c1647a1901157474f238988167a49a5a84cdac9fe99d2b3b079fa4b84b7ad` for autoplay
and `570c36bdda2e440bc69eca4d573f4e89e0cad316063aa3b386db6eca1e7b042c` for
manual in both trees.

Evidence is retained in `d202` through `d257` under
`C:\Flycast-Evidence\re4-dreamcast`. Timing evidence for R3p is in `d219`,
the manual smoke in `d220`, and the qualitative framebuffer check in `d221`.
The R3q profile captures are `d222`, `d223`, and `d224`. The R3r captures are
`d225` through `d234`, including the culling audits in `d229` and the paired
framebuffer comparisons in `d226`, `d231`, and `d233`. The rejected R3s
identity-cache runs are `d235` and `d236`. R3t is `d237` through `d240`,
including the calibrated profiles in `d239` and `d240`. The R3u sweep is `d241`
through `d243`, its framebuffer check `d244`, and its manual smoke `d245`.
R3v is the cross-batch probe `d246`, timing `d247`, framebuffers `d248` and
manual smoke `d249`. R3w is the R3v loop profile `d250`, the Flycast
calibration `d251`, timing `d252`, the dual-path bit comparison `d253` and
manual smoke `d254`. R3x is timing `d255`, framebuffers `d256` and manual
smoke `d257`.
Physical Dreamcast timing remains pending.

## Measured bottleneck queue

Choose each next experiment from the current trace. Every candidate must boot,
retain a reference path where appropriate, pass its correctness check, record
before/after timing and memory, and end in a keep-or-revert decision.

1. **Memory instructions in the per-record loops.** Under the calibrated
   model every remaining CPU stage is priced by its memory instructions. The
   opaque room pass is 21.981 ms after R3x slimmed the slot fill and merged
   the pack pass; what remains there is the transform-and-light body itself
   (vertex loads, static light loads, `mat_trans_single` register traffic,
   `shade_color`) and the per-strip overhead of the sphere test, whose basis
   and eye globals are reloaded per strip. Actor lighting is 14.189 ms
   after R3w with 66 memory instructions per normal. R4g gives the target
   here: at `-O3` the per-normal loop body is 654 instructions and 166 memory
   operations against 297 and 66 at `-O2`, doing identical floating-point work,
   so a loop the optimizer cannot inflate is worth up to 2 ms. The build-policy
   routes to that saving are closed, and so is caching per-entry inputs.
   [R4H](R4H_NORMAL_NORMALIZATION_HOIST_CHECKPOINT.md) hoisted normalization to
   one call per source normal, proved it bit-exact over 15.8 million entries and
   measured it 0.240 ms *slower*: the transformed normal is reused 1.095 times,
   and a cache at that reuse factor costs more memory traffic than the 721
   duplicate normalizations it removes. Per-position reuse of the point and spot
   terms is the same trade with a worse constant, reuse 1.133 over a payload
   several times larger and scattered rather than streamed, so it is recorded
   there rather than built.
   [R4I](R4I_LIGHT_RECORD_TRAFFIC_CHECKPOINT.md) then gave each light type its
   own record, keeping selection order through an ordered code stream, and
   measured it 0.487 ms slower with bit-identical output over 16.1 million
   entries. It disproves the premise it was built on: the loop's memory
   instruction count is 166 before and 169 after, because a 60-field record
   never forced a load of a field the code does not mention. Record size
   affected addressing, not load count, while the dispatch cost a byte load and
   a branch per light per entry. What is left is narrower. Both actors run
   exactly four lights from one unchanging selection mask each, Leon
   directional, directional, directional, spot and Ganado directional, point,
   directional, point, so a bounded specialization of those observed sequences
   as straight-line code, with the general evaluator retained as a fallback for
   any other selection, is the next branch. It preserves accumulation order by
   construction. R4i also establishes two facts that survive its revert:
   premultiplying a directional light's colour by its intensity is bit-exact,
   and an ordered code stream preserves the accumulation sequence exactly. `project_character()` is 5.820 ms
   at roughly 200 memory instructions per position and the actor packet loop
   in `draw_character()` 11.789 ms; both should be read the same way. Count
   with `tools/sh4_loop_cost.py`, change the data layout, keep the arithmetic
   identical, and prove it with a dual-path bit comparison as R3w did. Strip
   count is not the lever: split vertices bound opaque strips at about 65% of
   the current count.
1b. **Batch-local tables into the package.** R3v builds its local index and
   batch vertex tables at load and holds 413,696 bytes for them. Emitting
   them from the converter as 16-bit local strip indices plus a batch vertex
   table would shrink the package and remove the load pass. This is memory
   work with no expected frame change; do it before any candidate that needs
   the RAM back.
2. **Room partition: cell size is settled, strip length is not.** R3u re-swept
   2 m, 4 m and 8 m after strip culling existed and took 4 m; 8 m ties it and
   2 m is 0.5 ms worse. Do not re-sweep cell size without a change to the cull
   tests. The converter's strip split is the open package-level lever: 12,625
   strips for 30,895 triangles is 2.4 triangles per strip in the package and
   2.7 per visible strip. Longer strips reduce the 2,242 ns per-strip term
   directly and the per-reference term through fewer duplicated boundary
   vertices, but they must keep the alpha materials unpartitioned and in source
   order, and any restrip must be verified by the existing ordered-strip
   certificate.

3. **Actor preparation and lighting.** Add conservative render eligibility before
   pose work. Cache settled death poses and other unchanged inputs using explicit
   animation, transform, camera-relative light, selected-light, component, and
   material dependencies. Inspect SH-4 assembly and benchmark batch palette/
   selected-light kernels against the portable reference with numerical bounds.
   The DCA3 audit names this the first rendering experiment and bounds it:
   A1a merges eligibility and packet assembly into one rewindable pass over an
   actor strip, the room-side strategy R3x already accepts; A1b emits compact
   draw recipes offline only if assembly is still material; A1c derives
   conservative pose-aware bounds, never rest-pose ones. Measure preparation and
   draw together so an emission win paid back by preparation is rejected, and
   preserve `kProjectionDepthBias` and the existing fallback exactly. Its A3
   entry permits batching the directional light subset only, never replacing
   RE4's point and spot terms. See
   [DCA3_SOURCE_AUDIT.md](DCA3_SOURCE_AUDIT.md).
3b. **Build policy: done, and it was the cheapest 2.839 ms on this list.**
   `-O3` with link-time optimization is now the default, measured in
   [R4D_BUILD_POLICY_CHECKPOINT.md](R4D_BUILD_POLICY_CHECKPOINT.md). There was
   no optimization setting on the link line at all beforehand. `-O3` alone is
   worth 2.606 ms and LTO adds 0.233 ms on top; LTO without `-O3` is worth
   nothing. A per-file optimization policy was considered and rejected: RE4DC
   has seven translation units and one of them holds nearly all the frame work.
   The measurement overturned that: actor lighting is 2.018 ms *slower* at
   `-O3`, so splitting the prepared-light evaluators into their own unit at
   `-O2` looked worth up to 2 ms. **It is not, and this line of work is
   closed.** Three routes were measured and all failed:
   [R4F](R4F_BUILD_POLICY_REFINEMENT_CHECKPOINT.md) rejected a per-function
   `optimize("O2")` attribute, which makes the stage 2.968 ms *worse* by
   blocking inlining, and seven `-O3` sub-flag arms, which leave actor lighting
   at 16,207 us to the microsecond;
   [R4G](R4G_ACTOR_LIGHTING_UNIT_CHECKPOINT.md) built the translation-unit split
   itself and measured it 0.160 ms slower, then explained why. Compiled in its
   own unit the kernel is 708 instructions at `-O2` and 704 at `-O3`, against
   560 inside `main.cpp` at `-O2`: the advantage was never the optimization
   level, it was the interprocedural context `main.cpp` provides, and any split
   that holds its own optimization level must also cut that context off.
   One flag did pay, `-fno-predictive-commoning`, worth 0.386 ms elsewhere, and
   is adopted. `-ffast-math` and friends remain out of scope and unneeded.
4. **Submission transport: closed by R3q.** The KOS `pvr_prim` store-queue path
   costs 1.331 ms for the room and 2.580 ms in total. Bounded KOS DMA buffers
   cannot recover more than that even if they made the copy free, and they would
   add main-RAM buffers and pipeline latency. Do not revisit DMA without a trace
   in which transport is a materially larger share. Enlarging or re-hashing the
   room vertex cache is closed for the same reason: it can save at most 33
   evaluations per frame.
5. **Native texture/resource layout, now the first R4 deliverable.** The
   offline twiddled payloads and explicit layout metadata are done and measured
   in
   [R4B_NATIVE_TEXTURE_LAYOUT_CHECKPOINT.md](R4B_NATIVE_TEXTURE_LAYOUT_CHECKPOINT.md):
   a 60x cut in texture upload time and no per-frame, VRAM or image change, as
   predicted. One uploaded handle per deduped payload is still open. Then
   evaluate `pvrtex` VQ, palette, and mip
   candidates per texture with native upload, previews, moving-scene review,
   and uncompressed fallbacks, choosing the representation per texture from
   the asset inventory in
   [R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md). Alpha edges, HUD,
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
- DCA3 (GTA III/VC on KallistiOS) is the residency and streaming reference for
  R4: offline asset conversion and archive repacking, a Dreamcast CD streaming
  path under the original streaming system, and a continuously changing
  working set on the same 16 MB / 8 MB / 2 MB target. Mechanisms only; check
  the licence before any code reuse and never use its data. `vendor/librw` is
  MIT, the game-side files are not covered by it. The audited mechanisms, their
  pinned source regions and the RE4DC backlog they imply are in
  [DCA3_SOURCE_AUDIT.md](DCA3_SOURCE_AUDIT.md), reconciled against this branch
  rather than the revision it was written for.

Primary references: [KallistiOS PVR scene path][kos-scene],
[KallistiOS pvrtex][kos-pvrtex], [SH4ZAM][sh4zam],
[QuakeSpasm-DC][quakespasm-dc], [Doom 64 DC][doom64-dc], and for R4
[DCA3][dca3].
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
- R4a: the asset inventory tool and the previously untracked r100 texture and
  HUD build recipes.
- R4b: `re4tex` carries a payload format and the converters twiddle offline, so
  the SH-4 no longer reorders 2.6 MB of texels at load; upload falls from
  1,022,663 us to 16,945 us with no frame, memory or image change. The first
  attempt did not boot because the room Makefile had no header dependency
  tracking, which is now fixed for every package header.
- R4c: actor direct strips are assembled in one rewindable pass instead of a
  separate eligibility scan followed by an emission walk, the DCA3 audit's A1a.
  0.429 ms off the frame with a byte-identical submitted stream over 524 ticks.
  Framebuffer capture at fixed ticks is not valid evidence for a change that
  alters frame cadence; the `SUBMIT_DIGEST` build exists for that reason.
- R4d: `-O3` plus link-time optimization on both the compile and the link, the
  DCA3 audit's A2. 2.839 ms off the frame for no source change, with the stream
  proved byte-identical across 508 ticks, 7,396 more bytes of text and one page
  less free main RAM. Actor lighting regressed 2.018 ms under it, which is the
  measured case for a per-file optimization policy.
- R4e: one PVR allocation per distinct texture payload instead of one per
  descriptor, the DCA3 audit's B1. 1,509,728 bytes of texture memory recovered,
  36.7% of the total, with the frame and the framebuffers unchanged.
- R4f: `-fno-predictive-commoning` adopted for 0.386 ms. The actor-lighting
  regression R4d introduced is unexplained and unrecovered; the per-function
  optimization attribute and seven sub-flag arms all failed, and those routes
  are closed. Also establishes that a stream digest covers polygon headers, so
  a digest baseline must come from the same texture-allocation regime.
- R4g: the actor-lighting translation unit, built and reverted at 0.160 ms
  slower. Its value is the explanation: the kernel's `-O2` advantage comes from
  compilation context inside `main.cpp`, not from the level, so no split can
  keep it. Attacking the regression now means restructuring the per-normal loop,
  which belongs to queue item 1.
- R4h: normalization hoisted out of the per-entry loop, built and reverted at
  0.240 ms slower, with the dual-path comparison bit-exact over 15,786,387
  entries. It closes per-entry input caching on this loop by measuring the reuse
  factor, 1.095 for the normal and 1.133 for the position, and adds a reusable
  512-byte SUBMIT_PROFILE telemetry layout to the capture reader.
- R4i: type-specific prepared-light records with an ordered code stream, built
  and reverted at 0.487 ms slower and bit-identical over 16,127,220 entries. It
  closes the general compact representation by showing the loop never loaded
  irrelevant fields in the first place, and leaves a bounded specialization of
  the two observed four-light sequences as the next branch.

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

## Scale Gate: when the boot-forward track opens

An intermediate gate between the single-room optimization phase and broader
game integration. It does not relax the final target: the approximately 30 fps
/ 33.3 ms stock-Dreamcast goal above remains the final performance gate unless
later physical-hardware evidence prompts an explicit separate decision.

The gate is met when all of the following hold:

- The accepted r100 encounter sustains roughly 20 fps under representative
  gameplay, measured as about 50 ms or better p95 frame time. A 20 fps average
  does not qualify.
- No dropped simulation time, no simulation overruns, no input-queue loss.
- Human-controlled movement, camera turns, aim, firing, reload, enemy contact,
  death and retry are responsive and correct.
- R4 has demonstrated one real room-to-room transition through the intended
  residency model: next-room resources loaded through the R4 path, transition
  peak RAM, VRAM and AICA measured, resources unique to the previous room
  reclaimable, shared resources still valid, and no reliance on keeping both
  complete rooms permanently resident.

Once met, open a boot-forward integration track from the game's normal startup
toward the beginning of Disc 1, running in parallel with continued renderer and
performance work. It must reuse the existing Dreamcast renderer, collision,
animation, audio, texture and R4 residency systems: no second gameplay or
rendering implementation and no scene-specific framework. The cabin stays a
permanent regression and performance fixture as further representative scenes
are added.

The trigger is stable representative play at about 20 fps plus one correct
streamed room transition. VQ completion, the full PS2 comparison database and
campaign-wide streaming are explicitly not prerequisites.

## Scale after the same-encounter work: the R4 workstream

The residency and streaming work is now a named workstream with its own plan,
[R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md): convert every
resource offline into its Dreamcast-native representation, keep only the
active and prefetched working set resident, derive residency from the
authored GameCube block sets, take DCA3 as the Dreamcast streaming reference,
and use the PS2 disc only as an oracle for Capcom-authored reductions when the
GameCube representation cannot meet the budget. Its first deliverables, the
asset inventory tool and the native texture layout, can run alongside the
remaining R3 frame work; the residency model and asynchronous reads follow.
The paragraphs below remain the source-side rules R4 must respect.

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
[dca3]: https://gitlab.com/skmp/dca3-game
[doom64-dc]: https://github.com/jnmartin84/doom64-dc
