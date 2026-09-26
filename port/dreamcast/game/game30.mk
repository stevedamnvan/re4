# Game-side CPU knobs (D367 game30). Included by the Makefile after the flag variables and
# object lists are defined. Every knob defaults to 0 and then contributes nothing: the
# reference image is byte-identical with or without this file.
#
# Bit-identical by construction or by proof (gate: the determinism trace, LOGIC_TRACE=1):
#   GAME_PS_ALIAS=1   the paired-single SDK entry points (PSMTX*/PSVEC*) are bound at link to
#                     the C bodies they forwarded to (platform/ps_alias.ld): the same machine
#                     code runs minus one call frame per call (~3,700 call sites).
#   GAME_SH4_MATH=1   (implies GAME_PS_ALIAS) hot PS entry points bound to hand-scheduled
#                     SH-4 bodies (platform/mtx_sh4.S) that execute the identical FP dataflow
#                     (tools/fpsym2.py --strict proof over the linked ELF).
#   GAME_ROOM_INDEX=1 cRoomData::getRoomSavePtr through a record-index table built once from
#                     the static stage tables instead of a ~70-entry scan per call (exhaustive
#                     host check over all 65,536 room ids).
#   GAME_ROT_CACHE=1  RotMatrix (Rz*Ry*Rx from Euler angles: 6 sinf/cosf) memoised on the exact
#                     angle bits in a 32-entry table; a hit returns the bits a call computes (pure
#                     function). Hit rate reported by GAME_TICK_LOG ("rotcache=hits/misses").
#   GAME_CPU=1        PS_ALIAS + SH4_MATH + ROOM_INDEX (ROT_CACHE stays separate until its hit
#                     rate is measured).
# Test instrumentation (never in a product image):
#   LOGIC_TRACE=1     one determinism record per frame-loop iteration (logic_trace.cpp).
#   GAME_TICK_LOG=N   one line per N frames with the mean/max time of every ProcessTickGet phase
#                     (TaskScheduler, EmMgr.move, Player, objTrans, ...) through re4dc_log: the
#                     serial console on real hardware (tick_log.cpp). Observation only.
#   LOGIC_TRACE_DELAY_US=N  (trace builds only) burn N us per frame in the trace hook: the
#                     timing-perturbation control arm that proves the fixture is insensitive to
#                     CPU speed before any A/B verdict is trusted.
# Build every arm in its own OBJDIR (flag changes do not rebuild existing objects).
GAME_CPU ?= 0
ifeq ($(GAME_CPU),1)
GAME_PS_ALIAS ?= 1
GAME_SH4_MATH ?= 1
GAME_ROOM_INDEX ?= 1
endif
GAME_PS_ALIAS ?= 0
GAME_SH4_MATH ?= 0
GAME_ROOM_INDEX ?= 0
GAME_ROT_CACHE ?= 0
LOGIC_TRACE ?= 0
GAME_TICK_LOG ?= 0
LOGIC_TRACE_DELAY_US ?= 0
# LOGIC_TRACE_MASK_RENDER=1 (trace builds only, opt-in): leave the render-only be_flag 0x08000000
# out of the hash (logic_trace.cpp; the frame pacing gates). Default 0: hashes unchanged.
LOGIC_TRACE_MASK_RENDER ?= 0

GAME30_LINK_INPUTS =
ifeq ($(GAME_SH4_MATH),1)
ifneq ($(GAME_PS_ALIAS),1)
$(error GAME_SH4_MATH=1 binds the PS* entry points and needs GAME_PS_ALIAS=1)
endif
PLATFORM_OBJS += $(OBJDIR)/platform/mtx_sh4.o
GAME30_LINK_INPUTS += platform/ps_alias_sh4.ld
$(OBJDIR)/platform/mtx.o: PLATFORM_CPPFLAGS += -DRE4DC_PS_ALIAS=1 -DRE4DC_SH4_MATH=1
$(OBJDIR)/platform/mtx_sh4.o: platform/mtx_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
else ifeq ($(GAME_PS_ALIAS),1)
GAME30_LINK_INPUTS += platform/ps_alias.ld
$(OBJDIR)/platform/mtx.o: PLATFORM_CPPFLAGS += -DRE4DC_PS_ALIAS=1
endif

ifeq ($(GAME_ROOM_INDEX),1)
$(OBJDIR)/src/game/roomdata.o: GAME_CPPFLAGS += -DRE4DC_ROOM_INDEX=1
endif

ifeq ($(GAME_ROT_CACHE),1)
$(OBJDIR)/src/game/math_sub.o: GAME_CPPFLAGS += -DRE4DC_ROT_CACHE=1
endif

# design-logic prototypes (bit-exact by construction; gate: LOGIC_TRACE STRICT):
#   GAME_PWC_DIAG=1  partsWorldCalc non-uniform-scale path: the two multiplies by a diagonal scale
#                    matrix run the concat kernel's own dataflow with the provably dead terms removed
#                    (diag a*s + 0, column 3 unchanged, NaN guard -> original path; model.cpp comment,
#                    host proof design-logic/proofs/pwc_diag_check.c). =2: check build, both paths,
#                    mismatches counted in the tick log ("pwcdiag=checks/mismatches").
#   GAME_ATCHK=1     EmAtCheck walks each actor list once per call (collidable bodies into an array,
#                    next-body prefetch) instead of three times.
#   GAME_MOTION_INDEX=1  re4dc_motion_acquire finds the clip record by binary search over the
#                    bind-validated, strictly increasing record offsets instead of a linear scan
#                    (platform residency layer only; returns the same record, so the same key table).
GAME_PWC_DIAG ?= 0
GAME_ATCHK ?= 0
GAME_MOTION_INDEX ?= 0
# GAME_SINCOS=1 (design-logic P6, needs GAME_TRIG=1): RotMatrix and the SDK rotation builders take sin and
#                    cos of one angle from re4dc_sincosf (game30_trig.c: one |x| test and argument reduction,
#                    the same kernels): bit-identical by construction, all 2^32 inputs checked on the host
#                    (tools/game30/sincos_exhaustive.sh).
GAME_SINCOS ?= 0
ifneq ($(GAME_SINCOS),0)
ifneq ($(GAME_TRIG),1)
$(error GAME_SINCOS needs GAME_TRIG=1)
endif
$(OBJDIR)/game30_trig.o: KOS_CFLAGS += -DRE4DC_SINCOS=1
$(OBJDIR)/src/game/math_sub.o: GAME_CPPFLAGS += -DRE4DC_SINCOS=1
$(OBJDIR)/sdk/mtx.o: SDK_CFLAGS += -DRE4DC_SINCOS=1
endif
ifeq ($(GAME_MOTION_INDEX),1)
$(OBJDIR)/platform/native_motion.o: PLATFORM_CPPFLAGS += -DRE4DC_MOTION_INDEX=1
endif
ifneq ($(GAME_PWC_DIAG),0)
$(OBJDIR)/src/game/model.o: GAME_CPPFLAGS += -DRE4DC_PWC_DIAG=$(GAME_PWC_DIAG)
endif
ifeq ($(GAME_PWC_DIAG),2)
$(OBJDIR)/tick_log.o: PLATFORM_CPPFLAGS += -DRE4DC_PWC_DIAG_LOG=1
endif
ifeq ($(GAME_ATCHK),1)
$(OBJDIR)/src/game/at_mod.o: GAME_CPPFLAGS += -DRE4DC_ATCHK=1
endif
# GAME_ATCHK_LIST=1 (needs GAME_ATCHK=1; square plan step 1): EmAtCheck keeps the EmMgr / ObjMgr alive
#                    lists in list order in an array, rebuilt when the list changed (cManager.h bumps a
#                    per-type generation on every list or work-array change), and tests each body's live
#                    collision flags from it with a deep prefetch. Same candidates, same order.
#                    =2: every cached use is checked against a list walk ("ATL" log line, mismatch count).
#                    A header knob: every object gets the define, so each inline list mutation bumps.
GAME_ATCHK_LIST ?= 0
ifneq ($(GAME_ATCHK_LIST),0)
ifneq ($(GAME_ATCHK),1)
$(error GAME_ATCHK_LIST needs GAME_ATCHK=1)
endif
GAME_CPPFLAGS += -DRE4DC_ATCHK_LIST=$(GAME_ATCHK_LIST)
PLATFORM_CPPFLAGS += -DRE4DC_ATCHK_LIST=$(GAME_ATCHK_LIST)
endif
# GAME_ATCHK_CACHE=1 (needs GAME_ATCHK_LIST=1; G, collision traversal; exact): EmAtCheck keeps each list's
#                    collected bodies while the list is unchanged and applies to them every body whose
#                    collidable test (cAtariInfo m_flag bit 0x200, m_radius2 != 0) changed: the two fields
#                    become wrappers that note such writes, and taking their address does not compile
#                    (atariInfo.h). A header knob: every object. =2 (check build): every reuse compared
#                    with a fresh collection ("ATC" lines).
GAME_ATCHK_CACHE ?= 0
ifneq ($(GAME_ATCHK_CACHE),0)
ifeq ($(GAME_ATCHK_LIST),0)
$(error GAME_ATCHK_CACHE needs GAME_ATCHK_LIST=1)
endif
GAME_CPPFLAGS += -DRE4DC_ATCHK_CACHE=$(GAME_ATCHK_CACHE)
PLATFORM_CPPFLAGS += -DRE4DC_ATCHK_CACHE=$(GAME_ATCHK_CACHE)
endif
# GAME_OBJHIT_LIST=1 (needs GAME_ATCHK_LIST=1; G, collision traversal; exact): ObjHitCheck (the camera's
#                    line against every live object) walks GAME_ATCHK_LIST's array of ObjMgr's alive list,
#                    the objects' header and id lines prefetched ahead, instead of chasing pNext.
#                    =2 (check build): the array compared with the live list at every call ("OHL" lines).
GAME_OBJHIT_LIST ?= 0
ifneq ($(GAME_OBJHIT_LIST),0)
ifeq ($(GAME_ATCHK_LIST),0)
$(error GAME_OBJHIT_LIST needs GAME_ATCHK_LIST=1)
endif
$(OBJDIR)/src/game/at_mod.o: GAME_CPPFLAGS += -DRE4DC_OBJHIT_LIST=$(GAME_OBJHIT_LIST)
endif
# GAME_LINE_LEAF=1 (G, collision traversal; exact): the scenery line queries' leaf loop (atari.cpp
#                  blkPolyLineCkCore) runs the polyBit dedup and At_poly_line_ck's first four tests (plane
#                  crossing, three edge sides) in platform/lnk_sh4.S with the same float operations on
#                  the same operands; only the polygons passing all four reach At_poly_line_ck. =2 (check
#                  build): every verdict compared with the tests in C and At_poly_line_ck ("LNK" lines).
GAME_LINE_LEAF ?= 0
ifneq ($(GAME_LINE_LEAF),0)
PLATFORM_OBJS += $(OBJDIR)/platform/lnk_sh4.o
$(OBJDIR)/platform/lnk_sh4.o: platform/lnk_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_LEAF=$(GAME_LINE_LEAF)
endif
# GAME_LINE_WALK=1 (G, collision traversal; exact): the scenery line queries' block walk (atari.cpp
#                  blkPolyLineCk: lineOverlap on every block of a chain, recursion into the overlapped
#                  nodes) in platform/lnw_sh4.S with lineOverlap's float operations on the same operands;
#                  the overlapped leaves then run blkPolyLineCkCore in the walk's order; hitCheck2 walks
#                  each piece first and ends a piece without an overlapped leaf there (no polyBit clear, no
#                  hit transform). =2 (check build): the recursive walk's leaves compared ("LNW" lines).
GAME_LINE_WALK ?= 0
ifneq ($(GAME_LINE_WALK),0)
PLATFORM_OBJS += $(OBJDIR)/platform/lnw_sh4.o
$(OBJDIR)/platform/lnw_sh4.o: platform/lnw_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_WALK=$(GAME_LINE_WALK)
endif
# GAME_LINE_PIECE=1 (G, collision traversal; exact; needs GAME_LINE_WALK=1 and GAME_FP_CONTRACT=off):
#                  hitCheck2's per-piece segment transform and walk setup in platform/lnw_sh4.S
#                  (re4dc_line_piece): the x and z rows of MTXMultVec's contract-off dataflow for both ends,
#                  mid / dir / |dir| as the C computes them, then the walk; only a piece with an overlapped
#                  leaf transforms both ends in full, as before. The piece loop steps a pointer. =2 (check
#                  build): the kernel's ends and leaves compared with PSMTXMultVec's and lineWalkPiece's
#                  ("LNP" lines).
GAME_LINE_PIECE ?= 0
ifneq ($(GAME_LINE_PIECE),0)
ifeq ($(GAME_LINE_WALK),0)
$(error GAME_LINE_PIECE=$(GAME_LINE_PIECE) needs GAME_LINE_WALK=1)
endif
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_LINE_PIECE mirrors the contract-off MTXMultVec dataflow: needs GAME_FP_CONTRACT=off)
endif
$(OBJDIR)/platform/lnw_sh4.o: KOS_CFLAGS += -DRE4DC_LINE_PIECE=1
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_PIECE=$(GAME_LINE_PIECE)
endif
# GAME_SPHERE_WALK=1 (G, collision traversal; exact; needs GAME_FP_CONTRACT=off): the swept-sphere queries'
#                   block walk (atari.cpp polySphereCk / blkPolySphereCk: hitCheckSphere on every block of a
#                   chain, recursion into the overlapped nodes) in platform/spw_sh4.S with hitCheckSphere's
#                   float operations on the same operands, resumable (a leaf's polygon test moves the sphere's
#                   end; the walk goes on against the moved end). Each piece is walked first with the x and z
#                   rows of both ends (MTXMultVec's contract-off dataflow); only a piece with an overlapped leaf
#                   clears polyBit and transforms both ends in full, as before. wallAdjust's two calls share
#                   one walk (the second replays the first's leaves when the first hit nothing). =2 (check
#                   build): the original loop on copies, a C walk per kernel step, the re-walks and
#                   PSMTXMultVec's x / z compared ("SPW" lines).
GAME_SPHERE_WALK ?= 0
ifneq ($(GAME_SPHERE_WALK),0)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_SPHERE_WALK mirrors the contract-off MTXMultVec dataflow: needs GAME_FP_CONTRACT=off)
endif
PLATFORM_OBJS += $(OBJDIR)/platform/spw_sh4.o
$(OBJDIR)/platform/spw_sh4.o: platform/spw_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_SPHERE_WALK=$(GAME_SPHERE_WALK)
endif
# GAME_CUBE_MEMO=1 (G, camera line vs box bodies; exact): ComnHitCheck's box test (emLineCubeCrossCk: corners,
#                 six face normals normalized, per call) keeps each box's face normals and plane offsets in a
#                 table indexed by the body, keyed on the matrix, sizes and offset bits; a call runs only the
#                 two plane tests per face, and the original test when a face passes both (at_mod.cpp).
#                 =2 (check build): every call compared with emLineCubeCrossCk, every hit rebuilt ("CBM").
GAME_CUBE_MEMO ?= 0
ifneq ($(GAME_CUBE_MEMO),0)
$(OBJDIR)/src/game/at_mod.o: GAME_CPPFLAGS += -DRE4DC_CUBE_MEMO=$(GAME_CUBE_MEMO)
endif
# GAME_EM10_IDFIRST=1 (G, Ganado AI scan; exact): em10SomebodyDamageNowCk tests each slot's id range before
#                    be_flag (two plain loads, either failing skips the slot): fewer cache lines touched.
#                    =2 (check build): both orders compared ("EID" lines).
GAME_EM10_IDFIRST ?= 0
ifneq ($(GAME_EM10_IDFIRST),0)
$(OBJDIR)/mod/%/em10.o: GAME_CPPFLAGS += -DRE4DC_EM10_IDFIRST=$(GAME_EM10_IDFIRST)
endif
# GAME_LINE_YROW=1 (G, line queries; exact; needs GAME_LINE_PIECE=1): hitCheck2 takes a walked piece's ends'
#                 x / z rows from re4dc_line_piece and computes only the y rows (MTXMultVec's expression); the
#                 current end's transform is lb's until a hit is taken, the hit test's re-transform the one
#                 taken before the leaf tests (atari.cpp). =2 (check build): each compared with PSMTXMultVec
#                 ("LYR" lines).
GAME_LINE_YROW ?= 0
ifneq ($(GAME_LINE_YROW),0)
ifeq ($(GAME_LINE_PIECE),0)
$(error GAME_LINE_YROW needs GAME_LINE_PIECE=1)
endif
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_YROW=$(GAME_LINE_YROW)
endif
# GAME_ATRECT_FAR=1 (G, em-em collision; decision-exact): At_em_sphere_rect_ck returns 0 before building the
#                  box frame (RotRad, MultVec, PSMTXInverse) when the sphere's old and new positions both lie
#                  beyond the box's reach (offset + 2 x (sizes + radius)) plus a rounding margin on one side in
#                  x or z (at_mod.cpp arfFar): the original returns 0 there with no write. =2 (check build):
#                  the original always runs; rejected calls that hit are counted ("ARF" lines).
GAME_ATRECT_FAR ?= 0
ifneq ($(GAME_ATRECT_FAR),0)
$(OBJDIR)/src/game/at_mod.o: GAME_CPPFLAGS += -DRE4DC_ATRECT_FAR=$(GAME_ATRECT_FAR)
endif
# GAME_OBJHIT_IDFIRST=1 (G, camera line vs objects; exact; needs GAME_OBJHIT_LIST=1): ObjHitCheck tests each
#                      object's id before be_flag (1045 of 1240 objects/tick have id 2) and prefetches only the
#                      id lines from the array: one line per object instead of two (at_mod.cpp objHitOne).
#                      =2 (check build): both orders compared ("OID" lines).
GAME_OBJHIT_IDFIRST ?= 0
ifneq ($(GAME_OBJHIT_IDFIRST),0)
ifeq ($(GAME_OBJHIT_LIST),0)
$(error GAME_OBJHIT_IDFIRST needs GAME_OBJHIT_LIST=1)
endif
$(OBJDIR)/src/game/at_mod.o: GAME_CPPFLAGS += -DRE4DC_OBJHIT_IDFIRST=$(GAME_OBJHIT_IDFIRST)
endif
# GAME_EMHIT_LIST=1 (G, camera line vs characters; exact; needs GAME_ATCHK_LIST=1): EmHitCheck walks the
#                  alive-list array with the bodies' collision lines prefetched, and skips ComnHitCheck for a
#                  body without a box when the caller's flag has no bit 1 (it returns 0 there) (at_mod.cpp).
#                  =2 (check build): array vs list compared, skipped calls made and checked ("EHL" lines).
GAME_EMHIT_LIST ?= 0
ifneq ($(GAME_EMHIT_LIST),0)
ifeq ($(GAME_ATCHK_LIST),0)
$(error GAME_EMHIT_LIST needs GAME_ATCHK_LIST=1)
endif
$(OBJDIR)/src/game/at_mod.o: GAME_CPPFLAGS += -DRE4DC_EMHIT_LIST=$(GAME_EMHIT_LIST)
endif
# GAME_LINE_LEAF2=1 (G, collision traversal; exact; needs GAME_LINE_LEAF=1): the leaf kernel as platform/
#                   lnk2_sh4.S's re4dc_line_leaf2: lnk_sh4.S's passes software-pipelined (the polygon two
#                   ahead's vertex / normal lines prefetched during a plane test, the next edge's lines during
#                   an edge test), every float operation and compare kept. =2 (check build): lnk_sh4.S runs
#                   first on each chunk (polyBit put back); survivors and polyBit compared ("LK2" lines).
GAME_LINE_LEAF2 ?= 0
ifneq ($(GAME_LINE_LEAF2),0)
ifeq ($(GAME_LINE_LEAF),0)
$(error GAME_LINE_LEAF2 needs GAME_LINE_LEAF=1)
endif
PLATFORM_OBJS += $(OBJDIR)/platform/lnk2_sh4.o
$(OBJDIR)/platform/lnk2_sh4.o: platform/lnk2_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_LEAF2=$(GAME_LINE_LEAF2)
endif
# GAME_LINE_WALK_PF=1 (G, collision traversal; exact; needs GAME_LINE_WALK=1): the line walk and piece entry
#                     from platform/lnw2_sh4.S: lnw_sh4.S's with three prefetches added (the next block's
#                     `next` line, an overlapped node's child's `next` line, the root's lines at a piece's
#                     start). =2 (check build): lnw_sh4.S also runs; leaves and ends compared ("LWP" lines).
GAME_LINE_WALK_PF ?= 0
ifneq ($(GAME_LINE_WALK_PF),0)
ifeq ($(GAME_LINE_WALK),0)
$(error GAME_LINE_WALK_PF needs GAME_LINE_WALK=1)
endif
PLATFORM_OBJS += $(OBJDIR)/platform/lnw2_sh4.o
$(OBJDIR)/platform/lnw2_sh4.o: platform/lnw2_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
ifneq ($(GAME_LINE_PIECE),0)
$(OBJDIR)/platform/lnw2_sh4.o: KOS_CFLAGS += -DRE4DC_LINE_PIECE=1
endif
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_WALK_PF=$(GAME_LINE_WALK_PF)
endif
# GAME_LINE_TAIL=1 (G, collision traversal; exact; needs GAME_LINE_LEAF=1): a leaf kernel survivor (it passed
#                  At_poly_line_ck's plane and edge tests with the same operations) runs At_poly_line_tail
#                  (at_sub.cpp): At_poly_line_ck from t on, dp0 and a recomputed as there, the same decision
#                  trace note. =2 (check build): At_poly_line_ck also runs and is compared ("LTL" lines).
GAME_LINE_TAIL ?= 0
ifneq ($(GAME_LINE_TAIL),0)
ifeq ($(GAME_LINE_LEAF),0)
$(error GAME_LINE_TAIL needs GAME_LINE_LEAF=1)
endif
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_LINE_TAIL=$(GAME_LINE_TAIL)
$(OBJDIR)/src/game/at_sub.o: GAME_CPPFLAGS += -DRE4DC_LINE_TAIL=$(GAME_LINE_TAIL)
endif
# GAME_SCEAT_LIST=1 (G, trigger areas; exact): the per-frame area walks (sceAtCheck_main per caller type,
#                   sceAtDataLoopInit, sceAtItemFindCheck, sceAtCamCtrlCheck, SceAtCheckFieldInfo,
#                   SceAtCheckMoveScrAt, sceAtLink_check) take a list of the ordering table's records passing
#                   their checkType / type filter (table order), rebuilt when the table changes (every AddPrim /
#                   DelPrim / ClearOTagR in sce_at.cpp bumps a generation); a body that changes the table sends
#                   its walk back to the table (sce_at.cpp). =2 (check build): every list step compared with
#                   the table walk ("SAL" lines).
GAME_SCEAT_LIST ?= 0
ifneq ($(GAME_SCEAT_LIST),0)
$(OBJDIR)/src/game/sce_at.o: GAME_CPPFLAGS += -DRE4DC_SCEAT_LIST=$(GAME_SCEAT_LIST)
endif
# GAME_WORKAT_INLINE=1 (the 30 fps rethink; port overhead, exact; needs OBJECT_DEMAND=1 ENEMY_DEMAND=1):
#                    the demand-backed cObj / cEm managers' workAt (parts_bridge.cpp: two out-of-line
#                    calls per lookup, ~3,700 lookups per square tick from EfmDelete, GetEmPtrFromList,
#                    em10SomebodyDamageNowCk and the manager scans) inline for the common case: no pool
#                    frozen for the sub screen, the room's own array, an index in range: the slot table.
#                    Every other case takes the bridge as before. A header knob (include/cManager.h).
GAME_WORKAT_INLINE ?= 0
ifneq ($(GAME_WORKAT_INLINE),0)
ifneq ($(OBJECT_DEMAND)$(ENEMY_DEMAND),11)
$(error GAME_WORKAT_INLINE needs OBJECT_DEMAND=1 ENEMY_DEMAND=1)
endif
GAME_CPPFLAGS += -DRE4DC_WORKAT_INLINE=$(GAME_WORKAT_INLINE)
PLATFORM_CPPFLAGS += -DRE4DC_WORKAT_INLINE=$(GAME_WORKAT_INLINE)
endif
# GAME_ESP_OWNER=1 (square plan: active effects): live esp slots counted per owner (info.Core_pEm)
#                    bucket, so EspDelete with an owner returns at once when that owner has no live
#                    slot (include/esp.h). A header knob (ESP_INFO_SET): every game object gets it.
#                    =2: every early return is checked by the slot loop ("ESPOWN" log line).
GAME_ESP_OWNER ?= 0
ifneq ($(GAME_ESP_OWNER),0)
GAME_CPPFLAGS += -DRE4DC_ESP_OWNER=$(GAME_ESP_OWNER)
endif
# GAME_FX_SCAN=1 (30 fps rethink, lane fx; exact; needs GAME_ESP_OWNER=1): slot maps so the per-tick
#                effect pool loops (the source loops) step over runs of slots their tests cannot pass,
#                re-reading the map at every step: EspMove (live esp slots), EspDelete with an owner (the
#                owner bucket's live slots), EspgenMove / EspgenTrans / EspgenDelete (occupied controllers),
#                EfmDelete (slots holding obj 4 / 5 / 9, listed once per ObjMgr alive-list generation;
#                with GAME_ATCHK_LIST=1 and GAME_WORKAT_INLINE=1, else the source loop). A header knob
#                (include/esp.h). =2: every skipped slot is tested as the source loop would test it and
#                counted, with the maps checked against the pools every tick ("FXS" lines).
GAME_FX_SCAN ?= 0
ifneq ($(GAME_FX_SCAN),0)
ifeq ($(GAME_ESP_OWNER),0)
$(error GAME_FX_SCAN needs GAME_ESP_OWNER=1)
endif
GAME_CPPFLAGS += -DRE4DC_FX_SCAN=$(GAME_FX_SCAN)
PLATFORM_CPPFLAGS += -DRE4DC_FX_SCAN=$(GAME_FX_SCAN)
endif
# GAME_FX_MOVE=1 (30 fps rethink, lane fx; exact): the effect base update (cEsp::CommonMove with its
#                ColorUpdate, cEsp::AnmMove) and cEsp48::move read and write their float fields through
#                walking pointers (fmov.s @Rm+ / @-Rn, include/esp.h FXL / FXS): the same operations on
#                the same operands in the same order, fewer address adds. A header knob (esp.h). =2: the
#                source runs live and the new code on a copy of the effect, compared field for field
#                ("FXM" / "FX48" lines; FX48 also counts sinf argument repeats).
GAME_FX_MOVE ?= 0
ifneq ($(GAME_FX_MOVE),0)
GAME_CPPFLAGS += -DRE4DC_FX_MOVE=$(GAME_FX_MOVE)
PLATFORM_CPPFLAGS += -DRE4DC_FX_MOVE=$(GAME_FX_MOVE)
endif
# GAME_OB_SCAN=1 (30 fps rethink, lane ob; exact): per-tick bookkeeping scans. cDmgMgr::hitCheck tests
#                the live damage volumes from the alive list in slot order instead of all 20 slots, and
#                cDmgMgr::move skips the dieCheck calls that can no longer change a work (dmg.cpp);
#                GetEmPtrFromList searches EmMgr's alive list (one match = the answer, else the source
#                loop; em_set.cpp); IDSystem::move runs level pass 0 as the source and lists the deeper
#                units it steps over, so passes 1..m_levelMax walk that list instead of every slot
#                (id_sys.cpp). No static data at =1 (the image's data layout does not move). =2: the
#                source runs live beside each fast answer and every difference is counted ("OBS" lines).
GAME_OB_SCAN ?= 0
ifneq ($(GAME_OB_SCAN),0)
$(OBJDIR)/src/game/dmg.o: GAME_CPPFLAGS += -DRE4DC_OB_SCAN=$(GAME_OB_SCAN)
$(OBJDIR)/src/game/em_set.o: GAME_CPPFLAGS += -DRE4DC_OB_SCAN=$(GAME_OB_SCAN)
$(OBJDIR)/src/game/id_sys.o: GAME_CPPFLAGS += -DRE4DC_OB_SCAN=$(GAME_OB_SCAN)
endif
# GAME_OB_MAT=1 (30 fps rethink, lane ob; exact): idSysMove03 keeps l_mat / mat when the unit's rotation,
#               position and group parent's matrix are unchanged (versions in IdUnit pad_D8; no static
#               data at =1). =2: the source matrices are built beside every call and compared ("OBM").
GAME_OB_MAT ?= 0
ifneq ($(GAME_OB_MAT),0)
$(OBJDIR)/src/game/id_sys.o: GAME_CPPFLAGS += -DRE4DC_OB_MAT=$(GAME_OB_MAT)
endif
# GAME_OB_PATH=1 (30 fps rethink, lane ob; exact): idSysMove00's path points (FuncPathCalc) computed with
#                the same de_Boor_Cox arithmetic in stack arrays instead of 3 + n + m heap blocks per call
#                (the heap lists end each call as they started; id_sys.cpp). =2: both run, compared ("OBP").
GAME_OB_PATH ?= 0
ifneq ($(GAME_OB_PATH),0)
$(OBJDIR)/src/game/id_sys.o: GAME_CPPFLAGS += -DRE4DC_OB_PATH=$(GAME_OB_PATH)
endif
# GAME_OB_NEAR=1 (30 fps rethink, lane ob; exact): getNearPoint's ten-nearest insertion as one test-and-shift
#                loop (the source's tests in the same order) instead of the two memmove calls GCC made of
#                the shift per inserted point (route_ck.cpp). =2: the source selection runs beside it and
#                its answer is used; differences counted ("OBN").
GAME_OB_NEAR ?= 0
ifneq ($(GAME_OB_NEAR),0)
$(OBJDIR)/src/game/route_ck.o: GAME_CPPFLAGS += -DRE4DC_OB_NEAR=$(GAME_OB_NEAR)
endif
# GAME_OB_DECODE=1 (30 fps rethink, lane ob; exact): the effect record reader (platform/native_effect.cpp,
#                  built at -O1) read every word through a 4-byte memcpy library call: an aligned word is
#                  read in place, and decode() expands an aligned record with the three mask words held
#                  in registers (the same 75 output words in the same order). =2: the source expansion
#                  runs beside it into a second buffer and its output is used; differences counted ("OBD").
GAME_OB_DECODE ?= 0
ifneq ($(GAME_OB_DECODE),0)
$(OBJDIR)/platform/native_effect.o: PLATFORM_CPPFLAGS += -DRE4DC_OB_DECODE=$(GAME_OB_DECODE)
endif
# GAME_ROTVEC_MEMO=1 (square plan: collision body positions; exact): RotVector (sub2.cpp) keeps yaw-only
#                    results in 256 one-line entries keyed by the input bits (RVM_BITS=n: 2^n entries);
#                    cAtariInfo::getPos repeats it for every candidate body on each EmAtCheck call.
#                    =2: every hit recomputed and compared ("RVM" log line).
GAME_ROTVEC_MEMO ?= 0
# GAME_ID_LISTS=1 (30 fps rethink, R headroom; exact): IDSystem::trans builds each unit's child lists once
#                 and unitTrans walks them instead of rescanning the pool per queued unit (0x80 units of
#                 0x138 bytes, ~38 queued per tick). =2: the lists run dry beside the live scans and every
#                 queued sequence is compared ("IDL" lines).
GAME_ID_LISTS ?= 0
ifneq ($(GAME_ID_LISTS),0)
$(OBJDIR)/src/game/id_sys.o: GAME_CPPFLAGS += -DRE4DC_ID_LISTS=$(GAME_ID_LISTS)
endif
# GAME_OT_MASK=1 (R headroom; exact): per-table bits "took an entry" / "took a model entry" since the
#                table's clear (trans_ot.cpp); ExecOt returns at once for an empty table and the model-asset
#                walk (model_asset_bridge.cpp) skips tables without models. =2: both ways, compared ("OTM").
GAME_OT_MASK ?= 0
ifneq ($(GAME_OT_MASK),0)
GAME_CPPFLAGS += -DRE4DC_OT_MASK=$(GAME_OT_MASK)
PLATFORM_CPPFLAGS += -DRE4DC_OT_MASK=$(GAME_OT_MASK)
endif
# UI_HEAP_LAZY=N (R headroom): the native frame stats' source_heap_free (OSCheckHeap, a whole-heap walk,
#                ~0.12 hw ms) refreshes every Nth frame; nothing in the image reads it.
UI_HEAP_LAZY ?= 0
ifneq ($(UI_HEAP_LAZY),0)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_UI_HEAP_LAZY=$(UI_HEAP_LAZY)
endif
# UI_PALETTE_SLOTS=N (R headroom; exact; with UI_HANDLES=1): the indexed-image handles' palette copies are
#                N slots given out on demand (LRU) instead of 16 fixed to handle index % 16 (the HUD's
#                indexed images evicted each other: 6 full resolves per tick in the r101 square).
UI_PALETTE_SLOTS ?= 0
ifneq ($(UI_PALETTE_SLOTS),0)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_UI_PALETTE_SLOTS=$(UI_PALETTE_SLOTS)
endif
# LINK_ORDER=<file> (G; exact, code placement only): an ld --section-ordering-file that puts the hot
#                    input sections first in .text (tools/d367/ordgen_c3.py from hwproject evidence: call
#                    chains clustered to the 8 KB direct-mapped I-cache, placed by density). The r101-square
#                    order is link-order/r101-square-c3-8k.ld: never-draw work -1.25 hw ms (I-miss 4.67 ->
#                    3.74), every tick drawn -0.94, logic trace STRICT. Regenerate it after code changes.
LINK_ORDER ?=
ifneq ($(LINK_ORDER),)
GAME_LDFLAGS += -Wl,--section-ordering-file,$(abspath $(LINK_ORDER))
endif
# PACE_TRANS_SKIP=mask (private test knob): presentation stages skipped for a dropped image
# (1 EspTrans 2 EspgenTrans 4 CtrlMgr.trans 8 ShadowTrans 16 ClothDraw 32 FilterTrans 64 TexRender
#  128 IdSys.trans 256 DrawOTag(MainOt[4]) 512 cMes.Trans 1024 Render() on a skipped iteration).
PACE_TRANS_SKIP ?= 0
ifneq ($(PACE_TRANS_SKIP),0)
$(OBJDIR)/src/game/trans.o $(OBJDIR)/src/game/main.o $(OBJDIR)/src/game/esp.o $(OBJDIR)/src/game/espgen.o: GAME_CPPFLAGS += -DRE4DC_PACE_TRANS_SKIP=$(PACE_TRANS_SKIP)
endif
# COARSE=1 (30 fps rethink step 2; needs PACE_CATCHUP=2 and the qualified PACE_TRANS_SKIP=4063): in-room
#          play images are drawn by coarse.cpp from gameplay records (camera-opaque collision pieces,
#          part skeletons, live effects). Trans() runs such a tick's presentation stages as for a
#          dropped image, but a drawn one keeps TexRender (the HUD's render textures); Render() runs
#          OTs 0 / TEX_RENDER1, then the coarse view in place of the world OTs ("COARSE" log line every
#          120 images). =2: + camera / stream state and a screen-point probe (what covers the view).
COARSE ?= 0
# ACTOR_SWAP=1 (benchmark, version A; needs COARSE=0 COARSE_LEON=1 COARSE_GANADO=1): the old renderer's
#              ModelRender draws Leon and the Ganados through the COARSE_LEON / COARSE_GANADO adapters (the
#              reduced meshes, native actor submission) instead of their source infos, so old and new
#              renderers are timed with the same character models (actor_swap.cpp). Presentation only.
ACTOR_SWAP ?= 0
ifneq ($(ACTOR_SWAP),0)
ifneq ($(COARSE),0)
$(error ACTOR_SWAP is the version A (COARSE=0) twin of the coarse actor adapters)
endif
ifneq ($(COARSE_LEON)$(COARSE_GANADO),11)
$(error ACTOR_SWAP needs COARSE_LEON=1 COARSE_GANADO=1)
endif
PLATFORM_OBJS += $(OBJDIR)/actor_swap.o
$(OBJDIR)/actor_swap.o: actor_swap.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -MMD -MP -c $< -o $@
$(OBJDIR)/src/game/trans.o: GAME_CPPFLAGS += -DRE4DC_ACTOR_SWAP=1
endif
# COARSE_GANADO_CAST=1 (needs COARSE_GANADO=1; render only): the Ganados draw the external cast's
#                      per-appearance meshes (coarse_ganado_cast.cpp replaces coarse_ganado.cpp in the link):
#                      COARSE_ACTOR_ASSET_DIR is then a private bundle with ganado_cast_runtime.h (four chunks
#                      per appearance in the source info order, the appearance's inverse bind, the source
#                      infos' signatures, the atlas key), made outside the repository from the cast packs.
#                      An actor draws the appearance its body and head signatures name; any cast hand pose
#                      draws that appearance's default hand. =2: check build, the 874 matcher runs beside
#                      each attempt ("GCAST" lines: both / cast only / 874 only / neither, role mismatches).
COARSE_GANADO_CAST ?= 0
COARSE_GANADO_SRC := coarse_ganado.cpp
ifneq ($(COARSE_GANADO_CAST),0)
ifneq ($(COARSE_GANADO),1)
$(error COARSE_GANADO_CAST needs COARSE_GANADO=1)
endif
COARSE_GANADO_SRC := coarse_ganado_cast.cpp $(COARSE_ACTOR_ASSET_DIR)/ganado_cast_runtime.h
$(OBJDIR)/coarse_ganado.o: GAME_CPPFLAGS += -DRE4DC_COARSE_GANADO_CAST=$(COARSE_GANADO_CAST)
endif
# Private live-Ganado experiment. Limit affects mesh presentation only; ACT_CAP remains 0.
COARSE_GANADO ?= 0
COARSE_GANADO_LIMIT ?= -1
ifneq ($(COARSE_GANADO),0)
ifeq ($(COARSE_LEON),0)
$(error COARSE_GANADO requires COARSE_LEON=1 for the shared hooks)
endif
PLATFORM_OBJS += $(OBJDIR)/coarse_ganado.o
$(OBJDIR)/coarse.o $(OBJDIR)/coarse_actor.o: GAME_CPPFLAGS += -DRE4DC_COARSE_GANADO=1
# COARSE_FREEZE_AT=N (diagnostic, captures only): the CPU stops in frame N's actor pass (frame N-1 stays on screen)
COARSE_FREEZE_AT ?= 0
ifneq ($(COARSE_FREEZE_AT),0)
$(OBJDIR)/coarse_ganado.o: GAME_CPPFLAGS += -DRE4DC_COARSE_FREEZE_AT=$(COARSE_FREEZE_AT)
endif
$(OBJDIR)/coarse_ganado.o: $(COARSE_GANADO_SRC) $(COARSE_ACTOR_ASSET_DIR)/ganado874_runtime.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -DRE4DC_COARSE_GANADO_LIMIT=$(COARSE_GANADO_LIMIT) -I$(COARSE_ACTOR_ASSET_DIR) -MMD -MP -c $< -o $@
endif
# Private 4K Leon proof through the existing actor path; generated assets stay outside Git.
COARSE_LEON ?= 0
ifneq ($(COARSE_LEON),0)
ifeq ($(COARSE)$(ACTOR_SWAP),00)
$(error COARSE_LEON requires COARSE (or ACTOR_SWAP=1, the version A benchmark))
endif
ifneq ($(NATIVE_ACTOR_FAST)$(NATIVE_ACTOR_SKIN_LAZY),11)
$(error COARSE_LEON requires NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN_LAZY=1)
endif
ifndef COARSE_ACTOR_ASSET_DIR
$(error COARSE_ACTOR_ASSET_DIR must point at the private qualified asset)
endif
PLATFORM_OBJS += $(OBJDIR)/coarse_actor.o
$(OBJDIR)/coarse.o $(OBJDIR)/model_bridge.o: GAME_CPPFLAGS += -DRE4DC_COARSE_LEON=1
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_COARSE_LEON=1
$(OBJDIR)/coarse_actor.o: coarse_actor.cpp $(COARSE_ACTOR_ASSET_DIR)/leon4k_runtime.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -I$(COARSE_ACTOR_ASSET_DIR) -MMD -MP -c $< -o $@
endif
# COARSE_SKIN_FTRV=1 (coarse actor adapters, render-only): palette matrices with FTRV (coarse_skin_sh4.S):
#                    T = root^-1 x part x bind^-1 for the bones the palettes use (two FTRV passes), each
#                    palette entry the weighted sum of its bones' T (three FTRVs; one-bone entries copied)
#                    instead of 2 PSMTXConcat per bone and the scalar weight loop. =2 check build: the C
#                    path runs too and COARSE_SKIN_CHK logs the largest difference.
COARSE_SKIN_FTRV ?= 0
ifneq ($(COARSE_SKIN_FTRV),0)
ifneq ($(COARSE_LEON),1)
$(error COARSE_SKIN_FTRV needs COARSE_LEON=1)
endif
PLATFORM_OBJS += $(OBJDIR)/coarse_skin_sh4.o
$(OBJDIR)/coarse_actor.o $(OBJDIR)/coarse_ganado.o: GAME_CPPFLAGS += -DRE4DC_COARSE_SKIN_FTRV=$(COARSE_SKIN_FTRV)
$(OBJDIR)/coarse_skin_sh4.o: coarse_skin_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
endif
ifneq ($(COARSE),0)
ifneq ($(PACE_CATCHUP),2)
$(error COARSE needs PACE_CATCHUP=2 and PACE_TRANS_SKIP (the qualified mask 4063))
endif
ifeq ($(PACE_TRANS_SKIP),0)
$(error COARSE needs PACE_CATCHUP=2 and PACE_TRANS_SKIP (the qualified mask 4063))
endif
PLATFORM_OBJS += $(OBJDIR)/coarse.o
$(OBJDIR)/src/game/trans.o: GAME_CPPFLAGS += -DRE4DC_COARSE=$(COARSE)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_COARSE=$(COARSE)
$(OBJDIR)/coarse.o: coarse.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -DRE4DC_COARSE=$(COARSE) -MMD -MP -c $< -o $@
endif
# COARSE_WORLD=bits (lane wd, test; needs COARSE=1): the coarse view's world beyond
#   the flat collision (coarse_world.cpp; data in the generated private coarse_world.h, textures staged with
#   EXTRA_TEXDIRS). 1: house shells (every house BIN of the room as its baked 128 VQ render shell, the
#   face light in the texture, in place of the collision polygons of its outer surfaces). 2: ground (the
#   floors under the source ground as 3.2 m cells coloured from it with a grey detail texture, in place of
#   those floors). 4: sky (the room's dome, unfogged, fading into the fog colour at the horizon; the PVR
#   background takes the fog colour, native_static FOG_BACKGROUND). 8: trees (the Standard impostor records
#   as their atlas quads in the punch-through list; needs TREE_IMPOSTOR=1).
COARSE_WORLD ?= 0
ifneq ($(COARSE_WORLD),0)
ifeq ($(COARSE),0)
$(error COARSE_WORLD needs COARSE=1)
endif
PLATFORM_OBJS += $(OBJDIR)/coarse_world.o
$(OBJDIR)/coarse.o: GAME_CPPFLAGS += -DRE4DC_COARSE_WORLD=$(COARSE_WORLD)
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_COARSE_WORLD=$(COARSE_WORLD)
$(OBJDIR)/coarse_world.o: coarse_world.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -DRE4DC_COARSE=$(COARSE) -DRE4DC_COARSE_WORLD=$(COARSE_WORLD) -MMD -MP -c $< -o $@
ifneq ($(shell echo $$(( $(COARSE_WORLD) & 4 ))),0)
$(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -DRE4DC_FOG_BACKGROUND=1
endif
ifneq ($(shell echo $$(( $(COARSE_WORLD) & 8 ))),0)
ifneq ($(TREE_IMPOSTOR),1)
$(error COARSE_WORLD bit 8 (trees) needs TREE_IMPOSTOR=1 (the punch-through list, re4dc_model_pt_begin))
endif
endif
endif
ifneq ($(GAME_ROTVEC_MEMO),0)
$(OBJDIR)/src/game/sub2.o: GAME_CPPFLAGS += -DRE4DC_ROTVEC_MEMO=$(GAME_ROTVEC_MEMO) $(if $(RVM_BITS),-DRE4DC_RVM_BITS=$(RVM_BITS))
endif
# GAME_DECISION_TRACE=1 (test builds, with LOGIC_TRACE=1): per sample, hashes of the em-em collision
#                    results (pair order included), the scenery line tests, the area checks and the damage hit
#                    tests, in call order ("LX"), plus every alive enemy's position bits every 4th sample
#                    ("LP"): the decision-level comparison for last-bit FP changes.
GAME_DECISION_TRACE ?= 0
ifneq ($(GAME_DECISION_TRACE),0)
GAME_CPPFLAGS += -DRE4DC_DECISION_TRACE=$(GAME_DECISION_TRACE)
PLATFORM_CPPFLAGS += -DRE4DC_DECISION_TRACE=$(GAME_DECISION_TRACE)
endif
# GAME_SKEL_FTRV=1 (square plan: one gameplay matrix chain; last-bit FP policy, NOT exact): inside
#                    cEm10::move (the Ganados' whole update) partsWorldCalc runs each part's concat
#                    through FTRV from a table of this call's parent matrices (model.cpp).
#                    =2: check build, the FTRV pass runs in shadow and is compared with the live
#                    original ("SKELFTRV" log line; logic trace STRICT).
GAME_SKEL_FTRV ?= 0
ifneq ($(GAME_SKEL_FTRV),0)
GAME_CPPFLAGS += -DRE4DC_SKEL_FTRV=$(GAME_SKEL_FTRV)
endif
# GAME_PWC_KERNEL=1 (the 30 fps rethink, step 2; exact twin of GAME_SKEL_FTRV=1's live loop): the
#                    Ganados' part-world pass as one streaming SH-4 loop (platform/pwc_sh4.S: @Rn+ /
#                    @-Rn addressing, inverse scales once per distinct parent scale; the same FP operations
#                    on the same operands). =2: check build, the kernel pass runs first, then skelPass
#                    recomputes live and every mat / world / r_scale word is compared ("PWCK" log line).
#                    =3: every model's part-world pass on the kernel (Leon and objects move from the library
#                    path to FTRV: last-bit FP policy, decisions compared with GAME_DECISION_TRACE).
GAME_PWC_KERNEL ?= 0
ifneq ($(GAME_PWC_KERNEL),0)
ifneq ($(GAME_SKEL_FTRV),1)
$(error GAME_PWC_KERNEL needs GAME_SKEL_FTRV=1)
endif
PLATFORM_OBJS += $(OBJDIR)/platform/pwc_sh4.o
$(OBJDIR)/platform/pwc_sh4.o: platform/pwc_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/src/game/model.o: GAME_CPPFLAGS += -DRE4DC_PWC_KERNEL=$(GAME_PWC_KERNEL)
endif
# GAME_PMC_KERNEL=1 (the 30 fps rethink, step 2; exact): cModel::partsMatCalc's parts whose rotation is in
#                    RotMatrix's memo (GAME_ROT_CACHE) as one streaming SH-4 loop (platform/pmc_sh4.S: the
#                    memo words, pos, the scale products and the copy to mat, stored with @-Rn); a memo miss
#                    takes the original four calls. Needs GAME_ROT_CACHE=1.
GAME_PMC_KERNEL ?= 0
ifneq ($(GAME_PMC_KERNEL),0)
ifneq ($(GAME_ROT_CACHE),1)
$(error GAME_PMC_KERNEL needs GAME_ROT_CACHE=1)
endif
PLATFORM_OBJS += $(OBJDIR)/platform/pmc_sh4.o
$(OBJDIR)/platform/pmc_sh4.o: platform/pmc_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/src/game/model.o $(OBJDIR)/src/game/math_sub.o: GAME_CPPFLAGS += -DRE4DC_PMC_KERNEL=$(GAME_PMC_KERNEL)
endif
# GAME_HERMITE_FAST=1 (the 30 fps rethink, step 2; exact): HermiteInterpolation (motion.cpp, every key
#                    stream evaluation) as a restructured twin: the common key layouts (5, 0, 6, 10) decoded
#                    inline with the same conversions, the hermite blend inline (same expression), the axis
#                    stride from a table; the search, history and persistence of f0 / f1 / val / tan across
#                    axes unchanged. =2: check build, the original runs first on a copy of the history and
#                    every output word, history slot and return value is compared ("HERMF" log line).
GAME_HERMITE_FAST ?= 0
ifneq ($(GAME_HERMITE_FAST),0)
$(OBJDIR)/src/game/motion.o: GAME_CPPFLAGS += -DRE4DC_HERMITE_FAST=$(GAME_HERMITE_FAST)
endif
# ---- lane gskel (skeleton / animation / cloth / math library; arm prefix sk) ----
# GAME_LIGHT_LAZY=1 (G -> drawn frames; exact): cLightInfo::updateMatrix keeps its inputs in imat and
#                   marks the info; imat's only reader (lightHitCheckBBox: light selection for drawing)
#                   materializes it with the original arithmetic (lightInfo.cpp, light.cpp).
#                   =2: check build, the original also runs into a side table at every call and every
#                   materialization is compared word for word ("LLZ" log line).
GAME_LIGHT_LAZY ?= 0
ifneq ($(GAME_LIGHT_LAZY),0)
$(OBJDIR)/src/game/lightInfo.o $(OBJDIR)/src/game/light.o: GAME_CPPFLAGS += -DRE4DC_LIGHT_LAZY=$(GAME_LIGHT_LAZY)
endif
# GAME_FP_SCHED=1 (exact): GCC's pre-register-allocation scheduler (sched1, register-pressure aware) on
#                 this lane's FP code (motion, math_sub, IK, cloth, RotVector, the SDK matrix / quaternion /
#                 vector units, the trig file and the fdlibm cores). sched1 runs after combine and only
#                 orders instructions (independent chains interleave, e.g. sinf's and cosf's Horner
#                 polynomials), so every FP operation is the reference build's.
GAME_FP_SCHED ?= 0
SK_SCHED_FLAGS = -fschedule-insns -fsched-pressure
ifneq ($(GAME_FP_SCHED),0)
$(OBJDIR)/src/game/motion.o $(OBJDIR)/src/game/math_sub.o $(OBJDIR)/src/game/ik.o $(OBJDIR)/src/game/pendulum.o \
	$(OBJDIR)/src/game/pl_cloth.o $(OBJDIR)/src/game/sub2.o: GAME_CPPFLAGS += $(SK_SCHED_FLAGS)
$(OBJDIR)/platform/mtx.o: PLATFORM_CPPFLAGS += $(SK_SCHED_FLAGS)
$(OBJDIR)/sdk/mtx.o $(OBJDIR)/sdk/quat.o $(OBJDIR)/sdk/vec.o: SDK_CFLAGS += $(SK_SCHED_FLAGS)
$(OBJDIR)/game30_trig.o: KOS_CFLAGS += $(SK_SCHED_FLAGS)
$(OBJDIR)/fdlibm/%.o: KOS_CFLAGS += $(SK_SCHED_FLAGS)
endif
# GAME_HF_INLINE=1 (exact; with GAME_HERMITE_FAST): hfGet inline at its three sites in hermiteFast.
GAME_HF_INLINE ?= 0
ifneq ($(GAME_HF_INLINE),0)
$(OBJDIR)/src/game/motion.o: GAME_CPPFLAGS += -DRE4DC_HF_INLINE=$(GAME_HF_INLINE)
endif
# GAME_HF_PF=1 (exact; with GAME_HERMITE_FAST): PREFs of the next axis' key header (hermiteFast) and of the next
#              joint's first key header (MotionMoveCore): those demand loads missed on nearly every axis.
GAME_HF_PF ?= 0
ifneq ($(GAME_HF_PF),0)
ifeq ($(GAME_HERMITE_FAST),0)
$(error GAME_HF_PF needs GAME_HERMITE_FAST)
endif
$(OBJDIR)/src/game/motion.o: GAME_CPPFLAGS += -DRE4DC_HF_PF=$(GAME_HF_PF)
endif
# GAME_PWC_SCHED=1 (exact; with GAME_PWC_KERNEL): pwc_sh4.S's part-world loop rescheduled for the SH-4
#                  pipeline (r_scale first in the back bank, loads ahead of their fmuls, FTRV rows stored as
#                  they arrive); every FP operation and operand role is the original's.
# GAME_PWC_PF=1 (exact; with GAME_PWC_SCHED): each part prefetches the next part's lines at exact field
#                  addresses (flags, pList, mat / l_mat / pParent / world, scale / r_scale).
GAME_PWC_SCHED ?= 0
GAME_PWC_PF ?= 0
ifneq ($(GAME_PWC_SCHED),0)
ifeq ($(GAME_PWC_KERNEL),0)
$(error GAME_PWC_SCHED needs GAME_PWC_KERNEL)
endif
$(OBJDIR)/platform/pwc_sh4.o: KOS_CFLAGS += -DRE4DC_PWC_SCHED=$(GAME_PWC_SCHED)
endif
ifneq ($(GAME_PWC_PF),0)
ifeq ($(GAME_PWC_SCHED),0)
$(error GAME_PWC_PF needs GAME_PWC_SCHED)
endif
$(OBJDIR)/platform/pwc_sh4.o: KOS_CFLAGS += -DRE4DC_PWC_PF=$(GAME_PWC_PF)
endif
# GAME_TRIG_LEAN=1 (exact; acts with GAME_TRIG=1): game30_trig.c's sinf / cosf / re4dc_sincosf as leaf
#                  functions of the same operations (word moves through FPUL, large / non-finite arguments
#                  in separate functions, one kernel pick per quadrant); all 2^32 inputs checked on the host
#                  (tools/game30/trig_lean_exhaustive.sh).
GAME_TRIG_LEAN ?= 0
ifneq ($(GAME_TRIG_LEAN),0)
$(OBJDIR)/game30_trig.o: KOS_CFLAGS += -DRE4DC_TRIG_LEAN=$(GAME_TRIG_LEAN)
endif
# GAME_ACOS_LEAN=1 (exact; acts with GAME_FDLIBM=1): acosf / asinf (ef_acos.c, ef_asin.c) built
#                  -fno-math-errno, so their sqrtf is the bare fsqrt without the errno guard (a libgcc
#                  __unordsf2 call per acosf, ~0.1 ms / tick, mostly I-cache misses). The guard's other
#                  path is unreachable there: both square roots take (1 -/+ x) * 0.5 with 0.5 <= |x| < 1,
#                  so the argument lies in (0, 0.25] and the result is fsqrt's either way.
GAME_ACOS_LEAN ?= 0
ifneq ($(GAME_ACOS_LEAN),0)
$(OBJDIR)/fdlibm/ef_acos.o $(OBJDIR)/fdlibm/ef_asin.o: KOS_CFLAGS += -fno-math-errno
endif
# GAME_VEC_NORM_INLINE=1 (exact): PSVECNormalize inline (C_VECNormalize's body) in the cloth unit, the
#                 orientation builders and C_MTXRotAxisRad (include/vec.h, sdk mtx.c). =2: each call
#                 compared with C_VECNormalize ("VNRM").
GAME_VEC_NORM_INLINE ?= 0
ifneq ($(GAME_VEC_NORM_INLINE),0)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_VEC_NORM_INLINE inlines the contract-off normalize body: needs GAME_FP_CONTRACT=off)
endif
$(OBJDIR)/src/game/pendulum.o $(OBJDIR)/src/game/math_sub.o: GAME_CPPFLAGS += -DRE4DC_VEC_NORM_INLINE=$(GAME_VEC_NORM_INLINE)
$(OBJDIR)/sdk/mtx.o: SDK_CFLAGS += -DRE4DC_VEC_NORM_INLINE=$(GAME_VEC_NORM_INLINE)
$(OBJDIR)/platform/mtx.o: PLATFORM_CPPFLAGS += -DRE4DC_VEC_NORM_INLINE=$(GAME_VEC_NORM_INLINE)
endif
# GAME_MTXINV_SCHED=1 (exact; with GAME_SH4_MATH=1 and GAME_FP_CONTRACT=off): PSMTXInverse's hand-written
#                 body (platform/mtx_sh4.S) list-scheduled: the same instructions on the same operands as
#                 the RE4DC_FP_CONTRACT_OFF body, in dual-issue order (tools/game30/mtx_inverse_sched.py;
#                 proof tools/game30/prove_mtxinv_sched.sh: fpsym2 --strict vs the old body).
GAME_MTXINV_SCHED ?= 0
ifneq ($(GAME_MTXINV_SCHED),0)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_MTXINV_SCHED schedules the contract-off PSMTXInverse body: needs GAME_FP_CONTRACT=off)
endif
ifneq ($(GAME_SH4_MATH),1)
$(error GAME_MTXINV_SCHED schedules platform/mtx_sh4.S's body: needs GAME_SH4_MATH=1)
endif
$(OBJDIR)/platform/mtx_sh4.o: KOS_CFLAGS += -DRE4DC_MTXINV_SCHED=1
endif
# ---- end lane gskel ----
# GAME_COL_PREFETCH=1: the scenery collision walks (block chains, block polygon lists) prefetch the next
#                    block and the next polygon's record, vertex and normal. Loads only: same answers.
GAME_COL_PREFETCH ?= 0
ifeq ($(GAME_COL_PREFETCH),1)
$(OBJDIR)/src/game/atari.o: GAME_CPPFLAGS += -DRE4DC_COL_PREFETCH=1
endif

ifeq ($(LOGIC_TRACE),1)
PLATFORM_OBJS += $(OBJDIR)/logic_trace.o
$(OBJDIR)/src/game/main.o $(OBJDIR)/src/game/rnd.o: GAME_CPPFLAGS += -DRE4DC_LOGIC_TRACE=1
$(OBJDIR)/logic_trace.o: logic_trace.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -DRE4DC_LOGIC_TRACE=1 -DRE4DC_LOGIC_TRACE_DELAY_US=$(LOGIC_TRACE_DELAY_US) -DRE4DC_LOGIC_TRACE_MASK_RENDER=$(LOGIC_TRACE_MASK_RENDER) -MMD -MP -c $< -o $@
endif

ifneq ($(GAME_TICK_LOG),0)
PLATFORM_OBJS += $(OBJDIR)/tick_log.o
$(OBJDIR)/src/game/main.o $(OBJDIR)/src/game/debug.o: GAME_CPPFLAGS += -DRE4DC_TICK_LOG=$(GAME_TICK_LOG)
$(OBJDIR)/tick_log.o: tick_log.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(PLATFORM_CPPFLAGS) -DRE4DC_TICK_LOG=$(GAME_TICK_LOG) -MMD -MP -c $< -o $@
endif

# GAME_SCHED=1: GCC's post-register-allocation list scheduler (sched2) and peephole2 on every
# object; GAME_SCHED=game limits it to the recovered game code and the SDK (not the platform layer /
# native renderer, which other streams own). sched2 orders each block for the SH-4 pipeline: dual
# issue of different groups, 2-cycle loads, 3-cycle FPU results, fdiv/fsqrt busy time. Flycast
# charges ~1 cycle per instruction and does not see any of that; real hardware does
# (tools/sh4_cycles.py estimates the gain). Nothing that runs before or in RTL combine (where -O1
# forms its fmac) changes, so the RTL leaving combine is identical to the reference build in every
# function (tools/rtl_norm_cmp.py over -fdump-rtl-combine of every translation unit ->
# proofs/sched-combine-identity.txt); later passes only allocate registers, order, and fill delay
# slots, so the FP operations each execution path performs are identical by construction.
# (-fcaller-saves: +11 KB text and no modelled gain; -fipa-ra/-flra-remat: no effect. Left out.)
GAME_SCHED ?= 0
GAME_SCHED_FLAGS = -fschedule-insns2 -fpeephole2
ifeq ($(GAME_SCHED),1)
GAME_CPPFLAGS += $(GAME_SCHED_FLAGS)
PLATFORM_CPPFLAGS += $(GAME_SCHED_FLAGS)
SDK_CFLAGS += $(GAME_SCHED_FLAGS)
else ifeq ($(GAME_SCHED),game)
GAME_CPPFLAGS += $(GAME_SCHED_FLAGS)
SDK_CFLAGS += $(GAME_SCHED_FLAGS)
endif

# ---------------------------------------------------------------------------------------------
# Fusing policy 6B (USER SIGN-OFF 2026-09-23), in two separately gated steps:
#   GAME_FP_CONTRACT=off  step 1 (with GAME_FDLIBM=1 by default and the render-only exemption
#                         GAME_FP_RENDER=fast, both below): -ffp-contract=off on every logic, game, SDK
#                         and platform object. GCC then
#                         forms no fmac anywhere (~1,360 sites become fmul + fadd/fsub): the ONE-TIME
#                         approved behaviour change. Recapture the determinism baseline on this build
#                         (LOGIC_TRACE=1 GAME_FP_CONTRACT=off) and gate everything after it against
#                         that baseline. Logic then uses only IEEE fadd/fsub/fmul/fdiv, so it no longer
#                         depends on how an emulator implements the SH-4 fmac. GAME_SH4_MATH switches to
#                         the unfused kernel bodies (RE4DC_FP_CONTRACT_OFF in platform/mtx_sh4.S).
#   GAME_O2=hot|game      step 2 (needs GAME_FP_CONTRACT=off): -O2 with the decomp-safety guards on the
#                         hot gameplay objects (list below, from the logic stream's profile) or on every
#                         game + SDK object. Without contraction no -O2 pass changes an FP result (no
#                         reassociation without -ffast-math), so the FP dataflow is identical by
#                         construction; the guards keep CodeWarrior-era integer/pointer semantics.
#                         Objects with their own -O3/-Os policy (native renderer) keep it: their
#                         target-specific flags come later on the command line.
# Never (logic): -ffast-math family, -fsingle-precision-constant, -mfsrra/-mfsca, ftrv/fipr kernels,
# O2/Os without GAME30_DECOMP_SAFE.
# Hot gameplay objects (logic stream, proto/Makefile.logic.mk LOGIC_HOT_OBJS: profiled logic and
# game render-side units; native renderer, libraries and generated stubs excluded). Defined
# before the rules below: make expands a rule's target list when it reads the rule.
GAME30_HOT_OBJS = \
	$(OBJDIR)/platform/mtx.o \
	$(OBJDIR)/sdk/mtx.o \
	$(OBJDIR)/sdk/mtx44.o \
	$(OBJDIR)/sdk/mtxvec.o \
	$(OBJDIR)/sdk/quat.o \
	$(OBJDIR)/sdk/vec.o \
	$(OBJDIR)/src/game/Espgen42.o \
	$(OBJDIR)/src/game/Espgen43.o \
	$(OBJDIR)/src/game/EtcModel.o \
	$(OBJDIR)/src/game/act_btn.o \
	$(OBJDIR)/src/game/area.o \
	$(OBJDIR)/src/game/at_mod.o \
	$(OBJDIR)/src/game/at_sub.o \
	$(OBJDIR)/src/game/at_sub2.o \
	$(OBJDIR)/src/game/atari.o \
	$(OBJDIR)/src/game/atariInfo.o \
	$(OBJDIR)/src/game/cMotBase.o \
	$(OBJDIR)/src/game/cam_ctrl.o \
	$(OBJDIR)/src/game/cam_extra.o \
	$(OBJDIR)/src/game/cam_motion.o \
	$(OBJDIR)/src/game/cam_qfps.o \
	$(OBJDIR)/src/game/cam_sys.o \
	$(OBJDIR)/src/game/camera.o \
	$(OBJDIR)/src/game/cinesco.o \
	$(OBJDIR)/src/game/cloth.o \
	$(OBJDIR)/src/game/ctrl.o \
	$(OBJDIR)/src/game/ctrl00.o \
	$(OBJDIR)/src/game/ctrl01.o \
	$(OBJDIR)/src/game/ctrl10.o \
	$(OBJDIR)/src/game/ctrl11.o \
	$(OBJDIR)/src/game/ctrl12.o \
	$(OBJDIR)/src/game/ctrl14.o \
	$(OBJDIR)/src/game/dmg.o \
	$(OBJDIR)/src/game/eff_sys.o \
	$(OBJDIR)/src/game/em.o \
	$(OBJDIR)/src/game/emBar.o \
	$(OBJDIR)/src/game/emBarred.o \
	$(OBJDIR)/src/game/em_cloth.o \
	$(OBJDIR)/src/game/em_dm_val.o \
	$(OBJDIR)/src/game/em_set.o \
	$(OBJDIR)/src/game/em_sub.o \
	$(OBJDIR)/src/game/embarrel.o \
	$(OBJDIR)/src/game/embox.o \
	$(OBJDIR)/src/game/emdata.o \
	$(OBJDIR)/src/game/emdoor.o \
	$(OBJDIR)/src/game/emhit.o \
	$(OBJDIR)/src/game/emitem.o \
	$(OBJDIR)/src/game/emmine.o \
	$(OBJDIR)/src/game/emobj.o \
	$(OBJDIR)/src/game/emrack.o \
	$(OBJDIR)/src/game/emrock.o \
	$(OBJDIR)/src/game/emshield.o \
	$(OBJDIR)/src/game/emswitch.o \
	$(OBJDIR)/src/game/emtorch.o \
	$(OBJDIR)/src/game/emtree.o \
	$(OBJDIR)/src/game/emwep.o \
	$(OBJDIR)/src/game/emwindow.o \
	$(OBJDIR)/src/game/esp.o \
	$(OBJDIR)/src/game/esp00.o \
	$(OBJDIR)/src/game/esp01.o \
	$(OBJDIR)/src/game/esp02.o \
	$(OBJDIR)/src/game/esp03.o \
	$(OBJDIR)/src/game/esp04.o \
	$(OBJDIR)/src/game/esp05.o \
	$(OBJDIR)/src/game/esp06.o \
	$(OBJDIR)/src/game/esp07.o \
	$(OBJDIR)/src/game/esp08.o \
	$(OBJDIR)/src/game/esp09.o \
	$(OBJDIR)/src/game/esp0a.o \
	$(OBJDIR)/src/game/esp0b.o \
	$(OBJDIR)/src/game/esp0c.o \
	$(OBJDIR)/src/game/esp0d.o \
	$(OBJDIR)/src/game/esp0e.o \
	$(OBJDIR)/src/game/esp0f.o \
	$(OBJDIR)/src/game/esp10.o \
	$(OBJDIR)/src/game/esp11.o \
	$(OBJDIR)/src/game/esp12.o \
	$(OBJDIR)/src/game/esp13.o \
	$(OBJDIR)/src/game/esp14.o \
	$(OBJDIR)/src/game/esp15.o \
	$(OBJDIR)/src/game/esp16.o \
	$(OBJDIR)/src/game/esp17.o \
	$(OBJDIR)/src/game/esp18.o \
	$(OBJDIR)/src/game/esp19.o \
	$(OBJDIR)/src/game/esp1a.o \
	$(OBJDIR)/src/game/esp1b.o \
	$(OBJDIR)/src/game/esp3f.o \
	$(OBJDIR)/src/game/esp40.o \
	$(OBJDIR)/src/game/esp41.o \
	$(OBJDIR)/src/game/esp42.o \
	$(OBJDIR)/src/game/esp43.o \
	$(OBJDIR)/src/game/esp44.o \
	$(OBJDIR)/src/game/esp45.o \
	$(OBJDIR)/src/game/esp46.o \
	$(OBJDIR)/src/game/esp47.o \
	$(OBJDIR)/src/game/esp48.o \
	$(OBJDIR)/src/game/esp49.o \
	$(OBJDIR)/src/game/esp4a.o \
	$(OBJDIR)/src/game/esp4b.o \
	$(OBJDIR)/src/game/esp4c.o \
	$(OBJDIR)/src/game/esp4d.o \
	$(OBJDIR)/src/game/esp4e.o \
	$(OBJDIR)/src/game/esp4f.o \
	$(OBJDIR)/src/game/esp_app.o \
	$(OBJDIR)/src/game/esp_efm.o \
	$(OBJDIR)/src/game/esp_sub.o \
	$(OBJDIR)/src/game/espgen.o \
	$(OBJDIR)/src/game/espgen00.o \
	$(OBJDIR)/src/game/espgen01.o \
	$(OBJDIR)/src/game/espgen02.o \
	$(OBJDIR)/src/game/espgen10.o \
	$(OBJDIR)/src/game/espgen40.o \
	$(OBJDIR)/src/game/espgen44.o \
	$(OBJDIR)/src/game/espgen45.o \
	$(OBJDIR)/src/game/est.o \
	$(OBJDIR)/src/game/event.o \
	$(OBJDIR)/src/game/fade.o \
	$(OBJDIR)/src/game/flr_at.o \
	$(OBJDIR)/src/game/foot_shadow.o \
	$(OBJDIR)/src/game/foot_shadow_tbl.o \
	$(OBJDIR)/src/game/game.o \
	$(OBJDIR)/src/game/geometry.o \
	$(OBJDIR)/src/game/hermite.o \
	$(OBJDIR)/src/game/id_sys.o \
	$(OBJDIR)/src/game/ik.o \
	$(OBJDIR)/src/game/item_model.o \
	$(OBJDIR)/src/game/light.o \
	$(OBJDIR)/src/game/light01.o \
	$(OBJDIR)/src/game/light02.o \
	$(OBJDIR)/src/game/light03.o \
	$(OBJDIR)/src/game/light04.o \
	$(OBJDIR)/src/game/light05.o \
	$(OBJDIR)/src/game/light06.o \
	$(OBJDIR)/src/game/light07.o \
	$(OBJDIR)/src/game/light08.o \
	$(OBJDIR)/src/game/light10.o \
	$(OBJDIR)/src/game/lightInfo.o \
	$(OBJDIR)/src/game/lightPath.o \
	$(OBJDIR)/src/game/light_area.o \
	$(OBJDIR)/src/game/main.o \
	$(OBJDIR)/src/game/map_obj.o \
	$(OBJDIR)/src/game/math_sub.o \
	$(OBJDIR)/src/game/mes.o \
	$(OBJDIR)/src/game/mirror.o \
	$(OBJDIR)/src/game/model.o \
	$(OBJDIR)/src/game/motion.o \
	$(OBJDIR)/src/game/obj.o \
	$(OBJDIR)/src/game/obj00.o \
	$(OBJDIR)/src/game/obj01.o \
	$(OBJDIR)/src/game/obj02.o \
	$(OBJDIR)/src/game/obj03.o \
	$(OBJDIR)/src/game/obj04.o \
	$(OBJDIR)/src/game/obj05.o \
	$(OBJDIR)/src/game/obj06.o \
	$(OBJDIR)/src/game/obj08.o \
	$(OBJDIR)/src/game/obj09.o \
	$(OBJDIR)/src/game/obj10.o \
	$(OBJDIR)/src/game/obj12.o \
	$(OBJDIR)/src/game/obj13.o \
	$(OBJDIR)/src/game/obj14.o \
	$(OBJDIR)/src/game/obj15.o \
	$(OBJDIR)/src/game/obj16.o \
	$(OBJDIR)/src/game/obj18.o \
	$(OBJDIR)/src/game/obj19.o \
	$(OBJDIR)/src/game/obj1b.o \
	$(OBJDIR)/src/game/obj1c.o \
	$(OBJDIR)/src/game/obj1d.o \
	$(OBJDIR)/src/game/obj20.o \
	$(OBJDIR)/src/game/obj26.o \
	$(OBJDIR)/src/game/objBull.o \
	$(OBJDIR)/src/game/objGondola.o \
	$(OBJDIR)/src/game/objMissile.o \
	$(OBJDIR)/src/game/objPillar.o \
	$(OBJDIR)/src/game/objRobo.o \
	$(OBJDIR)/src/game/objRocket.o \
	$(OBJDIR)/src/game/objSubWep.o \
	$(OBJDIR)/src/game/objTrolley.o \
	$(OBJDIR)/src/game/objWep.o \
	$(OBJDIR)/src/game/objYagura.o \
	$(OBJDIR)/src/game/path.o \
	$(OBJDIR)/src/game/pendulum.o \
	$(OBJDIR)/src/game/pl_ashley.o \
	$(OBJDIR)/src/game/pl_body.o \
	$(OBJDIR)/src/game/pl_class.o \
	$(OBJDIR)/src/game/pl_cloth.o \
	$(OBJDIR)/src/game/pl_debug.o \
	$(OBJDIR)/src/game/pl_dmg.o \
	$(OBJDIR)/src/game/pl_event.o \
	$(OBJDIR)/src/game/pl_knife.o \
	$(OBJDIR)/src/game/pl_leon.o \
	$(OBJDIR)/src/game/pl_npc.o \
	$(OBJDIR)/src/game/pl_push.o \
	$(OBJDIR)/src/game/pl_sub.o \
	$(OBJDIR)/src/game/pl_wep.o \
	$(OBJDIR)/src/game/player.o \
	$(OBJDIR)/src/game/quake.o \
	$(OBJDIR)/src/game/rnd.o \
	$(OBJDIR)/src/game/room_jmp.o \
	$(OBJDIR)/src/game/route_ck.o \
	$(OBJDIR)/src/game/sce_at.o \
	$(OBJDIR)/src/game/sce_com.o \
	$(OBJDIR)/src/game/sce_sys.o \
	$(OBJDIR)/src/game/scheduler.o \
	$(OBJDIR)/src/game/scroll.o \
	$(OBJDIR)/src/game/se_at.o \
	$(OBJDIR)/src/game/shadow.o \
	$(OBJDIR)/src/game/shape.o \
	$(OBJDIR)/src/game/snd.o \
	$(OBJDIR)/src/game/snd_efx.o \
	$(OBJDIR)/src/game/snd_iss0.o \
	$(OBJDIR)/src/game/snd_iss1.o \
	$(OBJDIR)/src/game/snd_iss2.o \
	$(OBJDIR)/src/game/snd_iss3.o \
	$(OBJDIR)/src/game/snd_iss4.o \
	$(OBJDIR)/src/game/snd_main.o \
	$(OBJDIR)/src/game/snd_ram.o \
	$(OBJDIR)/src/game/snd_seq0.o \
	$(OBJDIR)/src/game/snd_seq1.o \
	$(OBJDIR)/src/game/snd_seq2.o \
	$(OBJDIR)/src/game/snd_seq3.o \
	$(OBJDIR)/src/game/snd_str0.o \
	$(OBJDIR)/src/game/snd_str1.o \
	$(OBJDIR)/src/game/snd_str2.o \
	$(OBJDIR)/src/game/snd_str3.o \
	$(OBJDIR)/src/game/snd_str4.o \
	$(OBJDIR)/src/game/snd_sub0.o \
	$(OBJDIR)/src/game/snd_sub1.o \
	$(OBJDIR)/src/game/snd_sub2.o \
	$(OBJDIR)/src/game/snd_sub3.o \
	$(OBJDIR)/src/game/stage.o \
	$(OBJDIR)/src/game/sub2.o \
	$(OBJDIR)/src/game/trans.o \
	$(OBJDIR)/src/game/trans_lit.o \
	$(OBJDIR)/src/game/trans_ot.o \
	$(OBJDIR)/src/game/view.o
GAME30_HOT_MODULE_PATTERNS = \
	$(OBJDIR)/mod/em12/%.o \
	$(OBJDIR)/mod/em10g/%.o \
	$(OBJDIR)/mod/em23/%.o \
	$(OBJDIR)/mod/wep02/%.o

# ACTOR_VTX_KERNEL=1 (the 30 fps rethink, vertex-loop lane; render only): the actors30 meshlet vertex
#                    passes (native_actor_fast.cpp pass_positions / pass_lights: every character's
#                    transform, outcode and fast light) on software-pipelined SH-4 loops (platform/avk_sh4.S,
#                    generated by tools/game30/avk/mkavk.py): two vertices in flight, in-kernel skin palette
#                    switches, s16 and u16 UVs, s8 normals through a float table; the same float operations
#                    as ACTOR_POS_ASM / ACTOR_LIGHT_ASM (u16 UVs: fmul + fadd where positions_c may fuse).
#                    Outcode bits reordered (near first) for every producer. =2: check build, the previous
#                    path recomputes each kernel vertex and every word is compared ("VTXK" log lines).
ACTOR_VTX_KERNEL ?= 0
ifneq ($(ACTOR_VTX_KERNEL),0)
PLATFORM_OBJS += $(OBJDIR)/platform/avk_sh4.o
$(OBJDIR)/platform/avk_sh4.o: platform/avk_sh4.S
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -c $< -o $@
$(OBJDIR)/platform/native_actor_fast.o: PLATFORM_CPPFLAGS += -DRE4DC_ACTOR_VTX_KERNEL=$(ACTOR_VTX_KERNEL)
endif

GAME_FP_CONTRACT ?= fast
GAME_O2 ?= 0
# Render-only objects exempt from contract-off (see GAME_FP_RENDER below). Game code reaches them only
# through submit/bind/frame entry points that take const inputs; they reference no data symbol
# defined outside themselves and write only TA/PVR data, their own statics and the renderer's
# per-frame workspace. native_ui has no contracted FP (listed for completeness, compiles the same).
# NOT exempt although renderer-side: gx_stub (GXProject hands screen coordinates back to game code),
# native_model (two-way interface with trans.o: re4dc_model_skipped_writeback/source_span/stamp),
# the bridges and native_motion (joint matrices).
GAME30_RENDER_EXEMPT_OBJS = \
	$(OBJDIR)/platform/native_static.o \
	$(OBJDIR)/platform/native_actor.o \
	$(OBJDIR)/platform/native_actor_fast.o \
	$(OBJDIR)/platform/native_ui.o \
	$(OBJDIR)/native-reuse/pvr_geometry.o \
	$(OBJDIR)/native-reuse/room_package.o \
	$(OBJDIR)/native-reuse/native_draw_plan.o \
	$(OBJDIR)/native-reuse/source_lighting.o
# GAME_CONCAT_COL=1 (design-logic P3, needs GAME_FP_CONTRACT=off): the contract-off MTXConcat kernel
# computed column by column (b column loaded once, a_ik loaded straight into each product register)
# and list-scheduled for SH-4 dual issue: the same fmul/fadd on the same operands in the same roles
# (tools/game30/mtx_concat_col.py generates it; tools/game30/prove_concat_col.sh: fpsym2 --strict vs
# the build's own C_MTXConcat over every alias partition). hwsim: 206 -> 102 cycles per call.
GAME_CONCAT_COL ?= 0
ifeq ($(GAME_CONCAT_COL),1)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_CONCAT_COL=1 replaces the contract-off MTXConcat body: needs GAME_FP_CONTRACT=off)
endif
endif
# GAME_MULTVEC_SCHED=1 (design-logic P3b, needs GAME_FP_CONTRACT=off): the contract-off MTXMultVec body
# with its three rows interleaved for SH-4 dual issue: the same fmul/fadd on the same operands in the
# same roles, all loads before the stores (tools/game30/prove_multvec_sched.sh: fpsym2 --strict vs the
# build's own C_MTXMultVec). hwsim: 56 -> 34 cycles per call.
GAME_MULTVEC_SCHED ?= 0
ifeq ($(GAME_MULTVEC_SCHED),1)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_MULTVEC_SCHED=1 replaces the contract-off MTXMultVec body: needs GAME_FP_CONTRACT=off)
endif
endif
# GAME_VEC_INLINE=1 (needs GAME_FP_CONTRACT=off): the small PSVEC* routines (add, subtract, scale,
# square magnitude, dot, cross, square distance) inline in game units (include/vec.h): the SDK's own C_*
# bodies, same operations in the same order, instead of two calls each (PS* -> C_*). Bit-identical with
# contraction off; the platform/native renderer units keep the calls.
GAME_VEC_INLINE ?= 0
ifeq ($(GAME_VEC_INLINE),1)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_VEC_INLINE=1 inlines the contract-off SDK vector bodies: needs GAME_FP_CONTRACT=off)
endif
GAME_CPPFLAGS += -DRE4DC_VEC_INLINE=1
endif
GAME30_DECOMP_SAFE = -fwrapv -fno-strict-aliasing -fno-delete-null-pointer-checks \
	-fno-isolate-erroneous-paths-dereference
GAME30_O2_FLAGS = -O2 $(GAME30_DECOMP_SAFE)
GAME30_FP_FLAGS =
ifeq ($(GAME_FP_CONTRACT),off)
GAME30_FP_FLAGS = -ffp-contract=off
$(OBJDIR)/platform/mtx_sh4.o: KOS_CFLAGS += -DRE4DC_FP_CONTRACT_OFF=1
ifeq ($(GAME_CONCAT_COL),1)
$(OBJDIR)/platform/mtx_sh4.o: KOS_CFLAGS += -DRE4DC_CONCAT_COL=1
endif
ifeq ($(GAME_MULTVEC_SCHED),1)
$(OBJDIR)/platform/mtx_sh4.o: KOS_CFLAGS += -DRE4DC_MULTVEC_SCHED=1
endif
# Render-only exemption (coordinator decision 2): these native renderer objects keep the default
# contraction (fmac) because nothing they compute flows back into gameplay state: their FP results
# go only to TA/PVR vertex data, renderer-private caches and draw lists (evidence in the game30
# report: interface census + STRICT trace of the exempt vs non-exempt build). Logic, SDK, game,
# bridges, GX emulation and native_motion stay contract-off. GAME_FP_RENDER=off drops the exemption.
GAME_FP_RENDER ?= fast
ifeq ($(GAME_FP_RENDER),fast)
$(GAME30_RENDER_EXEMPT_OBJS): GAME30_FP_FLAGS =
else ifneq ($(GAME_FP_RENDER),off)
$(error GAME_FP_RENDER must be fast or off)
endif
else ifneq ($(GAME_FP_CONTRACT),fast)
$(error GAME_FP_CONTRACT must be fast or off)
endif
# ACTOR_VTX_KERNEL's asm repeats the contracted (fmac) render code of native_actor_fast.cpp: it needs that object
# built with contraction on (GAME_FP_CONTRACT=fast, or =off with the GAME_FP_RENDER=fast exemption).
ifneq ($(ACTOR_VTX_KERNEL),0)
ifeq ($(GAME_FP_CONTRACT),off)
ifneq ($(GAME_FP_RENDER),fast)
$(error ACTOR_VTX_KERNEL repeats native_actor_fast.o's contracted render code: needs GAME_FP_RENDER=fast with GAME_FP_CONTRACT=off)
endif
endif
endif
# Per-object flags: recursive, so target/pattern-specific values below reach each compile (and each
# member compile of a REL module) at recipe time. Placed after GAME_OPT, so -O2 wins over -O1.
GAME30_OBJ_FLAGS =
GAME_CPPFLAGS += $(GAME30_FP_FLAGS) $(GAME30_OBJ_FLAGS)
PLATFORM_CPPFLAGS += $(GAME30_FP_FLAGS) $(GAME30_OBJ_FLAGS)
SDK_CFLAGS += $(GAME30_FP_FLAGS) $(GAME30_OBJ_FLAGS)
ifneq ($(GAME_O2),0)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_O2 changes fmac formation unless GAME_FP_CONTRACT=off (6B step 1 first))
endif
ifeq ($(GAME_O2),hot)
$(GAME30_HOT_OBJS) $(GAME30_HOT_MODULE_PATTERNS): GAME30_OBJ_FLAGS = $(GAME30_O2_FLAGS)
else ifeq ($(GAME_O2),game)
GAME_CPPFLAGS += $(GAME30_O2_FLAGS)
SDK_CFLAGS += $(GAME30_O2_FLAGS)
$(OBJDIR)/platform/mtx.o: GAME30_OBJ_FLAGS = $(GAME30_O2_FLAGS)
else
$(error GAME_O2 must be 0, hot or game)
endif
endif
# GAME_COLD_OS=1 (needs GAME_FP_CONTRACT=off): -Os for code that never runs in the frame loop of
# the route's gameplay (title/save/options/merchant/puzzle/debug screens and the Sscrn sub-screen
# REL, SUBSCREEN=1). Image bytes are heap-4 bytes (ARENA_FIT=1); with contraction off the FP
# results are the same at any -O level, and the decomp guards are kept as for -O2.
GAME_COLD_OS ?= 0
GAME30_COLD_OBJS = \
	$(OBJDIR)/src/game/title.o \
	$(OBJDIR)/src/game/card.o \
	$(OBJDIR)/src/game/option.o \
	$(OBJDIR)/src/game/t_option.o \
	$(OBJDIR)/src/game/merchant.o \
	$(OBJDIR)/src/game/puzzle.o \
	$(OBJDIR)/src/game/db_cam.o \
	$(OBJDIR)/src/game/debug.o \
	$(OBJDIR)/src/game/dbmodule.o \
	$(OBJDIR)/src/game/t_bugcheck.o \
	$(OBJDIR)/src/game/mercenaries.o
GAME30_COLD_MODULE_PATTERNS = $(OBJDIR)/mod/Sscrn/%.o
ifeq ($(GAME_COLD_OS),1)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_COLD_OS changes fmac formation unless GAME_FP_CONTRACT=off)
endif
$(GAME30_COLD_OBJS) $(GAME30_COLD_MODULE_PATTERNS): GAME30_OBJ_FLAGS = -Os $(GAME30_DECOMP_SAFE)
else ifneq ($(GAME_COLD_OS),0)
$(error GAME_COLD_OS must be 0 or 1)
endif

# GAME_FDLIBM=1 (needs GAME_FP_CONTRACT=off; part of 6B step 1, before the baseline is recaptured):
# the single-precision libm the game calls (sinf/cosf/tanf/atanf and the acosf/asinf/atan2f cores,
# __kernel_*, the pi/2 reduction and the sqrtf errno-path core) compiled from the game's own recovered sources
# (src/lib/fdlibm, newlib 1.8.2 as shipped with the original) with -ffp-contract=off, in place of the
# toolchain's prebuilt newlib members, which were built with fmac (127 reachable fmac in 10 functions
# remain after GAME_FP_CONTRACT=off alone). With it no logic path executes fmac at all. Linked as
# ordinary objects ahead of libm, so the archive members defining these symbols are not pulled; the
# public wrappers that stay in libm (acosf, asinf, atan2f) call these cores.
# Coordinator decision 1: part of step 1, so GAME_FP_CONTRACT=off turns it on by default (one
# baseline recapture); GAME_FDLIBM=0 with contract-off only for the drift-attribution arm.
ifeq ($(GAME_FP_CONTRACT),off)
GAME_FDLIBM ?= 1
else
GAME_FDLIBM ?= 0
endif
GAME30_FDLIBM_UNITS = ef_acos ef_asin ef_atan2 ef_rem_pio2 ef_sqrt kf_cos kf_rem_pio2 kf_sin kf_tan sf_atan sf_cos \
	sf_sin sf_tan
# GAME_TRIG=1 (needs GAME_FDLIBM=1): sinf/cosf from game30_trig.c, the same fdlibm source with
# __kernel_sinf/__kernel_cosf and the |x| <= 2^7*pi/2 part of __ieee754_rem_pio2f inlined, -O2 with
# the decomp-safety guards and -ffp-contract=off: bit-identical by construction (same operations, same
# order) and checked for all 2^32 inputs on the host (tools/trig_exhaustive.sh, FTZ/DAZ).
GAME_TRIG ?= 0
ifeq ($(GAME_TRIG),1)
ifneq ($(GAME_FDLIBM),1)
$(error GAME_TRIG=1 replaces the GAME_FDLIBM sinf/cosf: needs GAME_FDLIBM=1)
endif
GAME30_FDLIBM_UNITS := $(filter-out sf_sin sf_cos,$(GAME30_FDLIBM_UNITS))
PLATFORM_OBJS += $(OBJDIR)/game30_trig.o
$(OBJDIR)/game30_trig.o: game30_trig.c
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -w $(GAME_OPT) -O2 -ffp-contract=off $(GAME30_DECOMP_SAFE) -I$(ROOT)/include -MMD -MP -c $< -o $@
else ifneq ($(GAME_TRIG),0)
$(error GAME_TRIG must be 0 or 1)
endif
ifeq ($(GAME_FDLIBM),1)
ifneq ($(GAME_FP_CONTRACT),off)
$(error GAME_FDLIBM=1 belongs to 6B step 1: needs GAME_FP_CONTRACT=off)
endif
PLATFORM_OBJS += $(patsubst %,$(OBJDIR)/fdlibm/%.o,$(GAME30_FDLIBM_UNITS))
$(OBJDIR)/fdlibm/%.o: $(ROOT)/src/lib/fdlibm/%.c
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) -w $(GAME_OPT) -ffp-contract=off $(GAME30_DECOMP_SAFE) -I$(ROOT)/include -MMD -MP -c $< -o $@
endif

# ---------------------------------------------------------------------------------------------
# D367 B1 (user-approved census item; CHANGES GAMEPLAY once it parks): ACT_CAP=N caps the Ganados
# (ids 0x10..0x20) that run their AI / motion tick at N per logic tick (act_cap.cpp). The others
# are parked: no emMove, plDist2 kept current, still alive in EmMgr for every counter (kill count,
# waves, bell, doors). Engaged, threatening, damaged, in-view or near Ganados are never parked.
# 0 (default) builds nothing. N at or above the live Ganado count parks nothing and the logic trace
# is STRICT against the reference.
#   ACT_CAP_ROOM=0xSSRR  room the cap works in (default 0x101 = r101; 0 = every room)
#   ACT_CAP_RANGE_M=M    engagement radius in metres, never parked inside it (default 12)
#   ACT_CAP_VIEW_M=M     view frustum inflation in metres (default 3)
#   ACT_CAP_CREEP=K      a parked Ganado still runs every K-th tick, staggered (default 4; 0 = frozen)
#   ACT_CAP_LOG=N        one "AC" stats line per N ticks through re4dc_log (measurement builds only)
# em.o depends on the generated header in every build, so switching N (or back to 0) in one OBJDIR
# recompiles it; the default build compiles em.cpp without it (RE4DC_ACT_CAP undefined = off).
ACT_CAP ?= 0
ACT_CAP_ROOM ?= 0x101
ACT_CAP_RANGE_M ?= 12
ACT_CAP_VIEW_M ?= 3
ACT_CAP_CREEP ?= 4
ACT_CAP_LOG ?= 0
.PHONY: act-cap-force
$(OBJDIR)/act-cap.h: act-cap-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_ACT_CAP %s\n#define RE4DC_ACT_CAP_ROOM %s\n#define RE4DC_ACT_CAP_RANGE_M %s\n#define RE4DC_ACT_CAP_VIEW_M %s\n#define RE4DC_ACT_CAP_CREEP %s\n#define RE4DC_ACT_CAP_LOG %s\n' '$(ACT_CAP)' '$(ACT_CAP_ROOM)' '$(ACT_CAP_RANGE_M)' '$(ACT_CAP_VIEW_M)' '$(ACT_CAP_CREEP)' '$(ACT_CAP_LOG)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/src/game/em.o: $(OBJDIR)/act-cap.h
ifneq ($(ACT_CAP),0)
PLATFORM_OBJS += $(OBJDIR)/act_cap.o
$(OBJDIR)/src/game/em.o: GAME_CPPFLAGS += -include $(OBJDIR)/act-cap.h
$(OBJDIR)/act_cap.o: act_cap.cpp $(OBJDIR)/act-cap.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -include $(OBJDIR)/act-cap.h -MMD -MP -c $< -o $@
endif
