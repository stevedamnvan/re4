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

## Update 2026-09-21 (second slice): through the card check into the title screens

The boot now continues past item 4 above:

5. The memory-card first check runs with no card ("no memory card" prompt);
   the scripted input fixture answers it (Up, A = continue without saving),
   `CardStatus` bit 31 is set and `titleWait` completes.
6. `SS/eng/title.dat` (2,518,944 bytes) is read into the title heap and the
   ID layout system starts the Nintendo / warning / logo screens
   (`IdDataLoad`, `idSysMove04`, the ordering-table submit).

The three earlier errors ("Illegal SE No.", "Message::init Address Error",
"CORE_DATA IS TOO LARGE") had one cause, found with a memory watch: the DVD
read staging buffer `DVD_BUFF` in `src/game/dvd.cpp` was the GameCube's fixed
address `0x80350000`, which is not RAM on the Dreamcast, so every archive
part copied through it arrived as zeros. The Dreamcast branch now uses a
128 KB platform buffer (`re4dc_dvd_buff`); the PowerPC branch is unchanged.

### Scripted input fixture

`port/dreamcast/fixtures/padscript.txt` lists `frame buttons hold` lines
(vblank count, GameCube `PAD_*` bits in hex, frames held). `tools/mkdisc.sh`
publishes the fixtures directory as `/cd/dc/` and `platform/pad.cpp` ORs a
running entry into controller port 0, so a boot through the card check and
the title screens is reproducible without a player or an emulator input hook
(key injection into Flycast's SDL window did not reach the emulated pad).

### Diagnostics added (Dreamcast branch only)

`re4dc_watch_set` (vi.cpp): a checksum of a region compared every vblank,
logging the running context the first time it changes. Card state trace in
`cCard::MainLoop`, pad button-edge log, message-table dump in `Message::init`
on a NULL message, thread dump with a return-address scan of parked stacks.

## Next precise missing dependency

The ID system reads `title.dat`'s three `EFF` sub-files (2,127,840, 222,720
and 115,584 bytes) as raw big-endian data: `IdDataLoad(): EffData Invalid`,
every texture id lookup fails (`idSysMove04 ... No such Texture`) and the
render stub's primitive buffer overflows with the fallback primitives. The
fix is the `EFF` handler in `tools/le_mirror.py`, written from
`include/id_sys.h` and `src/game/id_sys.cpp` (the effect / texture-table
layout the ID units index), after which the same scripted boot should reach
`titleMain`, the menu, New Game and `GameTask`.

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
entries, one nesting level, `.das`/`.drs`/`title.snd`/...), the tagged
sub-file archive (`{n, ofs[n], tag[n]}` in `core.das` part 0, `ss/*.dat`,
`memcard.das`, room archives) with `MDT` (message tables), `TPL` (texture
palettes), `UWF` (id/effect work files) and the sound MRAM block of type-1
container parts (ISS header, SIT, wavetable sections, sequence table),
`bgm/bio4str.hed` (stream blocks: RIT and SHD records), `bgm/bio4midi.hed`,
`bgm/doorse.hed`, `bgm/bgmtbl.dat`, `font/*.fnt`, `*.tpl`. The last run
converted 779 files (410 whole files handled, 1,180 tagged sub-files of which
339 handled, 18 sound parts, 0 errors); still raw by tag: BIN 411, MHT 214,
FCV 155, EFF 38, LIT 10, SMD 5, FNT 3, SAT 2, CAM/TEX/VIB 1 each.

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
bash tools/mkdisc.sh game/re4dc-game.elf /root/re4data-le /root/probe/game-disc fixtures
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
- `Dvd.ReadCheckInfo` reported a spurious "CORE_DATA IS TOO LARGE": the
  `asm("ReadCheck__4cDvdi")` alias relied on the caller's register surviving
  into the callee; the Dreamcast branch defines it as a real function
  (`include/dvd.h`, `src/game/dvd.cpp`) and the report is gone.
