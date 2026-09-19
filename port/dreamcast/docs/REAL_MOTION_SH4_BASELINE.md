# Real character motion on SH-4

This checkpoint evaluates one motion from the locally supplied `G4BE08` debug
Disc 1 with the reconstructed Resident Evil 4 motion code compiled for
Dreamcast SH-4. Disc-derived bytes stay in ignored build and private evidence
directories and are not part of the repository.

## Input identity

- Disc: Resident Evil 4 GameCube debug prototype, Disc 1
- Game ID: `G4BE08`, disc number 0, revision 0
- Disc SHA-256: `b7fcbf121cf7c527aae23838e9c3f0818e31115bb597eb77a2c49c9e8fa46492`
- Character archive: `files/em/pl00.drs`
- Archive SHA-256: `5ea520d7026c48e33e12256ef82173140e72cf4019758167a7d5aa5b6e356090`
- Model: entry 0, 119 parts
- Motion: entry 117, 71 frames, 28 joints, four IK chains
- Original FCV SHA-256: `adaeb432b87678ba869d3a1024955db3958d5dfa02e1487c132c4b87426da8f8`
- Little-endian SH-4 fixture: 7,968 bytes, SHA-256
  `ecb1f91cd65b353fc839d07dd3d2116fa705b0c0c9559d4dabfd7eb28b675740`

The upstream whole-disc verifier found 128 character archives, 9,273 motion
entries, 9,261 byte-identical motion round trips, and 6,351 of 6,351
byte-identical sequence-table round trips. Its 12 reported motion exceptions
are the same documented attach-camera/stub cases in `tools/motion/README.md`.

## Reproduction

Place or link the private image at `orig/G4BE08/re4_debug_disc1.iso`. Then:

```sh
make -C port/dreamcast -f Makefile.host motion-real-host
source port/dreamcast/kos-env.sh
make -C port/dreamcast/motion real
```

`tools/build_real_motion_fixture.py` extracts only `pl00.drs`, parses the model
and motion, serialises the FCV image for the little-endian target, and records
host-reference poses for frames 0, 12, 35, and 70. The generated header and
manifest live under `port/dreamcast/build/private/`, which Git ignores.

Both targets execute the original prepared implementations of `MotionSetCore`,
`MotionMove`, `MotionMoveCore`, `HermiteInterpolation`, the model hierarchy and
matrix functions, `IKInit`, `InverseKinematics`, and quaternion blend handling.

## Results

| Target | Parts | Joints | Samples | Root error | Angle error | Maximum world-position error | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| x86-64 host | 119 | 28 | 4 | 0 | 0 | 0 mm | PASS |
| SH-4 in Flycast | 119 | 28 | 4 | 0.0000010 | 0.0000001 | 0.004272 mm | PASS |

The SH-4 ELF is a statically linked 32-bit little-endian Renesas SH executable.
Its linked footprint is 282,240 bytes and its SHA-256 is
`ef252476d088ba2a77acaeeff4e1cc45954e2705075d67a6febd4f57784aa2c4`.
The symbol table retains `MotionSetCore`, `MotionMoveCore`,
`InverseKinematics`, and `run_real_motion_checks`.

The final emulator evidence is stored outside the repository at
`C:\Flycast-Evidence\re4-dreamcast\real-motion-20260919-145236`. Its console
capture records the numerical result and continued `PASS` reports beyond frame
300; its render capture shows the green pass frame. The manifest binds the
candidate ELF, fixture metadata, logs, captures, Flycast executable, and source
commit.

## Acceptance boundary

This proves that one real Leon skeleton and motion can be decoded and evaluated
by reconstructed RE4 code running on SH-4 within the error threshold. It does
not yet render the character, load a room, measure gameplay frame time, validate
streaming or audio, or prove behavior on physical Dreamcast hardware.
