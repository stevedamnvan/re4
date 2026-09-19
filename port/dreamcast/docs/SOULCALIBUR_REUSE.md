# Reuse from the local Soulcalibur work

The Soulcalibur work under `C:\Game Dev\Emulators\flycast` is an emulator and
RTX Remix project, not a native-game port. Its value here is the validation
architecture and its knowledge of Dreamcast PVR state. No Flycast code is
copied into this target.

## Practices carried into this port

### Exact identity precedes comparison

Soulcalibur captures bind a frame to the game, source revision, producer epoch,
ordinal, texture upload generation, render-to-texture generation, and palette
generation. The port will apply the same rule to reference and Dreamcast runs:
room, event, RNG seed, simulation tick, input record, source revision, asset-pack
hash, and executable hash must match before visual or behavioral comparison.

The `evidence_manifest.py` tool records immutable input hashes. A comparison is
invalid when its manifest or files no longer validate.

### Preserve source truth and report omissions

Flycast's PVR scene capture retains projected geometry but explicitly reports
that camera/world provenance is unknown and lists omissions. RE4 has a stronger
starting point because its camera, model transforms, skinning inputs, and
materials are available before GPU submission. The Dreamcast renderer should
capture both CPU-side world/view inputs and submitted PVR vertices. It must list
features it approximates or drops, such as TEV stages, indirect effects,
modifier geometry, or alpha behavior.

### Resource identity includes palette state

Soulcalibur proved that a texture address alone is not an identity. For the
native port, texture-cache keys must include the converted asset hash, package
generation, palette bank/generation, mip level, format, and sampling state.
Room unload invalidates the relevant generation before memory can be reused.

### Bounded captures and immutable artifacts

Capture windows are explicit and small. A capture records storage preflight,
frame range, limits, and a terminal status. Retained captures are never edited
in place. A failed or incomplete capture remains evidence of that result rather
than being silently replaced.

### Protected UI and effect ownership

Soulcalibur separates protected HUD/overlay geometry from scene geometry and
tracks native effects independently. RE4 should similarly classify HUD,
inventory, letterbox, subtitles, fades, full-screen filters, particles, and
world geometry. This prevents a renderer optimization from accidentally
discarding gameplay UI or double-applying a full-screen effect.

### Validation ladder

Use each environment only for claims it can support:

1. Host fixtures: parser round trips, math, scheduling, serialization, and
   deterministic state traces.
2. Dolphin reference: behavior and image evidence from the identified GameCube
   build.
3. Flycast candidate: rapid Dreamcast executable iteration and automated input.
4. Stock Dreamcast: timing, cache/DMA behavior, controller, AICA, GD/ODE loading,
   display modes, and VMU acceptance.

Passing an earlier rung does not imply a later one. This follows the local
Soulcalibur rule that fixture/build success is not live visual acceptance.

## Concrete local assets to reuse

- Flycast itself as the fast Dreamcast test runner.
- Existing bounded launch/capture patterns in `neuraltest/remake_launch.py`.
- Packet and resource limit checks in `neuraltest/validate_pvr_packet.ps1`.
- PVR state vocabulary and palette-generation handling in
  `core/rend/neural/pvr_scene_capture.h`, `pvr_material_capture.h`, and
  `pvr_palette_binding.h`.
- The existing evidence location convention under `C:\Flycast-Evidence`, with
  a separate `re4-dreamcast` subtree when live captures begin.

The current Flycast worktree is intentionally dirty. It is read-only input to
this effort; do not clean, reset, stage, or modify it from the RE4 port.
