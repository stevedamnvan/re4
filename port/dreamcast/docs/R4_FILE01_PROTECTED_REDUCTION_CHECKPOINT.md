# D366 FILE_01 protected reduction: rejected, paused

2026-09-23. User requested pause and commit. No candidate promotion or merge.
Base: e02e264e7ff9ed4d1f2839ac924e4fdf020ec9ad. Branch:
`experiment/r100-file01-v4-reduction`; worktree `/root/work/re4-file01-v4-reduction`.
Primary runtime and its inherited source overlay were not edited by this experiment.

## Purpose and result

FILE_01 is the explicit cost target under the existing four-owner/AoS20 architecture.
Its accepted native package is 1,000,874 bytes. The modeled complete-encounter
shortfall remains 746,816 bytes before adapter/staging costs; the 900 KB–1 MB
gross reduction/headroom objective is unchanged. These are not live allocations
from a cutover executable. No source backing or heap was reclaimed here.

This bounded custom-DC trial used Blender's existing Decimate modifier, retaining
source object/material groups, protected openings/edges/UV and normal seams, and
source-alpha batches. It fed the existing convert_room_obj.py -> D353 lighting
bake -> AoS20 pipeline. No new room converter, renderer, texture path or owner.

| FILE_01 arm | Triangles | AoS20 bytes | Delta vs accepted package |
|---|---:|---:|---:|
| Accepted D364 input | 24,983 | 1,000,874 | 0 |
| Unmodified exchange control | 24,983 | 998,346 | -2,528 |
| Protected conservative (40% requested) | 24,785 | 1,000,390 | -484 |
| Protected lean (15% requested) | 24,739 | 999,146 | -1,728 |

The lean candidate is **800 bytes larger than its exchange control**. It removed
only 244 triangles. The converter's resulting strip/triangle backing differs,
so polygon reduction is not a reliable encoded-byte saving. This result does
not warrant target timing or visual promotion. Do not repeat this protected
decimation recipe as the way to close the remaining deficit. It does not prove
that reviewed retopology, different material/alpha choices or qualified PS2
substitution cannot work.

## Qualification and limits

Blender 5.2.0 LTS, build fbe6228777e7, ran in a separate factory/offline CLI
session with add-ons disabled. No Blender MCP tools were exposed; no MCP edits
are claimed. Existing Blender/user state and preferences were not changed.

There are 50 source objects and 105 pre-partition source batches. Normal
roundtrip failed the 0.1-degree bound for 19 batches (11,736 triangles); those
batches were retained from original source inputs, not accepted with relaxed
tolerance. Both flat/smooth importer setup attempts retained the same worst
normal mismatch (81.8266 degrees); the precise cause is unresolved. The full
Blender roundtrip is therefore **not** qualified. 8,536 triangles were both
opaque and normal-qualified before additional boundary constraints.

The source-control path retained original triangle inputs. Decimal OBJ output
and altered topology IDs are not byte-identical source encoding. No unmodified
target visual equivalence is claimed. Geometry-error checks sampled vertices
and triangle centers in both directions (not a rigorous whole-surface bound).
Candidate limits were 0.10 m / 0.25 m, with protected vertices/edges retained;
failed batches reverted to original source inputs. No gameplay/collision or
source material identity was intentionally changed.

No PS2 substitution was generated in D366. The prior D353 correspondence data
remain leads, not qualified runtime input. No textures were resized, recompressed
or uploaded. No recovered-game activation, memory recovery, moving visual review,
target CPU/PVR/FPS run or physical-hardware test occurred. Blender did not render
an image. Existing private captures and executable baselines are unchanged.

## Reproduction and private artifacts

- Private input/output: `C:/Game Dev/Emulators/re4_helpers/experiments/r100-file01-d366`.
- Final Blender run: `candidates-v4/report.json`, `reference-locked.blend`,
  `selectable-candidates.blend`, and the three OBJ inputs. Prior `candidates-v1`
  through `v3` retain failed import/gate evidence; do not treat them as accepted.
- Re-encoded packages/logged exact commands: `/root/probe/d366-native-cutover/file01-protected-v1`.
  `result.json` gives hashes and section bytes for all three arms.
- Local recipe and encoding driver: `C:/Game Dev/Emulators/re4-session-scripts/`
  `reduce_file01_blender.py` and `d366_encode_candidates.py`. The committed helper
  has comment corrections only relative to the executed copy; hash both if used.
- Blender command: `blender --background --factory-startup --offline-mode
  --disable-autoexec --python-exit-code 1 --python <reduce_file01_blender.py>
  -- --repo <converter-root> --private <private-input-root> --output <new-folder>`.
  Use a private BLENDER_USER_RESOURCES and do not overwrite an evidence folder.
- Exact v3 source-aware arguments derive from the FILE_01 command in
  `/root/probe/d364-native-r100/source-block-trace/slices-v1/reproduction.json`.
- Bake: `/root/work/re4-r100-prelit-d353/port/dreamcast/tools/bake_room_prelit.py`
  with source `/root/work/re4-r100-reference-5f42caa`. Compact with the existing
  `convert_room_obj.py --compact-prelit --layout aos20` and both manifests.

The optional parse_obj(retain_source_indices=True) retains the original OBJ
position/UV/normal index tuple for editor topology. It is offline-only; the
default parser/package path is unchanged. A focused synthetic test checks seam
identity, negative OBJ indices and identical default package bytes.

## Resume boundary

User paused the primary goal. This rejected experiment stays isolated and does
not change the production roadmap. Read the primary CLAUDE.md and its D366
handoff before any implementation. No shared AoS20 strip-submission function or
recovered-game v4 hooks were implemented during this turn. Do not infer success
from the native package reader or the negative Blender result.
