# r100 R3m source punch-through checkpoint

Recorded 2026-09-20 after the R3l character-assembly correction. This pass
restores one source-authored alpha-test decision and uses it to make the existing
one-metre room subdivision safe for that material. It changes no geometry,
texture resolution, camera, lighting, collision, or gameplay behavior.

## Source rule and bounded classification

`SmxSetFlag` in `src/game/scroll.cpp` maps SMX flag bit 3 to the model's
`alpha_omit = 0x80`. `alphaSetup` in `src/game/trans.cpp` uses that model value
as the GX alpha-compare reference for alpha-textured parts. The room converter
already preserved the raw SMX flags, but the Dreamcast renderer previously sent
every alpha texture through one order-dependent translucent list.

The texture converter now records whether the final converted alpha samples are
strictly binary. This is an additional format property, not a material decision.
The runtime selects the PVR punch-through list only when both conditions hold:

1. the converted texture contains only alpha 0 or 255; and
2. the source room group carries SMX bit 3.

The current package audit is:

| Material | Binary alpha | SMX flags | Source triangles | Runtime path |
|---|---:|---:|---:|---|
| `ROOM_MATERIAL_008` | yes | `0x00` | 16 | translucent blend |
| `ROOM_MATERIAL_029` | yes | `0x0a` | 1,596 | punch-through at `0x80` |
| other alpha materials | no | varied | unchanged | translucent blend |

Material 029 spans 108 source child groups after the existing one-metre spatial
partition. Binary cutouts do not require back-to-front triangle order, so these
children can now be rejected conservatively by the existing frustum test. The
other alpha materials remain unpartitioned and blended. Material 008 remains
blended until its source per-part alpha reference is recovered; binary pixels
alone are insufficient authority to change its draw semantics.

## Implementation

Texture package version 1 retains binary compatibility and uses a new descriptor
flag for binary alpha. The manifest reports the classification for audit. The
runtime compiles separate PVR punch-through headers, sets the hardware reference
to `0x80`, submits only source-authorized batches in that list, and excludes
those batches from the translucent list. The alpha-room telemetry stage continues
to include punch-through plus blended room work so the comparison remains
compatible with telemetry version 8.

The production room recipe removes only material 029 from the blanket
unpartitioned-alpha set. All source triangles remain in the package.

## Validation

The 49-test host suite passes, including binary and gradient classification. The
SH-4 r100 autoplay ELF builds successfully. The generated room retains all 30,895
source triangles, and the generated texture package marks only materials 008 and
029 as binary.

Flycast telemetry was compared over the same simulation ticks 274-347 against
the accepted post-character-fix baseline:

| Median metric | Baseline | Candidate | Change |
|---|---:|---:|---:|
| complete frame | 88,997 us | 81,806 us | -7,191 us (-8.1%) |
| render total | 88,675 us | 81,491 us | -7,184 us (-8.1%) |
| alpha-room stage | 29,270 us | 22,041 us | -7,229 us (-24.7%) |
| submit interval | 62,046 us | 54,851 us | -7,195 us (-11.6%) |
| room triangles emitted | 6,377 | 5,871 | -506 (-7.9%) |
| room cache misses | 15,484 | 12,292 | -3,192 (-20.6%) |

Actor pose, normal, lighting, and opaque-room medians remain effectively
unchanged. The 28-second visual sequence shows the intact fireplace, railings,
furniture, complete characters, and HUD through encounter state changes.

Evidence:

- baseline telemetry: `C:\Flycast-Evidence\re4-dreamcast\d200-r3m-character-fix-baseline`
- candidate telemetry and visual sequence: `C:\Flycast-Evidence\re4-dreamcast\d203-source-punchthrough-candidate`
- candidate ELF SHA-256: `1feacc30cdd072b3ca03ff976892013e6c21d4966d6eac1e7303cf12e9cb7ae4`
- room package SHA-256: `d6010467fbc15f2a18c10b3f78eaddfd7ad4e09a44163ad79bf2385b59e57aa7`
- texture package SHA-256: `4b66255f8357c87b8dfb9573c3eaa6bea9177558fa946382b3ac84223020f8eb`

## Full-route and manual results

A second comparison ran both exact ELFs for 42 seconds and covers simulation
ticks 30-1198. It includes turn, level aim, firing, reload, kill, the expensive
settled result view, and the timed retry. The current technical route does not
exercise free movement, aim extremes, enemy contact, or Leon death.

| Full-route metric | Baseline | Candidate |
|---|---:|---:|
| CPU frame p50 / p95 / p99 | 99.00 / 101.50 / 102.57 ms | 92.23 / 94.72 / 95.83 ms |
| PVR ready-to-ready p50 / p95 / p99 | 100.09 / 102.59 / 102.60 ms | 83.41 / 100.10 / 102.60 ms |
| PVR registration p50 | 72.03 ms | 65.29 ms |
| PVR render p50 | 7.50 ms | 7.50 ms |
| simulation drops / overruns | 0 / 0 | 0 / 0 |

A separate manual-build virtual-controller trace moved/turned Leon, fired three
shots, requested reload, took two source axe hits, and restarted. Five action
edges were delivered with no queue drops, maximum queue depth one, worst input
sample gap 19.96 ms, and no discarded simulation time. A focused host-timestamped
run observed the fire state 158 ms after button-down and the restart state 218 ms
after button-down. Those are host-side technical bounds, not human or physical
controller latency acceptance.

The candidate's observed steady-state main-RAM headroom is 5,640,192 bytes,
94,208 bytes below the baseline. Heap usage increases by 4,168 bytes. PVR and
AICA snapshots are unchanged. Loading, restart, stack, TA-overflow, and
fragmentation peaks remain uninstrumented.

Additional evidence:

- full baseline: `C:\Flycast-Evidence\re4-dreamcast\d204-corrected-character-full-baseline`
- full candidate: `C:\Flycast-Evidence\re4-dreamcast\d205-source-punchthrough-full-candidate`
- manual route: `C:\Flycast-Evidence\re4-dreamcast\d206-source-punchthrough-manual-input`
- input latency: `C:\Flycast-Evidence\re4-dreamcast\d207-manual-input-latency`
## Acceptance boundary

This accepts the source-authorized punch-through path and the resulting
material-029 spatial rejection in Flycast. It does not establish all source
per-part alpha references, exact original-game pixels, physical Dreamcast timing,
or the 30 fps target. The full-route candidate presents roughly 10-12 distinct frames per second and remains below the real-time gate.