# r100 R1d source actor-strip checkpoint

Recorded 2026-09-20 after the threaded-input checkpoint. This change retains
the original BIN/GX primitive connectivity in character package v3 and submits
source triangle strips directly to the PVR when every strip vertex is inside
the accepted depth range.

## Source inventory

The current full-detail Leon package contains 975 source triangle strips and
the Ganado contains 372. Their original draw records are substantially smaller
than the flattened triangle lists used by the previous runtime.

| Actor | Flattened triangle records | Source strip records | All source records |
|---|---:|---:|---:|
| Leon | 28,557 | 10,660 | 12,703 |
| Ganado | 9,333 | 3,459 | 4,449 |

Package v3 keeps both representations. Triangle indices remain authoritative
for reconstructed normals and for clipping fallback. Primitive records retain
the source opcode, draw-vertex range, and corresponding flattened-index range.
Packages produced with experimental position clustering omit the source stream
because clustering changes vertex identity and can remove triangles; those
packages retain the existing triangle path.

GX triangle strips (`0x98`) use the native PVR strip path. GX quads and
independent triangles continue through the existing triangle path because their
source record order does not describe one equivalent PVR strip. Character
headers use PVR clockwise culling to preserve the previous CPU path's accepted
negative screen-space winding. A strip with a vertex crossing the near plane or
outside the configured far range falls back to its retained triangles and the
existing clipper.

Telemetry ABI version 7 adds submitted actor vertex-record, direct-strip, and
strip-fallback counts.

## Matched Flycast measurement

The primary comparison uses the same autoplay simulation-tick range, 213
through 692, at 640x480 with the same room, camera, textures, lighting, actors,
and simulation. Times are medians.

| Measure | Triangle runtime | Source-strip runtime | Change |
|---|---:|---:|---:|
| Total render work | 264.868 ms | 217.005 ms | -18.1% |
| Submission interval | 227.378 ms | 179.528 ms | -21.0% |
| Opaque actor draw | 57.135 ms | 15.814 ms | -72.3% |
| Translucent actor/HUD draw | 11.384 ms | 2.457 ms | -78.4% |
| Actor pose | 6.523 ms | 6.523 ms | unchanged |
| Actor normals | 8.672 ms | 8.674 ms | unchanged |
| Actor lighting | 22.258 ms | 22.259 ms | unchanged |

Every measured frame used all 1,347 source strips directly. There were zero
strip fallbacks. Actor submission used a median 15,898 vertex records in the
autoplay trace (range 15,826-15,955), rather than resubmitting three records for
every surviving triangle.

The v3 source streams reduce main-RAM headroom by 65,536 bytes in this embedded
ROM-disk build. VRAM and AICA headroom are unchanged.

Private evidence:

- Before: `C:\Flycast-Evidence\re4-dreamcast\d136-r0-threaded-input-autoplay-regression`
- Manual image and telemetry: `C:\Flycast-Evidence\re4-dreamcast\d138-r1d-source-actor-strips-manual`
- Matched autoplay: `C:\Flycast-Evidence\re4-dreamcast\d139-r1d-source-actor-strips-autoplay`

The manual ELF SHA-256 is
`15b7697e3e11eac344af3891552ac2d5b04bdabe1c081d12a52cf03131ff4e73`.
The autoplay ELF SHA-256 is
`3f4bd70225928231fbf9aa1100efe2ae0a8fd96bcd2a3165e07ff0d3c2000953`.

The manual and encounter captures retain complete Leon and Ganado surfaces in
the inspected views. This is a visual regression check, not a matched-tick
pixel certificate. Aim extremes, near-plane strip fallback, animated alpha,
and physical PVR winding still need explicit stress coverage.

## Verification and acceptance boundary

All 44 host converter/package tests pass. Both the r10d fixture and r100
autoplay builds compile after regenerating private v3 packages. The final
presentation build is rebuilt separately without `autoplay.flag`.

This is a large fidelity-preserving submission improvement, but it does not
close real-time playability. The matched route still spends about 217 ms per
rendered frame, approximately 4.6 fps. Room drawing remains about 161 ms across
opaque and translucent passes, while actor pose, normal construction, and
lighting together remain about 37 ms. Stock Dreamcast timing and image output
remain untested.
