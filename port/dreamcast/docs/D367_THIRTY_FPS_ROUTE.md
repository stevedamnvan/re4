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
| LG | 100 | LF + frontend30 + printf pass (f52746a). Hardware model: **158.1 -> 131.3 ms** (-26.8); Flycast work 95.8 -> 78.9. STRICT; safe under async present. Game30 knobs not yet included (integration run LH pending). |

Remaining work in LC is about 98 ms. It rounds up to 7 vblanks.

| Area | ms/frame |
|---|---|
| Game-side CPU | ~36 |
| Actors | ~21 |
| Scenery | ~19 |
| Memory copies | ~12-15 |
| Vblank pacing waste | ~19 idle |

## Hardware projection (SH-4 model, 2026-09-23)

The model: an interpreter-mode Flycast trace of LD, frames 2401-2520 (30 frames fully traced), replayed through an SH-4 timing model built from the Sega/SH-4 manuals. It covers pairing and latencies, the 8 KB I-cache and 16 KB D-cache with copy-back, miss penalties, the shared bus, and store queues. PVR/DMA bus contention is not modelled, so the figures lean low. Uncalibrated until console microbenchmarks run.

**LD work projects to ~158 ms/frame on hardware (137-187; quote 130-195) against ~96 ms in Flycast: real hardware costs about 1.65x Flycast.** That is ~4.7x over the 33 ms budget, not ~2.9x.

| Area | Flycast | HW nominal (range) | of which I-miss / D-miss |
|---|---|---|---|
| GC code on render thread (model/light setup, matrices, GX stubs) | 19.7 | 37.3 (31.6-44.9) | 8.3 / 2.0 |
| Actors | 20.6 | 34.5 (31.2-38.9) | 3.0 / 3.7 |
| Scenery | 17.7 | 31.4 (27.6-36.2) | 3.9 / 5.0 |
| Game logic | 15.5 | 25.8 (22.3-30.5) | 5.4 / 1.2 |
| UI / texture cache (native_ui.cpp) | 5.5 | 12.3 (10.0-15.1) | 2.3 / 0.5 |
| Copies | 10.9 | 8.3 (7.6-9.1) | 0.5 / 1.1 |
| TA submission | 4.0 | 5.0 (3.7-7.7) | |
| KOS | 0.6 | 3.3 | |
| **Total** | **~95** | **157.8 (136.7-186.6)** | 24.8 / 14.2 |

Ranked hardware levers:
1. copies, up to 8.75 ms;
2. direct store-queue vertex writes and movca.l staging, 7-8 ms;
3. instruction scheduling and FTRV in hot render asm, ceiling 28.8 ms, realistic 30-50% of it;
4. UI texture-cache O(1) handles, 8-10 ms;
5. fsrra, ~1.4 ms;
6. GC render front-end reduction, worth ~1.7x its Flycast gain.

Not worth doing:
- hot/cold link ordering (+1.2 ms worse);
- OC-RAM (net 1.4-3.2 ms);
- OIX (+17.8 ms; never enable it);
- pref in loops (0.4 ms);
- game-object data packing (at most ~1 ms).

Game logic alone is ~26 ms on hardware, so a 33 ms frame leaves almost nothing for rendering. See "Plan to 30 fps".

Tools: port/dreamcast/tools/hwmodel (24ba078). `hwproject.sh <dir>` projects any candidate in about 6 minutes.

Current stack (LF + frontend30 + UI_VRAM 2048 + tex-vq3) projects to **130.3 ms (114.7-151.1)** against LD's 157.8. Hardware keeps 172% of the Flycast gain.
By area: render-side 32.3, actors 31.1, scenery 27.2, logic 24.7, UI 8.5, copies 3.6, TA 0.3, KOS 2.5.

### D349 on hardware (hwmodel-d349)

D349 (5f42caa, the r100 autoplay prototype: reduced gameplay, sampled camera and animation) projects to **76.3 ms on hardware** (Flycast 53.4). It is not cheaper per unit of work:
- actors cost 2.69 hardware ms per 1k TA vertex records, against our 1.28;
- scenery costs 2.20, against our 1.42.

It draws less (0.87 MB TA/frame vs 1.40 MB) and runs almost no game logic, UI or GC front end. Those three are ~65 ms of our 130.

Not worth porting:
- its prepared actor lights (its most expensive kernel);
- its RAM-buffer-plus-copy packet path;
- AoS20 (already in our static path).

Worth porting (with estimated hardware savings):
1. prepared per-model records instead of the GC front end (-8 to -12).
   - **v1 landed as FRONT_NATIVE=1 (c881fba): -4.1 hw ms** (129.0 -> 124.9; band -3.7 to -4.6). ModelRender draws from only the state the bridge reads.
   - Proof: FRONT_NATIVE=2 compares every model part bit-exactly (0 mismatches over 349,713 parts); the logic trace is STRICT.
   - Ceiling: -11.8 if the whole model front end goes. Left for v2: per-TPL texture objects (~0.9), bridge build, and the HUD unitTrans O(n^2) scan (0.46).
   - Finding: effects are never drawn on DC. EspCommonTrans ends in a no-op GXCallDisplayList stub, so part of its ~1.5-2 hw ms is dead work. Most of it must be kept, because the bridge reads the m_Mat and ChannelSet colour results, so EFFECT_LEAN is estimated at only -0.4 to -0.6 hw ms (another -0.4 to -0.5 if nothing reads m_Mat).
   - Native effect sprites (the default and sub-rectangle sprite paths: fire, smoke, blood, sparks, muzzle flash, weather) are estimated at +0.3 to +0.5 hw ms in r100 (~200-230 sprites, ~20 KB TA) and +0.5 to +1.0 in an r101 fight (300-450 sprites). That's roughly cost-neutral with EFFECT_LEAN. Effect VRAM and translucent fill (large fog sheets, ~1.5 ms PVR each) are unmeasured. User decision pending.
   - Effect creation and movement draw from the shared game random-number stream, so logic-side effect caps break the STRICT trace. Only the draw side is safe to gate.
2. one straight per-part emission loop instead of the packet/defer layer (-5 to -6);
3. precompiled HUD headers (~-1.5);
4. a small grouped render hot path (-1 to -2);
5. ~~a per-frame transformed-vertex cache for scenery~~: measured at 0. The transform-once meshlets (02d5a0f) already realise it (24.4% of corners saved), and repeats across draws use different matrices. What's left is a converter-side position/attribute split, ~-0.5 to -0.8 ms, unmeasured.

## Work plan: serialized perf lane (2026-09-23)

Performance work is serialized: one integrated build, one change at a time.
- After each step, measure the stacked build with hwproject and Flycast, in the r100 quiet window and the r101 fight, reporting p50, p99 and max against the 50 ms target.
- Gains measured as separate arms overlap in the same frames, so only the stacked number counts.

| Step | Change | Status |
|---|---|---|
| 0 | FRONT_NATIVE v1, RELEASE_FLAGS | landed (c881fba, ecbea1f) |
| 1 | Texture preload per room, O(1) handles, no runtime CRC (movement hitches; crowd texture cost) | finishing |
| 2 | Game-logic cuts (game30 LH recipe, then tick cuts) | LH recipe + GAME_TRIG landed (7dd50e7, 28ef388): hw game-logic 25.8 -> **12.0 ms/tick**, inside the ~15 budget; frame 157.8 -> 120.3 hw. STRICT. Next, ranked: D-cache prefetch in the logic list walks (EmAtCheck, partsWorldCalc; ceiling -3.25), EmAtCheck prefilter (<1), Hermite/vector maths (~0.5). Skip: I-cache relink (makes it worse), reciprocal fdiv (not bit-exact). Visual sims stay: cloth and pendulum write the parts chain; effects share the RNG. |
| 3 | Enemies: Leon <=5 ms, CROWD_LOD tiers, ACT_CAP, safe cuts (FX_LEAN, static car/cops; gore kept), Leon fewer-bone rebuild, low-poly Ganado meshes | queued. actors30-v3 ready: NATIVE_ACTOR_SKIN_LAZY also fixes a 128 KiB prim-buffer overflow that made Leon vanish with 6+ Ganados. Per Ganado: 7.4 hw ms full, 4.5 with tiers. Any Ganado in view also adds ~93 hw ms of texture CRC/reload, which is step 1's fix. Logic trace STRICT at 4 and 8 Ganados. |
| 4 | Render front end: EFFECT_LEAN, EMIT_DIRECT, FRONT_NATIVE v2 | queued |
| 5 | Scenery: fog distance, tree cap, house from halfway, W9 worst views and per-room fog | queued. Trials done: 25 m far plane (room's own curve) is scenery 29.9 -> 18.7 hw ms, frame 158.3 -> 140.1. 20 m fails the enemy rule (a Ganado at 20 m is 100% fogged). Rule for other rooms: min(room far, 25 m). House from halfway (~21 m) needs per-object building fog: open. LOD 5 px (-2.9 at 42.7 m) and TREE_THIN are unmeasured on top. |

Parallel tracks (off the frame path; needed for the console gate):
- r101/r103 bring-up (frontier W4, W9 packages);
- audio;
- cutscenes;
- inventory/retry (W11);
- GDEMU disc reads (W10).

Asset exploration (PS2/Blender) is parked after the house images.

## 20 fps hardware budget (2026-09-23)

Game logic is a fixed 30 Hz tick: one update per frame (main.cpp, 2 vsyncs), with no delta-time scaling; only pad repeat timers use GetSystemVcnt. Rendering at 20 fps at the correct game speed therefore needs 1.5 logic ticks per rendered frame, so logic is a fixed per-second tax whatever the frame rate. At the modelled 25.8 ms/tick, logic alone is 77% of the CPU.

| Area | HW now (LD) | 20 fps budget (50 ms) |
|---|---|---|
| Game logic | 25.8 / tick (38.7 / frame) | ~15 / tick (22.5 / frame) |
| GC render front-end | 37.3 | ~3 (replace it; don't trim it) |
| Actors | 34.5 | ~7 (Leon full, Ganado tier + crowd rules) |
| Scenery | 31.4 | ~8 (shorter fog, coarser LOD, impostors, house shells) |
| UI / texture cache | 12.3 | ~2 (O(1) handles) |
| Copies + TA + KOS | 16.6 | ~7.5 |

User decisions (2026-09-23):
- **Approved:** shorter fog/draw distance, ~43 m -> 20-30 m ("most of the game is outdoors"). It must never hide an enemy within engagement range; trials pick the distance.
- **Approved, "more drastic":** Ganado crowd rules. Near 2-3 full detail; mid tier about 1/4 vertices, rigid parts, skinned every other frame; far tier a few hundred triangles, skinned every 3rd-4th frame. Leon always full; threats are never culled.
- **Closed, not possible:** visual-only simulations at half rate. Cloth and pendulum write the model parts chain, which feeds hit and attach points, and effects draw from the shared game random-number stream, so both change game state.
- **Decided (2026-09-23):**
  - Fog: 25 m confirmed ("34% fogged at 20 m seems right"). For reference, PS2 draws r100 to 78.9 m (EXP fog, end 263 m, ratio 0.70) and r101 to 38.4 m in most cuts; GC draws 42.7 m and 70 m.
  - House appearance: ~40% of the approach under the 25 m wall is fine; no per-object building fog.
  - Simplified house shells (item 21, MESH_TEXTURES=1): the mid mesh with a 512 VQ texture (66 KB per house), used everywhere with no near swap. -0.71 hw ms for FILE_01/17+18; ~-1.6 to -1.8 projected for all FILE_01. Step 5.
  - Effects: bring back native sprites for muzzle flash, blood and fire (+0.5 to 1.0 hw ms), together with EFFECT_LEAN. Step 4.
  - Cutscene subtitles: no, for now.
  - **Low setting mode (requested 2026-09-23):** a pre-game debug-menu toggle (Normal / Low, plus per-feature switches) that turns on the aggressive options: full replacement of the GC model drawing path, the Leon rebuild plus low-poly Ganados, and occlusion.
    - Normal targets 20 fps; Low pushes toward 30 fps (33 ms hw).
    - The switches are runtime, not compile-time. Only the selected asset set is resident. The logic trace is STRICT across modes.
    - In design at /root/probe/d367-agents/design-lowmode, design-scenery and design-ganado.
  - Outlook: all planned work lands at ~50-65 hw ms in quiet views, so 20 fps is the target. 30 fps would need every area near its floor at once.
  - **Low mode decisions (2026-09-23, design at /root/probe/d367-agents/design-lowmode):**
    - Estimates: Low is worth -2 to -4.5 hw ms quiet and -7 to -13.5 in r101 fights. It's a safety margin, not 30 fps.
    - The full native model path (-9 to -13 hw ms, bit-exact, records held in the existing 64 KiB slab) is ON in Standard.
    - Heavier Low levers approved: flat Ganado lighting; a draw-side crowd rule; a scenery-only cull at 18-20 m, with the fog kept at 25 m, only if it doesn't visibly pop.
    - Decided 2026-09-23: crowd rule **N=2** (the nearest 2 Ganados at near/mid detail, the rest at the far tier, none hidden; 8-Ganado fight 31.5 vs 32.1 hw ms at N=6, design-ganado 08). **FTRV render maths: yes** (render-only transforms; the logic trace stays STRICT). **Flat Ganado lighting: yes**, default in Standard (~-5.8 hw ms in the 8-Ganado fight, model estimate; verify on the hw model). **Heads always detailed: no** (heads follow the body's L1/L2 level).
    - A Low effect draw cap (draw side only): yes.
    - Thermal scope, self shadow and cast shadow stay in the build.
    - The quality choice is remembered on the VMU.
    - Picker: once per boot, at the first title main menu, in the game's message window; per-feature submenu in test builds only.
    - Leon's face bones: PS2 FMV replaces most story cutscenes, so merge them always in Low, unless a route event still in-engine shows Leon's face up close (being checked).
    - Occlusion at the 25 m fog is ~0.1 hw ms for 32.7 KB heap: dropped unless the final scenery design shows more.
  - A bottom-up estimate puts Standard at ~73 hw ms quiet / ~80 in the r101 fight, above the earlier 50-65 outlook. Stacked step 3-5 measurements will settle it.
  - **Gore stays** ("keep gore don't remove it"): CUT_GORE (r103 corpses and the r100 gore object via the JP path) is rejected and must not enter the recipe. That route now relies on the r103 corpse constructor alias (55c0a5b). Safe cuts are down to FX_LEAN (foot shadows, about 0.1 ms). Particle/decal caps aren't possible (shared RNG), and screen filters stay (about 0 ms; some set game flags).
  - Added to the lane: outdoor occlusion/PVS (hide houses and trees behind buildings; est. -3 to -6 hw ms in r101/r103), step 5. Leon render rebuild with fewer skinned bones (render skin weights only; the game skeleton, attach points and hit zones untouched; ~5-6 -> ~3 hw ms), step 3. Lower-poly Ganado render meshes (heads kept), step 3.
  - **Rejected:** reduced animation/skin update rates for any actor ("might throw off gameplay"). Crowd tiers vary geometry and shading only; every actor's pose updates every frame. This supersedes the earlier "skinned every other/3rd-4th frame" crowd tiers.
- **Enemy/object census (aligned):**
  - Take the SAFE cuts: r103 corpses and the r100 gore object off via the JP path (CUT_GORE); effect and decal caps; no foot shadows; car and police props static.
  - Cap concurrent active Ganados in r101 (ACT_CAP, N=4/6/8 trials, ~12 hw ms estimate). Parked Ganados stay alive for every counter; engaged or visible threats are never parked.
  - Never cut: the r100 s03 Ganado; ESL entries 3/4/5 and 0x25; any r101 initial Ganado; the r101 kill/timer/wave logic; linked breakables.
  - Don't remove wave members: phantom kills (5 per wave) would shorten the fight.
  - Found alongside: with 10 Ganados on screen, texture_package.cpp costs 71.5 ms/frame in Flycast. It goes to the texture-hitch fix (preload per room, O(1) handles).

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
| 12 | Game CPU: SH-4 matrix kernels, rotation cache, -O2 on hot objects | game-side 13.9 -> 9.7 (wall 116.8 -> 100.1) | logic 25.8/tick on hardware (model); target ~15 | Done (6e79b70), STRICT. Next: bit-exact faster math, visual-only sims off the tick |
| 13 | FP 6B (contract-off + FDLIBM; render-only objects exempt) | ~0 | ~0 | Done (6e79b70), user-approved float-only drift; new STRICT baseline |
| 14 | Memory-copy audit (~15 ms) | -7.5 (COPY_LEAN) | more (cache thrash) | Done (de03f28); validating on LF |
| 15 | GC render front-end removal (objTrans, light setup, normal matrices, draw-plan walk) + direct TA meshes | -6.4 (FRONT_LEAN) -3.6 (MESH_DIRECT) | similar | Done (de03f28); validating on LF |
| 16 | UI VRAM diet -> 2 MiB vertex bank | 0 | required: r100 needs ~1,031 KB of TA params per frame, overflowing 1024 KB | Done (700e2d0, UI_VRAM=1 + TA_VERTBUF_KB=2048 + tex-vq3) |
| 17 | Hardware projection model (pairing + I/D-cache simulation) | - | LD = ~158 ms on hardware (1.65x Flycast) | Done; see Hardware projection |
| 18 | fsrra, movca.l staging, SQ-direct writes, instruction scheduling (OC-RAM and pref dropped by the model) | ~0 in Flycast | fsrra -1.4, SQ/movca.l -7 to -8, scheduling up to -29 ceiling | Assigned (frontend30 pass 2, actors) |
| 19 | I-cache hot/cold code layout | ~0 in Flycast | model: +1.2 ms worse; ideal packing only -1.8 | Dropped (the per-frame code footprint of 216 KB is the problem, not layout) |
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

## Controls (done: e024e19, 0a33d0c)

Standard pad:
- Stick, A, B, X, Y, Start, L and R map directly, with the GC PADClamp ranges.
- In free movement the D-pad is camera look, and a short tap of D-pad down is Z (map).
- In scope or binoculars, D-pad up/down zooms.
- In menus, aiming and QTEs the D-pad is the D-pad.

Dual-analog pads use the second stick as the C-stick, and C/Z as Z.

Debug traps (L+Start, Z item-maker) are blocked unless DEBUG_PAD=1.

0a33d0c fixes stick aiming on little-endian targets. Before it, only the D-pad aimed.

The glyph swap for Z/C-stick prompts is still to do. No Z or C-stick glyph textures exist; wording is spelled out in the message tables. The A/B/X/L/R/stick glyphs are in core.das #25 and the ss_map/ss_cmmn/ss_cap hint strips.

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
| W7 | r101 events with FMV presentation | Working in Flycast: the r120 intro and r100 s40 play as 288x192 PS2 movies with audio; the source effects apply and gameplay continues (c6). Open: only 14-15 of 29.97 fps shown; s03/s20/s30/s41/s43/s44 not yet exercised; 57 KB heap margin during s40 |
| W8 | r101 -> r103 | Not started |
| W9 | r101/r103 scenery packages | Tooling done (`convert_room_bins.py --smd`, `room_smd.py release`, `ps2_trees.py --room`; recipe in `tools/d367/README.md`). Packages: r101 1.27 MB with the PS2 trees, r103 1.39 MB. The release frees 1.59 MB (r101) or 1.55 MB (r103) of GC geometry from the room archive, a net +0.32 MB (r101) of heap 4 after the package. With it, r101 gets past the em15 motion-key HALT and renders in Flycast (evidence `w9-r101-native-released-m2`); the unreleased control still halts. Model estimate (worst view, 70 m fog far): 67-71k strip vertices, 19-25 ms hardware, so over the 10 ms budget; median 7-10 ms. Flycast ms/frame not measured yet: the fixture's present counter stalls in r101 |
| W10 | GDEMU image, disc IO | GDI boot done (93a03e3). MOTION_FAST_READ (a09fd4d): r100->r100 door 24.1 -> 16.0 s on the old recipe. IO_PROBE telemetry + fs_read/fs_open/genwait wraps: on the old recipe the other ~10 s was 63 texture-package fs_opens (~159 ms each, iso9660 rescanning the flat tex directory), which the LFV recipe's TEX_RESIDENT fan-out already removes. LFV + MOTION_FAST_READ: door 6.8 s, of which 2.7 s is 575 misaligned 16 KiB-bounce texture preload reads, 0.9 s source DVD, 0.6 s opens, 0.3 s motion. Hardware-safe design (design-doorload/DESIGN.md): Flycast's door says little about hardware (~2,000 mostly single-sector GD commands, 12.1 MB); estimated today GDEMU 8-17 s, GD-ROM 20-40 s. Queued units: IO_PROBE counters + door summary, TEX_KEEP (textures resident across a room change; Flycast 6.85 -> ~3.4 s), aligned static-mesh reads, DVD wait/reopen fixes; then per-room texture and motion packs, and a GD-ROM disc layout. Target GDEMU ~5-9.5 s. Async/read-ahead and GD-DMA into VRAM rejected |
| W11 | Inventory backing and retry | SUBSCREEN=1 landed (8878e3d, le_mirror formats 153dd7b): inventory/transceiver open and close over a saved 3 MiB backing window. Grey-screen root cause fixed: room demand pools (cEm/cParts/cModelInfo/cObj) had headers inside the zeroed window, and EmMgr growth wrote a heap cell into .text; the pools are now frozen at open and thawed at close. r100 x3 open/close on the m1 recipe + TEX_RESIDENT (w11-ss17-m1-inv3): hashes ok, no HALT, heap 4 and player state identical, ~88 ms/frame before and after; ~1.4 s texture re-preload per close. The .text-change flag was KOS's IRQ temp stack below irq_save_regs (benign, present before any sub screen; w11-ss18-m1-textdiag). Open: ROUTE_MOVIES halt at main.cpp(548) ~3600 vblanks into the r120s00 intro (cause: the 60 s haltExecCheck during long movies, wedging the b50cfa3 YUV path; port-side fix in review). Death/Continue x3 in r100 passes on the m1 recipe (08d51b9 fixture; w11-ss20-m1-die3): heap 4 flat, VRAM 0, BGM restarts, player state identical. Open: r101 death (needs the movie route), VMU save (design running), merchant, r101 inventory, ~175 KB SUBSCREEN image cost |
| W12 | Audio (music and sound effects) | Backend committed (79d3252, AICA_AUDIO=1): GC sequencer + SFX engine on the AICA, ~0.2 ms/frame, fixes the continue hang. Next: offline bank conversion (5.3 s load-time CPU today), fixed per-room AICA layout, st002/st008 streams |

## Working rules carried forward

- Shared checkout: never broadly stage, reset or clean.
- Commit only reviewed owned hunks. The 75 inherited dirty files stay as
  they are.
- Private assets and evidence stay out of Git.
- Use new evidence directories; never overwrite accepted evidence.
- Toolchain: KOS `kos-re4dc-d336` with GCC 15.2.
