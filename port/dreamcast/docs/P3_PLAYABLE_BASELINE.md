# P3 playable Flycast baseline

Recorded 2026-09-19 for the native KallistiOS r10d demo. This closes the
emulator gameplay and representative-spawn performance gate. It does not close
visual parity, optical-disc boot, memory-pool, or physical Dreamcast acceptance.

## Selected profile

- 320x240 RGB565, flat-shaded opaque PVR list
- r10d source-group package clustered per material batch at 8 m
- Leon and Ganado clustered per source batch at 75 mm after offline skinning;
  every selected source clip retains its original frame count and timing
- 35 m draw horizon for the bounded demo route
- room and actor frustum/backface rejection
- one PVR submission per triangle instead of three vertex submissions

The converters are deterministic and keep all generated packages private. The
default `demo-r10d` target selects this profile. Set `R10D_CLUSTER_SIZE=0` and
`CHARACTER_CLUSTER_MM=0` to generate the unmodified comparison meshes.

## Measured result

At the representative spawn, live SH-4 telemetry read from Flycast reported:

| Profile | Groups | Transformed room vertices | Room triangles | Actor triangles | Frame |
|---|---:|---:|---:|---:|---:|
| Source groups, source actors | 137 | 47,966 | 11,592 | 3,979 | 117,116 us |
| Selected playable profile | 61 | 5,633 | 2,038 | 748 | 29,354 us |

The selected spawn sample is approximately 34.1 frames per second in Flycast.
The completed route's final view reported 37,821 us (about 26.4 fps), 65 visible
groups, 5,947 transformed room vertices, 2,022 room triangles, and 752 actor
triangles. These are point samples rather than route percentiles and are not
physical console timing.

The private package identities used by the passing run are:

- room SHA-256 `a8419893de4e96c002b2df2280ef1552fe2b649169e48ade739cb6bda77f7c16`
- Leon SHA-256 `1aa0368c28664ac47a33496d63952f4e9c74cef0c07e809636902085439b3371`
- Ganado SHA-256 `e777f220958c8275094533883dc29a5f2dcbfb4b28088cf85516a1e9f2a312ce`

## Complete-loop evidence

The optimized autoplay executable was launched in an isolated Flycast data
directory at:

`C:\Flycast-Evidence\re4-dreamcast\p3-playable-final`

Live telemetry reached phase 7 with flags `0x7` and loop count 1. The freshly
created VMU image contains:

`RE4DC_AUTOPLAY_PASS death=1 reload=1 loop=1`

This proves that the optimized build observed player death, restart, an empty
magazine and reload, enemy defeat, collision traversal, exit, and encounter
reset. The exit is at x=32, z=-284 on the reachable side of the SAT wall. The
older x=9 exit could only be reached by low-frame-rate tunneling through the
wall and was removed from the accepted route.

## Remaining limits

- The room and actors are coarse, untextured LODs. The run demonstrates a
  readable moving combat prototype, not source-image fidelity.
- The 35 m horizon is a scoped demo choice. It does not describe the GameCube
  renderer's general room visibility.
- Near-plane clipping, route timing percentiles, RAM/VRAM pool peaks, basic
  textures and attachments, audio, and a bootable optical-disc image remain.
- No physical Dreamcast run has been performed. Flycast success must not be
  reported as stock hardware acceptance.
