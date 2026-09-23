#!/bin/bash
# D367 disc: selected source mirror + fixtures overlay + native packages under
# /cd/dc/native/<room>/. Inputs are hard-linked or copied, never modified.
# usage: [MIRROR=.. FIXTURES_SRC=.. KEYED=.. MESHDIR=.. TEXDIRS="d1 d2"
#         MESHROOMS="r101=dir .." ROOMFILES="st1/r101.dar=file .."] stage.sh <build-dir> <disc-dir>
# MIRROR, FIXTURES_SRC and KEYED are private (locally extracted game data); defaults are
# the original D367 workstation paths. TEXDIRS overlays *.re4tex files onto /cd/dc/tex/
# (e.g. the PS2 tree bark replacing its GC source key); later TEXDIRS win. MESHDIR holds the r100
# packages; MESHROOMS adds other rooms' *.re4mesh (convert_room_bins.py --smd) under
# /cd/dc/native/<room>/. ROOMFILES replaces mirror files (a released room archive from
# room_smd.py release: st1/<room>.dar, and its .arc) in a hard-linked copy of the mirror;
# a released archive is only valid with its packages and NATIVE_MESH=1.
# Default recipe (README.md): TEXDIRS="<tex-vq3 VQ overlay> <PS2 bark>". The inputs are
# recorded in <disc-dir>/stage-inputs.txt.
# GDI=1 also writes the GDEMU image (mkgdi.sh) from the same tree to GDI_OUT
# (default <disc-dir>/gdi; put it on /mnt/d when WSL's host drive is short).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
build=${1:?usage: stage.sh <build-dir> <disc-dir>}
out=${2:?usage: stage.sh <build-dir> <disc-dir>}
base=${D367_BASE:-/root/probe/d367-native-static}
mirror=${MIRROR:-/root/probe/d362-mirror}
fixtures=$(mktemp -d "${TMPDIR:-/tmp}/re4dc-fixtures.XXXXXX")
overlay=
trap 'rm -rf "$fixtures" ${overlay:+"$overlay"}' EXIT
export RE4DC_KOS_BASE=${RE4DC_KOS_BASE:-/root/work/kos-re4dc-d336}
set +u; source "$here/../../kos-env.sh"; set -u
rmdir "$fixtures"; cp -al "${FIXTURES_SRC:-/root/probe/d354v7-fixtures}" "$fixtures"
mkdir -p "$fixtures/native/r100"
for o in MAINSCENARIO FILE_00 FILE_01 FILE_02; do
  cp "${KEYED:-$base/keyed12}/$o.re4room" "$fixtures/native/r100/$o.re4room"
done
if [ -n "${MESHDIR:-}" ]; then cp "$MESHDIR"/*.re4mesh "$fixtures/native/r100/"; fi
for spec in ${MESHROOMS:-}; do
  room=${spec%%=*}; dir=${spec#*=}
  case $room in r[0-9a-f][0-9a-f][0-9a-f]) ;; *) echo "stage: bad MESHROOMS room $room" >&2; exit 1;; esac
  mkdir -p "$fixtures/native/$room"
  rm -f "$fixtures/native/$room"/*.re4mesh
  cp "$dir"/*.re4mesh "$fixtures/native/$room/"
done
# TA_VERTBUF_KB above 1024 shrinks the PVR texture pool (2.6 MB at 2048); the title/menu
# images then fit only as VQ (README.md: tex-vq3). Flycast without it: 1,884 upload failures.
ta_kb=$(grep -o 'TA_VERTBUF_KB=[0-9]*' "$build/candidate.txt" 2>/dev/null | head -1 | cut -d= -f2 || true)
vq_overlay=
for d in ${TEXDIRS:-}; do if [ -e "$d/vq-native-ui-report.json" ]; then vq_overlay=$d; fi; done
if [ "${ta_kb:-1024}" -gt 1024 ] && [ -z "$vq_overlay" ]; then
  echo "stage.sh: WARNING: TA_VERTBUF_KB=$ta_kb build staged without a VQ texture overlay in TEXDIRS (README.md: tex-vq3)" >&2
fi
for d in ${TEXDIRS:-}; do
  mkdir -p "$fixtures/tex"
  for f in "$d"/*.re4tex; do rm -f "$fixtures/tex/$(basename "$f")"; cp "$f" "$fixtures/tex/"; done
done
# TEX_RESIDENT builds skip the runtime payload CRC: verify every staged texture package here
# (header payload_crc32 = CRC-32 of the bytes after the header). A mismatch stops staging.
if [ -d "$fixtures/tex" ]; then
  python3 - "$fixtures/tex" <<'PY'
import os, struct, sys, zlib
d = sys.argv[1]; bad = []; n = 0
for f in sorted(os.listdir(d)):
    if not f.endswith(".re4tex"): continue
    b = open(os.path.join(d, f), "rb").read(); n += 1
    size, crc = struct.unpack_from("<I", b, 12)[0], struct.unpack_from("<I", b, 36)[0]
    if len(b) < 48 or zlib.crc32(b[size:]) != crc: bad.append(f)
print("stage: %d texture packages, payload CRC %s" % (n, "ok" if not bad else "MISMATCH: " + " ".join(bad[:8])), file=sys.stderr)
sys.exit(1 if bad else 0)
PY
fi
# TEX_RESIDENT builds open /cd/dc/tex/<first hex digit>/<crc>-<fnv>.re4tex: the flat directory
# (~550 packages, 17+ sectors) overflowed the iso9660 16-sector inode cache, so every open
# re-read the directory from the disc (~0.2 s per first-sight texture in Flycast).
if grep -q 'TEX_RESIDENT=1' "$build/candidate.txt" 2>/dev/null && [ -d "$fixtures/tex" ]; then
  for f in "$fixtures"/tex/*.re4tex; do b=$(basename "$f"); mkdir -p "$fixtures/tex/${b:0:1}"; mv "$f" "$fixtures/tex/${b:0:1}/"; done
  echo "stage: TEX_RESIDENT build: texture packages fanned out into tex/0..f" >&2
fi
if [ -n "${ROOMFILES:-}" ]; then
  overlay=$(mktemp -d "${TMPDIR:-/tmp}/re4dc-mirror.XXXXXX")
  cp -al "$mirror"/. "$overlay/"
  for spec in $ROOMFILES; do
    rel=${spec%%=*}; src=${spec#*=}
    test -e "$overlay/$rel" || { echo "stage: $rel not in the mirror" >&2; exit 1; }
    rm -f "$overlay/$rel"; cp "$src" "$overlay/$rel"
  done
  mirror=$overlay
fi
bash "$here/mkdisc-hardlink.sh" "$build/re4dc-game.elf" "$mirror" "$out" "$fixtures"
{
  echo "build=$build candidate=$(cat "$build/candidate.txt" 2>/dev/null || echo '?')"
  echo "MIRROR=${MIRROR:-/root/probe/d362-mirror} ROOMFILES=${ROOMFILES:-} FIXTURES_SRC=${FIXTURES_SRC:-/root/probe/d354v7-fixtures} KEYED=${KEYED:-$base/keyed12} MESHDIR=${MESHDIR:-} MESHROOMS=${MESHROOMS:-}"
  for d in ${TEXDIRS:-}; do
    echo "TEXDIR $d re4tex=$(ls "$d"/*.re4tex | wc -l)$([ "$d" = "$vq_overlay" ] && echo " vq-report-sha256=$(sha256sum < "$d/vq-native-ui-report.json" | cut -c1-16)")"
  done
} > "$out/stage-inputs.txt"
if [ -n "${GDI:-}" ]; then
  gdi=${GDI_OUT:-$out/gdi}
  KOS_TOOLS_BASE=${KOS_TOOLS_BASE:-$RE4DC_KOS_BASE} \
    bash "$here/mkgdi.sh" "$build/re4dc-game.elf" "$mirror" "$gdi" "$fixtures"
  (cd "$gdi" && sha256sum disc.gdi IP.BIN track0[123].*) | tee "$gdi/gdi.sha256"
fi
bash "$here/syms.sh" "$build"
"$KOS_CC_BASE/bin/sh-elf-nm" -C "$build/re4dc-game.elf" > "$build/symbols-demangled.txt"
sha256sum "$out/disc.bin" | tee "$out/disc.sha256"
