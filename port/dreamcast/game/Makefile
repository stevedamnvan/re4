# The boot-forward RE4 executable: the recovered game sources compiled for
# SH-4 over a Dreamcast implementation of the platform interfaces they call
# (platform/). This is the game's own main(), scheduler, title, game state
# machine, scenario system, rooms, player, enemies and tools, not the room
# viewer in ../room.
#
#   make            build re4dc-game.elf (tools/link.sh: link-name aliases,
#                   then loud stubs for whatever is still unresolved)
#   make census     compile everything and list the symbols the platform
#                   layer still has to provide (no ELF is produced)
#
# Sources outside this directory are never written to: objects go under obj/.

TARGET = re4dc-game.elf
.DEFAULT_GOAL := all
ROOT = ../../..

# The executable is the DOL's own code (src/game). The REL modules (stage
# rooms, sub-screens, tools, enemies) each define their own _prolog/_epilog
# and re-compile shared sources per module, so they join through the module
# table with per-module symbol prefixes; the census still
# compiles them all to keep the platform inventory complete.
GAME_DIRS = src/game
CENSUS_DIRS = src/game src/st src/st1 src/Sscrn \
	src/tools src/Tools src/t_camera src/t_emlist src/t_esp src/t_event \
	src/t_id src/t_light src/t_movie src/t_sce
# yz2asm.cpp / memset_2.cpp are whole-function PowerPC asm with C replacements
# in platform/; t_util_{menu,nomenu,id}.cpp are the REL-specific re-includes of
# t_util.cpp (one object per REL on the GameCube).
GAME_EXCLUDE = src/game/yz2asm.cpp src/game/memset_2.cpp \
	src/tools/t_util_menu.cpp src/tools/t_util_nomenu.cpp src/tools/t_util_id.cpp
GAME_SRCS = $(filter-out $(addprefix $(ROOT)/,$(GAME_EXCLUDE)), \
	$(foreach d,$(GAME_DIRS),$(wildcard $(ROOT)/$(d)/*.cpp)))

CENSUS_SRCS = $(filter-out $(addprefix $(ROOT)/,$(GAME_EXCLUDE)), \
	$(foreach d,$(CENSUS_DIRS),$(wildcard $(ROOT)/$(d)/*.cpp)))
PLATFORM_SRCS = $(wildcard platform/*.cpp)
# SDK units compiled from the game's src/lib with the CodeWarrior asm bodies
# stripped (platform/sdk/strip_cw_asm.py) over the shim headers in platform/sdk.
SDK_UNITS = mtx mtxvec mtx44 vec quat OSAlloc
SDK_GEN = $(addprefix platform/sdk/gen/,$(addsuffix .c,$(SDK_UNITS)))

OBJDIR = obj
# REL modules linked into the image. On the GameCube each stage REL is its
# own link (config/G4BE08/modules/<mod>/splits.txt lists its units; the
# rooms it does not hold resolve to its _unresolved). tools/gen_modules.py
# turns every module in MODULES into one partially linked object whose only
# global symbols are its renamed entry points (obj/modules.mk), and
# platform/modules.cpp maps the REL header ids to them for OSLink.
MODULES = st1_0 st1_1 st1_2 st1_3 wep02 em12 em23
MODULE_OBJS =
MODULES_MK = $(OBJDIR)/modules.mk
GAME_OBJS = $(patsubst $(ROOT)/%.cpp,$(OBJDIR)/%.o,$(GAME_SRCS))
CENSUS_OBJS = $(patsubst $(ROOT)/%.cpp,$(OBJDIR)/%.o,$(CENSUS_SRCS))
PLATFORM_OBJS = $(patsubst %.cpp,$(OBJDIR)/%.o,$(PLATFORM_SRCS))
SDK_OBJS = $(patsubst platform/sdk/gen/%.c,$(OBJDIR)/sdk/%.o,$(SDK_GEN))
NATIVE_REUSE_OBJS = $(OBJDIR)/native-reuse/source_lighting.o $(OBJDIR)/native-reuse/native_draw_plan.o $(OBJDIR)/native-reuse/pvr_geometry.o $(OBJDIR)/native-reuse/gpu_lifecycle.o $(OBJDIR)/native-reuse/texture_package.o $(OBJDIR)/native-reuse/room_storage.o $(OBJDIR)/ui_bridge.o $(OBJDIR)/model_bridge.o $(OBJDIR)/model_asset_bridge.o $(OBJDIR)/motion_bridge.o $(OBJDIR)/parts_bridge.o
# Native static room packages (NATIVE_STATIC below); default images carry none of it.
ifeq ($(NATIVE_STATIC),1)
NATIVE_REUSE_OBJS += $(OBJDIR)/native-reuse/room_package.o
else
PLATFORM_OBJS := $(filter-out $(OBJDIR)/platform/native_static.o,$(PLATFORM_OBJS))
endif
# D367 actor path (probe PROPOSAL option A); default images carry none of it.
NATIVE_ACTOR ?= 0
ifneq ($(NATIVE_ACTOR),1)
PLATFORM_OBJS := $(filter-out $(OBJDIR)/platform/native_actor.o,$(PLATFORM_OBJS))
endif
OBJS = $(NATIVE_REUSE_OBJS) $(GAME_OBJS) $(MODULE_OBJS) $(PLATFORM_OBJS) $(SDK_OBJS)

GAME_OPT ?= -O1
# -fpermissive: cManager<T>::arrayPush names Debug_alloc before its
# declaration (a GCC 2.95 two-phase-lookup leniency the sources rely on).
# -w: the sources carry the original's warnings by design; the platform layer
# is compiled with warnings on below.
# -I$(ROOT)/src: a few tool units #include "tools/x.cpp" by that path.
# The prelude declares the libc functions some units use without declaring.
GAME_CPPFLAGS = -std=gnu++20 -fpermissive -w $(GAME_OPT) \
	-include platform/include/re4dc_prelude.h \
	-I$(ROOT)/include -I$(ROOT)/src -Iplatform/include -DRE4DC_GAME
PLATFORM_CPPFLAGS = -std=gnu++20 -Wall -Wextra $(GAME_OPT) \
	-Iplatform/include -DRE4DC_GAME

# Immutable qualified EVD file backing; mutable swaps remain explicitly rejected.
# Keep the source reference selectable while the event path is integrated.
EVENT_FILES ?= 0
.PHONY: event-files-force
$(OBJDIR)/event-files.h: event-files-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_EVENT_FILES %s\n' '$(EVENT_FILES)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/src/game/datactrl.o: $(OBJDIR)/event-files.h
$(OBJDIR)/src/game/datactrl.o: GAME_CPPFLAGS += -include $(OBJDIR)/event-files.h
SDK_CFLAGS = -w $(GAME_OPT) -Iplatform/sdk -I$(ROOT)/include

KOS_GCCVER_MIN = 12.0.0
include $(KOS_BASE)/Makefile.rules

.PHONY: all clean census

all: $(TARGET)

$(OBJDIR)/%.o: $(ROOT)/%.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -MMD -MP -c $< -o $@

$(OBJDIR)/platform/%.o: platform/%.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(PLATFORM_CPPFLAGS) -MMD -MP -c $< -o $@

# Nothing uses C++ exceptions or RTTI; their tables are ~362 KB of image, which
# lets the 13 MiB arena request fit (D367: source heap +256 KiB, KOS +~100 KB).
# FP instruction streams are unchanged in all 1,155 FP functions (fmac pairing).
NO_EH ?= 0
ifeq ($(NO_EH),1)
NO_EH_FLAGS = -fno-exceptions -fno-unwind-tables -fno-asynchronous-unwind-tables -fno-threadsafe-statics
GAME_CPPFLAGS += $(NO_EH_FLAGS)
PLATFORM_CPPFLAGS += $(NO_EH_FLAGS)
SDK_CFLAGS += -fno-unwind-tables -fno-asynchronous-unwind-tables
endif
platform/sdk/gen/%.c: $(ROOT)/src/lib/%.c platform/sdk/strip_cw_asm.py
	@mkdir -p $(dir $@)
	python3 platform/sdk/strip_cw_asm.py $< $@

$(OBJDIR)/sdk/%.o: platform/sdk/gen/%.c
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) $(SDK_CFLAGS) -MMD -MP -c $< -o $@

-include $(OBJS:.o=.d) $(CENSUS_OBJS:.o=.d)

$(MODULES_MK): Makefile tools/gen_modules.py $(ROOT)/config/G4BE08/modules.py $(ROOT)/config/G4BE08/modules/*/splits.txt $(ROOT)/src/st1/st1.cpp
	@mkdir -p $(OBJDIR)
	python3 tools/gen_modules.py $(ROOT)/config/G4BE08/modules $(ROOT) $(OBJDIR) $@ $(MODULES)
include $(MODULES_MK)

$(TARGET): $(KOS_BASE)/lib/$(KOS_ARCH)/libkallisti.a $(OBJS) tools/link.sh tools/gen_aliases.py tools/gen_missing.py platform/aliases-manual.ld
	@if [ "$(PVR_STREAM)" = 1 ]; then test "$$($(KOS_CC_BASE)/bin/$(KOS_CC_PREFIX)-nm -g --defined-only $(KOS_BASE)/lib/$(KOS_ARCH)/libkallisti.a | grep -Ec ' T _pvr_(set_manual_flip|resolve_frame)$$')" -eq 2 || { echo 'PVR_STREAM requires the pinned manual-flip KOS patch' >&2; exit 1; }; fi
	bash tools/link.sh $(TARGET) "$(GAME_OPT)" $(OBJS)

# Undefined-symbol inventory over every gameplay unit, REL modules included.
census: $(CENSUS_OBJS) $(PLATFORM_OBJS) $(SDK_OBJS)
	@kos-c++ $(GAME_OPT) -o /dev/null $(CENSUS_OBJS) $(PLATFORM_OBJS) $(SDK_OBJS) 2>&1 \
		| grep -o "undefined reference to \`[^']*'" \
		| sed "s/undefined reference to \`//; s/'$$//" \
		| sort | uniq -c | sort -rn > census.txt; \
	echo "undefined symbols: $$(wc -l < census.txt) (census.txt)"

clean:
	rm -rf $(OBJDIR) $(TARGET) census.txt platform/sdk/gen

# Existing native ownership/read/upload implementations; no second texture backend.
$(OBJDIR)/native-reuse/%.o: ../room/%.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(PLATFORM_CPPFLAGS) -MMD -MP -c $< -o $@
$(OBJDIR)/ui_bridge.o: ui_bridge.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -MMD -MP -c $< -o $@

$(OBJDIR)/motion_bridge.o: motion_bridge.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -MMD -MP -c $< -o $@

$(OBJDIR)/model_bridge.o: model_bridge.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -MMD -MP -c $< -o $@

$(OBJDIR)/model_asset_bridge.o: model_asset_bridge.cpp
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -MMD -MP -c $< -o $@

# Select the full source reference by default. A compact core candidate must
# match its report; the source DVD queue rejects oversized input before copying.
CORE_RESIDENT_BYTES ?= 0x234000
OPTION_RESIDENT_BYTES ?= 0x40000
PLAYER_RESIDENT_BYTES ?= 0x118000
WEAPON_RESIDENT_BYTES ?= 0x70000
# Bytes of the fixed 13 MiB source arena left to the KOS heap instead. The KOS
# heap funds native code/staging and had only a few KiB spare at D362; the
# native static candidate's code needs this. Zero keeps the reference layout.
ARENA_KOS_BYTES ?= $(if $(filter 1,$(NATIVE_STATIC)),32768,0)
.PHONY: core-budget-force
$(OBJDIR)/core-budget.h: core-budget-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_CORE_RESIDENT_BYTES %s\n' '$(CORE_RESIDENT_BYTES)' > $@.tmp
	@printf '#define RE4DC_OPTION_RESIDENT_BYTES %s\n' '$(OPTION_RESIDENT_BYTES)' >> $@.tmp
	@printf '#define RE4DC_PLAYER_RESIDENT_BYTES %s\n#define RE4DC_WEAPON_RESIDENT_BYTES %s\n' '$(PLAYER_RESIDENT_BYTES)' '$(WEAPON_RESIDENT_BYTES)' >> $@.tmp
	@printf '#define RE4DC_ARENA_KOS_BYTES %s\n' '$(ARENA_KOS_BYTES)' >> $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/mem.o: $(OBJDIR)/core-budget.h
$(OBJDIR)/platform/mem.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/core-budget.h

# Opt-in backing policy; logical source capacity and cParts layout are unchanged.
PARTS_DEMAND ?= 0
MODELINFO_DEMAND ?= 0
OBJECT_DEMAND ?= 0
ENEMY_DEMAND ?= 0
# Direct-slot consumers reviewed for this module set. Audit any newly linked
# module before enabling sparse enemy backing; census/reference remain usable.
ifeq ($(ENEMY_DEMAND),1)
ifneq ($(filter-out st1_0 st1_1 st1_2 st1_3 wep02 em12 em23,$(MODULES)),)
$(error ENEMY_DEMAND requires a direct-slot consumer audit for the selected MODULES)
endif
endif
.PHONY: parts-budget-force
$(OBJDIR)/parts-budget.h: parts-budget-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_PARTS_DEMAND %s\n' '$(PARTS_DEMAND)' > $@.tmp
	@printf '#define RE4DC_MODELINFO_DEMAND %s\n' '$(MODELINFO_DEMAND)' >> $@.tmp
	@printf '#define RE4DC_OBJECT_DEMAND %s\n' '$(OBJECT_DEMAND)' >> $@.tmp
	@printf '#define RE4DC_ENEMY_DEMAND %s\n' '$(ENEMY_DEMAND)' >> $@.tmp
	@cmp -s $@.tmp $@ || cp $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/parts_bridge.o: parts_bridge.cpp $(OBJDIR)/parts-budget.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -include $(OBJDIR)/parts-budget.h -MMD -MP -c $< -o $@

# Selectable serial native submission. The original KOS/reference stays usable.
# Only the existing frame owner needs this macro; source end-frame is neutral.
PVR_STREAM ?= 0
.PHONY: pvr-stream-force
$(OBJDIR)/pvr-stream.h: pvr-stream-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_PVR_STREAM %s\n' '$(PVR_STREAM)' > $@.tmp
	@cmp -s $@.tmp $@ || cp $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_ui.o: $(OBJDIR)/pvr-stream.h
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/pvr-stream.h

# D367 frame pipeline (all default off). PVR_FAST_WAKE: reschedule the PVR
# render-done/vblank waiter at once instead of on the next 10 ms tick.
# PVR_PIPELINE (implies FAST_WAKE): resolve/present the finished scene on a
# presenter thread while the next frame runs; fenced before the next scene
# and before any VRAM free/upload. PVR_PIPELINE=2: no presenter thread;
# the decision is applied by the render-done IRQ and flipped in the vblank IRQ
# (needs the KOS async-present patch; with TA_DOUBLEBUF=1 TA input of the next
# frame also overlaps the render). TA_DIRECT: store-queue direct submission
# API for emitters (native_model.h). BRIDGE_LEAN: libcall-free translucent
# view words and borrowed GX lighting per part.
# Hardware (TA/VRAM): TA_VERTBUF_KB per-bank vertex (parameter) buffer,
# TA_DOUBLEBUF, TA_OPB_BINS (16|32 words, OP/TR), TA_OPB_OVERFLOW; defaults
# are the current 1024/0/16/3. TA_GUARD=1: adaptive part budget + overflow
# detection/logging; =2 also never presents an overflowed scene.
# PERF_HUD=1: on-screen frame/CPU/render/wait/TA bars for console tests.
PVR_FAST_WAKE ?= 0
PVR_PIPELINE ?= 0
TA_DIRECT ?= 0
BRIDGE_LEAN ?= 0
TA_VERTBUF_KB ?= 1024
TA_DOUBLEBUF ?= 0
TA_OPB_BINS ?= 16
TA_OPB_OVERFLOW ?= 3
TA_GUARD ?= 0
PERF_HUD ?= 0
.PHONY: pipeline30-force
$(OBJDIR)/pipeline30.h: pipeline30-force
	@mkdir -p $(dir $@)
	@if [ "$(PVR_PIPELINE)" = 2 ]; then test "$$($(KOS_CC_BASE)/bin/$(KOS_CC_PREFIX)-nm -g --defined-only $(KOS_BASE)/lib/$(KOS_ARCH)/libkallisti.a | grep -Ec ' T _pvr_present_(async|wait|pending)$$')" -eq 3 || { echo 'PVR_PIPELINE=2 requires the KOS async-present patch' >&2; exit 1; }; fi
	@printf '#define RE4DC_PVR_FAST_WAKE %s\n#define RE4DC_PVR_PIPELINE %s\n#define RE4DC_TA_DIRECT %s\n#define RE4DC_BRIDGE_LEAN %s\n' '$(PVR_FAST_WAKE)' '$(PVR_PIPELINE)' '$(TA_DIRECT)' '$(BRIDGE_LEAN)' > $@.tmp
	@printf '#define RE4DC_TA_VERTBUF_KB %s\n#define RE4DC_TA_DOUBLEBUF %s\n#define RE4DC_TA_OPB_BINS %s\n#define RE4DC_TA_OPB_OVERFLOW %s\n#define RE4DC_TA_GUARD %s\n#define RE4DC_PERF_HUD %s\n' '$(TA_VERTBUF_KB)' '$(TA_DOUBLEBUF)' '$(TA_OPB_BINS)' '$(TA_OPB_OVERFLOW)' '$(TA_GUARD)' '$(PERF_HUD)' >> $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/model_bridge.o: $(OBJDIR)/pipeline30.h
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/pipeline30.h
$(OBJDIR)/model_bridge.o: GAME_CPPFLAGS += -include $(OBJDIR)/pipeline30.h
$(OBJDIR)/native-reuse/texture_package.o: $(OBJDIR)/pipeline30.h
$(OBJDIR)/native-reuse/texture_package.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/pipeline30.h

# Both renderer arms retain the full source arena. Reuse a smaller native I/O
# bounce (same reader, short-read/CRC/unaligned-small-file contracts), reclaiming
# 48 KiB of redundant staging rather than funding metadata from gameplay RAM.
$(OBJDIR)/native-reuse/room_storage.o: PLATFORM_CPPFLAGS += -DRE4DC_STORAGE_BOUNCE_BYTES=16384

# Exact source-position reuse, scoped to one native part. 0 is the reference path.
# Shared room/character strip assembly in recovered source models. Selectable
# until matched target timing and appearance qualification are complete.
D349_RENDERER_STACK ?= 0
ifeq ($(D349_RENDERER_STACK),1)
override MODEL_ROOM_STRIPS = 1
override MODEL_DRAW_PLANS = 1
override MODEL_POSITION_CACHE = 1
ifneq ($(PVR_STREAM),1)
$(error D349_RENDERER_STACK requires the existing PVR_STREAM=1 frame owner)
endif
endif
.PHONY: d349-stack-force
$(OBJDIR)/d349-stack.h: d349-stack-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_D349_RENDERER_STACK %s\n' '$(D349_RENDERER_STACK)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
D349_NATIVE_OBJS = $(OBJDIR)/native-reuse/source_lighting.o $(OBJDIR)/native-reuse/pvr_geometry.o $(OBJDIR)/platform/native_model.o $(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/gx_stub.o
$(D349_NATIVE_OBJS): $(OBJDIR)/d349-stack.h
$(D349_NATIVE_OBJS): PLATFORM_CPPFLAGS += -include $(OBJDIR)/d349-stack.h
$(OBJDIR)/src/game/trans.o: $(OBJDIR)/d349-stack.h
$(OBJDIR)/src/game/trans.o: GAME_CPPFLAGS += -include $(OBJDIR)/d349-stack.h
$(OBJDIR)/ui_bridge.o $(OBJDIR)/model_bridge.o $(OBJDIR)/model_asset_bridge.o: $(OBJDIR)/d349-stack.h
$(OBJDIR)/ui_bridge.o $(OBJDIR)/model_bridge.o $(OBJDIR)/model_asset_bridge.o: GAME_CPPFLAGS += -include $(OBJDIR)/d349-stack.h
# Bounded diagnostic attribution; both A/B arms use the same enabled policy.
NATIVE_RENDER_PROFILE ?= 0
.PHONY: native-profile-force
$(OBJDIR)/native-profile.h: native-profile-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_NATIVE_RENDER_PROFILE %s\n' '$(NATIVE_RENDER_PROFILE)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
# Default-off, bounded source-view/reuse audit through the existing RAM log.
NATIVE_REUSE_AUDIT ?= 0
.PHONY: native-reuse-audit-force
$(OBJDIR)/native-reuse-audit.h: native-reuse-audit-force
	@printf '#define RE4DC_NATIVE_REUSE_AUDIT %s\n' '$(NATIVE_REUSE_AUDIT)' > $@.tmp
	@cmp -s $@.tmp $@ || cp $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_model.o: $(OBJDIR)/native-reuse-audit.h platform/include/native_reuse_audit.hpp
$(OBJDIR)/platform/native_model.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/native-reuse-audit.h

$(OBJDIR)/platform/native_model.o $(OBJDIR)/platform/native_ui.o $(OBJDIR)/native-reuse/pvr_geometry.o: $(OBJDIR)/native-profile.h platform/include/native_render_profile.hpp
$(OBJDIR)/platform/native_model.o $(OBJDIR)/platform/native_ui.o $(OBJDIR)/native-reuse/pvr_geometry.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/native-profile.h
# Historical native-only kernel policy; source gameplay retains its current flags.
ifeq ($(D349_RENDERER_STACK),1)
$(OBJDIR)/platform/native_model.o $(OBJDIR)/native-reuse/source_lighting.o $(OBJDIR)/native-reuse/pvr_geometry.o: PLATFORM_CPPFLAGS += -O3 -fno-predictive-commoning
endif

MODEL_ROOM_STRIPS ?= 0
.PHONY: model-room-strips-force
$(OBJDIR)/model-room-strips.h: model-room-strips-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_MODEL_ROOM_STRIPS %s\n' '$(MODEL_ROOM_STRIPS)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_model.o: $(OBJDIR)/model-room-strips.h ../room/pvr_geometry.hpp platform/include/native_model.h
$(OBJDIR)/platform/native_model.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/model-room-strips.h
$(OBJDIR)/native-reuse/pvr_geometry.o: ../room/pvr_geometry.hpp

MODEL_POSITION_CACHE ?= 1
.PHONY: model-position-force
$(OBJDIR)/model-position.h: model-position-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_MODEL_POSITION_CACHE %s\n' '$(MODEL_POSITION_CACHE)' > $@.tmp
	@cmp -s $@.tmp $@ || cp $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_model.o: $(OBJDIR)/model-position.h
$(OBJDIR)/platform/native_model.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/model-position.h

# Compact structural plans share the existing native packet slab. No source
# heap reservation and no copied display-list corners.
MODEL_DRAW_PLANS ?= 0
.PHONY: model-draw-plan-force
$(OBJDIR)/model-draw-plan.h: model-draw-plan-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_MODEL_DRAW_PLANS %s\n' '$(MODEL_DRAW_PLANS)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_model.o $(OBJDIR)/platform/native_draw_plan_owner.o: $(OBJDIR)/model-draw-plan.h
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_model.o $(OBJDIR)/platform/native_draw_plan_owner.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/model-draw-plan.h

# Recovered scroll objects draw keyed v4 static room packages from
# /cd/dc/native/<room>/<owner>.re4room (platform/native_static.cpp). Opt-in until
# matched target visual/timing acceptance. NATIVE_STATIC_OWNERS is a mask:
# bit 0 main scenario, bit n+1 source block n.
NATIVE_STATIC ?= 0
NATIVE_STATIC_OWNERS ?= 1
# NATIVE_MESH=1 draws instanced per-BIN meshes (<owner>.re4mesh, COMMON.re4mesh)
# instead of placement-baked packages; owner mask bit 6 is the room's common set.
NATIVE_MESH ?= 0
ifeq ($(NATIVE_STATIC),1)
ifneq ($(D349_RENDERER_STACK),1)
$(error NATIVE_STATIC requires the D349_RENDERER_STACK=1 packet/deferral owner)
endif
# The fixed 13 MiB source arena leaves the KOS heap only a few KiB (D367); an
# image that grows by more exhausts it at r100 thread creation. Keep this small.
$(OBJDIR)/native-reuse/room_package.o $(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -Os
endif
.PHONY: native-static-force
$(OBJDIR)/native-static.h: native-static-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_NATIVE_STATIC %s\n#define RE4DC_NATIVE_STATIC_OWNERS %sU\n#define RE4DC_NATIVE_MESH %s\n' '$(NATIVE_STATIC)' '$(NATIVE_STATIC_OWNERS)' '$(NATIVE_MESH)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
NATIVE_STATIC_PLATFORM = $(OBJDIR)/platform/native_static.o $(OBJDIR)/platform/native_model.o $(OBJDIR)/platform/native_ui.o
NATIVE_STATIC_GAME = $(OBJDIR)/model_bridge.o $(OBJDIR)/ui_bridge.o $(OBJDIR)/src/game/scroll.o
$(NATIVE_STATIC_PLATFORM) $(NATIVE_STATIC_GAME): $(OBJDIR)/native-static.h platform/include/native_static.h
$(NATIVE_STATIC_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/native-static.h
$(NATIVE_STATIC_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/native-static.h
$(OBJDIR)/platform/native_static.o: $(OBJDIR)/d349-stack.h ../room/room_package.hpp ../room/static_room_prepare.hpp ../room/instanced_mesh.hpp
$(OBJDIR)/platform/native_static.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/d349-stack.h

# Non-scenery parts through platform/native_actor.cpp. Its ~14 KiB of -O2 code
# comes out of the source heap after the arena; build with NO_EH=1 to fund it.
ifeq ($(NATIVE_ACTOR),1)
ifneq ($(D349_RENDERER_STACK),1)
$(error NATIVE_ACTOR requires the D349_RENDERER_STACK=1 packet/deferral owner)
endif
$(OBJDIR)/platform/native_actor.o: PLATFORM_CPPFLAGS += -O2 -include $(OBJDIR)/d349-stack.h
$(OBJDIR)/platform/native_actor.o: $(OBJDIR)/d349-stack.h ../room/pvr_geometry.hpp platform/include/native_actor.hpp platform/include/native_model.h
endif
.PHONY: native-actor-force
$(OBJDIR)/native-actor.h: native-actor-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_NATIVE_ACTOR %s\n' '$(NATIVE_ACTOR)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
$(OBJDIR)/platform/native_model.o $(OBJDIR)/model_bridge.o: $(OBJDIR)/native-actor.h
$(OBJDIR)/platform/native_model.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/native-actor.h
$(OBJDIR)/model_bridge.o: GAME_CPPFLAGS += -include $(OBJDIR)/native-actor.h
