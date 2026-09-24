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
#   SUBSCREEN_OVL=1 (needs SUBSCREEN=1) takes the Sscrn module (~122 KB) out of the resident
#                  image: it is linked as one section outside RAM (gen_modules.py <mod>:ovl),
#                  tools/link.sh links the image twice at two overlay addresses, proves that only
#                  the overlay's own absolute words differ (the image holds no pointer into it),
#                  writes sscrn.ovl (bytes + relocation list) next to the ELF and strips the
#                  section. Each open reads it into offset 0 of the sub screen area, where the
#                  GameCube's Sscrn.rel sat, and relocates it (sscrn_bridge.cpp). Heap 4 gains the
#                  module's size; stage.sh puts sscrn.ovl on the disc as /cd/dc/sscrn.ovl.
#   SS_POOL_HIGH=1 (needs SUBSCREEN=1) allocates the room's effect pools (cEspSystem, the esp pool,
#                  the Espgen controller pool) above the 3 MiB sub screen window at pG->pStFnt.
#                  On the GameCube the stage font and the room archive fill that window, so those
#                  pools always sit above it; the port's arena fit frees the archive's unused tail
#                  and they could land inside, where the sub screen's own files overwrite them
#                  while its main loop keeps running EspgenMove / EspMove (the r101 first-visit
#                  call reset). The room's light works (LightMgr, moved by the sub screen loop too)
#                  are moved above it right after their allocation. Same pools, same sizes, only
#                  the address differs.
SUBSCREEN ?= 0
W11_FIXTURE ?= 0
SUBSCREEN_OVL ?= 0
SS_POOL_HIGH ?= 0
ifeq ($(SUBSCREEN),1)
ifneq ($(TA_DOUBLEBUF),0)
# The backing borrows bank 1 while a sub screen is open: TA_DOUBLEBUF=1 switches the TA to one bank
# for that time (design-doublebuf), through the KOS vbuf-switch patch (patches/README.md).
SUBSCREEN_TA_SWITCH = 1
endif
ifeq ($(SUBSCREEN_OVL),1)
MODULES += Sscrn:ovl
export RE4DC_LINK_OVERLAY = .ovl_Sscrn
else
MODULES += Sscrn
endif
else ifeq ($(SUBSCREEN_OVL),1)
$(error SUBSCREEN_OVL=1 needs SUBSCREEN=1)
else ifeq ($(SS_POOL_HIGH),1)
$(error SS_POOL_HIGH=1 needs SUBSCREEN=1)
endif
.PHONY: subscreen-force
$(OBJDIR)/subscreen.h: subscreen-force
	@mkdir -p $(dir $@)
	@if [ "$(SUBSCREEN_TA_SWITCH)" = 1 ]; then test "$$($(KOS_CC_BASE)/bin/$(KOS_CC_PREFIX)-nm -g --defined-only $(KOS_BASE)/lib/$(KOS_ARCH)/libkallisti.a | grep -c ' T _pvr_set_vbuf_doublebuf$$')" -eq 1 || { echo 'SUBSCREEN=1 with TA_DOUBLEBUF=1 requires the KOS vbuf-switch patch (patches/kos-804b319-vbuf-switch.patch)' >&2; exit 1; }; fi
	@printf '#define RE4DC_SUBSCREEN %s\n#define RE4DC_W11_FIXTURE %s\n#define RE4DC_SUBSCREEN_OVL %s\n#define RE4DC_SS_POOL_HIGH %s\n' '$(SUBSCREEN)' '$(W11_FIXTURE)' '$(SUBSCREEN_OVL)' '$(SS_POOL_HIGH)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
# A knob change regenerates the module list.
$(MODULES_MK): $(OBJDIR)/subscreen.h
SUBSCREEN_GAME = $(OBJDIR)/src/game/sscrn.o $(OBJDIR)/ui_bridge.o $(OBJDIR)/src/game/cDataSwap.o \
                 $(OBJDIR)/src/game/espgen.o $(OBJDIR)/src/game/esp.o $(OBJDIR)/src/game/eff_sys.o \
                 $(OBJDIR)/src/game/game.o
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
