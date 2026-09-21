# Recovered r100 memory checkpoints

## D307: reclaim the duplicate platform reservation

2026-09-21; keep this target layout correction. The source SndInit uses
0x80370000..0x803F0000 (512 KiB), while 0x803F0000 is the old GX FIFO.
The native carver mistakenly reserved a separate unused 512 KiB "DVD" region,
then placed sound in another 448 KiB region. Actual DVD staging already uses
the separate 128 KiB re4dc_dvd_buff; the native FIFO is separately owned too.

Sound now starts at the arena base with its original 512 KiB capacity. The
legacy dvd field aliases that lower-bound marker and has no storage consumer.
Core/option/player/weapon capacities, total arena size, all gameplay pools and
both source primitive-buffer halves are unchanged. This returns 458,752 bytes
to the game heap (8,272 -> 8,720 KiB); sound capacity grows by 64 KiB rather than
being cut. Source scan covers all dvd/sound marker consumers and DVD staging.

The actual native carver passes a host test for full-size/fallback allocation,
exhaustion, idempotence, full sound writes without touching core, and separate
DVD staging. The game builds with the same six existing unresolved stubs.

The 55-second D307 Flycast replay loads the unchanged qualified r100 archive
and ROOM/FOOT sound blocks. Matched allocation points recover exactly 458,752
bytes: after the unchanged 638,976-byte primitive allocation, free space is
463,136 instead of 4,384. Both 5,760-byte collision arrays and the 19,200-byte
event table now succeed; 429,536 bytes remain after that event allocation.
No allocation failures appear in this replay. This is not a final gameplay peak.

Next exact consumer: the captured task stack resolves to
`cModInfoMgr::create` -> `notBinData`, called by `cModel::modelInit` from
`cPlLeon::setModel`/constructor. The mirror report marks `em/pl00.drs:0`
(1,055,264-byte player archive) unhandled. The source version check is a sleep
loop, not a successful model installation. Qualify the player's source-layout
archive using existing motion/archive, BIN/TPL/FCV/EFF code and require it at
the native-consumer boundary before replaying further. Do not relax version
checks, use viewer character packages, or report full room initialization.

Evidence: `C:\Flycast-Evidence\re4-dreamcast\d307-native-arena`; fixture remains
`/root/probe/d292-fixtures`, disc `/root/probe/d307-disc`. Same toolchain/emulator
as D306. Read timing is still invalid; GX/audio placeholders and normal manual
gameplay remain unaccepted. Captured patch includes inherited integration edits.

| Artifact | SHA-256 |
|---|---|
| ELF | bca0e11f6f0fef34d11c3a10da8c3d823ab0c0c63bea7985ec2a539b7372ad33 |
| Disc | 4c89babba3841079aa1a58f4b2afd304e4b0167c35f276c36501fb631f9ed565 |
| r100.dar | 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739 |

## D306: allocation diagnostic (historical)

2026-09-21; diagnostic on top of c325c41, not a memory optimization.

The existing `/cd/dc/diag.txt` switch now logs room-heap allocations of at least
1024 bytes and every failed allocation. It does not change allocation sizes,
ownership or lifetimes. Small successful allocations remain included in reported
free totals. This is initialization diagnostics, not production frame telemetry.

Build passed with the same six existing unresolved stubs. A 55-second scripted
Flycast replay using `/root/probe/d292-fixtures` repeats D305's normal first-play
opening completion, r100 archive load and ROOM/FOOT sound dispatch, then the same
collision/event allocation failures. No visible/manual gameplay acceptance.

| Allocation | Requested bytes | Heap free afterward |
|---|---:|---:|
| Qualified r100 archive | 4,669,568 | 2,451,136 |
| Model info pool | 134,336 | 2,314,336 |
| Parts pool | 618,336 | 1,695,936 |
| Enemy pool | 213,120 | 1,482,752 |
| Object pool | 334,560 | 1,148,128 |
| Effect work array | 344,064 | 753,248 |
| Primitive buffer, two halves | 638,976 | 4,384 |
| SAT / EAT arrays | 5,760 each; failed | 4,384 |
| Event data table | 19,200; failed | 1,696 |

The table omits smaller successful allocations; do not sum it as a full ledger.
Manager identities follow the sequential calls in gameRoomInit. The complete
trace includes addresses and source tags. The original r100 CNS values select
319,488 bytes per primitive half; this is not the default 0xA0000. The source
primInit allocation succeeds before required later pools run out. This establishes
ordering and sizes, not a safe smaller buffer or final gameplay peak.

Next: verify which target reservations/lifetimes can release memory without
changing gameplay capacity or dropping rendering work. Keep source pool counts,
qualified data and behavior intact. Trace the primitive buffer's consumers and
backend ownership before changing its representation. Existing GX/audio stubs
are integration debt, not justification for deleting required resources.

Private evidence: `C:\Flycast-Evidence\re4-dreamcast\d306-room-allocations`.
Disc build: `/root/probe/d306-disc`. Source/KOS/emulator environment matches D305;
the captured patch records inherited dirty integration work. The effective
scenario/enemy/object switches are not yet logged, so this trace cannot qualify
those systems. `read_us=0` remains invalid timing. Physical hardware untested.

| Artifact | SHA-256 |
|---|---|
| ELF | d1882af719ad7e67253a2deab613fe4dff8b36fc2286fd40a09621b697429069 |
| Disc | 0a455d1a6629c20e0e3dd191ec09bb24b2f5a04bdc2a3857526915afa9ce9929 |
| r100.dar | 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739 |
| Flycast | 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a |
