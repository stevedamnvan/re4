# R4b: native texture layout (offline twiddling)

Status: kept. R4 deliverable 2's first half. Texture payloads are now written in
the PVR's twiddled order at build time and copied raw into texture memory, so
the SH-4 no longer reorders 2.6 MB of texels during load.

Result: texture upload falls from 1,022,663 us to 16,945 us, a 60.4x reduction
and 1.006 s off the load. Per-frame cost, VRAM, main RAM and the rendered
framebuffers are unchanged.

## What changed

The `re4tex` format gained a per-texture payload field, so the runtime can be
told how a payload is laid out instead of assuming one layout:

| | v1 | v2 |
|---|---|---|
| texture record | `<64s6I`, 88 B | `<64s8I`, 96 B (`payload`, `reserved_0`) |
| payload order | linear, always | linear, twiddled (VQ reserved) |
| upload | `pvr_txr_load_ex(..., PVR_TXRLOAD_16BPP)` reorders every texel | raw `pvr_txr_load()` for non-linear payloads |

`tools/convert_tpl.py` grew `twiddle_16bpp()` and a `--twiddle` flag;
`tools/convert_core_hud.py` and `tools/convert_character.py` gained the same
option. The Makefile recipes turn it on by default for the r100 room, both
characters and the HUD. `room/texture_package.cpp` branches on the payload
field and keeps the old reordering path for `kPayloadLinear`, so a linear
package still loads.

`twiddle_16bpp()` was checked against a transcription of KOS's own
`TWIDOUT(x & mask, y & mask) + (x / min + y / min) * min * min` for every shape
from 8x8 to 256x512 before any of this was built.

## Why the first attempt did not boot

The first twiddled build reached the telemetry block and then stopped before
frame 0. The cause was not the format: `port/dreamcast/room/Makefile` had no
header dependency tracking, so widening the `Texture` record in
`texture_package.hpp` recompiled `texture_package.cpp` but left `main.o`
reading 88-byte records out of a 96-byte array. The fix is `-MMD -MP` with
`-include $(OBJS:.o=.d)`, and `clean` now removes the `.d` files. This was a
latent hazard for every package header in the tree, not only this one.

## Measurements

Flycast, 640x480, r100 autoplay, matched window (simulation ticks 165-1194).
All three builds captured in one session, with an all-linear build of the same
source and the same timer as the control. The control's p50 frame time is
61,229 us, which is the R3x figure recorded in `REALTIME_PATH.md` to the
microsecond, so this run is directly comparable to the accepted baseline and
R4b introduces no frame regression against it.

| | all-linear control | room+characters twiddled | all twiddled |
|---|---:|---:|---:|
| texture upload (us) | 1,022,663 | 91,240 | 16,945 |
| frame_us p50 | 61,229 | 61,221 | 61,221 |
| frame_us p95 | 61,292 | 61,295 | 61,290 |
| opaque_actor_us p50 | 11,789 | 11,789 | 11,789 |
| PVR free after textures (B) | 1,521,128 | 1,521,128 | 1,521,128 |
| main RAM free (B) | 5,357,568 | 5,357,568 | 5,357,568 |
| heap used (B) | 135,004 | 135,004 | 135,004 |

The 8 us spread in p50 is run-to-run noise: a later bracketed pair of repeat
runs put the baseline at 61,220 and 61,223 us, so the noise floor here is a few
microseconds and no per-frame effect is claimed either way. Report p50 rather
than the window mean when comparing with the recorded budget table, because the
mean includes the early part of the window and reads several milliseconds low.

Upload time is measured by a new `texture_upload_us` field that reuses the spare
`room_reserved_0` slot, so the telemetry layout and its 376-byte size are
unchanged and existing readers keep working.

The HUD is worth its own line: leaving it linear cost 74,295 us on its own,
more than four times the fully twiddled total, because its 25 padded textures
were still being reordered a texel at a time.

Memory is unchanged by construction. Twiddling permutes a payload; it does not
resize it. Package sizes are byte-for-byte the same as the linear packages, and
VRAM after upload is identical to the byte.

## Correctness

Framebuffers captured at simulation ticks 250, 450 and 700, both buffers:

- 6 of 6 byte-identical to the all-linear control.
- 5 of 6 byte-identical to the accepted `d256-r3x-visual` baseline. The sixth,
  tick 250 buffer 1, differs in both the twiddled build and the linear control
  by the same amount, so it is a back-buffer capture-phase artefact of that one
  sample and not a property of the change.

Host tests pass with zero failures. Package hashes reproduce: the r100 texture
package is `eb20a17f...`, Leon `574b0514...`, Ganado `6f8ded54...`, the HUD
textures `e08669f9...`, and the HUD layout is unchanged at `c46d0151...`,
confirming only the texture payload order moved.

## Evidence

- `d261-r4b-twiddled-fixed` — timing and upload measurements, all three builds.
- `d262-r4b-twiddled-visual` — framebuffer captures for the twiddled build and
  the linear control.

## What this leaves open

The `kPayloadVq` value is defined and rejected by the converter, not produced.
The second half of deliverable 2 is the six textures the R4a inventory found:
restoring them to their authored resolution under vector quantisation for
46% less VRAM and 5.7 to 7.3 dB more PSNR. That needs codebook plus index
payloads from `pvrtex`, `PVR_TXRFMT_VQ_ENABLE` in the poly headers, and the
small-codebook address bias DCA3 uses. Nothing in R4b blocks it.

Palette payloads (PAL4/PAL8) are still unexpressed and need the PVR's shared
1024-entry palette RAM budgeted across packages, which the inventory tool
already models but the format does not carry.
