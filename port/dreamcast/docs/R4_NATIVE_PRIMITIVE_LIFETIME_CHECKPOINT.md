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
