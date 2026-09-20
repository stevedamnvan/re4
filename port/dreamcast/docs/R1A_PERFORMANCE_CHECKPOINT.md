# r100 R1a performance checkpoint

Recorded 2026-09-20 against `70ea2e1755009d5a9088395de9614ffbd2f5f2f2`.
This checkpoint keeps the r100 camera, visible groups, geometry, materials,
light set, character packages, collision, audio, and 640x480 presentation.
It changes when repeated render work is performed; it does not reduce the
authored content to claim a speedup.

## What changed

The target telemetry ABI is now version 4 with a byte size and odd/even
publication sequence. A host reader accepts a snapshot only after two identical
even-sequence reads. Each record associates the current render with its
simulation tick range and reports input gaps, all discarded simulation time,
simulation debt, actor preparation, room/actor submission stages, and the KOS
PVR statistics sample.

The room renderer uses a bounded 1,024-entry direct cache keyed by the converted
source vertex index. A hit reuses that vertex's camera transform, projection,
and lighting for the current frame. It does not weld equal positions or merge
normal/UV identities. The cache consumes a fixed amount of BSS and is invalidated
by a generation counter each frame.

Near-plane clipping now has trivial accept and reject paths. The full clipper is
used only when a triangle crosses the near plane.

Source-light direction normalization, quadratic attenuation constants, and
spotlight cutoff terms are prepared once. The two view-relative directional
lights are transformed once per camera update. The per-vertex evaluator retains
the existing nine-light equation and final clamp. This is numeric work reuse,
not static-light baking or an invented distance cutoff.

## Matched Flycast result

The comparison used the packaged Flycast executable with SHA-256
`64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`,
the same 640x480/vsync configuration, 28 visible room groups, 4,226 emitted room
triangles, an alive player, and the same untouched encounter packages. Values
below are representative medians from consecutive steady-state frames; they are
emulator measurements, not physical Dreamcast timings.

| Measure | R0 telemetry baseline | R1a final | Change |
|---|---:|---:|---:|
| Total render work | 751.3 ms | 322.5 ms | -57.1% |
| Opaque room | 428.7 ms | 146.2 ms | -65.9% |
| Translucent room | 143.1 ms | 58.1 ms | -59.4% |
| Actor lighting | 74.8 ms | 34.3 ms | -54.2% |
| PVR last-render sample | about 7.5 ms | about 7.5 ms | no material change |
| Room index references | 56,283 | 56,283 | unchanged |
| Room transforms/light evaluations | 56,283 | 28,970 | -48.5% |

The final frame classified 12,022 room triangles as trivially in front of the
near plane, 6,170 as trivially behind it, and 569 as crossing it. The cache hit
27,313 of 56,283 index references. A 512-entry comparison hit 26,623 references
and rendered at about 493 ms before light preparation; 1,024 entries saved about
six further milliseconds for roughly 30 KiB of additional bounded storage.

Artifact identities:

| Build | SHA-256 | Private evidence directory |
|---|---|---|
| R0 telemetry baseline | `9994ba2674ce525f14ad3e0d923437db3db5840ee652ceede72719140041d740` | `C:\Flycast-Evidence\re4-dreamcast\d111-r0-telemetry-v4-smoke` |
| R1a cache 512 | `ae054d176ebe5dda6d5a86e318a40aa23a8a57e60e2728f54bb149a4f3640804` | `C:\Flycast-Evidence\re4-dreamcast\d112-r1a-room-cache-smoke` |
| R1a cache 1,024 | `36f765bc721a330b810842d9a26934db2c718264514b0d54231cdcb0aa69a9fa` | `C:\Flycast-Evidence\re4-dreamcast\d113-r1a-room-cache1024-smoke` |
| R1a manual with prepared lights | `d4045cd5042c45aaa717fbd6bddd96546b81bec0f5ed84fa143bb89c9f4f680e` | `C:\Flycast-Evidence\re4-dreamcast\d114-r1a-prepared-lights-smoke` |
| R1a 30-second autoplay | `40c7c6934edd2a8b1b0d98b2b6611dfa2ea58ba480b7130e681ba4d472d8ccd0` | `C:\Flycast-Evidence\re4-dreamcast\d115-r1a-autoplay30-smoke` |

## Thirty-second state smoke

The autoplay build was observed across simulation ticks 918 through 1,835,
covering a complete 900-tick presentation cycle and the next restart. In 30.313
wall-clock seconds it exercised the six-round handgun, reload, enemy health
500/365/230/95/0, death, and reset. The trace recorded zero discarded ticks and
zero discarded microseconds. Render work ranged from 318.3 to 347.0 ms and the
maximum accumulated simulation debt was 391,944 microseconds. The manual package
was rebuilt afterward and verified to contain no stale `autoplay.flag`.

## Acceptance boundary

R1a demonstrates a substantial CPU-work reduction and a complete real-time
fixed-tick scripted cycle in Flycast. It does not establish responsive manual
play: controller sampling still occurs once per roughly 0.33-0.36 second render
iteration. It also does not establish stock-hardware timing, pixel identity, or
the original r100 per-model light selection. The current evaluator still applies
the prototype's nine-light list until source object identity, masks, volumes,
and ordered selected-light traces are recovered.

The next fidelity/performance gate is R1b from
[REALTIME_PATH.md](REALTIME_PATH.md): preserve source object identity and recover
the original model light selection before baking any static contribution. The
independent input service remains required before this build is accepted as a
responsive manual demo.
