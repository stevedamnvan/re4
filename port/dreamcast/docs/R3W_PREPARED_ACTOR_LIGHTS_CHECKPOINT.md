# R3w prepared actor lights and Flycast cost-model calibration checkpoint

Date: 2026-09-20

Decision: **accepted.** Actor lighting now evaluates each normal against a
contiguous per-actor list of prepared light records instead of indexing the
source light table and the prepared-light table through the selection list on
every normal. The arithmetic is unchanged operation for operation; a gated
dual-path build compared every lit normal for 676 sampled frames and found
zero differing bits. Against R3v over matched simulation ticks 165-1194, CPU
frame p50 falls from 68.789 ms to 64.758 ms and p95 from 68.883 ms to
64.809 ms. No memory, package, geometry or telemetry layout changed in
production.

## Flycast cost-model calibration

This checkpoint was chosen from a measurement rather than a guess. Six
hand-written SH-4 loops of the form `op; dt; bf` ran 200,000 iterations each
under a gated build (`d251-flycast-calibration`):

| Loop body | ns per iteration |
|---|---:|
| `add #1, rN` | 10.0 |
| `fmul` | 10.0 |
| `fdiv` | 10.0 |
| `fsqrt` | 10.0 |
| `mov.l @rM, rN` | 20.2 |
| `mov.l rN, @rM` | 20.0 |

Flycast charges about 3.3 ns for any non-memory instruction, including
`fdiv` and `fsqrt`, and about 13.3 ns for a load or store. It models no
floating-point latency and no cache. Under this model a hot loop's cost is
its instruction count plus four times its memory-instruction count, which can
be read from the disassembly before a capture. `tools/sh4_loop_cost.py`
lists the backward-branch loops of named functions with that estimate. A real
SH-4 charges the opposite way: `fdiv` and `fsqrt` are tens of cycles and
cached loads and stores are one or two, so a change that reduces both is the
only kind this bench can validate for hardware.

Read against that model, the per-normal loop of `build_character_lighting()`
carried 325 instructions of which 81 were memory instructions on its longest
path. Most of the loads came from `kSourceLights[index]` and
`g_prepared_source_lights[index]`: two tables of wide records, indexed by a
byte read from the selection list, with the light type, colour, intensity,
position, direction and spot terms each loaded per normal per light.

## Change

`prepare_actor_lights()` copies each selected light once per actor per frame
into a `PreparedActorLight` record of fourteen floats and a type, in selection
order. `evaluate_prepared_actor_lighting()` walks that array with a pointer.
Its body is the previous `evaluate_selected_actor_lighting()` with the field
reads redirected and the three accumulators held as locals; every arithmetic
expression, comparison, clamp and early `continue` is the same and in the same
order, so the float results are bit-identical. `build_character_lighting()`
prepares the list, evaluates each normal, and writes the lighting floats and
the packed colour as before.

The reference evaluator is retained under `RE4DC_SUBMIT_PROFILE`, where the
build evaluates both paths for every normal and counts normals whose three
floats differ in any bit. That build also carries the calibration loops and
publishes their results in the profile telemetry. Production compiles neither.

The longest path of the new per-normal loop is 297 instructions with 66
memory instructions.

## Correctness

`d253-r3w-light-verify`: 676 sampled frames over simulation ticks 0-1711,
8,313 normals compared per frame (6,413 Leon, 1,900 Ganado), **0 mismatches**.
Because the lighting floats are identical, the packed colours and every
submitted vertex are identical; no framebuffer comparison is needed and none
was run.

## Matched Flycast result

| p50 unless stated | R3v | R3w |
|---|---:|---:|
| CPU frame | 68.789 ms | **64.758 ms** |
| CPU frame p95 | 68.883 ms | 64.809 ms |
| CPU frame p99 | 71.326 ms | 67.294 ms |
| actor lighting | 18.198 ms | 14.189 ms |
| Leon lighting | 13.960 ms | 10.948 ms |
| Ganado lighting | 4.232 ms | 3.235 ms |
| `submit_us` | 41.832 ms | 41.832 ms |
| opaque room | 25.320 ms | 25.320 ms |
| actor pose / normals / opaque draw | 5.820 / 1.831 / 11.789 ms | 5.820 / 1.831 / 11.789 ms |
| free main RAM | 5,324,800 B | 5,324,800 B |

Every stage other than actor lighting is identical to the microsecond, which
is expected when the emitted vertices are identical. Zero simulation overruns
and zero discarded simulation time. The 4.009 ms lighting reduction is
482 ns per normal; the static estimate from the memory-instruction count was
about 300 ns per normal, so the model under-predicts the gain but ranks it
correctly.

## Manual build

`d254-r3w-manual-smoke`: the manual ELF reached simulation tick 2,617,
sampled input 8,718 times with a 12.485 ms maximum gap, and reported zero
queue drops, simulation overruns or discarded simulation time. A first run
of this smoke was disturbed by a stray input to the emulator window and is
retained as `telemetry-disturbed-first-run.jsonl`; it is not used.

## Retained evidence

- `d250-r3v-loop-profile` — R3v gated loop profile, ELF
  `ed7df11a6f2adacc953736b75ee4ed00a2613c0ae94583d1520d68826ac26a17`
- `d251-flycast-calibration` — calibration loops, ELF
  `eaebdeaf08e36938ae7f2d4bd5d02bbb0739c54ac49d7c4c3006d70cd9719f1c`
- `d252-r3w-prepared-actor-lights` — accepted timing, ELF
  `1f49b029e61492419e6e0b75652ba68d34528b7353144c3a6c866b83d9e5fbf3`
- `d253-r3w-light-verify` — dual-path bit comparison, ELF
  `d0a5a99f4c52d6b85fdb53778c9d8e2e90a5dce96fbd3a367188606153759411`
- `d254-r3w-manual-smoke` — manual build smoke, ELF
  `fa036e868d40d224c5d1eff16a0536b509c8eac2d0e4524934e6db315f47d0e7`

## Limits

The calibration is of Flycast, not of a Dreamcast. The gain here is a
memory-instruction reduction, which hardware also rewards, but by less. The
per-normal loop still normalizes each of the 6,413 Leon entries although only
5,774 source normals exist, and still evaluates the position-dependent spot
and point terms per normal rather than per position; both are exact
restructurings left for a later pass. Physical Dreamcast timing remains
pending.
