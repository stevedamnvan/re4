# r100 R2a SAT hierarchy checkpoint

Recorded 2026-09-20 after the R1b source-selection implementation. This
checkpoint restores the source SAT broad phase before changing the port's
remaining collision primitives. It does not introduce a newly designed spatial
tree.

## Source data retained

`convert_sat.py` now parses the variable-sized `cSatBlock` graph beginning
after the source polygon table. It preserves the source traversal structure as
flat portable records with explicit child and next indices, plus each leaf's
ordered floor, slope, and wall polygon references. It also retains the source
edge-vector table and the three edge identities of every polygon.

The r100 section-0 package contains:

| Record | Count |
|---|---:|
| Collision polygons | 1,507 |
| Edge vectors | 4,521 |
| Blocks | 1,157 |
| Parent blocks | 289 |
| Leaf blocks | 868 |
| Ordered polygon references | 7,034 |

The optional extension is appended after the existing collision geometry and
covered by the package payload CRC. Old blockless fixtures remain byte-identical.
The target loader validates all strides, ranges, child/next indices, leaf
counts, edge indices, and polygon references before exposing the hierarchy.

`make -C port/dreamcast -f Makefile.host collision-r100-source` regenerates the
private package. Its SHA-256 is
`fd0f70280f08d0a16e628a6b6f12cae1e073c358dff1e1ca6cbbe78c6a3a510a`.
The extension adds 135,976 bytes to the 47,624-byte flat package.

## Runtime traversal

Floor probes, actor wall candidates, route visibility, shots, and the three-ray
source camera correction now traverse the source child/next block graph. The
line overlap and swept-sphere block tests follow `cSatBlock::lineOverlap` and
`cSatBlock::hitCheckSphere`. A fixed 1,024-byte bitset reproduces the source
one-test-per-polygon rule. Candidate order remains the source leaf/reference
order; there is no coordinate sort or replacement BVH.

Telemetry ABI version 5 adds query, block-test, and polygon-candidate counts.
No dynamic allocation was added to a collision query. The fixed candidate
buffer supports the source maximum of 8,192 polygons.

## Flycast result

The comparison uses the same 640x480 r100 presentation and source-selected
lighting as R1b. These are emulator measurements, not physical Dreamcast
timings.

| Measure | R1b flat scans | R2a source hierarchy |
|---|---:|---:|
| Simulation work per outer loop | 8.61 ms average | 0.78 ms average |
| Camera collision | 3.37 ms average | 0.147 ms average |
| Render work | 295.9 ms average | 296.9 ms average |
| Main-RAM free telemetry | 1,904,640 bytes | 1,658,880 bytes |

The R2a trace averaged 23.1 collision queries, 578.6 block tests, and 157.4
polygon candidates per outer loop; the maximum candidate count was 316. It
retained the same sampled enemy health progression 500/365/230/95/0 in the
combined R2a traces, ammo states 6 through 2, and reset timing within the
roughly nine-tick telemetry sampling interval. No simulation ticks or
microseconds were discarded.

Private evidence:

- package/load smoke:
  `C:\Flycast-Evidence\re4-dreamcast\d122-r2a-sat-hierarchy-package`
- full state/reset trace:
  `C:\Flycast-Evidence\re4-dreamcast\d123-r2a-sat-hierarchy-autoplay`
- telemetry-v5 counter trace, ELF SHA-256
  `daaf8c7823216901f6db5ba51d4af5b0fc62067b30f99b37e7b1d453b855290f`:
  `C:\Flycast-Evidence\re4-dreamcast\d124-r2a-sat-hierarchy-v5`
- final manual-input package, ELF SHA-256
  `332fa26b322533294b47568cfa6fb70795f833cd03ed282bde35b0276821e519`:
  `C:\Flycast-Evidence\re4-dreamcast\d125-r2a-final-manual`

The final manual trace captured 35 coherent telemetry-v5 samples from ticks
330 through 622. The autoplay flag was clear in every sample, main-RAM free was
1,658,880 bytes, and no simulation ticks or microseconds were discarded.

## Acceptance boundary

This closes source hierarchy preservation and target-side broad-phase use. It
does not close all of R2a. The port still uses its reduced floor projection,
wall-segment pushout, and triangle-line tests rather than the source
`At_poly_sphere_ck` and `At_poly_line_ck` rules with full attribute filtering.
The source-versus-port query trace still needs block IDs, polygon IDs, hit
attributes, mutation order, and results at matched states. SAT section 1 also
needs its original `SatMgr`/`EatMgr` ownership established before use.

The added resident hierarchy costs about 240 KiB in the current ROM-disk model.
It is acceptable for this checkpoint but strengthens the need for explicit disc
residency instead of embedding every future room resource. Stock Dreamcast
timing and physical collision validation remain pending.
