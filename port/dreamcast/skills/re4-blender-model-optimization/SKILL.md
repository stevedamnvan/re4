---
name: re4-blender-model-optimization
description: Use local Blender Python to prepare source-compatible RE4 Dreamcast model reductions and measure their rendering or FPS benefit after residency is stable. Preserves source identities, materials, animation contracts, private assets and reviewed visual quality. Does not certify recovered-game playability or automatically resume the rejected r100 pilot.
---

# RE4 Blender model optimization

Optimize a measured rendering bottleneck with local, reversible model candidates.
The intended later use is FPS work once residency permits representative gameplay.
Creating or invoking this skill alone does not resume the rejected D323 experiment.
Its saved scripts and lessons are reusable; its candidate assets are not accepted.

## Start with the current authority

Use the WSL Ubuntu-24.04 repository `/root/work/re4-dreamcast` (Windows:
`\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast`). Read `AGENTS.md`, current
`CLAUDE.md`, then the relevant parts of:

- `port/dreamcast/docs/PLAYABLE_PATH.md`: governing gameplay/integration scope.
- `port/dreamcast/docs/REALTIME_PATH.md`: measurement and fidelity policy.
- `port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md`: resource ownership and selectable assets.

These may have advanced. Check branch, dirty state, current fixture and active work
before treating any older measurement or tool path below as current. Use an isolated
worktree for owned scripts/docs; keep original data, derived assets and captures in
new private directories. Do not alter primary runtime code to compensate for an
exporter or to make an optimization benchmark cheaper.

## Concrete procedure for Astra low or Sol

1. **Name one bottleneck and one set.** Record the loaded package/allocation owner,
   mesh IDs, material IDs, source placement/state references, unique meshes versus
   repeated instances, and the maximum simultaneous set. For FPS, measure draw/transform/
   packet work or GPU cost in a representative state. For memory, calculate the actual
   backing reduction and fixed reservation separately. Triangle count, encoded bytes,
   loaded RAM and frame time are different metrics; none proves another. If residency
   still prevents representative gameplay, keep geometry preparation secondary and
   label timing unavailable rather than manufacturing a gameplay baseline.
2. **Bound the experiment.** State a reference, conservative candidate and lean candidate,
   expected benefit, geometry/image tolerances and tests before substantial editing.
   Choose by measured cost and source compatibility, not whether an environment or
   character is easier to edit. Identify constraints such as seams, hard edges,
   silhouettes, openings, cover, attachments, collision alignment and switching state.
   An 80%/60% triangle pair is only a starting target, not required policy or a byte/FPS
   prediction. Static, nonmorph, nonswitched meshes are the simpler proven path; skinning,
   morph, skeleton, attachments and motion require their own demonstrated roundtrip.
3. **Prove the unmodified pipeline first.** Read [the source-contract checklist](references/source-contracts.md).
   Use existing converters/consumers and archive loaders. Compare source BIN -> exchange
   -> Blender -> BIN independently from tool-only repacking. Check coordinates, units,
   handedness, winding, referenced normals/colors/UVs, exact material identities/order,
   bounds, transforms and companion metadata. An exporter returning success is not a
   gate. Fix a narrow demonstrated defect or leave the specific unsupported boundary;
   do not normalize identities, discard failing meshes silently or loosen tolerances
   just to continue. Keep failing assets original and report a qualified subset explicitly.
4. **Edit locally and reversibly.** Read [local execution](references/local-execution.md).
   Save `REFERENCE_LOCKED`, `CANDIDATE_CONSERVATIVE`, `CANDIDATE_LEAN` and `REVIEW_CAMERAS`
   in private `.blend` files before destructive operations. Preserve source normals and
   discontinuities deliberately; use explicit exclusions and verify them after modifiers.
   An empty modifier mask can mean unrestricted operation: skip it and validate the
   resulting protected edges/vertices. Evaluate bidirectional surface error and several
   representative views, not just vertex count or a single attractive angle.
5. **Replace the costly backing.** Use the existing source-compatible package boundary
   and retain its nested references, flags, metadata, alignment and native texture identity
   records. Keep already-externalized texels removed. Do not load reference and candidate
   simultaneously in measurements. A diagnostic viewer proves geometry inspection only;
   it does not qualify the recovered game's source-layout archive or allocation lifetime.
6. **Measure a small, representative pair.** Request an exclusive measurement window
   from the agent owning runtime work, when applicable. Stop Blender rendering/heavy jobs
   before captures. Pin executable, assets, emulator, fixture, camera, light/state and
   resolution (current RE4 policy: 640x480). Measure both arms at the same representative
   states, then a short normal movement/combat/transition check appropriate to the asset.
   Record frame-interval median/tails, geometry/packet work, CPU/GPU timing where available,
   RAM reservation/free heap/staging, VRAM and visible differences. Repeat only if noise,
   failure or a new change needs resolution. Do not disable enemies/events/blocks or clear
   source hold to obtain a faster or more visible benchmark.
7. **Decide and hand off.** Report promising pending review, not worthwhile, or the exact
   blocked boundary. Keep both selectable candidates and reference, source hashes,
   commands, numerical/visual results and remaining tests. Materially changed appearance
   requires user review before becoming the default; do not automatically promote,
   merge or switch assets. Respect already-given review authorization without inventing
   an additional gate. Commit only owned asset-free helpers/manifests/docs, never private
   models, textures, `.blend` files or captures. No new renderer, loader, compressor or
   broad asset campaign is needed for one model experiment.

## Proven limitations and reusable tools

Read [the D323 result](references/d323-result.md) before reusing that asset set or its
strict bridge. It records a useful tool fix and a rejected optimization—not a success
recipe. Use current source implementations first: `convert_room_obj.py`,
`convert_character.py`, `le_mirror.py`, `prepare_native_ui.py`, `convert_tpl.py` and
`vq_export.py` where present and applicable. Do not add another asset pipeline because
an older helper has a narrow input contract.

Bundled `scripts/blender_roundtrip.py` performs only an unmodified, offline exchange
and saves inspection evidence. Its success is not source fidelity. The original
D323 candidate/gate/manifest scripts are preserved in the isolated branch named in
its reference; they deliberately encode that pilot's limits and are not universal
model optimizers. The pinned MIT upstream color fix and private compiler helper are
included for reuse when that exact version is selected.