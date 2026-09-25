# RE4 Dreamcast working handoff

Updated 2026-09-23. Project rules: [AGENTS.md](AGENTS.md).

**Active (D367, user-directed, 2026-09-23).** Goals:
- 20 fps (50 ms/frame) on a real NTSC Dreamcast via GDEMU + VMU. 30 fps was the original target; 15 fps is the fallback in fights.
- The recovered game playing r100 -> r101 -> r103 with PS2-FMV cutscenes, music, inventory and retry.

Resume with the shared skill `re4-dreamcast-d367` (Claude and Codex): it covers the procedure, harness, commit recipe and standing decisions. Then read [D367_THIRTY_FPS_ROUTE.md](port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md):
- its "Work plan: serialized perf lane" table: one integrated build, steps 1-5, each measured stacked by hwproject hw ms;
- the 20 fps budget;
- every user decision.

Build recipes are in [tools/d367/README.md](port/dreamcast/tools/d367/README.md). LH is the integrated base: 83 ms Flycast, 120.3 hw.

2026-09-25: the r101 square (30 fps rethink) follows [D367_SQUARE_PERF_PLAN.md](port/dreamcast/docs/D367_SQUARE_PERF_PLAN.md), section "Current order and status". Frame pacing and the coarse renderer landed default off (f4da5fd); R headroom and code placement (LINK_ORDER) landed default off (801d72d): G_q 33.39, R ~4. Next: G (collision traversal, then visual simulation).

State at this update (HEAD 5285bc7 or later):
- **Perf lane:**
  - Step 0 (FRONT_NATIVE, RELEASE_FLAGS) landed.
  - Step 2 (logic, 12.0 hw ms/tick) landed.
  - Step 1 (texture preload/O(1) handles; r101 slots; ~93 hw ms reload whenever a Ganado is in view) is in progress.
  - Steps 3-5 are queued. Patches are ready in /root/probe/d367-agents/{actors30,actcap,safecuts,frontend,w9,scenery-trials,ps2-blender}.
- **Route blockers, in order:**
  1. Stream waits: fixed, 5285bc7.
  2. W11 SUBSCREEN (transceiver): pending commit.
  3. Codec data `op/op01.das` missing from the disc.
  4. Image/heap regression: the ELF grew 2.06 -> 2.35 MB; source heap free at r100 s40 fell from 310 KB to 48 KB, so movies fail.
  5. The real r100 -> door -> r101 fixture.
  6. The r101 fight to the bell, then r103.
  Also: a room re-entry takes ~15 s (motion-key per-sector reads plus an unprofiled remainder).
- **Agent state:** each area has `/root/probe/d367-agents/<area>/STATE.md`. Read it before resuming that area.

Evidence goes on D:\Flycast-Evidence
e4-dreamcast (new dirs from the C: harness template). Run at most 2 Flycasts per agent, and delete disc images after each run.

The sections below (D366 pause, the four-owner "beat D349" sequence, Sol/Max assignment) are historical context; where they conflict, D367 wins. The [D366 pause handover](port/dreamcast/docs/R4_D366_CLAUDE_HANDOFF.md) still describes the inherited dirty overlay (~75 files; never stage, reset or clean it).

## Historical (pre-D367): persistent goal and model handoff

North star: **beat D349, do not merely recreate it**. The recovered game drives
a cheaper native visual workload while retaining its real source state systems.
Complete [the r100 native static cutover](port/dreamcast/docs/R100_NATIVE_CUTOVER_GOAL.md)
in `re4dc-game.elf`. The app goal was reset to this milestone on 2026-09-22.
The broader normal-menu -> r100 -> r101 -> r103 playable objective remains open.

**Implementation assignee: GPT-6 Sol / Max.** Continue the accepted four-owner bounded
[D349 slice/source-block qualification](port/dreamcast/docs/R4_R100_SOURCE_BLOCK_BUDGET.md).
The 14,577,304-byte all-block conversion is not the target representation or proof
of architectural failure. Reuse existing selection/partition and source block
ownership; continue implementation if bounded native packages fit that lifetime.
Follow the [escalation rule](port/dreamcast/docs/R100_NATIVE_CUTOVER_GOAL.md#astramax-escalation-rule)
only on demonstrated contract/budget failure or a need for different architecture.
D364 completed v4's first layout qualification. AoS20 is frozen as the leading
layout unless integrated evidence disproves it; D349 math stays default. Do not
repeat Split24/SH4ZAM layout tuning. Keep the accepted four owners and GCC15.2/KOS.
Continue AoS20 integration/reader qualification -> source-backing accounting ->
FILE_01 PS2/DC reduction -> complete static cutover -> residual CPU/PVR measurement
-> native actors -> broader visual reductions -> SH-4 tuning. The goal document
owns the detailed roadmap and historical comparison thresholds.
The persistent goal is paused at the operator's request; it is not complete.
Passing an isolated adapter or host test does not complete it.

Recovered GameCube source is the simulation/state authority. Productionize the
existing D349 preparation/converter -> `.re4room` -> native renderer pipeline.
The live GX/ModelPart bridge is only a fallback. GC and PS2 assets are first-class
offline visual inputs; the final runtime representation is Dreamcast-native.
Replace qualified source render-only backing, preserve source owner/state
contracts, and measure the complete candidate. D362 ended lossless scavenging.
No further bridge-cache/admission campaign or second room converter is planned.

The goal document owns the detailed contract and anti-reinvention rule. Older
next-task instructions in historical checkpoints are evidence, not active orders.
The PS2/native static phase is active; there is no prerequisite to finish a
perfect GC-oriented bridge or a perfect GC-derived asset first.

## Retained baseline and current work

Primary reference: D362 `62414dc39feccc949af4b3ed29053be9fde4d5fc` on
`dreamcast-port`. Preserve newer work and the inherited dirty source overlay;
HEAD alone does not reproduce the accepted executable.

| Reference | Verified result / role |
|---|---|
| D361 `1039667` | 128 KiB retained preparation improved matched render p50 from ~1,563 to ~1,368 ms. Keep as control, not a prompt to continue cache tuning. |
| D362 `62414dc` | Exact UV sharing recovered 34,016 source-heap bytes; free/largest 116,704 bytes. Render p50/p95 1,368.093/1,370.801 ms; page-flip p50/p95 1,389.602/1,406.282 ms. No material CPU saving. |
| D349 `5f42caa634c0e6124c48842e21570033738adfda` | Preserved native room architecture and presentation reference. Its ~49-58 ms CPU cost belongs to the smaller historical workload, not the recovered game's budget. |
| D353 `d928ad6` | Existing GC-derived static RGB bake and native modulation path. Direct PS2-authored RGB transfer is not yet qualified. |

[D361/D362 evidence](port/dreamcast/docs/R4_NATIVE_PREPARATION_CHECKPOINT.md)
records exact limits. Settled scripted presentation is not manual combat/audio,
transition/retry, real-time or hardware acceptance. Disabled audit counters are
unmeasured, not zero.

The cutover has not yet run on target. The uncommitted embedded-native-BIN draft
was rejected: it bypassed `.re4room` and expanded loaded geometry. Its scripts and
patch remain in `/root/probe/d363-rejected-embedded-format`; do not resume it.
The untracked `tools/bake_room_prelit.py` adaptation is not accepted runtime work.
Reuse the pinned D353 bake in the existing package chain and qualify any changes.

Continue from the existing source-object/owner mapping and package contract.
Historical `r100-source-cell-4.re4room` is an encounter-radius subset, not complete
r100 coverage. Full source-authored OBJ inputs already exist (paths below).
Extend existing SourceGroup identity for source instance/owner state; adapt the
proven native room submission and actual backing retirement together. Keep an
explicit dynamic/unconverted fallback list. Static cutover acceptance comes
before native actor-package integration, then r101/r103.

## Latest bounded checkpoint: D364

[Package-v4/SH4ZAM qualification](port/dreamcast/docs/R4_ROOM_PACKAGE_V4_CHECKPOINT.md)
now exists for the exact four accepted owner packages. AoS20 totals 1,299,298
bytes versus v3 1,992,824; Split24 is 1,478,690. Flycast CPU fixture p50 totals:
v3 prelit 35.293 ms; AoS/D349 47.486 ms; Split/D349 47.935 ms. SH4ZAM's
transform/reciprocal did not win; it remains optional, default math stays D349.
These are preparation/packet fixture times, not game FPS or a whole-frame win.

The leading storage candidate is AoS20, pending moving visual/source binding
acceptance. No v4 package has been activated in re4dc-game.elf or source backing
reclaimed. The [four-owner budget](port/dreamcast/docs/R4_R100_SOURCE_BLOCK_BUDGET.md)
prices a modeled 746,816-byte shortfall. This activates FILE_01 asset reduction
now: compare GC v4, qualified PS2 and custom DC input through the same package.
Target roughly 900 KB-1 MB gross reduction/headroom if feasible, including the
net allocator and loading-overlap accounting. Do not grow budgets or equate file
savings with source-heap savings. Preserve source readers,
generation/rebase/retire boundaries and the single frame owner. Continue the
cutover; do not return to cache tuning or treat this fixture as room acceptance.

The source-range reader now qualifies all four unchanged AoS20 packages against
owner/work/BIN/common identity (58 source instances / 1,093 child groups), with
no extra registry/allocation. The game hooks are still pending. FILE_01's exact
cost and material coverage are in the budget's latest decomposition; private
evidence is `/root/probe/d365-r100-cutover`. Four combined texture/mask identities
remain unqualified in the selected folder. Preserve their fallback explicitly.
Continue actual source binding/backing replacement and the authorized FILE_01
candidate, not layout/math tuning; no whole-game saving is claimed yet.

## Working paths and reproduction

| Purpose | Path |
|---|---|
| Primary repository | `/root/work/re4-dreamcast` (WSL Ubuntu-24.04) |
| Windows repository access | `\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast` |
| Target | `port/dreamcast/game/re4dc-game.elf` |
| Reusable renderer/packages | `port/dreamcast/room`, `port/dreamcast/tools` |
| D349 reference worktree | `/root/work/re4-r100-reference-5f42caa` |
| D353 prelighting worktree | `/root/work/re4-r100-prelit-d353` |
| Source OBJ inputs | `orig/G4BE08/rooms/r100/stream/r100_full_export/R100.allparts.obj` and companion metadata |
| Selected UV-shared private mirror | `/root/probe/d362-mirror` |
| Source assets | `/root/re4data` |
| Current fixture/native textures | `/root/probe/d354v7-fixtures` and its `tex/` |
| Pinned KOS / compiler | `/root/work/kos-re4dc-d336`; `/opt/toolchains/dc/sh-elf` GCC 15.2 |
| Matched build recipe | `/root/probe/d361-build.sh` (inspect inherited source identity before reuse) |
| Baseline evidence | `C:/Flycast-Evidence/re4-dreamcast/d361-retained-model` and `d362-shared-uv` |
| Private scratch | `/root/probe`; `C:/Game Dev/Emulators/re4-session-scripts` |
| Inherited-work snapshot | `/root/probe/d363-before` |

Set `RE4DC_KOS_BASE=/root/work/kos-re4dc-d336` before sourcing `kos-env.sh`.
Adapt the saved matched build recipe to a fresh destination; do not run it
unchanged because it writes the preserved D361 output. Use current mirror/fixture
identities; the old D305 generic build recipe is not the current control. Separate generated
candidate outputs and capture windows. Check disk space before full disc builds;
preserved disc deltas need their named, hash-verified base. Keep video audio.

Remote: `https://github.com/stevedamnvan/re4.git`. Keep assets/evidence private;
commit only reviewed owned code/docs. Preserve uncommitted event/source work;
its presence is not permission to stage it with this cutover.

## Existing backlogs and completed side work

- [PLAYABLE_PATH.md](port/dreamcast/docs/PLAYABLE_PATH.md): normal menu/three-room
  acceptance, source/event/audio/inventory/transition dependencies and debug tools.
- [REALTIME_PATH.md](port/dreamcast/docs/REALTIME_PATH.md): matched timing and
  acceptance, not another renderer roadmap.
- [R4_ASSET_RESIDENCY_PLAN.md](port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md):
  source ownership, native textures, warm motion and transition overlap.
- [PS2_INSPIRED_DREAMCAST_PROFILE.md](port/dreamcast/docs/PS2_INSPIRED_DREAMCAST_PROFILE.md):
  authorized visual candidates and quality/cost qualification.
- [D349 recovery](port/dreamcast/docs/R4_R100_REFERENCE_RECOVERY_CHECKPOINT.md):
  matching historical assets/builds and proven mechanisms to reuse.
- [First-stage audit](port/dreamcast/docs/R4_FIRST_STAGE_GAP_AUDIT.md): source/data
  route r100 -> r101 -> r103 and remaining dependencies across all 29 stage rooms.
  Converter fix `961c51e` and private r101 DAR exist; native r101 loading remains
  unproved. Use its latest addenda, not superseded missing-file lists.
- Isolated movie, water, PS2 and Blender work retain their own branches/checkpoints.
  Inspect current deliverables before reuse; do not relaunch finished experiments
  or assume an old running-agent report is live. Stove `14dd633` remains rejected.

Full historical handoff and build identities remain in
[the D362 snapshot](https://github.com/stevedamnvan/re4/blob/62414dc39feccc949af4b3ed29053be9fde4d5fc/CLAUDE.md) and the named checkpoints.
This concise handoff replaces their stale execution instructions, not their evidence.
