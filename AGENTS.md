# RE4 Dreamcast implementation instructions

## Governing objective

Deliver a native Dreamcast game that starts from cold boot, presents a working
source-derived title/main menu, accepts New Game, and lets the player complete
the first three rooms in the original opening progression in one session.
Cutscene presentation is explicitly deferred by the user for this milestone.
Room 120 initialization is an intermediate diagnostic checkpoint, not success.
Determine the actual three room IDs and required transitions from the matching
source and data; a debug-configured start and numerical room order are not proof.

Use the GameCube source for behavior and authored presentation; use native
SH-4/KallistiOS/PVR/AICA techniques for execution. Continue the existing port.
The active recovered game target is `port/dreamcast/game`; the working renderer
and room fixtures in `port/dreamcast/room` are reusable components and regression
references, not a substitute for original gameplay integration.

## Read order and existing backlogs

Read `CLAUDE.md` for current working paths and the last inspected frontier, then:

1. `port/dreamcast/docs/PLAYABLE_PATH.md`: authoritative execution plan, current
   menu/three-room scope, integration milestones, debug fixture workflow.
2. `port/dreamcast/docs/R4_GAME_BOOT_CHECKPOINT.md` and
   `R4_GAME_TARGET_CENSUS.md`: historical boot evidence and platform coverage.
   Their next-blocker statements are dated; inspect current source and logs.
3. `port/dreamcast/docs/REALTIME_PATH.md`: supporting measurement, fidelity,
   performance backlog and previously rejected experiments.
4. `port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md`: supporting resource,
   transition, memory and alternate-asset backlog.
5. Only the checkpoint/source files needed for the selected dependency.

Do not replace these backlogs with a competing roadmap. Route new work into the
existing plan and update the relevant checkpoint. R0-R4 labels record history,
not task priority. Preserve deferred chapter/Disc 1, performance, resource,
source-parity, debug-tool, cutscene and physical-hardware work explicitly; it is
not silently completed or abandoned when this milestone closes.

Current user scope overrides older narrower cabin goals and older requirements
that cutscene presentation must precede playable integration. Do not inherit an
old "next task", test count, FPS, or clean-tree claim without checking it.

## Acceptance contract

- One native executable boots through the required startup/card prompts to a
  visible, controllable title/main menu. New Game and the menu choices used by
  the opening route work; debug-start fixtures do not replace normal menu entry.
  Pause/inventory and their return to gameplay work where needed by the route.
- All three verified opening rooms are playable consecutively with source
  player/camera/collision, complete character and weapon components, required
  enemies/combat, interactions, HUD, audio, events and exit conditions.
- Both forward room boundaries use normal source progression, preserving
  inventory, health and required flags. Re-entry where allowed, death, retry
  and return to the relevant menu must restore valid state without stale data.
- Cutscenes may be skipped, including their video/audio/presentation. Trace the
  source skip/completion path; apply necessary event/flag/inventory/spawn/camera
  effects, release resources, and return control at the correct point. If no
  source skip exists, document and test a specific completion adaptation. Do
  not omit an entire script or invent flags just to unlock a door.
- Manual play with visible moving output and game audio proves the route.
  Scripted input, logs, linking, stubs and room-update counters are supporting
  evidence only. Record missing behavior honestly. No required silent stubs.
- Keep 640x480 and the accepted presentation policy. Measure frame intervals,
  input response, simulation debt/drops and memory across combat and transitions.
  Retain the existing approximately 30 presented FPS target; poor performance
  does not block safe integration, but boot-only execution is not playability.
  Flycast-first evidence and physical-console acceptance are separate gates;
  unavailable hardware does not stop useful implementation or imply a pass.

## Execution workflow for Sol and Astra

Both models implement against the same evidence and acceptance contract. This
file does not change the selected model or authorize automatic delegation.

For Sol, make each slice concrete: identify the reproducible trigger, last good
state, exact missing dependency, owned files, source behavior, proposed change,
verification command/fixture and expected observable result. Prefer one bounded
hypothesis with a runnable candidate, rather than a broad reconstruction task.

For Astra, use deeper analysis when ambiguity crosses subsystem boundaries:
module lifecycle, task scheduling, endian/data ownership, event/transition
semantics or contradictory measurements. Resolve a concrete source contract and
implement it or leave a precise implementation brief with the same fields.
Do not turn the model distinction into mandatory review or an approval queue.

For every slice:

1. Inspect branch, HEAD, dirty files, live processes and relevant evidence.
   Preserve existing edits and identify what is already implemented.
2. Reproduce the current blocker on the active game target. Trace its source
   caller and data producer; classify it as missing code, bad data conversion,
   lifecycle/scheduling, rendering/audio, memory, or performance.
3. Select the smallest change that advances the normal menu-to-room route.
   Reuse existing native systems. A diagnostic bypass must be labelled and
   followed by verification through the natural path before acceptance.
4. Implement, build, and run focused correctness checks. Preserve the PowerPC
   path when editing shared recovered source and run the existing comparison
   procedure where applicable. Avoid tests that merely repeat the implementation.
5. Run the candidate through the prior successful frontier and new behavior.
   For optimizations, compare matched states and before/after costs; for source
   corrections, validate against source behavior rather than preserving a defect.
6. Record keep/revert, exact executable/assets/toolchain/emulator identities,
   command/fixture, evidence directory, reached state and next blocker. Update
   the existing plan/handoff before yielding at a coherent checkpoint.
7. Continue through routine dependent fixes. A commit is not a stop instruction.

If a command seems stuck, inspect its process/session before restarting. Use
script files for complex Windows-to-WSL commands rather than nested quoting.
Do not mutate an evidence folder belonging to a running or accepted capture.

## Current integration hazards

- Required REL entry points must resolve to compiled SH-4 code, never PPC bytes
  or generated missing-function stubs. Check symbols before and after partial
  linking and in the final ELF. Unknown module IDs must fail explicitly and the
  caller must not execute a stale/raw prolog after failure.
- Static linking does not reproduce REL reload semantics automatically. Account
  for constructors/destructors, BSS/reset behavior, registration and unload state;
  exercise retry and transitions. Document temporary lifecycle limits.
- Read ID/light-path formats with their consuming source. Distinguish missing
  files from incorrect endian/offset conversion. Fixture success is not proof
  that the normal New Game entry or all three rooms have complete data coverage.
- GX/audio placeholder execution is not evidence of displayed menus, rendered
  gameplay or working sound. Connect the existing native backend as dependencies
  are reached; do not build a general GX interpreter or second gameplay engine.
- Source gameplay/events remain active when rendering is culled. Preserve source
  timing, collision and input ordering instead of buying speed by dropping work.

## Workspace and Git discipline

Use the Linux checkout `/root/work/re4-dreamcast` under WSL Ubuntu-24.04. The
Windows `re4-dreamcast-WINDOWS-INCOMPLETE` tree cannot preserve case-sensitive
source names. Read the paths and commands in `CLAUDE.md` before building.

The tree contains ongoing integration changes. Never clean/reset, overwrite
others' edits, broadly stage, or commit proprietary assets, captures or generated
packages. Stage exact reviewed files; the user has authorized commits and pushes
of accepted work to `origin` on `dreamcast-port`. Inspect the staged diff and
verify remote SHA after push. Documentation-only checkpoints do not accept dirty
runtime changes. Keep Soulcalibur/Flycast reference code read-only unless asked.

The persistent-goal tool may still display the old room-120 objective because
its API cannot edit an active goal. The user's menu-plus-three-room scope is the
completion standard. Do not complete the goal merely upon reaching room init.
