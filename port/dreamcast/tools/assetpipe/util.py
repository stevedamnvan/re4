"""Deterministic helpers: hashing, canonical JSON, subprocess environment."""
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _norm(obj):
    """Canonical form: floats printed with 9 significant digits (no repr noise),
    tuples as lists, Paths as strings, dict keys as strings (sorted on dump)."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError("non-finite float in canonical data")
        r = float("%.9g" % obj)
        return int(r) if r == int(r) and abs(r) < 2 ** 53 else r
    if isinstance(obj, dict):
        return {str(k): _norm(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_norm(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def canon(obj):
    """Canonical JSON bytes: sorted keys, no whitespace, normalised floats."""
    return json.dumps(_norm(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def canon_hash(obj):
    return sha256_bytes(canon(obj))


def dumps(obj):
    """Readable, still deterministic JSON (sorted keys, normalised floats)."""
    return json.dumps(_norm(obj), sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def write_json(path, obj):
    Path(path).write_text(dumps(obj))


def det_env(extra=None):
    """Environment for every generator subprocess: no locale, time zone or hash
    randomisation differences between runs or machines."""
    keep = ("PATH", "HOME", "USER", "RE4DC_KOS_BASE", "KOS_BASE", "TMPDIR")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.update(LC_ALL="C", LANG="C", TZ="UTC", PYTHONHASHSEED="0", SOURCE_DATE_EPOCH="0",
               PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1")
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


class StepError(RuntimeError):
    pass


def run(cmd, cwd=None, log=None, env=None, timeout=None):
    """Run a generator; stdout+stderr go to `log` (a Path) when given. Raises
    StepError with the log tail on failure."""
    cmd = [str(c) for c in cmd]
    with (open(log, "w") if log else open(os.devnull, "w")) as out:
        out.write("$ " + " ".join(cmd) + "\n")
        out.flush()
        p = subprocess.run(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, env=env or det_env(),
                           timeout=timeout)
    if p.returncode:
        tail = Path(log).read_text(errors="replace").splitlines()[-25:] if log else []
        raise StepError("%s failed (%d)\n%s" % (Path(cmd[0]).name if len(cmd) == 1 else " ".join(cmd[:3]),
                                                p.returncode, "\n".join(tail)))


def seed_of(text):
    """Fixed per-asset seed for anything stochastic (never time based)."""
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def parse_ranges(spec):
    """'0-10,13,15-16' -> [0..10, 13, 15, 16]."""
    out = []
    for r in str(spec).split(","):
        r = r.strip()
        if not r:
            continue
        lo, _, hi = r.partition("-")
        out.extend(range(int(lo, 0), int(hi or lo, 0) + 1))
    return out


def ranges(values):
    """[0,1,2,5] -> '0-2,5' (sorted, stable)."""
    v = sorted(set(values))
    out, i = [], 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[j + 1] == v[j] + 1:
            j += 1
        out.append(str(v[i]) if i == j else "%d-%d" % (v[i], v[j]))
        i = j + 1
    return ",".join(out)
