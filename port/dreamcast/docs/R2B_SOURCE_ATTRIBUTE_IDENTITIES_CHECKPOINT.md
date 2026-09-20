# r100 R2b source attribute-identity checkpoint

Recorded 2026-09-20 on top of the source actor-strip and source-child culling
checkpoints. Character package version 4 now keeps animated source positions,
authored normal identities, UV draw corners, and gameplay markers as separate
records instead of expanding every sampled position at each UV seam.

## Representation

The converter now keys a draw corner by its original position, normal, and UV
indices. Each draw corner references one animated position and one normal work
item. A normal work item retains the original position/normal pairing and a
position reference for lighting. GameCube primitive streams continue to index
draw corners, so the existing direct PVR strip path remains intact.

This fixes two structural losses in the version 3 package:

- sampled positions are no longer duplicated solely because a surface crosses
  a UV seam; and
- corners with the same position and UV but different authored normals are no
  longer merged.

The runtime projects unique animated positions once. Its current interim normal
path still derives the deformed direction from adjacent faces, but accumulates
and lights through the recovered source position/normal identities. Source
normal values, their palette references, and `MakeWeightPalette/Ext` skinning
remain open work.

## Exact r100 package inventory

| Actor | Animated positions | Draw corners | Normal work items | Source strips |
|---|---:|---:|---:|---:|
| Leon plus handgun and markers | 5,745 | 7,371 | 6,535 | 975 |
| Ganado plus head, hands, hatchet, and markers | 1,690 | 2,427 | 1,900 | 372 |

All 9,519 Leon and 3,111 Ganado source triangles remain present. Gameplay
markers remain at the end of the animated-position array and are never exposed
as draw corners.

The resident packages changed as follows:

| Package | Version 3 | Version 4 | Change |
|---|---:|---:|---:|
| Leon | 4,716,276 bytes | 3,926,268 bytes | -790,008 bytes |
| Ganado | 4,003,972 bytes | 2,926,888 bytes | -1,077,084 bytes |
| Combined | 8,720,248 bytes | 6,853,156 bytes | -1,867,092 bytes |

## Matched Flycast result

The comparison uses the same 640x480 room, source camera, actors, textures,
lighting, simulation, and autoplay route. Medians cover the overlapping route
from simulation ticks 220 through 474; nearest samples differ by at most three
simulation ticks.

| Measure | Version 3 | Version 4 | Change |
|---|---:|---:|---:|
| Total render work | 180.211 ms | 178.840 ms | -1.336 ms matched |
| Actor pose projection | 6.523 ms | 5.179 ms | -1.344 ms |
| Actor normal construction | 8.677 ms | 9.727 ms | +1.051 ms |
| Actor lighting | 22.257 ms | 20.216 ms | -2.041 ms |
| Opaque actor submission | 15.811 ms | 16.667 ms | +0.855 ms |
| Main-RAM headroom | 974,848 bytes | 2,842,624 bytes | +1,867,776 bytes |
| Actor triangles | 12,014 | 12,014 | unchanged |
| Direct source strips | 1,347 | 1,347 | unchanged |
| Strip fallbacks | 0 | 0 | unchanged |

The extra normal and submission cost comes from honoring additional hard-edge
draw identities and the new indirection. The reduced position and lighting work
still produces a small net frame-time improvement. The memory recovery is more
important: it creates room for source skeletal data and bounded streaming work
without reducing texture or mesh fidelity.

Evidence:

- Version 3 baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d146-r3a-source-cell24-source-alpha-order-autoplay`
- Version 4 autoplay:
  `C:\Flycast-Evidence\re4-dreamcast\d150-r2b-attribute-identities-autoplay`
- Version 4 manual image and input trace:
  `C:\Flycast-Evidence\re4-dreamcast\d151-r2b-attribute-identities-manual`
- Autoplay ELF SHA-256:
  `a0e4becf9629b071329bb09785fdbdfe252cb0def6d086141020f8d0cc8af55e`
- Manual ELF SHA-256:
  `aef7b4133edff50e3be7df495f920df2ad46c543e156882d1cb50f1e29a004ec`

The manual build reported flags `16`, sampled the controller at about 10 ms,
and contained no autoplay file. Its captured cabin image shows intact actors,
weapon attachment, source room, lighting, and HUD. This is Flycast evidence;
stock Dreamcast timing and physical output remain untested.

## Acceptance boundary

This checkpoint does not claim source normal-vector skinning, source runtime
bone animation, 30 fps, physical-hardware validation, or matched original-game
pixels. It establishes the package/runtime boundary required to add those
pieces without duplicating position work at UV seams.
