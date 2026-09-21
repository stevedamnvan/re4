# D314: recovered ID output connected to native textures and PVR

2026-09-21. Adapter committed as 4123a85. D314 is the **first verified
source-to-native UI presentation checkpoint**, not complete menu or room
acceptance and not a replacement for the accepted room renderer.

## Observable result and limits

Source title code now produces visible native output: warning, logo sequence,
animated title layers and START / LOAD / OPTIONS. Source ID layout, timers,
parent transforms, ordering-table callbacks and menu selection remain in control.

Evidence: C:/Flycast-Evidence/re4-dreamcast/d314f-menu-visible.
Open frames-corrected/sample05-fb0.png (warning) and
frames-corrected/sample17-fb0.png (main menu). The adjacent records.json associates
samples with latest title and UI telemetry states. The existing input fixture
holds at the menu by commenting its final A/New Game and debug-menu START
entries. This is scripted selection, not manual control acceptance.
The source attract timer still attempts missing demo movies during the hold.

The ordinary boot-forward fixture in d314e-ui-framebuffer selected New Game
and entered title exit. The preserved Flycast log records **Fatal: SH4 exception
when blocked at 00:50:526**, before the requested 105-second capture deadline.
The log reader observes process exit before boot2.ps1 calls Stop-Process.
This is an actual guest/emulator failure, not the capture harness ending its
run. The reader's "guest rebooted" message only observes a ring-head reset;
it does not establish a source reset. The exact fault remains to be diagnosed.
This build has not re-established D313's later r100 frontier.

### Focused interaction evidence (existing run, no recapture)

| Delivered raw input / source frame | Established source result |
|---|---|
| Start 0x1000 / 2469 | Title is 5/0; titleMain case 0 itself initializes the menu. Do not claim this input alone opened it. |
| Up 0x0008 / 2589 | In 5/1, titleMenuInit starts the three-entry cursor at 1 (LOAD); TITLE_MENU_MOVE moves it to 0 (START). |
| A 0x0100 / 2649 | titleMenuSelect returns 1 for cursor 0. titleMain sets Rno1=3; the same-frame log is 5/3, then 7/3 at 2651. |
| Start 0x1000 / 2849 | Confirms titleExit's separate debug room-selection wait (Joy[0].trg & 0x1100). This is not the main START-item confirmation. |

The existing pad fixture, delivery log and recovered title.cpp establish this
bounded selection/confirmation check. titleExit releases title resources and
TaskChain(GameTask, 0) leads to SubScreenGameInit/SubScreenAramRead. Full manual
menu interaction is still unaccepted. No additional historical capture campaign
was needed.

## Existing implementation connected, minimum new adapter

| Recovered producer / consumer | Existing native mechanism reused | New adapter |
|---|---|---|
| IDSystem::trans -> source OT -> IdCommonTrans | KOS PVR packets, existing texture handles | ui_bridge.cpp carries source positions, UVs, colour and blend; native_ui.cpp emits common quads in source order. |
| IdGetTexWk / source TPL descriptor | Package::adopt/upload/release_payload/close | Content identity binds the source-selected image to one existing-format package; bounded GPU handle cache. |
| Qualified UI archives | le_mirror TPL traversal/check_required and convert_tpl.build_package | prepare_native_ui.py and fixtures/native-ui-deps.txt: 254 unique images. Other core regions remain incomplete. |
| Native staging | storage::Arena/read_file | Exact bounded source-heap allocation, freed after upload and metadata retention; failures close partial ownership. |
| Reuse/retirement | Both waits from room_gpu_quiesced | Extracted contract to room/gpu_lifecycle.*; both executables call it. No free after failed fence. |

Five ID functions relied on PPC fixed-register aliases that became uninitialized
locals on SH-4. Native branches initialize them from the actual arguments;
the PowerPC path is unchanged.

Uploads occur in the source OT callback, while TPL storage is valid. Deferring
resolution until Render_swap would allow intervening tasks to retire backing.
Cached packages retain only metadata and VRAM; current-frame handles cannot be
evicted. Registration invalidates pointer-to-content shortcuts. Future dynamic
in-place image/palette mutation requires explicit invalidation.

Zero material alpha cannot pass the source common ID alpha comparison. Rejecting
such quads before loading avoids bringing invisible title layers into the active
set. The initial candidate exceeded its budget; retain d314b-ui-trace as a
negative result. Source animation and menu logic still execute.

Package metadata now uses libc allocation, independent of the game's overridden
C++ allocator/current room heap. Source heap reset must not invalidate metadata
still owning VRAM. Shared VRAM allocations are still freed exactly once.

## Measured ownership and memory

| Quantity | Bytes / count |
|---|---:|
| Uploads with before/after source heap checks | 40 |
| Heap mismatches after freeing staging | 0 |
| Maximum aligned staging allocation | 1,048,736 |
| Cumulative staging freed across loads/reloads | 7,264,512 |
| Retained UI texture VRAM, last sample | 3,946,496 |
| Peak UI texture VRAM | 4,192,256 |
| GPU texture cache budget | 4,194,304 |
| Retained header/descriptors per package | 144 |
| Common-quad missing textures / unsupported masks or blends / queue drops | 0 / 0 / 0 |

Pointer/ownership arrays add logical 5 bytes per single-image package plus
allocator overhead. Cache/queue/storage scratch is in the executable.
Cumulative staging freed is **not simultaneous memory savings**.
Original source archives remain resident and have CPU users. Their payloads
have not been reclaimed; no source-archive recovery is claimed.

ELF text/data/BSS = 2,253,904 / 75,424 / 672,024; total 3,001,352 bytes.
That is 129,776 above D313's 2,871,576. The coarse arena allocator steps down
262,144 bytes; reported source heap span is 8,464 KiB versus 8,720 KiB.
This is real integration cost, not a memory optimization. Menu startup
headroom is not a demonstrated room/transition peak.

## Verification and identities

- ELF SHA256: c112a7acdc2acf553d123a3230267624a04efa2ac801908867edfc83a29d7a4e.
- Held-menu disc: 3adcf4b0c3be02a634caf33f5d3df330a2a8fc7e9ff2284746e37c1633612be1.
- Boot-forward disc: 5ca8ccd32eaedc868054db196beb94db73c6e34ef9368d6c0b41487b37e90467.
- Flycast: 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a.
- KOS 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3; SH GCC 15.2.0.
- Evidence retains asset/native-image manifests, fixtures, dirty patch, adapter
  snapshots, logs and hashes. Proprietary bytes remain outside Git.
- 15 converter tests, 25 mirror tests, 3 native-connection fixtures pass.
  Fixtures compile the actual Package and GPU fence; cover failed/partial
  upload, shared ownership, repeated close, backing reuse after release,
  failed fences, stale output rejection and runtime/offline identity agreement.
- id_sys, texture and main_sub PPC preprocessed tokens match pre-slice working
  files. Not a new full ProDG comparison.
- Game links with the same five missing stubs; affected viewer objects compile.
  Historical viewer lifecycle evidence does not automatically qualify this consumer.
- No gameplay frame-time distribution or physical-hardware acceptance.

## Blue-image readback correction

Hidden-window readback was black. The first VRAM adapter treated
pvr_get_front_buffer() as a raw framebuffer offset, producing cyan/blue images.
Images in d314e-ui-framebuffer/frames are INVALID.

Pinned KOS pvr_misc.c returns PVR_RAM_BASE + 2 * frame_offset. The corrected
adapter reverses that calculation, then reuses the existing
d221-actor-normal-alias-fix-visual/capture_vram.py bank mapping/RGB565 reader.
Flycast rend.EmulateFramebuffer=yes enables readback. This fixes capture,
not output colours. Preserve bad images labelled for diagnosis. In this tested
KOS/Flycast configuration, framebuffer readback **is available**; a blanket
"unavailable" rule does not apply. Hidden PrintWindow failure is a different
capture path and does not disqualify VRAM readback. This result is not a claim
about every emulator backend or physical hardware.

Logged pointers a514e900/a594e900 map to raw offsets 0a7480/4a7480. Masking
both with 007fffff aliases them at the wrong offset 14e900. The existing D221
bank reader then maps correct raw offsets to VRAM64 addresses 14e900/14e904.
The checked-in tools/capture_ui_vram.py preserves that reader and adds the
explicit inverse plus bounded inputs and Windows handle types. Two focused
fixtures check front/back distinction, invalid ranges, bank mapping and RGB565
primary colours. It is a reader, not another runtime renderer or capture harness.

[D314_VALIDATION_IDENTITIES.json](D314_VALIDATION_IDENTITIES.json) pins ELF,
discs, emulator/config, fixture payloads, asset manifests, dirty patch, exact
private capture adapter and its D221 helper, logs and the two accepted images.
The supplement C:/Flycast-Evidence/re4-dreamcast/d314-validation preserves a
copy of the manifest/helper without changing accepted captures. The new public
reader did not generate the historical images; their exact tool is separately
pinned. No audible output, source-archive recovery or room gameplay is claimed.

## Reproduction and next work

From /root/work/re4-dreamcast, source port/dreamcast/kos-env.sh and build
make -C port/dreamcast/game -j4. Copy the existing padscript.txt and diag.txt
from /root/probe/d292-fixtures into a fresh fixture directory. Run:

    python3 port/dreamcast/tools/prepare_native_ui.py /root/re4data \
      port/dreamcast/fixtures/native-ui-deps.txt <fixture>/tex
    bash port/dreamcast/tools/mkdisc.sh port/dreamcast/game/re4dc-game.elf \
      /root/re4data-le-static <disc-output> <fixture>

The tex destination must not exist. Exit failure must prevent packaging.
Use the existing boot/log/VRAM helpers with current ELF symbol identities.
The D313 required mirror gate is separate; exporting images does not qualify
unrelated source archive subfiles.

RGB565/ARGB4444 quantization and border padding preserve dimensions without
resizing but still require moving source comparison. Recovered UI explicitly
preserves GX I4/I8 intensity in alpha, checked against
[Dolphin's decoder](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/TextureDecoder_Generic.cpp).
The legacy viewer's intensity-alpha default is unchanged. No compressor/library
was copied. Padded sampling, wrap/filter semantics and blend/alpha edges remain
quality checks; a screenshot does not prove full parity.

Only common unmasked ID quads are connected. Fonts/card text, negative/shimmer/
background-copy effects, full fades, 3D and audio remain unbound. Common-quad
counters do not measure those consumers. Manual menu and retry remain open.

Next diagnose the boot-forward reboot while preserving visible UI and ownership.
Then connect source-selected room/actor resources to the existing native draw
mechanisms. Account for CPU users before reclaiming source backing. D313's
required block pool 1,126,272 bytes, enemy body 3,577,728 bytes and EVD/ARAM
requirements remain unresolved. r101 EVS, third opening room, audio,
transitions and physical hardware stay in the existing backlogs.
