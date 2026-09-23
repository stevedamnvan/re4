#!/bin/bash
# D367 disc: selected source mirror + fixtures overlay + native packages under
# /cd/dc/native/r100/. Inputs are hard-linked or copied, never modified.
# usage: [MIRROR=.. FIXTURES_SRC=.. KEYED=.. MESHDIR=.. TEXDIRS="d1 d2"] stage.sh <build-dir> <disc-dir>
# MIRROR, FIXTURES_SRC and KEYED are private (locally extracted game data); defaults are
# the original D367 workstation paths. TEXDIRS overlays *.re4tex files onto /cd/dc/tex/
# (e.g. the PS2 tree bark replacing its GC source key).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
build=${1:?usage: stage.sh <build-dir> <disc-dir>}
out=${2:?usage: stage.sh <build-dir> <disc-dir>}
base=${D367_BASE:-/root/probe/d367-native-static}
fixtures=$(mktemp -d "${TMPDIR:-/tmp}/re4dc-fixtures.XXXXXX")
trap 'rm -rf "$fixtures"' EXIT
export RE4DC_KOS_BASE=${RE4DC_KOS_BASE:-/root/work/kos-re4dc-d336}
set +u; source "$here/../../kos-env.sh"; set -u
rmdir "$fixtures"; cp -al "${FIXTURES_SRC:-/root/probe/d354v7-fixtures}" "$fixtures"
mkdir -p "$fixtures/native/r100"
for o in MAINSCENARIO FILE_00 FILE_01 FILE_02; do
  cp "${KEYED:-$base/keyed12}/$o.re4room" "$fixtures/native/r100/$o.re4room"
done
if [ -n "${MESHDIR:-}" ]; then cp "$MESHDIR"/*.re4mesh "$fixtures/native/r100/"; fi
for d in ${TEXDIRS:-}; do
  mkdir -p "$fixtures/tex"
  for f in "$d"/*.re4tex; do rm -f "$fixtures/tex/$(basename "$f")"; cp "$f" "$fixtures/tex/"; done
done
bash "$here/mkdisc-hardlink.sh" "$build/re4dc-game.elf" "${MIRROR:-/root/probe/d362-mirror}" "$out" "$fixtures"
bash "$here/syms.sh" "$build"
"$KOS_CC_BASE/bin/sh-elf-nm" -C "$build/re4dc-game.elf" > "$build/symbols-demangled.txt"
sha256sum "$out/disc.bin" | tee "$out/disc.sha256"
