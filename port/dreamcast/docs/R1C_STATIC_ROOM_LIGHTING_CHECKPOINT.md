# r100 R1c static room-lighting checkpoint

Recorded 2026-09-20 after the R2a SAT hierarchy checkpoint. This change keeps
the source-selected light set and full room geometry, but evaluates the fixed
world-space portion of room lighting once at startup. Each frame still applies
the two view-relative directional lights after the source camera basis changes.

## Preserved calculation

The startup pass uses the same room ambient, prepared light constants,
per-source-object masks, and volume selection as the prior renderer. It stores
unclamped RGB floating-point partial sums for each source render vertex. The
runtime adds only the selected view-relative contributions, then performs the
same final clamp and 8-bit color conversion. Static partials are not clamped
before the dynamic contribution is added.

The preparation pass validates group, batch, index, and vertex ranges. If one
render vertex is shared by source groups with different selected-light masks,
the build fails at startup instead of reusing an invalid result. This r100
package has 40,419 vertices and satisfies that ownership rule.

## Correctness comparison

A one-frame verification build evaluated both the prior complete calculation
and the split calculation for every room-cache miss at the initial source
camera. All 28,959 final packed vertex colors matched, and the maximum measured
floating-point channel error was zero. Private verification evidence is in:

`C:\Flycast-Evidence\re4-dreamcast\d130-r2b-float-static-light-verify`

A measured Q12 fixed-point experiment reduced the cache footprint by about
265 KiB, but changed 2,893 of 28,959 packed colors by one 8-bit level. It was
rejected for this accuracy-first slice. A 4,096-entry group-local transform
cache also failed to improve frame time while consuming about 196 KiB, so it
was removed rather than committed.

This comparison proves equivalence to the preceding Dreamcast lighting
calculation at the checked camera. It does not replace the still-pending matched
original-game selected-light and image trace.

## Flycast result

The comparison uses the same native 640x480 r100 room, camera, geometry,
textures, source-selected lighting, actors, collision, and autoplay route. The
R2a baseline and R1c candidate are emulator measurements, not physical
Dreamcast timings.

| Measure | R2a full per-frame room lighting | R1c prepared static lighting |
|---|---:|---:|
| Median render work | 300.691 ms | 264.602 ms |
| Median opaque room work | 145.308 ms | 120.723 ms |
| Median translucent room work | 50.158 ms | 38.116 ms |
| Main-RAM free telemetry | 1,658,880 bytes | 1,077,248 bytes |

The median render interval fell by 12.0%. Combined opaque and translucent room
work fell by 18.7%. The resulting median remains about 3.78 rendered frames per
second, far from the 30 fps acceptance target. The float cache costs 581,632
bytes of reported main-RAM headroom.

The final autoplay package retained ammo states 6 through 2 with no discarded
simulation time. The preceding equivalent float-cache trace also captured the
complete enemy-health progression 500/365/230/95/0. Private evidence:

- final autoplay telemetry, ELF SHA-256
  `dc15ade928e43e736a794345e9313576b4f0d68c90ffc0238f38a50763bde750`:
  `C:\Flycast-Evidence\re4-dreamcast\d131-r2b-final-static-room-lighting`
- final manual package, ELF SHA-256
  `31dfb6969fdba1da902ebb86040a52b1afec748542dbf77d2f5340687d0ca794`:
  `C:\Flycast-Evidence\re4-dreamcast\d132-r1c-final-manual`

The manual trace contains 36 coherent telemetry-v5 samples from simulation
ticks 18 through 284. Its autoplay flag was clear in every sample and it
discarded no simulation ticks or microseconds.

## Acceptance boundary

This closes reuse of the current fixed world-space room-light contributions.
It does not close R1b source-fidelity acceptance, actor lighting, original-game
light ordering, stock-hardware timing, peak transition memory, or the 30 fps
target. The next rendering work must address the measured actor preparation and
submission costs or native room packet/visibility work without changing the
authored camera or visible content.
