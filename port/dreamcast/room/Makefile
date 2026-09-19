TARGET = re4dc-room-viewer.elf
OBJS = main.o room_package.o collision_package.o character_package.o texture_package.o romdisk.o
ROOM_PACKAGE ?= ../build/private/r10d.re4room
COLLISION_PACKAGE ?= ../build/private/r10d.re4sat
CHARACTER_PACKAGE ?= ../build/private/leon.re4chr
ENEMY_PACKAGE ?= ../build/private/ganado.re4chr
TEXTURE_PACKAGE ?= ../build/private/r10d.re4tex
AUTOPLAY_FLAG ?=
KOS_ROMDISK_DIR = ../build/room-romdisk

romdisk.img: KOS_GENROMFS := $(KOS_GENROMFS) -V re4dc-room

KOS_CPPFLAGS += -std=c++20 -Wall -Wextra -Werror -I../include
KOS_GCCVER_MIN = 12.0.0

.PHONY: all clean rm-elf run prepare-romdisk

all: prepare-romdisk rm-elf $(TARGET)

include $(KOS_BASE)/Makefile.rules

ifeq ($(call KOS_GCCVER_MIN_CHECK,$(KOS_GCCVER_MIN)),1)

prepare-romdisk:
	@test -f $(ROOM_PACKAGE) || { echo 'missing private room package: $(ROOM_PACKAGE)' >&2; exit 1; }
	@test -f $(COLLISION_PACKAGE) || { echo 'missing private collision package: $(COLLISION_PACKAGE)' >&2; exit 1; }
	@test -f $(CHARACTER_PACKAGE) || { echo 'missing private character package: $(CHARACTER_PACKAGE)' >&2; exit 1; }
	@test -f $(ENEMY_PACKAGE) || { echo 'missing private enemy package: $(ENEMY_PACKAGE)' >&2; exit 1; }
	@test -f $(TEXTURE_PACKAGE) || { echo 'missing private texture package: $(TEXTURE_PACKAGE)' >&2; exit 1; }
	@mkdir -p $(KOS_ROMDISK_DIR)
	cp $(ROOM_PACKAGE) $(KOS_ROMDISK_DIR)/r10d.re4room
	cp $(COLLISION_PACKAGE) $(KOS_ROMDISK_DIR)/r10d.re4sat
	cp $(CHARACTER_PACKAGE) $(KOS_ROMDISK_DIR)/leon.re4chr
	cp $(ENEMY_PACKAGE) $(KOS_ROMDISK_DIR)/ganado.re4chr
	cp $(TEXTURE_PACKAGE) $(KOS_ROMDISK_DIR)/r10d.re4tex
	@if [ -n "$(AUTOPLAY_FLAG)" ]; then \
		test -f "$(AUTOPLAY_FLAG)" || { echo 'missing autoplay flag: $(AUTOPLAY_FLAG)' >&2; exit 1; }; \
		cp "$(AUTOPLAY_FLAG)" $(KOS_ROMDISK_DIR)/autoplay.flag; \
	fi

romdisk.img: prepare-romdisk

clean: rm-elf
	-rm -f $(OBJS) romdisk.img
	-rm -rf $(KOS_ROMDISK_DIR)

rm-elf:
	-rm -f $(TARGET)

$(TARGET): $(OBJS)
	kos-c++ -o $(TARGET) $(OBJS)

run: $(TARGET)
	$(KOS_LOADER) $(TARGET)

else
  all $(TARGET) clean rm-elf run prepare-romdisk:
	$(KOS_GCCVER_MIN_WARNING)
endif
