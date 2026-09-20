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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from motion import archive, evalhost, fcv, modelbin  # noqa: E402
import convert_tpl  # noqa: E402


MAGIC = b"R4CH"
VERSION = 6
HEADER = struct.Struct("<4s26If")
BATCH = struct.Struct("<6I")
PRIMITIVE = struct.Struct("<IIHHB3x")
CLIP = struct.Struct("<16sIIff")
DRAW_VERTEX = struct.Struct("<HH2f")
NORMAL_POSITION = struct.Struct("<H")
NORMAL_SOURCE = struct.Struct("<H")
SOURCE_NORMAL = struct.Struct("<3hH")
POSITION_RECORD = struct.Struct("<3fHH")
POSE_MATRIX = struct.Struct("<9h2x3f")


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
    """Return skinned sources plus UV-split draw vertices and material batches."""
    flags = be_u32(data, 0x20)
    shift = data[0x28]
    vertex_offset = be_u32(data, 0x30)
    normal_offset = be_u32(data, 0x34)
    texcoord_offset = be_u32(data, 0x10)
    vertex_count = be_u16(data, 0x38)
    normal_count = be_u16(data, 0x3A)
    part_offset = be_u32(data, 0x1C)
    part_count = be_u16(data, 0x1A)
    weight_offset = be_u32(data, 0x14)
    weight_count = data[0x18]
    weight_ext_count = be_u16(data, 0x2A)
    if weight_ext_count > 0xFF:
        raise ValueError("extended model weights are not supported by the lean converter")
    if weight_count == 0:
        raise ValueError("model has no skinning palette")
    normal_stride = 4 if flags & 0x20000000 else 8
    if (normal_count == 0 or normal_offset == 0 or
            normal_offset + normal_count * normal_stride > len(data)):
        raise ValueError("model normal array exceeds entry")

    source_normals = []
    normal_palettes = []
    for index in range(normal_count):
        offset = normal_offset + index * normal_stride
        if normal_stride == 4:
            x, y, z, palette = struct.unpack_from(">3bB", data, offset)
            source_normals.append((x * 256, y * 256, z * 256))
        else:
            x, y, z, palette = struct.unpack_from(">3hH", data, offset)
            source_normals.append((x, y, z))
        normal_palettes.append(palette)

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
    if min(normal_palettes) < 0 or max(normal_palettes) >= len(weights):
        raise ValueError("normal references a skinning palette entry outside the table")

    record_size = 8 if flags & 0x80000000 else 6
    draw_sources = []
    draw_normals = []
    texcoords = []
    draw_vertex_map = {}
    indices = []
    batches = []
    primitive_indices = []
    primitives = []
    batch_primitive_ranges = []
    texture_bindings = []
    cursor = part_offset
    for part_index in range(part_count):
        if cursor + 0x20 > len(data):
            raise ValueError("model part header exceeds entry")
        material = data[cursor + 0x0C]
        part_flags = data[cursor + 0x0B]
        alpha_texture = data[cursor + 0x0E] if part_flags & 4 else None
        stream_size = be_u32(data, cursor + 0x18)
        stream = cursor + 0x20
        stream_end = stream + stream_size
        if stream_end > len(data):
            raise ValueError("model part stream exceeds entry")
        first_index = len(indices)
        first_primitive = len(primitives)
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
            primitive = []
            for vertex in range(count):
                record = stream + vertex * record_size
                position_index = be_u16(data, record)
                normal_index = be_u16(data, record + 2)
                texcoord_index = be_u16(data, record + record_size - 2)
                if position_index >= vertex_count:
                    raise ValueError(
                        "GX primitive references a vertex outside the source array"
                    )
                if normal_index >= normal_count:
                    raise ValueError(
                        "GX primitive references a normal outside the source array"
                    )
                texcoord = texcoord_offset + texcoord_index * 4
                if texcoord_offset == 0 or texcoord + 4 > len(data):
                    raise ValueError("GX primitive references a texture coordinate outside the source array")
                key = (position_index, normal_index, texcoord_index)
                if key not in draw_vertex_map:
                    if flags & 0x80000000:
                        raw_u, raw_v = struct.unpack_from(">2h", data, texcoord)
                        uv = (raw_u / 256.0, raw_v / 256.0)
                    else:
                        raw_u, raw_v = struct.unpack_from(">2H", data, texcoord)
                        uv = (raw_u / 32768.0, raw_v / 32768.0)
                    draw_vertex_map[key] = len(draw_sources)
                    draw_sources.append(position_index)
                    draw_normals.append(normal_index)
                    texcoords.append(uv)
                primitive.append(draw_vertex_map[key])
            if primitive and max(primitive) >= len(draw_sources):
                raise ValueError("GX primitive references a vertex outside the source array")
            primitive_first_index = len(indices)
            for triangle in triangulate(opcode, primitive):
                indices.extend(triangle)
            primitive_index_count = len(indices) - primitive_first_index
            primitive_first_vertex = len(primitive_indices)
            primitive_indices.extend(primitive)
            primitives.append((
                primitive_first_vertex, primitive_first_index, count,
                primitive_index_count, opcode,
            ))
            stream += byte_count
        count = len(indices) - first_index
        if count:
            batches.append((first_index, count, material, part_index))
            batch_primitive_ranges.append(
                (first_primitive, len(primitives) - first_primitive)
            )
            texture_bindings.append(
                convert_tpl.MaterialBinding(
                    f"PART_{part_index:03d}", material, alpha_texture
                )
            )
        cursor = stream_end
    return (
        positions, palette_indices, weights, source_normals, normal_palettes,
        draw_sources, draw_normals, normal_count, texcoords,
        indices, batches, texture_bindings, primitive_indices, primitives,
        batch_primitive_ranges,
    )


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


def make_weight_palette(pose, rest_world, weights):
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
    return palette


def skin_frame(source_positions, palette_indices, palette):
    return [transform_point(palette[palette_indices[index]], position)
            for index, position in enumerate(source_positions)]


def rigid_component_matrix(pose, parent_bone, translation, yaw):
    sine = math.sin(yaw)
    cosine = math.cos(yaw)
    local = [
        cosine, 0.0, sine, translation[0],
        0.0, 1.0, 0.0, translation[1],
        -sine, 0.0, cosine, translation[2],
    ]
    return affine_multiply(pose.mat[parent_bone], local)


def linear_matrix(matrix):
    return tuple(matrix[index] for index in (0, 1, 2, 4, 5, 6, 8, 9, 10))


def quantise_pose_matrices(frames):
    output = bytearray()
    maximum_error = 0.0
    for frame in frames:
        for matrix in frame:
            quantised = []
            for value in linear_matrix(matrix):
                bounded = max(-1.0, min(1.0, value))
                integer = int(round(bounded * 32767.0))
                quantised.append(integer)
                maximum_error = max(
                    maximum_error, abs(value - integer / 32767.0)
                )
            output += POSE_MATRIX.pack(
                *quantised, matrix[3], matrix[7], matrix[11]
            )
    return output, maximum_error


def normal_matrix_direction_error(frames, source_normals):
    minimum_dot = 1.0
    compared = 0
    for frame in frames:
        for nx, ny, nz, matrix_index in source_normals:
            matrix = linear_matrix(frame[matrix_index])
            quantised = [
                int(round(max(-1.0, min(1.0, value)) * 32767.0)) /
                32767.0
                for value in matrix
            ]
            source = (nx / 16384.0, ny / 16384.0, nz / 16384.0)
            reference = tuple(
                sum(matrix[row * 3 + column] * source[column]
                    for column in range(3))
                for row in range(3)
            )
            candidate = tuple(
                sum(quantised[row * 3 + column] * source[column]
                    for column in range(3))
                for row in range(3)
            )
            reference_length = math.sqrt(sum(value * value for value in reference))
            candidate_length = math.sqrt(sum(value * value for value in candidate))
            if reference_length <= 1.0e-12 or candidate_length <= 1.0e-12:
                continue
            dot = (
                sum(a * b for a, b in zip(reference, candidate)) /
                (reference_length * candidate_length)
            )
            minimum_dot = min(minimum_dot, max(-1.0, min(1.0, dot)))
            compared += 1
    if compared == 0:
        return 0.0
    return math.degrees(math.acos(minimum_dot))


def pose_matrix_position_error(frames, position_records, reference_frames,
                               quantum_mm):
    maximum_error = 0.0
    exact_quantised = 0
    compared = 0
    for matrices, reference_frame in zip(frames, reference_frames):
        for index, (x, y, z, matrix_index) in enumerate(position_records):
            matrix = matrices[matrix_index]
            linear = [
                int(round(max(-1.0, min(1.0, value)) * 32767.0)) /
                32767.0
                for value in linear_matrix(matrix)
            ]
            candidate = (
                linear[0] * x + linear[1] * y + linear[2] * z + matrix[3],
                linear[3] * x + linear[4] * y + linear[5] * z + matrix[7],
                linear[6] * x + linear[7] * y + linear[8] * z + matrix[11],
            )
            reference = reference_frame[index]
            maximum_error = max(
                maximum_error,
                math.sqrt(sum((a - b) ** 2 for a, b in zip(candidate, reference)))
            )
            candidate_quantised = tuple(
                int(round(value / quantum_mm)) for value in candidate
            )
            reference_quantised = tuple(
                int(round(value / quantum_mm)) for value in reference
            )
            exact_quantised += candidate_quantised == reference_quantised
            compared += 1
    return maximum_error, exact_quantised, compared


def cluster_animated_geometry(positions, texcoords, indices, batches, frames,
                              cluster_mm):
    """Create a coarse animated mesh by clustering vertices within each batch.

    Batch scoping prevents separate source parts and materials from welding.
    Every generated animation vertex is the average of its source members, so
    all clips retain the original timing while degenerate and duplicate faces
    are removed.
    """
    if cluster_mm <= 0.0:
        return positions, texcoords, indices, batches, frames

    cluster_members = []
    clustered_indices = []
    clustered_batches = []
    for first_index, index_count, material, part_index in batches:
        source_triangles = []
        members_by_key = {}
        for offset in range(first_index, first_index + index_count, 3):
            keys = []
            for source_index in indices[offset:offset + 3]:
                position = positions[source_index]
                uv = texcoords[source_index]
                key = (
                    *(round(value / cluster_mm) for value in position),
                    round(uv[0] * 4096.0), round(uv[1] * 4096.0),
                )
                members_by_key.setdefault(key, set()).add(source_index)
                keys.append(key)
            source_triangles.append(tuple(keys))

        index_by_key = {}
        for key, members in members_by_key.items():
            index_by_key[key] = len(cluster_members)
            cluster_members.append(tuple(sorted(members)))

        first_clustered_index = len(clustered_indices)
        seen = set()
        for keys in source_triangles:
            triangle = tuple(index_by_key[key] for key in keys)
            if len(set(triangle)) < 3 or triangle in seen:
                continue
            seen.add(triangle)
            clustered_indices.extend(triangle)
        clustered_count = len(clustered_indices) - first_clustered_index
        if clustered_count:
            clustered_batches.append(
                (first_clustered_index, clustered_count, material, part_index)
            )

    if not clustered_indices:
        raise ValueError("character clustering removed every triangle")

    def average_points(points, members):
        count = float(len(members))
        return tuple(
            sum(points[index][axis] for index in members) / count
            for axis in range(3)
        )

    clustered_positions = [
        average_points(positions, members) for members in cluster_members
    ]
    clustered_texcoords = [
        tuple(
            sum(texcoords[index][axis] for index in members) / float(len(members))
            for axis in range(2)
        )
        for members in cluster_members
    ]
    clustered_frames = [
        [average_points(frame, members) for members in cluster_members]
        for frame in frames
    ]
    return (clustered_positions, clustered_texcoords, clustered_indices,
            clustered_batches, clustered_frames)


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
    if len(fields) not in (3, 4):
        raise argparse.ArgumentTypeError(
            "clip must be NAME:ARCHIVE:ENTRY[:SAMPLE_STEP]"
        )
    name, archive_name, entry = fields[:3]
    if not name or len(name.encode("ascii", "strict")) > 15:
        raise argparse.ArgumentTypeError("clip name must be 1-15 ASCII bytes")
    sample_step = int(fields[3], 0) if len(fields) == 4 else None
    if sample_step is not None and sample_step <= 0:
        raise argparse.ArgumentTypeError("clip sample step must be positive")
    return name, archive_name, int(entry, 0), sample_step


def parse_attachment(specification):
    fields = specification.split(":")
    if len(fields) not in (4, 5):
        raise argparse.ArgumentTypeError(
            "attachment must be "
            "NAME:MODEL_ARCHIVE:MODEL_ENTRY:TEXTURE_ENTRY or "
            "NAME:MODEL_ARCHIVE:MODEL_ENTRY:TEXTURE_ARCHIVE:TEXTURE_ENTRY"
        )
    if len(fields) == 4:
        name, model_archive, model_entry, texture_entry = fields
        texture_archive = model_archive
    else:
        name, model_archive, model_entry, texture_archive, texture_entry = fields
    if not name or not model_archive or not texture_archive:
        raise argparse.ArgumentTypeError("attachment name and archive must not be empty")
    return (
        name, model_archive, int(model_entry, 0), texture_archive,
        int(texture_entry, 0),
    )


def parse_rigid_attachment(specification):
    fields = specification.split(":")
    if len(fields) not in (5, 9):
        raise argparse.ArgumentTypeError(
            "rigid attachment must be "
            "NAME:ARCHIVE:MODEL_ENTRY:TEXTURE_ENTRY:PARENT_BONE"
            "[:TX:TY:TZ:YAW]"
        )
    name, archive_name, model_entry, texture_entry, parent_bone = fields[:5]
    if not name or not archive_name:
        raise argparse.ArgumentTypeError("attachment name and archive must not be empty")
    translation = (0.0, 0.0, 0.0)
    yaw = 0.0
    if len(fields) == 9:
        translation = tuple(float(value) for value in fields[5:8])
        yaw = float(fields[8])
    return (
        name, archive_name, int(model_entry, 0), int(texture_entry, 0),
        int(parent_bone, 0), translation, yaw,
    )


def parse_rigid_marker(specification):
    fields = specification.split(":")
    if len(fields) != 9:
        raise argparse.ArgumentTypeError(
            "rigid marker must be NAME:PARENT_BONE:TX:TY:TZ:YAW:PX:PY:PZ"
        )
    name = fields[0]
    if not name or len(name.encode("ascii", "strict")) > 31:
        raise argparse.ArgumentTypeError("marker name must be 1-31 ASCII bytes")
    return (
        name,
        int(fields[1], 0),
        tuple(float(value) for value in fields[2:5]),
        float(fields[5]),
        tuple(float(value) for value in fields[6:9]),
    )


def transform_rigid_point(point, translation, yaw):
    """Apply the child cCoord Y rotation and translation before parenting."""
    x, y, z = point
    sine = math.sin(yaw)
    cosine = math.cos(yaw)
    return (
        cosine * x + sine * z + translation[0],
        y + translation[1],
        -sine * x + cosine * z + translation[2],
    )


def sampled_frame_indices(frame_count, step):
    if frame_count <= 0 or step <= 0:
        raise ValueError("frame count and sample step must be positive")
    indices = list(range(0, frame_count, step))
    final_frame = frame_count - 1
    if indices[-1] != final_frame:
        indices.append(final_frame)
    return indices


def sampled_frames_per_second(frame_indices, source_max_frame, source_fps):
    """Keep a reduced clip's duration equal to its authored FCV duration."""
    if source_max_frame <= 0 or len(frame_indices) <= 1:
        return source_fps
    return (len(frame_indices) - 1) * source_fps / source_max_frame


def root_forward_speed_mps(motion, frames_per_second):
    """Extract FCV root motion applied to the actor by MotionMove."""
    if motion.max_frame <= 0:
        return 0.0
    for joint in motion.joints:
        if joint.kind == 1 and joint.parts_no == 0 and len(joint.axes) >= 3:
            forward = joint.axes[2]
            if not forward.keys:
                return 0.0
            displacement_mm = forward.keys[-1][0] - forward.keys[0][0]
            return displacement_mm * 0.001 * frames_per_second / motion.max_frame
    return 0.0


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
    texture_entry_index = (
        args.texture_entry if args.texture_entry is not None else args.model_entry + 1
    )
    rest_world = rest_world_positions(model)
    for name, parent_bone, _, _, _ in args.rigid_marker:
        if not 0 <= parent_bone < model.n_parts:
            raise ValueError(
                f"marker {name!r} parent bone {parent_bone} is outside "
                f"the base skeleton"
            )

    archives = {args.model_archive: model_archive}
    component_specs = [
        ("body", args.model_archive, args.model_entry, args.model_archive,
         texture_entry_index,
         None, (0.0, 0.0, 0.0), 0.0)
    ]
    component_specs.extend(
        (*attachment, None, (0.0, 0.0, 0.0), 0.0)
        for attachment in args.attachment
    )
    component_specs.extend(
        (name, archive_name, model_index, archive_name, texture_index,
         parent_bone, translation, yaw)
        for (name, archive_name, model_index, texture_index, parent_bone,
             translation, yaw) in args.rigid_attachment
    )
    components = []
    component_manifest = []
    positions = []
    position_records = []
    draw_position_indices = []
    draw_normal_indices = []
    normal_positions = []
    normal_sources = []
    normal_key_map = {}
    source_normals = []
    texcoords = []
    indices = []
    batches = []
    primitive_indices = []
    primitives = []
    batch_primitive_ranges = []
    texture_bindings = []
    texture_images = []
    texture_sources = {}
    source_vertex_count = 0
    source_normal_count = 0
    normal_matrix_count = 0
    source_triangle_count = 0

    for (component_name, archive_name, model_index, texture_archive_name,
         texture_index,
         parent_bone, rigid_translation, rigid_yaw) in component_specs:
        if archive_name not in archives:
            archives[archive_name] = load_archive(args.source, archive_name, cache_dir)
        component_archive = archives[archive_name]
        component_entry = component_archive.entry(model_index)
        if component_entry.tag != "BIN":
            raise ValueError(
                f"component {component_name!r} model entry is not BIN"
            )
        geometry = parse_geometry(component_entry.data)
        (
            component_positions, palette_indices, weights,
            component_normals, normal_palettes, draw_sources,
            draw_normals, component_normal_count, component_uvs,
            component_indices, component_batches,
            component_bindings, component_primitive_indices,
            component_primitives, component_batch_primitive_ranges,
        ) = geometry
        referenced_bones = [bone for ids, _ in weights for bone in ids]
        if (parent_bone is None and referenced_bones and
                max(referenced_bones) >= model.n_parts):
            raise ValueError(
                f"component {component_name!r} references bone "
                f"{max(referenced_bones)}, but the base skeleton has {model.n_parts} parts"
            )
        if parent_bone is not None and not 0 <= parent_bone < model.n_parts:
            raise ValueError(
                f"component {component_name!r} parent bone {parent_bone} "
                f"is outside the base skeleton"
            )

        if texture_archive_name not in archives:
            archives[texture_archive_name] = load_archive(
                args.source, texture_archive_name, cache_dir
            )
        texture_archive = archives[texture_archive_name]
        texture_source_key = (texture_archive_name, texture_index)
        if texture_source_key not in texture_sources:
            texture_entry = texture_archive.entry(texture_index)
            if texture_entry.tag != "TPL":
                raise ValueError(
                    f"component {component_name!r} texture entry is not TPL"
                )
            image_base = len(texture_images)
            images = convert_tpl.parse_tpl(texture_entry.data)
            texture_images.extend(images)
            texture_sources[texture_source_key] = (
                image_base, texture_entry, len(images)
            )
        image_base, texture_entry, image_count = texture_sources[texture_source_key]

        position_base = len(positions)
        draw_vertex_base = len(draw_position_indices)
        normal_source_base = source_normal_count
        normal_matrix_base = normal_matrix_count
        index_base = len(indices)
        primitive_index_base = len(primitive_indices)
        primitive_base = len(primitives)
        positions.extend(component_positions)
        position_records.extend(
            (*position, normal_matrix_base + palette)
            for position, palette in zip(component_positions, palette_indices)
        )
        source_normals.extend(
            (*normal, normal_matrix_base + palette)
            for normal, palette in zip(component_normals, normal_palettes)
        )
        for source_position, source_normal in zip(draw_sources, draw_normals):
            position_index = position_base + source_position
            normal_key = (position_index, normal_source_base + source_normal)
            if normal_key not in normal_key_map:
                normal_key_map[normal_key] = len(normal_positions)
                normal_positions.append(position_index)
                normal_sources.append(normal_source_base + source_normal)
            draw_position_indices.append(position_index)
            draw_normal_indices.append(normal_key_map[normal_key])
        texcoords.extend(component_uvs)
        indices.extend(draw_vertex_base + index for index in component_indices)
        primitive_indices.extend(
            draw_vertex_base + index for index in component_primitive_indices
        )
        primitives.extend((
            primitive_index_base + first_vertex,
            index_base + first_index,
            vertex_count,
            index_count,
            opcode,
        ) for (first_vertex, first_index, vertex_count, index_count, opcode)
                          in component_primitives)
        for batch, binding, primitive_range in zip(
                component_batches, component_bindings,
                component_batch_primitive_ranges):
            first_index, index_count, material, _ = batch
            first_primitive, primitive_count = primitive_range
            global_part = len(texture_bindings)
            batches.append((
                index_base + first_index, index_count, material, global_part
            ))
            batch_primitive_ranges.append((
                primitive_base + first_primitive, primitive_count
            ))
            texture_bindings.append(convert_tpl.MaterialBinding(
                f"PART_{global_part:03d}",
                image_base + binding.color_image,
                None if binding.alpha_image is None
                else image_base + binding.alpha_image,
            ))
        components.append((
            component_name, component_positions, palette_indices, weights,
            parent_bone, rigid_translation, rigid_yaw,
        ))
        source_vertex_count += len(component_positions)
        source_normal_count += component_normal_count
        normal_matrix_count += len(weights)
        source_triangle_count += len(component_indices) // 3
        component_manifest.append({
            "name": component_name,
            "archive": archive_name,
            "model_entry": model_index,
            "model_sha256": hashlib.sha256(component_entry.data).hexdigest(),
            "texture_archive": texture_archive_name,
            "texture_entry": texture_index,
            "texture_sha256": hashlib.sha256(texture_entry.data).hexdigest(),
            "texture_images": image_count,
            "vertices": len(component_positions),
            "normals": component_normal_count,
            "draw_vertices": len(draw_sources),
            "triangles": len(component_indices) // 3,
            "parent_bone": parent_bone,
            "translation": list(rigid_translation),
            "yaw": rigid_yaw,
        })

    frames = []
    pose_matrix_frames = []
    marker_frames = []
    clips = []
    source_manifest = []
    for name, archive_name, entry_index, clip_sample_step in args.clip:
        if archive_name not in archives:
            archives[archive_name] = load_archive(args.source, archive_name, cache_dir)
        entry = archives[archive_name].entry(entry_index)
        if entry.tag != "FCV":
            raise ValueError(f"{archive_name}:{entry_index} is not FCV")
        motion = fcv.parse(entry.data)
        # Evaluate the source frame range without the host's loop attribute.
        # The Dreamcast runtime decides which clips loop. Enabling it here can
        # wrap the final sampled frame of one-shot hit/death motions back toward
        # their starting pose and bake the wrong terminal silhouette.
        player = evalhost.Player(model, motion, loop=False)
        first_frame = len(frames)
        sample_step = clip_sample_step or args.sample_step
        frame_indices = sampled_frame_indices(motion.n_frames, sample_step)
        for frame in frame_indices:
            pose = player.frame(frame)
            combined_frame = []
            combined_pose_matrices = []
            for (_, source_positions, palette_indices, weights,
                 parent_bone, rigid_translation,
                 rigid_yaw) in components:
                if parent_bone is None:
                    palette = make_weight_palette(pose, rest_world, weights)
                    source_frame = skin_frame(
                        source_positions, palette_indices, palette
                    )
                    combined_pose_matrices.extend(palette)
                else:
                    rigid_matrix = rigid_component_matrix(
                        pose, parent_bone, rigid_translation, rigid_yaw
                    )
                    source_frame = [
                        transform_point(rigid_matrix, position)
                        for position in source_positions
                    ]
                    combined_pose_matrices.extend(
                        rigid_matrix for _ in weights
                    )
                combined_frame.extend(source_frame)
            frames.append(combined_frame)
            if len(combined_pose_matrices) != normal_matrix_count:
                raise ValueError("pose matrix palette count changed between frames")
            pose_matrix_frames.append(combined_pose_matrices)
            marker_frames.append([
                transform_point(
                    pose.mat[parent_bone],
                    transform_rigid_point(point, translation, yaw),
                )
                for (_, parent_bone, translation, yaw, point)
                in args.rigid_marker
            ])
        root_speed = root_forward_speed_mps(motion, args.fps)
        sampled_fps = sampled_frames_per_second(
            frame_indices, motion.max_frame, args.fps
        )
        clips.append((
            name, first_frame, len(frame_indices), sampled_fps,
            root_speed,
        ))
        source_manifest.append({
            "name": name,
            "archive": archive_name,
            "entry": entry_index,
            "source_frames": motion.n_frames,
            "frames": len(frame_indices),
            "sample_step": sample_step,
            "root_forward_speed_mps": root_speed,
            "sha256": hashlib.sha256(entry.data).hexdigest(),
        })

    uv_split_vertex_count = len(draw_position_indices)
    if args.cluster_mm > 0.0:
        expanded_positions = [positions[index] for index in draw_position_indices]
        expanded_frames = [
            [frame[index] for index in draw_position_indices]
            for frame in frames
        ]
        positions, texcoords, indices, batches, frames = cluster_animated_geometry(
            expanded_positions, texcoords, indices, batches, expanded_frames,
            args.cluster_mm
        )
        draw_position_indices = list(range(len(positions)))
        draw_normal_indices = list(range(len(positions)))
        normal_positions = list(range(len(positions)))
        normal_sources = []
        source_normals = []
        position_records = []
        normal_matrix_count = 0
        pose_matrix_frames = []
        # Position clustering can remove degenerate triangles and changes draw
        # vertex identities, so the source GX streams are no longer valid.
        # Keep the package readable and select the triangle-normal fallback.
        primitive_indices = []
        primitives = []
        batch_primitive_ranges = [(0, 0) for _ in batches]
    # Markers are unindexed animation points used by native gameplay checks.
    # Append them after clustering so mesh reduction can never merge or remove
    # a source-authored weapon sweep point.
    positions.extend((0.0, 0.0, 0.0) for _ in args.rigid_marker)
    for frame, markers in zip(frames, marker_frames):
        frame.extend(markers)
    legacy_frame_data, maximum_error, bounds_min, bounds_max = quantise_frames(
        frames, args.quantum_mm
    )
    skinned_position_count = len(position_records)
    stored_frame_positions = marker_frames if position_records else frames
    marker_frame_data, _, _, _ = quantise_frames(
        stored_frame_positions, args.quantum_mm
    )
    pose_matrix_data, normal_matrix_error = quantise_pose_matrices(
        pose_matrix_frames
    )
    normal_direction_error = normal_matrix_direction_error(
        pose_matrix_frames, source_normals
    )
    position_matrix_error, exact_quantised_positions, compared_positions = (
        pose_matrix_position_error(
            pose_matrix_frames, position_records, frames, args.quantum_mm
        ) if position_records else (0.0, 0, 0)
    )
    if normal_sources and len(normal_sources) != len(normal_positions):
        raise ValueError("normal source map does not match normal work items")
    if normal_matrix_count > 0xFFFF or len(source_normals) > 0xFFFF:
        raise ValueError("source normal records exceed uint16 package indices")
    if max((len(positions), len(texcoords), len(normal_positions)),
           default=0) > 0xFFFF:
        raise ValueError(
            "character position/normal/draw counts exceed uint16 package indices"
        )
    header_size = HEADER.size
    index_offset = align(header_size)
    batch_offset = align(index_offset + len(indices) * 2)
    primitive_offset = align(batch_offset + len(batches) * BATCH.size)
    primitive_index_offset = align(
        primitive_offset + len(primitives) * PRIMITIVE.size
    )
    clip_offset = align(primitive_index_offset + len(primitive_indices) * 2)
    draw_vertex_offset = align(clip_offset + len(clips) * CLIP.size)
    normal_position_offset = align(
        draw_vertex_offset + len(texcoords) * DRAW_VERTEX.size
    )
    normal_source_offset = align(
        normal_position_offset + len(normal_positions) * NORMAL_POSITION.size
    )
    source_normal_offset = align(
        normal_source_offset + len(normal_sources) * NORMAL_SOURCE.size
    )
    position_record_offset = align(
        source_normal_offset + len(source_normals) * SOURCE_NORMAL.size
    )
    marker_frame_offset = align(
        position_record_offset + len(position_records) * POSITION_RECORD.size
    )
    pose_matrix_offset = align(marker_frame_offset + len(marker_frame_data))
    blob = bytearray(pose_matrix_offset + len(pose_matrix_data))
    HEADER.pack_into(
        blob, 0, MAGIC, VERSION, header_size, len(positions),
        skinned_position_count, len(texcoords),
        len(normal_positions), len(source_normals), len(indices), len(batches),
        len(clips), len(frames), len(primitives),
        len(primitive_indices), normal_matrix_count,
        index_offset, batch_offset, primitive_offset,
        primitive_index_offset, clip_offset, draw_vertex_offset,
        normal_position_offset, normal_source_offset, source_normal_offset,
        position_record_offset, marker_frame_offset, pose_matrix_offset,
        args.quantum_mm * 0.001,
    )
    struct.pack_into(f"<{len(indices)}H", blob, index_offset, *indices)
    for index, (batch, primitive_range) in enumerate(
            zip(batches, batch_primitive_ranges)):
        BATCH.pack_into(
            blob, batch_offset + index * BATCH.size,
            *batch, *primitive_range,
        )
    for index, primitive in enumerate(primitives):
        PRIMITIVE.pack_into(
            blob, primitive_offset + index * PRIMITIVE.size, *primitive
        )
    if primitive_indices:
        struct.pack_into(
            f"<{len(primitive_indices)}H", blob, primitive_index_offset,
            *primitive_indices,
        )
    for index, (name, first_frame, frame_count, fps, root_speed) in enumerate(clips):
        encoded = name.encode("ascii") + b"\0"
        CLIP.pack_into(blob, clip_offset + index * CLIP.size,
                       encoded.ljust(16, b"\0"), first_frame, frame_count, fps,
                       root_speed)
    for index, (position, normal, uv) in enumerate(zip(
            draw_position_indices, draw_normal_indices, texcoords)):
        DRAW_VERTEX.pack_into(
            blob, draw_vertex_offset + index * DRAW_VERTEX.size,
            position, normal, *uv,
        )
    for index, position in enumerate(normal_positions):
        NORMAL_POSITION.pack_into(
            blob, normal_position_offset + index * NORMAL_POSITION.size,
            position,
        )
    for index, source_normal in enumerate(normal_sources):
        NORMAL_SOURCE.pack_into(
            blob, normal_source_offset + index * NORMAL_SOURCE.size,
            source_normal,
        )
    for index, normal in enumerate(source_normals):
        SOURCE_NORMAL.pack_into(
            blob, source_normal_offset + index * SOURCE_NORMAL.size,
            *normal,
        )
    for index, position in enumerate(position_records):
        POSITION_RECORD.pack_into(
            blob, position_record_offset + index * POSITION_RECORD.size,
            *position, 0,
        )
    blob[marker_frame_offset:marker_frame_offset + len(marker_frame_data)] = (
        marker_frame_data
    )
    blob[pose_matrix_offset:pose_matrix_offset + len(pose_matrix_data)] = (
        pose_matrix_data
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(blob)
    temporary.replace(output)
    texture_output = (
        Path(args.texture_output)
        if args.texture_output
        else output.with_suffix(".re4tex")
    )
    texture_package, texture_metadata = convert_tpl.build_package(
        texture_images, texture_bindings, args.texture_max_dimension,
        args.twiddle_textures
    )
    texture_output.parent.mkdir(parents=True, exist_ok=True)
    texture_temporary = texture_output.with_suffix(texture_output.suffix + ".tmp")
    texture_temporary.write_bytes(texture_package)
    texture_temporary.replace(texture_output)
    texture_metadata.update({
        "tpl_sources": [
            {
                "archive": archive_name,
                "entry": entry_index,
                "sha256": hashlib.sha256(entry.data).hexdigest(),
                "images": image_count,
            }
            for (archive_name, entry_index), (_, entry, image_count)
            in texture_sources.items()
        ],
        "package": texture_output.name,
        "package_bytes": len(texture_package),
        "package_sha256": hashlib.sha256(texture_package).hexdigest(),
    })
    texture_manifest = texture_output.with_suffix(texture_output.suffix + ".json")
    texture_manifest.write_text(
        json.dumps(texture_metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "format": "re4dc-character-v6",
        "output": str(output.resolve()),
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "model": {
            "archive": args.model_archive,
            "entry": args.model_entry,
            "sha256": hashlib.sha256(model_entry.data).hexdigest(),
            "parts": model.n_parts,
        },
        "components": component_manifest,
        "markers": [
            {
                "name": name,
                "parent_bone": parent_bone,
                "translation": list(translation),
                "yaw": yaw,
                "point": list(point),
            }
            for name, parent_bone, translation, yaw, point
            in args.rigid_marker
        ],
        "texture": {
            "sources": texture_metadata["tpl_sources"],
            "package": texture_output.name,
            "package_sha256": hashlib.sha256(texture_package).hexdigest(),
            "bytes": len(texture_package),
        },
        "positions": len(positions),
        "skinned_positions": skinned_position_count,
        "marker_positions": len(positions) - skinned_position_count,
        "position_record_bytes": len(position_records) * POSITION_RECORD.size,
        "marker_frame_bytes": len(marker_frame_data),
        "legacy_frame_bytes": len(legacy_frame_data),
        "legacy_frame_sha256": hashlib.sha256(legacy_frame_data).hexdigest(),
        "draw_vertices": len(texcoords),
        "normal_work_items": len(normal_positions),
        "source_normals": len(source_normals),
        "normal_matrices_per_frame": normal_matrix_count,
        "pose_matrix_bytes": len(pose_matrix_data),
        "maximum_normal_matrix_error": normal_matrix_error,
        "maximum_normal_direction_error_degrees": normal_direction_error,
        "maximum_position_matrix_error_mm": position_matrix_error,
        "exact_legacy_quantised_positions": exact_quantised_positions,
        "compared_legacy_quantised_positions": compared_positions,
        "vertices": len(texcoords),
        "uv_split_vertices": uv_split_vertex_count,
        "triangles": len(indices) // 3,
        "batches": len(batches),
        "source_primitives": len(primitives),
        "source_primitive_vertices": len(primitive_indices),
        "cluster_mm": args.cluster_mm,
        "cluster_source_vertices": source_vertex_count,
        "cluster_source_normals": source_normal_count,
        "cluster_source_triangles": source_triangle_count,
        "frames": len(frames),
        "sample_step": args.sample_step,
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
    parser.add_argument("--texture-entry", type=lambda value: int(value, 0))
    parser.add_argument(
        "--attachment", action="append", type=parse_attachment, default=[],
        help="NAME:ARCHIVE:MODEL_ENTRY:TEXTURE_ENTRY (repeatable)",
    )
    parser.add_argument(
        "--rigid-attachment", action="append", type=parse_rigid_attachment,
        default=[],
        help="NAME:ARCHIVE:MODEL_ENTRY:TEXTURE_ENTRY:PARENT_BONE (repeatable)",
    )
    parser.add_argument(
        "--rigid-marker", action="append", type=parse_rigid_marker, default=[],
        help="NAME:PARENT_BONE:TX:TY:TZ:YAW:PX:PY:PZ (repeatable)",
    )
    parser.add_argument("--clip", action="append", type=parse_clip, required=True,
                        help="NAME:ARCHIVE:ENTRY[:SAMPLE_STEP] (repeatable)")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--sample-step", type=int, default=1,
                        help="bake every Nth source frame; runtime interpolates")
    parser.add_argument("--quantum-mm", type=float, default=0.0625)
    parser.add_argument("--cluster-mm", type=float, default=0.0,
                        help="coarse per-batch animated-mesh cluster size")
    parser.add_argument("--cache-dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--texture-output")
    parser.add_argument(
        "--twiddle-textures", action="store_true",
        help="write texture payloads in the PVR's twiddled order",
    )
    parser.add_argument(
        "--texture-max-dimension", type=int,
        help="halve oversized character textures to fit a bounded VRAM budget",
    )
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if (args.fps <= 0.0 or args.quantum_mm <= 0.0 or
            args.cluster_mm < 0.0 or args.sample_step <= 0):
        parser.error(
            "fps, quantum, and sample step must be positive; cluster must be non-negative"
        )
    if args.texture_max_dimension is not None and args.texture_max_dimension < 8:
        parser.error("texture max dimension must be at least 8")
    if any(not 0 <= marker[1] < 256 for marker in args.rigid_marker):
        parser.error("marker parent bone must be in 0..255")
    convert(args)


if __name__ == "__main__":
    main()
