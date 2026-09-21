# Boot-forward game target: SH-4 compile of the recovered sources and the platform census

This checkpoint opens the boot-forward track proper. Until now every Dreamcast
binary in this port was the room viewer in `port/dreamcast/room`, which drives
the renderer from hand-authored scene state. The acceptance path (PLAYABLE_PATH.md)
is the game's own `main()` → `systemStartInit` → `Title_task` → `GameTask` →
`gameRoomInit`, so the recovered gameplay tree itself has to compile for SH-4
and run over a Dreamcast implementation of the platform interfaces it calls.
This slice makes the tree compile and measures that interface.

## What was done

`port/dreamcast/game/Makefile` (`make census`) compiles the gameplay directories
`src/game src/st src/st1 src/Sscrn src/tools src/Tools src/t_*` with the KOS
`sh-elf` toolchain (`-std=gnu++20 -fpermissive -w -O1`, the game's own
`include/` and `src/` on the include path, `platform/include/re4dc_prelude.h`
force-included), links the objects with nothing else and records every symbol
the linker cannot resolve. The enemy modules `src/em*` join the link as the game
demands them; they compile under the same flags (see the verification below).

Excluded from the SH-4 build, each with a replacement to write in the platform
layer:

| unit | why | replacement |
| --- | --- | --- |
| `src/game/yz2asm.cpp` | whole-function PowerPC asm (the room-archive decoder loop) | C port of the decoder, verified on the host against the JADERLINK-extracted sub-files |
| `src/game/memset_2.cpp` | whole-function PowerPC asm (`memset_asm`, `memclr_asm`) | `memset`-based C |
| `src/tools/t_util_{menu,nomenu,id}.cpp` | REL-specific re-includes of `t_util.cpp` (one object per GameCube REL) | one `t_util.o` serves the single image |
| `src/game/*.c`, `src/lib/**` | CodeWarrior/SN libc and the SDK's PowerPC units | newlib, and the SDK's C reference functions (next slice) |

Result: **all 386 remaining gameplay units compile** (387 objects with the
platform's `lc.cpp`), and the link leaves **402 distinct undefined symbols**.
That list, `census.txt`, is the platform layer's contract.

## Source portability patches (85 files, +378/−177 lines)

The recovered sources are a byte-matching decompilation, so every patch keeps the
PowerPC text unchanged under `#if defined(__PPC__)` and adds a C arm for other
targets. Categories:

1. **Register pins.** `register T x asm("rN")` / `asm("frN")` (165 sites in 75
   files) became `PPC_REG("rN")`, a macro in `include/types.h` that expands to
   the original `asm("rN")` on PowerPC and to nothing elsewhere.
2. **GQR / SPR writes.** The paired-single quantisation set-up in `main.cpp`,
   `scheduler.cpp` (`li 3,4 …`) and `trans.cpp` (`mtspr 918`) is PowerPC-only;
   off PowerPC `setupGQR6` records the register value and the C skinning loops
   below read it.
3. **Paired-single macros.** `PSQ_L_S16 / PSQ_ST_S16 / PSQ_L_U8 / PSQ_L_U8_TO`
   in `dbmodule.cpp`, `shape.cpp`, `trans.cpp`, `espgen45.cpp`, `Espgen42.cpp`
   have plain-C definitions (load the integer, convert).
4. **Skinning loops.** `trans.cpp` `CalcSk1_x` / `CalcSk1_x2` (the `psq_l …
   ps_madds … psq_st` vertex and normal skinning over the locked-cache matrix
   palette) are re-expressed in C: GQR6's load half dequantises the s16/s8
   input (× 2⁻ˢᶜᵃˡᵉ), its store half quantises the result (× 2ˢᶜᵃˡᵉ, truncated
   toward zero, saturated). Rotation is exact fixed point; only the translation
   row is scaled, and the normal passes' large negative scales (0x32073207,
   0x20062006) make that row vanish exactly as on the Gekko. The palette base
   `0xE0000000` became `RE4DC_LC_PALETTE`; off PowerPC that is the platform's
   16 KB `re4dc_locked_cache` buffer (`platform/lc.cpp`, with `LCEnable` a no-op).
5. **Math intrinsics.** `SQRTF` (`frsqrte` + Newton step) → `__builtin_sqrtf`;
   `fabsf` in `math_sub.h` (`fabs`) → `__builtin_fabsf`; `LIMIT_ANGLE`
   (`fcmpu` loop) → the same loop in C; `SINF` / `COSF` (paired-single Taylor
   series over `Coeff[10]`) → the identical series in scalar C (odd powers in
   slot 0, even powers in slot 1, summed last, as `ps_sum0` does).
6. **GCC 2.95 leniencies.** `cAtariInfo`'s anonymous-aggregate constructor
   (`model.h`) and the `__10cAtariInfo` alias are PowerPC-only, with a
   `memset`-based inline elsewhere; `cVarLoop<T>` (`dbg_var.h`) names its base
   members through `this->`; a `li %0,0` zero in `dbg_tool.h` is `z = 0`.
7. **Prelude.** `memcpy` / `strcmp` declarations for the units that use them
   without declaring them (the original headers are CodeWarrior's).

The unchanged PowerPC build is the acceptance test for these patches; see
"Verification" below.

## The census: what the platform layer must provide

402 symbols, by family (`port/dreamcast/game/census.txt` has the full list with
reference counts):

| family | symbols | Dreamcast implementation |
| --- | --- | --- |
| `GX*` | 97 | the Dreamcast renderer's command translation: vertex descriptors/formats, TEV stages, texture objects, matrices, viewport/scissor, display lists, copies (`GXCopyDisp`, `GXCopyTex`, `GXPeekZ`). The room viewer already renders the same batch/material data; this is the interface the game drives it through. |
| `OS*` | 54 | threads (`OSCreateThread`/`Resume`/`Suspend`/`Sleep`/`Wakeup`/`Exit`/`Cancel`, thread queues) over KOS `thd_*`; heaps (`OSInitAlloc`/`OSCreateHeap`/`OSAllocFromHeap`/`OSFreeToHeap`/`OSSetCurrentHeap`, `__OSCurrHeap`) from the SDK's portable `OSAlloc.c`; time (`OSGetTime`/`OSGetTick`/calendar) over `timer_us_gettime64`; interrupts, stopwatches, semaphores, arena, reset, font, `OSReport` |
| `AX*`, `AXFX*`, `AXART*`, `AI*` | 51 | the sound driver's voice/aux/effects API; first as a silent stub that keeps the voice-state machine consistent, then over the AICA |
| `CARD*` | 17 | memory card over the VMU, or "no card" results (the title path tolerates it) |
| `PSMTX*`, `PSVEC*`, `C_MTX*`, `C_QUAT*` | 33 | the SDK's C reference matrix/vector functions (`src/lib/mtx.c`, `mtxvec.c`, `mtx44.c`, `vec.c`, `quat.c` with the CodeWarrior `asm` PS* bodies stripped) with PS* wrappers |
| `DVD*` | 15 | file reads from the disc image's data track (the room viewer's `fs_*` reader), `DVDConvertPathToEntrynum` over a name table, async completion callbacks |
| `mwPly*`, `ADX*` | 16 | Sofdec/ADX: stubbed to "no movie / no stream" until the movie pipeline exists |
| `VI*` | 10 | video mode, retrace wait/callback, frame-buffer swap over `vid_*`/`vblank_handler_add` |
| `PPC*`, `DC*`, `LC*`, `AR*`, `ARQ*` | 18 | performance counters (no-ops), cache flush/invalidate (`arch_dcache_*`), locked cache (buffer), ARAM (a RAM-backed region or the loader's staging; the game's `ARAlloc(0x6FC000)` cannot be honoured on 16 MB, see the residency plan) |
| `PAD*` | 7 | `PADRead` over `maple` controller state into `PADStatus`; clamp/analog mode/motor |
| `PC*` | 7 | the SN host file I/O (`PCopen`/`PCread`/…), debug-only: fail cleanly |
| PowerPC-mangled aliases | 22 | `asm("init__10cAtariInfoiiifffffff")`-style declarations that call a C++ member by its GCC 2.95 name (matching aid). Off PowerPC these need bridge definitions, one per name (`platform/aliases.cpp`) |
| `asm("name")` declarations | ~37 | the sources declare some functions and globals by their PowerPC link name as a matching aid (`extern GlobalWork* pG` reached through `asm("pG")`, `IdUnit* unitPtrI(...) asm("unitPtr__8IDSystemUcUc")`, 22 GCC 2.95-mangled members among them). On `sh-elf` C symbols carry a leading underscore and members use Itanium mangling, so the names stay unresolved even though their definitions compiled (`main.o` defines `_pG`). Fix in the platform layer: a linker assignment file mapping each PowerPC name to its SH-4 symbol (`pG = _pG; init__10cAtariInfoiiifffffff = _ZN10cAtariInfo4initEiiifffffff;` — the member ABI is the same call with `this` first). |
| excluded-unit symbols | 5 | `memset_asm` / `memclr_asm` (memset_2.cpp), `yz2Decode_Decode` (yz2asm.cpp), `TEXGet` (`src/lib/texPalette.c`), `__GXSetIndirectMask` (`src/lib/GXBump.c`) |
| out-of-line inlines | 6 | `cModel::getPartsPtr` / `isTrans`, `cPlayer::subCharLiveCheck`, `cSsPartsMgr` / `cSsModInfoMgr` constructors, `cManager<cObj>::destroyNow`: bodies the original compiler emitted as external copies that GCC 15 keeps inline-only. A non-PowerPC arm of those definitions drops `inline` (next slice). |
| vtables | 16 | classes whose key function lives in an `em*` module or an excluded unit; resolved by the full link |

Most-referenced: `PSVECAdd` 282, `PSMTXMultVec` 273, `cModel::getPartsPtr` 267,
`PSVECSubtract` 245, `PSVECScale` 229, `PSVECNormalize` 158, `PSMTXConcat` 152,
`memclr_asm` 122, `OSReport` 101.

## Verification

* SH-4: `make -k -j4 census` exits 0; 387 objects; `census.txt` 402 lines.
* PowerPC: every gameplay unit (`src/game src/st src/st1 src/Sscrn src/tools
  src/Tools src/t_* src/em*`) compiled with the original ProDG compiler
  (`build/compilers/ProDG/3.9.3/ngccc.exe` via wibo, `-O2 -mfast-cast`, the
  project's include path and defines, `-G 0` plus the module flags of
  `config/G4BE08/modules.py` for REL units) from the pristine `HEAD` tree and
  from the patched tree; objects compared byte for byte. See the result line
  appended below. The full `ninja` matching build could not run here because
  the disc-2 image (the four `st3_*` RELs) is not present in this checkout;
  the object comparison covers every unit the patches touch.

Result: **438 units, 438 identical objects, 0 differences** (`RESULT same=438
diff=0 nocompile=0`). The patches do not change a single byte of the PowerPC
build.

## What this does not yet do

No Dreamcast ELF is linked: the platform objects are the next slice, family by
family in the order the boot path needs them (OS/heaps → VI/PAD → DVD →
GX → mtx → stubs), after which the `main()` in `src/game/main.cpp` runs on
Flycast with the disc's `debug/config.txt` and `debug/roominfo.dat` fixtures
selecting the entry (stage 1, room 0x100 / 0x101 jump points) and the first
blocker is whatever `gameRoomInit` asks for that the platform layer cannot yet
answer (expected: the room archive decoder, then the 16 MB memory map for
`SystemMemInit`'s fixed regions).
