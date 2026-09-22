# D350-D351: native strip reuse and prepared draw-plan experiment

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
`/root/work/kos-re4dc-d336`, SH GCC15.2; Flycast SHA256
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
GCC15.2 compatibility, matrix convention/register ownership and numerical-error
checks required. See https://sh4zam.com/ . Do not label current code SH4ZAM-backed
or claim another project's speedup. This does not replace missing preparation,
source material/lighting or event/gameplay connections.

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

Both use KOS `/root/work/kos-re4dc-d336`, GCC15.2, mirror
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
slab: 24 KiB packet storage,8KiB deferred spill and32KiB compact metadata. No source
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
