# One-Ganado combat P2 baseline

This checkpoint completes the smallest playable combat loop in the native
Dreamcast target. It combines disc-derived room, collision, Leon, and Ganado
data with a bounded translation of the source enemy state machine. It is a
Flycast acceptance checkpoint, not a stock-Dreamcast performance result.

## Source and asset mapping

The generic village enemy is `em10`. The source setup selects body arc `0x1bc`
for the ordinary male variant, which is archive entry 440 after the archive's
four-entry numbering offset. The private package contains 770 vertices, 1,460
triangles, five material batches, and these source clips:

| Runtime state | Source arc | Archive entry | Source use |
| --- | ---: | ---: | --- |
| Idle | `0x05` | 1 | `em10SetWaitMotion` default |
| Walk | `0x08` | 4 | `em10SetWalkMotion` plain walk base |
| Attack | `0x86` | 130 | forward bare-hand Catch lunge |
| Hit | `0x2e` | 42 | one front head-hit stagger variant |
| Death | `0x69` | 101 | walking knock-out/collapse |

The generated package is 2,457,652 bytes and has SHA-256
`d81463cf4dee5ae664ee4cc2fde7fc8e3f5a7c8194494f3659aeb44daeb15c3a`.
It remains ignored with every other disc-derived artifact.

The runtime follows the source's high-level `Move`, `Damage`, and `Die` split.
Its chase turn limit comes from the walk routine's 0.15707964 radians per
30 Hz frame. The normal bare-hand attack choice, lunge motion, damage reaction,
and walking knock-out are directly mapped to their `em10` routines.

## Deliberate demo bounds

This is a compact translation of the exercised paths rather than a linked copy
of the full enemy module. Navigation uses direct pursuit on the converted SAT
floor. The original route graph, obstacle actions, random walk variants,
weapons, grabs, parasites, sound, effects, and rank logic remain out of scope.

The source bare-hand catch check uses a 1.1 m range. The demo starts its attack
at 2.4 m because it applies one timed 25-point strike instead of synchronising
the complete two-actor grab. Enemy health is three aimed hits rather than the
room ESL's 1,000-unit value. The inserted enemy is the ordinary `em10` village
variant; r10d's original stage-one ESL entry is enemy id `0x18`, so this is an
intentional combat-slice insertion and is not described as the room's original
encounter.

The player uses a six-round demo magazine, a one-second reload, a horizontal
aim cone with movement held while aiming, 100 health, and a 35 m shot limit.
These values make every required
state visible in one short loop; they are not asserted as final weapon-balance
parity. Models remain flat shaded and omit the handgun, hands, head attachments,
textures, weapon effects, sound, and paired grab animation.

## Controls and loop

- Stick or D-pad: tank movement and turn
- Right trigger or Y: aim and show the reticle
- A: fire while aiming
- X: reload
- B: restart the encounter
- START: clean exit

The exit marker is red until the Ganado dies and green afterward. Reaching it
increments the loop count and resets Leon, the enemy, health, and ammo.

## Flycast evidence

The retained evidence is
`C:\Flycast-Evidence\re4-dreamcast\combat-p2-final`. Its deterministic input
path used the same runtime controls and deliberately:

1. allowed the enemy attack to kill Leon;
2. restarted the encounter;
3. fired the magazine empty away from the target;
4. reloaded, aimed, and fired three hits;
5. traversed SAT collision around the room wall endpoints; and
6. crossed the unlocked marker and reset the encounter.

Live SH-4 telemetry ended at phase 7 with flags `0x7`, loop count 1, restored
player health 100, and ammo 6. The emulated VMU independently contains:

```text
RE4DC_AUTOPLAY_PASS death=1 reload=1 loop=1
```

The evidence manifest validates all retained inputs, including the private
character packages, executable, telemetry snapshot, Flycast log, and VMU
image. This proves the deterministic loop in Flycast. A manual controller
usability pass, stable 30 fps, texture readability, GD-ROM or ODE packaging,
and stock Dreamcast execution remain open P3 gates.
