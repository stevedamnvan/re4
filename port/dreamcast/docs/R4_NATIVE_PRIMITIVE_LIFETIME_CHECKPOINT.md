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
