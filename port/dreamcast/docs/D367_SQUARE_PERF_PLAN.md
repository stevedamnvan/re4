# D367 square performance plan: r101 at 15 fps real time

Owner: the D367 serialized perf lane. Started 2026-09-24 from the user's play tests. The repeatable loop
lives in the `re4-dreamcast-square-perf` skill. This file is the plan and the ledger: update the ledger
with every measured arm, and the plan when an item lands or is dropped.

## Persistent goal (user, 2026-09-24)

**This is the standing goal until it is reached. Iterate on this plan without deviating, unless a measured
better solution appears; then record the switch and why in the ledger.** Every session resumes here.

## Goal (user, 2026-09-24)

- **The r101 square must run at least 15 fps at real game speed, "at any cost, or the player can't play".**
  The one-Ganado house fight "felt heavy" too; quiet areas feel fine.
- The game runs one logic tick per 33.3 ms. With frame pacing (render skip), one drawn image per two ticks
  is 15 fps at real speed. So the budget per drawn frame is **2 x logic + render <= 67 ms** (hardware model).
  Exact form: **W + tau <= 66.7 ms**, W = a drawn tick, tau = a skipped tick (PACE_CATCHUP=2 still runs all
  logic, Trans, effects and iTask; it skips ModelRender, ModelTrans for the dropped image, TA and present).
  Measured directly by a square arm built with `PACE_CATCHUP=2 PACE_FORCE=2` (every second image dropped):
  the hwproject figure is then the mean of W and tau per tick, so W + tau = 2 x that figure.
- Never changed: collision, event sequencing, game state, AI decisions. Render-only changes keep the logic
  trace STRICT. FTRV/FIPR maths in logic is allowed as a measured option (deterministic, last-bit FP
  policy, collision checked separately). Parking far, unseen Ganados (ACT_CAP) is approved.

## Where the time goes (hwproject, r101-bell-fight room frames 1000-1119, Standard stack)

| arm | hw ms | render-side | actors | logic/tick | scenery | ui | 2L+R |
|---|---|---|---|---|---|---|---|
| sq0 base (tree5 play stack) | 120.9 | 29.9 | 28.5 | 26.6 | 19.7 | 8.8 | ~147 |
| sq1 ACT_CAP=6 | 115.8 | 28.1 | 28.3 | 23.1 | 20.0 | 9.0 | ~139 |
| sq2 ACT_CAP=6 + ACTOR_FOG_GATE | 114.2 | 27.3 | 29.9 | 21.4 | 19.9 | 8.4 | ~136 |
| sq3 ACT_CAP=4 + fog gate | 113.8 | | | | | | |

**Measured budget (2026-09-24, PACE_CATCHUP=2 PACE_FORCE=2, traced parities split):**

| arm | tau: skipped tick | W: drawn tick | W + tau (budget 66.7) |
|---|---|---|---|
| sq12: sq5 stack (VEC_INLINE, ACT_CAP=6, fog gate) | 45.3 | 106.2 | **151.5** |
| sq13: + CROWD_FLAT, COL_PREFETCH v1, FOG_FAR=18000, CROWD_NEAR=2/5 m/12 m | 45.8 | 99.3 | **145.1** |

What this means:
- Per-tick game work G (game-logic + game-render-side: logic, collision, EmAtCheck, effects,
  Trans/ModelTrans) is ~41 hw ms on **every** tick, drawn or skipped (skipped tick: 20.1 + 21.6; drawn:
  17.2 + 21.8). The drawn-only render R (actors, scenery, ui, copies) is ~60-65.
- **G alone is above 33.3**: even with nothing drawn, the square cannot run at game speed.
- 15 fps at real speed needs 2G + R <= 66.7, e.g. G ~22 and R ~22 (today 2 x 41 + 62).
- So a ms of G is worth two of R: logic items move ahead of render items (FTRV bones, collision,
  EmAtCheck/atchkCollect, effects, trig), and the render items still have to cut R by two thirds.
- Skipped-tick functions (sq12): partsWorldCalc 2.9, PSMTXConcat 2.1, atchkCollect 1.9, At_poly_line_ck
  1.6, MakeWeightPalette 1.2, sincos 1.1, PSMTXMultVec 1.1, EspDelete 0.8, Hermite 0.7. By file:
  EmAtCheck + scenery collision 7.4, skeleton maths 7, effects 3.5, Trans 2.9, motion 1.9.

**Retained work and normal baseline (2026-09-24, sq13 stack):**

| arm | what it runs | hw ms/tick | trace |
|---|---|---|---|
| sq15 | draws every tick (normal play) | **104.5** | render only vs tr2 |
| sq16 | PACE_CATCHUP=2 PACE_FORCE=A: every image dropped (no ModelRender, no ModelTrans) | **39.5** | STRICT tr2 vs tr3, 3277 ticks |

- 39.5 is the work retained per tick today, not an irreducible floor. Drawing adds 65.0 per image;
  ModelTrans for a kept image is ~6.3 (45.8 skipped-tick minus 39.5).
- Retained work by system: skeleton and matrix maths ~14-15 (partsWorldCalc 2.8, mtx_sh4 kernels
  Concat 1.6 / MultVec 1.1 / Inverse 0.6, math_sub RotMatrix/Hermite 3.5, trig 2.6, motion 1.9),
  collision ~8 (at_mod EmAtCheck 3.1 incl. atchkCollect 1.9, atari 3.1, at_sub 1.7), effects ~4.5
  (esp_sub, esp, est, esp48), cloth/pendulum ~1.6, IDSystem 0.9, remainder ~9.
- Milestones: 15 fps at full speed needs roughly 20 retained + 25 drawing (2 x 20 + 25 = 65; today
  2 x 39.5 + 65 = 144). 30 fps needs retained + drawing <= 33.3 in one tick (today 104.5).

## Retained-work savings table (2026-09-24, sq16 never-draw arm, 39.54 hw ms/tick)

Method: sq16 functions.tsv (cost columns) joined with the run's per-PC execution counts
(trace/counts.bin over the 120 counted ticks: entry PC = calls, loop-body PCs = iterations);
scratchpad tools retained.py / calls.py / loops.py. "Exact" = identical results (STRICT gate).
"Last-bit" = the FP policy with a shadow comparison of hit/grounding/collision decisions.
Residuals are estimates until measured; unknown rows need the counter build (next).

Where the time is, by kind: load-use stalls 7.1, I-cache misses 4.5, D-cache misses 3.5 of 39.5
(~15 ms waiting on memory); the rest is issue and FP dependency.

| # | item | measured now (hw ms/tick) | structure (per tick) | change | residual est. | saving est. | class |
|---|---|---|---|---|---|---|---|
| 1 | EmAtCheck candidate walks (atchkCollect) | 1.92 (dep_load 1.45) | 46.5 walks, 6975 node visits, 651 pass (91% rejected) | alive-order array with deep prefetch, or a maintained candidate list; same order | 0.3-0.6 | 1.3-1.6 | exact |
| 2 | Effect pool scans (EspDelete 0.78, ESP_IsActive 0.34, EfmDeleteSub 0.19, slot loops ~0.15) | 1.46 | 1024 slots per scan, ~421 live; ESP_IsActive 2048 calls | live-slot bitmap walked in index order | ~0.6 | ~0.8 | exact |
| 3a | Matrix kernels, bit-exact tuning | Concat 1.57, MultVec 1.05, Inverse 0.64, Copy 0.12 | 2580 / 4884 / 493 / 659 calls; scalar, no fmov.d pair moves, no FTRV/FIPR | pair moves for loads/stores, inlining the MultVec call | - | 0.2-0.4 | exact |
| 3b | Matrix kernels on FTRV | same | same | FTRV Concat / MultVec | Concat ~0.8, MultVec ~0.6 | +0.9-1.1 | last-bit |
| 4 | partsWorldCalc self | 2.79 | 94 calls, 2236 part matrices, 1118 on the non-uniform-scale path (3 fdivs each, 3550 fdivs) | parent reciprocal reused across children, loop restructure | 2.2-2.5 | 0.3-0.6 | exact |
| 5 | Repeated skeleton updates | part of the ~5.3 skeleton-world stage (4 + kernel share + TransMatrix 0.34) | 94 partsWorldCalc calls vs 13 motion updates: EmAtCheck recomputes after the push; object moves recompute static poses | skip when every input is bit-identical to the last computation | unknown | 0-2 | exact; counter build |
| 6a | Rotation from angles (low_RotMatrix 0.80, RotMatrix 0.56) | 1.36 | 1633 calls; GAME_ROT_CACHE hits ~8% | reuse on identical angles | unknown | 0-0.6 | exact; counter build |
| 6b | Trig (re4dc_sincosf 1.10, SINF 0.45, COSF 0.45, sinf 0.38, acosf 0.20) | 2.58 | ~4300 evaluations | FSCA | ~0.6 | +1.5-2.0 | last-bit |
| 7 | Motion (Hermite 0.73, MotionMoveCore 0.26, MotionMove 0.15, IK 0.31) | 1.45 | 13 models, 287 Hermite calls | scheduling | ~1.25 | ~0.2 | exact |
| 8 | Scenery collision tests (At_poly_line_ck 1.48, blkPolyLineCk + Core 1.48, lineOverlap 0.47, hitCheck2 0.40, hitCheckSphere 0.30, sphere/em line checks ~0.4) | ~4.5 | 1324 poly tests (179 insns each), 2465 block tests, 79 line queries | conservative block/poly rejection before the exact tests; same candidates and order | 3.0-3.7 | 0.8-1.5 | exact |
| 9 | Other collision (ObjHitCheck, atchkPasses, getPos, sce_at, dmg) | ~1.8 | per-pair work | - | ~1.6 | ~0.2 | exact |
| 10 | Effect behaviour for ~421 live effects (CommonMove, ChannelSet, esp48, ColorUpdate, AnmMove ...) | ~3.3 | RNG consumers, per effect per tick | layout/scheduling only | ~3.0 | ~0.3 | exact |
| 11 | Cloth/pendulum | 0.95 | - | - | 0.85 | ~0.1 | exact |
| 12 | Remainder | 8.15 | 853 functions; only 13 above 0.1 ms (2.26 total) | code layout / selective -O3 / LTO (an earlier I-cache relink lost) | 6-7 | 1-2 | exact, uncertain |
| 13 | Everything else in skeleton (getPartsPtr, workAt, partsMatCalc, PSVECNormalize ...) | ~2.3 | 1421 getPartsPtr, 2935 workAt calls | - | ~2.1 | ~0.2 | exact |

Totals (saving, hw ms/tick):
- Exact, measured-basis rows (1, 2, 3a, 4, 7, 8, 9, 10, 11, 13): ~4.4-6.0.
- + last-bit rows (3b, 6b): ~6.8-9.1.
- + unknown rows at their upper bounds (5, 6a, 12): up to ~13.
- **Best plausible retained work: ~27-33 hw ms/tick against the 14 target (25.5 needed) and the 15 fps
  milestone's ~20 (19.5 needed).**

Verdict: optimising the current per-tick work cannot reach 14 ms, and is unlikely to reach the ~20 ms
of the 15 fps milestone. The work scales with what the square holds each tick: ~2236 part matrices,
~421 live effects, ~150-node actor lists walked 46 times, 23 EmAtCheck bodies. At 30 fps every tick
draws, so deferring presentation work does not help there: 30 fps in the square needs the retained
work itself below ~20 with drawing under ~13, which this table does not support under the gameplay
constraints. For 15 fps at full speed, one architectural lever remains: skip presentation-only work on
skipped ticks (for example part matrices no gameplay code reads). Its size needs the consumer audit.

Next, in order: (1) counter build to settle rows 5 and 6a and list which part matrices gameplay reads
(collision, hit volumes, attach points, IK, events); (2) row 1, the largest exact item; (3) the bounded
skeleton experiment (3a, then 3b and 6b with the shadow check); (4) row 8.

## Skeleton audit (2026-09-24, GAME_SKEL_AUDIT counter build, tree5; last 1800 square ticks)

Arm tr4 (tr2 flags + GAME_SKEL_AUDIT=1): logic trace STRICT vs tr2 over 3035 ticks (read-only counters).
partsWorldCalc hashes every input (local/parent matrices, scales, flags, addRot, pos) and every output
before and after each call, per model; RotMatrix/low_RotMatrix note repeated angles per destination;
getPartsPtr notes callers by phase. Parser: scratchpad sa_parse.py (skill scripts).

Q1, repeated unchanged work: **rare.** 94.1 calls and 1390 parts per tick. Calls with bit-identical
inputs and untouched outputs since the model's previous call: 2.7 calls / 59 parts per tick (4%, crows
em28 and em26, same tick). Calls that changed nothing: 8.0 / 136 parts. 85 of 94 calls follow a real
mutation of the model's outputs or inputs. The redundancy is structural instead:

| caller (model) | calls/tick | parts/tick | pattern | dependency-tracking candidate | parts avoidable (est.) |
|---|---|---|---|---|---|
| MotionMove (em15 Ganados) | 14.5 | 493 | all 14 Ganados every tick, parked ones included | parked (unseen) Ganados: compute only the chains gameplay reads (collision parts 0/2 ...), the rest before a draw | ~200-270 |
| cEm10::move (em15) | 7.25 | 247 | second full pass after em10NeckMove / em10WaistMove (they read parts 1-4) | first pass limited to what is read before the second pass | ~150-210 |
| MotionMove + cPlayer::move (Leon) | 3.0 | 357 | three full 119-part passes per tick | same test between passes | ~119-238 |
| crows / em26 / objects | ~70 | ~290 | small models; 59 parts exact repeats | skip exact repeats | ~59 |

At ~3 us per part (partsWorldCalc self + Concat/MultVec/TransMatrix share) the candidates total
**~0.5-0.8 k parts, ~1.6-2.4 hw ms/tick**, each still needing a consumer proof (source + STRICT).

Rotation: RotMatrix 747 calls/tick, 59% all-zero angles (already served by GAME_ROT_CACHE), 21% same
angles as the destination's previous call; low_RotMatrix 886 calls, 12% repeats. Exact memo gain ~0.1-0.2.

Q2, observed part-matrix readers (getPartsPtr, per tick): collision cAtariInfo::getPos parts 0/2 (481),
MotionMoveCore parts 0-15 (286), MotionMove (65), em10 neck/waist parts 1-4 (36), cloth (16), weapon
attach cEmWep::setParentMatCalc parts 10/16/17 (11), Leon eye/waist/push/corner/damage (~10), plus
presentation readers ModelTrans (293, Trans phase), cLightInfo (137), ModelRender (103). Inlined copies
inside model.cpp and direct pList walks are not counted; one recording is not proof of non-use: every
candidate above needs source inspection of its readers before a STRICT experiment.

Q3, stacked: dependency tracking removes whole part updates, so it shrinks the base the matrix-kernel
(3a/3b) and partsWorldCalc (4) rows act on by the same ~35-50%: after it, 3a+3b fall from ~1.1-1.5 to
~0.6-0.9, row 4 from ~0.3-0.6 to ~0.2-0.4. The rotation memo overlaps FSCA (6b) by ~15%.

**Result: dependency tracking and reuse expose ~2 hw ms/tick (1.6-2.4), not the ~12-19 still missing.**
Revised best plausible retained work: ~25-31 hw ms/tick. The 14 ms allocation is not credible for the
square under the gameplay constraints; the 30 fps architecture and budget need an explicit revision.

## Revised approach: bounded architectural investigation (user decision, 2026-09-24)

30 fps stays the objective; 15 fps at full speed stays the intermediate gate. **The 14 ms retained
allocation is retired** (the audit does not support it). The audit justifies revising the engineering
approach, not changing encounters or accepting slow motion (both still rejected).

Budget identity, per second of game time with G = retained work per tick (every tick, 30/s) and R =
drawing cost per image at F images/s: **30 x G + F x R <= 1000 ms.** At G = 28 and R = 25 that is
6.4 fps, not 11-12. Drawing allowance R per image:

| retained work G | R at 30 fps | R at 15 fps |
|---|---|---|
| 20 ms | 13.3 | 26.7 |
| 25 ms | 8.3 | 16.7 |
| 28 ms | 5.3 | 10.7 |

Today: G = 39.5, R = 65.0 (sq16 / sq15).

Qualifications: the 1.6-2.4 ms structural skeleton saving is a hypothesis (reader coverage is
incomplete); 25-31 ms describes the opportunities identified so far, not an architectural limit.

Steps, in order, each measured in full:
1. **Exact collision candidate collection.** Replace the alive-list walks with maintained candidate
   data; measure the entire replacement (mutation hooks, invalidation, rebuilds, order preservation).
   STRICT.
2. **Compact skeleton processing prototype on one representative actor:** contiguous hot data, fewer
   pointer traversals, batched matrix work, dependency-aware partial updates. Measure the complete
   update including gathering inputs and writing results. Before omitting any work, audit direct AND
   inlined readers.
3. **Collision spatial structure prototype:** candidate order and exact final tests preserved,
   maintenance cost included; compared against step 1.
4. **Reassess the combined retained cost, then run the actor-rendering proof** against the matching
   allowance above.

Next checkpoint delivers: a measured retained cost G, the rendering allowance it leaves, and the
quantified remaining gap.

**Order revised (user, 2026-09-24, after the DCA3 / SH4ZAM study,
`C:\Game Dev\Emulators\re4-research\dca3-sh4zam-20260924\FINDINGS.md`):** compact collision candidates
(done, step 1) -> ordered active effects (live-slot index in slot order; slot reuse, iteration, RNG
unchanged) -> actor matrix composition (skin_position_matrix, 1.54 ms/frame in sq15, scalar
skin-to-screen preparation) -> one gameplay matrix chain (skeleton/collision, with the agreed numerical
and collision-decision checks) -> remaining part preparation (packet reserve/begin). Each complete
replacement is measured before stacking. Parked for the matrix-chain item: in partsWorldCalc's
uniform-scale path the concat's translation column equals the MultVec world bit for bit (same SDK
expression tree), so world can be read from the concat and MultVec + TransMatrix dropped; sibling
parts can reuse the parent's reciprocal scales.

### Step 1 result: GAME_ATCHK_LIST (2026-09-24)

EmAtCheck walked the EmMgr and ObjMgr alive lists 46.5 times per tick (~150 nodes each, 6975 node
visits, 651 candidates), stalled on each pNext load. The replacement keeps each list's order in an
array and rebuilds it only when the list changes: cManager.h bumps a generation on every list or
work-array change (deleteList, addListFront/Back, roomInit, arrayAlloc/Free, arrayPush/Pop, and the
demand-backed array_alloc/array_free in parts_bridge.cpp; a source search found no other pNext or
pAlive writer for these lists). Each call still tests every body's live m_flag / m_radius2 in list
order, with the next bodies prefetched, so the candidates and their order are unchanged. Caching the
candidate set itself is not exact: m_flag has 281 write sites (some through union views) and em10
rewrites m_radius2 every tick.

Complete cost, never-draw arms (PACE_FORCE=A), paired baseline sq17 (= sq16, 39.54):
- sq19 (kept): **38.42 hw ms/tick (-1.12)**. atchkCollect 1.92 -> 1.16 (walk incl. syncs), atchkPasses
  0.30 -> 0.18 (candidates now cached), EmAtCheck +0.02 (sync/rebuild), bumps not visible.
- Maintenance measured in the check build (tr5, =2): 30 rebuilds in ~197k list uses over the run,
  longest list 248 (array 320, no overflow), **0 mismatches** between the cached order and a list walk.
- Variants that did not beat it (the SH-4 has one fill in flight, so extra prefetches wait): radius
  pointers + array-line prefetch every entry (sq20, 38.85), unrolled blocks (sq21, 39.16: loads stall
  on lines still filling), array-line prefetch once per 8 (sq22, 38.79; prefetched the radius line,
  not the flag's), the same prefetching the flag line (sq23, 38.45 = sq19, more code). What remains of
  the walk is one body line per node per call: 7000 line touches per tick.
- Memory: 2.6 KB of data (two 320-entry arrays).

Checkpoint after step 1: **G = 38.4 hw ms/tick.** 30 x G alone is 1153 ms per second of game time, so
even with no drawing the square still runs slower than real time; the rendering allowance at 15 or
30 fps is negative. Remaining gap: G must fall another 13.4 ms (to 25, leaving R 16.7 at 15 fps) to
18.4 ms (to 20, leaving R 26.7 at 15 fps or 13.3 at 30 fps), and R from 65 to that allowance.

### Items 2-4 of the revised order (2026-09-24)

- **Ordered active effects: GAME_ESP_OWNER (committed 158b4d6), -0.33 retained.** A live-slot
  bitmap for the pool scans lost (sq25, +0.29: the ~421 live slots carry the cost, and the bit walk
  reloads globals around every call). What won is narrower: live esp slots are counted per owner
  bucket ((owner>>4 ^ owner>>10) & 63, maintained at PullEsp/PushEsp and every info.pEm write, and
  recounted after array alloc/free/push/pop), so EspDelete(c != 0) returns without scanning when the
  owner has no live effects (79% of 14336 calls). Slot order, reuse and RNG are untouched: nothing
  else changes. EspgenDelete (0.13) and EfmDelete (0.27) are the same shape but EfmDelete visits dead
  works by id, which cannot be tracked exactly; left as follow-ups.
- **Actor matrix composition: ACTOR_SKIN_FTRV (committed dd8c4aa), -1.03 drawn.** Render only;
  logic STRICT; 0.0007 px worst over 22.1M on-screen points (numeric check build, not screenshots:
  wall-clock screenshots are not tick-matched and differ by 30-70k px between two control runs).
- **One gameplay matrix chain, first exact attempt: GAME_PWC_FUSE dropped (sq29, +0.54).** Bit-exact
  (1.05M fused parts, 1.8M reused reciprocals) but only ~275 parts per tick take the uniform-scale
  path. The next candidate is an FTRV skeleton chain under the last-bit policy, with the agreed
  numerical checks plus a shadow comparison of hit, grounding and collision decisions.

**Checkpoint (option 3, after collision, effects and actor matrices):** G = **38.09 hw ms/tick**
retained (sq26, reproduced by sq30); drawing every tick W = **101.69** (sq28), so R = W - G = **63.60**.
The 15 fps real-time identity needs 2G + R = W + G <= 66.7: today it is 139.78, a gap of **73.1 ms**;
at 30 fps W <= 33.3 per tick, a gap of **68.4 ms**. The rendering allowance is still negative (30 x G =
1143 ms per second of game time before anything is drawn).

Attribution uses paired arms with one G (review 2026-09-24, re4-research/dca3-sh4zam-20260924/
CHECKPOINT_REVIEW.md; an earlier draft mixed the old G with the new W):

| pair | W | G | R = W - G | W + G |
|---|---:|---:|---:|---:|
| sq27 before FTRV | 102.72 | 38.09 | 64.63 | 140.81 |
| sq28 after FTRV | 101.69 | 38.09 | 63.60 | 139.78 |

Historical stack comparison (not a paced acceptance run): sq15/sq16 W 104.46, G 39.54, W + G 144.00 ->
139.78 now, **-4.22 ms**. The study items are each worth about a millisecond; none changes the order
of the gap. Allocations (not predictions) that keep both targets visible:

| retained G | R allowance at 15 fps | R allowance at 30 fps |
|---:|---:|---:|
| 20 | 26.67 | 13.33 |
| 25 | 16.67 | 8.33 |

against R = 63.60 today. The next architectural checkpoint must show a costed path for BOTH G and R,
with the unresolved gaps stated; another successful kernel alone does not establish it.

**Scope of the FTRV evidence:** tr12's 0.0007 px is the maximum over accepted synthetic probes (eight
corners 50 units around each bone, both results past the near plane, reference on screen), not over
rendered vertices, and it did not measure clipping agreement. Clipped triangles are rebuilt from
world_of + project, which never read the FTRV matrix, so the matrix reaches the image only through
each vertex's screen x/y, 1/w and outcode byte (cull / copy / clip decisions). The tr13 check build
compares exactly those, for every submitted skinned vertex, before any filtering: each skinned run of
records goes through the same vertex kernel a second time with the scalar-built matrix.

tr13 (ACTOR_SKIN_FTRV=2, r101 square, logic trace STRICT vs tr2 over 3237 ticks):
- Real vertices: 47.9M skinned vertices, run lengths identical, **0 nonfinite** in either path,
  **0 near-plane and 0 far classification differences**. The near plane was exercised: 207,840
  vertices behind it (clipped triangles) and 39,292 within twice the near distance. On-screen max
  difference **0.0017 px** (0 above 0.25 px); max over all vertices in front of the near plane
  (off-screen included) 0.0186 px; max relative 1/w difference 2.3e-6.
- 3 vertices out of 47.9M differ in a screen-edge outcode bit (a vertex within ~0.002 px of an edge).
  Screen bits only cull a whole strip when every corner is past the same edge, so the most such a
  flip can change is whether a strip lying entirely on the edge is dropped: nothing visible (the PVR
  scissors the rest).
- Synthetic probes, now counted before the filter: 18.0M points, 0 near-plane disagreements,
  0 nonfinite, max 0.0007 px.
Clipped geometry itself is identical by construction (world_of + project, which don't read the matrix).

**Bound on the next skeleton experiment:** Concat 1.53 + MultVec 1.04 + Inverse 0.63 = 3.20 hw ms/tick
in sq26, so even a free matrix kernel cannot supply 13-18 ms. The prototype covers one complete
representative actor update (compact hot inputs, parent-ordered batched matrix work, fewer
intermediate stores/reloads, only dependency-proven omissions), timed with input gathering, output
writes, the original fallback and validation separately; then the agreed hit / grounding / collision
decision shadow checks (candidate order and accumulated state included, not only a decision hash).
Report the whole-square change in G and the actor/type coverage before expanding it; one actor's
kernel speedup is not extrapolated.

Cost bound for the Ganado (sq26 per-call costs x call counts; skeleton audit part counts): Ganados
account for 740 of 1390 part-world updates per tick (MotionMove's two passes around IK on all 14,
plus cEm10::move's pass after neck / waist). A part costs ~3.1 us (partsWorldCalc self 2.1 +
Concat / MultVec / TransMatrix share), so **~2.3 ms**; local matrices (partsMatCalc: RotMatrix,
Trans, Scale, Copy) **~1.4**; motion keys (Hermite, MotionMoveCore, Fcc) **~1.2**; IK **~0.3**. A
complete Ganado skeleton update is **~5.2 hw ms/tick**, so even a free one is worth ~5 and a 2x
faster one ~2.6: the prototype cannot close the G gap alone, and the G route has to be assembled
from several items of this size.

Queued exact lead (collision, found while bounding): RotVector (Euler matrix via low_RotMatrix: up
to three SINF/COSF pairs, then MultVec) runs 770 times per tick, 675 of them from cAtariInfo::getPos,
which EmAtCheck repeats for every candidate body on each of its 46.5 calls although a body's offset
and angles rarely change between them. Cost ~1.85 hw ms/tick (getPos 0.28, RotVector 0.09,
low_RotMatrix 0.55, SINF/COSF 0.77, MultVec 0.16). RotVector is a pure function of the offset and
angle bits, so a value-keyed memo is exact. (The skeleton audit's 12% low_RotMatrix repeat rate
was measured per destination matrix, a stack temporary here, so it does not bound this.)

## 30 fps proposal adopted into this plan (2026-09-24, C:\Game Dev\Emulators\RE4_30FPS_PLAN_2026-09-24.md)

(Superseded in part by the revised approach above: the 14 ms allocation is retired.)

Engineering budgets (targets, not forecasts) for one tick: required simulation + shared model work
14, actor presentation 8, scenery 5, packets/copies/submission/HUD/system 3, margin 3.3. Order:
1. Explain the 39.5 retained ms by function and consumer (collision, attachments, hit volumes, events,
   AI, RNG, thermal scope, shadows); bypass only proven presentation-only work, STRICT.
2. Skeleton maths (FTRV/FIPR kernels, batching, reuse of unchanged outputs) under the last-bit FP
   policy with a shadow comparison of hit/grounding/collision decisions; compact collision candidate
   data with conservative rejection before the exact tests (order and ties preserved); effect
   bookkeeping without changing RNG, order or rate.
3. An integrated 8 ms actor path for Leon + the six active Ganados (submission, preparation, packets).
4. r101 scenery to a measured 5 ms (asset pipeline: compact groups, baked light, hidden-surface removal).
5. Serial integration; 15 fps at full speed as the intermediate gate, then 30 fps with no routine skips.
Knob sweeps (fog, prefetch, crowd tiers) no longer take the main effort.

Square census (ACT_CAP_LOG): 14 live Ganados, 6 active (all six must stay active: in view, in range,
engaged), 8 parked. Tighter caps gain nothing; the remaining logic is Leon, collision, effects and the six.

Top functions (sq0): re4dc_actor_submit 16.9, MeshDraw::draw 8.8, pass_lights 5.1, cModel::partsWorldCalc
4.2, PSMTXConcat 3.9, mesh_submit 3.4, vp::transform 3.1, atchkCollect 2.2, PSMTXMultVec 1.9.
Logic split: animation/skeleton ~10-11, vector helpers ~4.1, collision ~5.7, effects/cloth/AI ~6.

## Plan (in order; each item measured in the square before it goes on a user disc)

1. **Logic speed-ups, logic STRICT unless noted.**
   - a. GAME_VEC_INLINE: small PSVEC* routines inline (the SDK C bodies, same op order). Est. -1.5..-2/tick.
   - b. Collision fast paths with exact answers (At_poly_line_ck, blkPolyLineCk, cSatBlock::lineOverlap,
     hitCheckSphere): cheaper rejection before the exact test. Est. -1.5..-2/tick.
   - c. Bone matrices on FTRV (partsWorldCalc, PSMTXConcat/MultVec in logic): last-bit FP policy, measured,
     collision checked separately. Est. -4..-5/tick.
2. **Offline-converted enemies (DCA3 lesson: convert everything offline).** Ganado v4 blobs from
   design-ganado (prebuilt L0/L2/L2 Standard, L1/L2/L2 Low), no runtime conversion or LOD-build workspace;
   flat Ganado lighting. The same for em21/em23/em2a. Est. -6..-12 in fights, plus heap.
3. **Converted Standard room archive with per-part residency (DCA3 CdStreamDC model).** Drop the GameCube
   display lists and texture payloads that the native packages already replace; keep collision, map-object
   records, events, lights. First count every remaining walker of the GX geometry (thermal scope, shadows).
   Frees heap 4 (the r100 ambush is ~400 KB short) and load time.
4. **Single-version scenery (PS2 approach) with better textures.** One cheap mesh per tree/house instead of
   runtime distance levels (user: "we spend more time translating it at different viewing distances");
   512 VQ house shells with baked lighting; Standard fog 15-18 m with a painted backdrop. PS2 r100 scenery is
   77k tris vs GC 337k, one version per object (ps2-blender/ps2/ps2-summary.json). Review disc first.
5. **Visibility table (PVS) for the square.** It is walled in by houses; skip scenery and actor draws that
   cannot be seen from the player's zone. Measure the hidden share first.
6. **Queued disc reads** (64 KiB chunks, audio-aware): unavoidable in-play reads stop stalling frames.
7. **Selective -O3 / LTO build experiment** (DCA3 build policy): hot kernels -O3, cold code -Os.
8. **Pacing:** Fast is the default (user preference), PACE_CAP=2 so pictures may drop to 10 fps before the
   game ever runs slower than real time while the items above land.
9. **Knob sweeps first (free):** CROWD_NEAR/CROWD_NEAR_M/CROWD_MID_M/CROWD_MID_PX, MESH_LOD_PX,
   NATIVE_ACTOR_LOD_PX, FOG_FAR (Standard), measured in the square.

PS2 comparison (2026-09-24, emleon00.esl from BIO4DAT.AFS vs the GC list; probe enemy-census/ps2/):
the PS2 r101 roster is the GC roster (43 em15, 1 em26, 2 em28, same waves and positions). Differences:
entries 26 and 27 (two Ganados at x ~38.8 m by the far house) and em28 entry 78 start inactive (be 0) on
PS2, and entries 34-36 carry flag bit 0x80 with ch 0. So the PS2 did not thin the square's crowd; its
outdoor savings were draw distance, single-version scenery and effects (see memory notes).

Checked and dropped (2026-09-24):
- r101 draw-plan cache: 0 misses in the harness square. The play session's rejects built up over longer
  play; revisit only with a play log, since KOS has ~3 KB free there.
- Block model pool: it creates map objects (SMD, cObj id 2). Not droppable.
- "native parts run": the game's own cParts/cModelInfo/cEm/cObj work. Real state.

## Memory track (r100 post-house ambush, heap 4)

Census at the failure: heap 4 8,967,552 B, 3,968 B free. r100.dar 2.62 MB, enemy archives 1.62 MB, block
pool 1.13 MB, em12 hot motion 1.00 MB, parts work 0.92 MB, Standard scenery packages 0.77 MB, esp pool
0.34 MB (peak 538 of 1024 slots), prim buffer 0.32 MB (peak 223 KB). A loaded save reached r101
(minimum 389 KB free; one 530 KB event-data load failed without a crash). Target: half the GameCube's
headroom at the same point (Dolphin reference with the GC debug disc: `C:\Game Dev\Emulators\Dolphin`).
Fixes come from items 3 and 4 plus an esp pool cap.

## Ledger

Append one row per measured arm: date, arm, change, hw ms (2L+R), logic trace verdict, keep/revert.

| date | arm | change | hw ms | 2L+R | trace | decision |
|---|---|---|---|---|---|---|
| 09-24 | sq0 | base: tree5 play stack | 120.9 | ~147 | - | baseline |
| 09-24 | sq1 | ACT_CAP=6 | 115.8 | ~139 | approved change | keep |
| 09-24 | sq2 | + ACTOR_FOG_GATE | 114.2 | ~136 | STRICT (r100 fight, 6667 ticks) | committed 16f8356 |
| 09-24 | sq3 | ACT_CAP=4 + fog gate | 113.8 | - | - | no gain over 6 |
| 09-24 | tr1 | GAME_VEC_INLINE (SDK C_VEC* bodies inline, contraction off) | see sq5 | - | STRICT vs sq-tr0, 3018 ticks | keep |
| 09-24 | sq5 | sq2 + GAME_VEC_INLINE | 113.5 (-0.7) | - | STRICT (tr1) | committed d6282f5, in LH |
| 09-24 | sq6 | sq5 + CROWD_NEAR=2 CROWD_NEAR_M=5 CROWD_MID_M=12 | 112.6 (-0.9, actors) | - | render only | candidate (visual: more mid-tier Ganados) |
| 09-24 | sq7 | sq5 + MESH_LOD_PX=6 | 113.5 (0.0) | - | render only | drop: the Standard square scenery has no mesh levels to pick |
| 09-24 | sq10 | sq5 + CROWD_FLAT=1 (near-tier Ganados one light colour per part) | 111.6 (-1.9) | - | render only | committed 9547dc8 (user decision: flat Ganado lighting default in Standard) |
| 09-24 | sq11 | sq5 + GAME_COL_PREFETCH v1 (next block; poly record +2, vertex/normal +1) | 113.1 (-0.4; line tests -0.3, blkPolyLineCkCore +0.47 from the dependent record load) | - | gate queued | superseded by v2 (sq14) |
| 09-24 | sq12 | sq5 + PACE_CATCHUP=2 PACE_FORCE=2 (budget arm) | tau 45.3 / W 106.2 | W+tau 151.5 | - | the measured budget baseline |
| 09-24 | sq13 | sq12 + CROWD_FLAT + COL_PREFETCH v1 + FOG_FAR=18000 + CROWD_NEAR=2/5/12 | tau 45.8 / W 99.3 | W+tau 145.1 | - | render cuts barely move the budget: G dominates |
| 09-24 | sq14 | sq5 + GAME_COL_PREFETCH v2 (record +4, vertex/normal +2) | 113.0 (-0.5) | - | STRICT tr1 vs tr2, 3073 ticks | committed 4723dff, in LH |
| 09-24 | sq15 | sq13 stack, every tick drawn (normal baseline) | 104.5 | - | render only | the 30 fps baseline |
| 09-24 | sq16 | sq13 stack + PACE_FORCE=A (never draw) | 39.5 retained/tick | - | STRICT tr2 vs tr3, 3277 ticks | retained-work baseline |
| 09-24 | tr4 | GAME_SKEL_AUDIT counter build | - | - | STRICT tr2 vs tr4, 3035 ticks | exact repeats 4% of parts; structural candidates ~2 ms |
| 09-24 | sq17 | sq16 rebuilt (paired never-draw baseline) | 39.54 retained/tick | - | - | baseline for step 1 |
| 09-24 | sq19 | sq17 + GAME_ATCHK_LIST=1 (alive-list arrays, generation-tracked) | 38.42 (-1.12) | - | tr5 (=2 check build): STRICT tr2 vs tr5, 3277 ticks, 0 list mismatches; tr6 (=1) STRICT 3277 ticks | committed 1a3c91d, in LH |
| 09-24 | sq20-sq23 | walk variants (radius pointers, array-line prefetch, unrolled blocks, flag-line prefetch) | 38.85 / 39.16 / 38.79 / 38.45 | - | - | dropped: none beats sq19 |
| 09-24 | sq25 | sq19 + live-slot bitmap for the esp pool scans (EspMove/EspTrans/EspDelete/EspDeleteEvent) | 38.71 (+0.29) | - | - | dropped: EspDelete -0.15 but EspMove/EspTrans +0.27 (bit walk + global reloads around calls); the ~421 live slots, not the free ones, carry the cost |
| 09-24 | sq26 | sq19 + GAME_ESP_OWNER=1 (live esp slots counted per owner bucket; EspDelete(c != 0) returns when empty) | 38.09 (-0.33) | - | tr7 (=2): 14336 owner deletes checked, 79% early returns, 0 mismatches, STRICT tr2 vs tr7 3277 ticks; tr8 (=1) STRICT | committed 158b4d6, in LH. EspDelete 0.79 -> 0.14; EspMove/ESP_IsActive +0.09 (slot lines no longer warmed) |
| 09-24 | sq29 | sq30 (= sq26, 38.09 reproduced) + GAME_PWC_FUSE=1 (uniform-scale parts: world from the concat's translation column, MultVec + TransMatrix dropped; reciprocal scales reused per parent r_scale bits) | 38.63 (+0.54) | - | tr11 (=2): 1.05M fused parts and 1.8M reused reciprocals bit-identical, STRICT 3277 ticks | dropped: only ~275 parts/tick take the uniform path (MultVec 4884 -> 4610); the bit-compare memo added ~500 insns per call (float-to-int moves) |
| 09-24 | sq27 | draw every tick, sq15 flags + GAME_ATCHK_LIST (LH) + GAME_ESP_OWNER | 102.72 | - | - | drawing baseline for the actor matrix item |
| 09-24 | sq28 | sq27 + ACTOR_SKIN_FTRV=1 (skinned palette matrices through FTRV) | 101.69 (-1.03) | - | tr9 (=1, with ESP_OWNER) STRICT tr2 vs tr9, 3277 ticks; tr12 (=2): 22.1M on-screen corner points 50 units around each bone, max 0.0007 px, none above 0.25 px | committed dd8c4aa (render knob, default off). skin_position_matrix 1.52 -> 0.71 (378 -> 119 insns per build, 734 builds/frame) |
| 09-24 | tr13 | ACTOR_SKIN_FTRV=2 extended check: every submitted skinned vertex through the same kernel with the scalar matrix; probe near-plane / nonfinite counts before the filter | - | - | STRICT tr2 vs tr13, 3237 ticks | 47.9M vertices: 0 nonfinite, 0 near / far classification differences (207,840 behind near, 39,292 near band), 3 screen-edge bits, max 0.0017 px on screen; probes 0 near disagreements |
| 09-24 | sq9 | sq5 + NATIVE_ACTOR_LOD_PX=4 | 111.6 (-1.9, actors) | - | render only | candidate (coarser runtime levels for Leon too; superseded by v4 blobs) |
| 09-24 | sq8 | sq5 + FOG_FAR=18000 | 107.2 (-6.3: scenery -2.2, actors -2.5, ui -1.0) | - | render only | candidate for the nearer-fog + backdrop item (needs the review disc) |
