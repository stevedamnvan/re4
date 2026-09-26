#!/bin/bash
# prove_mtxinv_sched.sh OBJDIR GAME.elf [OLD.elf] : lane gskel GAME_MTXINV_SCHED proof (fpsym2, every alias
# partition of (src, inv), both det branches, stack balance and fr12-fr15 / r8-r14 restored on every path).
#   1. --strict against the _re4dc_sh4_MTXInverse of OLD.elf (a build without GAME_MTXINV_SCHED: the
#      RE4DC_FP_CONTRACT_OFF body in platform/mtx_sh4.S): the same instructions on the same operands.
#   2. commutative mode against the build's own contract-off C_MTXInverse (OBJDIR/sdk/mtx.o, linked alone),
#      the standard the old body meets (it commutes two fmul operand pairs relative to GCC's code).
# Prints EQUIVALENT per check or fails.
set -euo pipefail
O=$1; E=$2; OLD=${3:-}; H=$(cd $(dirname $0) && pwd)
B=/opt/toolchains/dc/sh-elf/bin
W=$(mktemp -d)
if [ -n "$OLD" ]; then
    python3 $H/fpsym2.py $OLD _re4dc_sh4_MTXInverse $E _re4dc_sh4_MTXInverse --args p,p --ret int --strict | tail -2
fi
$B/sh-elf-ld -EL -Ttext=0x8c010000 -e _C_MTXInverse --unresolved-symbols=ignore-all -o $W/ref.elf $O/sdk/mtx.o
python3 $H/fpsym2.py $W/ref.elf _C_MTXInverse $E _re4dc_sh4_MTXInverse --args p,p --ret int | tail -2
rm -rf $W
