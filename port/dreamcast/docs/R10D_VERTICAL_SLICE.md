# r10d playable vertical slice

`r10d` is the first playable-room target. Its original room module allocates
empty work and performs no per-frame scripting; the room is driven by its data
files. The first slice hard-codes one encounter and exit instead of enabling
all data-driven events. An empty room module alone does not prove there are no
event or actor dependencies. The current task order is in
[PLAYABLE_PATH.md](PLAYABLE_PATH.md), with supporting
[hardware/source research](HARDWARE_TRANSLATION.md).

## Private asset preparation

The supplied `G4BE08` Disc 1 image is kept under `orig/` and ignored by Git.
The validated preparation path is:

1. Copy `/files/St1/r10d.das` from the disc with pinned `dtk` 1.8.3.
2. Extract the YZ2-compressed DAS with `RE4_DASYZ2_TOOL` 2025-07-17.
3. Export `r10d_004.SMD` with `RE4_GCWII_SCENARIO_SMD_TOOL` V1.3.1.
4. Convert the resulting OBJ with `tools/convert_room_obj.py`.
5. Convert extracted `r10d_001.SAT` with `tools/convert_sat.py`.

The two external releases are source-available third-party tools. Pin their
archives by SHA-256 before using them:

- `RE4_DASYZ2_TOOL-2025-07-17.zip`:
  `51e70185d7caecba7d6351c7e93f5de3a515918a7fbfb514974598532e259dc4`
- `RE4_GCWII_SCENARIO_SMD_TOOL.V.1.3.1.zip`:
  `370c2ead63c2e9f40cc31be81ec5fab78b3979d478d81a17450bf157e68c2350`

From the repository root, after the OBJ exists, run:

```sh
make -C port/dreamcast -f Makefile.host room-r10d
```

The generated package and manifest remain under `port/dreamcast/build/private`.
No disc-derived bytes belong in Git.

Build the private flat-shaded room viewer with:

```sh
source port/dreamcast/kos-env.sh
make -C port/dreamcast/room
```

The executable validates both package headers and CRCs, maps the room and SAT
data from its generated ROM disk, culls groups by their bounds, and reports the
player position, collision hits, submitted triangles, and render-call time.
The timer includes PVR wait time. See
[the corrected interpretation](ROOM_SH4_BASELINE.md).

## Package boundary

`re4dc-room` version 2 is little-endian and starts with the eight-byte magic
`RE4DCRM\0`. It contains fixed-size material names, group records with bounds,
material batches, interleaved position/normal/UV vertices, and 32-bit triangle
indices. Version 2 also carries winding-preserving strip records for native PVR
submission while retaining the triangle stream for ordered transparency and
clipping fallback. The first `r10d` build partitioned static triangles into 10-unit X/Z
cells. The current default preserves OBJ export groups because the bounded
gameplay-camera comparison transformed fewer vertices with the same submitted
triangle count. Recreate the older cell package for comparison with:

```sh
python3 port/dreamcast/tools/convert_room_obj.py --cell-size 10 \
  orig/G4BE08/rooms/r10d/r10d/r10d_004.scenario.obj \
  port/dreamcast/build/private/r10d-cells.re4room
```

These historical comparison packages retain the same geometry. At the unchanged spawn camera, the
source-group package transformed 47,966 vertices versus 58,217 for cells and
submitted the same 11,592 triangles; combined render time fell only from about
114 ms to 110 ms. Source-group bounds are conservative but are not yet mapped
to original SMD visibility flags or source culling spheres.

The current experimental default additionally uses an 8 m room cluster. That
changes geometry and UVs and has not passed presentation review. Today's plan
requires intact foreground shapes and correct textures in the selected area.

Textures are outside the historical version 1 package. They are now the first
implementation priority for today's convincing-demo plan: the existing TPL and
MTL material/alpha mappings must feed a versioned textured package. The flat
prototype is not presentation acceptance; see [PLAYABLE_PATH.md](PLAYABLE_PATH.md).

`RE4DCSAT` version 1 is a separate little-endian collision package containing
scaled positions, source normals, polygon vertex/normal indices, attributes,
and the original floor/slope/wall ranges. The runtime currently scans the 50
floor/slope and 219 wall triangles directly. It does not need the source block
tree at this scale. The current prototype starts at `(0, -7.98, -245)`, draws
animated actor bodies, and resets near the marker at `(32, -7.98, -284)`.
Today's encounter will be selected for visual coherence and reachable combat;
the older x=9 route is superseded.

## Prototype and presentation acceptance

The historical functional prototype requires controller movement for animated
Leon in converted `r10d`, SAT-derived player collision, a shoulder follow camera,
and one Ganado that can approach, attack, and take aimed handgun damage.
Firing/reloading, player damage/death, enemy death, and an exit/reset
complete the small loop. The recorded evidence covers automated state transitions;
it does not establish convincing appearance or a manually reviewed presentation.

Today's acceptance additionally requires complete textured actors and scenery,
a visible handgun and matching action animation, wall-aware enemy/hit behavior,
stable camera/clipping, core sound, legible HUD, completion/retry presentation,
whole-route timing/memory evidence, and a private launchable Flycast package.
Saves, general room streaming, story events, complete audio coverage, and
campaign progression remain deferred. The ordered work and deadline tradeoffs
are in [PLAYABLE_PATH.md](PLAYABLE_PATH.md).
