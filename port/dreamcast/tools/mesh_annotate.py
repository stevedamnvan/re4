#!/usr/bin/env python3
"""Append runtime tables to an R4IM v2/v3 mesh package (convert_room_bins.py --lod).

LOD header word 7 ('reserved'; W9b uses words 5/6 for class/rule offsets) =
offset of a 32-byte runtime-table head {impostor offset, impostor count,
texture offset, 5 zero words}, written after the tables.

  mesh_annotate.py <in.re4mesh> <out.re4mesh> [--impostors MANIFEST.json] [--textures MANIFEST.json]

--impostors (game TREE_IMPOSTOR=1; tree_impostors.py manifest): one
MeshImpostor record (instanced_mesh.hpp) per listed BIN present in the
package, ascending by mesh index, 32-byte aligned after the last section;
head words 0/1 = its offset/count. Header bytes and CRC are
updated; every other byte is unchanged, so a runtime without the knob draws
exactly the geometry it drew before. Records for BINs the package does not
hold are skipped (the manifest covers the room's common set).

--textures (game MESH_TEXTURES=1; house_shells.py manifest): one MeshTexture
record (instanced_mesh.hpp) per listed (BIN, part): package part index,
texture size and prepared package key; head word 2 = offset of a
u32 count followed by the records, ascending by part index.
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_room_bins as crb  # noqa: E402

IMPOSTOR = struct.Struct("<3I6H5fI")  # 48 bytes
TEXTURE = struct.Struct("<I2H2I")      # 16 bytes


def meshes(blob):
    h = crb.HEADER.unpack_from(blob, 0)
    count, offset = h[4], h[10]
    return [crb.MESH.unpack_from(blob, offset + i * crb.MESH.size) for i in range(count)]


def annotate(blob, impostors=None, textures=None):
    h = list(crb.HEADER.unpack_from(blob, 0))
    if h[0] != crb.MAGIC or h[1] not in (crb.VERSION_LOD, crb.VERSION_SHARE) or h[2] != len(blob):
        raise ValueError("expected a complete R4IM v2/v3 package")
    lod = list(crb.LOD_HEADER.unpack_from(blob, crb.HEADER.size))
    rt = [0, 0, 0]  # runtime-table head words 0..2 (LOD word 7 points at the head)
    if lod[7]:
        raise ValueError("package already carries runtime tables")
    out = bytearray(blob)
    report = {}
    if impostors:
        index = {(m[0], bool(m[1])): i for i, m in enumerate(meshes(blob))}
        rows = []
        for r in impostors["records"]:
            m = index.get((r["bin"], bool(r["common"])))
            if m is None:
                continue
            rows.append((m, int(r["key"][0], 16), int(r["key"][1], 16), r["views"], r["cols"], r["cell"][0],
                         r["cell"][1], r["atlas"][0], r["atlas"][1], *r["centre"], r["half_w"], r["half_h"], 0))
        rows.sort()
        if len({r[0] for r in rows}) != len(rows):
            raise ValueError("two impostor records for one mesh")
        if rows:
            out.extend(b"\0" * (crb.align(len(out)) - len(out)))
            rt[0], rt[1] = len(out), len(rows)
            for r in rows:
                out.extend(IMPOSTOR.pack(*r))
        report["impostors"] = len(rows)
    if textures:
        mesh_rows = meshes(blob)
        index = {(m[0], bool(m[1])): i for i, m in enumerate(mesh_rows)}
        rows = []
        for r in textures["textures"]:
            m = index.get((r["bin"], bool(r["common"])))
            if m is None:
                continue
            first, count = mesh_rows[m][6], mesh_rows[m][7]
            if not 0 <= r["part"] < count:
                raise ValueError("BIN %d has no part %d" % (r["bin"], r["part"]))
            rows.append((first + r["part"], r["width"], r["height"], int(r["key"][0], 16), int(r["key"][1], 16)))
        rows.sort()
        if len({r[0] for r in rows}) != len(rows):
            raise ValueError("two texture records for one part")
        if rows:
            out.extend(b"\0" * (crb.align(len(out)) - len(out)))
            rt[2] = len(out)
            out.extend(struct.pack("<I", len(rows)))
            for r in rows:
                out.extend(TEXTURE.pack(*r))
        report["textures"] = len(rows)
    if any(rt):
        out.extend(b"\0" * (crb.align(len(out)) - len(out)))
        lod[7] = len(out)
        out.extend(struct.pack("<8I", *rt, 0, 0, 0, 0, 0))
    out.extend(b"\0" * (crb.align(len(out)) - len(out)))
    crb.LOD_HEADER.pack_into(out, crb.HEADER.size, *lod)
    h[2] = len(out)
    h[3] = zlib.crc32(bytes(out[crb.HEADER.size:])) & 0xFFFFFFFF
    crb.HEADER.pack_into(out, 0, *h)
    return bytes(out), report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--impostors", type=Path)
    ap.add_argument("--textures", type=Path)
    a = ap.parse_args()
    impostors = json.loads(a.impostors.read_text()) if a.impostors else None
    textures = json.loads(a.textures.read_text()) if a.textures else None
    blob, report = annotate(a.src.read_bytes(), impostors, textures)
    a.out.write_bytes(blob)
    print(json.dumps(dict(report, bytes=len(blob))))


if __name__ == "__main__":
    main()
