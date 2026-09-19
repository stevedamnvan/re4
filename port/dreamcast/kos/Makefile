TARGET = re4dc-smoke.elf
OBJS = main.o

KOS_CPPFLAGS += -std=c++20 -Wall -Wextra -Werror -I../include
KOS_GCCVER_MIN = 12.0.0

include $(KOS_BASE)/Makefile.rules

ifeq ($(call KOS_GCCVER_MIN_CHECK,$(KOS_GCCVER_MIN)),1)

all: rm-elf $(TARGET)

clean: rm-elf
	-rm -f $(OBJS)

rm-elf:
	-rm -f $(TARGET)

$(TARGET): $(OBJS)
	kos-c++ -o $(TARGET) $(OBJS)

run: $(TARGET)
	$(KOS_LOADER) $(TARGET)

else
  all $(TARGET) clean rm-elf run:
	$(KOS_GCCVER_MIN_WARNING)
endif
