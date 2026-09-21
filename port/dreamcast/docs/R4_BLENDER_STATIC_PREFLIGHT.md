# D323 isolated Blender static-asset preflight

Disposition: specific blocked conversion boundary; no runtime replacement or
reduction candidate accepted. This is secondary to source-resource lifetime work.
Branch `experiment/r100-environment-blender`, base
`b1cda581c96ce4f44d86e43e3c9153e10bc47172`. Main checkout untouched.

## Selection and ceiling

Read-only residency audit selects r100.arc entry 5, common SMD BIN 0..10:
529,344 encoded bytes, 12,336 source positions, 23,127 GX triangle equivalents,
11 material parts. Each has one joint, no weights or morph table; common placement
records use motion 255 / source ID 254. They share room-archive backing across
block instances. This direct room allocation is the proposed replacement boundary.
529,344 is an impossible deletion ceiling, not feasible savings. Even hypothetical
50% encoded reduction recovers only 264,672 bytes against D322's 3,095,232-byte
enemy shortfall. Character mesh total is smaller (415,040) and carries animation
contracts; environment selection follows measured backing, not editing convenience.
No block-pool saving: its maximum active set is blocks 1/2/3, 1,126,272 bytes.

## Executed unmodified pilot

Largest common BIN 9: 87,872 source bytes, 1,888 positions, 3,704 nondegenerate
triangles. JADERLINK GC/WII BIN Tool 1.0.4 exports privately to OBJ and companions.
Both a tool-only repack and OBJ -> Blender -> OBJ -> BIN were independently checked.
The checker reuses `convert_character.triangulate`, compares oriented triangle
position/UV multisets, material header bytes, color corners and integer normals.
All 3,704 oriented position/UV triangles and material headers match in both paths.
Blender retained 1,888 positions; import/export uses the same Y-forward/Z-up axes
and unit scale. No scene recentering or gameplay transforms were applied.

However, both repacks fail source fidelity **before reduction**:

- All 11,112 referenced color corners change from RGBA (0,0,0,0) to (255,255,255,255).
- Header flags change 0xa0000000 -> 0xe0000000; nTex changes 7 -> 0.
- Normal components differ by up to one signed integer step.

`UseVertexColor:True` and `UseIdxMaterial:True` retain a color stream and original
material header, but do not restore the source values. Default `UseVertexColor:False`
omits the color pointer entirely. Source `commonModelTrans` uses bit31 to bind the
color array, so this is not an ignorable unused data difference. Tool-only bytes
78,976 and Blender bytes 79,008 are **not accepted memory savings**. Further work
requires a small source-qualified exchange/repack correction, then the same
unmodified roundtrip gate; no gameplay changes should accommodate exporter loss.

## Local Blender execution and artifacts

Blender 5.2.0 LTS, build fbe6228777e7, was launched headlessly with factory startup,
`--offline-mode --disable-autoexec`, isolated BLENDER_USER_RESOURCES. Script asserts
`bpy.app.online_access == False` and disables all add-ons. API properties were
introspected before use. No MCP server was found or configured; this was local bpy.
No external upload, model API, render, emulator run or build was performed.

Private root:
`C:/Game Dev/Emulators/re4_helpers/experiments/r100-environment-d323`

- `blender-bin9/reference-locked.blend`: pristine geometry, REFERENCE_LOCKED;
  CANDIDATE_CONSERVATIVE, CANDIDATE_LEAN and REVIEW_CAMERAS are intentionally empty.
- `blender-bin9/blender-report.json`, `blender-api.json`: offline/add-on/API evidence.
- `roundtrip-validation.json`, `validate_roundtrip.py`: exact private comparison.
- `roundtrip-bin9`: original exchange companions and tool-only failure outputs.
- `blender-bin9`: Blender exchange and repacked failure output.
- Linux `/root/probe/r100-environment-d323/audit/FINDINGS.md` and `inventory.json`:
  bounded shared allocation/instance inventory.

Tracked `blender_static_roundtrip.py` takes input OBJ and a private output directory.
Preserve/restore the original idxggbin, idxmaterial and MTL companions before BIN
repack; Blender-generated MTL is not authoritative. Textures were absent from this
geometry-only preflight and no visual/material appearance acceptance is claimed.

80%/60% geometry variants, source-compatible room repack, matched 640x480 source
views, allocation/reservation/VRAM/CPU measurements and source-hold world-visible
acceptance remain pending. Nothing was merged, pushed, selected by default or
inserted into a shared original, mirror, archive or evidence fixture.

Workflow references: https://github.com/JADERLINK/RE4-GCWII-BIN-TOOL and
https://community.openai.com/t/how-does-gpt-6-actually-generate-3d-models-in-release-demo-via-codex-local-blender-or-mcps-apis/1395391
The latter is a community description of headless bpy, not verified provenance
of an OpenAI demo or evidence of installed MCP capabilities.