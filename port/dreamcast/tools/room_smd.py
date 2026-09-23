#!/usr/bin/env python3
"""Room SMD scenery for any room: BIN extraction, placement scales and the
native-mesh release contract (D367 W9).

A room's static scenery is its SMD (game/scroll.cpp cSmd): a 16-byte header
(version, flags, work count, BIN / TPL / FCV table offsets), optional group
counts, one 72-byte SmdWork per placement (pos, rot, scale, binNo, tplNo,
motNo, id, ..., flags at +0x44; flags bit 4 = BIN and TPL from the common SMD)
and the tables. Table entries are offsets from the table itself.

  room_smd.py extract <room.das|tagged archive|.SMD> <outdir>
      Local (non-common) BINs as <outdir>/NNNN.BIN in source byte order, plus
      placements.json and scales.json (largest |scale| per BIN, the form
      convert_room_bins.py --scales takes, owner 0xff).
  room_smd.py release <room.arc|room.dar> <MAINSCENARIO.re4mesh.json> <out>
      The release contract below, applied to a converted (little-endian)
      room archive or its .dar container; writes <out>.json with per-BIN
      savings. Every other sub-file stays byte-identical.

Release contract. A BIN that a native R4IM package covers completely (every
source part, single node, rigid, no shape table; convert_room_bins.py lists
these in its summary under "release") is never drawn from its GX data. Its
render payload leaves the archive and the BIN keeps only what the game still
reads (model.cpp getBoundingBox / calcModelAddr, trans.cpp part walk and
shaderSetup, scroll.cpp SmdSetParam, model_bridge.cpp):
  - header, joint heads (pHead), weights, blend/flip tables: unchanged;
  - vertices: 2 records, the source box corners (min, max; so getBoundingBox
    and the light/cull bounds are unchanged), nVtx = 2;
  - normals: 1 record (nNrm = 1); UVs: 1 record;
  - CLR0: unchanged, still directly followed by the UV array (the bridge
    bounds vertex alpha over pClr..pTex);
  - parts: every 32-byte part header, in order, with its stream size set to 0
    and no stream, so parts stay 32-byte aligned and the walk steps 32 bytes.
The runtime (native_static.cpp) recognises nVtx == 2 with a zero stream size
as released and matches parts by index (offset / 32) instead of by source
offset and size. A released part never falls back to GX data: any path that
would (no package, reserve failure) draws nothing. The released archive is
therefore only valid together with its packages and NATIVE_MESH=1.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

WORK_SIZE = 72
COMMON_FLAG = 0x10
RELEASED_VERTICES = 2  # instanced_mesh.hpp kReleasedVertices
# releasable() reasons that also keep a BIN off the native mesh path
# (model_bridge.cpp static_geometry); other reasons only block the release.
RENDER_UNQUALIFIED = ("multi-node", "shape", "skinned", "version", "empty")
CONTAINER_MAGIC = b"\xca\xb6\xbe\x20" * 8


def align(n, a=32):
    return (n + a - 1) & ~(a - 1)


# ---- containers -------------------------------------------------------------
def tagged_entries(data, e):
    """Tagged archive (u32 count, 12 bytes, u32 offsets[count], tags[count][4])
    -> [(tag, start, end)] in index order; ends follow the next larger offset."""
    n = struct.unpack_from(e + "I", data, 0)[0]
    if not 0 < n <= 0x100 or 0x10 + 8 * n > len(data):
        raise ValueError("not a tagged archive")
    offs = struct.unpack_from(e + "%dI" % n, data, 0x10)
    tags = [bytes(data[0x10 + 4 * n + 4 * i:0x14 + 4 * n + 4 * i]) for i in range(n)]
    out = []
    for i in range(n):
        later = [o for o in offs if o > offs[i]]
        out.append((tags[i], offs[i], min(later) if later else len(data)))
    return out


def archive_endian(data):
    for e in (">", "<"):
        n = struct.unpack_from(e + "I", data, 0)[0]
        if 0 < n <= 0x100 and 0x10 + 8 * n <= len(data) and not any(data[4:16]):
            first = struct.unpack_from(e + "I", data, 0x10)[0]
            if 0x10 + 8 * n <= first <= len(data):
                return e
    raise ValueError("not a tagged archive")


def decode_das(data):
    """Room DVD container -> its decoded (source byte order) tagged archive."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from decode_yz2 import decode
    payloads = []
    for pos in range(0x20, 0x400, 0x20):
        kind, size, _, offset = struct.unpack_from(">4I", data, pos)
        if kind == 0xFFFFFFFF:
            break
        if kind == 0:
            payloads.append((offset, size))
    if len(payloads) != 1:
        raise ValueError("expected one type-0 room payload")
    offset, size = payloads[0]
    return bytes(decode(data[offset:offset + size]))


def load_smd(path):
    """-> (smd bytes, byte order '>' or '<') from a .das, a tagged archive or an SMD."""
    data = Path(path).read_bytes()
    if data[:32] == CONTAINER_MAGIC:
        data = decode_das(data)
    try:
        e = archive_endian(data)
    except ValueError:
        return data, smd_endian(data)
    smd = [(s, t) for tag, s, t in tagged_entries(data, e) if tag == b"SMD\0"]
    if len(smd) != 1:
        raise ValueError("%s: expected one SMD, found %d" % (path, len(smd)))
    return data[smd[0][0]:smd[0][1]], e


def smd_endian(data):
    for e in (">", "<"):
        count = struct.unpack_from(e + "H", data, 2)[0]
        tables = struct.unpack_from(e + "3I", data, 4)
        if count and all(0x10 <= t <= len(data) for t in tables):
            return e
    raise ValueError("not an SMD")


# ---- SMD --------------------------------------------------------------------
class Smd:
    def __init__(self, data, e=">"):
        self.data, self.e = bytes(data), e
        self.flag = data[1]
        self.count = struct.unpack_from(e + "H", data, 2)[0]
        self.tables = list(struct.unpack_from(e + "3I", data, 4))
        work = 0x10
        if self.flag & 1:
            work = 0x14 + 4 * struct.unpack_from(e + "I", data, 0x10)[0]
        self.work = work
        self.placements = []
        for i in range(self.count):
            p = work + i * WORK_SIZE
            f = struct.unpack_from(e + "9f", data, p)
            b, t, m, ident = data[p + 36:p + 40]
            flags = struct.unpack_from(e + "I", data, p + 0x44)[0]
            self.placements.append(dict(work=i, pos=f[0:3], rot=f[3:6], scale=f[6:9], bin=b, tpl=t, mot=m,
                                        id=ident, flags=flags, common=bool(flags & COMMON_FLAG)))

    def used(self):
        return [p for p in self.placements if p["id"] != 0xFF]

    def local_bins(self):
        return sorted({p["bin"] for p in self.used() if not p["common"]})

    def bin_table(self):
        """-> (table offset, [BIN start] for indices 0..max local, region end)."""
        local = self.local_bins()
        base = self.tables[0]
        n = max(local) + 1 if local else 0
        starts = [base + struct.unpack_from(self.e + "I", self.data, base + 4 * i)[0] for i in range(n)]
        later = [t for t in self.tables[1:] if t > base]
        end = min(later) if later else len(self.data)
        return base, starts, end

    def bins(self):
        """Local BINs -> {index: bytes}; a body ends at the next BIN start or the region end."""
        base, starts, end = self.bin_table()
        cuts = sorted(set(starts + [end]))
        out = {}
        for i in self.local_bins():
            s = starts[i]
            if not base < s < end:
                raise ValueError("BIN %d outside the BIN region" % i)
            out[i] = self.data[s:min(c for c in cuts if c > s)]
        return out

    def scales(self, owner=0xFF):
        out = {}
        for p in self.used():
            if p["common"]:
                continue
            key = "%d:%d" % (owner, p["bin"])
            out[key] = max(out.get(key, 0.0), max(abs(s) for s in p["scale"]))
        return out


# ---- BIN layout -------------------------------------------------------------
BIN_POINTERS = (("head", 0), ("clr", 12), ("tex", 16), ("weight", 20), ("parts", 28), ("shape", 44),
                ("vtx", 48), ("nrm", 52))


def bin_layout(b, e):
    """ModelData fields and pointer regions (each region runs to the next pointer)."""
    u32 = lambda o: struct.unpack_from(e + "I", b, o)[0]
    u16 = lambda o: struct.unpack_from(e + "H", b, o)[0]
    version = u32(60)
    ptr = {k: u32(o) for k, o in BIN_POINTERS}
    if version == 0x20030818:
        ptr.update(blend=u32(64), flip=u32(68))
    head = 72 if version == 0x20030818 else 64
    starts = sorted({v for v in ptr.values() if v} | {len(b)})
    region = {k: (v, min(s for s in starts if s > v)) for k, v in ptr.items() if v}
    return dict(version=version, head_bytes=head, ptr=ptr, region=region, nw=b[24], nj=b[25], nd=u16(26),
                flags=u32(32), ext=u16(42), nv=u16(56), nn=u16(58))


def part_headers(b, e, lay):
    """-> [(offset from the first part header, stream size)] in source order."""
    out, cur = [], lay["ptr"]["parts"]
    for _ in range(lay["nd"]):
        size = struct.unpack_from(e + "I", b, cur + 0x18)[0]
        out.append((cur - lay["ptr"]["parts"], size))
        cur += 0x20 + size
    return out


def releasable(b, e):
    """None when the release stub is exact for this BIN, else the reason."""
    lay = bin_layout(b, e)
    if lay["version"] not in (0x20010801, 0x20030818):
        return "version"
    if lay["nj"] != 1:
        return "multi-node"
    if lay["ptr"]["shape"]:
        return "shape"
    if lay["nw"] > 1 or lay["ext"] > 0xFF:
        return "skinned"
    if not lay["nv"] or not lay["nn"]:
        return "empty"
    order = sorted((v, k) for k, v in lay["ptr"].items() if v)
    names = [k for _, k in order]
    if "clr" in names and names[names.index("clr") + 1:names.index("clr") + 2] != ["tex"]:
        return "CLR0 not followed by UVs"
    for k in ("vtx", "nrm", "tex", "parts"):
        if k not in lay["region"]:
            return "no %s" % k
    heads = part_headers(b, e, lay)
    if heads and heads[-1][0] + 0x20 + heads[-1][1] > lay["region"]["parts"][1] - lay["ptr"]["parts"]:
        return "parts overrun"
    if lay["ptr"]["parts"] % 32 or lay["ptr"]["vtx"] % 4:
        return "alignment"
    return None


def release_bin(b, e):
    """Source BIN (either byte order) -> the release stub (module docstring)."""
    why = releasable(b, e)
    if why:
        raise ValueError("BIN not releasable: " + why)
    lay = bin_layout(b, e)
    nv = lay["nv"]
    vtx = lay["ptr"]["vtx"]
    pos = [struct.unpack_from(e + "3h", b, vtx + 8 * i) for i in range(nv)]
    lo = [min(p[a] for p in pos) for a in range(3)]
    hi = [max(p[a] for p in pos) for a in range(3)]
    nrm_bytes = 4 if lay["flags"] & 0x20000000 else 8
    new = {
        "vtx": struct.pack(e + "4h", *lo, 0) + struct.pack(e + "4h", *hi, 0),
        "nrm": b[lay["ptr"]["nrm"]:lay["ptr"]["nrm"] + nrm_bytes],
        "tex": b[lay["ptr"]["tex"]:lay["ptr"]["tex"] + 4],
    }
    heads = part_headers(b, e, lay)
    parts = bytearray()
    for off, _ in heads:
        h = bytearray(b[lay["ptr"]["parts"] + off:lay["ptr"]["parts"] + off + 0x20])
        struct.pack_into(e + "I", h, 0x18, 0)
        parts += h
    new["parts"] = bytes(parts)
    out = bytearray(b[:min(v for v in lay["ptr"].values() if v)])
    moved = {}
    for start, name in sorted((v, k) for k, v in lay["ptr"].items() if v):
        body = new.get(name, b[lay["region"][name][0]:lay["region"][name][1]])
        # CLR0 keeps its exact length so the UV array follows it directly.
        out += bytes((-len(out)) % (4 if name == "tex" else 32))
        moved[name] = len(out)
        out += body
    out += bytes((-len(out)) % 32)
    for name, o in dict(BIN_POINTERS + (("blend", 64), ("flip", 68))).items():
        if name in moved:
            struct.pack_into(e + "I", out, o, moved[name])
    struct.pack_into(e + "HH", out, 56, RELEASED_VERTICES, 1)
    return bytes(out)


def released_bounds(b, e):
    """getBoundingBox over a BIN's vertex array (for checks)."""
    lay = bin_layout(b, e)
    shift = b[0x28]
    pos = [struct.unpack_from(e + "3h", b, lay["ptr"]["vtx"] + 8 * i) for i in range(lay["nv"])]
    lo = [min(p[a] for p in pos) / (1 << shift) for a in range(3)]
    hi = [max(p[a] for p in pos) / (1 << shift) for a in range(3)]
    return [(lo[a] + hi[a]) / 2 for a in range(3)], [(hi[a] - lo[a]) / 2 for a in range(3)]


def release_smd(smd, e, release):
    """-> (new SMD bytes, report). release: {bin index: package identity dict
    (vertices, parts, part_offsets, part_sizes)}; each BIN is checked against
    it before its payload is dropped."""
    s = Smd(smd, e)
    base, starts, end = s.bin_table()
    first = min(starts) if starts else end
    order = sorted(set(starts))
    body = {st: smd[st:min([x for x in order if x > st] + [end])] for st in order}
    new_region, where, report = bytearray(), {}, []
    index_of = {}
    for i, st in enumerate(starts):
        index_of.setdefault(st, []).append(i)
    for st in order:
        b = body[st]
        ids = index_of[st]
        want = [i for i in ids if i in release]
        if want:
            ident = release[want[0]]
            lay = bin_layout(b, e)
            heads = part_headers(b, e, lay)
            got = dict(vertices=lay["nv"], parts=lay["nd"], part_offsets=[o for o, _ in heads],
                       part_sizes=[z for _, z in heads])
            for k, v in got.items():
                if k in ident and ident[k] != v:
                    raise ValueError("BIN %d: %s differs from its package" % (want[0], k))
            stub = release_bin(b, e)
            report.append(dict(bin=want[0], source=len(b), resident=len(stub), parts=lay["nd"]))
            b = stub
        new_region += bytes((-(first + len(new_region))) % 32)
        where[st] = first + len(new_region)
        new_region += b
    new_region += bytes((-(first + len(new_region))) % 32)
    delta = (first + len(new_region)) - end
    out = bytearray(smd[:first]) + new_region + smd[end:]
    for i, st in enumerate(starts):
        struct.pack_into(e + "I", out, base + 4 * i, where[st] - base)
    tables = [t + delta if t >= end else t for t in s.tables]
    struct.pack_into(e + "3I", out, 4, *tables)
    return bytes(out), dict(smd_source=len(smd), smd_resident=len(out), saved=len(smd) - len(out), bins=report,
                            bin_region_start=first, bin_region_end=end)


def release_archive(arc, release):
    """Converted room archive -> (archive with its SMD released, report)."""
    e = archive_endian(arc)
    entries = tagged_entries(arc, e)
    smd = [i for i, (tag, _, _) in enumerate(entries) if tag == b"SMD\0"]
    if len(smd) != 1:
        raise ValueError("expected one SMD in the room archive")
    _, s, t = entries[smd[0]]
    new_smd, report = release_smd(arc[s:t], e, release)
    delta = len(new_smd) - (t - s)
    if delta % 32:
        raise ValueError("SMD size change is not 32-byte aligned")
    out = bytearray(arc[:s]) + new_smd + arc[t:]
    for i, (_, o, _) in enumerate(entries):
        if o >= t and o != s:
            struct.pack_into(e + "I", out, 0x10 + 4 * i, o + delta)
    # Only the BIN region shrinks: SMD bytes from its end on (TPL / FCV tables)
    # and every later sub-file move by delta.
    region_start, moved_from = s + report.pop("bin_region_start"), s + report.pop("bin_region_end")
    for tag, o, _ in entries:
        if tag == b"ESQ\0":
            raise ValueError("ESQ effect identity index: absolute offsets not rebased by release")
        if tag == b"NTR\0":
            rebase_native_table(out, o + delta if o >= t else o, e, region_start, moved_from, delta)
    report.update(archive_source=len(arc), archive_resident=len(out))
    return bytes(out), report


NATIVE_TABLE_MAGIC = b"R4NTBL\0\0"


def rebase_native_table(out, at, e, region_start, moved_from, delta):
    """prepare_native_ui.py --compact-room NTR index (magic, version, count,
    stride 12, crc32(records), original bytes, resident bytes; records of
    absolute payload / header / TPL offsets): rebase offsets past the BIN
    region, set the resident size, recompute the CRC. texture_package.cpp
    SourceIdentityTable rejects the archive otherwise."""
    import zlib
    magic, version, count, stride, _, original, _ = struct.unpack_from(e + "8s6I", out, at)
    if magic != NATIVE_TABLE_MAGIC or version != 1 or stride != 12:
        raise ValueError("unknown NTR index")
    for k in range(3 * count):
        p = at + 32 + 4 * k
        v = struct.unpack_from(e + "I", out, p)[0]
        if region_start <= v < moved_from:
            raise ValueError("NTR record inside the released BIN region")
        if v >= moved_from:
            struct.pack_into(e + "I", out, p, v + delta)
    crc = zlib.crc32(bytes(out[at + 32:at + 32 + 12 * count])) & 0xFFFFFFFF
    struct.pack_into(e + "8s6I", out, at, magic, version, count, stride, crc, original, len(out))


def release_container(data, release):
    """.dar (converted DVD container, room in the first type-0 slot) or a bare
    converted room archive -> the same form, released (le_mirror.py
    replace_native_payload keeps nested sound entries untouched)."""
    if data[:32] != CONTAINER_MAGIC:
        return release_archive(data, release)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import le_mirror
    slot = le_mirror.native_payload_slot(data)
    _, size, _, offset = struct.unpack_from("<4I", data, slot)
    arc, report = release_archive(data[offset:offset + size], release)
    # replace_native_payload appends; a payload that already ends the
    # container (an earlier native payload) is dropped rather than kept as
    # dead disc bytes. Nested sound entries lie before it and never move.
    others = []
    for pos in range(0x20, 0x400, 0x20):
        kind, _, _, at = struct.unpack_from("<4I", data, pos)
        if kind == 0xFFFFFFFF:
            break
        if pos != slot:
            others.append(at)
    tail = align(offset + size) == len(data) and all(at < offset for at in others)
    if tail and offset % 32 == 0:  # the same slot record replace_native_payload writes
        out = bytearray(data[:offset]) + arc + bytes((-len(arc)) & 31)
        struct.pack_into("<4I", out, slot, 0, len(arc), 0, offset)
        out = bytes(out)
    else:
        out = bytes(le_mirror.replace_native_payload(data, arc))
    le_mirror.native_payload_slot(out)
    report.update(container_source=len(data), container=len(out))
    return out, report


def package_release(summary):
    """convert_room_bins.py summary JSON -> {bin: identity} of releasable BINs."""
    return {int(r["bin"]): r for r in summary.get("release", [])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("extract")
    x.add_argument("source", type=Path)
    x.add_argument("out", type=Path)
    x.add_argument("--owner", type=lambda v: int(v, 0), default=0xFF)
    r = sub.add_parser("release")
    r.add_argument("archive", type=Path)
    r.add_argument("package_json", type=Path)
    r.add_argument("out", type=Path)
    a = ap.parse_args()
    if a.cmd == "extract":
        smd, e = load_smd(a.source)
        s = Smd(smd, e)
        a.out.mkdir(parents=True, exist_ok=True)
        bins = s.bins()
        for i, b in bins.items():
            if e == "<":
                raise ValueError("extract needs source byte order (.das, decoded archive or source SMD)")
            (a.out / ("%04d.BIN" % i)).write_bytes(b)
        (a.out / "placements.json").write_text(json.dumps(s.used(), indent=0))
        (a.out / "scales.json").write_text(json.dumps(s.scales(a.owner), indent=0, sort_keys=True))
        why = {i: releasable(b, e) for i, b in bins.items()}
        print(json.dumps(dict(source=str(a.source), smd_bytes=len(smd), sha256=hashlib.sha256(smd).hexdigest(),
                              placements=len(s.used()), common_placements=sum(p["common"] for p in s.used()),
                              local_bins=len(bins), bin_bytes=sum(len(b) for b in bins.values()),
                              not_releasable={i: w for i, w in why.items() if w})))
    else:
        release = package_release(json.loads(a.package_json.read_text()))
        out, report = release_container(a.archive.read_bytes(), release)
        if a.out.exists():
            raise FileExistsError(a.out)
        a.out.write_bytes(out)
        report.update(archive=str(a.archive), package=str(a.package_json), sha256=hashlib.sha256(out).hexdigest())
        Path(str(a.out) + ".json").write_text(json.dumps(report, indent=1))
        print(json.dumps({k: v for k, v in report.items() if k != "bins"}))


if __name__ == "__main__":
    main()
