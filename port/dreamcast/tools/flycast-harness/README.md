# Parallel Flycast capture harness (D367)

Scripts for one evidence directory. Up to 8 run at once on one host:
- `boot2.ps1` waits for a free slot (`$MaxInstances`) instead of refusing to start.
- Each instance picks a free GDB port (3263..3299), writes it into its own `emu.cfg`,
  and records it in `gdb.port`.
- Guest RAM is read per process id (ReadProcessMemory), so instances share nothing.

Setup for a new evidence dir `<dir>` (Windows):
1. Copy these files plus a pinned `flycast.exe` and its `data/` dir into `<dir>`.
2. Add `game.cue` (`FILE "disc-output/disc.bin" BINARY` / `TRACK 01 MODE1/2048` /
   `INDEX 01 00:00:00`) and the staged `disc-output/disc.bin`.
3. Copy `re4dc-game.elf` and `syms.txt` from the build (`tools/d367/syms.sh`).
4. Run `python capture-run.py 360 "120"` from PowerShell. It writes `run-output.txt`,
   `boot.log`, `run.pcs` (when the sampler is linked) and `shot-120s/frames/*.png`.

Frame times are guest time. If an A/B delta looks surprising, rerun that pair alone,
since host load has shifted results before. Never overwrite an accepted evidence dir;
always stage a new one.
