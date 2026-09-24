"""Standard set on disc: the per-room index the runtime reads (docs/D367_ASSET_PIPELINE.md s16).

write_low(out, ...) lays out out/standard/<room>/low/ (the room's Standard files, as staged under
/cd/dc/native/<room>/low/) and out/standard/<room>/texlow/ (the textures Standard adds, staged
under /cd/dc/texlow/). tools/d367/stage_std.py copies both onto the disc for QUALITY=1 builds.

index.txt is text, one record per line, tokens separated by one space, '#' starts a comment
line; a reader ignores lines whose first token it does not know. Records (s16.3):

  re4dc-std 1 <room>                      first line
  lod_px <px>                             the lod_px the packages were built for
  mesh <OWNER> <bytes> <sha16>            open native/<room>/low/<OWNER>.re4mesh for OWNER
  orig <OWNER> <bytes> <sha16>            the Original package this set was built against
  tex <crc>-<fnv> <w> <h> <vram> <bytes>  a texture Standard adds (/cd/dc/texlow/)
  drop <crc>-<fnv>                        a room texture Standard never draws
  cull <OWNER> <mesh> <bin> <common> <mm>
  imp <OWNER> <mesh> <bin> <common> <mm> <crc>-<fnv> <views> <cols> <cell_w> <cell_h> <atlas_w>
      <atlas_h> <cx> <cy> <cz> <half_w> <half_h>      (one line)
  impt <OWNER> <mesh> <bin> <common> <part> <first> <count> <mm> <crc>-<fnv> <views> <cols> <cell_w>
      <cell_h> <atlas_w> <atlas_h> <cx> <cy> <cz> <half_w> <half_h>   (one line; one per tree)
  ptex <OWNER> <part> <bin> <common> <crc>-<fnv> <w> <h>
  end <records>                           last line: the number of records above it
"""
import hashlib
import json
import os
import shutil
import struct
import sys
import zlib
from pathlib import Path

SCHEMA = "re4dc-std"
IMPT_CLUSTERS = 64      # impt: a tree's clusters must lie within the first 64 of its part
VERSION = 1


def sha16(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def image_key(image):
    """The runtime source identity of a TPL image (prepare_native_ui.image_identity)."""
    palette = image.palette_data or b""
    meta = struct.pack("<5I", image.width, image.height, image.format,
                       image.palette_format if image.palette_format is not None else 0xffffffff, len(palette))
    payload = meta + image.data + palette
    fnv = 2166136261
    for b in payload:
        fnv = ((fnv ^ b) * 16777619) & 0xffffffff
    return "%08x-%08x" % (zlib.crc32(payload) & 0xffffffff, fnv)


def tpl_keys(tpl_path, tools_dir):
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import convert_tpl
    return [image_key(im) for im in convert_tpl.parse_tpl(Path(tpl_path).read_bytes())]


def used_textures(pk, skip_parts=()):
    """Room TPL indices the package's drawing parts reference (a part with a ptex record draws
    its baked texture instead, so its source image is not counted)."""
    used = set()
    for i, p in enumerate(pk.parts):
        if p[7] > 0 and i not in skip_parts:
            used.add(p[2])
            if p[4] & 4 and p[3] != 255:
                used.add(p[3])
    return used


def _code(owner):
    return int(owner, 0) if isinstance(owner, str) else int(owner)


def _key(k):
    return "%s-%s" % tuple(k) if isinstance(k, (list, tuple)) else str(k)


def _f(x):
    s = "%.3f" % float(x)
    return "0.000" if s == "-0.000" else s


def build(room, lod_px, owners, std_pkgs, std_files, orig_files, bins, imp_recs, shell_textures, tex_files,
          room_keys, tree_recs=None):
    """-> (index text, low file names, texlow {name: path}).
    owners: [(name, code, common)]; std_pkgs {name: r4im.Package}; std_files / orig_files
    {name: path of the .re4mesh}; bins {"OWNER/0xNN:b": {imp_mm?, cull_mm?}} (the plan's final
    choices); imp_recs {(code, bin): record}; shell_textures: textures.json rows; tex_files: the
    added .re4tex paths; room_keys: runtime key of every room TPL index; tree_recs {(code, bin):
    [grove.py tree record]} for BINs whose option is split (s16.5: impt records)."""
    tree_recs = tree_recs or {}
    code_of = {n: c for n, c, _ in owners}
    lines = ["%s %d %s" % (SCHEMA, VERSION, room), "lod_px %s" % ("%g" % lod_px)]
    low = []
    for name, _, _ in owners:
        s, o = Path(std_files[name]), Path(orig_files[name])
        if s.read_bytes() != o.read_bytes():
            low.append(name)
            lines.append("mesh %s %d %s" % (name, s.stat().st_size, sha16(s)))
    for name, _, _ in owners:
        o = Path(orig_files[name])
        lines.append("orig %s %d %s" % (name, o.stat().st_size, sha16(o)))
    texlow = {}
    for f in sorted(tex_files, key=lambda p: Path(p).name):
        from .texture import read_re4tex
        t = read_re4tex(f)
        tx = t["textures"][0]
        texlow[Path(f).name] = f
        # VRAM = the uploaded payload (texture_package.cpp: vram_bytes_ += data_size); read_re4tex's
        # formula does not know item 20's PAL4 VQ atlases (format 3)
        lines.append("tex %s %d %d %d %d" % (Path(f).stem, tx["width"], tx["height"],
                                             sum(x["data_bytes"] for x in t["textures"]), t["file_bytes"]))
    # per-mesh records, keyed by the index of the mesh / part in the package Standard opens
    ptex = {}
    for r in shell_textures:
        code = _code(r["owner"])
        name = next(n for n, c, _ in owners if c == code)
        pk = std_pkgs[name]
        mk = pk.mesh_by_bin().get((r["bin"], bool(r["common"])))
        if mk is None:
            continue
        m = pk.meshes[mk]
        if not 0 <= r["part"] < m[7]:
            raise ValueError("%s BIN %d has no part %d" % (name, r["bin"], r["part"]))
        ptex.setdefault(name, []).append((m[6] + r["part"], r["bin"], int(bool(r["common"])), _key(r["key"]),
                                          r["width"], r["height"]))
    cull, imp, impt = {}, {}, {}
    for k, o in sorted(bins.items()):
        name, bid = k.split("/")
        code, b = (int(x, 0) for x in bid.split(":"))
        pk = std_pkgs.get(name)
        if pk is None:
            continue
        for (bb, common), mk in sorted(pk.mesh_by_bin().items()):
            if bb != b:
                continue
            if o.get("cull_mm"):
                cull.setdefault(name, []).append((mk, b, int(common), int(round(o["cull_mm"]))))
            if o.get("imp_mm") and o.get("split"):
                rs = tree_recs.get((code, b))
                if not rs:
                    raise ValueError("%s: split impostor distance without tree records" % k)
                m = pk.meshes[mk]
                for r in sorted(rs, key=lambda r: (r["part"], r["first"])):
                    if bool(r["common"]) != bool(common):
                        continue
                    if not 0 <= r["part"] < m[7]:
                        raise ValueError("%s: tree record for missing part %d" % (k, r["part"]))
                    p = m[6] + r["part"]
                    if r["first"] + r["count"] > min(pk.part_lod[p][1], IMPT_CLUSTERS):
                        # the runtime keeps one 64-bit skip mask per part (std-runtime, 2026-09-23)
                        raise ValueError("%s: tree clusters %d+%d beyond the part's %d" % (
                            k, r["first"], r["count"], pk.part_lod[p][1]))
                    if Path(r["tex_file"]).name not in texlow:
                        raise ValueError("%s: tree atlas %s is not in texlow" % (k, Path(r["tex_file"]).name))
                    cw, ch = r["cell"]
                    aw, ah = r["atlas"]
                    impt.setdefault(name, []).append((mk, b, int(common), p, r["first"], r["count"],
                                                      int(round(o["imp_mm"])), _key(r["key"]), r["views"], r["cols"],
                                                      cw, ch, aw, ah, *r["centre"], r["half_w"], r["half_h"]))
            elif o.get("imp_mm"):
                r = imp_recs.get((code, b))
                if r is None:
                    raise ValueError("%s: impostor distance without a record" % k)
                if r.get("tex_file") and Path(r["tex_file"]).name not in texlow:
                    raise ValueError("%s: atlas %s is not in texlow" % (k, Path(r["tex_file"]).name))
                cw, ch = r["cell"]
                aw, ah = r["atlas"]
                imp.setdefault(name, []).append((mk, b, int(common), int(round(o["imp_mm"])), _key(r["key"]),
                                                 r["views"], r["cols"], cw, ch, aw, ah, *r["centre"], r["half_w"],
                                                 r["half_h"]))
    skip = {n: {p[0] for p in rows} for n, rows in ptex.items()}
    used_std = set()
    for name, pk in std_pkgs.items():
        used_std |= used_textures(pk, skip.get(name, ()))
    for name in sorted(code_of):
        for row in sorted(cull.get(name, [])):
            lines.append("cull %s %d %d %d %d" % ((name,) + row))
        for row in sorted(imp.get(name, [])):
            lines.append("imp %s %d %d %d %d %s %d %d %d %d %d %d %s %s %s %s %s" % (
                (name,) + row[:11] + tuple(_f(x) for x in row[11:])))
        for row in sorted(impt.get(name, [])):
            lines.append("impt %s %d %d %d %d %d %d %d %s %d %d %d %d %d %d %s %s %s %s %s" % (
                (name,) + row[:14] + tuple(_f(x) for x in row[14:])))
        rows = sorted(ptex.get(name, []))
        if len({r[0] for r in rows}) != len(rows):
            raise ValueError("%s: two ptex records for one part" % name)
        for row in rows:
            lines.append("ptex %s %d %d %d %s %d %d" % ((name,) + row))
    return lines, low, texlow, used_std


def finish(lines, dropped):
    body = lines + ["drop %s" % k for k in dropped]
    return "\n".join(body + ["end %d" % len(body)]) + "\n"


def write_low(out, room, lod_px, owners, std_pkgs, std_files, orig_files, orig_pkgs, bins, imp_recs,
              shell_textures, tex_files, room_keys, plan_json, tree_recs=None):
    """Lay out out/low/ and out/texlow/; -> dict(report)."""
    lines, low, texlow, used_std = build(room, lod_px, owners, std_pkgs, std_files, orig_files, bins, imp_recs,
                                         shell_textures, tex_files, room_keys, tree_recs)
    used_orig = set()
    for pk in orig_pkgs.values():
        used_orig |= used_textures(pk)
    dropped = sorted({room_keys[i] for i in used_orig - used_std if i < len(room_keys)}
                     - {room_keys[i] for i in used_std if i < len(room_keys)})
    text = finish(lines, dropped)
    out = Path(out)
    for d in ("low", "texlow"):
        if (out / d).exists():
            shutil.rmtree(out / d)
        (out / d).mkdir(parents=True)
    for name in low:
        _link(std_files[name], out / "low" / (name + ".re4mesh"))
    for n, f in sorted(texlow.items()):
        _link(f, out / "texlow" / n)
    (out / "low" / "index.txt").write_text(text)
    shutil.copy2(plan_json, out / "low" / "plan.json")
    return dict(low=low, texlow=sorted(texlow), dropped=dropped, records=len(text.splitlines()) - 1,
                index_bytes=len(text.encode()),
                low_bytes=sum(Path(std_files[n]).stat().st_size for n in low),
                texlow_bytes=sum(Path(f).stat().st_size for f in texlow.values()))


def _link(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def parse(text):
    """-> dict of lists (the reader the tests and stage_std.py use; mirrors the runtime rules)."""
    rows = text.splitlines()
    if not rows or rows[0].split()[:2] != [SCHEMA, str(VERSION)]:
        raise ValueError("index: bad first line")
    last = rows[-1].split()
    body = [r for r in rows[:-1]]
    if last[:1] != ["end"] or int(last[1]) != len(body):
        raise ValueError("index: truncated (no matching end record)")
    out = dict(room=rows[0].split()[2], lod_px=None, mesh=[], orig=[], tex=[], drop=[], cull=[], imp=[], impt=[],
               ptex=[])
    for r in body[1:]:
        t = r.split(" ")
        if not t or t[0].startswith("#"):
            continue
        if t[0] == "lod_px":
            out["lod_px"] = float(t[1])
        elif t[0] in out and isinstance(out[t[0]], list):
            out[t[0]].append(t[1:])
    return out
