# R4a texture inventory checkpoint

Date: 2026-09-20

Decision: **the inventory tool is accepted and its first finding is recorded.
No package or runtime change is made yet.** R4 deliverable 1 exists as
`tools/asset_residency_report.py`, the accepted r100 texture package now has a
tracked recipe that reproduces it byte for byte, and a measured comparison
answers the question the R4 plan opened with. The conversion itself is
deliverable 2 and is not done here.

## The texture package had no recipe

The accepted build consumes `build/private/r100-entry-source.re4tex`, but
`Makefile.host` had a rule only for the r10d fixture. The r100 package had been
produced by an untracked invocation, so the asset that every timing result in
R3 was measured against could not be rebuilt from the repository. A
`texture-r100-production` target now reproduces it exactly:

    make -C port/dreamcast -f Makefile.host texture-r100-production

SHA-256 `4b66255f8357c87b8dfb9573c3eaa6bea9177558fa946382b3ac84223020f8eb`,
1,983,080 bytes, identical to the package the accepted ELFs were built with.
The recipe records the `--max-dimension 256` limit that had been applied, which
is a source-asset reduction and is treated as one below.

## What the tool reports

`asset_residency_report.py` reads the private GameCube TPL and MTL through the
same decoders `convert_tpl.py` uses for the build, and the built Dreamcast
package through its own header, so the GameCube and current columns are the
real assets. For each material it measures the decoded content at the
resolution each candidate would store, and prices every candidate exactly:

| Candidate | VRAM |
|---|---|
| twiddled 16-bit | `w * h * 2` |
| vector quantised | `2048 + w * h / 4` |
| PAL8 | `w * h`, plus a 256-entry palette bank |
| PAL4 | `w * h / 2`, plus a 16-entry palette bank |

Two corrections during development are worth recording because a naive version
of this tool gets both wrong. Colour counts must be measured on the pixels a
candidate actually stores, not on the full-resolution source, or a texture the
build reduced is judged on colours it will never hold. And the PVR has 1,024
palette entries in total, so palette decisions are only valid while the
simultaneously resident set fits; the first run proposed 1,344 entries. The
tool now assigns palette banks by bytes saved per entry consumed and demotes
the rest, which brings r100 to 832 of 1,024 entries.

The PS2 column is structural. No PS2 RE4 disc is present in this workspace, so
every row reads "no PS2 source" and the oracle half of the R4 plan is blocked
on obtaining one. The tool takes `--ps2-manifest` and will fill the column
without further changes.

## First finding: the reduction we shipped costs more VRAM than the source

Six of the 53 r100 materials were reduced by the 256-pixel limit. For each,
restoring the authored resolution under vector quantisation is better on both
axes at once. Measured with `pvrtex` (full codebook, `AUTO` format) against the
decoded GameCube source, with the shipped representation measured the same way
(box reduction, then the 16-bit quantisation the runtime uploads):

| Material | GameCube | ships now | PSNR now | full-res VQ | PSNR VQ | gain |
|---|---|---:|---:|---:|---:|---:|
| ROOM_MATERIAL_011 | 256x512 | 65,536 B | 24.76 dB | 34,848 B | 30.56 dB | +5.80 |
| ROOM_MATERIAL_013 | 128x512 | 32,768 B | 21.39 dB | 18,464 B | 28.66 dB | +7.27 |
| ROOM_MATERIAL_019 | 256x512 | 65,536 B | 22.67 dB | 34,848 B | 28.35 dB | +5.68 |
| ROOM_MATERIAL_034 | 512x64 | 16,384 B | 23.98 dB | 10,272 B | 29.87 dB | +5.89 |
| ROOM_MATERIAL_038 | 256x512 | 65,536 B | 22.73 dB | 34,848 B | 29.34 dB | +6.61 |
| ROOM_MATERIAL_039 | 256x512 | 65,536 B | 22.01 dB | 34,848 B | 29.18 dB | +7.17 |

311,296 bytes become 168,128 bytes, a 46% reduction, while every one of the six
regains its authored resolution. `material-019-comparison.png` in the evidence
directory shows the three representations side by side at 1:1.

## Second finding: vector quantisation is not a default

The same measurement on textures the build did **not** reduce goes the other
way, because there is no resolution loss to recover and VQ is pure loss:

| Material | GameCube | ships now | PSNR now | VQ | PSNR VQ | change |
|---|---|---:|---:|---:|---:|---:|
| ROOM_MATERIAL_001 | 256x256 | 131,072 B | 40.91 dB | 18,464 B | 37.51 dB | -3.40 |
| ROOM_MATERIAL_029 | 128x128 | 32,768 B | 38.78 dB | 6,176 B | 38.25 dB | -0.53 |
| ROOM_MATERIAL_012 | 256x256 | 131,072 B | 43.28 dB | 18,464 B | 29.82 dB | -13.46 |
| ROOM_MATERIAL_040 | 256x256 | 131,072 B | 41.82 dB | 18,464 B | 29.34 dB | -12.48 |

The split is unanimous and follows exactly one property: whether the build
reduced the texture. The decision rule in the tool encodes that. Restoring a
reduced texture under VQ is taken by default because it has no trade-off;
quantising an unreduced texture is offered only under `--spend-vq`, for the
case where a residency budget requires the VRAM, and still needs a
moving-scene review before acceptance.

This corrects the expectation the R4 plan was written with. "Dreamcast VQ may
allow us to retain the higher-resolution GameCube artwork for less VRAM" is
confirmed, and confirmed strongly. "VQ everything to fit the budget" is not
supported: it would cost 12 to 13 dB on the room's large unreduced textures.

## Current r100 texture budget

| Plan | Texture VRAM | Fidelity |
|---|---:|---|
| GameCube at 16 bpp, no compression | 2,912,256 B | authored |
| current accepted package | 1,978,368 B | six textures halved |
| default candidate plan | 1,732,608 B | **six textures restored**, nine palettised losslessly |
| every texture at GameCube size under VQ | 472,576 B | floor for residency planning, costs quality on unreduced textures |

The default plan is smaller and better than what ships. The floor matters only
when several rooms must be resident at once, which is deliverable 4.

## Retained evidence

`d258-r4-texture-inventory`:

- `r100-residency.json` — the full per-material record
- `vq-quality.json` — the PSNR measurements above
- `previews/` — the GameCube, shipped and VQ images for the ten measured
  materials
- `material-019-comparison.png` — the three-way visual

## Limits

PSNR is a proxy. The six restorations are supported by both PSNR and a visual
comparison, but they have not been seen in a moving scene on the target, and no
package or runtime change has been made yet, so no frame or load measurement
exists for them. The runtime still twiddles on upload through
`pvr_txr_load_ex()`; moving that offline is part of deliverable 2, and the
Dreamcast VQ path needs the texture header to carry the format, which the
current `re4tex` header does not. The PS2 oracle is unavailable. Nothing here
has been measured on physical hardware.
