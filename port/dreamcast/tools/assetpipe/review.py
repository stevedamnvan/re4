"""Per-room review sheet: before (source) / after (chosen) renders at 3, 8, 20 m,
counts, bytes, predicted hw ms and the rule that decided each asset.

Renders are deterministic (raster.py) and cached per (package, BIN, distance) key.
The page is static HTML with relative image paths and no timestamps.
"""
import html
import math
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import raster
from .cache import fingerprint
from .camera import screen_k
from .rooms import placement_matrix, bin_id
from .util import dumps

DISTANCES_MM = (3000.0, 8000.0, 20000.0)
AZIMUTH_DEG = 35.0
LARGE_MM = 15000.0
W, H = 320, 240


def _xf(M, p):
    return tuple(M[r][0] * p[0] + M[r][1] * p[1] + M[r][2] * p[2] + M[r][3] for r in range(3))


def _nx(M, n):
    v = [M[r][0] * n[0] + M[r][1] * n[1] + M[r][2] * n[2] for r in range(3)]
    l = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / l for x in v)


def _box(pkg, k, M, lo, hi):
    m = pkg.meshes[k]
    origin, step = m[8:11], m[11:14]
    c = [origin[a] + (lo[a] + hi[a]) * 0.5 * step[a] for a in range(3)]
    e = [(hi[a] - lo[a]) * 0.5 * step[a] for a in range(3)]
    wc = [sum(M[r][q] * c[q] for q in range(3)) + M[r][3] for r in range(3)]
    we = [sum(abs(M[r][q]) * e[q] for q in range(3)) for r in range(3)]
    return wc, we


def _mesh_box(pkg, k, M):
    m = pkg.meshes[k]
    origin, step, lo, hi = m[8:11], m[11:14], m[14:17], m[17:20]
    glo = [(lo[a] - origin[a]) / step[a] for a in range(3)]
    ghi = [(hi[a] - origin[a]) / step[a] for a in range(3)]
    return _box(pkg, k, M, glo, ghi)


def views_for(pkg, k, w, worst_view=None):
    """[(label, eye, target)] for an asset: 3/8/20 m from its box at eye height, or,
    for assets larger than 15 m (terrain), its worst room view plus 2 more yaws."""
    M = placement_matrix(w)
    c, e = _mesh_box(pkg, k, M)
    rh = math.hypot(e[0], e[2])
    ground = c[1] - e[1]
    if rh > LARGE_MM and worst_view is not None:
        eye = tuple(worst_view["eye"])
        out = []
        for i, dy in enumerate((0.0, -45.0, 45.0)):
            yaw = math.radians(worst_view["yaw"] + dy)
            tgt = (eye[0] + math.sin(yaw) * 10000.0, eye[1] - 400.0, eye[2] + math.cos(yaw) * 10000.0)
            out.append(("worst view%s" % ("" if not dy else " %+d deg" % dy), eye, tgt))
        return out
    az = math.radians(AZIMUTH_DEG)
    out = []
    for d in DISTANCES_MM:
        eye = (c[0] + math.sin(az) * (rh + d), ground + 1600.0, c[2] + math.cos(az) * (rh + d))
        tgt = (c[0], min(c[1], ground + 1600.0 + 0.3 * e[1]), c[2])
        out.append(("%d m" % round(d / 1000), eye, tgt))
    return out


def triangles(pkg, k, M, view, px, K, runtime_choice):
    """World-space triangles of mesh k: all of level 0 (source), or the runtime's
    per-cluster level at this camera (after)."""
    scale = max(math.sqrt(sum(M[r][a] ** 2 for r in range(3))) for a in range(3))

    def choose(cl, levels):
        if not runtime_choice or cl["lo"] is None:
            return 0
        c, e = _box(pkg, k, M, cl["lo"], cl["hi"])
        z = view.depth_of_box(c, e)
        pick = 0
        for li, (err, _) in enumerate(levels):
            if err * scale * K / z <= px:
                pick = li
        return pick
    tris = pkg.level_triangles(k, None, choose=choose)
    return [(_xf(M, a), _xf(M, b), _xf(M, c), _nx(M, na), _nx(M, nb), _nx(M, nc), p)
            for a, b, c, na, nb, nc, p in tris]


_JOB = None


def _render_job(i):
    pkgs, jobs, px, K = _JOB
    pkg_name, k, w, label, eye, tgt, runtime = jobs[i]
    pkg = pkgs[pkg_name]
    M = placement_matrix(w)
    view = raster.View(eye, tgt, W, H)
    tris = triangles(pkg, k, M, view, px, K, runtime)
    png, drawn = raster.render(view, tris)
    return png, len(tris), drawn


def review_room(ctx, room, manifest, pk_built, pk_reset, views, out):
    cfg, cache = ctx.cfg, ctx.cache
    rev = cfg.root / "review" / manifest["mode"] / room.name
    img = rev / "img"
    img.mkdir(parents=True, exist_ok=True)
    K = screen_k(cfg.cost)
    px = cfg.cost["lod"]["px"]
    fp = fingerprint([Path(raster.__file__), Path(__file__)])
    first = {}
    for w in room.placements():
        first.setdefault("%s/%s" % (w["owner"], bin_id(w["code"], w["bin"])), w)
    worst = {}
    vmax = max(range(len(views)), key=lambda i: manifest["views"][i]["ms"]) if views else None
    pkgs = {}
    jobs, keys, meta = [], [], []
    for a in manifest["assets"]:
        if a["class"] == "texture" or a.get("key") not in first:
            continue
        w = first[a["key"]]
        ref = pk_reset.get(w["owner"])
        rk = ref.mesh_by_bin().get((w["bin"], bool(w["common"]))) if ref else None
        if rk is None:
            continue
        # one camera set per asset, from the source box, used for both sides
        cams = views_for(ref, rk, w, views[vmax] if vmax is not None else None)
        for side, pmap in (("before", pk_reset), ("after", pk_built)):
            pkg = pmap[w["owner"]]
            k = pkg.mesh_by_bin().get((w["bin"], bool(w["common"])))
            if k is None:
                continue
            pname = "%s:%s" % (side, w["owner"])
            pkgs[pname] = pkg
            for label, eye, tgt in cams:
                pkg_hash = a["outputs"].get(w["owner"] + ".re4mesh") if side == "after" else \
                    manifest["steps"].get("reset:" + w["owner"])
                params = dict(side=side, owner=w["owner"], bin=w["bin"], work=w.get("work"), label=label,
                              eye=eye, tgt=tgt, px=px, W=W, H=H)
                key, _ = cache.key("review.render", params, {"pkg": "sha256:%s" % pkg_hash}, fp)
                jobs.append((pname, k, w, label, eye, tgt, side == "after"))
                keys.append((key, params, pkg_hash))
                meta.append((a["id"], side, label))
    # --verify rebuilds cached shots too, so every one of them is rendered again here
    todo = [i for i, (key, _, _) in enumerate(keys)
            if cache.verify or not (cache.objects / key[:2] / key / "step.json").exists()]
    global _JOB
    _JOB = (pkgs, jobs, px, K)
    results = {}
    try:
        if todo:
            ctx.log("  review: rendering %d images (%d cached)" % (len(todo), len(jobs) - len(todo)))
            n = min(len(todo), ctx.jobs or os.cpu_count() or 1)
            if n > 1:
                with ProcessPoolExecutor(n, mp_context=multiprocessing.get_context("fork")) as ex:
                    for i, r in zip(todo, ex.map(_render_job, todo)):
                        results[i] = r
            else:
                for i in todo:
                    results[i] = _render_job(i)
    finally:
        _JOB = None
    shots = {}
    for i, (key, params, pkg_hash) in enumerate(keys):
        def fn(o, work, i=i):
            png, ntri, drawn = results[i]
            (o / "shot.png").write_bytes(png)
            return dict(triangles=ntri, pixels=drawn)
        obj = cache.step("review.render", params, {"pkg": "sha256:%s" % pkg_hash}, fp, fn,
                         label="render %s" % meta[i][0])
        aid, side, label = meta[i]
        name = "%s-%s-%s.png" % (aid.split("/", 1)[1].replace("/", "_").replace(":", "-"), side,
                                 label.replace(" ", "").replace("+", "p").replace("-", "m"))
        t = img / name
        if t.exists():
            t.unlink()
        try:
            os.link(obj.path("shot.png"), t)
        except OSError:
            t.write_bytes(obj.path("shot.png").read_bytes())
        shots.setdefault(aid, {}).setdefault(label, {})[side] = (name, obj.info.get("triangles"))
    page = render_html(manifest, shots)
    (rev / "index.html").write_text(page)
    (rev / "review.json").write_text(dumps(dict(room=room.name, mode=manifest["mode"],
                                                manifest_sha256=manifest["manifest_sha256"], shots=shots)))
    ctx.log("  review: %s" % (rev / "index.html"))
    return rev / "index.html"


CSS = """
:root{--bg:#f6f7f9;--fg:#1d232b;--mut:#5d6773;--line:#d9dde3;--card:#fff;--ok:#1a7f37;--bad:#b42318;--acc:#2f5fb3}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--fg:#e6e9ee;--mut:#98a2ae;--line:#2c3138;--card:#1b1f24;--ok:#4cc36b;--bad:#ff7b72;--acc:#7aa7ff}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}
.sum{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.k{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}
.k b{display:block;font-size:18px}.k span{color:var(--mut);font-size:12px}
table{border-collapse:collapse;width:100%;background:var(--card)}
td,th{border-bottom:1px solid var(--line);padding:6px;vertical-align:top;text-align:left}
th{position:sticky;top:0;background:var(--card);font-size:12px;color:var(--mut)}
.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.pair{display:flex;gap:4px}.pair figure{margin:0}.pair img{width:160px;height:120px;image-rendering:pixelated;border:1px solid var(--line)}
figcaption{font-size:11px;color:var(--mut)}
.ok{color:var(--ok)}.bad{color:var(--bad)}.why{font-size:12px;color:var(--mut);max-width:260px}
.wrap{overflow-x:auto}
"""


def _k(label, value, sub=""):
    return '<div class="k"><span>%s</span><b>%s</b><span>%s</span></div>' % (
        html.escape(label), html.escape(str(value)), html.escape(sub))


def render_html(m, shots):
    p = m["predicted"]
    s, r = p["scenery"], p["reset_scenery"]
    b = m["budgets"].get("scenery_ms_p95")
    out = ["<!doctype html><html lang=en><head><meta charset=utf-8>",
           "<meta name=viewport content='width=device-width,initial-scale=1'>",
           "<title>%s asset review</title><style>%s</style></head><body>" % (html.escape(m["room"]), CSS),
           "<h1>%s: asset review (%s, plan %s)</h1>" % (html.escape(m["room"]), m["mode"], m["plan"]),
           "<div class=why>manifest %s &middot; config %s &middot; status <b class=%s>%s</b></div>" % (
               m["manifest_sha256"][:16], m["config_sha256"][:12], "ok" if m["status"] == "OK" else "bad",
               m["status"]),
           '<div class="sum">',
           _k("scenery p95 (hw ms)", s["ms_p95"], "budget %s; source %s" % (b, r["ms_p95"])),
           _k("scenery mean", s["ms_mean"], "source %s" % r["ms_mean"]),
           _k("scenery max", s["ms_max"], "source %s" % r["ms_max"]),
           _k("fixed base_ms", p["base_ms"], "not reachable by assets"),
           _k("TA bytes max", s["ta_bytes_max"], "budget %s" % m["budgets"].get("ta_bytes_max", "-")),
           _k("heap 4 (packages)", p["heap4_bytes"], "source %s" % p["heap4_reset_bytes"]),
           _k("texture VRAM (overlays)", p["vram_bytes"], ""),
           _k("views", s["views"], "grid x yaws, eye 1.6 m, fog %g m" % 25),
           "</div>"]
    if m.get("checks"):
        out.append("<div class=why>checks: %s</div>" % html.escape(", ".join("%s=%s" % kv for kv in
                                                                             sorted(m["checks"].items()))))
    rows = [a for a in m["assets"] if a["class"] != "texture"]
    rows.sort(key=lambda a: (-(a["predicted"]["reset_hw_ms_mean"] - a["predicted"]["hw_ms_mean"]), a["id"]))
    out.append("<h2>Meshes (%d), sorted by predicted hw ms saved</h2><div class=wrap><table>" % len(rows))
    out.append("<tr><th>asset</th><th>decided by</th><th class=num>tris src/L0..</th>"
               "<th class=num>hw ms mean<br>src &rarr; now</th><th class=num>p95</th><th>3 m / 8 m / 20 m "
               "(source | chosen)</th></tr>")
    for a in rows:
        pr = a["predicted"]
        lv = " / ".join(str(x["tris"]) for x in a.get("levels", []))
        sh = shots.get(a["id"], {})
        figs = []
        for label in sorted(sh, key=lambda x: (len(x), x)):
            pair = sh[label]
            cells = []
            for side in ("before", "after"):
                if side in pair:
                    name, nt = pair[side]
                    cells.append("<figure><img loading=lazy src='img/%s' alt='%s %s'><figcaption>%s %s, %s tris"
                                 "</figcaption></figure>" % (name, side, label, "src" if side == "before" else "now",
                                                              html.escape(label), nt))
            figs.append("<div class=pair>%s</div>" % "".join(cells))
        out.append("<tr><td><b>%s</b><br><span class=why>%s &middot; %s inst &middot; r %s m</span></td>"
                   "<td class=why>%s</td><td class=num>%s<br><span class=why>%s</span></td>"
                   "<td class=num>%.3f &rarr; <b>%.3f</b></td><td class=num>%.3f &rarr; %.3f</td><td>%s</td></tr>" % (
                       html.escape(a["id"]), html.escape(a["class"]), a["source"].get("instances"),
                       round((a["source"].get("radius_mm") or 0) / 1000, 1), html.escape(a["decided_by"]),
                       a["source"].get("tris"), lv, pr["reset_hw_ms_mean"], pr["hw_ms_mean"], pr["reset_hw_ms_p95"],
                       pr["hw_ms_p95"], "".join(figs)))
    out.append("</table></div>")
    tex = [a for a in m["assets"] if a["class"] == "texture"]
    out.append("<h2>Textures (%d)</h2><div class=wrap><table><tr><th>asset</th><th>option</th><th>decided by</th>"
               "<th class=num>VRAM bytes</th></tr>" % len(tex))
    for a in tex:
        out.append("<tr><td>%s</td><td>%s</td><td class=why>%s</td><td class=num>%s</td></tr>" % (
            html.escape(a["id"]), html.escape(a["option"]), html.escape(a["decided_by"]),
            a["predicted"].get("vram_bytes")))
    out.append("</table></div></body></html>\n")
    return "\n".join(out)
