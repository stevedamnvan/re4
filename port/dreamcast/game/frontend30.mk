# D367 frontend30: memory-copy audit and GC render front-end trimming. Included at the end of
# the Makefile. Every knob defaults to 0 and then contributes nothing (identical image).
#   COPY_LEAN=1   native renderer staging without redundant work: no zero-fill of scratch that
#                 is written before it is read, word copies instead of SH-4 memcpy libcalls in
#                 the GX state stubs, hash-first compares of deferred lighting, one-pass view
#                 diffs, texture-key lookups indexed instead of scanned (same keys), and no
#                 lighting snapshot for deferred scenery parts that are already lit. On SH-4 also:
#                 no eprintf formatting (the debug-text glyphs go to the GXWGFifo sink, never
#                 shown) and the mem_alloc "file(line)" tag written without sprintf (same bytes).
#   FRONT_LEAN=1  skip recovered-game render preparation the native renderers make redundant:
#                 light selection / GX light objects / normal matrix for scenery whose every
#                 drawn info is an already lit native mesh, and the per-frame draw-plan OT walk
#                 when the registration set is unchanged. Render-only (determinism trace gate).
#   MESH_DIRECT=1 native scenery meshes go to the TA through the store queues instead of
#                 packet slab + pvr_prim copy (needs TA_DIRECT=1; pair with NATIVE_ACTOR_DIRECT=1).
#   HW_LEAN=1     pass 2, SH-4 hardware costs Flycast under-charges (hwmodel): 1/w by fsrra(w*w)
#                 instead of fdiv in the scenery transform and the clipper projection (render only).
#   RELEASE_FLAGS=N  debug-disc boot displays off (debug.cpp ConfigSet): 1 heap/process-bar overlay
#                 (Debug_flg[2] 0x40000000), 2 + pad monitor (0x8000), 3 + debug_mode 0.
COPY_LEAN ?= 0
FRONT_LEAN ?= 0
MESH_DIRECT ?= 0
HW_LEAN ?= 0
RELEASE_FLAGS ?= 0
ifeq ($(MESH_DIRECT),1)
ifneq ($(TA_DIRECT),1)
$(error MESH_DIRECT=1 requires TA_DIRECT=1 (pipeline30 direct TA API))
endif
endif
.PHONY: frontend30-force
$(OBJDIR)/frontend30.h: frontend30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_COPY_LEAN %s\n#define RE4DC_FRONT_LEAN %s\n#define RE4DC_MESH_DIRECT %s\n#define RE4DC_HW_LEAN %s\n#define RE4DC_RELEASE_FLAGS %s\n' '$(COPY_LEAN)' '$(FRONT_LEAN)' '$(MESH_DIRECT)' '$(HW_LEAN)' '$(RELEASE_FLAGS)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
FRONTEND30_PLATFORM = $(OBJDIR)/native-reuse/pvr_geometry.o $(OBJDIR)/platform/native_static.o \
	$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/gx_stub.o $(OBJDIR)/platform/native_draw_plan_owner.o
FRONTEND30_GAME = $(OBJDIR)/model_asset_bridge.o $(OBJDIR)/src/game/trans.o $(OBJDIR)/src/game/eprintf.o $(OBJDIR)/src/game/main_mem.o $(OBJDIR)/src/game/debug.o
$(FRONTEND30_PLATFORM) $(FRONTEND30_GAME): $(OBJDIR)/frontend30.h
$(FRONTEND30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/frontend30.h
$(FRONTEND30_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/frontend30.h
$(OBJDIR)/platform/native_static.o: platform/include/ta_direct.hpp ../room/mesh_fastpath.hpp
