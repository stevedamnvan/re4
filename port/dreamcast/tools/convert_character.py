#!/usr/bin/env python3
"""Convert an RE4 GameCube character model and motions into a compact Dreamcast package.

Only the user-supplied disc-derived output is private.  The converter contains no game data.
It decodes the model's GX primitive streams, evaluates selected FCV motions with the existing
source-derived motion host, skins the vertices offline, and stores quantised animation frames.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from motion import archive, evalhost, fcv, modelbin  # noqa: E402


MAGIC = b"R4CH"
VERSION = 1
HEADER = struct.Struct("<4s11If")
BATCH = struct.Struct("<4I")
CLIP = struct.Struct("<16sIIff")


def align(value, alignment=4):
    return (value + alignment - 1) & ~(alignment - 1)


def be_u16(data, offset):
    return struct.unpack_from(">H", data, offset)[0]


def be_s16(data, offset):
    return struct.unpack_from(">h", data, offset)[0]


def be_u32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def triangulate(opcode, vertices):
    if opcode == 0x80:
        if len(vertices) % 4:
            raise ValueError("quad stream vertex count is not divisible by four")
        for index in range(0, len(vertices), 4):
            a, b, c, d = vertices[index:index + 4]
            yield a, b, c
            yield a, c, d
    elif opcode == 0x90:
        if len(vertices) % 3:
            raise ValueError("triangle stream vertex count is not divisible by three")
        for index in range(0, len(vertices), 3):
            yield tuple(vertices[index:index + 3])
    elif opcode == 0x98:
        for index in range(2, len(vertices)):
            if index & 1:
                yield vertices[index - 1], vertices[index - 2], vertices[index]
            else:
                yield vertices[index - 2], vertices[index - 1], vertices[index]
    else:
        raise ValueError(f"unsupported GX primitive opcode {opcode:#x}")


def parse_geometry(data):
    """Return source positions, palette indices, triangle indices and material batches."""
    flags = be_u32(data, 0x20)
    shift = data[0x28]
    vertex_offset = be_u32(data, 0x30)
    vertex_count = be_u16(data, 0x38)
    part_offset = be_u32(data, 0x1C)
    part_count = be_u16(data, 0x1A)
    weight_offset = be_u32(data, 0x14)
    weight_count = data[0x18]
    weight_ext_count = be_u16(data, 0x2A)
    if weight_ext_count > 0xFF:
        raise ValueError("extended model weights are not supported by the lean converter")
    if weight_count == 0:
        raise ValueError("model has no skinning palette")

    scale = 1.0 / float(1 << shift)
    positions = []
    palette_indices = []
    for index in range(vertex_count):
        offset = vertex_offset + index * 8
        x, y, z, palette = struct.unpack_from(">4h", data, offset)
        positions.append((x * scale, y * scale, z * scale))
        palette_indices.append(palette)

    weights = []
    for index in range(weight_count):
        offset = weight_offset + index * 8
        ids = tuple(data[offset:offset + 3])
        count = data[offset + 3]
        values = tuple(data[offset + 4:offset + 8])
        if not 1 <= count <= 3:
            raise ValueError(f"weight {index} has invalid influence count {count}")
        weights.append((ids[:count], values[:count]))
    if min(palette_indices) < 0 or max(palette_indices) >= len(weights):
        raise ValueError("vertex references a skinning palette entry outside the table")

    record_size = 8 if flags & 0x80000000 else 6
    indices = []
    batches = []
    cursor = part_offset
    for part_index in range(part_count):
        if cursor + 0x20 > len(data):
            raise ValueError("model part header exceeds entry")
        material = data[cursor + 0x0C]
        stream_size = be_u32(data, cursor + 0x18)
        stream = cursor + 0x20
        stream_end = stream + stream_size
        if stream_end > len(data):
            raise ValueError("model part stream exceeds entry")
        first_index = len(indices)
        while stream < stream_end:
            opcode = data[stream]
            stream += 1
            if opcode == 0:
                continue
            if opcode not in (0x80, 0x90, 0x98):
                raise ValueError(
                    f"part {part_index} has unsupported GX opcode {opcode:#x}"
                )
            count = be_u16(data, stream)
            stream += 2
            byte_count = count * record_size
            if stream + byte_count > stream_end:
                raise ValueError("GX primitive records exceed their model part")
            primitive = [be_u16(data, stream + i * record_size) for i in range(count)]
            if primitive and max(primitive) >= vertex_count:
                raise ValueError("GX primitive references a vertex outside the source array")
            for triangle in triangulate(opcode, primitive):
                indices.extend(triangle)
            stream += byte_count
        count = len(indices) - first_index
        if count:
            batches.append((first_index, count, material, part_index))
        cursor = stream_end
    return positions, palette_indices, weights, indices, batches


def affine_multiply(a, b):
    out = [0.0] * 12
    for row in range(3):
        for column in range(3):
            out[row * 4 + column] = sum(
                a[row * 4 + k] * b[k * 4 + column] for k in range(3)
            )
        out[row * 4 + 3] = a[row * 4 + 3] + sum(
            a[row * 4 + k] * b[k * 4 + 3] for k in range(3)
        )
    return out


def affine_inverse(matrix):
    a, b, c = matrix[0], matrix[1], matrix[2]
    d, e, f = matrix[4], matrix[5], matrix[6]
    g, h, i = matrix[8], matrix[9], matrix[10]
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(determinant) < 1.0e-12:
        raise ValueError("singular root matrix")
    inverse = [
        (e * i - f * h) / determinant,
        (c * h - b * i) / determinant,
        (b * f - c * e) / determinant,
        0.0,
        (f * g - d * i) / determinant,
        (a * i - c * g) / determinant,
        (c * d - a * f) / determinant,
        0.0,
        (d * h - e * g) / determinant,
        (b * g - a * h) / determinant,
        (a * e - b * d) / determinant,
        0.0,
    ]
    tx, ty, tz = matrix[3], matrix[7], matrix[11]
    inverse[3] = -(inverse[0] * tx + inverse[1] * ty + inverse[2] * tz)
    inverse[7] = -(inverse[4] * tx + inverse[5] * ty + inverse[6] * tz)
    inverse[11] = -(inverse[8] * tx + inverse[9] * ty + inverse[10] * tz)
    return inverse


def transform_point(matrix, point):
    x, y, z = point
    return (
        matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3],
        matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7],
        matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11],
    )


def rest_world_positions(model):
    result = []
    for part in model.parts:
        if part.parent < 0:
            result.append(tuple(part.pos))
        else:
            parent = result[part.parent]
            result.append(tuple(parent[axis] + part.pos[axis] for axis in range(3)))
    return result


def skin_frame(pose, rest_world, source_positions, palette_indices, weights):
    bone_matrices = []
    for index, matrix in enumerate(pose.mat):
        # The GameCube skinning pass first makes these root-relative, then the
        # draw pass applies the animated root matrix again.  Bake the combined
        # result so the Dreamcast runtime only applies the player's world pose.
        relative = list(matrix)
        rest = rest_world[index]
        relative[3] -= relative[0] * rest[0] + relative[1] * rest[1] + relative[2] * rest[2]
        relative[7] -= relative[4] * rest[0] + relative[5] * rest[1] + relative[6] * rest[2]
        relative[11] -= relative[8] * rest[0] + relative[9] * rest[1] + relative[10] * rest[2]
        bone_matrices.append(relative)

    palette = []
    for ids, percentages in weights:
        blended = [0.0] * 12
        used = 0.0
        for influence, bone in enumerate(ids):
            rate = percentages[influence] * 0.01
            if influence == len(ids) - 1:
                rate = 1.0 - used
            used += rate
            for element, value in enumerate(bone_matrices[bone]):
                blended[element] += value * rate
        palette.append(blended)
    return [transform_point(palette[palette_indices[index]], position)
            for index, position in enumerate(source_positions)]


def load_archive(source, name, cache_dir):
    source = Path(source).resolve()
    if not archive.is_disc(str(source)):
        result = archive.Archive(str(source))
        if result.name != name:
            raise ValueError(f"archive is {result.name}, expected {name}")
        return result
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / name
    if not destination.exists():
        if not Path(archive.DTK).is_file():
            raise FileNotFoundError(f"{archive.DTK} is missing; configure the repository first")
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        subprocess.run(
            [archive.DTK, "vfs", "cp", f"{source}:/files/em/{name}", str(temporary)],
            check=True,
        )
        temporary.replace(destination)
    return archive.Archive(str(destination))


def parse_clip(specification):
    fields = specification.split(":")
    if len(fields) != 3:
        raise argparse.ArgumentTypeError("clip must be NAME:ARCHIVE:ENTRY")
    name, archive_name, entry = fields
    if not name or len(name.encode("ascii", "strict")) > 15:
        raise argparse.ArgumentTypeError("clip name must be 1-15 ASCII bytes")
    return name, archive_name, int(entry, 0)


def quantise_frames(frames, quantum_mm):
    output = bytearray()
    maximum_error = 0.0
    bounds_min = [math.inf, math.inf, math.inf]
    bounds_max = [-math.inf, -math.inf, -math.inf]
    for frame in frames:
        for point in frame:
            values = []
            for axis, value in enumerate(point):
                quantised = int(round(value / quantum_mm))
                if not -32768 <= quantised <= 32767:
                    raise ValueError(
                        f"animated vertex exceeds int16 range at {value:g} mm; increase --quantum-mm"
                    )
                values.append(quantised)
                maximum_error = max(maximum_error, abs(value - quantised * quantum_mm))
                bounds_min[axis] = min(bounds_min[axis], value)
                bounds_max[axis] = max(bounds_max[axis], value)
            output += struct.pack("<3h", *values)
    return output, maximum_error, bounds_min, bounds_max


def convert(args):
    output = Path(args.output)
    cache_dir = Path(args.cache_dir) if args.cache_dir else output.parent / "disc-cache"
    model_archive = load_archive(args.source, args.model_archive, cache_dir)
    model_entry = model_archive.entry(args.model_entry)
    if model_entry.tag != "BIN":
        raise ValueError("selected model entry is not BIN")
    model = modelbin.parse(model_entry.data)
    model.check_tree()
    positions, palette_indices, weights, indices, batches = parse_geometry(model_entry.data)
    rest_world = rest_world_positions(model)

    frames = []
    clips = []
    source_manifest = []
    archives = {args.model_archive: model_archive}
    for name, archive_name, entry_index in args.clip:
        if archive_name not in archives:
            archives[archive_name] = load_archive(args.source, archive_name, cache_dir)
        entry = archives[archive_name].entry(entry_index)
        if entry.tag != "FCV":
            raise ValueError(f"{archive_name}:{entry_index} is not FCV")
        motion = fcv.parse(entry.data)
        player = evalhost.Player(model, motion, loop=True)
        first_frame = len(frames)
        for frame in range(motion.n_frames):
            frames.append(skin_frame(player.frame(frame), rest_world, positions,
                                     palette_indices, weights))
        clips.append((name, first_frame, motion.n_frames, args.fps))
        source_manifest.append({
            "name": name,
            "archive": archive_name,
            "entry": entry_index,
            "frames": motion.n_frames,
            "sha256": hashlib.sha256(entry.data).hexdigest(),
        })

    frame_data, maximum_error, bounds_min, bounds_max = quantise_frames(
        frames, args.quantum_mm
    )
    header_size = HEADER.size
    index_offset = align(header_size)
    batch_offset = align(index_offset + len(indices) * 2)
    clip_offset = align(batch_offset + len(batches) * BATCH.size)
    frame_offset = align(clip_offset + len(clips) * CLIP.size)
    blob = bytearray(frame_offset + len(frame_data))
    HEADER.pack_into(
        blob, 0, MAGIC, VERSION, header_size, len(positions), len(indices),
        len(batches), len(clips), len(frames), index_offset, batch_offset,
        clip_offset, frame_offset, args.quantum_mm * 0.001,
    )
    struct.pack_into(f"<{len(indices)}H", blob, index_offset, *indices)
    for index, batch in enumerate(batches):
        BATCH.pack_into(blob, batch_offset + index * BATCH.size, *batch)
    for index, (name, first_frame, frame_count, fps) in enumerate(clips):
        encoded = name.encode("ascii") + b"\0"
        CLIP.pack_into(blob, clip_offset + index * CLIP.size,
                       encoded.ljust(16, b"\0"), first_frame, frame_count, fps, 0.0)
    blob[frame_offset:] = frame_data

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(blob)
    temporary.replace(output)
    manifest = {
        "format": "re4dc-character-v1",
        "output": str(output.resolve()),
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "model": {
            "archive": args.model_archive,
            "entry": args.model_entry,
            "sha256": hashlib.sha256(model_entry.data).hexdigest(),
            "parts": model.n_parts,
        },
        "vertices": len(positions),
        "triangles": len(indices) // 3,
        "batches": len(batches),
        "frames": len(frames),
        "clips": source_manifest,
        "quantum_mm": args.quantum_mm,
        "maximum_quantisation_error_mm": maximum_error,
        "bounds_mm": {"min": bounds_min, "max": bounds_max},
    }
    manifest_path = Path(args.manifest) if args.manifest else output.with_suffix(output.suffix + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="debug Disc 1 image or extracted archive")
    parser.add_argument("--model-archive", default="pl00.drs")
    parser.add_argument("--model-entry", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--clip", action="append", type=parse_clip, required=True,
                        help="NAME:ARCHIVE:ENTRY (repeatable)")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--quantum-mm", type=float, default=0.0625)
    parser.add_argument("--cache-dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if args.fps <= 0.0 or args.quantum_mm <= 0.0:
        parser.error("fps and quantum must be positive")
    convert(args)


if __name__ == "__main__":
    main()
