# r10d room SH-4 baseline

This checkpoint proves that a real Disc 1 room can be extracted offline,
packaged, validated, and rendered by a native KallistiOS SH-4 executable. It
also records a missed frame budget for this viewer and camera. The source audit
below supersedes the earlier conclusion that the room mesh itself must be
replaced for the playable slice.

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
render-call duration is far above the 33.3 ms target, but includes
`pvr_wait_ready()` and therefore cannot isolate SH-4 work from prior PVR work
or pacing. There are no textures, Leon, collision, enemy logic, or audio in this
viewer, and this is not a representative combined gameplay-frame measurement.

## Decision

The arbitrary orbit camera and cell grouping touched 97.8% of the package's
vertices. The original engine instead registers separate models and checks
their bounds against the camera before drawing accepted display lists. Source
frustum culling is confirmed; the exact visible r10d set has not been captured.
This is not proof of general occlusion culling or of a particular speedup.

Preserve the art and first compare a gameplay camera with conservative group
culling and correct near-plane clipping. Separate wait, transform, submission,
and complete-frame timing. Use SAT for collision and an optional temporary
debug mesh, not as a mandatory replacement for scenery. Apply LOD only to
measured costs; keep movement/Leon/combat integration advancing.

The existing converter's `--cell-size 0` path generated a separate private
comparison package with 226 exported groups, 311 batches, 3,197,028 bytes, and
SHA-256 `3bc4c94b6b32c2e3a322483c35591d396fd8ae22a6cbc765e508404a70f8bb32`.
It retains the same vertex/triangle counts and has not yet been rendered or
timed. Export groups are not yet verified as original SMD visibility objects.

The historical capture and its `render-proof-performance-rejected` manifest
remain unchanged. That label applies to the recorded viewer run. The current
decision and next implementation item are in [PLAYABLE_PATH.md](PLAYABLE_PATH.md).
