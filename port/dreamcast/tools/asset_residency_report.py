#!/usr/bin/env python3
"""Compare each GameCube RE4 texture with its current and candidate Dreamcast
representations, and report the VRAM cost of every candidate.

R4 deliverable 1. The tool reads the private GameCube TPL and MTL through the
same decoders `convert_tpl.py` uses for the build, and the built Dreamcast
package through its own header, so the "GameCube" and "current" columns are the
real assets rather than assumptions. It measures the content of every image
(distinct colours, alpha use) so that a palette or a format narrowing can be
called lossless where it provably is, and it prices every candidate in bytes.

It does not decide picture quality. Vector quantisation is lossy and its cost is
exact but its acceptability is not; candidates that need an encoder pass and a
moving-scene review are marked as such.

PS2 RE4 is the third reference: for each material it records what Capcom shipped
on their own constrained port. That column is filled from `--ps2-manifest`, a
JSON file produced separately from a PS2 disc. When no manifest is given the
column reads "no PS2 source", which is the current state of this workspace.

Usage:
  asset_residency_report.py --tpl R100.TPL.TPL --mtl R100.allparts.mtl \\
      --package build/private/r100-entry-source.re4tex [--max-dimension 256] \\
      [--ps2-manifest ps2.json] [--format markdown] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import convert_tpl  # noqa: E402  (tool lives beside it)


# PVR texture memory arithmetic. A twiddled 16-bit texture is two bytes per
# pixel. A vector-quantised texture is a 256-entry codebook of 2x2 blocks of
# 16-bit pixels, 2048 bytes, plus one index byte per 2x2 block. Palettised
# textures store one index per pixel and keep their entries in the PVR's
# palette RAM rather than in texture memory.
VQ_CODEBOOK_BYTES = 2048
PALETTE_RAM_ENTRIES = 1024

GX_FORMAT_NAMES = {
    convert_tpl.GX_TF_I4: "I4",
    convert_tpl.GX_TF_I8: "I8",
    convert_tpl.GX_TF_IA4: "IA4",
    convert_tpl.GX_TF_IA8: "IA8",
    convert_tpl.GX_TF_RGBA8: "RGBA8",
    convert_tpl.GX_TF_C4: "C4",
    convert_tpl.GX_TF_C8: "C8",
    convert_tpl.GX_TF_CMPR: "CMPR",
}

DC_FORMAT_NAMES = {0: "rgb565", 1: "argb1555", 2: "argb4444"}


def bytes_16bpp(width: int, height: int) -> int:
    return width * height * 2


def bytes_vq(width: int, height: int) -> int:
    # Blocks are 2x2; odd dimensions are not produced by this pipeline.
    return VQ_CODEBOOK_BYTES + (width * height + 3) // 4


def bytes_pal8(width: int, height: int) -> int:
    return width * height


def bytes_pal4(width: int, height: int) -> int:
    return (width * height + 1) // 2


def power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def read_package(path: pathlib.Path) -> dict[str, dict]:
    """Return the built package's per-material record, keyed by material name."""
    data = path.read_bytes()
    header = struct.unpack_from("<8s10I", data, 0)
    magic = header[0]
    if magic != b"RE4DCTX\0":
        raise ValueError(f"{path.name} is not a Dreamcast texture package")
    (version, header_size, texture_stride, texture_count, texture_offset,
     data_offset, data_size, payload_crc32, source_image_count,
     flags) = header[1:]
    if texture_stride != 88:
        raise ValueError(f"unexpected texture stride {texture_stride}")
    textures = {}
    for index in range(texture_count):
        record = struct.unpack_from(
            "<64s6I", data, texture_offset + index * texture_stride)
        name = record[0].split(b"\0")[0].decode("ascii")
        textures[name] = {
            "width": record[1],
            "height": record[2],
            "format": DC_FORMAT_NAMES.get(record[3], f"format{record[3]}"),
            "bytes": record[5],
        }
    return {
        "version": version,
        "texture_count": texture_count,
        "data_size": data_size,
        "source_image_count": source_image_count,
        "textures": textures,
    }


def measure(pixels: list[tuple[int, int, int, int]]) -> dict:
    """Content facts that decide whether a narrowing is lossless."""
    rgb = set()
    rgba = set()
    alphas = set()
    for pixel in pixels:
        rgba.add(pixel)
        rgb.add(pixel[:3])
        alphas.add(pixel[3])
    binary_alpha = alphas <= {0, 255}
    return {
        "distinct_rgb": len(rgb),
        "distinct_rgba": len(rgba),
        "has_alpha": alphas != {255},
        "binary_alpha": binary_alpha and alphas != {255},
        "distinct_alpha": len(alphas),
    }


def combined_pixels(color_pixels, alpha_pixels):
    """Apply a separate alpha image the way the converter does, for measurement."""
    if alpha_pixels is None:
        return color_pixels
    if len(alpha_pixels) != len(color_pixels):
        return color_pixels
    return [
        (c[0], c[1], c[2], a[0])
        for c, a in zip(color_pixels, alpha_pixels)
    ]


def reduced_size(width: int, height: int, limit: int | None) -> tuple[int, int]:
    """The dimensions the build produced under --max-dimension."""
    if limit is None:
        return width, height
    while width > limit or height > limit:
        width = max(1, width // 2)
        height = max(1, height // 2)
    return width, height


def reduce_pixels(pixels, width, height, target_width, target_height):
    """Halve with the converter's box filter until the build's size is reached,
    so colour counts are measured on the pixels a candidate would actually
    store rather than on the full-resolution source."""
    while (width, height) != (target_width, target_height) and (
            width > target_width or height > target_height):
        pixels, width, height = convert_tpl.downsample_box(
            pixels, width, height)
    return pixels, width, height


def decide(record: dict, spend_vq: bool = False) -> tuple[str, str]:
    """Pick a candidate and say why.

    The order of these rules is a measurement, not a preference. Encoding the
    r100 textures with `pvrtex` and comparing both representations against the
    same GameCube source (evidence `d258-r4-texture-inventory`) showed two
    different situations:

    * For a texture the build reduced to meet the 256-pixel limit, restoring
      the authored resolution under vector quantisation is better on both
      axes at once: 5.7 to 7.3 dB more PSNR than the reduced uncompressed
      texture we ship today, for roughly half the VRAM. There is no trade-off
      to review, so this is taken by default.
    * For a texture the build did not reduce, vector quantisation is a pure
      loss of 3.4 to 13.5 dB in exchange for VRAM. That is a real trade-off,
      so it is only offered when the caller asks for it with `spend_vq`, and
      it still needs a moving-scene review before acceptance.

    Palette narrowings come first where they are provably lossless, subject to
    the palette-bank budget the caller applies afterwards.
    """
    if record["distinct_rgba"] <= 16:
        return "pal4", "lossless at %dx%d: %d distinct colours" % (
            record["width"], record["height"], record["distinct_rgba"])
    if record["distinct_rgba"] <= 256:
        return "pal8", "lossless at %dx%d: %d distinct colours" % (
            record["width"], record["height"], record["distinct_rgba"])
    if record["was_reduced"] and record["gc_vq_bytes"] <= record["current_bytes"]:
        return "gc_vq", (
            "restores %dx%d for %d B against %d B at %dx%d: more detail and "
            "less VRAM" % (
                record["gc_width"], record["gc_height"], record["gc_vq_bytes"],
                record["current_bytes"], record["width"], record["height"]))
    if spend_vq and record["vq_bytes"] < record["current_bytes"]:
        return "vq", (
            "%d B against %d B at the same size, but VQ costs quality here; "
            "needs a moving-scene review" % (
                record["vq_bytes"], record["current_bytes"]))
    return "keep", "authored resolution already fits uncompressed"


def build_rows(tpl_path, mtl_path, package_path, limit, ps2, spend_vq=False):
    images = convert_tpl.parse_tpl(tpl_path.read_bytes())
    bindings = convert_tpl.parse_mtl(
        mtl_path.read_bytes().decode("utf-8-sig"))
    package = read_package(package_path)
    decoded: dict[int, list] = {}

    def pixels_for(index: int):
        if index not in decoded:
            decoded[index] = convert_tpl.decode_image(images[index])
        return decoded[index]

    rows = []
    for binding in bindings:
        color = images[binding.color_image]
        current = package["textures"].get(binding.name)
        if current is None:
            continue
        gc_pixels = combined_pixels(
            pixels_for(binding.color_image),
            pixels_for(binding.alpha_image)
            if binding.alpha_image is not None else None)
        width, height = current["width"], current["height"]
        gc_width, gc_height = color.width, color.height
        expected = reduced_size(gc_width, gc_height, limit)
        # Colour facts for a candidate stored at the current size come from the
        # reduced pixels; the GameCube-size facts come from the source pixels.
        current_pixels, _, _ = reduce_pixels(
            gc_pixels, gc_width, gc_height, width, height)
        facts = measure(current_pixels)
        gc_facts = measure(gc_pixels)
        row = {
            "material": binding.name,
            "gc_width": gc_width,
            "gc_height": gc_height,
            "gc_format": GX_FORMAT_NAMES.get(color.format, str(color.format)),
            "gc_tpl_bytes": len(color.data),
            "gc_alpha_image": binding.alpha_image is not None,
            "gc_alpha_tpl_bytes": (
                len(images[binding.alpha_image].data)
                if binding.alpha_image is not None else 0),
            "width": width,
            "height": height,
            "current_format": current["format"],
            "current_bytes": current["bytes"],
            "was_reduced": (gc_width, gc_height) != (width, height),
            "reduction_matches_limit": expected == (width, height),
            "gc_16bpp_bytes": bytes_16bpp(gc_width, gc_height),
            "gc_vq_bytes": bytes_vq(gc_width, gc_height),
            "vq_bytes": bytes_vq(width, height),
            "pal8_bytes": bytes_pal8(width, height),
            "pal4_bytes": bytes_pal4(width, height),
            "power_of_two": power_of_two(width) and power_of_two(height),
            "gc_distinct_rgba": gc_facts["distinct_rgba"],
            "gc_distinct_rgb": gc_facts["distinct_rgb"],
            "ps2": ps2.get(binding.name) if ps2 else None,
        }
        row.update(facts)
        candidate, reason = decide(row, spend_vq)
        row["candidate"] = candidate
        row["reason"] = reason
        row["candidate_bytes"] = {
            "pal4": row["pal4_bytes"],
            "pal8": row["pal8_bytes"],
            "gc_vq": row["gc_vq_bytes"],
            "vq": row["vq_bytes"],
            "keep": row["current_bytes"],
        }[candidate]
        rows.append(row)
    return rows, package


def apply_palette_budget(rows: list[dict]) -> list[dict]:
    """The PVR holds 1024 palette entries. A palette decision is only valid
    while the simultaneously resident set fits, so keep the palette candidates
    that save the most bytes per entry consumed and send the rest to their next
    best candidate. This assumes every texture of one room is resident at once,
    which is what the current build does; a residency model that guarantees
    fewer simultaneous textures can revisit it."""
    palette_rows = [
        row for row in rows if row["candidate"] in ("pal4", "pal8")]
    entries = {"pal4": 16, "pal8": 256}

    def value(row):
        saved = row["current_bytes"] - row["candidate_bytes"]
        return saved / entries[row["candidate"]]

    remaining = PALETTE_RAM_ENTRIES
    for row in sorted(palette_rows, key=value, reverse=True):
        needed = entries[row["candidate"]]
        if needed <= remaining:
            remaining -= needed
            continue
        # Demote to the best non-palette candidate.
        row["palette_demoted_from"] = row["candidate"]
        if row["vq_bytes"] < row["current_bytes"]:
            row["candidate"] = "vq"
            row["candidate_bytes"] = row["vq_bytes"]
            row["reason"] = (
                "%d B against %d B at the same size; needs VQ review "
                "(palette bank budget exhausted)" % (
                    row["vq_bytes"], row["current_bytes"]))
        else:
            row["candidate"] = "keep"
            row["candidate_bytes"] = row["current_bytes"]
            row["reason"] = (
                "already the cheapest representation "
                "(palette bank budget exhausted)")
    return rows


def palette_budget(rows: list[dict]) -> dict:
    """The PVR keeps 1024 palette entries. PAL8 textures need a 256-entry bank
    each and PAL4 textures a 16-entry bank each, so a palette decision is only
    valid while the simultaneously resident set fits."""
    pal8 = [row for row in rows if row["candidate"] == "pal8"]
    pal4 = [row for row in rows if row["candidate"] == "pal4"]
    return {
        "pal8_textures": len(pal8),
        "pal4_textures": len(pal4),
        "entries_required": len(pal8) * 256 + len(pal4) * 16,
        "entries_available": PALETTE_RAM_ENTRIES,
        "fits": len(pal8) * 256 + len(pal4) * 16 <= PALETTE_RAM_ENTRIES,
    }


def emit_markdown(rows, package, budget, out) -> None:
    current_total = sum(row["current_bytes"] for row in rows)
    candidate_total = sum(row["candidate_bytes"] for row in rows)
    gc_total = sum(row["gc_16bpp_bytes"] for row in rows)
    print("| Material | GC | PS2 | Current DC | DC candidate | VRAM | Decision |",
          file=out)
    print("|---|---|---|---|---|---:|---|", file=out)
    for row in rows:
        gc = "%dx%d %s" % (row["gc_width"], row["gc_height"], row["gc_format"])
        ps2 = row["ps2"] or "no PS2 source"
        cur = "%dx%d %s %d B" % (
            row["width"], row["height"], row["current_format"],
            row["current_bytes"])
        if row["candidate"] == "gc_vq":
            candidate = "%dx%d VQ" % (row["gc_width"], row["gc_height"])
        elif row["candidate"] == "vq":
            candidate = "%dx%d VQ" % (row["width"], row["height"])
        elif row["candidate"] == "keep":
            candidate = "unchanged"
        else:
            candidate = "%dx%d %s" % (
                row["width"], row["height"], row["candidate"].upper())
        print("| %s | %s | %s | %s | %s | %d B | %s |" % (
            row["material"], gc, ps2, cur, candidate,
            row["candidate_bytes"], row["reason"]), file=out)
    print(file=out)
    print("Totals: GameCube at 16 bpp %d B, current package %d B, "
          "candidates %d B (%.1f%% of current)." % (
              gc_total, current_total, candidate_total,
              100.0 * candidate_total / current_total if current_total else 0.0),
          file=out)
    print("Palette entries required %d of %d available; %s." % (
        budget["entries_required"], budget["entries_available"],
        "fits" if budget["fits"] else "DOES NOT FIT, revisit the PAL decisions"),
        file=out)


def emit_table(rows, package, budget, out) -> None:
    header = ("%-20s %-16s %-18s %-10s %10s %10s %10s %8s  %s" % (
        "material", "gc", "current", "candidate", "current B",
        "cand B", "gc vq B", "colours", "reason"))
    print(header, file=out)
    print("-" * len(header), file=out)
    for row in rows:
        print("%-20s %-16s %-18s %-10s %10d %10d %10d %8d  %s" % (
            row["material"],
            "%dx%d %s" % (row["gc_width"], row["gc_height"], row["gc_format"]),
            "%dx%d %s" % (row["width"], row["height"], row["current_format"]),
            row["candidate"],
            row["current_bytes"], row["candidate_bytes"], row["gc_vq_bytes"],
            row["distinct_rgba"], row["reason"]), file=out)
    current_total = sum(row["current_bytes"] for row in rows)
    candidate_total = sum(row["candidate_bytes"] for row in rows)
    gc_vq_total = sum(row["gc_vq_bytes"] for row in rows)
    gc_total = sum(row["gc_16bpp_bytes"] for row in rows)
    reduced = [row for row in rows if row["was_reduced"]]
    print(file=out)
    print("materials                     %d" % len(rows), file=out)
    print("reduced by the build          %d" % len(reduced), file=out)
    print("GameCube size at 16 bpp       %10d B" % gc_total, file=out)
    print("current package textures      %10d B" % current_total, file=out)
    print("all candidates                %10d B" % candidate_total, file=out)
    print("every texture at GC size, VQ  %10d B  (floor for residency"
          " planning; costs quality on textures that were not reduced)"
          % gc_vq_total, file=out)
    print("palette entries required      %d of %d (%s)" % (
        budget["entries_required"], budget["entries_available"],
        "fits" if budget["fits"] else "DOES NOT FIT"), file=out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tpl", type=pathlib.Path, required=True)
    parser.add_argument("--mtl", type=pathlib.Path, required=True)
    parser.add_argument("--package", type=pathlib.Path, required=True)
    parser.add_argument(
        "--max-dimension", type=int,
        help="the limit the build applied, used only to check the reduction")
    parser.add_argument(
        "--ps2-manifest", type=pathlib.Path,
        help="JSON mapping material name to the PS2 representation")
    parser.add_argument(
        "--spend-vq", action="store_true",
        help="also vector-quantise textures the build did not reduce, which "
             "trades measured picture quality for VRAM; use when a residency "
             "budget requires it, not by default")
    parser.add_argument(
        "--format", choices=("table", "markdown"), default="table")
    parser.add_argument("--json", type=pathlib.Path, help="write the full record")
    args = parser.parse_args(argv)

    ps2 = {}
    if args.ps2_manifest is not None:
        ps2 = json.loads(args.ps2_manifest.read_text(encoding="utf-8"))

    rows, package = build_rows(
        args.tpl, args.mtl, args.package, args.max_dimension, ps2,
        args.spend_vq)
    apply_palette_budget(rows)
    budget = palette_budget(rows)

    if args.format == "markdown":
        emit_markdown(rows, package, budget, sys.stdout)
    else:
        emit_table(rows, package, budget, sys.stdout)

    if args.json is not None:
        args.json.write_text(json.dumps({
            "package": args.package.name,
            "tpl": args.tpl.name,
            "mtl": args.mtl.name,
            "max_dimension": args.max_dimension,
            "ps2_source": (
                args.ps2_manifest.name if args.ps2_manifest else None),
            "palette_budget": budget,
            "materials": rows,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"asset residency report failed: {error}", file=sys.stderr)
        raise SystemExit(1)
