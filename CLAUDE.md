# RE4 Dreamcast working handoff

Updated 2026-09-22. Project rules: [AGENTS.md](AGENTS.md).

## Active persistent goal and model handoff

Complete [the r100 native static cutover](port/dreamcast/docs/R100_NATIVE_CUTOVER_GOAL.md)
in `re4dc-game.elf`. The app goal was reset to this milestone on 2026-09-22.
The broader normal-menu -> r100 -> r101 -> r103 playable objective remains open.

**Implementation assignee: GPT-6 Sol, Max reasoning.** Astra's assignment ends
with the architecture/instruction checkpoint and handoff. Continue implementation
under the locked contract, through the integrated build, checks and measurements.
A first adapter, host test pass or extra plan does not complete the milestone.

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
