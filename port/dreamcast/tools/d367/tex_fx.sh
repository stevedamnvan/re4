#!/bin/bash
# D367 effect texture packages for EFFECT_SPRITES=1 (effects30.mk): every TPL image in the
# effect-owning archives, packaged by the existing prepare_native_ui.py (convert_tpl
# build_package, source identity keys). Deterministic: pinned inputs, and the result is
# checked against the expected image count before it replaces the cache.
# usage: [RE4DATA=/root/re4data] tex_fx.sh <out-dir>   (no-op when <out-dir>/tex-fx.ok exists)
# The source tree is private (locally extracted game data). prepare_native_ui.py exits 2
# for its qualification gate on unrelated sub-files (core VIB/SAT, wep09 joint padding);
# those are the only accepted errors, and the images are still exported.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: tex_fx.sh <out-dir>}
src=${RE4DATA:-/root/re4data}
[ -f "$out/tex-fx.ok" ] && exit 0
deps=$(mktemp); tmp="$out.tmp.$$"
trap 'rm -rf "$deps" "$tmp"' EXIT
# Owners: core (0, the shot's smoke/flash), EM10 (0x10, blood), weapons 0x34.. (muzzle flash).
printf '%s\n' etc/core.das em/em10.drs em/wep00.drs em/wep01.drs em/wep02.drs em/wep03.drs \
  em/wep04.drs em/wep05.drs em/wep06.drs em/wep07.drs em/wep08.drs em/wep09.drs > "$deps"
rc=0; python3 "$here/../prepare_native_ui.py" "$src" "$deps" "$tmp" > "$tmp.log" 2>&1 || rc=$?
[ "$rc" = 0 ] || [ "$rc" = 2 ] || { cat "$tmp.log" >&2; rm -f "$tmp.log"; exit 1; }
rm -f "$tmp.log"
python3 - "$tmp" <<'PY'
import json, sys
r = json.load(open(sys.argv[1] + "/native-ui-report.json"))
allowed = ("no handler (tag VIB)", "invalid SAT polygon counts", "lies in the 0xCD padding")
bad = [e for e in r["errors"] if not any(a in json.dumps(e) for a in allowed)]
if bad or r["unique_images"] < 500:
    sys.exit("tex_fx: unexpected result: images=%d errors=%s" % (r["unique_images"], bad[:3]))
print("tex_fx: %d effect images" % r["unique_images"], file=sys.stderr)
PY
touch "$tmp/tex-fx.ok"
rm -rf "$out"; mv "$tmp" "$out"
