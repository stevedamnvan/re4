# r101 diagnostic render checkpoint

The village renders on the Dreamcast. This is a **diagnostic** build, not an
accepted port of r101: it has no enemies, no events, no door progression, no
authored camera, and it does not hold 30 FPS. A known rendering mismatch in the
strip fallback path is still unresolved and is reported below rather than
waived.

## What was wrong, and what the evidence was

The first r101 boot did not reach a frame. The guest's `printf` does not reach
the capture, telemetry does not exist before the first frame, and an unhandled
exception reboots the machine and clears `.bss`, so every failure looked the
same from the host: silence.

Three instruments closed that gap, and all three are kept.

* `g_room_boot_stage`, a **volatile** word naming the installation step. The
  first attempt used `g_re4dc_demo_telemetry.flags`, which is an ordinary
  object: link-time optimisation sank and reordered those stores, and the
  observed order was wrong. That is why the word is volatile.
* `g_room_validate_progress`, the same for package validation, which runs
  before any frame.
* A handler on the processor exceptions (`EXC_DATA_ADDRESS_READ`,
  `EXC_DATA_ADDRESS_WRITE`, `EXC_ILLEGAL_INSTR`, `EXC_GENERAL_FPU`,
  `EXC_SLOT_FPU`, `EXC_INSTR_ADDRESS`) that records the code, PC, PR, TEA and
  EXPEVT and then stops, instead of letting the reboot erase them. It is
  registered per exception: the first attempt used
  `irq_set_global_handler()`, which also takes the timer interrupt, and the
  first thing it "caught" was an ordinary TMU tick.

With those in place the failure was ordinary and specific: **a scene without
actors was still reading packages it had never opened.** Four sites survived
the earlier `kSceneHasActors` pass:

| site | what it read |
| --- | --- |
| `leon_textures.upload()` | an unopened texture package |
| Leon/Ganado header allocations | `leon.header()`, `ganado.header()` |
| actor transform capacity check | `leon.header()`, `ganado.header()` |
| boot texture report | `leon_textures.header()`, `ganado_textures.header()` |

Each dereferenced a null header. No processor exception was recorded for them,
which is consistent with a TLB-class fault the handler is not registered for;
the reboot loop it produced was reproducible and is what the boot-stage word
localised, one step at a time, to the region between stages 39 and 40.

Two other things were also cabin-specific and are now shared by responsibility:

* `prepare_source_lights()`, `prepare_room_static_lighting()`,
  `prepare_room_primitive_bounds()` and `prepare_room_batch_locals()` sat
  inside `#if defined(RE4DC_SCENE_R100)`. They are room support, not encounter
  content, and now sit under `RE4DC_SOURCE_SCENE` with only the actor capacity
  check and the per-actor light-selection report gated on `kSceneHasActors`.
* `prepare-romdisk` copied the character packages unconditionally, so r101
  linked 1.9 MB of Leon into the binary's romdisk and held it in main RAM for a
  scene that never opens it. They are now optional, like the HUD and route
  packages, and the r101 target clears them. **ELF 5,820,384 -> 3,046,364
  bytes.**

## The render

Entry position is r101's own: point 0 of `r101_016.RTP`, at
(-51.1649, 0.500, 22.1509) metres. The camera is the existing follow camera and
is a **diagnostic camera** — r101's authored cameras in `r101_000.CAM` have not
been recovered.

`make r101-sweep` adds `-DRE4DC_DIAGNOSTIC_SWEEP`, an unattended driver that
walks forward eight seconds and turns for two, repeating. It overwrites the pad
so a capture needs no operator. It is a diagnostic driver, **not** recovered
gameplay, and it is a separate target from `r101`.

Captures in `d282-r4-r101-diagnostic/frames-sweep/` show the gate and path at
the entry, the village interior with houses, fences and scaffolding, and a
house approached closely. The viewer moved from (-51.16, 22.15) to
(-25.45, -2.36) with yaw 54.5 degrees under the existing SAT collision, which
kept it on the ground the whole way. 319 near-plane crossings were recorded
over the run.

r100 was rebuilt and re-captured from the same tree: it still renders the
cabin, Leon, the Ganado and the HUD.

## Memory: the loading peak, not the steady state

Package size and arena occupancy both understate what loading needs, because
`prepare_room_batch_locals()` still takes six bytes per **room** vertex from the
heap transiently, even though the tables it fills are bounded.

| | bytes |
| --- | --- |
| room arena capacity | 8,912,896 |
| room arena used / high water | 8,560,640 |
| bytes read from disc | 11,551,274 |
| free main RAM at boot | 5,296,128 |
| free main RAM after the packages | 5,230,592 |
| free main RAM after the derived tables | 5,230,592 |
| **free main RAM low mark** | **4,169,728** |
| batch-local installation scratch requested | 1,062,192 |
| binary `.bss` | 10,864,092 |
| binary text + data | 379,941 |
| KOS heap arena / used at runtime | 202,180 / 200,860 |
| PVR free before / after textures | 6,885,376 / 3,900,552 |

The loading peak is **1,126,400 bytes below the steady state** — of which
1,062,192 is the batch-local scratch and the rest is heap bookkeeping. Reporting
the 8,560,640 arena figure alone would have hidden a megabyte.

## Covered versus fallback work

The bounded accelerator tables do not cover all of r101, and the uncovered work
goes to the fallback path rather than disappearing:

| table | covered | r101 needs |
| --- | --- | --- |
| batch-local vertices | 2,696 batches, 54,274 vertices | 4,504 batches |
| primitive bounds | 16,384 | 54,129 strips |
| static lighting | 45,000 | 177,032 vertices |

Both the bounds and the lighting tables stopped exactly at capacity, which is
what partial coverage is supposed to look like. Visible geometry is preserved:
nothing is dropped for want of a table.

Per frame over the sweep (frames after 60): visible groups 148 / 396 / 1,440
(min/median/max), room triangles 3,426 / 12,996 / 91,752, median 5,261 direct
strips against 136 fallbacks.

## Frame times

Measured over the sweep, which deliberately walks into the heaviest views:

| | µs | FPS |
| --- | --- | --- |
| p10 | 24,698 | 40.5 |
| p50 | 80,175 | 12.5 |
| p90 | 255,991 | 3.9 |
| worst | 552,936 | 1.8 |

Validation of the 8,430,664-byte package takes 3,154,476 µs, dominated by the
payload CRC.

This is slow. It is stated as measured; no setting was changed to improve it,
and 30 FPS was not a precondition for this checkpoint.

## What is explicitly not done

* **The strip fallback mismatch is still unresolved.** Copying vertices out of
  the mutable cache immediately took the boundary test from 5/21 to 11/22
  identical stable frames. The remaining cause is not identified. Candidates
  not yet separated: primitive grouping, software culling, packet values, and
  the transparency-sort configuration. No emulator setting was changed to make
  a comparison pass. **This build is not promoted to fidelity acceptance.**
* Enemies, events and door progression in r101: unimplemented.
* r101's authored cameras: not recovered.
* Human gameplay acceptance and physical-hardware validation: not done.
* `room_strip_fallbacks` still combines geometric fallback with other reasons.
  Cache state is no longer one of them, but the counter is not yet split.

## Note on the fault handler

The exception handler stops the machine instead of letting it reboot. That is
better for diagnosis and worse for a shipped build, where a reboot is at least
a visible symptom. It stays for now because this milestone is diagnostic; it
should be reconsidered before anything is presented as finished.
