# D306: recovered r100 allocation trace

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
