# RE4 Dreamcast: boot-forward playable integration

D327 recovers **511,200 actual source-heap bytes** by loading qualified compact
pl00/wep02 texture backing directly into smaller selectable fixed reservations.
The source menu remains visible and the required block pool still allocates,
now leaving **1,477,696 bytes**. The **1,426,304-byte enemy body now loads**,
including the source sound-container dispatch, and its 37 texture identities bind.
A demonstrated native DVD/ISR filesystem-lock deadlock is fixed by deferring
background-task suspension during bounded I/O scopes; KOS preemption stays active.

The next exact failure is **hot motion-key prefetch allocation**: 16,608 payload
bytes (16,640 requested including owner header) with 16,096 free. One key loaded;
full warm-up did not complete. Keep hot keys cached and keep the source-derived
prefetch/concurrency audit: the existing 75-clip profile is still incomplete.
The selected cache capacity/metadata/allocator budget needs at least **983,264
additional bytes** after the enemy body, before later actor/event/audio costs.
D324 remains the accepted integration reference; D325-D327 remain selectable
candidates. No complete enemy rendering, room gameplay, audio or retry is accepted.
See [D327](R4_NATIVE_PRIMITIVE_LIFETIME_CHECKPOINT.md#d327-playerweapon-backing-and-native-read-lifetime).

Updated 2026-09-21. **This is the authoritative execution plan.** It supersedes
previous instructions to finish or optimize an isolated scene before integrating
the game. [REALTIME_PATH.md](REALTIME_PATH.md) is the supporting performance and
validation policy. [R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md) is the
supporting resource and alternative-render-asset policy. Historical checkpoint
letters do not schedule the next task.

## Active milestone: main menu and first three playable rooms

User scope, 2026-09-21: cold boot through required startup/card prompts, a visible
and controllable source-derived title/main menu, New Game, and the first three
rooms of the original opening progression in one manually playable session.
Include required pause/inventory interactions, combat and events where present,
audio/HUD, both forward room transitions, death/retry and relevant menu return.
Verify the actual room IDs, entry state and exit conditions from source/data;
the current configured room-120 fixture does not establish the original sequence.

**Cutscene presentation is deferred for this milestone by explicit user request.**
Use the source skip/completion path when available. Preserve required script
side effects, flags, inventory, spawning, camera restoration and player control.
Where the source cannot skip, implement and document a bounded completion
adaptation. Skipping a cinematic is not permission to skip its gameplay effects,
required encounter, title/main menu, or door conditions. Record skipped sequences
and their completion contracts; full presentation remains in the deferred backlog.

This scope supersedes older cutscene-presentation gates and the isolated cabin
objective. Menu/debug fixtures remain valuable development tools but cannot pass
the normal-menu or continuous-three-room acceptance gates. A headless source loop
or required stub call does not demonstrate a playable or rendered game.

Shared agent instructions are in [AGENTS.md](../../../AGENTS.md); current working
paths/frontier are in [CLAUDE.md](../../../CLAUDE.md). Both Sol and Astra follow
the same source authority, implementation loop and evidence requirements.

| Existing backlog | Disposition for this milestone |
|---|---|
| Boot/title/menu, scheduler/input, module linking, endian/ID/light-path coverage | Immediate dependencies; verify normal New Game progression and explicit failure paths. |
| Player/camera/collision, required enemy/weapon/event systems, HUD/audio and menu interaction | Integrate as reached on the verified three-room route, then prove manual play. |
| Room/resource lifecycle, module reload/BSS/constructors, persistent flags and retry | Required at transitions and retry; reuse the existing residency infrastructure. |
| Native rendering and performance | Reuse completed R3/R4 work; fix representative blockers. Keep REALTIME_PATH targets and hardware gates distinct from integration progress. |
| Native texture/resource and alternate-asset experiments | Keep R4_ASSET_RESIDENCY_PLAN policy; select only experiments justified by the active route's measured needs. |
| Debug tools/source parity | Use targeted fixtures to unblock source behavior; return to the natural path for acceptance. Do not rebuild every editor first. |
| Cinematic presentation, later opening chapter/Disc 1 | Explicitly deferred beyond this milestone; retain existing plans and checkpoint history. |
| Physical Dreamcast validation | Separate final hardware gate; continue useful Flycast implementation when hardware is unavailable. |

For each of the three room IDs once verified, record entry/exit source evidence,
required systems, stub/unimplemented hits, manual gameplay results, transition
and retry results, exact build/assets and capture location. Keep missing entries
open rather than assigning guessed IDs or declaring completion from compilation.

## Historical D314 presentation and D315 stack correction

D314 is the first verified source-to-native warning/main-menu presentation;
[its checkpoint](R4_SOURCE_UI_CONNECTION_CHECKPOINT.md) pins corrected captures
and input evidence. D315 repairs the native task-stack underrun and the same
New Game fixture returns to r100's required block/enemy allocation failures.
See [D315](R4_SUBSCREEN_BOOT_CHECKPOINT.md) for stack/memory costs and precise
subscreen dependencies. Preload control flow is restored; ARAM storage, archive
qualification and Sscrn binding still prevent inventory acceptance. Continue
source-selected native resource ownership and visible output without dropping
content. D320/D322/D324 subsequently reclaim selected source backing as recorded above;
3D/audio/manual play stay open.

## Historical D312-D313 boot frontier (D312 integration / D313 storage candidate, 2026-09-21)

D312 qualifies required EVD/FCV variants and binds native em12 using the existing
module mechanism. The R100Em constructor alias passes its SH-4 layout check.
The replay reaches authored room check tasks, but R100Init fails enemy creation:
4,006,016 bytes requested with 409,152 free. Earlier the required block-model
pool also fails: 1,126,272 requested with 419,456 free. Repeated enemy loads see
343,552 free. This is incomplete initialization, not a playable room.

Next: account for and adapt the actual block/enemy/resource working set without
removing required geometry, animation, effects or gameplay capacity. Use native
resource ownership and existing mechanisms; preserve qualified loader semantics.
See [R4_EVENT_ENEMY_CHECKPOINT.md](R4_EVENT_ENEMY_CHECKPOINT.md). The required
D312 mirror manifest passes; r101 still rejects unsupported EVS. GX/audio stubs,
ID/effect errors and module reload/reset behavior remain open.

D313 adds selectable compact native-module descriptors through the existing
mirror/binder: 46,464 live heap bytes recovered, em12 demand reduced by 428,288.
Both block/enemy allocations still fail. See
[R4_STATIC_MODULE_STORAGE_CHECKPOINT.md](R4_STATIC_MODULE_STORAGE_CHECKPOINT.md).
Next connect bounded resource ownership based on the source-active texture set;
retaining all images as 16-bit native textures would exceed VRAM. Preserve source
metadata, CPU users and the existing accepted viewer reference.

D303's source-derived first-play opening skip still reaches r100 through normal
stage initialization; r120 is cinematic staging, not a playable room. Its D302
qualified transport remains a separate reference. D304/D305 extend the existing
mirror rather than adding a decoder or loading system. See
[R4_ROOM_ENDIAN_CHECKPOINT.md](R4_ROOM_ENDIAN_CHECKPOINT.md) for exact identities,
coverage limits and tests. No visible menu, completed room, manual play, audio
output, performance or physical-hardware acceptance is implied by these logs.

After first-room manual acceptance, package the proven approach as an Astra
light skill according to AGENTS.md; keep the three-room goal and wider backlogs.

## Integration correction: reuse the whole available implementation

User clarification, 2026-09-21: step back from one-failure-at-a-time archive
integration and use the recovered source and working native systems together.
This changes task selection, not the menu/three-room objective or fidelity rules.
Whole qualified room archives already load; the fragmentation is in subsystem
integration. Do not confuse conversion progress with renderer/resource readiness.

The next implementation unit is the recovered game's resource-to-render path.
Before editing it, make one bounded source-to-native dependency/ownership map
for the current opening route, then implement against that map. Use current code
and accepted artifacts; do not reconstruct completed mechanisms or audit the
entire game's source as a new prerequisite. Keep focused checks inside the slice,
but choose the slice by the combined gameplay, memory and presentation result.

| Existing implementation to reuse | Connection still required |
|---|---|
| `src/game/trans.cpp` model eligibility, selected lights, pose/normal preparation and material setup | Feed source-authoritative current models/camera/material state into native rendering; preserve gameplay/event updates. |
| `room/pvr_geometry.*` clipping/packets (D317), remaining strips/lighting in `room/main.cpp` | Reuse applicable helpers with recovered-game inputs. Its `render_scene` currently takes prototype Player/Enemy/package state; copying that gameplay loop would be a regression. |
| `tools/convert_tpl.py` and `room/texture_package.*` native layout, sharing, upload and payload release | Maintain source texture/material identity and CPU users; connect upload success and handles to source-owned resources. Do not invent another converter. |
| `room/room_storage.*`, `load_room_texture`, `room_gpu_quiesced`, `retire_room` | Adapt these ownership/failure/fence contracts to core, player, weapon, room, block and event lifetimes; avoid a second full resident copy or an unreclaimed reservation. |
| Recovered source collision, streaming selection, actor/event/module logic; existing native input/audio mechanisms | Keep source behavior, identify adapters and actual missing consumers together. ARAM staging is not AICA memory; current no-copy/audio stubs remain missing functionality. |

Budget the combined menu-to-room working set: core/UI, Leon, weapon, authored
enemies, source-selected blocks, effects/events, staging, main RAM, VRAM and
AICA. Include pause/retry/transition ownership. The D313 image inventory is a
capacity lead, not the active set. Do not reject the optimized pipeline using an
all-images-expanded estimate, or assume all existing viewer assets cover source
menu/event/material semantics. Preserve original/GameCube and accepted native
references; only explicit measured tradeoffs may change presentation.

Require a source-driven visible result and measured resident/loading costs as
the next integration milestone. Use smaller fixtures to validate adapters, but
do not require every remaining source subsystem to run headlessly before wiring
native graphics/audio. Keep missing data conversions explicit and resume normal
boot/New Game progression in the same target; no separate replacement game.

## Opening-route evidence (partial; third room and exit gates open)

| Position | Room | Entry/progression evidence | Required exit / acceptance |
|---|---|---|---|
| Cinematic staging; not counted | r120 | `src/st1/r120.cpp::R120Event` first-play skip/completion reaches r100; D303 implements persistent effects. | Presentation skipped; required gameplay effects retained. |
| First playable room | r100 | Source r120 jump, normal stage/load entry verified in D305/D306. | Authored AEV door targets r101; event/unlock conditions and manual completion remain unverified. |
| Next connected room | r101 | r100 AEV destination is r101; gameplay qualification remains open. | Verify normal entry, required village combat/events and onward exit. |
| Third playable room | Unresolved | Trace matching opening event/door data, not numerical order. | Record ID and required completion/transition conditions once verified. |

## Binding correction

**Advance the recovered game from normal startup through continuously playable
content. Stop optimizing scene viewers as a substitute for porting the game.**

The primary workstream is source-system integration from boot. Complete the
systems needed to play the opening sequence coherently, then extend progression
through the opening chapter and Disc 1. Do not wait for every late-game system,
debug editor, SDK function, or middleware routine to be ported before playing
anything. Equally, a scene that merely draws does not count as gameplay progress.

The former Scale Gate (20 FPS plus a room transition before boot-forward work)
is **retired as an integration prerequisite**. Approximately 20 FPS remains an
intermediate playability measurement; approximately 30 distinct presented FPS
at the intended 640x480 output on stock Dreamcast remains the final target unless
the user explicitly approves a different target. Neither benchmark blocks safe
integration. Performance work during integration must remove a demonstrated
memory, correctness, or practical testing blocker, or address a substantial
bottleneck in a representative playable sequence.

A commit boundary is not a stop instruction. Continue through routine dependent
implementation, testing, and integration without requesting another prompt for
each newly exposed dependency. Preserve working code and user changes. Escalate
material fidelity decisions, unavailable required assets or hardware, and
consequential tradeoffs that evidence does not resolve.

## Reconciled starting point

This revision was reconciled against `b7d29e3` and its ancestors. Recheck actual
HEAD and the local tree before implementation; do not reset to this revision.

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| `5055eeb` and subsequent lifecycle/fence fixes | Owned room load, retirement, reload, and failure recovery infrastructure exists. | A normal source-driven room transition or campaign flow. |
| `a00d967`, `17f3a32`, `5f42caa` | Transient CPU texture backing, explicit upload completion, and corrected partial-upload test wiring. | All assets or runtime states are qualified. |
| `8a44852`, `70e77e3`, `d14a2c8` | Reduced duplicate connectivity, bounded accelerator coverage, full-width global vertex identities, and boundary repairs. | Whole-village performance or complete source presentation. |
| `17f6ae2` | r101 environment loads and renders diagnostically. | An authored gameplay camera, village encounter, or a 640x480 result; its reported diagnostic capture was 320x240. |
| `fbd0012` | Leon and r101 are integrated independently of the cabin enemy, at 640x480. Reported sweep CPU-frame median is about 87 ms, p90 about 200 ms; minimum reported free main RAM is 1,757,184 bytes. | Source-authentic entry/progression, physical-console performance, or a playable village fight. |
| `b7d29e3` | Snapshot capture now stops on the exact requested simulation tick. Across the six tested snapshots, 91-133 room batches per frame using the fallback matched the local path with no divergent batch records. | Universal renderer equivalence. The earlier 5/21 and 11/22 comparisons are not evidence of a remaining renderer defect; they compared different actual ticks. |

These are repository-reported results, not new measurements from this planning
change. Keep identities, limitations, and corrected evidence attached to their
checkpoints. Do not reopen the tested fallback mismatch or call it simulation
nondeterminism without a new same-state reproduction after `b7d29e3`.

The repository documents a matched GameCube debug-build decompilation, not a
finished Dreamcast game. Recovery of source bytes, native compilation of a
function, and integration of its gameplay behavior are different milestones.

## Architecture and source authority

Use the matching GameCube debug build, its decompiled code, and the user's
matching private assets as the gameplay authority. Trace real call paths and
state dependencies. Do not assume retail PS2 content or public gameplay footage
matches that debug version merely because names or room numbers agree.

Prefer compiling/adapting recovered gameplay systems over repeatedly recreating
their visible effects in `port/dreamcast/room/main.cpp`. Preserve source control
flow, state transitions, scheduling, input/RNG/event order, object identities,
and data dependencies where they affect behavior. Adapt platform interfaces for
SH-4, KallistiOS, PowerVR, AICA, storage, input, and saves. PowerPC assembly,
GameCube addresses/endianness, SDK and auxiliary-memory assumptions need explicit
adaptation; compiler-matching constructs are not mandatory target architecture.

Reuse the existing Dreamcast renderer, package readers/converters, collision,
animation, audio, input service, and room lifecycle. Retain useful adapters while
progressively replacing demo-only orchestration. Do not start a second gameplay
engine, second renderer, wholesale GX emulator, or new scene-specific framework.

The source reading guide is [docs/overview.md](../../../docs/overview.md).
Use it to enter the following call paths, then inspect the implementations:

| Integration responsibility | Source starting locations |
|---|---|
| Startup and game/stage/room state flow | `src/game/main.cpp`, `scheduler.cpp`, `game.cpp`, `title.cpp` |
| Task/event progression and trigger activation | `sce_sys.cpp`, `sce_at.cpp`, `event.cpp`, and the relevant `src/st*/` room modules |
| Resource/object ownership and display | `datactrl.cpp`, `block.cpp`, `scroll.cpp`, `model.cpp`, `trans.cpp`, `trans_ot.cpp`, manager and flag declarations |
| Player and enemy behavior | `src/pl*/`, `src/wep*/`, `src/em*/`, `em_set.cpp`, and their shared game routines |
| Camera, collision, and movement | `cam_ctrl.cpp`, `cam_qfps.cpp`, `cam_extra.cpp`, `atari.cpp`, related collision and route routines |
| Inventory, death/retry, persistent state | `src/Sscrn/`, item/game state, room-save flags, and the source save/retry call paths |
| Sound and opening media | `snd*`, `sofdec.cpp`, the actual startup/event callers, and the selected target audio/video adapters |

Paths without a directory above are in `src/game/`. This is a navigation map,
not a claim that every listed dependency is needed at once.

## Three sources of leverage, used together

The port draws on three complementary sources, and they are used together
rather than queued as separate research projects:

```text
GameCube decompilation      = behavioral / state authority
GameCube debug tooling      = development acceleration, reproducible fixtures
GameCube + PS2 render assets = candidate visual / resource representations
Dreamcast runtime           = target-native implementation
```

The decompilation decides gameplay behaviour, progression, state machines,
camera, collision, events, object activation, scheduling, room transitions and
the original visual target. The recovered debug systems are the preferred way to
reach and exercise a section without inventing scene fixtures. The PS2 release
and its established extraction tools are an authored constrained-platform
reference: alternative geometry, textures, materials, collision representations,
model variants, effects, audio/video presentation and other reductions Capcom
actually shipped. PS2 gameplay logic never replaces GameCube gameplay; a
diagnostic viewer never replaces source state; the most expensive GameCube
render asset is not insisted on where an authored compatible lower-cost
representation demonstrably preserves the intended result.

Since `cb0d60a` the game's own `main()`, scheduler, title, `GameTask` and room
initialization compile for SH-4 (`port/dreamcast/game`, see
[R4_GAME_TARGET_CENSUS.md](R4_GAME_TARGET_CENSUS.md)); the fixtures below drive
that executable, not a viewer.

### The standard toolbox

**Recovered debug systems** (source-authored acceleration; recover the useful
semantics, not necessarily the original UI): `cRoomJmp` / `CRoomInfo` /
`RoomJump`, the title debug-start menu, `debug/config.txt` / `ConfigSet()`, the
debug camera, FLAG EDIT, EVENT TOOL, SCENARIO ATARI, ROUTE CHECK, BLOCK AREA
TOOL, ITEM SET TOOL and EM INFO TOOL (details in the numbered list below).
Prefer `stage + room + authored jump point -> source NextPos / NextY /
next_room / next_point -> normal room and game initialization` over hard-coded
spawn constants, an arbitrary camera and a diagnostic sweep.

**PS2 extraction / adaptation toolchain** (candidate tools, applied to the
supplied private PS2 image; verify the exact tool, version and format
compatibility before relying on output): JADERLINK_DATUDAS_TOOL and AFS
parsing for `BIO4DAT.AFS` / `BIO4MOV.AFS` / `BIO4MOV2.AFS` (archives),
RE4-PS2-SCENARIO-SMD-TOOL (environment/scenario geometry), RE4-PS2-BIN-TOOL
(character/object models), RE4-PS2-TPL-TOOL (textures), RE4-SAT-EAT-TOOL
(collision), RE4-MDT-TOOL and FNT/UI inspectors (text/UI data), vgmstream
(audio), SofdecVideoTools / SFDExtractor and other validated SFD demuxers
(prerecorded movies). The list is not exhaustive: an established RE4-specific
tool that materially accelerates the current slice is evaluated before a parser
is rebuilt, and "find every PS2 tool" is not a project of its own. The policy
for using the output is in
[R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md); the PS2 track runs
in an isolated worktree with private generated-asset and evidence directories,
bounded to representative cases, and never interrupts boot-forward integration.

## Development fixtures: the recovered debug tooling

Two paths, kept distinct:

* **Acceptance** is cold boot -> normal title/new game -> normal game
  initialization -> normal events and gameplay -> normal room transition ->
  the next playable section. Only this path proves progression.
* **Development acceleration** is a source-authored debug fixture -> the
  selected stage / room / jump point / relevant source state -> the normal
  room initialization and gameplay systems -> exercise and debug that section.
  A debug jump proves a section can run from a valid source-authored state; it
  does not prove the preceding gameplay reaches it. Both are required.

The recovered debug build already carries Capcom's mechanisms for starting and
advancing gameplay at controlled points. They are first-class tooling of this
port. Invented spawn constants, diagnostic sweeps and per-room executables are
no longer the default way to bring a section up.

1. **`cRoomJmp` / `CRoomInfo` / `RoomJump`** (`include/room_jmp.h`,
   `src/game/room_jmp.cpp`) is the authoritative room-position fixture. The
   table `debug/roominfo.dat` (loaded by `systemRestartInit`, on disc 1 at
   10,790 bytes: 5 stages, 4/52/83/67/16 points) holds per point
   `flag` (bit 0: position valid), `roomNo` (stage << 8 | room), `pos`, `angle`
   and the authored name, screen and programmer strings.
   `CRoomInfo::setNextPos()` writes exactly the state the game consumes on a
   room change: `NextPos`, `NextY`, `room_id_prev`, `Part_old`, `next_room`,
   `next_point = 0`. The tool exits through `roomJumpExit`, which sets
   `pG->Rno0 = 4`, i.e. the normal door-demo room-change routine
   (`gameDoordemo` -> `gameStageInit` -> `gameRoomInit`); it never teleports
   a player inside an already-running scene. The Dreamcast adaptation keeps
   that semantic: a fixture enters through the room-change path. Do not
   invent `kSpawn*` values where an authored jump point exists (stage 1 has
   "MORI" for r100, "MURA" (-51510, 165, 21834), angle 2.33 for r101, and
   named points for every village room). The AEV door destination remains
   the natural-progression entry; the jump point is the fixture entry; both
   are source-authored, and a report says which one a capture used.
2. **Title debug-start path** (`titleDebugMenu`, `titleExit` in
   `src/game/title.cpp`). Before `titleExit` chains into `GameTask` the menu
   edits, in `pG`/`pSys` and the title work: player type (`pl_type` 0..6),
   load number, stage / room / jump point through `cRoomJmp`, the enemy list
   (`em_list_no`, with the `Scenario_flg[0]` bits for lists > 2/3), debug
   page (`debug_mode`), ENEMY SET (`Debug_flg[2]` 0x00200000 set = OFF),
   ETC SET (`Debug_flg[3]` 0x00000800 set = OFF), sound mode, SCENARIO
   (`Debug_flg[2]` 0x04000000 set = OFF), USE DBMEM (`Debug_flg[3]`
   0x00200000 set = ON), shooting mode,
   Ashley costume, language/region, game mode and one more `Debug_flg[2]`
   0x400 switch; then `getRoomInfo(...)->setNextPos()`, `System_flg |=
   0x2000` (new game) and the normal `GameTask` start. This is the preferred
   way to start at a source-defined location. The exact original UI is not
   required at first: a Dreamcast developer interface or configuration file
   that drives the same fields with the same initialization semantics is
   acceptable. The title menu has SOUND MODE, not a BGM enable switch.
3. **`debug/config.txt` / `ConfigSet()`** (`src/game/debug.cpp`, read in
   `systemRestartInit`) is the source-authored precedent for deterministic
   fixtures: `[USER]`, `[BRIGHTNESS]`, `[STAGE]`, `[ROOM]`, `[JUMP_POINT]`,
   `[PRINT_PAGE]`, `[PLAYER]`, `[BGM]`, `[SE]` and further switches (the disc
   copy sets STAGE 0x01, ROOM 0x20, PLAYER 0, GAME_MODE NORMAL, TITLE_CUT OFF).
   Plan a small Dreamcast-side developer configuration selecting at least
   STAGE, ROOM, JUMP_POINT, PLAYER, SCENARIO on/off, enemy on/off and the
   relevant source debug/start flags, consuming `roominfo.dat` and the source
   fields rather than duplicating positions into build-time constants. One
   executable, data-selected rooms. ConfigSet BGM OFF sets `Debug_flg[2]`
   0x00100000; SCENARIO OFF sets word 2 mask 0x04000000; ENEMY_SET OFF
   sets word 2 mask 0x00200000; ETC_SET OFF sets word 3 mask 0x00000800.
   NO_ENEMY uses inverse wording: ON disables enemies, OFF enables them.
   Evidence must record the effective scenario, enemy and object-setup switches
   after configuration/title choices, so disabled behavior is not misdiagnosed
   as missing implementation. This does not change runtime flags.
4. **Debug camera** (`src/game/db_cam.cpp`, `CamDbg` from `CameraMove` on pad
   1: orbit / dolly / zoom, target the selected enemy, object or player,
   B returns control to the gameplay camera) is a visual-inspection tool for
   geometry, materials, collision and matched-reference captures. It is not a
   substitute for `CamCtrl`, room CAM data or gameplay-camera acceptance.
5. **Near-term audit of the remaining tools**, recovering the smallest useful
   semantics and data paths, not whole editors: FLAG EDIT
   (`src/game/t_flag.cpp`, pages of the flag words with per-bit names),
   EVENT TOOL (`src/t_event/t_event.cpp`), SCENARIO ATARI
   (`src/tools/t_sce_at.cpp`), ROUTE CHECK (`src/Tools/t_rck.cpp`),
   BLOCK AREA TOOL (`src/t_sce/t_block.cpp`), ITEM SET TOOL
   (`src/t_sce/t_sce_item.cpp`) and EM INFO TOOL (`src/Tools/t_eminfo.cpp`,
   with the ESL editor `src/t_emlist/t_emlist.cpp`). Decide per tool whether it
   accelerates source-state reproduction, event testing, enemy set-up, room
   progression, collision/trigger inspection or later-room debugging.

The workflow for new content is:

1. identify the next real gameplay section from the source;
2. create a reproducible fixture with the room/jump/state tooling;
3. run it through the normal room / player / camera / scenario systems;
4. implement the missing dependencies until the section works;
5. iterate and regress on the fixture;
6. return to the preceding natural gameplay path;
7. prove normal progression reaches the same state;
8. move the playable frontier forward.

The tooling accelerates development and does not redefine gameplay. The
GameCube decompilation stays authoritative for progression, scenario/event
state, player placement, camera behaviour, collision, enemies, object state
and room transitions. A fixture may initialize those values directly where the
original tool does; it must not fabricate a state the game could never produce.
When a fixture bypasses prior progression, the report labels which state was
injected and which systems actually executed. The same fixtures are the
comparison harness for the GameCube/PS2 render-asset experiment: compare
candidates at the same authored room, jump point, player/camera state and
scenario state, never from free-camera screenshots or unrelated positions.

After every coherent integration slice the question is: how far does the real
game now execute from normal startup before the next missing dependency stops
it? The substantive report answers, in this order: what executes from normal
boot; what later state a source-authored fixture reaches; which recovered
systems were integrated; whether any PS2 or alternate representation was
actually tested; measured memory/performance at the representative state; the
next precise missing dependency blocking natural progression.

## Continuous playable milestones

These are integration slices, not a requirement to finish every subsystem in
isolation. Maintain a runnable build and continue after each milestone.

1. **Normal boot to source new-game initialization.** Execute the recovered
   startup/title/new-game control flow through appropriate platform adapters.
   Establish scheduler, input, memory, resources, and initial game state. Trace
   the actual opening route rather than assuming the cabin viewer is startup.
   Render and operate the title/main menu, including required startup prompts.
   Opening cutscene presentation may use the authorized skip policy above;
   required initialization and event-completion behavior must still execute.
2. **Opening gameplay through the first coherent encounter.** Integrate the
   source player/camera/environment/object state, triggers, relevant enemy AI,
   weapon behavior, collision, audio/HUD, and event transitions. Exercise human
   movement, aiming, firing, reload, interaction, and the applicable death/retry.
   Replace manual post-cutscene flag/spawn fixtures with source-derived
   initialization and completion paths under the authorized cutscene-skip policy.
3. **Persistent gameplay across the first authored room transition.** Use one
   executable and the existing lifecycle to enter r101 from r100 with correct
   entry/camera/object state and player persistence. Respect the source's door
   availability and room flags; a graph edge does not prove a door is currently
   traversable. Exercise return/retry where the source allows it. Blocking loads
   behind the authored transition are acceptable before I/O optimization.
4. **Complete the verified three-room opening route.** Prove consecutive manual
   play from the main menu through all three rooms and both transitions, including
   required events/combat, audio, death/retry and allowed re-entry. Cutscene
   presentation is deferred under the explicit policy above. The complete
   three-room sequence remains open; use the source/data evidence table above.
5. **Deferred: content beyond the verified three-room route.** Continue into
   the rest of the opening chapter and Disc 1 afterward. Any village enemies,
   objects, interactions, combat, events, inventory, audio and exit conditions
   needed to complete the three-room route remain in the current milestone.
   Entering or rendering a room is not completing its gameplay.

The completion measure is the longest repeatable, normally controllable sequence
reached from boot, with required systems classified as source-integrated,
behavior-preserving adaptation, diagnostic stub, or unimplemented. Keep that
small coverage ledger here as implementation advances. Do not report completion
percentages based only on symbol counts or compiled source lines.

A development checkpoint may remain slow or incomplete. An accepted continuous
sequence must not depend on an undisclosed skip, inert event, fabricated enemy,
manual state patch, or standalone room executable.

## Representative scene execution

Recover game state before optimizing the workload:

    game/room state -> resource and object activation -> player -> evaluated
    camera -> source display/visibility -> Dreamcast preparation and rendering

For r101, trace the actual incoming door/AEV destination, orientation, room part,
initialization, and relevant flags. RTP point 0 is a navigation fixture, not
proof of player entry; the authored development entry is the `roominfo.dat`
jump point (see the fixture track above). Read `.CAM` with its consuming routines; recover the
resulting camera, collision pull-in, interpolation, FOV, viewport, near/far/fog,
and coordinate conventions rather than transcribing one attractive shot.

Distinguish resident resources, active objects, and submitted geometry. Verify
source display/part/event rules and necessary set dressing. Do not invent an
occlusion/PVS system because a view is expensive, mistake a light mask for a
visibility mask, or assume every exported alternate is concurrently displayed.
A broad source view is legitimate and must not be narrowed to claim a win.

Use the existing Leon implementation with the appropriate source state,
independently of missing village enemies. Player, enemy, HUD, camera, and
diagnostic-driver availability must not share one cabin-only switch.

Compare selected entry/movement states against the matching GameCube build using
existing tools where available. Record actual state and camera parameters.
Unmatched public footage or equal elapsed time is not a same-state reference.
Lack of an existing source capture permits clearly labeled provisional
integration; it does not justify a large new emulator harness as a prerequisite.

## Supporting workstreams and asset policy

Integration owns priority. Performance and residency work enable this sequence;
they do not replace it. During integration, fix safety issues, impossible memory
peaks, untenable loading, or frame costs that prevent useful playtesting. Defer
speculative micro-tuning until representative gameplay identifies the cost.

[REALTIME_PATH.md](REALTIME_PATH.md) defines reproducible timing and acceptance.
[R4_ASSET_RESIDENCY_PLAN.md](R4_ASSET_RESIDENCY_PLAN.md) authorizes a bounded
parallel experiment using compatible lower-detail GameCube assets and extracted
PS2 render assets. The old prohibition on any PS2 asset entering a private
candidate is superseded. Start with equivalent village environment content and
one representative enemy, not a campaign-wide asset database.

GameCube behavior/collision/progression stays authoritative. PS2 geometry,
textures, or prelit render attributes are candidate presentation inputs, not a
replacement game engine. Verify object placement, materials, rigs, attachments,
and source-version compatibility. Preserve the GameCube render reference and
label every alternative. A measured faithful adaptation is not automatically
pixel-identical to GameCube. Promote a material visual tradeoff only with explicit
review/user acceptance. Do not download or commit copyrighted game assets;
converters operate on locally supplied private images.

Use one owner per mutable checkout. An isolated helper may deliver one bounded
asset candidate or read-only source trace; it must not select overlapping
follow-on work or modify shared build/evidence outputs. Review and integrate its
commit through the primary owner.

## Execution, validation, and stopping rules

- Read producer/consumer and lifetime paths, not just snippets and comments.
  Implement routine dependencies within the slice. A discovered guard, parser,
  optional-resource, or scene-state dependency is work to complete, not an
  automatic reason to return another proposal.
- Preserve valid memory, range checks, resource ownership, GPU/audio completion,
  and failure rollback. Unsafe execution blocks running. An unresolved visual
  difference blocks fidelity acceptance, not all memory-safe diagnostics.
- Test the changed contract at relevant boundaries, then run integrated
  regression at a coherent milestone. Do not repeat every historical emulator
  campaign after each small change. Keep timing runs separate from instrumented
  image/digest runs and collect exact simulation snapshots after `b7d29e3`.
- The source game arbitrates correctness. An accepted prototype is a regression
  reference, not a requirement to preserve a discovered source-behavior bug.
  Document intentional source-correctness changes separately from pure speedups.
- Commit reviewable, tested pieces and keep progressing. Update these existing
  plans only when facts or decisions change; do not create another parallel
  roadmap or return a checklist instead of working runtime behavior.
- Escalate only an actual decision or unavailable prerequisite. State the exact
  failing operation, evidence, viable remedy, and independent work that can
  continue. Do not claim local tree cleanliness, human play, or hardware evidence
  that has not been checked.

Every substantive report must lead with: what can now be played from boot;
which source systems now execute; a capture/launch identity; actual resolution,
complete memory peak and frame-time distribution; and the next concrete blocker.
No requirement to achieve 30 FPS before reporting a working integration slice.
Final acceptance still requires responsive human control and physical hardware.

## Historical evidence, not current instructions

The previous 30-second r100 brief, source-ownership ledger, hashes, and deadline
fallback are preserved in the [pre-amendment PLAYABLE_PATH](https://github.com/stevedamnvan/re4/blob/b7d29e3fe9ba58b807ef2146776b09caf1acbaea/port/dreamcast/docs/PLAYABLE_PATH.md).
The pre-amendment [REALTIME_PATH](https://github.com/stevedamnvan/re4/blob/b7d29e3fe9ba58b807ef2146776b09caf1acbaea/port/dreamcast/docs/REALTIME_PATH.md)
and [R4 plan](https://github.com/stevedamnvan/re4/blob/b7d29e3fe9ba58b807ef2146776b09caf1acbaea/port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md)
retain their former measurement ledgers. All separate checkpoint documents and
private evidence remain untouched. Their old task order, single-scene scope,
20-FPS integration prerequisite, and PS2-oracle-only restriction are not active
instructions. This document and its two supporting policies supersede them.
