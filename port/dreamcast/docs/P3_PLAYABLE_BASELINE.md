# P3 functional Flycast prototype baseline

Recorded 2026-09-19 for the native KallistiOS r10d prototype. This records an
automated gameplay-state loop and improved performance point samples. The
earlier description that the performance gate was closed was too broad: no
whole-route timing distribution or manual audiovisual review was accepted,
and the final-view sample exceeds the 33.33 ms target.

The user's presentation requirement now follows [PLAYABLE_PATH.md](PLAYABLE_PATH.md):
a convincing textured encounter today in Flycast, with physical Dreamcast next.
This historical checkpoint does not satisfy that requirement.

## Experimental profile

- 320x240 RGB565, flat-shaded opaque PVR list
- r10d source-group package clustered per material batch at 8 m
- Leon and Ganado clustered per source batch at 75 mm after offline skinning;
  every selected source clip retains its original frame count and timing
- 35 m draw horizon for the bounded demo route
- room and actor frustum/backface rejection
- one PVR submission per triangle instead of three vertex submissions

The converters are deterministic and keep all generated packages private. At
this checkpoint the default `demo-r10d` target selects this experimental profile;
it has not been promoted for the convincing demo. Set `R10D_CLUSTER_SIZE=0` and
`CHARACTER_CLUSTER_MM=0` to generate the unmodified comparison meshes.

## Measured result

At the representative spawn, live SH-4 telemetry read from Flycast reported:

| Profile | Groups | Transformed room vertices | Room triangles | Actor triangles | Frame |
|---|---:|---:|---:|---:|---:|
| Source groups, source actors | 137 | 47,966 | 11,592 | 3,979 | 117,116 us |
| Experimental LOD profile | 61 | 5,633 | 2,038 | 748 | 29,354 us |

The selected spawn sample has a reciprocal rate of approximately 34.1 fps;
this is not a measured sustained or displayed frame rate.
The completed route's final view reported 37,821 us (about 26.4 fps), 65 visible
groups, 5,947 transformed room vertices, 2,022 room triangles, and 752 actor
triangles. A separate normal-boot sample reported 26,817 us. These are point
samples rather than route percentiles and are not physical console timing.

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

This establishes that the optimized build's state trace observed player death,
restart, an empty magazine and reload, enemy defeat, collision traversal, exit, and encounter
reset. It does not establish manual controller usability or that the visible
combat matches the trace. The exit is at x=32, z=-284 on the reachable side of
the SAT wall. The older x=9 route stalled against collision in faster runs;
low-frame-rate tunneling was the working explanation, not an independently
verified collision diagnosis. The new route passed the automated loop.

## Remaining limits

- The room and actors are coarse, untextured LODs. Readability and moving visual
  quality have not been accepted. Telemetry cannot establish either property.
- Enemy pursuit currently omits wall resolution and the shot check omits wall
  occlusion. The convincing-demo plan makes those visible behavior fixes required.
- The 35 m horizon is a scoped demo choice. It does not describe the GameCube
  renderer's general room visibility.
- Near-plane clipping, route timing percentiles, RAM/VRAM pool peaks, basic
  textures and attachments, audio, and a bootable optical-disc image remain.
- No physical Dreamcast run has been performed. Flycast success must not be
  reported as stock hardware acceptance.
