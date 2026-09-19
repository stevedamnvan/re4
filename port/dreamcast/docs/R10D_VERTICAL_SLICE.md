# r10d playable vertical slice

`r10d` is the first playable-room target. Its original room module allocates
empty work and performs no per-frame scripting; the room is driven by its data
files. That avoids pulling the event system into the first gameplay milestone.

## Private asset preparation

The supplied `G4BE08` Disc 1 image is kept under `orig/` and ignored by Git.
The validated preparation path is:

1. Copy `/files/St1/r10d.das` from the disc with pinned `dtk` 1.8.3.
2. Extract the YZ2-compressed DAS with `RE4_DASYZ2_TOOL` 2025-07-17.
3. Export `r10d_004.SMD` with `RE4_GCWII_SCENARIO_SMD_TOOL` V1.3.1.
4. Convert the resulting OBJ with `tools/convert_room_obj.py`.

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

The viewer validates the package header and CRC, maps the room directly from
its generated ROM disk, culls groups by their bounds, and reports submitted
triangles and render time. It establishes the real geometry budget before
character integration or texture work.

## Package boundary

`re4dc-room` version 1 is little-endian and starts with the eight-byte magic
`RE4DCRM\0`. It contains fixed-size material names, group records with bounds,
material batches, interleaved position/normal/UV vertices, and 32-bit triangle
indices. The `r10d` build partitions static triangles into 10-unit X/Z cells;
cell bounds let the first renderer reject distant or off-screen geometry before
transforming its vertices.

Textures are intentionally outside version 1. The first runtime checkpoint is
flat-shaded room geometry plus collision. Texture conversion follows once the
camera, visibility, and frame-time measurements are real.

## Playable acceptance boundary

The vertical slice is playable when a controller can move animated Leon in the
converted `r10d` room, SAT-derived collision blocks him, a fixed follow camera
frames the room, one Ganado can approach and take aimed handgun damage, and an
exit trigger ends or resets the slice. Menus, saves, general room streaming,
story events, complete audio, and campaign progression are outside this gate.
