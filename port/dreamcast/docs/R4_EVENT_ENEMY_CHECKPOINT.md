# D312: source event qualification and native enemy module

2026-09-21. Kept as integration progress; enemy creation and room residency
still fail for insufficient main RAM. No playable/rendered acceptance.

## Change and verification

R100Em's ignored constructor asm name now aliases the existing cEm constructor.
An actual SH-4 layout fixture verifies the compact 0x3e0 object, 0x320 cModel,
and damage/subArc layout before reusing that constructor. The em12 module uses
the existing shared em10 source and static module generator/registry (REL ID 18).
Native-only symbol visibility/spelling fixes preserve the PowerPC token stream.
Five explicit missing-function stubs remain, including cEm27::setWaterHeight;
linking em12 is not proof every enemy branch works.

The existing mirror now handles the required EVD header, bounded packet records,
named asset table and its BIN/TPL/EFF/FCV/LIT/MDT dependencies. Unsupported packet
kinds and malformed bounds remain rejected. Existing FCV codec support now
preserves observed empty fills, zero size-word variants and aligned key padding;
every source FCV must roundtrip exactly before conversion. Native EVD magic is
compared as ASCII, retaining the original PowerPC numeric check.

20 mirror and 40 room-format tests pass. Source-vs-native checks cover all 161
packets and 133 named assets in r100s40/41/43/44, preserving strings and offsets.
The expanded /root/probe/d312-required.txt gate passes. Seven mirror errors
outside this fixture remain; r101 EVS remains unqualified. Three changed source
files have identical preprocessed PowerPC tokens against the pre-slice working
source; this is not a full ProDG comparison.

## Replay and exact next failures

The 55-second scripted replay passes the R100Em stub and starts the authored
r100 door/window/stream-check tasks. It is not a successful encounter:

- Block::checkBlockMemory requests 1,126,272 bytes with 419,456 free, fails,
  and disables its block data. This must be fixed before room acceptance.
- em12 body requests 4,006,016 bytes with 409,152 free, then repeats with
  343,552 free. DVD allocation fails, EmSetEvent fails and R100Init logs failure.
- EVD names register and reach ARAM_LOAD. The current ARAM/audio placeholders
  do not establish actual event resource residency or audio playback.
- IDSystem missing units and ESP_CTRL02 range errors remain. Sleeping source
  tasks do not establish correctly advancing gameplay or successful initialization.

The next slice must account for archives, source pools and block/enemy working
sets, then remove redundant target residency without cutting required content.
Static module BSS/reload behavior, native rendering/audio, title/UI, manual
character/camera/combat verification and normal three-room progression remain
open. Preserve both source behavior and the accepted native viewer reference.

## Reproduction and identities

Private evidence: C:\Flycast-Evidence\re4-dreamcast\d312-event-enemy.
Build: source port/dreamcast/kos-env.sh; make -C port/dreamcast/game -j4.
Mirror: python3 port/dreamcast/tools/le_mirror.py /root/re4data /root/re4data-le
--native-rooms --require /root/probe/d312-required.txt.
Disc staging: /root/probe/d312-disc, existing /root/probe/d292-fixtures.
Evidence retains build/package/mirror logs, all asset hashes, dirty source patch,
scripted boot log, SH layout fixture, source token check and EVD verification.

- ELF SHA256: 79f10b18e0f319f955f24cfcc5f84b9a59ab054fc02ec3ec72cccc2972c6988f
- Disc SHA256: 5649f9ff5839b2de58d407e4ffec6af95ce8a3edfd1b7c2b456d81cbb749f167
- Flycast SHA256: 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a
- r100 DAR unchanged: 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739
- KOS: 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3; SH GCC 15.2.0.

Memory figures are failed-request snapshots, not measured gameplay peaks.
No presented frame rate, visual/audio correctness or physical-hardware result.
