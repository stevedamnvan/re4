# D367 effects30: effect sprites (EspCommonTrans). Included at the end of the Makefile. Every
# knob defaults to 0 and then contributes nothing (identical image).
#   EFFECT_LEAN=1    the common sprite draw keeps only the GX state the native side reads
#                    (projection, normal matrix, channel control/material colour, TEV scale);
#                    no blend/TEV/vertex-format/texture-load/display-list stub traffic. The
#                    heat-shimmer and frame-buffer ("nega") variants are untouched. Render only.
#   EFFECT_SPRITES=1 native PVR sprites for the approved classes: weapon muzzle flash (owners
#                    0x34..0x4f), the core effects of the same shot (owner 0) and blood (owner
#                    0x10). Excluded: full-screen sheets (0xd0), room ambient/screen effects (0x01),
#                    masked, spline (Esp1b), texture-render targets, non-blend modes. Sprites go
#                    into the deferred translucent queue in OT order; on queue pressure a sprite
#                    is dropped, never the frame. Render only.
#   EFFECT_SPRITE_MAX=N  sprites per frame (default 64).
EFFECT_LEAN ?= 0
EFFECT_SPRITES ?= 0
EFFECT_SPRITE_MAX ?= 64
.PHONY: effects30-force
$(OBJDIR)/effects30.h: effects30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_EFFECT_LEAN %s\n#define RE4DC_EFFECT_SPRITES %s\n#define RE4DC_EFFECT_SPRITE_MAX %s\n' '$(EFFECT_LEAN)' '$(EFFECT_SPRITES)' '$(EFFECT_SPRITE_MAX)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
EFFECTS30_GAME = $(OBJDIR)/src/game/esp_sub.o
EFFECTS30_PLATFORM = $(OBJDIR)/platform/native_ui.o
$(EFFECTS30_GAME) $(EFFECTS30_PLATFORM): $(OBJDIR)/effects30.h
$(EFFECTS30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/effects30.h
$(EFFECTS30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/effects30.h
