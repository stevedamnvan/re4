# PS2 complete-asset experiment: r101 stove

2026-09-21. **Not worthwhile for this object and diagnostic representation.**
A complete selectable PS2 mesh/UV/texture/authored-color candidate ran through
the existing native room renderer at 640x480. It removes 41 triangles and 25
resident vertex records, but adds more resident color/code bytes than it saves,
leaves VRAM unchanged, and regresses the measured fixed-state median by 0.510 ms.
Keep GameCube as the default; do not promote or merge this branch.

This is the existing **diagnostic native room runtime**, not recovered-game
boot-forward integration, PS2 source-game acceptance, or physical hardware.
The earlier [texture-only experiment](PS2_TEXTURE_EXPERIMENT.md) is preserved;
its 32 KiB texture saving is a different asset and is not included here.

## Isolation and exact inputs

Worktree `/root/work/re4-ps2-experiment`, branch `experiment/ps2-asset`, designated
base `70eb085`, preceding texture-only checkpoint `a6edcba`. Primary checkout,
shared extracted/mirror trees, active emulator configuration and main plans were
not modified. Private extraction, packages, scripts, build logs, ELF files and
metadata are in `/root/probe/ps2-asset-complete`. Host evidence is
`C:\Flycast-Evidence\re4-dreamcast\ps2-asset-complete`. Source and generated assets
are excluded from this commit. Captures were coordinated with the parent task.

- GC: supplied `Resident Evil 4 Debug (Disc 1).iso`, G4BE08 extraction,
  `r101_004.SMD`, SMD054 / SMX053 / BIN049, `ROOM_MATERIAL_066`, TPL image 76.
- PS2: supplied USA disc, SYSTEM.CNF `SLUS_211.34`, VER 1.01, NTSC;
  BIO4DAT.AFS entry 2301 `r101.dat`, tag 4 `r101_004.SMD`,
  SMD072 / SMX030 / BIN165, `ROOM_MATERIAL_055`, TPL image 96.
- PS2 r101.dat SHA256:
  `9775f65af2fa8a4afb257975838db4bb7976cffa46b76f3cb58b3b2f9643e809`.
- PS2 SMD SHA256:
  `dd6f07fc18d432b17376a110b15175287fc68ae6d5bc508daf318444bf17094b`.
- Every actual GC/PS2 OBJ, BIN, SMD, SMX, TPL, PNG and companion material/texture
  metadata input is SHA256-pinned in `oven-selection.json`; additional disc
  header and GC instance data are in `source-identities.json`. No full-disc hash
  is claimed. `oven-audit.json` records the selected BIN and OBJ hashes too.

Established upstream tools, with their MIT notices retained privately:

| Tool | Pinned identity |
|---|---|
| JADERLINK_DATUDAS_TOOL | `4480c91e154719a2efed5d11658aa5bedd065e00` |
| RE4-PS2-SCENARIO-SMD-TOOL | `39fd0f2150b229637f36cfb2d3a8bccfa7f66e75`, upstream release V1.3.0 |
| RE4-PS2-TPL-TOOL | `b9bff8da2296d51a669284836de6bc96a93fc524` |
| RE4-PS2-BIN-TOOL | `eb37fbddeb9f2e4703efaacc6296ca872e7e25de` (inspected, not the extraction path) |
| JADERLINK_MODEL_VIEWER | `ecd32acd1c62cf34ce4a6e958d8ea1ddafbd7dec` (PS2 loader/shaders inspected) |

The unmodified SMD release executable runs under Mono; the prior local Mono
compiler tuple failure was not a format blocker. Release ZIP SHA256
`4de7d4ed74ee0300b4d3914f4c424c8d0fc3258a10418836a7f4f419f7635a07`, executable
`9fc3d21b164b2e7930eab4ec7e2eb93752758b811314c3c194101cfd7e19b610`.
All exported BINs, `.idx_ps2_smd`, `.idx_ps2_scenario`, `.idxmaterial`, TPL and
per-image `.IdxtplHeader` files remain beside the OBJ. The viewer was used as
source-code corroboration, not claimed as a second rendered oracle.

## Correspondence and interpretation contract

The stove is identified by mesh, texture, exact original instance transform and
room placement, not filenames. Both instances use source position
(2238.3869629, 0, -17305.0839844), zero rotation and scale 0.9500000477 on all axes.
The selected GC placed BIN has no alternate colocated LOD in the inspected r101
export; this is not a campaign-wide LOD inventory.

The audit reads original PS2 signed 16-bit position/UV/RGB fields, unsigned alpha,
segment scale and strip restart markers, independently of the OBJ writer. All
193 raw records and 131 triangles agree with the exporter, including material,
primitive order and winding; largest printed-coordinate rounding error is
0.00001021 exported units. Source strip duplicates remain distinct. No invented
normals, position-only welding, recentering or vertex-color transfer occurs.

Position mapping is raw position times segment scale /100, then original
instance scale and position/100; the existing room scale 0.1 converts exported
coordinates to metres. The selected rotation is zero; the audit explicitly
refuses nonzero rotations rather than claiming a general transform decoder.
Axes and handedness are retained as exported. GC and PS2 bounds agree within
0.000000412 m. Vertex/centroid-to-triangle sampling measures maximum deviations
of 0.0731 m PS2-to-GC and 0.1979 m GC-to-PS2, consistent with removed detail; this is
not a continuous Hausdorff or collision-clearance proof. See `placement.json`.

GC SAT/EAT, anchors, camera blockers, activation metadata and event ownership
remain authoritative and byte-identical. PS2 status 0x09 includes the tool's
EXE-scripted bit, versus GC 0x08. This experiment uses its first-visit placed
geometry under GC ownership; later PS2 event behavior is **not qualified**.
Bounds/surface evidence does not accept every projectile/interaction boundary.
No physics shape or event record is replaced to hide a geometry difference.

The PS2 material's original 12 bytes are `0060ffffff000000000000ff`: plain diffuse
slot 96, no opacity/bump/specular slot. Its 128x128, 8-bit indexed, interlace 2 TPL
record has `GsTex:40000005DD408000`; retained output reports no extra mip level.
Pinned TPL extraction uses flipY=false and rotate=false. The decoded PNG is
opaque; every alpha value is 255. It passes through the existing RGBA8 adapter,
RGB565 encoder, twiddler, texture package validator and native upload path.
There is no PS2 layout uploaded directly to PVR and no additional downscale.

Raw vertex RGB/alpha normalization is /128, corroborated by the exporter and
viewer PS2 loader; RGB is per original record, with alpha 128 meaning 1.0. The
viewer shader multiplies texture, material color and vertex color, and bypasses
normal lighting for a color-only mesh. This is tool/runtime interpretation
support, not a trace of the original PS2 GS command stream. Original PS2 runtime
sampler/ambient changes outside the selected state have not been independently
recovered. The candidate explicitly retains the existing GC-target repeat,
bilinear, depth/cull and fog policies, rather than silently inventing PS2 state.

### Range-preserving target adaptation

The selected authored RGB maxima are (1.59375,1.4921875,1.2578125). Clamping them
at 1 or adding GC normal lighting would be wrong. For each channel, let `g` be
max(1, the maximum authored color). Encode `texture' = texture*g` and
`color' = color/g`. Their product is algebraically unchanged before encoding.
Full-image extrema, not a few visible samples, prove that no channel clips:
maximum texture/color products are (0.825,0.760723,0.636305). Constant scaling
commutes with bilinear sampling, wrap/clamp and color interpolation. Alpha stays
opaque. The existing post-texture PVR fog remains active; no second light bake
is applied to these color-only vertices. This does not reconstruct full PS2 LIT.

RGBA byte rounding, RGB565 quantization and the existing 8-bit vertex-color
packing are lossy. Full-texel/full-vertex-color cross-product checks bound the
observed channel errors at (5.861,2.796,4.788) 8-bit levels. Conservative continuous
sampling bounds are (9.726,5.548,9.726) levels. Fog cannot amplify these bounds.
See `quantization.json`; no bit-identical PS2 appearance is claimed.

Room format v3 and texture format v2 are unchanged. A test-only generated sidecar
v1 retains 193 RGB triples (2,316 bytes), plus first/count and full room payload
CRC. The runtime checks CRC and bounds on initial installation and reload; its
immutable table holds no arena pointers. The table remains resident across room
retirement and is included in costs. Existing per-corner UVs, clipping, direct
strips, material compilation, upload and fog submission are reused. GC normal
fast-path eligibility ignores these explicitly color-only records. Both new
runtime features are opt-in defines; ordinary builds retain GC behavior.

## Actual target comparison

A generated GC package is byte-identical to the accepted r101 reference:
SHA256 `69b4fa883b1f9586ec9f65b34360b73b3fd509a56ed73a8d0d376665b4d61572`.
Private semantic comparison proves 4,503 other batches' triangles and per-corner
attributes unchanged, every source-group record unchanged, and only texture
material 066 changed. The selected batch is `source_054_cell_0_-5`.

| Cost | A: GC | B: PS2 |
|---|---:|---:|
| Complete room package bytes | 8,430,664 | 8,429,604 |
| Complete native texture package bytes | 2,990,672 | 2,990,672 |
| Selected texture payload/VRAM bytes | 32,768 | 32,768 |
| Selected triangles | 172 | 131 |
| Selected resident vertex records | 218 | 193 |
| Complete room vertex records | 177,032 | 177,007 |
| Complete room triangles | 135,813 | 135,772 |
| Complete material batches | 4,504 | 4,504 |
| Persistent diagnostic color bytes | 0 | 2,316 |
| ELF text/read-only-data bytes, timing build | 2,687,345 | 2,689,993 |
| Room arena reservation | 8,912,896 | 8,912,896 |
| Initial arena used / observed loading peak | 8,560,640 | 8,559,584 |
| Heap used at fixed state | 204,900 | 204,900 |
| Heap free at fixed state | 143,016 | 140,584 |
| Reported main RAM free at fixed state | 2,654,208 | 2,654,208 |
| PVR free after scene textures | 2,429,480 | 2,429,480 |
| Room bytes read on initial load | 11,551,274 | 11,550,214 |
| Initial read / validation time, us | 27,799 / 3,154,518 | 27,802 / 3,154,211 |
| Initial texture upload time, us | 8,771 | 9,081 |

The 1,056-byte arena-use reduction does not shrink its fixed reservation and does
not recover available RAM. The sidecar plus extra code grows text/read-only data
by 2,648 bytes; heap headroom falls 2,432 bytes in the timing build. Page alignment
also matters: B's lifecycle build reports 8,192 fewer main-RAM-free bytes than A.
These are actual build-dependent allocations, not claims that file savings equal
usable RAM. Texture descriptor counts and allocation sizes are unchanged.

Timing uses a separate build without snapshot freezes/readback/digests/profiling.
The fixture advances deterministically to simulation tick 40, then holds the
actual player/animation/camera state there. Both arms use 640x480, identical
surroundings, source lighting/fog and scene state. After discarding frames<25:

| Fixed-state measurement | A (468 frames) | B (464 frames) |
|---|---:|---:|
| Frame work median / p95, ms | 78.900 / 81.393 | 79.410 / 81.914 |
| Outer-frame median / p95, ms | 78.912 / 81.412 | 79.422 / 81.926 |
| Frame-work interquartile range, us | 19 | 13 |
| Submitted room triangles/frame | 7,596 | 7,555 |
| Transformed vertices/frame | 13,339 | 13,314 |

One paired run measures a 0.510 ms median regression (0.65%), not a village FPS
benefit. No artificial object duplication was used. Existing light-evaluation
telemetry counts the color lookup as a call too; it does not prove that every
reported call evaluated normal lighting. Asset-only draw/preparation time is
not separately instrumented. This negative result does not establish another
asset's break-even point or campaign performance.

Each arm also completed one successful retire/reload, with zero failed loads or
GPU-fence failures and unchanged PVR/heap values across that cycle. Reload upload
was 8,108/8,066 us and installation 357,060/365,730 us for A/B. A shared baseline
asymmetry loads the 12,608-byte aligned route package only on reload, so arena
use rises equally in both arms; this is not a candidate leak. One cycle is not
an unbounded leak test. Exact records are in `measured-results.json`.

## Views, motion, identity and limits

Use `a-visual-full/frames` and `b-visual-full/frames` in the Windows evidence root.
Each contains frozen ticks 40, 80, 120, 170, 220, 270 from the same deterministic camera
movement. Tick 40 is the normal stove view; tick 170 is the closer/grazing view.
The PS2 stove is boxier, with a simpler chimney and visibly different authored
metal shading. Other positions cross unchanged furniture/room surfaces; those
occluded frames are retained and are not evidence of candidate clipping quality.
The object is opaque, so no alpha-blended candidate behavior is claimed.

`matched-states.json` verifies identical observed player position/yaw, health,
ammo and scene actor state at all six ticks. Camera/projection are pure functions
of those exact ticks in `RE4DC_PS2_ASSET_FIXTURE`; no framing changes occur between
A and B. This fixture is explicitly diagnostic, not a source room-jump camera.
Underlying source collision remains active for the stationary player.

Earlier wrong-offset, hidden-window, obstructed-camera and titlebar-cropped
captures are preserved with descriptive suffixes and excluded from acceptance.
The inherited PrintWindow helper captured a full window into a client-sized
bitmap; the final helper uses CLIENTONLY|RENDERFULLCONTENT and saves the complete
640x480 client image. No candidate defects are cropped out.

Builds use KOS `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`, the existing SH-4
O3/LTO flags, and Flycast SHA256
`64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.

| ELF | SHA256 |
|---|---|
| A visual | `0a3ed1faf6cea7b1fae36d7d99a60c306fb22bad580bdd1232f88add398fc923` |
| B visual | `1fc6a8fb6704d4a5d2ee3f55d3ed64d13fc3b355ab161d3f12472c6bcf9dc277` |
| A timing | `68e3f5b3beae7c60f3bb64378b8bc276ac2deee32298c14036e7977f836dc8ca` |
| B timing | `ba4c96c52cb870b598d65becb17b6f3944188aec06bd758245e711a116769e00` |

## Reproduce and select

`ps2_opaque_candidate.py` defaults to GC and refuses existing output directories.
Private selection files pin every input before conversion. For new outputs:

```sh
cd /root/work/re4-ps2-experiment
python3 port/dreamcast/tools/ps2_opaque_candidate.py \
 /root/probe/ps2-asset-complete/oven-selection.json /root/probe/NEW-OVEN-A
python3 port/dreamcast/tools/ps2_opaque_candidate.py \
 /root/probe/ps2-asset-complete/oven-selection.json /root/probe/NEW-OVEN-B --variant ps2
python3 -m unittest discover -s port/dreamcast/tests -p test_ps2_opaque_candidate.py
```

The complete private reproducible build command is retained in
`/root/probe/ps2-asset-complete/build.sh`; it runs `make ... all -j1` with the
existing r101 room, collision, route, Leon and audio packages. `bash build.sh a
visual` / `b visual` select the frozen-view pair; `a timing` / `b timing` select
tick 40; `a cycle` / `b cycle` select one lifecycle run. B passes
`RE4DC_PS2_OPAQUE_EXPERIMENT` and includes its generated sidecar directory; both
pass `RE4DC_PS2_ASSET_FIXTURE`. Timing additionally passes
`RE4DC_PS2_FIXED_STATE`. Build/disc output names are private experiment outputs;
use a copied script with new output names to preserve existing evidence.

Ready-to-run separate `disc.cue`/`disc.bin` pairs are under each of the six host
capture directories; only one alternative is resident in each. Exact symbols
are copied per arm and the launcher derives telemetry offsets from those files.
Never run competing timed Flycast processes.

Ten new synthetic tests cover raw attribute/triangle/transform preservation,
truncation, pointer overflow, unsupported weighted records, VIF bounds, malformed
attributes, alpha/range rejection and factorization. Twelve existing texture
conversion tests pass. The unchanged room-converter suite has a pre-existing
v3 expectation failure: `test_deterministic_package_and_manifest` expects nine
triangle indices although the current strip-only representation correctly
stores zero; its other nine tests pass. Do not report a wholly green suite.
Rebuilding both candidates with the hardened adapter reproduces package/sidecar
bytes exactly. `package-verification.json` checks the actual generated packages.

Rejected investigations are retained: nearest-bounds PS2 SMD037 was not equivalent
to GC SMD010's alpha shadow; the cart SMD013/BIN042 had mixed opacity and overbright
channels. A naive additive extra pass for that cart would require correct alpha
saturation, sorting and fog treatment. The opaque stove's exact factorization
avoids that unsupported operation without changing a global brightness setting.
No character, animated asset, full PS2 lighting, event compatibility or full-game
performance conclusion follows from this one negative environment result.
