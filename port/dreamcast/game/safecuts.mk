# D367 safe cuts (enemy/object census, SAFE class). Included at the end of the Makefile. The knob
# defaults to 0 and then contributes nothing: the image is identical with or without this file.
#   FX_LEAN=1   character foot shadows off (DrawFootShadow; the blob sprites under the characters,
#               drawn through GX, read-only on game state). Render only (determinism trace gate).
# (CUT_GORE was measured and rejected by the user: gore stays.)
FX_LEAN ?= 0
.PHONY: safecuts-force
$(OBJDIR)/safecuts.h: safecuts-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_FX_LEAN %s\n' '$(FX_LEAN)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
SAFECUTS_GAME = $(OBJDIR)/src/game/foot_shadow.o
$(SAFECUTS_GAME): $(OBJDIR)/safecuts.h
$(SAFECUTS_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/safecuts.h
