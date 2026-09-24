# D367 build, stage and capture tooling

The plan and measurements are in `port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md`.

## Canonical recipe (integrated base; every stacked measurement and the m1 disc use this)

```
LH="NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=2 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1 COPY_LEAN=1 FRONT_LEAN=1 MESH_DIRECT=1 TA_DIRECT=1 NATIVE_ACTOR_DIRECT=1 UI_VRAM=1 TA_VERTBUF_KB=2048 GAME_FP_CONTRACT=off GAME_CPU=1 GAME_ROT_CACHE=1 GAME_O2=hot GAME_TRIG=1 GAME_PWC_DIAG=1 GAME_ATCHK=1 GAME_MOTION_INDEX=1 GAME_CONCAT_COL=1 GAME_SINCOS=1 GAME_MULTVEC_SCHED=1 GAME_VEC_INLINE=1 AICA_AUDIO=1 RELEASE_FLAGS=1"
M1="ROUTE_MOVIES=1 AICA_STREAMS=1 SUBSCREEN=1 UI_HANDLES=1 TEX_RESIDENT=1 FX_LEAN=1 EM10_SHARED=1 ARENA_FIT=1 GAME_COLD_OS=1 SOUND_REGION_BYTES=0x60000 MOTION_FAST_READ=1 NATIVE_ACTOR_SKIN_LAZY=1 QUALITY=1 VMU_SAVE=1 VMU_DEBUG_SLOT=1 NATIVE_MES=1 SUBSCREEN_OVL=1 SS_POOL_HIGH=1 NATIVE_PKG_HIGH=1"
PERF="FRONT_NATIVE=1 HW_LEAN=1 FOG_FAR=25000 EFFECT_LEAN=1 EFFECT_SPRITES=1 PLAN_ADMIT_LEAN=1 SCENERY_GATE=1 MODEL_SLAB_LATCH=1 NATIVE_ACTOR_LOD=1 NATIVE_ACTOR_PRELIT=1 CROWD_LOD=1 TA_DOUBLEBUF=1"
EXTRA_MAKE="$LH $M1 $PERF OBJDIR=/path/obj-<name>"
# stage: TEXDIRS="$VQ $P/tex" (tex-vq5 + PS2 bark); EFFECT_SPRITES=1 makes stage.sh prepend the
# tex-fx cache itself (tools/d367/tex_fx.sh). User discs add UI_OVERRIDES=/root/re4data/overrides/ui.
```

- `LH`: the game30 logic recipe (12.0 hw ms/tick), plus the bit-exact logic cuts GAME_PWC_DIAG=1 / GAME_ATCHK=1 / GAME_MOTION_INDEX=1 (-2.65 / -3.25 hw ms/tick at 6 / 8 engaged Ganados) and GAME_CONCAT_COL=1 (dbe1abb, a further -1.06 / -1.25; needs GAME_FP_CONTRACT=off). Rejected: GAME_PWC_FAST (+0.45 hw ms), GAME_SCHED=game (no logic gain). Never ship GAME_PWC_DIAG=2 (test-only check build). `M1`: route and memory knobs for the playable disc. `QUALITY=1` is the Standard/Original picker after Start (766332d); Standard is the default. Its text draws through NATIVE_MES=1 (native cMes glyph atlas, 32 KB VRAM). VMU saves (6d5d6a9/cd0343a): `VMU_SAVE=1` saves to the VMU (17 blocks per save, never formats, overwrites in place when full, heap 4 -16 KB) and stores the picker choice as RE4DCCFG; `VMU_DEBUG_SLOT=1` adds the RE4DCDBG debug slot (hold L+START 1 s in play, reload as FILE 20; ~96 KB taken from heap 4 only during the save, refused with a log line if short) that the user asked to keep on the first disc for reloads. `SUBSCREEN_OVL=1` loads the sub-screen code from /cd/dc/sscrn.ovl at each open (heap 4 +112 KB; ~+0.1-0.2 s per open on GD-ROM).
- `PERF` lists landed lane steps: FRONT_NATIVE (c881fba, -4.1 hw ms), the approved 25 m fog far
  plane, the native effect sprites (a0a32aa), and D1 + S1a + the slab latch (27fb5a5; fight p99
  488 -> 172 ms in Flycast, -2.4 hw ms at 25 m), and TA_DOUBLEBUF (b7a7e2d: the TA double-buffered in
  play, a single bank while a sub screen is open; needs `patches/kos-804b319-vbuf-switch.patch` in the
  d367 KOS worktree, which subscreen.mk checks with nm; r100 quiet 73.2 -> 71.3 ms Flycast mean, the
  r101 fight unchanged because it is CPU-bound; the gain grows as CPU per frame falls).
- Add each new lane step here when it lands. Untracked -D knobs don't trigger rebuilds: delete the
  tree ELF, use a fresh OBJDIR per flag set, and record the ELF sha256.

## Default recipe (LFV: LF + UI_VRAM + 2 MiB TA buffer + VQ UI/model textures + resident textures)

```
LFV="NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=2 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1 UI_VRAM=1 TA_VERTBUF_KB=2048 UI_HANDLES=1 TEX_RESIDENT=1"
P=/root/probe/d367-agents/ps2-blender/stage/ps2trees     # LD packages (private)
VQ=/root/probe/d367-agents/ui-vram/tex-vq5                # VQ texture overlay (private, see below)

# build (private OBJDIR keeps flag changes from reusing the shared obj/)
OWNERS=0x7F STATIC=1 MESH=1 EXTRA_MAKE="$LFV OBJDIR=/path/obj-<name>" \
  bash port/dreamcast/tools/d367/build.sh /path/build-<name>

# stage (MIRROR, FIXTURES_SRC and KEYED are locally extracted private data).
# TEXDIRS order matters: later directories win. The VQ overlay also re-encodes
# the GC bark key f6e54e3e-1ef21097, so the PS2 bark ($P/tex) must come last.
MIRROR=/root/probe/d367-mirror KEYED=/root/probe/d367-native-static/keyed12 \
  MESHDIR=$P/mesh TEXDIRS="$VQ $P/tex" \
  bash port/dreamcast/tools/d367/stage.sh /path/build-<name> /path/disc-<name>
```

Capture with `port/dreamcast/tools/flycast-harness/` (see its README). `stage.sh` records
its inputs in `<disc-dir>/stage-inputs.txt` and warns when a `UI_VRAM=1 TA_VERTBUF_KB=2048`
build is staged without a VQ overlay (the 2.6 MB texture pool then thrashes: 1,884 upload
failures and multi-second frames at r100 in Flycast).

### UI image overrides (UI_OVERRIDES)

`UI_OVERRIDES=/root/re4data/overrides/ui` (private, never in Git) replaces source UI images
with edited PNGs. Name and place each PNG as `extract_ui_images.py` writes it, under the
archive's path: `ss/eng/title_eff0_tpl31_tex00_CMPR_640x360.png` is the title background
(ss/eng/title.dat EFF 0, TPL 31, texture 0, key `c67f5c01-63e0879e`). `tools/ui_overrides.py`
first re-encodes the original through the same path and must reproduce the staged package
(fixtures 16-bit, or the TEXDIRS VQ overlay) byte for byte, then encodes the PNG the same
way under the original key; a size or name mismatch fails. The disc's title.dat is unchanged
(the runtime keys packages by the unmodified source texels). `stage-inputs.txt` and
`<disc>/ui-overrides-report.json` record each override's sha256. Unset: staging is unchanged.

`UI_HANDLES=1 TEX_RESIDENT=1` (texture hitch fix; Flycast r100 camera tour, frames 2400+):
- The hitch was the first-sight texture load: ~0.2 s per package at r100 (~0.3-0.4 s at r101),
  almost all of it the iso9660 lookup. The flat `/cd/dc/tex` directory (~550 packages, 17+
  sectors) overflowed KOS's 16-sector inode cache, so every open re-read the directory from
  the disc. `stage.sh` fans a TEX_RESIDENT build's packages out into `tex/0`..`tex/f` (first hex
  digit); the build opens `/cd/dc/tex/<d>/<crc>-<fnv>.re4tex`.
- `TEX_RESIDENT=1`: the room/enemy/player/weapon identity sets are preloaded at room entry
  (in disc order, leaving 32 of the 192 entries and 256 KiB for first-sight loads), absent
  packages are remembered and never evict a resident texture, eviction is
  least-recently-requested, and the runtime payload CRC is skipped (`stage.sh` verifies every
  package's CRC instead; `TEX_PAYLOAD_CRC=1` keeps the runtime check).
- `UI_HANDLES=1`: one direct-mapped handle per source image descriptor (O(1), no hashing).
- Tour result, LFV + tex-vq3 -> this recipe: median 100 -> 100 ms, p99 870 -> 119 ms, max
  4264 -> 489 ms, frames over 2x the median 289 -> 5, texture loads while moving 756 -> 6.
  The five remaining spikes are not textures (3 are draw-plan installs, `visit_draw_locals` +
  memmove, ~450 ms). The r100 room entry preloads 177 packages in 4.4 s (r101: 188 in 5.0 s).
- Image cost with the knobs on: +41,888 bytes (text +3,360; data +17,920 = the 192 cache
  entries; bss +20,608 = handle table, palette copies, preload list). `TEX_SLOTS=128`
  saves 10,240 bytes. The default build is byte-identical.

Why each part of LFV is needed (Flycast r100, frames 2401-2520, all 116.8 ms/frame):
- `TA_VERTBUF_KB=2048`: r100 sends ~1.41 MB/frame of TA stream (~1031 KB of TA
  parameters), over a 1024 KB bank on hardware (Flycast does not enforce it).
- The 2 MiB banks shrink the PVR texture pool from 4.74 MB to 2.64 MB. `UI_VRAM=1` sizes
  the native texture cache from the actual pool (LRU eviction, fragmentation retry,
  fail-fast, 2 KiB page placement for VQ).
- `tex-vq3` makes the title/menu textures (32 images, 7.24 MB -> 0.97 MB) and large model
  textures (23 images, 2.75 MB -> 0.39 MB) full-codebook VQ. Title peak 1.04 MB, r100 uses
  1.59 MB of 2.58 MB; 0 upload failures, 0 evictions. Worst model PSNR is 26.3 dB (leaf
  litter), which was not visibly different in 2x gameplay crops against LF.

### VQ overlay tex-vq6 (tex-vq5 + r101; the asset pipeline's 00-vq)

r101's room textures were never VQ: tex-vq5 is built from r100 logs only, so r101 streamed 126
textures as 16-bit (4.04 MB against the 2.47-2.55 MB budget). Uploads thrashed and the square
barely moved (warp-vp0-r101: 4,613 failed uploads, 245 ticks in 200 s). tex-vq6 is the same
rule (`--model-min-bytes 16384`) with two r101 square logs added to `ui_logs`
(`warp-vp0-r101`, `warp-sa1-r101`). The source is the route fixtures (`frontier/fixtures/tex`,
a superset of `d354v7-fixtures/tex`).
- 198 images, 18,546,688 -> 2,723,840 bytes.
- The 137 tex-vq5 packages are byte-identical.
- The 61 new r101 images go 4,521,984 -> 690,176 bytes, lowest PSNR 27.6 dB.

The asset pipeline regenerates it as each room's `tex/00-vq` (`sources.toml`: `fixtures`,
`ui_logs`, pinned `vq_overlay`).

r101 bell fight with it: 15 failed uploads, 1,955 ticks in 200 s, Flycast steady 10.1 fps
Standard / 9.4 Original (warp-sa2p-r101, warp-sa2o-r101). Standard vs Original logic trace is
STRICT. Add the logs of later rooms to `ui_logs` the same way when they are brought up.

### Generating the VQ overlay (tex-vq5; tex-vq3 below is the same rule on fewer logs)

tex-vq5 applies the tex-vq3 rule to three more logs (the camera tour and the 4/10-Ganado
crowd) and to the r100 textures the room preload loads, and makes model textures VQ from
16 KiB padded (tex-vq3: 64 KiB), so the r100 room set fits the 2.58 MB pool: 137 images,
14,024,704 -> 2,033,664 bytes, lowest PSNR 26.3 dB (the tex-vq3 leaf litter). Logs are kept
privately in `/root/probe/d367-agents/ui-vram/logs/`:

```
L=/root/probe/d367-agents/ui-vram/logs
python3 port/dreamcast/tools/vq_native_ui.py --textures /root/probe/d354v7-fixtures/tex \
  --log $L/v2-run-output.txt --log $L/v3-run-output.txt --log $L/p2048a-run-output.txt \
  --log $L/la-run-output.txt --log $L/lod2048-run-output.txt --log $L/scen-tour-G25-run-output.txt \
  --log $L/actors30-gcrowd-crowd-run-output.txt --log $L/actors30-gfull-crowd-run-output.txt \
  --log $L/uivram-tour-t1-run-output.txt --log $L/uivram-tour-t3-run-output.txt \
  --model-min-bytes 16384 --output /root/probe/d367-agents/ui-vram/tex-vq5
```

### Generating the VQ overlay (tex-vq3)

The packages are private derived game data: keep them out of Git. Inputs are the
fixtures' native texture packages (`$FIXTURES_SRC/tex`, default
`/root/probe/d354v7-fixtures/tex`) and Flycast run logs that reached r100 gameplay; the
`native UI: load ...` lines name the images the title, menus and r100 load. The measured
`tex-vq3` came from the five logs kept (private) in `/root/probe/d367-agents/ui-vram/logs/`:

```
L=/root/probe/d367-agents/ui-vram/logs
python3 port/dreamcast/tools/vq_native_ui.py --textures /root/probe/d354v7-fixtures/tex \
  --log $L/v2-run-output.txt --log $L/v3-run-output.txt --log $L/p2048a-run-output.txt \
  --log $L/la-run-output.txt --log $L/lod2048-run-output.txt --model-min-bytes 65536 \
  --output /root/probe/d367-agents/ui-vram/tex-vq3 [--previews <png-dir>]
```

Without those logs, pass the `run-output.txt` of any one LFV/LF run that reached r100
instead. The encoder is deterministic: that gives the same 55 packages byte for byte, plus
3 model textures only the LF scenery loads (256x256, 32.9-34.5 dB; 58 images,
10,387,456 -> 1,417,216 bytes). The 58-image set was not captured in Flycast.

UI images (loaded before the first room binds, or indexed C4/C8 sources) of at least 32 KiB
padded and 32 px per side, and model textures of at least 64 KiB padded, are re-encoded
by the pinned KOS `pvrtex` (`/root/work/kos-re4dc-d336/utils/pvrtex/pvrtex`, full
256-entry codebook). The package names (source identities), padded sizes and UV scale are
unchanged. `vq-native-ui-report.json` lists every image with its PSNR; the expected summary
is 55 images, 9,994,240 -> 1,361,920 bytes. The overlay is required only by the 2 MiB TA
recipe; the default-flag build ignores it.

## Effect sprites (`EFFECT_LEAN=1 EFFECT_SPRITES=1`, effects30.mk)

Muzzle flash (weapon owners 0x34-0x4f), the shot's core effects (owner 0) and blood (EM10,
owner 0x10) are drawn as native PVR sprites in OT order (the deferred translucent queue); a
sprite that finds no queue room is dropped, never the frame. Their TPL images have no
packages in the base texture set, so `stage.sh` runs `tex_fx.sh` for any build whose
candidate.txt has `EFFECT_SPRITES=1`: 552 packages from etc/core.das, em/em10.drs and
em/wep00-09.drs (pinned list, `prepare_native_ui.py`, ~10 s once), cached in `FX_CACHE`
(private, default /root/probe/d367-fx-cache, source `RE4DATA`, default /root/re4data) and
staged FIRST in TEXDIRS so the VQ overlay and the PS2 bark still win. No manual step.
r100 fight (a0a32aa): hw 133.3 -> 134.1 ms (+0.8, for effects that were not drawn before),
STRICT; the run log line is `native effect sprites: queued= direct= missing= dropped=`.

## Asset pipeline (assets.sh)

`tools/d367/assets.sh` generates a room's asset set from formulas instead of hand-tuned
arguments, caches every step by content hash, writes a manifest and a review sheet, and
stages the result for `stage.sh`. The design, formulas, override format and plug-in interface
are in `docs/D367_ASSET_PIPELINE.md`. Everything it reads or writes is private: the cache,
manifests and review sheets live under `RE4DC_ASSETS_ROOT` (default
`/root/probe/d367-agents/assets`), and the input paths are listed in
`tools/assetpipe/sources.toml`.

```
tools/d367/assets.sh rooms                       # every stage room on the GC disc image
tools/d367/assets.sh inventory r101              # BIN counts, bounds, instances
tools/d367/assets.sh build r100 [--verify]       # --plan recipe (default today): the accepted packages
ASSETS=$RE4DC_ASSETS_ROOT/out/standard/r100 bash tools/d367/stage.sh <build> <disc>
```

`build r100 --plan recipe` reproduces the LFV r100 inputs byte for byte: the seven LD packages
(`COMMON` `cdeade63...`), the tex-vq5 overlay (137 images) and the PS2 bark. `--verify`
rebuilds every cached step and compares the output hashes. It also writes
`review/standard/r100/index.html`: source vs chosen renders at 3, 8 and 20 m, and predicted
hardware ms per asset. `stage.sh` reads the generated `stage.env` through `ASSETS=`, and
variables set explicitly still win.

## Candidate flag sets (Flycast r100, frames 2401-2520)

| Name | ms/frame | EXTRA_MAKE |
|---|---|---|
| LD | 117 | `NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=1 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1` |
| LF | 117 | `NO_EH=1 NATIVE_ACTOR=1 NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1 PVR_FAST_WAKE=1 BRIDGE_LEAN=1 PVR_PIPELINE=2 MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1`. Async present; `build.sh` selects `/root/work/kos-re4dc-d367` (see `patches/README.md`). Neutral in Flycast; adopted because it stops the CPU waiting on render. |
| LFV (default) | 117 | LF plus `UI_VRAM=1 TA_VERTBUF_KB=2048`, staged with the `tex-vq3` overlay (above). Fits the r100 TA stream on hardware; same Flycast frame time as LF. |

LD packages: the scenery30 LOD packages with the PS2 tree substitution (`MESHDIR`), and
the PS2 bark texture overlay (`TEXDIRS`). The generation steps are documented with the
converter (`tools/convert_room_bins.py --lod ...`).

Add `PC_SAMPLER=1 PC_SAMPLER_BYTES=8192` for the PC-sampling profiler, when that knob is
present in the tree.

## Blender scenery knobs (items 20/21, `game/blender30.mk`)

Both default to 0, and the default image is then byte-identical. Both need `MESH_LOD=1` and
packages annotated by `tools/mesh_annotate.py`. A runtime without the knob ignores the
annotations.

| Knob | Effect | Package input |
|---|---|---|
| `TREE_IMPOSTOR=1` (`TREE_IMPOSTOR_MM=12000`) | Past that view depth, each PS2 tree draws as one camera-facing punch-through quad from a 16-view atlas (4bpp palettised VQ, format kPal4). Quads are batched per atlas into the PT list. | `--impostors` (`tools/tree_impostors.py`) |
| `MESH_TEXTURES=1` | A part with a texture record binds that prepared package instead of its source image. This is how house shells carry their baked GC detail. | `--textures` (`tools/house_shells.py`) |

```
# tree impostors (COMMON): bake, encode, annotate; TEXDIRS += <imp>/tex
blender -b --factory-startup --python tools/blender/bl_impostor_bake.py -- <trees-dc> <bake>
python3 tools/tree_impostors.py <imp> --bake <bake> --trees <trees-dc>
python3 tools/mesh_annotate.py <pkg>/COMMON.re4mesh <out>/COMMON.re4mesh --impostors <imp>/impostors.json
# house shells (FILE_01/17, /18): shell + bake per BIN, package, replace, annotate; TEXDIRS += <sh>/tex
blender -b --factory-startup --python tools/blender/bl_house_shell.py -- FILE_01_17.obj <tpl png dir> <s17> \
  --keep-alpha --cull-hidden --faces 550 --tex-size 512
python3 tools/house_shells.py <sh> <s17> <s18>
python3 tools/convert_room_bins.py <tmp>/FILE_01.re4mesh --owner 1 --bins <R100.FILE_1> <LD lod args> \
  --lod-substitute <dir: the other FILE_01 replacements + <sh>/replace/*.obj>
python3 tools/mesh_annotate.py <tmp>/FILE_01.re4mesh <out>/FILE_01.re4mesh --textures <sh>/textures.json
# honest comparison renders (VQ-decoded texture), 3/8/20 m, 8 azimuths, worst first in metrics.json
blender -b --factory-startup --python tools/blender/bl_house_compare.py -- FILE_01_17.obj <s17>/FILE_01_17.obj \
  <tpl png dir> <sh>/preview/FILE_01_17.png <cmp>
```

`TREE_IMPOSTOR=1` at 12 m, measured on r100 frames 2401-2520 with LF in one Flycast sitting:
frame 116.8 -> 100.1 ms, work 91.3 -> 88.6 ms, TA 1.41 -> 1.28 MB/frame (about 30 quads in 5
batches). The hardware model (`frame_ms.py --impostor`) gives -1.08 ms, or -0.98 ms at 15 m.
VRAM is 84 KB of atlases plus 77 KB of PT bins.

`MESH_TEXTURES=1` with the FILE_01/17 and /18 shells (550 and 800 triangles, 512 VQ each)
gives -0.71 ms/frame in the hardware model (heavy mean 8.62 -> 7.91; per BIN 0.81 -> 0.32 and
0.63 -> 0.40). VRAM is 132 KB. Not measured in Flycast.

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

## Warp rig (`DBG_WARP=1`, test builds only)

Starts a test build next to an event trigger or a door, with the scenario state that event needs,
seconds after boot, instead of a whole title -> intro -> r100 walk.

- **Build:** add `DBG_WARP=1` to the build flags (dbgwarp.mk, dbgwarp_bridge.cpp). With the default
  `DBG_WARP=0` the hooks compile out and the image is byte-identical. Never on a user disc: stage
  `warp.txt` only on test discs.
- **Config:** `/cd/dc/warp.txt` in the staged fixtures (FIXTURES_SRC). Write it from a preset:
  `python3 port/dreamcast/tools/d367/warp.py <preset> [--door] [--dump] -o <fixtures>/warp.txt`
  (`warp.py list` lists them). Lines: `room 0x100`, `pos x y z`, `ang <rad>` or `dir 0x8000`,
  `rsf <room> <bit>...` (room save flags), `scenario <0|1> <hex>`, `find <hex>` (Item_find_flg),
  `unlock <0|1> <hex>`, `inv default`, `act <room frame> <a|b|x|y|start|fwd|back> <hold>`,
  `trg <no> <room frame> [room]` (`--trg NO:FRAME[:ROOM]`), `dump`.
- **What it does:** once the title data is loaded, the title, picker and menus are skipped and
  titleExit takes the debug-start path (config.txt [STAGE]/[ROOM] + START) with the warp room, so
  the room loads through the game's own new-game and room-load code. Quality comes from RE4DCCFG /
  quality.txt. `pos`/`ang` replace the jump point's NextPos/NextY. The flags are set once at the
  first room entry (after gameInit, before the room init reads them). `act` lines press a button or
  push the stick in the first room (door test mode), timed in PADRead calls (one per game frame in
  play; they keep counting inside the sub screen, so Y then B opens and closes the inventory); an event cuts the running action. `dump` logs
  every AEV area of the room (number, type, trigger, centre, door destination). `trg` makes the
  source's developer shortcut `DebugTrg(no)` (sce_com.cpp; the retail stub returns 0) return 1 once,
  at or after that frame of the current room (of `room` only, when given). r101_checkEmNum rings the
  bell on `DebugTrg(0)`, so the square fight reaches event 30 without 15 kills or the 11,700-frame
  timer. The fight before it is the game's own; everything after the bell is the game's own too.
- **Log:** `warp:` lines give vblank and guest time for the title skip, each room entry, the
  placement and each action.
- **Boot fixture:** a blank harness VMU asks to create RE4DCSYS; stage a padscript with
  `0 0008 3 card=8/1 3000` and `+20 0100 3 card=8/1 300` (clock source).
- **Base fixtures:** r101 needs 16 motion keys that `/root/probe/d354v7-fixtures` lacks
  (`RE4DC MISSING: motion key read` at r101 entry); `frontier/fixtures` has them.

| Preset | Room | Flags | Event it reaches |
|---|---|---|---|
| r100-spawn | 0x100 | none | s40 movie and the radio call (r100_StartEvent) |
| r100-post-radio | 0x100 | rsf 13, Scenario[0] 0x10 | play at the gate |
| r100-house-door | 0x100 | rsf 13, Scenario[0] 0x10 | s03 (area 0xA, r100_Sce_look) |
| r100-bridge | 0x100 | rsf 13, Scenario[0] 0x10 | s44 (area 0x1B, r100_EventBrige) |
| r100-east-door | 0x100 | rsf 13, Scenario[0] 0x10 | r101 door (AEV area 0, no lock) |
| r101-entry | 0x101 | none | r101 first visit |
| r101-bell-fight | 0x101 | find 0x2000 | r101 square fight |
| r101-bell | 0x101 | find 0x2000, trg 0 at 1200 | the fight, then the bell (event 30, r101s30) |

**A warp start is not STRICT against continued play.** The room is entered fresh with synthesized
flags; the RNG, timers, enemy list state, inventory and play time are those of a new game, not of
a run that played up to that point. Use warps for iteration and bring-up (does the door open, does
the event start, what does the room cost). Logic proofs, STRICT traces and route sign-off still
use normal runs.

### Cost, heap-4 and class options (W9b)

| Option | Effect |
|---|---|
| `--lod-bias OWNER:BINS=F` | Scales the stored level errors, so coarse levels switch in closer. r101: 0.25 on the heavy terrain/building BINs; r103: 0.375 (0.25 visibly thins its trees). |
| `--lod-floor [OWNER:BINS=]MM` | Level 0 is the source simplified to MM (world, source mm) before clustering. A part is only floored when its area and area-weighted normal stay within 0.2%. Otherwise it keeps the source. `2` removes 14-16% of level-0 triangles. |
| `--lod-share` | R4IM v3. Coarse meshlets index their part's existing vertices through a u16 table instead of storing copies: -133 KB (r101), -176 KB (r103), -176 KB (r100, all seven packages). Level 0 is unchanged. Only a runtime with v3 support adopts it (`room/instanced_mesh.hpp`). Lighting is still one pass per part, over the part's vertex pool. |
| `--class OWNER:BINS=CLASS`, `--class-auto`, `--class-rule CLASS=FULL_M,CULL_M` | Per-mesh scenery class (default, ground, tree, landmark, clutter, structure) and per-room distances, both optional, in the v2/v3 LOD header. A shared runtime distance rule reads them through `mesh_class()` / `class_rule()`. `--class-auto` tags card fields and replaced BINs as tree. Other BINs become ground, clutter or structure by world extent (`auto_class`). Landmarks are only tagged by hand. |

Current r101/r103 recipes (the model's worst view at a 25 m fog far: r101 10.1-12.8 ms, r103 10.9-14.0 ms):

```
# r101 (after the PS2 tree step above)
... --lod-substitute <trees> --lod-bias 0xff:13-17=0.375 --lod-bias 0xff:3,9,12,34,70,64,31,29,38=0.25 \
    --lod-floor 2 --lod-share --class 0xff:13-17=tree --class-auto
# r103
... --lod-bias 0xff:38,59,60,62-67=0.375 --lod-bias 0xff:0,18,61,17,24,28=0.375 \
    --lod-floor 2 --lod-share --class 0xff:38,59,60,62-67=tree --class-auto
```

The runtime keeps a v3 meshlet's gathered corners in a 3 KiB buffer in the package's own heap-4
allocation (not the packet range: with MESH_DIRECT too few slots remain there after the part headers).

## Room discovery (`assets.sh discover <room|route>`)

The first stage of the room pipeline: what a room can load, and whether the build and the prepared
disc provide it, from the source data alone (no emulator, seconds). Run it before building a disc for
a room, and after changing MODULES, the module table or the prepared archives.

```bash
bash port/dreamcast/tools/d367/assets.sh discover route                 # r100 r101 r103
bash port/dreamcast/tools/d367/assets.sh discover r100 --log <evidence>/run-output.txt   # + compare a run
bash port/dreamcast/tools/d367/assets.sh discover r100 --repo <tree> --obj <OBJDIR>      # another tree/build
```

- **Demand:** the room's enemy list (stage.cpp checkEmListNo; stage 1 mirrored so far), each entry
  of the room (alive bit set: spawns at entry; clear: `enabled-later`, e.g. em2a in r100 after s20),
  the room script's `EmSetFromList2` spawns and `EmReadSearch`/`SearchEmModule` loads. Enemy id ->
  read.cpp `EmFileTbl` -> dvd.cpp `FileTbl`: archive (`em/emXX.drs`) and REL module.
- **Checks:** Makefile MODULES, the ENEMY_DEMAND audit list, platform/modules.cpp
  `MODULE(<rel.json module_id>, name)`, missing-symbol stubs naming the module (`--obj`/missing.txt),
  the prepared archive (sources.toml `prepared_mirror`), at most 4 live enemy archives
  (EmReadModule[4]), and heap 4: the prepared header's allocation (u32 at 0x24, as "DVD: Mem Alloc")
  summed over every archive against `[room.X.demand] enemy_heap4_bytes`, a measured value
  (free at an enemy read + the enemy allocations live then). A room without one says so; record it
  from a run log.
- **`--log`:** archives the run loaded that were not predicted (a discovery gap), failed reads, the
  first `alloc[..]:free[..]` shortfall, HALTs, and the linked modules.
- Output: the report, `<assets_root>/discover/<room>.json`; exit 1 when anything is a problem.
- Proof (2026-09-24): on dadfbac (before e6f65cc) it reports em2a missing from MODULES, the audit list and
  the table (the warp-east-1 HALT main_sub.cpp(1440)); on r100 the worst case is 171,328 bytes over the
  measured room, the exact shortfall warp-ea4-after logged at the em23 (crows) read; r101's
  prediction equals what warp-bell1 loaded.
- **Lint** (tools/assetpipe/wiring.py): the known porting traps in each needed module and the room's
  stage module, in the code the Dreamcast build compiles (`#if` evaluated with `__PPC__` undefined):
  `value-init` (`new (em) cEmXX()` zeroes what cEmMgr::construct set), `asm-alias` (an asm-label
  alias of a file-static binds to a missing-symbol stub), `slot-math` (`EmMgr.pArray` / `EmMgr.size *`
  instead of `EmMgr.workAt` + null check), `vptr-offset` (`(u8*)this + 4 + ...`, warning). Errors
  are problems.
- **`--wire`:** writes the missing wiring into `--repo` (default this tree): Makefile MODULES,
  `MODULE(name)` and `MODULE(<rel.json id>, name)` with a room/reason comment, and the ENEMY_DEMAND
  audit list only when the module's lint has no errors. It links the original module's code; game
  logic is never generated. Review the diff and prove the room as usual.
- Proof (round 2): on dadfbac, `discover r100 --wire` writes e6f65cc's Makefile/modules.cpp lines and
  the lint reports the four traps that commit fixed by hand (em2a value-init, slot-math, asm-alias;
  em21 asm-alias); the audit entry waits for them.
- **Heap-4 options** (tools/assetpipe/enemy_heap.py): each live archive's prepared body by tag, and
  the lossless ways to shrink it: `rel-strip` (the REL copy of a linked module; exact),
  `tex-upload` (TPL texels to VRAM), `motion-stream` (FCV keys through motion leases), `effect-compact`
  (unmeasured). Each is `applied`, `qualified` (prepare_enemy_motions.py supports it for that
  archive; its GANADO/SMALL tuples are read from the tool) or `needs-contract`, read against
  sources.toml `enemy_compaction` (the compaction summary). A SHORT room gets a plan: qualified
  options first, then the largest needs-contract ones. r100 (2026-09-24): nothing qualified is left;
  em21 motion-stream (<= 294,240 B) alone covers the 171,328 B crows shortfall; em23 + em2a
  (motion + textures + em2a's 17,152 B REL) is the alternative.
- **Events** (tools/assetpipe/events.py): every `evd/r<room>sNN.evd` the room script names, read from
  the GC ISO: size, asset bytes, actors (kind-3 model sets: em10/em13/em15/em16 Ganados, pl00 Leon,
  pl07 Ashley, obm objects ...). An evd is self-contained (its asset table holds the models,
  textures and motion), so event actors need no enemy REL or archive. The check: a route movie
  (sources.toml `route_movies`; the movie presents the event, the evd is never loaded) or the
  prepared evd with its qualified `.evq` (native_event_file.cpp refuses one without). Names not on
  the disc (r100s01/s02/s42) are listed only. Route (2026-09-24): every r100/r101 event has a movie,
  r101's evds are also qualified, r103 names none.
- **Standard + VRAM** (tools/assetpipe/standard.py): from the room's Standard set index
  (`<assets_root>/out/standard/<room>/low/index.txt`): package bytes vs Original (the native static
  package is heap 4, so the Standard enemy heap-4 room = the measured one minus that delta) and the
  VRAM Standard adds (`tex` records; `drop` textures are not subtracted: an upper bound) against
  `[room.X.standard.budget_context] vram`. Standard assets load only with QUALITY_ASSETS=1, so
  measured budgets so far are Original packages. With `--log`: lowest texture-pool free, peak used,
  rejects, and texture packages the room loads that are not on the disc (`open failed`).
  Route (2026-09-24): Standard r100 -282,560 B of packages, so the crows fit with QUALITY_ASSETS=1
  (111,232 spare; Original stays 171,328 short); r101 -423,328; r103 -406,496. VRAM upper bounds
  leave r101 >= 32,000 and r103 >= 145,536 free. warp-dbp0-fight-orig: lowest free 10,280 and 16
  texture packages missing on that warp disc (a staging gap to trace).
- Not covered yet: other stages' list rules.

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

### Disc IO probe and door-load telemetry (`IO_PROBE=1`, default 0)

Diagnostic builds only; the default image does not change.

- `MOTION_FAST_READ=1` (default 0): motion keys are read whole into their aligned
  residency block (98 -> 0.18 ms per key in Flycast).
- `IO_PROBE=1` adds `platform/io_probe.cpp`, which runs timed disc reads at the end of
  OSInit when the fixture `ioprobe.txt` (staged as `/cd/dc/ioprobe.txt`) exists, e.g.
  `seq=8 cold=48 opens=50`. Results go to `ioprobe:` log lines, the `re4dc_ioprobe`
  struct, VMU LCD pages and a PERF_HUD row.
  - The stream phases `idle=N load=N` default to 0 (off): in Flycast they faulted or reset
    the guest in 4 of 6 runs. Pass them only for diagnosis.
- With the room cycle fixture (`roomcycle.txt`, `door 3 300`) each room entry logs one
  `iotime: door` and one `iotime: steady` line: wall time, game frames, source DVD
  blocking and motion-key waits. Read them with
  `tr -d '\0' < run-output.txt | grep -a "iotime: door"`.
- `platform/io_wrap.cpp` links `--wrap=fs_read,fs_open,thd_sleep,genwait_wait` and prints
  `iowrap:` lines with each `iotime` line: blocking time by file path, by caller (return
  address, symbolize with `symbols-demangled.txt`), by KOS wait kind and thread, and per
  thread.
