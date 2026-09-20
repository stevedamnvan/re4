# RE4 Dreamcast port handover

## Mission

Continue the existing native Sega Dreamcast port of Resident Evil 4. This is a course correction and optimization effort, not a restart. The immediate goal is a responsive, high-performance, manually playable 30-second r100 encounter that preserves the accepted room, lighting, corrected complete character presentation, source camera/FOV, transparency, animation/event timing, collision, combat behavior, audio, and 640x480 output.

Use the GameCube source to decide what the game must do. Use Dreamcast-native data layouts and algorithms to decide how to do it. Do not preserve redundant GameCube work or a known prototype defect merely because it appears in an older checkpoint.

## Working folders

| Purpose | Linux / WSL path | Windows path |
| --- | --- | --- |
| Active repository | `/root/work/re4-dreamcast` | `\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast` |
| Dreamcast port | `/root/work/re4-dreamcast/port/dreamcast` | `\\wsl.localhost\Ubuntu-24.04\root\work\re4-dreamcast\port\dreamcast` |
| KallistiOS | `/root/work/kos` | `\\wsl.localhost\Ubuntu-24.04\root\work\kos` |
| kos-ports | `/root/work/kos-ports` | `\\wsl.localhost\Ubuntu-24.04\root\work\kos-ports` |
| Private captures and timing evidence | `/mnt/c/Flycast-Evidence/re4-dreamcast` | `C:\Flycast-Evidence\re4-dreamcast` |
| Source disc image | `/mnt/c/Game Dev/Emulators/Resident Evil 4 Debug (Disc 1)/Resident Evil 4 Debug (Disc 1).iso` | `C:\Game Dev\Emulators\Resident Evil 4 Debug (Disc 1)\Resident Evil 4 Debug (Disc 1).iso` |
| Soulcalibur Dreamcast/Flycast reference | `/mnt/c/Game Dev/Emulators/flycast` | `C:\Game Dev\Emulators\flycast` |

Treat the Soulcalibur tree as a read-only reference unless the user explicitly changes its scope. Do not commit the disc image, extracted proprietary assets, private captures, telemetry dumps, generated packages, or local toolchains.

The Linux checkout is authoritative. Upstream contains distinct `src/Tools` and `src/tools` paths, so the retained `C:\Game Dev\Emulators\re4-dreamcast-WINDOWS-INCOMPLETE` checkout is not a build source.

## Repository state

- Branch: `dreamcast-port`
- GitHub remote: `origin = https://github.com/stevedamnvan/re4.git`
- Original project remote: `upstream = https://github.com/adonis-singh/re4.git`
- Latest accepted implementation checkpoint: `000bdb4f5e5ef7090c9fa27fe36113ba9ca4a9f7`
- Checkpoint meaning: separate immutable actor normals from lighting output; retain actor timing/mask telemetry; reject and remove the slower `frsqrt` experiment
- Latest measurement pass: R3q, which adds only the compile-gated `SUBMIT_PROFILE` room diagnostic and changes no accepted code; it closes submission transport and room vertex cache growth
- Latest accepted optimization: R3r, per-strip bounds culling plus the `kProjectionDepthBias` fix for the KOS projection; CPU frame p50 86.217 ms to 74.139 ms while drawing more room geometry. Any new visibility test must measure projected extents at `depth + 1`
- Latest rejected experiment: R3s room identity cache, 21.5% fewer transform-and-light evaluations but 1.274 ms slower; the opaque room pass is per-reference/per-record bound, not transform bound
- Expected state after the handover commit and push: clean local tree with local HEAD equal to `origin/dreamcast-port`

Read these first:

1. `port/dreamcast/README.md`
2. `port/dreamcast/docs/REALTIME_PATH.md`
3. `port/dreamcast/docs/R3P_ACTOR_NORMAL_ALIAS_FIX_CHECKPOINT.md`
4. `port/dreamcast/docs/R3O_HEADER_PAYLOAD_BATCHING_CHECKPOINT.md`
5. `port/dreamcast/docs/R3N_VISIBILITY_REUSE_CHECKPOINT.md`

Preserve all historical checkpoint documents. Update the README current-status section and `REALTIME_PATH.md` only after a candidate has been built, measured, and accepted or reverted.

## Accepted references

Keep two separate authorities:

- The original GameCube/decomp behavior determines gameplay and authored presentation.
- R3p is the latest accepted Dreamcast regression/performance baseline. It detects regressions in the working native port but does not make known prototype approximations authoritative.

The accepted audio/video progress capture remains:

`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2\re4dc-dba07e2-current-progress-32s-with-audio.mp4`

- Video SHA-256: `c93e31f09744413d8f3bf56603ec3b7a6408b55d14762187f04753fac4120125`
- Corrected visual ELF SHA-256: `c5ae9de436fd7b9f3770ce3e7cc40d1f37b8e2c000b3b9dfb9be5d46ce7c0e68`
- Keep audio in future progress recordings.

The R3p qualitative framebuffer check is in:

`C:\Flycast-Evidence\re4-dreamcast\d221-actor-normal-alias-fix-visual`

- Framebuffer SHA-256: `658ae4dbb1f6a13e80fd4c48eda5124b7a7a0f36f0ab2e2ff5940c7b0e8236f9`
- It retains the accepted room, complete Leon and Ganado assemblies, HUD, camera, transparency, and coherent lighting.
- Full-framebuffer emulation was enabled only to extract the image. Do not use D221 as timing evidence.

Flycast results are emulator evidence. Physical Dreamcast acceptance has not happened and must be reported separately.

## Current measured baseline

R3p timing evidence is in:

`C:\Flycast-Evidence\re4-dreamcast\d219-actor-normal-alias-fix-final`

- Exact autoplay ELF SHA-256: `4fd89b4e929aca49a9cdc8b7e231c9a1e33ff387cac81466d42e0d49b686a44f`
- Manual ELF SHA-256: `b265872f40b74f8fbe3cd5e7be28e4bcb73e8af2e54717d8cc5076f9ef91dd0a`
- Matched ticks against R3o: 165-1194
- CPU frame p50/p95/p99: 86.217 / 88.719 / 88.836 ms
- TA registration p50: 58.096 ms
- Presented ready-to-ready p50/p95: 83.409 / 100.096 ms
- Actor lighting p50: 18.198 ms, split into Leon 13.960 ms and Ganado 4.232 ms
- Selected masks remained Leon `0x00000053`, Ganado `0x00000126`
- Visible work medians: 327 room groups, 9,155 room triangles, 11,900 actor triangles, 617 PVR submissions, and 1,071,840 submitted bytes
- Main-RAM break-to-stack headroom: 5,570,560 bytes
- No discarded simulation time or catch-up overruns

The separate buffers cost exactly 98,304 bytes versus R3o, but fixed a real correctness defect and improved CPU frame p50 by 1.398 ms. The old buffer held transformed source normals and then lighting output even though package `normal_sources` references are repeated and non-monotonic. R3p makes those source normals immutable for the whole lighting pass.

The clean manual smoke is in `d220-actor-normal-alias-fix-manual`. It reached tick 558, sampled input 1,860 times with a 12.484 ms maximum gap, and had zero queue drops, simulation overruns, or discarded time. The manual ROM-disk staging had no `autoplay.flag`. It did not inject combat inputs, so it is not full manual or physical-console acceptance.

This is still roughly 11-12 distinct presented frames per second. A 33.33 ms CPU frame needs about 52.9 ms more median reduction. The last separately measured PVR raster p50 was 7.50 ms in R3n, while target preparation and TA registration remain much larger.

## Closed R3p experiment

The actor-normal alias fix is accepted. The KallistiOS `frsqrt` subexperiment is rejected and removed.

Evidence:

- `d216-actor-lighting-alias-fix-validation`: corrected dual-path validation, 330 frames
- `d217-actor-lighting-alias-fix-production`: `frsqrt` production candidate, actor-lighting p50 19.514 ms
- `d218-actor-lighting-reference-production`: portable square-root production reference, actor-lighting p50 18.692 ms
- `d219-actor-normal-alias-fix-final`: clean accepted autoplay build
- `d220-actor-normal-alias-fix-manual`: clean manual smoke
- `d221-actor-normal-alias-fix-visual`: qualitative framebuffer check

After the alias fix, almost every packed-color comparison was exact; the worst observed frame changed one channel value in one packed actor color. The `frsqrt` path still regressed actor lighting by 0.822 ms p50, so it was reverted. Do not retry it without a materially different implementation and fresh evidence.

Production telemetry is ABI version 10, 360 bytes. It retains total, Leon, and Ganado lighting timings and the selected light masks. Validation-only telemetry and Makefile switches were removed.

## Immediate continuation

Choose the next bounded candidate from the latest trace, not from the checkpoint letter sequence.

1. Prioritize room packet work. Opaque plus binary/blended room work totals 44.507 ms p50, the largest visible frame cost. Measure transforms, light evaluations, clipping crossings, headers, vertices, bytes, and calls per list before changing the path. Preserve winding, near-plane clipping, alpha order, and all accepted content.
2. In parallel only where independently bounded, target the stable actor selected-light work, especially Leon's 13.960 ms p50. Retain the portable evaluator as a reference, validate packed colors, and include the 98,304-byte normal scratch in memory accounting.
3. Treat direct store-queue versus bounded DMA/buffering as a benchmark, not an assumption. Current KOS `pvr_prim` already uses store queues.
4. Continue the native texture/resource pipeline after or alongside measured frame work: offline native layout, deduped handles, then per-texture VQ/palette/mipmap candidates with moving-scene quality review and uncompressed fallbacks.
5. Expand the benchmark route to free movement, aim extremes, enemy contact, Leon death, kill, and retry. Keep human control and physical Dreamcast timing as separate acceptance gates.

Every experiment must end with a bootable candidate, a correctness check, matched timing and memory evidence, and a keep-or-revert decision. Do not claim gains from changing the camera, resolution, room, complete character components, lighting, transparency, simulation quality, or audio.

## Build and verification

From WSL:

```bash
cd /root/work/re4-dreamcast
source port/dreamcast/kos-env.sh
python3 -m unittest discover -s port/dreamcast/tests -p 'test_*.py'
make -C port/dreamcast/room r100-autoplay
make -C port/dreamcast/room r100
```

R3p passed all 49 Python tests and both builds after the final source cleanup. The rebuilt manual ELF matches the accepted SHA-256 above, and the manual staging contains no stale autoplay flag.

For every performance experiment:

1. Produce a bootable candidate.
2. Run an appropriate correctness or image/state comparison.
3. Capture before/after timing, presentation intervals, simulation debt, input delivery, and memory changes over matched gameplay.
4. Make and document a keep-or-revert decision.

Use repeatable movement, turning, aim extremes, firing, reload, enemy attack, death, and retry segments. A settled pose or dead enemy is not an adequate performance sample.

## Fidelity and scope rules

- Do not restart or introduce a new engine, generic GX interpreter, generalized rendering framework, or wholesale rewrite.
- Preserve the accepted geometry, complete Leon and Ganado components, weapon/component visibility, camera/FOV, resolution, lighting behavior, transparency order, near-plane clipping, animation timing, collision, combat behavior, and audio.
- Cull rendering work conservatively without suppressing off-screen gameplay, collision, animation events, or hit volumes.
- Prefer source-derived selection and ownership rules when they reduce work: SAT collision hierarchy, per-model light selection, position/normal/UV identity, source model eligibility, weight palettes, and source residency decisions.
- Use Dreamcast-native structures and mature KallistiOS/PVR tooling. Benchmark store queues, DMA/buffering, VQ, palette formats, mipmaps, and native texture layouts rather than assuming a gain.
- Keep visual or numerical adaptations separate from equivalent optimizations so quality tradeoffs remain attributable.
- Do not call emulator evidence physical-hardware acceptance.

## Git discipline

The user authorized committing and pushing accepted work to the GitHub `origin`. Stage exact files only. Never use broad `git add`, clean/reset the tree, or commit private assets/evidence. Before every commit, inspect the staged file list and diff. After pushing, verify that local HEAD and `origin/dreamcast-port` match.
