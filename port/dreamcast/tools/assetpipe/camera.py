"""Offline camera model: prices every (asset, option) at every view in one pass.

Generalises scenery30's scenery_model.py / W9's room_model.py (same visibility and
level rules as native_static.cpp) to any room and to per-asset option vectors:

  per view: object sphere vs the fog far; per part: cluster box test, level choice
  (coarsest level with stored_err * bias * scale * K / z_near <= px), then per-meshlet
  box tests; counts accumulated per asset and option.

Options of an asset (sorted best quality first):
  {"id": "b1", "bias": 1.0}                     stored errors times bias
  {"id": "imp12", "bias": 0.375, "imp_mm": 12000}  a tree drawn as one quad beyond depth D
Costs use costmodel.toml [scenery] (section 4.2); quality is section 4.8.
"""
import math
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor

from .rooms import placement_matrix

COUNT_FIELDS = ("records", "strips", "meshlets", "tests", "parts", "objects", "verts", "tris", "imps")


def screen_k(cost):
    s = cost["screen"]
    return (s["height"] / 2.0) / math.tan(math.radians(s["fovy_deg"] / 2.0))


def world_box(M, origin, step, lo, hi):
    c = [origin[a] + (lo[a] + hi[a]) * 0.5 * step[a] for a in range(3)]
    e = [(hi[a] - lo[a]) * 0.5 * step[a] for a in range(3)]
    wc = [sum(M[r][k] * c[k] for k in range(3)) + M[r][3] for r in range(3)]
    we = [sum(abs(M[r][k]) * e[k] for k in range(3)) for r in range(3)]
    return wc, we


class Camera:
    def __init__(self, eye, yaw_deg, far, fovy=60.0, aspect=4.0 / 3.0, znear=100.0, pitch_deg=0.0):
        yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
        self.eye = eye
        cp = math.cos(pitch)
        self.f = (math.sin(yaw) * cp, math.sin(pitch), math.cos(yaw) * cp)
        self.r = (math.cos(yaw), 0.0, -math.sin(yaw))
        # up = r x f
        f, r = self.f, self.r
        self.u = (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])
        self.tv = math.tan(math.radians(fovy / 2))
        self.th = self.tv * aspect
        self.far, self.znear = far, znear

    @classmethod
    def look_at(cls, eye, target, far, **kw):
        d = [target[i] - eye[i] for i in range(3)]
        yaw = math.degrees(math.atan2(d[0], d[2]))
        pitch = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
        return cls(eye, yaw, far, pitch_deg=pitch, **kw)

    def box(self, c, e):
        d = [c[a] - self.eye[a] for a in range(3)]
        f, r, u = self.f, self.r, self.u
        vz = d[0] * f[0] + d[1] * f[1] + d[2] * f[2]
        rz = abs(f[0]) * e[0] + abs(f[1]) * e[1] + abs(f[2]) * e[2]
        if vz + rz < self.znear or vz - rz > self.far:
            return False, 0.0
        vx = d[0] * r[0] + d[1] * r[1] + d[2] * r[2]
        rx = abs(r[0]) * e[0] + abs(r[1]) * e[1] + abs(r[2]) * e[2]
        if vx - self.th * vz - (rx + self.th * rz) > 0 or -vx - self.th * vz - (rx + self.th * rz) > 0:
            return False, 0.0
        vy = d[0] * u[0] + d[1] * u[1] + d[2] * u[2]
        ry = abs(u[0]) * e[0] + abs(u[1]) * e[1] + abs(u[2]) * e[2]
        if vy - self.tv * vz - (ry + self.tv * rz) > 0 or -vy - self.tv * vz - (ry + self.tv * rz) > 0:
            return False, 0.0
        return True, max(self.znear, vz - rz)

    def sphere(self, c, rad):
        d = [c[a] - self.eye[a] for a in range(3)]
        z = sum(d[a] * self.f[a] for a in range(3))
        if z + rad < self.znear or z - rad > self.far:
            return False, z
        x = sum(d[a] * self.r[a] for a in range(3))
        if abs(x) - rad * math.sqrt(1 + self.th ** 2) > z * self.th:
            return False, z
        y = sum(d[a] * self.u[a] for a in range(3))
        if abs(y) - rad * math.sqrt(1 + self.tv ** 2) > z * self.tv:
            return False, z
        return True, z


def build_instances(pkgs, placements, key_of):
    """pkgs: {owner name: r4im.Package}. -> [instance] with world-space boxes.
    key_of(placement) -> asset key (str)."""
    out = []
    for w in placements:
        pk = pkgs.get(w["owner"])
        if pk is None:
            continue
        mk = pk.mesh_by_bin().get((w["bin"], bool(w["common"])))
        if mk is None:
            continue
        m = pk.meshes[mk]
        origin, step, lo, hi = m[8:11], m[11:14], m[14:17], m[17:20]
        M = placement_matrix(w)
        scale = max(abs(x) for x in w["scale"])
        glo = [(lo[a] - origin[a]) / step[a] for a in range(3)]
        ghi = [(hi[a] - origin[a]) / step[a] for a in range(3)]
        oc, oe = world_box(M, origin, step, glo, ghi)
        parts = []
        for p in pk.mesh_parts(mk):
            cls = []
            for cl in pk.part_levels(p):
                box = world_box(M, origin, step, cl["lo"], cl["hi"]) if cl["lo"] is not None else None
                levels = []
                for err, lets in cl["levels"]:
                    ls = []
                    for i in lets:
                        v, c, s, t, glo_, ghi_ = pk.meshlet_info(i)
                        ls.append((world_box(M, origin, step, glo_, ghi_), (c, s, v, t)))
                    levels.append((err, ls))
                rad = math.sqrt(sum(x * x for x in box[1])) if box else 0.0
                cls.append((box, levels, rad))
            parts.append(cls)
        out.append(dict(key=key_of(w), scale=scale, sphere=(oc, math.sqrt(sum(x * x for x in oe))), parts=parts))
    return out


def _eval_view(args):
    """Worker: one view -> {key: [per-option (counts..., q)]}."""
    view, instances, options, px, K, far, area_div = args
    eye, yaw, pitch = view
    cam = Camera(eye, yaw, far, pitch_deg=pitch)
    res = {}
    for inst in instances:
        key = inst["key"]
        opts = options.get(key)
        if not opts:
            continue
        vis, zc = cam.sphere(*inst["sphere"])
        if not vis:
            continue
        acc = res.get(key)
        if acc is None:
            acc = res[key] = [[0] * 10 for _ in opts]
        scale = inst["scale"]
        rad_obj = inst["sphere"][1]
        depth_obj = zc - rad_obj
        imp_done = [False] * len(opts)
        for oi, o in enumerate(opts):
            acc[oi][5] += 1
            d = o.get("imp_mm") or 0
            if d and depth_obj >= d:
                a = acc[oi]
                a[0] += 4
                a[1] += 1
                a[3] += 1
                a[8] += 1
                imp_done[oi] = True
                # impostor view-quantisation error vs the full mesh (best option has none)
                e = 0.195 * rad_obj * K / max(depth_obj, 1.0)
                ar = min(1.0, math.pi * (rad_obj * K / max(depth_obj, 1.0)) ** 2 / area_div)
                a[9] += e * ar
        for clusters in inst["parts"]:
            drawn = [False] * len(opts)
            for box, levels, crad in clusters:
                if box is not None:
                    for oi in range(len(opts)):
                        if not imp_done[oi]:
                            acc[oi][3] += 1
                    vis, zmin = cam.box(*box)
                    if not vis:
                        continue
                else:
                    zmin = max(cam.znear, depth_obj)
                s_k_z = scale * K / zmin
                # best (bias 1) choice for the quality reference
                ref = 0
                for li, (err, _) in enumerate(levels):
                    if err * s_k_z <= px:
                        ref = li
                e_ref = levels[ref][0] * s_k_z
                ar = min(1.0, math.pi * (crad * K / zmin) ** 2 / area_div) if crad else 0.0
                for oi, o in enumerate(opts):
                    if imp_done[oi]:
                        continue
                    b = o.get("bias", 1.0)
                    pick = 0
                    for li, (err, _) in enumerate(levels):
                        if err * b * s_k_z <= px:
                            pick = li
                    a = acc[oi]
                    for wb, (c, s, v, t) in levels[pick][1]:
                        a[3] += 1
                        if not cam.box(*wb)[0]:
                            continue
                        drawn[oi] = True
                        a[0] += c
                        a[1] += s
                        a[2] += 1
                        a[6] += v
                        a[7] += t
                    e = levels[pick][0] * s_k_z
                    if e > e_ref:
                        a[9] += (e - e_ref) * ar
            for oi in range(len(opts)):
                if drawn[oi]:
                    acc[oi][4] += 1
    return res


def cycles(cost, n):
    sc = cost["scenery"]
    imp = cost.get("impostor", {})
    return (sc["c_rec"] * n[0] + sc.get("c_strip", 0) * n[1] + sc["c_meshlet"] * n[2] + sc["c_test"] * n[3]
            + sc["c_part"] * n[4] + sc.get("c_obj", 0) * n[5] + imp.get("quad_cycles", 150.0) * n[8])


class Pricing:
    """Per (asset, option): per-view cost (hw ms) and counts; per view: nothing is
    added across assets here (the solver sums vectors)."""

    def __init__(self, views, options, per_view, cost):
        self.views, self.options, self.cost = views, options, cost
        clock = cost["scenery"]["clock_mhz"] * 1000.0
        self.ms = {}       # key -> [option][view] ms
        self.counts = {}   # key -> [option] {field: mean over views}
        self.quality = {}  # key -> [option] q
        self.ta = {}       # key -> [option][view] TA parameter bytes
        tb = cost["ta"]
        nv = len(views)
        for key, opts in options.items():
            ms = [[0.0] * nv for _ in opts]
            ta = [[0] * nv for _ in opts]
            tot = [[0] * 10 for _ in opts]
            for vi, r in enumerate(per_view):
                a = r.get(key)
                if not a:
                    continue
                for oi in range(len(opts)):
                    ms[oi][vi] = cycles(cost, a[oi]) / clock
                    ta[oi][vi] = tb["bytes_per_record"] * a[oi][0] + tb["bytes_per_substrip"] * a[oi][1]
                    for k in range(10):
                        tot[oi][k] += a[oi][k]
            self.ms[key] = ms
            self.ta[key] = ta
            self.counts[key] = [{f: round(t[i] / nv, 2) for i, f in enumerate(COUNT_FIELDS)} for t in tot]
            self.quality[key] = [round(t[9] / nv, 6) for t in tot]

    def mean(self, key, oi):
        v = self.ms[key][oi]
        return sum(v) / len(v)


def ground_views(cloud, placements_centres, grid, yaws, eye_mm):
    """Ground grid over the placement area; ground = 20th percentile placed height
    within 1.5 m (room_model.py), eye 1.6 m above it."""
    xs = [c[0] for c in placements_centres]
    zs = [c[2] for c in placements_centres]
    if not xs:
        return []
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    buckets = {}
    cell = 1500.0
    for v in cloud:
        buckets.setdefault((int(v[0] // cell), int(v[2] // cell)), []).append(v[1])
    views = []
    for i in range(grid):
        for j in range(grid):
            x = x0 + (x1 - x0) * (i + 0.5) / grid
            z = z0 + (z1 - z0) * (j + 0.5) / grid
            ys = []
            bx, bz = int(x // cell), int(z // cell)
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    ys.extend(buckets.get((bx + dx, bz + dz), ()))
            if not ys:
                continue
            ys.sort()
            y = ys[len(ys) // 5] + eye_mm
            for k in range(yaws):
                views.append(dict(name="grid_%d_%d" % (i, j), eye=(round(x, 1), round(y, 1), round(z, 1)),
                                  yaw=360.0 * k / yaws, pitch=0.0))
    return views


_SHARED = None


def _eval_index(i):
    views, instances, options, px, K, far, area_div = _SHARED
    v = views[i]
    return _eval_view(((v["eye"], v["yaw"], v.get("pitch", 0.0)), instances, options, px, K, far, area_div))


def price(instances, views, options, cost, px=None, far=None, jobs=None):
    """-> Pricing. options: {key: [option dict]}; views: [dict(eye, yaw, pitch)].
    Views are evaluated in forked workers (the instance data is inherited, not pickled);
    results are combined in view order, so the output does not depend on the job count."""
    global _SHARED
    K = screen_k(cost)
    px = px if px is not None else cost["lod"]["px"]
    far = far if far is not None else cost["lod"]["fog_far_mm"]
    area_div = float(cost["screen"]["width"] * cost["screen"]["height"])
    _SHARED = (views, instances, options, px, K, far, area_div)
    jobs = jobs or min(16, os.cpu_count() or 1)
    try:
        if jobs > 1 and len(views) > 8:
            ctx = multiprocessing.get_context("fork")
            with ProcessPoolExecutor(jobs, mp_context=ctx) as ex:
                per_view = list(ex.map(_eval_index, range(len(views)), chunksize=max(1, len(views) // (jobs * 4))))
        else:
            per_view = [_eval_index(i) for i in range(len(views))]
    finally:
        _SHARED = None
    return Pricing(views, options, per_view, cost)


def percentile(values, q):
    v = sorted(values)
    if not v:
        return 0.0
    return v[min(len(v) - 1, int(len(v) * q))]
