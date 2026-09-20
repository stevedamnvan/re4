# r100 R3l source character assembly checkpoint

Recorded 2026-09-20 after the R3k room checkpoint. This checkpoint corrects
visible character assembly defects reported from the accepted room capture. It
changes no room geometry, camera, lighting, collision, or gameplay timing.

## Source assembly recovered

`cPlLeon::setModel` does not define one monolithic Leon mesh. For the starting
costume it creates the body, costume, morphable head shape, hair, eyes, a
normally zero-scaled face-expression overlay, and replaceable hand models.
`cObjMauser::setMotion` supplies the Red9-specific right hand and selects left
hand 4. After accounting for the DRS four-entry header, the handgun slice now
converts:

| Visible component | Model source | Texture source |
|---|---|---|
| body | `pl00.drs` entry 0 | `pl00.drs` entry 1 |
| costume | `pl00.drs` entry 6 | `pl00.drs` entry 1 |
| head shape | `pl00.drs` entry 4 | `pl00.drs` entry 3 |
| hair | `pl00.drs` entry 2 | `pl00.drs` entry 3 |
| eyes | `pl00.drs` entry 5 | `pl00.drs` entry 3 |
| Red9 right hand | `wep02.drs` entry 6 | `pl00.drs` entry 13 |
| Red9 left hand | `pl00.drs` entry 20 | `pl00.drs` entry 13 |
| Red9 | `wep02.drs` entry 2 | `wep02.drs` entry 1 |

The converter now permits a component model and its texture palette to come
from different archives. The earlier build incorrectly used Leon's default
hands and flattened the zero-scaled expression overlay as an always-visible
mesh. The latter produced the apparent extra blade/limb. The neutral handgun
slice now omits that overlay because the source initializes all three of its
blend scales to zero; expression-state integration remains open.

`Model::CullMode` initializes to zero and `commonModelTrans` maps that state to
source front-face culling. The old Dreamcast path culled the opposite winding,
exposing the front facial layer through the back of Leon's head. Both direct
PVR strips and clipped CPU triangles now use the source-facing cull direction.

The type-0 Ganado is also assembled dynamically. For the current right-handed
hatchet, `em10HandSet` selects the weapon-grip right hand and relaxed left hand.
The previous package combined that right hand with the mirrored weapon-grip
left hand. The package now uses `em12.drs` entries 447 and 449 with the source
hatchet on part 10.

## Validation

All 48 host tests pass, including the new cross-archive attachment parser
case. The SH-4 r100 autoplay ELF builds successfully.

The short matched capture and gamma-lifted inspection sheet show the corrected
rear hair/scalp, continuous jacket and arms, one handgun, no expression-overlay
artifact, and complete Ganado body/hand silhouettes through aim, fire, hit,
death, and recovery poses. A second 32-frame capture spans the complete
30-second autoplay cycle and shows no recurrence.

Evidence:

- focused capture: `C:\Flycast-Evidence\re4-dreamcast\d198-r3m-source-cull-hand-fix`
- full-route capture: `C:\Flycast-Evidence\re4-dreamcast\d199-r3m-source-cull-hand-fix-30s`
- bright full-route sheet: `C:\Flycast-Evidence\re4-dreamcast\d199-r3m-source-cull-hand-fix-30s\bright-30s-contact-sheet.png`
- Leon package SHA-256: `1eb569b8561fa905762086d959b5f928cc0a860e1486ebd4166282e91a4eb9b3`
- Ganado package SHA-256: `a53c3b43aae31d3871c4a5814cca32278d9c351e3bf8d9959eaee625b86faf6d`
- accepted ELF SHA-256: `c5ae9de436fd7b9f3770ce3e7cc40d1f37b8e2c000b3b9dfb9be5d46ce7c0e68`

## Acceptance boundary

This accepts the visible source-authored component set for the current neutral
and handgun encounter states. It does not claim the full source character
system is complete. Runtime face-expression overlays, source hair/jacket cloth
simulation, eye behavior, all weapon/hand swaps, damage variants, and physical
Dreamcast validation remain open. Brightened sheets are inspection aids only;
the accepted render uses the source-derived room lighting.