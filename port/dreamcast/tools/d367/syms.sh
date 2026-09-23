#!/bin/bash
# Write <build>/syms.txt = guest RAM offsets of logbuf, log head, stage word and (when
# linked) the PC-sampler ring, as read by the Flycast harness.
set -euo pipefail
B=${1:?usage: syms.sh <build-dir>}
N=${KOS_CC_BASE:-/opt/toolchains/dc/sh-elf}/bin/sh-elf-nm
sym(){ local a; a=$($N "$B/re4dc-game.elf" | awk -v s="$1" '$3==s{print $1}'); if [ -n "$a" ]; then printf '0x%x' $(( 0x$a - 0x8c000000 )); fi; }
echo "$(sym _re4dc_logbuf) $(sym _re4dc_log_head) $(sym _re4dc_stage) $(sym _re4dc_pcs)" | sed 's/ *$//' > "$B/syms.txt"
cat "$B/syms.txt"
