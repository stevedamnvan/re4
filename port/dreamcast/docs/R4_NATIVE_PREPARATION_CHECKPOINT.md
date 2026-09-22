# Native renderer integration checkpoints: D350-D352

Updated 2026-09-22. Base HEAD `ed9165bc7069232df840aba5a70150166b21989b`
plus the recorded inherited integration overlay. No historical gameplay, pose,
camera or facing state was imported. Both selectors default off.

## D350: keep the shared strip mechanism

The existing room `prepare_direct_strip` and `triangle_visible_xy` implementations
now live in shared `pvr_geometry.*`. Both room/main.cpp and the recovered
native_model.cpp call them. The new adapter supplies current source positions,
modelview, topology, UVs, material alpha and cull state. The existing packet
buffer provides temporary tail space; clipping falls back to the existing path.
`MODEL_ROOM_STRIPS=1` selects this connection. No extra resident buffer.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d350a-render-baseline` and
`D:/Flycast-Evidence/re4-dreamcast/d350b-shared-strips` (C: junction available).
Existing startup-only fixture and capture tools, 160-second runs, 640x480,
Flycast only. This is the post-title outside-cabin scene, not an active combat
route, the historical cabin workload, or physical-hardware acceptance.

44 common source-frame IDs 1232-1275, host seconds 70-150 excluding capture
windows: presentation p50 **1621.893 ->1003.415 ms**, p95 **1623.154 ->1003.417**
(-38.13% median). The asynchronous source CPU samples have medians
1619.160 ->1000.436 ms; render setup 1555.038 ->939.887 ms. PVR registration
1583.221 ->968.212 ms includes CPU preparation; render about 7.503 ms overlaps
other work and must not be added to it. These are not a fully attributed profile.
Matched player position/angle differences were zero; final images were inspected,
but different capture ticks are not a pixel-equivalence certificate.

Required block/em12 allocation-point free bytes remain 2,921,856 /1,806,336;
final source heap capacity/free/largest 8,840,576 /66,592 /66,592. Texture VRAM
3,276,800; VRAM free 1,462,184 in these observations. ELF text/data/BSS
2,312,764 /77,016 /673,464, +856 text versus the preceding build. No additional
source archive or animation recovery. Position/reference counter deltas are
asynchronous observations, recorded in comparison.json rather than asserted
as precisely paired per-frame work.

Reference ELF SHA256:
`3d56e49f1b3164c16a3aec52589002604e2f10945f9a0f40e3673d45f5ebdb92`
Candidate ELF:
`a1e717b1f30832d0bf9517dbf2198d30f4c4c88676c0f48cf87c65610d7a6410`
Candidate disc:
`eb24556046cb1b2d7e2c0b7dfc121308e46df7c112811c69137b9992efba3fdf`.

**Correction:** this improvement did not remove lighting. Both arms already used
the same white/unlit diagnostic shading. Neither restores accepted source
lighting, masks, material/pass organization or full character presentation.

## D351: implemented and measured; do not promote this cache policy

`NativeDrawPlan` prepares ordered primitive records and decoded position,
normal, UV and color indices on qualified first use. The existing source archive
bind/unbind/retire hooks establish ownership; `storage::Arena` provides bounded
backing. Copied plans are leased until synchronous submission returns and reset
on owner replacement/invalidation. No pose, camera, light or gameplay data is
cached. Current bindings and attribute ranges are checked at draw time.

This adds only native structure preparation, typed-corner submission and owner
metadata. It does not supply static primitive bounds, batch-local renumbering,
lighting, material classification or archive-payload recovery. Animated bounds
cannot be frozen from one pose. Unowned/capacity-rejected parts remain on the
explicit reference path. Failed/capacity admissions do not repeatedly prepare.

Three target attempts are preserved separately:

| Attempt | Outcome |
| --- | --- |
| d351-native-draw-plans | em12 DVD queue stuck at Rno1/step4 before any model/plan use; no timing conclusion |
| d351b-dvd-diagnostic | room reached; 64 KiB plan allocation failed and native texture metadata later failed; rejected |
| d351c-funded-draw-plans | explicit 16 KiB cache plus 16 KiB native margin, funded by a 32 KiB smaller source arena; room visible and textures upload |

These folders are under `D:/Flycast-Evidence/re4-dreamcast/`, with C: junctions.
D351c has exact `owned-source/`, hashes, inherited tracked patch, ELF/disc,
fixture, symbol map, toolchain/config/capture identities, logs, RAM and images.
Private reproduction: `/root/probe/d351-build.sh`, then
`/root/probe/d351c-prepare.py` with a fresh evidence suffix. The preserved
owned-source snapshot includes temporary DVD diagnostics subsequently removed.
The subsequent build-only cleanup ELF is
`90980f2ea48b20dba63e32cc4e24f4065ec2442a2c5be85ac53c3026ae298974`,
text/data/BSS 2,319,044 /77,016 /676,856; it has not been rerun on target.

D351c ELF SHA256:
`50270ac1524382c7f91fc57457a343c9a354444433799f010243d9d9e94ae57f`
Disc SHA256:
`a6f07c608e08bea6b2403cd565a4d2ee0503cea067e8f1f51a7b908bf50f4883`.
Text/data/BSS 2,319,564 /77,016 /676,856. Toolchain is pinned KOS
`/root/work/kos-re4dc-d336`, SH GCC 15.2; Flycast SHA256
`64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
The private mirror remains `/root/probe/d343-mirror`; fixture
`/root/probe/d347d-fixtures`. Manifests preserve individual asset/tool hashes.

After first-load frames, 65 common source-frame IDs 1240-1304 give:

| Metric | D350 strips | D351c plans |
| --- | ---: | ---: |
| Presented interval p50 | 1003.415 ms | 970.051 ms |
| Presented interval p95 | 1003.417 ms | 983.391 ms |
| Presented interval p99 | 1003.417 ms | 986.737 ms |
| Source CPU asynchronous p50 | 1000.435 ms | 970.495 ms |
| Source render setup asynchronous p50 | 939.958 ms | 911.868 ms |
| Source final free/largest | 66,592 B | 33,824 B |
| Source heap capacity | 8,840,576 B | 8,807,808 B |

The observed median improvement is **3.33%**, not a fully isolated decode-cost
measurement. Source IDs match, but player positions differ by up to 1.765625
source units (angles equal); no exact state/pixel parity claim. Final captures
show the same diagnostic scene and retain its known material/lighting defects.
Image inspection records 139,053 changed pixels, mean absolute channel error
2.7867/255, from different source ticks. This is not visual acceptance.

Three plans install; steady samples reuse only **two parts**, with **185
reference fallbacks** (114 capacity, 71 owner). Cache used/peak is **16,288 B**.
Installed plans read no GX command/index bytes during draws; installation decoded
bytes remain zero after warm-up. The remaining reference path still walks
**2,990,528 bytes per sampled frame**. No invalid-plan reports or repeated cache
reconstruction were observed. The 32 KiB arena reduction also lowers the earlier
block/em12 free values by 32,768 B; all required initialization still succeeds.
Final source free-list traversal, not just a logged counter, verifies the loss.
VRAM observations differ slightly with source state (D351c textures 3,268,608,
free 1,470,408); this is not a texture-memory saving. Loading/retry peaks, active
combat, response latency, audio and physical timing remain unqualified.

**Decision:** keep source/fixture as a default-off experiment; reject the funded
copy-cache policy for primary adoption. Its low coverage and lost game headroom
are not justified by this small gain. Do not enlarge the duplicate cache blindly.
The prepared representation needs wider ownership coverage and a compact/replacing
storage strategy before the zero-GX-decoding gate covers the required scene.

## Validation and next connection

Host ASan/UBSan packet tests cover cache0/1, shared strips0/1 and plans0/1 against
the reference implementation, including clipping, alpha, winding and chunking.
The actual owner/arena test covers unchanged-use reuse, three retirement cycles,
leases during replacement, same-address reload, malformed input and capacity
fallback. Both pass; these are host contract checks, not complete room acceptance.
Temporary DVD call-site tracing preserved the PowerPC preprocessed source.
The original native queue step4 failure did not reproduce in b/c, so no scheduling
fix is claimed. Their logs show blockRead pumping a background queue at step1/2;
concurrent yielding source steps remain a specific unresolved hypothesis.

Continue the user's existing integration order: qualified prepared draw structure;
source-driven native opaque/mask/translucent passes; prepared current selected
lights; conservative bounds and batch-local transforms. Preserve current source
facing, pose, camera and lifecycle. The historical room's depth+1 projection bias
is not automatically compatible with the recovered source projection.

SH4ZAM status checked 2026-09-22: no SH4ZAM includes/link dependency/symbols in
this target. The old room uses KOS mat_trans_single/FTRV; the current native model
hot loop still multiplies its modelview with scalar operations. SH4ZAM is a
specific candidate for the batch transform/normal kernels, with pinned version,
GCC 15.2 compatibility, matrix convention/register ownership and numerical-error
checks required. See https://sh4zam.com/ . Do not label current code SH4ZAM-backed
or claim another project's speedup. This does not replace missing preparation,
source material/lighting or event/gameplay connections.


## D352 integrated stack and asset-lifetime boundary

In progress, 2026-09-22. User direction supersedes the historical per-component
sequence above. HEAD7afde16 plus recorded inherited work; one default-off
`D349_RENDERER_STACK=1` candidate, compared against selector0 from the same state.
No automatic promotion, source gameplay substitutions or copied prototype loop.

The integration has three explicit adapters:

| Adapter | Source producer and lifetime | Reused mechanism / current connection |
| --- | --- | --- |
| Asset | `cModInfoMgr::create`, active `ModInfoMgr` list, archive/block bind/relocate/retire | `model_asset_bridge.cpp` prepares the existing `NativeDrawPlan` once per changed asset set before emission; owner/slab code retains compact spans and optional immutable bounds. Draw lookup does not install. |
| Frame | current source skinning arrays, instance matrix, camera/projection, visibility and facing | `model_bridge.cpp` borrows current arrays through the source render barrier; `pvr_geometry` direct strips/visibility/clipping and native packet owner consume them. No second deformation or gameplay loop. |
| Material/light | source shader/texture animation/alpha setup and selected GX light state | Existing GX hooks capture semantic state; shared prepared lighting, material headers and existing texture handles feed OP/TR. Supported source masks reuse prepared native packages. |

Plans contain16-byte headers plus8 bytes per command, not decoded corners.
A 9000-corner command takes24 bytes. B partitions the existing 64 KiB slab into
24 KiB packets,8 KiB static-light storage,32 KiB metadata (including its entry
table). D351's32 KiB source-arena cut is removed. Storage staging is 16 KiB in
both game arms (room target remains64 KiB):49,152 BSS bytes removed, unchanged
source capacity and small-file unaligned/direct-read rules. No new streamer,
source texture copy or fourth asset registry was introduced.

Historical code reuse does not permit importing historical semantics blindly.
The extracted historical `PreparedActorLights` evaluator remains shared with the
room target. Source GX coefficients use the source-semantic evaluator where the
historical attenuation/material model cannot express them. FTRV/compiler policy,
visibility, strips and packet mechanisms are reused. The tiny unchanged-state
static-light cache is not the historical full world-light bake; moving-camera
reuse and source-exact integer rounding are still qualification limits.

Graded same-UV masks use10 explicit offline native texture pairs (157,952 gross
VRAM bytes if all loaded), through the existing package/identity cache. Source
alpha GREATER0/depth equivalence, higher thresholds, independent UVs, no-image,
specular/fog and general TEV remain incomplete. PT phase is currently empty;
this is not full punch-through support. Batch-local source positions use bounded
frame scratch; offline local-index preparation/whole-scene plan coverage are
not proven. Full character appearance cannot be claimed from build/tests alone.

### Prerequisites and initial target attempts

Initial D352 A reached room output but exhausted KOS heap during native uploads;
source heap still had66,592 bytes. The reduced shared I/O staging addresses that
separate native budget. V2 A and B then reproduced em12 Rno1/step4 before any
3D use. Both are loader failures, not performance measurements. Their complete
snapshots are preserved under d352v2a/b-integrated-stack. A forced-interleaving
host control reproduces exactly step4: foreground pumping reenters a queue while
synchronous KOS DVD I/O yields, before the source increments its step. The common
candidate serializes a complete `cDvdQueue::Read` call using existing native-I/O
cancellation depth. Contention yields/returns pending; source completion and
sound/container handling remain unchanged. No success stub or state forcing.

V3 A passes menu, required block/enemy loading and reaches diagnostic room
rendering with 66,592 source free bytes. Current v3 ELF identities:

| Arm | SHA256 | text / data / BSS bytes |
| --- | --- | --- |
| A | `e63750eaea6098e4b7262a4e69d36b5c2d4f3d6ef761153df23ddd508ed13b53` | 2,316,372 /77,016 /624,696 |
| B | `35a74030ba8b92a1cbb9ea5050d9f248b09d7a1a24bbc9735b1e167dc1e4451c` | 2,335,548 /82,920 /625,560 |

B's static executable cost is 25,944 bytes above A; it is not free simply because
metadata reuses a slab. Source arena request remains13 MiB in both; the effective
source heap remains a separately measured value. Peak native allocations and
complete gameplay peaks are not implied by these linker sizes.

Evidence lives in `D:/Flycast-Evidence/re4-dreamcast/d352v3a-integrated-stack`
and `d352v3b-integrated-stack`: exact source snapshot/inherited patch, executable,
assets/fixture, KOS/GCC/Flycast/config and capture identities. KOS d336, GCC 15.2,
mirror `/root/probe/d343-mirror`, fixture `/root/probe/d352-fixtures`. Reuse the
existing 160-second startup/source fixture and corrected framebuffer reader.
It contains no combat route or movie playback. Earlier D352/v2 discs are now
verified xdelta3 encodings against the preserved D351c disc; individual
`disc-compression.json` files record hashes/restoration. Captures/ELFs remain.

Host checks pass for structural-only plans, no draw-time install, same-address
reload/leases/retire, bounded/short reads, native VQ, shared lighting capture,
source queue reentry, deferred source pose lifetime and native pass/frame owner.
PowerPC preprocessed block/trans/model/DVD bodies match HEAD plus the initial
inherited patch. This is not a new ProDG object comparison. Both target arms
build. SH4ZAM is not linked; no global fast-math was added.

Whole-stack target outcome is pending below; a successful loader/isolated adapter
is not restored cabin or three-room acceptance. Keep source events/audio,
inventory, complete materials/characters, active combat, transitions/retry,
response and hardware qualification visible.


### D352 v3-v5 full-candidate failures and current boundary

The common DVD queue-step fix is committed/pushed06567b3; remote SHA verified.
The renderer stack remains unpromoted. V3 B entered an empty PT list although
pinned KOS enabled only OP/TR bins; completion masks could not agree. V4 removes
that list entry. Its very small packet counts were invalid performance evidence:
KOS mat_trans_single returns reciprocal depth and was incorrectly used for an
affine modelview transform. V5 uses mat_trans_nodiv, then the existing source
projection. These are fixes following whole-stack failures, not per-feature FPS
promotion. New focused deferred-stream host check passes.

V5 B ELF `ed1cd78a61b4fae0cb5bee390c962622b642e3218361d90494a0a541e3a6fffa`,
text/data/BSS2,335,516/82,920/625,560. Evidence directory
`D:/Flycast-Evidence/re4-dreamcast/d352v5b-integrated-stack`. Final RGB565 readback
shows source-controlled Leon and the forest/cabin geometry. The collected flip
trace does not keep advancing reliably after initial room frames, despite later
source draw-plan log updates. Resolve actual presentation/queue ownership before
claiming a steady-state frame budget. This is neither full appearance acceptance
nor active combat acceptance. The harness ends at its160-second deadline.

Asset registration reported531 part references and 95 successful prepares at one
update. The32 KiB partition saturates; a later frame has 38 plan hits and 203
uncovered part calls, ~2,018,080 reference GX bytes walked. Zero draw-time plan
installation is established, but zero whole-scene GX parsing is not. Do not hide
capacity fallback behind the structural metadata design. Source free remains
66,592 after required block/enemy loading.

After commit06567b3 the user requested a separate PS2 r100 COLOR/NORMAL inventory
and prelit-room experiment. Its isolated worktree is
`/root/work/re4-r100-prelit-d353`, branch`experiment/r100-prelit-d353`; private
inputs/results are`/root/probe/d353-ps2-r100-prelit`. It uses the preserved D349
room target for a diagnostic lighting comparison. It does not replace the
recovered game, fix D352 presentation, promote PS2 content or accept gameplay.


## D354 - stable integrated profile, not performance acceptance (2026-09-22)

The primary task remains wholesale D349 architecture integration beneath the
recovered game. This is one default-off `D349_RENDERER_STACK=0/1` comparison,
not individual promotion of strips, lighting, compiler options or submission.
Current source camera, pose, facing, material selection and gameplay remain the
only authority. D349's isolated room executable is unchanged.

### Qualified window and identities

D354v8 has **70 identical captured source snapshots at identical source ticks
2382-2451**, native frames 2383-2452 and 70 consecutive observed presentations
2349-2418. Warm-up excludes the first 32 model-presenting native frames. Every
completed frame in the window is checked, including zero-packet/aborted frames;
presentation intervals use all observed flip IDs, not only the last sample of
each native frame. Both arms have zero frame aborts, queue drops, native texture
allocation/open/upload/slot/budget failures and zero uploads after warm-up.
No missing native/source/presentation IDs occur in that window. This is a stable
**diagnostic** A/B, not a claim of complete gameplay or equivalent visual work.

The snapshot covers the source counter, system/stop/room/status flags, player
transform, camera and motion. It does not certify every enemy field or RNG state.
The fixture is the settled post-opening view, without movement/combat/death/retry.
Startup still logs the existing oversized arena probe before the smaller arena
succeeds; the zero-allocation-failure claim is for the measured window, not that
initial probe. One B frame was discarded during warm-up and is not hidden as a
successful frame. No source hold, camera or gameplay counter was forced.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d354v8a-integrated-stack` and
`d354v8b-integrated-stack`; comparison and analysis recipe are
`d354v8-comparison.json` and `d354v8-report.py` in the same parent directory.
Each arm retains executable/disc/capture hashes, source patch and owned new files,
fixture hashes, configuration, tools, RAM, logs and corrected RGB565 readback.
The builds are primary 06567b3 **plus the recorded dirty source**, not reproducible
from HEAD alone. Never overwrite current work with a historical reference.

| Arm | ELF SHA256 | text / data / BSS bytes |
| --- | --- | --- |
| A | `7323c4ebba36a3b9067fddd17fbff2286c0ccf6e109fbb525c6052ca2085e9de` | 2,323,676 / 78,236 / 621,144 |
| B | `74fc73aefca2311066074ba01be4a3376821cf2db1176ea0fa94eddc5643e5b5` | 2,343,728 / 85,480 / 622,008 |

Both use KOS `/root/work/kos-re4dc-d336`, GCC 15.2, mirror
`/root/probe/d343-mirror`, fixture `/root/probe/d354v7-fixtures`, and Flycast
SHA256 `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
Private recipes `/root/probe/d354v8-build-arm.sh` and
`d354v8-prepare-arm.py` take `a` or `b`; existing output directories must not be
reused. `NATIVE_RENDER_PROFILE=1` is common to both arms. Required resource/demand,
streaming, position-cache, event and strip options are recorded in those recipes.
The native kernel compiler policy and FTRV/direct OP paths were already present;
this slice did not replace them or introduce SH4ZAM.

### Budget, including profiling cost

TMU2 nested wall spans are exclusive on the render thread, include task preemption
and instrumentation, and preserve the pinned KOS clock configuration. PRFC1 was
not used. Completed statistics carry the same native-frame ID and captured source
snapshot. The outer render span runs between source UI begin and end-frame entry;
uninstrumented source work is separately visible as `outside`. Asset registration
before begin and asynchronous GPU rendering are not included in those scopes.

| Measured quantity | A | B |
| --- | ---: | ---: |
| Render wall p50 ms | 1191.831 | 1842.358 |
| Render wall p95 ms | 1194.561 | 1844.195 |
| Presented interval p50 ms | 1220.281 | 1873.373 |
| Presented interval p95 ms | 1222.787 | 1873.376 |

| Exclusive stage, p50 ms | A | B |
| --- | ---: | ---: |
| topology | 97.840 | 40.108 |
| transform_project | 381.938 | 377.852 |
| lighting | 0.000 | 723.596 |
| visibility | 0.000 | 1.128 |
| clip_fallback | 167.538 | 159.034 |
| packet_pack | 485.990 | 456.764 |
| texture_resolve | 0.622 | 1.006 |
| texture_upload | 0.000 | 0.000 |
| submit_op | 0.000 | 8.743 |
| submit_pt | 0.000 | 0.000 |
| submit_tr | 6.596 | 0.931 |
| tr_enqueue | 0.000 | 6.801 |
| tr_drain | 0.000 | 2.161 |
| ui_enqueue | 0.108 | 0.113 |
| ui_drain | 0.135 | 0.136 |
| model_setup | 4.371 | 14.143 |
| outside | 44.587 | 47.686 |
| presentation_fence | 27.938 | 28.278 |

The presentation fence is after the outer render span. PVR reports about 7.50 ms
render time in both arms; it overlaps CPU work and is not added to CPU totals.
Stage medians are individual distributions, not an exactly additive frame.

Scope overhead is substantial: approximately 553k clock reads/frame for A and 979k
for B. The 512-switch empty-scope calibration suggests roughly 185 ms and 329 ms of
instrumentation respectively. Those are estimates, not corrections to subtract:
call-site/compiler/cache/preemption costs differ from that empty calibration.
These instrumented values are not release FPS or physical Dreamcast timings.

A remains the older unlit/material-limited path; B performs selected source
lighting and serves additional source color/mask resources. Therefore B's higher
cost is not evidence that D349's historical lighting evaluator regressed at an
equal workload. It establishes that the present source adapters still fail to
reproduce D349's economical preparation. Source weight/palette/morph/position/
normal preparation remains about 9.9 ms and is secondary.

### Work, strips, culling and remaining architectural gaps

| Per-frame work (median unless stated) | A | B |
| --- | ---: | ---: |
| gx_walk_bytes | 2,996,928 | 543,200 |
| position_references | 195,296 | 201,203 |
| position_transforms | 128,710 | 132,776 |
| normal_transforms | 0 | 156,075 |
| light_evaluations | 0 | 389,180 |
| light_hits | 0 | 45,128 |
| prepared_parts | 0 | 189 |
| unprepared_parts | 187 | 159 |
| culled_groups | 0 | 3 |
| culled_primitives | 0 | 5,592 |
| clipped_triangles | 1,311 | 1,463 |
| local_position_refs | 0 | 4,776 |
| general_position_refs | 0 | 196,427 |
| intact_strips | 0 | 10,412 |
| reconstructed_strips | 8,387 | 0 |
| strip_clip_fallbacks | 176 | 192 |
| hardware_cull_op | 0 | 153 |
| hardware_cull_pt | 0 | 0 |
| hardware_cull_tr | 0 | 81 |
| pvr_calls | 188 | 344 |
| pvr_bytes | 2,471,456 | 3,574,688 |

B commits 10,411-10,428 qualified visible strips intact per frame, with zero
reconstructed qualified strips and 192 depth-qualification fallbacks. Its OP
headers configure hardware culling for 153 parts and TR for 81. These are submitted
header states, not a claim that hardware counters prove every culled pixel.
PT remains unqualified/unused; graded masks are not silently made binary.
CPU cull counts exclude faces now rejected by PVR and are not directly comparable.

The compact source-backed plan partition is full at 32,768 bytes. B still walks
543,200 GX bytes/frame in uncovered paths. Its dense local-slot subset covers
only 4,776 of 201,203 references (~2.4%); it is not the historical R3v working-set
representation. The current prepared source-light structure selects/copies source
lights but does not yet supply all invariant preparation and reuse of D349's
inputs. Static-light cache hits are zero. Do not claim that these contracts are
fully transplanted merely because functions with historical names are linked.

**Next implementation is still the integrated stack:** finish the asset/frame/
material-light input contracts so visibility and bounded batch-local preparation
feed shared positions/normals, prepared selected lights and native packet assembly
without repeated corner work. Use the measured lighting, packet preparation and
transform spans to judge whether that whole system now behaves like D349. Keep
source backing, owner generations, seam identities and current source state.
Do not add another whole-geometry copy, source-heap cut, queue expansion, renderer,
per-feature target acceptance sequence, skinning project or prelit quality arm.
Submission is about 10 ms here; new store-queue/DMA work is not the priority.
PRFC1 can later diagnose the dominant native stage; TMU2 remains the timing source.

### Queue and residency corrections required for the integrated run

B directly submits 176 OP parts/frame. Deferred work is 78 masked and 8 blended
parts, no depth-only entries: 22,592-22,880 masked bytes and 2,592-2,656 blend bytes.
The high-water range is 25,184-25,536 of 26,624 effective model bytes (at least 1,088
bytes spare), without growth during the window. View snapshots use 15,712-16,064
bytes, selected light sets 5,920, light-state records 3,264 and basis 288. UI uses
1,872-1,976 bytes within its reserved 8 KiB lane. Queue pressure is primarily masked
source ordering, not opaque work waiting for a TR drain.

The previously accepted 8 KiB reassignment remains inside the existing 64 KiB native
slab: 24 KiB packet storage,8 KiB deferred spill and 32 KiB compact metadata. No source
capacity is removed. The shared texture cache had a separate demonstrated limit:
64 simultaneously pinned handles could not serve the70-texture working set.
Rebalance existing static metadata to 80 handles and 128 source-key entries
(previously 64/256). At the measured B layouts (160/36 bytes), this removes 2,048
static bytes rather than increasing the metadata budget. Evicted lookup entries
still resolve through the existing archive-owner path; no second cache is added.

| Measured memory | A | B |
| --- | ---: | ---: |
| Source heap free after required room/block/enemy loads and in window | 66,592 | 66,592 |
| Native packet/metadata slab | 65,536 | 65,536 |
| Resident texture VRAM | 3,276,800 | 3,682,304 |
| Observed texture VRAM loading peak | 4,192,256 | 4,192,256 |
| Pinned textures / pinned VRAM bytes | 57 / 3,268,608 | 70 / 3,674,112 |

B has 28,160 more linked text/data/BSS bytes than A. Each loaded texture retains 144
bytes of package metadata (71 B resident handles including the unpinned texture).
Allocator bookkeeping/fragmentation and total native heap/stack peaks are not
fully measured by these counters; do not call this a complete RAM peak report.
No new source-archive bytes are recovered by this renderer slice.

### Focused corrections, checks and negative results

- Reuse of `prepare_model_pairs`, qualified source texture identities and native
  packages supplied nine missing color/mask pairs (308,496 transport bytes).
  The ten original fixture pairs remain. No new converter/backend or restored
  source texel payload was introduced.
- D354v4's PRFC0 clock was inactive: its zero stage readings are invalid. V5 onward
  reads the actual pinned TMU2 timer without configuring a performance counter.
- V5 had 46 no-slot requests per settled frame despite zero uploads. It is rejected
  as a complete workload. V6 fixes the common cache metadata budget and serves all
  resources, but A/B source counters differ by one pregame tick. All 90 captured
  room states match at offset one; this was not relabeled an exact-tick pair.
- The existing pad fixture now optionally uses `clock source`, retaining retrace
  scheduling by default. It reads `pG->Frame_cnt`; it never resets counters or
  forces states. V7 exposed CRLF parsing and was stopped by the coordinator.
  The parser accepts CRLF/trailing whitespace, with an actual-parser host check.
  V8 retains the same fixture in both arms and removes periodic thread dumps.
  Three optional logo-skip requests time out; card/menu/New Game inputs are
  delivered normally at the same source ticks, including final START at 2309.
- Native model host checks cover real build configurations, seams, randomized
  geometry, clipping, strips and sanitizer paths. Native stream/UI checks cover
  deferred ownership, spills, texture pins/failures and source-key-cache eviction.
  New profile checks cover exclusive nesting, same-stage scopes, counter wrap
  and publication; new pad checks cover both clocks, hold/state/timeout and CRLF.
- B skips only the two CPU-consumed post-skin writebacks. Pinned KOS `ocbwb`
  writes back without invalidating, so no cache-eviction benefit is claimed.
  Shared PPC preprocessing is unchanged for those source spans; a new full
  ProDG object comparison has not been run.

Older owned diagnostic discs (through v7) are preserved as verified xdelta3
against untouched D351c `game.bin`; each `disc-compression.json` records base and
reconstructed hashes. Restore before launching their cues. V8 discs remain whole.

Final images show source-controlled Leon/handgun, forest/cabin and HUD. B's masks
and illumination differ from A; sky/material/fog quality and full character/enemy
coverage remain unaccepted. Final images are at different end ticks, not a pixel
comparison fixture. No audible-output, manual input responsiveness, encounter,
transition/retry or physical-hardware acceptance is claimed. Keep the candidate
selectable and unpromoted; carry these limits into the continuing integrated work.


## D355 - shared preparation audit and bounded candidate (2026-09-22)

Five matched source ticks **2382-2386** qualify the unique-input audit: all 1,310 part records have matching reference counts and two order checksums in the actual native-model host fixture. Later logs have transport gaps and/or pose-dependent replay differences; they are not silently counted as full-window evidence. SH-4 CPU times below are target TMU2 spans, not host timings. The host replay has four packet-count differences at clipping/precision boundaries against SH-4 at tick2382; the source reference-order checks still match. This is preparation evidence, not a pixel-equivalence claim.

| Per frame | Observed work | Distinct qualified inputs |
|---|---:|---:|
| Positions | 201,203 references; 132,776 transforms | 70,118 |
| Normals | 201,203 references; 156,075 transforms | 82,717 |
| Lighting | 156,075 vertex evaluations; 389,180 individual-light evaluations | 100,531 position/normal pairs; 100,531 complete lit-input keys |
| Selected lights | 262 list builds | 115 model/info-scoped list states |
| Packet preparation | 129,284 direct-strip pack calls | 127,896 render-input identities, including rejected work |
| Submitted PVR | 111,376 vertex records at tick2382 | Not the same population as pre-cull prepared inputs |

UV/normal/color seams remain separate. Position keys include source instance/info, pose backing, stride/scale, transform, projection and viewport; normal keys include backing and current normal matrix. Lit keys additionally include selected light values, channel/ambient/material/diffuse/attenuation/TEV state and required source color identity. Position-dependent attenuation forbids treating normal identity alone as a lit-input identity. In this window vertex-color/channel distinctions add no pairs, but the adapter must still handle them.

There are 105 source models. Prepared lights average 3.000 per part build, maximum 7; averaging each model's part samples first gives 2.733. These are source-selected lists, not nearest-light or fixed-light approximations.

Per-part distinct totals are 71,537 positions, 83,650 normals, 101,481 lit inputs and 127,912 render inputs. Reuse across parts/passes therefore accounts for 1,419 positions, 933 normals, 950 lit inputs and only 16 complete render inputs. Most repeated preparation is within parts/strips. This does not establish the same working-set locality as the historical offline clustered room.

Top ten by each exclusive CPU stage (mean microseconds over the five qualified ticks). Addresses identify the exact source instances/parts in the private RAM fixture; model kind 0 is player, 1 enemy, 2 scenery. Separate instances of a shared part remain separate transforms.

### Models

| Rank | Transform / project | Lighting | Packet preparation |
|---:|---|---|---|
| 1 | 0x8cbcf200 (kind 0): 30,349.8 | 0x8cbcf200 (kind 0): 50,473.2 | 0x8cbcf200 (kind 0): 32,004.2 |
| 2 | 0x8cbe9aa0 (kind 1): 22,924.8 | 0x8cbe9aa0 (kind 1): 37,590.4 | 0x8cbe9aa0 (kind 1): 23,975.6 |
| 3 | 0x8cf99050 (kind 2): 13,867.6 | 0x8cf7de90 (kind 2): 21,653.2 | 0x8cf99050 (kind 2): 14,675.0 |
| 4 | 0x8cf7de90 (kind 2): 13,860.8 | 0x8cf99050 (kind 2): 21,646.4 | 0x8cf7de90 (kind 2): 14,372.8 |
| 5 | 0x8cf7b148 (kind 2): 12,956.0 | 0x8cf65a58 (kind 2): 20,689.6 | 0x8cf7b148 (kind 2): 14,046.4 |
| 6 | 0x8cbe8f18 (kind 1): 11,542.4 | 0x8cf8d3d8 (kind 2): 20,192.2 | 0x8cf7e268 (kind 2): 11,519.8 |
| 7 | 0x8cf7e268 (kind 2): 10,821.4 | 0x8cf7b148 (kind 2): 19,620.2 | 0x8cf98c78 (kind 2): 11,499.0 |
| 8 | 0x8cf98c78 (kind 2): 10,803.8 | 0x8cf7e268 (kind 2): 17,884.2 | 0x8cbe8f18 (kind 1): 11,148.4 |
| 9 | 0x8cf984c8 (kind 2): 10,656.0 | 0x8cbe8f18 (kind 1): 17,045.4 | 0x8cf984c8 (kind 2): 11,113.2 |
| 10 | 0x8cf8d3d8 (kind 2): 9,745.2 | 0x8cf98c78 (kind 2): 16,114.8 | 0x8cf65a58 (kind 2): 10,191.2 |

### Batches (model / source part)

| Rank | Transform / project | Lighting | Packet preparation |
|---:|---|---|---|
| 1 | 0x8cf99050 / 0x8c838e00: 13,867.6 | 0x8cf7de90 / 0x8c838e00: 21,653.2 | 0x8cf99050 / 0x8c838e00: 14,675.0 |
| 2 | 0x8cf7de90 / 0x8c838e00: 13,860.8 | 0x8cf99050 / 0x8c838e00: 21,646.4 | 0x8cf7de90 / 0x8c838e00: 14,372.8 |
| 3 | 0x8cf7b148 / 0x8c801440: 12,956.0 | 0x8cf8d3d8 / 0x8cc910a0: 20,192.2 | 0x8cf7b148 / 0x8c801440: 14,046.4 |
| 4 | 0x8cbe9aa0 / 0x8ca65b00: 11,092.0 | 0x8cf7b148 / 0x8c801440: 19,620.2 | 0x8cf7e268 / 0x8c84c720: 11,519.8 |
| 5 | 0x8cf7e268 / 0x8c84c720: 10,821.4 | 0x8cf7e268 / 0x8c84c720: 17,884.2 | 0x8cf98c78 / 0x8c84c720: 11,499.0 |
| 6 | 0x8cf98c78 / 0x8c84c720: 10,803.8 | 0x8cbe9aa0 / 0x8ca65b00: 17,700.4 | 0x8cf984c8 / 0x8c84c720: 11,113.2 |
| 7 | 0x8cf984c8 / 0x8c84c720: 10,656.0 | 0x8cf98c78 / 0x8c84c720: 16,114.8 | 0x8cbe9aa0 / 0x8ca65b00: 10,725.0 |
| 8 | 0x8cf8d3d8 / 0x8cc910a0: 9,745.2 | 0x8cf984c8 / 0x8c84c720: 15,878.0 | 0x8cf8d3d8 / 0x8cc910a0: 10,001.8 |
| 9 | 0x8cf84bc0 / 0x8c81a800: 9,080.6 | 0x8cf988a0 / 0x8c7f1840: 14,104.2 | 0x8cf8aa68 / 0x8c81a800: 9,784.8 |
| 10 | 0x8cf8aa68 / 0x8c81a800: 9,076.8 | 0x8cf831b0 / 0x8c7f1840: 14,094.4 | 0x8cf84bc0 / 0x8c81a800: 9,746.2 |

### Implementation and current qualification

The existing part-local position/shade preparation has a shared model/frame alternative inside the same native-model adapter. It borrows **12,288 bytes from the existing packet scratch**, retaining the 64 KiB slab, 32 KiB draw metadata and 8 KiB queue spill; packet scratch becomes 12 KiB. No source heap or queue growth. Exact source-state changes and frame/owner invalidation reset dependent values. Normal preparation is separate from position and lit-pair identity. Prepared lights are shared across compatible parts; packed RGB is lazy and remains a candidate rather than accepted quality/performance policy.

Packed validity includes the current source transform/pose generation, normal matrix, selected light contents and order, source channels, ambient/material source and values, diffuse/attenuation, TEV scale and actual mutable vertex-color value. Alpha and UV remain separate live packet inputs. Synthetic checks cover changed channel/color/normal/light inputs and frame reuse.

The v2 collision-chain map reduced transforms to 124,060, normal transforms to 128,006 and lighting calls to 147,287, with 114 light builds versus 262. However, slot retirement/lookup overhead increased instrumented render p50 to about 2,318 ms. **Negative result; not a performance promotion.** It retained source heap 66,592 bytes, no new texture uploads, and no post-warm-up aborts in the sampled window. The run did not hang: sparse console logging was initially misread; completed-frame telemetry continued normally.

V3 completed with bounded four-way keyed slots and lazy packed RGB, but remains
obsolete under the user's correction. Do not tune its lookup or promote it. The
next integrated candidate uses load-time dense local indices and generation-tagged
arrays, matching the R3v/R3x preparation boundary. Full target qualification of
that replacement is recorded separately as D356.

Largest captured source strip is 105 vertices, below the new 383-vertex packet capacity. This predicts no capacity-induced strip fallback, but target flush/PVR-call/fallback deltas still govern acceptance. Do not infer unchanged packet cost merely from that bound.

Private evidence: `C:/Flycast-Evidence/re4-dreamcast/d355b-reuse-audit` and `d355v2b-integrated-stack`; both discs are preserved as verified xdelta3 against the recorded D351c base. D354v8 B remains whole. Audit recipe/scripts and exact source snapshots are under `/root/probe/d355-*`; the captured evidence includes `reuse-report.json`, RAM, sealed views and executable/asset/tool identities. The obsolete v3 target recipe used `/root/probe/d355v3-build-arm.sh` and `d355v3-prepare-arm.py`; do not overwrite completed artifacts.


## D356 - dense local indices, measured admission limit (2026-09-22)

Keep the integrated candidate default-off and intact, but **do not promote its
performance**. D356 replaces the rejected keyed hot-loop cache with asset-bound
local indices and generation slots in the existing shared preparation workspace.
Prepared-light reuse extends across compatible source part boundaries. Source
pose, normal matrix, selected lights, channels, material/alpha and order remain
authoritative; there are no fixed-light or gameplay substitutions.

### Reproducible full-stack comparison

D356v4 A/B completes **85 identical recorded source snapshots**, ticks 2382-2466,
native frames 2383-2467, presentations 2349-2433. All measured windows have zero
discarded frames, queue drops, native allocation/texture failures or post-warm-up
uploads, with contiguous observed IDs. Warm-up excludes the first 32 model frames;
the existing startup discard/allocation-probe history is not erased. The source
snapshot covers player/camera/motion and selected system/room flags, not every
enemy/RNG state. The fixture remains a settled opening view, not combat acceptance.

| Matched instrumented measurement | A recovered baseline | B integrated stack |
| --- | ---: | ---: |
| Render wall p50 / p95 | 1192.463 / 1195.034 ms | 1948.184 / 1950.040 ms |
| Presented interval p50 / p95 | 1220.280 / 1222.786 ms | 1973.462 / 1973.474 ms |
| Source heap free | 66,592 B | 66,592 B |
| Native slab | 65,536 B | 65,536 B |
| Texture VRAM / peak | 3,276,800 / 4,192,256 B | 3,682,304 / 4,192,256 B |
| PVR calls / submitted bytes, median | 188 / 2,471,456 | 470 / 3,578,720 |

B's exclusive median TMU2 stages are lighting 759.753 ms, packet pack477.745 ms,
transform/project 417.505 ms, clip fallback160.405 ms, topology 48.552 ms,
model setup 13.222 ms, visibility 0.990 ms, texture resolve 1.006 ms/upload 0,
OP submission 9.023 ms/PT0/TR0.940 ms, TR enqueue 6.803 ms/drain 2.162 ms,
UI enqueue 0.113 ms/drain 0.136 ms and other 47.708 ms. Stage medians need not sum to
the median total. Presentation fence 20.226 ms and asynchronous PVR render ~7.503 ms
are separate intervals and must not be added to CPU spans. Source pose preparation
remains about 9.918 ms. Do not optimize skinning next.

There are 552,808 /975,486 median clock reads. Empty-scope overhead estimates are
185.450 /338.219 ms; do not subtract them as exact corrections or call these
instrumented results release FPS. A still lacks B's selected lighting/material
coverage, so this is a matched source-state diagnostic, not equal visual coverage.
Both final images were inspected: source-controlled Leon/handgun, cabin/forest
and HUD are visible with the corrected rear-facing view. The user subsequently accepted candidate B's current appearance as accurate
for now and stopped the visual-gap investigation. Keep B as the accepted visual
baseline for this continuing performance work; no lighting/material redesign is
authorized by A/B brightness differences. This does not promote its performance.
End captures are at
different ticks, no enemy is visible in this view, and they do not certify complete
characters through unexercised poses, audio or manual responsiveness.

### Reuse coverage and bounded-memory failure

Per measured B frame:200,643 position references;132,787 position transforms;
155,777 normal transforms;387,269 individual-light evaluations. Dense local slots
cover only **2,970 references (1.48%)**, versus 197,673 general references. The shared
state boundary records 263 parts,126 position/normal state builds and 137 state
hits each,**114 light builds /149 light-build hits**,22 position/normal/shade
batch activations,127 dense normal hits and 2,036 dense packed colors. The older
D355 audit retains unique-input and top-ten tables; those distinct counts are
not relabelled as a new D356 audit.

Structural coverage is 209 prepared /140 unprepared live part submissions and
841,824 fallback GX bytes walked per frame. Final metadata fills 32,768 bytes:
8 KiB entry table,16 KiB structural/bounds partition,8 KiB local mappings. It contains
239 tracked streams,132 structural plans,107 stable negatives and 4,748 raw bound
bytes. No steady owner misses or invalid plans were observed. Native source heap
capacity and queue capacity did not change.

Final local mappings fill**8,192/8,192 bytes** (early8,128 reporting was superseded):
12 source parts,2,872 encoded corners,2,305 pairs,22 batches;7,978 payload bytes
and 214 alignment bytes. This is source-asset data, not live instance-weighted work.
The existing whole-part allocator rejects large useful parts even in an empty
partition: stream 8c83af60 needs 16,268 B;8c84e880 needs 12,147 B;8c8035a0 needs 14,764 B.

Reconstructing the current encoding across the239 tracked streams gives 111,515
source corners,94,127 pairs and 737 batches, requiring**314,429 bytes** before
alignment. Formula:12/part + 16/batch + 2/pair + 1/corner. This is not a request to
allocate314 KB. It demonstrates why an8 KB copied local-ID companion cannot
provide broad prepare-once reuse. Merely changing first-fit order is insufficient.
Independently generated LocalBatch domains also invalidate slots on domain change;
matching source state alone does not yet share vertex values across those domains.

A read-only exact-index check finds136/737 batches (12,935 source corners) can
use implicit source ranges instead: position/normal spans each fit160 slots,
and one index uniquely determines the complete position/normal/color identity.
Their33,611 B corner/pair payload could become compact range/mode descriptors.
None of the three largest examples qualifies under the current batching. This
is an unimplemented coverage opportunity, not a target speedup claim. Continue
the same source-backed asset/batch representation and generation slots; do not
grow source heap/queues, revive a keyed cache, or disguise the admission gap with
prelighting/SH4ZAM. Preserve whole strips and draw order when qualifying batches.

Packet workspace is 12 KiB versus D354's24 KiB, with a383-vertex capacity and observed
maximum source strip 105. B records 212 packet flushes and ~470 PVR calls/frame
(D354 B ~344 calls), recording the current transport/flush cost with the smaller packet area.
Strip fallbacks are 171 versus the older192, with 1,184 clipped triangles;10,411-
10,428 strips remain intact, zero reconstructed strips. Hardware culling applies
to 153 OP and 81 TR submissions; PT has no submissions in this fixture. These
revision differences do not isolate packet capacity as the only changed cause.
Queue high-water25,536 remains below 26,624 (masked 22,880, blend 2,656 at medians).

### Loader correction shared by both arms

D356v3 B never reached rendering: em/em23.drs request 32 was pending in PUSH,
pCur_queue still pointed to that slot, and both DVD workers had stopped. Saved
headers described completed em12. The synchronous source blockRead borrow could
restore a completed/recycled request after native filesystem I/O yielded.

Commit f2ed3dc extends the existing native DVD owner across blockRead header
save/use/restore and ReadProc completion publication. Same-thread Read steps
nest; foreign pumps yield without holding IRQs across I/O. Restore checks the
request ID/live/unpublished state; completion clears only its own current pointer.
Scopes end before task exit. No source flags or em23 loading are bypassed.
The actual-body regression fixture passes -O2 and ASAN/UBSAN scheduling/reuse/
header-lifetime cases. PowerPC preprocessed tokens match the pre-slice source;
full ProDG comparison was not rerun. Both v4 arms now load em23 and render.

### Identities and disposition

Private evidence: C:/Flycast-Evidence/re4-dreamcast/d356v4[a|b]-integrated-stack;
matched report: d356v4-comparison.json. Each arm retains its ELF,disc,source overlay,
owned-source snapshot,asset/fixture manifests,toolchain/capture identities,logs,RAM
and menu/final images. Recipes: /root/probe/d356v4-build-arm.sh and
d356v4-prepare-arm.py; report helper: C:/Game Dev/Emulators/re4-session-scripts/
d356v4-report.py. Admission inspection: /root/probe/d356v4-admission-review.md.

Base is e698b98 plus the preserved working overlay (not a clean-HEAD build).
Both use /root/probe/d343-mirror and /root/probe/d354v7-fixtures; matching selected
input manifest SHA256 a78cb8af57acf76d8ee27610bee1e9a8072f0eca7d43761cd6ceb1a1e474e3b2; fixture manifest 76e6289eb9f1b84e36aa08582e2ff10fd29a1287cb6b1e4209202c149f427708.
SH GCC 15.2.0; KOS 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3 with the recorded
pinned patch; KOS library f5b2f71970dabd1d51199bc77e11102fb63c80765ef7ccac334db9208139b9ca.
Flycast 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a.

A ELF 4c71d4d52e8eeba66915c48379755e76283f01a1743d5843c8b2948599743d36;
B ELF ac75515e925c89b60c544e92b0bd744504ff0d163d9e0c4f5c7ccf2170b82dba.
ELF text/data/BSS: A2,324,384/78,236/621,304; B2,352,576/85,480/622,232.
No additional source archive/animation recovery. No physical-hardware acceptance.
Keep the loader correction; preserve the integrated renderer as an unpromoted
candidate and correct its insufficient dense coverage. The three-room goal,
manual combat, full presentation/audio, event activation and retry remain open.

## D357 - source-backed spans and historical input-contract audit (2026-09-22)

D357v3 now completes 78 matching recorded source snapshots/ticks
2387-2464. Both arms have zero measured discards/queue drops,
native allocation/texture failures and warm uploads, with queue high-water below
capacity. Render p50/p95: A 1,211.301/1,213.904 ms,
B 1,971.792/1,973.605 ms; presentation p50:
A 1,236.963 ms, B 2,006.830 ms.
This is an instrumented settled-view comparison, not release FPS, full source/RNG
parity, manual combat or hardware acceptance. A remains material/lighting limited;
B retains the intended richer source presentation. The complete candidate stays
default-off and performance is not accepted.

The current legal span representation replaces persistent corner maps with
20-byte descriptors, references the original immutable streams, and uses the
same160-slot/12-KiB preparation workspace and8-KiB local arena. Partial admission
ranks descriptors within a part; all source seams, whole strips/fans and reference
fallback remain. Focused optimized/sanitizer checks pass; the captured262-part
host fixture retains40,374 expanded triangles and byte hashes with regenerated
unbounded metadata. That host result is not bounded target coverage.

The first D357 B failed native texture-metadata allocations and did not complete
warm-up; its A was packaged but not run. Resident executable growth was11,732 B,
including optional detailed audit and duplicated count/admit installation walkers.
Sharing one non-template walker saved4,038 B with the same algorithm, budgets,
compiler policy and passing focused checks. V3 completes the valid comparison.
No source-heap capacity was cut to obtain it.

Steady B:200,643 source position references,133,147 transforms,155,195 normal
transforms and387,402 individual-light evaluations. Dense position references
25,985 (12.95%), normal27,212 (13.56%), shade27,301 (13.61%). Light builds114,
reuse149; channel states126 each, state reuse137;725 batch activations,755 normal
hits and 17,889 cached color packs. Packet flushes 212 and strip fallbacks 171 are
unchanged from D356v4;470 PVR calls,3,578,720 bytes. Source free66,592 B, native
slab 65,536 B, local metadata8,192 B, texture VRAM 3,682,304 B, peak 4,192,256 B.
The preparation snapshot's two added counters account for32 B across live/sealed
statistics; no metadata-budget growth. Light/transform/pack cost remains dominant.

`/root/probe/d357v3-current-fallback-report.json` ranks current whole-part spans.
Complete current witnesses 2382/2385/2386 each have263 sealed parts (789 total).
2383/2384 each lack two records and are excluded. Historical D355 had262 parts
and ordered-reference qualification fails; it is explicitly not current state
parity. Among complete current witnesses,167 fully general-position parts have
159,163 references; their mean total transform/light/packet spans are
380.831/607.262/371.068 ms.30 parts are mixed and66 all-local. These are costs of
parts classified by position coverage, not isolated fallback-only timers.
Highest examples include enemy0x8cbebf20 (10,798 general references), player
0x8cbd1680 (7,217 general +5,250 local), scenery0x8cf8f858/part 0x8cc93520
(6,246 general), and two instances of part 0x8c83b280 (6,046 general each).
Addresses are current-run identities, not persistent asset IDs. Full top-model/
part rankings are retained privately; do not generalize them across executables.

### What commit history says is still missing

- `21586f8` (R3v) prepared dense remaps for up to1,024 unique slots, with413,696 B
  in tables/workspace. Current160-wide original source-index spans can fail even
  with few distinct indices. Full remapping is a historical memory assumption,
  not a cheap mechanism overlooked in the new code. Classify top streams before
  claiming metadata reorder alone can solve their coverage.
- `fcf9bf5` gave strip visibility16,384 prepared spheres (262,144 B);
  `1e15ee5` reused group visibility across passes. Current early tests in
  `native_model.cpp` precede vertex work correctly where bounds exist, but
  `native_draw_plan_owner.cpp` makes structural admission a prerequisite for
  bounds/local metadata. A negative structural entry loses all three mechanisms.
  Prioritize independently affordable conservative group bounds in the existing
  ownership/budget, with source position/owner lifetime validation.
- Current source registration admits actors then scenery in OT order. Local
  descriptor ranking occurs inside each part only. Earlier lower-benefit parts
  can consume capacity before expensive later streams. Adapt the existing
  asset-update admission to visible work value without changing source draw order,
  adding persistent corner maps, heap cuts, metadata growth or frame-hot lookup.
- Historical `5f42caa:room/main.cpp` `prepare_room_static_lighting`/`light_room_vertex`
  retained unclamped invariant contributions and added dynamic contributions
  before one final clamp. Its45,000 RGB+owner entries cost630,000 B. Current
  `native_ui.cpp` allocates zero bytes to the previously ineffective tiny cache;
  active dense shading is frame/batch reuse, not equivalent room-lifetime reuse.
  `gx_stub.cpp::GXLoadLightObjImm`/`SourceLighting` omit original light identity,
  world/camera provenance and pre-camera change generation. Adapt the existing
  source lighting publication/owner boundary before retaining bounded static
  partial contributions; current evaluator clamps/material-scales internally and
  cannot simply cache its final result as a partial sum. World-space alone does
  not certify immutable lights, channels, colors or model selection. This is an
  equivalent source-lighting optimization, separate from PS2 visual substitution.
- `PreparedModelBatch::activate` resets all channel generations when a descriptor
  changes even if some domains remain identical. This is secondary: R3v itself
  reset per batch and accepted604 extra cross-batch transforms. Do not invent
  global reuse or rerank it above measured uncovered work.

Already present: native FTRV/compiler policy, prepared selected-light records,
one-pass final packet preparation, intact qualified strips, hardware facing/cull,
source owner generations and direct/deferred native list mechanisms. `26b4442`
(R3x) and `ee8d3e8` packet mechanisms are substantially reused. Do not rebuild
these or claim D349's approximately49-ms historical workload predicts current
cost. Keep the full integrated stack as the acceptance unit.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d357v3[a|b]-integrated-stack` and
parent `d357v3-comparison.json`; exact executables, asset/fixture identities,
source overlays, SDK/emulator and capture tools are pinned per arm. Recipes
`/root/probe/d357v3-build-arm.sh` / `d357v3-prepare-arm.py`; report
`C:/Game Dev/Emulators/re4-session-scripts/d357v3-report.py`.
TMU2 spans include scope/preemption overhead; no estimated overhead is subtracted.
PVR render and presentation intervals remain separate and are not added to CPU.
No full gameplay/audio/transition/retry or physical-hardware acceptance is claimed.

## D358 - global admission and remaining reuse gap (2026-09-22)

The simultaneous history review remains the architectural guide; this is the
same default-off integrated stack, not a separate renderer experiment. The
complete D358v2 A/B has 78 matched recorded source snapshots/ticks
2387-2464, zero measured native discards/queue drops,
allocation/texture failures and warm uploads, and a bounded queue. Instrumented
render p50/p95: A 1,211.301/1,213.904 ms,
B 1,972.755/1,974.568 ms. Presentation p50:
A 1,236.963, B 2,006.830 ms.
There is **no meaningful performance improvement over D357v3 B**. Keep the full
candidate intact and default-off; increased dense coverage is not acceptance.

The source OT adapter now finishes admission after its complete registration
walk. It reuses the existing local-span walker and 8-KiB arena: a bounded
256-record installation heap ranks gross source reuse times source-instance
registrations, then compacts into source-backed descriptors in place. The
existing entry's reserved byte stores saturated demand; no record, metadata,
workspace or source-heap budget grows. Runtime lookups still use direct source
index subtraction and generation slots. Stable frames neither reparse nor
readmit. Demand is an installation snapshot, not camera-adaptive reranking.
The final 256-descriptor cap can leave space unused: this is not maximal packing.

D358v2 steady metadata: 5,984/8,192 local bytes, total 30,560/32,768, installation
peak 32,768; source free 66,592; native slab 65,536; texture VRAM 3,682,304,
peak 4,192,256. Packet flushes 212, strip fallbacks 171 remain unchanged.

| Work per steady B frame | D357v3 | D358v2 |
|---|---:|---:|
| Source position references | 200,643 | 200,643 |
| Dense position references | 25,985 (12.95%) | 68,397 (34.09%) |
| Actual position transforms | 133,147 | 133,111 |
| Actual normal transforms | 155,195 | 154,396 |
| Individual-light evaluations | 387,402 | 384,223 |
| Dense normal/shade references | 27,212 / 27,301 | 70,071 / 70,071 |
| Prepared light builds / reuse | 114 / 149 | 114 / 149 |
| Batch activations | 725 | 991 |

The key remaining contract is **incremental reuse**, not dense routing. Existing
fallback positions and complete position/normal/color lighting use 64-slot tables
for the lifetime of a Builder. Those tables already survive strips, flushes and
UV retries. Dense descriptors replace those lookups and invalidate all three
channels when their domain changes; the two paths do not share populated slots.
The admission score counts gross repetition and does not subtract existing
fallback hits. More selected spans can therefore mostly replace existing hits
and can also lose cross-domain reuse. Current counts support that concern but
do not yet attribute the 36 saved transforms to exact hits/losses.

Counter limits: normal_hits counts normal reuse only after a shade miss;
color_packs counts only dense lazy packing, excluding the general packing branch.
Their 755->97 and 17,889->40,669 changes do not prove lost total normal reuse or
increased total packing. Do not optimize those raw counters as totals.

**Next bounded check:** reuse the captured-source replay/fixtures to classify
references as hit-in-both, dense-only hit, fallback-only hit or miss-in-both,
separately for positions and complete lit identities. Use actual installed
admission and preserve descriptor resets, clip fallback/retry and source state;
count both packing branches. Then correct lifetime/batch admission inside this
same integrated stack. Do not start a fourth cache, revive R3s hot keyed lookup,
or require separate target promotion for subfeatures.

The prior bounds hypothesis is deprioritized by the current source snapshot:
of 105 qualified boundless instances, only 4 (97 references,0.761ms whole-part
CPU) conservatively reject. Preserve current primitive bounds rather than
spending their budget on this low-yield settled-view opportunity. Source stream
classification remains at /root/probe/d358-stream-classification.json/.md.
Historical invariant room-light reuse is still missing: restore original light
identity/provenance/change generations before retaining unclamped partial sums.
This remains separate from the authorized but gated PS2 visual-profile phase.

Initial D358 B is an explicit failed run: +1,944 resident text bytes over D357v3
exhausted native texture-metadata headroom. Its A was packaged, not run. Reusing
the recovered game's already-linked qsort for cold descriptor ordering removed
2,636 bytes of template sorting code; v2 text is 692 bytes below D357v3 B. Source
heap capacity, compiler policy and hot arithmetic are unchanged. Initial D358
and completed D357v3 discs are SHA-verified xdelta3 archives with captures/logs
retained; accepted D356v4 B remains whole. Never benchmark failed startup.

Focused host tests pass: actual owner with 460 competing spans -> 256 exact
compacted descriptors; late/repeated source demand; unchanged source bytes;
leased reset/reused owner; no stable-frame redecoding; visitor/bridge ordering;
actual native-model fixture. Owner and span/admission checks include sanitizers.
This qualifies structure/lifetime, not gameplay or hardware. B final framebuffer
was inspected and retains the user-accepted outdoor room/Leon/HUD presentation.


The matched window is explicitly 2387-2464, with consecutive native and presented
records in both arms. A's longer unmatched tail lacks the observed source 2494 /
native 2495 / presentation 2461 record; retain the whole-arm continuity gate as
false. The matched-window gates are separately true. A missing observation is
not evidence of a dropped game frame, and is not silently removed from the raw
report. The accepted window contains no such gap.

Current detailed audit has complete 263-part witnesses 2382/2384/2386; missing
records in 2383/2385 are excluded. Private current-work-report.json retains top 10
model/part CPU rankings and counter limits. Against D357v3, 1,308 common records
match source-reference counts and both ordered-index hashes with zero mismatches;
this does not establish full pose/light/source-state parity. Two instances of
part 0x8c83b260 still cost 53.664/53.152ms whole-part transform/light/packet time,
each with 5,202 general-position references. Part0x8c8038a0 costs 49.317ms with
5,682 general references. These are current-run addresses and whole-part spans,
not asset IDs or isolated fallback-only costs.

Evidence: C:/Flycast-Evidence/re4-dreamcast/d358v2[a|b]-integrated-stack and
parent d358v2-comparison.json. B ELF
87ceb9422c1f5afe8c5f00e600ecf2361d6a4a5fe90bed4330f1a06b7a802723;
A 46930720ccee32338a492462ddbc50fe08e3e2b426fcd88c17cb076da7a52ed1.
Recipes /root/probe/d358v2-build-arm.sh and d358v2-prepare-arm.py; existing report
adaptation C:/Game Dev/Emulators/re4-session-scripts/d358v2-report.py. Each arm
pins executable/disc/assets/fixture/toolchain/emulator/capture and source overlay.
HEAD 4e45b76 alone does not reproduce these dirty integration executables.
TMU2 spans include instrumentation/preemption; no estimated overhead is removed.
Page-flip/GPU intervals are separate. This is settled-view Flycast evidence,
not full RNG/enemy-state parity, manual encounter/audio/retry or console approval.
