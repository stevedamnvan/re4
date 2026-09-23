"""Room sources: which rooms exist, their BINs, placements and scales.

- `export` rooms (r100): the seven owner BIN directories of the GC r100 export and the
  reclaim placements (the inputs of the accepted LD packages).
- `smd` rooms (every other stage room): St*/<room>.das from the GC disc image (or the
  route extraction), BINs and placements from its SMD (tools/room_smd.py).
"""
import json
import math
import struct
import sys
from pathlib import Path

from .config import TOOLS
from .util import sha256_bytes

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _room_smd():
    import room_smd
    return room_smd


def _crb():
    import convert_room_bins
    return convert_room_bins


# ---- GameCube disc image (FST) ------------------------------------------------
class GcIso:
    """Read-only GameCube ISO file system (big-endian FST at 0x424)."""

    def __init__(self, path):
        self.path = Path(path)
        with self.path.open("rb") as f:
            f.seek(0x424)
            fo, fs = struct.unpack(">II", f.read(8))
            f.seek(fo)
            fst = f.read(fs)
        n = struct.unpack(">I", fst[8:12])[0]
        strings = fst[n * 12:]

        def name(o):
            return strings[o:strings.index(b"\0", o)].decode("latin-1")
        self.files = {}
        stack = [(n, "")]
        for i in range(1, n):
            while stack and i >= stack[-1][0]:
                stack.pop()
            w0, a, b = struct.unpack(">III", fst[i * 12:i * 12 + 12])
            p = (stack[-1][1] + "/" + name(w0 & 0xFFFFFF)) if stack else name(w0 & 0xFFFFFF)
            if w0 >> 24:
                stack.append((b, p))
            else:
                self.files[p.lstrip("/")] = (a, b)
        self.lower = {k.lower(): k for k in self.files}

    def find(self, rel):
        return self.lower.get(rel.lower())

    def read(self, rel):
        key = self.find(rel)
        if key is None:
            raise FileNotFoundError(rel)
        off, size = self.files[key]
        with self.path.open("rb") as f:
            f.seek(off)
            return f.read(size)

    def rooms(self):
        out = []
        for k in self.files:
            parts = k.split("/")
            if len(parts) == 2 and parts[0].lower().startswith("st") and parts[1].lower().endswith(".das") \
                    and parts[1][0].lower() == "r" and len(parts[1]) == 8:
                out.append((parts[1][:-4].lower(), k))
        return sorted(out)


def all_rooms(cfg):
    rooms = {}
    for key in ("gc_iso", "gc_iso2"):
        p = cfg.path(key)
        if p and p.exists():
            for r, rel in GcIso(p).rooms():
                rooms.setdefault(r, (key, rel))
    return rooms


# ---- one room --------------------------------------------------------------------
OWNER_NAMES = {0xFF: "MAINSCENARIO", 0xFE: "COMMON"}


def owner_name(code):
    return OWNER_NAMES.get(code, "FILE_%02d" % code)


def rot_matrix(r):
    sx, sy, sz = (math.sin(a) for a in r)
    cx, cy, cz = (math.cos(a) for a in r)
    return [[cz * cy, cz * sx * sy - sz * cx, cz * cx * sy + sz * sx],
            [sz * cy, sz * sx * sy + cz * cx, sz * cx * sy - cz * sx],
            [-sy, cy * sx, cy * cx]]


def placement_matrix(w):
    """SmdWork pos/rot/scale -> 3x4 model-to-world (scenery_model.placement)."""
    R = rot_matrix(w["rot"])
    s = w["scale"]
    return [[R[r][c] * s[c] for c in range(3)] + [w["pos"][r]] for r in range(3)]


class Room:
    def __init__(self, cfg, cache, name):
        self.cfg, self.cache, self.name = cfg, cache, name
        self.recipe = cfg.room(name)
        self.kind = self.recipe.get("kind", "smd")
        self._owners = None
        self._placements = None

    # ---- source files
    def das_path(self):
        """The room .das: extracted from the GC disc image into the cache (content keyed),
        else the route extraction (iso-src)."""
        rel = self.recipe.get("das")
        for key in ("gc_iso", "gc_iso2"):
            iso = self.cfg.path(key)
            if not iso or not iso.exists():
                continue
            g = GcIso(iso)
            k = g.find(rel) if rel else next((k for r, k in g.rooms() if r == self.name), None)
            if not k:
                continue

            def extract(out, work, g=g, k=k):
                data = g.read(k)
                (out / (self.name + ".das")).write_bytes(data)
                return dict(file=k, bytes=len(data), sha256=sha256_bytes(data))
            obj = self.cache.step("iso.extract", dict(file=k), dict(iso=iso), dict(reader="GcIso/1"), extract,
                                  label="%s das" % self.name)
            return obj.path(self.name + ".das")
        p = self.cfg.path("route_src")
        if p and (p / "st1" / (self.name + ".das")).exists():
            return p / "st1" / (self.name + ".das")
        raise FileNotFoundError("%s: no .das in the GC disc image(s) or route_src" % self.name)

    def owners(self):
        """[dict(name, code, common, bins={bin: bytes}, inputs={label: path})]."""
        if self._owners is not None:
            return self._owners
        out = []
        if self.kind == "export":
            base = self.cfg.path("r100_export")
            for o in self.recipe["owners"]:
                d = base / o["bins"]
                bins = {int(p.stem): p.read_bytes() for p in sorted(d.glob("*.BIN"))}
                out.append(dict(name=o["name"], code=int(o["owner"], 0), common=bool(o.get("common")),
                                bins=bins, dir=d))
        else:
            rs = _room_smd()
            das = self.das_path()
            smd, e = rs.load_smd(das)
            s = rs.Smd(smd, e)
            self._smd = s
            out.append(dict(name="MAINSCENARIO", code=int(self.recipe.get("owner", "0xff"), 0), common=False,
                            bins=s.bins(), das=das))
        self._owners = out
        return out

    def placements(self):
        """[dict(owner=name, code, bin, common, pos, rot, scale)] (world space, source mm)."""
        if self._placements is not None:
            return self._placements
        out = []
        if self.kind == "export":
            rec = json.loads(self.cfg.path("reclaim").read_text())[self.name]["placements"]
            code = {o["name"]: int(o["owner"], 0) for o in self.recipe["owners"]}
            for key in sorted(rec, key=lambda k: (k.split("/")[0], int(k.split("/")[1]))):
                own, b = key.split("/")
                for w in rec[key]:
                    if w["owner"] not in code:
                        continue
                    out.append(dict(owner=own, code=code[own], bin=int(b), common=own == "COMMON",
                                    pos=w["pos"], rot=w["rot"], scale=w["scale"], work=w.get("work"),
                                    placed_by=w["owner"]))
        else:
            self.owners()
            for w in self._smd.used():
                if w["common"]:
                    continue
                out.append(dict(owner="MAINSCENARIO", code=int(self.recipe.get("owner", "0xff"), 0), bin=w["bin"],
                                common=False, pos=w["pos"], rot=w["rot"], scale=w["scale"], work=w["work"]))
        self._placements = out
        return out

    def scales(self):
        """{"<code>:<bin>": largest |scale|}, the converter's --scales form."""
        out = {}
        for p in self.placements():
            k = "%d:%d" % (p["code"], p["bin"])
            out[k] = max(out.get(k, 0.0), max(abs(s) for s in p["scale"]))
        return dict(sorted(out.items()))

    def input_files(self):
        """Files whose content defines the room's scenery sources (for cache keys)."""
        if self.kind == "export":
            d = {o["name"]: o["dir"] for o in self.owners()}
            d["placements"] = self.cfg.path("reclaim")
            return d
        return {"das": self.das_path()}

    # ---- inventory
    def inventory(self):
        """Per BIN: counts, bounds, instances, largest scale, render qualification."""
        crb = _crb()
        rs = _room_smd()
        inst = {}
        for p in self.placements():
            inst.setdefault((p["code"], p["bin"]), []).append(p)
        rows = []
        for o in self.owners():
            for b, data in sorted(o["bins"].items()):
                why = None
                if self.kind != "export":
                    why = rs.releasable(data, ">")
                    if why not in rs.RENDER_UNQUALIFIED:
                        why = None
                try:
                    src = crb.parse_bin(data)
                except ValueError as exc:
                    rows.append(dict(id="%s/scenery/%s" % (self.name, bin_id(o["code"], b)), owner=o["name"],
                                     code=o["code"], bin=b, error=str(exc), instances=len(inst.get((o["code"], b), []))))
                    continue
                pos = src["positions"]
                used = sorted({k[0] for pt in src["parts"] for s in pt["strips"] for k in s} |
                              {k[0] for pt in src["parts"] for t in pt["loose"] for k in t})
                tris = sum(max(0, len(s) - 2) for pt in src["parts"] for s in pt["strips"]) + \
                    sum(len(pt["loose"]) for pt in src["parts"])
                if used:
                    lo = [min(pos[i][a] for i in used) for a in range(3)]
                    hi = [max(pos[i][a] for i in used) for a in range(3)]
                else:
                    lo = hi = [0.0, 0.0, 0.0]
                ps = inst.get((o["code"], b), [])
                scale = max([max(abs(s) for s in p["scale"]) for p in ps] or [1.0])
                ext = [(hi[a] - lo[a]) * scale for a in range(3)]
                rows.append(dict(id="%s/scenery/%s" % (self.name, bin_id(o["code"], b)), owner=o["name"],
                                 code=o["code"], bin=b, common=o["common"], bytes=len(data), vertices=len(used),
                                 parts=len(src["parts"]), triangles=tris, instances=len(ps), scale=scale,
                                 extent_mm=[round(x, 1) for x in ext],
                                 radius_mm=round(0.5 * math.sqrt(sum(x * x for x in ext)), 1),
                                 textures=sorted({pt["texture"] for pt in src["parts"]}),
                                 alpha_parts=sum(1 for pt in src["parts"] if pt["flags"] & 4),
                                 gx_kept=why))
        return rows


def bin_id(code, b):
    return "%s:%d" % ("0x%02x" % code if code >= 0xF0 else str(code), b)
