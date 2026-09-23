#!/bin/bash
# D367 recovered-game build: the D361/D362 ELF flag set plus the native static/mesh
# renderer. usage: [OWNERS=0x7F STATIC=1 MESH=1 EXTRA_MAKE="..."] build.sh <dest-dir>
# Candidate flag sets are listed in README.md (LD is the current best).
set -euo pipefail
REPO=${REPO:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel)}
cd "$REPO"
if pgrep -f "^make .*-C port/dreamcast/game" >/dev/null; then echo "another game build is running" >&2; exit 1; fi
export RE4DC_KOS_BASE=${RE4DC_KOS_BASE:-/root/work/kos-re4dc-d336}
source port/dreamcast/kos-env.sh
dest=${1:?usage: build.sh <dest-dir>}
mkdir -p "$dest"
make NATIVE_REUSE_AUDIT=0 NATIVE_RENDER_PROFILE=0 -C port/dreamcast/game -j${JOBS:-6} \
  CORE_RESIDENT_BYTES=1360608 OPTION_RESIDENT_BYTES=149920 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 \
  PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1 ENEMY_DEMAND=1 PVR_STREAM=1 MODEL_POSITION_CACHE=1 \
  EVENT_FILES=1 R100_DEFER_EVENTS=1 MODEL_ROOM_STRIPS=1 MODEL_DRAW_PLANS=0 D349_RENDERER_STACK=1 \
  NATIVE_STATIC=${STATIC:-1} NATIVE_STATIC_OWNERS=${OWNERS:-1} NATIVE_MESH=${MESH:-0} NATIVE_STATIC_PROBE_SKIP=${PROBE_SKIP:-0} \
  ${EXTRA_MAKE:-} >"$dest/build.log" 2>&1 || { tail -40 "$dest/build.log"; exit 1; }
cp port/dreamcast/game/re4dc-game.elf "$dest/re4dc-game.elf"
"$KOS_CC_BASE/bin/sh-elf-size" "$dest/re4dc-game.elf" | tee "$dest/size.txt"
sha256sum "$dest/re4dc-game.elf" | tee "$dest/elf.sha256"
git diff --binary > "$dest/tracked.patch"
git rev-parse HEAD > "$dest/head.txt"
echo "${EXTRA_MAKE:-}" > "$dest/candidate.txt"
grep -c "warning" "$dest/build.log" || true
