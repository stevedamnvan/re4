# D367 frame pacing (design-pacing DESIGN.md: option B, render skip with catch-up). Included at
# the end of the Makefile. Every knob defaults to 0 / off and then contributes nothing: the
# default image is byte-identical with or without this file.
#   PACE_CATCHUP=1   logic ticks at 29.97 Hz on the vblank clock (anchor + 2 vblanks per tick,
#                    so a slow frame is repaid by shorter waits). When the game is at least one
#                    tick behind, the next iteration runs its whole logic tick (TaskScheduler,
#                    Trans(), every OT callback, pad, sound, fades, messages) with the draw
#                    skipped: ModelRender returns at entry, the native frame is not begun (no UI
#                    quads, effect sprites or ID quads), nothing is presented (the previous
#                    picture stays). Never while a movie, the sub screen (inventory/map/radio/
#                    typewriter card) or a held picture (System_flg 0x400) owns the frame, nor
#                    outside in-room play (Rno0 3: title, picker, card, loads and doors run as
#                    today), nor when GetSystemVcnt() != 2.
#   PACE_CATCHUP=2   v2: also no ModelTrans (emTrans/objTrans) for a dropped image: the drop is
#                    decided before Trans() of tick k and iteration k+1 then skips as above.
#   PACE_CAP=N       consecutive skipped iterations at most (default 1 = 2 ticks per drawn
#                    frame). PACE_CAP=0 keeps the anchor clock without any skip (reference arm).
#   Runtime mode (pace.cpp re4dc_pace_mode, read every iteration, safe to change at any moment;
#                    it only changes which ticks draw): Smooth (the floor below; the default) /
#                    Fast (no floor, catch-up up to the cap) / Off (no pacing: today's loop).
#                    QUALITY=1 builds keep it in RE4DCCFG features bits 16-17 (mode + 1,
#                    re4dc_quality_pace / re4dc_quality_set_pace); quality.txt pace=1|2|3 sets it.
#                    (The in-game Options row that changes it is a later item.)
#   PACE_FLOOR_FPS=N Smooth's floor: a skip is taken only while the gap between two presents
#                    stays at or under 1/N s (default 15). Load beyond it degrades to slow motion
#                    instead of dropping more frames. 0 makes Fast the default (Smooth: 15).
#   PACE_MODE=smooth|fast|off  the build's default mode (before RE4DCCFG / quality.txt / menu).
#   PACE_DEBUG=1     (default: QUALITY_DEBUG) in game, a START press that begins with R held (L not held)
#                    cycles Smooth -> Fast -> Off with a 2 s on-screen note; the game never sees
#                    that START (pad.cpp, like the L+START debug chord).
#   PACE_LOG=N      one "PACE" telemetry line every N ticks (default 300 = 10 s).
# Test instrumentation (never in a product image):
#   PACE_FORCE=3|N|R|A  forced skip pattern, a pure function of the eligible-tick index (timing,
#                    cap and floor ignored): every Nth image (3 = every 3rd), R = p 0.5 from a
#                    platform xorshift seeded by PACE_SEED (never the game RNG), A = every image.
#                    iTaskScheduler runs on every iteration. For the forced-skip STRICT gate.
#   PACE_SEED=N      xorshift seed for PACE_FORCE=R (default 1).
#   PACE_TEST_DRAW_US=N  busy-wait N us on drawn iterations only (the skippable half).
#   PACE_TEST_TICK_US=N  busy-wait N us on every iteration (the per-tick half).
#   PACE_TEST_TOGGLE_S=N  cycle the mode every N s (the STRICT mode-toggle gate).
#   PACE_CHECK=2     (PACE_CATCHUP=2 + LOGIC_TRACE=1) a dropped image still runs ModelTrans,
#                    between two hashes of every logic-trace field; "pacechk=<n>/<fail>".
# Build every arm in its own OBJDIR; pace.h is regenerated when a value changes.
PACE_CATCHUP ?= 0
PACE_CAP ?= 1
PACE_FLOOR_FPS ?= 15
PACE_LOG ?= 300
PACE_FORCE ?= 0
PACE_SEED ?= 1
PACE_TEST_DRAW_US ?= 0
PACE_TEST_TICK_US ?= 0
PACE_CHECK ?= 0
PACE_TEST_TOGGLE_S ?= 0
PACE_DEBUG ?= $(or $(QUALITY_DEBUG),0)
PACE_MODE ?= $(if $(filter 0,$(PACE_FLOOR_FPS)),fast,smooth)
ifneq ($(PACE_CATCHUP),0)
PACE_MODE_NUM = $(if $(filter off,$(PACE_MODE)),2,$(if $(filter fast,$(PACE_MODE)),1,$(if $(filter smooth,$(PACE_MODE)),0,$(error PACE_MODE=smooth|fast|off))))
PACE_FORCE_NUM = $(if $(filter R,$(PACE_FORCE)),-1,$(if $(filter A,$(PACE_FORCE)),1,$(PACE_FORCE)))
ifneq ($(PACE_CHECK),0)
ifneq ($(LOGIC_TRACE),1)
$(error PACE_CHECK=2 hashes the logic-trace fields and needs LOGIC_TRACE=1)
endif
ifneq ($(LOGIC_TRACE_MASK_RENDER),1)
$(error PACE_CHECK=2 needs LOGIC_TRACE_MASK_RENDER=1 (be_flag 0x08000000 is the draw marker))
endif
endif
.PHONY: pace-force
$(OBJDIR)/pace.h: pace-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_PACE_CATCHUP %s\n#define RE4DC_PACE_CAP %s\n#define RE4DC_PACE_FLOOR_FPS %s\n#define RE4DC_PACE_LOG %s\n#define RE4DC_PACE_FORCE %s\n#define RE4DC_PACE_SEED %s\n#define RE4DC_PACE_TEST_DRAW_US %s\n#define RE4DC_PACE_TEST_TICK_US %s\n#define RE4DC_PACE_CHECK %s\n#define RE4DC_PACE_TEST_TOGGLE_S %s\n#define RE4DC_PACE_DEBUG %s\n#define RE4DC_PACE_MODE %s\n' '$(PACE_CATCHUP)' '$(PACE_CAP)' '$(PACE_FLOOR_FPS)' '$(PACE_LOG)' '$(PACE_FORCE_NUM)' '$(PACE_SEED)' '$(PACE_TEST_DRAW_US)' '$(PACE_TEST_TICK_US)' '$(PACE_CHECK)' '$(PACE_TEST_TOGGLE_S)' '$(PACE_DEBUG)' '$(PACE_MODE_NUM)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
PLATFORM_OBJS += $(OBJDIR)/pace.o
$(TARGET): $(OBJDIR)/pace.o
PACE_GAME = $(OBJDIR)/src/game/main.o $(OBJDIR)/src/game/main_sub.o $(OBJDIR)/src/game/trans.o
# RE4DCCFG bits, quality.txt pace= (QUALITY=1) and the test-build chord.
PACE_GAME += $(OBJDIR)/quality_picker.o
PACE_PLATFORM = $(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/pad.o $(OBJDIR)/platform/quality.o
$(PACE_GAME) $(PACE_PLATFORM) $(OBJDIR)/pace.o: $(OBJDIR)/pace.h
$(PACE_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/pace.h
$(PACE_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/pace.h
ifneq ($(PACE_CHECK),0)
$(OBJDIR)/logic_trace.o: $(OBJDIR)/pace.h
$(OBJDIR)/logic_trace.o: GAME_CPPFLAGS += -include $(OBJDIR)/pace.h
endif
$(OBJDIR)/pace.o: pace.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -include $(OBJDIR)/pace.h -MMD -MP -c $< -o $@
-include $(OBJDIR)/pace.d
endif
