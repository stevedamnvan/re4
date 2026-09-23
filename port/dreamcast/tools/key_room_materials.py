#!/usr/bin/env python3
"""Record each v4 room material's source ModelPart key in its package record.

prepare_streamed_room_obj.py names every OBJ material segment after the source
BIN part's (texId, alphaTex) pair through the room MTL. The runtime needs that
pair to draw a batch while the recovered part's live material state is current,
without frozen material headers. This writes it into the unused tail of each
64-byte material identity and sets kFlagMaterialSourceKeys (room_package.hpp).
Geometry, colour, sources and every other section are unchanged; only the
material records, header flags and payload CRC differ.

With --bin-root PREFIX=DIR (owner prefixes, plus COMMON for the shared BINs),
every covered source is checked: the materials its batches use must be exactly
the keys of its original BIN parts. Inputs and outputs are
private generated assets; this file contains no game data.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, struct, sys, zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare_streamed_room_obj import parse_bin_roots, parse_materials, parse_model_parts

HEADER = struct.Struct("<8s24I6fI")
COMPACT = struct.Struct("<8I")
FLAG_SOURCE_GROUPS, FLAG_PRELIT, FLAG_MATERIAL_KEYS = 1, 2, 4
NO_ALPHA = 0xFF
KEY_OFFSET = 60


def owner_prefix(owner):
    return "MAINSCENARIO" if owner == 0xFF else f"FILE_{owner:02d}"


def key_package(data, bindings):
    data = bytearray(data)
    fields = list(HEADER.unpack_from(data, 0))
    version, header_size, flags = fields[1], fields[2], fields[23]
    material_count, material_offset = fields[10], fields[15]
    if fields[0] != b"RE4DCRM\0" or version != 4 or header_size != 160:
        raise ValueError("input is not a v4 room package")
    if flags & ~FLAG_MATERIAL_KEYS != FLAG_SOURCE_GROUPS | FLAG_PRELIT:
        raise ValueError(f"unexpected v4 header flags {flags:#x}")
    by_name = {name: key for key, name in bindings.items()}
    keys = []
    for index in range(material_count):
        offset = material_offset + 64 * index
        record = bytes(data[offset:offset + 64])
        name = record.split(b"\0", 1)[0].decode("ascii")
        if len(name) >= KEY_OFFSET:
            raise ValueError(f"material {name!r} leaves no room for its key")
        if name not in by_name:
            raise ValueError(f"material {name!r} has no MTL texture binding")
        texture, alpha = by_name[name]
        alpha = NO_ALPHA if alpha is None else alpha
        if not 0 <= texture < 256 or not 0 <= alpha < 256 or alpha == NO_ALPHA and by_name[name][1] is not None:
            raise ValueError(f"material {name!r} key {by_name[name]} does not fit one byte each")
        data[offset + KEY_OFFSET:offset + 64] = bytes((ord("K"), texture, alpha, 0))
        keys.append({"material": name, "texture": texture,
                     "alpha": None if alpha == NO_ALPHA else alpha})
    fields[23] = flags | FLAG_MATERIAL_KEYS
    fields[22] = zlib.crc32(bytes(data[header_size:])) & 0xFFFFFFFF
    HEADER.pack_into(data, 0, *fields)
    return bytes(data), keys


def source_materials(data):
    fields = HEADER.unpack_from(data, 0)
    group_count, batch_count = fields[11], fields[12]
    group_offset, batch_offset = fields[16], fields[17]
    _, _, source_offset, source_count, source_stride, _, _, _ = COMPACT.unpack_from(data, 128)
    used = [set() for _ in range(source_count)]
    groups = [struct.unpack_from("<IHH", data, group_offset + 32 * i) for i in range(group_count)]
    for first, count, source in groups:
        for batch in range(first, first + count):
            used[source].add(struct.unpack_from("<I", data, batch_offset + 52 * batch)[0])
    sources = []
    for index in range(source_count):
        owner, common, work, bin_number = struct.unpack_from("<BBHH", data, source_offset + source_stride * index + 76)
        sources.append({"source": index, "owner": owner, "common": bool(common), "work": work,
                        "bin": bin_number, "materials": sorted(used[index])})
    return sources


def verify(sources, keys, roots):
    report = []
    for source in sources:
        entry = {k: source[k] for k in ("source", "owner", "work", "bin", "common")}
        # Common-flag objects in any owner read their BIN from the room's shared SMD.
        prefix = "COMMON" if source["common"] else owner_prefix(source["owner"])
        if prefix not in roots:
            entry["status"] = f"unverified: no {prefix} BIN root"
            report.append(entry)
            continue
        parts = parse_model_parts(roots[prefix] / f"{source['bin']:04d}.BIN")
        expected = {(p.texture, p.alpha) for p in parts}
        actual = {(keys[m]["texture"], keys[m]["alpha"]) for m in source["materials"]}
        if actual != expected:
            raise ValueError(f"source {source['source']} ({prefix} work {source['work']} BIN {source['bin']}): "
                             f"package keys {sorted(actual, key=str)} != BIN parts {sorted(expected, key=str)}")
        entry["status"] = "verified"
        entry["parts"] = len(parts)
        report.append(entry)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=pathlib.Path)
    parser.add_argument("mtl", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--bin-root", action="append", default=[], metavar="PREFIX=PATH")
    parser.add_argument("--manifest", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.package.resolve():
        raise ValueError("refusing to overwrite the input package")
    source = args.package.read_bytes()
    keyed, keys = key_package(source, parse_materials(args.mtl))
    sources = source_materials(keyed)
    report = verify(sources, keys, parse_bin_roots(args.bin_root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(keyed)
    manifest = {
        "format": "re4dc-room-material-keys",
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "output_sha256": hashlib.sha256(keyed).hexdigest(),
        "mtl_sha256": hashlib.sha256(args.mtl.read_bytes()).hexdigest(),
        "bytes": len(keyed),
        "materials": keys,
        "sources": report,
        "changed_bytes": sum(a != b for a, b in zip(source, keyed)),
    }
    (args.manifest or args.output.with_suffix(args.output.suffix + ".keys.json")).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verified = sum(1 for entry in report if entry["status"] == "verified")
    print(json.dumps({"output": str(args.output), "materials": len(keys), "sources": len(report),
                      "verified_sources": verified, "changed_bytes": manifest["changed_bytes"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"material keying failed: {error}", file=sys.stderr)
        raise SystemExit(1)
