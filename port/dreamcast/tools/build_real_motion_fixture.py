#!/usr/bin/env python3
"""Build an ignored C++ fixture from a user-supplied RE4 debug disc.

The generated header contains a little-endian motion image, the model's parts
hierarchy, and host-reference poses. It belongs under port/dreamcast/build/ and
must never be committed: it is derived from the original game disc.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from motion import archive, evalhost, fcv, modelbin  # noqa: E402


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def c_float(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"non-finite reference value: {value}")
    if value == 0.0:
        return "0.0f"
    return value.hex() + "f"


def lines(values, render, width=8):
    values = list(values)
    return ["    " + ", ".join(render(v) for v in values[i:i + width]) + ","
            for i in range(0, len(values), width)]


def extract_archive(source, name, cache_dir):
    source = os.path.abspath(source)
    if not archive.is_disc(source):
        arc = archive.Archive(source)
        if arc.name != name:
            raise ValueError(f"archive is {arc.name}, expected {name}")
        return arc

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / name
    if not os.path.isfile(archive.DTK):
        raise FileNotFoundError(
            f"{archive.DTK} is missing; run configure.py or download dtk v1.8.3"
        )
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    subprocess.run(
        [archive.DTK, "vfs", "cp", f"{source}:/files/em/{name}", str(temporary)],
        check=True,
    )
    temporary.replace(destination)
    return archive.Archive(str(destination))


def build_fixture(args):
    output = Path(args.output)
    cache_dir = Path(args.cache_dir) if args.cache_dir else output.parent / "disc-cache"
    arc = extract_archive(args.source, args.archive, cache_dir)
    model_entry = arc.entry(args.model)
    motion_entry = arc.entry(args.motion)
    if model_entry.tag != "BIN":
        raise ValueError(f"{arc.name}:{args.model} is {model_entry.tag}, expected BIN")
    if motion_entry.tag != "FCV":
        raise ValueError(f"{arc.name}:{args.motion} is {motion_entry.tag}, expected FCV")

    model = modelbin.parse(model_entry.data)
    model.check_tree()
    motion = fcv.parse(motion_entry.data)
    image = fcv.serialise(motion, "<")
    frames = [float(v) for v in args.frames.split(",")]
    if frames != sorted(frames):
        raise ValueError("sample frames must be in ascending order")

    player = evalhost.Player(model, motion)
    poses = [player.frame(frame) for frame in frames]
    blend = model.blend_table or []
    blend_words = [len(blend) & 0xFFFF, len(blend) >> 16]
    blend_words.extend(word for entry in blend for word in entry)

    out = []
    out.append("// Generated from a user-supplied RE4 debug disc. DO NOT COMMIT.\n")
    out.append("#pragma once\n\n")
    out.append("#include <cstddef>\n#include <cstdint>\n\n")
    out.append("namespace re4dc_real_fixture {\n\n")
    out.append(f"static constexpr const char* kArchive = \"{arc.name}\";\n")
    out.append(f"static constexpr int kModelEntry = {args.model};\n")
    out.append(f"static constexpr int kMotionEntry = {args.motion};\n")
    out.append(f"static constexpr int kPartCount = {model.n_parts};\n")
    out.append(f"static constexpr int kJointCount = {len(motion.joints)};\n")
    out.append(f"static constexpr float kMaxFrame = {c_float(motion.max_frame)};\n\n")

    out.append("static const std::int32_t kParents[kPartCount] = {\n")
    out.extend(line + "\n" for line in lines((p.parent for p in model.parts), str, 12))
    out.append("};\n\n")
    out.append("static const float kRestPosition[kPartCount * 3] = {\n")
    out.extend(line + "\n" for line in lines((v for p in model.parts for v in p.pos), c_float, 6))
    out.append("};\n\n")
    out.append(f"static const std::uint16_t kBlendWords[{len(blend_words)}] = {{\n")
    out.extend(line + "\n" for line in lines(blend_words, str, 12))
    out.append("};\n\n")
    out.append(f"alignas(4) static const std::uint8_t kMotionImage[{len(image)}] = {{\n")
    out.extend(line + "\n" for line in lines(image, lambda v: f"0x{v:02x}", 16))
    out.append("};\n\n")

    out.append(f"static constexpr int kSampleCount = {len(frames)};\n")
    out.append("static const float kSampleFrames[kSampleCount] = {\n")
    out.extend(line + "\n" for line in lines(frames, c_float, 8))
    out.append("};\n\n")
    out.append("static const float kExpectedRootPosition[kSampleCount * 3] = {\n")
    out.extend(line + "\n" for line in lines((v for p in poses for v in p.root_pos), c_float, 6))
    out.append("};\n\n")
    out.append("static const float kExpectedRootRotation[kSampleCount * 3] = {\n")
    out.extend(line + "\n" for line in lines((v for p in poses for v in p.root_rot), c_float, 6))
    out.append("};\n\n")
    out.append("static const float kExpectedAngles[kSampleCount * kPartCount * 3] = {\n")
    out.extend(line + "\n" for line in lines((v for p in poses for xyz in p.ang for v in xyz), c_float, 6))
    out.append("};\n\n")
    out.append("static const float kExpectedWorld[kSampleCount * kPartCount * 3] = {\n")
    out.extend(line + "\n" for line in lines((v for p in poses for xyz in p.world for v in xyz), c_float, 6))
    out.append("};\n\n")
    out.append("} // namespace re4dc_real_fixture\n")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text("".join(out), encoding="utf-8")
    temporary.replace(output)

    manifest = {
        "source": os.path.abspath(args.source),
        "archive": arc.name,
        "archive_sha256": sha256(Path(arc.path).read_bytes()),
        "model_entry": args.model,
        "model_entry_sha256": sha256(model_entry.data),
        "parts": model.n_parts,
        "motion_entry": args.motion,
        "motion_entry_sha256": sha256(motion_entry.data),
        "little_endian_image_sha256": sha256(image),
        "motion_bytes": len(image),
        "frames": motion.n_frames,
        "joints": len(motion.joints),
        "ik_chains": sum(1 for joint in motion.joints if joint.kind & 0x30),
        "sample_frames": frames,
    }
    manifest_path = Path(args.manifest) if args.manifest else output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="debug Disc 1 image or extracted .drs")
    parser.add_argument("--archive", default="pl00.drs")
    parser.add_argument("--model", type=int, default=0)
    parser.add_argument("--motion", type=int, default=117)
    parser.add_argument("--frames", default="0,12,35,70")
    parser.add_argument("--cache-dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest")
    build_fixture(parser.parse_args())


if __name__ == "__main__":
    main()
