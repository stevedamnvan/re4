# R4 game boot checkpoint: the recovered game runs its frame loop on the Dreamcast target

Date: 2026-09-21. Branch `dreamcast-port`. Builds on the SH-4 compile of the
recovered sources (`cb0d60a`) and the planning corrections (`d683e20`,
`1741dda`).

## What executes from normal boot

The linked game ELF (`port/dreamcast/game/re4dc-game.elf`, `src/game` plus
the platform layer, 1,664,040 bytes of text, 68,304 data, 430,924 bss) boots
from a CD image in Flycast and runs the game's own startup in order:

1. `main()` → `systemStartInit()`: `OSInit`, `VIInit`, `Dvd.Init()` (the
   file table existence check over the 512-entry disc table), `SystemMemInit`
   (heap 0 carved from the platform arena), `TaskSchedulerInit`, `Render_init`
   (GX stub), `SndInit` (reads `bgm/bio4str.hed`, `bgm/bio4midi.hed`,
   `bgm/doorse.hed`, `bgm/bgmtbl.dat`, `etc/memcard.das`), `SofdecInit`,
   `IdSys.gameInit`, `EprintfInit`, `LogInit`, `init_dbmodule`
   (`debug/config.txt`, `debug/roomInfo.dat`), `Dvd.SizeTableRead`
   (`etc/sizetbl.dat`), `cMes.init()`.
2. `systemRestartInit()`: pad, heap 1, `Font/common_p.fnt`, managers.
3. `TaskExec(0, Title_task, 0)` and the frame loop: `Render_before`, `PadRead`,
   `DebugControl`, `Render`, `TaskScheduler` (the title task runs on its own
   8 KB thread and sleeps a frame at a time), `IdSys`, `Trans`, `Dvd.Watcher`
   (spawns the DVD read-pump task), `SndWatcher`, `cMes`, `iTaskScheduler`,
   `Render_done`, the two vsync waits, `systemVSyncPost`, `systemResetCheck`.
4. Inside the title task: `CoreDataRead` (`etc/core.das`, 2.3 MB core archive
   plus the CORE sound block), the memory-card task (`ss/cmn/save_e.dat`,
   "Slot A Unmount" from the no-card platform), and the message system init.

The frame loop keeps running (vblank count advances, the scheduler resumes
the title task every frame). The run is deterministic in Flycast and takes
about 4 s of guest time from `OSInit` to the frame loop.

## Next precise missing dependency

`Message::init()` and the title task read the core archive's sub-files
(`ArcFile` offsets at +0x10.., message tables at `ofs_28`) as raw GameCube
big-endian data. On the SH-4 those reads return byte-swapped values
("Message::init() Msg[24] Address Error", `SndCall` "Illegal SE No.", and the
main thread looping in `Message::WidthCk` over a garbage table), so the title
never reaches `titleInit`'s `SS/cmn/title.snd` read. The fix is the next
handlers of the little-endian mirror (below): the `ArcFile` offset table of
`etc/core.das` part 0 and the message-table format that `mes.cpp` overlays
(the PS2 `RE4-MDT-TOOL` in the toolbox documents the same MDT layout).

## Decisions recorded by this slice

### Data endianness: an offline little-endian mirror, not a runtime shim

The game overlays its structures directly on file bytes. Rather than patching
every reader, `port/dreamcast/tools/le_mirror.py` builds a mirror of the
extracted data tree in which every scalar a game structure reads is
byte-swapped in place, layout untouched, one handler per format written from
the game headers (`include/dvd.h`, `include/snd.h`, `include/snd_drv.h`).
Files or archive parts without a handler are copied verbatim and listed in
`le_mirror_report.json`, so a boot failure maps to the next format to cover.
The disc is built from the mirror (`tools/mkdisc.sh <elf> <mirror> <out>`).

Handled so far: the archive container (`cab6be20` magic, 32-byte `DvdHeader`
entries, one nesting level, `.das`/`.drs`/`title.snd`/...), `bgm/bio4str.hed`
(stream blocks: RIT and SHD records), `bgm/bio4midi.hed`, `bgm/doorse.hed`,
`bgm/bgmtbl.dat`. Reported and still raw: 50 container parts (the core
archive, memcard, player/enemy `.drs` parts, room archives) and 757 files.

The mirror and the extracted tree are private data and stay outside the
repository, like the disc image.

### Thread model over KOS

KOS here is always preemptive (`thd_set_mode` is a no-op), so the platform
reproduces the GameCube rules in `platform/os.cpp`: priorities map one to one
(main thread 16, tasks 15), a suspended thread is taken off the KOS run queue
(`STATE_WAIT` on a private marker) and put back by `OSResumeThread`, which
yields when the resumed thread outranks the caller; a thread suspended while
it sleeps in a queue or semaphore parks itself when it wakes. `OSCreateThread`
writes the SDK's `0xDEADBABE` stack guard the scheduler's overflow check reads.

### Source patches that keep the PowerPC objects identical

Every game-side change is under `#if defined(__PPC__)` / `#else` so the
PowerPC token stream is unchanged; the ProDG object comparison over all 438
units reports 0 differences after this slice. The Dreamcast branches:

- `include/va_ppc.h`: the compiler's `<stdarg.h>` (the GameCube `va_list`
  layout produced garbage arguments in every log line);
- `include/main.h`, `src/game/main.cpp`, `src/game/dvd.cpp`: `vsync_cnt` is
  `volatile` (GCC turned the frame loop's empty vsync wait into a self-branch);
- `src/game/dvd.cpp` `cDvd::ReadCheck` (both overloads), `src/game/emwindow.cpp`
  `SetBreakEsp`, `src/game/item.cpp` `available`: explicit returns for three
  functions the GameCube compiler let fall off the end (r3 flowed through),
  which on SH-4 fell into the literal pool (illegal instruction);
- memory regions, bus clock, frame buffers and FIFO from the platform
  (`main_mem.cpp`, `read.cpp`, `snd.cpp`, `main_sub.cpp`, `debug.cpp`), and
  the inline/static and template adjustments from `cb0d60a`.

### Fault capture in the emulator

Flycast's serial capture is empty in this setup and a fatal "SH4 exception
when blocked" gives no PC, so the platform routes KOS debug output into the
RAM log ring (`platform/fault.cpp` dbgio handler), logs the context of any
unhandled SH-4 exception (PC, PR, SP, SR, r0-r15) and parks the CPU so the
evidence reader can still read the ring. `OSPanic` does the same. The
launcher `boot2.ps1` polls the ring every 5 ms, survives guest reboots, and
keeps `boot.log`. Two hard faults were found this way: the fall-through
returns (illegal instruction at `cDvd::ReadCheck+0x28`) and the byte-swapped
archive part size that made a 58 KB read into a 1.6 GB one.

## Runnable build and capture

```
# WSL, from port/dreamcast
source kos-env.sh
make -C game -j4
python3 tools/le_mirror.py /root/re4data /root/re4data-le
bash tools/mkdisc.sh game/re4dc-game.elf /root/re4data-le /root/probe/game-disc
# Windows: copy disc.bin to the evidence dir as game.bin, then
powershell -File C:\Flycast-Evidence\re4-dreamcast\d290-game-boot\boot2.ps1 -Seconds 40
```

`syms.txt` (log ring offsets from `sh-elf-nm`) is regenerated by the WSL
build script; `read_log.py` prints the ring and the platform stage word.

## Memory and performance configuration at this state

Platform arena 13,312 KB at `0x8c2399a0`: DVD 512 KB, sound 448 KB, core
2,256 KB, option 256 KB, player 1,120 KB, weapon 448 KB, game heap 8,272 KB.
The title task, card task, message task and DVD pump use the scheduler's
8 KB / 12 KB stacks. No rendering, audio or auxiliary-RAM transfer is
performed yet (GX, AX and ARQ are stubs; the ARQ stub fills the request so
callbacks see their owner), so frame time is the game's own CPU work plus the
vsync waits; no performance claim is made at this state.

## Not done in this slice

- No recovered debug fixture (RoomJump, config.txt room start) has been
  reached: the title task is the frontier.
- No PS2 or alternate representation was tested.
- REL modules (enemy/player/weapon `.drs` code parts) are not linked.
- `Dvd.ReadCheckInfo` reports a spurious "CORE_DATA IS TOO LARGE(0/2310144)";
  the size it compares is not the part size the pump recorded (to trace).
