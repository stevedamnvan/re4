# D367 build, stage and capture tooling

The plan and measurements are in `port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md`.

## Commands

```
# build (private OBJDIR keeps flag changes from reusing the shared obj/)
OWNERS=0x7F STATIC=1 MESH=1 EXTRA_MAKE="<flags> OBJDIR=/path/obj-<name>" \
  bash port/dreamcast/tools/d367/build.sh /path/build-<name>

# stage (MIRROR, FIXTURES_SRC and KEYED are locally extracted private data)
MIRROR=/root/probe/d367-mirror KEYED=/root/probe/d367-native-static/keyed12 \
  MESHDIR=<packages> TEXDIRS="<texture overlays>" \
  bash port/dreamcast/tools/d367/stage.sh /path/build-<name> /path/disc-<name>
```

Capture with `port/dreamcast/tools/flycast-harness/` (see its README).

## Candidate flag sets (Flycast r100, frames 2401-2520)

| Name | ms/frame | EXTRA_MAKE |
|---|---|---|
| LD (current best) | 117 | `NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=1 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1` |
| LF | measuring | LD with `PVR_PIPELINE=2`, built against a KOS with the async-present patch (`RE4DC_KOS_BASE=<patched kos>`) |

LD packages: the scenery30 LOD packages with the PS2 tree substitution (`MESHDIR`), and
the PS2 bark texture overlay (`TEXDIRS`). The generation steps are documented with the
converter (`tools/convert_room_bins.py --lod ...`).

Add `PC_SAMPLER=1 PC_SAMPLER_BYTES=8192` for the PC-sampling profiler, when that knob is
present in the tree.
