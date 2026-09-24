#!/bin/bash
# prove_multvec_sched.sh OBJDIR GAME.elf : design-logic P3b proof. fpsym2 --strict between the build's own
# contract-off C_MTXMultVec (OBJDIR/sdk/mtxvec.o, linked alone) and the _re4dc_sh4_MTXMultVec linked into
# GAME.elf (GAME_MULTVEC_SCHED=1), over every alias partition of (m, src, dst). Prints EQUIVALENT or fails.
set -euo pipefail
O=$1; E=$2; H=$(cd $(dirname $0) && pwd)
B=/opt/toolchains/dc/sh-elf/bin
W=$(mktemp -d)
$B/sh-elf-ld -EL -Ttext=0x8c010000 -e _C_MTXMultVec --unresolved-symbols=ignore-all -o $W/ref.elf $O/sdk/mtxvec.o
python3 $H/fpsym2.py $W/ref.elf _C_MTXMultVec $E _re4dc_sh4_MTXMultVec --args p,p,p --strict -v
rm -rf $W
