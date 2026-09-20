# r100 R0 input-service checkpoint

Recorded 2026-09-20 after the R1c static room-lighting checkpoint. This change
keeps gameplay and simulation single-owned by the main thread, but samples the
Dreamcast controller from a small normal KallistiOS thread while a long frame is
being prepared and submitted.

## Scheduling and ownership

The service polls in normal thread context and sleeps between polls. It does not
call Maple from an interrupt and never changes player, enemy, camera, collision,
or render state. A mutex-protected 128-entry ring retains timestamped input-state
transitions. The fixed 30 Hz simulation consumes transitions through each tick's
wall-clock boundary and applies a rising fire, reload, restart, or exit edge at
most once.

A press and release observed between two simulation ticks is latched for the
next eligible tick. A fire edge also retains the aim state captured with that
edge. If simulation time is deliberately discarded by the existing bounded
catch-up policy, input transitions in that discarded interval update held state
but are not replayed late as gameplay actions.

Telemetry ABI version 6 adds queue depth, queue drops, and delivered-edge
counts. The existing sample count and gap fields now describe the service poll
stream in manual builds. Autoplay does not start the service and retains its
tick-indexed input path.

## Flycast measurements

The manual comparison uses the same 640x480 r100 package and nearly identical
render cost before and after the service.

| Measure | R1c render-loop sampling | R0 input service |
|---|---:|---:|
| Median input sample gap | 251.947 ms | 9.981 ms |
| Maximum observed sample gap | 343.410 ms | 12.484 ms |
| Median render work | 249.229 ms | 249.445 ms |
| Queue drops | not applicable | 0 |

The service reduced the median observation gap by about 25 times without a
measurable render regression in this emulator comparison. The final manual
trace contained 56 coherent telemetry-v6 samples and reached 1,416 controller
polls with no queue overflow or discarded simulation ticks.

Private manual evidence, ELF SHA-256
`5ec51dab508e20f1caf753dbca95c4673ae0c0d6a5d390fcf75ae9f1a90c182f`:

`C:\Flycast-Evidence\re4-dreamcast\d133-r0-threaded-input-manual`

## Short-edge test

A virtual Xbox controller was explicitly routed to Dreamcast port 0 for this
test. It held aim, pressed fire for 50 ms, and released aim. The entire pulse was
shorter than the roughly 249 ms render interval. Telemetry recorded exactly one
delivered edge, zero queue drops, and ammo changed from 6 to 5.

Private evidence:

`C:\Flycast-Evidence\re4-dreamcast\d137-r0-short-input-edge-routed`

The first two virtual-pad attempts were invalid because the virtual device was
assigned to Dreamcast port 1 while a physical controller occupied port 0. They
are retained as negative routing evidence in `d134` and `d135`; they are not
input-service failures.

The autoplay regression retained ammo states 6 through 2, enemy-health samples
365/230/95/0, and zero discarded simulation time. Its ELF SHA-256 is
`0e1d4faaca28477fbf048d65f2427f9ad01568eb282153903c747f81f0a557ba`:

`C:\Flycast-Evidence\re4-dreamcast\d136-r0-threaded-input-autoplay-regression`

## Acceptance boundary

This closes target-side capture of short manual transitions during long render
frames. It does not make the current 3.8 fps output feel like a real-time game,
prove the original GameCube input-sampling policy, or validate scheduling and
Maple behavior on stock Dreamcast hardware. Manual aim, movement, reload,
death, disconnect, and repeated-retry acceptance still need a human controller
run, and physical-hardware timing remains separate.
