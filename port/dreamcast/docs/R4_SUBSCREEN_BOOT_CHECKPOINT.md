# D315: native task stack budget restores boot-forward initialization

2026-09-21. D314 remains the first verified source-to-native UI presentation
checkpoint. D315 fixes its demonstrated native file-I/O stack failure; this is
not inventory, menu-interaction, audio, room-gameplay or hardware acceptance.

## Failure and smallest correction

The original D314 executable fails at about 50.5 seconds, before its 105-second
harness deadline. Flycast logs Fatal: SH4 exception when blocked. The same ELF
reproduces the failure in d315b-original-fault and d315c-fault-handler. In D315c,
the saved log reaches both KOS thd_pslist and thd_pslist_queue. The pinned KOS
thd_schedule_inner invokes that pair on **Thread stack underrun**. Its current
source task is tid 10, saved PC 8c1bee62 in strcpy during native file opening.
The final emulator error occurs while reporting this failure; it is not evidence
that the subscreen REL was executed. No OSResetSystem request was recorded.

KOS fs_hnd_open keeps a PATH_MAX=4096 array while calling fs_normalize_path,
which keeps another. The linked SH-4 prologues consume 4116 + 4132 = 8248 bytes
before their source callers, interrupts and further calls. Source task slots
were only 6144/8192 bytes (one slot 12288). Even short paths use those fixed
stack frames. Observing a successful read without a timer interrupt was not
proof that the old stacks were safe.

Reuse: TaskSchedulerInit already allocates and paints one owned source stack
pool, GetStackSize chooses each slice, and OSCreateThread gives that slice to
KOS. The only execution adaptation is a 12288-byte Dreamcast task-stack floor.
The original PowerPC sizes and preprocessing are unchanged. No alternate loader,
forced game-state transition, new ARAM implementation or second renderer was added.

The existing fault observer additionally handles double faults. A bounded
stack report reuses the source B3 paint/DEADBABE guards and deduplicates reused
thread slots. Subscreen logs name completion status and explicitly retain the
no-copy ARAM limitation. These diagnostics do not turn placeholder transfers
into successful resource storage.

## Same fixture, corrected candidate

C:/Flycast-Evidence/re4-dreamcast/d315d-stack-budget runs the same D314e input
fixture and data, retaining visible source UI. It reaches SubScreenGameInit,
the existing native st1_0 binding, the source-derived r120 opening skip into
r100, qualified ReadAreaData and the existing native handgun prolog. No forced
state or subscreen skip is used. The process remains active until the harness's
90-second deadline (logged elapsed 90.005); no stack-underrun/fault report occurs.
A startup image from the checked-in corrected VRAM reader is also retained.
D314's warning/main-menu images remain the accepted UI reference.

| Measurement | Result |
|---|---:|
| Source-owned stack pool, before / after | 124928 / 221184 bytes |
| Added resident stack cost | 96256 bytes |
| Sampled untouched prefixes at subscreen completion | 3016 / 3632 / 3764 bytes |
| Largest sampled used stack | 9272 bytes; exceeds the former 8192-byte slot |
| Sampled stack guards | all DEADBABE |
| ELF text / data / BSS | 2254684 / 75424 / 672024 bytes |
| ELF increase versus D314 | 780 bytes |
| Native UI loads / heap mismatches / missing / queue drops | 40 / 0 / 0 / 0 at the title sample |
| Native UI retained / peak VRAM | 3946496 / 4192256 bytes |

The stack measurement qualifies this boot segment, not every later game call
chain. Source archives remain resident. The correction spends RAM to remove
undefined execution; it is not an optimization or memory-recovery claim.

## Exact subscreen dependency and consumer boundary

Producer: titleExit -> TaskChain(GameTask) -> gameInit -> SubScreenGameInit ->
SubScreenAramRead. All three source requests use DvdReadN mode 9; the existing
DVD reader stages chunks through re4dc_dvd_buff then trans2aram/ARQPostRequest.
No new allocation of whole subscreen files and no REL binding occur here.

| Requested resource | File bytes / aligned reported bytes | Read / conversion / destination |
|---|---:|---|
| rel/Sscrn.rel | 310156 / 310176 | req 18, stat 0; converted REL header ID 71. Raw PPC body retained. Logical ARAM D00000. ID 71 is not in the native module registry; no link attempted. |
| SS/eng/ss_cmmn.dat | 531040 / 531040 | req 19, stat 0; logical ARAM D4BBA0. Existing handlers convert MDT/EFF/UWF/LIT/FCV; required-file gate rejects FNT member #0. |
| SS/eng/ss_pzzl.dat | 912704 / 912704 | req 20, stat 0; logical ARAM DCD600. Required-file gate rejects unhandled file. |

Reported total 1753920 (0x1ac340), remaining logical source ARAM 1391808
(0x153cc0). **ARQPostRequest still completes without copying**. Those offsets
and read-success statuses establish the original control flow, not resident
subscreen data. They neither allocate that much native RAM nor prove data
recovery. The last successful initialization consumer is SubScreenRoomInit,
which prepares state, followed by gameInit's cockpit/item/stage initialization.
No subscreen archive consumer or Sscrn entry point ran.

On an actual inventory open, SubScreenExec still requires its memory-swap/
residency contract, qualified archives, and the existing static-module mechanism
extended to ID 71 before native consumers may run. Common archive root metadata
saying complete is insufficient: check_required correctly reports the nested
FNT rejection. The preserved subscreen-qualification.json records both failures.
Do not compact the unbound REL or enable those consumers on these unqualified
bytes. Reuse the current parsers and Package/UI resource connection as they are
qualified; do not build a parallel backend.

## Returned opening-room frontier

The candidate consumes the unchanged r100.dar: 4669568 decoded archive bytes,
with original ROOM/FOOT sound-block dispatch (still no audible output).
Required block-model allocation is 1126272 bytes with only 107520 free. Required
em12 body is 3577728 with 97216 free on the first attempt, 31616 after TexRender.
R100Init reports enemy creation failure; source room tasks and EVD placeholder
activity are not room acceptance. The low room memory is real, including this
stack correction, D314 integration cost, source archives and remaining resources.

Continue source-to-native room/block/actor resource ownership to reduce measured
resident cost, retaining CPU users and source selection. The original archive,
block pool, enemy, EVD/ARAM, source effect/ID, audio and native 3D requirements
remain open. Inventory readiness, r101 EVS and the third verified opening room
remain in the existing backlog. No roadmap or fidelity concession is introduced.

## Evidence and validation

- ELF SHA256: ed95f7b7e50663b9f43e06a8c16412050f231c0c182a17b7a80f1015f0a90f15.
- Disc SHA256: 415ee95c89208cf1f922eb7e7abf20e37780ff7639a0041e8867685c7c17e88b.
- Flycast SHA256: 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a.
- r100 DAR SHA256: 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739.
- KOS 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3; SH GCC 15.2.0.
- Existing evidence_manifest.py pins/validates executable, disc, assets, fixture,
  source patch/snapshots, launcher/logger, capture reader, logs and image.
- scheduler.cpp / sscrn.cpp PPC preprocessed tokens match pre-slice source.
  This is not a full ProDG comparison. Game links with the same five missing stubs.
- D314 focused Package/fence/identity tests and the two new readback tests pass.
- Negative diagnostics retained: d315a's diagnostic-only relink happened to pass
  but did not repair the unsafe stack budget; no credit for that pass. D315b's
  optional GDB connection was unavailable; its ordinary replay still reproduced
  failure. D315c only registered the original double-fault observer in RAM, with
  exact patch recorded; it still failed in the stack-report path. No such memory
  modification was used for D315d acceptance.
