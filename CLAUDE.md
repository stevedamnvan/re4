# RE4 Dreamcast port handover

## Mission

Continue the existing native Sega Dreamcast port of Resident Evil 4. This is a course correction and optimization effort, not a restart. The immediate goal is a responsive, high-performance, manually playable 30-second r100 encounter that preserves the accepted room, lighting, corrected complete character presentation, source camera/FOV, transparency, animation/event timing, collision, combat behavior, and 640x480 output.

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

Treat the Soulcalibur tree as a read-only reference unless the user explicitly changes its scope. Do not commit the disc image, extracted proprietary assets, private captures, telemetry dumps, or local toolchains.

## Repository state

- Branch: `dreamcast-port`
- GitHub remote: `origin = https://github.com/stevedamnvan/re4.git`
- Original project remote: `upstream = https://github.com/adonis-singh/re4.git`
- Last accepted implementation checkpoint: `3afbb80a80c2e1d620d74601298a36b4852de19d`
- Accepted implementation commits immediately before this handover:
  - `1e15ee54b937273e56b419b8e3ae8f9cd2e86930` — reuse room visibility across passes
  - `3afbb80a80c2e1d620d74601298a36b4852de19d` — batch PVR headers with payloads

Read these first:

1. `port/dreamcast/README.md`
2. `port/dreamcast/docs/REALTIME_PATH.md`
3. `port/dreamcast/docs/R3N_VISIBILITY_REUSE_CHECKPOINT.md`
4. `port/dreamcast/docs/R3O_HEADER_PAYLOAD_BATCHING_CHECKPOINT.md`

Preserve all historical checkpoint documents. Update the README current-status section and `REALTIME_PATH.md` only after a candidate has been built, measured, and accepted or reverted.

## Accepted references

Keep two separate authorities:

- The original GameCube/decomp behavior determines gameplay and authored presentation.
- The latest accepted Dreamcast build detects regressions in the working native port. It does not make known prototype defects authoritative.

The accepted audio/video progress capture is:

`C:\Flycast-Evidence\re4-dreamcast\d202-current-progress-video-audio-dba07e2\re4dc-dba07e2-current-progress-32s-with-audio.mp4`

- Video SHA-256: `c93e31f09744413d8f3bf56603ec3b7a6408b55d14762187f04753fac4120125`
- Corrected visual ELF SHA-256: `c5ae9de436fd7b9f3770ce3e7cc40d1f37b8e2c000b3b9dfb9be5d46ce7c0e68`
- Keep audio in future progress recordings.

Flycast results are emulator evidence. Physical Dreamcast acceptance has not happened and must be reported separately.

## Current measured baseline

The latest accepted runtime candidate is R3o in:

`C:\Flycast-Evidence\re4-dreamcast\d209-header-payload-batching-candidate`

- Exact autoplay ELF SHA-256: `191676ca573aaaec9aed99bb33c88fca3102b1d90344a8e7c4020455bf1dfbdc`
- Manual ELF SHA-256: `13857924539cec27012e1d6cdd46c9ec44ee17a5db942281b2f3caedaa3267ea`
- Matched ticks: 165–1194 over two repeated runs
- Presented CPU frame p50: 87.615 ms
- TA registration p50: 58.731 ms
- PVR render p50 in the preceding R3n matched run: 7.50 ms
- Visible content was preserved: 327 room groups, 9,155 room triangles, and 11,900 actor triangles
- No discarded simulation time or catch-up overruns were observed
- Header/payload batching reduced immediate PVR calls from 1,219 to 617 while preserving 1,071,840 submitted bytes; it saved only about 0.12 ms, so do not repeat that experiment as the main performance strategy.

This is still well short of real-time 30 fps. Choose the next work from measured costs rather than from a fixed source-reconstruction sequence.

## Uncommitted experiment: preserve this work

At handover, the working tree intentionally contains edits in:

- `port/dreamcast/room/Makefile`
- `port/dreamcast/room/main.cpp`

Do not clean, reset, discard, overwrite, or broadly stage these files. They are an unfinished actor-lighting measurement and fast-normal experiment. They are not accepted production work.

The experiment currently adds:

- `ACTOR_LIGHTING_VALIDATE ?= 0` and `RE4DC_VALIDATE_ACTOR_LIGHTING`
- actor-specific lighting timings and selected-light masks
- telemetry ABI v11, record size 368 bytes
- optional KallistiOS `frsqrt` normal handling with refinement and a bounded fallback

Measured actor-lighting inventory before the fast path:

- Total actor lighting p50: 18.959 ms
- Leon p50: 14.655 ms; selected light mask `0x00000053`
- Ganado p50: 4.299 ms; selected light mask `0x00000126`

The current validation result is invalid because input normals and output lighting alias the same buffer. Calls such as `build_character_lighting(..., leon_lighting, leon_lighting, ...)` overwrite data that the comparison path later treats as source normals. The production loop may also corrupt later normal reads when `normal_sources` is not identity ordered. Do not accept or reject the fast path from the current color-delta telemetry.

Private experimental evidence is under:

- `d210-actor-lighting-inventory`
- `d211-actor-lighting-frsqrt-validation`
- `d212-actor-lighting-frsqrt-refined-validation`
- `d213-actor-lighting-frsqrt-two-refinements`
- `d214-actor-lighting-fast-normal-validation`
- `d215-actor-lighting-fast-normal-bounded-validation`

The validation folders after d210 are retained negative/diagnostic results; their packed-color comparisons are tainted by the aliasing defect.

## Immediate continuation

1. Inspect the converted character packages and determine whether each `normal_sources` map is identity, a permutation, or an order with repeated/non-monotonic references.
2. Separate immutable source-normal scratch from output-lighting storage, or compute the reference result before any output overwrites its input. Keep memory bounded and report its peak cost.
3. Rerun the packed-color validation at matched simulation ticks. Record changed packed colors and maximum per-channel delta only after the validator is trustworthy.
4. Measure the corrected fast-normal candidate against the R3o/R3n matched encounter. Keep it only if it has a useful timing win and an explicitly accepted numerical/visual bound; otherwise revert the fast path while retaining the actor-lighting timing split.
5. Update the existing plan and README with the measured keep/revert decision, build both manual and autoplay variants, run the focused test suite, and commit only the accepted files.
6. Continue with the largest measured cost. Candidate areas include dependency-aware actor preparation/lighting reuse, tighter native PVR submission, and the Dreamcast-native texture/resource pipeline. Do not silently remove visible content or reduce gameplay work to claim a gain.

## Build and verification

From WSL:

```bash
cd /root/work/re4-dreamcast
source port/dreamcast/kos-env.sh
python3 -m unittest discover -s port/dreamcast/tests -p 'test_*.py'
make -C port/dreamcast/room r100-autoplay
make -C port/dreamcast/room r100
```

The last accepted checkpoint passed 49 Python tests and both builds. Verify exact ELF hashes for every evidence folder. Keep manual and autoplay staging isolated, and verify that the manual package has no stale autoplay flag.

For every performance experiment:

1. Produce a bootable candidate.
2. Run an appropriate correctness or image/state comparison.
3. Capture before/after timing, presentation intervals, simulation debt, input delivery, and memory changes over matched gameplay.
4. Make and document a keep-or-revert decision.

Use repeatable movement, turning, aim extremes, firing, reload, enemy attack, death, and retry segments. A settled pose or dead enemy is not an adequate performance sample.

## Fidelity and scope rules

- Do not restart or introduce a new engine, generic GX interpreter, generalized rendering framework, or wholesale rewrite.
- Preserve the accepted geometry, complete Leon and Ganado components, weapon/component visibility, camera/FOV, resolution, lighting behavior, transparency order, near-plane clipping, animation timing, collision, and combat behavior.
- Cull rendering work conservatively without suppressing off-screen gameplay, collision, animation events, or hit volumes.
- Prefer source-derived selection and ownership rules when they reduce work: SAT collision hierarchy, per-model light selection, position/normal/UV identity, source model eligibility, weight palettes, and source residency decisions.
- Use Dreamcast-native structures and mature KallistiOS/PVR tooling. Benchmark store queues, DMA/buffering, VQ, palette formats, mipmaps, and native texture layouts rather than assuming a gain.
- Keep visual or numerical adaptations separate from equivalent optimizations so quality tradeoffs remain attributable.
- Do not call emulator evidence physical-hardware acceptance.

## Git discipline

The user authorized committing and pushing accepted work to the GitHub `origin`. Stage exact files only. Never use broad `git add`, clean/reset the tree, or commit private assets/evidence. Before every commit, inspect the staged file list and diff. After pushing, verify that local HEAD and `origin/dreamcast-port` match.

The two dirty experiment files named above belong to the active investigation. Commit them only after the aliasing issue is corrected and the measured candidate is accepted; otherwise revert only the rejected experimental portions with care and preserve useful instrumentation.
