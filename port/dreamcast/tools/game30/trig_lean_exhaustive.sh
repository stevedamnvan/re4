#!/bin/bash
# usage: trig_lean_exhaustive.sh <tree> [opt]   exhaustive host check of the GAME_TRIG_LEAN sinf / cosf /
# re4dc_sincosf (game30_trig.c) against the game's recovered fdlibm sinf/cosf (src/lib/fdlibm), every 2^32
# input; then the negative control (must report exactly 1 mismatch).
set -euo pipefail
T=${1:?tree}; OPT=${2:--O2}
W=$(mktemp -d); trap 'rm -rf $W' EXIT
F=$T/src/lib/fdlibm
CF="$OPT -ffp-contract=off -fno-fast-math -msse2 -mfpmath=sse -w -I$T/include -I$F"
REN="-Dsinf=ref_sinf -Dcosf=ref_cosf -D__kernel_sinf=ref_ksinf -D__kernel_cosf=ref_kcosf -D__ieee754_rem_pio2f=ref_rem_pio2f -D__kernel_rem_pio2f=ref_krem_pio2f"
for u in sf_sin sf_cos kf_sin kf_cos ef_rem_pio2 kf_rem_pio2; do gcc $CF $REN -c $F/$u.c -o $W/$u.o; done
gcc $CF -DRE4DC_SINCOS=1 -DRE4DC_TRIG_LEAN=1 -Dsinf=new_sinf -Dcosf=new_cosf -D__ieee754_rem_pio2f=ref_rem_pio2f \
    -D__kernel_rem_pio2f=ref_krem_pio2f -c $T/port/dreamcast/game/game30_trig.c -o $W/new.o
gcc -O2 -msse2 -c $(dirname $0)/trig_lean_exhaustive.c -o $W/main.o
gcc $W/*.o -o $W/tl -lpthread -lm
time $W/tl
TRIG_NEG=1 $W/tl | head -1
