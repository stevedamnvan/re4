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
VERSION = 2
HEADER = struct.Struct("<4s12If")
BATCH = struct.Struct("<4I")
CLIP = struct.Struct("<16sIIff")
UV = struct.Struct("<2f")


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
    texcoord_offset = be_u32(data, 0x10)
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
    draw_sources = []
    texcoords = []
    draw_vertex_map = {}
    indices = []
    batches = []
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
                texcoord_index = be_u16(data, record + record_size - 2)
                if position_index >= vertex_count:
                    raise ValueError(
                        "GX primitive references a vertex outside the source array"
                    )
                texcoord = texcoord_offset + texcoord_index * 4
                if texcoord_offset == 0 or texcoord + 4 > len(data):
                    raise ValueError("GX primitive references a texture coordinate outside the source array")
                key = (position_index, texcoord_index)
                if key not in draw_vertex_map:
                    if flags & 0x80000000:
                        raw_u, raw_v = struct.unpack_from(">2h", data, texcoord)
                        uv = (raw_u / 256.0, raw_v / 256.0)
                    else:
                        raw_u, raw_v = struct.unpack_from(">2H", data, texcoord)
                        uv = (raw_u / 32768.0, raw_v / 32768.0)
                    draw_vertex_map[key] = len(draw_sources)
                    draw_sources.append(position_index)
                    texcoords.append(uv)
                primitive.append(draw_vertex_map[key])
            if primitive and max(primitive) >= len(draw_sources):
                raise ValueError("GX primitive references a vertex outside the source array")
            for triangle in triangulate(opcode, primitive):
                indices.extend(triangle)
            stream += byte_count
        count = len(indices) - first_index
        if count:
            batches.append((first_index, count, material, part_index))
            texture_bindings.append(
                convert_tpl.MaterialBinding(
                    f"PART_{part_index:03d}", material, alpha_texture
                )
            )
        cursor = stream_end
    return (
        positions, palette_indices, weights, draw_sources, texcoords,
        indices, batches, texture_bindings,
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
    if len(fields) != 3:
        raise argparse.ArgumentTypeError("clip must be NAME:ARCHIVE:ENTRY")
    name, archive_name, entry = fields
    if not name or len(name.encode("ascii", "strict")) > 15:
        raise argparse.ArgumentTypeError("clip name must be 1-15 ASCII bytes")
    return name, archive_name, int(entry, 0)


def parse_attachment(specification):
    fields = specification.split(":")
    if len(fields) != 4:
        raise argparse.ArgumentTypeError(
            "attachment must be NAME:ARCHIVE:MODEL_ENTRY:TEXTURE_ENTRY"
        )
    name, archive_name, model_entry, texture_entry = fields
    if not name or not archive_name:
        raise argparse.ArgumentTypeError("attachment name and archive must not be empty")
    return name, archive_name, int(model_entry, 0), int(texture_entry, 0)


def parse_rigid_attachment(specification):
    fields = specification.split(":")
    if len(fields) != 5:
        raise argparse.ArgumentTypeError(
            "rigid attachment must be NAME:ARCHIVE:MODEL_ENTRY:TEXTURE_ENTRY:PARENT_BONE"
        )
    name, archive_name, model_entry, texture_entry, parent_bone = fields
    if not name or not archive_name:
        raise argparse.ArgumentTypeError("attachment name and archive must not be empty")
    return (
        name, archive_name, int(model_entry, 0), int(texture_entry, 0),
        int(parent_bone, 0),
    )


def sampled_frame_indices(frame_count, step):
    if frame_count <= 0 or step <= 0:
        raise ValueError("frame count and sample step must be positive")
    return list(range(0, frame_count, step))


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

    archives = {args.model_archive: model_archive}
    component_specs = [
        ("body", args.model_archive, args.model_entry, texture_entry_index, None)
    ]
    component_specs.extend((*attachment, None) for attachment in args.attachment)
    component_specs.extend(args.rigid_attachment)
    components = []
    component_manifest = []
    positions = []
    texcoords = []
    indices = []
    batches = []
    texture_bindings = []
    texture_images = []
    texture_sources = {}
    source_vertex_count = 0
    source_triangle_count = 0

    for (component_name, archive_name, model_index, texture_index,
         parent_bone) in component_specs:
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
            source_positions, palette_indices, weights, draw_sources,
            component_uvs, component_indices, component_batches,
            component_bindings,
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

        texture_source_key = (archive_name, texture_index)
        if texture_source_key not in texture_sources:
            texture_entry = component_archive.entry(texture_index)
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

        vertex_base = len(positions)
        index_base = len(indices)
        positions.extend(source_positions[index] for index in draw_sources)
        texcoords.extend(component_uvs)
        indices.extend(vertex_base + index for index in component_indices)
        for batch, binding in zip(component_batches, component_bindings):
            first_index, index_count, material, _ = batch
            global_part = len(texture_bindings)
            batches.append((
                index_base + first_index, index_count, material, global_part
            ))
            texture_bindings.append(convert_tpl.MaterialBinding(
                f"PART_{global_part:03d}",
                image_base + binding.color_image,
                None if binding.alpha_image is None
                else image_base + binding.alpha_image,
            ))
        components.append((
            component_name, source_positions, palette_indices, weights,
            draw_sources, parent_bone,
        ))
        source_vertex_count += len(source_positions)
        source_triangle_count += len(component_indices) // 3
        component_manifest.append({
            "name": component_name,
            "archive": archive_name,
            "model_entry": model_index,
            "model_sha256": hashlib.sha256(component_entry.data).hexdigest(),
            "texture_entry": texture_index,
            "texture_sha256": hashlib.sha256(texture_entry.data).hexdigest(),
            "texture_images": image_count,
            "vertices": len(source_positions),
            "draw_vertices": len(draw_sources),
            "triangles": len(component_indices) // 3,
            "parent_bone": parent_bone,
        })

    frames = []
    clips = []
    source_manifest = []
    for name, archive_name, entry_index in args.clip:
        if archive_name not in archives:
            archives[archive_name] = load_archive(args.source, archive_name, cache_dir)
        entry = archives[archive_name].entry(entry_index)
        if entry.tag != "FCV":
            raise ValueError(f"{archive_name}:{entry_index} is not FCV")
        motion = fcv.parse(entry.data)
        player = evalhost.Player(model, motion, loop=True)
        first_frame = len(frames)
        frame_indices = sampled_frame_indices(motion.n_frames, args.sample_step)
        for frame in frame_indices:
            pose = player.frame(frame)
            combined_frame = []
            for (_, source_positions, palette_indices, weights,
                 draw_sources, parent_bone) in components:
                if parent_bone is None:
                    source_frame = skin_frame(
                        pose, rest_world, source_positions, palette_indices,
                        weights,
                    )
                else:
                    source_frame = [
                        transform_point(pose.mat[parent_bone], position)
                        for position in source_positions
                    ]
                combined_frame.extend(
                    source_frame[index] for index in draw_sources
                )
            frames.append(combined_frame)
        clips.append((
            name, first_frame, len(frame_indices), args.fps / args.sample_step
        ))
        source_manifest.append({
            "name": name,
            "archive": archive_name,
            "entry": entry_index,
            "source_frames": motion.n_frames,
            "frames": len(frame_indices),
            "sha256": hashlib.sha256(entry.data).hexdigest(),
        })

    uv_split_vertex_count = len(positions)
    positions, texcoords, indices, batches, frames = cluster_animated_geometry(
        positions, texcoords, indices, batches, frames, args.cluster_mm
    )
    frame_data, maximum_error, bounds_min, bounds_max = quantise_frames(
        frames, args.quantum_mm
    )
    header_size = HEADER.size
    index_offset = align(header_size)
    batch_offset = align(index_offset + len(indices) * 2)
    clip_offset = align(batch_offset + len(batches) * BATCH.size)
    uv_offset = align(clip_offset + len(clips) * CLIP.size)
    frame_offset = align(uv_offset + len(texcoords) * UV.size)
    blob = bytearray(frame_offset + len(frame_data))
    HEADER.pack_into(
        blob, 0, MAGIC, VERSION, header_size, len(positions), len(indices),
        len(batches), len(clips), len(frames), index_offset, batch_offset,
        clip_offset, uv_offset, frame_offset, args.quantum_mm * 0.001,
    )
    struct.pack_into(f"<{len(indices)}H", blob, index_offset, *indices)
    for index, batch in enumerate(batches):
        BATCH.pack_into(blob, batch_offset + index * BATCH.size, *batch)
    for index, (name, first_frame, frame_count, fps) in enumerate(clips):
        encoded = name.encode("ascii") + b"\0"
        CLIP.pack_into(blob, clip_offset + index * CLIP.size,
                       encoded.ljust(16, b"\0"), first_frame, frame_count, fps, 0.0)
    for index, uv in enumerate(texcoords):
        UV.pack_into(blob, uv_offset + index * UV.size, *uv)
    blob[frame_offset:] = frame_data

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
        texture_images, texture_bindings
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
        "format": "re4dc-character-v2",
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
        "texture": {
            "sources": texture_metadata["tpl_sources"],
            "package": texture_output.name,
            "package_sha256": hashlib.sha256(texture_package).hexdigest(),
            "bytes": len(texture_package),
        },
        "vertices": len(positions),
        "uv_split_vertices": uv_split_vertex_count,
        "triangles": len(indices) // 3,
        "batches": len(batches),
        "cluster_mm": args.cluster_mm,
        "cluster_source_vertices": source_vertex_count,
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
    parser.add_argument("--clip", action="append", type=parse_clip, required=True,
                        help="NAME:ARCHIVE:ENTRY (repeatable)")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--sample-step", type=int, default=1,
                        help="bake every Nth source frame; runtime interpolates")
    parser.add_argument("--quantum-mm", type=float, default=0.0625)
    parser.add_argument("--cluster-mm", type=float, default=0.0,
                        help="coarse per-batch animated-mesh cluster size")
    parser.add_argument("--cache-dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--texture-output")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if (args.fps <= 0.0 or args.quantum_mm <= 0.0 or
            args.cluster_mm < 0.0 or args.sample_step <= 0):
        parser.error(
            "fps, quantum, and sample step must be positive; cluster must be non-negative"
        )
    convert(args)


if __name__ == "__main__":
    main()
