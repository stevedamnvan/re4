# D367 W11: the sub screen (inventory, map, examine, files) and its memory backing, plus
# the W11 test instrumentation. Included at the end of the Makefile. Every knob defaults to
# 0 and then contributes nothing: the default image is byte-identical.
#   SUBSCREEN=1    link the Sscrn REL into the image (static module id 71; its constructors
#                  run per link from its own _prolog, tools/gen_modules.py PER_LINK_CTORS) and
#                  replace the GameCube ARAM swap of the sub screen area (SubScreenExec /
#                  SubScreenExitCore: 3 MiB at pG->pStFnt <-> ARAM 0xD00000) with a Dreamcast
#                  backing (sscrn_bridge.cpp, platform/subscreen_backing.cpp): while the screen
#                  is open the live game bytes of that area (heaps 2/3/4, free cells skipped)
#                  are held in VRAM - the second TA vertex bank, idle with TA_DOUBLEBUF=0, then
#                  a texture-pool block - and checked on the way back; the screen's own files
#                  (ss_cmmn, ss_pzzl) are read from disc at open instead of being kept in ARAM.
#                  The ARAM preload at game start (1.75 MB of reads with nowhere to go) is
#                  skipped. Needs the sub screen data converted (le_mirror ss/ handlers) and
#                  its texture packages on the disc.
#                  The card screen's cDataSwap (a typewriter save swaps ~250 KB of the room heap
#                  out) uses the same backing when its heap copy does not fit (VMU design S0).
#   W11_FIXTURE=1  test instrumentation, never in a product image: /cd/dc/w11.txt (death /
#                  life fixture through the source damage entry), heap/VRAM/KOS census around
#                  every sub screen open and close and every death, frame-time windows per
#                  phase, and "w11 shot:" markers for framebuffer captures.
SUBSCREEN ?= 0
W11_FIXTURE ?= 0
ifeq ($(SUBSCREEN),1)
ifneq ($(TA_DOUBLEBUF),0)
$(error SUBSCREEN=1 keeps the sub screen backing in the idle second TA vertex bank: needs TA_DOUBLEBUF=0)
endif
MODULES += Sscrn
endif
.PHONY: subscreen-force
$(OBJDIR)/subscreen.h: subscreen-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_SUBSCREEN %s\n#define RE4DC_W11_FIXTURE %s\n' '$(SUBSCREEN)' '$(W11_FIXTURE)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
# A knob change regenerates the module list.
$(MODULES_MK): $(OBJDIR)/subscreen.h
SUBSCREEN_GAME = $(OBJDIR)/src/game/sscrn.o $(OBJDIR)/ui_bridge.o $(OBJDIR)/src/game/cDataSwap.o
$(SUBSCREEN_GAME) $(OBJDIR)/platform/modules.o: $(OBJDIR)/subscreen.h
$(SUBSCREEN_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/subscreen.h
$(OBJDIR)/platform/modules.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/subscreen.h
# native_ui.cpp: re4dc_ui_reclaim_one() for the backing (compiled only with SUBSCREEN=1).
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_motion.o: $(OBJDIR)/subscreen.h
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_motion.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/subscreen.h
# motion_bridge.cpp / native_motion.cpp: residency held while open, heap-12 clips dropped at close.
$(OBJDIR)/motion_bridge.o $(OBJDIR)/parts_bridge.o: $(OBJDIR)/subscreen.h
$(OBJDIR)/motion_bridge.o $(OBJDIR)/parts_bridge.o: GAME_CPPFLAGS += -include $(OBJDIR)/subscreen.h
# platform/subscreen_backing.cpp is in the platform wildcard: with both knobs 0 it compiles empty.
$(OBJDIR)/platform/subscreen_backing.o: $(OBJDIR)/subscreen.h $(OBJDIR)/pipeline30.h
$(OBJDIR)/platform/subscreen_backing.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/subscreen.h -include $(OBJDIR)/pipeline30.h
ifneq ($(SUBSCREEN)$(W11_FIXTURE),00)
PLATFORM_OBJS += $(OBJDIR)/sscrn_bridge.o
# Included after the link rule: name the object as its prerequisite here.
$(TARGET): $(OBJDIR)/sscrn_bridge.o
$(OBJDIR)/sscrn_bridge.o: sscrn_bridge.cpp $(OBJDIR)/subscreen.h $(OBJDIR)/pipeline30.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -include $(OBJDIR)/subscreen.h -include $(OBJDIR)/pipeline30.h -MMD -MP -c $< -o $@
-include $(OBJDIR)/sscrn_bridge.d
endif
