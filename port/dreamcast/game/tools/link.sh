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
# RE4DC_LINK_OVERLAY=.ovl_<mod> (subscreen.mk SUBSCREEN_OVL=1): that section is placed outside
# RAM (after .ocram, so _end and the arena do not move), kept whole (--gc-sections would drop it:
# the image no longer references it), and turned into <dir of target>/<mod>.ovl below.
OVL=${RE4DC_LINK_OVERLAY:-}
OVL_OUT=$(dirname "$TARGET")/sscrn.ovl
rm -f "$OVL_OUT"
OVL_A=0x8E000000; OVL_B=0x8E100000
ovl_script() {
    printf 'SECTIONS {\n  %s %s : { KEEP(*(%s)) }\n}\nINSERT AFTER .ocram;\n' "$OVL" "$2" "$OVL" > "$1"
}
OVL_LD=
if [ -n "$OVL" ]; then
    ovl_script obj/overlay-a.ld $OVL_A
    ovl_script obj/overlay-b.ld $OVL_B
    OVL_LD="-Wl,-T,obj/overlay-a.ld"
fi
# manual aliases (platform/aliases-manual.ld) come first so they win
cat platform/aliases-manual.ld obj/aliases.ld > obj/aliases-all.ld
# pass 1: what is still unresolved after the aliases and the libraries
if ! kos-c++ $OPT ${GAME_LDFLAGS:-} $OVL_LD -Wl,--unresolved-symbols=ignore-all -o obj/pass1.elf $OBJS obj/aliases-all.ld > obj/pass1.log 2>&1; then
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
kos-c++ $OPT ${GAME_LDFLAGS:-} $OVL_LD -o $TARGET $OBJS obj/missing.o obj/aliases-all.ld
if [ -n "$OVL" ]; then
    # Second link with the overlay 1 MiB higher: gen_overlay.py takes every overlay word that moved
    # by exactly that as a relocation, and fails on any other difference (a PC-relative reference
    # across the overlay boundary, or an image word that points into the overlay).
    kos-c++ $OPT ${GAME_LDFLAGS:-} -Wl,-T,obj/overlay-b.ld -o obj/overlay-b.elf $OBJS obj/missing.o obj/aliases-all.ld
    python3 tools/gen_overlay.py "$TARGET" obj/overlay-b.elf "$OVL" $OVL_A $OVL_B "$OVL_OUT"
    sh-elf-objcopy -R "$OVL" "$TARGET"
    rm -f obj/overlay-b.elf
fi
sh-elf-size $TARGET
