# DCA3 source audit: verified mechanisms and the RE4DC backlog they imply

Source: an audit supplied on 20 September 2026 against `dreamcast-port` at
`9369db2`, reconciled here against the branch as it now stands. It reads DCA3
at the GitHub mirror commit `14608caa1e64d855103fe52efd0e02f1a5ab5675`, whose
root trees match the GitLab API snapshot taken at the time. That verifies the
snapshot inspected; it does not prove no later upstream commit exists. Canonical
project: [skmp/dca3-game on GitLab](https://gitlab.com/skmp/dca3-game).

The audit is implementation instruction, not measured result. Nothing in it was
run on an executable or a physical console. Every candidate below still has to
boot, pass its correctness check, record before and after timing and memory, and
end in a keep-or-revert decision.

## What has already landed since the audited revision

The audit's B1 opens with "native payload format is still missing". Half of it
is no longer missing. R4b versioned the `re4tex` record with a payload format,
moved twiddling into the converters and made the runtime copy payloads raw;
texture upload fell from 1,022,663 us to 16,945 us with no frame, VRAM, main RAM
or framebuffer change. See
[R4B_NATIVE_TEXTURE_LAYOUT_CHECKPOINT.md](R4B_NATIVE_TEXTURE_LAYOUT_CHECKPOINT.md).
The audit's own caution held exactly: offline twiddling does not improve
sampling of textures that were already twiddled at load, and no frame benefit
was claimed.

What remains of B1 is the part R4b did not touch: one shared allocation per
content identity, and the VQ payloads themselves.

## Provenance and licence

`vendor/librw/LICENSE` is MIT. That does not extend to the game-side DCA3 or
`re3` files, which carry no licence of their own in the tree inspected here.
Read for mechanism; check provenance before reusing any code; never use its
data. `DC_SH4`, `DC_SIM` and `DC_TEXCONV` conditionals matter: a host
conversion or simulation path is not evidence of target runtime behaviour.

## Priorities

| Work | Applicability | Benefit category | Position |
|---|---|---|---|
| A1 actor packet preparation and eligibility specialization | high; the actor draw still re-walks indices and attributes | resident-scene CPU frame time | first rendering experiment |
| A2 selective optimization levels and LTO | high as a cheap experiment, uncertain outcome | CPU time and code size | small matrix, allowed alongside A1 |
| A3 batched directional dot products | conditional; GTA has no local lights in this path and RE4 does | CPU lighting, mostly on hardware | only the compatible directional subset |
| B1 shared raster ownership, then VQ payloads | high; payload format now exists, sharing does not | VRAM and residency | next R4 implementation |
| B2 native local geometry tables in packages | high; the runtime pass already exists | startup and live RAM | after duplicate representations are accounted for |
| B3 queued reads, dependency-aware residency, safe reclamation | high fit, larger integration | transition stalls, memory stability | after B1/B2 and the authored-set inventory |
| H1 OIX/ORA scratch and custom cache-flush submission | real technique, substantial target risk | possible hardware throughput | hardware-gated research only |

## A1: reduce actor packet preparation, not the PVR call count

DCA3 prepares bounded local vertex records, indexes them with a compact local
stream where seven bits are the index and the high bit terminates a strip, and
picks a transform path by format and clipping need instead of rebuilding a
general vertex per occurrence. The portable idea is: **prepare a bounded useful
representation once, then submit from cheap local references.**

Do not copy its 64-byte intermediate vertex; the RE4 packed-colour PVR packet is
already 32 bytes. `pvr_vertex16_t` means 16-bit UV fields, not a 16-byte vertex.

RE4 target: `build_character_lighting()` and `draw_character()` in
`room/main.cpp`. The direct-strip path scans
`primitive_indices -> draw_vertices -> projected.position.depth` for
eligibility, then walks the same references again to fetch position, UV and
packed normal colour. Schema work belongs in `tools/convert_character.py` and
`room/character_package.hpp/.cpp`, preserving their independent source
positions, authored normals, draw corners, palette references and markers.

- **A1a, smallest change.** Merge eligibility and packet assembly into one pass
  for an eligible strip. Reserve capacity first, remember the strip's starting
  count, and on the first ineligible vertex rewind the whole unsubmitted strip
  and take the existing fallback. Never flush a speculative partial strip. Keep
  counters local and publish once per strip. This is the room-side strategy
  already accepted in R3x, applied to actors.
- **A1b, only if assembly is still material.** Emit compact actor draw recipes
  offline and compare a pre-resolved occurrence stream against a bounded local
  corner cache. A corner's identity is position plus normal/colour context plus
  UV; do not weld on coordinate equality. Keep full-precision UVs and existing
  positions and colours at first, and keep position and normal work shared so
  local batches do not re-skin every occurrence. Decide from counts of emitted
  occurrences, distinct corners, cache fills, positions transformed and bytes
  touched. Do not grow an actor-wide cache without showing reuse repays its fill.
- **A1c, optional.** Derive conservative pose-aware bounds to pick the
  no-clipping kernel without scanning every depth. Start at whole-actor
  eligibility. Rest-pose bounds are unsafe for animated characters: blended
  poses, attachments, attack motions and death poses must be contained, and
  unproven bounds take the existing path.

**Projection guard.** The current path uses `kProjectionDepthBias = 1.0f` and
its strip visibility accounts for the KOS projection denominator rather than a
conventional depth-only projection. Do not transplant GTA frustum equations,
`frsqrt(w*w)`, or near/far conventions. A fast-path eligibility change must
preserve the accepted projection and fallback behaviour; fixing a projection
defect is a separate source-fidelity change.

**Acceptance.** Compare at identical render snapshots: normal pose, turn, the
full aim range, reload, attack, hit, death and near-plane crossings. Preserve
strip parity, source-facing culling, alpha order, depth behaviour and marker
output, and compare whole actor images rather than only pixels outside the
actor. Measure preparation plus draw together, so an emission win paid back by
preparation is rejected. Report whole-route p50/p95/p99 and memory. No forecast
of milliseconds is an acceptance criterion.

## A2: selective build policy, not a flag bundle

DCA3's `liberty/Makefile` uses `-Os` as the ordinary setting, an `OBJS_O3` list
for hot units, an `OBJS_NO_FAST_MATH` list for camera units, and link-time
optimization. That is a real implementation, not folklore.

RE4's room Makefile asks for `-O2`, compiles most frame and gameplay work
together in `main.cpp`, and leaves the rest to KOS. Inspect the effective
compile and link commands before assuming a setting is absent. Test separately:
current settings; `-O3` with unchanged floating-point semantics; then compatible
LTO. Hold assets, KOS revision and toolchain fixed, confirm that changed flags
invalidate the incremental rebuild, and measure linked size, RAM and the same
route. If file-level policy helps, move only the hot renderer kernels into a
small translation unit as a movement-only patch first.

Do not import global `-ffast-math`, `-fmerge-all-constants`, altered FP modes or
camera exceptions as presumed-safe defaults, and do not strip assertions
indiscriminately. Relaxed arithmetic is a separate rendering-only candidate with
its own numerical validation.

## A3: batch directional dot products, keep RE4's local lights

DCA3's `setLights()` packs directional vectors and its `lightingCB()` asserts
`numLocals == 0`; `tnlMeshletDiffuseColor<>()` computes up to four directional
dot products as one matrix-vector operation, clamping and combining each
contribution. It is not a general point or spot implementation, and swapping
RE4's lighting for it would change the scene.

Work inside `prepare_actor_lights()`, `evaluate_prepared_actor_lighting()` and
`build_character_lighting()`. The prepared contiguous records are already
accepted (R3w); do not redo them. Prototype batching only the directional
subset, keeping normalization, distance, attenuation, cone tests and source
selection intact, and either retain original-order accumulation or validate the
numerical difference explicitly. Audit matrix register ownership between the
transform and lighting kernels. Measure actual directionals per actor and normal
evaluations first: a small subset may not amortize matrix setup. Keep the
existing dual-evaluator check for diagnostics, and remember trace-enabled
timings are not production numbers. The `frsqrt` loss under the measured Flycast
model is not evidence that hardware has no opportunity, and a synthetic hardware
advantage is not evidence that this game improves.

## B1 remainder: one shared allocation per content identity

DCA3's `readNativeTexture()` reads explicit format flags, payload size, texture
offset and resource ID, consults `cachedRasters`, increments a shared reference
count and skips a duplicate payload instead of uploading it again;
`writeNativeTexture()` and `destroyNativeRaster()` serialize the representation
and free the allocation after the last reference; `CTxdStore` tracks dictionary
references separately. That separation of container lifetime from payload
lifetime is the mechanism to take.

RE4's `Package::open/upload/close` still allocates per descriptor and still
requires `data_size == width * height * 2`, which VQ and palette payloads will
break. Extend the schema with encoding and layout, logical dimensions, the
actual aligned allocation size, mip and palette metadata where supported, a
texture-address offset where the format needs one, and a validated content
identity. Keep per-material sampler and blend state separate: identical texels
may share storage while material state differs. Use a content digest plus
descriptor compatibility and collision validation rather than trusting a bare
32-bit identifier. Test partial upload failure and rollback.

Then integrate the six high-resolution VQ candidates the inventory already
found; do not rebuild the inventory. Higher PSNR and fewer bytes make them
promising, not automatically visually lossless: compare close views, motion,
filter behaviour, alpha edges and the original-resolution source. Unreduced
textures stay uncompressed unless their own evidence says otherwise. Note that
the inspected GTA reader asserts one mip level and leaves its palette-lock
methods unimplemented, so it is evidence for native payloads and sharing only;
use the KOS formats for mip and palette paths.

**Lifetime rules.** Duplicate descriptors within and across packages must share
one allocation, and releasing one owner must not invalidate another. A texture
is not renderable until its upload completes. Keep DMA staging alive until
completion, handle busy transfers, and respect the pinned KOS alignment and
cache requirements. GPU references outlive CPU submission: pin resources for all
in-flight frames and retire them only after the relevant render completes, not
on submission return and not at the next simulation tick. Report unique resident
payload bytes, total and largest-contiguous VRAM free, staging peaks, upload
time and loading p95.

## B2: serialize the geometry tables already built at load

DCA3 runs native geometry instancing inside its converter under `DC_TEXCONV`
and carries versioned `readNativeData()`/`writeNativeData()` for the prepared
blob. RE4's equivalent is to move `prepare_room_batch_locals()` into the room
converter and package, preserving R3v/R3x local-index semantics, the
oversized-batch fallback, source identity, selected-light context and strip
order.

Do not promise to recover all 413,696 bytes by moving them into a memory-mapped
ROM disk: package bytes are resident too. Remove redundant forms where safe or
quantify the real reduction in temporary and persistent memory, and keep startup
work removed separate from any layout-related frame change. Test converter and
runtime round-trip, corrupted offsets, index-width limits, historical package
behaviour, oversized batches and byte-identical packets where expected.

## B3: queue storage, preserve dependencies, reclaim only when safe

DCA3 separates request submission, readiness polling and explicit blocking; its
reader loop limits ordinary reads to 64 KiB chunks and services queued audio
work between chunks and before channel work, which is cooperative I/O
scheduling rather than a second CPU. Its streaming couples model requests to
texture dependencies with requested/reading/loaded state, and its allocator
triggers reclamation and relocation under pressure, updating the raster address
when a texture moves.

RE4 keeps the authored active, staged and remove block sets as the residency
authority. A resource off camera may still be needed by gameplay, imminent
camera motion, sound, collision or an in-flight frame, so do not import GTA
distance heuristics, actor budgets or behind-camera eviction. Model explicit
states, proposed here and not a claim about GTA's names:
`unloaded -> reading -> CPU-ready -> uploading -> resident -> retiring`, with
stable resource identifiers, dependency references, in-flight frame pins and
cancellation generations. Use a small bounded request queue, aligned staging
buffers, and a storage index of offset, aligned read size, valid payload size,
checksum and dependencies. Budget the completed-load processing and the VRAM
uploads too: an async read followed by a long unbounded main-thread install
still stutters. Treat 64 KiB as a starting experiment and measure the intended
GD-ROM/GDEMU path rather than assuming optical and flash behave alike.

Do not copy the error handling: the inspected reader handles `read() == -1` but
makes no progress on `read() == 0`. Handle EOF, short reads, cancellation,
failed checksums, timeout and shutdown explicitly, and stop stale completed
requests from publishing into a restarted room.

**Fragmentation.** Measure the largest free allocation as well as total free
VRAM, and prefer planned arenas, shared lifetimes and proactive eviction before
custom defragmentation. RE4 caches compiled material headers that encode texture
addresses, so moving a texture must update or regenerate every affected header
and wait for in-flight users; updating a handle's pointer is not enough. Keep
unbounded reclamation out of the gameplay frame. A moving allocator stays
optional until fragmentation evidence justifies it.

## Hardware-gated or non-portable

**OIX/ORA scratch.** DCA3's `enter_oix_`, `leave_oix_`, alternate ORA functions
and `driverOpen()` use special cache mappings, cache flushes, interrupt handling
and a runtime fallback. This is not a safe array replacement. Benchmark ordinary
aligned bounded scratch first; an OIX candidate needs a standalone hardware
fixture, documented cache, interrupt and FPU ownership, KOS compatibility and
coexistence tests with render, input and audio.

**PVR defaults and autosort.** DCA3's buffer sizes and sorting policy match its
own renderer; do not transplant them without RE4 fragment ordering, occupancy
and memory evidence.

**Compact formats.** Seven-bit local indices suit a bounded batch; reduced
position, normal or UV precision is a separate adaptation. Keep full precision
in the first layout experiment, and remember a compact UV encoding does not
shrink an already 32-byte PVR packet.

**Content assumptions.** No replacing RE4 point and spot lights with
directionals, no global texture caps, no inherited pedestrian LODs, no arbitrary
invisible-asset eviction, and no removing features merely because GTA disables
them.

## PS2 cross-check

The workspace now holds a PS2 RE4 disc image, so the R4 plan's "no PS2 source"
note applies only until a manifest is built from it. When it is, match assets by
validated scene, material and content identity rather than filename or ordinal,
compare dimensions, formats, colour and alpha, mip presence and dependency
grouping, and record what fails to match. Use the differences as comparative
evidence only: no PS2 asset enters a package, the GameCube source stays the
rendering and behaviour reference, and each Dreamcast format decision needs its
own quality and memory evidence. Do not delay A1 to A3 or the native layout work
for a full cross-platform database, and do not infer transfer rate or residency
from image dimensions.

## Evidence rules this adds

Keep one experiment ledger: source mechanism, target functions, baseline and
candidate identifiers, known changed variables, CPU-stage and whole-frame
distributions, presentation and input evidence, RAM/VRAM/AICA peaks, correctness
result, and the keep-or-revert reason. Include whole-route and deliberately
difficult states; a dead-enemy microbenchmark is not enough. Run diagnostic
parity and production timing separately so trace overhead and mismatched
animation phases cannot masquerade as either result. Benchmark A/B builds
sequentially under the same conditions and repeat beyond observed noise.
Emulator-only successes stay explicitly provisional for physical performance.

A milestone is not complete because source inspection, package validity, a
nominal 30 Hz simulation, autoplay completion or a 30 fps video says so. It is
complete when the accepted encounter runs with responsive manual play, sustained
target presentation, correct source-timed behaviour, stable resource lifetimes
and verified hardware budgets.

## Pinned reading references

Regions, not instructions to copy every line; the function names identify the
intent within each region. All at mirror commit
`14608caa1e64d855103fe52efd0e02f1a5ab5675`.

| Tag | What | Path and lines |
|---|---|---|
| G1 | meshlet representation, transform specialization, `setLights()`, `lightingCB()` | `vendor/librw/src/dc/rwdc.cpp` 2100-2390 |
| G2 | `submitMeshlet`, `submitMeshletFallback` | `vendor/librw/src/dc/rwdc.cpp` 2660-2810 |
| G3 | meshlet loop in `defaultRenderCB`, light-count dispatch | `vendor/librw/src/dc/rwdc.cpp` 4000-4245 |
| G4 | `OBJS_O3`, `-Os`, `OBJS_NO_FAST_MATH`, LTO | `liberty/Makefile` 107-182 |
| G5 | `tnlMeshletDiffuseColor<cntDiffuse,floatNormals>()` | `vendor/librw/src/dc/rwdc.cpp` |
| G6 | `readNativeTexture()`, `cachedRasters`, `pvr_txr_load_dma` | `vendor/librw/src/dc/rwdc.cpp` |
| G7 | `writeNativeTexture()`, `destroyNativeRaster()`, `read/writeNativeData()` | `vendor/librw/src/dc/rwdc.cpp` |
| G8 | `CTxdStore` dictionary references | `src/liberty/rw/TxdStore.cpp` |
| G9 | converter geometry instancing | `src/tools/texconv.cpp` |
| G10 | `defaultInstance()` under `DC_TEXCONV`, `driverOpen()` | `vendor/librw/src/dc/rwdc.cpp` |
| G11 | `CdStreamRead`, `GetStatus`, `Sync`, channel setup | `src/liberty/core/CdStreamDC.cpp` |
| G12 | `read_loop()`, `CdStreamThread()`, 64 KiB chunks | `src/liberty/core/CdStreamDC.cpp` |
| G13 | `CStreaming::RequestModel`, `RemoveModel` | `src/liberty/core/Streaming.cpp` |
| G14 | `allocTexture()`, `allocDefrag()`, `DcRaster::texaddr` | `vendor/librw/src/dc/alloc.cpp` |
| G15 | `enter_oix_`, `leave_oix_`, ORA functions | `vendor/librw/src/dc/` |
| G16 | MIT licence, librw only | `vendor/librw/LICENSE` |

Local reference checkout used for this reconciliation:
`re4_helpers/dca3-game-beta` (beta branch snapshot), read for mechanism only.
