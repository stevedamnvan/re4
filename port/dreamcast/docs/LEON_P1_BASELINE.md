# Disc-derived Leon P1 baseline

This checkpoint replaces the orange player marker with a flat-shaded animated
mesh derived from the locally supplied RE4 debug Disc 1. It advances the
playable-demo path, but it is not the combat-loop or stock-hardware gate.

## Source mapping

The source code removes the ambiguity around motion names:

- `pl00.drs` entry 0 (`PL_ARC_PTR(..., 4)`) is Leon's primary body model.
- The starting handgun module is `wep02`.
- `wep02.drs` entry 7 (`WEP_ARC_PTR(0x0b)`) is the idle motion assigned to
  `pMotTbl[0]`.
- `wep02.drs` entry 13 (`WEP_ARC_PTR(0x11)`) is the walk motion assigned to
  `pMotTbl[2]`.

`convert_character.py` decodes the body's GX quads, triangles, and triangle
strips, evaluates both FCV clips with the existing source-derived motion host,
applies the original weighted skinning rules offline, and writes quantised
little-endian frames. This keeps GameCube display-list parsing and 119-part
skeleton evaluation off the SH-4 gameplay frame.

The current private package contains:

| Item | Value |
| --- | ---: |
| Vertices | 1,484 |
| Triangles | 2,519 |
| Material batches | 14 |
| Idle frames | 91 |
| Walk frames | 29 |
| Position quantum | 0.0625 mm |
| Maximum measured quantisation error | 0.03125 mm |
| Package size | 1,083,936 bytes |

The package and its JSON manifest live under `port/dreamcast/build/private` and
remain ignored. The converter, package reader, and synthetic parser tests are
tracked; no disc-derived bytes are committed.

## Dreamcast runtime result

The KallistiOS room target builds with the character package in romdisk. At
runtime it validates the package ranges and indices, selects idle while the
player is still, selects walk while moving, advances animation in elapsed time,
and projects the baked source vertices at the collision-controlled player
position and yaw.

An isolated Flycast run displayed the animated body in the existing r10d
shoulder-camera route, accepted movement input, and exited through START. The
retained visual evidence is under
`C:\Flycast-Evidence\re4-dreamcast\leon-p1-20260919-164056`.

## Acceptance boundary

This proves a disc-derived, source-motion-driven humanoid in the native room.
The current pass uses only the primary body entry and approximate flat colours.
Leon-specific face, hair, hand, weapon, and costume attachment handling remains
open, as do textures, interpolation, combat behavior, a measured combined frame
budget, and physical Dreamcast validation.
