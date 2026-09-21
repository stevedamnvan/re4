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
ROOT = ../../..

# The executable is the DOL's own code (src/game). The REL modules (stage
# rooms, sub-screens, tools, enemies) each define their own _prolog/_epilog
# and re-compile shared sources per module, so they join through the module
# table with per-module symbol prefixes (a later slice); the census still
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
GAME_OBJS = $(patsubst $(ROOT)/%.cpp,$(OBJDIR)/%.o,$(GAME_SRCS))
CENSUS_OBJS = $(patsubst $(ROOT)/%.cpp,$(OBJDIR)/%.o,$(CENSUS_SRCS))
PLATFORM_OBJS = $(patsubst %.cpp,$(OBJDIR)/%.o,$(PLATFORM_SRCS))
SDK_OBJS = $(patsubst platform/sdk/gen/%.c,$(OBJDIR)/sdk/%.o,$(SDK_GEN))
OBJS = $(GAME_OBJS) $(PLATFORM_OBJS) $(SDK_OBJS)

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

platform/sdk/gen/%.c: $(ROOT)/src/lib/%.c platform/sdk/strip_cw_asm.py
	@mkdir -p $(dir $@)
	python3 platform/sdk/strip_cw_asm.py $< $@

$(OBJDIR)/sdk/%.o: platform/sdk/gen/%.c
	@mkdir -p $(dir $@)
	kos-cc $(KOS_CFLAGS) $(SDK_CFLAGS) -MMD -MP -c $< -o $@

-include $(OBJS:.o=.d) $(CENSUS_OBJS:.o=.d)

$(TARGET): $(OBJS) tools/link.sh tools/gen_aliases.py tools/gen_missing.py platform/aliases-manual.ld
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
