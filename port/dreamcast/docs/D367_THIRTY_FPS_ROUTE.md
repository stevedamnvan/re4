# D367: 30 fps on real hardware, three-room route

Active since 2026-09-23 (Claude, user-directed). This document supersedes the
paused D366 handover and the "beat D349" sequence as the current plan. Earlier
checkpoints remain evidence.

## Goals and decision rules (user)

- **Target: 30 fps on a real Dreamcast.** Flycast is a proxy. It counts issued
  instructions and has no cache or latency model. It does not enforce TA or VRAM
  capacity.
- **Decide by frame time.** Every option states its ms/frame impact as:
  - a real-hardware estimate against the 33 ms frame;
  - the measured Flycast figure, noting the 16.7 ms vblank quantisation.

  Take the fastest option whose visual difference is negligible. A modest cost
  is acceptable only when the result looks substantially better.
- **GameCube rendering tech may be abandoned** for Dreamcast-native approaches,
  including new or simplified assets and PS2-derived art. Collision, events,
  game sequencing and gameplay state stay source-authoritative.
- **An ODE (GDEMU) may be required.** Ship GDI with 2048-byte data tracks, not
  CDI. Design for ms-class latency and 1.5-3 MB/s sustained reads, all async
  and prefetched. The G1 bus caps reads at about 10 MB/s.
- **Floating point:** `-ffp-contract=off` everywhere was approved (logic plan
  step 6B). Recapture the determinism baseline once. After that, O2 changes
  must be strictly identical.
  - GAME_FDLIBM=1 (contract-off trig built from the recovered newlib sources)
    goes in the same step.
  - Render-only native renderer objects are exempt, saving about 0.5 ms on
    hardware.
  - KOS flushes denormals (FPSCR), so O2 isn't identical by construction. The
    STRICT trace gate decides.
- **Hardware test gate:**
  - No console testing until the recovered game plays r100 -> r101 -> r103
    through normal transitions, with cutscenes, music, sound effects,
    inventory and death/retry.
  - Flycast must reach about 15 fps first.
  - The test kit is a GDEMU and a VMU, with no serial link. Diagnostics go on
    the VMU LCD (dca3 style) and an on-screen PERF_HUD with the logic digest.
- **Cutscenes must play.** Skipping them loses story context. Present each
  route event with its PS2 pre-rendered movie (BIO4MOV.AFS) while the GC event
  code applies every gameplay effect. Build on branch
  `experiment/ps2-fmv-spike`: it has the menu, the intro FMV with audio, and
  the route entry. Its FMV state is largely uncommitted in that worktree.

## Hardware budget

Sources are the official Sega documents (catalogue and citations in the
private probe `dc-official-docs/REPORT.md`) and the dca3-game source.

**Render rate.** Sega's real-world figure is 1 M polys/s for 100-pixel
triangles, about 33k triangles per frame at 30 fps.
- Plan about 20-24k scenery triangles and 6-8k actor triangles.
- That is 50-65k strip vertices per frame.

**VRAM parameter cost** (Dev.Box 3.7.9). Stored cost is 12 B per sub-strip,
plus per vertex:

| Vertex format | Bytes per vertex |
|---|---|
| Textured, 16-bit UV | 20 B |
| Textured, 32-bit UV or offset colour | 24 B |
| Textured, 32-bit UV and offset colour | 28 B |

- At Strip_Len 6 that is 28.7-39.3 B per triangle.
- TA input is 32 B per vertex; don't confuse the two.
- The TA guard must count stored bytes.

**Vertex buffer.** It is a pvr_init VRAM allocation, not a hardware constant.
- dca3 uses 2 MiB per bank x2 with an adaptive per-meshlet guard.
- We currently use 1 MiB, which r100 exceeds on hardware even after LOD.
- Larger buffers are blocked by UI texture VRAM: the UI cache holds 3.0-3.6 MB
  at the title screen.

**Overflow.** A parameter or object-list overflow means that frame cannot be
drawn. Kamui never overflows.

**CPU.** One SH-4 core carries logic and rendering in the same 33 ms.
- Estimated cycles per vertex:
  - prelit scenery: 30-45;
  - lit geometry: 45-70;
  - skinned actors: 70-120.
- Timings: FTRV 1 per 4 cycles; FDIV 12-13 cycles.

## Measured progression (Flycast, r100, frames 2401-2520)

| Candidate | ms/frame | Change |
|---|---|---|
| Q | 559 | |
| S | 409 | NO_EH (f10ed71) |
| T | 234 | Meshlet fast path (02d5a0f), dense actor path (bfa1452) |
| U | 217 | Spatial meshlet packages |
| V2 | 200 | pipeline30: PVR_FAST_WAKE, BRIDGE_LEAN, PVR_PIPELINE=1 |
| LA | 150 | scenery30: MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1 (LOD packages, GX fog as PVR table fog to the 42.7 m source far plane) |
| LB | 150 | Lightly reduced GC trees; about 2 ms less work, same vblank step |
| LC | 117 | actors30: NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1; actors about 51 -> 18 ms |
| LD | 117 | PS2 trees (ps2-blender stage.sh overlay). About 2.5 ms less work; COMMON package 507 -> 136 KB, so heap 4 gains ~370 KB. **Chosen.** |
| LE | 117-119 | PS2 "groves" variant. 6% more TA data; a few more background trunks; the visual gain is negligible. Rejected by the frame-time rule. |
| LF | 117 | LD + async present (PVR_PIPELINE=2, KOS patch `kos-804b319-async-present`). Work ~96 ms plus ~6 ms fence wait still lands on the 100 ms+ vblank step, so Flycast shows no change. **Adopted as the default**: the better architecture (CPU no longer waits on render), per the user's rule. |
| FE | 100 | LD + frontend30 (COPY_LEAN, FRONT_LEAN, MESH_DIRECT+TA_DIRECT+NATIVE_ACTOR_DIRECT; de03f28): work 95.9 -> 79.9 ms, one vblank step fewer. The logic trace is STRICT. Being re-validated on LF. |

Remaining work in LC is about 98 ms. It rounds up to 7 vblanks.

| Area | ms/frame |
|---|---|
| Game-side CPU | ~36 |
| Actors | ~21 |
| Scenery | ~19 |
| Memory copies | ~12-15 |
| Vblank pacing waste | ~19 idle |

## Asset decisions

- **Trees:** PS2 trees for r100, with the source key texture replaced by the
  PS2 bark (VQ).
  - The worst village view drops from 61.7k to 35.7k strip corners.
  - A "groves" variant (one PS2 tree per GC trunk) costs about 2.5 ms more
    scenery time on hardware. It was compared in game (LD vs LE) and rejected:
    the visual gain is negligible.
- **PS2 static scenery** is the same geometry as GC, so there is no gain there.
- **PS2 character meshes** are not lighter (em12: 411 KB vs 407 KB). Actors
  instead rely on:
  - LOD;
  - moving non-animated room objects to the static prelit path;
  - 16-bit UV.
- **Blender** (5.2, Windows, headless) is used for measurement, planar
  decimation of static BINs and comparison renders. Its collapse and far-LOD
  output lost to the converter's own QEM LOD.

## Performance plan status (updated 2026-09-23)

Flycast ms are for r100, frames 2401-2520. The "work" figure excludes vblank
idle. Hardware figures are estimates until the projection model and the
console calibrate them.

| # | Item | Flycast effect | Hardware effect (est.) | Status |
|---|---|---|---|---|
| 1 | Instanced per-BIN scenery, source-to-native static path | 1390 -> 559 | large | Done (5dd04d3, ed9393c) |
| 2 | Remove per-vertex libcalls | 559 -> 434 | similar | Done (e62cc4b) |
| 3 | NO_EH; also frees 360 KB for heap 4 | 434 -> 409 | small | Done (f10ed71) |
| 4 | Meshlet fast path + dense actor path | 409 -> 234 | large | Done (02d5a0f, bfa1452) |
| 5 | Spatial meshlet packages | 234 -> 217 | medium | Done (e62cc4b option) |
| 6 | PVR pipeline, fast wake, lean bridge | 217 -> 200 | overlaps render on hardware | Done (a1db43d) |
| 7 | Scenery LOD + source fog + far cull | 200 -> 150 | scenery ~9-11 ms | Done (64b25dd) |
| 8 | Fast actor path + deferred skinning | 150 -> 117 (actors 51 -> 18) | actors ~16 ms | Done (4fa839d) |
| 9 | PS2 trees | -2.5 ms work, heap +370 KB | worst views 61.7k -> 35.7k corners | Done; tooling committed (7a7036a) |
| 10 | Async present (PVR_PIPELINE=2, private KOS) | removes part of ~19 ms pacing waste | overlaps CPU and render | Done: LF, adopted as default (neutral in Flycast) |
| 11 | Actors pass 2: static room objects, whole-part LOD, 16-bit UV | ~18 -> ~8 | ~16 -> 3-5 | In progress |
| 12 | Game CPU: SH-4 matrix kernels, PS alias links, room index, rot cache | ~-6 | more (call overhead, cache) | Code proven; Flycast validation running |
| 13 | FP 6B (contract-off + FDLIBM), then O2 on hot objects | ~0 to -2 | -1 to -3 | Validation running |
| 14 | Memory-copy audit (~15 ms) | -7.5 (COPY_LEAN) | more (cache thrash) | Done (de03f28); validating on LF |
| 15 | GC render front-end removal (objTrans, light setup, normal matrices, draw-plan walk) + direct TA meshes | -6.4 (FRONT_LEAN) -3.6 (MESH_DIRECT) | similar | Done (de03f28); validating on LF |
| 16 | UI VRAM diet -> 1.5-2 MiB vertex banks | 0 | required so hardware doesn't overflow | Patch proven: title peak 3.95 MB -> 1.04 MB, r100 0 upload failures at 1536/2048 KB (LRU + fail-fast + VQ). Validating on LF |
| 17 | Hardware projection model (pairing + I/D-cache simulation) | - | ranks items 18-21 | In progress |
| 18 | pref / OC-RAM transform cache / fsrra in render code | ~0 in Flycast | est. several ms | Waiting on #17 ranking |
| 19 | I-cache hot/cold code layout | ~0 in Flycast | potentially large (8 KB IC, large code) | Waiting on #17 |
| 20 | Tree impostors beyond ~12-15 m (16 views x 128, 4bpp VQ, 82 KB VRAM) | - | -1.0 to -1.2 (heavy mean 8.62 -> 7.39-7.64 ms with PS2 trees) | Designed; needs a batched punch-through quad path. Flat at 8 m |
| 21 | Lighter near-camera FILE_01 houses (5.18 of 8.6 ms hardware scenery; 17.1k corners in 3.9k strips) | - | automatic Blender reduction only -0.17 at acceptable error; new low-poly shells with a baked texture could save most of ~4 ms | Open: needs package-supplied textures + new house meshes |
| 22 | Bytes-based TA guard + 32-byte limits (Sega rules) | 0 | correctness | After #16 |
| - | Costs being added: music + SFX, FMV decode (cutscenes only) | +1-3 ms in gameplay | +1-3 ms | Audio and cutscene agents |

**Projection.** Items 10-15 take Flycast work from ~96 ms to about 55-65 ms
(15-18 fps), which clears the ~15 fps console gate. Items 17-21 target the
rest of the way to 33 ms on hardware.

## Plan to 30 fps

Steps are ordered by expected frame-time gain.

1. Actors, second pass: static-path room objects, whole-part LOD, 16-bit UV.
   Target about 8k triangles, about 3-5 ms on hardware.
2. Game-side CPU:
   - proven-identical SH-4 matrix kernels, PS alias links and the room index
     (about -6 ms);
   - 6B then O2;
   - removing GC render front-end work the native renderer makes redundant
     (objTrans about 13 ms, GX stubs, light setup).
3. Memory-copy audit (about 15 ms).
4. Async present (PVR_PIPELINE=2, KOS patch) and fixed 30 fps pacing.
5. UI VRAM diet, so 1.5-2 MiB vertex banks fit.
6. Hardware tuning after the first console session: cache layout, prefetch,
   OC-RAM.

## Route plan (frontier units)

Assessment: the recovered game reaches r100 gameplay. r101 and r103 have never
run in it; "r101 works" commits are the separate room viewer.

| Unit | Work | Status (2026-09-23) |
|---|---|---|
| W0 | Frozen private baseline | Done (private tree; hashes in frontier notes) |
| W1 | Extract route files from the debug ISO; build r101/r103 DARs; compact em15/26/28/21 | Done: tools ded299f; mirror complete for all 18 route files; em15 resident 3.86 -> 1.14 MB |
| W2 | Register the enemy modules | Patch ready (em15/26/28/21, slot audit). Held: +282 KB image comes out of heap 4, lands with W4 |
| W3 | First r101 entry fixture and measured census | Entered r101, then HALT: heap 4 short (s30 event 2.37 MB; em15 motion keys). Census: room archive 5.47 MB = 62% of heap 4 |
| W4 | Fit r101 memory and VRAM | In progress: ~1.2 MB short after dropping cutscene assets. Levers: event code without cutscene assets, room archive GC-render payload release, em15 hot motion |
| W5 | r100 events | Not started |
| W6 | Door lifecycle: relink-overlap hazard, module .bss reset, ARAlloc reset, KOS headroom | Done (a575a76): r100->r100 relink round trips repeat with 0 heap/VRAM/KOS change; 0 ms. Reload/continue hangs in SndRoomBgmLoad until audio lands (W12) |
| W7 | r101 events with FMV presentation | In progress (PS2 FMV, ROUTE_MOVIES=1) |
| W8 | r101 -> r103 | Not started |
| W9 | r101/r103 scenery packages | In progress (converter generalised to r101/r103; drops ~2.05 MB of GC geometry from heap 4) |
| W10 | GDEMU image | Not started |
| W11 | Inventory backing and retry | Not started |
| W12 | Audio (music and sound effects) | In progress (AICA SFX + music) |

## Working rules carried forward

- Shared checkout: never broadly stage, reset or clean.
- Commit only reviewed owned hunks. The 75 inherited dirty files stay as
  they are.
- Private assets and evidence stay out of Git.
- Use new evidence directories; never overwrite accepted evidence.
- Toolchain: KOS `kos-re4dc-d336` with GCC 15.2.
