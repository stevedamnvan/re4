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
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -DRE4DC_LOGIC_TRACE=1 -DRE4DC_LOGIC_TRACE_DELAY_US=$(LOGIC_TRACE_DELAY_US) -MMD -MP -c $< -o $@
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
