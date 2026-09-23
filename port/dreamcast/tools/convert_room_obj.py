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
import re
import struct
import sys
import zlib
from dataclasses import dataclass, field, replace


MAGIC = b"RE4DCRM\0"
VERSION = 3
# ...6f is the bounds; the trailing I is triangle_count, the room's total
# triangle count, which index_count no longer gives because the triangle
# table now holds only the batches that still need one.
HEADER = struct.Struct("<8s23I6fI")
VERTEX = struct.Struct("<8f")  # position, normal, UV
INDEX = struct.Struct("<I")
MATERIAL = struct.Struct("<64s")
GROUP = struct.Struct("<64sII6f")  # name, first batch, count, bounds
BATCH = struct.Struct("<IIIIIII")  # material/index range/group/flags/primitive range
PRIMITIVE = struct.Struct("<IHH")  # first vertex, vertex count, triangle count
SOURCE_GROUP = struct.Struct("<I4BII15f")
FLAG_SOURCE_GROUP_METADATA = 1 << 0
SOURCE_GROUP_HAS_LIGHT_VOLUME = 1 << 0
BATCH_STRIP_ORDER_PRESERVED = 1 << 0
# Set when this batch's triangle index range is present in the package.
# Clear means the strips are the batch's only representation, and they are
# authoritative because the order-preserved proof passed.
BATCH_TRIANGLES_RESIDENT = 1 << 1
SOURCE_GROUP_NAME = re.compile(r"#SMX_(\d+)#")
SOURCE_OBJECT_NAME = re.compile(
    r"^([^#]+)#SMD_(\d+)#SMX_(\d+)#.*#BIN_(\d+)#(CommonBIN#)?$"
)
SMX_WORK_SIZE = 0x90
SMD_WORK_SIZE = 0x48


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


@dataclass(frozen=True)
class SourceGroupData:
    select_mask: int
    source_id: int
    object_type: int
    ot_type: int
    cull_mode: int
    flags: int
    metadata_flags: int = 0
    light_center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    light_size: tuple[float, float, float] = (0.0, 0.0, 0.0)
    inverse_rotation: tuple[float, ...] = (
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
    )


def parse_smx(path: pathlib.Path) -> dict[int, SourceGroupData]:
    data = path.read_bytes()
    if len(data) < 0x10:
        raise ValueError("SMX is smaller than its header")
    count = data[1]
    expected = 0x10 + count * SMX_WORK_SIZE
    if expected > len(data):
        raise ValueError("SMX work table exceeds the file")
    records: dict[int, SourceGroupData] = {}
    for index in range(count):
        offset = 0x10 + index * SMX_WORK_SIZE
        source_id, object_type, ot_type, cull_mode = struct.unpack_from(
            "4B", data, offset
        )
        if cull_mode > 3:
            raise ValueError(
                f"SMX object {source_id} has invalid GX cull mode {cull_mode}"
            )
        if source_id in records:
            raise ValueError(f"SMX contains duplicate object id {source_id}")
        records[source_id] = SourceGroupData(
            select_mask=struct.unpack_from(">I", data, offset + 4)[0],
            source_id=source_id,
            object_type=object_type,
            ot_type=ot_type,
            cull_mode=cull_mode,
            flags=struct.unpack_from(">I", data, offset + 8)[0],
        )
    return records


def source_groups_for_names(
    group_names: list[str], smx_records: dict[int, SourceGroupData]
) -> dict[str, SourceGroupData]:
    result = {}
    for name in group_names:
        match = SOURCE_GROUP_NAME.search(name)
        if match is None:
            raise ValueError(f"group has no source SMX identity: {name!r}")
        source_id = int(match.group(1))
        # SmdInit leaves these defaults when id 0xFE has no SMX record or an
        # ordinary source id is absent from the sparse table.
        result[name] = smx_records.get(
            source_id,
            SourceGroupData(0xFFFFFFFF, source_id, 0, 3, 0, 0),
        )
    return result


def parse_smd_roots(values: list[str]) -> dict[str, pathlib.Path]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"SMD mapping must be PREFIX=PATH: {value!r}")
        prefix, raw_path = value.split("=", 1)
        path = pathlib.Path(raw_path)
        if not prefix or prefix in result or not path.is_file():
            raise ValueError(f"invalid SMD mapping {value!r}")
        result[prefix] = path
    return result


def smd_work(data: bytes, work_index: int) -> dict[str, object]:
    if len(data) < 0x10:
        raise ValueError("SMD is smaller than its header")
    model_count = struct.unpack_from(">H", data, 2)[0]
    if work_index >= model_count:
        raise ValueError(f"SMD work {work_index} exceeds {model_count} models")
    work_offset = 0x10
    if data[1] & 1:
        if len(data) < 0x14:
            raise ValueError("grouped SMD is smaller than its header")
        group_count = struct.unpack_from(">I", data, 0x10)[0]
        work_offset = 0x14 + group_count * 4
    offset = work_offset + work_index * SMD_WORK_SIZE
    if offset + SMD_WORK_SIZE > len(data):
        raise ValueError(f"SMD work {work_index} exceeds the file")
    values = struct.unpack_from(">9f4B", data, offset)
    return {
        "position": values[0:3],
        "rotation": values[3:6],
        "scale": values[6:9],
        "bin": values[9],
        "id": values[12],
        "flags": struct.unpack_from(">I", data, offset + 0x44)[0],
    }


def model_bounds(smd_data: bytes, bin_index: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    table_offset = struct.unpack_from(">I", smd_data, 4)[0]
    entry_offset = table_offset + bin_index * 4
    if entry_offset + 4 > len(smd_data):
        raise ValueError(f"SMD BIN table has no entry {bin_index}")
    model_offset = table_offset + struct.unpack_from(">I", smd_data, entry_offset)[0]
    if model_offset + 0x3C > len(smd_data):
        raise ValueError(f"SMD BIN {bin_index} header exceeds the file")
    vertex_offset = model_offset + struct.unpack_from(">I", smd_data, model_offset + 0x30)[0]
    vertex_count = struct.unpack_from(">H", smd_data, model_offset + 0x38)[0]
    shift = smd_data[model_offset + 0x28]
    if vertex_count == 0 or vertex_offset + vertex_count * 8 > len(smd_data):
        raise ValueError(f"SMD BIN {bin_index} vertex array exceeds the file")
    scale = float(1 << shift)
    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]
    for vertex in range(vertex_count):
        values = struct.unpack_from(">3h", smd_data, vertex_offset + vertex * 8)
        for axis, raw in enumerate(values):
            value = raw / scale
            minimum[axis] = min(minimum[axis], value)
            maximum[axis] = max(maximum[axis], value)
    center = tuple((minimum[axis] + maximum[axis]) * 0.5 for axis in range(3))
    size = tuple((maximum[axis] - minimum[axis]) * 0.5 for axis in range(3))
    return center, size


def rotation_matrix(rotation: tuple[float, ...]) -> tuple[float, ...]:
    sx, sy, sz = map(math.sin, rotation)
    cx, cy, cz = map(math.cos, rotation)
    return (
        cz * cy, cz * sx * sy - sz * cx, cz * cx * sy + sz * sx,
        sz * cy, sz * sx * sy + cz * cx, sz * cx * sy - cz * sx,
        -sy, cy * sx, cy * cx,
    )


def add_source_light_volumes(
    source_groups: dict[str, SourceGroupData], smd_roots: dict[str, pathlib.Path],
    common_smd: pathlib.Path | None, source_unit_scale: float,
) -> dict[str, SourceGroupData]:
    smd_cache = {prefix: path.read_bytes() for prefix, path in smd_roots.items()}
    common_data = common_smd.read_bytes() if common_smd is not None else None
    bounds_cache = {}
    result = {}
    for name, source in source_groups.items():
        match = SOURCE_OBJECT_NAME.match(name)
        if match is None:
            raise ValueError(f"group has no complete source object identity: {name!r}")
        prefix, raw_work, raw_id, raw_bin, common_marker = match.groups()
        if prefix not in smd_cache:
            raise ValueError(f"group prefix has no SMD mapping: {prefix!r}")
        placement_data = smd_cache[prefix]
        work = smd_work(placement_data, int(raw_work))
        if work["id"] != int(raw_id) or work["bin"] != int(raw_bin):
            raise ValueError(f"group identity disagrees with SMD work: {name!r}")
        model_data = common_data if common_marker else placement_data
        if model_data is None:
            raise ValueError(f"common BIN group requires --common-smd: {name!r}")
        bin_index = int(raw_bin)
        cache_key = (id(model_data), bin_index)
        if cache_key not in bounds_cache:
            bounds_cache[cache_key] = model_bounds(model_data, bin_index)
        local_center, local_size = bounds_cache[cache_key]
        matrix = rotation_matrix(work["rotation"])
        scaled_center = tuple(
            local_center[axis] * work["scale"][axis] for axis in range(3)
        )
        world_center = tuple(
            work["position"][row] + sum(
                matrix[row * 3 + column] * scaled_center[column]
                for column in range(3)
            )
            for row in range(3)
        )
        inverse = tuple(matrix[column * 3 + row] for row in range(3) for column in range(3))
        result[name] = replace(
            source,
            metadata_flags=source.metadata_flags | SOURCE_GROUP_HAS_LIGHT_VOLUME,
            light_center=tuple(value * source_unit_scale for value in world_center),
            light_size=tuple(
                abs(local_size[axis] * work["scale"][axis]) * source_unit_scale
                for axis in range(3)
            ),
            inverse_rotation=inverse,
        )
    return result


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


def parse_obj(path: pathlib.Path, *, retain_source_indices: bool = False) -> dict[str, object]:
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
        **({"vertex_source_indices": list(vertex_map)} if retain_source_indices else {}),
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


def spatial_partition(
    parsed: dict[str, object], cell_size: float,
    source_groups: dict[str, SourceGroupData] | None = None,
    unpartitioned_materials: set[str] | None = None,
) -> dict[str, SourceGroupData] | None:
    if cell_size <= 0.0:
        return source_groups
    vertices = parsed["vertices"]
    source_batches = parsed["batches"]
    preserve_sources = source_groups is not None
    unpartitioned_materials = unpartitioned_materials or set()
    source_order = {
        name: index for index, name in enumerate(parsed["group_order"])
    }
    cells: dict[tuple[object, ...], dict[str, BatchData]] = {}
    groups: dict[str, GroupData] = {}
    cell_sources: dict[str, SourceGroupData] = {}
    unpartitioned: dict[str, list[BatchData]] = {}

    for source_batch in source_batches:
        preserve_batch = (
            preserve_sources and
            source_batch.material in unpartitioned_materials
        )
        if preserve_batch:
            ordinal = source_order[source_batch.group]
            name = f"source_{ordinal:03d}_unpartitioned"
            if name not in groups:
                groups[name] = GroupData(name)
                cell_sources[name] = source_groups[source_batch.group]
                unpartitioned[source_batch.group] = []
            batch = BatchData(
                name, source_batch.material, list(source_batch.indices)
            )
            unpartitioned[source_batch.group].append(batch)
            for vertex_index in source_batch.indices:
                groups[name].include(vertices[vertex_index][:3])
            continue
        for start in range(0, len(source_batch.indices), 3):
            triangle = source_batch.indices[start : start + 3]
            positions = [vertices[index][:3] for index in triangle]
            center_x = sum(position[0] for position in positions) / 3.0
            center_z = sum(position[2] for position in positions) / 3.0
            cell_x = math.floor(center_x / cell_size)
            cell_z = math.floor(center_z / cell_size)
            key = ((source_batch.group, cell_x, cell_z) if preserve_sources
                   else (cell_x, cell_z))
            if preserve_sources:
                ordinal = source_order[source_batch.group]
                name = f"source_{ordinal:03d}_cell_{cell_x}_{cell_z}"
            else:
                name = f"cell_{cell_x}_{cell_z}"
            if key not in cells:
                cells[key] = {}
                groups[name] = GroupData(name)
                if source_groups is not None:
                    cell_sources[name] = source_groups[source_batch.group]
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
    def order_key(key: tuple[object, ...]) -> tuple[int, int, int]:
        if preserve_sources:
            return source_order[key[0]], key[1], key[2]
        return 0, key[0], key[1]

    ordered_keys = sorted(cells, key=order_key)
    if preserve_sources:
        ordered_keys_by_source = {
            name: [key for key in ordered_keys if key[0] == name]
            for name in parsed["group_order"]
        }
        source_sequence = parsed["group_order"]
    else:
        ordered_keys_by_source = {None: ordered_keys}
        source_sequence = [None]
    for source_name in source_sequence:
        for key in ordered_keys_by_source[source_name]:
            if preserve_sources:
                ordinal = source_order[key[0]]
                name = f"source_{ordinal:03d}_cell_{key[1]}_{key[2]}"
            else:
                name = f"cell_{key[0]}_{key[1]}"
            group = groups[name]
            group_order.append(name)
            for material in parsed["materials"]:
                if material in cells[key]:
                    group.batch_indices.append(len(batches))
                    batches.append(cells[key][material])
        if preserve_sources and source_name in unpartitioned:
            ordinal = source_order[source_name]
            name = f"source_{ordinal:03d}_unpartitioned"
            group = groups[name]
            group_order.append(name)
            for batch in unpartitioned[source_name]:
                group.batch_indices.append(len(batches))
                batches.append(batch)

    parsed["source_groups"] = len(parsed["group_order"])
    parsed["groups"] = groups
    parsed["group_order"] = group_order
    parsed["batches"] = batches
    parsed["cell_size"] = cell_size
    parsed["source_child_groups"] = len(group_order)
    return cell_sources if source_groups is not None else None


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


def stripify_triangles(indices: list[int]) -> list[list[int]]:
    """Build deterministic, winding-preserving strips from one material batch."""
    triangles = [
        tuple(indices[index:index + 3])
        for index in range(0, len(indices), 3)
    ]
    edge_map: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for triangle_index, (a, b, c) in enumerate(triangles):
        for first, second, third in ((a, b, c), (b, c, a), (c, a, b)):
            edge_map.setdefault((first, second), []).append(
                (triangle_index, third)
            )
    unused = set(range(len(triangles)))
    strips = []
    while unused:
        triangle_index = min(unused)
        unused.remove(triangle_index)
        a, b, c = triangles[triangle_index]

        def extend(start: tuple[int, int, int]) -> tuple[list[int], list[int]]:
            strip = list(start)
            consumed = []
            available = set(unused)
            while True:
                if len(strip) & 1:
                    edge = strip[-1], strip[-2]
                else:
                    edge = strip[-2], strip[-1]
                match = next(
                    ((candidate, vertex)
                     for candidate, vertex in edge_map.get(edge, ())
                     if candidate in available),
                    None,
                )
                if match is None:
                    break
                available.remove(match[0])
                consumed.append(match[0])
                strip.append(match[1])
            return strip, consumed

        strip, consumed = max(
            (extend(start) for start in ((a, b, c), (b, c, a), (c, a, b))),
            key=lambda result: len(result[0]),
        )
        unused.difference_update(consumed)
        strips.append(strip)
    return strips


def strip_triangle_order_preserved(
    indices: list[int], strips: list[list[int]]
) -> bool:
    """Return whether strips reproduce the source triangle order and winding."""
    def canonical(triangle: tuple[int, int, int]) -> tuple[int, int, int]:
        a, b, c = triangle
        return min((a, b, c), (b, c, a), (c, a, b))

    source = [
        canonical(tuple(indices[index:index + 3]))
        for index in range(0, len(indices), 3)
    ]
    rebuilt = []
    for strip in strips:
        for index in range(2, len(strip)):
            triangle = (
                (strip[index - 1], strip[index - 2], strip[index])
                if index & 1
                else (strip[index - 2], strip[index - 1], strip[index])
            )
            rebuilt.append(canonical(triangle))
    return rebuilt == source


def build_package(
    parsed: dict[str, object],
    source_groups: dict[str, SourceGroupData] | None = None,
    keep_triangle_indices: bool = False,
) -> tuple[bytes, dict[str, object]]:
    vertices = parsed["vertices"]
    materials = parsed["materials"]
    groups = parsed["groups"]
    group_order = parsed["group_order"]
    source_batches = parsed["batches"]
    material_ids = {name: index for index, name in enumerate(materials)}

    group_blob = bytearray()
    batch_blob = bytearray()
    index_blob = bytearray()
    primitive_blob = bytearray()
    primitive_index_blob = bytearray()
    source_group_blob = bytearray()
    ordered_batch_count = 0
    ordered_strip_batches = 0
    ordered_strip_triangles = 0
    resident_triangle_batches = 0
    dropped_index_bytes = 0
    total_triangles = 0
    all_min = [math.inf, math.inf, math.inf]
    all_max = [-math.inf, -math.inf, -math.inf]

    for group_index, group_name in enumerate(group_order):
        group = groups[group_name]
        first_batch = ordered_batch_count
        for source_batch_index in group.batch_indices:
            batch = source_batches[source_batch_index]
            strips = stripify_triangles(batch.indices)
            order_preserved = strip_triangle_order_preserved(
                batch.indices, strips
            )
            if order_preserved:
                ordered_strip_batches += 1
                ordered_strip_triangles += len(batch.indices) // 3
            # A batch keeps its triangle range only when the strips are not
            # proven to reproduce it, or when a comparison build asks for the
            # old layout. A batch with no strips at all always keeps it.
            triangles_resident = (
                keep_triangle_indices or not order_preserved or not strips
            )
            total_triangles += len(batch.indices) // 3
            first_index = len(index_blob) // INDEX.size
            if triangles_resident:
                resident_triangle_batches += 1
                for index in batch.indices:
                    index_blob.extend(INDEX.pack(index))
            else:
                first_index = 0
                dropped_index_bytes += len(batch.indices) * INDEX.size
            first_primitive = len(primitive_blob) // PRIMITIVE.size
            for strip in strips:
                first_vertex = len(primitive_index_blob) // INDEX.size
                for vertex in strip:
                    primitive_index_blob.extend(INDEX.pack(vertex))
                primitive_blob.extend(
                    PRIMITIVE.pack(first_vertex, len(strip), len(strip) - 2)
                )
            batch_blob.extend(
                BATCH.pack(
                    material_ids[batch.material],
                    first_index,
                    len(batch.indices) if triangles_resident else 0,
                    group_index,
                    (BATCH_STRIP_ORDER_PRESERVED if order_preserved else 0) |
                    (BATCH_TRIANGLES_RESIDENT if triangles_resident else 0),
                    first_primitive,
                    len(primitive_blob) // PRIMITIVE.size - first_primitive,
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
        if source_groups is not None:
            source = source_groups[group_name]
            source_group_blob.extend(
                SOURCE_GROUP.pack(
                    source.select_mask,
                    source.source_id,
                    source.object_type,
                    source.ot_type,
                    source.cull_mode,
                    source.flags,
                    source.metadata_flags,
                    *source.light_center,
                    *source.light_size,
                    *source.inverse_rotation,
                )
            )

    material_blob = b"".join(MATERIAL.pack(_name_bytes(name)) for name in materials)
    vertex_blob = b"".join(VERTEX.pack(*values) for values in vertices)
    material_offset = HEADER.size
    group_offset = material_offset + len(material_blob)
    batch_offset = group_offset + len(group_blob)
    vertex_offset = batch_offset + len(batch_blob)
    index_offset = vertex_offset + len(vertex_blob)
    source_group_offset = index_offset + len(index_blob)
    primitive_offset = source_group_offset + len(source_group_blob)
    primitive_index_offset = primitive_offset + len(primitive_blob)
    payload = bytes(
        material_blob + group_blob + batch_blob + vertex_blob + index_blob +
        source_group_blob + primitive_blob + primitive_index_blob
    )
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
        len(primitive_blob) // PRIMITIVE.size,
        len(primitive_index_blob) // INDEX.size,
        material_offset,
        group_offset,
        batch_offset,
        vertex_offset,
        index_offset,
        primitive_offset,
        primitive_index_offset,
        payload_crc32,
        FLAG_SOURCE_GROUP_METADATA if source_groups is not None else 0,
        *all_min,
        *all_max,
        total_triangles,
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
        "strips": len(primitive_blob) // PRIMITIVE.size,
        "strip_vertices": len(primitive_index_blob) // INDEX.size,
        "ordered_strip_batches": ordered_strip_batches,
        "ordered_strip_triangles": ordered_strip_triangles,
        "total_triangles": total_triangles,
        "resident_triangle_batches": resident_triangle_batches,
        "dropped_index_bytes": dropped_index_bytes,
        "bounds": {"min": all_min, "max": all_max},
        "payload_crc32": f"{payload_crc32:08x}",
    }
    if source_groups is not None:
        metadata["source_group_metadata"] = len(source_groups)
        metadata["source_cull_modes"] = {
            str(mode): sum(
                source.cull_mode == mode for source in source_groups.values()
            )
            for mode in sorted({source.cull_mode for source in source_groups.values()})
        }
    return header + payload, metadata


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



# v4 is a storage extension of the existing v3 topology/bake pipeline. It never
# reconstructs triangles, welds positions, or changes strip order. Historical
# OBJ -> v3 conversion stays byte-identical and remains the default until target
# layout/quality acceptance. Inputs to this step are qualified D353-style bakes.
COMPACT_VERSION = 4
FLAG_PRELIT = 1 << 1
COMPACT_EXTENSION = struct.Struct("<8I")
COMPACT_VERTEX = struct.Struct("<3fHHI")
COMPACT_ATTRIBUTE = struct.Struct("<HHI")
COMPACT_POSITION = struct.Struct("<4f")
COMPACT_GROUP = struct.Struct("<IHH6f")
COMPACT_BATCH = struct.Struct("<9I4f")
COMPACT_IDENTITY = struct.Struct("<BBHHH")  # owner, common, work, BIN, reserved
COMPACT_INDEX = struct.Struct("<H")
COMPACT_UV_ENCODING = 1  # per-batch float bias/scale + unsigned normalized 16-bit


def _f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def compact_prelit_package(
    data: bytes, source_names: list[str], layout: str = "aos20",
    max_uv_error: float = 0.5 / 1024.0,
) -> tuple[bytes, dict[str, object]]:
    """Repack certified v3 prelit geometry; source_names is original OBJ order.

    This CPU-only converter does not certify live source ownership or a bake's
    dynamic-light eligibility. The CLI additionally verifies the bake provenance.
    No debug name is used as a runtime resource key: owner/work/BIN is explicit.
    """
    if layout not in ("aos20", "split24"):
        raise ValueError("unknown compact vertex layout")
    if not math.isfinite(max_uv_error) or max_uv_error <= 0:
        raise ValueError("UV error bound must be finite and positive")
    if len(data) < HEADER.size:
        raise ValueError("truncated v3 header")
    h = list(HEADER.unpack_from(data))
    if (h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]) != (
        MAGIC, 3, 128, 32, 4, 64, 96, 28
    ) or h[23] != FLAG_SOURCE_GROUP_METADATA | FLAG_PRELIT:
        raise ValueError("compact conversion requires a source-mapped v3 prelit bake")
    if zlib.crc32(data[h[2]:]) & 0xFFFFFFFF != h[22]:
        raise ValueError("v3 CRC mismatch")
    source_offset = h[19] + h[9] * 4
    sections = [
        ("materials", h[15], h[10]*64), ("groups", h[16], h[11]*96),
        ("batches", h[17], h[12]*28), ("vertices", h[18], h[8]*32),
        ("triangle_indices", h[19], h[9]*4),
        ("source_groups", source_offset, h[11]*76),
        ("primitives", h[20], h[13]*8), ("strip_indices", h[21], h[14]*4),
    ]
    end = 128
    for name, start, size in sections:
        if start != end or start + size > len(data):
            raise ValueError("noncanonical/truncated v3 section: " + name)
        end = start + size
    if end != len(data):
        raise ValueError("unexpected trailing v3 bytes")
    vertices = [VERTEX.unpack_from(data, h[18]+i*32) for i in range(h[8])]
    if any(not all(math.isfinite(x) for x in v) or
           any(c < 0 or c > 1 for c in v[3:6]) for v in vertices):
        raise ValueError("nonfinite vertex or invalid prelit RGB")
    triangles = struct.unpack_from(f"<{h[9]}I", data, h[19])
    strip_indices = struct.unpack_from(f"<{h[14]}I", data, h[21])
    primitives = [PRIMITIVE.unpack_from(data, h[20]+i*8) for i in range(h[13])]
    if any(n < 3 or t != n-2 or f+n > len(strip_indices)
           for f,n,t in primitives):
        raise ValueError("invalid v3 primitive")
    if any(i >= len(vertices) for i in (*triangles, *strip_indices)):
        raise ValueError("v3 vertex index out of range")
    identity_records: list[bytes] = []
    identity_ids: dict[bytes, int] = {}
    identity_manifest = []
    identity_by_owner_work = {}
    previous_source_id = None
    group_blob = bytearray(); batch_blob = bytearray()
    vertex_blob = bytearray(); attribute_blob = bytearray()
    triangle_blob = bytearray(); primitive_blob = bytearray(); strip_blob = bytearray()
    groups = [GROUP.unpack_from(data,h[16]+i*96) for i in range(h[11])]
    batches = [BATCH.unpack_from(data,h[17]+i*28) for i in range(h[12])]
    used_batches = 0; used_primitives = 0; used_triangles = 0; used_strips = 0
    vertex_count = 0; total_triangles = 0; maximum_batch = 0; uv_error = 0.0
    for gi, group in enumerate(groups):
        raw_name, first_batch, batch_count, *bounds = group
        name = raw_name.split(b"\0")[0].decode("ascii")
        cell = re.fullmatch(r"source_(\d+)_(?:cell_-?\d+_-?\d+|unpartitioned)", name)
        if cell:
            ordinal = int(cell[1])
            if ordinal >= len(source_names):
                raise ValueError("source group ordinal exceeds identity map")
            source_name = source_names[ordinal]
        elif name in source_names:
            source_name = name
        else:
            raise ValueError("source identity not recoverable: " + name)
        match = SOURCE_OBJECT_NAME.fullmatch(source_name)
        if not match:
            raise ValueError("invalid original source identity: " + source_name)
        prefix, work, smx, bin_index, common = match.groups()
        owner = 255 if prefix == "MAINSCENARIO" else (
            int(prefix[5:]) if re.fullmatch(r"FILE_\d+", prefix) else -1)
        if not (0 <= owner <= 255 and 0 <= int(work) <= 65535 and
                0 <= int(bin_index) <= 65535 and 0 <= int(smx) <= 255):
            raise ValueError("source identity exceeds compact fields")
        if prefix != "MAINSCENARIO" and owner == 255:
            raise ValueError("block owner collides with main owner")
        src = data[source_offset+gi*76:source_offset+(gi+1)*76]
        if src[4] != int(smx):
            raise ValueError("source identity/SMX mismatch")
        record = src + COMPACT_IDENTITY.pack(owner,bool(common),int(work),int(bin_index),0)
        key = (owner, int(work))
        if key in identity_by_owner_work and identity_by_owner_work[key] != record:
            raise ValueError("conflicting source owner/work binding")
        identity_by_owner_work[key] = record
        if record not in identity_ids:
            identity_ids[record] = len(identity_records)
            identity_records.append(record)
            identity_manifest.append(dict(source=source_name,owner=owner,work=int(work),bin=int(bin_index),common=bool(common)))
        source_id = identity_ids[record]
        if previous_source_id is not None and source_id not in (
                previous_source_id, previous_source_id + 1):
            raise ValueError("interleaved source groups require explicit source ordering")
        previous_source_id = source_id
        if source_id > 65535 or batch_count > 65535 or first_batch != used_batches:
            raise ValueError("group count/identity exceeds compact range")
        if first_batch + batch_count > len(batches):
            raise ValueError("group batch range out of bounds")
        group_blob.extend(COMPACT_GROUP.pack(first_batch,batch_count,source_id,*bounds))
        for bi in range(first_batch,first_batch+batch_count):
            mat, fi, ni, bg, flags, fp, np = batches[bi]
            if bg != gi or mat >= h[10] or flags & ~3 or fp != used_primitives:
                raise ValueError("invalid source batch identity/flags/order")
            if fp+np > len(primitives) or fi+ni > len(triangles):
                raise ValueError("invalid source batch range")
            resident = bool(flags & BATCH_TRIANGLES_RESIDENT)
            if resident:
                if not ni or ni%3 or fi != used_triangles:
                    raise ValueError("invalid resident triangle range")
            elif ni or fi or not np or not flags & BATCH_STRIP_ORDER_PRESERVED:
                raise ValueError("strip-only batch lacks source order proof")
            ids = {}; ordered = []
            def local(index):
                if index not in ids:
                    ids[index] = len(ordered); ordered.append(index)
                return ids[index]
            # Keep packet visitation order for contiguous transforms. No hot-loop map.
            for f,n,t in primitives[fp:fp+np]:
                if f != used_strips:
                    raise ValueError("noncanonical primitive index range")
                primitive_blob.extend(PRIMITIVE.pack(len(strip_blob)//2,n,t))
                for index in strip_indices[f:f+n]:
                    value = local(index)
                    if value > 65535: raise ValueError("batch needs legal-boundary splitting before uint16 conversion")
                    strip_blob.extend(COMPACT_INDEX.pack(value))
                used_strips += n
            new_fi = len(triangle_blob)//2 if resident else 0
            for index in triangles[fi:fi+ni]:
                value = local(index)
                if value > 65535: raise ValueError("batch needs legal-boundary splitting before uint16 conversion")
                triangle_blob.extend(COMPACT_INDEX.pack(value))
            if not ordered: raise ValueError("empty native batch")
            bias = [_f32(min(vertices[i][axis] for i in ordered)) for axis in (6,7)]
            scale = [_f32((max(vertices[i][axis] for i in ordered)-bias[a])/65535.0)
                     for a,axis in enumerate((6,7))]
            for index in ordered:
                v = vertices[index]; q = []
                for a in range(2):
                    value = round((v[6+a]-bias[a])/scale[a]) if scale[a] else 0
                    value = max(0,min(65535,value)); q.append(value)
                    decoded = _f32(bias[a]+_f32(value*scale[a]))
                    uv_error = max(uv_error,abs(decoded-v[6+a]))
                # Same truncation and float multiplication as D349 shade_color.
                c = [int(_f32(x*255.0)) for x in v[3:6]]
                color = 0xff000000 | c[0]<<16 | c[1]<<8 | c[2]
                if layout == "aos20":
                    vertex_blob.extend(COMPACT_VERTEX.pack(*v[:3],*q,color))
                else:
                    vertex_blob.extend(COMPACT_POSITION.pack(*v[:3],1.0))
                    attribute_blob.extend(COMPACT_ATTRIBUTE.pack(*q,color))
            batch_blob.extend(COMPACT_BATCH.pack(mat,new_fi,ni,gi,flags,fp,np,
                vertex_count,len(ordered),*bias,*scale))
            vertex_count += len(ordered); maximum_batch = max(maximum_batch,len(ordered))
            total_triangles += ni//3 if resident else sum(t for f,n,t in primitives[fp:fp+np])
            used_batches += 1; used_primitives += np; used_triangles += ni
    if (used_batches,used_primitives,used_triangles,used_strips,total_triangles) != (h[12],h[13],h[9],h[14],h[30]):
        raise ValueError("unowned records or triangle total mismatch")
    if uv_error > max_uv_error:
        raise ValueError(f"compact UV error {uv_error:g} exceeds {max_uv_error:g}")
    result = bytearray(HEADER.size+COMPACT_EXTENSION.size)
    offsets = {}; sizes = {}; padding = 0
    blobs = [('materials',data[h[15]:h[15]+h[10]*64]),('groups',group_blob),
        ('batches',batch_blob),('vertices',vertex_blob),('attributes',attribute_blob),
        ('triangle_indices',triangle_blob),('source_groups',b''.join(identity_records)),
        ('primitives',primitive_blob),('strip_indices',strip_blob)]
    for name, blob in blobs:
        pad = (-len(result))%32; padding += pad; result.extend(bytes(pad))
        offsets[name] = len(result); sizes[name] = len(blob); result.extend(blob)
    h[1:8] = [4,160,20 if layout=='aos20' else 16,2,64,32,52]
    h[8] = vertex_count
    h[15:22] = [offsets[n] for n in ('materials','groups','batches','vertices','triangle_indices','primitives','strip_indices')]
    h[22] = zlib.crc32(result[160:]) & 0xffffffff
    result[:128] = HEADER.pack(*h)
    result[128:160] = COMPACT_EXTENSION.pack(1 if layout=='aos20' else 2,
        offsets['attributes'],offsets['source_groups'],len(identity_records),84,
        COMPACT_UV_ENCODING,1,0)
    before = {name:size for name,offset,size in sections};before['header']=128
    after = dict(sizes,header=160,padding=padding)
    assert sum(before.values()) == len(data) and sum(after.values()) == len(result)
    return bytes(result),dict(format='re4dc-room',version=4,layout=layout,
        source_sha256=sha256_bytes(data),package_sha256=sha256_bytes(result),
        package_bytes=len(result),sections_before=before,sections_after=after,
        source_vertices=len(vertices),vertices=vertex_count,
        duplicated_local_vertices=vertex_count-len(vertices),max_batch_vertices=maximum_batch,
        batches=h[12],groups=h[11],source_identities=identity_manifest,
        uv_encoding='per-batch affine unorm16',max_uv_error=uv_error,
        max_uv_error_texels_at_1024=uv_error*1024,position_encoding='unchanged float32 XYZ',
        color_encoding='D349 shade_color float32 truncation to opaque ARGB8888',
        runtime_static_normal_transforms=0,runtime_static_light_evaluations=0,
        runtime_source_corner_remaps=0,
        limits='Encoded package candidate, not runtime source-heap recovery or visual/gameplay acceptance')


def compact_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Version the existing qualified prelit room package')
    parser.add_argument('input',type=pathlib.Path)
    parser.add_argument('output',type=pathlib.Path)
    parser.add_argument('--compact-prelit',action='store_true',required=True)
    parser.add_argument('--layout',choices=('aos20','split24'),default='aos20')
    parser.add_argument('--source-obj',type=pathlib.Path,required=True)
    parser.add_argument('--reference-manifest',type=pathlib.Path,required=True)
    parser.add_argument('--bake-manifest',type=pathlib.Path,required=True)
    args = parser.parse_args(argv)
    data = args.input.read_bytes(); reference=json.loads(args.reference_manifest.read_text())
    bake=json.loads(args.bake_manifest.read_text())
    if (bake.get('candidate_sha256') != sha256_bytes(data) or
        bake.get('reference_sha256') != reference.get('package_sha256') or
        bake.get('camera_relative_selected') is not False or
        bake.get('max_shared_color_difference',1) > 1.0/255.0 or
        reference.get('source_sha256') != sha256_bytes(args.source_obj.read_bytes())):
        raise ValueError('bake/reference/OBJ identity or lighting qualification mismatch')
    names = parse_obj(args.source_obj)['group_order']
    package,manifest=compact_prelit_package(data,names,args.layout)
    manifest['reference_sha256']=reference['package_sha256']
    manifest['bake_manifest_sha256']=sha256_bytes(args.bake_manifest.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(package)
    args.output.with_suffix(args.output.suffix+'.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='source_identities'},sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--compact-prelit" in argv:
        return compact_main(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path, help="private exported room OBJ")
    parser.add_argument("output", type=pathlib.Path, help="private Dreamcast room package")
    parser.add_argument("--manifest", type=pathlib.Path, help="JSON manifest path")
    parser.add_argument(
        "--keep-triangle-indices",
        action="store_true",
        help="store every batch's triangle range as well as its strips, which "
             "provides the retained-index comparison layout",
    )
    parser.add_argument(
        "--smx", type=pathlib.Path,
        help="source room SMX whose per-object masks and cull modes are appended",
    )
    parser.add_argument(
        "--smd", action="append", default=[], metavar="PREFIX=PATH",
        help="source placed-model SMD mapping used to recover light volumes",
    )
    parser.add_argument(
        "--common-smd", type=pathlib.Path,
        help="source common SMD used by CommonBIN groups",
    )
    parser.add_argument(
        "--source-unit-scale", type=float, default=0.001,
        help="multiply SMD/BIN source units into runtime units",
    )
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
        "--unpartitioned-material", action="append", default=[],
        help="material kept in source-group order while other batches use cells",
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
    if not math.isfinite(args.source_unit_scale) or args.source_unit_scale <= 0.0:
        raise ValueError("source unit scale must be finite and positive")
    if args.smd and args.smx is None:
        raise ValueError("--smd requires --smx")
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
    source_groups = None
    if args.smx is not None:
        source_groups = source_groups_for_names(
            parsed["group_order"], parse_smx(args.smx)
        )
        if args.smd:
            source_groups = add_source_light_volumes(
                source_groups, parse_smd_roots(args.smd), args.common_smd,
                args.source_unit_scale,
            )
    source_groups = spatial_partition(
        parsed, args.cell_size, source_groups,
        set(args.unpartitioned_material),
    )
    cluster_geometry(parsed, args.cluster_size)
    package, metadata = build_package(
        parsed, source_groups, args.keep_triangle_indices
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(package)
    metadata.update(
        {
            "source": args.input.name,
            "source_sha256": sha256_bytes(args.input.read_bytes()),
            "source_smx": args.smx.name if args.smx is not None else None,
            "source_smx_sha256": (
                sha256_bytes(args.smx.read_bytes()) if args.smx is not None else None
            ),
            "source_light_volumes": (
                sum(
                    bool(source.metadata_flags & SOURCE_GROUP_HAS_LIGHT_VOLUME)
                    for source in source_groups.values()
                ) if source_groups is not None else 0
            ),
            "source_positions": parsed["positions"],
            "source_normals": parsed["normals"],
            "source_texcoords": parsed["texcoords"],
            "source_faces": parsed["source_faces"],
            "source_scale": args.source_scale,
            "source_groups": parsed.get("source_groups", len(parsed["group_order"])),
            "source_child_groups": parsed.get(
                "source_child_groups", len(parsed["group_order"])
            ),
            "cell_size": parsed.get("cell_size", 0.0),
            "unpartitioned_materials": sorted(args.unpartitioned_material),
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
