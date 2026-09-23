# Claude handover: RE4 Dreamcast, paused at D366

2026-09-23. The operator requested **pause here**, a Claude-compatible handover,
and commits of in-flight changes. The app persistent goal is **paused**, not
complete. No implementation, optimization or emulator runs should start until
the operator resumes. This preserves the current sequence, not another roadmap.

## Entry points and preservation

- Primary repo: `/root/work/re4-dreamcast` in WSL Ubuntu-24.04, `dreamcast-port`.
  Windows: `\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast`.
- Read AGENTS.md, CLAUDE.md and port/dreamcast/docs/R100_NATIVE_CUTOVER_GOAL.md.
  Supporting backlogs remain PLAYABLE_PATH.md, REALTIME_PATH.md and
  R4_ASSET_RESIDENCY_PLAN.md. Do not reread all historical checkpoints as orders.
- Implementation HEAD entering this handoff: e02e264e7ff9ed4d1f2839ac924e4fdf020ec9ad.
  A subsequent documentation-only commit records this pause. Inspect live HEAD;
  these are references, not reset targets.
- Remote: https://github.com/stevedamnvan/re4.git.
- **75 inherited modified/untracked source/build/fixture files remain.** Their
  pause hashes are /root/probe/d366-native-cutover/pause-inherited-before.json.
  They were neither authored nor committed by this slice. Never broadly stage,
  reset or clean. HEAD alone does not reproduce the recovered-game executable.
- No owned Blender/Flycast process was left running by D366. Recheck processes
  and coordinate exclusive emulator windows before resuming.

## Locked architecture and state

Recovered GameCube source owns gameplay/state/camera/pose/activation/materials/
audio/progression/lifetimes. D349 native packages and renderer own presentation;
the live GX/ModelPart bridge is fallback. One PVR/frame owner. No prototype
gameplay, fixed camera, sampled animation or duplicate scene representation.

Keep exactly four owner-aligned packages: MAINSCENARIO, FILE_00, FILE_01, FILE_02.
AoS20 and D349 math lead. Do not resume the 14.58 MB monolith, Split24/SH4ZAM
layout tuning, cache campaigns or a new converter/residency architecture.
GC/PS2/custom DC are authorized offline inputs to this same native contract.

Sequence remains: AoS20 integration -> backing replacement/accounting ->
substantive FILE_01 reduction -> r100 static cutover -> residual CPU/PVR -> native
actors. Preserve normal-menu/r100/r101/r103 and the other systems backlog.
The canonical goal holds full acceptance and Astra/Max escalation rules.

- D364 four v3 packages: 1,992,824 B; AoS20: 1,299,298 B. Target CPU fixture
  qualified reading/preparation/packet construction, not recovered-game output.
  AoS20 fixture p50 47.486 ms is not gameplay FPS.
- D365/e02e264 Package::resolve_source qualifies owner/work/BIN/common ->
  58 source instances/1,093 groups, with no extra retained registry/allocation.
  **No recovered-game hook uses it yet.**
- FILE_01 native baseline: 1,000,874 B. Modeled encounter shortfall: **746,816 B**
  after known source-span replacement, before adapter/staging cost. The target
  remains roughly 900 KB-1 MB gross reduction/headroom if feasible.
- **Actual source backing removed and actual source-heap recovery: zero.**
  No v4 package is active in re4dc-game.elf. Its Makefile does not yet link
  room_package/static_room_prepare. The historical room target rejects v4 so
  its v3 evidence stays reproducible.
- No new game ELF/disc/capture/timing/hardware run occurred in D366. These four
  historical encounter slices are not all authored r100; list remaining fallback.

## Isolated D366 asset trial: rejected, no promotion

Worktree /root/work/re4-file01-v4-reduction; branch
experiment/r100-file01-v4-reduction; committed d1a2d42c297544c5148e038d3664da9da318c6dd.
Nothing was merged into primary. Owned files: optional offline OBJ source-index
view, reduce_file01_blender.py, focused test and
R4_FILE01_PROTECTED_REDUCTION_CHECKPOINT.md. This is a bounded negative trial,
not a universal reducer or a recipe to promote.

| FILE_01 arm | Triangles | Encoded AoS20 B |
|---|---:|---:|
| Accepted D364 | 24,983 | 1,000,874 |
| Unmodified exchange control | 24,983 | 998,346 |
| Protected conservative | 24,785 | 1,000,390 |
| Protected lean | 24,739 | 999,146 |

Lean saves only 1,728 B versus accepted, and is **800 B larger than its exchange
control**. Do not repeat this protected-decimation sweep for the budget problem.
Encoding differences are not heap recovery. More substantive reviewed asset
changes/PS2 substitutions remain authorized; this trial does not invalidate D349.

Blender 5.2.0 LTS/fbe6228777e7 ran in a separate factory/offline CLI session, with
add-ons disabled. No Blender MCP tools were exposed. 19/105 batches failed the
normal roundtrip bound and retained original source input; 14/16 batches changed
in the two arms. The worst normal discrepancy remained 81.8266 degrees after
both flat/smooth setup attempts; its precise cause is unresolved. No complete
Blender roundtrip or target visual equivalence is claimed. Sampled surface tests
are not rigorous whole-surface bounds. No Blender render/target measurement
followed the negative encoded result. No texture changes or PS2 substitution.

- Private Blender artifacts: C:/Game Dev/Emulators/re4_helpers/experiments/
  r100-file01-d366/candidates-v4: report.json, OBJ files, reference-locked.blend,
  selectable-candidates.blend. Earlier v1/v2/v3 retain failed checks, not acceptance.
- Re-encoding: /root/probe/d366-native-cutover/file01-protected-v1. result.json
  and command/log files pin all packages, hashes and section bytes.
- Private drivers: C:/Game Dev/Emulators/re4-session-scripts/
  reduce_file01_blender.py and d366_encode_candidates.py. The committed helper
  differs only in clarified comments. Private assets/captures are not committed.
- Commit checks: optional parser seam/negative-index/default-byte test and ten
  existing converter tests passed; helper Python compilation passed. No gameplay
  or appearance acceptance follows from them.

## Exact code resume point

The last technical action was **read-only inspection** of pvr_geometry.hpp/.cpp,
static_room_prepare.hpp/.cpp and room/main.cpp::submit_room_strips(). No new
strip submission implementation or source-game v4 hook was written.

1. Package::resolve_source is the existing cold owner/work/BIN/common selector.
   SMX id alone is insufficient, especially repeated 254. Do not retain borrowed
   pointers across owner replacement/rebase/retirement.
2. prepare_static_batch reads AoS20 directly into caller-owned DirectStripVertex
   slots via D349/KOS math. It does not own a scene, material or PVR submission.
   pvr_geometry already supplies prepare_direct_strip, clip_projected_triangle,
   group_visible, begin_pvr_packet and submit_pvr. Adapt the proven room strip
   assembly to v4 local indices/slots under native_ui's existing frame/pass owner.
3. scroll.cpp::setObj/SmdSetParam sees block/work/BIN/common identity while
   creating source objects. Bind native SourceGroups at that boundary without
   creating another gameplay/visibility registry.
4. block.cpp already binds/unbinds native draw owners at create/delete/ARAM.
   moveBlockData unbinds, copies/rebases models/SMD, then rebinds. Native package
   views must use the same owner generation and rebase/retire boundaries.
5. model.cpp::cModInfoMgr::create calls getBoundingBox on original positions at
   initialization. Preserve its source-local bound before retiring arrays;
   native world-space group bounds are not a substitute. Other readers include
   trans.cpp, shadow.cpp, mirror.cpp, shape.cpp and debug code. Qualify/adapt their
   actual use before removal; no backing-removal patch exists yet.
6. commonModelTrans still selects shaderSetup/materials, texture changes,
   alpha/blend/cull. model_bridge captures those for fallback. Do not replace
   current source material state with frozen historical headers or prepare twice.
7. D361's optional 128 KiB retained preparation is not free memory until its
   remaining consumers stop using it and actual storage is released.

Next implementation should connect source state/lifetime to native batch
submission and real backing replacement, with the required asset reduction to
fit. A helper/host fixture is not cutover acceptance. If genuinely different
ownership/streaming or a locked budget increase becomes necessary, use the
existing Astra/Max escalation rule; do not silently invent it.

## Paths for existing inputs and references

- D349: /root/work/re4-r100-reference-5f42caa at 5f42caa;
  D353 bake: /root/work/re4-r100-prelit-d353 at d928ad6.
- Four native packages: /root/probe/d364-native-r100/four-owner-v4-v2.
- Exact owner recipe/budget: /root/probe/d364-native-r100/source-block-trace.
- Identity/cost evidence: /root/probe/d365-r100-cutover. Its material report
  resolves 35/39 materials; four combined texture/mask identities are not
  qualified. Do not infer missing texels from the incomplete native-ui catalog.
- Existing PS2 leads: /root/probe/d353-ps2-r100-prelit/inventory-v3,
  geometry-matches.json and color comparisons. No qualified complete FILE_01
  substitute exists. Do not restart extraction or the rejected stove.
- Source mirror: /root/probe/d362-mirror. Fixtures/textures:
  /root/probe/d354v7-fixtures. Keep accepted private outputs immutable.
- RE4DC_KOS_BASE=/root/work/kos-re4dc-d336; /opt/toolchains/dc/sh-elf GCC15.2.
  No upgrade. Adapt /root/probe/d361-build.sh to fresh output; never overwrite D361.
- Retained game evidence: C:/Flycast-Evidence/re4-dreamcast/d361-retained-model
  and d362-shared-uv. Check their checkpoint for complete source/ELF/fixture hashes.
