# r100 R3k source-child cell checkpoint

Recorded 2026-09-20 from the package-v6 actor and 2,048-entry room-cache
baseline. The converter now has a reproducible production profile that divides
opaque source objects into conservative one-metre child cells. It preserves all
40,419 vertices and 30,895 triangles. The 14 alpha-bearing materials remain
unpartitioned so their source draw order is unchanged.

## Controlled sweep

All candidates use the same source camera and actor state over simulation ticks
273 through 348. Times are Flycast medians, not physical Dreamcast results.

| Cell size | Groups | Visible groups | Room triangles | Median frame | Free main RAM | Decision |
|---:|---:|---:|---:|---:|---:|---|
| 24 m | 221 | 35 | 10,573 | 112.888 ms | 6,303,744 bytes | Previous production profile |
| 12 m | 478 | 52 | 10,282 | 109.702 ms | 6,197,248 bytes | Improved, superseded |
| 8 m | 636 | 61 | 10,079 | 105.968 ms | 6,164,480 bytes | Improved, superseded |
| 4 m | 1,063 | 101 | 7,903 | 94.866 ms | 6,062,080 bytes | Improved, superseded |
| 2 m | 1,815 | 148 | 6,835 | 91.182 ms | 5,894,144 bytes | Improved, superseded |
| 1 m | 3,006 | 243 | 6,377 | 89.606 ms | 5,632,000 bytes | Accepted |
| 0.5 m | 4,569 | 450 | 5,814 | 91.252 ms | 5,287,936 bytes | Rejected: traversal and strip fragmentation outweigh culling |

The accepted profile reduces the matched frame interval by 23.282 ms, or
20.6%, relative to the 24-metre profile. Opaque-room work falls from 44.151 to
19.240 ms. Room index references fall from 28,398 to 18,111. No source geometry,
camera data, texture, light rule, character, collision, or resolution was
removed.

The finer grouping exposed vertices shared by source objects with different
selected-light lists. Static room-light ownership now uses a 16-bit group index.
Such shared vertices are marked conflicted and use the exact per-use light path;
they are never baked with another object's light list.

The production package is deterministic. `make -f Makefile.host
room-r100-production` recreates the accepted package with SHA-256
`f8ae5774390b9b51932403e9dfd767c72b50adac6d58f9d3996a1a52beaf4c21`.

## Full-route evidence

The accepted build ran through simulation tick 957, killed the Ganado, reset at
tick 905, and killed it again. It reported no simulation overruns, dropped
simulation ticks, discarded simulation time, or input-queue drops. Across the
full route after warm-up, its median frame interval was 99.580 ms and its 95th
percentile was 102.084 ms, approximately 10 presented frames per second in
Flycast. Minimum reported free main RAM was 5,632,000 bytes.

Evidence:

- 24-metre reference: `C:\Flycast-Evidence\re4-dreamcast\d184-r3j-room-cache-2048`
- 1-metre sweep: `C:\Flycast-Evidence\re4-dreamcast\d193-r3k-source-child-cell1`
- Rejected 0.5-metre sweep: `C:\Flycast-Evidence\re4-dreamcast\d194-r3k-source-child-cell0_5`
- Accepted full route and screenshot: `C:\Flycast-Evidence\re4-dreamcast\d195-r3k-source-child-cell1-production-30s`
- Accepted ELF SHA-256: `2838e8c131b39fc790f523ebc778427a33d0e0ec8a94185e71227208ae3b088e`

## Acceptance boundary

This checkpoint accepts conservative visibility granularity for the current
30-second encounter. It does not establish visual parity for every free-camera
position, complete character-model correctness, 30 fps, or physical Dreamcast
timing. The accepted capture still exposes unresolved Leon attachment and face
presentation questions, which are the next fidelity gate.
