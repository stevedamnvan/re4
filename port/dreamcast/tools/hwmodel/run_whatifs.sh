#!/bin/bash
# run_whatifs.sh - hwsim sensitivity band + optimisation what-ifs over one set of hwtrace traces.
#   run_whatifs.sh ELF TRACEDIR OUTDIR [jobs]
# e.g. run_whatifs.sh /mnt/d/Flycast-Evidence/re4-dreamcast/hwmodel-ld2/re4dc-game.elf \
#        /mnt/d/Flycast-Evidence/re4-dreamcast/hwmodel-ld2/trace results-ld2 12
# Writes OUTDIR/<job>.{pcs,lines,frames}.tsv + .sum.txt, OUTDIR/rep/ (hwreport with every what-if
# as a wi_<job> column) and prints ms/frame per job.
set -e
T=$(cd "$(dirname "$0")" && pwd)
E=${1:?elf}; TD=${2:?trace dir}; O=${3:?out dir}; J=${4:-12}
TR=$(ls "$TD"/trace-*.bin | tr '\n' ' ')
HWSIM=${HWSIM:-$T/hwsim}
TID="--pcs-tid1 ${HWM_TID1:-/root/probe/d367-agents/hwmodel/data/ld-pcs-func-tid1.csv} --pcs-tid12 ${HWM_TID12:-/root/probe/d367-agents/hwmodel/data/ld-pcs-func-tid12.csv}"
[ -x "$HWSIM" ] && [ "$HWSIM" -nt "$T/hwsim.c" ] || gcc -O2 -march=native -o "$HWSIM" "$T/hwsim.c" -lm
mkdir -p "$O"; cd "$O"
$HWSIM --elf $E --out base $TR > base.log 2>&1
python3 $T/hwreport.py --elf $E --sim base $TID --out rep-base > /dev/null
python3 $T/gen_whatif.py --elf $E --sim base --funcs rep-base/functions.tsv --out wi
cat > jobs.txt <<JOBS
low       --fill-hit 12 --fill-miss 20 --fill-ovh 0 --burst-tail 6 --wb-hit 8 --wb-miss 16 --sq-cost 10
high      --fill-hit 16 --fill-miss 26 --fill-ovh 10 --burst-tail 4 --wb-hit 10 --wb-miss 20 --sq-cost 24
nodma     --no-dma
perfic    --perfect-ic
perfdc    --perfect-dc
perfall   --perfect-ic --perfect-dc
icfunc    --icmap wi/icmap_func.txt
iclines   --icmap wi/icmap_lines.txt
ora8      --oc-kb 8
ora8best  --oc-kb 8 --pin wi/pin_best8k.txt
ora8xf    --oc-kb 8 --pin wi/pin_xform8k.txt
streampf  --streampf
fsrra     --fdiv wi/render_fdiv.txt --fdiv-lat 5 --fdiv-lock 0
nocopies  --skip wi/copies.txt
nosqcpy   --skip wi/sqcpy.txt
oix       --oix
wastream  --wa-stream
wanofill  --wa-nofill
nodep     --no-dep
streamwa  --streampf --wa-stream
JOBS
awk 'NF' jobs.txt | while read name args; do echo "$HWSIM --elf $E --out $name $args $TR > $name.log 2>&1"; done \
  | xargs -P $J -I{} bash -c "{}"
WI=$(awk 'NF{printf " --whatif %s=%s", $1, $1}' jobs.txt)
python3 $T/hwreport.py --elf $E --sim base $WI $TID --out rep > rep.txt
for f in *.sum.txt; do printf "%-10s %s\n" ${f%.sum.txt} "$(grep ms_per_frame $f)"; done
