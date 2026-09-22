# D349: recovered r100 renderer performance reference

2026-09-22. Historical source: `5f42caa634c0e6124c48842e21570033738adfda`.
Primary recovered-game HEAD at recovery: `961c51ef3e2ee51b2fd583cd213a0302705bccb7`,
with its existing uncommitted integration overlay preserved. No reset, downgrade,
asset regeneration, or experimental renderer promotion occurred.

## Disposition and user review

Keep this **historical presentation/performance reference** for integrating the
working room renderer into `re4dc-game.elf`. The user reviewed the fresh manual
run: the overall appearance looks great, but the character faces the wrong way
relative to the correction in the newer native build. That orientation is a
known defect, not an acceptance constraint. Retain the newer correction when
reusing the renderer. This does not certify every character component/pose,
source gameplay, complete menu interaction, three rooms, or physical hardware.

The cabin, textured Leon and Ganado, handgun, HUD, source-derived lighting, and
game sounds are present. Manual observation captures show the Ganado approaching
and attacking; a later framebuffer shows player death. Appearance evidence is
separate from the timing run. The room executable still uses its historical
reduced gameplay loop and sampled animation; none of that becomes the recovered
game's authoritative AI, camera, motion/event selection or progression.

## Recovery and reproducibility

- Isolated detached worktree: `/root/work/re4-r100-reference-5f42caa`.
- Preserved original evidence: `C:/Flycast-Evidence/re4-dreamcast/d278-r4-one-representation`.
- Fresh evidence: `C:/Flycast-Evidence/re4-dreamcast/d349-r100-reference`.
- Recovery scratch: `/root/probe/d349-reference-recovery`.
- Exact asset map, individual sizes/hashes, build/compiler/library/emulator
  identities and operational patch: `reference-manifest.json`,
  `recovery-manifest.json`, `asset-name-map.json` in the fresh evidence folder.
- Commands and recovery scripts: its `recipe/` directory. These are private,
  task-specific reproduction records, not another asset pipeline.

The preserved `candidate.elf` produces the exact unscrambled payload in
`cycle.bin`, **not** the later corrected `cycle2.bin`. All three preserved discs
contain `cycle.flag`; `snap.bin` is a separate diagnostic. They remain intact.
A clean benchmark cannot use these lifecycle/snapshot configurations.

All **22 required inputs** were recovered byte-identically from `cycle2.bin`,
including its embedded ROM filesystem, and copied to the isolated build's private
input directory under the names expected by its historical Makefile. No current
package was substituted merely because its filename matched. Geometry, textures,
collision, route, complete saved actor packages, HUD and eleven sound files retain
their original identities. The original `r10d.*` disc names carry the r100 data.

Build commands, in the isolated worktree, after private input recovery:

```sh
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room r100-autoplay
make -C port/dreamcast/room disc
# Preserve ELF, external-file disc and build flags before building the other arm.
make -C port/dreamcast/room r100
make -C port/dreamcast/room disc
```

The historical disc target is used. Its sole local tracked change redirects
`mkdisc.sh`'s hardcoded `/root/discwork` to
`/root/probe/d349-reference-discwork`, protecting primary scratch/output. No
runtime source changed. KOS and ports remained read-only and clean at the pins:

- KOS `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`.
- KOS ports `f4faacc42faaf552625777b7709e871a827e1055`.
- SH GCC 15.2.0, historical `-O3 -fno-predictive-commoning`, LTO, `-m4-single`.
- Flycast Windows product version `v2.7-14-g12bb43652`.

Both rebuilt executables are new artifacts, not claims of byte-identical ELF
reproduction. The complete private manifest records the exact tool binaries and
assets. Source .text/.data/.bss reported by `size` is
3,004,285 / 7,784 / 5,578,132 bytes (8,590,201 total).

| Arm | ELF SHA-256 | Disc SHA-256 |
|---|---|---|
| `autoplay` | `d6b4fb57a6e05a1016f36b223a3ff21f75bfab28bf1e58fbbc0cafd9cb4fa38c` | `28b6cff7cae4f21d6c21985824a1f3b19401b46bfb7e1efe5b87b1c9dacebec8` |
| `manual` | `817ce1926f323374143a90ec74699c82b813676e989f7c274b199beb52a2b1c9` | `643c86e7f1bccfa1a4507cb9579023a090a15802d1cd399cbe4447f3db6ec5e2` |

Emulator SHA-256:
`64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
Each arm has its own ELF/disc/config/logs. Do not write new runs over these files.

## Clean autoplay timing

The `autoplay/` arm ran alone for 120 host seconds with the historical emulator
configuration and no profile, digest, snapshot or lifecycle flag. Heavy builds,
audio/video recording and framebuffer capture were excluded. The existing D278
seqlock telemetry reader was reused with the exact rebuilt symbol
`0x8c2ef3a4`, 440-byte/version-20 layout and host polling shortened from 50 to
5 ms. It captured every telemetry frame **1 through 2,085**, no missing frame
IDs; final simulation tick 3,449. Exclude the first nine frames from steady-state
statistics. The 30-second source fixture repeats shooting, kill, reload, aim
hold, idle and encounter reset. It does not cover manual movement/aim extremes.
`autoplay_phase` is the older unused enum for this r100 fixture; do not infer
coverage from its constant value. Health/ammo/state and fixed ticks show activity.

| Segment | Frames | CPU work p50 / p95 / p99 (ms) | Page-flip interval p50 / p95 / p99 (ms) |
|---|---:|---:|---:|
| First 270 simulation ticks, after warm-up | 163 | 48.880 / 57.627 / 60.109 | 50.046 / 66.727 / 66.728 |
| Enemy alive, all repetitions | 122 | 48.799 / 54.833 / 55.609 | 50.046 / 52.548 / 66.727 |
| Entire steady sample | 2,076 | 57.559 / 57.636 / 60.112 | 50.049 / 66.728 / 69.230 |

The early median reproduces D278's approximately 48.879 ms CPU reference. The
full trace includes the more expensive later standing/camera state; its CPU
mean is 54.862 ms and maximum 61.948 ms. Do not advertise the early slice as the
whole encounter. Mean page-flip interval is 55.158 ms, approximately **18.13
unique presented frames/s**; worst sampled interval 100.092 ms. PVR render-time
median is 7.502 ms. These are distinct, overlapping pipeline quantities and
must not be summed or replaced by the reciprocal of CPU time.

Pinned KOS `pvr_get_stats()` returns `frame_last_len` in `frame_last_time`;
`PVR_SYNC_PAGEFLIP` records elapsed nanoseconds between completed page flips.
Thus these are guest presentation intervals, not just TA submission timing,
not the host monitor's scanout intervals, and not physical-console measurements.
They are sampled with their PVR frame identifiers, separately from current CPU
work; no assertion of a same-frame GPU/CPU additive breakdown is made.

Zero room retirements, failed loads, simulation overruns, discarded simulation
microseconds and input queue drops occurred. Autoplay does not measure real
controller responsiveness; its zero input-service counters are not a manual
latency result. All summary distributions and raw rows are retained in
`autoplay/timing-summary.json` and `telemetry.jsonl`.

## Observed memory and content

| Counter | Bytes |
|---|---:|
| Room package | 1,991,864 |
| Room arena used and observed high water | 3,343,712 |
| Reserved room arena | 3,440,640 |
| Main RAM free counter | 7,667,712 |
| Heap used counter | 139,780 |
| VRAM available | 3,030,856 |
| AICA available | 1,378,336 |

These reproduce the original documented residency counters. They are this
standalone room target's budget, not newly recovered source-game heap. They do
not establish loading/retry peaks for the full recovered executable.

The manual arm is `r100` without autoplay or cycle flags. Its private keyboard
mapping uses the working version-2 format: arrows move/turn, V aims, X fires,
S reloads, C (Dreamcast B) retries, Enter (Start) exits. These controls differ
from the recovered game. The user-facing instance was PID 31560; check its path
and live state before reuse. It is deliberately left open for the user, so
other agents do not have an emulator window until it is released.

Manual-only `rend.EmulateFramebuffer=yes` enables the existing corrected VRAM
reader. Pinned SH-4 `offsetof` verifies PVR frame-buffer records at byte 312,
view target at 44, dimensions at 332 and page count at 452; existing
`capture_ui_vram.py` bank/RGB565 decoding is reused. The 640x480 native readback
is observational, not a frozen matched-tick screenshot. Window captures retain
window chrome and are separately labelled. No blue/uncorrected readback is used.

`manual/audio-loopback.wav` preserves 29.355 seconds of actual stereo 48 kHz
host output. Correlation with the recovered source samples is 0.99729 for the
enemy swing and 0.99805 / 0.99954 / 0.99931 for Leon's three damage voices.
Peak signed PCM magnitude is 31,368, no full-scale samples. This establishes
actual game sound output; it does not certify absolute A/V drift, all cues,
absence of stutter or physical AICA behavior. The death voice was not confirmed
within that recording. No artificial silent audio track was substituted.

## Integration handoff

Preserve the room's proven pass organization, complete actor assembly,
source-normal/light preparation, visibility caches, native strip emission,
material headers and load/upload/retire/fence ownership as shared implementation.
Adapt source-owned model/instance, camera, pose, selected-light and resource
inputs; do not copy the prototype encounter loop or process models twice.
The historical facing defect must yield to the newer corrected native behavior.

The D348 shared-strip candidate in the primary tree remains default-off,
host-tested and built, **not target-measured or accepted**. Its shared functions
are `prepare_direct_strip()` and `triangle_visible_xy()` in `pvr_geometry.hpp`,
used by both room and recovered model paths. This is a first small connection,
not completion of the user's instruction to reuse the room renderer substantially
intact. Snapshot `/root/probe/d348-before`, scripts/build log under `/root/probe/`.
Current primary game ELF is that unmeasured build; D347e and both D349 executables
are separately preserved. Do not confuse the three targets or their measurements.

D347e confirmed delivered keyboard input and source movement, but its sampled
source CPU/render setup was approximately 1.60/1.54 seconds. The manual route was
stopped at the user's request to prioritize renderer reuse. Source events/combat,
lighting/material parity, sound/inventory and r101/r103 transitions remain open.
Keep the established three-room plan and agent isolation. This reference recovery
neither merges movie/water candidates nor completes the persistent goal.


### Concrete source-to-room integration boundary

The live connection is `commonModelTrans` -> `re4dc_draw_model_part`
(`game/model_bridge.cpp`) -> `re4dc_model_submit`. It already carries model,
instance/part identity, source-prepared position/normal buffers, modelview,
projection/viewport, source cull/depth/blend state, source alpha and the selected
texture descriptor. Extend this connection to the shared room implementation;
replace the diagnostic draw preparation underneath it, not source registration.

| Existing mechanism to extract/reuse | Recovered producer/consumer | Small new adaptation |
|---|---|---|
| `submit_room_strips`, cached visibility/transforms, triangle clip fallback | Source-registered static model instances and `ModelPart` streams | Prepare source-ID/material-preserving native draw records at conversion/load; supply current instance/camera state without a second whole-room representation. |
| `project_character` projection portion, `build_character_source_normals`, `build_character_lighting`, `draw_character` | `commonScreenMatSub`'s current skinned position/normal buffers, rigid original arrays, source-selected parts | Feed prepared source arrays and selected source lights into the existing native projection/light/draw work; bypass historical sampled-clip/deformation inputs. Source buffers stay valid only within their documented frame lifetime. |
| `compile_room_material_headers`, `compile_character_headers_for`, existing native texture handles | Actual source texture animation/swaps and material/depth/cull/alpha state | Bind source identity to existing native handles and header inputs; preserve newer source-facing correction. Reject unsupported effects explicitly until adapted. |
| Existing room opaque/punch-through/translucent/HUD pass organization | Current `re4dc_ui_begin`/`re4dc_ui_present` frame owner | Extend that owner beyond its diagnostic all-translucent stream, retaining source presentation holds, correct ordering and one PVR scene owner. |
| `texture_package`, `room_storage`, GPU fence/retirement | Current compact source resource and owner-release paths | Install/release native draw metadata under existing source owners; price temporary overlap and actual freed allocation. |

First preserve existing room-target output after extraction. Then switch the
recovered target through a default-off selector to this same implementation,
with source camera/pose/state unchanged and **one** preparation path per model.
Compare ordinary menu -> room entry, correct complete Leon/Ganado, materials and
lighting, firing/reload and clean retirement through the existing fixtures.
Measure CPU stages, page flips and source/KOS/VRAM allocations independently.
Expand that same connection to all required scene content; a bounded initial
model check is diagnostic, not the cabin restored. The reference frame rate is
an optimization target for comparable work, not a promise for the larger source
workload. Keep newer source behavior where the old prototype differs.
