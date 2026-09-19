# r10d room SH-4 baseline

This checkpoint proves that a real Disc 1 room can be extracted offline,
packaged, validated, and rendered by a native KallistiOS SH-4 executable. It
also rejects the full-resolution mesh as the geometry path for the first
playable slice.

## Inputs and artifacts

- Source room: private `G4BE08 /files/St1/r10d.das`
- Exported OBJ SHA-256:
  `ce3789f79d327e7cf19558f7f687cae076cb7cc14ba4c464dd224b156d04c6f2`
- `re4dc-room` package: 3,229,396 bytes
- Package SHA-256:
  `588e5dc48253828dd1348a623c2c967eea52832a9fd64a0f0a60e3a5a3caf13a`
- Viewer ELF SHA-256:
  `a5e2c7f456fe35c0c6ebbf9b4686cbf238b15d8f1cc4481a4f6312bd7d8a9716`
- Evidence directory:
  `C:\Flycast-Evidence\re4-dreamcast\room-r10d-20260919-153238`

The private package contains 75,009 deduplicated vertices, 63,745 triangles,
59 materials, 389 ten-unit X/Z cells, and 1,147 material batches. Its runtime
loader validates the schema, ranges, and payload CRC before rendering.

## Flycast result

The native viewer booted under KallistiOS 2.3.0, mapped the room package from
its ROM disk, and produced recognisable room geometry at 320x240. At frame 120
the selected fixed view reported:

- 268 visible cells
- 73,340 transformed vertices
- 23,491 submitted flat-shaded triangles after back-face rejection
- 171,688 microseconds in the measured render call

This is emulator evidence. It is not a physical-hardware timing result. The
result is far above the 33.3 ms frame deadline even before textures, Leon,
collision, enemy logic, or audio are added.

## Decision

Do not continue adding features to this full-resolution triangle path. The
playable gate should render a SAT-derived collision proxy plus a deliberately
small set of simplified scenery, while retaining the full room package as the
visual reference. Add higher-detail cells only against a measured visible
triangle and transform budget. Triangle strips and more aggressive SH-4/store-
queue processing remain useful later, but they must not block controller
movement, collision, camera, and combat integration.
