TARGET = re4dc-room-viewer.elf
OBJS = main.o room_package.o collision_package.o character_package.o texture_package.o romdisk.o
ROOM_PACKAGE ?= ../build/private/r10d.re4room
COLLISION_PACKAGE ?= ../build/private/r10d.re4sat
CHARACTER_PACKAGE ?= ../build/private/leon.re4chr
ENEMY_PACKAGE ?= ../build/private/ganado.re4chr
CHARACTER_TEXTURE_PACKAGE ?= ../build/private/leon.re4tex
ENEMY_TEXTURE_PACKAGE ?= ../build/private/ganado.re4tex
TEXTURE_PACKAGE ?= ../build/private/r10d.re4tex
AUTOPLAY_FLAG ?=
FIRE_SOUND_0 ?=
FIRE_SOUND_2 ?=
RELOAD_SOUND ?=
ENEMY_SWING_SOUND ?=
DEMO_SCENE ?= r10d
DEMO_RESOLUTION ?= 240p
KOS_ROMDISK_DIR = ../build/room-romdisk
BUILD_CONFIG = .build-config

romdisk.img: KOS_GENROMFS := $(KOS_GENROMFS) -V re4dc-room

CPPFLAGS += -std=c++20 -Wall -Wextra -Werror -I../include
ifeq ($(DEMO_SCENE),r100)
CPPFLAGS += -DRE4DC_SCENE_R100
endif
ifeq ($(DEMO_RESOLUTION),480p)
CPPFLAGS += -DRE4DC_480P
endif
ifneq ($(DEMO_YAW),)
CPPFLAGS += -DRE4DC_DEMO_YAW=$(DEMO_YAW)
endif
KOS_GCCVER_MIN = 12.0.0

.PHONY: all clean rm-elf run prepare-romdisk FORCE

all: prepare-romdisk rm-elf $(TARGET)

include $(KOS_BASE)/Makefile.rules

ifeq ($(call KOS_GCCVER_MIN_CHECK,$(KOS_GCCVER_MIN)),1)

FORCE:

$(BUILD_CONFIG): FORCE
	@printf '%s\n' '$(CPPFLAGS)' > $(BUILD_CONFIG).tmp
	@if ! cmp -s $(BUILD_CONFIG).tmp $(BUILD_CONFIG); then \
		mv $(BUILD_CONFIG).tmp $(BUILD_CONFIG); \
	else \
		rm -f $(BUILD_CONFIG).tmp; \
	fi

main.o room_package.o collision_package.o character_package.o texture_package.o: $(BUILD_CONFIG)

prepare-romdisk:
	@test -f $(ROOM_PACKAGE) || { echo 'missing private room package: $(ROOM_PACKAGE)' >&2; exit 1; }
	@test -f $(COLLISION_PACKAGE) || { echo 'missing private collision package: $(COLLISION_PACKAGE)' >&2; exit 1; }
	@test -f $(CHARACTER_PACKAGE) || { echo 'missing private character package: $(CHARACTER_PACKAGE)' >&2; exit 1; }
	@test -f $(ENEMY_PACKAGE) || { echo 'missing private enemy package: $(ENEMY_PACKAGE)' >&2; exit 1; }
	@test -f $(CHARACTER_TEXTURE_PACKAGE) || { echo 'missing private character texture package: $(CHARACTER_TEXTURE_PACKAGE)' >&2; exit 1; }
	@test -f $(ENEMY_TEXTURE_PACKAGE) || { echo 'missing private enemy texture package: $(ENEMY_TEXTURE_PACKAGE)' >&2; exit 1; }
	@test -f $(TEXTURE_PACKAGE) || { echo 'missing private texture package: $(TEXTURE_PACKAGE)' >&2; exit 1; }
	@mkdir -p $(KOS_ROMDISK_DIR)
	cp $(ROOM_PACKAGE) $(KOS_ROMDISK_DIR)/r10d.re4room
	cp $(COLLISION_PACKAGE) $(KOS_ROMDISK_DIR)/r10d.re4sat
	cp $(CHARACTER_PACKAGE) $(KOS_ROMDISK_DIR)/leon.re4chr
	cp $(ENEMY_PACKAGE) $(KOS_ROMDISK_DIR)/ganado.re4chr
	cp $(CHARACTER_TEXTURE_PACKAGE) $(KOS_ROMDISK_DIR)/leon.re4tex
	cp $(ENEMY_TEXTURE_PACKAGE) $(KOS_ROMDISK_DIR)/ganado.re4tex
	cp $(TEXTURE_PACKAGE) $(KOS_ROMDISK_DIR)/r10d.re4tex
	rm -f $(KOS_ROMDISK_DIR)/autoplay.flag
	rm -f $(KOS_ROMDISK_DIR)/wep02-fire-0.wav \
		$(KOS_ROMDISK_DIR)/wep02-fire-2.wav \
		$(KOS_ROMDISK_DIR)/wep02-reload-16.wav \
		$(KOS_ROMDISK_DIR)/em12-swing-3d.wav
	@if [ -n "$(AUTOPLAY_FLAG)" ]; then \
		test -f "$(AUTOPLAY_FLAG)" || { echo 'missing autoplay flag: $(AUTOPLAY_FLAG)' >&2; exit 1; }; \
		cp "$(AUTOPLAY_FLAG)" $(KOS_ROMDISK_DIR)/autoplay.flag; \
	fi
	@if [ -n "$(FIRE_SOUND_0)$(FIRE_SOUND_2)$(RELOAD_SOUND)" ]; then \
		test -n "$(FIRE_SOUND_0)" -a -n "$(FIRE_SOUND_2)" -a -n "$(RELOAD_SOUND)" || \
			{ echo 'source weapon audio requires fire cues 0 and 2 plus reload cue 0x16' >&2; exit 1; }; \
		test -f "$(FIRE_SOUND_0)" || { echo 'missing fire cue 0: $(FIRE_SOUND_0)' >&2; exit 1; }; \
		test -f "$(FIRE_SOUND_2)" || { echo 'missing fire cue 2: $(FIRE_SOUND_2)' >&2; exit 1; }; \
		test -f "$(RELOAD_SOUND)" || { echo 'missing reload cue 0x16: $(RELOAD_SOUND)' >&2; exit 1; }; \
		cp "$(FIRE_SOUND_0)" $(KOS_ROMDISK_DIR)/wep02-fire-0.wav; \
		cp "$(FIRE_SOUND_2)" $(KOS_ROMDISK_DIR)/wep02-fire-2.wav; \
		cp "$(RELOAD_SOUND)" $(KOS_ROMDISK_DIR)/wep02-reload-16.wav; \
	fi
	@if [ -n "$(ENEMY_SWING_SOUND)" ]; then \
		test -f "$(ENEMY_SWING_SOUND)" || { echo 'missing enemy swing cue 0x3d: $(ENEMY_SWING_SOUND)' >&2; exit 1; }; \
		cp "$(ENEMY_SWING_SOUND)" $(KOS_ROMDISK_DIR)/em12-swing-3d.wav; \
	fi

romdisk.img: prepare-romdisk

clean: rm-elf
	-rm -f $(OBJS) romdisk.img $(BUILD_CONFIG) $(BUILD_CONFIG).tmp
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
