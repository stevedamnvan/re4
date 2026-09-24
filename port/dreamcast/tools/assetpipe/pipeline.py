"""Room build orchestration: sources -> generators -> pricing -> manifest -> staging."""
import json
import math
import os
from pathlib import Path

from . import r4im
from .cache import Cache, link_tree, outputs_hash
from .camera import build_instances, ground_views, price, percentile, screen_k
from .config import Config
from .generators import Gen, converter_dir
from .rooms import Room, bin_id, placement_matrix
from .texture import read_re4tex
from .util import canon_hash, dumps, write_json

TREE_CLASS = "tree"


class Ctx:
    def __init__(self, cfg=None, verify=False, jobs=None, log=print):
        self.cfg = cfg or Config()
        self.cache = Cache(self.cfg.root, verify=verify, log=log)
        self.gen = Gen(self.cfg, self.cache)
        self.jobs = jobs
        self.log = log


def recipe_specs(room):
    """Per owner converter spec from rooms.toml [room.X.recipe] (the accepted packages)."""
    r = room.recipe.get("recipe", {})
    spec = dict(bias=list(r.get("bias", [])))
    if r.get("floor"):
        spec["floor"] = [r["floor"]]
    if r.get("share"):
        spec["share"] = True
    if r.get("classes"):
        spec["classes"] = list(r["classes"])
    if r.get("class_auto"):
        spec["class_auto"] = True
    if r.get("class_rules"):
        spec["class_rules"] = list(r["class_rules"])
    return spec


def owner_filter(spec, code):
    """Keep only the bias/class entries that name this owner (the converter ignores the
    others, but a clean spec keeps cache keys per owner independent)."""
    def mine(s):
        o = s.split(":")[0]
        return int(o, 0) == code
    out = dict(spec)
    for k in ("bias", "classes", "cluster_trees", "cluster_bins"):
        if k in out:
            out[k] = [s for s in out[k] if mine(s)]
            if not out[k]:
                del out[k]
    if "floor" in out:
        out["floor"] = [f for f in out["floor"] if "=" not in str(f) or mine(str(f))]
    return out


def substitutes_for(ctx, room):
    subs, names = [], room.recipe.get("recipe", {}).get("substitute", [])
    objs = {}
    if "trees" in room.recipe and "trees" in names:
        objs["trees"] = ctx.gen.ps2_trees(room)
    if "planar2" in names:
        objs["planar2"] = ctx.gen.pinned("r100_planar2")
    for n in names:
        if n in objs:
            subs.append(objs[n])
    return subs, objs


def build_packages(ctx, room, specs, subs, scales, reset=False):
    """{owner name: Obj} for the given per-owner specs (reset: v1, no LOD, no substitutes)."""
    out = {}
    for o in room.owners():
        if reset:
            spec = dict(lod_args=["--cell", "0"], reset=True)
            out[o["name"]] = ctx.gen.package(room, o, spec, None, ())
        else:
            out[o["name"]] = ctx.gen.package(room, o, owner_filter(specs, o["code"]), scales, subs)
    return out


def load_pkgs(objs):
    return {name: r4im.load(obj.path(name + ".re4mesh")) for name, obj in objs.items()}


def asset_class(room, code, b, pkg_meta):
    t = room.recipe.get("trees")
    if t:
        o, bins = t["gc"].split(":")
        from .util import parse_ranges
        if int(o, 0) == code and b in parse_ranges(bins):
            return TREE_CLASS
    return pkg_meta.get((code, b), "scenery")


def room_views(ctx, room, pkgs):
    """Ground grid views (camera.ground_views) from the placed package vertices."""
    cost = ctx.cfg.cost
    cloud, centres = [], []
    for w in room.placements():
        pk = pkgs.get(w["owner"])
        if pk is None:
            continue
        k = pk.mesh_by_bin().get((w["bin"], bool(w["common"])))
        if k is None:
            continue
        M = placement_matrix(w)
        m = pk.meshes[k]
        centres.append([M[r][3] for r in range(3)])
        for p in pk.mesh_parts(k):
            for cl in pk.part_levels(p):
                for let in cl["levels"][0][1][:4]:
                    fv, vc = pk.meshlets[let][0], pk.meshlets[let][3]
                    for vi in range(fv, fv + vc, 7):
                        v = pk.vertex(vi)
                        q = pk.world(k, *v[:3])
                        cloud.append([M[r][0] * q[0] + M[r][1] * q[1] + M[r][2] * q[2] + M[r][3] for r in range(3)])
    views = ground_views(cloud, centres, cost["views"]["grid"], cost["views"]["yaws"], cost["screen"]["eye_mm"])
    return views


def price_room(ctx, room, pkgs, keyfn, options=None, views=None):
    """Price every placed asset of `pkgs` at the room views (default: the grid from `pkgs`
    itself); options default: the built package as is (bias 1 on its stored errors)."""
    views = views if views is not None else room_views(ctx, room, pkgs)
    inst = build_instances(pkgs, room.placements(), keyfn)
    keys = sorted({i["key"] for i in inst})
    opts = options or {k: [dict(id="built", bias=1.0)] for k in keys}
    return price(inst, views, opts, ctx.cfg.cost, jobs=ctx.jobs), views


def summarise(pr, keys, oi_of, base_ms):
    nv = len(pr.views)
    tot = [base_ms] * nv
    ta = [0] * nv
    rec = [0.0] * nv
    for k in keys:
        oi = oi_of(k)
        if k not in pr.ms:
            continue
        for v in range(nv):
            tot[v] += pr.ms[k][oi][v]
            ta[v] += pr.ta[k][oi][v]
    return dict(views=nv, ms_mean=round(sum(tot) / max(1, nv), 3), ms_p50=round(percentile(tot, 0.5), 3),
                ms_p95=round(percentile(tot, 0.95), 3), ms_max=round(max(tot) if tot else 0, 3),
                ta_bytes_max=max(ta) if ta else 0, worst_view=tot.index(max(tot)) if tot else None), tot


def room_base_ms(cfg, room):
    return float(cfg.cost["scenery"].get("base_ms", {}).get(room, cfg.cost["scenery"]["base_ms_default"]))


def build_room(ctx, name, mode="original", plan="recipe", only=None, review=True):
    cfg, gen = ctx.cfg, ctx.gen
    room = Room(cfg, ctx.cache, name)
    ctx.log("== %s (%s, plan=%s)" % (name, mode, plan))
    scales = gen.scales(room) if room.kind == "export" else None
    subs, sub_objs = substitutes_for(ctx, room)
    if plan != "recipe":
        raise NotImplementedError("plan=%s arrives with the solver (step c)" % plan)
    specs = recipe_specs(room)
    built = build_packages(ctx, room, specs, subs, scales)
    reset = build_packages(ctx, room, None, (), None, reset=True)
    expect = room.recipe.get("recipe", {}).get("expect", {})
    checks = {}
    for oname, sha in sorted(expect.items()):
        got = built[oname].outputs.get(oname + ".re4mesh")
        checks[oname] = "ok" if got == sha else "MISMATCH %s" % (got or "missing")[:16]
    # textures: VQ overlay (pinned, regenerated from logs when present) + PS2 bark
    texdirs, tex_assets = [], []
    vq = None
    logs = sorted(cfg.path("ui_logs").glob("*run-output.txt")) if cfg.path("ui_logs") else []
    if logs:
        vq = gen.vq_overlay(logs)
        pinned = cfg.path("vq_overlay")
        if pinned and pinned.exists():
            same = all((pinned / f).exists() and ctx.cache.file_hash(pinned / f) == h
                       for f, h in vq.outputs.items() if f.endswith(".re4tex"))
            checks["vq_overlay_vs_pinned"] = "ok" if same else "differs"
        texdirs.append(("00-vq", vq, lambda rel: rel.endswith(".re4tex") and "/" not in rel))
    pairs = cfg.rooms_cfg.get("material_pairs", {}).get("pairs", [])
    if (logs or pairs) and cfg.path("gc_iso") and cfg.path("gc_iso").exists():
        mp = gen.material_pairs(logs, pairs)
        if mp.info.get("pairs"):
            texdirs.append(("05-pairs", mp, lambda rel: rel.endswith(".re4tex") and "/" not in rel))
    bark = None
    if room.recipe.get("trees", {}).get("bark_png"):
        bark = gen.ps2_bark(room)
        texdirs.append(("10-bark", bark, lambda rel: rel.startswith("tex/") and rel.endswith(".re4tex")))
    # pricing: built vs reset, per asset
    base = room_base_ms(cfg, name)
    keyfn = lambda w: "%s/%s" % (w["owner"], bin_id(w["code"], w["bin"]))
    pk_built, pk_reset = load_pkgs(built), load_pkgs(reset)
    pr_b, views = price_room(ctx, room, pk_built, keyfn)
    # the same cameras for both sides: substitutes (PS2 trees) move the vertex cloud the
    # grid is built from, and r101's grid then has a different view count
    pr_r, _ = price_room(ctx, room, pk_reset, keyfn, views=views)
    keys = sorted(set(pr_b.ms) | set(pr_r.ms))
    sum_b, tot_b = summarise(pr_b, keys, lambda k: 0, base)
    sum_r, tot_r = summarise(pr_r, keys, lambda k: 0, base)
    assets = []
    inv = {r["id"]: r for r in room.inventory()}
    for o in room.owners():
        pkg = pk_built[o["name"]]
        for (b, common), mk in sorted(pkg.mesh_by_bin().items()):
            code = o["code"]
            aid = "%s/scenery/%s" % (name, bin_id(code, b))
            key = "%s/%s" % (o["name"], bin_id(code, b))
            cls = asset_class(room, code, b, {})
            spec = owner_filter(specs, code)
            decided = "recipe:rooms.toml [room.%s.recipe]" % name
            bias = [s for s in spec.get("bias", []) if b in _bins_of(s)]
            if bias:
                decided += " bias %s" % bias[0].split("=")[1]
            if any(("%s_%d.obj" % (o["name"], b)) in (s.outputs if hasattr(s, "outputs") else {})
                   for s in subs):
                decided += " + substitute (PS2 tree)"
            elif room.kind == "export" and "planar2" in sub_objs and \
                    (Path(sub_objs["planar2"]) / ("%s_%d.obj" % (o["name"], b))).exists():
                decided += " + Blender planar2"
            lv = pkg.mesh_summary(mk)
            def mean(pr, k):
                return round(sum(pr.ms[k][0]) / len(views), 4) if k in pr.ms else 0.0
            def p95(pr, k):
                return round(percentile(pr.ms[k][0], 0.95), 4) if k in pr.ms else 0.0
            assets.append(dict(id=aid, key=key, owner=o["name"], bin=b, **{"class": cls},
                               option="recipe", decided_by=decided,
                               levels=[dict(error=round(x["error"], 2), tris=x["tris"], records=x["corners"],
                                            strips=x["strips"], meshlets=x["meshlets"]) for x in lv],
                               source=dict(tris=inv.get(aid, {}).get("triangles"), instances=inv.get(aid, {}).get("instances"),
                                           radius_mm=inv.get(aid, {}).get("radius_mm")),
                               predicted=dict(hw_ms_mean=mean(pr_b, key), hw_ms_p95=p95(pr_b, key),
                                              reset_hw_ms_mean=mean(pr_r, key), reset_hw_ms_p95=p95(pr_r, key),
                                              records_mean=pr_b.counts.get(key, [{}])[0].get("records", 0),
                                              reset_records_mean=pr_r.counts.get(key, [{}])[0].get("records", 0)),
                               outputs={o["name"] + ".re4mesh": built[o["name"]].outputs[o["name"] + ".re4mesh"]}))
    for label, obj, sel in texdirs:
        for rel, sha in sorted(obj.outputs.items()):
            if not sel(rel):
                continue
            t = read_re4tex(obj.path(rel))
            key = Path(rel).stem
            assets.append(dict(id="%s/texture/%s" % (name, key), **{"class": "texture"}, option=label[3:],
                               decided_by="recipe:%s" % ("tex-vq5 rule (vq_native_ui --model-min-bytes 16384)"
                                                         if label.endswith("vq") else "PS2 bark (ps2_tree_texture.py)"),
                               predicted=dict(vram_bytes=t["vram_bytes"]), outputs={rel: sha}))
    heap4 = sum(obj.info.get("package_bytes") or 0 for obj in built.values())
    heap4_reset = sum(obj.info.get("package_bytes") or 0 for obj in reset.values())
    # staging view
    out = cfg.root / "out" / mode / name
    if out.exists():
        import shutil
        shutil.rmtree(out)
    mesh = out / "mesh"
    for oname, obj in sorted(built.items()):
        link_tree(obj, mesh, only=lambda rel: rel.endswith(".re4mesh"))
    tex_stage = []
    for label, obj, sel in texdirs:
        d = out / "tex" / label
        link_tree(obj, d, only=sel, rename=lambda rel: Path(rel).name)
        tex_stage.append(str(d))
    stage = {}
    if room.recipe.get("stage", "MESHROOMS") == "MESHDIR":
        stage["MESHDIR"] = str(mesh)
    else:
        stage["MESHROOMS"] = "%s=%s" % (name, mesh)
    if tex_stage:
        stage["TEXDIRS"] = " ".join(tex_stage)
    if room.recipe.get("keyed"):
        stage["KEYED"] = str(gen.pinned("keyed"))
    budgets = cfg.budgets(mode)
    status = "OK"
    if sum_b["ms_p95"] > budgets.get("scenery_ms_p95", 1e9):
        status = "OVER" if sum_b["ms_p95"] - base > budgets["scenery_ms_p95"] else "OVER-BASE"
    manifest = dict(schema="re4dc-assets/1", room=name, mode=mode, plan=plan,
                    config_sha256=canon_hash(cfg.cost), rooms_sha256=canon_hash(room.recipe),
                    converter=str(converter_dir(cfg, room).name), checks=checks, budgets=budgets, status=status,
                    predicted=dict(base_ms=base, scenery=sum_b, reset_scenery=sum_r, heap4_bytes=heap4,
                                   heap4_reset_bytes=heap4_reset,
                                   vram_bytes=sum(a["predicted"].get("vram_bytes", 0) for a in assets)),
                    views=[dict(v, ms=round(tot_b[i], 3), reset_ms=round(tot_r[i], 3)) for i, v in enumerate(views)],
                    assets=sorted(assets, key=lambda a: a["id"]),
                    steps={k: v for k, v in sorted(_steps(built, reset, texdirs, sub_objs).items())},
                    stage=stage)
    manifest["manifest_sha256"] = canon_hash({k: v for k, v in manifest.items() if k != "stage"})
    write_json(out / "manifest.json", manifest)
    env = "".join(': "${%s:=%s}"\nexport %s\n' % (k, v, k) for k, v in sorted(stage.items()))
    (out / "stage.env").write_text("# generated by tools/d367/assets.sh (%s %s); source before stage.sh\n%s" % (
        name, mode, env))
    ctx.cache.save_memo()
    if review:
        from .review import review_room
        review_room(ctx, room, manifest, pk_built, pk_reset, views, out)
    return manifest


def _bins_of(spec):
    from .util import parse_ranges
    try:
        return parse_ranges(spec.split(":")[1].split("=")[0])
    except (IndexError, ValueError):
        return []


def _steps(built, reset, texdirs, sub_objs):
    s = {}
    for n, o in built.items():
        s["scenery:" + n] = o.key
    for n, o in reset.items():
        s["reset:" + n] = o.key
    for label, o, _ in texdirs:
        s["texture:" + label] = o.key
    for n, o in sub_objs.items():
        s["subst:" + n] = getattr(o, "key", None) or "pinned:" + str(o)
    return s
