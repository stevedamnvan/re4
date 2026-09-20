#!/usr/bin/env python3
"""Convert an offline-exported RE4 room OBJ into a compact Dreamcast package.

The input and output are expected to be private, generated assets. This tool
contains no game data and is safe to track in Git.
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
from dataclasses import dataclass, field


MAGIC = b"RE4DCRM\0"
VERSION = 1
HEADER = struct.Struct("<8s19I6f")
VERTEX = struct.Struct("<8f")  # position, normal, UV
INDEX = struct.Struct("<I")
MATERIAL = struct.Struct("<64s")
GROUP = struct.Struct("<64sII6f")  # name, first batch, count, bounds
BATCH = struct.Struct("<IIIII")  # material, first index, count, group, flags


@dataclass
class BatchData:
    group: str
    material: str
    indices: list[int] = field(default_factory=list)


@dataclass
class GroupData:
    name: str
    batch_indices: list[int] = field(default_factory=list)
    bounds_min: list[float] = field(
        default_factory=lambda: [math.inf, math.inf, math.inf]
    )
    bounds_max: list[float] = field(
        default_factory=lambda: [-math.inf, -math.inf, -math.inf]
    )

    def include(self, xyz: tuple[float, float, float]) -> None:
        for axis, value in enumerate(xyz):
            self.bounds_min[axis] = min(self.bounds_min[axis], value)
            self.bounds_max[axis] = max(self.bounds_max[axis], value)


def _name_bytes(name: str) -> bytes:
    encoded = name.encode("utf-8")
    if len(encoded) >= 64:
        raise ValueError(f"name is too long for room package: {name!r}")
    return encoded.ljust(64, b"\0")


def _obj_index(value: str, count: int, kind: str, line_no: int) -> int:
    if not value:
        return -1
    raw = int(value)
    result = raw - 1 if raw > 0 else count + raw
    if result < 0 or result >= count:
        raise ValueError(f"line {line_no}: {kind} index {raw} is out of range")
    return result


def parse_obj(path: pathlib.Path) -> dict[str, object]:
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    texcoords: list[tuple[float, float]] = []
    vertices: list[tuple[float, ...]] = []
    vertex_map: dict[tuple[int, int, int], int] = {}
    materials: list[str] = []
    material_set: set[str] = set()
    groups: dict[str, GroupData] = {}
    group_order: list[str] = []
    batches: list[BatchData] = []
    current_group = "default"
    current_material = "default"
    current_batch = -1
    source_faces = 0
    triangles = 0

    def ensure_group(name: str) -> GroupData:
        if name not in groups:
            groups[name] = GroupData(name)
            group_order.append(name)
        return groups[name]

    def ensure_material(name: str) -> None:
        if name not in material_set:
            material_set.add(name)
            materials.append(name)

    def get_batch() -> BatchData:
        nonlocal current_batch
        if (
            current_batch < 0
            or batches[current_batch].group != current_group
            or batches[current_batch].material != current_material
        ):
            current_batch = len(batches)
            batches.append(BatchData(current_group, current_material))
            ensure_group(current_group).batch_indices.append(current_batch)
            ensure_material(current_material)
        return batches[current_batch]

    def get_vertex(token: str, line_no: int) -> int:
        fields = token.split("/")
        if len(fields) > 3 or not fields[0]:
            raise ValueError(f"line {line_no}: invalid face corner {token!r}")
        vi = _obj_index(fields[0], len(positions), "position", line_no)
        ti = (
            _obj_index(fields[1], len(texcoords), "texcoord", line_no)
            if len(fields) > 1
            else -1
        )
        ni = (
            _obj_index(fields[2], len(normals), "normal", line_no)
            if len(fields) > 2
            else -1
        )
        key = (vi, ti, ni)
        if key not in vertex_map:
            xyz = positions[vi]
            normal = normals[ni] if ni >= 0 else (0.0, 0.0, 0.0)
            uv = texcoords[ti] if ti >= 0 else (0.0, 0.0)
            values = xyz + normal + uv
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"line {line_no}: non-finite vertex data")
            vertex_map[key] = len(vertices)
            vertices.append(values)
        ensure_group(current_group).include(positions[vi])
        return vertex_map[key]

    with path.open("r", encoding="utf-8-sig") as source:
        for line_no, raw_line in enumerate(source, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            command = fields[0]
            if command == "v":
                if len(fields) < 4:
                    raise ValueError(f"line {line_no}: position needs three values")
                positions.append(tuple(map(float, fields[1:4])))
            elif command == "vn":
                if len(fields) < 4:
                    raise ValueError(f"line {line_no}: normal needs three values")
                normals.append(tuple(map(float, fields[1:4])))
            elif command == "vt":
                if len(fields) < 3:
                    raise ValueError(f"line {line_no}: texcoord needs two values")
                texcoords.append(tuple(map(float, fields[1:3])))
            elif command in {"g", "o"}:
                current_group = " ".join(fields[1:]) or "default"
                current_batch = -1
            elif command == "usemtl":
                current_material = " ".join(fields[1:]) or "default"
                current_batch = -1
            elif command == "f":
                if len(fields) < 4:
                    raise ValueError(f"line {line_no}: face needs at least three corners")
                corners = [get_vertex(token, line_no) for token in fields[1:]]
                batch = get_batch()
                for corner in range(1, len(corners) - 1):
                    batch.indices.extend(
                        (corners[0], corners[corner], corners[corner + 1])
                    )
                    triangles += 1
                source_faces += 1

    if not vertices or not batches:
        raise ValueError("OBJ has no renderable faces")

    return {
        "positions": len(positions),
        "normals": len(normals),
        "texcoords": len(texcoords),
        "source_faces": source_faces,
        "triangles": triangles,
        "vertices": vertices,
        "materials": materials,
        "groups": groups,
        "group_order": group_order,
        "batches": batches,
    }


def spatial_partition(parsed: dict[str, object], cell_size: float) -> None:
    if cell_size <= 0.0:
        return
    vertices = parsed["vertices"]
    source_batches = parsed["batches"]
    cells: dict[tuple[int, int], dict[str, BatchData]] = {}
    groups: dict[str, GroupData] = {}

    for source_batch in source_batches:
        for start in range(0, len(source_batch.indices), 3):
            triangle = source_batch.indices[start : start + 3]
            positions = [vertices[index][:3] for index in triangle]
            center_x = sum(position[0] for position in positions) / 3.0
            center_z = sum(position[2] for position in positions) / 3.0
            key = (math.floor(center_x / cell_size), math.floor(center_z / cell_size))
            name = f"cell_{key[0]}_{key[1]}"
            if key not in cells:
                cells[key] = {}
                groups[name] = GroupData(name)
            if source_batch.material not in cells[key]:
                cells[key][source_batch.material] = BatchData(
                    name, source_batch.material
                )
            batch = cells[key][source_batch.material]
            batch.indices.extend(triangle)
            for position in positions:
                groups[name].include(position)

    batches: list[BatchData] = []
    group_order: list[str] = []
    for key in sorted(cells):
        name = f"cell_{key[0]}_{key[1]}"
        group = groups[name]
        group_order.append(name)
        for material in parsed["materials"]:
            if material in cells[key]:
                group.batch_indices.append(len(batches))
                batches.append(cells[key][material])

    parsed["source_groups"] = len(parsed["group_order"])
    parsed["groups"] = groups
    parsed["group_order"] = group_order
    parsed["batches"] = batches
    parsed["cell_size"] = cell_size


def cluster_geometry(parsed: dict[str, object], cluster_size: float) -> None:
    """Build an explicit coarse LOD while retaining groups and materials.

    Clusters are scoped to one batch so unrelated objects and materials cannot
    weld together. Position and normal buckets select the cluster; position,
    normal, and UV values are averaged. Degenerate and duplicate triangles are
    removed after remapping.
    """
    if cluster_size <= 0.0:
        return
    source_vertices = parsed["vertices"]
    source_triangles = sum(len(batch.indices) for batch in parsed["batches"]) // 3
    vertices: list[tuple[float, ...]] = []
    for batch in parsed["batches"]:
        clusters: dict[tuple[int, ...], list[float]] = {}
        triangle_keys: list[tuple[tuple[int, ...], ...]] = []
        for start in range(0, len(batch.indices), 3):
            keys = []
            for index in batch.indices[start : start + 3]:
                vertex = source_vertices[index]
                key = (
                    round(vertex[0] / cluster_size),
                    round(vertex[1] / cluster_size),
                    round(vertex[2] / cluster_size),
                    round(vertex[3] * 4.0),
                    round(vertex[4] * 4.0),
                    round(vertex[5] * 4.0),
                )
                if key not in clusters:
                    clusters[key] = [0.0] * 8 + [0.0]
                aggregate = clusters[key]
                for component, value in enumerate(vertex):
                    aggregate[component] += value
                aggregate[8] += 1.0
                keys.append(key)
            triangle_keys.append(tuple(keys))

        cluster_indices: dict[tuple[int, ...], int] = {}
        for key, aggregate in clusters.items():
            count = aggregate[8]
            values = [value / count for value in aggregate[:8]]
            length = math.sqrt(sum(value * value for value in values[3:6]))
            if length > 0.000001:
                values[3:6] = [value / length for value in values[3:6]]
            cluster_indices[key] = len(vertices)
            vertices.append(tuple(values))

        indices: list[int] = []
        seen: set[tuple[int, int, int]] = set()
        for keys in triangle_keys:
            triangle = tuple(cluster_indices[key] for key in keys)
            if len(set(triangle)) < 3 or triangle in seen:
                continue
            seen.add(triangle)
            indices.extend(triangle)
        batch.indices = indices

    triangles = sum(len(batch.indices) for batch in parsed["batches"]) // 3
    if triangles == 0:
        raise ValueError("vertex clustering removed every triangle")
    parsed["vertices"] = vertices
    parsed["triangles"] = triangles
    parsed["cluster_size"] = cluster_size
    parsed["cluster_source_vertices"] = len(source_vertices)
    parsed["cluster_source_triangles"] = source_triangles


def build_package(parsed: dict[str, object]) -> tuple[bytes, dict[str, object]]:
    vertices = parsed["vertices"]
    materials = parsed["materials"]
    groups = parsed["groups"]
    group_order = parsed["group_order"]
    source_batches = parsed["batches"]
    material_ids = {name: index for index, name in enumerate(materials)}

    group_blob = bytearray()
    batch_blob = bytearray()
    index_blob = bytearray()
    ordered_batch_count = 0
    all_min = [math.inf, math.inf, math.inf]
    all_max = [-math.inf, -math.inf, -math.inf]

    for group_index, group_name in enumerate(group_order):
        group = groups[group_name]
        first_batch = ordered_batch_count
        for source_batch_index in group.batch_indices:
            batch = source_batches[source_batch_index]
            first_index = len(index_blob) // INDEX.size
            for index in batch.indices:
                index_blob.extend(INDEX.pack(index))
            batch_blob.extend(
                BATCH.pack(
                    material_ids[batch.material],
                    first_index,
                    len(batch.indices),
                    group_index,
                    0,
                )
            )
            ordered_batch_count += 1
        group_blob.extend(
            GROUP.pack(
                _name_bytes(group_name),
                first_batch,
                ordered_batch_count - first_batch,
                *group.bounds_min,
                *group.bounds_max,
            )
        )
        for axis in range(3):
            all_min[axis] = min(all_min[axis], group.bounds_min[axis])
            all_max[axis] = max(all_max[axis], group.bounds_max[axis])

    material_blob = b"".join(MATERIAL.pack(_name_bytes(name)) for name in materials)
    vertex_blob = b"".join(VERTEX.pack(*values) for values in vertices)
    material_offset = HEADER.size
    group_offset = material_offset + len(material_blob)
    batch_offset = group_offset + len(group_blob)
    vertex_offset = batch_offset + len(batch_blob)
    index_offset = vertex_offset + len(vertex_blob)
    payload = bytes(material_blob + group_blob + batch_blob + vertex_blob + index_blob)
    payload_crc32 = zlib.crc32(payload) & 0xFFFFFFFF
    index_count = len(index_blob) // INDEX.size
    header = HEADER.pack(
        MAGIC,
        VERSION,
        HEADER.size,
        VERTEX.size,
        INDEX.size,
        MATERIAL.size,
        GROUP.size,
        BATCH.size,
        len(vertices),
        index_count,
        len(materials),
        len(group_order),
        ordered_batch_count,
        material_offset,
        group_offset,
        batch_offset,
        vertex_offset,
        index_offset,
        payload_crc32,
        0,
        *all_min,
        *all_max,
    )
    metadata = {
        "format": "re4dc-room",
        "version": VERSION,
        "vertices": len(vertices),
        "indices": index_count,
        "triangles": index_count // 3,
        "materials": len(materials),
        "groups": len(group_order),
        "batches": ordered_batch_count,
        "bounds": {"min": all_min, "max": all_max},
        "payload_crc32": f"{payload_crc32:08x}",
    }
    return header + payload, metadata


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path, help="private exported room OBJ")
    parser.add_argument("output", type=pathlib.Path, help="private Dreamcast room package")
    parser.add_argument("--manifest", type=pathlib.Path, help="JSON manifest path")
    parser.add_argument(
        "--source-scale", type=float, default=1.0,
        help="multiply exported OBJ positions by this source-to-runtime scale",
    )
    parser.add_argument(
        "--cell-size",
        type=float,
        default=0.0,
        help="partition static triangles into X/Z cells of this size",
    )
    parser.add_argument(
        "--cluster-size",
        type=float,
        default=0.0,
        help="build a coarse per-batch vertex-cluster LOD at this size",
    )
    args = parser.parse_args(argv)

    if not math.isfinite(args.source_scale) or args.source_scale <= 0.0:
        raise ValueError("source scale must be finite and positive")
    parsed = parse_obj(args.input)
    if args.source_scale != 1.0:
        parsed["vertices"] = [
            (vertex[0] * args.source_scale,
             vertex[1] * args.source_scale,
             vertex[2] * args.source_scale,
             *vertex[3:])
            for vertex in parsed["vertices"]
        ]
        for group in parsed["groups"].values():
            group.bounds_min = [value * args.source_scale for value in group.bounds_min]
            group.bounds_max = [value * args.source_scale for value in group.bounds_max]
    spatial_partition(parsed, args.cell_size)
    cluster_geometry(parsed, args.cluster_size)
    package, metadata = build_package(parsed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(package)
    metadata.update(
        {
            "source": args.input.name,
            "source_sha256": sha256_bytes(args.input.read_bytes()),
            "source_positions": parsed["positions"],
            "source_normals": parsed["normals"],
            "source_texcoords": parsed["texcoords"],
            "source_faces": parsed["source_faces"],
            "source_scale": args.source_scale,
            "source_groups": parsed.get("source_groups", len(parsed["group_order"])),
            "cell_size": parsed.get("cell_size", 0.0),
            "cluster_size": parsed.get("cluster_size", 0.0),
            "cluster_source_vertices": parsed.get(
                "cluster_source_vertices", len(parsed["vertices"])
            ),
            "cluster_source_triangles": parsed.get(
                "cluster_source_triangles", parsed["triangles"]
            ),
            "package": args.output.name,
            "package_bytes": len(package),
            "package_sha256": sha256_bytes(package),
        }
    )
    manifest_path = args.manifest or args.output.with_suffix(args.output.suffix + ".json")
    manifest_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"room conversion failed: {error}", file=sys.stderr)
        raise SystemExit(1)
