# Source-contract and roundtrip checklist

Use the source consumer and actual loaded package as authorities. Establish the
archive/tag/ordinal/BIN identity and its material, texture, placement, activation,
attachment and animation contracts; filenames alone are not identities. Preserve
common/unique instance relationships and source bounds/transforms. Count backing
once per allocation; repeated draws may increase FPS opportunity without increasing
resident geometry bytes.

For an unmodified roundtrip, compare tool-only and Blender paths separately:

- Encoded size/hash; positions and quantization scale; oriented triangle multiset
  including winding; bounds and source transform; no unexplained coordinate recentering.
- Referenced UVs, seam/material boundaries, normal directions and zero-length behavior,
  RGBA including alpha, exact material order and source texture references. Duplicate
  triangles require unambiguous correspondence, not a map that silently overwrites one.
- Joint/skin influence/rest-pose data, morph targets and bone/attachment references when
  present. A rigid static pass does not qualify characters. Character validation also
  needs appropriate motion, attacks/reactions/death and attachment behavior.
- Companion metadata and source flags; nested table pointers, alignment and native
  external texture records through the recovered game's owning archive. Reuse its
  existing endian/qualification/packing path. Preserve source collision/nav/events.

Set tolerances against source precision and the intended visual contract. D323 used
exact oriented positions/UV/colors/material/header checks with <=1 S8 component and
<=0.5 degree normal deviation for an explicitly labelled numerical candidate. That
bound is historical, not mandatory for every asset. Rejected meshes retain originals;
a mesh without a trustworthy correspondence or supported morph path does not pass.

Only apply a small correction with demonstrated mapping. For example, D323's uniform
zero-color bridge was topology-independent only after proving every referenced corner
had that exact constant. Never generalize it to multicolor meshes or patch changed
geometry's normals/colors using unrelated source indices. Retain sampler-count/flag
semantics from the source after validating active references, not blind byte copying.

During reduction, protect required discontinuities and review silhouettes/openings,
cover/attachment/collision alignment. Geometry images are inspection, not target-light
or gameplay equivalence. Record whether surface deviation is sampled or a true bound.
If protective constraints leave little reduction or exceed declared quality limits,
report not worthwhile instead of removing constraints to reach a percentage target.