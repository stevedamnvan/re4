#!/usr/bin/env python3
"""Convert an RE4 GameCube SAT collision file into a Dreamcast package.

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
from dataclasses import dataclass


MAGIC = b"RE4DCSAT"
VERSION = 1
SOURCE_SCALE = 0.01
HEADER = struct.Struct("<8s15I6f")
VECTOR = struct.Struct("<3f")
POLYGON = struct.Struct("<4HI")
HIERARCHY_MAGIC = b"RE4DCHY\0"
HIERARCHY_VERSION = 1
HIERARCHY_HEADER = struct.Struct("<8s14I")
POLYGON_EDGES = struct.Struct("<3H2x")
BLOCK = struct.Struct("<6f4H4I")
BLOCK_INDEX = struct.Struct("<H")
SAT_HEADER = struct.Struct(">BB9H")
SAT_VECTOR = struct.Struct(">3f")
SAT_POLYGON = struct.Struct(">7H2xI")
SAT_BLOCK = struct.Struct(">6f4HI")


@dataclass
class SourceBlock:
    minimum: tuple[float, float, float]
    size: tuple[float, float, float]
    floor_count: int
    slope_count: int
    wall_count: int
    flags: int
    child: int = -1
    next: int = -1
    polygon_indices: tuple[int, ...] = ()


def _parse_blocks(
    data: bytes, offset: int, block_count: int, polygon_count: int,
    source_scale: float,
) -> list[SourceBlock]:
    if block_count == 0:
        return []
    blocks: list[SourceBlock] = []
    offset_to_index: dict[int, int] = {}
    visiting: set[int] = set()

    def parse_block(block_offset: int) -> int:
        if block_offset in offset_to_index:
            return offset_to_index[block_offset]
        if block_offset in visiting:
            raise ValueError("SAT block graph contains a cycle")
        if block_offset < offset or block_offset + SAT_BLOCK.size > len(data):
            raise ValueError("SAT block header exceeds the file")
        visiting.add(block_offset)
        values = SAT_BLOCK.unpack_from(data, block_offset)
        floor_count, slope_count, wall_count, flags, next_relative = values[6:]
        reference_count = floor_count + slope_count + wall_count
        index = len(blocks)
        offset_to_index[block_offset] = index
        blocks.append(SourceBlock(
            minimum=tuple(value * source_scale for value in values[0:3]),
            size=tuple(value * source_scale for value in values[3:6]),
            floor_count=floor_count,
            slope_count=slope_count,
            wall_count=wall_count,
            flags=flags,
        ))
        if flags & 1:
            if reference_count != 0:
                raise ValueError("SAT parent block also contains polygon indices")
            blocks[index].child = parse_block(block_offset + SAT_BLOCK.size)
        else:
            indices_offset = block_offset + SAT_BLOCK.size
            _checked_span(indices_offset, reference_count, 2, len(data), "block polygon")
            indices = struct.unpack_from(f">{reference_count}H", data, indices_offset) \
                if reference_count else ()
            if any(polygon >= polygon_count for polygon in indices):
                raise ValueError("SAT block contains an invalid polygon index")
            blocks[index].polygon_indices = indices
        if next_relative:
            next_offset = block_offset + next_relative
            if next_offset <= block_offset:
                raise ValueError("SAT block next offset does not advance")
            blocks[index].next = parse_block(next_offset)
        visiting.remove(block_offset)
        return index

    parse_block(offset)
    if len(blocks) != block_count:
        raise ValueError(
            f"SAT block graph contains {len(blocks)} blocks, expected {block_count}"
        )
    return blocks


def _checked_span(offset: int, count: int, stride: int, size: int, label: str) -> None:
    end = offset + count * stride
    if offset < 0 or count < 0 or end > size:
        raise ValueError(f"{label} table exceeds SAT file")


def _sat_offsets(data: bytes) -> list[int]:
    if len(data) < SAT_HEADER.size:
        raise ValueError("SAT source is smaller than a collision header")
    if (data[0] & 0x80) == 0:
        return [0]
    count = data[1]
    if count == 0:
        raise ValueError("SAT container has no collision sections")
    table_end = 4 + count * 4
    if table_end > len(data):
        raise ValueError("SAT container offset table exceeds file")
    offsets = list(struct.unpack_from(f">{count}I", data, 4))
    if any(offset < table_end or offset + SAT_HEADER.size > len(data) for offset in offsets):
        raise ValueError("SAT container contains an invalid section offset")
    return offsets


def parse_sat(path: pathlib.Path, sat_index: int = 0, source_scale: float = SOURCE_SCALE) -> dict[str, object]:
    data = path.read_bytes()
    offsets = _sat_offsets(data)
    if sat_index < 0 or sat_index >= len(offsets):
        raise ValueError(
            f"SAT section {sat_index} is out of range for {len(offsets)} sections"
        )
    base = offsets[sat_index]
    (
        source_version,
        _reserved,
        vertex_count,
        normal_count,
        edge_count,
        _unknown_count,
        polygon_count,
        floor_count,
        slope_count,
        wall_count,
        block_count,
    ) = SAT_HEADER.unpack_from(data, base)
    if floor_count + slope_count + wall_count != polygon_count:
        raise ValueError("SAT floor, slope, and wall counts do not match polygons")

    vertex_offset = base + SAT_HEADER.size
    normal_offset = vertex_offset + vertex_count * SAT_VECTOR.size
    edge_offset = normal_offset + normal_count * SAT_VECTOR.size
    polygon_offset = edge_offset + edge_count * SAT_VECTOR.size
    _checked_span(vertex_offset, vertex_count, SAT_VECTOR.size, len(data), "vertex")
    _checked_span(normal_offset, normal_count, SAT_VECTOR.size, len(data), "normal")
    _checked_span(edge_offset, edge_count, SAT_VECTOR.size, len(data), "edge")
    _checked_span(polygon_offset, polygon_count, SAT_POLYGON.size, len(data), "polygon")

    vertices = [
        tuple(value * source_scale for value in SAT_VECTOR.unpack_from(data, vertex_offset + i * SAT_VECTOR.size))
        for i in range(vertex_count)
    ]
    normals = [
        SAT_VECTOR.unpack_from(data, normal_offset + i * SAT_VECTOR.size)
        for i in range(normal_count)
    ]
    polygons: list[tuple[int, int, int, int, int]] = []
    polygon_edges: list[tuple[int, int, int]] = []
    for index in range(polygon_count):
        record = SAT_POLYGON.unpack_from(data, polygon_offset + index * SAT_POLYGON.size)
        v0, v1, v2, normal, e0, e1, e2, attribute = record
        if max(v0, v1, v2) >= vertex_count:
            raise ValueError(f"SAT polygon {index} has an invalid vertex index")
        if normal >= normal_count:
            raise ValueError(f"SAT polygon {index} has an invalid normal index")
        if max(e0, e1, e2) >= edge_count:
            raise ValueError(f"SAT polygon {index} has an invalid edge index")
        polygons.append((v0, v1, v2, normal, attribute))
        polygon_edges.append((e0, e1, e2))

    block_offset = polygon_offset + polygon_count * SAT_POLYGON.size
    blocks = _parse_blocks(
        data, block_offset, block_count, polygon_count, source_scale
    )

    if not vertices or not polygons:
        raise ValueError("SAT section has no usable collision geometry")
    if not all(math.isfinite(value) for vector in vertices + normals for value in vector):
        raise ValueError("SAT section contains non-finite vectors")
    bounds_min = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
    bounds_max = [max(vertex[axis] for vertex in vertices) for axis in range(3)]
    return {
        "source_version": source_version,
        "source_scale": source_scale,
        "sat_index": sat_index,
        "sat_sections": len(offsets),
        "block_count": block_count,
        "vertices": vertices,
        "normals": normals,
        "edges": [
            SAT_VECTOR.unpack_from(data, edge_offset + i * SAT_VECTOR.size)
            for i in range(edge_count)
        ],
        "polygons": polygons,
        "polygon_edges": polygon_edges,
        "blocks": blocks,
        "floor_count": floor_count,
        "slope_count": slope_count,
        "wall_count": wall_count,
        "bounds_min": bounds_min,
        "bounds_max": bounds_max,
    }


def build_package(parsed: dict[str, object]) -> tuple[bytes, dict[str, object]]:
    vertices = parsed["vertices"]
    normals = parsed["normals"]
    polygons = parsed["polygons"]
    vertex_blob = b"".join(VECTOR.pack(*vector) for vector in vertices)
    normal_blob = b"".join(VECTOR.pack(*vector) for vector in normals)
    polygon_blob = b"".join(POLYGON.pack(*polygon) for polygon in polygons)
    hierarchy_blob = b""
    vertex_offset = HEADER.size
    normal_offset = vertex_offset + len(vertex_blob)
    polygon_offset = normal_offset + len(normal_blob)
    base_payload = vertex_blob + normal_blob + polygon_blob
    blocks = parsed["blocks"]
    if blocks:
        edge_blob = b"".join(VECTOR.pack(*edge) for edge in parsed["edges"])
        polygon_edge_blob = b"".join(
            POLYGON_EDGES.pack(*edges) for edges in parsed["polygon_edges"]
        )
        block_blob = bytearray()
        reference_blob = bytearray()
        hierarchy_offset = HEADER.size + len(base_payload)
        edge_offset = hierarchy_offset + HIERARCHY_HEADER.size
        polygon_edge_offset = edge_offset + len(edge_blob)
        block_offset = polygon_edge_offset + len(polygon_edge_blob)
        reference_offset = block_offset + len(blocks) * BLOCK.size
        for block in blocks:
            first_reference = len(reference_blob) // BLOCK_INDEX.size
            for polygon in block.polygon_indices:
                reference_blob.extend(BLOCK_INDEX.pack(polygon))
            block_blob.extend(BLOCK.pack(
                *block.minimum, *block.size,
                block.floor_count, block.slope_count, block.wall_count,
                block.flags,
                block.child if block.child >= 0 else 0xFFFFFFFF,
                block.next if block.next >= 0 else 0xFFFFFFFF,
                first_reference, len(block.polygon_indices),
            ))
        hierarchy_header = HIERARCHY_HEADER.pack(
            HIERARCHY_MAGIC, HIERARCHY_VERSION, HIERARCHY_HEADER.size,
            VECTOR.size, POLYGON_EDGES.size, BLOCK.size, BLOCK_INDEX.size,
            len(parsed["edges"]), len(parsed["polygon_edges"]), len(blocks),
            len(reference_blob) // BLOCK_INDEX.size,
            edge_offset, polygon_edge_offset, block_offset, reference_offset,
        )
        hierarchy_blob = bytes(
            hierarchy_header + edge_blob + polygon_edge_blob + block_blob +
            reference_blob
        )
    payload = base_payload + hierarchy_blob
    package = HEADER.pack(
        MAGIC,
        VERSION,
        HEADER.size,
        VECTOR.size,
        VECTOR.size,
        POLYGON.size,
        len(vertices),
        len(normals),
        len(polygons),
        parsed["floor_count"],
        parsed["slope_count"],
        parsed["wall_count"],
        vertex_offset,
        normal_offset,
        polygon_offset,
        zlib.crc32(payload) & 0xFFFFFFFF,
        *parsed["bounds_min"],
        *parsed["bounds_max"],
    ) + payload
    manifest = {
        "format": "RE4DCSAT",
        "version": VERSION,
        "source_version": parsed["source_version"],
        "sat_index": parsed["sat_index"],
        "sat_sections": parsed["sat_sections"],
        "source_scale": parsed["source_scale"],
        "vertices": len(vertices),
        "normals": len(normals),
        "polygons": len(polygons),
        "floors": parsed["floor_count"],
        "slopes": parsed["slope_count"],
        "walls": parsed["wall_count"],
        "source_blocks": parsed["block_count"],
        "source_edges": len(parsed["edges"]),
        "source_block_polygon_references": sum(
            len(block.polygon_indices) for block in blocks
        ),
        "hierarchy_bytes": len(hierarchy_blob),
        "bounds": {"min": parsed["bounds_min"], "max": parsed["bounds_max"]},
        "bytes": len(package),
        "sha256": hashlib.sha256(package).hexdigest(),
    }
    return package, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--sat-index", type=int, default=0)
    parser.add_argument("--source-scale", type=float, default=SOURCE_SCALE)
    args = parser.parse_args(argv)
    if not math.isfinite(args.source_scale) or args.source_scale <= 0.0:
        raise ValueError("source scale must be finite and positive")
    parsed = parse_sat(args.source, args.sat_index, args.source_scale)
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
        print(f"convert_sat: {error}", file=sys.stderr)
        raise SystemExit(1) from error
