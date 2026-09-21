# R4: resource lifetimes and render-asset adaptation for playable RE4

Updated 2026-09-21; reconciled against `b7d29e3`.
This policy supports the authoritative [PLAYABLE_PATH.md](PLAYABLE_PATH.md).
R4 is not an independent prerequisite project that must be perfected before
boot-forward game integration can start. [REALTIME_PATH.md](REALTIME_PATH.md)
defines measurement and fidelity/performance qualification.

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

Room/jump fixtures are the standard controlled context for testing alternate
GameCube/PS2 representations and room-resource behaviour: the same authored
stage, room and `roominfo.dat` jump point entered through the normal room
change, the same player/camera state and the same scenario state for every
candidate (see the fixture track in [PLAYABLE_PATH.md](PLAYABLE_PATH.md)).
Memory, loading peak, batch counts, frame times and appearance are compared
there, not from free-camera screenshots or unrelated positions.

1. **Pick equivalent content.** Start with corresponding village environment
   geometry and one representative enemy. Inspect available GameCube gameplay/LOD
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

Candidate tooling to verify and pin for the actual PS2 image:

- [JADERLINK_DATUDAS_TOOL](https://github.com/JADERLINK/JADERLINK_DATUDAS_TOOL)
- [RE4-PS2-SCENARIO-SMD-TOOL](https://github.com/JADERLINK/RE4-PS2-SCENARIO-SMD-TOOL)
- [RE4-PS2-BIN-TOOL](https://github.com/JADERLINK/RE4-PS2-BIN-TOOL)
- [RE4-PS2-TPL-TOOL](https://github.com/JADERLINK/RE4-PS2-TPL-TOOL)

These are investigation entry points, not evidence that extraction, rig matching,
or savings have already succeeded in this checkout. AFS/archive access and
model/material mapping may require additional verified adapters.

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

Within-package sharing is already implemented. Cross-package sharing requires
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
