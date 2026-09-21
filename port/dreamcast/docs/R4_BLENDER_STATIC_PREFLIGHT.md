# D323 isolated Blender static-asset experiment

**Decision: not worthwhile; reject both geometry reductions.** No package, emulator
run, merge, push or default switch. Main source-resource lifetime work takes priority.
This supersedes the initial converter-blocked preflight in commit f68ea09.
Isolated branch `experiment/r100-environment-blender`, base b1cda581c96ce4f44d86e43e3c9153e10bc47172.

## Actual allocation and bounded return

The residency audit selected common r100.arc entry 5 / SMD BIN 0..10, by measured
backing rather than editing convenience. Total encoded geometry is 529,344 bytes,
12,336 positions / 23,127 nondegenerate triangles / 11 parts. Each has one joint,
no weights or morph table, motion 255 and source ID 254 in the audited common
placements. Their shared owner is the room archive; repeated DAT instances do not
multiply this saving. The 1,126,272-byte block pool is unaffected (its maximum
active set is blocks 1/2/3). Source collision, navigation, events and transforms
were never changed.

529,344 bytes is a deletion ceiling, not attainable saving. Hypothetical 50%
encoded reduction would be 264,672 bytes. Neither could resolve D322's 3,095,232-byte
or D324's subsequently reported 2,621,536-byte enemy-allocation shortfall.
Character mesh total 415,040 bytes is smaller and has additional motion contracts;
mesh work does not compress FCV/SEQ.

| Measured private encoding | Bytes | Meaning |
|---|---:|---|
| Six numerically qualified source BINs (0,1,4,6,7,9) | 308,480 | Subset after roundtrip testing |
| Same six, unmodified Blender numerical roundtrip | 291,840 | 16,640-byte encoding-only difference; no target acceptance |
| Protected 80% candidate | 289,504 | Only 2,336 additional geometry bytes; rejected |
| Protected 60% candidate | 289,504 | Same constraint-limited result; rejected |

## Narrow converter correction and qualified interchange

Pinned release JADERLINK GC/WII BIN Tool 1.0.4 was inspected against upstream source
commit `638e9d5f63fb8322cfab0d48f4ffbb23f6e7bb68`. Its OBJ repack passes literal
`false` to `RepackOBJ` for colors despite `UseVertexColor:True`. The asset-free
patch changes that argument to `idxbin.UseVertexColor`. PowerShell's installed
Roslyn compiled the source locally; no SDK installation or binary patching was
needed. Original source/license notices remain intact in the private clone. MIT
license and one-line patch are retained under `tools/patches/jaderlink-bin-1.0.4`.

A strict bridge proves all referenced corners, including degenerate records, use
constant zero RGBA across this exact set, emits that constant on OBJ vertices,
and restores source flags/nTex after validating the repacked stream and material
headers. Uniform color has an unambiguous mapping even if topology changes. The
bridge rejects other flags, color patterns, multiple material parts, weights and
morphs. It checks active sampler IDs against the original texture count before
retaining nTex; it does not invent a count or alter pointers. Original companion
idxggbin, idxmaterial and MTL are authoritative. Blender material-name collisions
were removed by clearing the private session's unused material datablocks.

All 11 pass corrected tool-only numerical gates: exact oriented position/UV
triangle multisets, referenced colors, material headers and source flags/nTex.
The OBJ exporter normalizes original integer normals; repacking normalizes again
and quantizes to S8 range 127. Tool-only maximum angular difference is 0.355207
degrees. No referenced source normal has zero length.

Blender's unmodified roundtrip passes BIN0/1/4/6/7/9 with <=1 integer-component
error and <=0.5 degree angular error (worst 0.465046 degrees). This is a bounded
numerical candidate, **not exact normal arrays or visual equivalence**. BIN2/3/5/8/10
remain original: Blender introduces zero/changed normals or exceeds the bound;
BIN8 reaches approximately 75.71 degrees. The threshold was not relaxed. The
checker reuses `convert_character.triangulate`, rejects ambiguous duplicate triangle
identities, and independently checks actual BIN corner streams.

## Reduction results and rejection

Both candidates protect boundary/UV seam/material/sharp-edge vertices and edges,
plus bounds extrema. Sharp edges use a 30-degree criterion. Targets 80% and 60%
are requests, not claimed achieved ratios. Saved pristine references precede every
destructive modifier operation. Empty reducible groups explicitly skip reduction.

BIN0/1/7 have no eligible interior under those protections and retain their geometry.
BIN4/6/9 retain all protected edges/vertices but remove only 58/70/50 triangles.
Across the six files, 13,684 triangles become 13,506. Sampled bidirectional distance
(vertices and triangle centroids in both directions) is respectively 101.22,
66.38 and 85.16 mm. These fail the declared conservative 10 mm / lean 20 mm limits.
They are sampled distances, not a continuous Hausdorff bound. OBJ unit=100 source
millimetres was checked against source fixed-point positions and exporter scaling.
The 2,336-byte marginal geometry gain does not justify those deviations. No rejected
mesh was inserted into the actual room archive; archive alignment, staging, retained
native identities, free heap, VRAM or CPU improvements therefore remain unmeasured.

No visual approval is claimed: textures were not loaded for this geometry preflight,
no Blender render was made, review camera collections remain empty, and the recovered
game's source hold prevents complete world-visible acceptance. No target measurement
window was requested for rejected content. Processing paused during the parent's
D324 capture and resumed after the explicit window release.

## Reproduction and exact private artifacts

Private Windows root:
`C:/Game Dev/Emulators/re4_helpers/experiments/r100-environment-d323`

- `source-candidate-manifest.json`: all source hashes, exact archive/tag/BIN identities,
  source placements/material cost audit, bounded gates, candidate hashes/bytes and decisions.
- `set-source`: copies verified byte-identical to private original BINs 0..10.
- `set-tool`: corrected tool-only exchange/repack; `set-tool-gate.json` initial numerical report.
- `set-blender-qualified/{0000,0001,0004,0006,0007,0009}`: final clean-name unmodified
  roundtrips and `.blend` references; final comparison results are in the manifest.
- `candidates/<BIN>/reference-locked.blend` and `selectable-candidates.blend`:
  REFERENCE_LOCKED, CANDIDATE_CONSERVATIVE, CANDIDATE_LEAN, REVIEW_CAMERAS collections.
- `candidates/<BIN>/<CANDIDATE_*>`: OBJ, authoritative metadata and corrected BIN.
- `candidates/geometry-report.json`: protected-boundary and sampled distance results.
- `tools/bin-source`, `tools/bin-color-fix.dll`: pinned source clone and private patched build.
- `blender-api.json` and Blender logs: version/offline/API evidence; initial failed
  intermediates remain private as diagnostics, not selectable accepted packages.

Linux audit: `/root/probe/r100-environment-d323/audit/FINDINGS.md` and `inventory.json`.
Main checkout, shared originals, mirrors, sound, externalized texels and fixtures
were untouched. No proprietary data or derived models/textures/captures are tracked.

The tracked scripts are bounded reproducible components:

1. Apply `tools/patches/jaderlink-bin-1.0.4/use-colors.patch` to the pinned private clone.
   Build it with the adjacent `build-private.ps1`; no upstream source is vendored.
2. Export private BIN copies with the pinned tool. Run `static_bin_exchange_gate.py
   prepare SOURCE.BIN OUTPUT.obj`, corrected tool repack, then `finalize` and `compare`.
3. Run `blender_static_roundtrip.py -- INPUT.obj PRIVATE_OUTPUT_DIRECTORY` using Blender
   `--background --factory-startup --offline-mode --disable-autoexec --python SCRIPT`.
   Preserve original metadata companions, repeat prepare/repack/finalize/compare.
4. After the six gates pass, run `blender_static_candidates.py -- PRIVATE_ROOT` with
   the same Blender flags. It consumes the documented set-tool layout. Repeat the
   same guarded repack per candidate; these particular candidates must remain rejected.
5. Run `static_bin_manifest.py PRIVATE_ROOT ORIGINAL_BIN_DIRECTORY AUDIT_INVENTORY.json`.
   The generated manifest checks original copy identity and all six roundtrip gates.

Blender was 5.2.0 LTS build fbe6228777e7; a private BLENDER_USER_RESOURCES directory,
`bpy.app.online_access == False` assertion and disabling all add-ons keep the workflow
local. No MCP was installed or used. The user-provided community thread describes
headless bpy but is not verified provenance for an OpenAI release demo:
https://community.openai.com/t/how-does-gpt-6-actually-generate-3d-models-in-release-demo-via-codex-local-blender-or-mcps-apis/1395391
Upstream converter: https://github.com/JADERLINK/RE4-GCWII-BIN-TOOL