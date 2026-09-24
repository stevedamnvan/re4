"""Standard (default) mode: the budget-first "Dreamcast-native look" plan (doc section 4.9).

Original = the faithful recipe packages (pipeline.build_room, mode "original").
Standard = the same sources, re-planned against hard per-view budgets:
  * every asset gets a class (rooms.toml [room.X.standard] + size heuristics) and a
    class option list (costmodel.toml [plan.standard.options]): extra LOD bias, tree
    impostor distance, clutter cull distance;
  * houses become baked shells (item 21 bl_house_shell.py) from a face ladder;
  * runtime LOD px 5;
  * a greedy multiple-choice solver picks one option per asset so that EVERY view
    (ground grid + named views) stays within the scenery budget (hw ms excluding the
    fixed base, triangles), losing the least weighted quality; views that cannot fit
    even at the cheapest options are reported INFEASIBLE with their floor.
The chosen biases are baked into rebuilt packages (converter --lod-bias); impostor and
cull distances go to plan.json for the runtime (item 20 records, W9b class rules).
"""
import json
import math
import multiprocessing
import os
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import r4im, texture
from .cache import link_tree
from .camera import build_instances, percentile, price, screen_k
from .generators import converter_dir
from .pipeline import (build_packages, build_room, load_pkgs, owner_filter, recipe_specs, room_base_ms,
                       room_views, substitutes_for)
from .raster import View, png_bytes
from .render import render_scene
from .rooms import Room, bin_id, placement_matrix
from .scene import SceneBuilder, Textures
from .util import canon_hash, parse_ranges, ranges, write_json


# ---------------------------------------------------------------------------- classes
def classify(room, inv, plan):
    """{asset key '<owner>/<bin id>': class}. Explicit lists first (houses, landmarks,
    recipe trees), then: ground = flat and wide, clutter = small, else structure."""
    st = room.recipe.get("standard", {})
    houses = set(st.get("houses", []))
    landmarks = set(st.get("landmarks", []))
    trees = set()
    t = room.recipe.get("trees")
    if t:
        o, bins = t["gc"].split(":")
        trees = {bin_id(int(o, 0), b) for b in parse_ranges(bins)}
    for c in room.recipe.get("recipe", {}).get("classes", []):     # W9b "--class 0xff:13-17=tree"
        sel, cls = c.split("=")
        if cls == "tree":
            o, bins = sel.split(":")
            trees |= {bin_id(int(o, 0), b) for b in parse_ranges(bins)}
    auto = plan.get("houses_auto")   # candidates by size; house_shells keeps only those a shell fits
    out = {}
    for r in inv:
        bid = bin_id(r["code"], r["bin"])
        key = "%s/%s" % (r["owner"], bid)
        ext = r.get("extent_mm") or [0, 0, 0]
        horiz = max(ext[0], ext[2])
        if bid in landmarks:
            c = "landmark"
        elif bid in houses:
            c = "house"
        elif bid in trees:
            c = "tree"
        elif horiz >= plan["ground_min_mm"] and ext[1] <= plan["ground_flat"] * horiz:
            c = "ground"
        elif auto and bid not in auto.get("exclude", []) and                 auto["min_radius_mm"] <= (r.get("radius_mm") or 0) <= auto.get("max_radius_mm", 1e9)                 and (r.get("triangles") or 0) >= auto["min_tris"] and ext[1] >= auto["min_height_mm"]                 and ext[1] <= auto.get("max_height_ratio", 1.0) * horiz and (r.get("instances") or 1) <= auto["max_instances"]:
            c = "house"
        elif (r.get("radius_mm") or 0) <= plan["clutter_radius_mm"]:
            c = "clutter"
        else:
            c = "structure"
        out[key] = c
    return out


def class_options(cls, plan, has_impostor):
    """Option dicts for a class, cartesian product of its lists, best quality first."""
    spec = plan["options"].get(cls, {"bias": [1.0]})
    out = []
    for b in spec.get("bias", [1.0]):
        for imp in (spec.get("imp_mm", [0]) if has_impostor else [0]):
            for cull in spec.get("cull_mm", [0]):
                o = dict(bias=float(b))
                name = "b%g" % b
                if imp:
                    o["imp_mm"] = float(imp)
                    name += "-imp%gm" % (imp / 1000.0)
                if cull:
                    o["cull_mm"] = float(cull)
                    name += "-cull%gm" % (cull / 1000.0)
                o["id"] = name
                out.append(o)
    return out


# ---------------------------------------------------------------------------- solver
def solve(pr, keys, weights, nviews, b_ms, b_tris, log=print):
    """Lazy-greedy multiple-choice solver. pr: Pricing with options per key (index 0 = best
    quality). Constraint for every view v: sum ms <= b_ms and sum tris <= b_tris. A move
    changes one asset's option; its score is the reduction of the summed relative excess over
    all views per unit of added weighted quality loss (moves that lose nothing go first).
    Scores only fall as the excess falls, so stale heap entries are re-scored lazily. Ties:
    higher score, lower option index, key order (deterministic). Then an upgrade pass gives
    quality back wherever no view gets worse or leaves its budget. Returns (choice {key:
    option index}, per-view ms, per-view tris, indices of views still over budget)."""
    import heapq
    ms, tr = pr.ms, pr.tris
    vis = {}
    for k in keys:
        s = set()
        for row in ms[k]:
            s.update(v for v in range(nviews) if row[v] > 0)
        for row in tr[k]:
            s.update(v for v in range(nviews) if row[v] > 0)
        vis[k] = sorted(s)
    cur = {k: 0 for k in keys}
    S = [0.0] * nviews
    T = [0] * nviews
    for k in keys:
        for v in vis[k]:
            S[v] += ms[k][0][v]
            T[v] += tr[k][0][v]
    Q = {k: [q * weights[k] for q in pr.quality[k]] for k in keys}
    ib, it = 1.0 / b_ms, 1.0 / b_tris

    def gain(k, j):
        c = cur[k]
        mc, mj, tc, tj = ms[k][c], ms[k][j], tr[k][c], tr[k][j]
        g = 0.0
        for v in vis[k]:
            s, t = S[v], T[v]
            if s > b_ms:
                s2 = s - mc[v] + mj[v]
                g += ((s - b_ms) - (s2 - b_ms if s2 > b_ms else 0.0)) * ib
            elif mj[v] > mc[v]:
                s2 = s - mc[v] + mj[v]
                if s2 > b_ms:
                    g -= (s2 - b_ms) * ib
            if t > b_tris:
                t2 = t - tc[v] + tj[v]
                g += ((t - b_tris) - (t2 - b_tris if t2 > b_tris else 0)) * it
            elif tj[v] > tc[v]:
                t2 = t - tc[v] + tj[v]
                if t2 > b_tris:
                    g -= (t2 - b_tris) * it
        return g

    def score(k, j):
        g = gain(k, j)
        if g <= 1e-9:
            return None
        dq = Q[k][j] - Q[k][cur[k]]
        return g / max(dq, 1e-9) if dq > 0 else 1e18 + g

    ver = {k: 0 for k in keys}
    heap = []

    def push_key(k):
        for j in range(len(Q[k])):
            if j == cur[k]:
                continue
            sc = score(k, j)
            if sc is not None:
                heapq.heappush(heap, (-sc, -j, k, j, ver[k]))
    for k in keys:
        push_key(k)
    steps = 0
    while heap:
        if not any(S[v] > b_ms + 1e-9 or T[v] > b_tris for v in range(nviews)):
            break
        negsc, _, k, j, vv = heapq.heappop(heap)
        if vv != ver[k] or j == cur[k]:
            continue
        sc = score(k, j)
        if sc is None:
            continue
        if heap and sc < -heap[0][0] - 1e-12:
            heapq.heappush(heap, (-sc, -j, k, j, ver[k]))
            continue
        c = cur[k]
        for v in vis[k]:
            S[v] += ms[k][j][v] - ms[k][c][v]
            T[v] += tr[k][j][v] - tr[k][c][v]
        cur[k] = j
        ver[k] += 1
        steps += 1
        push_key(k)
    infeasible = [v for v in range(nviews) if S[v] > b_ms + 1e-9 or T[v] > b_tris]
    changed = True
    while changed:
        changed = False
        for k in keys:
            c = cur[k]
            q = Q[k]
            for j in sorted(range(len(q)), key=lambda j: (q[j], j)):
                if q[j] >= q[c]:
                    break
                ok = True
                for v in vis[k]:
                    s = S[v] - ms[k][c][v] + ms[k][j][v]
                    t = T[v] - tr[k][c][v] + tr[k][j][v]
                    if (s > b_ms + 1e-9 and s > S[v] + 1e-12) or (t > b_tris and t > T[v]):
                        ok = False
                        break
                if ok:
                    for v in vis[k]:
                        S[v] += ms[k][j][v] - ms[k][c][v]
                        T[v] += tr[k][j][v] - tr[k][c][v]
                    cur[k] = j
                    changed = True
                    break
    log("  solver: %d moves, %d/%d views over budget after the solve" % (steps, len(infeasible), nviews))
    return cur, S, T, infeasible


# ---------------------------------------------------------------------------- views
def _ground_fn(ctx, room, pkgs):
    """ground(x, z) -> 20th percentile placed-vertex height within 1.5 m (as ground_views)."""
    cloud = []
    for w in room.placements():
        pk = pkgs.get(w["owner"])
        if pk is None:
            continue
        k = pk.mesh_by_bin().get((w["bin"], bool(w["common"])))
        if k is None:
            continue
        M = placement_matrix(w)
        for p in pk.mesh_parts(k):
            for cl in pk.part_levels(p):
                for let in cl["levels"][0][1]:
                    fv, vc = pk.meshlets[let][0], pk.meshlets[let][3]
                    for vi in range(fv, fv + vc, 3):
                        q = pk.world(k, *pk.vertex(vi)[:3])
                        cloud.append([M[r][0] * q[0] + M[r][1] * q[1] + M[r][2] * q[2] + M[r][3] for r in range(3)])
    cell = 1500.0
    buckets = {}
    for v in cloud:
        buckets.setdefault((int(v[0] // cell), int(v[2] // cell)), []).append(v[1])

    def ground(x, z):
        ys = []
        bx, bz = int(x // cell), int(z // cell)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                ys.extend(buckets.get((bx + dx, bz + dz), ()))
        if not ys:
            return None
        ys.sort()
        return ys[len(ys) // 5]
    return ground


def _look(eye, target):
    d = [target[i] - eye[i] for i in range(3)]
    yaw = math.degrees(math.atan2(d[0], d[2]))
    pitch = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
    return round(yaw, 4), round(pitch, 4)


def named_views(ctx, room, pkgs, grid, grid_ms_original):
    """rooms.toml [room.X.views] -> [dict(name, eye, target, yaw, pitch, frame)]."""
    spec = room.recipe.get("views", {})
    eye_mm = ctx.cfg.cost["screen"]["eye_mm"]
    out = []
    ground = None
    order = ["spawn", "path_a", "path_b", "fight", "fight_in", "cow_pen", "house", "w9_worst", "widest"]
    for name in sorted(spec, key=lambda n: (order.index(n) if n in order else len(order), n)):
        s = spec[name]
        if "cam" in s:
            cam = [float(x) for x in s["cam"]]
            to = s["toward"]
            d = [to[0] - cam[0], to[2] - cam[2]]
            n = math.hypot(*d) or 1.0
            p = math.radians(s.get("pitch", 0.0))
            tgt = [cam[0] + d[0] / n * 1000.0, cam[1] + math.tan(p) * 1000.0, cam[2] + d[1] / n * 1000.0]
            yaw, pitch = _look(cam, tgt)
            out.append(dict(name=name, eye=cam, target=tgt, yaw=yaw, pitch=pitch, frame=s.get("frame")))
        elif "player" in s:
            # door arrival (AEV dstPos / dstAngle): the camera behind and above the player as
            # at the r100 spawn frame (1.29 m back, 1.76 m up, 10 degrees down)
            px_, py_, pz_ = [float(x) for x in s["player"]]
            a = float(s["angle"])
            f = [math.sin(a), math.cos(a)]
            back, up = s.get("back_mm", 1290.0), s.get("up_mm", 1764.0)
            cam = [round(px_ - f[0] * back, 1), round(py_ + up, 1), round(pz_ - f[1] * back, 1)]
            p = math.radians(s.get("pitch", -10.0))
            tgt = [cam[0] + f[0] * 1000.0, cam[1] + math.tan(p) * 1000.0, cam[2] + f[1] * 1000.0]
            yaw, pitch = _look(cam, tgt)
            out.append(dict(name=name, eye=cam, target=tgt, yaw=yaw, pitch=pitch, frame=None))
        elif "yaw" in s:
            # a fixed eye and yaw (the W9 model's grid views: yaw about +y, 0 = +z, pitch 0)
            eye = [float(x) for x in s["eye"]]
            yr, pr_ = math.radians(s["yaw"]), math.radians(s.get("pitch", 0.0))
            tgt = [eye[0] + math.sin(yr) * 1000.0, eye[1] + math.tan(pr_) * 1000.0, eye[2] + math.cos(yr) * 1000.0]
            out.append(dict(name=name, eye=eye, target=tgt, yaw=float(s["yaw"]), pitch=s.get("pitch", 0.0),
                            frame=None))
        elif "eye_xz" in s:
            # standing at eye_xz (ground + eye height) looking at at_xz (ground + 1 m)
            ground = ground or _ground_fn(ctx, room, pkgs)
            ex, ez = [float(x) for x in s["eye_xz"]]
            ax, az = [float(x) for x in s["at_xz"]]
            gy, gt = ground(ex, ez), ground(ax, az)
            eye = [ex, round((gy if gy is not None else 0.0) + eye_mm, 1), ez]
            tgt = [ax, round((gt if gt is not None else 0.0) + 1000.0, 1), az]
            yaw, pitch = _look(eye, tgt)
            out.append(dict(name=name, eye=eye, target=tgt, yaw=yaw, pitch=pitch, frame=None))
        elif "bin" in s:
            ground = ground or _ground_fn(ctx, room, pkgs)
            code, b = s["bin"].split(":")
            code = int(code, 0)
            w = next(w for w in room.placements() if w["code"] == code and w["bin"] == int(b))
            pk = pkgs[w["owner"]]
            mk = pk.mesh_by_bin()[(w["bin"], bool(w["common"]))]
            m = pk.meshes[mk]
            lo, hi = m[14:17], m[17:20]
            M = placement_matrix(w)
            c = [(lo[a] + hi[a]) * 0.5 for a in range(3)]
            e = [(hi[a] - lo[a]) * 0.5 for a in range(3)]
            wc = [sum(M[r][k] * c[k] for k in range(3)) + M[r][3] for r in range(3)]
            we = [sum(abs(M[r][k]) * e[k] for k in range(3)) for r in range(3)]
            src = next(v for v in out if v["name"] == s["from"])["eye"]
            u = [src[0] - wc[0], src[2] - wc[2]]
            n = math.hypot(*u) or 1.0
            u = [u[0] / n, u[1] / n]
            reach = abs(u[0]) * we[0] + abs(u[1]) * we[2]
            gh = ground(wc[0], wc[2])
            for dm in s["distances_m"]:
                x, z = wc[0] + u[0] * (reach + dm * 1000.0), wc[2] + u[1] * (reach + dm * 1000.0)
                gy = ground(x, z)
                eye = [round(x, 1), round((gy if gy is not None else wc[1]) + eye_mm, 1), round(z, 1)]
                ty = (gh if gh is not None else wc[1]) + eye_mm
                tgt = [wc[0], max(ty, eye[1] - 0.15 * (reach + dm * 1000.0)), wc[2]]
                yaw, pitch = _look(eye, tgt)
                out.append(dict(name="%s_%gm" % (name, dm), eye=eye, target=tgt, yaw=yaw, pitch=pitch,
                                frame=None, subject=s["bin"]))
        elif s.get("grid") == "max_original_ms":
            i = max(range(len(grid)), key=lambda i: (grid_ms_original[i], -i))
            g = grid[i]
            yr, pr_ = math.radians(g["yaw"]), math.radians(g.get("pitch", 0.0))
            tgt = [g["eye"][0] + math.sin(yr) * 1000.0, g["eye"][1] + math.tan(pr_) * 1000.0,
                   g["eye"][2] + math.cos(yr) * 1000.0]
            out.append(dict(name=name, eye=list(g["eye"]), target=tgt, yaw=g["yaw"], pitch=g.get("pitch", 0.0),
                            frame=None, grid=g["name"]))
    return out


# ---------------------------------------------------------------------------- shells
def house_shells(ctx, room, classes, inv, plan):
    """{bin id: (Obj, faces)}: per house the first ladder rung whose p90 source->shell error
    is within plan house_err_cm (else the last rung). With plan `houses_auto` (size-picked
    candidates) a candidate no rung fits is not shelled: its class goes back to structure and
    it is listed in plan['_shell_rejected']."""
    out = {}
    rejected = plan.setdefault("_shell_rejected", {})
    names = {o["code"]: o["name"] for o in room.owners()}
    for key, cls in sorted(classes.items()):
        if cls != "house":
            continue
        owner, bid = key.split("/")
        code, b = bid.split(":")
        skey = "%s_%d" % (owner, int(b))
        chosen = None
        for faces in plan["house_faces"]:
            try:
                obj = ctx.gen.house_shell(room, skey, faces, plan["house_tex"])
            except Exception as ex:        # a size-picked candidate the shell tool cannot bake
                if not plan.get("houses_auto"):
                    raise
                ctx.log("  shell %s %d faces failed (%s); not shelled" % (skey, faces, str(ex).splitlines()[0][:80]))
                chosen = (None, faces, 1e9)
                break
            err = (obj.info.get("source_to_shell_cm") or {}).get("p90", 1e9)
            chosen = (obj, faces, err)
            if err <= plan["house_err_cm"]:
                break
        if plan.get("houses_auto") and chosen[2] > plan["house_err_cm"]:
            rejected[key] = round(min(chosen[2], 1e6), 1)
            classes[key] = "structure"
            continue
        out[bid] = chosen
    return out


# ---------------------------------------------------------------------------- render workers
_R = None


def _render_job(i):
    jobs, builders, cost, far = _R
    name, mode, view, opts, px = jobs[i]
    sb = builders[mode]
    tris, n = sb.build(view["eye"], view["target"], opts, px, far)
    png, drawn = render_scene(View(view["eye"], view["target"], 480, 360), tris, fog=(3000.0, far))
    return png, n


# ---------------------------------------------------------------------------- main
def build_standard(ctx, name, only=None, review=True):
    cfg, gen = ctx.cfg, ctx.gen
    plan = cfg.cost["plan"]["standard"]
    budgets = cfg.budgets("standard")
    room = Room(cfg, ctx.cache, name)
    # per-room plan overrides (rooms.toml [room.X.standard.plan]; options merge per class)
    over = room.recipe.get("standard", {}).get("plan", {})
    if over:
        plan = dict(plan, **{k: v for k, v in over.items() if k != "options"})
        plan["options"] = dict(cfg.cost["plan"]["standard"]["options"], **over.get("options", {}))
    else:
        plan = dict(plan)
    ctx.log("== %s (standard: budget-first; original for comparison)" % name)
    orig = build_room(ctx, name, mode="original", plan="recipe", review=False)
    scales = gen.scales(room) if room.kind == "export" else None
    subs, sub_objs = substitutes_for(ctx, room)
    specs = recipe_specs(room)
    if plan.get("lod_args"):
        specs = dict(specs, lod_args=list(plan["lod_args"]))    # coarser LOD chain: more levels to choose from
    inv = room.inventory()
    classes = classify(room, inv, plan)
    shells = house_shells(ctx, room, classes, inv, plan)
    shell_dirs = [Path(o.out) / "replace" for o, _, _ in (shells[b] for b in sorted(shells))]
    orig_objs = build_packages(ctx, room, recipe_specs(room), subs, scales)
    # Standard substitutes: the recipe's, minus any whole-BIN replacement of a shelled house
    names = {o["code"]: o["name"] for o in room.owners()}
    shelled = ["%s_%d" % (names[int(b.split(":")[0], 0)], int(b.split(":")[1])) for b in shells]
    recipe_subs = list(subs)

    def subs_minus(exclude):
        out = []
        for s in recipe_subs:
            d = Path(s.out if hasattr(s, "out") else s)
            if any((d / (k + ".obj")).exists() for k in exclude):
                s = gen.subst_without(s, exclude).out
            out.append(s)
        return out
    subs = subs_minus(shelled)
    # split groves (plan grove_split, s16.5): every tree-class BIN is converted with per-tree clusters;
    # the converter leaves a BIN with fewer than two trunks unchanged
    gs = plan.get("grove_split")
    if gs:
        tb = {}
        for k, c in sorted(classes.items()):
            if c == "tree":
                code, b = _imp_key(k)
                tb.setdefault(code, []).append(b)
        if tb:
            specs = dict(specs, cluster_trees=["%s:%s" % ("0x%02x" % c if c >= 0xF0 else str(c), ranges(sorted(bs)))
                                               for c, bs in sorted(tb.items())])
    # base Standard packages: recipe + shells (biases come from the solver below)
    base_objs = build_packages(ctx, room, specs, list(subs) + shell_dirs, scales)
    # coarse geometry variant (Blender reduction of ground/structure BINs), priced as extra options
    coarse = plan.get("coarse")
    coarse_obj, coarse_keys, coarse_err = None, {}, {}
    if coarse:
        for k, c in sorted(classes.items()):
            if c in coarse["classes"]:
                owner, bid = k.split("/")
                coarse_keys[k] = "%s_%d" % (owner, int(bid.split(":")[1]))
        if coarse_keys:
            coarse_obj = gen.decimate(room, sorted(coarse_keys.values()), coarse["variant"], coarse["ops"])
            rep = json.loads(coarse_obj.path("blender-report.json").read_text()).get(coarse["variant"], {})
            rad = {"%s/%s" % (r["owner"], bin_id(r["code"], r["bin"])): r.get("radius_mm") or 0.0 for r in inv}
            for k, sk in coarse_keys.items():
                r = rep.get(sk, {})
                p90 = float(max(r.get("fwd_p90") or 0.0, r.get("rev_p90") or 0.0))
                worst = float(r.get("rev_max") or 0.0)
                # absolute limits, and relative to the object (a 1 m well must not lose 0.6 m: r101's
                # well became a cone)
                if p90 <= coarse.get("max_p90_mm", 1e9) and worst <= coarse.get("max_mm", 1e9) and                         worst <= coarse.get("max_rel", 1e9) * rad.get(k, 0.0):
                    coarse_err[k] = p90
            coarse_subs = subs_minus(shelled + sorted(coarse_keys.values())) + [coarse_obj.out]
            coarse_objs = build_packages(ctx, room, specs, coarse_subs + shell_dirs, scales)
    pk_base, pk_orig = load_pkgs(base_objs), load_pkgs(orig_objs)
    keyfn = lambda w: "%s/%s" % (w["owner"], bin_id(w["code"], w["bin"]))
    # views: grid + named (named views from the original packages, so both modes share cameras)
    grid = room_views(ctx, room, pk_orig)
    cost = cfg.cost
    far = cost["lod"]["fog_far_mm"]
    inst_o = build_instances(pk_orig, room.placements(), keyfn)
    keys_o = sorted({i["key"] for i in inst_o})
    pr_grid_o = price(inst_o, grid, {k: [dict(id="orig", bias=1.0)] for k in keys_o}, cost, px=cost["lod"]["px"],
                      far=far, jobs=ctx.jobs)
    grid_ms_o = [sum(pr_grid_o.ms[k][0][v] for k in keys_o) for v in range(len(grid))]
    named = named_views(ctx, room, pk_orig, grid, grid_ms_o)
    views = [dict(name=v["name"], eye=tuple(v["eye"]), yaw=v["yaw"], pitch=v["pitch"]) for v in named] + grid
    nv = len(views)
    # Original priced at every view (its own px), Standard options priced on the base packages
    pr_o = price(inst_o, views, {k: [dict(id="orig", bias=1.0)] for k in keys_o}, cost, px=cost["lod"]["px"], far=far,
                 jobs=ctx.jobs)
    imp_recs = _impostor_records(ctx, room, plan, classes, orig_objs)
    grove_recs, tree_table = _grove_trees(ctx, room, base_objs, gs) if gs else ({}, {})
    for kk in grove_recs:
        imp_recs.pop(kk, None)      # a split grove offers per-tree impostors, not the whole-BIN one
    inst_s = build_instances(pk_base, room.placements(), keyfn, trees=tree_table)
    keys_s = sorted({i["key"] for i in inst_s})
    options = {k: class_options(classes.get(k, "structure"), plan, _imp_key(k) in imp_recs or
                                _imp_key(k) in grove_recs) for k in keys_s}
    for k in keys_s:
        for o in options[k]:
            if not o.get("imp_mm"):
                continue
            if _imp_key(k) in grove_recs:
                o.update(split=True, views=int(gs.get("views", 8)), id=o["id"] + "-trees")
            else:           # the whole-BIN atlas's view count sets its view-quantisation error
                o["views"] = int(imp_recs[_imp_key(k)]["views"])
    # empty LOD levels: no nearer vanishing than Original (priced here, patched into the packages)
    vmin = _vanish_min(room, pk_orig, plan["px"], cost["lod"]["px"])
    for k in keys_s:
        for o in options[k]:
            o["vanish_min"] = vmin.get(k, NEVER)
    ctx.log("  pricing %d assets x %d views (%d options)" % (len(keys_s), nv, sum(len(v) for v in options.values())))
    pr_s = price(inst_s, views, options, cost, px=plan["px"], far=far, jobs=ctx.jobs)
    if coarse_obj is not None:
        pk_c = load_pkgs(coarse_objs)
        inst_c = build_instances(pk_c, room.placements(), keyfn, trees=tree_table)
        opt_c = {k: [dict(o, id="%s-%s" % (coarse["variant"], o["id"]), geom=coarse["variant"],
                          err_floor=coarse_err[k]) for o in options[k]] for k in sorted(coarse_err) if k in options}
        ctx.log("  pricing %d %s variants" % (sum(len(v) for v in opt_c.values()), coarse["variant"]))
        pr_c = price(inst_c, views, opt_c, cost, px=plan["px"], far=far, jobs=ctx.jobs)
        for k, oc in opt_c.items():
            options[k] = options[k] + oc
            pr_s.ms[k] = pr_s.ms[k] + pr_c.ms[k]
            pr_s.tris[k] = pr_s.tris[k] + pr_c.tris[k]
            pr_s.quality[k] = pr_s.quality[k] + pr_c.quality[k]
            pr_s.counts[k] = pr_s.counts[k] + pr_c.counts[k]
    if os.environ.get("RE4DC_ASSETS_DUMP_PRICING"):
        import pickle
        with open(os.environ["RE4DC_ASSETS_DUMP_PRICING"], "wb") as f:
            pickle.dump(dict(ms=pr_s.ms, tris=pr_s.tris, quality=pr_s.quality, keys=keys_s, nv=nv,
                             classes=classes, options=options), f)
    wq = cost["quality"]["weights"]
    weights = {k: float(wq.get(classes.get(k, "default"), wq.get("default", 1.0))) for k in keys_s}
    choice, S, T, infeasible = solve(pr_s, keys_s, weights, nv, budgets["scenery_ms_view_max"],
                                     budgets["scenery_tris_view_max"], log=ctx.log)
    chosen = {k: options[k][choice[k]] for k in keys_s}
    # final substitutes: recipe minus shelled/coarse-chosen BINs, + the chosen coarse BINs
    use_coarse = sorted(coarse_keys[k] for k in keys_s if chosen[k].get("geom") and k in coarse_keys)
    subs = subs_minus(shelled + use_coarse)
    if use_coarse:
        unused = sorted(set(coarse_keys.values()) - set(use_coarse))
        subs.append(gen.subst_without(coarse_obj, unused).out if unused else coarse_obj.out)
    # final packages: recipe bias x chosen bias baked per BIN
    final_objs = _final_packages(ctx, room, specs, subs, shell_dirs, scales, chosen, vmin)
    # heap 4: no Standard package may be larger than Original's; an owner that grew (deeper LOD
    # chain) is rebuilt with the recipe's LOD arguments
    grew = [n for n in sorted(final_objs) if (final_objs[n].info.get("package_bytes") or 0) >
            (orig_objs[n].info.get("package_bytes") or 0)]
    if grew and "lod_args" in specs:
        ctx.log("  heap 4: %s grew with the Standard LOD chain; rebuilt with the recipe LOD args" % ", ".join(grew))
        redo = _final_packages(ctx, room, {k: v for k, v in specs.items() if k != "lod_args"}, subs, shell_dirs,
                               scales, chosen, vmin)
        for n in grew:
            final_objs[n] = redo[n]
    pk_final = load_pkgs(final_objs)
    if gs and _tree_rows(final_objs) != _tree_rows(base_objs):
        raise RuntimeError("%s: the final packages' grove clusters differ from the base packages'" % name)
    # what the staged packages cost (biases baked, runtime options only): the numbers reported
    inst_f = build_instances(pk_final, room.placements(), keyfn, trees=tree_table)
    opt_f = {k: [dict(id="final", bias=1.0, **{x: chosen[k][x] for x in ("imp_mm", "cull_mm", "split", "views")
                                               if chosen[k].get(x)})]
             for k in sorted({i["key"] for i in inst_f})}
    pr_f = price(inst_f, views, opt_f, cost, px=plan["px"], far=far, jobs=ctx.jobs)
    S_solver = S
    S = [sum(pr_f.ms[k][0][v] for k in opt_f) for v in range(nv)]
    T = [sum(pr_f.tris[k][0][v] for k in opt_f) for v in range(nv)]
    infeasible = [v for v in range(nv) if S[v] > budgets["scenery_ms_view_max"] + 1e-9 or
                  T[v] > budgets["scenery_tris_view_max"]]
    drift = max(abs(a - b) for a, b in zip(S, S_solver)) if nv else 0.0
    ctx.log("  staged packages priced: max |staged - solver| %.3f ms over %d views" % (drift, nv))
    # Original per view
    So = [sum(pr_o.ms[k][0][v] for k in keys_o) for v in range(nv)]
    To = [sum(pr_o.tris[k][0][v] for k in keys_o) for v in range(nv)]
    base_today = room_base_ms(cfg, name)
    base_plan = float(budgets.get("base_ms_planned", 2.5))
    rest = float(budgets.get("frame_rest_ms", 28.3))
    view_rows = []

    def top(pr, keys, i, n=6):
        rows = sorted(((pr.ms[k][0][i], k) for k in keys if pr.ms[k][0][i] > 0), reverse=True)[:n]
        return [[k, classes.get(k, "structure"), round(x, 3)] for x, k in rows]
    for i, v in enumerate(views):
        extra = {}
        if i < len(named):
            extra = dict(top_standard=top(pr_f, sorted(opt_f), i), top_original=top(pr_o, keys_o, i))
        view_rows.append(dict(name=v["name"], eye=list(v["eye"]), yaw=v["yaw"], pitch=v["pitch"], **extra,
                              standard=dict(assets_ms=round(S[i], 3), tris=T[i],
                                            scenery_ms_today=round(S[i] + base_today, 3),
                                            scenery_ms_planned=round(S[i] + base_plan, 3),
                                            frame_ms_est=round(rest + base_plan + S[i], 2)),
                              original=dict(assets_ms=round(So[i], 3), tris=To[i],
                                            scenery_ms_today=round(So[i] + base_today, 3),
                                            scenery_ms_planned=round(So[i] + base_plan, 3),
                                            frame_ms_est=round(rest + base_plan + So[i], 2)),
                              over_budget=i in infeasible))
    # sizes: heap 4 per owner, VRAM, disc
    shell_tex = []
    for b in sorted(shells):
        o = shells[b][0]
        shell_tex += [o.path(r) for r in sorted(o.outputs) if r.startswith("tex/")]
    used_imp = {_imp_key(k) for k in keys_s if chosen[k].get("imp_mm") and not chosen[k].get("split")}
    used_groves = {_imp_key(k) for k in keys_s if chosen[k].get("imp_mm") and chosen[k].get("split")}
    tree_files = sorted({Path(r["tex_file"]) for k in used_groves for r in grove_recs[k]})
    atlas_files = sorted({Path(imp_recs[k]["tex_file"]) for k in used_imp}) + tree_files
    sizes = _sizes(cfg, gen.room_tpl(room), orig_objs, final_objs, pk_orig, pk_final, shell_tex, atlas_files, imp_recs, used_imp)
    if used_groves:
        gv = sum({r["package"]: r["vram_bytes"] for k in used_groves for r in grove_recs[k]}.values())
        v = sizes["vram"]
        v.update(tree_atlases=gv, standard=v["standard"] + gv, delta=v["delta"] + gv)
    # assets list
    inv_by = {"%s/%s" % (r["owner"], bin_id(r["code"], r["bin"])): r for r in inv}
    assets = []
    for k in keys_s:
        o = chosen[k]
        i0 = choice[k]
        cls = classes.get(k, "structure")
        why = "solver: cheapest quality loss that keeps every view in budget" if i0 else "solver: best option fits"
        if cls == "house":
            bid = k.split("/")[1]
            ob, faces, err = shells[bid]
            why = "house shell %d faces (ladder %s, first with p90 error <= %g cm; got %.0f cm); %s" % (
                faces, plan["house_faces"], plan["house_err_cm"], err, why)
        assets.append(dict(id="%s/scenery/%s" % (name, k.split("/")[1]), key=k, **{"class": cls}, option=o["id"],
                           params={x: o[x] for x in ("geom", "bias", "imp_mm", "cull_mm", "err_floor", "split", "views")
                                   if x in o},
                           decided_by=why,
                           quality_loss=round(pr_s.quality[k][i0] * weights[k], 5),
                           predicted=dict(hw_ms_mean=round(sum(pr_s.ms[k][i0]) / nv, 4),
                                          hw_ms_max=round(max(pr_s.ms[k][i0]), 4),
                                          original_hw_ms_mean=round(sum(pr_o.ms[k][0]) / nv, 4) if k in pr_o.ms else 0.0,
                                          tris_max=max(pr_s.tris[k][i0])),
                           source=dict(tris=inv_by.get(k, {}).get("triangles"),
                                       radius_mm=inv_by.get(k, {}).get("radius_mm"))))
    grid_idx = range(len(named), nv)

    def dist(vals, idx):
        xs = [vals[i] for i in idx]
        return dict(p50=round(percentile(xs, 0.5), 3), p95=round(percentile(xs, 0.95), 3), max=round(max(xs), 3))
    summary = dict(standard=dict(assets_ms=dist(S, grid_idx), tris=dist(T, grid_idx),
                                 named_assets_ms_max=round(max(S[:len(named)]), 3)),
                   original=dict(assets_ms=dist(So, grid_idx), tris=dist(To, grid_idx),
                                 named_assets_ms_max=round(max(So[:len(named)]), 3)),
                   views=nv, views_over_budget=len(infeasible), solver_drift_ms=round(drift, 3),
                   over_budget=[views[i]["name"] for i in infeasible][:40])
    status = "OK" if not infeasible else "INFEASIBLE-%d-VIEWS" % len(infeasible)
    # staging (Standard set) + plan.json for the runtime
    out = cfg.root / "out" / "standard" / name
    if out.exists():
        shutil.rmtree(out)
    mesh = out / "mesh"
    for oname, obj in sorted(final_objs.items()):
        link_tree(obj, mesh, only=lambda rel: rel.endswith(".re4mesh"))
    tex_stage = [str(Path(p)) for p in orig["stage"].get("TEXDIRS", "").split()]
    d = out / "tex" / "20-shell"
    d.mkdir(parents=True)
    for f in shell_tex:
        os.link(f, d / Path(f).name)
    if atlas_files:
        d2 = out / "tex" / "30-impostor"
        d2.mkdir(parents=True)
        for f in atlas_files:
            os.link(f, d2 / Path(f).name)
        tex_stage.append(str(d2))
    tex_stage.append(str(d))
    plan_json = dict(schema="re4dc-standard-plan/1", room=name, lod_px=plan["px"],
                     bins={k: dict(**{"class": classes.get(k)}, **{x: chosen[k][x] for x in ("geom", "imp_mm", "cull_mm",
                                                                                               "split")
                                                                    if chosen[k].get(x)})
                           for k in keys_s if chosen[k].get("imp_mm") or chosen[k].get("cull_mm") or chosen[k].get("geom")})
    write_json(out / "plan.json", plan_json)
    # the disc side (s16): low/ (Standard files + index.txt + plan.json) and texlow/ (added textures)
    from . import stdindex
    from .config import TOOLS
    owners = [(o["name"], o["code"], bool(o["common"])) for o in room.owners() if o["name"] in final_objs]
    shell_rows = []
    for b in sorted(shells):
        shell_rows += json.loads(shells[b][0].path("textures.json").read_text())["textures"]
    disc_std = stdindex.write_low(
        out, name, plan["px"], owners, pk_final, {n: final_objs[n].path(n + ".re4mesh") for n, _, _ in owners},
        {n: orig_objs[n].path(n + ".re4mesh") for n, _, _ in owners}, pk_orig, plan_json["bins"],
        {k: imp_recs[k] for k in used_imp}, shell_rows, list(shell_tex) + list(atlas_files),
        stdindex.tpl_keys(gen.room_tpl(room), TOOLS), out / "plan.json",
        tree_recs={k: grove_recs[k] for k in used_groves})
    stage = {"STDROOMS": "%s=%s" % (name, out)}
    if room.recipe.get("stage", "MESHROOMS") == "MESHDIR":
        stage["MESHDIR"] = str(mesh)
    else:
        stage["MESHROOMS"] = "%s=%s" % (name, mesh)
    stage["TEXDIRS"] = " ".join(tex_stage)
    if "KEYED" in orig["stage"]:
        stage["KEYED"] = orig["stage"]["KEYED"]
    manifest = dict(schema="re4dc-assets/1", room=name, mode="standard", plan="budget",
                    lod_px=dict(standard=plan["px"], original=cost["lod"]["px"]),
                    config_sha256=canon_hash(cfg.cost), rooms_sha256=canon_hash(room.recipe),
                    converter=str(converter_dir(cfg, room).name), budgets=budgets, status=status,
                    original_manifest_sha256=orig["manifest_sha256"],
                    predicted=dict(base_ms_today=base_today, base_ms_planned=base_plan, frame_rest_ms=rest,
                                   summary=summary, sizes=sizes),
                    shells={b: dict(faces=shells[b][1], p90_cm=shells[b][2], step=shells[b][0].key,
                                    info=shells[b][0].info) for b in sorted(shells)},
                    disc_standard=disc_std, views=view_rows, assets=sorted(assets, key=lambda a: a["id"]),
                    steps=dict(**{"standard:" + n: o.key for n, o in sorted(final_objs.items())},
                               **{"shell:" + b: shells[b][0].key for b in sorted(shells)}),
                    stage=stage)
    if plan.get("_shell_rejected"):
        manifest["shell_rejected_p90_cm"] = dict(sorted(plan["_shell_rejected"].items()))
    ctxb = room.recipe.get("standard", {}).get("budget_context")
    if ctxb:
        manifest["budget_context"] = ctxb
    notes = room.recipe.get("standard", {}).get("review_notes")
    if notes:
        manifest["review_notes"] = list(notes)
    manifest["manifest_sha256"] = canon_hash({k: v for k, v in manifest.items() if k != "stage"})
    write_json(out / "manifest.json", manifest)
    env = "".join(': "${%s:=%s}"\nexport %s\n' % (k, v, k) for k, v in sorted(stage.items()))
    (out / "stage.env").write_text("# generated by tools/d367/assets.sh (%s standard); source before stage.sh\n%s" % (
        name, env))
    ctx.cache.save_memo()
    if review:
        variants = []
        used = sorted({f for _, f, _ in shells.values()})
        for faces in sorted(set(plan["house_faces"]) | set(plan.get("house_review_faces", []))):
            if not shells or faces in used:
                continue
            vsh = {}
            for bid in sorted(shells):
                code, b = bid.split(":")
                o = gen.house_shell(room, "%s_%d" % (names[int(code, 0)], int(b)), faces, plan["house_tex"])
                vsh[bid] = (o, faces, (o.info.get("source_to_shell_cm") or {}).get("p90"))
            vobjs = _final_packages(ctx, room, specs, subs, [Path(o.out) / "replace" for o, _, _ in
                                                             (vsh[b] for b in sorted(vsh))], scales, chosen, vmin)
            variants.append((faces, load_pkgs(vobjs), vsh))
        _review(ctx, room, manifest, named, pk_final, pk_orig, chosen, imp_recs, shells, out, variants)
    return manifest


def _tree_rows(objs):
    """{(owner, bin, common, part): [[first, count], ...]} from the packages' converter summaries."""
    out = {}
    for name, obj in sorted(objs.items()):
        summ = json.loads(obj.path(name + ".re4mesh.json").read_text())
        for m in summ.get("meshes_detail", []):
            for pi, p in enumerate(m["parts"]):
                if p.get("trees"):
                    out[(name, m["bin"], bool(m["common"]), pi)] = [[t["first"], t["clusters"]] for t in p["trees"]]
    return out


def _grove_trees(ctx, room, objs, gs):
    """Split groves of the base packages -> ({(code, bin): [tree record]}, tree table for
    build_instances). Records come from gen.grove_impostors (one atlas per tree)."""
    recs, table = {}, {}
    rows = _tree_rows(objs)
    codes = {o["name"]: o["code"] for o in room.owners()}
    for name in sorted({k[0] for k in rows}):
        groves = [(codes[name], b, cm, pi, trees) for (n, b, cm, pi), trees in sorted(rows.items()) if n == name]
        obj = ctx.gen.grove_impostors(room, name, objs[name], groves, int(gs.get("views", 8)), int(gs.get("cell", 128)),
                                      int(gs.get("ss", 4)), jobs=ctx.jobs or 1)
        man = json.loads(obj.path("impostors.json").read_text())
        for r in man["records"]:
            at = man["atlases"][r["atlas_name"]]
            recs.setdefault((r["code"], r["bin"]), []).append(dict(
                r, package=at["package"], vram_bytes=at["vram_bytes"], tex_file=str(obj.path("tex/" + at["package"]))))
            table.setdefault((name, r["bin"], bool(r["common"])), []).append(dict(
                part=r["part"], first=r["first"], count=r["count"], centre=r["centre"],
                radius=max(r["half_w"], r["half_h"])))
    return recs, table


def _imp_key(k):
    owner, bid = k.split("/")
    code, b = bid.split(":")
    return (int(code, 0), int(b))


def _impostor_records(ctx, room, plan=None, classes=None, orig_objs=None):
    """{(code, bin): record + image}: r100 from the item 20 Blender bake of its PS2 tree models
    (plan `impostors`: generators.tree_bake; without it the pinned 16-view bake); another room whose
    plan sets `impostors` from impostor.py (every tree-class BIN of the recipe package)."""
    if room.name == "r100" and plan and plan.get("impostors"):
        spec = plan["impostors"]
        d = ctx.gen.tree_bake(room, spec.get("views", 16), spec.get("cell", 128)).out
    elif room.name == "r100":
        try:
            d = ctx.cfg.path("r100_impostors")
        except KeyError:
            return {}
        if not d or not d.exists():
            return {}
    elif plan and plan.get("impostors") and classes and orig_objs:
        owners = {o["name"]: o for o in room.owners()}
        d = None
        recs = {}
        by_owner = {}
        for k, c in sorted(classes.items()):
            if c == "tree":
                owner, bid = k.split("/")
                code, b = _imp_key(k)
                by_owner.setdefault(owner, []).append((code, b, bool(owners[owner]["common"])))
        for owner, bins in sorted(by_owner.items()):
            spec = plan["impostors"]
            obj = ctx.gen.room_impostors(room, owner, orig_objs[owner], bins, spec.get("views", 16),
                                         spec.get("cell", 128), spec.get("ss", 4), jobs=ctx.jobs or 1)
            man = json.loads(obj.path("impostors.json").read_text())
            for r in man["records"]:
                at = man["atlases"][str(r["model"])]
                recs[(int(r["owner"], 0), r["bin"])] = dict(
                    r, package=at["package"], vram_bytes=at["vram_bytes"],
                    preview=str(obj.path("preview/%d.png" % r["model"])), tex_file=str(obj.path("tex/" + at["package"])))
        return recs
    else:
        return {}
    man = json.loads((d / "impostors.json").read_text())
    recs = {}
    for r in man["records"]:
        at = man["atlases"][str(r["model"])]
        rec = dict(r, package=at["package"], vram_bytes=at["vram_bytes"],
                   preview=str(d / "preview" / ("%d.png" % r["model"])), tex_file=str(d / "tex" / at["package"]))
        recs[(int(r["owner"], 0) if isinstance(r["owner"], str) else r["owner"], r["bin"])] = rec
    return recs


NEVER = 3.0e38      # an empty level Original never reaches: Standard never picks it either


def _vanish_min(room, pk_orig, px_std, px_orig):
    """{asset key: least stored error of a Standard empty LOD level}: the Original package's
    smallest empty-level error x px_std / px_orig, so an object vanishes no nearer than in
    Original; NEVER where Original has no empty level."""
    out = {}
    for o in room.owners():
        pk = pk_orig.get(o["name"])
        if pk is None:
            continue
        for (b, common), k in sorted(pk.mesh_by_bin().items()):
            errs = [e for p in pk.mesh_parts(k) for cl in pk.part_levels(p) for e, lets in cl["levels"] if not lets]
            out["%s/%s" % (o["name"], bin_id(o["code"], b))] = min(errs) * px_std / px_orig if errs else NEVER
    return out


def _guard(ctx, room, objs, vmin):
    """Apply the vanish guard (generators.vanish_guard) to every owner's package."""
    out = {}
    owners = {o["name"]: o for o in room.owners()}
    for n, obj in sorted(objs.items()):
        vm = {}
        for k, v in vmin.items():
            owner, bid = k.split("/")
            if owner == n:
                vm[(_imp_key(k)[1], bool(owners[n]["common"]))] = v
        out[n] = ctx.gen.vanish_guard(room, n, obj, vm) if vm else obj
    return out


def _final_packages(ctx, room, specs, subs, shell_dirs, scales, chosen, vmin=None):
    """Rebuild each owner with bias = recipe bias x chosen bias per BIN (then the vanish guard)."""
    rec = {}
    for s in specs.get("bias", []):
        o, rest = s.split(":")
        bins, f = rest.split("=")
        for b in parse_ranges(bins):
            rec[(int(o, 0), b)] = float(f)
    per = {}
    for k, o in chosen.items():
        code, b = _imp_key(k)
        f = rec.get((code, b), 1.0) * o.get("bias", 1.0)
        if abs(f - 1.0) > 1e-12:
            per.setdefault(code, {}).setdefault(round(f, 6), []).append(b)
    for (code, b), f in rec.items():
        if not any(_imp_key(k) == (code, b) for k in chosen):
            per.setdefault(code, {}).setdefault(round(f, 6), []).append(b)
    spec = {k: v for k, v in specs.items() if k != "bias"}
    spec["bias"] = []
    for code in sorted(per):
        oc = "0x%02x" % code if code >= 0xF0 else str(code)
        for f in sorted(per[code]):
            spec["bias"].append("%s:%s=%g" % (oc, ranges(sorted(set(per[code][f]))), f))
    objs = build_packages(ctx, room, spec, list(subs) + list(shell_dirs), scales)
    return _guard(ctx, room, objs, vmin) if vmin else objs


def _tex_vram(img_w, img_h, cost):
    """tex-vq5 rule: VQ when the padded 16-bit size reaches vq_min_bytes, else 16-bit."""
    raw = texture.vram_bytes("rgb16", img_w, img_h)
    return texture.vram_bytes("vq", img_w, img_h) if raw >= cost["texture"]["vq_min_bytes"] else raw


def _used_textures(pk):
    used = set()
    for p in pk.parts:
        if p[7] > 0:
            used.add(p[2])
            if p[4] & 4 and p[3] != 255:
                used.add(p[3])
    return used


def _sizes(cfg, tpl, orig_objs, final_objs, pk_orig, pk_final, shell_tex, atlas_files, imp_recs, used_imp):
    heap = {}
    for n in sorted(orig_objs):
        a = orig_objs[n].info.get("package_bytes") or 0
        b = final_objs[n].info.get("package_bytes") or 0
        heap[n] = dict(original=a, standard=b, delta=b - a)
    # VRAM: room TPL images referenced by drawing parts + added shell/atlas textures
    dims = []
    if tpl is not None:
        from .config import TOOLS
        import sys
        sys.path.insert(0, str(TOOLS))
        import convert_tpl
        dims = [(im.width, im.height) for im in convert_tpl.parse_tpl(tpl.read_bytes())]
    uo, us = set(), set()
    for pk in pk_orig.values():
        uo |= _used_textures(pk)
    for pk in pk_final.values():
        us |= _used_textures(pk)
    vo = sum(_tex_vram(*dims[i], cfg.cost) for i in sorted(uo) if i < len(dims))
    vs = sum(_tex_vram(*dims[i], cfg.cost) for i in sorted(us) if i < len(dims))
    shell_v = sum(texture.read_re4tex(f)["vram_bytes"] for f in shell_tex)
    atlas_v = sum({imp_recs[k]["package"]: imp_recs[k]["vram_bytes"] for k in used_imp}.values())
    vram = dict(original=vo, standard=vs + shell_v + atlas_v, room_textures_dropped=sorted(uo - us),
                shells=shell_v, impostor_atlases=atlas_v)
    vram["delta"] = vram["standard"] - vram["original"]
    # disc: the two sets' files by content; cost of carrying the second (Original) set
    std_files = {}
    for n, o in final_objs.items():
        std_files[o.outputs[n + ".re4mesh"]] = o.path(n + ".re4mesh").stat().st_size
    for f in list(shell_tex) + list(atlas_files):
        from .util import sha256_file
        std_files[sha256_file(f)] = Path(f).stat().st_size
    orig_files = {}
    for n, o in orig_objs.items():
        orig_files[o.outputs[n + ".re4mesh"]] = o.path(n + ".re4mesh").stat().st_size
    second = sum(sz for h, sz in orig_files.items() if h not in std_files)
    disc = dict(standard_set_bytes=sum(std_files.values()), original_set_bytes=sum(orig_files.values()),
                second_set_bytes=second, shared_bytes=sum(sz for h, sz in orig_files.items() if h in std_files))
    return dict(heap4=heap, heap4_ok=all(v["delta"] <= 0 for v in heap.values()), vram=vram, disc=disc)


# ---------------------------------------------------------------------------- review sheet
def _review(ctx, room, man, named, pk_final, pk_orig, chosen, imp_recs, shells, out_dir, variants=()):
    global _R
    cfg = ctx.cfg
    name = room.name
    rev = cfg.root / "review" / "standard" / name
    if rev.exists():
        shutil.rmtree(rev)
    (rev / "img").mkdir(parents=True)
    tex = _textures(ctx, room, shells, imp_recs)
    codes = {o["name"]: o["code"] for o in room.owners()}
    placements = room.placements()
    b_std = SceneBuilder(pk_final, placements, codes, cfg.cost, tex, _imp_images(imp_recs))
    b_org = SceneBuilder(pk_orig, placements, codes, cfg.cost, tex, {})
    std_opts = {k: {x: o[x] for x in ("imp_mm", "cull_mm") if o.get(x)} for k, o in chosen.items()}
    px_s = cfg.cost["plan"]["standard"]["px"]
    px_o = cfg.cost["lod"]["px"]
    far = cfg.cost["lod"]["fog_far_mm"]
    jobs = []
    for v in named:
        jobs.append((v["name"], "standard", v, std_opts, px_s))
        jobs.append((v["name"], "original", v, {}, px_o))
    builders = dict(standard=b_std, original=b_org)
    for faces, vpk, vsh in variants:
        mode = "standard-f%d" % faces
        builders[mode] = SceneBuilder(vpk, placements, codes, cfg.cost, _textures(ctx, room, vsh, imp_recs),
                                      _imp_images(imp_recs))
        for v in named:
            if v["name"].startswith("house_"):
                jobs.append((v["name"], mode, v, std_opts, px_s))
    _R = (jobs, builders, cfg.cost, far)
    n = min(len(jobs), ctx.jobs or os.cpu_count() or 1)
    try:
        with ProcessPoolExecutor(n, mp_context=multiprocessing.get_context("fork")) as ex:
            res = list(ex.map(_render_job, range(len(jobs))))
    finally:
        _R = None
    counts = {}
    for (vn, mode, _, _, _), (png, cnt) in zip(jobs, res):
        (rev / "img" / ("%s-%s.png" % (vn, mode))).write_bytes(png)
        counts[(vn, mode)] = cnt
    for v in named:
        if v.get("frame"):
            src = cfg.path("evidence") / v["frame"]
            if src.exists():
                shutil.copyfile(src, rev / "img" / ("%s-flycast.png" % v["name"]))
    vinfo = [(faces, {b: dict(p90_cm=e, info=o.info) for b, (o, f, e) in vsh.items()}) for faces, _, vsh in variants]
    (rev / "index.html").write_text(_html(man, named, counts, rev, vinfo))
    write_json(rev / "review.json", dict(manifest_sha256=man["manifest_sha256"],
                                         counts={"%s/%s" % k: v for k, v in sorted(counts.items())}))
    ctx.log("  review: %s" % (rev / "index.html"))


def _textures(ctx, room, shells, imp_recs):
    from .config import TOOLS
    imgs = texture.tpl_images(ctx.gen.room_tpl(room), TOOLS)
    by_index = {}
    if room.recipe.get("trees", {}).get("bark_png"):
        bark = ctx.gen.ps2_bark(room)
        prev = bark.path("preview/ps2-bark-vq.png")
        if prev.exists():
            by_index[0] = texture.png_read(prev)
    by_part = {}
    for bid, (obj, faces, err) in shells.items():
        man = json.loads(obj.path("textures.json").read_text())
        for r in man["textures"]:
            key = "%s_%d" % ({0xFF: "MAINSCENARIO", 0xFE: "COMMON"}.get(r["owner"], "FILE_%02d" % r["owner"]), r["bin"])
            by_part[(r["owner"], r["bin"], r["part"])] = texture.png_read(obj.path("preview/%s.png" % key))
    return Textures(imgs, by_index, by_part)


def _imp_images(recs):
    out = {}
    cache = {}
    for k, r in recs.items():
        p = r["preview"]
        if p not in cache:
            cache[p] = texture.png_read(p)
        out[k] = dict(r, image=cache[p])
    return out


CSS = """
:root{--bg:#f6f5f2;--fg:#1d1d1b;--mut:#6b6a66;--card:#fff;--line:#dedcd6;--good:#1f7a3a;--bad:#b3261e;--acc:#2d5b8a}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe7;--mut:#a3a19b;--card:#21211f;--line:#383733;--good:#6fcf8a;--bad:#ff8a80;--acc:#8ab4e0;color-scheme:dark}}
:root[data-theme=dark]{--bg:#161615;--fg:#ecebe7;--mut:#a3a19b;--card:#21211f;--line:#383733;--good:#6fcf8a;--bad:#ff8a80;--acc:#8ab4e0;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0}
main{max-width:1500px;margin:0 auto;padding:16px}
h1,h2,h3{text-wrap:balance}td,th{font-variant-numeric:tabular-nums}
h1{font-size:22px;margin:4px 0}h2{font-size:17px;margin:28px 0 8px}h3{font-size:15px;margin:0 0 6px}
.mut{color:var(--mut)}.good{color:var(--good)}.bad{color:var(--bad)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}
.tile b{font-size:19px;display:block}
.view{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0}
.pics{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.pics figure{margin:0}.pics img{width:100%;height:auto;border-radius:4px;display:block;image-rendering:auto}
figcaption{font-size:13px;margin-top:4px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:right}
th:first-child,td:first-child{text-align:left}th{color:var(--mut);font-weight:600}
.scroll{overflow-x:auto}
"""


def _html(man, named, counts, rev, variants=()):
    from html import escape
    p = man["predicted"]
    sm, sz = p["summary"], p["sizes"]
    rows = {v["name"]: v for v in man["views"]}
    b = man["budgets"]

    def ms(x):
        return "%.2f" % x

    def verdict(v):
        return '<span class="good">in budget</span>' if not v["over_budget"] else '<span class="bad">over budget</span>'
    # page contract of the Artifact viewer: title and style first, no html/head/body wrapper (browsers
    # opening the file locally accept the same markup)
    h = ["<meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>%s Standard vs Original</title><style>%s</style><main>" % (escape(man["room"]), CSS)]
    h.append("<h1>%s: Standard (default) vs Original</h1>" % escape(man["room"]))
    h.append("<p class=mut>Identical cameras for both modes. <b>Standard (default)</b> = budget-first Dreamcast-native "
             "look (LOD px %g, baked house shells, tree impostors, clutter culling; per asset chosen by the solver). "
             "<b>Original</b> = the faithful recipe packages (LOD px %g). Pictures are the pipeline's software "
             "render of exactly what each mode draws at that view (same textures, lighting and 25 m fog for both)%s.</p>"
             % (man["lod_px"]["standard"], man["lod_px"]["original"],
                "; the spawn view also shows the real game's frame at that camera (Flycast, scenery-trials arm C) to "
                "check the render against" if any(v.get("frame") for v in named) else ""))
    h.append("<div class=tiles>")
    tiles = [
        ("Standard scenery assets, worst named view", "%s hw ms" % ms(sm["standard"]["named_assets_ms_max"]),
         "budget %s ms excl. base" % ms(b["scenery_ms_view_max"])),
        ("Original scenery assets, worst named view", "%s hw ms" % ms(sm["original"]["named_assets_ms_max"]), ""),
        ("Standard grid p95 / max", "%s / %s ms" % (ms(sm["standard"]["assets_ms"]["p95"]), ms(sm["standard"]["assets_ms"]["max"])),
         "%d views, %d over budget" % (sm["views"], sm["views_over_budget"])),
        ("Original grid p95 / max", "%s / %s ms" % (ms(sm["original"]["assets_ms"]["p95"]), ms(sm["original"]["assets_ms"]["max"])), ""),
        ("Triangles per view, max (grid)", "%d vs %d" % (sm["standard"]["tris"]["max"], sm["original"]["tris"]["max"]),
         "Standard vs Original; budget %d" % b["scenery_tris_view_max"]),
        ("Heap 4 (scenery packages)", "%+d B" % sum(v["delta"] for v in sz["heap4"].values()),
         "Standard minus Original; %s" % ("every file <= Original" if sz["heap4_ok"] else "SOME FILE LARGER")),
        ("VRAM", "%+d KB" % round(sz["vram"]["delta"] / 1024), "shells %d KB, atlases %d KB" % (
            round(sz["vram"]["shells"] / 1024), round(sz["vram"]["impostor_atlases"] / 1024))),
        ("Disc: second set (Original)", "%.2f MB" % (sz["disc"]["second_set_bytes"] / 1e6),
         "extra bytes to ship Original next to Standard"),
    ]
    for t, v, s in tiles:
        h.append("<div class=tile><span class=mut>%s</span><b>%s</b><span class=mut>%s</span></div>" % (
            escape(t), escape(v), escape(s)))
    h.append("</div>")
    bc = man.get("budget_context")
    if bc:
        dh = sum(v["delta"] for v in sz["heap4"].values())
        h.append("<h2>Against the route memory budgets</h2><div class=scroll><table><tr><th>heap 4 case</th>"
                 "<th>Original free</th><th>Standard free</th><th>vs margin %d KB</th>%s</tr>" % (
                     bc.get("heap4_margin_kb", 0), "<th>vs gate %d KB</th>" % bc["heap4_gate_kb"]
                     if bc.get("heap4_gate_kb") else ""))
        for c in bc.get("heap4", []):
            lo, hi = c["original_free_kb"]
            slo, shi = lo - dh / 1024.0, hi - dh / 1024.0

            def rng(a, b_):
                return "%+.0f KB" % a if abs(a - b_) < 0.5 else "%+.0f to %+.0f KB" % (a, b_)

            def ok(x):
                return "good" if x >= 0 else "bad"
            m = bc.get("heap4_margin_kb", 0)
            g = bc.get("heap4_gate_kb")
            h.append("<tr><td style='text-align:left'>%s</td><td>%s</td><td><b>%s</b></td><td class=%s>%s</td>%s</tr>" % (
                escape(c["case"]), rng(lo, hi), rng(slo, shi), ok(slo - m), rng(slo - m, shi - m),
                "<td class=%s>%s</td>" % (ok(slo - g), rng(slo - g, shi - g)) if g else ""))
        h.append("</table></div>")
        v = bc.get("vram")
        if v:
            used_s = v["original_used"] + sz["vram"]["delta"]
            h.append("<p>VRAM pool %d KB: Original uses %d KB (%s), Standard <b>%d KB</b> (%+d KB: shells %d, "
                     "impostor atlases %d, room textures no longer drawn %s), <span class=%s>%d KB free</span>.</p>" % (
                         v["pool"] // 1024, v["original_used"] // 1024, escape(v["source"]), used_s // 1024,
                         round(sz["vram"]["delta"] / 1024), round(sz["vram"]["shells"] / 1024),
                         round(sz["vram"]["impostor_atlases"] / 1024),
                         ", ".join(str(i) for i in sz["vram"]["room_textures_dropped"]) or "none",
                         "good" if used_s <= v["pool"] else "bad", (v["pool"] - used_s) // 1024))
        if bc.get("note"):
            h.append("<p class=mut>%s</p>" % escape(bc["note"]))
    if man.get("review_notes"):
        h.append("<div class=view><h3>This room</h3><ul>%s</ul></div>" % "".join(
            "<li>%s</li>" % escape(x) for x in man["review_notes"]))
    h.append("<p class=mut>Frame estimate per view = rest of frame %.1f ms (design-lowmode D2 floor: everything "
             "but scenery at 30 fps) + scenery base %.1f ms (planned after design-scenery S1-S5; today %.1f) + "
             "scenery assets. Target 33.3 ms (30 fps). The same rest-of-frame is used for both modes, so the "
             "difference is scenery only.</p>" % (p["frame_rest_ms"], p["base_ms_planned"], p["base_ms_today"]))
    nin = sm["views"] - sm["views_over_budget"]
    h.append("<div class=view><h3>Reading this sheet</h3><ul>"
             "<li>Standard fits the %.0f ms scenery-asset budget at <b>%d of %d</b> priced views (ground grid "
             "every %d x %d cells, 8 headings, plus the named views below); the rest are listed as over budget "
             "with their largest costs.</li>"
             "<li>Asset ms exclude the fixed scenery base (%.1f ms today, %.1f planned), which is runtime work in "
             "both modes.</li>"
             "<li>Houses: the shell ladder picks the first face count whose p90 error is within the limit; the "
             "house views also show the rejected lower rungs, so the 'few dozen polygons' request can be judged "
             "by eye.</li>"
             "<li>Disc: every Standard package differs from Original because the chosen LOD biases are baked in "
             "(D367_ASSET_PIPELINE.md section 15 weighs a runtime per-BIN table instead).</li>"
             "<li>No object vanishes nearer in Standard than in Original: an empty LOD level keeps at least "
             "Original's vanish distance (the vanish guard).</li></ul></div>" % (
                 b["scenery_ms_view_max"], nin, sm["views"], 6, 6, p["base_ms_today"], p["base_ms_planned"]))
    h.append("<h2>Views</h2>")
    for v in named:
        r = rows[v["name"]]
        s, o = r["standard"], r["original"]
        cs, co = counts.get((v["name"], "standard"), {}), counts.get((v["name"], "original"), {})
        h.append("<div class=view><h3>%s %s</h3>" % (escape(v["name"]), verdict(r)))
        h.append("<div class=pics>")
        h.append("<figure><img src='img/%s-standard.png' alt='Standard'><figcaption><b>Standard (default)</b>: "
                 "assets %s ms, %d tris, frame est. %s ms</figcaption></figure>" % (
                     escape(v["name"]), ms(s["assets_ms"]), s["tris"], ms(s["frame_ms_est"])))
        h.append("<figure><img src='img/%s-original.png' alt='Original'><figcaption><b>Original</b>: "
                 "assets %s ms, %d tris, frame est. %s ms</figcaption></figure>" % (
                     escape(v["name"]), ms(o["assets_ms"]), o["tris"], ms(o["frame_ms_est"])))
        for faces, vi in variants:
            if (v["name"], "standard-f%d" % faces) in counts:
                c = counts[(v["name"], "standard-f%d" % faces)]
                h.append("<figure><img src='img/%s-standard-f%d.png' alt='shell %d'><figcaption>Standard with "
                         "%d-face house shells (%s; not staged): %d tris drawn</figcaption></figure>" % (
                             escape(v["name"]), faces, faces, faces,
                             ", ".join("%s p90 %s cm" % (b, x["p90_cm"]) for b, x in sorted(vi.items())), c["tris"]))
        if (rev / "img" / ("%s-flycast.png" % v["name"])).exists():
            h.append("<figure><img src='img/%s-flycast.png' alt='Flycast'><figcaption>Flycast frame at this camera "
                     "(real game, arm C recipe; Leon and HUD included)</figcaption></figure>" % escape(v["name"]))
        h.append("</div><div class=scroll><table><tr><th></th><th>assets hw ms</th><th>scenery today (base %.1f)</th>"
                 "<th>scenery planned (base %.1f)</th><th>frame est. vs 33.3</th><th>tris</th><th>drawn records</th>"
                 "<th>impostors</th><th>objects</th></tr>" % (p["base_ms_today"], p["base_ms_planned"]))
        for label, x, c in (("Standard (default)", s, cs), ("Original", o, co)):
            fe = x["frame_ms_est"]
            h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class=%s>%s</td><td>%d</td><td>%s</td>"
                     "<td>%s</td><td>%s</td></tr>" % (
                         label, ms(x["assets_ms"]), ms(x["scenery_ms_today"]), ms(x["scenery_ms_planned"]),
                         "good" if fe <= 33.3 else "bad", ms(fe), x["tris"], c.get("records", ""), c.get("imps", ""),
                         c.get("objects", "")))
        h.append("</table></div>")
        for label, key in (("Standard", "top_standard"), ("Original", "top_original")):
            if r.get(key):
                h.append("<p class=mut>%s, largest asset costs here: %s</p>" % (label, escape(", ".join(
                    "%s (%s) %.2f" % (k, c, x) for k, c, x in r[key]))))
        h.append("<p class=mut>eye %s, yaw %.1f, pitch %.1f</p></div>" % (
            tuple(round(e) for e in v["eye"]), v["yaw"], v["pitch"]))
    # asset decisions
    h.append("<h2>Standard decisions per asset</h2><div class=scroll><table><tr><th>asset</th><th>class</th>"
             "<th>option</th><th>hw ms mean (Std / Orig)</th><th>max tris</th><th>decided by</th></tr>")
    for a in sorted(man["assets"], key=lambda a: -a["predicted"]["original_hw_ms_mean"]):
        h.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%.3f / %.3f</td><td>%d</td><td style='text-align:left'>%s</td></tr>" % (
            escape(a["key"]), a["class"], escape(a["option"]), a["predicted"]["hw_ms_mean"],
            a["predicted"]["original_hw_ms_mean"], a["predicted"]["tris_max"], escape(a["decided_by"])))
    h.append("</table></div>")
    # sizes
    h.append("<h2>Memory and disc</h2><div class=scroll><table><tr><th>package</th><th>Original B</th>"
             "<th>Standard B</th><th>delta</th></tr>")
    for n, v in sorted(sz["heap4"].items()):
        h.append("<tr><td>%s</td><td>%d</td><td>%d</td><td class=%s>%+d</td></tr>" % (
            n, v["original"], v["standard"], "good" if v["delta"] <= 0 else "bad", v["delta"]))
    d = sz["disc"]
    h.append("</table></div><p>Disc: Standard set %.2f MB, Original set %.2f MB, shared %.2f MB; shipping both costs "
             "<b>%.2f MB</b> more than Standard alone. VRAM: Original %d KB, Standard %d KB (room textures no "
             "longer drawn: %s).</p>" % (
                 d["standard_set_bytes"] / 1e6, d["original_set_bytes"] / 1e6, d["shared_bytes"] / 1e6,
                 d["second_set_bytes"] / 1e6, round(sz["vram"]["original"] / 1024), round(sz["vram"]["standard"] / 1024),
                 ", ".join(str(i) for i in sz["vram"]["room_textures_dropped"]) or "none"))
    h.append("<h2>Houses</h2><table><tr><th>BIN</th><th>faces requested</th><th>shell tris</th><th>alpha tris</th>"
             "<th>p90 source to shell cm</th><th>p90 shell to source cm</th></tr>")
    for bid, sh in sorted(man["shells"].items()):
        i = sh["info"]
        h.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            bid, sh["faces"], i.get("shell_triangles"), i.get("alpha_triangles"),
            (i.get("source_to_shell_cm") or {}).get("p90"), (i.get("shell_to_source_cm") or {}).get("p90")))
    h.append("</table><p class=mut>manifest %s (Standard), %s (Original)</p></main>" % (
        man["manifest_sha256"][:16], man["original_manifest_sha256"][:16]))
    return "\n".join(h)
