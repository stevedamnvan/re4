# RE4 Dreamcast first-stage dependency and allocation audit

2026-09-22. Bounded read-only review of `/root/work/re4-dreamcast`, D346 HEAD `0ff83d9a15d4715c29bdc0366e576baee59798b3`; inherited edits preserved. Supporting discovery report for PLAYABLE_PATH and R4_ASSET_RESIDENCY_PLAN, not a new roadmap. No build, extraction, runtime, emulator, model work or evidence changes.

## Current-use qualification (2026-09-22)

The initial D346 census below is historical source discovery. The later opening
route section supersedes its unresolved third-room statements: r100 -> r101 ->
r103 is established from source/data, while native traversal remains unproved.
Converter fix `961c51e` is already merged; selected r101 target data is still
pending. Later D349-stack material/lighting work and accepted D356v4 B appearance
supersede treating every original presentation rejection as a current missing
implementation. Recheck a listed consumer against current code before assigning
work. Keep the source dependencies and allocation/lifetime formulas as planning
inputs; this document does not certify current target timing or whole-stage fit.

## Scope and evidence classes

`src/st1/st1.cpp:90-118` registers 29 rooms: r100-r10f, r111-r113, r117-r120; indices 110 and 114-116 are absent. All have source. `sce_sys.cpp:102,154` dispatches the room table; `game.cpp:1291-1398` owns normal door cleanup/reload. Scope is the entire registered stage, although implementation acceptance remains menu plus the first three actual playable rooms. r120 is cinematic staging. Only source r120->r100 and authored r100->r101 are established here; the third playable room and full conditional graph remain unresolved.

The selected `/root/probe/d343-mirror` has room ARC identities for r100, r101, r120, but native DAR containers only for r100/r120. r101 ARC is 5,466,016 bytes and DAS 5,033,632; neither satisfies native `read.cpp:244-260`, which explicitly requires DAR. The other 26 rooms lack those selected room archives entirely. Thus **27 registered rooms lack ready native room containers**, without implying 27 observed failures. Native Yz2 work is not required: `read.cpp:220-243` is PPC-only; native already reads decoded LE containers and binds source identities (:244-280).

Confirmed cause = explicit native reject/stub or missing selected artifact. Occurrence risk = source caller exists but conditional reachability/data/capacity are unqualified. Route verification = code exists but end-to-end behavior is unaccepted. No static call below proves target execution.

## Shared confirmed causes

| Priority | Confirmed cause and trigger | Reuse and next bounded qualification | Dependency/confidence |
|---|---|---|---|
| P0 | r100 event activation: `r100.cpp:463,506,551` loads the named data unit and directly borrows/restores the enemy archive. General `event.cpp:2384-2455,2575-2604` provides another borrow/restore path; both owners need coverage. Immutable native EVD backing rejects mutable swap (`native_event_file.cpp:83`). s03 needs 1,341,504 vs compact enemy body 1,105,152; s20 independent MRAM 689,632 vs 66,592 late free. | Existing immutable preflight, source completion and `EvtFree`; qualify a specific source completion adaptation under cutscene deferral or a reversible writable borrow with lifetime proof. A failed read is not a skip. | Confirmed source capacity/backing gap; current straight fixture did not reach rejection. Depends on exact event side effects and live enemy pins. |
| P1 | Inventory calls `MemorySwap` with 3,145,728-byte SS window (`sscrn.cpp:77,501,634`); ARAM requests complete without transfer (`audio_stub.cpp:131-149`). | Existing subscreen loader and swap owners; qualify one route inventory open/change/close with a real bounded backing/reload policy. | Confirmed missing storage contract; inventory occurrence/peak not observed. Shares P0 backing work, not a separate 3 MiB deficit. |
| P1 | Sound data consumed by `snd.cpp:115-175` reaches transfer-without-copy ARAM bridge (`audio_stub.cpp:131-149`). | Source sound door/reset state machine plus AICA hook; one BGM/SE sample bank with real transport/playback/release. | Confirmed native audio gap. AICA and main-RAM budgets not measured; movie presentation remains deferred. |
| P1 | Model pass state at `native_ui.cpp:372-425` rejects masks/no-image and incomplete blend families. | Existing native packets/identity cache and source OT eligibility; one eligible mask pass with correct threshold/alpha/mask texture, then lighting. | Confirmed native presentation gap; 39 mask parts in Leon archive 9 are not 39 always-visible missing parts. Complete 119-joint assembly does not accept appearance. |
| P2 | Required next room/event occurrence lacks qualified data; native `read.cpp:244-275` explicitly fails missing/invalid container. | Existing converter, prepared archive and room retirement; resolve next authored exit, qualify only that room and its dependencies. | Confirmed selected-mirror coverage gap; 27 rooms lack native .dar containers, not 27 reached failures. Third playable room remains unresolved. |


## Shared occurrence risks and route verification

- Module/data coverage: all four stage modules and every registered room source occur in `game/obj/modules.mk:3,15,27,39`. Old `obj/missing.txt`/`undefined.txt` are not selected-ELF proof. Actual reached enemy/player/weapon IDs must match current module descriptors and selected ELF; SndCall, EstSet and MotionMove source presence is not a native playback/rendering claim. Use explicit module binder and unknown-ID failure, not a new loader.
- Event paths bypass the general EvtRead helper: r100/r101/r10b/r117/r11c call `MemorySwap` directly (room anchors below). A general helper fix must cover those owners too. EVD table entries are source occurrences, not proof each variant executes in one route. Use existing immutable preparation and the correct callback/completion/rollback owner.
- Source data consumers (`read.cpp:278-280`, `sce_at.cpp:435-455,4067-4119`, `id_sys.cpp:1002-1035,1153-1185`) retain room/trigger/material references. Alternate costumes, animated/masked materials, event variants and EMI entries require actual tags and native lifetime qualification. A filename, TODO or missing census symbol is not a blocker by itself.
- Effects and lighting: room `EstSet`, `EatMgr`, `LightMgr`, reflection and water-render consumers below identify occurrences needing native qualification. Existing identity/effect bridges and source pass eligibility are reusable; binding is not visible effect completion. `native_ui.cpp:368-425` bounds current presentation. All 119 Leon joints/eight components are assembled; mask/pass semantics remain incomplete, and archive 9's 39 mask parts need source OT eligibility rather than an all-parts-must-draw claim.
- Route checks, not absent implementations: normal menu/New Game (`main.cpp:199,460-461`, `game.cpp:395-460`), authored collision/camera (`sce_com.cpp:829-874`), combat/player/weapon (`read.cpp:667-867,962-1130`), HUD (`cockpit.cpp`), door/re-entry (`game.cpp:1291-1398`), death/retry/menu (`game.cpp:1142-1260,1373-1409`) and inventory return (`sscrn.cpp:378-672`). Reuse source ownership and existing native retirement; verify required flags, inventory, health, retained pointers and task cancellation along the actual route. No new missing algorithm is inferred.
- Completed mechanisms excluded from new work: D346 counted task handoff and event preflight; D344 sparse stable enemy pages and crow packages; D343 option compaction; D345 source alpha/vertex path; D340 immutable EVD; existing hot-motion/room retirement, texture/package upload and static module binder. No savings counted twice. Cutscene presentation remains deferred; required source completion effects are not deferred.

## Allocation-pressure ledger (separate address spaces)

Selected build options are from immutable `independent-spikes-20260922T112434Z/build-options.txt:1`; source heap values from `CLAUDE.md:24-47` and D346 checkpoint, not a new capture. Sizes below are bytes. None are summed across all 29 rooms.

| Domain / owner and source callsite | Reservation, observed backing or formula | Lifetime/coexistence and actionable lever |
|---|---|---|
| Main RAM fixed arena, `platform/mem.cpp:20-31,46-74` | sound 524,288; core 1,360,608; option 149,920; player 846,656; weapon 247,776. Sum fixed 3,129,248; source heap capacity 8,840,576. DVD staging 131,072 is separate BSS (:103). | Fixed regions coexist with source heap, ELF/BSS, runtime, native caches. Lowering a file alone does not shrink compile-time reservations. Core/option/player/weapon compaction already selected; alternate files need pre-transfer bounds and matching reservation qualification. Do not subtract these savings again. |
| Main RAM room, `read.cpp:244-275,278-280` | Native room payload = `roomInfo.size[0][0]` plus actual allocator overhead; `.dar` file also contains sound and is NOT this allocation. Source PPC floor `max(decoded, ROOM_ARC_SIZE-used)` is not native formula. | Room pointers (RTP/MDT/OSD, geometry/collision/effect/UI records) stay live through room; retire through `game.cpp:1344-1398`, `read.cpp:362-369`. Only proven non-CPU texels may be externalized. Record actual type-0 request and native cache overlap on next room; do not add `.arc` and `.dar` duplicate payloads. |
| Main RAM block pool, `block.cpp:165-186` | `max_connected_sets(sum(m_size of MRAM blocks))`; selected 1,126,272 now allocates. | Pool persists across block movement. A smaller block0 alone saves zero because blocks1/2/3 set max. Review/repack every controlling set or justify bounded reload retaining source visibility/collision, then show decreased source reservation. |
| Main RAM enemy archive, `read.cpp:551-605` | For a newly loaded module and no supplied address: `max(converted len, requested size)`; module split may add `bssSize` allocation at :593. Supplied address: prove capacity separately. em12 selected body 1,105,152 now allocates. | Archive pointers retained by model/motion/effects; event borrowing needs snapshot and restoration. Existing `EmReadSearch` hits (:682-692) return the old archive without resizing; requested size is NOT a guaranteed capacity. Other stage enemies: apply same new-load formula to actual requested EMI ID and existing converted len; unknown here, no guessed MB. Sparse enemy/model/parts pages already reduce work arrays while preserving IDs. |
| Main RAM motion | Hot selected em12 keys 952,768 + metadata retained (D346). Existing D325 external transport unique bytes 1,702,176; not another resident sum. | Must coexist with archive and active model pointers; future enemies add only simultaneous pinned hot sets. Existing motion bridge is reusable. Zlib's historical 437,440 disc reduction is zero runtime saving; qualify a bounded pin/reload set before reclaiming any hot bytes. |
| Main RAM event, `event.cpp:2422-2455,2523-2564,2575-2604` | s03 1,341,504 > borrowed 1,105,152 by 236,352 BEFORE writable snapshot; s20 689,632 MRAM. Other events: `unit.m_size`, requested `sz`, borrow capacity and snapshot span determine peak. | Immutable prefetch is not mutable activation. Peak includes persistent room/player, enemy hot motion and required writable restore copy/staging. Source-completion adaptation may avoid presentation working set only after necessary effects are traced; no assumed deletion savings. |
| Main RAM inventory, `sscrn.cpp:77,501-511,576,600,634` | SS swap span 3,145,728; examination allocation 256,000; module BSS dynamic. Native actual inventory peak unknown. | Room-owned retained pointers cross pause; cannot free whole room without reconstruction contract. Reuse source heap-12/subscreen ownership. Count replacement backing and temporary transfer overlap, not GC ARAM addresses as real native storage. |
| Main RAM player/weapon, `read.cpp:802-820,1083-1107` | Actual request sum info sizes [0][0]+[0][1], constrained by selected fixed reservation above. Source player guards 0x118000/0x188000 and WEP_DATA_MAX are not selected compact capacity. | Weapon reload `ReleaseWepData` precedes new read; inventory-driven alternate weapon and Ashley/alternate player occurrences require actual converted bytes and native bound guard. Unknown alternate sizes; reuse selected pl00/wep02 compact identity path. |
| VRAM native textures | D326 em12 36 packages = 1,869,824 payload bytes IF all resident; D344 crow texture 32,768. These are inventory examples, not total live VRAM. | Count unique compatible payload once, plus palette/mips/alignment/framebuffers/TA and simultaneous room/player/enemy/hud. Cache sharing is already available; need current occupancy/largest block at transition. No measured full-stage fit. Smaller source files do not imply smaller uploaded format. |
| AICA | Actual banks/streams/code/buffers unknown because audio transfer is stubbed. | Separate from CPU heap/VRAM. Qualify one real sample/stream ownership path, pricing sample format, channels and double buffers. Do not allocate entire .sbb container or pretend GC ARAM maps to AICA. |
| GC ARAM logical storage | Immutable EVD transport exists; writable swap/audio storage does not. Source inventory window 0x300000 and other logical addresses are contracts, not Dreamcast memory. | Decide per-owner native backing/reload with writable restoration and concurrency. Shared mutable backing root cause spans events/inventory/audio; never count one region multiple times or total allstage files. |

Ranked footprint opportunities: (1) required event lifetime/completion and writable snapshot contract; (2) controlled block-set maximum, not block0 alone; (3) existing texture/compact record paths extended only to proven CPU-independent required families; (4) future enemy hot-set/pin and alternate fixed-region qualification; (5) reviewed mesh reduction only where the actual retained arena shrinks. Historical r100 remaining base texels 968,736 and room BIN backing 529,344 are ceilings from existing inventory, not new recoverable savings; em meshes 415,040 are likewise not guaranteed reclaimable. All already-kept D325-D344 savings are excluded from new gains. No water/FMV spike candidate is assumed promoted.

## Entire-stage caller coverage

All anchors below are `src/st1/<room>.cpp` physical lines. Event suffixes expand to `<room><suffix>.evd`; the private audit summary.json also records exact filenames and literal callsites. “None explicit” means no explicit EVD or EmReadSearch request in that room source, not absence of data-driven ESL/EMI/AEV or common loaders. Names in r100/r10b tables are tied to actual `DC.setData` calls. EmReadSearch tuples preserve `(id, address, requested size)`; do not confuse ESL indices in setEm with archive IDs. Each room's conditions/Part/flags govern whether a call is reached.

| Room | Explicit event requests / actual consumer | Explicit EmReadSearch calls | Special source consumer / lifetime |
|---|---|---|---|
| r100 | s03 @438; s01 @438; s02 @438; s20 @438; s30 @438; s41 @439; s42 @439; s43 @439; s44 @439; s40 @439; table -> DC.setData :463 | `0x12, 0, 0` @160; `0x12, 0, 0` @221 | Direct event borrow/restore :506,551; room/player archive-backed objects :174-176; source event activation :601,631 and door sound :698. |
| r101 | s00 @55,211; s21 @56,222; s30 @57,220 | `0x26, 0, r101_work->evt00->m_size` @213; `0x15, 0, r101_work->evt21->m_size` @225; `0x15, 0, r101_work->evt30->m_size` @227 | Direct em15/em26 swap :666,685,1002-1007; language-specific id101.eff/event001.uwf :407-415; object+SE :201-205. |
| r102 | s00 @61 | `0x18, 0, 0` @60 | Event SetEvt :78; no-water effect policy :51; source enemy placement :100; cover SE :143. |
| r103 | None explicit; data-driven unknown | `0x12, 0, 0` @206 | Enemy archive retained in player subArc :206; room objects :230; lid/cover SE :277,322,341. |
| r104 | s20 @196,694,745; s10 @718,744; s01 @742,755; s02 @743,758; s00 @752 | None explicit; EMI/common loader unknown | em13 event borrowing :694,718; source spawns :772-783; LightMgr light mutation :820; key/door tasks :208-209. |
| r105 | s10 @163,572,578; s00 @173,571 | None explicit; EMI/common loader unknown | em15 events :571-578; key/item door tasks :140-145; retained sound handle :438; source spawns :604-613. |
| r106 | s00 @99 | `0x12, 0, 0x3C0000` @101; `0x29, 0, 0` @102; `0x2A, 0, 0` @103; `0x2E, 0, 0` @104 | Conditional four-module preload :97-104; locked door room pointers :93; item/shelf callbacks :95-96; SetEvt :368; rolling object :472. |
| r107 | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Water OT :67; fish cEm27 water height :85; BGM task :54 and SE :122. |
| r108 | None explicit; data-driven unknown | `0x17, 0, 0` @121 | em17 preload :121; bell SE :230-245; event light teardown :401. |
| r109 | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Three SAT and EAT instances retain room entries :54-59; torch deletion :61-68; source hut visibility :82-95. |
| r10a | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Per-frame water OT and rock completion flag :188-190; source reinforcement dispatch :175-180. |
| r10b | s20 @219; s21 @219; s22 @219; s00 @219; s10 @219; table -> DC.setData :230 | None explicit; EMI/common loader unknown | Boss em2f direct swap/capacity guard :244-254 and restore :271-274; floating-island room motion :165-173; attached animated heads :581-583; light :625. |
| r10c | None explicit; data-driven unknown | `0x12, 0, 0` @122 | em12 preload :122; retained SE handles :193-195; wheels/gate sound :823,848-886; room objects :275,320; water collision query :1189. |
| r10d | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Only explicit room work allocation :19, empty Main :23-25. ESL/AEV/SMD occurrence is data-driven and unqualified; no invented event/script gap. |
| r10e | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Conditional enemy-list placement :46-58; delayed collision re-enable :73-75; previous-room/Part/flags govern lifetime :32-61. |
| r10f | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Animated room objects :237-239,372-374; table-driven setEm :426; room object :442; SE :487,540. |
| r111 | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Rack bounds :41-51; rain attached effects :57-59; broken-window models :62-66; thunder effect loop :90-110. |
| r112 | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | No-water policy :33; thunder and reused BGM tasks :34-35; data-driven remaining occurrences unknown. |
| r113 | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Thunder/Ashley/cesspit tasks :107-117; file interaction :130; partner-relative SE :163,175. |
| r117 | s00 @85,164; s10 @86,166 | `3, 0, W->evd1->m_size` @167 | em03 retained pointer :172; direct s00/s10 swaps :390-396,431-438; room model :155; source light :960; inventory follows Ashley event (trace before deferral). |
| r118 | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Source enemy wrapper :101; source SE :165,217; remaining model/event/module IDs data-driven. |
| r119 | s00 @116,264; s10 @265,383; s20 @266,307; s30 @267,372 | None explicit; EMI/common loader unknown | em2b event borrow :307,372,383; direct light work :209-228; source positional sound :439-517. |
| r11a | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Persistent player water effects :34-35 and water-hit table :36; per-frame water OT :42. |
| r11b | s00 @410 | None explicit; EMI/common loader unknown | Water-hit table/rain :114-118; event :410; event stand-in TexRenderModSet/reflection :480-487; effect teardown uses render-target masks :496-501. |
| r11c | s00 @66,291; s10 @67,293; s20 @425,508 | `0x13, 0, W->evd0->m_size` @294; `3, 0, 0x120000` @295; `4, 0, 0x120000` @372 | Direct em13/em03 swap :361-368,580-587; retained mod3 :299; partner destroy :317 and em04 creation :372-373; retained gate/gear sound :750,816. |
| r11d | None explicit; data-driven unknown | None explicit; EMI/common loader unknown | Attached core-backed object :217-218; source enemy wrappers :210,233; partner-relative SE :421,433; timed door/enemy tasks :105-135. |
| r11e | None explicit; data-driven unknown | `0x2B, 0, 0` @101 | em2b preload :101; positional enemy sound :212-280; partner-relative sound :436. |
| r11f | s00 @99,188; s01 @191; s02 @193; s11 @561,581; s10 @562,569 | None explicit; EMI/common loader unknown | Event chain :188-194,561-581; source enemy wrapper :194,490-491; four room-backed models :153-162; Ashley movement task :619. |
| r120 | s01 @90,94; s00 @91 | None explicit; EMI/common loader unknown | Sofdec opening.sfd :74; event chain :90-94; source light :152. Staging/completion only, not playable-room acceptance. |

## Concrete future pressure contracts

- **r106 conditional encounter (`r106.cpp:97-104`):** new em12 request floor `0x3C0000` = **3,932,160**, then em29/em2a/em2e. This is source-requested reserve, not a measured native peak or a demand to retain the original representation. A compact 1,105,152-byte em12 file does not automatically reduce that new-load floor. Identify the reason for the reserve and consumers before qualifying a smaller native request. Actual simultaneous enemy lengths/hot sets remain unknown.
- **r11c siege (`r11c.cpp:291-299,317-328,361-373,580-587`):** em13 reserved for s00; em03 and later em04 each request `0x120000` = **1,179,648**. Actor destruction is not archive release; em03 pointer is retained and later borrowed for s10. Price actual module lifetimes plus event snapshot and partner transition, not merely live actor count. New-load floor is max(archive length, request); existing-module calls retain existing capacity. Do not sum both floors without proving their overlap at the selected phase.
- **r101 (`r101.cpp:211-227,666-685,1002-1007`):** em26 floor s00.m_size; em15 floor max(s21.m_size,s30.m_size) on that conditional branch. Direct swaps require writable restoration. Existing event/file lengths remain unknown; no guessed MB. Missing r101 DAR is independently confirmed.
- **r117 (`r117.cpp:164-172,390-396,431-438`):** em03 requested against s10.m_size, but the retained module is also directly borrowed for s00. Verify BOTH spans <= actual capacity; the s00 path has no local size comparison before MemorySwap. This is a confirmed source contract requiring validation, not proof of overflow because actual lengths are unknown.
- **r10b (`r10b.cpp:219,230,244-274`):** five source event names borrow boss em2f; explicit guard compares event.m_size to module.size before swap, then `freeEvent` restores and clears. Qualify mutable backing and the actual boss archive/hot set; do not treat immutable prefetch or guard presence as successful activation.
- **Other explicit borrowing:** r104 uses em13 (s10/s20), r105 uses em15 (s00/s10), r119 uses em2b (s10/s20/s30). These follow general `event.cpp:2384-2455`, but need actual per-file m_size, existing/new archive status and snapshot owner. Non-borrowed events consume their MRAM working set alongside live room resources. Event names and anchors above identify the exact narrow data checks.

`read.cpp:682-692` is important to every formula: **EmReadSearch returns an already loaded module without resizing**, so a later larger requested size is not evidence the archive can hold it. Reuse the existing native preflight and actual ReadModule.size. Any reserve reduction must retain all source pointer/restore contracts and demonstrate smaller source-heap reservation, not only smaller files.

## Fixed reservation verification and limits

Current `port/dreamcast/game/obj/core-budget.h:1-4` reads CORE=1,360,608, OPTION=149,920, PLAYER=846,656, WEAPON=247,776, matching immutable `independent-spikes-20260922T112434Z/build-options.txt:1`. `platform/mem.cpp:20` adds SOUND=524,288; sum **3,129,248**. These are capacities, not current used payload totals. `mem.cpp:46-74` actually uses these macros to carve the arena. Existing D346 selected source heap remains 8,840,576, late free/largest 66,592; no fresh runtime measurements were made.

Remaining narrow checks: next authored AEV destination/condition, native r101 container/sound packaging, actual EMI/module IDs and converted lengths, per-event m_size and all retained pointers, pinned hot motion, mutable snapshot peak, VRAM unique-live payload and AICA playback budgets. Full stage source coverage is not full asset or dynamic reachability coverage. No new failing test, hardware acceptance, image-quality acceptance or promoted water/FMV candidate is claimed.

## Confirmed opening route and immediate destination gaps

A focused follow-up against current AEV data and source door overrides identifies
normal fresh-opening progression as **r100 -> r101 -> r103**. This is source/data
proof of the intended route, not completed native traversal. R120 is staging.
R100 AEV area0 targets r101. R101 area2 targets r103; its village-fight denial
callback is removed by the bell-event completion. R102 and r105 are separate
locked routes, not the next rooms by numerical order.

Relevant source contracts: `include/sce_at.h` door records; `src/st1/r101.cpp`
`r101_startEvent30`/`r101_Event30`, fight door overrides and `SceAtDataReset(0/2)`;
`src/game/game.cpp` `gameDoordemo`/`gameRoomMemInit`; `src/game/read.cpp`
`InitModule`. Preserve inventory/health/flags, stop old task/I/O ownership, retire
GPU/native resource references and then replace room heaps. Actor destruction is
not proof that its module archive is retired. S30 explicitly destroys actors and
releases em15 before its MRAM event load; do not reuse r100's borrowed-event
assumptions for that path.

The selected r101 ARC is present but its native DAR is absent. The next bounded
conversion rejection is EVS#24, a32-byte zero-entry table with CD padding.
`EventMgr::SetEvs` forms the table pointer even for zero entries, so qualification
must handle that unused offset deliberately and reject nonempty/unknown forms.
Update 2026-09-22: converter fix `961c51e` is now in primary history. It
qualifies a private 10,499,648-byte r101 DAR (transport bytes, not heap demand),
but the selected mirror still lacks r101.dar and target loading is unproved.
See `R4_R101_EMPTY_EVS_CHECKPOINT.md`; do not repeat the converter work or infer
room acceptance. This does not require another general event decoder.

The matching r103 source container, r101 s00/s21/s30 original EVDs and em15
archive are absent from the selected inputs. The current static module registry
also lacks em15/em26 bindings (REL IDs19/14). Presence of em26.drs alone does not
qualify its executable entry points or memory budget. Use the existing qualified
room/event/module tools for these precise dependencies; no full-stage extraction
or automatic broader asset conversion is prerequisite.

Private reproducible source/data anchors and recipes:
`/root/probe/re4-opening-gap-audit-20260922/next-room-dependency-brief.md`.
