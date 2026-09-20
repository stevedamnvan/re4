# r100 R3j room vertex-cache bound checkpoint

Recorded 2026-09-20 after source position palettes recovered more than 5 MiB of
main RAM. The room renderer's direct cache was intentionally bounded at 1,024
entries. The current source camera still produced 25,417 transform/light cache
misses from 28,398 room index references, so this checkpoint tests whether a
larger bound buys useful reuse without changing geometry, visibility,
materials, lighting, clipping, camera, or presentation resolution.

## Controlled sweep

All candidates use the same package-v6 actor build and the same dead-enemy,
handgun-ready state over simulation ticks 273 through 348.

| Entries | Cache hits | Cache misses | Median frame | Free main RAM | Decision |
|---:|---:|---:|---:|---:|---|
| 1,024 | 2,981 | 25,417 | 113.749 ms | 6,369,280 bytes | Previous bound |
| 2,048 | 3,913 | 24,485 | 112.888 ms | 6,303,744 bytes | Accepted |
| 4,096 | 3,919 | 24,479 | 112.823 ms | 6,172,672 bytes | Rejected: six hits for another 128 KiB |
| 8,192 | 3,919 | 24,479 | 112.697 ms | 5,910,528 bytes | Rejected: no added reuse |
| 32,768 | 3,919 | 24,479 | 112.388 ms | 4,337,664 bytes | Rejected: no added reuse |

At 2,048 entries, median opaque-room work falls from 45.005 to 44.151 ms
and total render work falls from 113.414 to 112.555 ms. The 65,536-byte cost
removes 932 repeated transforms and light evaluations. Larger bounds reach the
same practical reuse ceiling, so their small timing changes are not accepted as
a reasonable memory trade.

Evidence:

- 1,024-entry reference:
  `C:\Flycast-Evidence\re4-dreamcast\d178-r3i-v6-marker-gameplay-fix`
- Accepted 2,048-entry candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d184-r3j-room-cache-2048`
- Rejected 4,096-entry candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d183-r3j-room-cache-4096`
- Rejected 8,192-entry candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d181-r3j-room-cache-8192`
- Rejected 32,768-entry candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d182-r3j-room-cache-32768`
- Accepted production ELF SHA-256:
  `9bff489308aad3c77aef6ef9248e0370a544fbff52ba149f5c754dda287e1a72`

## Acceptance boundary

This is a bounded target-memory trade, not the final unique-room-vertex design.
It improves the current camera without changing the authored scene. A proper
cluster-local preparation path may recover more of the remaining 24,485 misses
with less scratch than a whole-room transformed array. The result remains about
8.9 Flycast frames per second and has no physical Dreamcast timing.
