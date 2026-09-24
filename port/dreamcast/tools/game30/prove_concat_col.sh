#!/bin/bash
# prove_concat_col.sh OBJDIR GAME.elf : design-logic P3 proof. fpsym2 --strict between the build's own
# contract-off C_MTXConcat (OBJDIR/sdk/mtx.o, linked alone) and the _re4dc_sh4_MTXConcat linked into
# GAME.elf (GAME_CONCAT_COL=1), over every alias partition of (a, b, ab). Prints EQUIVALENT or fails.
set -euo pipefail
O=$1; E=$2; H=$(cd $(dirname $0) && pwd)
B=/opt/toolchains/dc/sh-elf/bin
W=$(mktemp -d)
$B/sh-elf-ld -EL -Ttext=0x8c010000 -e _C_MTXConcat --unresolved-symbols=ignore-all -o $W/ref.elf $O/sdk/mtx.o
python3 $H/fpsym2.py $W/ref.elf _C_MTXConcat $E _re4dc_sh4_MTXConcat --args p,p,p --strict -v
rm -rf $W
