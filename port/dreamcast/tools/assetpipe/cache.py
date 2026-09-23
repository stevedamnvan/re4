"""Content-addressed step cache.

A step's key is sha256(canonical JSON of {api, step name, params, input content
hashes, tool fingerprints}). Paths and mtimes never enter a key. Outputs go to
objects/<kk>/<key>/out/ (built in <key>.tmp/ and renamed on success), with
step.json (inputs, params, output hashes, info) and log.txt beside them.

Text outputs (.json .txt .csv .md .html) have the build directory and the
private root replaced by "$WORK" / "$ROOT" before hashing, so the same step
built in another cache (--verify) hashes the same.
"""
import json
import os
import shutil
import threading
import time
from pathlib import Path

from . import API
from .util import canon_hash, dumps, sha256_file, canon

TEXT_SUFFIXES = {".json", ".txt", ".csv", ".md", ".html", ".log", ".toml"}


class Obj:
    def __init__(self, key, root, outputs, info, hit):
        self.key, self.root, self.outputs, self.info, self.hit = key, root, outputs, info, hit

    @property
    def out(self):
        return self.root / "out"

    def path(self, rel):
        return self.out / rel

    def __repr__(self):
        return "Obj(%s, %d files%s)" % (self.key[:12], len(self.outputs), ", hit" if self.hit else "")


def fingerprint(files=(), versions=None):
    """Tool fingerprint: sha256 of each script/binary file plus version strings."""
    fp = {Path(f).name: sha256_file(f) for f in sorted(set(map(str, files)))}
    if versions:
        fp.update({k: v for k, v in sorted(versions.items())})
    return fp


class Cache:
    def __init__(self, root, verify=False, log=print):
        self.root = Path(root)
        self.objects = self.root / "cache" / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.verify, self.log = verify, log
        self.canon_root = self.root      # replaced by "$ROOT" in text outputs (kept for --verify builds)
        self.mismatches, self.built, self.hits = [], [], []
        self._memo_path = self.root / "cache" / "hashmemo.json"
        self._lock = threading.Lock()
        try:
            self._memo = json.loads(self._memo_path.read_text())
        except (OSError, ValueError):
            self._memo = {}
        self._memo_dirty = False

    # ---- input hashing (content only; the memo is a speed-up keyed by size+mtime)
    def file_hash(self, p):
        p = Path(p)
        st = p.stat()
        k = str(p.resolve())
        with self._lock:
            m = self._memo.get(k)
            # trusted only if the file was already older than 2 s when it was hashed
            # (git's "racy" rule: mtime granularity can hide a same-size rewrite)
            if m and len(m) == 4 and m[0] == st.st_size and m[1] == st.st_mtime_ns and m[1] < m[3] - 2_000_000_000:
                return m[2]
        h = sha256_file(p)
        with self._lock:
            self._memo[k] = [st.st_size, st.st_mtime_ns, h, time.time_ns()]
            self._memo_dirty = True
        return h

    def input_hash(self, p):
        p = Path(p)
        if p.is_dir():
            items = sorted((str(f.relative_to(p)), self.file_hash(f)) for f in p.rglob("*") if f.is_file()
                           and "__pycache__" not in f.parts)
            return "dir:" + canon_hash(items)
        return self.file_hash(p)

    def save_memo(self):
        if self._memo_dirty:
            tmp = self._memo_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._memo, sort_keys=True))
            os.replace(tmp, self._memo_path)
            self._memo_dirty = False

    # ---- steps
    def key(self, name, params, inputs, tools):
        ih = {}
        for k, v in sorted(inputs.items()):
            if isinstance(v, (list, tuple)):
                ih[k] = [self.input_hash(x) for x in v]
            elif isinstance(v, str) and v.startswith("sha256:"):
                ih[k] = v[7:]                      # an already-hashed input (object key or content hash)
            elif isinstance(v, Obj):
                ih[k] = "obj:" + v.key
            else:
                ih[k] = self.input_hash(v)
        return canon_hash(dict(api=API, step=name, params=params, inputs=ih, tools=tools)), ih

    def _hash_outputs(self, out, work_names):
        res = {}
        for f in sorted(out.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix in TEXT_SUFFIXES:
                t = f.read_text(errors="surrogateescape")
                u = t
                for src, dst in work_names:
                    u = u.replace(src, dst)
                if u != t:
                    f.write_text(u, errors="surrogateescape")
            res[str(f.relative_to(out))] = sha256_file(f)
        return res

    def step(self, name, params, inputs, tools, fn, label=None):
        """fn(out_dir, work_dir) -> info dict. Returns an Obj."""
        key, ih = self.key(name, params, inputs, tools)
        final = self.objects / key[:2] / key
        label = label or name
        if (final / "step.json").exists():
            meta = json.loads((final / "step.json").read_text())
            obj = Obj(key, final, meta["outputs"], meta.get("info", {}), True)
            self.hits.append((label, key))
            if self.verify:
                self._verify(name, params, inputs, tools, fn, label, obj)
            return obj
        # one builder per key across processes: the others wait, then take the hit
        import fcntl
        final.parent.mkdir(parents=True, exist_ok=True)
        with open(final.parent / (key + ".lock"), "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try:
                if (final / "step.json").exists():
                    meta = json.loads((final / "step.json").read_text())
                    self.hits.append((label, key))
                    return Obj(key, final, meta["outputs"], meta.get("info", {}), True)
                obj = self._build(name, params, ih, tools, fn, label, final, key)
            finally:
                fcntl.flock(lk, fcntl.LOCK_UN)
        self.built.append((label, key))
        return obj

    def _build(self, name, params, ih, tools, fn, label, final, key):
        tmp = final.parent / (key + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        (tmp / "out").mkdir(parents=True)
        (tmp / "work").mkdir()
        t0 = time.time()
        self.log("  build %-28s %s" % (label, key[:12]))
        try:
            info = fn(tmp / "out", tmp / "work") or {}
        except Exception:
            self.log("  FAILED %s (work kept in %s)" % (label, tmp))
            raise
        outputs = self._hash_outputs(tmp / "out", [(str(tmp / "out"), "$OUT"), (str(tmp / "work"), "$WORK"),
                                                    (str(tmp), "$STEP"), (str(self.canon_root), "$ROOT")])
        if (tmp / "work" / "log.txt").exists():
            shutil.move(str(tmp / "work" / "log.txt"), str(tmp / "log.txt"))
        shutil.rmtree(tmp / "work")
        meta = dict(api=API, step=name, key=key, params=params, inputs=ih, tools=tools, outputs=outputs,
                    info=info)
        (tmp / "step.json").write_text(dumps(meta))
        (tmp / "seconds.txt").write_text("%.1f\n" % (time.time() - t0))   # not hashed, not in step.json
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            shutil.rmtree(tmp)
        else:
            os.replace(tmp, final)
        return Obj(key, final, outputs, info, False)

    def _verify(self, name, params, inputs, tools, fn, label, obj):
        # per process: two --verify runs at once must not rebuild into the same scratch dir
        scratch = self.root / "cache" / "verify" / ("p%d" % os.getpid())
        tmp_cache = Cache(scratch, verify=False, log=lambda *a: None)
        tmp_cache._memo = self._memo
        tmp_cache.canon_root = self.canon_root
        final = tmp_cache.objects / obj.key[:2] / obj.key
        if final.exists():
            shutil.rmtree(final)
        _, ih = self.key(name, params, inputs, tools)
        again = tmp_cache._build(name, params, ih, tools, fn, label, final, obj.key)
        if again.outputs != obj.outputs:
            diff = sorted(k for k in set(again.outputs) | set(obj.outputs)
                          if again.outputs.get(k) != obj.outputs.get(k))
            self.mismatches.append((label, obj.key, diff))
            self.log("  VERIFY MISMATCH %s: %s" % (label, ", ".join(diff[:6])))
        else:
            self.log("  verify ok %s" % label)
            shutil.rmtree(final)


def outputs_hash(outputs):
    return canon_hash(sorted(outputs.items()))


def link_tree(obj_or_dir, dest, only=None, rename=None):
    """Hard-link (or copy across devices) cached outputs into a staging view."""
    src = obj_or_dir.out if isinstance(obj_or_dir, Obj) else Path(obj_or_dir)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    done = []
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(src))
        if only and not only(rel):
            continue
        name = rename(rel) if rename else rel
        t = dest / name
        t.parent.mkdir(parents=True, exist_ok=True)
        if t.exists():
            t.unlink()
        try:
            os.link(f, t)
        except OSError:
            shutil.copy2(f, t)
        done.append(name)
    return done


__all__ = ["Cache", "Obj", "fingerprint", "link_tree", "outputs_hash", "canon"]
