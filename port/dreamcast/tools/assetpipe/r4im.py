"""Reader for native scenery packages (R4IM v1/v2/v3, tools/convert_room_bins.py).

Decodes meshes, parts, LOD clusters/levels and meshlets (strips, vertex grid
positions, octahedral normals), for the camera model, the review renders and the
package-bytes formula check. Read-only; the runtime format stays owned by the
converter and room/instanced_mesh.hpp.
"""
import math
import struct

HEADER = struct.Struct("<4s19I")
LOD_HEADER = struct.Struct("<8I")
MESH = struct.Struct("<HBBHHIII12f")
PART = struct.Struct("<IIBBBBII4f")
MESHLET = struct.Struct("<IIIHH6H")
VERTEX = struct.Struct("<6H")
PART_LOD = struct.Struct("<II")
CLUSTER = struct.Struct("<6HII")
LEVEL = struct.Struct("<IIf")
INDEXED = 0x8000
CLASS_NAMES = {0: "default", 1: "ground", 2: "tree", 3: "landmark", 4: "clutter", 5: "structure"}


def oct_decode(code):
    qx, qy = code & 63, (code >> 6) & 63
    x, y = qx / 63.0 * 2 - 1, qy / 63.0 * 2 - 1
    z = 1 - abs(x) - abs(y)
    if z < 0:
        x, y = (1 - abs(y)) * (1 if x >= 0 else -1), (1 - abs(x)) * (1 if y >= 0 else -1)
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / n, y / n, z / n)


class Package:
    def __init__(self, data):
        self.data = data = bytes(data)
        h = HEADER.unpack_from(data, 0)
        if h[0] != b"R4IM":
            raise ValueError("not an R4IM package")
        self.version, self.total = h[1], h[2]
        (mc, pc, lc, vc, ib, palc) = h[4:10]
        (mo, po, lo, vo, io, pao) = h[10:16]
        self.color_mode = h[16]
        self.counts = dict(meshes=mc, parts=pc, meshlets=lc, vertices=vc, index_bytes=ib, palette=palc)
        self.meshes = [MESH.unpack_from(data, mo + MESH.size * i) for i in range(mc)]
        self.parts = [PART.unpack_from(data, po + PART.size * i) for i in range(pc)]
        self.meshlets = [MESHLET.unpack_from(data, lo + MESHLET.size * i) for i in range(lc)]
        self._vo, self._io = vo, io
        self.palette = [struct.unpack_from("<I", data, pao + 4 * i)[0] for i in range(palc)]
        self.lod = None
        self.mesh_class = [0] * mc
        self.class_rules = {}
        if self.version >= 2:
            ncl, nlv, plo, clo, llo, clso, rlo, _ = LOD_HEADER.unpack_from(data, HEADER.size)
            self.counts.update(clusters=ncl, levels=nlv)
            self.part_lod = [PART_LOD.unpack_from(data, plo + 8 * i) for i in range(pc)]
            self.clusters = [CLUSTER.unpack_from(data, clo + 20 * i) for i in range(ncl)]
            self.levels = [LEVEL.unpack_from(data, llo + 12 * i) for i in range(nlv)]
            self.lod = True
            if clso:
                self.mesh_class = list(data[clso:clso + mc])
            if rlo:
                for c in range(8):
                    full, cull = struct.unpack_from("<HH", data, rlo + 4 * c)
                    if full or cull:
                        self.class_rules[CLASS_NAMES.get(c, str(c))] = (full / 10.0, cull / 10.0)
        self._let_cache = {}

    # ---- meshlets
    def meshlet_info(self, i):
        """(vertices, corners, strips, triangles, lo_grid, hi_grid) without decoding vertices."""
        c = self._let_cache.get(i)
        if c is None:
            m = self.meshlets[i]
            fv, fi, sb, vcount, sc = m[:5]
            indexed = bool(sc & INDEXED)
            s = self._io + fi + (2 * vcount if indexed else 0)
            end = s + sb
            d = self.data
            corners = strips = 0
            while s < end:
                n = d[s]
                corners += n
                strips += 1
                s += 1 + n
            c = (vcount, corners, strips, corners - 2 * strips, m[5:8], m[8:11])
            self._let_cache[i] = c
        return c

    def meshlet_strips(self, i):
        """[[vertex index, ...], ...] (absolute vertex indices)."""
        m = self.meshlets[i]
        fv, fi, sb, vcount, sc = m[:5]
        d = self.data
        base = self._io + fi
        if sc & INDEXED:
            table = struct.unpack_from("<%dH" % vcount, d, base)
            s = base + 2 * vcount
            remap = [fv + t for t in table]
        else:
            s = base
            remap = [fv + k for k in range(vcount)]
        end = s + sb
        out = []
        while s < end:
            n = d[s]
            out.append([remap[k] for k in d[s + 1:s + 1 + n]])
            s += 1 + n
        return out

    def vertex(self, i):
        return VERTEX.unpack_from(self.data, self._vo + VERTEX.size * i)

    # ---- structure
    def mesh_by_bin(self):
        return {(m[0], bool(m[1])): k for k, m in enumerate(self.meshes)}

    def mesh_parts(self, k):
        m = self.meshes[k]
        return range(m[6], m[6] + m[7])

    def part_levels(self, p):
        """[cluster] -> dict(lo, hi, levels=[(err_model, [meshlet...])]) (v1: one level)."""
        if not self.lod:
            part = self.parts[p]
            return [dict(lo=None, hi=None, levels=[(0.0, list(range(part[6], part[6] + part[7])))])]
        fc, n = self.part_lod[p]
        out = []
        for c in self.clusters[fc:fc + n]:
            lv = [(e, list(range(f, f + k))) for f, k, e in self.levels[c[6]:c[6] + c[7]]]
            out.append(dict(lo=c[0:3], hi=c[3:6], levels=lv))
        return out

    def world(self, k, gx, gy, gz):
        """Grid position -> BIN model space (source units)."""
        m = self.meshes[k]
        o, st = m[8:11], m[11:14]
        return (o[0] + gx * st[0], o[1] + gy * st[1], o[2] + gz * st[2])

    def level_triangles(self, k, level, bias=1.0, choose=None):
        """Triangles [(p0, p1, p2, n0, n1, n2, part)] of mesh k in model space.
        level: an int (clamped per cluster), or None with choose(cluster, levels) -> index."""
        tris = []
        for p in self.mesh_parts(k):
            for cl in self.part_levels(p):
                lv = cl["levels"]
                li = min(level, len(lv) - 1) if choose is None else choose(cl, lv)
                if li is None:
                    continue
                for let in lv[li][1]:
                    for s in self.meshlet_strips(let):
                        vs = [self.vertex(v) for v in s]
                        for j in range(len(s) - 2):
                            a, b, c = (vs[j + 1], vs[j], vs[j + 2]) if j & 1 else (vs[j], vs[j + 1], vs[j + 2])
                            pa, pb, pc = (self.world(k, *x[:3]) for x in (a, b, c))
                            if pa == pb or pb == pc or pa == pc:
                                continue
                            tris.append((pa, pb, pc, oct_decode(a[5] & 0xfff), oct_decode(b[5] & 0xfff),
                                         oct_decode(c[5] & 0xfff), p))
        return tris

    def mesh_summary(self, k):
        """Per-level totals for mesh k: [(max err, tris, corners, strips, meshlets, verts)]."""
        depth = 0
        per = []
        for p in self.mesh_parts(k):
            for cl in self.part_levels(p):
                per.append(cl["levels"])
                depth = max(depth, len(cl["levels"]))
        out = []
        for li in range(depth):
            err = t = c = s = n = v = 0
            for lv in per:
                e, lets = lv[min(li, len(lv) - 1)]
                err = max(err, e)
                for let in lets:
                    vc, cc, sc, tc, _, _ = self.meshlet_info(let)
                    t += tc
                    c += cc
                    s += sc
                    n += 1
                    v += vc
            out.append(dict(error=err, tris=t, corners=c, strips=s, meshlets=n, verts=v))
        return out


def level_errors_bad(pk):
    """The runtime's level rule (room/instanced_mesh.hpp MeshPackage::adopt, v2): within each
    cluster every stored level error is finite and below 3.0e38, and no smaller than the level
    before it; a package that breaks it is rejected and its owner draws on the generic path.
    -> [(mesh, part, cluster, [errors])] of the clusters that break it (float32 as stored)."""
    if not pk.lod:
        return []
    bad = []
    for k in range(len(pk.meshes)):
        for p in pk.mesh_parts(k):
            fc, n = pk.part_lod[p]
            for ci, c in enumerate(pk.clusters[fc:fc + n]):
                errs = [struct.unpack("<f", struct.pack("<f", e))[0] for _, _, e in pk.levels[c[6]:c[6] + c[7]]]
                if any(not (e < 3.0e38) or (i and e < errs[i - 1]) for i, e in enumerate(errs)):
                    bad.append((k, p, ci, errs))
    return bad


def load(path):
    with open(path, "rb") as f:
        return Package(f.read())


def predicted_bytes(meshes, parts, meshlets, clusters, levels, vertices, strip_bytes, shared_indices=0,
                    palette=16, lod=True):
    """Section 4.6 package-bytes formula (sections 32-byte aligned)."""
    def a(n):
        return (n + 31) & ~31
    head = 80 + (32 if lod else 0)
    body = [68 * meshes, 36 * parts, 28 * meshlets, 12 * vertices, strip_bytes + 2 * shared_indices, 4 * palette]
    if lod:
        body += [8 * parts, 20 * clusters, 12 * levels]
    return head + sum(a(b) for b in body) + 32
