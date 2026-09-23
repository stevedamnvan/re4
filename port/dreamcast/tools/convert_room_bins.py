#!/usr/bin/env python3
"""Convert r100 scenery BINs into one instanced native mesh package per owner.

Each source BIN becomes one prelit mesh in its own model space, drawn by every
placement that uses it with the part's live source modelview. Placement,
visibility, collision and sequencing stay in the recovered game; only the GX
geometry representation changes. Source part identity is the part header's
byte offset from the BIN's first part header plus its stream size, which the
runtime compares against the live ModelData before drawing.

Package (little endian, sections 32-byte aligned):
  MeshHeader, MeshRecord[mesh], MeshPart[part], Meshlet[meshlet],
  CompactVertex12[vertex] (uint16 grid position, uint16 part UV, uint16 colour),
  strip bytes ([count][count local indices] per strip), palette ARGB words.
Meshlets hold at most 256 vertices so strip indices are single bytes.

Colour: r100 scenery takes its colour from GX lights (CLR0 is near-uniform and
often zero), so each vertex's colour slot carries its 12-bit octahedral source
normal under a 4-bit CLR0 palette index. The runtime lights every part once,
at its first draw, with the source's own evaluator and live light state, and
overwrites the slot with ARGB1555 (header reserved[0] = 1).
"""
import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

MAGIC = b"R4IM"
VERSION = 1
HEADER = struct.Struct("<4s19I")          # 80 bytes, see pack below
MESH = struct.Struct("<HBBHHIII12f")       # 68 bytes
PART = struct.Struct("<IIBBBBII4f")        # 36 bytes
MESHLET = struct.Struct("<IIIHH6H")        # 28 bytes
VERTEX = struct.Struct("<6H")              # 12 bytes
MAX_MESHLET_VERTICES = 256
COLOR_OCT_NORMAL = 1  # header reserved[0]: colour slot = palette<<12 | oct normal, lit at runtime
MAX_STRIP = 255


def f32(x):
    """The package stores grid parameters as float32; quantize with those."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def be16(d, o):
    return struct.unpack_from(">H", d, o)[0]


def be32(d, o):
    return struct.unpack_from(">I", d, o)[0]


def align(n, a=32):
    return (n + a - 1) & ~(a - 1)


def triangles_of(op, v):
    if op == 0x80:
        for i in range(0, len(v) - 3, 4):
            a, b, c, d = v[i:i + 4]
            yield a, b, c
            yield a, c, d
    elif op == 0x90:
        for i in range(0, len(v) - 2, 3):
            yield tuple(v[i:i + 3])
    else:
        raise ValueError(op)


def strip_triangles(s):
    """GX strip order: odd triangles swap their first two corners."""
    for k in range(len(s) - 2):
        yield (s[k + 1], s[k], s[k + 2]) if k & 1 else (s[k], s[k + 1], s[k + 2])


def canonical(t):
    i = t.index(min(t))
    return t[i:] + t[:i]


def stripify(tris):
    """Greedy directed-edge stripifier preserving GX winding."""
    tris = [t for t in tris if len(set(t)) == 3]
    edge = {}
    for n, (a, b, c) in enumerate(tris):
        for e, x in (((a, b), c), ((b, c), a), ((c, a), b)):
            edge.setdefault(e, []).append((n, x))
    used = [False] * len(tris)

    def grow(seed):
        s = list(seed)
        taken = []
        while True:
            k = len(s) - 2
            key = (s[k], s[k + 1]) if k % 2 == 0 else (s[k + 1], s[k])
            nxt = None
            for n, x in edge.get(key, ()):
                if not used[n] and n not in taken:
                    nxt = (n, x)
                    break
            if nxt is None:
                return s, taken
            taken.append(nxt[0])
            s.append(nxt[1])

    strips = []
    for n, t in enumerate(tris):
        if used[n]:
            continue
        used[n] = True
        best = None
        for r in range(3):
            seed = t[r:] + t[:r]
            s, taken = grow(seed)
            if best is None or len(taken) > len(best[1]):
                best = (s, taken)
        for m in best[1]:
            used[m] = True
        strips.append(best[0])
    return strips


def split_strip(s):
    """Chunks of <=MAX_STRIP corners; each restarts at an even triangle."""
    out = []
    start = 0
    while len(s) - start > MAX_STRIP:
        end = start + MAX_STRIP
        if (end - 2 - start) % 2:  # next chunk must begin at an even triangle
            end -= 1
        out.append(s[start:end])
        start = end - 2
    out.append(s[start:])
    return out


def parse_bin(data):
    flags = be32(data, 0x20)
    shift = data[0x28]
    clr = be32(data, 0x0C)
    tex = be32(data, 0x10)
    vtx = be32(data, 0x30)
    nvtx = be16(data, 0x38)
    nparts = be16(data, 0x1A)
    cursor = be32(data, 0x1C)
    record = 8 if flags & 0x80000000 else 6
    if data[0x19] != 1:
        raise ValueError("multi-node BIN")
    scale = 1.0 / (1 << shift)
    positions = [tuple(v * scale for v in struct.unpack_from(">3h", data, vtx + 8 * i)) for i in range(nvtx)]
    parts = []
    for _ in range(nparts):
        pflags = data[cursor + 0x0B]
        texture = data[cursor + 0x0C]
        alpha = data[cursor + 0x0E] if pflags & 4 else 0xFF
        size = be32(data, cursor + 0x18)
        s, end = cursor + 0x20, cursor + 0x20 + size
        strips, loose = [], []
        while s < end:
            op = data[s]
            s += 1
            if op == 0:
                continue
            if op not in (0x80, 0x90, 0x98):
                raise ValueError(f"GX opcode {op:#x}")
            n = be16(data, s)
            s += 2
            corners = []
            for i in range(n):
                r = s + i * record
                p = be16(data, r)
                c = be16(data, r + 4) if record == 8 else None
                t = be16(data, r + record - 2)
                corners.append((p, c, t, be16(data, r + 2)))
            if op == 0x98:
                strips.append(corners)
            else:
                loose.extend(triangles_of(op, corners))
            s += n * record
        # Identity is relative to the first part header: archive compaction may
        # move the part block inside a BIN, never reorder or resize its parts.
        parts.append(dict(offset=cursor - be32(data, 0x1C), size=size, flags=pflags, texture=texture, alpha=alpha,
                          strips=strips, loose=loose))
        cursor = end
    def uv(t):
        o = tex + 4 * t
        if flags & 0x80000000:
            a, b = struct.unpack_from(">2h", data, o)
            return a / 256.0, b / 256.0
        a, b = struct.unpack_from(">2H", data, o)
        return a / 32768.0, b / 32768.0

    def color(c):
        if c is None:
            return (255, 255, 255, 255)
        return tuple(data[clr + 4 * c:clr + 4 * c + 4])

    nrm = be32(data, 0x34)
    nrm8 = bool(flags & 0x20000000)

    def normal(n):
        if nrm8:
            v = struct.unpack_from(">3b", data, nrm + 4 * n)
        else:
            v = struct.unpack_from(">3h", data, nrm + 8 * n)
        length = sum(x * x for x in v) ** 0.5
        return tuple(x / length for x in v) if length else (0.0, 1.0, 0.0)

    return dict(flags=flags, nvtx=nvtx, nparts=nparts, positions=positions, parts=parts, uv=uv, color=color,
                normal=normal, bytes=len(data))


def oct12(n):
    """Unit normal -> 6+6-bit octahedral code (runtime: native_static.cpp oct_normal)."""
    x, y, z = n
    s = abs(x) + abs(y) + abs(z)
    x, y, z = x / s, y / s, z / s
    if z < 0:
        x, y = (1 - abs(y)) * (1 if x >= 0 else -1), (1 - abs(x)) * (1 if y >= 0 else -1)
    qx = min(63, max(0, round((x * 0.5 + 0.5) * 63)))
    qy = min(63, max(0, round((y * 0.5 + 0.5) * 63)))
    return qx | (qy << 6)


def convert(entries, color_scale, cell=0.0, min_fill=64):
    """entries: [(owner, common, bin, path)] -> package bytes, report.

    cell > 0 builds spatial meshlets: triangles are restripped per model-space
    cell and, once it holds min_fill corners, a meshlet closes rather than span
    more than cell units on any axis."""
    meshes, parts, meshlets, vertices, index_bytes = [], [], [], [], bytearray()
    palette, palette_index = [], {}
    report = []
    for owner, common, bin_no, path in entries:
        data = path.read_bytes()
        src = parse_bin(data)
        used = sorted({k[0] for p in src["parts"] for s in p["strips"] for k in s} |
                      {k[0] for p in src["parts"] for t in p["loose"] for k in t})
        if not used:
            continue
        pos = src["positions"]
        lo = [f32(min(pos[i][a] for i in used)) for a in range(3)]
        hi = [f32(max(pos[i][a] for i in used)) for a in range(3)]
        step = [f32(max((hi[a] - lo[a]) / 65535.0, 1e-6)) for a in range(3)]
        q = lambda i: tuple(min(65535, max(0, round((pos[i][a] - lo[a]) / step[a]))) for a in range(3))
        first_part = len(parts)
        mesh_tris = mesh_strips = 0
        for part in src["parts"]:
            if cell:
                # Spatial meshlets: restrip each model-space cell's triangles so a
                # meshlet's bounds describe a compact region the runtime can cull.
                tris = [t for s in part["strips"] for t in strip_triangles(s)]
                tris += [tuple(t) for t in part["loose"]]
                cells = {}
                for t in tris:
                    key = tuple(int(sum(pos[k[0]][a] for k in t) / 3 // cell) for a in range(3))
                    cells.setdefault(key, []).append(t)
                groups = [stripify(cells[key]) for key in sorted(cells)]
            else:
                strips = [list(s) for s in part["strips"]]
                if part["loose"]:
                    strips.extend(stripify([tuple(t) for t in part["loose"]]))
                groups = [strips]
            chunks = [c for g in groups for s in g for c in split_strip(s) if len(c) >= 3]
            uvs = [src["uv"](k[2]) for c in chunks for k in c]
            if uvs:
                ulo = [f32(min(u[a] for u in uvs)) for a in range(2)]
                uhi = [f32(max(u[a] for u in uvs)) for a in range(2)]
            else:
                ulo, uhi = [0.0, 0.0], [0.0, 0.0]
            uscale = [f32(max((uhi[a] - ulo[a]) / 65535.0, 1e-9)) for a in range(2)]
            first_meshlet = len(meshlets)
            current = None

            def close():
                if current and current["strips"]:
                    grid = [q(k[0]) for k in current["keys"]]
                    bmin = [min(g[a] for g in grid) for a in range(3)]
                    bmax = [max(g[a] for g in grid) for a in range(3)]
                    meshlets.append((current["first_vertex"], current["first_index"],
                                     len(index_bytes) - current["first_index"], len(current["keys"]),
                                     current["strips"], *bmin, *bmax))

            for chunk in chunks:
                fresh = [k for k in dict.fromkeys(chunk) if current is None or k not in current["local"]]
                clo = [min(pos[k[0]][a] for k in chunk) for a in range(3)]
                chi = [max(pos[k[0]][a] for k in chunk) for a in range(3)]
                # Large terrain triangles alone exceed a cell; a minimum fill keeps
                # them from becoming 28-byte meshlets of a few corners each.
                spread = current is not None and cell and len(current["keys"]) >= min_fill and \
                    max(max(chi[a], current["hi"][a]) - min(clo[a], current["lo"][a]) for a in range(3)) > cell
                if current is None or spread or len(current["keys"]) + len(fresh) > MAX_MESHLET_VERTICES:
                    close()
                    current = dict(first_vertex=len(vertices), first_index=len(index_bytes), keys=[], local={},
                                   strips=0, lo=clo, hi=chi)
                current["lo"] = [min(clo[a], current["lo"][a]) for a in range(3)]
                current["hi"] = [max(chi[a], current["hi"][a]) for a in range(3)]
                for k in dict.fromkeys(chunk):
                    if k in current["local"]:
                        continue
                    current["local"][k] = len(current["keys"])
                    current["keys"].append(k)
                    r, g, b, a = src["color"](k[1])
                    # Authored CLR0 alpha is kept: the runtime uses it only when the
                    # source selects vertex alpha for the part.
                    argb = (a << 24) | (min(255, round(r * color_scale)) << 16) | \
                           (min(255, round(g * color_scale)) << 8) | min(255, round(b * color_scale))
                    if argb not in palette_index:
                        palette_index[argb] = len(palette)
                        palette.append(argb)
                    if palette_index[argb] > 15:
                        raise ValueError("more than 16 CLR0 values in one package")
                    # Colour slot before the runtime light bake: CLR0 palette index
                    # (4 bits) over a 12-bit octahedral source normal.
                    slot = (palette_index[argb] << 12) | oct12(src["normal"](k[3]))
                    u, v = src["uv"](k[2])
                    qu = min(65535, max(0, round((u - ulo[0]) / uscale[0])))
                    qv = min(65535, max(0, round((v - ulo[1]) / uscale[1])))
                    vertices.append((*q(k[0]), qu, qv, slot))
                index_bytes.append(len(chunk))
                index_bytes.extend(current["local"][k] for k in chunk)
                current["strips"] += 1
                mesh_strips += 1
                mesh_tris += len(chunk) - 2
            close()
            parts.append((part["offset"], part["size"], part["texture"], part["alpha"], part["flags"], 0,
                          first_meshlet, len(meshlets) - first_meshlet, ulo[0], ulo[1], uscale[0], uscale[1]))
        meshes.append((bin_no, int(common), owner, src["nvtx"], src["nparts"], src["flags"],
                       first_part, len(parts) - first_part, *lo, *step, *lo, *hi))
        report.append(dict(owner=owner, common=bool(common), bin=bin_no, source_bytes=src["bytes"],
                           triangles=mesh_tris, strips=mesh_strips, parts=len(parts) - first_part))
    if len(palette) > 65536:
        raise ValueError("palette exceeds uint16")
    body = bytearray()
    offsets = {}
    for name, blob in (("mesh", b"".join(MESH.pack(*m) for m in meshes)),
                       ("part", b"".join(PART.pack(*p) for p in parts)),
                       ("meshlet", b"".join(MESHLET.pack(*m) for m in meshlets)),
                       ("vertex", b"".join(VERTEX.pack(*v) for v in vertices)),
                       ("index", bytes(index_bytes)),
                       ("palette", b"".join(struct.pack("<I", c) for c in palette))):
        start = align(HEADER.size + len(body)) - HEADER.size
        body.extend(b"\0" * (start - len(body)))
        offsets[name] = HEADER.size + len(body)
        body.extend(blob)
    body.extend(b"\0" * (align(HEADER.size + len(body)) - HEADER.size - len(body)))
    total = HEADER.size + len(body)
    header = HEADER.pack(MAGIC, VERSION, total, zlib.crc32(body),
                         len(meshes), len(parts), len(meshlets), len(vertices), len(index_bytes), len(palette),
                         offsets["mesh"], offsets["part"], offsets["meshlet"], offsets["vertex"],
                         offsets["index"], offsets["palette"], COLOR_OCT_NORMAL, 0, 0, 0)
    blob = header + bytes(body)
    summary = dict(package_bytes=total, meshes=len(meshes), parts=len(parts), meshlets=len(meshlets),
                   vertices=len(vertices), strip_bytes=len(index_bytes), palette=len(palette),
                   triangles=sum(r["triangles"] for r in report), strips=sum(r["strips"] for r in report),
                   source_bytes=sum(r["source_bytes"] for r in report), meshes_detail=report)
    return blob, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--owner", type=lambda s: int(s, 0), required=True,
                    help="0xff main scenario, 0xfe common, otherwise source block number")
    ap.add_argument("--bins", type=Path, required=True, help="directory of NNNN.BIN files")
    ap.add_argument("--common", action="store_true", help="BINs are the room's common (shared) set")
    ap.add_argument("--color-policy", choices=["vertex"], default="vertex")
    ap.add_argument("--color-scale", type=float, default=1.0)
    ap.add_argument("--cell", type=float, default=0.0,
                    help="spatial meshlet cell in model units (source mm); 0 keeps source strip order")
    ap.add_argument("--min-fill", type=int, default=64,
                    help="corners a spatial meshlet holds before the cell extent may close it")
    a = ap.parse_args()
    entries = [(a.owner, a.common, int(p.stem), p) for p in sorted(a.bins.glob("*.BIN"))]
    blob, summary = convert(entries, a.color_scale, a.cell, a.min_fill)
    a.out.write_bytes(blob)
    summary.update(format="R4IM", version=VERSION, color_policy=a.color_policy, color_scale=a.color_scale,
                   cell=a.cell, min_fill=a.min_fill,
                   sha256=hashlib.sha256(blob).hexdigest(),
                   meaning="instanced native prelit meshes; colour is authored CLR0 times color_scale (placeholder)")
    Path(str(a.out) + ".json").write_text(json.dumps(summary, indent=1))
    detail = summary.pop("meshes_detail")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
