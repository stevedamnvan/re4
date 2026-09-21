# R4a texture inventory checkpoint

Date: 2026-09-20

Historical D258 measurements below are retained. See the D319 addendum for the
current encoded-file/runtime distinction and corrected VQ byte accounting.

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

## D319: existing VQ candidate stays compressed in native VRAM

Inspected 9369db2, asset_residency_report.py, vq_export.py and the retained
C:/Flycast-Evidence/re4-dreamcast/d258-r4-texture-inventory evidence before this
change. No inventory/encoder campaign was repeated. The inventory's PAL4/PAL8
rows and 832-entry palette budget are proposals: no native PAL package/upload/
sampling support is accepted. Ten actual pvrtex DcTx files remain at /root/vqtest.

The selectable candidate uses existing ROOM_MATERIAL_001.dt (SHA-256
7a38f3d8aed2cf9e20c1794dfb4b5cf07d87171dc790587f63f3cbb1917d1675), matched offline
to source image key 9544fbb0-cb9b3876. vq_export.py --pack-existing FILE --package
FILE wraps it without decoding/re-encoding, using the pinned KOS pvrtex DcTx
header definition (804b3195ebd1a06a27cc2b3a5eacf7a2429040a3). It is not DTEX.
Only this fresh fixture's matching .re4tex was replaced; the uncompressed
D318d fixture and original encoder files remain intact.

Shared Package::adopt/upload/release_payload/close, storage::read_file/Arena,
and the existing fenced UI/model cache are reused. Validation now accepts full
256-entry VQ codebooks with compact block indices and rejects unknown layouts.
The shared pvr_format helper supplies VQ sampling flags in room, actor, HUD,
source UI and source-model headers. Runtime formats are RGB565/ARGB1555/ARGB4444
in linear, twiddled or full-codebook VQ layouts. Palette formats, mipmaps and
partial codebooks remain unsupported; there is no runtime expansion to 16-bit.

Flycast D319 evidence: C:/Flycast-Evidence/re4-dreamcast/d319-existing-vq.
The recovered commonModelTrans material request selects the candidate naturally.
It logs 18432 payload bytes at a441b1c0, format48000000 and readback FNV1a
c804e363, matching the existing encoded payload. The actual pvr_mem_available
change is18464 bytes:18432 payload plus32 allocator overhead. Versus131072
uncompressed payload bytes, the payload saving is112640 (85.94%). The18592-byte
source-heap upload allocation is freed;144 metadata bytes remain. Source heap
returns to344416. This is not source-archive recovery (zero bytes reclaimed).

Historical D258 VQ table sizes included each32-byte DcTx file header. For example,
18464 is the encoded file size, not texture payload; the six restoration payloads
total167936 rather than168128 bytes. D319's identical18464-byte allocator delta
has a different cause:32 bytes of VRAM allocator overhead, not an uploaded header.

ELF SHA-256:227f84dce2b24eb11717ddfad695cbd3e54ef1f27d13e06c17bb36f71a491ece.
Disc SHA-256:be6508adc23286d6d91dbf1ad293618cc3f6be578422c5ccbad974ff33ee6995.
The validated evidence manifest pins assets, fixture, dirty source/new files,
KOS, compiler, emulator and capture tools. Source title/menu is still visible.
Snapshot has three processed parts/1344 input triangles, zero emitted triangles,
four material/resource rejections, and the same scheduler frontier. The65-second
harness ends at its deadline. No visible VQ world sampling, moving-scene quality,
frame-time improvement, manual room gameplay or physical hardware is accepted.
Both block/enemy allocations still fail at the D316 heap values.

Keep shared format support and the selectable diagnostic; do not promote001's
quality loss (-3.40dB in D258) over the full-resolution uncompressed reference.
Five native UI/texture tests include byte-preserving VQ wrapping, exact raw upload
allocation, no linear expansion, backing reuse and unsupported-layout rejection;
15 converter tests pass. The native model sanitizer fixture passes, both game
and existing room translation units compile, and trans.cpp PPC tokens are
unchanged. Remaining source archive memory work now targets verified upload-only
texels with offline identities; VQ savings do not replace that work.
