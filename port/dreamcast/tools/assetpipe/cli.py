"""assets.sh command line (docs/D367_ASSET_PIPELINE.md section 1)."""
import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .util import dumps

COMMANDS = ("build", "rooms", "inventory", "plan", "review", "stage-env", "calibrate")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv and argv[0] in COMMANDS else "build"
    ap = argparse.ArgumentParser(prog="assets.sh " + cmd, description=__doc__)
    ap.add_argument("target", nargs="?", default="route", help="room (r100), 'route' or 'all'")
    ap.add_argument("--mode", choices=("standard", "original"), default="standard",
                    help="standard (default): budget-first Dreamcast-native look; original: the faithful recipe")
    ap.add_argument("--plan", choices=("recipe", "solve"), default="recipe",
                    help="recipe: the accepted hand-tuned packages (rooms.toml); solve: the cost-model solver")
    ap.add_argument("--only", default="", help="classes to (re)build: scenery,tree,house,texture,actor,pvs,audio,movie")
    ap.add_argument("--override", action="append", default=[], type=Path)
    ap.add_argument("--costmodel", type=Path, help="extra TOML merged over costmodel.toml (e.g. costmodel.fit.toml)")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--verify", action="store_true", help="rebuild every cached step and compare output hashes")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--set", type=Path, help="calibrate: calibration set TOML")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cfg = Config(a.costmodel)
    if cmd == "rooms":
        from .rooms import all_rooms
        rooms = all_rooms(cfg)
        route = set(cfg.route())
        for r, (disc, rel) in sorted(rooms.items()):
            print("%s  %-14s %s%s" % (r, rel, disc, "  (route)" if r in route else ""))
        print("%d rooms" % len(rooms))
        return 0
    from .pipeline import Ctx, build_room
    ctx = Ctx(cfg, verify=a.verify, jobs=a.jobs or None)
    targets = _targets(cfg, a.target)
    if cmd == "inventory":
        from .rooms import Room
        for t in targets:
            rows = Room(cfg, ctx.cache, t).inventory()
            if a.json:
                print(dumps(rows))
            else:
                print("== %s: %d BINs, %d triangles, %d instances" % (
                    t, len(rows), sum(r.get("triangles", 0) for r in rows), sum(r.get("instances", 0) for r in rows)))
                for r in rows:
                    print("  %-26s tris %6s inst %3s r %7.1f m  %s" % (
                        r["id"], r.get("triangles"), r.get("instances"), (r.get("radius_mm") or 0) / 1000,
                        r.get("gx_kept") or r.get("error") or ""))
        ctx.cache.save_memo()
        return 0
    if cmd == "stage-env":
        return stage_env(cfg, targets, a.mode)
    if cmd == "calibrate":
        from .calibrate import calibrate
        return calibrate(ctx, a.set)
    rc = 0
    for t in targets:
        if a.mode == "standard":
            from .budget import build_standard
            m = build_standard(ctx, t, only=a.only.split(",") if a.only else None,
                               review=not a.no_review and cmd != "plan")
            sm = m["predicted"]["summary"]
            print("%s standard: status %s, scenery assets hw ms (excl. base) grid p95 %.2f max %.2f, named max %.2f "
                  "(original p95 %.2f max %.2f); heap4 ok %s, second set %.2f MB, manifest %s" % (
                      t, m["status"], sm["standard"]["assets_ms"]["p95"], sm["standard"]["assets_ms"]["max"],
                      sm["standard"]["named_assets_ms_max"], sm["original"]["assets_ms"]["p95"],
                      sm["original"]["assets_ms"]["max"], m["predicted"]["sizes"]["heap4_ok"],
                      m["predicted"]["sizes"]["disc"]["second_set_bytes"] / 1e6, m["manifest_sha256"][:16]))
            continue
        m = build_room(ctx, t, mode=a.mode, plan=a.plan, only=a.only.split(",") if a.only else None,
                       review=not a.no_review and cmd != "plan")
        s = m["predicted"]["scenery"]
        print("%s %s: status %s, scenery hw ms p50 %.2f p95 %.2f max %.2f (source p95 %.2f), heap4 %d, "
              "manifest %s" % (t, a.mode, m["status"], s["ms_p50"], s["ms_p95"], s["ms_max"],
                               m["predicted"]["reset_scenery"]["ms_p95"], m["predicted"]["heap4_bytes"],
                               m["manifest_sha256"][:16]))
        for k, v in sorted(m["checks"].items()):
            print("  check %s: %s" % (k, v))
            if v not in ("ok",):
                rc = 1
    print("steps: %d built, %d cached" % (len(ctx.cache.built), len(ctx.cache.hits)))
    if a.verify:
        if ctx.cache.mismatches:
            print("VERIFY: %d step(s) not reproducible:" % len(ctx.cache.mismatches))
            for label, key, diff in ctx.cache.mismatches:
                print("  %s %s: %s" % (label, key[:12], ", ".join(diff[:8])))
            rc = 2
        else:
            print("VERIFY: every step reproduced byte for byte")
    return rc


def _targets(cfg, t):
    if t == "route":
        return cfg.route()
    if t == "all":
        from .rooms import all_rooms
        return sorted(all_rooms(cfg))
    return [x for x in t.split(",") if x]


def stage_env(cfg, targets, mode):
    """Merge the rooms' stage.env files into one environment for tools/d367/stage.sh."""
    merged = {}
    for t in targets:
        m = json.loads((cfg.root / "out" / mode / t / "manifest.json").read_text())
        for k, v in m["stage"].items():
            if k in ("MESHROOMS", "TEXDIRS", "ROOMFILES", "NATIVEFILES"):
                parts = merged.get(k, "").split()
                parts += [x for x in v.split() if x not in parts]
                merged[k] = " ".join(parts)
            else:
                merged[k] = v
    out = cfg.root / "out" / mode / ("+".join(targets) if len(targets) > 1 else targets[0])
    out.mkdir(parents=True, exist_ok=True)
    env = "".join(': "${%s:=%s}"\nexport %s\n' % (k, v, k) for k, v in sorted(merged.items()))
    (out / "stage.env").write_text("# generated by tools/d367/assets.sh stage-env %s (%s)\n%s" % (
        " ".join(targets), mode, env))
    print(env, end="")
    print("# written to %s  (ASSETS=%s tools/d367/stage.sh <build> <disc>)" % (out / "stage.env", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
