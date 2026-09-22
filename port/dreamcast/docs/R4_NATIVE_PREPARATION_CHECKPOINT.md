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
