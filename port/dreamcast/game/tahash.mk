# D367 TA_HASH (test builds only; default 0 compiles it out: identical image). TA_HASH=1 folds every
# 32-byte TA store-queue burst of the game frame (stream packets, direct headers, re4dc_ta_put /
# re4dc_ta_vertex bursts) into an FNV-1a hash per display list and logs one line per scene:
#   ta_hash: frame=<native frame> present=<0|1> op=<hash>/<words> tr=.. pt=.. mod=<op mod>,<tr mod>
# Two builds that must submit the same geometry compare these lines frame by frame.
TA_HASH ?= 0
.PHONY: tahash-force
$(OBJDIR)/tahash.h: tahash-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_TA_HASH %s\n' '$(TA_HASH)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
TAHASH_PLATFORM = $(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/native_static.o $(OBJDIR)/platform/native_actor_fast.o
$(TAHASH_PLATFORM): $(OBJDIR)/tahash.h
$(TAHASH_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/tahash.h
