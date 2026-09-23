#!/bin/bash
# D367 disc: selected source mirror + fixtures overlay + native packages under
# /cd/dc/native/<room>/. Inputs are hard-linked or copied, never modified.
# usage: [MIRROR=.. FIXTURES_SRC=.. KEYED=.. MESHDIR=.. TEXDIRS="d1 d2"
#         MESHROOMS="r101=dir .." ROOMFILES="st1/r101.dar=file .."] stage.sh <build-dir> <disc-dir>
# MIRROR, FIXTURES_SRC and KEYED are private (locally extracted game data); defaults are
# the original D367 workstation paths. TEXDIRS overlays *.re4tex files onto /cd/dc/tex/
# (e.g. the PS2 tree bark replacing its GC source key). MESHDIR holds the r100
# packages; MESHROOMS adds other rooms' *.re4mesh (convert_room_bins.py --smd) under
# /cd/dc/native/<room>/. ROOMFILES replaces mirror files (a released room archive from
# room_smd.py release: st1/<room>.dar, and its .arc) in a hard-linked copy of the mirror;
# a released archive is only valid with its packages and NATIVE_MESH=1.
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
for d in ${TEXDIRS:-}; do
  mkdir -p "$fixtures/tex"
  for f in "$d"/*.re4tex; do rm -f "$fixtures/tex/$(basename "$f")"; cp "$f" "$fixtures/tex/"; done
done
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
if [ -n "${GDI:-}" ]; then
  gdi=${GDI_OUT:-$out/gdi}
  KOS_TOOLS_BASE=${KOS_TOOLS_BASE:-$RE4DC_KOS_BASE} \
    bash "$here/mkgdi.sh" "$build/re4dc-game.elf" "$mirror" "$gdi" "$fixtures"
  (cd "$gdi" && sha256sum disc.gdi IP.BIN track0[123].*) | tee "$gdi/gdi.sha256"
fi
bash "$here/syms.sh" "$build"
"$KOS_CC_BASE/bin/sh-elf-nm" -C "$build/re4dc-game.elf" > "$build/symbols-demangled.txt"
sha256sum "$out/disc.bin" | tee "$out/disc.sha256"
