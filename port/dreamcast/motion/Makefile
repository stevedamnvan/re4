.DEFAULT_GOAL := all

include Makefile.common

BUILD := ../build/motion-sh4
TARGET := $(BUILD)/re4dc-motion-smoke.elf
REAL_TARGET := $(BUILD)/re4dc-real-motion.elf
CXXFLAGS := -O2 -g -std=gnu++14 -fno-strict-aliasing -fno-fast-math \
            -ffunction-sections -fdata-sections -Wno-register \
            -Wno-unused-variable -Wno-unused-but-set-variable \
            -Wno-int-to-pointer-cast -Wno-unused-function -Wall -Wextra
GAME_OBJS := $(addprefix $(BUILD)/,$(addsuffix .o,$(GAME_NAMES)))
FDLIBM_OBJS := $(addprefix $(BUILD)/fdlibm_,$(addsuffix .o,$(FDLIBM_NAMES)))
LOCAL_OBJS := $(BUILD)/kos_main.o $(BUILD)/motion_checks.o
REAL_LOCAL_OBJS := $(BUILD)/real_kos_main.o $(BUILD)/motion_checks.o \
                   $(BUILD)/real_motion_checks.o

.PHONY: all real clean

all: $(TARGET)

$(BUILD):
	mkdir -p $@

$(BUILD)/kos_main.o: kos_main.cpp motion_checks.hpp | $(BUILD)
	kos-c++ $(CXXFLAGS) -I$(STUB_DIR) -c $< -o $@

$(BUILD)/motion_checks.o: motion_checks.cpp motion_checks.hpp | $(BUILD)
	kos-c++ $(CXXFLAGS) -I$(STUB_DIR) -c $< -o $@

$(BUILD)/real_kos_main.o: real_kos_main.cpp real_motion_checks.hpp | $(BUILD)
	kos-c++ $(CXXFLAGS) -I$(STUB_DIR) -c $< -o $@

$(BUILD)/real_motion_checks.o: real_motion_checks.cpp real_motion_checks.hpp $(REAL_FIXTURE) | $(BUILD)
	kos-c++ $(CXXFLAGS) -I$(STUB_DIR) -I$(REAL_FIXTURE_DIR) -c $< -o $@

$(BUILD)/%.o: $(HOST_BUILD)/%.cpp | $(BUILD)
	kos-c++ $(CXXFLAGS) -I$(STUB_DIR) -c $< -o $@

$(BUILD)/fdlibm_%.o: $(ROOT)/src/lib/%.cpp | $(BUILD)
	kos-c++ $(CXXFLAGS) -I$(ROOT)/include $(FDLIBM_DEFS) -c $< -o $@

$(TARGET): $(LOCAL_OBJS) $(GAME_OBJS) $(FDLIBM_OBJS)
	kos-c++ -o $@ $^

$(REAL_TARGET): $(REAL_LOCAL_OBJS) $(GAME_OBJS) $(FDLIBM_OBJS)
	kos-c++ -o $@ $^

real: $(REAL_TARGET)

clean:
	rm -rf $(BUILD)
