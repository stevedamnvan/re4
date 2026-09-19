#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PORT_DIR}/../.." && pwd)"

# shellcheck disable=SC1091
. "${PORT_DIR}/toolchain.lock"

WORK_ROOT="${RE4DC_TOOLCHAIN_ROOT:-/root/work}"
KOS_DIR="${RE4DC_KOS_BASE:-${WORK_ROOT}/kos}"
PORTS_DIR="${RE4DC_KOS_PORTS:-${WORK_ROOT}/kos-ports}"
JOBS="${RE4DC_BUILD_JOBS:-8}"
BUILD=0

if [[ "${1:-}" == "--build" ]]; then
    BUILD=1
elif [[ $# -ne 0 ]]; then
    echo "usage: $0 [--build]" >&2
    exit 2
fi

ensure_repo() {
    local url="$1" directory="$2" commit="$3"
    if [[ ! -d "${directory}/.git" ]]; then
        git clone --filter=blob:none "${url}" "${directory}"
    fi
    if [[ "$(git -C "${directory}" rev-parse HEAD)" != "${commit}" ]]; then
        git -C "${directory}" fetch origin "${commit}"
        git -C "${directory}" checkout --detach "${commit}"
    fi
    test "$(git -C "${directory}" rev-parse HEAD)" = "${commit}"
}

git -C "${REPO_ROOT}" merge-base --is-ancestor "${RE4_SOURCE_SHA}" HEAD || {
    echo "locked RE4 source is not an ancestor of this port branch" >&2
    exit 1
}

mkdir -p "${WORK_ROOT}"
ensure_repo https://github.com/KallistiOS/KallistiOS.git "${KOS_DIR}" "${KOS_SHA}"
ensure_repo https://github.com/KallistiOS/kos-ports.git "${PORTS_DIR}" "${KOS_PORTS_SHA}"

printf 'KOS=%s\nKOS_PORTS=%s\n' \
    "$(git -C "${KOS_DIR}" rev-parse HEAD)" \
    "$(git -C "${PORTS_DIR}" rev-parse HEAD)"

if [[ "${BUILD}" -eq 0 ]]; then
    exit 0
fi

for command in make gcc g++ bison flex makeinfo python3; do
    command -v "${command}" >/dev/null || {
        echo "missing toolchain prerequisite: ${command}" >&2
        exit 1
    }
done

cp --update=none "${KOS_DIR}/utils/kos-chain/Makefile.dreamcast.cfg" \
    "${KOS_DIR}/utils/kos-chain/Makefile.cfg"
make -C "${KOS_DIR}/utils/kos-chain" -j"${JOBS}"

export RE4DC_KOS_BASE="${KOS_DIR}"
export RE4DC_KOS_PORTS="${PORTS_DIR}"
# shellcheck disable=SC1091
. "${PORT_DIR}/kos-env.sh"
make -C "${KOS_DIR}" -j"${JOBS}"
make -C "${PORT_DIR}/kos"
