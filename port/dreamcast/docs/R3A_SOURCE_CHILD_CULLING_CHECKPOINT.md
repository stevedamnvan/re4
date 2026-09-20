# r100 R3a source-child culling checkpoint

Recorded 2026-09-20 on top of the source actor-strip checkpoint. This change
subdivides each recovered source room object into conservative 24 m X/Z child
bounds while retaining the parent SMX selection mask, cull mode, flags, and
model light volume on every child.

This is visibility structure, not geometric reduction. The accepted package
retains all 40,419 vertices and all 30,895 triangles. It expands 58 source
objects into 222 render groups and grows the embedded room package from
1,679,364 to 1,711,412 bytes.

## Alpha-order constraint

The first experiment partitioned every material. It was not accepted because
changing translucent batch order could change authored blending even when a
single inspected view looked correct.

The accepted converter takes an explicit unpartitioned-material list. The 14
materials classified as alpha by the current source texture package stay in
their original source-group and index order. Only opaque triangles enter the
child cells. This keeps the translucent room path's ordering and measured work
unchanged while allowing the opaque pass to reject smaller conservative bounds.

A zero-cell control rebuilt the previous room package byte for byte with
SHA-256
`f280a6248ce126cf86765147f154f09267d31b9e1da8a01462890acb127c25c9`.
That establishes that source metadata recovery, unit conversion, geometry, and
package serialization are unchanged when subdivision is disabled.

## Matched Flycast measurement

The comparison uses autoplay simulation ticks 213 through 480 at 640x480. All
values are medians.

| Measure | Source objects | 24 m source children | Change |
|---|---:|---:|---:|
| Total render work | 200.488 ms | 180.209 ms | -10.1% |
| Submission interval | 160.514 ms | 142.703 ms | -11.1% |
| Opaque room draw | 104.175 ms | 83.773 ms | -19.6% |
| Translucent room draw | 38.083 ms | 38.185 ms | unchanged |
| Room index references | 56,262 | 46,068 | -18.1% |
| Room cache misses / light evaluations | 28,959 | 25,417 | -12.2% |
| Emitted room triangles | 3,195 | 3,195 | unchanged |

Actor costs and submitted actor strips are unchanged. The embedded package
uses 32,768 more bytes of measured main-RAM headroom; VRAM and AICA headroom
are unchanged.

Private evidence:

- Baseline: `C:\Flycast-Evidence\re4-dreamcast\d139-r1d-source-actor-strips-autoplay`
- Accepted candidate: `C:\Flycast-Evidence\re4-dreamcast\d146-r3a-source-cell24-source-alpha-order-autoplay`
- Final manual build: `C:\Flycast-Evidence\re4-dreamcast\d147-r3a-final-manual`
- All-material diagnostic, rejected for alpha-order risk:
  `C:\Flycast-Evidence\re4-dreamcast\d140-r3-source-cell32-autoplay`

The accepted autoplay ELF SHA-256 is
`efbf6640ce5e3b7d8ee437c76bb90173f6745185525c592f255987a3c9eacbab`.
The final manual ELF SHA-256 is
`945b18834f8efc31f0dff85a94d49a2223254504667608756c003dc03fc73992`.
The inspected encounter view contains the same authored room surfaces, actors,
lighting, and HUD. This is not yet a matched-tick pixel certificate or a full
free-camera occlusion test.

## Acceptance boundary

This closes a target-side source-object subdivision experiment. It does not
claim that 24 m is optimal for every room, replace original model eligibility
or ordering-table traces, validate doors and windows across the whole room, or
establish physical Dreamcast timing. The full encounter remains well above the
30 fps budget; room drawing and per-frame actor preparation are still the
largest measured work packages.
