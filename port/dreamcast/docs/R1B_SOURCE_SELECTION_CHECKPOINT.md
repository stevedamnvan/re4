# r100 R1b source-selection checkpoint

Recorded 2026-09-20 after the R1a room-work checkpoint. This change restores
source object identity, cull state, and the selection inputs used by the
original per-model lighting manager. It keeps the same r100 room export,
textures, camera, actors, collision, audio, resolution, and encounter logic.

This is an implementation checkpoint, not final R1b acceptance. A matched
original-game trace of the ordered selected light IDs is still required. The
source-derived selection also changes the cabin image substantially, so that
image must be compared against the same r100 cut and simulation state in the
debug game before it becomes the visual reference.

## Recovered source data

`convert_room_obj.py` can now take the private room SMX and the placed/common
SMD files alongside the OBJ. For each original room object it appends:

- source object ID, type, ordering-table type, flags, and `SelectMask`;
- the exact GX cull mode;
- the source BIN model bounds transformed by the SMD position, rotation, and
  scale into a box lighting volume.

The optional records are covered by the existing room-package payload CRC and
guarded by a header flag. Packages built without these inputs retain their old
layout and remain byte-for-byte deterministic. Spatially subdivided OBJ groups
are rejected when source metadata is requested because one synthetic cell can
no longer stand for one source model.

The private r100 package has 58 source groups and 58 recovered light volumes.
Its cull modes are 32 `GX_CULL_NONE` and 26 `GX_CULL_BACK`. The converter tests
exercise SMX identity/cull transfer, synthetic SMD/BIN bound recovery, and the
unchanged package path. The package SHA-256 is
`f280a6248ce126cf86765147f154f09267d31b9e1da8a01462890acb127c25c9`;
no source asset bytes are tracked in Git.

## Runtime selection

Static room groups now reproduce the relevant `cLightMgr::setModel2` filters in
source order: the scenery enable bit, the object's source selection mask, and
the original box-versus-light-radius volume test. Source light 19 is included
in the cut-0 inventory because its scenery mask is live; the type-4 foot-shadow
light and empty slots remain excluded. The room cache key includes the selected
light set so a shared converted vertex is never reused across distinct lighting
contexts.

Leon and the village Ganado use the source `cLightInfo::init2` values found in
`player.cpp` and the shared `em10.cpp`: an upright one-metre-radius,
one-metre-half-height capsule, with enable masks 1 and 2. At the opening
placements the source-order filter selects four lights for each actor instead
of evaluating the prototype's nine-light list. The runtime retains the source
eight-light ceiling.

The renderer also applies each source object's GX cull mode. In the measured
view this removed 145 back-facing room triangles, from 4,226 to 4,081, without
removing a visible cabin surface in the inspected Flycast capture. This is a
semantic recovery; it currently occurs after vertex preparation and therefore
is not claimed as a large CPU optimization.

## Flycast observations

All results use the same packaged Flycast executable and 640x480 configuration
as R1a. They are emulator measurements, not physical Dreamcast timings.

| Step | Representative observation |
|---|---:|
| R1a prepared-light reference | about 322.5 ms render work |
| Source room selection | about 298-301 ms render work |
| Source actor selection, settled view | about 275-278 ms render work |
| Actor-lighting stage before actor selection | about 37.2 ms |
| Actor-lighting stage after actor selection | about 21.1 ms |
| PVR render sample | about 7.5 ms, materially unchanged |

The complete autoplay evidence spans simulation ticks 474 through 3,186 and
contains two reset boundaries, the enemy health sequence 500/365/230/95/0, and
ammo states 6 through 2. It records zero discarded ticks and zero discarded
microseconds. Across the mixed encounter states, average render work was 295.9
ms and average actor lighting was 21.5 ms. The final autoplay ELF SHA-256 is
`adc3e0af6c14a2afaa1e3c937011226dc24802c56a46900cb2348ba3c6d60d79`.
The presentation package was then rebuilt manually after both the r10d and r100
targets passed compilation. Its ROM disk contains no `autoplay.flag`, the
telemetry autoplay bit remained clear through a 27-frame smoke, and its ELF
SHA-256 is
`4e07682f5e27f0e67f0ef453aed75a05faa88e692150c01f44f4324da4fd24d9`.

Private evidence directories:

- `C:\Flycast-Evidence\re4-dreamcast\d116-r1b-source-cull-smoke`
- `C:\Flycast-Evidence\re4-dreamcast\d117-r1b-source-light-selection-smoke`
- `C:\Flycast-Evidence\re4-dreamcast\d118-r1b-actor-light-selection`
- `C:\Flycast-Evidence\re4-dreamcast\d119-r1b-source-light-autoplay`
- `C:\Flycast-Evidence\re4-dreamcast\d120-r1b-final-manual`
- `C:\Flycast-Evidence\re4-dreamcast\d121-r1b-final-dual-target-manual`

## Visual finding and acceptance boundary

The source selection makes most of the cabin darker than the all-lights
prototype while preserving the local fireplace contribution and character
shading. That is an expected possible consequence of restoring selection, but
the code path alone does not prove the pixels correct. Missing vertex/material
colour behavior, dynamic light state, or a model-space mismatch could still
explain part of the difference.

R1b closes only after a matched debug-game trace confirms, for Leon, the Ganado,
and representative cabin objects, the ordered selected light IDs and live light
state at the same cut/tick. The paired image must then distinguish a corrected
prototype error from a remaining renderer error. Static-light baking stays
blocked until that comparison. Physical Dreamcast performance, independent
input service, source normal/skinning structure, and the SAT hierarchy also
remain pending.
