#!/usr/bin/env python3
"""Convert an RE4 GameCube RTP route graph into a Dreamcast package.

The input and output are private, generated assets. This converter contains no
game data and is safe to track in Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import struct
import sys
import zlib


MAGIC = b"RE4DRTP\0"
VERSION = 1
SOURCE_MAGIC = b"2RTP"
SOURCE_SCALE = 0.001
SOURCE_HEADER = struct.Struct(">4sHH4sIII")
SOURCE_POINT = struct.Struct(">3fHH")
SOURCE_LINK = struct.Struct(">hH")
HEADER = struct.Struct("<8s11I6f")
POINT = struct.Struct("<3fHH")
LINK = struct.Struct("<hH")


def _checked_span(offset: int, count: int, stride: int, size: int, label: str) -> None:
    end = offset + count * stride
    if offset < SOURCE_HEADER.size or count < 0 or end > size:
        raise ValueError(f"{label} table exceeds RTP file")


def parse_rtp(path: pathlib.Path, source_scale: float = SOURCE_SCALE) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < SOURCE_HEADER.size:
        raise ValueError("RTP source is smaller than its header")
    magic, _reserved, point_count, _flags, point_offset, link_offset, next_offset = (
        SOURCE_HEADER.unpack_from(data)
    )
    if magic != SOURCE_MAGIC:
        raise ValueError("RTP source magic is not 2RTP")
    if point_count == 0:
        raise ValueError("RTP source has no route points")
    if point_count > 127:
        raise ValueError("RTP source exceeds the signed next-hop index range")
    if not (point_offset <= link_offset <= next_offset):
        raise ValueError("RTP table offsets are not ordered")
    _checked_span(point_offset, point_count, SOURCE_POINT.size, len(data), "point")
    if (next_offset - link_offset) % SOURCE_LINK.size:
        raise ValueError("RTP link table size is not aligned")
    link_count = (next_offset - link_offset) // SOURCE_LINK.size
    _checked_span(link_offset, link_count, SOURCE_LINK.size, len(data), "link")
    next_count = point_count * point_count
    _checked_span(next_offset, next_count, 1, len(data), "next-hop")

    points: list[tuple[float, float, float, int, int]] = []
    for index in range(point_count):
        x, y, z, first_link, point_links = SOURCE_POINT.unpack_from(
            data, point_offset + index * SOURCE_POINT.size
        )
        if first_link + point_links > link_count:
            raise ValueError(f"RTP point {index} has an invalid link range")
        point = (x * source_scale, y * source_scale, z * source_scale)
        if not all(math.isfinite(value) for value in point):
            raise ValueError(f"RTP point {index} is not finite")
        points.append((*point, first_link, point_links))

    links: list[tuple[int, int]] = []
    for index in range(link_count):
        target, flags = SOURCE_LINK.unpack_from(
            data, link_offset + index * SOURCE_LINK.size
        )
        if target < 0 or target >= point_count:
            raise ValueError(f"RTP link {index} has an invalid target")
        links.append((target, flags))

    next_hops = data[next_offset : next_offset + next_count]
    for index, value in enumerate(next_hops):
        signed = value if value < 128 else value - 256
        if signed < -1 or signed >= point_count:
            raise ValueError(f"RTP next-hop {index} has an invalid point")

    bounds_min = [min(point[axis] for point in points) for axis in range(3)]
    bounds_max = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "source_scale": source_scale,
        "points": points,
        "links": links,
        "next_hops": next_hops,
        "bounds_min": bounds_min,
        "bounds_max": bounds_max,
    }


def build_package(parsed: dict[str, object]) -> tuple[bytes, dict[str, object]]:
    points = parsed["points"]
    links = parsed["links"]
    next_hops = parsed["next_hops"]
    point_blob = b"".join(POINT.pack(*point) for point in points)
    link_blob = b"".join(LINK.pack(*link) for link in links)
    point_offset = HEADER.size
    link_offset = point_offset + len(point_blob)
    next_offset = link_offset + len(link_blob)
    payload = point_blob + link_blob + next_hops
    package = HEADER.pack(
        MAGIC,
        VERSION,
        HEADER.size,
        POINT.size,
        LINK.size,
        len(points),
        len(links),
        len(next_hops),
        point_offset,
        link_offset,
        next_offset,
        zlib.crc32(payload) & 0xFFFFFFFF,
        *parsed["bounds_min"],
        *parsed["bounds_max"],
    ) + payload
    manifest = {
        "format": "RE4DRTP",
        "version": VERSION,
        "source_scale": parsed["source_scale"],
        "points": len(points),
        "links": len(links),
        "next_hops": len(next_hops),
        "bounds": {"min": parsed["bounds_min"], "max": parsed["bounds_max"]},
        "bytes": len(package),
        "sha256": hashlib.sha256(package).hexdigest(),
    }
    return package, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--source-scale", type=float, default=SOURCE_SCALE)
    args = parser.parse_args(argv)
    if not math.isfinite(args.source_scale) or args.source_scale <= 0.0:
        raise ValueError("source scale must be finite and positive")
    parsed = parse_rtp(args.source, args.source_scale)
    package, manifest = build_package(parsed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(package)
    manifest["source_sha256"] = hashlib.sha256(args.source.read_bytes()).hexdigest()
    manifest_path = args.output.with_suffix(args.output.suffix + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, struct.error) as error:
        print(f"convert_rtp: {error}", file=sys.stderr)
        raise SystemExit(1) from error
