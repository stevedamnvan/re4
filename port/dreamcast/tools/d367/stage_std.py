#!/usr/bin/env python3
"""Stage the Standard asset sets of QUALITY=1 builds (docs/D367_ASSET_PIPELINE.md s16).

  stage_std.py <fixtures> [--tex-resident] <room>=<out/standard/<room>> ...

Called by stage.sh after the Original set is staged in <fixtures> (published under /cd/dc/).
For each room: checks <dir>/low/index.txt against its files and against the staged Original
packages (the `orig` records: the Standard set must have been built against exactly those),
then copies <dir>/low/ to <fixtures>/native/<room>/low/ and <dir>/texlow/*.re4tex to
<fixtures>/texlow/ (fanned out into texlow/<first hex digit>/ with --tex-resident, as tex/).
Prints one size report line per room on stderr and one stage-inputs line per room on stdout.
Any mismatch stops staging (exit 1). Inputs are copied, never modified.
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from assetpipe import stdindex  # noqa: E402


def sha(path, n=16):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:n]


def staged_tex(fixtures, key):
    t = fixtures / "tex"
    return (t / (key + ".re4tex")).exists() or (t / key[0] / (key + ".re4tex")).exists()


def stage_room(fixtures, room, src, tex_resident):
    low, texlow = src / "low", src / "texlow"
    index = low / "index.txt"
    if not index.is_file():
        raise SystemExit("stage_std: %s: no %s (run tools/d367/assets.sh build %s --mode standard)" % (room, index, room))
    ix = stdindex.parse(index.read_text())
    if ix["room"] != room:
        raise SystemExit("stage_std: %s: index is for %s" % (room, ix["room"]))
    native = fixtures / "native" / room
    errors = []
    for owner, size, h in ix["orig"]:
        f = native / (owner + ".re4mesh")
        if not f.is_file():
            errors.append("Original %s is not staged" % f.name)
        elif f.stat().st_size != int(size) or sha(f) != h:
            errors.append("staged Original %s is not the one the Standard set was built against" % f.name)
    listed = {"index.txt", "plan.json"}
    for owner, size, h in ix["mesh"]:
        f = low / (owner + ".re4mesh")
        listed.add(f.name)
        if not f.is_file() or f.stat().st_size != int(size) or sha(f) != h:
            errors.append("low/%s does not match its mesh record" % f.name)
    extra = sorted(p.name for p in low.iterdir() if p.name not in listed)
    if extra:
        errors.append("unlisted files in low/: %s" % " ".join(extra))
    keys = []
    for key, w, hgt, vram, size in ix["tex"]:
        f = texlow / (key + ".re4tex")
        keys.append(key)
        if not f.is_file() or f.stat().st_size != int(size):
            errors.append("texlow/%s.re4tex does not match its tex record" % key)
        if staged_tex(fixtures, key):
            errors.append("%s is both an Original (tex/) and a Standard (texlow/) key" % key)
    extra = sorted(p.name for p in texlow.iterdir() if p.stem not in keys) if texlow.is_dir() else []
    if extra:
        errors.append("unlisted files in texlow/: %s" % " ".join(extra))
    missing_drop = [k for (k,) in ix["drop"] if not staged_tex(fixtures, k)]
    if errors:
        raise SystemExit("stage_std: %s: %s" % (room, "; ".join(errors)))
    dst = native / "low"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for name in sorted(listed):
        if (low / name).exists():
            shutil.copy2(low / name, dst / name)
    for key in sorted(keys):
        d = fixtures / "texlow" / (key[0] if tex_resident else "")
        d.mkdir(parents=True, exist_ok=True)
        if (d / (key + ".re4tex")).exists():
            # another room's set carries the same texture: it must be the same file
            if (d / (key + ".re4tex")).read_bytes() != (texlow / (key + ".re4tex")).read_bytes():
                raise SystemExit("stage_std: %s: texlow key %s differs between rooms" % (room, key))
            continue
        shutil.copy2(texlow / (key + ".re4tex"), d / (key + ".re4tex"))
    low_bytes = sum(int(s) for _, s, _ in ix["mesh"])
    orig_bytes = sum(int(s) for o, s, _ in ix["orig"] if o in {m[0] for m in ix["mesh"]})
    tex_bytes = sum(int(t[4]) for t in ix["tex"])
    vram = sum(int(t[3]) for t in ix["tex"])
    idx_bytes = index.stat().st_size
    plan = (low / "plan.json").stat().st_size if (low / "plan.json").exists() else 0
    print("stage: %s Standard set: low/ %d package(s) %d B (Original of those owners %d B), texlow %d file(s) %d B "
          "(VRAM %d B), index %d B, plan.json %d B; disc +%d B; drop %d cull %d imp %d impt %d ptex %d%s" % (
              room, len(ix["mesh"]), low_bytes, orig_bytes, len(keys), tex_bytes, vram, idx_bytes, plan,
              low_bytes + tex_bytes + idx_bytes + plan, len(ix["drop"]), len(ix["cull"]), len(ix["imp"]),
              len(ix["impt"]), len(ix["ptex"]), "" if not missing_drop else "; %d drop key(s) have no staged package (nothing to skip): %s" % (
                  len(missing_drop), " ".join(missing_drop[:4]))), file=sys.stderr)
    return ("STDROOM %s dir=%s index-sha256=%s low=%d/%dB texlow=%d/%dB disc+%dB drop=%d cull=%d imp=%d impt=%d "
            "ptex=%d" % (
        room, src, sha(index), len(ix["mesh"]), low_bytes, len(keys), tex_bytes,
        low_bytes + tex_bytes + idx_bytes + plan, len(ix["drop"]), len(ix["cull"]), len(ix["imp"]), len(ix["impt"]),
        len(ix["ptex"])))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fixtures", type=Path)
    ap.add_argument("rooms", nargs="+", metavar="ROOM=DIR")
    ap.add_argument("--tex-resident", action="store_true")
    a = ap.parse_args(argv)
    specs = {}
    for s in a.rooms:
        room, _, d = s.partition("=")
        if len(room) != 4 or room[0] != "r" or not d:
            raise SystemExit("stage_std: bad room spec %r (expected rXXX=dir)" % s)
        if room in specs and specs[room] != d:
            raise SystemExit("stage_std: %s given twice" % room)
        specs[room] = d
    for room in sorted(specs):
        print(stage_room(a.fixtures, room, Path(specs[room]), a.tex_resident))
    return 0


if __name__ == "__main__":
    sys.exit(main())
