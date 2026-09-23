#!/bin/bash
# Links re4dc-game.elf from the game, SDK and platform objects.
#
# 1. the PowerPC link-name aliases are generated from the objects
#    (tools/gen_aliases.py -> obj/aliases.ld, an assignment-only script the
#    linker reads as an input file);
# 2. a first link with every unresolved symbol reported produces the list of
#    what the platform layer still lacks (obj/missing.txt);
# 3. those become loud stubs (tools/gen_missing.py -> obj/missing.cpp) and the
#    final link produces the ELF.
#
#   [GAME_LDFLAGS=..] link.sh <target.elf> <opt-flags> <objects...>
# GAME_LDFLAGS (from the Makefile) goes to both links, e.g. --wrap options.
set -e
TARGET=$1; OPT=$2; shift 2
OBJS="$@"
mkdir -p obj
sh-elf-nm $OBJS 2>/dev/null | grep -E " [TDBWRV] " | awk '{print $3}' | sort -u > obj/defined.txt
sh-elf-c++filt < obj/defined.txt > obj/defined-dem.txt
paste obj/defined.txt obj/defined-dem.txt > obj/nm-pairs.txt
sh-elf-nm $OBJS 2>/dev/null | grep -E " U " | awk '{print $2}' | sort -u | comm -23 - obj/defined.txt > obj/undefined.txt
python3 tools/gen_aliases.py obj/undefined.txt obj/nm-pairs.txt obj/aliases.ld
# manual aliases (platform/aliases-manual.ld) come first so they win
cat platform/aliases-manual.ld obj/aliases.ld > obj/aliases-all.ld
# pass 1: what is still unresolved after the aliases and the libraries
if ! kos-c++ $OPT ${GAME_LDFLAGS:-} -Wl,--unresolved-symbols=ignore-all -o obj/pass1.elf $OBJS obj/aliases-all.ld > obj/pass1.log 2>&1; then
    cat obj/pass1.log; exit 1
fi
sh-elf-nm obj/pass1.elf | grep -E " [Uw] " | awk '{print $2}' | sort -u > obj/missing.txt
# Registered stage entry points must never become generated trap stubs.
if grep -Eq '^_st[0-9]+_[0-9]+_(prolog|epilog)$' obj/missing.txt; then
    echo "stage module entry points missing after partial link:" >&2
    grep -E '^_st[0-9]+_[0-9]+_(prolog|epilog)$' obj/missing.txt >&2
    exit 1
fi
python3 tools/gen_missing.py obj/missing.txt obj/missing.cpp
kos-c++ $KOS_CFLAGS $OPT -Iplatform/include -c obj/missing.cpp -o obj/missing.o
kos-c++ $OPT ${GAME_LDFLAGS:-} -o $TARGET $OBJS obj/missing.o obj/aliases-all.ld
sh-elf-size $TARGET
