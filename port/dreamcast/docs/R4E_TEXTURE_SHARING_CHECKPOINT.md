# R4e: one allocation per distinct texture payload (DCA3 audit item B1)

Status: kept. The second half of R4 deliverable 2.

Several materials bind the same texture. The converter already noticed this and
stores such a payload once, so two descriptors carry the same `data_offset`.
The runtime did not notice: `Package::upload()` called `pvr_mem_malloc()` once
per descriptor and uploaded the same bytes again. Leon's package was 84%
redundant by this measure and the Ganado's 73%.

Result: 1,509,728 bytes of texture memory recovered, 36.7% of the total, and
texture upload falls from 16,945 us to 7,132 us. The frame, the submitted
stream and the rendered framebuffers are unchanged.

## What changed

`Package::upload()` now checks whether an earlier descriptor in the same package
already uploaded this `(data_offset, data_size)` and, if so, points at that
allocation instead of making a second one. A parallel `owns_texture_` flag
records which descriptor owns each allocation, and `close()` frees only the
owners. Without that flag the shared pointers would be double freed, which is
the one real hazard in this change.

Payload identity is not assumed from the offset alone: the converter writes a
payload once and every descriptor referring to it carries the same offset and
size, so equal `(data_offset, data_size)` means the same bytes by construction.
Material state is untouched. Sampler and blend state live in the per-material
polygon headers, so two materials may share texels while drawing differently.

The search is linear over earlier descriptors, at most 76 in the largest
package, which is 2,850 comparisons at load and nothing per frame.

## Measurements

Flycast, 640x480, r100 autoplay, matched window (ticks 165-1194), against the
accepted R4d build in the same session.

| | R4d accepted | R4e | change |
|---|---:|---:|---:|
| free PVR memory after textures | 1,521,128 B | 3,030,856 B | **+1,509,728 B** |
| texture upload | 16,945 us | 7,132 us | -9,813 us |
| allocations | 168 | 93 | -75 |
| frame p50 | 57,951 us | 57,950 us | -1 us |
| opaque room p50 | 19,464 us | 19,464 us | 0 |
| opaque actor p50 | 9,900 us | 9,899 us | -1 us |
| `submit_us` p50 | 33,391 us | 33,390 us | -1 us |
| main RAM free | 5,353,472 B | 5,353,472 B | 0 |
| heap used | 135,004 B | 135,276 B | +272 B |

The frame is unchanged, as expected: this removes duplicate uploads at load, not
per-frame work. The 272 extra heap bytes are the ownership flags, one byte per
descriptor across four packages plus allocator overhead. The upload saving comes
free with the memory saving, since 75 fewer payloads are copied into VRAM.

The recovered memory is concentrated exactly where the redundancy was. Leon's
76 descriptors resolve to 11 distinct payloads, the Ganado's 14 to 4. The room
and HUD packages have no duplicates at all and are untouched. One Leon payload,
a 64x128 texture of 16,384 bytes, was bound by 31 descriptors and uploaded 31
times; it is now uploaded once.

Free PVR memory before textures is 5,635,840 bytes, so texture residency falls
from 73% of that pool to 46%.

## Correctness

The framebuffer comparison is the right check here and the stream digest is not:
this change alters which texture address a polygon header points at, not which
vertices are emitted, so a digest of the submitted stream would pass trivially
while telling us nothing about the image. Frame time is unchanged to the
microsecond, so the cadence objection that made framebuffer capture invalid in
R4c and R4d does not apply.

Framebuffers captured at simulation ticks 250, 450 and 700, both buffers: 6 of 6
byte-identical to the R4d baseline.

Host tests pass with zero failures. The load report now prints the shared count
alongside the texture counts.

## Evidence

`d267-r4e-texture-sharing` holds the timing and memory measurement.
`d268-r4e-sharing-visual` holds the framebuffer comparison.

## What this leaves open

Cross-package sharing was measured and is worth nothing here: after in-package
deduplication the four packages hold 93 payloads with 93 distinct content
hashes, so no payload is shared between packages. A content-addressed global
cache would add a digest and a lookup for zero bytes. Revisit only if a future
residency set brings packages together that genuinely overlap.

Sharing is currently scoped to one package, keyed on an offset rather than on
content. When R4's residency work introduces packages that load and unload
independently, that key has to become a validated content identity with
reference counting across packages, as the audit describes. Nothing here blocks
that; the ownership flag is the seed of it.

VQ payloads remain the other open half of deliverable 2. The `data_size ==
width * height * 2` check in `Package::open()` still has to go before a VQ or
palette payload can be expressed.
