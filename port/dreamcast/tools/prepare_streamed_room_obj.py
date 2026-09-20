#!/usr/bin/env python3
"""Prepare a source-authored streamed RE4 room OBJ for Dreamcast conversion.

The r100 exporter preserves streamed SMD geometry but labels local model parts
as UNKNOWN_MATERIAL because the game appends the room's shared TPL at runtime.
The original BIN part headers still contain the exact diffuse/alpha texture
indices. This tool restores those bindings and selects a local source slice.
Inputs and outputs are private generated assets; this file contains no game data.
"""
from __future__ import annotations
import argparse, hashlib, json, math, pathlib, re, struct, sys
from dataclasses import dataclass

IMAGE_NUMBER = re.compile(r"-(\d+)\.png$", re.I)
GROUP_BIN = re.compile(r"^([^#]+)#.*#BIN_(\d+)#")

@dataclass(frozen=True)
class ModelPart:
    texture: int
    alpha: int | None
    triangles: int

@dataclass
class Bounds:
    minimum: list[float]
    maximum: list[float]
    @classmethod
    def empty(cls):
        return cls([math.inf] * 3, [-math.inf] * 3)
    def include(self, point):
        for axis, value in enumerate(point):
            self.minimum[axis] = min(self.minimum[axis], value)
            self.maximum[axis] = max(self.maximum[axis], value)
    def horizontal_distance(self, x, z):
        dx = 0.0 if self.minimum[0] <= x <= self.maximum[0] else min(
            abs(x - self.minimum[0]), abs(x - self.maximum[0]))
        dz = 0.0 if self.minimum[2] <= z <= self.maximum[2] else min(
            abs(z - self.minimum[2]), abs(z - self.maximum[2]))
        return math.hypot(dx, dz)

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def parse_bin_roots(values):
    roots = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"BIN root must be PREFIX=PATH: {value!r}")
        prefix, raw_path = value.split("=", 1)
        path = pathlib.Path(raw_path)
        if not prefix or prefix in roots or not path.is_dir():
            raise ValueError(f"invalid BIN root {value!r}")
        roots[prefix] = path
    return roots

def parse_materials(path):
    records, current = {}, None
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        fields = raw.strip().split()
        if not fields or fields[0].startswith("#"):
            continue
        if fields[0] == "newmtl":
            current = " ".join(fields[1:])
            records[current] = [None, None]
        elif fields[0] in {"map_Kd", "map_d"}:
            if current is None:
                raise ValueError(f"MTL line {line_no}: map precedes material")
            match = IMAGE_NUMBER.search(fields[-1].replace("\\", "/"))
            if match is None:
                raise ValueError(f"MTL line {line_no}: no TPL image number")
            records[current][0 if fields[0] == "map_Kd" else 1] = int(match.group(1))
    result = {}
    for name, pair in records.items():
        if pair[0] is not None:
            key = tuple(pair)
            if key in result:
                raise ValueError(f"duplicate material binding {key}")
            result[key] = name
    if not result:
        raise ValueError("MTL has no usable texture bindings")
    return result

def parse_model_parts(path):
    data = path.read_bytes()
    if len(data) < 0x48:
        raise ValueError(f"model BIN is too small: {path}")
    count = struct.unpack_from(">H", data, 0x1A)[0]
    offset = struct.unpack_from(">I", data, 0x1C)[0]
    parts = []
    for index in range(count):
        if offset + 0x20 > len(data):
            raise ValueError(f"part {index} header is outside {path}")
        flags = data[offset + 0x0B]
        texture = data[offset + 0x0C]
        alpha = data[offset + 0x0E] if flags & 0x04 else None
        size, triangles = struct.unpack_from(">II", data, offset + 0x18)
        if offset + 0x20 + size > len(data):
            raise ValueError(f"part {index} stream is outside {path}")
        parts.append(ModelPart(texture, alpha, triangles))
        offset += 0x20 + size
    return parts

def group_model_parts(group, roots, cache):
    if "#CommonBIN#" in group:
        return None
    match = GROUP_BIN.match(group)
    if match is None or match.group(1) not in roots:
        return None
    path = roots[match.group(1)] / f"{int(match.group(2)):04d}.BIN"
    if path not in cache:
        if not path.is_file():
            raise ValueError(f"missing model BIN for {group!r}: {path}")
        cache[path] = parse_model_parts(path)
    return cache[path]

def inspect_groups(path):
    positions, bounds, triangles = [], {}, {}
    group = "default"
    with path.open("r", encoding="utf-8-sig") as source:
        for line_no, raw in enumerate(source, 1):
            fields = raw.strip().split()
            if not fields or fields[0].startswith("#"):
                continue
            if fields[0] == "v":
                positions.append(tuple(map(float, fields[1:4])))
            elif fields[0] in {"g", "o"}:
                group = " ".join(fields[1:]) or "default"
            elif fields[0] == "f":
                record = bounds.setdefault(group, Bounds.empty())
                triangles[group] = triangles.get(group, 0) + len(fields) - 3
                for token in fields[1:]:
                    raw_index = int(token.split("/", 1)[0])
                    index = raw_index - 1 if raw_index > 0 else len(positions) + raw_index
                    if index < 0 or index >= len(positions):
                        raise ValueError(f"OBJ line {line_no}: position index out of range")
                    record.include(positions[index])
    return bounds, triangles

def prepare(args):
    roots = parse_bin_roots(args.bin_root)
    bindings = parse_materials(args.mtl)
    bounds, group_triangles = inspect_groups(args.input)
    prefixes = set(args.include_prefix)
    selected = set()
    for group, record in bounds.items():
        prefix = group.split("#", 1)[0]
        if prefixes and prefix not in prefixes:
            continue
        if args.radius is not None and record.horizontal_distance(args.center_x, args.center_z) > args.radius:
            continue
        selected.add(group)
    if not selected:
        raise ValueError("group selection produced no renderable geometry")

    cache, output_lines = {}, []
    repaired = output_triangles = 0
    group, keep, parts = "default", False, None
    part_index = part_faces = 0
    def finish_part():
        nonlocal part_faces
        if keep and parts is not None and part_index > 0:
            expected = parts[part_index - 1].triangles
            if part_faces != expected:
                raise ValueError(f"{group!r} part {part_index - 1}: OBJ {part_faces}, BIN {expected} triangles")
        part_faces = 0
    def finish_group():
        finish_part()
        if keep and parts is not None and part_index != len(parts):
            raise ValueError(f"{group!r}: OBJ {part_index}, BIN {len(parts)} parts")

    with args.input.open("r", encoding="utf-8-sig") as source:
        for raw in source:
            fields = raw.strip().split()
            command = fields[0] if fields else ""
            if command in {"g", "o"}:
                finish_group()
                group = " ".join(fields[1:]) or "default"
                keep = group in selected
                parts = group_model_parts(group, roots, cache) if keep else None
                part_index = part_faces = 0
                if keep:
                    output_lines.append(raw)
            elif command == "usemtl":
                if not keep:
                    continue
                finish_part()
                material = " ".join(fields[1:]) or "default"
                if parts is not None:
                    if part_index >= len(parts):
                        raise ValueError(f"too many material segments in {group!r}")
                    if material == "UNKNOWN_MATERIAL":
                        part = parts[part_index]
                        key = (part.texture, part.alpha)
                        if key not in bindings:
                            raise ValueError(f"no MTL binding for texture pair {key}")
                        material = bindings[key]
                        repaired += 1
                    part_index += 1
                output_lines.append(f"usemtl {material}\n")
            elif command == "f":
                if keep:
                    count = len(fields) - 3
                    part_faces += count
                    output_triangles += count
                    output_lines.append(raw)
            elif command in {"v", "vt", "vn", "mtllib", "s", ""}:
                output_lines.append(raw)
            elif keep:
                output_lines.append(raw)
    finish_group()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(output_lines), encoding="utf-8")
    return {
        "format": "re4dc-prepared-streamed-obj",
        "source": args.input.name, "source_sha256": sha256_file(args.input),
        "output": args.output.name, "output_sha256": sha256_file(args.output),
        "selected_groups": len(selected), "selected_triangles": output_triangles,
        "repaired_material_parts": repaired,
        "include_prefixes": sorted(prefixes),
        "selection_center": [args.center_x, args.center_z] if args.radius is not None else None,
        "selection_radius": args.radius,
        "groups": sorted(selected),
        "group_triangles": {name: group_triangles[name] for name in sorted(selected)},
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("mtl", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--bin-root", action="append", default=[], metavar="PREFIX=PATH")
    parser.add_argument("--include-prefix", action="append", default=[])
    parser.add_argument("--center-x", type=float, default=0.0)
    parser.add_argument("--center-z", type=float, default=0.0)
    parser.add_argument("--radius", type=float)
    parser.add_argument("--manifest", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.radius is not None and args.radius <= 0:
        raise ValueError("radius must be positive")
    metadata = prepare(args)
    manifest = args.manifest or args.output.with_suffix(args.output.suffix + ".json")
    manifest.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in metadata.items() if k not in {"groups", "group_triangles"}}, sort_keys=True))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"streamed room preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
