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

| Unit | Work |
|---|---|
| W0 | Frozen private baseline |
| W1 | Extract route files from the debug ISO; build r101/r103 DARs; compact em15/26/28/21 |
| W2 | Register the enemy modules |
| W3 | First r101 entry fixture and measured census |
| W4 | Fit r101 memory and VRAM |
| W5 | r100 events |
| W6 | Door lifecycle: relink-overlap hazard, module .bss reset, ARAlloc reset, KOS headroom |
| W7 | r101 events with FMV presentation |
| W8 | r101 -> r103 |
| W9 | r101/r103 scenery packages |
| W10 | GDEMU image |
| W11 | Inventory backing and retry |
| W12 | Audio (music and sound effects) |

## Working rules carried forward

- Shared checkout: never broadly stage, reset or clean.
- Commit only reviewed owned hunks. The 75 inherited dirty files stay as
  they are.
- Private assets and evidence stay out of Git.
- Use new evidence directories; never overwrite accepted evidence.
- Toolchain: KOS `kos-re4dc-d336` with GCC 15.2.
