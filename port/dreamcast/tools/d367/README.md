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
| LD | 117 | `NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=1 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1` |
| LF (default) | 117 | `NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=2 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1`. Async present; `build.sh` selects `/root/work/kos-re4dc-d367` (see `patches/README.md`). Neutral in Flycast; adopted because it stops the CPU waiting on render. |
| LH | 83 (hw 120.3) | `NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=2 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1 COPY_LEAN=1 FRONT_LEAN=1 MESH_DIRECT=1 TA_DIRECT=1 NATIVE_ACTOR_DIRECT=1 UI_VRAM=1 TA_VERTBUF_KB=2048 GAME_FP_CONTRACT=off GAME_CPU=1 GAME_ROT_CACHE=1 GAME_O2=hot GAME_TRIG=1 AICA_AUDIO=1 RELEASE_FLAGS=1`. Build TEXDIRS with tex-vq3 first, then the PS2 bark (they share a texture key). Logic trace STRICT vs the TR-OFF baseline; hw game-logic 12.0 ms/tick. The integrated perf lane's base; FRONT_NATIVE=1 is not yet measured on it. |

LD packages: the scenery30 LOD packages with the PS2 tree substitution (`MESHDIR`), and
the PS2 bark texture overlay (`TEXDIRS`). The generation steps are documented with the
converter (`tools/convert_room_bins.py --lod ...`).

Add `PC_SAMPLER=1 PC_SAMPLER_BYTES=8192` for the PC-sampling profiler, when that knob is
present in the tree.

## Any room: r101, r103 (W9)

The same package recipe as r100 (instanced meshes, LOD at `MESH_LOD_PX=3`, fog to the
source far plane), read straight from the room SMD. Every render-qualified local BIN is
packaged. r101 and r103 have no common placements, so they have no COMMON package.

```
# packages (private data; st1/<room>.das from the route mirror's iso-src)
python3 tools/convert_room_bins.py <pkg>/MAINSCENARIO.re4mesh --owner 0xff --smd st1/r101.das \
  --lod --lod-min-gain 0.4 --lod-max-levels 4 --lod-eps 24,48,96,192,384 \
  [--lod-substitute <trees> --lod-bias 0xff:13-16=0.375]
# PS2 trees paired by placement (r101: GC 13-16 <- PS2 81+82, 78, 79, 80; GC bark kept)
python3 tools/ps2_trees.py <trees> --room st1/r101.das --gc-bins 13-16 --ps2-bins 78-82 \
  --ps2-obj <PS2 r101_004.scenario.obj> --dc-uv
# release: the packaged BINs' GX payload leaves the prepared room archive (.dar and .arc)
python3 tools/room_smd.py release <room>.dar <pkg>/MAINSCENARIO.re4mesh.json <released>.dar
python3 tools/room_smd.py release <room>.arc <pkg>/MAINSCENARIO.re4mesh.json <released>.arc
# stage
MESHROOMS="r101=<pkg>" ROOMFILES="st1/r101.dar=<released>.dar st1/r101.arc=<released>.arc" \
  bash port/dreamcast/tools/d367/stage.sh /path/build-<name> /path/disc-<name>
```

`tools/room_smd.py` holds the release contract. A released BIN keeps its header, part
headers (stream size 0), CLR0, and a 2-vertex box, so bounds and the part walk are
unchanged. The runtime matches its parts by index. A released archive needs its package
and `NATIVE_MESH=1`: a released part never falls back to GX. The prepared room's NTR
texture index is rebased. `tests/test_room_smd.py` covers this, plus r101/r103 when
`RE4DC_ROUTE_DAS_DIR` holds the route .das files.

## GDEMU image (W10)

`GDI=1 GDI_OUT=/mnt/d/... stage.sh ...` also writes a GDI from the same tree through
`mkgdi.sh`, which also runs on its own with the `mkdisc-hardlink.sh` arguments:

| Track | LBA | Content |
|---|---|---|
| 01 | 0 | MODE1 placeholder ISO, 606 sectors (low-density area) |
| 02 | 756 | Audio, 302 sectors of silence |
| 03 | 45000 | IP.BIN plus the game ISO9660, with absolute extents (`genisoimage -C 0,45000`) |

- 1ST_READ.BIN is unscrambled, as a GD-ROM boot requires.
- IP.BIN fields: device `GD-ROM1/1`, area `JUE`, peripherals `0799810` (VGA, VMU,
  Start/A/B/X/Y/d-pad, analog stick and triggers).
- KOS mounts `/cd` from the low-density TOC. The game links with
  `-Wl,--wrap=cdrom_read_toc` (`game/platform/gdrom_mount.cpp`), which gives fs_iso9660
  the high-density TOC on a GD-ROM, and the boot log shows `gdrom: /cd from
  high-density TOC`. CD-R images are unchanged. Every file the game reads must be in
  track 3.
- `SECTOR=2352` (the default) writes raw MODE1 tracks with EDC/ECC (`mode1raw.c`, built
  with the host cc). `SECTOR=2048` writes `.iso` tracks. Either way the user data is
  2048-byte MODE1.
- To test in Flycast, boot `disc.gdi` (evidence `gdemu-a`; control `gdemu-a-cue`).
