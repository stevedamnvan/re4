# r100 R3c ordered alpha-strip checkpoint

Recorded 2026-09-20 on top of the native opaque room-strip checkpoint. The
converter now certifies whether each generated strip stream reproduces the
source triangle order as well as its winding. The translucent renderer uses a
native strip only when that certificate is present; every reordered batch stays
on the previous indexed-triangle path.

## Why the order gate exists

Alpha blending can change when triangles move relative to one another, even if
the same geometry is eventually submitted. The converter reconstructs every
strip triangle, normalizes only cyclic rotations of its three indices, and
compares the resulting sequence with the batch's original sequence. It writes
`kBatchStripOrderPreserved` only for an exact sequence match. The package loader
rejects unknown batch flags.

For the accepted r100 package and current texture-alpha classification:

| Alpha geometry | Count |
|---|---:|
| Alpha batches | 524 |
| Certified order-preserving batches | 503 |
| Alpha triangles | 5,910 |
| Triangles in certified batches | 5,186 |
| Batches retained on the old path | 21 / 724 triangles |

No geometry, texture, material, camera, light, or cull setting changed. The
package remains version 2 and 2,017,240 bytes; only previously reserved batch
flag bits now carry the certificate.

## Matched Flycast result

Medians cover simulation ticks 220 through 474 using the same autoplay route.

| Measure | Opaque strips only | Ordered alpha strips | Change |
|---|---:|---:|---:|
| Outer frame work | 155.421 ms | 153.157 ms | -2.264 ms (-1.5%) |
| Total render work | 155.035 ms | 152.773 ms | -2.262 ms (-1.5%) |
| Translucent room pass | 38.211 ms | 36.204 ms | -2.007 ms (-5.3%) |
| Opaque room pass | 59.936 ms | 59.643 ms | -0.293 ms |
| Room index references | 33,154 | 28,398 | -4,756 (-14.3%) |
| Room transforms/light evaluations | 25,417 | 25,417 | unchanged |
| Direct room strips | 3,187 | 4,257 | +1,070 |

The candidate and opaque-strip reference screenshots were captured at the same
settled autoplay camera and state. Every game-area pixel outside the actor's
small animation-difference region is byte-identical. The room, its alpha
surfaces, lighting, and HUD show no visible regression in the captured view.

Evidence:

- Opaque-strip baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d152-r3b-native-room-strips-autoplay`
- Ordered-alpha candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d154-r3c-ordered-alpha-strips-autoplay`
- Candidate ELF SHA-256:
  `7accae7077eb7e56bcbe4628d568978d792bc8b44617fc0b0b5c626e34184e30`
- Candidate r100 room package SHA-256:
  `3e6f451bd70e12ec64918f5630ff392f9cefac1cecfc9804f21a72cefc5c6895`

## Acceptance boundary

This is an incremental CPU/submission reduction. It does not prove correct
source blend/depth semantics for every material, all-camera alpha parity,
physical-hardware output, or real-time playability. The matched Flycast result
is about 6.5 fps, still far from the approximately 30 fps target.
