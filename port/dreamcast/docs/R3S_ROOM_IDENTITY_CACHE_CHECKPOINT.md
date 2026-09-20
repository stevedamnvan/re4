# R3s room identity-cache checkpoint

Date: 2026-09-20

Decision: **rejected and removed.** Keying the room vertex cache on vertex
identity removed 21.5% of the per-frame transform and lighting evaluations and
made the frame slower. No R3s code remains; the tree rebuilds the accepted R3r
autoplay ELF `f3975be3408b2059d9c9557753d16a736d359a21d2d911e47a0d09a397bef35d`
byte for byte.

## Candidate

R3q found that across the accepted package only 61.1% of the 40,419 room
vertices have distinct positions and 82.4% have distinct position-and-normal
pairs. R3s computed, at load, one identity per distinct (position, authored
normal, prepared static-light term) triple — vertices with the same identity
produce bit-identical transform and lighting output — and keyed the 2,048-entry
per-frame cache on that identity instead of the vertex index. Texture
coordinates, the one attribute that can differ, were restored from the source
vertex when the entry had been filled by a different vertex. The identity map
cost 81,920 bytes of static main RAM plus a transient 512 KiB hash table at load.

The load-time count was 33,303 identities for 40,419 vertices, exactly the
offline prediction.

## Matched Flycast result

Simulation ticks 165-1194 against the accepted R3r build.

| p50 | R3r | R3s, two copies per reference | R3s, one copy per reference |
|---|---:|---:|---:|
| CPU frame | 74.139 ms | 75.588 ms | 75.413 ms |
| CPU frame p95 | 74.238 ms | 75.731 ms | 75.526 ms |
| opaque room pass | 29.244 ms | 30.587 ms | 30.404 ms |
| room index references | 15,050 | 15,050 | 15,050 |
| room cache misses (transform + light) | 10,156 | 7,977 | 7,977 |
| room cache hits | 4,894 | 7,073 | 7,073 |
| free main RAM | 5,308,416 B | 5,222,400 B | 5,214,208 B |

The reuse was real and the short-window cache captured it: misses fell by 2,179
per frame. The frame still lost 1.274 ms. The first build paid two 52-byte
`RenderVertex` copies per reference because the helper returned by value into an
assignment; the second build removed that and skipped the texture-coordinate
patch when the entry had been filled by the same vertex, and it was still
1.274 ms slower than R3r.

## What this shows

Removing 2,179 transform-and-light evaluations per frame was worth less than the
cost of one identity lookup and one filled-by check per reference, over 15,050
references. Even attributing the entire per-reference overhead generously, the
cache-miss path costs well under 1 us in this cost model, not the 3.1 us that
R3q's attribution implied. That attribution divided the whole pass by its
transform count; it was not a measurement of the transform.

The opaque room pass is therefore dominated by work that scales with references
and emitted records — the strip gather copy into scratch, the packet write, the
colour pack, the per-vertex depth test, and the batch and group traversal — and
not by transform and lighting. Flycast does not model the SH-4 data cache, so
this conclusion is about instruction volume; it may differ on hardware, but it is
the only signal the current bench can give.

Identity reuse for the room is closed under this cost model. A full-size
identity table would recover at most the remaining 2,179 misses per frame and
would cost more memory for a smaller gain than the one measured here.

## Retained evidence

- `d235-r3s-identity-cache` — first build, ELF
  `fa0b0263b8edf489ddc33fb833947f7120d5ace4be548407a641546ab160e5f9`
- `d236-r3s-identity-cache-v2` — single-copy build, ELF
  `9d9996ce76a3322beef05c5d061e2c4ebd33f59d92dc9d1211386b6a5c1cd690`

Both traces report zero simulation overruns and zero discarded simulation time.
No visual comparison was needed because the candidate was rejected on timing.
