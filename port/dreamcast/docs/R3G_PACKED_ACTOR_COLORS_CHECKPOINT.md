# r100 R3g packed actor-color checkpoint

Recorded 2026-09-20 after the compact actor-light checkpoint. Actor lighting
produced one float RGB result per animated normal, but every emitted strip
vertex called the same clamp-and-pack routine again. The matched encounter emits
15,886 actor vertex records from 8,435 normal identities per frame.

The lighting stage now packs each normal's final color once into bounded Leon
and Ganado arrays. Native actor strips read that exact value. The float results
remain available to the existing triangle clipping path, where newly generated
near-plane vertices still require interpolated lighting. No material, geometry,
lighting, camera, animation, or clipping rule changes.

## Matched Flycast result

Medians cover simulation ticks 220 through 474.

| Measure | Per-record color packing | Per-normal color packing | Change |
|---|---:|---:|---:|
| Outer frame work | 125.552 ms | 122.975 ms | -2.577 ms (-2.1%) |
| Total render work | 125.221 ms | 122.621 ms | -2.600 ms (-2.1%) |
| Actor lighting and color preparation | 15.870 ms | 18.782 ms | +2.912 ms |
| Opaque actor pass | 16.666 ms | 12.050 ms | -4.616 ms (-27.7%) |
| Translucent actor and HUD pass | 2.600 ms | 1.735 ms | -0.865 ms (-33.3%) |
| Free main RAM | 2,490,368 bytes | 2,441,216 bytes | -49,152 bytes |

The combined preparation and actor submission cost falls by about 2.6 ms, and
the matched Flycast rate moves from about 8.0 to 8.1 frames per second. The two
fixed-capacity packed-color arrays account for the exact 48 KiB RAM change.
This result does not predict stock Dreamcast timing.

Correctness follows from retaining the existing `shade_color` conversion and
calling it on the same finalized float RGB values. The matched run reports zero
actor strip fallbacks; any future near-plane fallback continues through the old
float interpolation and packing path.

Evidence:

- Per-record baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d167-r3f-compact-actor-light-lists-production`
- Packed-color candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d170-r3h-packed-actor-colors-experiment`
- Candidate ELF SHA-256:
  `2eaeb83b1ddf208189c66feaa5ea36cb1dff71e94427a6306a10816b4fa5d5c4`

## Rejected adjacent experiment

An 8,192-entry room transform cache was also measured. It saved only about
1.1 ms while consuming 458,752 additional bytes of main RAM. The port retains
the 1,024-entry cache. The result confirms that capacity alone cannot restore
reuse erased when room position, normal, and UV identities were flattened.

Evidence:
`C:\Flycast-Evidence\re4-dreamcast\d169-r3g-room-cache-8192-experiment`.

## Acceptance boundary

This removes repeated actor color conversion from the current direct-strip
path. It does not establish original-game selected-light traces,
source-authored animated normals, 30 fps, physical-hardware timing, or complete
source material behavior. The dominant measured costs remain the room passes,
actor lighting and color preparation, actor submission, and rebuilt actor
normals.
