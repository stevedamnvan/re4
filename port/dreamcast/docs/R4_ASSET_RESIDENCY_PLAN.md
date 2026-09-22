# R4: resource lifetimes and render-asset adaptation for playable RE4

D341 corrects the opening enemy-list conversion in the existing mirror tool.
The old native list interpreted the house entry as room0x001/HP59395 instead of
room0x100/HP1000. All255 original records compare field-for-field after conversion;
target snapshots verify the corrected house entry. Required byte fields, indices,
record count and reserved bytes remain intact. Thirty-four focused tests pass.

This exposes required content previously suppressed by the bad room checks:
the authored crow archive now requests239,904 bytes, and its REL module7 is not
in the image. The first cold boot allocates that body, leaving147,168 free at
that point, but subsequent model-info requests4704 fail with4064 free. Required
block pool/em12 early points remain2,582,048/1,466,528 free. This is **zero new
heap recovery**, not a fit for the corrected encounter. After a guest reboot,
crow retries fail with75,936 free; do not combine those separate boot states.

The longer old-data approach also reaches missing r100s03/r100s20 requests.
Both files now pass the existing EVD converter/certificate producer (156 complete
records), but the corrected-list run stops earlier at crow initialization. Their
target preload/installation is not newly accepted. No event, combat, visual,
performance, audio, manual-play or hardware acceptance is claimed by D341.

Continue with the existing static module generator/registry for em23 (module7)
and the additional source working set. The module failure logs HALT and then
continues/reboots: the PPC invalid-address halt is not a reliable native stop.
Close that failure path before accepting new module consumers. Keep the corrected
list; do not regain the old image by suppressing required crows. EVENT_FILES
activation/mutable snapshots, source lighting/materials and all existing backlogs
remain. Simpler water is selectable and unimplemented; PS2 equivalence is unverified.

See [D341](R4_EVENT_ENEMY_CHECKPOINT.md#d341-opening-enemy-list-and-event-inputs).

### Previous D340 checkpoint

D340 adds selectable `EVENT_FILES=1` backing for qualified immutable EVD
preloads. It reuses `le_mirror` qualification, the native DVD root, existing
64 KiB storage reader, and source `cDataUnit` ownership. Source compaction moves
the file reference without allocating a whole-event scratch buffer. Actual
installation validates each payload chunk into the caller's final allocation;
mutable parking/swaps are explicitly rejected, not silently restored from disc.

A 450-second reference run reproduces the 694,560 /669,248 /309,632-byte
compaction failures with 41,472 bytes free. The kept candidate completes all
three moves without these failures. Four preparations read 372 metadata bytes,
zero EVD payload bytes, with worst observed preparation wait 16,384 us. No event
installation occurs in this run; that transport is host-tested, not yet exercised
by target event activation. The rejected full-preload-read variant took up to
18,228,242 us. These are emulator integration observations, not an FPS benchmark.

Required block/enemy allocation points remain 2,582,048 /1,466,528 free. Later
heap free and largest block both remain 41,472: **zero additional heap recovered**.
The change avoids failed scratch demands rather than freeing previously allocated
storage. No new payload arena or VRAM allocation; ELF text/data/BSS are
2,295,200 /76,836 /673,048 (+2,896 text, +32 BSS versus D339). The 540-byte
compiler-reported transfer stack excludes callees and is not a total stack peak.

Source title/menu and diagnostic room output remain visible. Delivered UP at
retrace 9011 moves Leon from approximately (-99,692,-454,-1,344) to
(-94,864,-123,-3,059); R at 21025 exercises the source aim path. These are
scripted controller observations, not manual encounter acceptance. Source frame
1483 is reached; the capture stops at its 450-second deadline, not a game crash.
Materials/lighting, event activation and mutable snapshots, full audio, inventory,
combat, transitions/retry, performance and hardware acceptance remain open.
Simpler water remains a selectable, unimplemented candidate.
See [D340](R4_EVENT_ENEMY_CHECKPOINT.md#d340-qualified-immutable-event-backing).

D339's part-local position cache and D338's source cull correction remain.
D339's prior matched-frame emulator interval median was 1,437.144 ms; D340
does not supersede that with a controlled performance comparison. Do not repeat
the cache, strip/chunk or cull work, or mistake the unlit diagnostic backend for
the complete accepted cabin presentation.


Updated 2026-09-22; accepted integration reference D324; experiment D340. Historical budgets below
retain their named checkpoints. This supports PLAYABLE_PATH and REALTIME_PATH;
it is not a competing prerequisite roadmap.

### Where the remaining memory can come from

D332 leaves 2,582,048 after the required block and 1,466,528 after the enemy
body: +305,184 at both early points. As objects are constructed, the saving falls
to 137,856 before water and 121,920 at the later snapshot. Full room-model parts
and collision allocations now succeed, leaving 41,472 free. D333 retains this
initialization working set; event/ARAM/audio, moving combat and transition peaks
are not priced as complete. Keep the still-incomplete motion response/concurrency
audit. D333 resolves scheduler ownership and exposes ARAM compaction scratch requests.
These do not justify removing hot motions or lowering object capacity. Largest-block/whole-encounter
peaks and full cache-budget growth remain required after execution advances.

User steering: evaluate simpler native water when worthwhile, alongside exact
right-sizing of the source target. Keep the original selectable, measure real
allocation and rendering costs, preserve collision/events and review appearance.
PS2 water is a comparison candidate, not a verified current implementation.

| Existing measured backing | Bytes | Proposed lever and acceptance limit |
|---|---:|---|
| Source ModInfoMgr backing |134,400 including allocator|D330 preserves460 logical slots;63,968 at prefetch (205 live),68,736 at the later failed-room snapshot (224 live).16-slot pages and stable pointers; unallocated slots are free, not dummy records. |
| Source PartsMgr backing | 618,400 including allocator | D329 preserves1,310 slots but uses176,544 for319 live parts/198 runs at the prefetch frontier:441,856 sustained recovery. Metadata5,376 and per-run overhead/alignment included. D330 later grows to224,448 before failures; no full-encounter peak or FPS acceptance. |
| em12 FCV bank (153 source entries) | 1,823,552 | D325 externalizes145 entries /1,702,176 unique transport bytes, retaining headers/events. Main body drops1,670,272, but provisional hot+reserve costs1,007,936 plus metadata/allocator costs: roughly645,984 net at conservative capacity bound.75-clip profile incomplete; full-bank prefetch costs more than reference. Close source repeated-use/response/concurrency set before promotion; no tiny cache assumption. |
| em12 selected nonpalette/nonmip texture backing | 482,816 | D326 removes these payloads directly, retaining1,184 token bytes and480 index bytes. Combined body request drops481,152; texture-only drops481,120 including extra header growth. Embedded EFM6,144 bytes stay resident.36 native packages total1,869,824 VRAM payload bytes if all resident; no simultaneous-world fit or visual acceptance claimed. This saving is already included above. |
| em12 EST records and sequence alignment | 566,304 original | D328 replaces these with 243,168 resident packed/raw bytes and a 1,984-byte borrowed index: net321,152 actual source-heap recovery. All records remain. New binding/statics cost96 BSS bytes; one300-byte local decode scratch, up to four nested. No effect I/O/cache; in-game effect appearance/lifecycle remains unqualified. This saving is already included above. |
| Remaining r100 base-level source texels | 968,736 | Existing D313 inventory1,830,048 minus D320 removed861,312; not a fresh inventory or all safe-to-remove bytes. Primarily pending mip/palette/unreviewed families. Preserve actual mip/filter/alpha/CPU semantics and native compact VRAM representation; shared cache has finite capacity. |
| pl00/wep02 fixed-reservation slack | 295,648 | Recovered in D327 for this selectable source fixture. Fixed-region pre-transfer guard rejects oversized alternate assets and later parts. Other costumes/weapons are not qualified by this budget. |
| pl00/wep02 source base textures | 247,808 original | D327 externalizes 209,920 + 7,168 texel bytes, retaining identity metadata: net backing reduction 215,552. Weapon mip texels 30,720 remain. Together with fixed slack this yields 511,200 actual heap bytes, already counted above. Native shared-VRAM and visible actor qualification remain required. |

The motion working set is the main architectural lever. Existing zlib pricing
saves437,440 on disc only and key-block dedup is low yield; neither is a runtime
solution. Do not delete unused-in-one-capture clips or replace source animation.
Motion preparation must consume one qualified representation per active clip,
with bounded installation and measured simultaneous pins. General campaign
streaming is unnecessary for proving this encounter's working set.

The Blender candidate selected shared room BIN0..10 because their actual room
archive backing is529,344 bytes (an impossible-delete ceiling). Enemy meshes
are415,040 total; the inspected PS2 top-level set is slightly larger. Neither
can close the gap. Replacing block0 alone also frees no pool because blocks1/2/3
set the1,126,272 maximum. Keep the isolated experiment secondary and selectable;
never count a small repack file or rejected appearance as source-heap recovery.

## Current decision

**Keep source-controlled gameplay and make its resources fit the target.**
Preserve the working lifecycle and asset pipeline. Use GameCube source variants
and compatible PS2 render assets as measured candidate representations, rather
than insisting on the largest GameCube mesh in every context or cutting game
behavior to satisfy a diagnostic scene budget.

The previous rule that the PS2 disc is only an oracle and no PS2 asset may enter
a package is **superseded for private candidate builds**. Extraction, conversion,
and one bounded comparison experiment are authorized. A materially different
presentation is not automatically accepted: retain the GameCube reference,
report visual differences, and obtain explicit review/user acceptance before
making a fidelity tradeoff the default. No copyrighted game assets are committed
or redistributed; work from locally supplied private images.

## Three authorities with distinct roles

| Reference | Role | Boundary |
|---|---|---|
| Matching GameCube decompilation and private source build | Gameplay, scheduling, collision, camera, event/progression and object-state authority; original visual reference. | Do not replace behavior with a viewer approximation or assume another release has identical state/layout. |
| Compatible GameCube variants and PS2 render assets | Candidate meshes, textures, materials/prelit attributes, and evidence of alternate authored representations. | Not a PS2 gameplay-engine switch. Verify compatibility and total target cost per asset; filenames do not prove identity. |
| DCA3 / KallistiOS / community ports | Mechanism-level prior art for offline conversion, native texture handling, bounded working sets and target I/O. | No borrowed world policy, unsupported FPS claim, or code reuse without a license check. |

Use [DCA3_SOURCE_AUDIT.md](DCA3_SOURCE_AUDIT.md) for pinned source leads, not its
historical task ordering. Preserve source room/transition rules; do not invent a
GTA loading radius or assume that GameCube ARAM can map onto AICA sample memory.

## Implemented infrastructure and evidence limits

The bullets below describe `port/dreamcast/room/`, not blanket integration into
`port/dreamcast/game/`. Track three states: implemented in the native scene
runtime; explicitly connected through recovered-game interfaces; validated in
normal gameplay including relevant transitions/retry. Existing readers, texture
and package classes, upload/sharing, transient backing and retirement are reuse
references. Viewer tests do not prove the latter two states.

Current recovered-game ownership is qualified source-layout `.dar` -> source
DVD queue and source heap -> recovered initialization/behavior. D305 consumes
r100 and dispatches its sound blocks; D306 measures the ensuing pool exhaustion.
D307 reclaims a duplicate platform reservation, returning 458,752 bytes without
cutting gameplay pools or render capacity. Collision/event allocations succeed;
D309 qualifies player/weapon data and D311 repairs cloth scratch addressing.
Historically, D312 qualified required EVD files and binds em12, but its 4,006,016-byte body
fails with 409,152 bytes free; the source's 1,126,272-byte block-model pool also
failed then. D320/D324 supersede those memory measurements as above. See
[R4_EVENT_ENEMY_CHECKPOINT.md](R4_EVENT_ENEMY_CHECKPOINT.md). This is a measured
resource blocker, not justification for arbitrary source-pool or content cuts.
Custom `.re4room`/`.re4sat` and native textures serve the scene renderer and are
not interchangeable with the source archive behind `pG->pRoom`. The recovered
target still links GX/audio placeholders; explicit connection and normal
transition/retry validation remain open. Historical budgets below belong to the
named scene builds, not the current recovered-game target.

- Room-owned packages can be read into owned storage, validated, retired and
  reloaded. The fence must protect completed rendering, not merely submitted
  commands; retirement must also honor audio and outstanding transfers.
- Texture payloads are offline-native/twiddled; repeated compatible descriptors
  share allocations within a package. Explicit successful-upload state precedes
  payload release. CPU texels are transient while metadata and GPU ownership
  survive. `a00d967` proved real main-memory recovery only after shrinking the
  reservation, not merely setting a released flag.
- The room format omits duplicate triangle connectivity where strip order and
  winding equivalence are certified (`8a44852`). Some batches still legitimately
  retain two representations; do not call all duplication eliminated.
- Derived accelerators have bounded coverage and correct uncovered paths as the
  intended contract. Boundary fixes and full-width global indices are recorded
  in `70e77e3` / `d14a2c8`. Do not enlarge all whole-room arrays by default.
- `fbd0012` runs Leon in r101 at 640x480 without the cabin enemy. Reported minimum
  free main RAM is 1,757,184 bytes in that diagnostic configuration. This is not
  an inventory of all enemies, events, or a qualified village working set.
- `b7d29e3` corrected exact-tick snapshot selection. The tested fallback/local
  batches match at equivalent states. Older mismatched-tick pixel ratios do not
  establish an outstanding resource/rendering defect.

Retain [R4_5A_ROOM_LIFECYCLE_CHECKPOINT.md](R4_5A_ROOM_LIFECYCLE_CHECKPOINT.md),
[R4_TRANSIENT_TEXTURE_PAYLOAD_CHECKPOINT.md](R4_TRANSIENT_TEXTURE_PAYLOAD_CHECKPOINT.md),
and [R4_ONE_REPRESENTATION_CHECKPOINT.md](R4_ONE_REPRESENTATION_CHECKPOINT.md).
These are historical measured checkpoints with their corrections, not claims
that the same sizes and timing apply to every new configuration.

The earlier D4 r101 estimate missed embedded textures and substantially
underestimated the converted room. Later geometry/source-metadata/player
changes also changed its cost. Do not reuse the 4-6 MB estimate, the 13.79 MB
ceiling, the actor-free village budget, or an older package's counts as the
current complete working set. The inventory checkpoint remains source evidence
with historical assumptions; current generated manifests and simultaneous
allocation measurements decide the budget.

## Resource ownership and transition policy

Keep the source hierarchy of persistent game/stage/room state and an explicit
owner for each CPU package, derived view, GPU allocation, and audio sample.
Name resources through validated source identity such as `(archive, tag,
ordinal)` plus format/content identity as required; filenames are locations.
Cross-platform substitution requires an explicit mapping and version evidence.

For the normal transition path, trace `gameRoomInit()`, `gameRoomMemInit()` and
`ReadAreaData()` alongside the door/fade code. Do not attribute all freeing to
`gameDoordemo()` or assume that all transitions have identical overlap. Preserve
the selected source load-stop behavior. One active room with bounded staging is
the initial implementation; two complete simultaneously resident rooms are not
a blanket requirement.

Track states including unloaded, reading, validated CPU data, uploading,
resident, retiring, and failed. Publish a resource to gameplay only when required
validation/install is complete. Handle short reads, EOF, malformed offsets,
allocation failures, partial uploads and cancellation without leaking or leaving
visible half-loaded state. Arm fault tests after adoption when adoption clears
test state; report reached aborts rather than requests.

Keep persistent player/inventory state across a door; do not call the cabin's
`reset_encounter()` as room progression. Honor source room flags, enemy death and
object state. Invalidate package views, material headers with texture addresses,
lighting/visibility caches, collision/navigation references and pending work at
retirement. Rebuild only what the incoming state requires. Free shared allocations
once, after their last owner and in-flight user has finished.

Source/display activation is not a residency heuristic: offscreen enemies,
collision, scripts or persistent flags may remain required. Conversely, loaded
assets need not all be drawn. Recover the source decisions before choosing
working-set policy.

## Memory accounting and bounded execution

Maintain a single current ledger tied to exact build and package hashes:

| Category | Include |
|---|---|
| Disc/container bytes | Archives and package files; not automatically resident bytes. |
| Persistent CPU resources | Live models, motion, collision, routes, game/state data and retained metadata. |
| Temporary installation | Read/upload buffers, validator scratch, decompression, table construction and audio conversion. |
| Derived state and reservations | Cached lighting, bounds, local mappings, packet buffers, fixed arrays, heap and stack high water. |
| VRAM | Unique compatible payloads, mip/palette needs, framebuffers and parameter/TA resources, largest contiguous free block. |
| AICA | Samples/streams, code and buffers, with playback lifetime accounted for. |
| Reserve | An explicit safety margin for the selected gameplay configuration and future required systems. |

Report simultaneous loading/transition peak and gameplay peak, not only arena
occupancy. Moving bytes out of `.rodata` into a same-size arena is not a saving.
A reservation must actually become reusable/reduced before claiming recovered
main RAM. Moving a runtime table into a resident package saves setup work only
unless redundant storage is also eliminated. Do not enlarge a heap and count
its internal free blocks plus the original outside-heap space twice.

Transient texture loading should read/validate/upload, retain descriptors and
handles, then reclaim backing bytes before the largest persistent allocations
when possible. Measure overlap and alignment/allocator overhead. Releasing CPU
texels must not destroy VRAM ownership or permit an incomplete upload to appear
complete. Compare target image and bindings, not only free-memory counts.

Bound transformation/clipping/packet scratch by processing units. Use 32-bit
global identities where required and validated narrower indices inside bounded
units. Consider offline-native mappings or reusable caches only when their net
resident cost and runtime effect are demonstrated. Do not rebuild all tables
every frame, copy whole geometry into another representation, or silently omit
work when a capacity is exceeded. Verify view/light/room-generation invalidation.

## I/O and streaming are conditional, not ceremonial gates

Use the existing synchronous path behind source transitions first. Required
loading work must complete before exposing the room; intentional pauses must
not accumulate simulation debt or replay queued gameplay controls.

Add bounded asynchronous reads, staging, cancellation and generation checks when
actual I/O/response requirements justify them. A fast read does not hide expensive
validation or main-thread installation; measure each. Retain validation when
optimizing it. Verify the actual deployment medium and KOS path on hardware.

Intra-room residency/streaming is permitted when the corrected working set still
requires it. It is not the same as processing a fully resident scene in bounded
batches. Show the measured deficit or stall before introducing a larger system,
then reuse the existing ownership/reader/upload/retirement code. Use authored
relationships and conservatively derived target policy where source assumptions
do not fit; do not pretend the source supplied a target-specific streaming plan.

## Bounded GameCube/PS2 render-asset experiment

Run this as a secondary, isolated task. It must not block the main boot-forward
integration path or expand into a campaign-wide extraction database.

The immediate assigned experiment is one equivalent static environment object
or small group: geometry, UVs, textures, authored vertex colors or normals,
materials and original instance transforms/identities. Characters, full-room
substitution and movie mapping remain later or separately assigned work. The
Astra light helper uses `/root/work/re4-ps2-experiment` and private extraction,
build/evidence paths; it does not edit the primary checkout/shared assets.

Completed isolated diagnostic (2026-09-21): branch `experiment/ps2-asset`,
commit `14dd633`, report `port/dreamcast/docs/PS2_COMPLETE_ASSET_EXPERIMENT.md`
on that branch. GC SMD054/BIN049 stove versus PS2 SMD072/BIN165: 41 fewer
triangles / 25 fewer vertices and 1,056 fewer used arena bytes, but unchanged
reserved arena/VRAM, 2,648 extra code/rodata bytes and 2,432 less heap headroom.
Matched tick-40 single-pair medians were 78.900 vs 79.410 ms; no speedup shown.
Six matched 640x480 views and one retire/reload per arm were recorded. Geometry
removes detail (reverse surface distance up to 19.8 cm), authored color
factorization adds explicit quantization, and PS2 activation compatibility is
not qualified. Decision: **not worthwhile for this asset/support path; keep GC**.
No candidate code is merged/promoted. Private evidence is
`C:\Flycast-Evidence\re4-dreamcast\ps2-asset-complete`; no character, full-room
or route-level performance claim follows. Do not repeat this rejected experiment
without a changed cost hypothesis.

Two acceptance levels apply:

- Early diagnostics use the existing native runtime with precisely matched
  object, camera, lighting, render state and resolution. They may establish
  compatibility and preliminary asset-specific savings before full source
  fixtures work. Preserve failed comparisons and limitations.
- Gameplay qualification uses the recovered game's representative source state,
  normal ownership and activation rules. Required for route-level benefit claims
  or promotion to accepted asset selection. A viewer comparison is not village FPS.

Preserve exporter companion metadata, source identities and instance status.
Verify coordinate transforms, color range/channel/alpha meaning, materials,
filter/wrap/depth/cull behavior and any quantization. Avoid applying dynamic
lighting twice to prelit geometry. Retain selectable GC assets; measure total
memory/rendering cost and appearance differences, not polygon count alone.
Do not overlap timed runs; coordinate the single host capture window.

Broader backlog categories (not the current assignment): room/environment meshes, character/enemy model variants,
texture resolutions/formats, vertex/prelit colour, materials/pass reductions,
collision representation (for comparison only), effect simplifications, UI
representations, audio encodings and prerecorded cinematics. Preserve original
assets alongside every alternative so the comparison is reversible; select per
validated resource, and do not match assets by filename alone.

1. **Pick equivalent content.** Start with one corresponding static environment
   object or small group. Inspect available GameCube gameplay/LOD
   variants and their selectors first or alongside PS2. Do not assume the current
   converted mesh is the required quality tier in every source situation.
2. **Extract from supplied private images.** Preserve manifests, source build,
   archive/chunk/model/material identities and converter/tool revisions. Reuse
   established tooling where compatible; verify supported format/version and
   license before relying on it. Keep extracts and derived assets private.
3. **Retain semantics during conversion.** Preserve positions/transforms, source
   group/material binding, UVs, alpha/depth/culling, normals or authored vertex
   color, and the distinction between a model and its instances. For characters,
   verify skeleton, bind pose, weights, attachments, motion compatibility, event
   markers and alignment with source hit volumes. A matching name is not enough.
4. **Keep gameplay authoritative.** Retain source collision, interaction points,
   door/ladder anchors, navigation and event/activation logic unless a separate
   source correction is demonstrated. Reject an attractive mesh that creates
   invisible walls or misaligned hits. Do not import PS2 progression or difficulty
   as an accidental side effect of changing a rendering asset.
5. **Convert and run one real candidate.** Feed the alternative through the
   existing Dreamcast package/renderer path with a selectable manifest and the
   GameCube reference retained. No direct PS2 display-list execution or new
   renderer. Evaluate baked/prelit attributes without double-applying lighting.
6. **Measure the full trade.** Compare target-converted vertices, triangles,
   strip/batch/material/pass counts, skinning and lighting cost, CPU/VRAM/AICA
   residency, loading peak, and frame-time distributions from matching gameplay
   cameras. Compare silhouettes, faces, alpha edges, nearby architecture and
   animation in motion. Smaller disc files or source polygon counts alone are
   not proof of a faster native port.

### The PS2 adaptation toolchain, by asset category

Candidate tooling to verify and pin for the actual PS2 image (exact tool,
version and format compatibility are checked before any output is relied on):

| category | tools | Dreamcast use |
|---|---|---|
| Archive / container extraction | [JADERLINK_DATUDAS_TOOL](https://github.com/JADERLINK/JADERLINK_DATUDAS_TOOL); AFS extraction/parsing for `BIO4DAT.AFS`, `BIO4MOV.AFS`, `BIO4MOV2.AFS` | private inventory of the PS2 content with archive/chunk identities |
| Environment / scenario geometry | [RE4-PS2-SCENARIO-SMD-TOOL](https://github.com/JADERLINK/RE4-PS2-SCENARIO-SMD-TOOL) | candidate room meshes, instance placement, prelit/vertex colour |
| Character / object models | [RE4-PS2-BIN-TOOL](https://github.com/JADERLINK/RE4-PS2-BIN-TOOL) | candidate enemy/object variants (rig-validated) |
| Textures | [RE4-PS2-TPL-TOOL](https://github.com/JADERLINK/RE4-PS2-TPL-TOOL) | authored lower-resolution/format candidates |
| Collision | [RE4-SAT-EAT-TOOL](https://github.com/JADERLINK/RE4-SAT-EAT-TOOL) | comparison of the PS2 SAT/EAT against the authoritative GameCube collision (never a replacement) |
| Text / UI data | [RE4-MDT-TOOL](https://github.com/JADERLINK/RE4-MDT-TOOL), FNT/UI inspectors where applicable | UI representation reference |
| Audio | [vgmstream](https://github.com/vgmstream/vgmstream) | inspection/conversion of the PS2 audio encodings as candidates for the AICA |
| Prerecorded movies | SofdecVideoTools, SFDExtractor, other validated SFD demux/extraction utilities | inventory and manifest of the PS2 cinematics (below) |

The list is not exhaustive. If the PS2 content exposes another established
RE4-specific tool that materially accelerates the current slice, evaluate it
rather than rebuilding a parser; but "find every PS2 tool" is not a project of
its own. These are investigation entry points, not evidence that extraction,
rig matching or savings have already succeeded in this checkout; AFS/archive
access and model/material mapping may require additional verified adapters.

### Compare authored platform strategies, not file sizes

When a GameCube scene or asset is costly, record what Capcom changed for PS2
in the equivalent content: geometry complexity, model LOD, texture dimensions
and count, material/pass count, prelit/vertex-colour usage, effect count and
type, enemy representation, animation representation, realtime versus
prerecorded presentation. The objective is not "make Dreamcast look like PS2"
but to use the evidence of Capcom's constrained-platform adaptation to identify
cheaper authored representations that preserve RE4's intended experience. Where
a cheaper GameCube LOD already exists and is compatible, prefer the simpler
same-version integration unless the PS2 alternative shows a measured advantage.

### Prerecorded PS2 movies and realtime-to-prerendered substitutions

Later/separately assigned work: audit `BIO4MOV.AFS` and `BIO4MOV2.AFS`, inventory their SFD
contents privately and build a manifest mapping

```text
PS2 movie <-> corresponding GameCube event/cutscene <-> duration <-> frame rate
<-> dimensions <-> audio <-> gameplay state before/after <-> whether the
GameCube performs it in realtime
```

Capcom's PS2 version may already give an authored answer for the sequences they
considered acceptable to prerender on a more constrained target; the manifest
identifies the Dreamcast candidates. A prerecorded substitution is appropriate
only when the PS2 version demonstrably uses one for the equivalent sequence,
branching/input/QTE/state semantics remain correct, the transition into and out
of playback matches source state, storage and streaming cost is acceptable, and
the resulting presentation passes review. Never replace every realtime
GameCube cutscene with PS2 video by default. The PS2 SFD is an authored
source/reference, not necessarily the Dreamcast runtime format: evaluate an
offline Dreamcast movie pipeline with bounded buffers and target-appropriate
audio/video representation. The GameCube Sofdec implementation (`sofdec.cpp`,
`mwPly*`) is source evidence for semantics and timing; its ARAM assumptions are
not copied onto the Dreamcast.

### Bounded scope and the shape of a result

The current task is bounded to that one static environment comparison. Report
exact correspondence, interpretation/compatibility checks, selectable build
identity, paired costs, appearance differences, keep/reject recommendation and
limits. Later character and cinematic studies need separate assignment; the
tool inventory above does not authorize them automatically. Do not build a
campaign-wide database or another renderer to answer this question.

Allow a hybrid result: suitable GameCube variants, retained high-detail player
assets, selected PS2 environment/enemy representations, and native Dreamcast
textures. Select per validated resource, not by blanket platform preference.
PS2-derived geometry is a potential fidelity trade, not a pure lossless
optimization. Report exact benefits and visual costs; stop a nonpaying candidate.
Explicit review/user acceptance is required before promoting material visual
changes. Do not further reduce texture resolution merely because an old plan
assumed it was the only available lever.

## Texture formats and sharing

Use target-native payloads with explicit dimensions, encoding, aligned sizes,
mips/palette/codebook metadata and compatible sampler/material state. Reuse
mature encoders where appropriate. VQ is a candidate, not a free/lossless default;
review its moving image, alpha and close-detail behavior. HUD and faces need
separate judgment. Preserve a suitable uncompressed reference/fallback.

Within-package sharing is implemented in the native scene runtime. Cross-package sharing requires
validated content identity and descriptor compatibility, lifetime references and
collision checks. Ninety-three distinct payload hashes in an earlier build do
not prove that another room shares nothing. Different actor ids also do not
prove all their assets are unique.

Authored enemy-list rows are not simultaneous live actors. Trace source
activation, variants and waves, then budget shared immutable resources and
per-instance pose/AI/state separately. The old roughly 1.5 MB enemy estimate is
not a measured complete village budget and must not be promoted as one.

## Completion and evidence

R4 succeeds by enabling the next playable sequence under PLAYABLE_PATH, not by
completing every possible texture, streaming or allocator feature. Deliver
reviewable code, lifecycle/failure evidence, current memory peaks and a runnable
integration result. Keep storage/hardware, visual fidelity and gameplay status
separate. Do not claim local asset availability or physical testing without
checking it in the actual execution environment.

The previous PS2-oracle-only policy, D4 estimates, R4 deliverable ordering and
historical measurement ledger remain accessible in the
[pre-amendment R4 plan](https://github.com/stevedamnvan/re4/blob/b7d29e3fe9ba58b807ef2146776b09caf1acbaea/port/dreamcast/docs/R4_ASSET_RESIDENCY_PLAN.md).
Separate checkpoint evidence and source-audit documents are unchanged. Their
obsolete restrictions are not a reason to stop boot-forward integration or this
bounded private asset experiment.
