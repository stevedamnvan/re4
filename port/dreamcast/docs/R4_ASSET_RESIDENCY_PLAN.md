# R4: Dreamcast asset residency and streaming

Status: open. Deliverable 1 is done and is recorded in
[R4A_TEXTURE_INVENTORY_CHECKPOINT.md](R4A_TEXTURE_INVENTORY_CHECKPOINT.md);
its measured findings have already corrected two assumptions in this plan, and
the corrections are folded in below.

## Goal

Convert RE4 resources offline into Dreamcast-native representations and keep
only the active and prefetched working set in main RAM, VRAM and AICA memory.
Use the original GameCube RE4 block, room and connection relationships to
decide residency; use DCA3's Dreamcast streaming architecture as
implementation prior art; use the PS2 RE4 assets as a reference for
Capcom-authored reductions only where the GameCube representation cannot meet
the Dreamcast budget.

The renderer work of R3 is approaching the point where the next problem is not
drawing the room faster but entering the next room without keeping the previous
rooms, every texture and every character resource resident. R4 is that
problem.

## Three references, three roles

| Reference | Role | What it decides |
|---|---|---|
| GameCube RE4 (decompilation and disc) | behavioural and visual authority | what the correct result is whenever the Dreamcast can afford it |
| PS2 RE4 (retail disc) | Capcom's constrained-memory reference | which assets and effects Capcom itself judged reducible, and by how much |
| DCA3 (GTA III/VC on KallistiOS) | Dreamcast implementation reference | how a shipped-scale Dreamcast port prepares assets offline and streams a working set on 16 MB / 8 MB / 2 MB |

DCA3 is a port of the reversed `re3` codebase; its value here is its structure,
not its code. Its build converts the original assets into the Dreamcast
representation and repacks the archives offline (`texconv` and the repacking
tools), and its runtime keeps the GTA `Streaming`/`TxdStore` systems with a
Dreamcast-specific `CdStreamDC` path. Study the mechanisms; do not copy source
without a licence check, and never its game data. Reference:
[DCA3 on GitLab](https://gitlab.com/skmp/dca3-game).

The PS2 disc is used only as a measurement oracle for its asset choices. No
PS2 asset enters a package.

## Lesson one: the SH-4 must not interpret GameCube assets at play time

The current slice already converts offline into `re4room`, `re4chr`, `re4tex`,
`re4sat`, `re4rtp`, `re4hud` and WAV packages, so the conversion principle is
in place. What is missing is the rest of the pipeline shape:

    BUILD TIME
    GC RE4 assets + source metadata
      -> Dreamcast asset compiler
         room geometry   -> native strips, cells, batch-local vertex tables (R3v)
         textures        -> native PVR twiddled 565/1555/4444, VQ, PAL4/PAL8
         animation       -> pose palettes (package v6)
         collision       -> SAT hierarchy (re4sat)
         audio           -> AICA-ready samples
         materials       -> precompiled PVR header state
      -> Dreamcast room/resource archive

    RUNTIME
    GD-ROM / GDEMU -> asynchronous reads -> staging arena
      -> 16 MB main RAM working set (active room, actors, animation)
      -> 8 MB VRAM (active textures) and 2 MB AICA (active cues)

Today the slice embeds every package in the executable's ROM disk and maps it
with `fs_mmap()`. Post-load free main RAM is 5,357,568 bytes with one room
(2.2 MB package), Leon (1.7 MB), Ganado (1.16 MB), their textures, the HUD
and the audio cues resident. That is a demo image, not a residency model.

Runtime work that still interprets rather than reads: texture upload from
the package layout into VRAM, the R3v batch-local table pass at load, and
any decode of texture payloads. Each is a candidate to move to build time.

## Lesson two: streaming is a subsystem, and RE4 makes it an easy one

RE4 already divides content into rooms, blocks, connections and transitions,
and the decompilation shows authored active/staged block sets and
`checkBlockMemory`. RE4DC therefore does not need GTA-style arbitrary world
streaming. The residency unit is the room, with these sets:

    always resident      room gameplay state, SAT and routes, Leon, common
                         weapon resources, common effects
    active set           visible room cells, active enemies, active room
                         textures, current animations
    prefetch set         connected room geometry, upcoming textures, upcoming
                         enemy types, transition resources
    evictable            previous room, distant or inactive resources, unused
                         animation and material banks

Start from the authored sets and recompute the largest active set and the
transition overlap with converted sizes and shared resource identities. Do not
introduce a guessed loading radius. Preserve original load-stop behaviour where
the source has it; seamless loading everywhere is not a source requirement.
GameCube ARAM is not spare AICA memory.

## Lesson three: choose a texture representation per texture

DCA3's authors describe RAM and VRAM as their main constraint and their early
conversion as brute force. RE4DC's texture compiler should decide per texture:

    GC texture
      lossless-enough at 16 bpp   -> PVR 565 / 1555 / 4444, twiddled offline
      VQ-friendly                 -> PVR VQ (pvrtex), codebook chosen per texture
      low-colour                  -> PAL4 / PAL8
      fidelity-sensitive          -> native uncompressed

and the runtime deals only in Dreamcast-ready payloads: read, allocate VRAM,
transfer. No PNG decode, no GameCube texture decode, no runtime VQ encoding,
no runtime twiddling.

## The PS2 disc as a second oracle

For every corresponding asset, measure automatically what Capcom changed
between GameCube and PS2: resolution, pixel format and colour depth, mipmap
count, texture count, geometry count, material and pass count, animation
representation, effect and material differences. The result is a database that
replaces guessing ("can this wall be 256x256?") with evidence ("Capcom shipped
it at 256x256 on PS2").

The Dreamcast does not inherit the PS2 downgrade. Decide per asset:

    GC original
      can DC keep it directly?         yes -> native format
      no -> try VQ                     visually acceptable? yes -> VQ
      no -> inspect the PS2 reduction  acceptable on DC?    yes -> PS2-sized, GC-sourced
                                                            no  -> escalate

This is now measured rather than assumed, on the r100 textures: a 256x512
GameCube wall the build had reduced to 128x256 costs 65,536 B as shipped and
34,848 B at full resolution under VQ, with 5.7 dB better PSNR. The
higher-resolution GameCube artwork is genuinely cheaper than the reduction, on
this room, for every texture that was reduced. It is not cheaper in quality
terms for textures that were not reduced; see the checkpoint.

PS2 teaches what can be reduced; DCA3 teaches how to manage it; GameCube says
what the correct result is.

## Deliverables and order

1. **Asset inventory tool** — **done**, `tools/asset_residency_report.py`, with
   `texture-r100-production` added to reproduce the previously untracked r100
   texture package. Run it with
   `make -C port/dreamcast -f Makefile.host asset-residency-r100`. Its first
   findings, in
   [R4A_TEXTURE_INVENTORY_CHECKPOINT.md](R4A_TEXTURE_INVENTORY_CHECKPOINT.md):
   six r100 textures that the build reduced to meet a 256-pixel limit can be
   restored to their authored resolution under vector quantisation for 46% less
   VRAM and 5.7 to 7.3 dB more PSNR, so that change has no trade-off to review;
   and vector quantisation applied to textures that were *not* reduced costs 3
   to 13 dB, so it is not a default and is reserved for a residency budget that
   requires it. The default candidate plan is 1,732,608 B against the shipped
   1,978,368 B, with six textures gaining detail; the all-VQ floor is
   472,576 B. No PS2 disc is present in this workspace, so that column reads
   "no PS2 source" until one is supplied to `--ps2-manifest`. Meshes are not
   yet inventoried; extend the tool when the residency model needs them.
2. **Native texture layout** (next): offline twiddled payloads with explicit
   layout metadata and one uploaded handle per deduplicated payload, then the
   per-texture representations deliverable 1 selected. This needs the `re4tex`
   header to carry the payload format, since the runtime currently assumes
   linear 16-bit and twiddles during `pvr_txr_load_ex()`; VQ and palette
   payloads cannot be expressed in the present format. Take the six
   restorations first: they are strictly better and exercise the whole path.
   Credit this to load time and memory unless a frame trace changes.
3. **Package-resident batch-local tables**: emit the R3v local strip indices
   and batch vertex tables from the converter, recovering most of the 413,696
   bytes the runtime pass holds.
4. **Residency model from the authored block sets**: enumerate the r100 active,
   staged and remove sets and the connected rooms from the decompilation;
   compute the largest converted working set and the transition overlap;
   record the storage path the source intends.
5. **Asynchronous reads and a staging arena**: bounded read buffers, active
   room blocks, immutable shared resources, texture handles and reclaimable
   upload staging for GD-ROM/GDEMU, replacing the embedded ROM disk and
   mandatory `fs_mmap()`. A path change from `/rd/` alone is insufficient;
   closing a mapped file does not remove its payload from the executable.
6. **Second room transition**: the first end-to-end proof, entering a
   connected room from r100 with the previous room evicted, measured for
   load time, peak RAM, VRAM and AICA high-water marks, and frame-time impact
   during prefetch.

Items 1-3 can proceed alongside the remaining R3 frame work; items 4-6 need
the residency model first. Memory high-water records precede any acceptance.

## Boundaries

R4 does not change the accepted r100 presentation, camera, geometry, lighting,
transparency, collision, timing or audio. Startup and load-time work is never
credited as a per-frame saving. Physical Dreamcast timing, GD-ROM read rates
and VRAM allocation behaviour must be measured on hardware before residency
sizes are fixed; Flycast can validate correctness and memory arithmetic only.
