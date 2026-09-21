# D297: decoded room mirror and source collision layout

## D299: original model arrays and morph deltas (2026-09-21)

The mirror now converts source ModelData/BIN versions 0x20010801 and 0x20030818:
section offsets, joint centers, compact position/normal arrays, weight palettes,
texture coordinates, part lengths/statistics, motion blend/flip tables and morph
delta lists. Byte joint identities, ordinary weights, RGBA8 colors, signed-byte
normals and GX command streams remain bytes. Original position, normal, UV,
weight, part and primitive identities remain separate. No mesh reduction,
flattening or baked-pose replacement is introduced.

SMD invokes the model converter within each resource's own bounds, including
referenced textures. All nine available SMD regions now report complete for the
known data layouts. Of 422 tagged BIN regions, 421 convert; one legacy core BIN
(`etc/core.das:0#11`, version word 0x2c020202) remains rejected and raw. The two
legacy core SAT errors remain. SMX callback work and other room formats still
block full archive qualification. Model/morph data conversion does not implement
missing animation runtime or native GX draw integration.

Do not bound an attached model's weight joint IDs by its local nParts: these IDs
can address the owning model's rig. Influence counts remain checked. Source
morph lists preserve every vertex index and signed delta; animation curves that
select/blend them are separate FCV/shape-animation coverage work.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d299-model-data` contains
converted room archive identities/copies, conversion report, comparison script
and results. An independent field/byte comparison of all 421 successfully
converted tagged BINs verified 230,385 positions, 218,257 normals and 1,401
material/draw streams against original data. It checks numeric array equality
and unchanged command/material bytes; it is not a rendered-image or skeletal
behavior comparison. Nested SMD models passed bounded conversion but were not
included in that independent tagged-BIN count.

Twelve room-endian, nine mirror and two offline decoder tests pass. This change
is offline tooling only; the most recent game build is D298 and the most recent
Flycast replay is D295. No new frame/input/performance or manual acceptance.

Next: remaining room formats (especially LIT/CAM), source animation/FCV data,
and the native loading boundary. Preserve nested sound reads from the original
DVD container when replacing only its compressed room payload. A `.arc` with
unhandled tags must continue to fail the required-dependency check. Keep the
r120 source-completion skip and full menu/three-room backlog active.

## D298: scene registration metadata (2026-09-21)

The normal mirror now converts SMD headers, placement transforms, source IDs,
flags, group reservation counts and table-relative resource offsets, plus the
referenced TPL palettes through the existing handler. BIN and FCV payloads stay
explicitly incomplete. All nine available SMD regions pass metadata conversion
without handler errors. Do not equate this with a complete renderable model.

A real-data correction matters: r100's grouped SMD has 13 inline placements;
the five group counts reserve 297 additional runtime slots for separately loaded
blocks. They are not 297 extra records in that SMD. cSmd::getWorkNum and
getWorkPtr distinguish these meanings; the converter preserves both.

SMX conversion covers display/light masks, numeric colors, UV scrolling and
source obj02 rotate/swing work. r100/r101 SMX records convert completely for the
current fixture. Two r120 type-zero records carry nonzero callback work with an
unestablished layout; they remain explicit raw coverage debt. No guess or silent
zeroing is used. SMD's low-byte flag union and SMX's packed 0xRRGGBBAA writes are
adapted on native builds so their byte views match the source meanings. PowerPC
preprocessing is unchanged for these new source/header changes. Existing dirty
pointer-range adaptations in scroll.cpp are preserved but not staged here.

Ten room-endian tests and nine mirror tests pass, and the recovered game target
builds. Tests include deferred group counts, preserved raw model payloads,
rotate/swing floats and byte flags, unresolved callback reporting, and compiled
native flag/color views. Private evidence is at
`C:\Flycast-Evidence\re4-dreamcast\d298-scene-metadata` (mirror report,
converted archive identities/copies and build log). No new Flycast replay;
last runtime evidence is D295. Core legacy SAT errors remain unchanged.

Next: source ModelData/BIN conversion including original position/normal,
weight/part and display-list identities, then FCV/remaining room formats and
the native loading boundary. Inspect mixed byte/word unions and GX byte streams
rather than swapping every 32-bit word. Reuse the existing native draw backend.
The unconverted resources still prevent claiming room or gameplay acceptance.

## D297 historical checkpoint

2026-09-21. Asset preparation/build checkpoint; last Flycast replay remains D295.

The existing `le_mirror.py --decode-rooms` now extracts the single type-0 YZ2
payload of each st*/r*.das, uses the D296 source decoder, and converts the decoded
archive through the normal tagged handlers into a sibling `.arc`. It preserves
the original DVD container, including its nested sound blocks. No runtime reader
is redirected yet: these sidecars are incomplete and must not be interpreted as
fully converted game structures. Use the existing `--require` gate on each `.arc`
to expose all remaining formats. The sidecar option decodes each requested room
on every invocation; caching is not needed for the three current fixtures.

CNS conversion follows ConsRoom in src/game/cons.cpp, including the extra bitmap
word when count crosses a 32-bit boundary. SAT/EAT conversion follows cSatFile,
cSatHeader, AtPoly and cSatBlock in include/atari.h and include/at_sub.h. It keeps
coordinates, vector bits, polygon order, attributes, relative block links,
child/leaf layout, duplicate polygon references and resource separation intact.
No new collision tree is introduced. Unsupported/invalid regions roll back raw.

AtPoly uses both numeric attr and named attrHi/attrLo in source collision code.
The native member order now preserves both views on little-endian SH-4; PowerPC
keeps its original layout. Its preprocessed header matches the prior HEAD exactly.
This is not a new full ProDG object-comparison result.

## Evidence and limits

- Recovered game target builds successfully after the header change.
- Seven synthetic room-format tests pass, including hierarchy/attributes,
  duplicate section offsets, invalid-reference rollback, bitmap boundaries,
  sidecar container preservation, incomplete-data rejection and compiled native
  AtPoly layout/half-word semantics.
- Nine pre-existing mirror tests pass. This commit also checkpoints their
  previously dirty bounded conversion/rollback, EFF, roominfo and REL-header
  support; it does not accept the remaining dirty runtime implementations.
- All nine CNS/SAT/EAT regions across decoded r100/r101/r120 convert successfully.
- Full mirror: 780 source files converted, 1281 tagged regions, 403 handled.
  Two core SAT regions (`etc/core.das:0#9` and `#10`) remain raw with explicit
  layout errors. Their 0x10 legacy headers differ from these room structures;
  do not suppress those failures or claim universal SAT support.
- Private artifacts/hashes, mirror report and build log are at
  `C:\Flycast-Evidence\re4-dreamcast\d297-room-endian`.
- No new target run or manual/physical gameplay acceptance is claimed.

Command: `python3 port/dreamcast/tools/le_mirror.py /root/re4data /root/re4data-le --decode-rooms`.
The standalone decoder still requires the pinned external tools documented in D296.

## Next

Continue the native room loader boundary and conversion in consumer order.
CNS is ready; SMD/SMX and their referenced model/texture/motion payloads are next
for gameRoomInit's scene registration. Keep byte views and packed colors distinct
from numeric words (SMX colors and SMD flags have mixed consumers). LIT/CAM and
other required room blocks remain explicit coverage debt. Full .arc dependency
checks must remain failing until these are converted. Preserve sound processing
from the original container when switching only the geometry archive to offline
preparation. Do not run the stub YZ2 decoder on an uncompressed sidecar.

The authorized r120 cinematic completion adaptation remains open alongside these
loader dependencies. The actual first-three-playable-room sequence, visible
menu/native rendering/audio integration, transitions and retry remain unaccepted.
