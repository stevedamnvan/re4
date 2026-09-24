# D367 handover: all workstreams on hold (2026-09-24)

The user put every workstream on hold at this point. This document is the resume entry: read it first, then the
`re4-dreamcast-d367` skill, then the owning area's `STATE.md` under `/root/probe/d367-agents/<area>/`. Each agent was
told to stop at a safe point, stop its own processes by PID, delete discs/stage dirs (evidence kept) and write its
STATE.md as a handover.

- Branch `dreamcast-port`, HEAD at hold time: the commit that adds this file (parent `8ac9f2d`).
- Working tree: the 75 inherited dirty files stay untouched; never broad-stage, reset or clean.
- Canonical build recipe: `port/dreamcast/tools/d367/README.md` ("Canonical recipe": LH + M1 + PERF lines).
- Route plan and decisions: `D367_THIRTY_FPS_ROUTE.md`; asset pipeline and the Standard runtime contract (s16):
  `D367_ASSET_PIPELINE.md`.

## Where the game is

| Milestone | State |
|---|---|
| m1: r100 disc | **Done and verified** (84fc8ff): title (2026 art) -> picker (text visible) -> intro -> s40 -> radio call (subtitles) -> r100 play (~15 fps Flycast) -> inventory -> typewriter save to VMU. Player copy: `D:\RE4DC-Play\m1-final\{gdi,cue}` (lacks 16 em15 motion keys, so it halts if r101 is ever entered; restage before an r101-capable disc). |
| r100 -> r101 door | ARAM fix works in Flycast (east swap passed, runs reached the truck), not yet committed at hold time; see Blockers. |
| r101 | Loads by direct entry ([ROOM] 0x01) on the canonical recipe; **resets ~1 s after the first-visit Hunnigan call** (4/4). |
| r103 | Plan only (user: "work on this plan but don't implement"). |
| Performance | r100 8-Ganado fight ~125 hw ms/frame after this session's cuts; target 50 ms (20 fps). |

## Critical path and blockers

1. **ARAM block swap (area `blockswap/`): fix ready, one gate open.** Root cause: the port had no ARAM backing;
   `ARQPostRequest` (audio_stub.cpp) ran the callback without copying, so area blocks sent to ARAM were dropped and
   ARAM_TO_MRAM handed back stale buffers (HALT model.cpp calcModelAddr, OSPanic scheduler.cpp:45, or a silently
   bad block). Fix: GD-ROM as ARAM; ARAM loads record address/size only, ARAM_TO_MRAM re-reads the unit's own file
   blocking on the game task (same logic tick as GC). Patch `blockswap/bswap-aramdisc-v3.patch`, sha256
   `59d920ef2f88a654ec9e83a78285e8fd0ef3ee365a29f34c987f9d9dc5f061a2`, no knob, touches `src/game/datactrl.cpp` and
   appends `re4dc_aram_file_read` to `platform/dvd.cpp`; applies (`--check` and `--cached --check`) at 8ac9f2d.
   Gates passed: swap in both orders, hash proof (r100_00 out, r100_03 back = disc bytes), STRICT frames 0-5776,
   after-swap diff only in object-set fields (base built block 3 from stale bytes), knob-off identity (build-time
   string only). Census after swap: heap 4 90,752 free, KOS 6,632, VRAM 28,616. Hitch: est. 0.4-0.45 s on real
   GD-ROM (one long frame per swap). **Open gate:** reaching the r101 door; the east-walk padscript sticks at a
   fence by a car in base and fix alike (waypoint problem; three detour padscripts staged, unrun). Commit after
   that gate. Test-only diag: `bswap-diag-v9.patch` (sha `004353cb…`). Open hazard: event-file MemorySwap calls in
   r100, r101, r117, r11c, r10b are a separate path. Evidence `bswap-A1`, `bswap-B1`, `bswap-Bs1`.
2. **r101 first-visit call reset (area `subscreen2/`).** Sub-screen type 20; 1 MB texture claim fits; ss_term,
   op01.das, ss_oc112 load; six `ESP_CTRL : CTRL_ID[..] is invalid`; guest resets with no fault line. r100's call
   (same type) works. **Leading hypothesis (unproven):** the sub screen keeps calling EspgenMove over the room's
   effect pool `EspgenArray` (heap 4, EspgenArrayAlloc game.cpp:528); if that pool lies inside the swapped 3 MiB
   window it is overwritten by the codec files, giving the invalid CTRL_IDs and then a call through a garbage
   pointer. Next: fixture log of the pool address vs the window at swap_open; if it overlaps, give the sub screen
   an empty controller pool while open and restore at close. Evidence `r101-direct-canon`, `r101-direct-canon2`.
3. After both: frontier east walk to the r101 door on the canonical recipe, r101 census, then r101 to the bell.

## Parked patches (not committed; none passed every gate)

Paths are under `/root/probe/d367-agents/`. Rebase anything whose base is older than 8ac9f2d before landing.

| Patch | sha256 | Base | Missing gate |
|---|---|---|---|
| `blockswap/bswap-aramdisc-v3.patch` | `59d920ef…61a2` | 5f32de5 (applies at 8ac9f2d) | r101 door reached |
| `hwcal/hwcal-disc-v3.patch` | `77ec6409…cc76` | applies at 8ac9f2d | finished disc run on current build; PREDICTIONS.md; HOW-TO-RUN in `hwcal/scripts/` |
| `subscreen2/wip-uiorder.patch` (SS_UI_ORDER) | `f75a4439…df53` | 471fd72 | codec screenshot, sub-screen hw ms, rebase (inventory fixed, STRICT over 6,290 samples) |
| `std-runtime/patches/item20-tree-impostor-84fc8ff.patch` | `e12cfb12…8125` | 84fc8ff (applies at 8ac9f2d) | hwproject fight window (quiet 96.1 -> 90.5 hw ms; STRICT 5,853 ticks) |
| `std-runtime/patches/item21-house-shells-84fc8ff.patch` | `3af4c52b…f51bf` | after item 20 | run with textured packages |
| `std-runtime/patches/std-assets-wip-84fc8ff.patch` | `229f2710…8362` | 84fc8ff | WIP; low/FILE_01/02 were rejected ("level error"); asset side fixed in 45138ce, restage and rerun; rejection fallback to Original untested |
| `vmu/kit-autoload-wip2.diff` (DBG_AUTOLOAD narrow starts) | `f8df61ad…67a1b2` | tree7 on 5f32de5 | rebase; gates A/B/C; its staging halts at r100 entry (213 texture opens fail, watchdog main.cpp:548) |
| `actors30/actor-fog-gate.patch` (ACTOR_FOG_GATE) | `9b3e1b3d…d0b` | 8ac9f2d | STRICT only over 629 ticks; n8 fb-diff; hw ms quiet + n8; user call on the 1-pixel diff (below). Knob-off identity passes |
| `vram/vram-pages-a-v1.patch` (VRAM_PAGES fix A) | `ad364080…f324` | ed24efa (applies at 8ac9f2d) | STRICT pair + hwproject. Flycast: alloc overhead 209,216 -> 0 B; preload 2.13 -> 2.40 MB resident; frame times unchanged |
| `pacing/pace-v1v2-0825810.patch` | `a8370cde…1ba0` | 0825810 (applies at 8ac9f2d) | route v2 reruns, game vs wall time at 20 fps, hw ms per skipped tick, Flycast p50/p99 with enemies, picker backdrop on screen |
| `w10/w10-door-u0/u1/u2/u6.patch` | stale | 5f32de5 | regenerate with `w10/tools/mkpatch_door.sh`; equalised STRICT via dvdhold (h0 baseline first) |
| frontier `FIX_R101_CALL_DONE` (test only) | commit 2f97c09 on tree4 `m1-fx` | pre-8ac9f2d | Makefile tail conflict; rebase, then run r101e |
| `assets/patches/w9b-lod-cluster-trees.patch`, then `w9b-lod-cluster-bins.patch` | `635f20a6…`, `83c20762…a6ad6` | on top of W9b | parked W9b add-ons |
| logic P5 `design-logic/patches/design-logic-p5-vec-inline.patch` | `a65b8c15…d1d929` | 0825810 on top of P3b | r6 hw number (STRICT r11 3516 / route 5975, identity, r8 -0.24 done) |
| logic P7 `…-p7-hermite-flat.patch` / P8 `…-p8-getpos-memo.patch` | `f843705d…` / `d1415f2b…` | 0825810 | P7: r8 +0.52 (layout effect), leaning reject, r6 check; P8: STRICT done, memo check run (0 mismatches) + hw runs |

Open question for the user from std-runtime: `TREE_IMPOSTOR=1` enables the PT polygon list at PVR init before the
quality mode is known, costing ~77 KB VRAM in Original mode too.

## Workstreams at hold (area dir under /root/probe/d367-agents/)

| Stream | Area | State at hold | Next |
|---|---|---|---|
| Frontier / route | `frontier/` | m1 verified; r101 direct entry measured (heap 4 ~2.46 MB free in play, VRAM 280 KB free in play); em15 motion keys added to `m1/m1-build-disc.sh` | test-only "call done" flag to see r101 play; east walk after the ARAM fix; restage m1 with em15 keys |
| ARAM block swap | `blockswap/` | fix built, passing in Flycast | gates + commit (see above); list ARAM units per room |
| r101 call reset | `subscreen2/` | investigation just started | root cause, fix |
| Sub-screen draw order (Hunnigan, attache-case items invisible) | `subscreen2/` | cause found: native UI draws all 2D quads after models; `SS_UI_ORDER=1` designed (flush queued quads before sub-screen model parts, models on TR list) | build + screenshots (parked behind the call reset) |
| Warp rig (DBG_WARP) | `warp/` | test builds; presets planned r100-spawn/post-radio/house-door/bridge/east-door, r101-entry/bell-fight | finish presets; prove s03 house scene and r101 door |
| VRAM | `vram/` | 161 KB r100 gap = 2 KiB page-alignment pad per texture (KOS pvr_mem in-VRAM headers defeat the page check); fix A (page allocator, ~158 KB) built, arms pa0/pa1 run; TA_DOUBLEBUF study arms ds0/ds1/dst0/dst1 run (SUBSCREEN=0 both sides) | analyse; deliver A; bring doublebuf vs C to the user |
| Door loading | `w10/` | U1+U2+U6: r100 door 10.22 -> 6.29-6.75 s (Flycast emulated), source blocked 1.03 -> 0.07 s; wall-time pad failed as an equaliser; frame-based hold (IO_PROBE test hook in cDvdQueue::Read) built, h0 baseline running | h1/h2/h6 held STRICT vs h0, in-room p99/max, deliver U0/U1/U2/U6 |
| Logic | `design-logic/` | P1-P4, P3 (GAME_CONCAT_COL), P6 (GAME_SINCOS) and, after the hold, P3b (GAME_MULTVEC_SCHED, 45fd3d9 + README 43c0e75; r6 -0.28, r8 -0.13 hw ms) landed and in LH; FTRV **rejected** (~1.1 hw ms/tick but RNG diverges at tick 634, 3rd kill 3074 vs 3071; parked on branch `dl3-ftrv`); P10, GAME_SCHED rejected. CPU share at 30 fps: 70% at 6, 80% at 8 engaged Ganados | P5 r6 number and land; P8 check; confirm P7 reject; scripts in `tools/dl-scripts/` hard-code an old scratchpad path; DESIGN.md is v1 |
| Enemies | `actors30/` | actor tiers in PERF (-19.9 hw ms at 8 Ganados); ACT_CAP code landed off; ACTOR_FOG_GATE built (18 cObjScr parts beyond 25 m fog cost 7.8 hw ms quiet r100); worktrees wt8/wt9/wtc kept; build dirs need a candidate.txt or the TEX_RESIDENT fan-out breaks | finish fog-gate gates, then PERF; item 4 Leon <=5 ms |
| Rendering | `builder/` | R1 (FRONT_TEXOBJ) landed, not in recipe (-0.45); TA_HASH (2fe6fba) and group-8 PVR header compare (0aa5cc9, 0 bad of 210,800 parts) landed after the hold; canonical-recipe fight fixture does not reach gameplay (VMU_SAVE/VMU_DEBUG_SLOT card screens, NATIVE_MES/SUBSCREEN_OVL title stall), gates ran on `scripts/bmk2.sh` | R2 (8 KiB records 128/160/448, ~-9.5 hw ms expected); W9b plus two parked add-ons |
| Standard assets, pipeline | `assets/` | Standard r100/r101/r103, disc staging, grove split (8 views), user VRAM trims landed; after the hold 45138ce landed BIN 59 split (r103 max 11.85 -> 9.85 ms, views within 5 ms 157 -> 162/270), BIN 1 shell skip (all-alpha BIN), Blender failures now fatal, and vanish-guard NEVER 1.0e30 (fixes std-runtime's "level error"); `out/standard/{r100,r101,r103}` rebuilt with it; --verify cache (586 MB) kept | tell std-runtime to restage and rerun its r100 fight; W9b add-ons in order: `patches/w9b-lod-cluster-trees.patch` (`635f20a6…`) then `patches/w9b-lod-cluster-bins.patch` (`83c20762…a6ad6`) |
| Standard assets, runtime | `std-runtime/` | contract s16 implemented in part (impt); item 20 rebase; low/ rejection fallback fixed | item 20 -> item 21 -> per-mode selection -> r100 proof; note ~77 KB PT-list VRAM at init |
| Frame pacing | `pacing/` | v1/v2 built; opt-in LOGIC_TRACE_MASK_RENDER for the render-only be_flag bit; picker question + RE4DCCFG bits 16-17 | rebase on 2ba789c picker; remaining gates |
| VMU | `vmu/` | S0-S9, S5, LCD status, pacing bits landed | DBG_AUTOLOAD start points (gate A+B, C at room entries); console checklist |
| hwcal disc | `hwcal/` | versions c1-c7 run in Flycast | finish disc + HOW-TO-RUN for the one approved console run |
| Cutscenes / audio | `cutscenes/`, `audio/` | idle | r101 door audio check |

## Waiting on the user

- **TA_DOUBLEBUF vs option C.** C (single-bank PVR layout) would grow the texture pool 2.64 -> 3.87/4.19 MB but
  rules out TA_DOUBLEBUF. Measured (vram/, SUBSCREEN=0 both arms, 8 live Ganados, Flycast wall ms):
  quiet p50/p99 66.8/68.8 -> 53.9/59.8 (15.0 -> 18.4 fps); fight p50/p99 117.7/213.5 -> 106.7/197.5, mean
  124.7 -> 111.7; frozen crowd 100.2 -> 87.9. The whole wait is the stream_open fence (~12.5 ms/frame); with
  doublebuf wall = busy and every frame is presented; STRICT over 3,473 ticks; texture pool unchanged. The
  hwproject pair (116.1 vs 147.5) is invalid (mismatched windows) and needs a rerun. **VRAM agent recommends
  doublebuf** once sub-screen option (b) exists: a ~15-line `pvr_set_vbuf_doublebuf()` in the pinned d367 KOS
  (fence, ta_target=0, vbuf_doublebuf=0, pvr_sync_reg_buffer() at open, back at close; <=1 frame per open/close).
  C gives up this ~12.5 ms/frame (roughly 16 vs 20 fps at the 50 ms target). Study patch
  `vram/ta-doublebuf-study-v1.patch` (sha `fb601d8e…c9f9c`), conflicts with SUBSCREEN=1 until (b).
- **r103 implementation go-ahead** (plan only so far).
- **ACTOR_FOG_GATE pixel.** In the frozen quiet frame exactly one pixel differs, (292,150): (148,137,115) off vs
  (148,137,123) on, a fully fogged object pixel (same-arm controls 0). Accept it, or cull only beyond far + a margin.
- **TREE_IMPOSTOR PT list** costs ~77 KB VRAM in Original mode too (see Parked patches).

## User decisions this session (also in the skill)

- Grove split: option B (8 views per tree). r101 trims: remaining grove atlases 8 views + shell textures 64 VQ;
  r100 tree atlases re-baked at 8 views. r103 BIN 59: option B (split, same look); the sparser PS2 tree rejected.
- FTRV for logic: rejected by rule (changes game state). Fast sin/cos (P6, bit-exact): in.
- Resources: up to 3 Flycasts per team; builds via `tools/d367/build.sh` (per-tree lock + two host-wide slots,
  -j4, fixed SOURCE_DATE_EPOCH); asset builds --jobs 4; stage discs on WSL ext4 and copy to D: once.
- Testing: prefer narrow starts (VMU start points, DBG_WARP) over full routes; the final disc still gets one full run.

## Traps to know before resuming

- Measurement arms at HEAD need `QUALITY_PICKER=0` (or quality.txt with picker=0); otherwise runs stop at the title.
- With `VMU_SAVE=1` the boot card screen waits at `card=8/1` (answer Up+A); `card=5/3` padscripts stall.
- Pad anchors like `room=256/1` only fire in LOGIC_TRACE builds; `w11.txt done N` counts the boot card screen.
- Unresolved symbols link to silent stubs: check `missing.txt` after builds (externs in an unnamed namespace,
  calls into the Sscrn module).
- `pvr_mem: ERROR -- out of PVR memory` lines are mostly claim probes; count real upload failures separately.
- Flycast door/frame times are emulated SH-4 time (safe with parallel instances); Flycast has no GD-ROM seek model.
- Stop processes by PID only (`pkill -f build.sh` killed other agents' builds twice).
- `SUBSCREEN_OVL=1` writes `sscrn.ovl` into the source tree; build/stage dirs must copy it or the disc halts at
  boot (`main.cpp(548)`).
- `VMU_DEBUG_SLOT=1` (in M1) stamped `__TIME__` before 8ac9f2d; byte-identity checks on older bases need it off.
- The fixture fight anchor is now frame 1719; old fixed hwproject windows (2401/2701) are wrong.
- Passing build variables as one quoted argument silently builds knob-off (hwcal trap).
- hwcal disc hides the memory card from the game; it only writes its own RE4DCCAL / RE4DCH1..5 files.
- GCC 2.95 vs modern class layout (vptr position) breaks `this+offset` arithmetic; see the skill.

## How to resume

1. Read this file, the skill, and the area STATE.md files above.
2. Land the ARAM fix first (its STATE has the gates), then the r101 call reset.
3. Resume the other streams in the order of the dependency list in the route doc; every patch still goes through
   the commit procedure in the skill (sha check, HEAD guard, empty index, `git apply --check` / `--cached --check`,
   commit with the Co-Authored-By line, push, dirty count stays 75).
