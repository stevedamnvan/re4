# D367 test warp rig (tools/d367/README.md "Warp rig"). Included at the end of the Makefile.
#   DBG_WARP=1   test builds only: /cd/dc/warp.txt (tools/d367/warp.py) skips the title and starts in
#                a room with Leon placed and synthesized scenario flags (dbgwarp_bridge.cpp). Not
#                STRICT against continued play; never on a user disc. Default 0: the hooks compile
#                out and the default image is byte-identical.
DBG_WARP ?= 0
.PHONY: dbgwarp-force
$(OBJDIR)/dbgwarp.h: dbgwarp-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_DBG_WARP %s\n' '$(DBG_WARP)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
DBGWARP_GAME = $(OBJDIR)/src/game/title.o $(OBJDIR)/src/game/sce_com.o $(OBJDIR)/ui_bridge.o
$(DBGWARP_GAME): $(OBJDIR)/dbgwarp.h
$(DBGWARP_GAME): GAME_CPPFLAGS += -include $(OBJDIR)/dbgwarp.h
$(OBJDIR)/platform/pad.o: $(OBJDIR)/dbgwarp.h
$(OBJDIR)/platform/pad.o: PLATFORM_CPPFLAGS += -include $(OBJDIR)/dbgwarp.h
ifeq ($(DBG_WARP),1)
PLATFORM_OBJS += $(OBJDIR)/dbgwarp_bridge.o
# Included after the link rule: name the object as its prerequisite here.
$(TARGET): $(OBJDIR)/dbgwarp_bridge.o
$(OBJDIR)/dbgwarp_bridge.o: dbgwarp_bridge.cpp $(OBJDIR)/dbgwarp.h
	@mkdir -p $(dir $@)
	kos-c++ $(KOS_CFLAGS) $(GAME_CPPFLAGS) -Iplatform/include -include $(OBJDIR)/dbgwarp.h -MMD -MP -c $< -o $@
-include $(OBJDIR)/dbgwarp_bridge.d
endif
