TARGET = re4dc-room-viewer.elf
OBJS = main.o room_package.o collision_package.o character_package.o texture_package.o route_package.o source_hud_package.o romdisk.o
ROOM_PACKAGE ?= ../build/private/r10d.re4room
COLLISION_PACKAGE ?= ../build/private/r10d.re4sat
CHARACTER_PACKAGE ?= ../build/private/leon.re4chr
ENEMY_PACKAGE ?= ../build/private/ganado.re4chr
CHARACTER_TEXTURE_PACKAGE ?= ../build/private/leon.re4tex
ENEMY_TEXTURE_PACKAGE ?= ../build/private/ganado.re4tex
TEXTURE_PACKAGE ?= ../build/private/r10d.re4tex
HUD_PACKAGE ?= ../build/private/source-hud.re4hud
HUD_TEXTURE_PACKAGE ?= ../build/private/source-hud.re4tex
ROUTE_PACKAGE ?=
AUTOPLAY_FLAG ?=
FIRE_SOUND_0 ?=
FIRE_SOUND_2 ?=
RELOAD_SOUND ?=
ENEMY_SWING_SOUND ?=
ENEMY_HIT_SOUND ?=
ENEMY_DAMAGE_VOICE ?=
ENEMY_DEATH_VOICE ?=
PLAYER_DAMAGE_VOICE_9 ?=
PLAYER_DAMAGE_VOICE_10 ?=
PLAYER_DAMAGE_VOICE_11 ?=
PLAYER_DEATH_VOICE_13 ?=
DEMO_SCENE ?= r10d
R100_ROOM_PACKAGE ?= ../build/private/r100-source-cell-4.re4room
# Preserve the r100 presentation slice at native Dreamcast VGA resolution.
# The older r10d engineering fixture stays at 240p unless explicitly overridden.
DEMO_RESOLUTION ?= $(if $(filter r100,$(DEMO_SCENE)),480p,240p)
KOS_ROMDISK_DIR = ../build/room-romdisk
BUILD_CONFIG = .build-config

romdisk.img: KOS_GENROMFS := $(KOS_GENROMFS) -V re4dc-room

CPPFLAGS += -std=c++20 -O2 -Wall -Wextra -Werror -I../include
ifeq ($(DEMO_SCENE),r100)
CPPFLAGS += -DRE4DC_SCENE_R100
endif
ifeq ($(DEMO_RESOLUTION),480p)
CPPFLAGS += -DRE4DC_480P
endif
ifneq ($(DEMO_YAW),)
CPPFLAGS += -DRE4DC_DEMO_YAW=$(DEMO_YAW)
endif
# Diagnostic submission profiling. Not part of any accepted build.
ifneq ($(SUBMIT_PROFILE),)
CPPFLAGS += -DRE4DC_SUBMIT_PROFILE
endif
# Diagnostic strip-culling audit. Not part of any accepted build.
ifneq ($(CULL_AUDIT),)
CPPFLAGS += -DRE4DC_CULL_AUDIT
endif
# Diagnostic checksum of the submitted vertex stream. Not part of any accepted
# build: it reads back every submitted byte and is far too slow to time with.
ifneq ($(SUBMIT_DIGEST),)
CPPFLAGS += -DRE4DC_SUBMIT_DIGEST
endif
KOS_GCCVER_MIN = 12.0.0

.PHONY: all clean rm-elf run prepare-romdisk r100 r100-autoplay r100-autoplay-profile r100-autoplay-cull-audit r100-autoplay-digest FORCE

all: prepare-romdisk rm-elf $(TARGET)

r100:
	$(MAKE) all DEMO_SCENE=r100 \
		ROOM_PACKAGE=$(R100_ROOM_PACKAGE) \
		COLLISION_PACKAGE=../build/private/r100-meters.re4sat \
		CHARACTER_PACKAGE=../build/private/leon-source-r100-gunhitcaps-pitch.re4chr \
		ENEMY_PACKAGE=../build/private/ganado-source-r100-hitcaps.re4chr \
		CHARACTER_TEXTURE_PACKAGE=../build/private/leon-source-r100-gunhitcaps-pitch.re4tex \
		ENEMY_TEXTURE_PACKAGE=../build/private/ganado-source-r100-hitcaps.re4tex \
		TEXTURE_PACKAGE=../build/private/r100-entry-source.re4tex \
		HUD_PACKAGE=../build/private/source-hud.re4hud \
		HUD_TEXTURE_PACKAGE=../build/private/source-hud.re4tex \
		ROUTE_PACKAGE=../build/private/r100.re4rtp \
		FIRE_SOUND_0=../build/private/source-audio/wep02-cue00.wav \
		FIRE_SOUND_2=../build/private/source-audio/wep02-cue02.wav \
		RELOAD_SOUND=../build/private/source-audio/wep02-cue16.wav \
		ENEMY_SWING_SOUND=../build/private/source-enemy-audio/em12-cue3d.wav \
		ENEMY_HIT_SOUND=../build/private/source-enemy-audio/em12-body-hit-0c.wav \
		ENEMY_DAMAGE_VOICE=../build/private/source-enemy-audio/em12-damage-voice-47.wav \
		ENEMY_DEATH_VOICE=../build/private/source-enemy-audio/em12-death-voice-16.wav \
		PLAYER_DAMAGE_VOICE_9=../build/private/source-player-audio/pl00-cue09.wav \
		PLAYER_DAMAGE_VOICE_10=../build/private/source-player-audio/pl00-cue10.wav \
		PLAYER_DAMAGE_VOICE_11=../build/private/source-player-audio/pl00-cue11.wav \
		PLAYER_DEATH_VOICE_13=../build/private/source-player-audio/pl00-cue13.wav

r100-autoplay:
	$(MAKE) r100 AUTOPLAY_FLAG=../build/private/autoplay.flag

r100-autoplay-profile:
	$(MAKE) r100 AUTOPLAY_FLAG=../build/private/autoplay.flag SUBMIT_PROFILE=1

r100-autoplay-cull-audit:
	$(MAKE) r100 AUTOPLAY_FLAG=../build/private/autoplay.flag CULL_AUDIT=1

r100-autoplay-digest:
	$(MAKE) r100 AUTOPLAY_FLAG=../build/private/autoplay.flag SUBMIT_DIGEST=1

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

main.o room_package.o collision_package.o character_package.o texture_package.o route_package.o source_hud_package.o: $(BUILD_CONFIG)

# Header dependency tracking. Without it a package-layout change in a header
# left main.o compiled against the old layout (R4b, 2026-09-20).
KOS_CFLAGS += -MMD -MP
-include $(OBJS:.o=.d)

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
	rm -f $(KOS_ROMDISK_DIR)/source-hud.re4hud \
		$(KOS_ROMDISK_DIR)/source-hud.re4tex
ifeq ($(DEMO_SCENE),r100)
	@test -f $(HUD_PACKAGE) || { echo 'missing private source HUD package: $(HUD_PACKAGE)' >&2; exit 1; }
	@test -f $(HUD_TEXTURE_PACKAGE) || { echo 'missing private source HUD textures: $(HUD_TEXTURE_PACKAGE)' >&2; exit 1; }
	cp $(HUD_PACKAGE) $(KOS_ROMDISK_DIR)/source-hud.re4hud
	cp $(HUD_TEXTURE_PACKAGE) $(KOS_ROMDISK_DIR)/source-hud.re4tex
endif
	rm -f $(KOS_ROMDISK_DIR)/route.re4rtp
	@if [ -n "$(ROUTE_PACKAGE)" ]; then \
		test -f "$(ROUTE_PACKAGE)" || { echo 'missing private route package: $(ROUTE_PACKAGE)' >&2; exit 1; }; \
		cp "$(ROUTE_PACKAGE)" $(KOS_ROMDISK_DIR)/route.re4rtp; \
	fi
	rm -f $(KOS_ROMDISK_DIR)/autoplay.flag
	rm -f $(KOS_ROMDISK_DIR)/wep02-fire-0.wav \
		$(KOS_ROMDISK_DIR)/wep02-fire-2.wav \
		$(KOS_ROMDISK_DIR)/wep02-reload-16.wav \
		$(KOS_ROMDISK_DIR)/em12-swing-3d.wav \
		$(KOS_ROMDISK_DIR)/em12-body-hit-0c.wav \
		$(KOS_ROMDISK_DIR)/em12-damage-voice-47.wav \
		$(KOS_ROMDISK_DIR)/em12-death-voice-16.wav \
		$(KOS_ROMDISK_DIR)/pl00-damage-voice-09.wav \
		$(KOS_ROMDISK_DIR)/pl00-damage-voice-10.wav \
		$(KOS_ROMDISK_DIR)/pl00-damage-voice-11.wav \
		$(KOS_ROMDISK_DIR)/pl00-death-voice-13.wav
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
	@if [ -n "$(ENEMY_HIT_SOUND)$(ENEMY_DAMAGE_VOICE)$(ENEMY_DEATH_VOICE)" ]; then \
		test -n "$(ENEMY_HIT_SOUND)" -a -n "$(ENEMY_DAMAGE_VOICE)" -a -n "$(ENEMY_DEATH_VOICE)" || \
			{ echo 'source enemy reaction audio requires hit 0x0c, damage 0x47, and death 0x16' >&2; exit 1; }; \
		test -f "$(ENEMY_HIT_SOUND)" || { echo 'missing enemy body-hit cue 0x0c: $(ENEMY_HIT_SOUND)' >&2; exit 1; }; \
		test -f "$(ENEMY_DAMAGE_VOICE)" || { echo 'missing enemy damage voice 0x47: $(ENEMY_DAMAGE_VOICE)' >&2; exit 1; }; \
		test -f "$(ENEMY_DEATH_VOICE)" || { echo 'missing enemy death voice 0x16: $(ENEMY_DEATH_VOICE)' >&2; exit 1; }; \
		cp "$(ENEMY_HIT_SOUND)" $(KOS_ROMDISK_DIR)/em12-body-hit-0c.wav; \
		cp "$(ENEMY_DAMAGE_VOICE)" $(KOS_ROMDISK_DIR)/em12-damage-voice-47.wav; \
		cp "$(ENEMY_DEATH_VOICE)" $(KOS_ROMDISK_DIR)/em12-death-voice-16.wav; \
	fi
	@if [ -n "$(PLAYER_DAMAGE_VOICE_9)$(PLAYER_DAMAGE_VOICE_10)$(PLAYER_DAMAGE_VOICE_11)$(PLAYER_DEATH_VOICE_13)" ]; then \
		test -n "$(PLAYER_DAMAGE_VOICE_9)" -a -n "$(PLAYER_DAMAGE_VOICE_10)" -a -n "$(PLAYER_DAMAGE_VOICE_11)" -a -n "$(PLAYER_DEATH_VOICE_13)" || \
			{ echo 'source player reactions require damage cues 9-11 and death cue 13' >&2; exit 1; }; \
		test -f "$(PLAYER_DAMAGE_VOICE_9)" || { echo 'missing player damage voice 9: $(PLAYER_DAMAGE_VOICE_9)' >&2; exit 1; }; \
		test -f "$(PLAYER_DAMAGE_VOICE_10)" || { echo 'missing player damage voice 10: $(PLAYER_DAMAGE_VOICE_10)' >&2; exit 1; }; \
		test -f "$(PLAYER_DAMAGE_VOICE_11)" || { echo 'missing player damage voice 11: $(PLAYER_DAMAGE_VOICE_11)' >&2; exit 1; }; \
		test -f "$(PLAYER_DEATH_VOICE_13)" || { echo 'missing player death voice 13: $(PLAYER_DEATH_VOICE_13)' >&2; exit 1; }; \
		cp "$(PLAYER_DAMAGE_VOICE_9)" $(KOS_ROMDISK_DIR)/pl00-damage-voice-09.wav; \
		cp "$(PLAYER_DAMAGE_VOICE_10)" $(KOS_ROMDISK_DIR)/pl00-damage-voice-10.wav; \
		cp "$(PLAYER_DAMAGE_VOICE_11)" $(KOS_ROMDISK_DIR)/pl00-damage-voice-11.wav; \
		cp "$(PLAYER_DEATH_VOICE_13)" $(KOS_ROMDISK_DIR)/pl00-death-voice-13.wav; \
	fi

romdisk.img: prepare-romdisk

clean: rm-elf
	-rm -f $(OBJS) $(OBJS:.o=.d) romdisk.img $(BUILD_CONFIG) $(BUILD_CONFIG).tmp
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
