# r101 source-entry checkpoint

Leon stands in the village where the source puts him when he walks through the
gate from r100, under the camera the source evaluates there, with r101's own
lighting and collision, and the controller drives him. This supersedes the
diagnostic placement and diagnostic camera of the r101 diagnostic render
checkpoint. It is a source-correct integration milestone for the player,
environment, collision and camera; it is not village gameplay (no enemies, no
events, no door progression, no area cameras), and it is not performance
qualified.

Acceptance levels, kept separate:

* execution-safe diagnostic: reached at 17f6ae2 (village renders, no player);
* source-correct integration: this checkpoint for player placement, initial
  camera, environment, collision and lighting, with the fixture limits below;
* performance-qualified gameplay: not reached; numbers below.

## Corrections to earlier reports

* The r101 diagnostic captures (d282) were 320x240, the Makefile default at
  the time. The r100 and r101 targets now default to 480p
  (`DEMO_RESOLUTION ?= $(if $(filter r100 r101,$(DEMO_SCENE)),480p,240p)`),
  and every number in this document and in d283/d284 is at 640x480. d282
  frame times are not comparable to these and are not used.
* The "unresolved fallback rendering mismatch" carried since d281 was a tool
  artefact, not a renderer difference: the snapshot freeze tested per frame,
  so a slower build ran one extra simulation tick before freezing. With the
  freeze at the exact tick (`snapshot_tick_due()`, b7d29e3) six frozen ticks
  compare with identical state, identical batch order, 91-133 room batches on
  differing paths, and zero divergent per-batch digests (header, positions,
  colours, all bytes). The batch-local and fallback paths are packet-identical.

## What the player can do

In r101 at 480p, with the cabin Ganado and its encounter absent
(`kSceneHasPlayer = true`, `kSceneHasEnemy = false`): walk and turn with the
existing Leon movement, animation and root-motion systems against r101's SAT
collision; aim and fire the handgun with the existing weapon pitch, ready
camera and muzzle systems; HUD as in r100. Damage, death and reload systems are
compiled in but nothing in the room can hurt him.

Capture (`d284-r4-r101-source-entry/frames-sweep-480p/t010..t058.png`, the
`r101-sweep` build's scripted 12-second move/turn/aim cycle standing in for
controller input): t010 walking away from the gate down the entry path, t014
turned back with the village gate in view, t030 the walking camera behind Leon
facing the gate. The plain `r101` build is the controller-driven one; the sweep
build differs only by `-DRE4DC_DIAGNOSTIC_SWEEP`.

## The source state being reproduced

Traced, not inferred:

* Transition: `r100_016.AEV` record 0, type DOOR, dstStage 1, dstRoom 0x01,
  dstPart 0, dstPos (-52144.40, 90.57, 22524.27) mm, dstAngle 2.1220217 rad.
  `sceAtFunc_door` (src/game/sce_at.cpp) copies these to `NextPos`, `NextY`,
  `next_room_no`, `next_point`; `gameDoordemo` (src/game/game.cpp) places the
  player at `NextPos`, sets `sub_angle = NextY` and `Part = next_point`.
  The runtime's yaw is the source `ang.y` unchanged, the same convention r100
  already uses (`r100_Sce_look` writes `ang.y = 1.75f`, the r100
  `kSpawnYaw`). Constants: `kSpawnX/Y/Z = -52.1444023, 0.0905708, 22.5242734`
  m, `kSpawnYaw = 2.12202168`.
* Room state fixture: first visit. `R101Init` (src/st1/r101.cpp) takes its
  first-visit branch when `Item_find_flg & 0x2000` and Rsf 6/7 are clear:
  `r101_checkFindPlayer`, the evt00 encounter at AT 7, obj00 placed for
  region != 0, doors 0xB locked, racks and ladders off unless Rsf 8. None of
  those enemies, events or objects exist in this runtime; the fixture is the
  entry position, orientation and part only, and the room's static geometry
  is what the diagnostic checkpoint exported (all cells, not a
  state-selected subset). That is the explicit limit of this checkpoint.
* Camera: `r101_000.CAM` parsed with the consuming code (`CameraCtrl::Check`,
  `areaHitCheck`, `CameraQuasiFPS::setAreaData`, `bindDefaultCamera`,
  `bindAreaCamera`, `checkCameraType`, `calcOffset`, `move`). The parser was
  validated on `r100_000.CAM` (area 2 entries 7/19 reproduce the hand
  transcription already in the r100 scene). r101 has 20 areas; none contains
  the entry point, so `areaHitCheck` finds nothing and `bindDefaultCamera`
  binds the default tables. For Leon (`pl_type 0`, `m_trans_type 0`) with no
  C-stick pitch the walking camera is `g_transOfs[0][0][1]`: Campos
  (-500, 1765, -1190), campos2 (-180, 1700, -110), target (0, 1340, 1480),
  fovy 50; the aiming camera is `g_readyOfs[0][0]` blended by weapon pitch,
  which r100 already implements and r101 shares. Offsets are applied in
  player space by `player_offset_to_world`, the close point feeds the SAT
  wall correction `correct_source_camera_walls` (the Dreamcast adaptation of
  `CameraQuasiFPS::hitCheck`), and the fov is the table's. Interpolation,
  the `lr_rate` x smoothing and blend-on-type-change are not implemented;
  the camera is the evaluated static offset.
* Not evaluated yet: position-dependent area cameras. Areas 2, 3, 6 and 7 of
  r101 carry type-8 quasi-FPS cuts that override the tables when the player
  enters them; the runtime does not test areas per frame, so leaving the
  entry region keeps the default camera where the source would switch.

## Memory (r101-sweep, 480p, `install-memory-480p.log`)

Free main RAM: boot 2,887,680; after packages 2,822,144; after tables
2,822,144; low mark during batch-local preparation 1,757,184 (batch-local
scratch 1,062,192 bytes, released); steady state 2,646,016. Room arena
8,560,640 of 8,912,896. PVR 5,635,840 before textures, 2,429,480 after. AICA
free 1,542,592. Unchanged from d283: the placement change moves no data.

Boot on the plain `r101` disc: stages 31 to 47 in 3.6 s, fault record all
zero for 60 s (`boot-plain.log`).

## Frame times (r101-sweep, 480p, 150 s, 1,579 frames)

frame_us p10/p50/p90/max = 40.5 / 65.7 / 139.6 / 541.1 ms. Phase medians
(slow-decile medians in brackets): opaque_room 38.9 (273.2), submit 49.4
(304.7), actor_lighting 9.1 (9.1), opaque_actor 6.5, actor_pose 3.9,
translucent_room 3.0 (23.3), room_visibility 1.5 (4.9), pvr_wait 0.
d283's sweep from the route point gave p50 85.6 ms and opaque_room 56.4 ms;
the difference is the view (the entry path looks at less of the village than
the route point did), not a renderer change, and is not reported as
progress. CPU room submission still dominates and PVR never waits.

## Remaining blockers

1. Area cameras: per-frame `areaHitCheck` over the CAM areas and the type-8
   cut tables, with the blend on switch.
2. Enemies, events, objects and door locks of `R101Init`'s first-visit state.
3. Door progression: one executable carrying the player r100 -> r101 through
   the AEV door (this checkpoint fixes the destination side of that door).
4. Room submission cost (opaque_room median 38.9 ms, slow decile 273 ms) at
   the pinned 640x480.
5. Hardware validation and human acceptance.

## Evidence

`C:\Flycast-Evidence\re4-dreamcast\d284-r4-r101-source-entry\`: `r101.bin/.cue`
(controller build), `r101-sweep.bin/.cue`, `boot-plain.log`,
`install-memory-480p.log`, `frames-sweep-480p/`, `telemetry-sweep-480p.jsonl`,
launch and reader scripts. Symbol offsets are recomputed per build with
`sh-elf-nm` and recorded in `MANIFEST.txt`.
