# D367 asset pipeline: formula-driven asset generation for every room

Status: steps a-b done (2026-09-23). Owner: assets agent. Offline tooling, off the frame path.
Tool: `port/dreamcast/tools/d367/assets.sh` (entry `assets.py`, code in `tools/assetpipe/`).

The user's request: "build that tool so we can generate all of the game assets. we can guess
based on asset sizes etc. how we need to adjust them formulaically instead of manually. then
we can upscale or reset assets in testing."

So the pipeline:
- measures every asset;
- predicts each option's hardware cost from formulas with measured coefficients;
- lets a per-room solver pick options within the room's budgets;
- builds the chosen outputs with the existing generators;
- writes a review sheet and a manifest;
- stages the result for `stage.sh`.

Any asset can be pinned to `reset`, `upscale` or explicit parameters, then rebuilt.

## 1. Command line

```
assets.sh <room|route|all> [--mode standard|original] [--only CLASS[,CLASS]] [--override FILE ...]
          [--jobs N] [--dry-run] [--verify] [--no-review]
assets.sh inventory <room|all>      # measure only: counts, bounds, textures, instances
assets.sh plan <room>               # solve only: print decisions and predicted cost, build nothing
assets.sh calibrate [--set FILE]    # re-fit coefficients from evidence dirs -> costmodel.fit.toml
assets.sh review <room>             # rebuild the review sheet from the last build
assets.sh stage-env <room|route>    # print the stage.sh environment for the last build
assets.sh rooms                     # every stage room found in the source disc(s)
```

- `route` is r100, r101 and r103. `all` is every `St*/r*.das` in the source disc image(s): 85
  rooms on the GC debug disc 1.
- `--only` limits the run to classes: `scenery`, `tree`, `house`, `texture`, `actor`, `pvs`,
  `audio`, `movie`. Everything else is taken from the cache as it is.
- `--verify` rebuilds every step into a scratch cache and compares output hashes and the
  manifest hash with the recorded build. It fails on any difference.
- Private roots come from `RE4DC_ASSETS_ROOT`, default `/root/probe/d367-agents/assets`:
  `cache/` (content-addressed objects), `out/<mode>/<room>/` (staged views and manifests),
  `review/<mode>/<room>/`.
- Private inputs (disc images, mirrors, exports, PS2 files) are named in `assetpipe/sources.toml`
  and can be overridden by the environment variables listed there. Nothing private is tracked.
- r101/r103 recipes need W9b converter options. Until they land in the checkout, set
  `RE4DC_SRC_CONVERTER=/root/probe/d367-agents/w9/ptree/port/dreamcast/tools`. A room with
  `w9b = false` (r100) always uses the checkout's converter, so the variable does not change
  r100's bytes. With it, `build r101|r103 --mode original` reproduces W9's `m-r101-FIN` /
  `m-r103-FIN` packages byte for byte (rooms.toml `expect`).

## 2. Assets and classes

An asset id is `<room>/<class>/<name>`:

| Class | Unit | Examples | Generator |
|---|---|---|---|
| `scenery` | one room BIN (all its placements) | `r101/scenery/0xff:12` | convert_room_bins.py |
| `tree` | a tree BIN (card field or PS2 replacement) | `r100/tree/0xfe:3` | ps2_trees.py + convert_room_bins.py; tree_impostors.py |
| `house` | a building BIN that has a shell | `r100/house/1:17` | house_shells.py + bl_house_shell.py |
| `texture` | one source image identity | `r100/texture/f6e54e3e-1ef21097` | fixtures, vq_native_ui.py, ps2_tree_texture.py, convert_tpl.py |
| `actor` | one character render mesh | `char/actor/em10` | plug-in (low-poly Ganado, Leon rebuild) |
| `pvs` | a room's visibility data | `r101/pvs/room` | plug-in (occlusion/PVS) |
| `audio` | the route's sound banks and streams | `route/audio/banks` | aica_banks.py |
| `movie` | one cutscene | `route/movie/r100s40` | convert_route_movies.py |

The scenery sub-classes (`ground`, `structure`, `clutter`, `landmark`, `tree`) are W9b's
`auto_class`/`--class` tags. The pipeline writes the same tags, so the runtime distance rule
reads them unchanged.

## 3. Inventory: what is measured

For every scenery/tree/house BIN, from the source BIN (`convert_room_bins.parse_bin`) and the
room SMD (`room_smd.Smd`):
- triangles, vertices, parts, strips after stripify, bounds (radius r, extent);
- instances (placements) and their largest scale s;
- the parts' textures, and each part's UV density rho (texels per mm: sqrt of the UV area in
  texels divided by the world area).

From the camera model (section 5), over the room's view set:
- the fraction of views in which the asset is visible;
- its nearest and typical view depth z (clamped to the fog far F);
- its projected area.

For every texture: source size, format, alpha use, padded size, and VRAM bytes per format.
Its screen coverage comes from the parts that use it.

For every actor: vertices, triangles, bones, parts and texture bytes. The engagement ranges come
from `costmodel.toml [actors]`.

## 4. Cost model (the formulas)

All coefficients live in `tools/assetpipe/costmodel.toml`, one commented value each, with where
it came from. `assets.sh calibrate` re-fits them. The shared constants are:
- screen: 640x480, fovy 60 deg, so `K = 240 / tan(30 deg) = 415.7` px per unit of size/depth;
- the 25 m fog far F (`min(room far, 25 m)`);
- `MESH_LOD_PX` P = 3.

### 4.1 Screen-space error and level choice (runtime rule, exact)

A level with world error eps (source mm), in a placement of scale s at nearest depth z, has
screen error `e_px = eps * s * K / z`. The runtime picks the coarsest level whose stored error
satisfies `eps * b * s * K / z <= P`, where b is the BIN's `--lod-bias`. The visible error is
therefore at most `P / b` px.

Every bias option's cost and error can be computed from one base package with the camera model,
without rebuilding anything. This is how the solver evaluates options.

### 4.2 Scenery hardware ms per view

```
scen_ms(v) = base_ms(room)
           + ( c_rec * records + c_strip * strips + c_meshlet * meshlets
             + c_test * box_tests + c_part * parts + c_obj * objects ) / clock
```

- `records` are TA vertex records (strip corners).
- `base_ms(room)` is the room's fixed scenery cost, which no asset option changes.
- The costs of transform-once meshlet vertices and per-part lighting are folded into `c_rec` and
  `c_part` until a log provides pool-vertex counts.

Coefficients (hw ms at 200 MHz):

| Coefficient | Value | Source |
|---|---|---|
| all-in scenery | **1.42 ms per 1k records** | LD r100 hwmodel vs D349 (2.20). The "records only" estimate. |
| marginal `c_rec` | 0.69 ms per 1k records (~138 cycles) | first fit, scenery-trials arms A-G25 (below) |
| per cluster (tests + meshlets + part) | ~0.026 ms (~5.2k cycles) | same fit |
| `base_ms(r100)` | ~12.2 ms | same fit (intercept) |
| strip / meshlet / test / part | 58 / 460 / 120 / 1500 cycles | scenery_model.py (Flycast cycles), used as priors for the split |
| hardware cycles per record | 30-45 | HW-BUDGET.md (prelit transform + submit) |

The arms fit pairs, per arm, the SCEN_LOG means over frames 2401-2520 with that arm's hwmodel
scenery ms:

| Arm | records (tri + 2 strips) | clusters | hw ms |
|---|---|---|---|
| A (42.7 m) | 19,164 | 174 | 29.95 |
| E (px 5) | 15,770 | 174 | 27.62 |
| B (30 m) | 10,242 | 91 | 21.34 |
| D (30 m, px 5) | 7,855 | 91 | 19.66 |
| C (25 m) | 6,980 | 68 | 18.72 |
| G25 (25 m + cull classes) | 6,764 | 63 | 18.49 |
| F (20 m) | 5,378 | 58 | 17.38 |

**Finding.** In r100 at a 25 m fog, the asset-dependent part of scenery is only ~6.5 of 18.7 hw
ms. About 12 ms is a fixed cost that no mesh or LOD choice reaches: the placement walk, per-part
setup, and lighting of drawn parts' vertex pools. The 8 ms scenery budget therefore needs
runtime work too (occlusion/PVS, part merging, cheaper per-part setup), not only lighter assets.
The solver reports this: when `base_ms` alone exceeds a budget, it says so rather than
over-reducing assets. `calibrate` replaces this first fit with a least-squares fit over every
matched evidence dir (section 9).

The all-in 1.42 is kept as a sanity check: `records * 1.42 / 1000` must land within the band of
the structured sum at the calibration views.

### 4.3 Actor hardware ms

```
actor_ms = sum over visible actors of ( c_actor + c_arec * records + c_bone * skinned_bones + c_apart * parts )
```

| Coefficient | Value | Source |
|---|---|---|
| all-in actors | **1.28 ms per 1k records** | hwmodel LD (D349: 2.69) |
| per Ganado, full / tiered | 7.4 / 4.5 hw ms | actors30-v3 (step 3 notes) |
| Leon | <= 5 target, ~5-6 -> ~3 after the fewer-bone rebuild | step 3 |

The worst case is the r101 fight with ACT_CAP active Ganados in view. Mesh levels per distance
tier come from the actor plug-in (section 7): Near 2-3 full, then mid and far tiers. Poses update
every frame for every actor (the user rejected reduced update rates), so a tier changes only
geometry and shading.

### 4.4 Textures

Texture memory in bytes, for padded power-of-two w x h:

| Format | Bytes | Note |
|---|---|---|
| 16-bit twiddled (RGB565 / ARGB1555 / ARGB4444) | `2 w h` | the fixtures' default |
| full-codebook VQ | `2048 + w h / 4` | pinned KOS pvrtex; 1/8 of 16-bit at large sizes |
| PAL4 / PAL8 | `w h / 2` / `w h` (+ palette RAM) | impostor atlases (kPal4, item 20) only |

**Needed resolution** (the "guess from asset sizes" rule). A part with UV density rho (texels
per mm at full size), seen no closer than z_min, shows `K / z_min` screen px per mm. So the
largest magnification is `m = K / (z_min * rho)`:
- If `m < 1/2`, a half-size texture is not visibly different; DC samples without mipmaps, so it
  also aliases less.
- If `m > 2`, the texture is magnified. Those are the `upscale` candidates: the authored source
  size, when the 256-px build limit reduced it.

The recommended scale is `2^floor(log2(min(1, 2m)))`, applied only where the runtime can express
it. A downscale changes the package/source size ratio, and `native_ui.cpp` derives the UV scale
from that ratio. So downscaling repeating textures needs a runtime flag. `[runtime]
tex_downscale = false` keeps it off until one exists. VQ never changes dimensions, so it is
always available.

**Quality loss.** For VQ: `loss = coverage * max(0, (psnr_ref - psnr) / psnr_ref)`, where the
PSNR comes from the encoder report (vq_native_ui.py) and psnr_ref = 48 dB. `coverage` is the
texture's mean screen fraction over the view set. A size change costs
`coverage * max(0, log2(needed / given))`.

**Budgets.**
- VRAM: the room set must fit `pool - resident`. With NATIVE_MES the pool is 2,610,888 B and the
  accounted texture budget 2,545,352 B (2,485.7 KB; 2,578,176 B before NATIVE_MES); resident is
  UI + Leon + weapons + core, measured from run logs. Allocation padding and fragmentation come on
  top of the accounted bytes (161,280 B at r100's peak, m1-final-verifyB).
- Room-entry load time: bytes / 1.5 MB/s (the GDEMU planning rate); reported only.

### 4.5 TA parameter memory (hard limit)

```
ta_bytes(v) = 12 * substrips + B_v * records     (B_v = 20 / 24 / 28 by vertex format)
```

The maximum over views must stay under the vertex bank (2 MiB) minus the adaptive-guard margin
(128 KiB). Sega: an overflowing frame is not drawn.

### 4.6 Heap 4 (bytes)

Sum over the room's resident packages (`.re4mesh`, `.re4pvs`, impostor and shell records):

```
pkg_bytes = 80 + 68 meshes + 36 parts + 28 meshlets + 20 clusters + 12 levels
          + 12 vertices + strip bytes (corners + strips) + 2 * shared indices + 4 * palette
```

rounded to 32-byte sections. Heap 4 couples to the ELF image size (image growth comes straight
out of heap 4), so the budget is per room and per build: `heap4_free_at_entry - margin`. The
prediction is checked against the built file, and a difference over 5% is flagged in the
manifest.

### 4.7 Tree impostors and house shells (discrete options)

**Impostor.** Beyond depth D, a tree is one quad from an N-view atlas: 4 records, 1 strip, ~150
cycles batched. The view quantisation (360/N deg, so an error of at most sin(180/N deg): 0.195 at
16 views, 0.383 at 8) gives an impostor screen error `e_imp = sin(pi/N) * r * K / z`; camera.py
takes N from each atlas. The distance rule is `D = 0.195 * r * K / P_imp` (16 views). `P_imp` =
20 px reproduces the approved 12 m for the r100 trees (r ~ 3 m), so the user's judgement is itself
a fitted coefficient, stored with its provenance. A new judgement re-fits it. Atlas VRAM comes from
the generator report (r100 set: 84 KB at 16 views, 46 KB at 8).

**House shell.** The user decision is the mid mesh with 512 VQ, everywhere, with no near swap:
`[house] policy = "always"`. The cost is the shell's own counts (550-800 triangles) plus 66 KB of
VRAM per house. Modelled: -0.71 hw ms for FILE_01/17+18, ~-1.6 to -1.8 for all of FILE_01.

### 4.8 Quality (what the solver trades)

```
Q(option) = w_class * sum over views of ( e_px(option) - e_px(best) )_+ * area_frac(v)
```

- The error term is the added visible px error; `area_frac` is the asset's projected screen
  fraction in that view.
- Class weights `w_class` are in the config: landmark > structure > tree > ground > clutter.
- Near-enemy views (engagement ranges) count double for the class they occlude.
- Textures use section 4.4's loss.

### 4.9 Budgets and the two modes

The two modes are two looks, not one look with a margin (user, 2026-09-23; names 2026-09-23):

- **Standard (default)** is budget-first: a "Dreamcast-native look" at 30 fps (33 ms hw).
  Its budgets are hard per view, and assets may change the look:
  - houses become baked low-poly shells (the item 21 house-shell generator; see 4.9.1);
  - terrain and structures may use a Blender reduction (planar dissolve + collapse) where its
    measured error is small;
  - trees become impostors beyond a few metres;
  - clutter is culled beyond a distance (never landmarks).
  Only render meshes change. Logic and collision data are untouched, and Standard never uses
  more heap 4 than Original at any allocation. (Earlier notes call this mode "Low".)
- **Original** is source-first: the faithful GC look at 20 fps (50 ms hw), the recipe
  packages (`--plan recipe`), reduced only as far as its budgets require. (Earlier notes call
  this mode "Standard".)

`--mode standard` (default) runs `assetpipe/budget.py`; `--mode original` runs the recipe
build (`pipeline.build_room`). A Standard build also builds Original and prices both from the
same cameras.

| Budget | Original (20 fps) | Standard (30 fps, budget-first) | Statistic |
|---|---|---|---|
| scenery hw ms | 8 | **5, excluding the fixed runtime overhead** (`base_ms`, which is being designed away separately) | Original: p95 over views; Standard: every view |
| scenery triangles per view | none | **15-20k** (hard; 18000 in costmodel.toml) | every view |
| actors | 7 hw ms | **at most 3 full-detail Ganados**; the rest on tiers | r101 fight worst case |
| texture VRAM, room set | pool - resident | same as Original | sum |
| TA parameter bytes | 2 MiB - 128 KiB | same | max over views |
| heap 4 | per room (measured free; ~155 KB margin at r100 s40 / r101) | never more than Original, per room and per file | sum |

Allocation outcomes must not differ between modes, because the logic trace is STRICT across
modes. Every Standard manifest records heap 4 per package (Original, Standard, delta), VRAM
(room textures still drawn, shells, impostor atlases) and the disc bytes of the second set.

#### 4.9.1 The Standard plan (budget.py)

1. Classes: explicit lists in rooms.toml `[room.X.standard]` (houses, landmarks) and the recipe
   trees (`[room.X.trees]` and the W9b `--class ...=tree` lists); otherwise ground (height <= 0.25
   x horizontal extent, >= 10 m wide), then, with the room plan's `houses_auto`, a house candidate
   by size (radius 5-15 m, >= 700 triangles, >= 4 m tall and no taller than wide, at most 2
   placements), then clutter (radius <= 1.5 m) or structure. A room can override any
   `[plan.standard]` key in `[room.X.standard.plan]` (options merge per class).
2. Houses: `house.shell` steps (Blender bl_house_shell.py + house_shells.py, cached by hash) on
   the ladder `house_faces`; the first rung whose p90 source-to-shell error is <= `house_err_cm`
   is used. r100: 48, 96 and 200 faces break the houses (p90 1.2-3.7 m); 400 faces pass (21 and
   26 cm), the same count as the approved low512 shells. The review shows the rejected rungs.
   A size-picked candidate that no rung fits is not shelled: it goes back to structure and the
   manifest lists it (`shell_rejected_p90_cm`). A candidate with no opaque triangle (every part
   alpha-masked, flag 4: bl_house_shell.py shells the opaque surface only) is not baked at all and
   is listed in `shell_skipped` (r103 BIN 1: 800 alpha-masked triangles). A bake that fails is an
   error: Blender runs with `--python-exit-code 1`, so a script exception fails the step with
   Blender's log instead of a missing output file.
3. Options per class (`[plan.standard.options]`): extra LOD bias, tree impostor centre depth
   (item 20 records), clutter cull centre depth; plus, for ground/structure, the same options on
   a Blender reduction (`scenery.decimate`, bl_decimate.py) whose p90 error is <= `max_p90_mm`
   and whose worst source-to-reduction distance is <= `max_mm` and <= `max_rel` (0.1) x the
   BIN's radius. That reduction's error is the
   option's error floor in the quality term. Standard packages use a coarser LOD chain of the
   same depth (`lod_args`); an owner whose package would grow is rebuilt with the recipe chain.
4. Pricing at runtime LOD px 5 over the ground grid plus the named views (`[room.X.views]`:
   `cam`/`toward` (SCEN_LOG frames), `player`/`angle` (an AEV door arrival: the camera just
   behind the head), `eye`/`yaw` (fixed cameras such as W9's model views), `eye_xz`/`at_xz`
   (standing on the ground looking at a point), `bin` (house approach at given distances), and
   `grid = "max_original_ms"`).
5. Lazy-greedy multiple-choice solver (`budget.solve`): moves ranked by reduction of summed
   relative excess over all views per unit of weighted quality loss, deterministic ties, then
   an upgrade pass. Views still over budget are reported, never hidden.
6. Final packages bake recipe bias x chosen bias per BIN; the staged set is priced again and
   those numbers are the ones reported (the solver's differ by at most ~0.5 ms).
   **Vanish guard.** An empty LOD level (no meshlets) is where an object stops drawing, and its
   stored error sets that distance (`err x scale x K / zmin <= px`). A baked bias scales it
   down with the other levels, and Standard's px 5 moves it nearer again, so r103's fence panels
   vanished at 1.8 m instead of 18 m. Every Standard package therefore gets its empty-level
   errors raised to at least Original's x px_std / px_orig (`scenery.vanish_guard`, only those
   floats change), and pricing uses the same rule (`vanish_min`), with the part's size as the
   quality error of a vanished part. No object vanishes nearer than in Original.
   `plan.json` carries the runtime choices (impostor/cull distances, geometry variant).
7. Review: `review/standard/<room>/index.html` renders both modes from identical cameras with
   the textured software renderer (`render.py`, `scene.py`: TPL textures, PS2 bark, baked shell
   textures, impostor atlas cells, PVR-style modulate, punch-through alpha, 25 m fog), with
   per-view asset ms, triangles, and a frame estimate = `frame_rest_ms` (design-lowmode D2 floor
   28.3) + `base_ms_planned` (2.5) + assets, against 33.3 ms.

Results (2026-09-23, scenery assets in hw ms excluding base, cost model as calibrated on r100;
no r101/r103 hwproject evidence exists yet, W8g is the first; r101 Original at W9's cameras is
within 0.3 ms of W9's model rows, so no re-fit was needed):

| Room | Standard named views | Standard grid p95 / max | views within 5 ms | Original grid p95 / max | heap 4 Std - Orig | VRAM Std - Orig |
|---|---|---|---|---|---|---|
| r100 | 5.7-10.7 | 7.37 / 10.7 | 155 / 215 | 17.6 / 24.9 | -294 KB | +14 KB (2 shells at 128: 12, 8-view atlases 46, dropped room textures -44) |
| r101 | 4.0-11.5 | 10.27 / 12.6 | 127 / 263 | 25.2 / 27.5 | -413 KB | +81 KB (9 shells at 64: 27, 8-view atlases 26, 9 tree atlases 62, dropped room textures -34) |
| r103 | 4.5-9.7 | 8.27 / 9.85 | 162 / 270 | 25.8 / 38.5 | -397 KB | +160 KB (3 shells at 256: 54, atlases 46, 13 tree atlases 82) |

r100's numbers include the vanish guard (before it: 7.34 / 10.6, 158 views). User decisions
(2026-09-23), applied: r100's two shells use 128 x 128 textures like r101 (was 512 VQ: +170 KB VRAM;
the hw ms are unchanged); r101 BIN 45 (the house with the well in the village square, fight area)
is a landmark, so real mesh at bias 1 instead of a 400-face shell: +0.49 ms grid p95 (10.3 -> 10.8),
+0.6 ms grid max, +0.4 ms in the fight view, +29 KB heap 4, -6 KB VRAM. Every Standard package is
no larger than Original's. The second set on disc is every Original package (1.51 / 1.01 / 1.13 MB)
while biases are baked; section 15 weighs a runtime per-BIN table. Remaining cost: tree groves
(one BIN, one centre: r101 17, r103 38/59, 2-3 ms when standing in them; splitting groves into single
trees is the next lever), single large ground meshes (~1 ms at every view), the shells.
Grove split (user option B, 2026-09-23; section 16.5), applied to r101/r103: the converter found
r101 BINs 13 (2 trees) and 17 (7), r103 BINs 38 (6) and 63 (7 small trees, ~3 m); the solver
chose per-tree impostors at 3 m for all four. Against the rows before it (extra clusters priced
at 5.2k cycles each): r101 grid p95 10.80 -> 10.27, max 14.45 -> 12.58, named max 12.41 -> 11.49,
spawn 3.97, views within 5 ms 117 -> 127, heap 4 -2 KB more saved, VRAM +26 KB; r103 grid p95
8.48 -> 8.50, max 13.31 -> 11.85, named max 10.46 -> 10.19, views within 5 ms 151 -> 157, heap 4
+26 KB (the split package is larger), VRAM +46 KB. r103 BIN 59 (camera inside one tree's canopy)
is split into regions (16.6, user option B): r103 grid p95 8.50 -> 8.27, max 11.85 -> 9.85, named
max 10.19 -> 9.70, cow_pen 10.19 -> 8.46, house_20m 9.42 -> 7.91, views within 5 ms 157 -> 162;
heap 4 +5.5 KB, VRAM 0.
VRAM trims (user, 2026-09-23), texture only, so the modelled hw ms are unchanged (grid p95 / max
and named max as above in all three rooms): r101's whole-BIN tree atlases (BINs 14/15/16) at 8
views instead of 16 (-20,480 B) and its 9 shell textures at 64 x 64 instead of 128 (-27,648 B);
r100's 5 PS2-tree atlases re-baked at 8 views (`tree.bake`: item 20's Blender bake, --threads 1;
-36,864 B, 84,128 -> 47,264 B).

Against the route budgets (review sheets, "Against the route memory budgets"):
- r101 heap 4: ~1.46 MB free at entry in Original (design-r103 estimate) -> ~1.87 MB in Standard.
- r103 heap 4: with W8b compaction 1.10-1.55 MB -> 1.53-1.98 MB; without W8b -0.35..-0.20 MB ->
  +0.08..+0.23 MB. Standard fits without W8b, but below the 155 KB margin at the low end and below
  W8d's 330 KB gate, so W8b is still needed.
- VRAM, against the accounted budget of 2,485.7 KB (2,545,352 B, NATIVE_MES) and, as an estimate,
  the physical pool (2,610,888 B less r100's measured 161,280 B of padding/fragmentation):
  - r100: Original peaks at 2,430,976 B accounted with 18,632 B of the pool free
    (m1-final-verifyB). Standard adds 14,496 B (2 shells + 5 atlases - 5 room textures no longer
    drawn; +51,360 B with 16-view atlases): 2,445,472 B, 99,880 B under the budget, ~4.0 KB of the
    pool free.
  - r101: Original 2,371 KB measured; Standard adds 83,328 B (131,456 B before the trims):
    ~2,452.4 KB, ~33.3 KB under the budget; with r100's padding the pool would be ~60 KB short
    (evictions and re-reads, not missing textures). Only an r101 run can measure its padding.
  - r103 (estimate: r101's non-room use + r103 room textures): ~2,193 KB -> ~2,354 KB, ~132 KB
    under the budget, ~38 KB of the pool free with r100's padding.
  - Levers not taken: r101 BIN 13's wide cells at 64 x 64 (-12 KB), BIN 17's cells at 32 x 64
    (-21 KB), 256 shells would add ~12 KB each.

## 5. Camera model and view set

This is the scenery30/W9 model (`scenery_model.py`, `room_model.py`), moved into
`assetpipe/camera.py` and generalised:
- Placements come from the room SMD; r100 also uses its owner files and common SMD.
- Views are a ground grid over the placement area: N x N points, 8 yaws, eye 1.6 m.
- Route camera tracks come from SCEN_LOG evidence (the `cam=`/`pl=` fields) when a room has
  them.
- Engagement views add an enemy at 3, 8 and 20 m.

Per view it emulates the object sphere test against the fog far, then per part the cluster box
test, the level choice (4.1) and the meshlet tests. It accumulates counts per (asset, option).
One pass therefore prices every bias option for every asset.

## 6. Solver

Each asset has an ordered list of options (best quality first), for example:
- scenery: bias {1, 0.75, 0.5, 0.375, 0.25} x floor {0, 2 mm};
- tree: {GC, PS2} x impostor D {off, 20, 15, 12, 10 m};
- house: {source, shell};
- texture: {16-bit, VQ, half, authored size};
- actor: the plug-in's levels.

Each option carries a per-view cost vector and its quality loss Q.

1. Start every asset at its best-quality option, with pins applied (section 8).
2. While a budget is violated, take the option step with the largest
   `sum over violated budgets d of (delta cost_d / budget_d) / (delta Q + 1e-6)`.
   View-statistic budgets (p95) are re-evaluated on the summed per-view vectors, not by adding
   p95s. Ties break by asset id.
3. Upgrade pass: while slack remains, undo the steps with the best `delta Q / delta cost` that
   keep every budget.
4. If the budgets cannot be met, emit the least-cost plan and mark the room `INFEASIBLE`, naming
   the binding budget and the fixed part (for example `base_ms`).

The solver is deterministic: sorted iteration and no randomness. Every decision records the
formula and the numbers that decided it (`decided_by`).

## 7. Generators and plug-ins

A generator turns (asset, option, inputs) into files. Built-in generators wrap the existing
tools unchanged:

| Generator | Tool | Output | Staged as |
|---|---|---|---|
| `scenery.r4im` | convert_room_bins.py (`--smd` or `--bins`, `--lod*`, `--lod-substitute`, and W9b's `--lod-floor/--lod-share/--class*` when the converter has them) | `<OWNER>.re4mesh` | r100: `MESHDIR`; others: `MESHROOMS` |
| `tree.ps2` | ps2_trees.py (`--room`, `--dc-uv`) + ps2_tree_texture.py | replacement OBJs, bark `.re4tex` | via `--lod-substitute`; bark via `TEXDIRS` |
| `tree.bake` | r100 (plan `impostors`): item 20's Blender bake of the PS2 tree models (vendored bl_impostor_bake.py, Blender --threads 1) encoded by tree_impostors.py; one atlas per PS2 model | `bake/`, atlases `.re4tex`, `impostors.json` records | `TEXDIRS` |
| `tree.impostor` | r100 without a plan `impostors`: the pinned item 20 bake (sources.toml `r100_impostors`, 16 views). Other rooms: `assetpipe/impostor.py` (pure Python, render.py; kPal4 packaging from the vendored tree_impostors.py) | atlases `.re4tex`, `impostors.json` records (+ `rgb`) | `TEXDIRS` |
| `texture.room_tpl` | SMD rooms: TPL 0 of the SMD's TPL table (every r101/r103 placement uses it) | `<room>.tpl` | review textures, VRAM |
| `scenery.bin_obj` | export_room_bins_obj.py (`--export` for r100, `--smd <das>` for SMD rooms) | `<OWNER>_<bin>.obj` | shells, decimation |
| `scenery.vanish_guard` | generators.vanish_guard (4.9.1 step 6) | package with empty-level errors raised | as the package |
| `house.shell` | bl_house_shell.py + house_shells.py (item 21; the checkout's copy when present, else the sha256-checked copies in `assetpipe/vendor/`) + mesh_annotate.py | shell OBJs, 512 VQ `.re4tex`, annotated package | `--lod-substitute`, `TEXDIRS` |
| `blender.planar` | bl_decimate.py (r100-planar2 spec; Standard's `scenery.decimate` coarse variant) | replacement OBJs | `--lod-substitute` |
| `texture.vq` | vq_native_ui.py (pinned pvrtex) | `.re4tex` overlay | `TEXDIRS` |
| `room.release` | room_smd.py release | released `.dar`/`.arc` | `ROOMFILES` |
| `audio.aica` | aica_banks.py build/streams (cached) | overlay | stage.sh `AICA_CACHE` (same cache) |
| `movie.fmv` | convert_route_movies.py | `.seq` per event | cutscene staging (`movies-288x192-full`) |
| `ui.native` | prepare_native_ui.py | fixture `.re4tex` set | fixtures (`FIXTURES_SRC`) |

### Plug-in interface (for pending generators)

A plug-in is either a Python module in `tools/assetpipe/plugins/` or an external command
declared in `assetpipe/plugins.toml` (so it can use its own venv, for example numpy). Either
way, it answers two calls with JSON files in a work directory the pipeline owns.

**`describe`** (cheap, no build). The pipeline writes `request.json`:

```json
{"call": "describe", "plugin": "ganado_lowpoly", "api": 1, "asset": "char/actor/em10",
 "room": "r101", "mode": "standard",
 "inputs": {"model": {"path": "...", "sha256": "..."}},
 "params": {}, "costmodel": {"...": "the resolved costmodel.toml tables"},
 "work": "/root/probe/d367-agents/assets/cache/work/<key>"}
```

The plug-in writes `describe.json`, listing its options best-quality first:

```json
{"api": 1, "deterministic": true, "tool_version": "g_simplify 3 / numpy 2.1.1",
 "options": [
   {"id": "L0", "params": {"level": 0},
    "cost": {"records": 5120, "strips": 610, "parts": 14, "meshlets": 31, "tris": 4200,
             "verts": 2900, "bones": 38, "vram_bytes": 65536, "heap4_bytes": 88000,
             "disc_bytes": 90000, "hw_ms": null},
    "quality": {"e_px_at": {"3": 0.0, "8": 0.0, "20": 0.0}, "metric": "silhouette px"},
    "tiers": {"near_m": 6, "mid_m": 14}}
 ]}
```

**`build`**. The request also carries `"option": "L1"` and `"out": "<dir>"`. The plug-in writes
its files into `out` and a `result.json`:

```json
{"api": 1, "outputs": [{"path": "em10.re4act", "kind": "actor-mesh",
                        "stage": {"var": "NATIVEFILES", "dest": "char/em10.re4act"}}],
 "cost": {"...": "same fields as describe, now measured on the built file"},
 "inputs_used": {"model": "sha256"}, "deterministic": true}
```

Cost-report fields: `records, strips, parts, meshlets, tris, verts, bones, vram_bytes,
heap4_bytes, disc_bytes` (plus `corners` for actors: design-ganado measures tiered parts at ~0.86 hw
ms per 1k records + ~0.08 per 1k corners, against 1.28 per 1k records for fully lit near parts). `hw_ms` may be null; the pipeline then computes it with its
coefficients. Plug-in-specific extras go under `extra`.

The contract:
- The same request gives byte-identical outputs.
- No timestamps and no absolute paths in outputs.
- Seeds are fixed.
- The plug-in reads only the files it is given.
- `deterministic: false` is allowed only for opt-in AI steps (section 10).

The pipeline hashes `request.json` (inputs by content, not by path) plus the plug-in's version
string and code hash, and skips the call when that key is cached.

Pending plug-ins and their stage kinds:

| Plug-in | Design agent | Asset / output | Standard mode |
|---|---|---|---|
| `ganado_lowpoly` | design-ganado (a75b5dc9f0fe43a05) | `actor`: 4 nested levels (L0-L3) per em model, 3 tiers (near <= 7 m or the nearest 3, mid <= 17 m, far); output one archive per enemy type, `em/em12.drs` and `em/em15.drs` | the same in both modes (user decision): L1 / L2 / L2 |
| `pvs` | design-scenery (a5dd25741b47eff9d) | `pvs`: `r<room>.re4pvs` (R4PV v1) from room .das + MAINSCENARIO package + classes | conservative in Original, aggressive in Standard |
| `lowmode_sets` | design-lowmode (af92085074ca55b28) | the Standard (ex-Low) set's runtime layout | defines the `--mode standard` staging layout |

### Original and Standard staging

Both modes are built from the same inventory with different budgets and option sets. The disc
paths keep design-lowmode's names (`low/`, `texlow/`), which predate the renaming.

- Original outputs stage as today (`/cd/dc/native/<room>/`, `/cd/dc/tex/<d>/`).
- Standard outputs that differ from Original stage under `/cd/dc/native/<room>/low/` and
  `/cd/dc/texlow/[<d>/]<key>.re4tex` (QUALITY=1 builds only; section 16 is the runtime contract).
- Each room's Standard set carries one index, `native/<room>/low/index.txt`: the Standard files,
  the added texture keys, the dropped room texture keys and the per-mesh impostor / cull / shell
  texture records (there is no separate `texlow/index.txt`). The runtime reads it once at room
  entry and opens only the listed Standard files, otherwise the Original path. There are no
  probe-opens: a failed iso9660 lookup re-reads the directory from the disc, which caused the
  ~0.2 s texture hitch.
- Actor meshes are per enemy type, not per room, and are the same in both modes (user
  decision): one prepared archive per enemy type, `em/em12.drs` and `em/em15.drs`, with levels
  L1 near / L2 mid / L2 far as pre-converted v4 blobs. They stage as mirror files
  (`ROOMFILES`-style), with no Standard variant and no Standard index. design-ganado owns the format:
  per-BIN v4 blobs with nested levels over the source vertex arrays, carrying a converter-hash
  check. That converter hash is part of the plug-in's cache key.
- A Standard file is never larger than the Original file it replaces.

design-lowmode confirmed this layout (DESIGN.md A5).

## 8. Overrides (testing)

`--override FILE` (TOML; repeatable, later files win) pins assets or classes:

```toml
[[pin]]
match = "r100/house/*"          # glob on asset ids; or: class = "texture"
action = "reset"                # original source: no reduction, source texture, GC mesh

[[pin]]
match = "r100/texture/f6e54e3e-1ef21097"
action = "upscale"              # authored source size / 16-bit instead of VQ / bias 1

[[pin]]
match = "r101/scenery/0xff:12"
action = "params"
params = { lod_bias = 0.5, lod_floor = 0 }

[[pin]]
class = "tree"
room = "r103"
action = "auto"                 # back to the solver
```

Actions:

| Action | Meaning |
|---|---|
| `auto` | The solver decides (default). |
| `reset` | The unreduced source: source mesh, levels at bias 1, no floor, source texture as packaged in the fixtures, no impostor or shell. |
| `upscale` | One quality step above the solver's pick, capped at the source's authored detail: a larger VQ, 16-bit, or authored size; for meshes, bias 1 and no floor. |
| `upscale:source` | Straight to the best source-derived option. |
| `ai-upscale` | Opt-in, non-deterministic step (section 10). |
| `params` | Explicit generator parameters, validated against the option schema. |

Rules:
- Precedence: exact id > glob > class; later rules win within a level.
- A pinned asset keeps its option, and the solver re-balances the rest to stay within budget. If
  it can't, the room is marked `INFEASIBLE-PINNED` and still builds.
- Rebuild only what changed: an override only changes the cache keys of the steps it touches,
  and every other step is a cache hit.
- `assets.sh plan` prints the diff against the previous build before anything runs.

## 9. Calibration

`assets.sh calibrate [--set assetpipe/calibration.toml]` fits the coefficients. Each set entry
names:
- an hwmodel projection dir (`proj/rep/areas.tsv`);
- the matching Flycast evidence dir with SCEN_LOG lines (frames and camera);
- the package directory, fog far and px that build used.

For every frame of the window, it replays the camera model at the logged camera position,
looking at the logged player position plus 1.2 m, and gets the structured counts. It checks them
against the logged counts (`tri`, `st`, `cl`) and flags any view mismatch over 10%. It then fits
`hw_ms = base + sum c_i * count_i` per area:
- non-negative least squares;
- priors from the current config as ridge terms, so a small set cannot swing a coefficient
  wildly;
- leave-one-out residuals reported.

It writes `costmodel.fit.toml` and a diff against `costmodel.toml`. A human copies it in, and the
fit is never applied silently.

- Scenery sets: `hwmodel-scen-{A,B,C,D,E,F,G25}` + `scen-tour-*`.
- Actor sets: `hwmodel-actors30-{lfull,lcrowd,sfull}-n{1,4,8}`, fitting per-actor and per-record
  terms.

It needs at most 1-2 Flycast runs, and only to add a calibration point.

## 10. Determinism and cache

Hard goal: the same inputs, config and overrides give byte-identical outputs and an identical
manifest hash.

**Cache.** A step's key is sha256 over:
- the step name and api version;
- the canonical JSON of its parameters (sorted keys, no floats printed with repr noise:
  `%.9g`);
- the sha256 of every input file (content, never path or mtime);
- the tool fingerprint: the sha256 of the generator scripts it runs plus the version strings of
  pinned binaries.

Outputs live in `cache/objects/<key>/`, written to a temporary dir and renamed on success. An
unchanged key is a hit and skips the work.

**Pins.**
- Python 3.12.3, stdlib only (no numpy in built-in steps).
- KOS pvrtex by sha256 (`kos-re4dc-d336/utils/pvrtex/pvrtex`).
- Blender 5.2, `--factory-startup`, version string checked.
- ffmpeg by `-version` line, run with `-threads 1`.
- A mismatch stops the step.

**Stable ordering.** Assets, placements and options are sorted. JSON is written with
`sort_keys`, and dicts are iterated in sorted order. Nothing depends on filesystem order.
Nothing stochastic runs without a fixed seed (`seed = sha256(asset id)[:8]`): VQ codebook
training is pvrtex's deterministic k-means, and QEM and card thinning are already
deterministic.

**No timestamps or absolute paths.** Outputs and manifests contain neither. Tool JSON sidecars
that embed input paths get the private root replaced by `$ROOT` before hashing.

**`--verify`.** It rebuilds every step with the cache bypassed and compares the hashes and the
manifest hash.

| Step | Deterministic | Note |
|---|---|---|
| inventory, camera model, solver, manifests | yes | pure Python |
| convert_room_bins (LOD, share, floor, class) | yes | the tracked tests pin hashes (COMMON `cdeade63...`) |
| ps2_trees, ps2_tree_texture, vq_native_ui (pvrtex) | yes | bark `5b403509...` |
| aica_banks | yes | already content-cached |
| room_smd release, prepare_native_ui, convert_tpl | yes | |
| Blender steps (planar decimation, house shell bake) | yes with pins (measured) | run as `blender -b --threads 1 --factory-startup --python-exit-code 1` (a script exception fails the step); fixed seeds and sample counts in the scripts; inputs sorted. Without `--threads 1` the same shell came out with the same metrics but a different vertex order (and so different OBJ/PNG/JSON bytes) than with a different thread count, so a machine with another core count would not reproduce it. `blender_threads` is part of the fingerprint. |
| impostor bake (item 20, `tree.bake`) | yes with pins (measured) | Blender Workbench, `--threads 1`, flat light, inputs from the cached ps2_trees / ps2_bark steps; at 16 views it reproduces the pinned bake (`r100_impostors`) byte for byte (PNGs, `.re4tex`, `impostors.json`) |
| impostor.py (other rooms), vanish guard | yes (measured) | pure Python + pinned pvrtex; verified in the r101/r103 `--verify` runs |
| convert_route_movies (ffmpeg) | yes with pins | `-threads 1`, pinned version |
| review renders | yes | pure-Python rasteriser |
| **ai-upscale** (ComfyUI + PBRify, local, port 7860) | **no** | opt-in only |

Measured (2026-09-23, r101 / r103 Standard, run concurrently): 263 and 132 steps byte-identical,
including their Blender shells and decimations, impostor atlases and guarded packages.

Measured (2026-09-23, r100, `--jobs 12`): `build r100 --verify` rebuilds every cached step and
compares output hashes. Standard: 142 of 142 steps byte-identical, including the 8 house-shell
rungs, the 600-face shells and `decimate coarse (95 BINs)` (Blender, `--threads 1`), the PS2
trees and bark, and every package. Original: 798 of 798 (18 build steps plus 780 review
renders). The two modes also verify byte-identically when run at the same time (each `--verify`
rebuilds into its own `cache/verify/p<pid>/`).

Two causes of non-reproduction were found and fixed:
- Blender's default thread count (above).
- convert_room_bins records its `--lod-substitute` paths in `.re4mesh.json`, and those paths
  contained other steps' cache keys. A tool change re-keyed those steps without changing their
  bytes, and the package JSON still changed. Substitute dirs are now linked into the step's
  `$WORK/subst<i>` and passed from there, so only content reaches the output.

`ai-upscale` is opt-in: an override action, never picked by the solver. Its output is stored as a
**pinned artifact** (`cache/pinned/<asset>/<sha256>`) keyed by the source image hash and the
workflow/model hashes. From then on it is an ordinary input identified by its content hash, so
every later step stays deterministic and `--verify` does not re-run it. `assets.sh pin-ai
<asset>` regenerates it deliberately.

## 11. Manifest

`out/<mode>/<room>/manifest.json` (sorted keys, no timestamps):

```json
{"schema": "re4dc-assets/1", "room": "r100", "mode": "standard",
 "config_sha256": "...", "overrides_sha256": "...", "tools": {"convert_room_bins.py": "sha256"},
 "budgets": {"scenery_ms_p95": 8.0}, "predicted": {"scenery_ms_p95": 7.6, "scenery_ms_max": 9.1,
             "base_ms": 12.2, "vram_bytes": 0, "heap4_bytes": 0, "ta_bytes_max": 0},
 "status": "OK|INFEASIBLE|INFEASIBLE-PINNED",
 "assets": [{"id": "r100/house/1:17", "class": "house", "option": "shell512",
             "decided_by": "override:pins.toml#3 | formula:house.policy=always | solver:ratio=...",
             "params": {}, "inputs": {"bin": "sha256"},
             "outputs": {"FILE_01.re4mesh": "sha256"},
             "predicted": {"hw_ms_mean": 0.21, "hw_ms_p95": 0.40, "vram": 67584, "heap4": 0},
             "counts": {"tris": 550, "records": 1100}}],
 "stage": {"MESHDIR": "...", "TEXDIRS": "...", "MESHROOMS": "...", "ROOMFILES": "..."},
 "manifest_sha256": "sha256 of this object without this field"}
```

## 12. Review sheet

`review/<mode>/<room>/index.html`: one row per asset, sorted by predicted hw ms saved, with:
- before (source) and after (chosen option) at 3, 8 and 20 m, true screen size plus a 2x crop,
  rendered by the deterministic rasteriser at the runtime's level choice;
- tris, records, bytes, VRAM, heap and predicted hw ms before and after;
- `decided_by`;
- for textures, source and encoded images with PSNR.

Room totals against budgets are at the top. The user judges from this page. A judgement ("this
is too coarse") becomes an override, or a re-fit of the quality coefficient (`P_imp`, class
weights).

## 13. Staging

`out/<mode>/<room>/stage.env` holds `MESHDIR`, `MESHROOMS`, `TEXDIRS`, `ROOMFILES`, `KEYED` and
`NATIVEFILES`, pointing at hard-linked views of cached objects. `stage.sh` reads it with
`ASSETS=<out/<mode>/<route>>`. Explicit environment variables still win.
- `TEXDIRS` order is: fixtures VQ overlay, then generated textures, then per-asset pins.
- `assets.sh stage-env route` merges the three rooms.
- A Standard build also writes `STDROOMS` (`<room>=out/standard/<room>`) and lays out
  `out/standard/<room>/low/` + `texlow/`, the room's Standard disc files (section 16). A
  `QUALITY=1` build stages both sets:
  `ASSETS=out/original/<route> STD_ASSETS=out/standard/<route> stage.sh <build> <disc>`
  (`STD_ASSETS` contributes only `STDROOMS`). `stage_std.py` checks each index against its files
  and the staged Original packages (`orig` records), copies the set, prints a size report per
  room and adds a `STDROOM` line per room to `stage-inputs.txt`. Builds without `QUALITY=1`
  ignore `STDROOMS`: the disc's file tree is identical with and without it (checked
  2026-09-23 on a staged route disc, 1,509 files; `disc.bin` itself differs run to run by
  genisoimage timestamps).

## 14. Delivery steps

| Step | Content | Status |
|---|---|---|
| a | this design | done |
| b | tool skeleton, cache, r100 wired to the existing generators, review sheet | done: `build r100 --plan recipe` reproduces the LFV r100 inputs byte for byte; `--verify` passes |
| b2 | Standard (budget-first) prototype for r100: classes, shells, coarse variants, impostor/cull options, solver, textured Standard vs Original review | done (prototype; 4.9.1) |
| c | solver (`--plan solve` for Original) + `calibrate` | solver done in budget.py; calibrate open |
| d | r101, r103 (Standard, built together: user decision 2026-09-23) | done: Original reproduces W9 FIN byte for byte; Standard with auto-picked shells, impostor.py atlases, vanish guard; `--verify` byte-identical (r101 263 steps, r103 132); review sheets with the heap 4 / VRAM budget tables. Calibration waits for W8g hwproject evidence |
| e | overrides + upscale (source) + opt-in ai-upscale | |
| g | Standard disc side (section 16): `stdindex.py` index + `low/`/`texlow/` layout, `stage_std.py`, `STDROOMS` in `stage.sh` | done: route disc with `QUALITY=1` adds exactly the 44 Standard files (r100 +1.31 MB, r101 +0.74 MB, r103 +0.85 MB) |
| f | `assets.sh audit <room>`: bring-up gaps (missing-module stubs, missing packages, events without PS2 FMV, unported systems, heap/image estimate), seeded from R4_FIRST_STAGE_GAP_AUDIT.md and the next-room dependency brief | |

## 15. Design note: runtime per-BIN mode table (not built)

**Problem.** Standard bakes its per-BIN choices (bias x recipe bias, LOD chain) into the
package, so every r100 package differs from Original's. The second set on disc is 1.51 MB for
r100; only FILE_01 (the shelled houses) and the coarse-variant owners differ in geometry.

**Proposal.** One package per owner for both modes, plus a small per-mesh table the runtime
applies for the active mode.
- **Where:** LOD header word 7 (unused today) holds the offset of an `R4MT` block appended to
  the package. The block has a count and 2 modes x n meshes x 8 bytes.
- **Entry (8 B):**
  - u8 bias code: bias = 2^(-v/8), with 0 meaning 1.0;
  - u8 max level (0xFF = the chain's own);
  - u16 impostor centre depth / 64 mm (0 = the room default, `RE4DC_TREE_IMPOSTOR_MM`);
  - u16 cull centre depth / 64 mm (0 = never);
  - u16 reserved (0).
- **Original** is the identity table; a package without a table behaves as today.

**Costs.**
- **Disc and heap:** r100 has 130 meshes across its 7 packages, so the table is 2 x 130 x 8 =
  ~2 KB. Only the active mode's half needs to stay resident (~1 KB of heap 4 per room;
  r103, with ~2x the scenery, ~2 KB), against
  1.51 MB of disc saved.
- **hw ms:** ~0. The mode is fixed at `titleExit`, so package load folds the table into each
  mesh's effective `px` threshold and distances once. The per-frame rule is unchanged (a
  precomputed per-mesh `px_eff` in place of the global `px`). The worst case is a per-part
  multiply if it has to live in the draw loop: ~200 parts x ~1.5 cycles, ~0.0015 ms.

**Feeding it from plan.json.**
- `plan.json` (`re4dc-standard-plan/1`) already lists the runtime choices per BIN (`class`,
  `imp_mm`, `cull_mm`, `geom`).
- It would gain `bias` and `max_level` per BIN, and the final-package step would stop baking the
  bias and pass the table instead: a converter flag `--mode-table plan.json` or a
  `mesh_annotate.py --mode-table` pass on the recipe package.
- The runtime reads per-mesh values in place of `RE4DC_TREE_IMPOSTOR_MM` and the W9b class
  distance rules.

**What it cannot do.** Geometry swaps still need a per-mode package or in-package alternates:
- house shells;
- the Blender coarse variants;
- Standard's coarser LOD chain.
Alternates cost heap in both modes, and heap is what Original lacks.

**Measured trade (r100, a shared-package build in which only FILE_01 differs).**

| | Shared-package build | Current Standard |
|---|---|---|
| Asset hw ms, grid p95 / max | 10.30 / 14.26 | 7.34 / 10.6 |
| Named views | 8.2-14.3 | 5.7-10.7 |
| Heap 4 vs Original | -50 KB (FILE_01 only) | -302 KB |
| Second set on disc | ~0.41 MB (FILE_01 only) | 1.51 MB |

The shared build loses ~3-3.7 ms at the worst views and ~250 KB of heap savings.

**Recommendation.** Keep two package sets.
- Disc is cheap: at ~1.5 MB x 85 rooms, the second sets are ~130 MB of a ~1 GB GD-ROM.
- Heap and hw ms are what is scarce.

Build the table only if the disc gets tight. If it is built, make it an addition rather than a
replacement: the table carries bias, impostor and cull, and the per-mode packages remain for
geometry.

## 16. Standard assets on disc: runtime contract

This section is for the game-side builder of Standard mode (`QUALITY=1`). It defines what
`stage.sh` puts on the disc for Standard, and what the runtime must do with it. The Original set
stays exactly as it is today. The generator is `tools/assetpipe/stdindex.py`, called from
`budget.py` at the end of a Standard build. Staging is `tools/d367/stage_std.py`, which
`stage.sh` calls.

### 16.1 Paths

| Disc path | What | Staged when |
|---|---|---|
| `/cd/dc/native/<room>/<OWNER>.re4mesh` | Original packages (unchanged) | always |
| `/cd/dc/native/<room>/low/index.txt` | the room's Standard index (16.3) | `QUALITY=1` build and `STDROOMS` given |
| `/cd/dc/native/<room>/low/<OWNER>.re4mesh` | Standard package for OWNER; only owners whose Standard bytes differ from Original | same |
| `/cd/dc/native/<room>/low/plan.json` | `re4dc-standard-plan/1`: for tools and evidence only; the runtime never reads it | same |
| `/cd/dc/texlow/<crc>-<fnv>.re4tex` | textures that Standard adds (house shells, impostor atlases) | same |

- `<room>` is `r%x%02x`, as in the Original path.
- OWNER is `MAINSCENARIO`, `FILE_%02u` or `COMMON`, named as in `native_static.cpp`.
- In `TEX_RESIDENT=1` builds, `texlow/` is fanned out exactly like `tex/`:
  `/cd/dc/texlow/<first hex digit>/<crc>-<fnv>.re4tex`. The runtime can use the same path
  formatter with `texlow` in place of `tex`.
- Rooms in the current set: r100, r101, r103.

### 16.2 Mode rules and residency

The mode is frozen at `titleExit` (`re4dc_quality()`), so each room entry sees exactly one mode.

**Original mode (and every `QUALITY=0` build).**
- Never read `low/index.txt`.
- Never open `low/` or `texlow/`.
- Behaviour and residency are as today.

**Standard mode.** At room entry, before the first package open:

1. Read `native/<room>/low/index.txt` once, then parse it into fixed tables (16.4).
   - A missing index means the room has no Standard set: open the Original packages and log it.
     `lod_px` stays 5, which is today's `QUALITY=1` behaviour.
   - Reject the whole index if it has a bad first line, a missing or wrong `end` count, a room
     that is not this room, or a record that fails its check (16.3). A rejected index is treated
     as missing. Never probe-open files: a failed iso9660 lookup re-reads the directory.
2. Open packages as follows:
   - **Owner with a `mesh` record:** open `native/<room>/low/<OWNER>.re4mesh`. The Original file
     for that owner is not opened. Heap 4 still holds one package per owner, as today.
   - **Owner without a `mesh` record:** open the Original path. The Standard set uses those
     bytes unchanged (an `orig` record lists them).
3. Textures:
   - **Key with a `tex` record:** open it from `texlow/`. These keys never exist in `tex/`, and
     Standard replaces no Original key.
   - **`TEX_RESIDENT` room-entry preload:** after the room-identity pass, add the `tex` keys.
     Their width, height and VRAM bytes are in the record. In the room-identity pass
     (`preload_select(room_identities, ...)` only), skip every key with a `drop` record.
   - A dropped key that is drawn anyway still loads on first sight, so a dropped key costs a
     hitch, never a missing texture. The enemy, player and weapon passes are unchanged.
4. **Per-mesh records** (`cull`, `imp`, `ptex`) are looked up by the mesh or part index in the
   package that was opened for the owner. They apply only to that package.

**Residency, file by file, in Standard mode.**

| File | Resident in Standard | Resident in Original |
|---|---|---|
| `low/index.txt` | read into a <= 4 KB temporary buffer at room entry and freed after parsing; only the parsed tables stay (16.4) | never read |
| `low/<OWNER>.re4mesh` | yes, in place of the Original file for that owner | never |
| Original `<OWNER>.re4mesh` of a `mesh` owner | never opened | yes |
| Original `<OWNER>.re4mesh` of an owner with no `mesh` record | yes (shared) | yes |
| `texlow/*.re4tex` | on first sight, or preloaded with `TEX_RESIDENT` | never |
| `tex/<drop key>` | not preloaded; first sight only | as today |
| `low/plan.json` | never (tools only) | never |

### 16.3 index.txt format (`re4dc-std 1`)

The file is ASCII text with `\n` line ends. Tokens are separated by one space. A line starting
with `#` is a comment. A reader ignores a line whose first token it does not know, so a later
version can add record types. Hex keys are 8+8 lowercase digits, as in the package names.
Integers are decimal. Floats are fixed-point with 3 decimals, in model units (mm). The line
order is:
1. the header line;
2. `lod_px`;
3. `mesh` lines;
4. `orig` lines;
5. `tex` lines;
6. per owner, sorted by name: its `cull` lines, then its `imp` lines, then its `impt` lines,
   then its `ptex` lines, each ascending by mesh or part index (`impt`: then by first cluster);
7. `drop` lines;
8. the `end` line.

| Record | Fields | Meaning / runtime check |
|---|---|---|
| `re4dc-std 1 <room>` | schema, version, room (`r101`) | first line; the version must be 1 and the room this room |
| `lod_px <px>` | the lod_px the packages were built for (5) | log a mismatch with `re4dc_quality()->lod_px` |
| `mesh <OWNER> <bytes> <sha16>` | package size and the first 16 hex digits of its sha256 | open `low/<OWNER>.re4mesh`; its size must equal `<bytes>` |
| `orig <OWNER> <bytes> <sha16>` | the Original package this set was built against | staging checks it against the staged Original; the runtime may ignore it |
| `tex <crc>-<fnv> <w> <h> <vram> <bytes>` | a texture Standard adds: size, VRAM bytes, file bytes | open from `texlow/`; add to the preload in Standard |
| `drop <crc>-<fnv>` | a room texture no Standard package draws | skip it in the room-identity preload pass |
| `cull <OWNER> <mesh> <bin> <common> <mm>` | distance cull | see below |
| `imp <OWNER> <mesh> <bin> <common> <mm> <crc>-<fnv> <views> <cols> <cell_w> <cell_h> <atlas_w> <atlas_h> <cx> <cy> <cz> <half_w> <half_h>` | tree impostor (one line) | see below |
| `impt <OWNER> <mesh> <bin> <common> <part> <first> <count> <mm> <crc>-<fnv> <views> <cols> <cell_w> <cell_h> <atlas_w> <atlas_h> <cx> <cy> <cz> <half_w> <half_h>` | one tree of a split grove (one line per tree) | 16.5 |
| `ptex <OWNER> <part> <bin> <common> <crc>-<fnv> <w> <h>` | part texture (baked house shell) | see below |
| `end <n>` | n = the number of lines before this one | guards against truncation |

**Common rules.**
- `<mesh>` is the `MeshRecord` index, and `<part>` the `MeshPart` index, in the package that
  was opened for OWNER in Standard.
- `<bin>` and `<common>` repeat that record's `bin` and `common`. The runtime checks
  `meshes()[mesh].bin == bin && meshes()[mesh].common == common`, and for `ptex` that `part`
  lies in `[first_part, first_part + part_count)` of such a mesh. A mismatch rejects the
  index.
- There is at most one `cull`, one `imp` and one `ptex` record per mesh or part. A mesh has either
  one `imp` or its `impt` records, never both.

**`cull` (clutter distance cull).**
- Let zc be the view depth of the mesh's bounds centre,
  `modelview x ((bounds_min + bounds_max) / 2)`, in model units: `-z` in view space. The
  pipeline priced exactly this.
- When `zc >= mm`, the whole mesh instance draws nothing: no parts and no clusters.
- The rule is independent of LOD. The W9b class rules inside r101/r103 packages are separate;
  a runtime without W9b ignores them, as today.

**`imp` (tree impostor).**
- Same zc as `cull`. When `zc >= mm`, the mesh instance draws as one camera-facing
  punch-through quad instead of its parts. Below `mm` it draws its geometry.
- The fields are exactly item 20's `MeshImpostor`: `mesh`, `key_crc`, `key_fnv`, `views`,
  `cols`, `cell_w`, `cell_h`, `atlas_w`, `atlas_h`, `centre[3]`, `half_w`, `half_h`, with the
  same meaning. The atlas holds `views` cells, `cols` per row, row 0 at the top.
  - Cell k looks along `-back_k`, with `back_k = (cos a, 0, -sin a)` and `a = 2 pi k / views`
    in model space.
  - The quad spans `half_w` / `half_h` around `centre`.
  - Cell choice: `k = round(turns(-dz, dx) x views) mod views`, where (dx, dz) is the camera
    direction in model space.
  - The quad corners are `centre + (+-half_w x (bz, 0, -bx)) + (0, +-half_h, 0)`.
  - Item 20's `mesh_impostor()` (patch `item20-tree-impostor.patch`, native_static.cpp) is a
    working reference. Replace `RE4DC_TREE_IMPOSTOR_MM` with the record's `mm`, and
    `v.package.impostor(m)` with a lookup in the parsed table.
- Several records can share one atlas key (r100 COMMON BINs 1 and 2: the same tree model at
  different sizes, each with its own centre and half sizes).
- The atlas is the record's `<crc>-<fnv>`, from `texlow/`. Atlases are item 20's palettised VQ
  packages: format 3 (`kPal4`), payload VQ, 4x4-texel codebook entries, and a 16-entry ARGB1555
  palette behind the data (`data_size = 2048 + texels / 16 + 32`). The runtime needs item 20's
  `texture_package.cpp` kPal4 support (validation, `bind_palettes` into one of 64 PVR palette
  banks, `PVR_TXRFMT_PAL4BPP | VQ`). House-shell textures are ordinary RGB565 VQ.

**`ptex` (baked shell texture).**
- The part draws with the prepared package `<crc>-<fnv>` (`<w>` x `<h>`) instead of its source
  image. Its UVs address that texture directly (0..1, scale 1).
- This is item 21's `MeshTexture` (reference: `item21-house-shells.patch`,
  `re4dc_model_texture()` around `mesh_submit`). The only change is that the record comes from
  the table instead of LOD header `reserved[2]`.

**What the packages already carry (no runtime work).**
- Standard biases and the coarser LOD chain.
- The vanish guard (empty-level errors). An empty level Original never reaches stores 1.0e30, not
  3.0e38: `MeshPackage::adopt` rejects a package whose level errors are not finite, below 3.0e38
  and non-decreasing per cluster, and the float32 of 3.0e38 is just above it (r100 FILE_01/02 were
  rejected in play). `r4im.level_errors_bad` mirrors the rule; the guard step and the Standard
  build fail on any break.
- Blender coarse variants (`geom`).
- House-shell geometry, which replaces the source BIN in the package.
- Collision, placement and sequencing never read any of this.

**Why a sidecar and not the package.** Item 20 puts impostor records in LOD header words 5/6,
and item 21 puts texture records in word 7. W9b uses words 5/6 for its class and rule tables,
and the r101/r103 packages are W9b packages. Keeping the per-mesh records in `index.txt` leaves
every package byte as the converter wrote it, and cannot collide with W9b.

### 16.4 Sizes (current set)

| Room | `mesh` owners (low/ bytes) | texlow (files / bytes / VRAM) | `drop` | `cull` / `imp` / `ptex` | index.txt |
|---|---|---|---|---|---|
| r100 | 7 of 7 (1,208,448) | 7 / 60,560 / 59,552 | 5 | 16 / 11 / 2 | 2,622 B, 58 lines |
| r101 | 1 of 1 (590,112) | 21 / 121,168 / 118,144 | 6 | 12 / 3 + 9 `impt` / 9 | 3,357 B, 65 lines |
| r103 | 1 of 1 (728,096) | 19 / 189,616 / 186,880 | 3 | 25 / 7 + 13 `impt` / 3 | 4,280 B, 75 lines |

- The texlow VRAM column is the sum of every added texture's payload: the `tex` records'
  `<vram>` field, which is what `texture_package.cpp` counts (`vram_bytes_ += data_size`).
- The r101/r103 Standard sets have one owner, MAINSCENARIO; the other owners open the Original
  file. r100's Standard set has all 7 owners.
- Parsed-table bounds per room, rounded up with headroom: 16 `mesh`, 32 `tex`, 16 `drop`,
  64 `cull` x 8 B, 32 `imp` x 48 B, 32 `impt` x 60 B, 32 `ptex` x 16 B. That is about 5 KB of
  static tables for the current room, rebuilt at each room entry.
- A room that exceeds a bound is rejected (logged), and Original is used for that room.

### 16.5 Split groves (`impt`)

A grove is several trees in one BIN (r101 BIN 17: 7 trees, 24 placements; r103 BIN 38: 6 trees).
With one impostor per mesh, a grove whose centre is nearer than the switch distance draws every
tree as mesh, the far ones too. User decision (2026-09-23, option B): split groves into trees,
each with its own 8-view atlas.

**Package side (converter, no runtime work).** `convert_room_bins.py --lod-cluster-trees
OWNER:BINS` groups a BIN's triangles into trees: connected components (welded vertices), each
joined to the nearest trunk in x/z, a trunk being a component taller than 3 m
(`TREE_TRUNK_MM`). Clusters are then formed per tree (`kd_clusters` on each tree), so no cluster
spans two trees and each tree's clusters are contiguous in its part. Geometry, vertex colours
and LOD levels are unchanged; only cluster boundaries move. A BIN with fewer than two trunks,
and every package built without the option, is byte-identical to before (tested; the r100,
r101 and r103 Original packages rebuilt with the new converters are unchanged). The converter
summary lists each tree (`meshes_detail[].parts[].trees`: first cluster, cluster count,
triangles). Rooms opt in with `grove_split` in `[room.X.standard.plan]` (r101, r103); every
tree-class BIN is passed and the converter decides. The W9b converter needs the same change:
`w9b-lod-cluster-trees.patch` (on top of W9b; `mesh_lod.tree_groups` comes with the HEAD patch).

**Record.** `impt <OWNER> <mesh> <bin> <common> <part> <first> <count> <mm> <atlas> <views>
<cols> <cell_w> <cell_h> <atlas_w> <atlas_h> <cx> <cy> <cz> <half_w> <half_h>`, one per tree:
- `<part>`: the `MeshPart` index (package-wide, as `ptex`), inside the mesh's part range;
- `<first>`, `<count>`: the tree's clusters, relative to that part's cluster list
  (`part_lods()[part].first_cluster + first`, `count` clusters); check
  `first + count <= part_lods()[part].cluster_count` and `first + count <= 64` (the runtime
  keeps a 64-bit cluster skip mask per part; stdindex.py refuses a larger index);
- `<mm>` and the atlas fields: as `imp` (item 20 `MeshImpostor` semantics), with the tree's
  own centre and half sizes (model units) and its own atlas.

**Runtime rule.** Per instance of a mesh with `impt` records, per tree: zc = view depth of
`modelview x centre` (the tree's centre, not the mesh bounds). When `zc >= mm`, queue the tree's
quad (item 20's queue, cell from the camera azimuth, `views` cells) and skip its clusters; else
draw its clusters as usual. The mesh's other clusters (none today) draw as usual. Cost: one
centre transform per tree per instance (~15 cycles); heap: the records.

**Atlases (option B).** One atlas per tree, 8 views. A tall tree (frame at most half as wide as
tall) has 64 x 128 cells: a 512 x 128 kPal4 VQ package of 6,176 bytes (2048 + 512 x 128 / 16 +
32); a wide one has 128 x 128 cells: 1024 x 128, 10,272 bytes (r101 BIN 13's two trees, one of
r103 BIN 63's). The groves' former whole-BIN atlases are not staged. Split groves now: r101 BIN
13 (2 trees) and 17 (7); r103 BIN 38 (6) and 63 (7 small trees, 140 triangles in all); VRAM r101
+26 KB, r103 +46 KB against the whole-BIN atlases they replace.

**Pricing.** `camera.py` prices each tree's quad or clusters at the tree centre depth; the view
error of 8 views is sin(22.5 deg) = 0.383 (16 views: 0.195), so the solver may pick a farther
switch than for a 16-view atlas. A split grove's clusters beyond the first per drawn part cost
`c_cluster` = 5,200 cycles each (costmodel.toml: the arms fit's per-cluster figure, the
conservative end; the fitted per-part cost already covers unsplit packages).

### 16.6 r103 BIN 59: a tree the camera stands inside (per-BIN cluster size)

BIN 59 is one 7 m dead tree (3,976 triangles, 6 placements). The converter keeps a compact object
whole (k-d splits need an extent over 0.4 x `--lod-cluster` = 8 m), so it was one cluster whose
level is chosen at the nearest point of its box: with the camera within the box's depth range that
point clamps to the near plane and all 3,973 triangles draw at any bias or impostor distance (up to
3.86 hw ms, 2.25 at cow_pen, 2.02 at house_20m; about 20 grid views over 2 ms). Its next level is
572 triangles (~19 cm error), with nothing between.

**Built (user option B, 2026-09-23).** `convert_room_bins.py --lod-cluster-bins OWNER:BINS=MM` sets
the cluster size of the named BINs only (byte-identical when absent: Original reproduces W9 FIN
and r100/r101 Standard are unchanged). r103's plan sets `cluster_bins = ["0xff:59=8000"]`: 8
regions of ~500 triangles, each with its own levels, culled and LOD-picked on its own box. The
look near the camera is unchanged (full detail where the camera is). `camera.py` charges the
extra drawn clusters `c_cluster`, as a split grove's. BIN 59: max 3.86 -> 3.42 ms (grid_0_1, the
camera 1.9 m from a trunk inside the crown), cow_pen 2.25 -> 0.51, house_20m 2.02 -> 0.52; views
over 2 ms 20 -> 7. Package +5.5 KB heap 4, VRAM 0. The W9b converter gets the same option
(`w9b-lod-cluster-bins.patch`, on top of W9b + w9b-lod-cluster-trees.patch).

**Measured and not taken.** A level cap (never the full level): BIN 59 max 0.68 ms, but ~19 cm
error where the camera stands. PS2 r103 BIN 74 as a substitute (691 triangles, 0.90 ms max): a
much sparser tree (trunk and ~6 branches against GC's full crown), and PS2 has it at 1 of the 6
spots. Blender collapse stops at 2,252 triangles (p90 17-22 cm, normals 52 degrees off on
average) and the house-shell bake at 1,726: neither reduces this mesh usefully.
