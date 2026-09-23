"""What one mode draws at one view: the pricing rule (camera.py) applied to real
geometry, as world-space textured triangles for render.py.

Per placement: object sphere vs the fog far; the chosen option's cull distance and
impostor distance (object centre depth, as TREE_IMPOSTOR_MM); else per part cluster
box test, level choice (coarsest level with err * bias * scale * K / zmin <= px) and
per-meshlet box test, exactly as camera._eval_view counts them.
"""
import math

from .camera import Camera, screen_k
from .rooms import placement_matrix


class Textures:
    """Part texture lookup: R100.TPL-style image list, per-index overrides (the keyed PS2
    bark), per (owner code, bin, part) overrides (baked house shells)."""

    def __init__(self, images, by_index=None, by_part=None):
        self.images = images
        self.by_index = dict(by_index or {})
        self.by_part = dict(by_part or {})

    def lookup(self, code, b, part_in_mesh, texture, alpha, flags):
        t = self.by_part.get((code, b, part_in_mesh))
        if t is not None:
            return t, None
        tex = self.by_index.get(texture)
        if tex is None and texture < len(self.images):
            tex = self.images[texture]
        atex = None
        if flags & 4 and alpha != 255 and alpha < len(self.images):
            atex = self.images[alpha]
        return tex, atex


def _rgb(argb):
    return ((argb >> 16) & 255, (argb >> 8) & 255, argb & 255)


class SceneBuilder:
    def __init__(self, pkgs, placements, codes, cost, textures, impostors=None):
        """pkgs {owner name: Package}; codes {owner name: owner code}; impostors
        {(code, bin): record (tree_impostors.py) + 'image'}."""
        self.pkgs, self.placements, self.codes, self.cost = pkgs, placements, codes, cost
        self.tex, self.imp = textures, impostors or {}
        self.K = screen_k(cost)
        self._tri = {}
        self._inst = []
        for w in placements:
            pk = pkgs.get(w["owner"])
            if pk is None:
                continue
            mk = pk.mesh_by_bin().get((w["bin"], bool(w["common"])))
            if mk is None:
                continue
            M = placement_matrix(w)
            m = pk.meshes[mk]
            origin, step, lo, hi = m[8:11], m[11:14], m[14:17], m[17:20]
            c = [(lo[a] + hi[a]) * 0.5 for a in range(3)]
            e = [(hi[a] - lo[a]) * 0.5 for a in range(3)]
            wc = [sum(M[r][k] * c[k] for k in range(3)) + M[r][3] for r in range(3)]
            we = [sum(abs(M[r][k]) * e[k] for k in range(3)) for r in range(3)]
            self._inst.append(dict(w=w, pk=pk, mk=mk, M=M, scale=max(abs(x) for x in w["scale"]),
                                   sphere=(wc, math.sqrt(sum(x * x for x in we)))))

    def _world_box(self, M, pk, mk, glo, ghi):
        m = pk.meshes[mk]
        origin, step = m[8:11], m[11:14]
        c = [origin[a] + (glo[a] + ghi[a]) * 0.5 * step[a] for a in range(3)]
        e = [(ghi[a] - glo[a]) * 0.5 * step[a] for a in range(3)]
        wc = [sum(M[r][k] * c[k] for k in range(3)) + M[r][3] for r in range(3)]
        we = [sum(abs(M[r][k]) * e[k] for k in range(3)) for r in range(3)]
        return wc, we

    def _meshlet_tris(self, pk, mk, p, let):
        key = (id(pk), let)
        t = self._tri.get(key)
        if t is not None:
            return t
        part = pk.parts[p]
        ulo0, ulo1, us0, us1 = part[8:12]
        out = []
        for s in pk.meshlet_strips(let):
            vs = [pk.vertex(v) for v in s]
            for j in range(len(s) - 2):
                a, b, c = (vs[j + 1], vs[j], vs[j + 2]) if j & 1 else (vs[j], vs[j + 1], vs[j + 2])
                if a[:3] == b[:3] or b[:3] == c[:3] or a[:3] == c[:3]:
                    continue
                out.append(tuple((pk.world(mk, *x[:3]), (ulo0 + x[3] * us0, ulo1 + x[4] * us1),
                                  self._colour(pk, x[5])) for x in (a, b, c)))
        self._tri[key] = out
        return out

    LIGHT = (0.30, 0.85, 0.43)
    AMBIENT, DIFFUSE = 30.0, 70.0      # matched by eye to the Flycast r100 spawn frames

    def _colour(self, pk, slot):
        """Prelit CLR0 colour, or (palette 0x00000000: no CLR0, lit at runtime) a fixed
        ambient + Lambert term on the model-space normal (the same for every mode)."""
        k = slot >> 12
        argb = pk.palette[k] if k < len(pk.palette) else 0xff808080
        if argb & 0xffffff:
            return _rgb(argb)
        from .r4im import oct_decode
        n = oct_decode(slot & 0xfff)
        L = self.LIGHT
        d = abs(n[0] * L[0] + n[1] * L[1] + n[2] * L[2])
        c = self.AMBIENT + self.DIFFUSE * d
        return (c, c * 0.97, c * 0.92)

    def build(self, eye, target, options, px, far):
        """-> (tris for render.render_scene, counts). options {asset key: option dict};
        the key of a placement is '<owner>/<bin id>' (pipeline keyfn)."""
        from .rooms import bin_id
        cam = Camera.look_at(eye, target, far)
        K = self.K
        tris = []
        n = dict(tris=0, records=0, meshlets=0, imps=0, objects=0)
        for inst in self._inst:
            w, pk, mk, M = inst["w"], inst["pk"], inst["mk"], inst["M"]
            code = w["code"]
            key = "%s/%s" % (w["owner"], bin_id(code, w["bin"]))
            o = options.get(key, {})
            vis, zc = cam.sphere(*inst["sphere"])
            if not vis:
                continue
            if o.get("cull_mm") and zc >= o["cull_mm"]:
                continue
            n["objects"] += 1
            rec = self.imp.get((code, w["bin"]))
            if o.get("imp_mm") and rec is not None and zc >= o["imp_mm"]:
                tris.extend(self._impostor(inst, rec, eye))
                n["imps"] += 1
                n["records"] += 4
                continue
            scale = inst["scale"]
            b = o.get("bias", 1.0)
            first = pk.meshes[mk][6]
            for p in pk.mesh_parts(mk):
                part = pk.parts[p]
                tex, atex = self.tex.lookup(code, w["bin"], p - first, part[2], part[3], part[4])
                for cl in pk.part_levels(p):
                    if cl["lo"] is not None:
                        vis, zmin = cam.box(*self._world_box(M, pk, mk, cl["lo"], cl["hi"]))
                        if not vis:
                            continue
                    else:
                        zmin = max(cam.znear, zc - inst["sphere"][1])
                    s_k_z = scale * K / zmin
                    pick = 0
                    for li, (err, _) in enumerate(cl["levels"]):
                        if err * b * s_k_z <= px:
                            pick = li
                    for let in cl["levels"][pick][1]:
                        v, c, s, t, glo, ghi = pk.meshlet_info(let)
                        if not cam.box(*self._world_box(M, pk, mk, glo, ghi))[0]:
                            continue
                        n["records"] += c
                        n["meshlets"] += 1
                        for (p0, t0, c0), (p1, t1, c1), (p2, t2, c2) in self._meshlet_tris(pk, mk, p, let):
                            tris.append((self._xf(M, p0), self._xf(M, p1), self._xf(M, p2), t0, t1, t2, c0, c1, c2,
                                         tex, atex))
                            n["tris"] += 1
        return tris, n

    @staticmethod
    def _xf(M, q):
        return (M[0][0] * q[0] + M[0][1] * q[1] + M[0][2] * q[2] + M[0][3],
                M[1][0] * q[0] + M[1][1] * q[1] + M[1][2] * q[2] + M[1][3],
                M[2][0] * q[0] + M[2][1] * q[1] + M[2][2] * q[2] + M[2][3])

    def _impostor(self, inst, rec, eye):
        """Cylindrical billboard (native_static.cpp mesh_impostor): cell from the camera
        azimuth in model space, quad facing the camera, punch-through atlas texel."""
        M = inst["M"]
        C = rec["centre"]
        wc = self._xf(M, C)
        d = [eye[a] - wc[a] for a in range(3)]
        # model-space direction: R^T d (columns of M normalised: rotation x uniform scale)
        cols = [[M[r][c] for r in range(3)] for c in range(3)]
        norms = [math.sqrt(sum(x * x for x in col)) or 1.0 for col in cols]
        dm = [sum(cols[c][r] * d[r] for r in range(3)) / norms[c] for c in range(3)]
        dx, dz = dm[0], dm[2]
        ln = math.hypot(dx, dz)
        bx, bz = (dx / ln, dz / ln) if ln > 0 else (1.0, 0.0)
        views = rec["views"]
        turns = (math.atan2(-dz, dx) / (2 * math.pi)) % 1.0
        cell = int(turns * views + 0.5) % views
        cw, ch = rec["cell"]
        aw, ah = rec["atlas"]
        col, row = cell % rec["cols"], cell // rec["cols"]
        u0, u1 = col * cw / aw, (col + 1) * cw / aw
        v0, v1 = row * ch / ah, (row + 1) * ch / ah
        hw, hh = rec["half_w"], rec["half_h"]
        corners = []
        for sx, sy, u, v in ((-hw, hh, u0, v0), (hw, hh, u1, v0), (hw, -hh, u1, v1), (-hw, -hh, u0, v1)):
            q = (C[0] + sx * bz, C[1] + sy, C[2] - sx * bx)
            corners.append((self._xf(M, q), (u, v)))
        col_rgb = rec.get("rgb", (90, 90, 90))
        img = rec["image"]
        (a, ta), (b, tb), (c, tc), (e, te) = corners
        return [(a, b, c, ta, tb, tc, col_rgb, col_rgb, col_rgb, img, None),
                (a, c, e, ta, tc, te, col_rgb, col_rgb, col_rgb, img, None)]
