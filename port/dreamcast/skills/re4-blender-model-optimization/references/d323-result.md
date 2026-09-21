# D323: useful pipeline, rejected optimization

Historical checkpoint, 2026-09-21; verify current plans before reuse. The experiment
is preserved at `/root/work/re4-environment-blender`, branch
`experiment/r100-environment-blender`, asset-free commit
`a4bfda0d996518ea7866890c55beb6b69d923ca1`. Its detailed report is
`port/dreamcast/docs/R4_BLENDER_STATIC_PREFLIGHT.md`; scripts are under
`port/dreamcast/tools/` (`blender_static_candidates.py`, `static_bin_exchange_gate.py`,
`static_bin_manifest.py`). They deliberately encode the audited pilot and depend
on repository converters. Do not run them as universal asset tools.

Private evidence was stored at
`C:/Game Dev/Emulators/re4_helpers/experiments/r100-environment-d323`, including
`source-candidate-manifest.json`, and `/root/probe/r100-environment-d323/audit`.
Do not overwrite, upload or commit those models, metadata, `.blend` files or captures.

Actual owner: common r100.arc entry 5 / SMD BIN0..10, shared room-archive backing,
529,344 encoded bytes. That is a deletion ceiling, not feasible saving. DAT instances
do not multiply it; the source block-pool reservation is unaffected. Mesh reduction
was secondary to larger resource-lifetime work and never solved the residency gap.

All 11 passed corrected tool-only numerical roundtrip gates. Blender qualified
BIN0/1/4/6/7/9 (308,480 original bytes). The five others remained original because
normal conversion exceeded the declared bound or introduced zero/changed normals.
The six unmodified roundtrips used 291,840 bytes: 16,640 encoding-only difference.
Both protected 80%/60% targets stalled at 289,504 bytes, only 2,336 additional geometry
bytes saved. Three meshes had no removable interior under the constraints. The three
with reduction removed 58/70/50 triangles but produced 66–101 mm sampled deviations,
failing 10/20 mm limits. Both candidates were rejected. No runtime package, measured
heap/FPS saving, target visual equivalence or physical-hardware acceptance followed.

## Exact upstream color correction

Upstream: https://github.com/JADERLINK/RE4-GCWII-BIN-TOOL
Pinned source: `638e9d5f63fb8322cfab0d48f4ffbb23f6e7bb68`, version 1.0.4.
The OBJ repack call in `SHARED_GCWII_BIN/MainAction.cs` passes literal `false` for
colors even when `UseVertexColor:True` is selected. Bundled
[use-colors.patch](use-colors.patch) changes only that argument to
`idxbin.UseVertexColor`; [upstream-license.txt](upstream-license.txt) preserves MIT notices.
Apply it only to the exact pinned private clone. `scripts/build_bin_tool.ps1`
checks the revision and correction, refuses to overwrite the output DLL, and compiles
using installed PowerShell Roslyn. Preserve the clone's third-party notices too.
Do not install a different toolchain or mutate global config merely to run this helper.

A separate narrow D323 bridge proved **every referenced corner had zero RGBA**, emitted
it explicitly, and retained source flags/nTex after stream/material/sampler checks.
That constant mapping survived topology changes. It is not a general vertex-color
repair: nonuniform colors need an actual correspondence-preserving pipeline.
The source consumer bound color by bit31 while the exporter tested bit30; correcting
only the OBJ repack argument did not by itself restore the omitted source colors.

The exporter/repacker normalizes then requantizes S8 normals. D323's accepted numerical
bound was <=1 component and <=0.5 degree; worst qualified Blender error was 0.465046
degrees. This was not raw-array identity or visual equivalence. All referenced source
normals were nonzero. Blender material datablocks also needed clearing between inputs
to prevent suffixes such as `.001` breaking exact source material names.

The reusable lesson is to qualify interchange independently, preserve the costly
allocation boundary, measure actual target performance, and keep a negative result
when tiny gains require visible damage. No automatic restart of D323 is warranted.