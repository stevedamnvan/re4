# D316: source primitive lifetime on the native target

2026-09-21; candidate based on d2e1fd5 plus the preserved integration worktree.
D314 remains the first accepted UI presentation checkpoint. D315's stack
correction remains required. This is a storage-lifetime optimization, not restored
cabin gameplay, source-archive recovery, or a performance acceptance.

## Connection and lifetime

Reuse the recovered primInit, GetPrimBuff, SetPrimBuffPtr and primFree functions.
Native builds retain the same nPrim bytes of capacity per frame and the source
allocation-failure fallback, but allocate one frame instead of two. No models,
geometry, animation, collision or gameplay pools are removed.

The source main loop calls Render before SetPrimBuffPtr and ClearOt, then runs
the next TaskScheduler/Trans preparation. Render consumes the old source ordering
tables and prepared position/normal arrays. OT 0x16 is consumed by Render_done
after the current preparation, before the next reset. Source buffer consumers
in trans, shadow, mirror and the primitive/UI callbacks use the current index.

The native draw contract is synchronous consumption of source arrays into copied
PVR packets. The current source-ID consumer already copies quads and resolves
texture handles before returning; presentation does not dereference the old
primitive storage. The existing GPU fence still protects native resource reuse.
A future native 3D/DMA adapter must honor this contract, or select two buffers.
Unbound GX 3D calls do not constitute validation of that future consumer.

The only new interface is native_primitive.h's buffer-count selection/contract.
RE4DC_PRIMITIVE_BUFFERS=2 retains the double-buffer reference. Changing that
compiler define requires rebuilding both game.cpp and trans.cpp; for example
force those prerequisites with make -W ../../../src/game/game.cpp
-W ../../../src/game/trans.cpp and GAME_OPT="-O1 -DRE4DC_PRIMITIVE_BUFFERS=2".
Rebuild the same two prerequisites with default GAME_OPT to restore the candidate.
The PowerPC path is unchanged.

## Measured result and decision

| Metric | D315 | D316 |
|---|---:|---:|
| Title primitive resident bytes | 262,144 | 131,072 |
| r100 per-frame capacity | 319,488 | 319,488 |
| r100 primitive resident bytes | 638,976 | 319,488 |
| Free at failed block request | 107,520 | 427,008 |
| Free at first failed enemy request | 97,216 | 416,704 |
| Free after TexRender allocation | 31,616 | 351,104 |
| ELF text+data+bss bytes | 3,002,132 | 3,002,220 |
| Source heap reservation | 8,464 KiB | 8,464 KiB |

Real r100 heap recovery is 319,488 bytes. The block request (1,126,272) and enemy
request (3,577,728) BOTH FAIL and therefore were not both charged. Their combined
4,704,000 bytes exceed the block-request free memory by 4,276,992 bytes before
allocation overhead and intervening allocations. The remaining deficit is not
merely the enemy allocation's shortfall.

Keep the native synchronous-consumption configuration, with the double-buffer
reference selectable. The source menu remains visible; the same boot-forward
fixture passes subscreen preload and reaches the same r100 failures. No new
fault or primitive overflow appears. Existing ESP_CTRL02 errors remain (219
observations in each 90-second run); do not treat that loop as initialized play.

At native UI frame 1200 the sampled counters match D315: 9,279 drawn, zero
missing/unsupported-common/drops, 40 uploads, 3,946,496 live VRAM and 4,192,256
peak VRAM. This does not measure gameplay FPS. D316a ends at the harness
90.001-second deadline; D315 was 90.005 seconds. Those deadlines are not CPU
frame timings. No physical-console evidence is claimed.

## Evidence and checks

Private D316a: C:/Flycast-Evidence/re4-dreamcast/d316-single-primitive.
Private D316b: C:/Flycast-Evidence/re4-dreamcast/d316b-primitive-ui.
ELF SHA-256: 93a21444e7d025dab54bc7e8ef649a56db90a7f66e91b6f6a7ebb2505540cdf9.
Disc SHA-256: df3c030f35c1da510b3f4d0922767dbee86bba714ed7871539f94dd0d4e70085.
Both contain validated evidence-manifest.json files with exact executable,
disc/assets, fixture, source patch, tools, KOS/compiler and emulator identities.
The source patch preserves inherited changes; the revision alone is not the
full build identity. Original data and accepted captures were not modified.

D316b menu-readback/frames/fb0.png shows Leon/Ashley and the source main menu
with normal colors. It is a sampled title=5/1 image, not an exact tick comparison;
LOAD is still highlighted before the later scripted Up/A selects START.
The existing corrected framebuffer reader was reused. D316a's attempted image
was too late after the harness stopped; its readback failure is retained and no
image acceptance is inferred from it.

The host fixture executes the actual source allocation/reset/free functions in
both buffer modes: full capacity, alignment, overflow rejection, guard bytes,
frame reuse, and allocation-failure fallback. Existing native Package sharing,
upload/failure/fence and image-identity checks pass (four focused tests total).
PowerPC preprocessed tokens for game.cpp/trans.cpp match the pre-slice working
files; this is not a full ProDG comparison. Native link retains five known stubs.

## Continue at the existing resource-to-render boundary

User's cabin-in-recovered-game instruction is the next coherent integration
unit. Connect commonModelTrans/ModelRender source-prepared pose, camera, identity,
selected lights and materials to shared mechanisms extracted from room/main.cpp.
Extend the existing UI frame owner; one PVR scene, no prototype gameplay loop,
no duplicate skinning or renderer. Adapt resource ownership together with this
consumer so source render payload can actually leave its resident allocation.

Required block/enemy creation, event/ARAM/audio storage, inventory qualification
and native module binding remain open. This checkpoint does not defer those
costs or establish archive-loaded == initialized == rendered == playable.

## D317 follow-on: extract the existing native draw mechanism

The subsequent recovered-game build uses room/pvr_geometry.hpp/.cpp, extracted
from the existing room/main.cpp rather than a second backend. The room target
uses the same shared implementation and retains its profiler/digest wrapper.

- Existing begin_pvr_packet and submit_pvr now serve source-driven native UI
  packets as well as the room renderer. UI submits the same header and four
  vertices in one contiguous packet; its scene/fence/hold/black semantics remain.
- Existing clip_projected_triangle, interpolation and shade_color are shared.
  Clip limits and the point-projection callback are explicit caller inputs so
  the recovered camera/model transform can supply them. No actor skinning,
  animation selection, world resource lookup or simulation is imported.
- Existing source prepared positions/normals remain the intended consumer inputs
  at commonModelTrans. That source-model adapter is NOT connected by D317.
  Native world/actor material, selected lighting, fog and ordering remain open.

The actual extracted clipper matches the pinned be32de7 implementation across
10,000 generated triangles times four cull modes (40,000 comparisons), including
near crossings, exact near points, far rejection, degenerates, and output guards.
Packet copy lifetime is checked; three existing native texture/identity checks
also pass. The r100 room main/helper objects compile with its source-scene/480p
profile, without replacing any accepted reference executable or private assets.
The recovered game links with the same five known stubs.

D317 evidence: C:/Flycast-Evidence/re4-dreamcast/d317-shared-native-geometry.
The validated evidence-manifest.json pins executable, disc, fixtures, dirty
source patch, extracted source files, compiler/KOS, emulator and capture tools.
ELF SHA-256: 4741f86a8751210b691078bbe4bf9d67b149b740f439e24ba5e602095855c0e7.
Disc SHA-256: 4da91bdc967b2ab0b0179c0af8229e1ad84509d0bde9e31e1d9c8650f89557ed.

The sampled menu-readback/frames/fb0.png visibly retains the source title/menu;
it is not an exact-tick image comparison. Source START follows the same fixture
and the run reaches the same r100 failures. It ends at the 75.004-second harness
deadline, not a guest fault. UI frame-1200 counters match D316; block/enemy free
values remain 427,008/416,704. ELF text+data+bss is 3,002,348 bytes (+128 versus
D316), BSS and source heap reservation unchanged. No source archive bytes are
reclaimed by this extraction; no gameplay or physical-hardware frame time claim.

Keep the shared extraction as the implementation base. The next connection must
consume source-prepared geometry once, reuse the same texture cache and PVR
owner, and honor source presentation holds. Avoid beginning an immediate world
scene that Render_swap can then leave unfinished when its hold flag is set.
Required resource backing recovery and block/enemy creation remain part of that
integration; this is not the cabin restored.

## D318: source model transport diagnostic, not visible 3D acceptance

The optional /cd/dc/model-diagnostic.flag enables the narrow adapter in the
recovered-game executable. Normal packages without that flag retain D317 UI.
No source state, camera, model placement, event or allocation failure is bypassed.

Connection: commonModelTrans supplies source-prepared rigid/skinned positions,
separate normal identity, BE primitive indices, its actual model-view matrix,
source camera projection and cull/depth state. materialSetup supplies the actual
base texture after source animation/swap selection. New model_bridge.cpp and
platform/native_model.cpp only adapt those inputs to the existing shared clipper,
packet helpers and native_ui texture/frame owner. No second skinning, AI loop,
PVR instance or frame is added. This diagnostic uses base textures without
lighting/fog/material-color parity; separate-alpha/complex materials are rejected.
It is not a fidelity candidate or complete-character claim.

The existing texture builder now accepts source .arc selectors through
le_mirror.prepare_room_archive and the recovered offline decoder. r100 produces
155 unique images with no qualification errors, plus one valid empty SMD palette
at archive offset 451200 (pAddTpl source behavior). The initial exporter error
was zero descriptors, not shared-header conversion; that speculative change was
removed. Existing player/weapon sources produce 36 images. No new encoder or
room decoder was written, and no reference asset/evidence was overwritten.

A 65,536-byte, 32-aligned KOS-owned diagnostic packet queue keeps copied output
valid across source primitive reuse and room-heap resets. Overflow rolls back a
whole part. It is allocated only with the flag, not from the source room heap.
The initial failed run used source-heap scratch; that lifetime hazard was fixed
before this candidate. No source archive backing is reclaimed.

D318d evidence: C:/Flycast-Evidence/re4-dreamcast/d318d-source-model.
ELF SHA-256: 80b4cbbf7e16a999bbdf02ac9ec4e4c896e474b82a9498bf5604da80f8abff54.
Disc SHA-256: fbff3505782592875753d64b5c66a1f9e9173ea4afd09569e109c64bff358949.
The validated manifest includes assets, fixture, dirty patch/new source files,
compiler, emulator and capture identities. Same source title/menu remains visible;
three room textures upload (131072, 16384, 65536 VRAM bytes), freeing their
131232/16544/65696-byte upload allocations. Source heap is 344416 before/after
those uploads. Title cache resources share the existing 4 MiB budget; no new
world cache exists. ELF text/data/bss=2263204/75428/672120, total3010752
(+8404 versus D317). Required block/enemy failures remain 1126272/3577728 with
427008/416704 free: both fail, combined lower-bound deficit still4276992.

D318e uses the same ELF/disc and the existing RAM/frame reader. Snapshot frame
1223 has Rno0=3, System=0x800, three processed parts/1344 input triangles but
ZERO emitted triangles, four resource/material rejections and zero overflows.
Do not describe this as a presented world. Main is parked with gate/suspend1
at OSWakeupThread -> TaskSchedulerMain -> TaskScheduler; last source timing
entries reach LightMove. The exact snapshot/symbols/analysis are retained in
C:/Flycast-Evidence/re4-dreamcast/d318e-model-boundary. The run ends at its
65-second harness deadline, not a native exception. This scheduling frontier
and source camera/visibility need tracing before visible 3D acceptance. Missing
required block/enemy memory remains independent; Rno0=3 is not room success.

Host sanitizer fixture covers mixed endian indices/CPU arrays, rigid and source
skinned strides, perspective/depth, both cull directions, strips/fans/quads,
near clipping, malformed bounds, whole-part queue rollback and copied-packet
lifetime. Four existing/extended native UI tests pass. trans.cpp PPC tokens
match the pre-slice working source; full ProDG not rerun. Five known stubs remain.

Keep this opt-in transport diagnostic as an integration aid, not an accepted
replacement scene. Next bounded user-directed work reuses the existing D258 VQ
candidate and extends this same texture path, verifying actual compact VRAM.
PAL proposals, encoded files and runtime-supported formats must stay distinct.
Source archive recovery, required room creation, source lighting/material parity,
visible moving 3D/audio/manual play and all three-room gates remain open.


## D320: compact r100 backing and bounded native texture installation

2026-09-21, final D320c candidate based on 503aa10 plus the preserved integration
worktree. This is actual source-archive recovery and successful required block
allocation. It is not visible cabin, enemy creation or playable-room acceptance.

### Existing connection, new adapter, and ownership

`prepare_native_ui.py --compact-room` reuses `le_mirror.prepare_room_archive`,
the recovered offline YZ2 decoder, whole-room/sound qualification and
`prepare_native_room`. Its small relocation observer records relative offsets
in the existing tagged/SMD/TPL/EFF/ITM parsers. It does not introduce a decoder
or a viewer-format replacement for source data.

For reviewed r100 SMD/model palettes, effect textures except CPU noise ID 0xFE,
and ITM pickup-model palettes, each eligible texel range becomes a 32-byte
identity record. The builder verifies the existing native texture package
against the existing converter, without writing/re-encoding textures. Mip
chains, palettes, unreviewed resource families, card/font data and CPU noise
stay resident. Item consumers are cItmSys::DataLoad -> ItemGetBinTplAddr ->
setItemObj/modelInit; their models, IDs and animation structures remain intact.
Original archive slot ordinals, direct ROOM_ARC_PTR consumers, material/animation
identities and all retained source data are preserved; relative byte offsets
are explicitly rebased and both source/resident locations recorded. NTR metadata
uses spare header space without shifting the existing offset slots.

`ReadAreaData` still uses its qualified .dar and source DVD queue. Type 0 now
requests the smaller final allocation directly. The old compressed geometry is
on disc only; no full original or second decoded archive is loaded in RAM.
Original sound-container headers, dispatch order and sound payloads remain.
This retains sound-loading semantics, not functioning ARAM/AICA/audio output.

New `SourceIdentityTable` in the shared texture package validates the compact
index before source pointer relocation. The existing UI/model texture cache
resolves its source pointer/dimensions to the offline resource key without
hashing discarded pixels. Incompatible external descriptors are rejected before
fallback hashing. The table is borrowed metadata inside the source room, not a
second archive. gameRoomMemInit reuses the GPU quiescence contract before clearing
queued native references/cache and retiring its identity view, ahead of heap
reuse. Full door/retry and special source heap-swap paths remain unqualified.

D320a initially reclaimed 780,224 bytes and allocated the block pool, but the
newly enabled blocks exhausted later collision/path and full-texture staging
allocations. Preserve that failure in d320-compact-room. D320c additionally
externalizes the verified ITM textures and uses `Package::open_streamed` with
`room_storage::read_chunks`. These extend the existing Package/storage path:
CRC-validated bounded metadata, the existing 64 KiB bounce buffer, direct native
VRAM upload, same sharing/partial-failure/close ownership and GPU fence. No new
full payload buffer is allocated; each sampled one-image package retains 144
metadata bytes plus its existing handle/ownership allocations. Whole-file CPU
payload release is correctly reported as zero for this path. Native VQ stays
compact; the 8x8 VQ tail is padded only for the 32-byte store-queue transfer.
Linear legacy packages keep the existing adopt/open path; streamed installation
explicitly rejects them. Source-game fixtures use native twiddled layouts.

This trades extra bounded file traversal/CRC work at first use for a lower
loading peak; it is not a measured CPU/frame-rate improvement. The files are
cached after installation. No second renderer or source preparation was added.

### Matched allocation results

| Metric | D319 uncompressed reference | D320c |
|---|---:|---:|
| Resident r100 archive | 4,669,568 | 3,812,576 |
| Actual source-heap recovery | 0 | 856,992 |
| Free immediately before block request | 427,008 | 1,284,000 |
| Required block payload | 1,126,272 (failed) | 1,126,272 (allocated) |
| Block allocator overhead | 0 (failed) | 64 |
| Free after block request | 427,008 | 157,664 |
| Free at first em12 request | 416,704 | 147,360 |
| Required em12 body | 3,577,728 (failed) | 3,577,728 (failed) |

The enemy's free memory is lower because the block pool is now actually charged.
Its first remaining shortfall is **3,430,368 bytes before overhead**, with later
allocations still required. Do not add the failed enemy request to used RAM.
Source heap reservation remains 8,667,136 bytes (8,464 KiB).

The room shrinks by 856,992 net bytes, including 3,104 replacement-record and
1,216 index bytes. No second full archive or compressed geometry overlaps its
final allocation. Source DVD staging, sound work and the KOS buffer remain
separate existing costs. 97 source image identities are retained. Blocks 0, 1,
2 load/create normally; block 3 ARAM staging is still an unimplemented copy.
Ten source-room native uploads succeed in the recorded log. Sampled room upload
heap free remains 75,072 before/after, including the 262,144-byte texture that
could not use full source-heap staging in D320a. This proves bounded installation,
not source archive recovery from that upload. All textures in D320c use the
uncompressed native reference; D319 VQ is separately selectable, not promoted.

The same fixture shows the source title menu at 640x480 with corrected readback.
At the captured snapshot: source frame 1236, Rno0=3, System=0xc00; 86 processed
parts, 28,107 input triangles, 435 output triangles, peak copied packet bytes
8,512, zero invalid/overflow counts, 40 resource rejections, and **zero model
presentations**. This advances D318's zero-output frontier, but the source hold
prevents visible 3D. Preserve it: do not force the hold flag off. Existing effect
path errors continue; required enemy/event/ARAM/audio/inventory work is open.
The capture ends at its 90-second deadline, not a reported native fault.

### Evidence, tests and keep decision

Final private evidence: C:/Flycast-Evidence/re4-dreamcast/d320c-qualified-compact.
Diagnostic predecessors: d320-compact-room and d320b-bounded-upload. Final and
initial evidence-manifest.json files validate. Final evidence pins the dirty
source patch/new fixture, exact executable/disc, per-file asset manifest,
input fixtures, tools/configuration, sampled menu and RAM snapshot. The revision
alone is not the full build identity. No old accepted evidence was overwritten.

- ELF SHA256: e8dd3e2093c28cb2e6c75beffaa32e7f633e6f8eb8dedb8cbd9fd81bb0f1f4e4.
- Disc SHA256: 8d6e105aece2000753b3af934a9744c326f0f98566807c227c5fddb310c488dc.
- Flycast SHA256: 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a.
- KOS 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3; SH GCC 15.2.0.

Checks: qualified compaction with retained noise/mip/other bodies and ITM lookup;
source load rejection before consumers; 40 room endian and 25 mirror tests;
shared Package/storage tests under ASan/UBSan including short reads, CRC and
partial-upload failures, pointer sharing, VQ tail/byte identity, and invalid
external descriptor rejection. Both native targets' affected units build;
game links with the five known stubs. read.cpp/game.cpp PowerPC preprocessing
matches pre-slice working tokens; full ProDG was not rerun.

Keep this selectable compact room and bounded installation. Reproduction:

```sh
python3 port/dreamcast/tools/prepare_native_ui.py   --compact-room /root/re4data/st1/r100.das   --textures /root/probe/d318d-fixtures/tex --output <fresh-output-directory>
```

Final mirror /root/probe/d320b-mirror differs from /root/re4data-le-static only
in r100.arc/.dar. Final disc /root/probe/d320c-disc uses /root/probe/d318d-fixtures.
Original mirrors and the accepted cabin audiovisual reference stay selectable.
Continue actual enemy memory recovery and source-controlled presentation/event
integration; no scene, gameplay, performance, full peak/lifecycle or physical
hardware acceptance is implied.

### Review of the supplied DC_MEMORY_PATHWAY note

The supplied scratchpad's externalization direction is useful and D320 provides
measured evidence for it. Its projected 3.9 MB saving and "memory only" conclusion
are not established. Current source heap is 8,667,136 bytes, not 8,929,280.
Current sound dispatch does not put its entire ARAM sample payload inside the
room allocation, so an AICA implementation cannot be credited with removing
that amount from r100. VRAM is not general backing for CPU-readable geometry.
Direct ROOM_ARC_PTR users also preclude treating GetDataExt as a universal lazy
loader boundary. Source rendering/presentation, enemy/event, inventory and audio
integration remain separate requirements. Do not import another port's memory
or performance numbers as RE4 acceptance.

### Enemy asset candidate boundary (user-authorized reductions)

The user authorizes smaller Dreamcast render assets, from original or compatible
PS2 content, provided they replace actual expensive backing, preserve source
gameplay/complete components, and receive memory/CPU/visual checks. This is not
a requirement to retain every render payload unchanged. Keep original references
and make perceptual changes selectable until reviewed.

Private /root/probe/ps2-enemy-audit/REPORT.md, audit.json, identities.json and the
existing pinned extraction tools establish a bounded negative result for using
PS2 meshes alone to reach 66% of the 3,577,728-byte em12 body. GC's 34 top-level
BINs total407,168 bytes; PS2 equivalents total411,264. GC nested effect BINs add
7,872. All mesh backing is therefore415,040 (11.60%); even removing every mesh
would leave88.40%, not66%. Source FCV/SEQ occupy1,864,928 bytes; top-level TPLs
480,800 and EFF819,168 include further texture data. The full PS2 archive is
3,321,120 bytes on disc, not a native residency measurement.

All34 model slots and joint ID/parent arrays correspond; bind translations
match exactly in17, otherwise within0.00039632 source units. Skin weights,
complete component semantics, deformation, visual/CPU/native-memory costs remain
unqualified. Do not promote PS2 motions/effects merely to claim archive savings.
Prioritize render texture backing and equivalent motion-storage reuse; selective
mesh changes remain candidates where a native working-set/timing gain is proven.


A follow-up bounded source-codec measurement (/root/probe/d321-motion-cost.json)
retains all153 original FCV clips: within-clip exact key-block deduplication saves
only14,208 bytes; global identical-key reuse has a22,667-byte upper bound before
additional alignment. Do not build that adapter as the route to a1.22 MB saving.
Per-clip zlib level9 pricing is1,386,112 aligned bytes versus1,823,552 source bytes
(a437,440-byte storage reduction); the largest uncompressed clip is32,416.
This is an offline cost experiment, not encoded assets installed in the game,
a native decoder/cache design, target memory recovery or CPU acceptance. Even
this saving plus488,960 potentially externalizable single-level/nonpalette texel
bytes falls short of the34% target before metadata/buffers. A66%-size enemy body
still would not fit the current147,360-byte free region. Continue source-backed
resource recovery across the actual working set; do not turn a mesh substitution
or a compressed file size into a claim that the allocation now fits.


## D322 - compact persistent core HUD backing (2026-09-21)

Keep D320's compact room, successful block pool and source menu. D322 reuses the
same offline identity/offset compaction, native texture packages and bounded
Package/storage uploader for the already-qualified `etc/core.das:0#25` HUD EFF
texture table. No textures are generated again: all 26 selected native packages
already exist and match the deterministic converter. No resizing, mesh changes,
PS2 substitution, palette conversion or VQ promotion occurs in this candidate.

### Connection and ownership

- Existing implementation reused: `prepare_native_ui` offset/identity compaction,
  `le_mirror` conversion/qualification and DVD payload replacement,
  `SourceIdentityTable`, `Package::open_streamed/upload/release_payload`, shared
  storage bounce and GPU-fenced texture cache.
- Source connection: `CoreDataRead` reads source file 3 to `CORE_DATA_ADDR`, binds
  identities before original TPL relocation, then continues normal SpecularInit
  and GlobalIlmTexInit. Existing source ID/model texture consumers resolve the
  same offline keys through the shared native cache.
- New adapter: one persistent core identity view alongside the existing room
  view; `re4dc_ui_bind_core`; a selectable fixed-core reservation; an oversized
  core guard in the DVD queue before any payload transfer. Room retirement
  clears room identities/cache after the existing fence, retaining the core
  view because its source region remains resident. No second resource cache.
- The smaller container reads directly into the smaller final fixed region.
  Original type-0 bytes remain on disc only, as in the existing room transport;
  original sound headers/data and source sound dispatch remain intact. This is
  RAM recovery, not a smaller disc image or proof of audible output.

Only EFF #25's qualified upload-only, single-level, nonpaletted images are
selected. Noise ID 0xFE, palettes, mip chains, specular/illumination and other
families remain resident. Every unselected converted core body is checked
byte-identical, even when its top-level offset moves. All source slot ordinals
remain stable. The core's EFF #1 path list, VIB #3 and SAT #9/#10 are still
unqualified; their status is explicitly retained in the report. This does not
activate their consumers or label the entire core archive qualified. The
existing boot-deps selector already requires #25 separately.

### Measured cost, with the same D320 room/input/native packages

| Metric, bytes | D320c | D322 |
|---|---:|---:|
| Core type-0 payload | 2,295,616 | 1,975,008 |
| Fixed core reservation | 2,310,144 | 1,975,008 |
| Source heap capacity | 8,667,136 | 9,002,272 |
| Free before required block request | 1,284,000 | 1,619,136 |
| Free after successful block allocation | 157,664 | 492,800 |
| Free at first em12 request | 147,360 | 482,496 |
| Required em12 request | 3,577,728 (fails) | 3,577,728 (fails) |
| Sampled room-upload free, before/after | 75,072 | 410,208 |

Actual source-heap gain is **335,136 bytes at both matched allocation points**:
320,608 net payload bytes plus 14,528 formerly unused reserved bytes. The compact
core includes 832 token bytes and a 352-byte identity index. The executable's
text/data/BSS total grows 656 bytes, including 32 BSS bytes; report that separate
cost rather than treating the source-heap gain as a whole-machine peak result.
The source arena allocation stays the same size. No second full core or new
texture staging buffer is allocated. Existing source DVD staging, native 64 KiB
bounce and per-texture metadata remain. Ten room uploads succeed with unchanged
source-heap free bytes. Sampled menu VRAM peak remains 4,192,256 bytes, with the
same native package files and shared 4 MiB cache policy.

CPU trade: one 26-record validation at load and a bounded core identity lookup
on a source-image cache miss. Hot source/texture caches are unchanged. No extra
per-frame model preparation, encoder or decompressor was added. This run does
not establish gameplay CPU/frame-time distributions, input responsiveness or
full loading/retry peak headroom.

The remaining enemy deficit is **3,095,232 bytes before overhead**, not solved
by this change. Source menu is visibly intact at 640x480. The asynchronous model
snapshot is frame 1234, Rno0=3, System=0x800, 16 processed parts, 5,507 input and
87 output triangles, 8,512 peak packet bytes, 0 invalid/overflow, 8 resource
rejections, **0 model presentations**. It is not a matched draw-count comparison
with D320's later snapshot. The source hold stays intact; no visible cabin or
moving HUD/actor acceptance. Existing effect-path errors, required enemy/event,
ARAM/audio/inventory and route/retry requirements remain open.

### Selection, rejection and verification

The build default remains the full 0x234000-byte core reservation. The Makefile
regenerates the single-object budget header when the profile changes, so stale
mem.o cannot silently retain the other profile. Switching to default and back
was tested; the restored candidate ELF was byte-identical. Reproduce candidate:

```sh
python3 port/dreamcast/tools/prepare_native_ui.py \
  --compact-core /root/re4data/etc/core.das \
  --textures /root/probe/d318d-fixtures/tex --output <fresh-core-output>
source port/dreamcast/kos-env.sh
make -C port/dreamcast/game -j4 CORE_RESIDENT_BYTES=1975008
```

Install that core.das in a fresh selectable mirror, retaining D320's compact
r100.arc/.dar and unchanged other assets. Current candidate paths:
`/root/probe/d322-core`, `/root/probe/d322-mirror`, `/root/probe/d322-disc`;
fixtures remain `/root/probe/d318d-fixtures`. Original mirrors are preserved.

The negative pairing uses the same candidate ELF with the full original core:
`native core read REJECTED: request=2295616 capacity=1975008 before transfer`.
It halts explicitly before binding/initialization, preventing an overwrite of
the adjacent option/player regions. The 20-second capture deadline ends that
intentional rejection. Positive capture ends at 90 seconds, not a native fault.

Focused checks: 2 compact source fixtures (including unchanged raw families,
qualified-family rejection, CPU-noise/mip/ITM offsets and no source overwrite),
5 native UI/package tests with real shared implementations under ASan/UBSan,
2 native room-load checks, 25 mirror and 40 room-endian checks. Persistent core
identity lookup survives room-view retirement; incompatible identities reject
before raw hashing. Game links with the same 5 known missing stubs. read.cpp and
dvd.cpp PowerPC preprocessed tokens match pre-slice files; full ProDG not rerun.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d322-compact-core` and
`d322-core-budget-rejection`, with validated manifests, exact executable/disc,
assets, fixtures, capture tools/configuration, dirty source patch, logs and menu
readback. KOS remains804b3195ebd1a06a27cc2b3a5eacf7a2429040a3, SH GCC15.2.0;
Flycast remains64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a.
Candidate ELF SHA25632d8674fd1ff5f0cfbc41b525adde9b45633908847756f565423d6a036c34383.
Disc SHA256c0c97387d040087ba2da4ba3267d6f95bd6aaac2e8a61190896c4708eafb5839.
The manifest pins all remaining identities. Commit alone does not
identify inherited dirty integration work used in the build.

Keep this selectable equivalent backing reduction. Continue recovering the
actual enemy/active resource working set and completing source-controlled native
presentation. Smaller reviewed render assets remain authorized where measured
cost justifies them; whole-room/source-system requirements are not waived.


## D324 - core effect paths qualified and more backing externalized

D324 continues D322's existing native resource connection. `le_mirror.fmt_eff`
now converts the distance paths consumed by `EspGetPathAddr` -> `PathGetLength` /
`PathGetPos[Em]`, using `include/path.h` (u16 count, 4-byte header, 40-byte vertices:
seven floats plus twelve byte lanes). This is not the ID-system spline format.
IDs and table-relative offsets retain identity, shared paths convert once, and
invalid lengths, bounds, weights or non-finite scalars reject with rollback.
Eleven real core paths / 344 vertices preserve every scalar bit and byte lane
through endian conversion AND archive compaction. The previous repeated
`ESP_CTRL02 : OUT OF RANGE.` message is absent from the 90-second replay; this
alone does not establish all effect behavior or native effect presentation.

`prepare_native_ui.compact_core(..., include_effects=True)` / `--core-effects`
adds the now-qualified core EFF #1 upload-only table to HUD #25. Reuses
`_compact_upload_only`, `replace_native_payload`, source `CoreDataRead` identity
binding, `SourceIdentityTable`, shared `Package::open_streamed/upload`, bounded
storage and existing GPU retirement. No new loader/cache/backend or runtime
source change. CPU noise ID FE, palette/mip data, effect sequences/paths/models,
and unselected families remain resident. VIB #3 and SAT #9/#10 are still explicitly
unqualified, with their converted/raw bodies unchanged. Sound containers remain
on the original DVD path.

### Measured allocation result

| Same allocation point | D322 | D324 |
|---|---:|---:|
| Actual persistent core reservation | 1,975,008 | 1,501,312 |
| Source heap capacity | 9,002,272 | 9,475,968 |
| Required block pool | 1,126,272, succeeds | 1,126,272, succeeds |
| Free after block pool | 492,800 | 966,496 |
| First enemy request | 3,577,728, fails | 3,577,728, fails |
| Free at first enemy request | 482,496 | 956,192 |
| Sampled native room upload heap before/after | 410,208 / 410,208 | 883,904 / 883,904 |

**473,696 additional real source-heap bytes recovered**; enemy shortfall is now
**2,621,536 bytes (2.50009 MiB) before overhead**. The original core payload was
2,295,616; cumulative payload recovery is 794,304. Relative to the original
2,310,144 reservation, cumulative source-heap recovery is 808,832. Final core
includes 1,888 token bytes and 768 identity-table bytes (59 descriptors). No full
original core is loaded first. DVD staging, shared 64 KiB upload bounce and 144
bytes per installed texture metadata are unchanged; no RAM saving is credited
from disc-only append transport. ELF text/data/BSS sizes are unchanged from D322.

33 newly externalized source image descriptors reuse eight existing packages;
25 missing packages were produced with the existing deterministic converter in
private fixtures. No new encoder, resize, PAL/VQ promotion or default asset
change. Source pattern tables and per-frame texture identities remain. The shared
native cache retains its existing 4 MiB policy, with menu peak 4,192,256 bytes.
Ten room uploads succeed. This does not measure all core/enemy textures resident
simultaneously, moving effect quality, full loading/retry peaks or gameplay CPU.
The added cold identity work is 59 records instead of 26; hot caches are unchanged.

Source menu capture remains visible at 640x480. The sampled model snapshot is
again source frame1234/Rno0=3/System0x800: 16 parts, 5,507 input / 87 output
triangles, 8,512 peak packet bytes, zero invalid/overflow, eight rejected resources,
**zero model presentations**. Source hold is preserved. This is not room acceptance;
enemy creation, full model/material/event/ARAM/audio/inventory and route/retry
requirements remain. The capture ends at its deadline, not a claimed game fault.

### Selection, checks and identities

```sh
python3 port/dreamcast/tools/prepare_native_ui.py \
  --compact-core /root/re4data/etc/core.das --core-effects \
  --textures /root/probe/d324-fixtures/tex --output <fresh-core-output>
source port/dreamcast/kos-env.sh
make -C port/dreamcast/game -j4 CORE_RESIDENT_BYTES=1501312
```

Default full-core budget and the HUD-only selection remain available. Existing
pre-transfer overflow guard remains; its D322 negative test is not a new D324
run. Current paths: `/root/probe/d324-core`, `/root/probe/d324-mirror`,
`/root/probe/d324-disc-kos`, `/root/probe/d324-fixtures`. The first packaging attempt
without kos-env exited before creating an image; the fresh `-kos` directory is the
actual packaged result. Prior assets/evidence are retained.

Checks: 27 mirror, 3 compact archive, 40 room-endian and 5 shared native UI/package
checks pass, plus real path bit/byte comparison. Tests cover weighted/shared paths,
invalid input rollback, compaction relocation, CPU-noise retention and rejection
of an unqualified selected family. No recovered C++ source was changed in this
slice; no new PowerPC matching claim. Same five known missing stubs remain.

Evidence `C:/Flycast-Evidence/re4-dreamcast/d324-core-effects` includes validated
manifest, exact dirty build source, executable/disc/assets/fixtures, toolchain,
launcher/readback/symbol identities, logs, snapshot and inspected menu image.
ELF SHA256 `f83e0a70a79603cf9fcae45497034c3b3a2994835663a94fd311110875943732`.
Disc SHA256 `b9eee0faa9c1e097175bc7e62bbc696e72e0669bb76f18f2eb7ec543c30ce118`.
KOS `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`, SH GCC15.2.0,
Flycast `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
Keep selectable equivalent backing reduction; no physical-hardware acceptance.

The next large memory lever is enemy motion working-set residency, alongside
qualified native texture externalization. Do not count all bank bytes as a saving:
active/blending clips, source header readers, events, per-instance pins, loading
scratch and retry/retire ownership must be measured. Blender is secondary; the
isolated static roundtrip/geometry experiment is not a main-branch runtime change.
See the current allocation-backed priorities in R4_ASSET_RESIDENCY_PLAN.md.

## D325: motion key residency candidate

D324 remains the accepted integration/reference asset selection. D325 is a
selectable implementation and diagnostic checkpoint, **not an encounter-qualified
prefetch policy or successful enemy allocation**. No animation, effect, mesh,
SEQ event, enemy state or source hold flag is deleted to make the result fit.

### Source connection and ownership

`prepare_enemy_motions.py` reuses `le_mirror` qualification, static REL compaction,
the existing FCV codec and DVD payload replacement. Shared `compact_spans()` now
also supports an inserted header slot. DRS retains its original DVD/sound records;
only the main-body request points at the smaller prepared body. Original main
payload bytes remain on disc, never loaded alongside the replacement. Exact LE
clips are separate identity-addressed files, not another animation format.

`readEmData()` binds the MTC table before module consumers. Source FCV headers,
joint-kind/number arrays, frame counts, ordinal slots and SEQ tables remain in the
resident archive. Cache entries contain full exact LE clips; every load validates
length, CRC/FNV, header equality and all key offsets before publishing relocated
pointers. No source `MotionWork` or `CameraMotionWork` contains an evictable cache
address: only evaluation-local tables do. Hermite histories retain indices/values,
not key addresses. Shape evaluation's table is local stack work.

| Source consumer / boundary | Required lifetime and native connection |
|---|---|
| em12 module initialization / `readEmData` | Model/Work references, source headers and SEQ/EFF remain archive-owned. Stable header proxies are retained; bind/prefetch precedes prolog consumption. |
| `MotionSetCore`, `MotionMoveCore`, `MotionGetSpeed`, `MotionGetPosition` | Existing source evaluator runs unchanged on leased keys. Blend/second MotionWork can acquire the same or another entry. Pins protect every evaluation; release retains cached keys. |
| `CameraMotion` construction/move and `CalculateShape_new` | Same FCV key boundary is adapted; no assumption that every FCV is skeletal. These adapters compile and preserve PPC preprocessing; this checkpoint's real pose fixture is skeletal, not full camera/morph acceptance. |
| `EspDataLoad` and effect users | Borrow TPL/ANM/EST/SST/path/EFM pointers with reference-counted release. Entire EFF family stays resident. No justified effect eviction boundary is implemented here. |
| `InitModule`, room heap retirement | Unbind before archive destruction; retire before room-heap replacement. Refuse retirement while pinned. D325 supports prepared room-heap 4 archives only; stage/frozen/ARAM swap ownership remains rejected/unqualified. |

The new `native_motion` adapter uses existing `storage::Arena/read_file` and its
bounded bounce storage. A reader mutex is acquired before `fs_open` can yield;
contention retains the existing explicit reentry result. Cache access/load is
serialized; hot entries never become LRU victims, cold entries are evicted only
under capacity pressure and never while pinned. The original full archive remains
selectable and takes its ordinary source evaluation path.

### Preserved source prefetch and concurrency audit

`audit_enemy_motion_prefetch.py` uses the **existing** enemy inventory and source
references, not another extraction or a replay-used list. `PL_ARC_PTR` word indices
are inventory ordinals +4. WALK expands base..base+5; BACK includes both operands;
actual FCV tags filter out SEQ companions. The current conservative response,
locomotion and cabin-attack closure selects 75 clips / 952,768 bytes. It includes
weapon/damage variants rather than only the four sampled poses.

**This is incomplete.** All direct em10 references cover 112 clips / 1,418,592
bytes; 33 more entries need initialization/module Work-table and indirect/event
resolution. Indirect R1 dispatch, authored spawns, all active instances,
blend/component/camera/shape use and prefetch-release boundaries still require
closure. The audit always reports `source_complete:false`; producing this candidate
requires `--diagnostic-incomplete-prefetch`. Do not promote 75 clips as the complete
repeated-use/immediate-response set. Two largest cold clips provide a diagnostic
capacity reserve, not proof of sufficient gameplay concurrency. An unchanged set
larger than that selection can still thrash; require a closed set before acceptance.

Source scheduling normally suspends the parent across native task I/O until
`TaskSleep`; ISR work has separate ownership. `pCTask` is a scheduler cursor, not
the native owner. Cache scopes and pins track `thd_current` under IRQ exclusion.
`OSCancelThread` drains outstanding cache I/O/evaluations before `thd_destroy`,
keeping IRQ exclusion across the final empty check and destruction. `TaskKill`
now distinguishes the actual running thread: another task marked RUN during a
native I/O yield goes through cancellation, not the caller's `TaskExit`. Self exit
with an active lease is explicitly rejected. `systemResetCommon` calls
`TaskAllClear` before `EmReadInit`; `InitModule` unbinds before freeing backing.
A focused host check compiles the **actual TaskKill/OSCancelThread bodies** with
the actual cache, blocks a read, and verifies no destroy before I/O and pin release.
This is supporting evidence; full game cancellation/retry during loaded combat is
not established because the enemy body still fails its allocation.

### Measured and bounded costs

| Item | D324 reference | D325 selectable candidate |
|---|---:|---:|
| Actual first em12 main-body request | 3,577,728 | 1,907,456 |
| Free at that request | 956,192 | 956,192 |
| Required block pool / free afterward | 1,126,272 succeeds /966,496 | same |
| Main-body request reduction | — | 1,670,272 |
| Enemy allocation / source-heap bytes actually reclaimed | failed /0 | failed /0 |
| Remaining body-only shortfall | 2,621,536 | 951,264, before cache/overhead |
| Selected hot key payload | resident in archive | 952,768 |
| Cold payload capacity reserve | — | 55,168 |
| Target slot metadata | — | 2,336 |

The prepared body includes 28,928 retained FCV-header bytes, 2,944 table bytes and
32 header-growth bytes. 145 externalized entries total 1,702,176 bytes. The older
1,823,552 inventory figure counts source FCV backing, not this exact unique key
transport; do not claim all of it was removed. Other families and static REL
remain byte-equivalent after required offset rebasing.

**Net budget is much smaller than the body reduction.** At full selected payload
capacity, 1,670,272 -1,007,936 -2,336 =660,000 bytes before allocation overhead.
`motion_bridge` records the OS heap owner; each allocation adds 32 owner bytes,
32 source MAD-tag bytes and32 OS cell bytes. A conservative 146-allocation bound
adds 14,016 bytes, giving **645,984 bytes of provisional net recovery with that capacity/overhead**,
not a measured successful-game saving. The initial 75-hot set plus metadata costs
962,400 including 76 allocation overheads, leaving707,872 before cold use.
Retaining all 145 keys hot would instead **increase** this family's total by 48,256
bytes. This rules out calling a tiny two-clip cache or full-bank prefetch a solution
to the encounter's remaining memory gap. Further source working-set closure and
qualified texture/resource-lifetime recovery are still necessary.

Loading replaces the body directly; it never first allocates the 3,577,728-byte
reference. Cache cold eviction precedes replacement allocation. No new whole-clip
scratch copy is introduced; shared storage bounce remains 64 KiB. The per-clip
cache publication peak is bounded by its payload budget; allocator metadata,
archive, shared bounce and whole-game loading/retry peaks are separate costs.

### Evidence and decision

The existing real-motion fixture now accepts an alternate motion pointer and an
after-evaluation hook. `Makefile.residency` links the same source motion/IK/math,
actual native cache/storage and existing platform RAM logger. It is a diagnostic
executable using KOS-owned test allocations, **not source-heap or room acceptance**.
The real em12 fixture is model 440/motion 1, 34 parts, 26 joints, four sampled poses.
A separate pressure phase changes only fixture hot flags to make that motion
cold, checks retained source pointers, and evicts/reloads it between evaluations.
No game candidate assets are changed by that stress phase.

Host: all 34 parts match at the four poses with zero measured root/angle/world
error after 634 forced evictions. Real-key host fixture: 75 initial loads/952,768
bytes; 100 warm repetitions add 0 misses/bytes. Peak cached payload 1,007,776;
peak pinned 32,416; host slot metadata 3,488 (host pointers are wider). Host 528 us
wait is not target I/O evidence. Synthetic tests also hold one cold pin while
another entry is replaced, verify every relocated key and an unchanged archive,
and observe ownership through a yielding read and cancellation.

Final Flycast timings/identities and the final normal-loader replay are recorded
in the private evidence manifests listed in the handoff. The SH-4 cache test must
show zero warm reloads, bounded numerical errors and clean retirement. Cold disc
wait is reported as a resource stall, never a gameplay speedup. There is no
physical-hardware test, complete encounter hot-set closure, live combat timing,
loaded-enemy peak, event/audio acceptance or successful death/retry yet.

Keep the selectable adapter and tests; **do not promote the incomplete prefetch
profile**. Continue allocation-backed lifetime work and source prefetch closure
alongside the existing recovered-game renderer connection. Do not restart model
extraction, substitute the cabin prototype loop, clear source hold or create a
new streaming framework. D324 remains the accepted reference; three-room goal
and the other existing backlogs remain active.

Final target evidence:

- Normal loader: `C:/Flycast-Evidence/re4-dreamcast/d325c-motion-request`.
  Exact source title capture, allocation trace and model-boundary snapshot are
  preserved with a validated manifest. Main-body request 1,907,456 still fails
  with 956,192 free. Source heap 9,475,968 and post-block 966,496 are unchanged.
  No native motion bind occurs in this run; no enemy heap recovery is credited.
- Cache/source-pose fixture: `C:/Flycast-Evidence/re4-dreamcast/d325b-motion-cache`.
  75 initial misses/read 952,768 bytes; 100 repetitions/7,500 evaluations add
  **zero misses and zero bytes**. Separate forced-pressure phase finishes at
  185 cumulative misses/loads, 34 evictions and 2,743,392 cumulative bytes read.
 Peak cache payload 981,440; peak pinned 32,416; target metadata 2,336;
 peak payload+metadata 983,776. These do not include KOS allocator headers or the
 separate 1,907,456-byte test archive. Worst resource wait 273,519 us (273.519ms),
 including read/validation and mutex wait where present. Emulated CD timing is
 not physical-disc acceptance or a live input-response measurement.
 Four source poses pass: root error 0.00000381, angle 0.00000003, world 0.00036621;
 existing bounds are 0.001/0.0002/0.05. Every cache load validates and relocates
 all key pointers; the fixture also checks retained source fields and unchanged
 archive bytes through pressure/reload. Clean cache retirement leaves 0 test-owned
 payload bytes. Effect, shape and camera behavior need their own runtime fixtures.

Cache ELF SHA256 `7428cef433acd19ecf8778a1d9c71768d52fa4c47346a36f65d2b2aee1ce6423`;
cache disc SHA256 `755e916582ea12ec30e259cb72214a5c4ec09f317251bbc0a7416c7818c079fb`.
KOS `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`, SH GCC15.2.0,
Flycast `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
Game text/data/BSS 2,275,740/75,620/672,632: +8,096 text/+448 BSS versus D324,
without changing the measured source-heap capacity. Same five missing stubs.

Focused checks: 4 motion-residency (including actual TaskKill/OSCancelThread drain),
5 shared UI/package/storage,3 compact-archive and27 mirror checks pass. PPC
preprocessed tokens match the 0518c93 source for motion/read/camera/shape/scheduler;
this is not a fresh full ProDG object-comparison claim. The em12 epilog is empty;
that fact is part of D325's narrow unbind contract, not permission to discard keys
before a future nonempty module's last CPU consumer. No physical-hardware gate.

Reproduce from existing assets, using fresh private output paths:

```sh
python3 port/dreamcast/tools/audit_enemy_motion_prefetch.py \
  --inventory /root/probe/d325-enemy-v2/motion-residency-report.json \
  --output <fresh-audit.json>
python3 port/dreamcast/tools/prepare_enemy_motions.py \
  --source /root/re4data/em/em12.drs --hot-audit <fresh-audit.json> \
  --diagnostic-incomplete-prefetch --output <fresh-prepared-directory>
source port/dreamcast/kos-env.sh
make -C port/dreamcast/game -j4 CORE_RESIDENT_BYTES=1501312
make -C port/dreamcast/motion -f Makefile.residency residency -j4 \
  BUILD=<private-cache-build> REAL_FIXTURE_DIR=/root/probe/d325-real \
  REAL_SOURCE=/root/re4data/em/em12.drs
```

The last command uses the existing model 440/motion 1 real fixture, not the default
Leon fixture. Fixture data is private; `/root/probe/d325-cache-data/em12.arc` and
`/root/probe/d325-cache-fixtures/mot` are packaged with existing `mkdisc.sh`.
Normal-game packaging uses `/root/probe/d325-mirror`, `/root/probe/d325-fixtures`,
and `/root/probe/d325-owner-disc`; none is a default asset promotion.

Normal-game ELF SHA256 `4ef0ff3d2f736a9f45538abf29fc1873a9ea0deac9df854f0903b866d749a8de`;
game disc SHA256 `36ebccb312ab211313ceb67a3bcc778a3aef63f2f66d1a303100568cfcf206e0`.


## D326: enemy upload-only texture backing

Keep as a selectable integration candidate, not a promoted encounter. D324 remains
accepted; D325 motion cache/prefetch/concurrency audit is preserved. No meshes,
source motions, SEQ events, effect behavior tables or gameplay code are removed.

### Connection and ownership

- Offline `prepare_enemy_motions.py --textures` reuses `prepare_native_ui`'s
  exact-package validation, `compact_spans` offset rebasing and NTR serializer.
  The selection/index operations are factored out of the existing room/core
  producer; their tests and real motion-only byte equivalence pass. There is no
  additional decoder, compressor, inventory or prepared-room transport.
- Source `readEmData()` -> `re4dc_ui_bind_enemy()` -> existing
  `SourceIdentityTable::adopt()/lookup()` -> existing `image_key()`/shared cache
  -> `Package::open_streamed()/upload()/release_payload()` with the existing
  64KiB storage reader. Four nonowning module views cost96 additional BSS bytes;
  no second texture cache or VRAM budget is introduced.
- Binding happens before model/effect TPL relocation and module consumers.
  Stable archive-owned32-byte identity records replace discarded image data.
  Identity lookup continues to work after the source mutates TEXHeader.data.
  InitModule unbinds after DLL_Unlink and before archive free. Existing room
  retirement fences the GPU, clears queued native work and all enemy views.
  Queued native packets own copied geometry/header/cache handles; the view's
  retirement does not free in-flight VRAM. Full loaded-enemy retry is still open.

The source contracts inspected are Em12Set/WeaponSet -> em10ModelInit/body and
accessory model creation -> cModelInfo/calcTplAddr/commonModelTrans; and
em10_R0_Init -> EspDataLoad(ARC4) -> espTexRegist -> cTexSys::TexRegist/CalcTplAddr.
Their selected headers/animation tables remain source-owned; the inspected image
consumer initializes GX texture objects, which the existing native adapter maps
to native identity. Palette/CLUT, mip chains and CPU noise ID0xfe are excluded.
Embedded EFM textures remain unreviewed and resident (6,144 bytes); they are not
silently counted among the removed payloads. Source offsets, material identities,
frame selection and the static64-byte REL descriptor remain. Other nonselected
families are byte-compared after required offset relocation.

### Bytes and actual target result

| Quantity | Bytes / result |
|---|---:|
| D324 enemy body / D325 motion candidate |3,577,728 /1,907,456|
| D326 combined body |1,426,304|
| Additional body reduction versus D325 |481,152|
| Texture-only body / saving, all motions resident |3,096,608 /481,120|
| Source texture payload removed |482,816|
| Retained identity records / NTR table |1,184 /480|
| Combined header growth / motion index (already in body) |32 /2,944|
| Required block pool / free after success |1,126,272 /966,496|
| Free at first enemy request / body-only shortfall |956,192 /470,112|
| Actual enemy allocation / heap recovery |failed /0|

The combined body's2,151,424-byte reduction is **not** the total runtime saving.
Keeping the same diagnostic hot+reserve budget1,007,936, target metadata2,336 and
conservative allocator overhead14,016 gives a provisional family-budget reduction
of1,127,136 bytes (1.075MiB). The remaining body+cache lower-bound shortfall is
1,494,400, before body allocation overhead, later actor/event/audio allocations
and fragmentation. Complete repeated-use/immediate-response closure may require
more keys. No tiny evaluation-only cache or replay-derived eviction policy is used.

The body is read directly at its smaller final size; the reference is never first
loaded into RAM. Original converted sound-container records/payloads stay on disc
and follow the existing source sound dispatch. Native upload uses the shared
64KiB bounce and144-byte/package metadata; there is no full-size enemy texture
staging allocation. The selected37 descriptors share36 exact-reference packages:
1,875,008 package-file bytes,1,869,824 unique VRAM payload bytes if all resident.
This is an offline all-images total, not measured simultaneous target residency.
No new VQ/PAL candidate is generated; no texture resolution/filter/alpha change
or VRAM saving is claimed. Actual world/actor simultaneous texture use remains
subject to the shared cache, required rendering and reviewed appearance.

### Validation, evidence and limits

- 13 focused host checks pass:5 native UI/package/storage (real binder added),
  4 motion-residency/PPC-source checks,3 compact room/core,1 new synthetic enemy
  transport test.27 existing mirror checks also pass. New transport coverage
  checks required qualification, source slot/offset identity, retained noise/mip
  bytes, sound sample/record preservation, stale output and wrong native packages.
- The actual combined archive passes the existing native implementations under
  host ASan/UBSan: all37 identities resolve after header-pointer relocation,
  all37 descriptor uploads succeed through bounded reads, retirement/reload
  succeeds. Synthetic four-owner tests reject duplicates/capacity/corruption and
  prove freeing one archive does not invalidate others. This is not SH-4 rendering.
- Combined real-key host fixture:75 warm misses/952,768 bytes;100 repetitions add
  zero misses/bytes. Pressure phase:285 cumulative misses,205 evictions,3,200,992
  bytes read, peak cache1,007,776, peak pinned32,416, host metadata3,488; worst host
  wait623us is not target disc timing. Every relocated key is checked and the
  archive remains unchanged. D325's separate SH-4 evidence remains the target
  cache reference (273,519us worst wait), not a D326 live-game result.
- Normal Flycast source-menu/New Game replay reaches the same allocation frontier;
  source frame1233/Rno0=3/System0x800,16 parts/5,507 input/87 output triangles,
  8,512 peak packet bytes,0 invalid/overflow,8 resource rejects,**0 presentations**.
  It never reaches enemy texture/cache binding because allocation still fails.
  Source title menu remains visible; no source hold is forced clear. The90-second
  capture harness deadline ends the run, not an identified new native fault.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d326-enemy-textures`; validated manifest
includes the exact fixture, source patch/build inputs, emulator/config/capture
reader, menu framebuffer, allocation log, RAM snapshot and separate host results.
Private candidates and commands are in CLAUDE.md. Reproduce with the existing
D325 producer command plus `--textures /root/probe/d326-fixtures/tex`; omit the
hot audit and add `--keep-motion-resident` for the independent texture-only case.
Use fresh output directories. Final producer regenerated byte-identical combined
and texture-only DRS outputs; motion-only DRS/ARC remains identical to D325.

ELF SHA256 `5c8484f9d89c1917bd85f92f4ce8b1a9c93a00518a2674a51f447960dccad500`;
disc SHA256 `38d89684269b5ba7635817550c2700f73cbeb9ef2684475591770b3dab4bc6a5`.
Source base `d3e82e8bae2276f0a18abe27c213fa0d7a60f449` plus preserved dirty inputs;
KOS `804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`, SH GCC15.2.0,
Flycast `64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a`.
Text/data/BSS2,276,220/75,620/672,728 (+480 text/+96 BSS versus D325), same five
missing stubs and unchanged source heap capacity9,475,968. No complete enemy,
encounter performance, source effect/audio or physical-hardware acceptance.

Keep the adapter and exact selectable candidates; do not change default assets.
Continue source working-set/prefetch closure and other qualified player/weapon/
room backing lifetimes alongside the current source-controlled 3D connection.
Do not count this texture ceiling again, restart extraction, weaken source
consumers or call the failed allocation an integrated cabin.


## D327: player/weapon backing and native read lifetime

Selectable candidate on D326 (`572cfc7`), 2026-09-21. The normal source menu
remains visible. The required block pool allocates and the full prepared enemy
body now loads. Source sound-container dispatch and 37 enemy texture identities
complete. The next explicit failure is hot-key prefetch allocation, before enemy
initialization/playability. D324 remains the accepted reference; neither the
incomplete 75-clip profile nor newly externalized actor textures are promoted.

### Connections and ownership

| Reused mechanism | Source boundary | New adapter |
|---|---|---|
| `prepare_enemy_motions`, qualified `le_mirror`, `compact_spans`, NTR identities | pl00/wep02 top-level TPLs and source DRS body | Textures-only family selection; preserve non-REL pl00 boundary and all FCV/SEQ/model/slot content. No new decoder. |
| `SourceIdentityTable`, existing `native_ui` lookup/cache and `Package::open_streamed/upload` | `ReadPlayerData`, `ReadWepData`, source TEXHeader identities | Two borrowed identity views; explicit release hooks. Views persist across room retirement if source player/weapon persists; shared VRAM still follows existing fence/retire/reupload. |
| Existing fixed arena and DVD part transfer | pl00/player and wep02/weapon owning reservations | Selectable exact reservations and pre-transfer checks against original request owner, including later parts, overflow and source shared-player range. Full defaults retained; alternate costumes/weapons require qualification. |
| Existing OS thread owner and cancellation drain | DVD filesystem calls and source `iTaskSuspend` | Nested bounded I/O scope in unused OSThread context space; defer source ISR suspension until filesystem locks/callback complete. Drain scopes before cancellation destroys stack. KOS scheduling/interrupts remain enabled. |

No prototype AI, motion selection, camera or source hold override was introduced.
Source gameplay, source archive descriptors, collision, events and every motion
remain. Only verified top-level nonpalette/nonmip texture payloads were removed.
Player EFF families were not automatically qualified. Weapon mip texels 30,720
remain resident. Static module/BSS policy is unchanged.

### Actual allocation and working-set evidence

| Item | D326 | D327 |
|---|---:|---:|
| Source heap arena capacity | 9,475,968 | 9,987,168 |
| Player reservation / loaded body | 1,146,880 / 1,055,264 | 846,656 / 846,656 |
| Weapon reservation / loaded body | 458,752 / 254,720 | 247,776 / 247,776 |
| Free after required 1,126,272-byte block pool | 966,496 | 1,477,696 |
| Enemy body requested | 1,426,304, failed | 1,426,304, loaded |
| Free after enemy allocation | not allocated | 41,024 |
| Free after cache metadata and first hot key | not reached | 16,096 |

**511,200 real source-heap bytes recovered**: 295,648 previously unused fixed
reservation bytes plus 215,552 net removed player/weapon backing. Player removes
209,920 texels and retains 1,312 metadata bytes (net208,608); weapon removes7,168
and retains224 (net6,944). Compact bodies load directly; original and compact
full archives are never simultaneously resident. Existing bounded64 KiB native
upload scratch and source DVD scratch remain. No new loading buffer is allocated.
New two-table metadata costs32 BSS bytes; OSThread layout/size is unchanged.

The enemy body is2,151,424 below the original3,577,728 request. Including selected
cache capacity1,007,936, metadata2,336 and conservative146 allocation overheads
14,016 leaves a **provisional net family budget reduction1,127,136**. This is not
a completed encounter peak. After actual body allocation, the remaining cache
budget deficit is **983,264**, before more actor/event/audio work and any extra
clips required by completed source/concurrency closure. Previous983,200 shorthand
excluded the now-observed64-byte body allocator charge.

Normal-game cache counters, read from the halted target RAM using this ELF's
symbols: 2 misses,1 successful load,0 evictions/hits;22,400 bytes read and peak
cached payload;0 pinned bytes (no evaluation reached);2,336 metadata;
210,892 us worst successful resource wait. The second payload16,608 requests
16,640 with its32-byte owner header and fails against16,096 free. Source allocator
adds another64 on successful allocations. This is an explicit game halt; the
capture harness continued to its90-second deadline. Warm-up was **not** reached.

D325's separate SH-4 fixture still establishes75 loads/952,768 bytes at warm-up,
100 repetitions/7,500 evaluations with **zero new misses/bytes**, peak cached
981,440/pinned32,416 and273,519 us worst wait. Do not relabel it live-game or
physical-disc evidence. Hot keys remain retained and nonvictims; release only
ends the evaluation pin. Source header/key-table restoration and relocated keys
remain checked across pressure/eviction/reload. The source prefetch/concurrency
audit remains incomplete: indirect R1/event selection, Work aliases and complete
instance/blend/shape/camera overlap must still be closed. Do not shrink the hot
set or use per-evaluation eviction to pass initialization.

### New stall resolved, validation and identities

`d327-player-weapon` and `d327b-enemy-read` preserve the original stall. Two RAM
snapshots15 seconds apart show DVD queue flags0x82010123, step1, MRAM copied0,
first128 KiB piece outstanding. Background task4 is parked at the source suspend
gate inside KOS `iso_read`; the main thread waits on `fh_mutex` in `iso_open`.
That owner cannot be suspended until its locks are released. With the bounded
I/O guard, enemy read completes (`DVD: Read Ok 431`) and sound block8 dispatches.
This is loading correctness, not an FPS gain or audible-output acceptance.

Checks:12 focused native I/O, cancellation/cache pointer, identity/ownership,
fixed reservation and compact-archive tests;30 existing room/mirror tests.
PowerPC preprocessed source tokens remain identical at affected source hooks.
The actual33 new descriptors pass separate ASan/UBSan shared-native package
relocation/upload/release/reload checks.32 unique native payloads total659,968
VRAM bytes if all resident; host sums with aliases are649,216 player and27,136
weapon. Neither is measured simultaneous target VRAM or visible actor acceptance.
The same complete shared native cache/budget is used. Existing em12 DRS/ARC outputs
remain byte-identical to D326; an initial private regression command confused
archive ordinal with source ARC index and was rejected, then corrected. No such
incorrect selection was used in the target build.

Final evidence: `C:/Flycast-Evidence/re4-dreamcast/d327c-io-guard`, validated
`evidence-manifest.json`, exact executable/disc, source and dirty patch, asset and
fixture identities, corrected source-menu framebuffer, snapshots and counters.
ELF SHA256 `63b546f8bc51992afc63b6efab66e2a2a7d88ae22b2d3ad0da1f17948efb2501`;
disc `82a76f627d8c4ccfa2d18898247eccf0144882e95add5ab7e8888147f28e2b1d`.
Text/data/BSS2,277,712/75,620/672,760; SH GCC15.2.0 and KOS
`804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`, exact Flycast/config in manifest.
No timed workload overlapped another emulator or Blender run.

Private preparation `/root/probe/d327-pl00`, `/root/probe/d327-wep02`, unchanged
`/root/probe/d326-combined`, mirror `/root/probe/d327-mirror`, fixtures
`/root/probe/d327-fixtures`, final disc `/root/probe/d327c-disc`.
Build `CORE_RESIDENT_BYTES=1501312 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776`.
Keep this selectable implementation and the measured negative full-fit result.
Continue justified source resource lifetimes and complete working-set closure,
alongside the existing 3D connection. Enemy creation, effects/audio, source hold,
visible complete models, manual gameplay, transitions/retry and physical hardware
remain open. A loaded archive is not initialized or playable gameplay.


## D328: resident effect records and retained generator references

Decision: keep a **selectable** lossless layout, not complete encounter acceptance.
The existing source loader consumes the smaller em12 body in the recovered-game
executable. Corrected source title/menu, required block pool and source sound
container dispatch still work. No enemies/events/hold flags were disabled.
D327 remains a reproducible before reference; D324 is the accepted integration
reference. The original GameCube behavior remains authoritative.

### Source contract and reused connection

| Existing mechanism | Source producer/consumer | Narrow addition |
|---|---|---|
| `le_mirror::fmt_sequence`, qualified DRS preparation, `compact_spans`, `replace_native_payload` | em12 EFF slot0 EST tables, original48-byte heads and relative offsets | Sequence observer and selectable zero-word record representation; append borrowed ESQ identity index before existing NTR/MTC. |
| Existing `readEmData` / `InitModule` archive ownership | Source effect tables and their controllers | Validate/bind ESQ before consumers, unbind after REL epilog and before source archive free. No new heap/cache/transport owner. |
| Original `EspgenDataSet`, `espgen10_Update`, `EspgenSeqSet`, `SetEstTbl`, `EspEstSetSelect`, `EspSeqSet` | Logical record index, Set_time, parent, parameters, RNG and dispatch | Resolve index to raw or opaque resident reference; reconstruct native words locally only when consumed. No scheduling/event/RNG changes. |
| Original `Espgen00_SetFreeWork` / repeating `espgen00_Update` | Retained record pointer used on later emission frames | Preserve the archive reference in `p->rec`; constructor reads local scratch, later `EspSeqSet` resolves the retained reference. Never store scratch. |
| Existing motion residency SH-4 fixture / shared storage | Same selected keys, source motion/IK, pressure/pointer checks | Optional effect checks from source-derived byte hashes; unchanged warm-set and pressure tests. |

All161 sequence heads, IDs/order,1,854 effect records and source flags remain.
Record count/offset table selects12-byte zero-word mask plus exact nonzero32-bit
words, or ordinary300-byte records. Negative zero, NaN payloads, integer lanes,
colors/padding and every other bit survive; this is not float quantization.
Only observed copy-consuming effect IDs and generator00 qualify. Sprite0x0e
retains `gen`; generator02 retains `rec`; unreviewed types stay ordinary.
All eight actual excluded records are retained raw. Generator00's reference
may survive arbitrarily many frames while the original archive remains alive.
No effect record is evicted or fetched from disc during evaluation/emission.

The source audit distinguishes original lifetime boundaries: registration keeps
EST heads/tables; delayed sequence player10 keeps its head; repeating00 keeps its
record; source owner/module teardown ends those lifetimes. em10's0x88 path reads
head count then uses the adapted `EspEstSetSelect`. em36 mutates owner0x2d records
and is outside this em12-only candidate. Debug editor bulk record read/write and
other owners are not qualified. The unchanged original representation remains
available. Full in-game cleanup/retry is still an acceptance gate; host relocation
checks are not a claim of a played transition.

### Actual budget and cost

| Measurement | D327 | D328 |
|---|---:|---:|
| Source heap arena |9,987,168|9,987,168|
| Required block pool / free afterwards |1,126,272 /1,477,696|same|
| Enemy body loaded |1,426,304|1,105,152|
| Free immediately after enemy allocation |41,024|362,176|
| Successful hot payloads before next OOM |1 /22,400|29 /356,416|
| Free at next failed key request |16,096|544|
| Remaining selected cache-budget deficit |983,264|662,112|

EST sequence backing566,304 becomes243,168 bytes plus1,984 index bytes: **321,152
net actual source-heap recovery**, including alignment and metadata. New native
binding/statistics cost96 BSS bytes and code3,628 bytes; no source-heap metadata
allocation. Each local scratch is300 bytes; up to four nested source calls add
1,200 bytes of scratch, excluding their other stack frames. Existing corrected
task stacks remain. Texture packages/VRAM, collision, models and all key files
are unchanged. Compact type0 reads directly into its smaller final allocation;
there is no full original/decoded overlap. Existing bounded64 KiB native storage
scratch and source DVD/sound staging are retained, not newly counted as savings.

Total body reduction against3,577,728 is2,472,576. Subtract selected cache capacity
1,007,936, metadata2,336 and conservative allocator overhead14,016: **provisional
net enemy-family budget reduction1,448,288**. This is not a measured full encounter
peak. The current selected profile still needs662,112 more bytes after body load,
before future actor/event/audio or additional required motions. Do not count
already recovered room/core/primitive/player/weapon backing again.

Actual game counters:30 misses,29 loads,0 evictions/hits,356,416 bytes read and
peak cached payload,0 pins,2,336 metadata,210,286 us worst successful resource
wait. The next9,664-byte key requests9,696 including owner header and fails with
544 free (successful source allocations add64 further bytes). This is an explicit
`motion key allocation` game halt; the capture harness then reaches its90s limit.
The game has not completed cache warm-up or enemy initialization.

### Verification and current prefetch/concurrency limit

Native host ASan/UBSan checks compare **all1,854 actual records** with the original
source-converted sequences. The actual recovered generator00 constructor is
compiled in the fixture:1,362 generator records preserve RNG count/initialized
state, retain the correct reference after return, and reproduce later emissions'
record bytes100 times. Relocation/rebind preserves every record; tagged references
are rejected after unbind. Unsupported records stay raw. Malformed spans/counts,
indices/masks and duplicate binding are rejected. Six source PPC preprocessed
units remain unchanged. Existing cache cancellation/pointer and archive/format
checks pass; this is not a replacement for in-game effect appearance acceptance.

Refreshed SH-4 fixture in Flycast:

- 75 initial hot misses /952,768 bytes;100 repetitions /7,500 evaluations then
 **zero additional misses or bytes read**. Hot keys remain nonvictims after pin release.
- Separate pressure phase:185 cumulative misses/loads,34 evictions,2,743,392 bytes
 read; peak cached981,440, peak pinned32,416, metadata2,336, worst wait273,518 us.
 Every relocated key and retained source table pointer is checked across reload.
- Four original motion/IK poses,34 parts/26 joints: errors0.00000381 root,
 0.00000003 angle,0.00036621 world, within existing bounds.
- All 1,854 effect records x100 produce original byte hashes. No effect heap
 allocations or post-load I/O. Total checked walk12,006,029 us includes fixture
 hashing and lookup; worst measured record decode2,553 us includes preemption.
 O2 fixture timing is not the O1 game's effect/frame budget or hardware timing.

The source-derived prefetch/concurrency audit remains beside both runs.75 hot
clips/952,768 plus55,168 cold reserve is a **diagnostic incomplete** profile, not
an inference from one replay or only simultaneously executing functions. Indirect
R1/event selections, Work aliases and complete instance/blend/shape/camera overlap
still require closure. Do not shrink this set, auto-evict on release, or promote
this candidate to claim complete encounter memory fit.

### Reproduction and evidence

Private producer output `/root/probe/d328-effects`; mirror `/root/probe/d328-mirror`;
unchanged fixtures `/root/probe/d327-fixtures`; game disc `/root/probe/d328-disc`.
Use existing `prepare_enemy_motions.py --compact-effects --textures <existing-tex>`
with the existing `--hot-audit` and explicit diagnostic-incomplete flag. All145 key
files/hot labels and37 texture identities match D327. Full reference/previous
compact representations remain selectable. No asset defaults are promoted.

Build flags remain `CORE_RESIDENT_BYTES=1501312 PLAYER_RESIDENT_BYTES=846656
WEAPON_RESIDENT_BYTES=247776`. Native fixture `/root/probe/d328-cache-sh4` uses
existing `Makefile.residency`, `/root/probe/d325-real`, source model440/motion1 and
`/root/probe/d328-cache-data`, including source-derived `effects-checks.bin`.
The fixture's log-only mem.cpp compilation now supplies the newly required
player/weapon reservation macros; it does not claim source-heap fit.

Evidence `C:/Flycast-Evidence/re4-dreamcast/d328-resident-effects` and
`d328b-residency-fixture`: validated manifests, exact executables/discs/assets,
source/dirty snapshots, compiler/KOS/Flycast/config/capture identities, checks and
counters. Corrected title framebuffer was inspected; no blue capture accepted.
Game ELF SHA256 `1c478a2be42a73ded78ec657bcb69254c7b86cb5492de25701591a45403326d1`;
disc `0855447c8ce3a69b3d66b948766e0fce6c8501d1c98f773f830b009924899090`.
SH GCC15.2.0, KOS`804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`;
text/data/BSS2,281,340/75,620/672,856. No emulator or Blender run overlapped.
The first private comparison used pre-compaction offsets against a post-texture
reference; it failed before acceptance and was corrected to match EST identity.
No source/candidate record bytes were changed to make the comparison pass.

Keep this measured candidate and continue remaining allocation-backed recovery
and complete source working-set closure alongside the existing 3D adapter.
Source hold, complete actor/effect rendering, required audio/events, manual combat,
transitions/retry and physical hardware remain open. A resource fixture or a
loaded archive does not establish those outcomes.


## D329: demand-backed source parts

Selectable `PARTS_DEMAND=1` reuses `cPartsMgr::createSequential()`, the source
`cManager` create/destroy/list rules and `cModel::makePartsList()` fallback.
`parts_bridge.cpp` is the new native backing adapter. It retains the original
logical slot order/capacity, native472-byte cParts layout, constructors, stable
per-model contiguous runs and linked-list fallback. Other managers keep their
original contiguous backing. No asset, animation cache/profile, renderer,
source pose, gameplay, event, collision or model-content change was made.

The manager's pArray is a private slot directory in this candidate. Audited
consumers are PartsMgrWork, create/createBack/indexed create, dieCheck,
countActiveWork/destroyAll, debug count displays, event-loop templates and
getPrevWork. Model consumers retain cParts pointers and the existing be_flag
0x2000 contiguous-versus-linked contract. All array scans use the native slot
accessor; unbacked slots are free, not dummy objects. `createSequential(0)` keeps
its source one-slot behavior; invalid oversized requests fail safely.

Partial/deferred deletion cannot release a chunk containing live/reserved parts.
Freed runs normally stay cached for reuse; fully dead overlapping runs can be
replaced, and allocation pressure can reclaim other wholly dead runs. No live
part moves. The directory records the owning source heap/handle; new runs use
that heap and retirement frees to that owner. Source roomInit continues to forget
backing after its room heap reset; arrayFree follows the original caller-owned
destruction order. Ordinary subscreen managers are independent. Debug array
push/pop parks/restores the directory and uses the original raw tool array.
Debug_flg[3]0x200000 bulk tool-memory sweeping is explicitly unqualified and
rejected by this opt-in candidate. Default `PARTS_DEMAND=0` retains full backing.

### Matched source heap results (Flycast)

| Measurement | D328 | D329b |
|---|---:|---:|
| Source heap arena |9,987,168|9,987,168|
| Required block pool request |1,126,272 succeeds|1,126,272 succeeds|
| Free after block request |1,477,696|2,018,048|
| Enemy archive request |1,105,152 succeeds|1,105,152 succeeds|
| Free after enemy request |362,176|902,528|
| Parts resident at prefetch, including allocator |618,400|176,544|
| Motion successful loads / bytes |29 /356,416|63 /793,984|
| Free at next failed key |544|1,568|
| Remaining full diagnostic cache-budget deficit |662,112|220,256|

The **540,352-byte** gain at both request points is real, but later block parts
consume another98,496. Sustained recovery before prefetch is **441,856 bytes**.
319 live slots in198 chunks use176,544 bytes, including5,376 directory bytes,
per-chunk32-byte headers, alignment and64-byte source allocator/tag overhead.
All1,310 target slot entries were checked against chunk bounds;319 were valid
live pointers and991 unbacked. Peak parts backing so far176,544; no reclaims or
parts allocation failures in this run. Future source parts may grow; this is
not an encounter-wide peak. No full pool is retained alongside the directory.

The enemy body remains1,105,152, reduced2,472,576 from3,577,728 by D325-D328.
This candidate's additional savings belong to PartsMgr, not the enemy archive.
Full selected cache1,007,936 +metadata2,336 +conservative allocation14,016 minus
804,032 free before motion metadata leaves220,256 still needed. Provisional
net enemy-family reduction remains1,448,288 with that complete cache budget;
actual complete-enemy/encounter peak and source hot/concurrency closure remain open.

Game cache:64 misses,63 loads,0 hits/evictions,793,984 resident/peak/read bytes,
0 current/peak pins (evaluation was not reached), one failed5,696-byte payload
requesting5,728 before source allocator costs. Worst successful resource wait
**241133us**. Failure is an explicit missing-allocation halt;
the90-second capture deadline terminates the already halted diagnostic. It is
not another stack/subscreen crash and not completed warm-up.

The D328b SH-4 cache fixture remains the unchanged reference:75 prefetch misses,
952,768 bytes;7,500 warm evaluations add no misses/reads. Pressure testing reaches
981,440 peak cache,32,416 peak pins,185 cumulative misses/2,743,392 read bytes,
34 evictions and273,518us worst successful wait, checking every relocated key
and retained source key-table pointer. Those are separate fixture numbers,
not D329 game scheduling/performance. Source prefetch audit remains
`/root/probe/d325-prefetch-final.json`: indirect R1/event/Work aliases and full
instance/blend/shape/camera response/concurrency coverage are still incomplete.

### Verification, identities and disposition

Final evidence `C:/Flycast-Evidence/re4-dreamcast/d329b-parts-demand`; initial
candidate retained separately in `d329-parts-demand`. Corrected source menu
capture, RAM snapshots, complete selected asset manifest, symbols, build source,
dirty diff, fixtures, emulator/config/capture tools and result.json accompany it.
ELF SHA256 `a4903f8dfe386935e16612c6e8b113d06b2f385f414c1e100e35ceb8470cbf25`;
disc SHA256 `4136a9dd2109824769ff63decaee34f20864b36c1b2241dcc23522b3791679f6`.
Base32abdcf plus the recorded candidate/inherited dirty work. KOS804b3195,
SH GCC15.2; text/data/BSS2,283,540/75,620/672,856 (+2,200 code, unchanged BSS).
Build with prior core/player/weapon budgets plusPARTS_DEMAND=1. Mirror and fixture
are unchanged `/root/probe/d328-mirror`, `/root/probe/d327-fixtures`;
private packaged disc `/root/probe/d329b-disc`.

Host ASan/UBSan (excluding vptr for the source pool's unconstructed slots)
executes the real manager/sequence algorithms and adapter against synthetic
parts, in full and demand modes. It checks contiguous/partial/deferred lifetimes,
source zero-count behavior, repeated reuse without allocation, full capacity,
failure without moving live parts, debug park/restore, independent heap owners
and room-reset invalidation. Four motion and three effect regression tests pass.
PowerPC preprocessed output is unchanged across all six edited shared files.
Host ABI shims and target319-slot inspection do not certify played retry.

**Keep selectable**, with no default promotion. Source menu, required blocks,
body load,37 texture identities and sound-container dispatch remain intact.
No complete enemy initialization, visible full3D, audible/manual gameplay or
physical hardware acceptance. Additional directory lookups/creation scans and
allocation work have no measured rendered-workload CPU/FPS claim yet. Next
resource recovery must close the220,256-byte lower bound and later actor/event/
audio needs while preserving this hot set, its source audit and native3D work.
Core/effect record packing was priced at roughly150KB additional potential,
not implemented or qualified for other owners; do not count it as freed memory.


## D330: completed hot prefetch, core EST and model-info backing

This selectable candidate extends two existing mechanisms. It does not reduce
the motion hot profile, geometry, actor components or source manager capacities.

| Existing mechanism | Source connection | Small native adaptation |
|---|---|---|
|`compact_effect_records.py`, qualified converter, `compact_spans`, ESQ record reader|`CoreDataRead` -> `EspInit` core EFF slots1/16, owners0/D1 -> existing `EstSet`/`EspEstSetSelect` and repeating generators|Opt-in core EST ranges and a separate persistent core binding; four module bindings remain available.|
|D329 `parts_bridge.cpp` owner/run backing and source `cManager` algorithms|`cModInfoMgr` create/destroy and source models' retained`pModelInfo`/`pList` pointers|Instantiate existing backing for model-info,16-slot pages; no live pointer moves.|
|Source enemy module constructor|`cEmMgr::construct` installs`subArc` -> `Em12Init` -> `em10_R0_Init`|Native default-initialization preserves the manager-installed pointer; PPC keeps the original spelling.|

### Core and model-info ownership

Core archive1,501,312 -> **1,360,608**,140,704 actual bytes removed from its
fixed reservation, including the appended ESQ index and unchanged59 NTR identities.
143 sequences/791 records use the qualified reader; all175 sequences/891 records
remain. Five sequences with nonzero unexplained trailers remain ordinary,
including every trailer byte. Noneligible retaining sprite/generator records
stay raw. No source effect, palette/noise/mip semantics, RNG operation, sound
container or texture encoding is dropped. The original core family/parser gates
remain; VIB/SAT qualification is not implied. Unselected families retain their
converted bytes. Other owners and debug effect editing are not newly qualified.

The existing codec reconstructs exact300-byte records into caller-owned scratch,
without heap allocation, disc reads or a decoded bank. Core binding borrows the
ESQ index until core reload; `CoreDataRead` unbinds before overwrite and binds
before source initialization. Stable source heads survive. Existing retained
generator references resolve through the live binding. One extra16-byte binding
is added; final ELF BSS does not grow because of layout padding. The existing
nested-call stack qualification remains, not a new unbounded decode stack.

Model-info has no audited cross-slot pointer arithmetic or raw manager-array
readers; source models retain individual records and linked lists. Existing
D329 owner/retirement, deferred flags, debug park/restore and pressure rules are
reused, with16-record pages. All460 slots remain available. Partial/deferred
releases cannot free a page holding another live record. Dead pages remain
cached. No second full pool is retained. EmMgr stays contiguous: its many raw
consumers prevent treating sparse conversion as another equivalent small change.
Default`MODELINFO_DEMAND=0` preserves full allocation.

### Matched loading measurements

| Source point | D329b | D330b |
|---|---:|---:|
| Source heap arena |9,987,168|10,127,872|
| Free after required1,126,272 block allocation |2,018,048|2,276,864|
| Free after1,105,152 enemy body allocation |902,528|1,161,344|
| Free before motion metadata |804,032|1,015,168|
| Model-info backing at prefetch, incl allocator |134,400|63,968|
| Successfully prefetched clips / bytes |63 /793,984|75 /952,768|
| Free after selected hot prefetch |not completed|52,768|

Early gain258,816 includes118,112 model-info recovery. At205 live model-info
records the backing has grown to63,968, leaving70,432 sustained recovery plus
140,704 core = **211,136 incremental bytes before prefetch**. Original
PartsMgr savings remain separate; additional parts/metadata still grow later.

Enemy body remains1,105,152:2,472,576 less than original3,577,728. The actual
warmed family adds952,768 cached files,2,336 slot metadata,76 allocations at
96-byte adapter/allocator overhead, and the enemy body's64-byte overhead:
**2,067,616 total versus3,577,792 original =1,510,176 net recovery**. This
candidate does not shrink the body again. Full selected-cache capacity1,007,936
with conservative14,016 allocator costs gives provisional1,448,288 net recovery;
that budget still lacks9,120 before later resources. This is a conservative
reservation calculation, not measured eventual full-encounter occupancy.

Game motion counters:75 misses/loads,6 hits,0 evictions/failures,952,768 current
and peak cached bytes,952,768 read bytes,0 current/22,400 peak pinned bytes,
2,336 metadata,**270941us worst successful resource wait**.
The source still pins only for evaluation safety and leaves unpinned hot/cold
cache entries resident; cold eviction remains pressure-driven, hot entries are
not victims. No cache-policy code or source hot-set selection changes in D330.

RAM verification checked all145 persistent source proxy headers, all75 live
cache payloads and1,904 relocated key pointers against exact selected files.
Full payloads match after accounting for table relocation; persistent headers
remain unmodified. Target manager checks validate every1,310/460 slot pointer.
Later snapshot PartsMgr:413 backed/395 live,224,448 peak,232 runs,2 failed growth
attempts; ModInfoMgr:224 backed/live,68,736 peak,14 pages,4 failed attempts.
These are peaks of a failed initialization, not accepted gameplay peaks.

The initial snapshot catches prefetch in progress. The later one records6 real
source cache hits with no extra misses/reads beyond the75 prefetch loads. That
is narrow game evidence; unchanged D328b SH-4 fixture remains the repeated-use
reference:7,500 warm evaluations,0 additional misses/bytes, with pressure testing
981,440 peak cache/32,416 peak pins,185 misses,2,743,392 bytes,34 evictions and
273,518us worst wait. Pointer release/eviction/reload/cancellation coverage is
retained and the host motion tests rerun. Do not combine these fixture counters
with live-game timing or infer a completed response/concurrency audit.

Source audit`/root/probe/d325-prefetch-final.json` remains with the candidate:
indirect R1 dispatch, event/Work aliases, complete immediate-response/repeated-use
closure, and active instance/blend/shape/camera concurrency are still open. Do
not replace that audit with either six hits or the fixture's selected75 clips.

### Next exact failures and constructor correction

The normal fixture delivers title0008 then0100 and leaves title5/1 through5/3,
7/3 to source game room initialization. Required block/enemy allocations,
37 enemy texture identities, static em12 prolog and selected prefetch succeed.
The first subsequent request is`r100::setTexRender -> GetTexRenderMgr ->
TexRenderMng::AllocBuf`:65,536 with51,616 free,13,984 short including64 overhead.
This water target starts128x128 RGBA8 then source sets64x64. Follow its actual
copy/CPU/native consumers before changing backing, capacity or lifetime. Do
not disable the water or report a failed optional subsystem as accepted.

D330's first replay separately exposed`EspDataLoad EM10:NULL` and Ganado model
failure. SH-4`Em12Init` disassembly showed a0xDE0-byte memset generated by modern
value-initialization, erasing the source manager's archive pointer. Native
`new(em)cEm10` now calls the base constructor and installs the vtable without
that memset; PowerPC preprocessing remains unchanged. D330b removes the null
archive/model errors, constructs the enemy's source parts and reaches evaluation.
Other modules need the same issue checked when integrated, not bulk-edited.

Later room model creation fails a30,240-byte contiguous run, tries the original
linked fallback, then exhausts smaller parts/model-info/collision/path requests.
Native output is **visibly incomplete**; resource failures and packet overflow
are recorded. The capture deadline ends the90-second run; these are actual
allocation failures before the harness exit. No source hold/black flag was forced.
Event/ARAM/audio support, target render-to-texture, full native scene/materials,
responsive manual combat, retries/transitions and physical validation remain open.

### Verification and identities

Host tests:four full/demand manager combinations with actual source manager
algorithms; exact core record reconstruction, delayed generator retention,
archive relocation/retirement and independent core+four-module binding capacity;
synthetic combined ESQ/NTR conversion with raw-trailer preservation; source enemy
constructor lifetime; existing motion cache regression.13 test methods total.
Actual core fixture checks891 records,334 retained generator cases,180 raw reads,
30,106 decode calls,0 I/O/heap allocations. Original default core producer is
byte-identical to D324/D329. PPC preprocessing unchanged for cManager/read/em12.
No new full dual-emulator framework or raw assets enter Git.

Final evidence`C:/Flycast-Evidence/re4-dreamcast/d330b-core-modelinfo`, initial
`d330-core-modelinfo` retained. Includes source menu/incomplete3D, RAM, exact
assets/fixture/emulator/config/capture tools, source snapshots and result.json.
ELF SHA256`a258704f368124d9b4e57b2b3282ac9940488b73abe654f2479b62258f0bf80c`;
disc SHA256`1a523ae9c2465431a4f576dec188a33796f0090f768d08aeecde3318204d3474`.
Base4b85a3f plus recorded owned/inherited dirty work. KOS804b3195,SH GCC15.2;
text/data/BSS2,285,452/75,620/672,856 (+1,912 text, unchanged BSS vsD329).
Build`CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1`.
Use private`/root/probe/d330-mirror`,`/root/probe/d330b-disc` and unchanged
`/root/probe/d327-fixtures`; generator`--compact-core --core-effects --compact-core-est`.

**Keep selectable, not promoted to accepted room/default assets.** The source
menu remains visible and selected cache warm-up now fits. Follow the demonstrated
water/model/collision and full3D dependencies without dropping hot responses,
required content or concurrency coverage. This checkpoint does not complete
the persistent menu-plus-three-room objective.

User steering after D330: simpler water is an authorized selectable candidate.
First distinguish equivalent target right-sizing from a cheaper visual effect.
Preserve gameplay/collision/events; measure RAM/VRAM/CPU and inspect source-aligned
views before accepting a quality trade. PS2 behavior must be inspected before
claiming its water technique or equivalent appearance.


## D331: source-configured water target allocation

The native r100 path calls `GetTexRenderMgrSized(64,64)` before the existing
`TexRenderMng::AllocBuf`. It no longer reserves 128x128 and then changes only
the source copy/texture dimensions to 64x64. Other callers retain the default
128x128 target. Source target ID 0xF8, mask 8, effect creation, two water objects,
material table, viewport/copy dimensions and owning room heap are preserved.
The PPC preprocessing of all three changed source/header files is unchanged.

This is an allocation correction, not a lower-resolution water effect. Inspection
of `RenderTexRenderMgr`, `CopyTexRenderMgr`, target lookup and r100 found no
consumer of the unused outer buffer area. The source copy descriptor is RGBA8,
64x64 with no sampled mip chain; the EFB source is 128x128 with downsampling.
Native `GXCopyTex` is still a placeholder, and the native material bridge rejects
the relevant multi-texture flag. Actual water rendering and any selectable simpler
approximation remain open. No PS2 visual equivalence has been established.

| Matched source allocation | D330b | D331 |
|---|---:|---:|
| Free before water | 51,616 | 51,616 |
| Requested payload | 65,536 | 16,384 |
| Result | failure | allocated |
| Actual consumed including allocator | 0 | 16,448 |
| Free after attempted allocation | 51,616 | 35,168 |

Required capacity falls **49,152 bytes**, but actual free memory compared with
the failed D330 request falls 16,448. Block/enemy allocation points are unchanged
at 2,276,864 / 1,161,344 free. There is one allocation and no full-size temporary,
second buffer or loading overlap. ELF text grows 136 bytes; data/BSS unchanged.
This change does not recover another byte from the enemy archive/cache.

The first later failed request is a 2,400-byte parts run with 2,240 free
(224 short including 64-byte allocator cost). Source falls back to linked parts,
then 512-byte runs fail; `R100Init : set failed`, collision and path allocation
failures follow. The capture stops at its 90-second deadline; actual failures
precede that stop. Event requests still use unqualified native ARAM semantics.
The preserved source menu is visible; the room/Leon/HUD image is incomplete and
is not character, water, scene or gameplay acceptance.

Cache snapshot: 6 hits, 75 loads/misses, zero evictions/failures;
952,768 current/peak/read bytes, zero current and 22,400 peak pinned bytes,
2,336 metadata, 270939 us worst resource wait. All 145 source
headers, 75 cached payloads and 1,904 relocated key pointers match exact files.
Enemy family remains 2,067,616 including actual warm cache and allocator costs,
1,510,176 net recovery versus original. Six hits do not establish sustained live
working-set stability; D328b's unchanged repeated-use/pressure fixture remains
separate. Source prefetch/immediate-response/concurrency closure is still open.

Target manager verification: PartsMgr 383 backed/live, 207,584 resident/peak,
206 runs, 24 failed attempts; ModInfoMgr 224 backed/216 live, 68,736 resident/peak,
14 pages, no failures. All logical slot mappings validate. Different failed
initialization paths are not a matched full-encounter peak comparison. A bounded
inventory also records ObjMgr 334,624/340 slots/203 live and EmMgr 213,184/60
slots/14 live. Neither is newly sparsified. Retained indexed object pointers,
especially future light parents, require backing through the source pool lifetime.

Verification: two host tests execute actual source acquisition/Init/AllocBuf/copy
code with ASan/UBSan guarded buffers, default and configured sizes, target IDs,
failed allocation, eight-target limit, room-reset reuse and input overflow.
Mock GX writes qualify the buffer boundary only. The second test compares PPC
preprocessing with 9c604ad. The game links and replays the unchanged source menu
fixture through selected hot prefetch and successful water allocation. RAM reads
verify `g_RndMgrNum=1`, size 64x64, buffer 0x8cfc2f20, ID 0xF8 and mask 8.
No hardware, FPS, manual combat, audio, retry or complete-room claim.

Evidence: `C:/Flycast-Evidence/re4-dreamcast/d331-water-size`; disc
`/root/probe/d331-disc`; unchanged `/root/probe/d330-mirror` and
`/root/probe/d327-fixtures`. Exact ELF/assets/emulator/config/input/capture-tool
identities, source snapshots, RAM, logs, captures and validation are in the
manifest. Base 9c604ad plus recorded inherited and owned changes. KOS 804b3195,
SH GCC15.2; text/data/BSS 2,285,588 / 75,620 / 672,856.
ELF SHA256 `85cc8fd99582523ffbaa8ed6ef17e93826dfa04b43fe4a1714a3012038beffe3`;
disc SHA256 `6d5fe2b98e590c59cda86e0509ec2530884f85bbe8d12597b5b662fd204b096f`.
Build: `CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1`.

**Keep** the correctly sized source target. Continue the remaining required
model/collision residency and native scene connection. Simpler water remains
an authorized, separately measured and visually reviewed candidate; it must
preserve source collision/events and cannot substitute for missing integration.


## D332: stable object pages pass the room allocation frontier

`parts_bridge.cpp` now supports opt-in `OBJECT_DEMAND=1` through the existing
`cManager<cObj>` source algorithms. The reused allocator retains source heap
ownership, slot directory, zero initialization, constructors/destructors, ordering,
logical predecessor, debug array parking and room reset semantics. Its only new
policy is eight-slot object pages that remain allocated until source pool teardown.
The default full pool remains available; no renderer or archive format is added.

Why object lifetime differs from model-info: `cLight::calcParent` can store a raw
slot pointer before construction, and a dead slot can be reused at the same address.
`ObjMgrWork` therefore commits its page before returning an indexed pointer, without
constructing an object. Scans use `workAt` and skip never-backed zero slots. Retained
pages are not pressure victims. Source scan order and dead backed records remain;
no live object moves and all 340 logical slots are still usable.

Audited direct consumers include block visibility, ladders, source enemy/object
searches, light parent mapping, effect-model cleanup, debug camera/work and indexed
tool helpers. Alias readers through `cObjMgr*` are included. The existing
`getPrevWork` is adapted to logical predecessor across physical pages for scroll
groups. Unintegrated later modules are not runtime-qualified by these edits.
PowerPC preprocessing matches the pre-edit source in all 18 affected shared files.

### Actual memory at source boundaries

| Source point | D331 | D332b |
|---|---:|---:|
| Source arena | 10,127,872 | 10,127,872 |
| Free after required block pool | 2,276,864 | 2,582,048 |
| Free after enemy body | 1,161,344 | 1,466,528 |
| Free before water | 51,616 | 189,472 |
| Free after water | 35,168 | 173,024 |
| Object backing including overhead, later snapshot | 334,624 | 212,704 |
| Backed/live parts | 383/383 | 527/527 |
| Parts allocation failures | 24 | 0 |

The early 305,184 recovery shrinks as source objects allocate: 137,856 before
water, **121,920** later. Final object directory is 1,504 bytes, pages including
headers/allocator 211,200, 27 pages/212 backed/206 live. No staging or second full
pool is retained. Object resident peak equals 212,704 in this observed run.
Parts grow to 276,992, model-info to 73,504; these are successful additional
requests, not regressions to conceal. Required 2,400/30,240-byte runs and source
collision/path setup now proceed. All directory entries for 1,310 parts, 460
model-info and 340 object slots validate against their actual owning chunks.
No failed native room allocation or `R100Init : set failed` is in the 135-second
run. Later source heap has 41,472 free; not a complete encounter or transition peak.
No new VRAM resource or geometry change is introduced by the backing adapter.

Enemy archive/cache content is unchanged: actual warmed family 2,067,616,
1,510,176 net recovery from original. Cache counters: 75 misses/loads, 6 hits,
zero failures/evictions, 952,768 current/peak/read bytes, 22,400 peak pinned,
2,336 metadata, 270,939 us worst wait. All 145 retained headers, 75 cached
payloads and 1,904 relocated key pointers validate. The unchanged counters in
later/final snapshots accompany a stalled game, not accepted repeated gameplay.
D328b retains warm/pressure coverage; the source prefetch audit remains incomplete.
The only em10 source change is a nullable object scan; the evidence records old/new
hashes and exact delta without silently declaring the old audit complete.

### New execution frontier

The source reaches Rno0=3/frame1239 with game and scenario tasks present, all
required model parts allocated. It then stays at frame1239 through the 125-second
snapshot: main suspend/gate1, source System0x800, black framebuffer, zero native
model presentations. Native diagnostics have 21 committed parts, 8,512 peak packet
bytes, 8 resource failures, zero invalid/overflow counts. The final image is black;
this is not restoration of the earlier cabin. The visible menu capture remains.

The next source/native mismatch is `cSceSys::scheduler`: it deliberately sets
`pParentThread=0` around nested priority-14 tasks. The current native
`NativeTaskParent` substitutes main for all non-ISR tasks. That changes suspend/
resume ownership during scenario dispatch. Preserve the source per-dispatch parent,
including null, alongside thread-owned task identity; do not force hold flags or
return to the resolved post-title stack investigation. This checkpoint does not
include that scheduler correction. Eight model resource failures, material/
lighting/water connection and source event/ARAM/audio behavior remain open.

### Checks and identity

Eight host combinations of full/demand parts, model-info and objects execute the
actual manager/backing and indexed lookup. ASan/UBSan cover pre-construction
parent references, death/reuse without I/O/allocation, no pressure eviction of
dead object pages, cross-page predecessors, complete logical capacity, deferred
destruction, debug park/restore, owning-heap frees and reset without stale frees.
There are no active type-4 light parents in the target snapshot: that particular
retained-pointer scenario is source/fixture evidence, not live light coverage.
Both full and demand object modes link on SH-4; restoring the candidate reproduces
the captured ELF exactly. Played inventory/retry/room transitions remain open.

Final evidence `C:/Flycast-Evidence/re4-dreamcast/d332b-object-pages`, initial
`d332-object-pages` retained. Private disc `/root/probe/d332b-disc`, unchanged
D330 mirror/core and D327 fixtures. Base 54b99d2 plus recorded inherited and owned
changes. KOS804b3195, SH GCC15.2. Text/data/BSS 2,287,388 /75,620 /672,856:
+1,800 text, no data/BSS increase or source-arena loss. Exact sources, executable,
assets, emulator/config/input/capture tools and snapshots are in the manifest.
ELF SHA256 `ff1aac2773393f80aa371f35194e92acab393d9de718148bc1ad5874d04d5d58`;
disc SHA256 `66243305b397696b4ed28f87897a5c94b4bec0da93cecbd8a31f790b1d1739ee`.
Build `CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1`.

**Keep selectable.** No geometry, simulation, collision, motion hot set, water,
object capacity or gameplay content is removed. Continue the newly exposed
scenario handoff and connected scene path. No playable room, FPS, manual combat,
correct audio or physical-console acceptance; the three-room objective is active.


## D333: preserve the source nested scenario parent

D332's native helper replaced every non-ISR source parent with the main thread.
But `cSceSys::scheduler` deliberately selects null for nested scenario tasks.
That mismatch left main suspended at source frame1239. The native-only adapter
now records the source parent per `TaskSchedulerMain` dispatch, including null;
`TaskSleep` obtains the new dispatch's parent again after waking. It reuses the
existing scheduler and per-thread task-owner lookup; no new scheduler or global
hold override. Shared PowerPC preprocessing matches the pre-edit source.

The focused existing task-owner fixture executes actual scheduler/helper bodies:
root and nested dispatch, 100 sleep/wake cycles, parent changes during a wait,
TaskChain/TaskExit, ISR, stale global cursor and foreign-thread rejection. Native
SH-4 build passes. This is a source semantics correction, not an FPS claim.

### Observed progression and remaining rendering failure

Same normal menu/New Game fixture and assets. D332 stayed at frame1239 with
main suspend/gate1 and zero model presentations. D333 snapshots advance from
1246 to1346, main suspend/gate0; model presentations grow8 to108. The run ends
at its135-second capture deadline, not an observed crash. System0x800 remains.
The model and final framebuffer captures inspected at640x480 show **HUD over
black**, not a visible cabin. Source model submission is established; visible
room/complete-character acceptance is not. Counters at the final snapshot:
2,451 committed parts, 3,097,862 input triangles,73,406 emitted,0 invalid,
21,132 resource rejections,5,803 packet overflow failures,65,504 peak packet
bytes. Counts are cumulative and the snapshot can be mid-frame. The64KiB
prototype diagnostic cap and unsupported material/resource paths remain, as do
native lighting/TEV/fog/water. Do not hide the black world behind the word rendered.

### Actual memory, event transport and motion residency

Source arena remains10,127,872; required block and enemy body allocation points
retain2,582,048 and1,466,528 free respectively. Final relevant free41,472.
D332's source manager backing remains: parts276,992; model-info73,504;
objects212,704, with all slot-to-owner pointers verified and no manager failures.
This scheduler edit adds64 BSS bytes and removes48 text bytes; it recovers no
additional archive bytes. No new geometry/texture/staging representation.

Three new allocation failures are694,560,669,248 and309,632, each with41,472 free.
These are `datactrl.cpp(452)` ARAM-to-ARAM compaction scratch requests for
r100s41/s43/s44 after r100s40 is cleared, not three charged simultaneous heaps.
On allocation failure the source clears/re-reads that unit; logs show those
reads repeating. Critically, native `ARQPostRequest` currently completes without
copying: even an ARAM_OK log does not prove stored event data. Any replacement
must preserve actual file bytes, source ownership/swap and completion effects;
avoid a fake direct move or a new13MiB RAM allocation. Real event transport,
activation and audio remain unqualified. This checkpoint only fixes scheduling.

Motion cache:75 misses/loads,6 hits,0 evictions/failures,952,768 current/peak/read
bytes,22,400 peak pinned,0 current pins,2,336 metadata,270,940 us worst wait.
All145 retained headers,75 cached payloads and1,904 relocated key pointers match
the source data. Warm family cost2,067,616; net original recovery1,510,176.
Later/final cache counters unchanged with no new evaluation activity: no repeated
reload, but not a completed active-combat/concurrency audit. Keep the original
prefetch audit and D332 source-only delta; D328b supplies separate warm/eviction
fixture coverage. Do not shrink the hot set based on this held source state.

### Identity and decision

Base a885e51 plus captured inherited/owned edits. Evidence
`C:/Flycast-Evidence/re4-dreamcast/d333-scenario-parent`; private disc
`/root/probe/d333-disc`; unchanged D330 mirror/core and D327 fixtures. Exact source,
executable, assets, emulator/config/input/capture tools and snapshots preserved.
ELF SHA256 `3100e911a02e777f104812b0ff305ae83d756b0027fc0c0f6d6fb8a3bbcfce7b`;
disc SHA256 `74e11a79a0a0cfe5414b4c9e6d4d8d7fc38bd815c13a769390246cc22c8b403d`.
Build `CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1`. KOS804b3195, SH GCC15.2;
text/data/BSS2,287,340 /75,620 /672,920. No physical hardware run.

**Keep.** Continue existing world/UI connection and real event transport;
no manual gameplay, complete encounter memory, sound, FPS or water acceptance.
The first-three-rooms goal remains active. Simpler water remains an authorized
selectable candidate; D331's64x64 allocation is not an implemented PS2-style effect.


## D334: source-unit background depth

The existing frame owner `re4dc_ui_init` reused KOS's default background inverse
depth0.0001. The source-driven camera/model bridge uses original units and emits
1/(-camera_z). D333's final64,000-byte queue contains1,995 vertices with inverse
depth0.000020828..0.000036935: all behind that background, despite valid screen
coordinates and white diagnostic vertex colors. The pinned KOS `pvr_buffers.c`
sets0.0001; `pvr_misc.c` writes it into `PVR_BGPLANE_Z`. See the primary
[KOS API documentation](https://kos-docs.dreamcast.wiki/group__pvr__global.html).

The correction calls existing `pvr_set_zclip(0.0f)` when the existing PVR owner
initializes. Positive model depths now lie in front of the background. The
shared source-projection near/far clipper, camera/FOV, source geometry/materials,
texture selection, native packet data and presentation-hold logic are unchanged.
No additional renderer, source object representation or per-frame pass is added.

### Matched output, not complete scene acceptance

Both D333/D334 final source snapshots are frame1346 with108 model presentations.
The actual64,000 queued bytes are identical (SHA256
`6419d2eea7d53c24d622975b74bc347bdcf9dcdc86c40bd919386609f08eebab`).
D333 was HUD over black. D334 shows sparse distant textured branches at upper
right with that same HUD. Final1,601 changed pixels are confined to
x535..639/y60..182; model capture1,597 changed pixels. Menu comparison has zero
changed pixels at640x480. These tiny visible branches prove this native depth
connection; they are not a convincing environment or complete character render.

The diagnostic64KiB queue still overflows5,803 times and records21,132 resource
rejections; counters are cumulative. Most of the world/actors remain absent.
Next rendering work must expand the existing native submission mechanism safely,
preserve source material/alpha/order and hold semantics, and distinguish actual
unsupported materials from packet capacity. Do not merely enlarge a retained
second scene or import prototype gameplay. Event backing is an independent open
dependency: three ARAM compaction scratch requests still fail and the native
ARQ transfer still does not store bytes. Do not activate unqualified events.

### Memory and identity

Source arena10,127,872; post-block2,582,048 free; post-enemy1,466,528;
later41,472. Parts276,992, model-info73,504, objects212,704 resident/peak; all
manager slot pointers validate, no manager failures. No heap/BSS/data/VRAM/
packet-buffer change. Text increases32 bytes to2,287,372; data75,620/BSS672,920.
Cache75 misses/loads,6 hits,0 evictions/failures,952,768 current/peak/read,
22,400 peak pinned,2,336 metadata,270,940 us worst wait. All145 headers and1,904
key pointers validate. Family recovery remains1,510,176; no extra archive saving.
No additional evaluation after warm-up; active repeated-combat/concurrency
qualification remains open, with D328b's separate fixture retained.

Base6bb05a2 plus captured inherited edits and the native-only depth change.
Evidence `C:/Flycast-Evidence/re4-dreamcast/d334-background-depth`;
disc `/root/probe/d334-disc`; unchanged D330 mirror/core and D327 fixtures.
ELF SHA256 `efe1bf42d26e9e6ab138b6effecb7b9f172bf2d324c6ec9a0ae59fa2ca540192`;
disc SHA256 `7b148ff6ac9b68ab7b2596ab9fa3f6feca5cbccb72b7731dc00ee2286c4aa230`.
Same build options as D333, KOS804b3195, SH GCC15.2. Native link passes;
135-second Flycast capture ends by harness deadline. No additional source-game
or asset edits, no physical-hardware evidence. Exact source/asset/emulator/tool
identities, snapshots, private pixel/packet comparison and capture checks retained.

**Keep the background correction.** Complete room, character presentation,
water, gameplay, audio and FPS are not accepted. User-authorized simpler water
remains a separately measured candidate; no PS2-equivalence claim.


## D335: native strips and complete-part texture admission

### Existing connection and bounded change

Reuses `clip_projected_triangle`, `begin_pvr_packet`, `submit_pvr`, shared
`texture::Package`, storage staging and `gpu::quiesce`. The source producer is
still `commonModelTrans` -> `re4dc_draw_model_part`, using source-selected pose,
camera, part and material views. The existing frame owner still copies completed
native packets before source primitive storage resets, and presents at the same
source-controlled boundary. No source gameplay, asset or KOS driver changes.

`Builder::append_triangle` joins consecutive surviving triangles only when the
two shared vertices match bit-for-bit in every attribute, with PVR strip parity.
UV/color seams, clipping and source order are preserved. A failed whole part is
never committed. `re4dc_model_packet_reserve` exposes the existing free packet
range without texture I/O. After a complete part fits, the existing bind loads
the native package and creates the header. Default converter padding supplies
provisional UV scales; if the actual package differs, the same synchronous part
is prepared again with its real scale **before** clipping. No target fallback
occurred in this run. The fallback is explicitly tested, not assumed equivalent.
Uploads remain cached; current-frame pins follow committed packets. UI still pins
when queued. Only unpinned entries can be evicted after the existing frame fence.

Eight host tests pass with sanitizer fixtures: 600 randomized comparisons against
D334's actual renderer expanded into exact triangles, cull/near-clip/UV seam and
alternate-layout cases, source-buffer overwrite, capacity/rollback, plus existing
package release/VQ/failure/fence checks. A64-triangle strip takes66 vertex records
instead of192 with identical expanded attributes. Actual cache functions test500
warm lookups, committed/UI protection, failed/empty admission and pressure/failure.
Native O1 link passes; five existing missing stubs remain. No recovered source
was edited in this slice, so there is no new PowerPC-path delta.

### Target evidence and negative experiments

Same135-second fixture, assets, emulator/config and capture tools:

| Logged native frame1320 | D334 | D335c |
|---|---:|---:|
| Queued native bytes |65,408|65,376|
| Cumulative emitted triangles |55,087|83,471|
| HUD quads |18|18|
| Cumulative UI missing textures |113|0|
| Cumulative uploads |108|53|
| Current texture VRAM bytes |2,967,552|1,011,712|
| Earlier peak texture VRAM bytes |4,192,256|4,192,256|

The native frame counter is a comparison checkpoint, not proof of equal complete
simulation state; different admission and loading can change scheduling. Source
final frame1351 /115 model presentations versus D3341346 /108 is not an FPS claim.
D335c ends by harness deadline. Final partial queue contains3 headers,2,040 vertices,
1,004 triangles:65,280 vertex bytes instead of96,384 independently emitted bytes
(31,104 fewer,32.27%). This is encoded packet cost, not heap capacity reclaimed.
Current room textures stay at53 total uploads through the final snapshot/log.

D335a (`d335-native-strips`) kept eager texture pins: extra accepted parts consumed
all48 handles and lost the HUD. Rejected. D335b (`d335b-visible-bind`) delayed binding
only until the first visible triangle and pinned only on commit. HUD returned,
but later overflowed parts repeatedly uploaded:272 at final snapshot,319 by run end;
38 model presentations. Rejected. Complete-part admission fixes that churn without
raising any budget. Negative source/executable snapshots and results remain private.

Menu capture is pixel-identical to D334. Inspected final output retains branches
and HUD, with3,673 changed pixels (2,575 in the HUD region). Source frames differ,
and the cap admits a different subset: these are not identical full-scene states.
Most environment and actors remain absent; neither old nor new diagnostic passes
room appearance acceptance. Texture/capacity rejection counters are now separate:
final10,602 unsupported-state,2,264 admission-capacity,0 texture,0 wrap,0 scale
rebuild;15,261 whole-part overflows. Counters are cumulative and include partial
current-frame preparation. Fix the actual cap/material frontier, not water polish.

Existing source profiler values in final RAM refer to the **preceding completed
frame**, whereas packet counters concern current preparation. D334 total519,320us,
D335a569,390us, D335b2,043,089us, D335c571,772us. Accepted geometry differs. These
single wall samples are neither matched distributions nor isolated PVR/GPU time;
D335c is not an established frame-time win over D334. It reduces packet cost and
wasted loading while retaining the native/source ownership contract.

### Memory, residency and remaining work

Native packet64KiB, texture48 handles/4MiB, staging64KiB unchanged. Text increases
1,180 bytes and BSS32; data unchanged. Source arena10,127,872; post-block2,582,048,
post-enemy1,466,528, later41,472 free. Parts276,992/model-info73,504/objects212,704
resident, all owners verified; no new source archive recovery. Smaller actual
VRAM working set does not lower its earlier menu peak or enlarge the source heap.

Enemy body1,105,152 plus warm cache952,768 and metadata2,336 =2,060,256 bytes,
with allocator/alignment included in the previously measured family2,067,616;
net original recovery1,510,176. Cache75 misses/loads,6 hits,0 evictions/failures,
952,768 current/peak/read,22,400 peak pinned,0 current pins,270,936us worst wait.
All145 retained headers and1,904 relocated pointers validate. No new evaluation
between later/final snapshots; D328b remains the separate7500-warm-evaluation and
eviction/reload fixture. Preserve incomplete source prefetch/response/concurrency
audit; do not infer an encounter working set from these static diagnostic frames.

The actual next independent resource failure remains source ARAM compaction of
r100s41/s43/s44: scratch694,560/669,248/309,632 with41,472 free. ARQ currently
acknowledges without copying. Real event backing/swap, completion effects and
audio remain open. Native submission must also preserve late source hold and room
retirement: Render consumes the old OT before primitive reset, then tasks can
retire resources before Render_swap. Opening/finishing TA early or guessing an RTT
framebuffer address does not preserve that contract. Continue the existing frame
owner and native helpers, not a second renderer or prototype gameplay loop.

Simpler water remains authorized as a selectable candidate. D331's64x64 buffer
sizing removes49,152 bytes of excess **requested** capacity, not free bytes from
a previously successful allocation. Native water RTT/material behavior and any
PS2 comparison remain unimplemented/unqualified. Preserve collision/events and
original assets; measure/review the actual effect before selecting a replacement.

### Identity and disposition

Base `c45c0cf433c1b1fe5ae7595b1bccf29b29a0ed96` plus preserved inherited source and
owned native edits. Evidence `C:/Flycast-Evidence/re4-dreamcast/d335c-admission`,
disc `/root/probe/d335c-disc`; untouched D330 mirror/core and D327 fixtures.
ELF SHA256 `d365085a3b6212c612519ae024b01bb790cbd88597422e48e907e4efe2d9d2c8`;
disc SHA256 `8dd805ab29ef8580a2e7cb1d52c6d445064b56f7e5ca2cb0a8015d700012d132`.
Text/data/BSS2,288,552 /75,620 /672,952; KOS804b3195, SH GCC15.2, O1 native game.
Build `CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1`.
Private result/comparison/source/assets/tool identities and evidence hashes retained.
**Keep D335c as a bounded native integration improvement.** D324 remains accepted
integration reference; no complete room/characters, manual combat, audio, FPS or
physical-hardware acceptance. Menu-plus-three-room goal remains active.

## D336: source-controlled serial submission

Date: 2026-09-22. Base D335c (`d09e99508de79f4d2af10777fd2f2351621f9e8e`),
with inherited dirty work preserved. This is an opt-in native integration
experiment. It connects more recovered source draws; it does not complete r100.

### Existing connection and small platform extension

`re4dc_draw_model_part` still supplies source identity, pose, camera, material and
indices to `native_model.cpp`. Existing `clip_projected_triangle`, exact strip
packing, `begin_pvr_packet`, `submit_pvr`, texture Package/storage/identity cache
and `gpu::quiesce` remain the implementation. No prototype update loop or second
renderer is introduced. Complete-part admission and upload checks still happen
before committing a part. The existing64KiB copied-packet buffer is now reused
after each part is synchronously transferred to TA, rather than limiting an
entire source frame to64KiB. The per-part limit remains a demonstrated rejection.

Source Render consumes the previous ordering table, then reuses primitive data
and dispatches tasks before Render_swap makes its hold decision. Deferring raw
source pointers or allowing KOS to auto-flip early would violate that lifetime.
PVR_STREAM=1 therefore uses one existing PVR scene owner plus an optional patch
to pinned KOS804b3195: hold the completed back buffer until explicitly presented
at vblank, or discard without changing the displayed buffer. Normal KOS automatic
presentation stays the default. No extra framebuffer or guessed RTT alias.

`Render_swap -> re4dc_ui_end_frame(present)` executes even on source hold. Late
VI-black discards the already submitted world and presents an empty scene only
when source presentation is permitted. Room retirement during an open scene
invalidates source views immediately but retains native uploads until the main
owner closes/discards/fences; it cannot wait on a TA list owned by the suspended
main task. SQ ownership is acquired only for actual submission/list operations,
not held across task dispatch or I/O. Source CPU archives have no deferred PVR
reader: native commands and texels have already been copied. Static automatic
mode and the original KOS checkout remain usable and unchanged.

KOS references: [scene management](https://kos-docs.dreamcast.wiki/group__pvr__scene__mgmt.html)
and [texture/framebuffer address semantics](https://kos-docs.dreamcast.wiki/group__pvr__txr__mgmt.html).
The implementation authority is the pinned local source, not moving web docs.
Patch, build procedure and KOS notices are in `port/dreamcast/patches/`.

### Checks and emulator result

Eleven focused tests pass. New checks compile the actual patched KOS functions
and actual native lifetime helpers with controlled state: automatic mode,
100 held/discarded/presented cycles, invalid/busy states, resolve timeout/retry,
SQ release between calls, late black, deferred/repeated retirement and fence
failure. Source Render_swap tests verify hold behavior and byte-identical PPC
preprocessing. These fixtures do not establish physical PVR interrupt timing.
The default original-KOS target builds; its library is rejected by the actual
streaming link guard, preventing missing-symbol stubs. The opt-in candidate
rebuild reproduces the captured ELF exactly. Five prior missing stubs remain.

Same135-second menu/New Game fixture and unchanged assets. Source menu is visible;
final source frame1256,31 completed model presentations. Source-controlled Leon,
cabin and trees now appear; the64-handle revision restores the HUD. The initial
48-handle D336 run lost HUD textures (248 misses) and is retained as rejected
evidence. Revised D336b has96 uploads,0 missing,3,112,960 current texture bytes,
4,192,256 earlier peak and1,626,088 logged free VRAM. Source states/capture times
differ from D335c; do not claim pixel or whole-scene equivalence from them.

**Visual rejection remains:** missing ground/other surfaces, exposed incorrect
head/face and incomplete hair. The camera/pose are source-driven, but that alone
does not certify their rendering. Final counters:277 whole-part overflows,
2,833 state rejects (2,801 separate-alpha,32 no-base-image/size; flags overlap),
0 invalid/capacity/texture/wrap/scale rejects. Parts with separate alpha are
explicitly unsupported, not silently flattened. No complete character, correct
lighting/TEV/fog/water, audible output, manual combat or room acceptance.

Maximum model commands in a completed frame1,668,832 bytes; peak individual part
64,480. Cumulative emitted triangles777,739/processed input3,428,167 includes
part of the in-progress frame. These are not per-frame hardware polygon counts.
Last completed PVR presentation interval1,773,284us, registration1,701,748us,
reported render7,501us. Registration includes CPU source work; intervals overlap
and must not be added. Flycast render duration is not stock-console GPU timing.
Different admitted content makes D335c's586,359us interval an invalid speedup
comparison. Full timing distributions, input responsiveness and target acceptance
remain open. One discarded scene and53 black scenes are recorded; the capture
does not identify the exact discard branch. Branch semantics are fixture-tested.

### Actual memory and target limitation

The pinned KOS allocates BOTH vertex banks even in single-bank mode. Raising each
from512KiB to1MiB costs1,048,576 extra VRAM: texture_base2,599,168 ->3,647,744.
This is not a free bank replacement. Flycast reports TA-used/peak=0 despite
visible output, so those counters are invalid. Neither1MiB TA capacity nor OPB
space is qualified on stock hardware. Submitted bytes and internal TA storage
are different; do not assume a fit from this emulator run. Keep opt-in until
budget/visual qualification; no default asset or renderer promotion.

64 vs48 texture handles cost1,216 data bytes; text+2,940 and BSS+64 versus D335c.
Packet scratch64KiB, texture byte budget4MiB, upload staging64KiB. Source arena
10,127,872 remains unchanged; post-block2,582,048 free, post-enemy1,466,528,
later41,472. No new archive/source-heap recovery. Parts276,992/model-info73,504/
objects212,704 retain verified pointers and no allocation failures.

Enemy-family net warm recovery remains1,510,176. Cache952,768 current/peak/read,
22,400 peak pinned,2,336 metadata,75 misses/loads,6 hits,0 evictions/failures,
270,939us worst wait;145 source headers,75 payloads and1,904 key pointers verify.
Later and final counters stay unchanged without additional motion evaluations;
this is not repeated combat working-set qualification. Keep the D328b warm/evict
fixtures and source prefetch/concurrency audit alongside implementation.

Event scratch694,560/669,248/309,632 still fails with41,472 free, and native ARQ
has no real backing. Continue bounded event storage/swap and native full-part/
material/character fixes without suppressing source requirements. Simpler water
is a selectable candidate authorized by the user, with no current PS2 comparison
or implemented substitute. It cannot be credited for memory or FPS today.

### Exact identity and disposition

Evidence `C:/Flycast-Evidence/re4-dreamcast/d336b-source-stream`; negative initial
`d336-source-stream`; discs `/root/probe/d336b-disc` and `/root/probe/d336-disc`.
Unmodified D330 mirror/core and D327 fixtures. SH GCC15.2, native O1, KOS pinned
804b3195ebd1a06a27cc2b3a5eacf7a2429040a3 plus the isolated manual-flip patch.
Text/data/BSS2,291,492 /76,836 /673,016. Build adds PVR_STREAM=1 to the existing
CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776
PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1 options. See evidence manifests
for the exact tool, configuration, fixture, private asset and dirty-source hashes.

ELF SHA256 `ace4aa79b4bd5bec3514e2998841bb844f4d4c0c17b42bbe3e62dd5d9209620b`;
disc SHA256 `5e1fa88f05321aca3e50970b7ab46a550c8aeeb7c4e004734a2e88bdc18e0ce0`;
patched KOS library SHA256 `f5b2f71970dabd1d51199bc77e11102fb63c80765ef7ccac334db9208139b9ca`;
patch SHA256 `c8bd2883f9422e78da250e1b26a5bbc97c3f363cd98a6be242bd9cecf239f4df`.

**Keep the source-controlled submission mechanism as opt-in integration.** Reject
the current image as complete scene/character acceptance. Default bounded path
and accepted references are retained. This is not a frame-time gain, recovered
event/audio subsystem, restored cabin gameplay or hardware pass. The menu and
three-room persistent goal remains active.

## D337: bounded chunks for large source parts

Date2026-09-22, base `b5a4cd03dd116d03d4fd9cddbf1dd98ca231d116` (D336b),
inherited work preserved. Reuses D336's single source-controlled scene owner,
manual flip, texture pins, retirement/fence and default non-streaming path.

The existing `native_model.cpp::Builder` now commits a full scratch chunk and
continues the same source part. A chunk ends its strip; the next starts with
the correct complete triangle, preserving winding, UV/color seams and draw order.
The native owner reuses the same header/texture/scratch, without another lookup,
upload, skinning pass or whole-scene CPU copy. Normal geometry is processed once.
Only the existing exceptional native-UV-size mismatch restarts preparation,
before any chunk is published. Empty/failed first chunks perform no repeated
texture I/O. A geometry failure after earlier chunks sets the existing frame
abort state; later submissions are rejected and Render_swap discards/fences the
whole image, retaining the prior front buffer. It never presents half a model.

Default PVR_STREAM=0 retains whole-part rollback. Both native builds pass and
the captured streaming ELF reproduces byte-identically after switching back.
Eleven focused tests pass: existing600 randomized D334 triangle comparisons,
120 additional streamed comparisons with3-21-vertex boundaries, clipping/seams,
alternate UV dimensions, a1,800-triangle part larger than64KiB, first binding
failure, late nonfinite geometry invalidation, and actual owner discard/fence
behavior. No recovered gameplay source changes in this slice.

Same135s source menu/New Game fixture, assets and emulator. Ends by harness
deadline, with source frame1255/30 model presentations in the final snapshot.
Sampled menu pixels match D336b exactly. Additional trees/scenery appear; cabin,
Leon/handgun and HUD remain visible. Ground remains absent and head/hair remains
unaccepted. Different final source frames1255 vs1256 preclude a full-state image
equivalence claim;88,021 final pixels change. This resolves supported-part
transport capacity, not complete source material/presentation fidelity.

| Measurement | D336b | D337 |
|---|---:|---:|
| Final cumulative whole-part overflows |277|0|
| Maximum submitted model bytes/frame |1,668,832|2,415,040|
| Peak scratch chunk bytes |64,480|65,536|
| Packet scratch allocation |65,536|65,536|
| Current texture VRAM bytes |3,112,960|3,112,960|
| Cumulative uploads / missing textures |96 /0|96 /0|
| Later source heap free |41,472|41,472|

Final D337 cumulative input3,447,460/output1,097,461 triangles,5,378 parts,
2,740 state rejects:2,709 separate-alpha and31 no-base-image plus size. These
include an in-progress frame and are not per-frame geometry. No invalid geometry,
packet capacity, texture, wrap or alternate-scale rejections. One source-controlled
discard and53 black scenes remain. Per-frame source-material rejection is now
the next exact native boundary, not another capacity mechanism. `ModelPart`
alpha flags and `ModelTexInfo` blend flags must not be conflated; use the existing
materialSetup/alphaSetup and native conversion/resource path.

Text+588; data/BSS unchanged. Native texture budget4MiB/64 handles and staging
64KiB unchanged. D336's extra1MiB TA reservation persists; Flycast TA-use/peak=0
remains invalid. Larger command output is not a proved physical TA/OPB fit.
Last completed PVR interval1,823,323us, registration1,770,205us, render7,503us.
Registration includes CPU draw work; overlapping intervals are not additive.
This draws more geometry and is not a frame-time win or stock-hardware budget.

Required block/enemy requests still allocate:2,582,048 and1,466,528 free at the
same checkpoints, later41,472. Source arena10,127,872 unchanged. Work managers
retain valid slots/owners and no failures. No new archive recovery. Warm enemy
net recovery1,510,176; cache952,768 current/peak/read,2,336 metadata,22,400 peak
pinned,75 misses/loads,6 hits,0 evictions/failures,270,938us worst resource wait.
All145 headers,75 payloads and1,904 relocated pointers verify. Later/final cache
counters unchanged with no new motion evaluation: combat response/prefetch and
concurrency coverage remain open. Event scratch694,560/669,248/309,632 fails and
ARQ still lacks actual stored bytes. No audio/manual play/transition acceptance.

Evidence `C:/Flycast-Evidence/re4-dreamcast/d337-chunked-parts`, disc
`/root/probe/d337-disc`; same untouched D330 mirror/core and D327 fixtures.
KOS804b3195 plus unchanged D336 optional patch, SH GCC15.2, native O1.
Text/data/BSS2,292,080 /76,836 /673,016. Same D336b build options. Private
source/tool/asset/config/fixture identities and evidence hashes are preserved.

ELF SHA256 `fe26c605286cf925376dcc1ba250473ab422e669e4dd28d7303337cab0ba21c7`;
disc SHA256 `f023798b1ab3f0bdd5d1912630ab84824303d913ffd27278b0d33c6f2e17da8a`.

**Keep bounded chunk transport in the selectable streaming integration.** No
default promotion, source-heap recovery, complete room, FPS or hardware claim.
Continue exact source materials/head presentation and real event storage. Water
simplification remains a separate selectable candidate with reviewed appearance;
neither PS2 equivalence nor savings have been demonstrated. Goal remains active.

## D338: source cull mapping restores ground and head surfaces

Date2026-09-22; base `1e996dc4b39b8956702e047cd380e4bd758396ec` (D337).
The prior goal turn made source-controlled, bounded submission progress. This
turn resolves the demonstrated missing-ground/backwards-face presentation bug.

### Cause and narrow correction

The adapter supplied source `cModel::CullMode` values to the existing viewer
clipper as if the conventions matched. `commonModelTrans` selects GX_FRONT for
model mode0 and GX_BACK for1. The local source SDK `GXGeometry.c::GXSetCullMode`
swaps these API bits in the hardware field; `GXTransform.c::__GXSetViewport`
sets negative viewport Y scale. Consequently GX_FRONT rejects positive native
screen area and GX_BACK negative area. The shared helper's2/1 values perform
those respective tests; the old adapter passed1/2 and rejected the opposite faces.

Only `model_bridge.cpp`'s mapping changes, via `re4dc_model_cull` in its existing
interface. Debug force-front uses the same corrected conversion; no-cull remains
no-cull. Existing shared clipper/renderer and accepted viewer data are unchanged.
There is no head rotation, pose/animation selection, camera adjustment, geometric
reduction, changed texture or source gameplay edit. The old source test used the
same viewer convention as its oracle and therefore missed this adapter mismatch.

The independent reference is the recovered SDK above and Dolphin's pinned
software clip-space facing test plus hardware cull fields. No third-party code
is incorporated into the product; only the verified behavior guides the mapping.
Pinned [Dolphin Clipper](https://github.com/dolphin-emu/dolphin/blob/233b2dfe6d6427bed6874d641dfab04ccac2974e/Source/Core/VideoBackends/Software/Clipper.cpp), commit233b2dfe6d6427bed6874d641dfab04ccac2974e;
private reference source/hashes are retained with the evidence.

### Verification and visible result

Eleven focused tests pass. The existing actual-renderer fixture adds200 randomized
clip-space winding cases through the real adapter mapping, all source modes and
debug override. Its determinant expectation is independent of viewer enum values.
Prior clipping, UV seams, source-buffer lifetime, bounded chunks and failure/fence
tests remain. Default original-KOS and optional patched-KOS native builds both
pass; restored candidate ELF matches captured bytes. No new unresolved symbols,
recovered source or PowerPC-path changes; five prior missing stubs remain.

Same135s menu/New Game fixture, no assets changed. Corrected final640x480 image
shows textured ground, cabin, trees, the back of Leon's head/body and handgun,
plus HUD. The previous backwards-face appearance is gone in this view. This
does not prove every character component/angle/pose or correct alpha/lighting.
Menu pixels match D337;217,216 final pixels intentionally change.

Both final RAM snapshots are source frame1255. Camera, projection, viewport,
player root matrices,119 parts' world/local matrices and transform fields,
and8 source model/prepared-position arrays compare byte-for-byte. Thus the visual
change comes from rendering rejection, not moving the head, changing animation
or selecting a more favorable camera. This comparison covers those source fields,
not every game state or a matched original-GameCube framebuffer.

Final native frame1256 with30 completed model presentations. Input triangles
3,447,460 /output1,094,912,5,378 parts (cumulative, includes current preparation).
0 invalid geometry,0 overflows/capacity/texture/wrap/scale failures. State rejects
2,740 remain:2,709 separate-alpha and31 no-base-image/size. The missing-ground
and head artifacts are resolved; these material families remain independent.

### Cost, remaining source dependencies and identity

Text/data/BSS unchanged2,292,080 /76,836 /673,016. Native scratch64KiB and existing
texture64 handles/4MiB budget unchanged. Current texture bytes3,244,032 versus
D3373,112,960 (+131,072 newly visible content),97 uploads versus96,0 missing;
earlier peak4,192,256 unchanged. Logged free VRAM1,494,984. Maximum submitted model
commands2,440,448 versus2,415,040. Physical TA/OPB capacity remains unqualified:
Flycast's zero usage is invalid, and internal TA bytes are not command bytes.
Keep D336's single-owner PVR streaming opt-in. Last completed interval1,823,323us,
registration1,794,281us, reported render7,504us; these overlap and do not establish
a hardware budget or real-time playability. No speedup is claimed.

Source arena10,127,872; post-block2,582,048 free, post-enemy1,466,528, later41,472.
Required allocations/manager owners still pass; no new source-heap recovery.
Enemy warm recovery1,510,176; cache952,768 current/peak/read,2,336 metadata,
22,400 peak pinned,75 misses/loads,6 hits,0 evictions/failures,270,938us worst wait.
All145 retained headers and1,904 relocated key pointers verify. No new motion
evaluations between later/final samples: combat hot-set/prefetch/concurrency
qualification remains open. Event scratch694,560/669,248/309,632 still fails and
ARQ has no actual byte backing. Audio/manual encounter/progression stay open.

Next native material connections must preserve `alphaSetup`'s selected alpha
texture, previous-alpha multiplication, model/part alpha threshold and possible
different UV source. `ModelTexInfo` blending is a separate mechanism. Do not
flatten all these into the existing viewer alpha replacement. Reuse compatible
native conversion/upload/ownership paths while tracing actual consumers.

Evidence `C:/Flycast-Evidence/re4-dreamcast/d338-source-cull`, disc
`/root/probe/d338-disc`; unchanged D330 mirror/core/D327 fixtures. Native O1,
SH GCC15.2, pinned KOS804b3195 with unchanged D336 optional patch. Same residency
and PVR_STREAM=1 options as D337; exact executable, private assets, emulator,
config, fixture, capture tools and inherited dirty-source identities retained.

ELF SHA256 `8ed836ffb2c18986979ba2a218515ed6560c54b9cea753a1d22d4521765eaed3`;
disc SHA256 `39d9a9191f0826ebbb5e3bbe2dac8c558b52839c390f0f68acbec51827ec53e8`.

**Keep the source cull correction.** Retain the earlier captures as invalid face-
selection evidence, not a visual reference to reproduce. Full materials/lighting,
event storage/audio, manual three-room play and physical hardware remain open.
Water simplification is still a separate unimplemented candidate, not this fix.
The persistent menu-plus-three-room goal remains active.

## D339: part-local position reuse

Date 2026-09-22; base `ed88d5bd25833f02e6d426b30987df9080a2edc1`. Prior turn
completed/pushed D338; this turn is a fidelity-preserving CPU-work experiment.

D339 keeps a bounded source-position cache in the existing native model adapter.
The same transformed position is reused across corners of one source part; UVs,
normals, winding, material and source pose retain their separate identities.
The 64-entry table lives for one synchronous submission, including packet flushes;
new part/pose/instance/camera submissions start empty. No cross-frame invalidation
scheme, geometry reduction, new renderer or extra resident allocation is added.

Two sequential Flycast runs compare `MODEL_POSITION_CACHE=0` and `=1` (default).
For 12 common observed source-frame tags, median presented interval drops from
1,840.012 to 1,437.144 ms (21.9%); p95 from 1,856.699 to 1,439.648 ms. This is
one emulator run per choice, observational completed-frame sampling, not physical
timing or real-time play. The candidate avoids 8,334,641 of 13,072,693 position
transforms (63.8%). Eleven focused tests pass, including both cache choices,
source winding, clipping, seams, chunk transport and failure ownership.

The candidate adds 2 KiB within the existing calling stack, no extra heap/VRAM
allocation. Compiler-reported submit stack is 2,160 bytes; this is not a whole-
call-chain peak. Text is 2,292,304 (+224 versus D338); data/BSS remain 76,836 /
673,016. Required block/enemy allocation points stay 2,582,048 /1,466,528 free;
later source free remains 41,472. Texture use is 3,244,032, peak 4,192,256, with
97 uploads and zero missing textures. No new source-archive recovery is claimed.

Menu captures match exactly. Reviewed room captures retain ground, Leon's rear
head, cabin and HUD. Final source frames differ, as do camera/pose buffers; the
203,091 changed pixels are not a matched-state visual comparison. Exact packet
comparison is supplied by focused fixtures; complete materials/lighting and
character/encounter acceptance remain open. PVR_STREAM=1 remains opt-in and
physical TA/OPB capacity is still unqualified.

Event storage is still required. This turn verified all four existing r100 EVDs
have complete conversion records, but ARQ still has no byte backing. Source
`MemorySwap` must preserve modified enemy/event bytes; read-only file references
alone cannot replace it. D339's 135-second samples remain in background preloads
and do not log the previously documented whole-event scratch allocation failures.
Do not report those older failures as newly reproduced in this window or claim
the absence proves they are solved. Continue qualified event lifetime/storage,
source materials/lighting and controller-driven progression; keep the existing
motion hot-set/prefetch/concurrency audit open. Simpler water remains a selectable,
unimplemented candidate. The full menu-plus-three-room goal remains active.

### Implementation and measurement limits

Reuses `native_model.cpp::Builder::vertex`, existing source-prepared position
arrays, the existing clipper and bounded packet owner. The only new mechanism is
a direct-mapped 64-entry index/ProjectedVertex table in the existing Builder.
Index collisions recompute; no coordinate welding. Only successful finite
position calculations enter it. UV/normal validation still occurs per corner.
Native assembly confirms cache hits avoid the scalar matrix/projection math;
no new math library, float reassociation or fast-math option was introduced.

The working test compares expanded packets against the existing reference and
runs both cache choices through source culling, clipped/random strips, changing
source arrays/transforms, collisions, UV retries and late failure. A 1,800-triangle
fixture has 5,400 references: cache0 transforms all; cache1 transforms three and
hits 5,397, while emitted vertices and failure semantics remain checked.

Two sequential135s runs use unchanged assets/config/input. Twelve common
observed source-frame tags1251..1262 provide the timing comparison. Candidate
registration median1,398.339ms versus1,811.451; render median7.503ms in both.
These intervals overlap; registration includes CPU preparation, tasks and I/O.
Do not sum them or call registration a pure transfer/GPU measure. A sampler
offset bug initially prevented reference interval rows; corrected supplementary
reads attached to the same still-live process captured12 completed frames.
No process restart, blue-image correction, source state force or framebuffer
change occurred. Both sampler scripts and the limitation are preserved.

Reference final source frame1256; candidate1265. Final output counters are from
different in-progress snapshots and must not be compared as one paired frame.
Maximum complete-frame model commands remain2,440,448 bytes. Zero model invalid,
overflow, texture/wrap/capacity failures in both. The snapshot image comparison
is intentionally not asserted equal: source camera and pose changed between
different simulation frames. Both views were reviewed; no geometry reduction
was made. Full manual/moving-scene acceptance remains outstanding.

Both reference and candidate retain identical manager residency/pointer checks
and native texture cost. Motion cache still retains952,768 bytes,22,400 peak
pinned,2,336 metadata,75 misses/loads,6 hits,0 evictions/failures. All145 source
headers and1,904 relocated key pointers validate; no new animation hot-set
coverage is claimed. Net previously measured warmed enemy-family recovery stays
1,510,176 bytes. No extra source heap was recovered by this rendering change.

**Keep** the bounded cache, with `MODEL_POSITION_CACHE=0` as the reference path.
The default bounded PVR backend and opt-in source streaming selection remain
separate; no PVR capacity or hardware acceptance is inferred.

### Evidence and continuation

Reference: `C:/Flycast-Evidence/re4-dreamcast/d339a-position-reference`.
Candidate: `C:/Flycast-Evidence/re4-dreamcast/d339b-position-cache`.
Private discs `/root/probe/d339a-disc`, `/root/probe/d339b-disc`; unchanged D330
mirror/core and D327 fixtures. KOS804b3195 plus unchanged D336 optional patch,
SH GCC15.2, native O1. Exact toolchain/source/ELF/disc/asset/fixture/capture
identities and reference/candidate build flags are preserved in evidence.

Reference ELF SHA256 `c9945456dc89a2863f34a3ada56c453ca7533277d4a2d29c17ba491117908b03`;
candidate ELF SHA256 `1fedad3816865d66b570658f9d7382fc2148fd964ee88c893a62801c225a9faf`.

Event audit: the four existing EVD conversion trees qualify (90/19/18/10 records,
respectively), but source-backed event bytes and mutable swaps are not integrated.
The full s40 file is2,227,072 bytes, larger than the compact enemy body1,105,152;
future source borrowing requires measured capacity and pointer lifetime handling.
No event storage, cutscene skip/completion or gameplay flag changed this turn.
Earlier D338 wording that scratch failures "still fail" described an unresolved
earlier reproduction, not a fresh logged failure during its135s window. D339's
logs likewise do not reach those failed compaction requests; keep them as an
open dependency, not evidence of newly exercised or fixed consumers.

Continue the existing event/resource and source-material connections toward
manual play. Do not preserve a known missing resource behind successful ARQ
callbacks. Do not add another renderer, repeat inventory/extraction, or substitute
water/mesh simplification for the missing storage and source-system integration.
