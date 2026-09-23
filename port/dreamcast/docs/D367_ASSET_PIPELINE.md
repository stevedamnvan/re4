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
- VRAM: the room set must fit `pool - resident`. The pool is 2.58 MB at `TA_VERTBUF_KB=2048`;
  resident is UI + Leon + weapons + core, measured from run logs.
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

**Impostor.** Beyond depth D, a tree is one quad from a 16-view atlas: 4 records, 1 strip, ~150
cycles batched. The view quantisation (22.5 deg, so an error of at most sin 11.25 deg = 0.195)
gives an impostor screen error `e_imp = 0.195 * r * K / z`. The distance rule is
`D = 0.195 * r * K / P_imp`. `P_imp` = 20 px reproduces the approved 12 m for the r100 trees
(r ~ 3 m), so the user's judgement is itself a fitted coefficient, stored with its provenance. A
new judgement re-fits it. Atlas VRAM comes from the generator report (84 KB for the r100 set).

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
   trees; otherwise ground (height <= 0.25 x horizontal extent, >= 10 m wide), clutter (radius
   <= 1.5 m) or structure.
2. Houses: `house.shell` steps (Blender bl_house_shell.py + house_shells.py, cached by hash) on
   the ladder `house_faces`; the first rung whose p90 source-to-shell error is <= `house_err_cm`
   is used. r100: 48, 96 and 200 faces break the houses (p90 1.2-3.7 m); 400 faces pass (21 and
   26 cm), the same count as the approved low512 shells. The review shows the rejected rungs.
3. Options per class (`[plan.standard.options]`): extra LOD bias, tree impostor centre depth
   (item 20 records), clutter cull centre depth; plus, for ground/structure, the same options on
   a Blender reduction (`scenery.decimate`, bl_decimate.py) whose p90 error is <= `max_p90_mm`
   and whose worst source-to-reduction distance is <= `max_mm`. That reduction's error is the
   option's error floor in the quality term. Standard packages use a coarser LOD chain of the
   same depth (`lod_args`); an owner whose package would grow is rebuilt with the recipe chain.
4. Pricing at runtime LOD px 5 over the ground grid plus the named views (`[room.X.views]`:
   spawn and walk frames from SCEN_LOG cam/pl, house approach at 30/8/3 m, the heaviest
   Original grid view).
5. Lazy-greedy multiple-choice solver (`budget.solve`): moves ranked by reduction of summed
   relative excess over all views per unit of weighted quality loss, deterministic ties, then
   an upgrade pass. Views still over budget are reported, never hidden.
6. Final packages bake recipe bias x chosen bias per BIN; the staged set is priced again and
   those numbers are the ones reported (the solver's differ by at most ~0.5 ms).
   `plan.json` carries the runtime choices (impostor/cull distances, geometry variant).
7. Review: `review/standard/<room>/index.html` renders both modes from identical cameras with
   the textured software renderer (`render.py`, `scene.py`: TPL textures, PS2 bark, baked shell
   textures, impostor atlas cells, PVR-style modulate, punch-through alpha, 25 m fog), with
   per-view asset ms, triangles, and a frame estimate = `frame_rest_ms` (design-lowmode D2 floor
   28.3) + `base_ms_planned` (2.5) + assets, against 33.3 ms.

r100 prototype (2026-09-23), scenery assets excluding base: Standard named views 5.7-10.7 hw
ms, grid p95 7.34 / max 10.6, within 5 ms at 158 of 215 views (159 before the Blender
`--threads 1` pin re-baked the shells); Original 14.2-24.9, grid p95
17.6 / max 24.9. Heap 4 -302 KB (every package <= Original), VRAM +170 KB (shells 132 KB,
atlases 82 KB), second set on disc 1.51 MB (every package differs while biases are baked; section 15
weighs a runtime per-BIN table that would limit it to geometry-changed packages). Remaining
cost: PS2 trees nearer than the impostor distance, a tail of terrain pieces, the two shells.

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
| `tree.impostor` | bl_impostor_bake.py + tree_impostors.py + mesh_annotate.py (item 20) | atlases `.re4tex`, annotated package | `TEXDIRS`, `MESHDIR` |
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
  `/cd/dc/texlow/<d>/<key>.re4tex`.
- Each Standard directory carries an index (`native/<room>/low/index.txt`: file names;
  `texlow/index.txt`: texture keys). The runtime reads it once at room entry and opens only the
  listed Standard files, otherwise the Original path. There are no probe-opens: a failed iso9660
  lookup re-reads the directory from the disc, which caused the ~0.2 s texture hitch.
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
| Blender steps (planar decimation, house shell bake) | yes with pins (measured) | run as `blender -b --threads 1 --factory-startup`; fixed seeds and sample counts in the scripts; inputs sorted. Without `--threads 1` the same shell came out with the same metrics but a different vertex order (and so different OBJ/PNG/JSON bytes) than with a different thread count, so a machine with another core count would not reproduce it. `blender_threads` is part of the fingerprint. |
| impostor bake (item 20) | pinned artifact | the r100 atlases are a pinned input (sources.toml `r100_impostors`), hashed by content like an AI output |
| convert_route_movies (ffmpeg) | yes with pins | `-threads 1`, pinned version |
| review renders | yes | pure-Python rasteriser |
| **ai-upscale** (ComfyUI + PBRify, local, port 7860) | **no** | opt-in only |

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

## 14. Delivery steps

| Step | Content | Status |
|---|---|---|
| a | this design | done |
| b | tool skeleton, cache, r100 wired to the existing generators, review sheet | done: `build r100 --plan recipe` reproduces the LFV r100 inputs byte for byte; `--verify` passes |
| b2 | Standard (budget-first) prototype for r100: classes, shells, coarse variants, impostor/cull options, solver, textured Standard vs Original review | done (prototype; 4.9.1) |
| c | solver (`--plan solve` for Original) + `calibrate` | solver done in budget.py; calibrate open |
| d | r101, r103 (Standard, built together: user decision 2026-09-23) | in progress |
| e | overrides + upscale (source) + opt-in ai-upscale | |
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
