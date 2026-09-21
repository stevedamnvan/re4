# RE4 Dreamcast working handoff

Updated 2026-09-21. Read and follow [AGENTS.md](AGENTS.md), the shared instruction
entry point for Sol, Astra and Claude. It defines scope, implementation workflow,
acceptance and preservation rules. This file records where to resume.

## Active objective

Cold boot -> required startup prompts -> visible, controllable title/main menu
-> New Game -> the first three source-authored opening rooms, fully playable
with normal transitions, combat/events where applicable, audio, death and retry.
Cutscene presentation is deferred for now; required source completion effects
and restoration of player control are still necessary. Verify the actual room
sequence from source/data. The room-120 debug start is only a dependency fixture.

## Working paths

| Purpose | Path |
|---|---|
| Authoritative repository | `/root/work/re4-dreamcast` |
| Windows access to repository | `\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast` |
| Active recovered game executable | `port/dreamcast/game/re4dc-game.elf` |
| Existing native renderer and scene fixtures | `port/dreamcast/room` |
| Extracted private source data | `/root/re4data` |
| Converted little-endian private mirror | `/root/re4data-le` |
| KallistiOS / ports | `/root/work/kos`, `/root/work/kos-ports` |
| Private evidence | `C:\Flycast-Evidence\re4-dreamcast` (`/mnt/c/Flycast-Evidence/re4-dreamcast`) |
| Source disc | `C:\Game Dev\Emulators\Resident Evil 4 Debug (Disc 1)\Resident Evil 4 Debug (Disc 1).iso` |
| Read-only Soulcalibur/Flycast reference | `C:\Game Dev\Emulators\flycast` |

Branch is `dreamcast-port`; origin is `https://github.com/stevedamnvan/re4.git`,
upstream is `https://github.com/adonis-singh/re4.git`. At inspection the latest
implementation commit was `7d03ad5` (title screens after card check), following
`2420a80` (game frame loop) and `cb0d60a` (SH-4 source compile). Recheck live Git;
these are evidence anchors, not instructions to reset the branch.

## Last committed boot evidence

The user's completion report for `7d03ad5` matches the inspected 14-file commit:
Dreamcast DVD staging-buffer fix (PowerPC address retained), sound MRAM mirror
handler, fixture-aware disc packaging, scripted pad input, and boot diagnostics.
It records card-check completion, title.dat loading and entry into the ID system.
The reported ProDG comparison was 438 same / 0 different; it was not rerun for
this documentation update and does not qualify subsequent dirty source edits.
The reported clean tree was immediately after that commit, not the current tree.
No source assets or evidence were included; launcher changes stayed private.

That committed checkpoint names EFF conversion as its next dependency. The
current dirty `le_mirror.py` already defines `fmt_eff` and `fmt_rel`. Inspect
those handlers and `test_le_mirror.py`, validate real ID data, then replay the
same boot before deciding whether EFF remains the blocker. Do not write a second
handler or treat uncommitted room-120 progress as accepted solely from the report.

## Latest bounded result: D297 (2026-09-21)

The existing mirror now writes decoded `.arc` sidecars with `--decode-rooms`.
CNS and full source-layout SAT/EAT (including block hierarchy) convert for all
three decoded room fixtures. Native AtPoly word/half-word views agree; the game
build and focused tests pass. See [R4_ROOM_ENDIAN_CHECKPOINT.md](port/dreamcast/docs/R4_ROOM_ENDIAN_CHECKPOINT.md).
The sidecars are not runtime-ready: scene/model, lighting/camera and other
formats remain unconverted; two legacy core SAT blocks explicitly fail layout
checks. Next: SMD/SMX and the native loader boundary, preserving sound-container
handling. Last target replay remains D295; no new gameplay acceptance.

## Historical bounded result: D296 (2026-09-21)

The missing r120 archive is now extracted from the source disc. The new offline
`port/dreamcast/tools/decode_yz2.py` executes the recovered PowerPC decoder during
asset preparation; r100, r101 and r120 decode with structurally valid archives.
See [R4_OFFLINE_ROOM_DECODE_CHECKPOINT.md](port/dreamcast/docs/R4_OFFLINE_ROOM_DECODE_CHECKPOINT.md)
for exact outputs, tool identities, tests, limitations and the next implementation.
The runtime YZ2 path is still a stub; decoded archives need endian conversion and
an explicit native loading contract. The last target replay is D295. Do not
rerun the now-present compressed archive and mistake the decoder stub for data
conversion. Working extracted/mirror data changed; preserve D295's exact disc.

## Historical bounded result: D295 (2026-09-21)

The native scheduler now resolves self-directed entry, sleep, chain and exit from
OSGetCurrentThread rather than the mutable pCTask scheduling cursor, and retains
the main scheduler parent separately from the interrupt-task cursor. D293 proved
TaskExit ran with pCTask=-1; D294 exposed TaskSleep waiting on address 0x32f.
D295 clears both observed stalls, finishes em/pl00.drs, and reaches the next
explicit failure: `DVD: File not found : st1/r120.das`. Neither the extracted
source tree nor the little-endian mirror contains that file at this checkpoint.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d295-task-owner`, 55-second scripted
Flycast run using `/root/probe/d292-fixtures`; disc `/root/probe/d295b-disc`.
Build and host execution of the actual native sleep/chain/exit bodies passed.
The scheduler's PowerPC-preprocessed source is identical to HEAD before this
change; this is not a new ProDG object-comparison result. Keep this correction.
Broader KOS suspension semantics, task reuse and transitions remain unqualified.

Next: locate/extract the source room archive from the private disc, inspect its
consumer and mirror coverage, package it, and replay. Do not fabricate room data
or treat r120 cinematic staging as one of the three playable rooms. Visible menus,
rendered recovered-game gameplay, audio and manual acceptance are still open.

ELF SHA-256: `7127776f2d0620f703e64b7fddc8460810ad60062a075bc40b6b9234a1b24041`.
Disc SHA-256: `2ba7625bda9a9e89901a4a5263d6d6a58ba01057c3568f215948304ba4665ed3`.
Flycast SHA-256: `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
The evidence folder retains the tracked dirty patch; other runtime integration
changes remain uncommitted and are not accepted by this scheduler checkpoint.

## Historical bounded implementation result: D291 (2026-09-21)

The current dirty game target now links real stage entry points. The generator
uses `--force-group-allocation` during the partial link before symbol localization;
otherwise duplicate C++ COMDAT selection discarded a module-local definition.
`OSLink` now propagates registry failure; an unknown module clears its entry
pointers and fails instead of executing a placeholder. The link script rejects
missing registered stage prolog/epilog symbols before generating stubs.

Fresh Flycast replay in `C:\Flycast-Evidence\re4-dreamcast\d291-static-stage`
reached `module: id 74 -> st1_0 (static)`, followed by `prolog...`, then read
`etc/emleon00.esl`. The previous raw-REL execution crash was not reproduced.
The new frontier is `TASK DON'T EXEC : level 4` after heap-4 creation; vblank
continues to 3000 without further progress in the 55-second capture. Investigate
DVD/background-task slot ownership and termination before changing scheduler
behavior. Room init/update, light-path correctness and visible gameplay remain
unproved. Title ID-unit-not-found messages remain open too.

Build passed; the nine focused little-endian mirror tests passed. The mirror
reported 779 up-to-date files, with LIT/CAM/SAT/BIN and other raw coverage still
open. Final ELF SHA-256:
`1bee895481958c037e21a5202da481aeb50fd9629613cada81ad076c01841888`.
Disc SHA-256:
`9e5e6b04e440ebf3d0b6a485515e6608a1355fe9daad721ecfb1524ff19a2beb`.
The evidence folder retains the log, ELF, disc, symbols, tracked worktree patch
and module generator/registry snapshots. Runtime integration edits remain dirty;
this is not three-room, visual, manual or hardware acceptance.

Source `src/st1/r120.cpp` confirms r120 is opening cinematic staging and jumps
to r100 through `SceAtExecRoomJump(0x100, ...)`. Do not count r120 as one of three
playable rooms. Preserve the source completion effects when implementing the
user-authorized cinematic skip. Module reload/BSS/constructor limitations remain.

## Frontier and unaccepted work (prior snapshot)

The current tree is deliberately dirty across recovered source, platform shims,
module/build tooling, fixtures and endian conversion. Preserve it. New files
include `game/platform/modules.cpp`, `game/tools/gen_modules.py`,
`fixtures/boot-deps.txt`, and `tests/test_le_mirror.py`, under `port/dreamcast`.
They are in-flight work, not an accepted three-room implementation.

The preceding implementor reports New Game reaching room-120 initialization,
then failing at stage REL linkage and light-path/ID data. The registry/generator
now exist and retain `_st1_*_prolog` / `_st1_*_epilog` symbols across partial
links. This report needs a fresh final-ELF symbol check and emulator replay.
At inspection, `OSLink` still returned success regardless of registry failure;
unknown IDs received placeholder entries. Static-module BSS persisted and
constructor execution differed from per-load source semantics. These are open
correctness issues, particularly for retries and transitions.

The historical boot checkpoint describes missing GX/audio implementations. Do
not infer that the recovered game's menu or room is visibly playable from a
frame-loop trace or from the separate room viewer's graphics. Inspect current
adapters and integrate the existing renderer/audio paths as needed.

Next bounded slice: follow the D295 missing-room-archive frontier above;
the D291 stage-entry failure has already been cleared. Record real room init/update execution as an
intermediate checkpoint. Subsequently return to normal menu/New Game entry,
verify the opening route, and advance through its three rooms.

## Existing backlog map

| Document | Role and how to use it |
|---|---|
| [PLAYABLE_PATH.md](port/dreamcast/docs/PLAYABLE_PATH.md) | Authoritative execution order, menu/three-room milestone and source/debug integration backlog. |
| [REALTIME_PATH.md](port/dreamcast/docs/REALTIME_PATH.md) | Supporting performance/fidelity gates. Integration first; representative bottlenecks when they block useful play/testing. |
| [R4_ASSET_RESIDENCY_PLAN.md](port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md) | Existing load/retire/transition infrastructure, native texture handling and explicit alternate-asset policy. |
| [R4_GAME_BOOT_CHECKPOINT.md](port/dreamcast/docs/R4_GAME_BOOT_CHECKPOINT.md) | Dated boot/capture procedure and known source/platform dependencies. Current dirty work may be ahead. |
| [R4_GAME_TARGET_CENSUS.md](port/dreamcast/docs/R4_GAME_TARGET_CENSUS.md) | Compile/platform inventory; compiled symbols are not behavior acceptance. |
| [R4_R101_SOURCE_ENTRY_CHECKPOINT.md](port/dreamcast/docs/R4_R101_SOURCE_ENTRY_CHECKPOINT.md) | Existing source entry/camera fixture and its explicit missing events/enemies/progression. |
| R3*/R4* checkpoint files in `port/dreamcast/docs` | Accepted implementations, corrections and rejected experiments; read only those relevant to the active dependency. |

Do not reimplement completed visibility, strips, light preparation, native texture
layout, ownership or upload-lifetime work because an old handoff calls it next.
The former R3p metrics and 49-test count are historical. The latest room-viewer
measurements do not establish recovered-game performance. Keep the wider chapter,
Disc 1, cutscene, performance and hardware backlogs; they are not prerequisites
to implementing every small opening-route dependency.

## Build and evidence workflow

Run from WSL; these commands target the recovered game, not the scene viewer:

```bash
cd /root/work/re4-dreamcast
source port/dreamcast/kos-env.sh
make -C port/dreamcast/game -j4
python3 -m unittest discover -s port/dreamcast/tests -p 'test_*.py'
python3 port/dreamcast/tools/le_mirror.py /root/re4data /root/re4data-le
# Choose an unused absolute output directory: mkdisc.sh replaces its output.
bash port/dreamcast/tools/mkdisc.sh port/dreamcast/game/re4dc-game.elf /root/re4data-le /root/probe/UNUSED-RUN-DIRECTORY port/dreamcast/fixtures
```

Inspect the mirror inputs/output and active processes before rebuilding shared
private data. Choose a new capture folder for each candidate. Existing launcher
and log-reading helpers are under
`C:\Flycast-Evidence\re4-dreamcast\d290-game-boot`; inspect hardcoded paths and
regenerate log symbol addresses from the candidate ELF before using them. Keep
prior `game.bin`, logs, symbols and captures paired with their exact build.
A padscript fixture must be identified in evidence; verify human controls in the
presentation build without automated input.

For runtime work, record exact source/dirty patch, ELF/assets, toolchain/emulator,
fixture and capture identity; reached normal-boot frontier; required stubs hit;
manual checks; frame/input/memory results; keep/revert and next blocker. Keep
PowerPC source-comparison checks for shared-source changes. No new runtime tests
or performance claims were made by this handoff update.

## Preserved audiovisual reference

Keep the existing capture with game audio:
`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2\re4dc-dba07e2-current-progress-32s-with-audio.mp4`.
Later renderer/resource checkpoints retain their own exact comparisons. These
are source-derived presentation references, not proof of current boot-forward
menu, three-room gameplay or physical hardware. Preserve audio in new captures.
