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
| 09-24 | sq2 | + ACTOR_FOG_GATE | 114.2 | ~136 | STRICT (r100 fight, 6667 ticks) | keep |
| 09-24 | sq3 | ACT_CAP=4 + fog gate | 113.8 | - | - | no gain over 6 |
| 09-24 | tr1 | GAME_VEC_INLINE (SDK C_VEC* bodies inline, contraction off) | hw pending (sq5) | - | STRICT vs sq-tr0, 3018 ticks | keep |
