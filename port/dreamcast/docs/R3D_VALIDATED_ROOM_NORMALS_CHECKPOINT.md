# r100 R3d validated room-normal checkpoint

Recorded 2026-09-20 after the native opaque and ordered-alpha strip passes.
The room package's authored normals are already unit length, but the dynamic
camera-relative lighting path normalized every cache miss again. The runtime
now validates that invariant once when the room loads and skips the repeated
square root and divides only when every room normal passes.

## Validation

The accepted package has 40,419 room vertices. Their source normal lengths are
between 0.9999998755 and 1.0000001336; none are zero and none differs from one
by more than `1.34e-7`. The runtime uses a wider `1e-5` squared-length gate,
rejects non-finite values, and retains the previous normalization path if any
vertex fails.

A separate verification ELF evaluated both paths for every visible room cache
miss across 33 frames, packed both results through the final 8-bit color
conversion, and reported zero color mismatches. That comparison code is not in
the production path. An analogous actor experiment found up to two packed
color differences per frame, so actor lighting keeps its second normalization
until source-authored normal skinning replaces the interim rebuilt-normal path.

## Matched Flycast result

Medians cover simulation ticks 220 through 474.

| Measure | Repeated normalization | Validated unit room normals | Change |
|---|---:|---:|---:|
| Outer frame work | 153.157 ms | 152.774 ms | -0.383 ms |
| Total render work | 152.773 ms | 152.390 ms | -0.383 ms |
| Opaque room pass | 59.643 ms | 59.243 ms | -0.400 ms |
| Translucent room pass | 36.204 ms | 35.965 ms | -0.239 ms |

This is a small emulator result and should not be extrapolated. It preserves
the same room transforms, light selections, evaluations, geometry, and packed
room colors.

Evidence:

- Baseline:
  `C:\Flycast-Evidence\re4-dreamcast\d154-r3c-ordered-alpha-strips-autoplay`
- Production candidate:
  `C:\Flycast-Evidence\re4-dreamcast\d160-r3d-validated-unit-room-normals-autoplay`
- Packed room-color verification:
  `C:\Flycast-Evidence\re4-dreamcast\d159-r3d-unit-room-packed-color-verify`
- Rejected actor-normal verification:
  `C:\Flycast-Evidence\re4-dreamcast\d158-r3d-unit-normal-packed-color-verify`
- Production ELF SHA-256:
  `49b8aea4e3382ae823c2906cfcc1b53c49390f07c8422e390a64cf6f1e3ef4b0`

## Acceptance boundary

This establishes a guarded invariant and a small CPU saving. It does not
establish source-authored actor normal skinning, 30 fps, stock Dreamcast timing,
or physical-hardware output.
