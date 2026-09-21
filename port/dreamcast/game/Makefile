# The boot-forward RE4 executable: the recovered game sources compiled for
# SH-4 over a Dreamcast implementation of the platform interfaces they call
# (port/dreamcast/platform). This is the game's own main(), scheduler, title,
# game state machine, scenario system, rooms, player, enemies and tools, not
# the room viewer in ../room.
#
#   make            build re4dc-game.elf
#   make census     compile everything and list the symbols the platform
#                   layer still has to provide (no ELF is produced)
#
# Sources outside this directory are never written to: objects go under obj/.

TARGET = re4dc-game.elf
ROOT = ../../..

# Gameplay units. The em*/pl*/wep* module directories join as the link
# demands them; the libc replacements (src/game/*.c) are CodeWarrior's and
# newlib stands in for them; the two whole-function PowerPC asm units have C
# replacements in platform/.
GAME_DIRS = src/game src/st src/st1 src/Sscrn \
	src/tools src/Tools src/t_camera src/t_emlist src/t_esp src/t_event \
	src/t_id src/t_light src/t_movie src/t_sce
# t_util_{menu,nomenu,id}.cpp are the REL-specific re-includes of t_util.cpp (one
# object per REL on the GameCube); one copy serves the single Dreamcast image.
GAME_EXCLUDE = src/game/yz2asm.cpp src/game/memset_2.cpp \
	src/tools/t_util_menu.cpp src/tools/t_util_nomenu.cpp src/tools/t_util_id.cpp
GAME_SRCS = $(filter-out $(addprefix $(ROOT)/,$(GAME_EXCLUDE)), \
	$(foreach d,$(GAME_DIRS),$(wildcard $(ROOT)/$(d)/*.cpp)))
PLATFORM_SRCS = $(wildcard platform/*.cpp)

OBJDIR = obj
GAME_OBJS = $(patsubst $(ROOT)/%.cpp,$(OBJDIR)/%.o,$(GAME_SRCS))
PLATFORM_OBJS = $(patsubst %.cpp,$(OBJDIR)/%.o,$(PLATFORM_SRCS))
OBJS = $(GAME_OBJS) $(PLATFORM_OBJS)

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
	-I$(ROOT)/include -Iplatform/include -DRE4DC_GAME

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

-include $(OBJS:.o=.d)

$(TARGET): $(OBJS)
	kos-c++ $(GAME_OPT) -o $(TARGET) $(OBJS)

# Undefined-symbol inventory: every game object linked with nothing but the
# platform objects present; the linker's complaints are the remaining surface.
census: $(OBJS)
	@kos-c++ $(GAME_OPT) -o /dev/null $(OBJS) 2>&1 \
		| grep -o "undefined reference to \`[^']*'" \
		| sed "s/undefined reference to \`//; s/'$$//" \
		| sort | uniq -c | sort -rn > census.txt; \
	echo "undefined symbols: $$(wc -l < census.txt) (census.txt)"

clean:
	rm -rf $(OBJDIR) $(TARGET) census.txt
