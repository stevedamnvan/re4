# R3r per-strip culling and projection-bias fix checkpoint

Date: 2026-09-20

Decision: **accept both changes.** R3r adds order-safe per-strip bounds culling
to the room path and corrects a projection error that made every frustum test in
the port too tight. Against R3p over matched simulation ticks 165-1194, CPU frame
p50 falls from 86.217 ms to 74.139 ms while the frame draws *more* room geometry
than R3p did.

## The projection defect

`group_visible()` has computed the projected half-extents as
`far_depth * tan(fovy/2)` since R3a. That is wrong for this pipeline. KOS
`mat_perspective()` builds its frustum matrix with `M[2][3] = -1` and
`M[3][3] = 1`, so a view-space point ends up with `w = 1 - z_view`. With the
right-handed `mat_lookat()` basis that is `w = depth + 1`, and
`mat_trans_single()` divides the screen coordinates by that `w`. The visible
view-space extents at depth `d` are therefore

    |x| <= (4/3) * (d + 1) * tan(fovy/2)
    |y| <=         (d + 1) * tan(fovy/2)

Dropping the `+ 1` makes the test tighter than the renderer, and the error grows
as geometry approaches the camera: at 2.5 m it rejects geometry 39% inside the
true frustum. The fix is one constant, `kProjectionDepthBias`, applied in both
`group_visible()` and the new `primitive_visible()`.

This was found by auditing the first R3r build, not by inspection. That build
looked like a 17.5 ms win but silently dropped part of a foreground object.

## Per-strip bounds culling

`submit_room_strips()` previously touched every vertex of every strip in a
visible batch. The depth test and the near-plane clipper then discarded the work
after `cached_room_vertex()` had already transformed and lit it. R3q measured the
consequence on the blended list: 18.917 ms to draw 1,718 triangles.

R3r computes one bounding sphere per native strip at load time, from the strip's
own vertices, into a fixed 16,384-entry table, and rejects the strip before any
vertex work. The test is the same conservative view-space support test
`group_visible()` uses, so the near and lateral planes are evaluated once per
strip rather than once per vertex.

Rejecting a strip removes work without reordering any triangle that is still
drawn, so the R3c source blend-order certificate continues to hold by
construction. Partitioning the alpha materials into finer cells, the other
obvious option, would reorder across cell boundaries and would need a new order
argument.

The table costs exactly 262,144 bytes of static main RAM. No package format,
converter output, geometry, texture, light, camera, or cull setting changed.

## Culling safety

A gated `CULL_AUDIT=1` build projects every rejected strip anyway and reports
what was lost. A strip is only safe to reject when every vertex is in front of
the near plane and the projected bounding box misses the 640x480 screen; testing
vertices alone is not enough, because one large triangle can cover pixels with
all of its vertices outside.

| Audit over matched ticks | Before the bias fix | After |
|---|---:|---:|
| strips culled per frame | 1,928 | 1,634 |
| culled strips with an on-screen vertex | 199 | 0 |
| worst horizontal overshoot of the tested half-width | 1.394x | none |
| worst vertical overshoot | 1.038x | none |

Both overshoot figures are exactly `(depth + 1) / depth` at the depth of the
offending strip, which is what identified the defect.

A second audit over 2,761 samples spanning ticks 0-5920 found **zero** rejected
strips whose projected bounding box touches the screen. Between 54 and 66 strips
per frame straddle the near plane and cannot be checked by projection at all;
those rest on the geometric argument that a sphere lying entirely outside one
conservative view-space slab cannot intersect the frustum.

## Matched Flycast result

Simulation ticks 165-1194, same autoplay route, pinned build and configuration.

| p50 unless stated | R3p | R3r strips only | R3r accepted |
|---|---:|---:|---:|
| CPU frame | 86.217 ms | 71.400 ms | **74.139 ms** |
| CPU frame p95 | 88.719 ms | 71.505 ms | 74.238 ms |
| CPU frame p99 | 88.814 ms | 73.940 ms | 76.701 ms |
| `submit_us` | 58.103 ms | 43.289 ms | 45.901 ms |
| opaque room | 26.687 ms | 26.663 ms | 29.244 ms |
| punch-through plus blended room | 17.820 ms | 3.023 ms | 3.053 ms |
| visible groups | 327 | 327 | 362 |
| room triangles | 9,155 | 7,524 | 8,208 |
| transformed and lit vertices | 15,350 | 9,355 | 10,156 |
| room index references | 20,178 | 13,850 | 15,050 |
| immediate PVR calls | 617 | 616 | 681 |
| submitted bytes | 1,071,840 | 962,560 | 1,002,656 |
| free main RAM | 5,570,560 B | 5,308,416 B | 5,308,416 B |

The middle column is strip culling with the corrected test but the old group
test. The accepted column adds the same correction to `group_visible()`, which
restores 35 groups and 684 triangles per frame that R3p was discarding, and costs
2.739 ms. The net result is 12.078 ms faster than R3p at p50 and 14.481 ms faster
at p95 while drawing more of the room.

Accepted stage medians:

| Stage | p50 |
|---|---:|
| opaque room transform/light/clip/submit | 29.244 ms |
| actor lighting | 18.198 ms |
| opaque actor draw | 11.789 ms |
| actor pose palettes/projection | 5.820 ms |
| punch-through plus blended room | 3.053 ms |
| room visibility and light selection | 2.089 ms |
| actor normals | 1.831 ms |
| translucent actors and HUD | 1.760 ms |

Zero simulation overruns and zero discarded simulation time. The presented rate
is roughly 13 to 14 frames per second; a 33.33 ms CPU frame still needs another
40.8 ms at p50.

## Visual result

Framebuffers were extracted from emulated VRAM with `rend.EmulateFramebuffer`
enabled, at matched simulation ticks, against the R3p reference in
`d226-r3p-visual-reference`.

- Strip culling alone is **byte-identical to R3p** at ticks 250, 450 and 700.
- The accepted build, which also restores the wrongly culled groups, is identical
  at tick 250, differs by 361 pixels at tick 450 and by 20 pixels at tick 700.
  Every difference is one least-significant channel step from an additional blend
  layer, except at tick 700 where the changed pixels form a three-pixel column at
  the extreme left edge, which is where the old test was clipping.

The first R3r build, before the bias fix, differed from R3p by 139 pixels in a
54x32 region at both ticks 450 and 700: a piece of a foreground object was
missing. That is the regression the audit then explained.

## Retained evidence

- `d225-r3r-strip-cull` — first candidate, superseded, ELF
  `b7b5915c0e7e7afdb45df4d1a879009e87f8446df05bcc3709d113b7dea6cb65`
- `d226-r3p-visual-reference` — R3p framebuffers
- `d227-r3r-visual-candidate` — the missing-geometry regression
- `d228-r3r-nofar-visual` — far-plane rejection removed; ruled that out as the cause
- `d229-r3r-cull-audit` — `telemetry-ratios.jsonl` before the fix,
  `telemetry-fixed.jsonl` after, `telemetry-bbox.jsonl` for the bounding-box audit
- `d230-r3r-strip-cull-fixed` — strips-only timing, ELF
  `7473c9f89aa4112800f16a038b8182078f1a732faaa8cbc9037d6ced01292f10`
- `d231-r3r-fixed-visual` — strips-only framebuffers
- `d232-r3r-group-bias-fix` — accepted timing
- `d233-r3r-group-fix-visual` — accepted framebuffers
- `d234-r3r-manual-smoke` — manual build smoke

Accepted autoplay ELF SHA-256
`f3975be3408b2059d9c9557753d16a736d359a21d2d911e47a0d09a397bef35d`.
Accepted manual ELF SHA-256
`7137228e6287394cbec9e12c67438bd06282a19d5410f5dd76346bba50c9859c`.
The manual ROM-disk staging contained no autoplay flag. The manual smoke reached
simulation tick 2,160, sampled input 7,196 times with a 12.485 ms maximum gap,
and reported zero queue drops, simulation overruns or discarded simulation time.
Post-load free main RAM was 5,308,416 bytes in both builds.

## Limits

These are Flycast measurements of the autoplay route. The pixel comparison covers
three matched ticks whose camera is nearly static; the two runs could not be
aligned to an identical tick inside the moving segment, so the moving-camera
guarantee rests on the bounding-box audit rather than on pixels. The audit itself
cannot verify near-plane-straddling strips. Free movement, aim extremes, enemy
contact, Leon death, human control and physical Dreamcast timing all remain
open, and the corrected group test has only been exercised on this route: other
cameras may reveal more geometry that R3p was discarding.
