# D367 scenery30 (design-scenery DESIGN.md). Included at the end of the Makefile. Every knob
# defaults to 0 and then contributes nothing (identical image). Render only, identical pixels.
#   PLAN_ADMIT_LEAN=1  D1: a model-info creation no longer forces the draw-plan local admission
#                      rebuild (visit_draw_locals + qsort, ~470 ms Flycast frames at every gunshot
#                      and spawn); the rebuild runs when a plan is really installed or after a reset.
#   SCENERY_GATE=1     S1a: a lit native-mesh scenery object whose whole mesh lies beyond the
#                      native cull depth (projection far, or the fogged View far) skips its render
#                      setup in ModelRender (needs FRONT_NATIVE=1 FRONT_LEAN=1 NATIVE_MESH=1).
#   MODEL_SLAB_LATCH=1 a failed 64 KiB native model slab allocation is tried once per room instead
#                      of once per part (each retry walked the allocator and logged "Out of memory").
PLAN_ADMIT_LEAN ?= 0
SCENERY_GATE ?= 0
MODEL_SLAB_LATCH ?= 0
.PHONY: scenery30-force
$(OBJDIR)/scenery30.h: scenery30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_PLAN_ADMIT_LEAN %s\n#define RE4DC_SCENERY_GATE %s\n#define RE4DC_MODEL_SLAB_LATCH %s\n' '$(PLAN_ADMIT_LEAN)' '$(SCENERY_GATE)' '$(MODEL_SLAB_LATCH)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
SCENERY30_GAME = $(OBJDIR)/src/game/trans.o
SCENERY30_PLATFORM = $(OBJDIR)/platform/native_static.o $(OBJDIR)/platform/native_draw_plan_owner.o $(OBJDIR)/platform/native_ui.o
$(SCENERY30_GAME) $(SCENERY30_PLATFORM): $(OBJDIR)/scenery30.h
$(SCENERY30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/scenery30.h
$(SCENERY30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/scenery30.h
