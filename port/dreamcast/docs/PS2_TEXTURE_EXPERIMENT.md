# Isolated PS2 texture candidate: r101 vertical planks

2026-09-21. Experimental branch `experiment/ps2-asset`, base `70eb085`.
This is one private conversion experiment under R4_ASSET_RESIDENCY_PLAN.md,
not a source-loader replacement or a completed gameplay/performance milestone.
The main checkout and qualified `.dar` loading are unchanged.

## Result and decision

A concrete, selectable full native `.re4tex` package was built with one PS2
texture substituted. GameCube geometry, UVs, materials and every other texture
remain unchanged. Keep the GameCube default. The candidate has **not** been
promoted: no moving-scene, target loading-peak, timing or hardware result yet.
The isolated extraction/conversion experiment has useful output; do not claim
its 32 KiB payload reduction solves the recovered game's memory frontier.

| Measurement | GameCube reference | PS2 candidate |
|---|---:|---:|
| Selected texture | image 26, 128x256 | image 29, 128x128 |
| Selected native RGB565 twiddled payload | 65,536 bytes | 32,768 bytes |
| Full native texture payload | 2,981,888 bytes | 2,949,120 bytes |
| Full package | 2,990,672 bytes | 2,957,904 bytes |

Only `ROOM_MATERIAL_014` differs; 90 other material descriptors (apart from
payload relocation) and payloads compare equal. The 32,768-byte payload delta
is the predicted unique texture VRAM allocation saving, **not measured target
free memory**. Disc bytes and transient CPU bytes also decrease by that amount;
resident CPU or loading-peak savings depend on the existing ownership path.
This is 50% for that texture, approximately 1.1% for the whole texture pack.

The generated GC package is byte-identical to the existing
`port/dreamcast/build/private/r101-source.re4tex` (256 maximum dimension):
`062561db2d9daa432ac23bbde96123d264a64ac7b8abcbb386445ecb04f4d858`.
PS2 candidate SHA256:
`e1ca5ea9381c5c15c0a97d5a9da23472e08109abcdebb2464e56ce2535081de7`.

## Source identity and scope

Supplied disc: `C:\Game Dev\Emulators\re4_helpers\Resident Evil 4 (USA)\Resident Evil 4 (USA).iso`,
4,435,836,928 bytes. ISO9660 SYSTEM.CNF names `SLUS_211.34`, BOOT2, VER1.01,
VMODE NTSC. This proves PS2 executable identity; it is not a full-disc hash.
BIO4DAT.AFS entry 2301 `r101.dat`: 4,793,024 bytes,
SHA256 `9775f65af2fa8a4afb257975838db4bb7976cffa46b76f3cb58b3b2f9643e809`.
Scenario tag4 SMD embedded TPL0, image29 is the candidate.
GC scenario SMD tag4 embedded TPL image26 is the retained reference.

Contact sheets and a normalized side-by-side comparison show the corresponding
vertical-plank artwork and orientation; PS2 loses vertical detail. This is an
explicit perceptual candidate, not a lossless optimization. No assumption was
made that same-numbered PS2/GC images correspond. Scene UV/contact compatibility
and moving quality are pending. Collision, player, motion, lights, scripts,
source progression and events are never substituted.

## Pinned tools and licenses

External clones remain private under `/root/probe/ps2-asset-experiment`:

- JADERLINK/JADERLINK_DATUDAS_TOOL `4480c91e154719a2efed5d11658aa5bedd065e00`, MIT.
- JADERLINK/RE4-PS2-TPL-TOOL `b9bff8da2296d51a669284836de6bc96a93fc524`, MIT;
  bundled TGASharpLib MIT notice retained.
- JADERLINK/RE4-PS2-SCENARIO-SMD-TOOL `39fd0f2150b229637f36cfb2d3a8bccfa7f66e75`, MIT,
  consulted for embedded TPL offsets. Full Mono compilation failed on tuple
  compiler incompatibilities; no geometry/tool rewrite was undertaken.
- Ubuntu python3-pycdlib reads ISO9660; Mono compiles unmodified DAT/TPL tools;
  Pillow reads PNG output. No upstream code/assets are vendored here.

TPL extraction used PNG, flipY=false, rotate=false. The older TPL tool writes
Windows backslashes literally under Mono; private normalize.py moves those
outputs into their intended folders. No image transforms occur in that step.

## Reproduce/select

Private working root: `/root/probe/ps2-asset-experiment`.
Windows evidence: `C:\Flycast-Evidence\re4-dreamcast\ps2-asset-experiment`.
`extract_one.py`, `make_selection.py`, upstream clones, extraction logs and
`selection.json` retain exact input identities. The selection file validates
GC TPL/MTL and PS2 PNG hashes and the complete affected material-name list.

From the isolated worktree (choose new output filenames):

```sh
python3 port/dreamcast/tools/texture_candidate.py \
 /root/probe/ps2-asset-experiment/selection.json /root/probe/ps2-asset-experiment/reference-new.re4tex
python3 port/dreamcast/tools/texture_candidate.py \
 /root/probe/ps2-asset-experiment/selection.json /root/probe/ps2-asset-experiment/candidate-new.re4tex --variant ps2
python3 -m unittest discover -s port/dreamcast/tests -p test_texture_candidate.py
python3 -m unittest discover -s port/dreamcast/tests -p test_convert_tpl.py
```

The adapter calls existing `convert_tpl.build_package()`; it adds no runtime
format or loading mechanism. PNG pixels are bridged losslessly into the existing
RGBA8 input API, covered by a rectangular colored/alpha fixture. It refuses
unsupported dimensions instead of resizing and defaults to GC. The candidate
must remain opaque in this bounded experiment. The existing reference cap256
is retained for other assets; no extra candidate downscale/filter change occurs.
14 focused tests pass. Private verify.py checks both CRCs and all 91 material
records/payloads. These checks are structural, not runtime presentation evidence.

## Next bounded evaluation

Use the existing native room resource selection to substitute only
`TEXTURE_PACKAGE=/root/probe/ps2-asset-experiment/ps2.re4tex`, with a GC control
using gc.re4tex. Reuse the r101 fixture's existing source camera and jump point;
find views that actually expose ROOM_MATERIAL_014. Do not modify the main
recovered game while its source integration proceeds, and do not run a competing
Flycast process during its captures. Pair exact simulation snapshots plus moving
near/far/oblique views at640x480. Measure upload/transition peak and largest free
VRAM block, source/batch counts and presented-frame distribution. Keep source
sampler, alpha, lighting, camera and geometry identical.

Promotion need not wait for three rooms or30FPS. Promote only if representative
playability is blocked by measured asset cost and this candidate improves that
budget with acceptable observed appearance/compatibility. r120 cinematic pool
exhaustion alone does not qualify this r101 texture. A 32KiB saving may be too
small to matter; retain that negative result if so. No new streamer, source
system bypass, blanket PS2 replacement or broader extraction is authorized by
this bounded result.
