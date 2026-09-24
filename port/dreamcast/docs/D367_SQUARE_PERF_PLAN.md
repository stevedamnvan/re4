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

## 30 fps proposal adopted into this plan (2026-09-24, C:\Game Dev\Emulators\RE4_30FPS_PLAN_2026-09-24.md)

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
| 09-24 | sq9 | sq5 + NATIVE_ACTOR_LOD_PX=4 | 111.6 (-1.9, actors) | - | render only | candidate (coarser runtime levels for Leon too; superseded by v4 blobs) |
| 09-24 | sq8 | sq5 + FOG_FAR=18000 | 107.2 (-6.3: scenery -2.2, actors -2.5, ui -1.0) | - | render only | candidate for the nearer-fog + backdrop item (needs the review disc) |
