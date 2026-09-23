#!/bin/bash
# D367 asset pipeline (docs/D367_ASSET_PIPELINE.md). Thin wrapper: pinned interpreter,
# deterministic environment. usage: assets.sh [cmd] <room|route|all> [options]; --help
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
export LC_ALL=C TZ=UTC PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export RE4DC_KOS_BASE=${RE4DC_KOS_BASE:-/root/work/kos-re4dc-d336}
exec python3 -B "$here/assets.py" "$@"
