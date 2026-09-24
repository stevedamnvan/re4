# D367 records30 (design-lowmode DESIGN.md R1..). Included at the end of the Makefile. Every knob
# defaults to 0 and then contributes nothing (identical image). Render only.
#   FRONT_TEXOBJ=1  R1: the native model walk (FRONT_NATIVE=1) keeps the texture objects of each
#                   TPL set built once per room and reads them by index (cTexChg swaps as a remap)
#                   instead of re-running GXInitTexObj over every descriptor at each TPL change;
#                   gx->texObj is written only when the source path or a verifier reads it.
FRONT_TEXOBJ ?= 0
.PHONY: records30-force
$(OBJDIR)/records30.h: records30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_FRONT_TEXOBJ %s\n' '$(FRONT_TEXOBJ)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
RECORDS30_GAME = $(OBJDIR)/src/game/trans.o
$(RECORDS30_GAME): $(OBJDIR)/records30.h
$(RECORDS30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/records30.h
