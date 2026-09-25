# D367 handover: the hold of 2026-09-24 (lifted 2026-09-25: parallel lanes, see "How to resume")

**Serial mode (later on 2026-09-24; ended 2026-09-25):** the user asked for the backlog to be worked through
serially in one session, without sub-agents. Since 2026-09-25 the work runs in parallel lanes ("How to resume").
Landed in serial mode: 23074db warp rig v2 (DBG_WARP), 9bba3c8 ARAM block units re-read
from GD-ROM, 4980a40 + 976c93d SS_POOL_HIGH (the r101 call reset and the file-screen reset after it), a0c3079
NATIVE_PKG_HIGH (FILE_01 westward reload), 8332a22 W9b (R4IM v3 runtime + converter: r101 scenery draws),
ea1e2d3 VRAM_PAGES (default off), 9951d17 items 20+21 (TREE_IMPOSTOR/MESH_TEXTURES on W9b, default off), 010169c
QUALITY_ASSETS (Standard selection, default off), 46b9f4f tex-vq6 (r101 textures VQ: the r101 VRAM blocker), e6f65cc
em2a linked (r100 after-state entry), 4f530e3 warp `trg` (r101 bell reached by warp), b1a342c `assets.sh discover` (room demand from source data: modules,
archives, heap 4; run it before building a room's disc), 07d4a82 movie ring (r101s30 plays from the fight),
b7a7e2d + edf0cc4 TA_DOUBLEBUF (canonical), 9f2f45a/4a7a560/b99e803/054bfd2/49b97b2 discover round 2. The
sections below are updated for those; everything else is as at the hold.

**User play testing (afternoon of 2026-09-24).** One-off route checks now go to the user's play discs in
`D:\RE4DC-Play` (one `Play-*.cmd` per disc; keyboard + DualSense on port A; the game log is copied to
`logs\game-<time>.txt`) instead of scripted walks. Work order (user): (1) the r100 post-house ambush (heap 4),
(2) **frame pacing, never to be deprioritised again**, (3) low-poly Ganado meshes, (4) the Leon rebuild. After the
24-hour fix review the user set: scope lockup -> launcher log -> frame pacing -> QUALITY_ASSETS into the recipe ->
ambush reserve -> ACTOR_FOG_GATE gates -> SS_UI_ORDER. Findings:
- **r101 scope lockup: fixed behind knobs (9598ce2).** The scope overlay (r101.arc#35, 256x224 C4, 128 KiB 16-bit)
  was never loaded by a scripted run, so it was never VQ'd; in play it found no contiguous block (928 KB free) and
  the retry evicted the scene every frame. Now VQ for every indexed image (`ui_indexed_coverage.py` log in
  `ui_logs`, pin tex-vq8: 1.93 MB -> 0.33 MB, scope 18 KB), `UI_FRAG_LATCH=1` and `UI_OVERLAY_SLAB_KB=24`. User
  test disc `warp-r101-scope` (with VRAM_PAGES=1). Recipe after the user's check and the VRAM_PAGES hwproject pair.
- **Just-in-time loading is the stutter.** A Standard route session did 357 texture loads in play after the last
  room preload (each a disc read inside a frame; GD-ROM seeks are 100-200 ms on hardware). Proposed next item after
  QUALITY_ASSETS: zero in-play loads per room (preload HUD/effects/overlays/texlow too, count loads since preload).
- **Ambush (heap 4):** em21/em23/em2a motion streaming contract landed (bcfbf2b; also fixes le_mirror's registry
  regex, broken since e6f65cc). The runtime reserve (`MOTION_RESERVE`, cold slabs allocated at bind) and
  `MOTION_USAGE_LOG` (first acquire per clip, to trim the em12 hot set of 952 KB) are in `warp/tree3`, not committed;
  user disc `route-ambush-reserve` is the test.
- **Standard gates (QUALITY_ASSETS TREE_IMPOSTOR MESH_TEXTURES):** STRICT std vs orig and orig vs base, 6191 ticks
  each; std fight 76.4 hw ms. The Original hw arms (and std quiet) were voided: hwproject staged its evidence dir
  without the joystick-off block and the user's DualSense drove them (fixed b951305). Reruns queued after pacing.
- **Frame pacing:** the pace2 arms (tree4, `pacing/queue2.sh`) are running in Flycast.
- Launcher (private, D:\RE4DC-Play): the DualSense relaunch lost the game log (stale flycast.log RAM address);
  Play-RE4DC.ps1 now waits for the old Flycast and read_log.py re-reads the address.

The user put every workstream on hold at this point (lifted 2026-09-25). For the hold-era streams this document is
the entry: read it, then the
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
| r100 -> r101 door | ARAM block-swap fix landed (9bba3c8); swaps in both directions pass in Flycast. |
| r101 | Loads by direct entry and by warp. The first-visit Hunnigan call and the "Playing Manual 2" file screen after it now work (SS_POOL_HIGH=1, in the M1 recipe; 4980a40, 976c93d). With W9b (8332a22) the scenery draws. With tex-vq6 (46b9f4f; r101 textures VQ) the square fight runs: warp r101-bell-fight 10.1 fps Standard / 9.4 Original in Flycast (test build), 15 failed uploads (was 4,613). Not yet played through to the bell. |
| r103 | Plan only (user: "work on this plan but don't implement"). |
| Performance | 2026-09-25, the r101 square (30 fps rethink, ACT_CAP=0): never-draw G_q 30.66 ms a tick (sq97), target 24.97 (gap 5.69); R 4.05 with coarse stick figures (cl22), 26.47 with the reduced characters (version C, cl21); the source renderer R 68.92 (cl27). Plan: D367_SQUARE_PERF_PLAN.md. (At the hold: the r100 8-Ganado fight ~125 hw ms/frame against a 50 ms target.) |

## Critical path and blockers

1. **ARAM block swap: landed (9bba3c8).** The port had no ARAM backing. Now GD-ROM stands in for ARAM: ARAM
   loads record the address and size, and ARAM_TO_MRAM re-reads the unit's own file. No knob. Still open: the
   event-file MemorySwap calls in r100, r101, r117, r11c and r10b are a separate path.
2. **r101 first-visit call reset: landed (4980a40, 976c93d; `SS_POOL_HIGH=1`, needs SUBSCREEN=1, in the M1
   recipe).** The sub screen swaps `[pG->pStFnt, +3 MiB)` out as the GC does with ARAM. On the GC, the stage font
   and room archive fill that window. The port's ARENA_FIT frees the archive tail, so later room allocations can
   land inside it. Anything the sub screen keeps using while it is open must stay out of the window:
   - the effect pools (EspgenArray, pEspBuf, g_pEspSys) and the LightMgr array: EspgenMove/EspMove/
     LightMgr.move run in the sub screen loop; before the fix this ended in a null jump and a silent reboot;
   - the primitive buffer (`primInit`, `pG->prim_cnt`): GetPrimBuff matrices corrupted heap 12, giving
     "Invalid key history", then "INVALID PTR" and a reset on the type 0x40 file screen.

   `re4dc_ss_alloc_above` (sscrn_bridge.cpp) places them above the window. Knob-off images are byte-identical.
   Logic trace is STRICT outside the swap interval; while the sub screen is open, game logic is frozen and the
   sampler reads swapped actors. The warp r101 run now shows the file screen ("Playing Manual 2", page 1/4).
   Diagnosis tool for the next case: the heapwatch diag (test only; `/root/probe/d367-agents/warp/heapwatch-diag.py` patches tree3). It records heap-4
   cells in the window at open, then names the old owner of the first broken heap-12 cell.
3. **Route bugs found by the warp rig** (all open):
   - r100 entered after s20 halted (em2a, module id 28, not in the image). Fixed by e6f65cc, which does three things:
     - links em2a;
     - keeps its subArc: `new (em) cEm2a;` off the GC, because value-initialisation zeroed it and every trap
       failed modelInit;
     - binds the em2a/em21 cut cameras to the real static instead of a missing-symbol stub.
     Open: in that state heap 4 is 172 KB short for the crow archive (em23.drs needs 0x36ac0, 0xcd80 free with
     Original packages), so the crows are absent. Options: Standard packages (-294 KB heap 4), or trimming em2a.drs
     (texture-only preparation as em21/em28).
   - `d354v7-fixtures` lacks the 16 r101 em15 motion keys and `m1stage.sh` uses it, so m1 route discs halt at
     r101 (same gap as the Play disc).
   - r101 scenery grey: fixed by W9b (8332a22). The staged r101/r103 packages are R4IM v3, which HEAD's runtime
     rejected.
   - r101 VRAM: fixed by 46b9f4f. The cause was not the page pad or Standard vs Original. The VQ overlay was built
     from r100 logs only, so r101 streamed 126 textures as 16-bit (4.04 MB against a 2.47-2.55 MB budget).
     - tex-vq6 = the same rule plus two r101 logs (61 new images, 4.52 -> 0.69 MB, PSNR >= 27.6 dB). The pipeline's
       `tex/00-vq` is now this set for every room.
     - Later rooms: add a log of the room to `ui_logs` and rebuild.
     - VRAM_PAGES alone (ea1e2d3) did not help r101: 4,613 vs 5,177 failed uploads, same progress.
   - r100 westward walk: FILE_01 failed to reload (heap-4 fragmentation); fixed by NATIVE_PKG_HIGH (a0c3079, M1).
     Without it, area 1 ran at ~4 fps in Flycast (source fallback); with it, 15 fps.
   - The bell: warp preset `r101-bell` (4f530e3) arms the source's DebugTrg(0) shortcut at room frame 1200, so the
     fight reaches event 30 without 15 kills (test builds only; default images byte-identical). warp-bell1: event 30
     runs to its end, room save flags 02000000 -> 03200000, Leon in control in the empty square.
   - **Fixed (07d4a82): the bell movie r101s30 did not play from the fight.** Cause: one-thread player, GD reads of
     140-310 ms after the game's own reads, an 8 KiB AICA ring (64 ms of fresh audio) and a fatal "decoder needs
     more data". Now a 512 ms ring + a waiting dry input: 1298/1331 pictures, full audio (warp-md3-bell); r100s40
     unchanged. The logic after a movie follows how long the movie held the frame (wall-timed, like doors).
     Queued (user): ADPCM movie audio, then 12 kHz PCM only if ADPCM fails; an async reader would remove the
     33 remaining early drops. Original note: It decoded 7 of 1331 pictures, dropped
     all 7 (never uploaded) and ended RE4DC_MOVIE_ERROR after 11.5 s; the cutscene took its end path. warp-bridge-2
     showed the same once for r100s44 (bridge-1/3 played it). The pictures fell behind the vblank clock from the
     first one: decode or GD reads starved while the fight's threads/streams were still live. Next: instrument
     native_movie.cpp's loop (per-picture feed/decode/read time, the failing return) on the r101-bell preset.
4. After these: frontier east walk to the r101 door on the canonical recipe, r101 census, then r101 to the bell.

## Parked patches (not committed; none passed every gate)

Paths are under `/root/probe/d367-agents/`. Rebase anything whose base is older than 8ac9f2d before landing.

| Patch | sha256 | Base | Missing gate |
|---|---|---|---|
| `hwcal/hwcal-disc-v3.patch` | `77ec6409…cc76` | applies at 8ac9f2d | finished disc run on current build; PREDICTIONS.md; HOW-TO-RUN in `hwcal/scripts/` |
| `subscreen2/wip-uiorder.patch` (SS_UI_ORDER) | `f75a4439…df53` | 471fd72 | codec screenshot, sub-screen hw ms, rebase (inventory fixed, STRICT over 6,290 samples) |
| items 20+21 | LANDED 9951d17 (default off; rebased on W9b: runtime-table head at LOD word 7) | | item 20 hwproject fight window; item 21 run with textured packages |
| Standard selection (QUALITY_ASSETS) | LANDED 010169c (default off; impt tokenizer fix) | | r100 Standard run + STRICT + hw ms (quiet/fight, std/orig/base); then the M1 recipe decision (with the 77 KB PT list) |
| `vmu/kit-autoload-wip2.diff` (DBG_AUTOLOAD narrow starts) | `f8df61ad…67a1b2` | tree7 on 5f32de5 | rebase; gates A/B/C; its staging halts at r100 entry (213 texture opens fail, watchdog main.cpp:548) |
| `actors30/actor-fog-gate.patch` (ACTOR_FOG_GATE) | `9b3e1b3d…d0b` | 8ac9f2d | STRICT only over 629 ticks; n8 fb-diff; hw ms quiet + n8; user call on the 1-pixel diff (below). Knob-off identity passes |
| VRAM_PAGES fix A | LANDED ea1e2d3 (default off) | | hwproject pair, then the canonical recipe. STRICT: r100 identical to the call close, then a 1-tick close-wait shift (door-frame category) |
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
| ARAM block swap | `blockswap/` | landed 9bba3c8 | list ARAM units per room; event-file MemorySwap path |
| r101 call reset | `warp/` (main session) | landed 4980a40 + 976c93d (SS_POOL_HIGH) | verify r101 play after the file screen |
| Sub-screen draw order (Hunnigan, attache-case items invisible) | `subscreen2/` | cause found: native UI draws all 2D quads after models; `SS_UI_ORDER=1` designed (flush queued quads before sub-screen model parts, models on TR list) | build + screenshots (parked behind the call reset) |
| Warp rig (DBG_WARP) | `warp/` | landed 23074db (v2; presets from `tools/d367/warp.py`, staging/run scripts in the session scratchpad `warp/`) | add presets as routes need them |
| VRAM | `vram/` | 161 KB r100 gap = 2 KiB page-alignment pad per texture (KOS pvr_mem in-VRAM headers defeat the page check); fix A (page allocator, ~158 KB) built, arms pa0/pa1 run; TA_DOUBLEBUF study arms ds0/ds1/dst0/dst1 run (SUBSCREEN=0 both sides) | analyse; deliver A; bring doublebuf vs C to the user |
| Door loading | `w10/` | U1+U2+U6: r100 door 10.22 -> 6.29-6.75 s (Flycast emulated), source blocked 1.03 -> 0.07 s; wall-time pad failed as an equaliser; frame-based hold (IO_PROBE test hook in cDvdQueue::Read) built, h0 baseline running | h1/h2/h6 held STRICT vs h0, in-room p99/max, deliver U0/U1/U2/U6 |
| Logic | `design-logic/` | P1-P4, P3 (GAME_CONCAT_COL), P6 (GAME_SINCOS) and, after the hold, P3b (GAME_MULTVEC_SCHED, 45fd3d9 + README 43c0e75; r6 -0.28, r8 -0.13 hw ms) landed and in LH; FTRV **rejected** (~1.1 hw ms/tick but RNG diverges at tick 634, 3rd kill 3074 vs 3071; parked on branch `dl3-ftrv`); P10, GAME_SCHED rejected. CPU share at 30 fps: 70% at 6, 80% at 8 engaged Ganados | P5 r6 number and land; P8 check; confirm P7 reject; scripts in `tools/dl-scripts/` hard-code an old scratchpad path; DESIGN.md is v1 |
| Enemies | `actors30/` | actor tiers in PERF (-19.9 hw ms at 8 Ganados); ACT_CAP code landed off; ACTOR_FOG_GATE built (18 cObjScr parts beyond 25 m fog cost 7.8 hw ms quiet r100); worktrees wt8/wt9/wtc kept; build dirs need a candidate.txt or the TEX_RESIDENT fan-out breaks | finish fog-gate gates, then PERF; item 4 Leon <=5 ms |
| W9b | `warp/` (main session) | landed 8332a22 (v3 runtime + converter + heap-4 gather buffer); r101 VRAM fixed by 46b9f4f | play r101 through to the bell |
| Rendering | `builder/` | R1 (FRONT_TEXOBJ) landed, not in recipe (-0.45); TA_HASH (2fe6fba) and group-8 PVR header compare (0aa5cc9, 0 bad of 210,800 parts) landed after the hold; canonical-recipe fight fixture does not reach gameplay (VMU_SAVE/VMU_DEBUG_SLOT card screens, NATIVE_MES/SUBSCREEN_OVL title stall), gates ran on `scripts/bmk2.sh` | R2 (8 KiB records 128/160/448, ~-9.5 hw ms expected); W9b plus two parked add-ons |
| Standard assets, pipeline | `assets/` | Standard r100/r101/r103, disc staging, grove split (8 views), user VRAM trims landed; after the hold 45138ce landed BIN 59 split (r103 max 11.85 -> 9.85 ms, views within 5 ms 157 -> 162/270), BIN 1 shell skip (all-alpha BIN), Blender failures now fatal, and vanish-guard NEVER 1.0e30 (fixes std-runtime's "level error"); `out/standard/{r100,r101,r103}` rebuilt with it; --verify cache (586 MB) kept | tell std-runtime to restage and rerun its r100 fight; W9b add-ons in order: `patches/w9b-lod-cluster-trees.patch` (`635f20a6…`) then `patches/w9b-lod-cluster-bins.patch` (`83c20762…a6ad6`) |
| Standard assets, runtime | `std-runtime/` -> `warp/tree3` | items 20+21 (9951d17) and QUALITY_ASSETS (010169c) landed default off; r101 Standard index accepted, std vs orig STRICT 1830 ticks | r100 proof (fight + STRICT + hw ms); note ~77 KB PT-list VRAM at init |
| Frame pacing | `pacing/` | v1/v2 built; opt-in LOGIC_TRACE_MASK_RENDER for the render-only be_flag bit; picker question + RE4DCCFG bits 16-17 | rebase on 2ba789c picker; remaining gates |
| VMU | `vmu/` | S0-S9, S5, LCD status, pacing bits landed | DBG_AUTOLOAD start points (gate A+B, C at room entries); console checklist |
| hwcal disc | `hwcal/` | versions c1-c7 run in Flycast | finish disc + HOW-TO-RUN for the one approved console run |
| Cutscenes / audio | `cutscenes/`, `audio/` | idle | r101 door audio check |

## Waiting on the user

Nothing (2026-09-24): the user answered every open decision; see the route doc
("User decisions 2026-09-24 (later)"). r103 is go; Standard look + TREE_IMPOSTOR 77 KB are approved; the fog-gate
pixel is delegated (zero visible difference unless the margin costs > ~0.2 hw ms).

- **DONE (b7a7e2d): TA_DOUBLEBUF with sub-screen option (b), in the canonical recipe.** Measured gain on the
  canonical base: r100 quiet -1.9 ms/frame Flycast, r101 fight 0 (CPU-bound); see the route doc. Background:
  C (single-bank PVR layout) would grow the texture pool 2.64 -> 3.87/4.19 MB but
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
- The dirty overlay can sit inside a patch's context (game.cpp primInit carries `RE4_MEM_LO` in the worktree,
  `0x80000000` at HEAD). Build the index patch from `git show HEAD:<file>` and apply the same edit to the worktree
  file; check the worktree result equals the tested private tree.
- Sub screen window: see blocker 2; any new allocation that the sub screen loop touches needs SS_POOL_HIGH placement.
- TA_HASH is sensitive to emulated timing: HEAD plus a dummy per-meshlet loop changes every frame's hash (the
  async pipeline defers or skips parts by timing), while an unused added function does not. It only compares
  builds whose hot paths are unchanged; use STRICT + word counts + draw counters otherwise.
- Heredocs through the Bash tool turn `\n` in C strings into real newlines: write edit scripts with the Write
  tool and run them from a file.
- GCC 2.95 vs modern class layout (vptr position) breaks `this+offset` arithmetic; see the skill.

## Landed during the hold

2fe6fba TA_HASH, 0aa5cc9 group-8 PVR header compare, 45fd3d9 + 43c0e75 GAME_MULTVEC_SCHED (P3b, in LH),
45138ce assets BIN 59 split + BIN 1 shell skip + level-rule fix. All 14 agents confirmed "held"; no Flycast,
build or watcher of theirs is running.

## How to resume

1. Read this file, the skill, and the area STATE.md files above.
2. Since 2026-09-25 the work runs in parallel, non-overlapping agent lanes; the lane map, owners and the landing
   rule are in D367_SQUARE_PERF_PLAN.md, "Current order and status". Serial mode had landed the warp rig, ARAM fix,
   r101 call reset, FILE_01 reload, W9b, VRAM_PAGES, items 20+21, QUALITY_ASSETS and tex-vq6. The rest of the serial
   backlog belongs to the route-bugs lane (bg, lane-bugs; paused):
   - r100 after-state crows (heap 4, see blocker 3);
   - the m1 restage with em15 keys;
   - r101 -> r103 (the bell movie plays since 07d4a82);
   - DONE discover round 2 (tools/d367/README.md "Room discovery"): porting-trap lint + `--wire` (9f2f45a;
     reproduces e6f65cc on dadfbac), heap-4 options per enemy archive with a covering plan (4a7a560), r101
     measured enemy heap-4 room 3,048,704 B (b99e803; r103 waits for W8b), event actors / evd (054bfd2; every
     route event has a movie), Standard budgets + VRAM + missing-texture check (49b97b2). Findings: r100 crows
     fit in Standard with QUALITY_ASSETS=1 (111,232 B spare); Original needs a new contract (em21 motion-stream
     <= 294,240 B, or em23 + em2a motion/textures + em2a's 17,152 B REL copy). The r101 warp disc misses 16 room
     texture packages (open failed): trace the staging gap;
   - ADPCM movie audio (queued by the user after the ring fix);
   - r100 Standard proof.
3. Other streams go to their lane; per change one cost arm and one STRICT gate, no series (user: minimal
   benchmarking). Lane agents hand their patches to the main session, which lands them via warp/tree7; every
   patch still goes through
   the commit procedure in the skill (sha check, HEAD guard, empty index, `git apply --check` / `--cached --check`,
   commit with the Co-Authored-By line, push, dirty count stays 75).
