# GameCube to Dreamcast: source and hardware findings

Researched 2026-09-19. RE4 source baseline:
`9dcd989370be7f083a9b66cfd19907fda627c893` (G4BE08 debug build).
Hardware references are manufacturer publications and the pinned KallistiOS
implementation. Recommendations below are engineering decisions, not measured
claims that the port already meets its budgets.

For the current r100 work, follow [REALTIME_PATH.md](REALTIME_PATH.md), revised
2026-09-20. It adds source SAT hierarchy/query recovery, per-model light selection,
shared skinning palettes, source object/draw/residency ownership, and corrected
performance/memory acceptance. The r10d priorities below are historical research,
not the current execution order.

## What RE4 actually renders

RE4's cinematics lead, Yoshiaki Hirabayashi, describes real-time cutscenes,
scene-specific asset budgets, and secondary cameras rendering images into
textures. His 2005 postmortem also describes Ganado variants of approximately
3,500 / 2,000 / 1,000 polygons and 512 / 256 / 128-pixel texture tiers. Those
are useful leads for reusing existing cheaper assets; they do not prove which
variants are present in our earlier debug build. [Developer postmortem][postmortem].

The local source and supplied Disc 1 establish the following distinctions:

| Path | Evidence | Consequence for this port |
|---|---|---|
| Room scenery | `scroll.cpp::setObj` creates placed models; `trans.cpp::ModelTrans` and `trans_ot.cpp` perform visibility checks; `commonModelTrans` submits their GX display lists. Our r10d SMD exports actual 3D vertices, normals, UVs, and triangles. | r10d is not a pre-rendered background plate. Keep world geometry and the moving camera; cull before transforming. |
| In-engine cinematics | `event.cpp::ExePacket_Pos`, `ExePacket_Mot`, and camera/light packets place and animate models. | Treat these as runtime scenes. Replacing all of them with movies would require new capture, video, input/QTE, and branching work; it is not an immediate shortcut. |
| Recorded video | `st1/r120.cpp::R120Event` calls `Sofdec.Initialize("movie/opening.sfd", 0)`, then executes `r120s00.evd` and `r120s01.evd`. `title.cpp` also starts SFD demos. | The game does use video, alongside real-time scenes. Convert actual movie assets later, without making a movie player a prerequisite for r10d. |
| Render-to-texture effects | `TexRender.cpp::CopyTexRenderMgr` copies a freshly rendered EFB image to a texture; `trans.cpp::GetEfbTex` and shader setup support further effects. | A cached image can have been rendered this frame. It is not automatically a disk movie or a free pre-rendered background. Simplify costly secondary passes when they enter the slice. |
| Material and lighting data | TPL textures, optional vertex colors in `commonModelTrans`, and the normal-based `GlobalIlluminationSetup` texture lookup contribute to shading. | Preserve authored texture/color information. Inspect the chosen materials before claiming a baked-lighting shortcut; the function name does not mean a modern real-time GI solver. |

Sources: [room objects][scroll], [model renderer][trans], [visibility][ot],
[event packets][events], [opening sequence][opening], [movie player][sofdec],
[render textures][texrender].

Read-only listing of `files/movie` on the verified private Disc 1 found seven
SFD entries: `opening`, `demo0`, `demo1`, `adaend_c`, `adaend_m`, `r214_ev`, and
`r229_ev`. This is a directory inventory, not a decoded visual review or an
exhaustive classification of every scene. Reproduce locally with:

```sh
build/tools/dtk vfs ls orig/G4BE08/re4_debug_disc1.iso:/files/movie
```

One significant movie-port trap is confirmed directly: `cSofdec::initWork`
parks a 5 MiB heap in GameCube ARAM and reuses that space for video; `finishMovie`
restores it. Dreamcast cannot inherit that auxiliary-memory assumption. A
later movie path needs bounded buffers and explicit scene unload/reload.
[Movie heap handling][sofdec].

## Differences that should drive implementation

| Priority / concern | GameCube to Dreamcast difference | Action for the playable slice |
|---|---|---|
| P0: geometry work | GameCube exposes a geometry engine and hardware lights. Our KOS PVR interface expects already transformed vertices. RE4 also performs software skinning for applicable models; not all source animation work is free on GX. | Cull complete objects first, transform only referenced visible geometry, and measure skinning with room rendering. Use KOS SH-4 matrix routines and batch submission. Reducing resolution alone cannot remove geometry CPU cost. [Nintendo][nintendo], [KOS PVR][pvr], [KOS matrices][matrix], [RE4 renderer][trans]. |
| P0: memory pools | GameCube has 24 MB main RAM and 16 MB auxiliary RAM. Dreamcast has 16 MB main, 8 MB video, and 2 MB sound RAM. GameCube's roughly 2 MB embedded framebuffer and 1 MB texture cache are not its whole texture-storage budget. | Count code, expanded geometry, collision, actors, pose/transform scratch, staging, and allocation peaks separately. VRAM also houses render/parameter resources. Avoid duplicate room copies and all-actor/all-motion preload. [Nintendo][nintendo], [Sega][sega], [KOS PVR][pvr]. |
| P0: clipping and submission | The existing viewer emits each triangle as an independent strip and rejects triangles crossing behind the camera. | Fix near-plane clipping for the shoulder camera. Benchmark grouped/strip submission only where it saves time; use the pinned SDK clipping example as a reference. [KOS clipping example][clip]. |
| P1: materials | RE4 builds GX TEV combinations for textures, shadows, specular, bump, alpha, and other effects. These are not a direct PowerVR material format. | Start with base texture plus vertex/static lighting; preserve necessary cutouts. Bake only static contributions, and simplify optional reflections/distortion/shadows. Add further passes only against measured cost. [RE4 shader setup][trans], [KOS PVR][pvr]. |
| P1: texture formats | GC compressed/tiled textures cannot be uploaded unchanged as Dreamcast textures. KOS offers RGB565, ARGB1555/4444, palettes, and VQ options; its VQ load flag does not encode data. | Decode/re-encode offline, generate needed mip levels, preserve alpha and UV seams, and measure actual VRAM usage. Audit source material/color data lost by the current OBJ path before changing its appearance. [KOS texture loading][textures], [KOS PVR][pvr]. |
| P1: fill and transparency | Dreamcast's PowerVR uses tiled deferred rendering and offers transparency sorting and texture compression. Hidden-surface savings apply after geometry submission. | Keep opaque, cutout, and blended geometry distinct. Use VQ/palettes when suitable; do not assume hidden surfaces eliminate the SH-4 work already spent transforming them. Check foliage and transparency on the actual target. [PowerVR designers][powervr], [TBDR explanation][tbdr]. |
| P1: ABI and transfers | The PPC/GX build's pointers, endian layout, paired-single math, fixed addresses, and display lists do not execute as native SH-4 code. KOS PVR DMA requires aligned addresses and transfer sizes; some SQ and DMA operations cannot overlap. | Keep explicit package serialization, the proven motion/math boundary, and narrowly compiled gameplay dependencies. Retain alignment, cache ownership, and transfer lifetimes; use native KOS APIs. [Existing ABI baseline](PORTABILITY_BASELINE.md), [KOS DMA][dma], [KOS store queues][sq]. |
| P2+: controls, media, and timing | Controller mappings, sound hardware, storage, and saves differ. Nintendo documents about 1.5 GB per GC disc; Sega documents roughly 1 GB GD-ROM. This does not define a homebrew CD/ODE delivery budget. | Map actions on the standard Dreamcast controller; retain simulation/event timing. Declare and measure the deployment route. Offline-convert sound/video when needed, stream with bounded buffers, and defer VMU/menu/campaign work. [Nintendo][nintendo], [Sega][sega], [Campaign plan](PLAYABLE_PATH.md). |

Raw peak polygon or floating-point figures are not an RE4 performance estimate.
Use combined scene measurements and physical Dreamcast results to decide LOD,
resident assets, and effect complexity.

## Changes to the immediate backlog

1. Keep r10d as real-time 3D. Integrate SAT collision, movement, and a shoulder
   camera, including correct scale and clipping.
2. Before creating new low-poly character art, inspect the supplied archive's
   model variants and selector logic. Reuse a compatible cheaper source variant
   if present, preserving skeleton, motion events, and hit/collision semantics.
   This is an asset audit task, not a claim that such a variant is already chosen.
3. Preserve basic source textures and inspect static lighting/color data; the
   current flat random material colors are a diagnostic view, not source fidelity.
4. Keep movie playback and expensive render-to-texture effects off the r10d
   critical path. Record them as campaign work instead of classifying them as
   already handled by pre-rendering.

The ordered implementation and acceptance boundaries are in
[PLAYABLE_PATH.md](PLAYABLE_PATH.md).

[postmortem]: https://www.gamedeveloper.com/design/postmortem-i-resident-evil-4-i-
[nintendo]: https://www.nintendo.com/en-gb/Hardware/Nintendo-History/Nintendo-GameCube/Technical-Details/Technical-Details-627134.html
[sega]: https://www.sega.jp/history/hard/dreamcast/
[pvr]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/include/dc/pvr.h
[matrix]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/include/dc/matrix.h
[textures]: https://kos-docs.dreamcast.wiki/group__pvr__txrload__constants.html
[clip]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/examples/dreamcast/pvr/modifier_volume_zclip/pvr_zclip.c
[dma]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/include/dc/pvr/pvr_dma.h
[sq]: https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/kernel/arch/dreamcast/include/dc/sq.h
[powervr]: https://blog.imaginationtech.com/celebrating-the-20th-anniversary-of-dreamcast-and-powervr/
[tbdr]: https://blog.imaginationtech.com/powervr-graphics-we-render-funny/
[scroll]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/scroll.cpp
[trans]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/trans.cpp
[ot]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/trans_ot.cpp
[events]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/event.cpp
[opening]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/st1/r120.cpp
[sofdec]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/sofdec.cpp
[texrender]: https://github.com/adonis-singh/re4/blob/9dcd989370be7f083a9b66cfd19907fda627c893/src/game/TexRender.cpp
