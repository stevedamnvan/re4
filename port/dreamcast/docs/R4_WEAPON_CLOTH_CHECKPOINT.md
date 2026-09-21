# D309-D311: native handgun module and cloth workspace

2026-09-21. Kept; startup reaches the authored R100Init after the player/weapon
startup that previously stalled. This does not establish visible or playable output.

## D309: existing DRS and module mechanisms

`le_mirror.py` reuses `tools/drs.py` to validate/roundtrip the source DRS container,
including alternate signature, empty slots, embedded REL boundary and nested
sound. Existing BIN/TPL/EFF/FCV/SEQ handlers convert its entries in source layout.
The last asset ends at the REL offset; raw PPC code is never treated as a model.
REL headers are metadata; raw PPC code/relocations remain unchanged, and every
embedded-module report explicitly requires a native binding. Data qualification
alone does not prove executable module coverage.

The existing static-module generator now resolves shared source paths from
`config/G4BE08/modules.py` and handles non-stage modules without room tables.
Module 4 uses the original wep02 entry, ObjMauser, ObjRuger and PlHandgunMove
sources. Partial/final SH-4 symbols confirm real entry points, not missing stubs.
The prior stage generator/registry and OSLink binding are now checkpointed with
this extension. Unknown module IDs fail with cleared entry points. Static BSS,
constructor and unlink/reload fidelity remain explicit transition/retry debt.

The source weapon keeps 60 slots: one EFF, two TPL, four BIN, 42 FCV, ten SEQ,
one empty. Checks preserve indices, offsets, ARAM samples and 22,292 embedded
REL bytes except converted metadata. Prior Leon/r100/r120 identities are unchanged.
The boot/title+r100+Leon+weapon manifest `/root/probe/d309-required.txt` passes.

D309's 55-second replay reads the correct 0x439e0 weapon body, dispatches WEP
sound, binds module 4 and logs `Wep02 HANDGUN prolog Ok`. The bad size/read crash
is gone. It remains active in vector work; this was not evidence of completion.

## D310-D311: retain cloth, adapt its scratch address

The existing thread diagnostic now also scans the interrupted active thread,
within its recorded stack bounds. Stack entries are candidate return addresses,
not an unwinder. D310's 75-second replay repeatedly identifies Leon startup ->
cloth Move3 -> penClothAtCk. Source inspection finds penClothAtMake still using
Gekko locked cache at 0xE0000000, which is SH-4 store-queue space.

D311 redirects only the non-PowerPC workspace to the existing aligned 16 KiB
`re4dc_locked_cache` used by the target skinning path. No new buffer, cloth
removal, collision simplification or gameplay pool reduction. PowerPC
preprocessed tokens are identical before/after; not a new full ProDG comparison.

The 55-second D311 replay passes that stall, allocates three 3,264-byte cloth
buffers and dispatches BGM0. It reaches R100Init, where em/em12.drs and four
r100s40/41/43/44 EVD files are absent, then halts in the pre-existing missing
`R100Em` constructor stub. Last logged room allocation is 65,536 bytes at
TexRender.cpp(323), leaving 343,552 bytes; not final peak headroom.

## Next dependency and limits

The five missing files have since been extracted from the same private source
ISO using existing tools/extract_orig.py Gcm reader, into `/root/re4data` only.
Hashes: `/root/probe/d312-extracted.json`. They are not on D311's captured disc.
An isolated conversion probe handles em12's data; its native module still needs
compilation/binding. All four EVD files remain explicitly unhandled. Expanded
`/root/probe/d312-required.txt` rejects them; do not activate unqualified data.

Resolve the R100Em compiler-name mismatch using the existing alias mechanism,
after verifying the source constructor and compact stack-object layout. Then
qualify required event/archive consumers and native enemy module in source order.
Preserve the authorized cutscene-completion effects; no blanket event skip.
Account for the newly required working set rather than trimming source pools.

Fifteen mirror tests and 40 room-format tests pass. New fixtures exercise empty
last slots beside REL data, raw-code preservation, malformed-boundary rollback
and rejection of unknown neighbors. Recovered target builds with the same six
pre-existing missing-symbol stubs. No character orientation/grip/completeness,
visible menu/gameplay, audible sound, real-time or hardware acceptance is claimed.
GX/audio placeholders and effective-debug-flag capture remain open.

## Paired evidence

Private folders under `C:\Flycast-Evidence\re4-dreamcast`:
`d309-weapon-module`, `d310-active-stack`, `d311-cloth-workspace`. Each retains
its executable/disc, symbol offsets, dirty patch, mirror report, asset manifest,
required manifest, build/package logs and scripted capture. D309 includes actual
weapon verification; D311 includes PowerPC check and next-data extraction report.
Fixture remains `/root/probe/d292-fixtures`. KOS, compiler and Flycast identities
are unchanged from D307; do not compare these source-init logs as renderer FPS.

| Build | ELF SHA-256 | Disc SHA-256 |
|---|---|---|
| D309 | `1a1bd13e145816b6122cebba0eb78a09593757bc927d6012c1ddaac9a3bae552` | `5cbd753c8cc84d1ca4b192d07ff30be8a571b0a070daaa336112e9bb9f61514b` |
| D311 | `f40b0f3cde96311a9f1dad164327a95b386ef6c64129fe2a8572fd494bb19de2` | `aae18dcfaf45685601d6754da4aad32fb8a2e2edaf0d3cdff1e05acb7b07cec5` |

Weapon DRS SHA-256:
`69e6c8c15a7cf5caf1716ab08d50595f1e08c5b0d308afb62711b6dd1cd44178`.
