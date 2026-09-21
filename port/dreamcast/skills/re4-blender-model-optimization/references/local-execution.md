# Local Blender execution

Installed-path reference (verify before use):
`C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`, historical version
5.2.0 LTS / build fbe6228777e7. No Blender MCP was installed during D323. Headless
CLI plus saved bpy scripts worked; MCP is not required. Do not replace MCP config,
install third-party generation services or enable network integrations for this skill.

Inspect existing Blender processes and avoid touching any open/unsaved user session.
Launch a separate background factory session with a private `BLENDER_USER_RESOURCES`,
`--offline-mode --disable-autoexec`. Assert `bpy.app.online_access` is false and
explicitly disable add-ons in that session. Do not save global preferences. Imported
assets stay local. The historical source textures may be absent from a geometry
preflight; report that and do not call an untextured preview material acceptance.

PowerShell example (supply actual absolute private paths):

```powershell
$env:BLENDER_USER_RESOURCES = $privateProfile
& $blender --background --factory-startup --offline-mode --disable-autoexec `
  --python $skillScript -- $inputObj $newPrivateOutput
```

Use tool execution time limits; if a command exceeds its window, inspect the process,
log and output before retrying. Do not start overlapping retries. No Blender rendering
or heavy processing during another agent's timed emulator run. Consult current API
properties (`get_rna_type().properties`) before adopting a new bpy operator or parameter.
The helper records this inventory and does not render.

OBJ importer/exporter axes must match each other and the independently established
source mapping. The bundled helper uses Y forward/Z up, unit scale, and no recentering;
that preserved the D323 exchange coordinates. It is not a universal source-unit claim.
Preserve an original copy of metadata files before export: Blender's generated MTL
is not authoritative for source flags, texture bindings or alpha ordering. Clear unused
material datablocks in the isolated session to avoid name suffixes changing identities.

Run `python scripts/blender_roundtrip.py --help` without Blender for usage. The actual
script requires bpy and refuses an existing output directory, preserving old evidence.
All modifying operations target the new private Blender session and output directory.