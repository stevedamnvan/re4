#!/usr/bin/env python3
"""Replace source UI images with edited PNGs, encoded exactly as the originals are.

ui_overrides.py --overrides <dir> --source <gc-tree> --textures <fixtures/tex>
                [--texdir <dir> ...] --output <dir> [--pvrtex PATH]

<dir> holds PNGs named by extract_ui_images.py, at the archive's relative path in the
source tree: <dir>/ss/eng/title_eff0_tpl31_tex00_CMPR_640x360.png replaces
ss/eng/title.dat (or .tpl), EFF entry 0, TPL 31, texture 0. The name's format and size
must match that source image and the PNG must have the same width and height, or this
fails. The runtime looks packages up by the source image identity
(prepare_native_ui.image_identity: CRC-32/FNV of the unmodified GC texels), so the disc
archive is not changed; only the package under that name is replaced.

Encoding follows the package the stage would otherwise use: the last --texdir holding
<key>.re4tex (stage.sh TEXDIRS order), else --textures. A directory whose
vq-native-ui-report.json lists the key is a VQ overlay: the override is built as the
16-bit package (convert_tpl.build_package, as prepare_native_ui.py) and then VQ-encoded
(vq_native_ui.encode, pinned pvrtex). Otherwise the 16-bit package is used. Before any
override is encoded, the original image is re-encoded through the same path and must
reproduce the staged package byte for byte; a mismatch (unknown provenance, or a
non-deterministic encoder) stops. Writes <output>/<key>.re4tex and
ui-overrides-report.json (override sha256, source mapping, package sha256).

Private inputs and outputs: override images are derived game art; never commit them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import convert_tpl as tpl  # noqa: E402
import extract_ui_images as xui  # noqa: E402
import vq_native_ui as vq  # noqa: E402
from prepare_native_ui import image_identity  # noqa: E402

NAME = re.compile(r"(?P<stem>.+)_(?P<tag>[a-z0-9]{3})(?P<entry>\d+)_tpl(?P<tpl>\d{2,})_tex(?P<tex>\d{2,})"
                  r"_(?P<fmt>[A-Z0-9]+)_(?P<w>\d+)x(?P<h>\d+)\.png")


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def locate(source: pathlib.Path, rel: pathlib.Path, match):
    """The TplImage an override name addresses, with its archive path and TPL offset."""
    stem = match["stem"]
    archives = [p for p in (source / rel / (stem + ".dat"), source / rel / (stem + ".tpl")) if p.is_file()]
    if len(archives) != 1:
        raise SystemExit("ui_overrides: %s: expected one of %s/%s.dat|.tpl in %s, found %d" % (
            match.string, rel.as_posix(), stem, source, len(archives)))
    archive = archives[0]
    want = (match["tag"], int(match["entry"]), int(match["tpl"]), int(match["tex"]))
    for tag, ei, start, pos, k, j, im in xui.iter_images(archive.read_bytes()):
        if (tag, ei, k, j) == want:
            if xui.image_name(stem, tag, ei, k, j, im) != match.string:
                raise SystemExit("ui_overrides: %s: source image is %s %dx%d" % (
                    match.string, xui.NAMES[im.format], im.width, im.height))
            return archive, start, pos, im
    raise SystemExit("ui_overrides: %s: no such image in %s" % (match.string, archive))


def package_16(im, pixels=None) -> bytes:
    # prepare_native_ui.prepare(): the arguments that built the fixture packages.
    package, _ = tpl.build_package([im], [tpl.MaterialBinding("source", 0, None)], twiddle=True,
                                   pad_to_power_of_two=True, source_intensity_alpha=True,
                                   source_pixels=None if pixels is None else {0: pixels})
    return package


def vq_listed(directory: pathlib.Path, key: str) -> bool:
    report = directory / "vq-native-ui-report.json"
    return report.is_file() and any(e["key"] == key for e in json.loads(report.read_text())["images"])


def encode(key, im, pixels, vq_dir, pvrtex, scratch):
    """(package, psnr_db or None) for the given pixels through the 16-bit or VQ path."""
    package = package_16(im, pixels)
    if vq_dir is None:
        return package, None
    work = pathlib.Path(tempfile.mkdtemp(dir=scratch))
    (work / "in").mkdir(); (work / "out").mkdir()
    (work / "in" / (key + ".re4tex")).write_bytes(package)
    entry = vq.encode(key, work / "in", work / "out", pvrtex, (im.width, im.height), work)
    return (work / "out" / (key + ".re4tex")).read_bytes(), entry["psnr_db"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--overrides", type=pathlib.Path, required=True)
    ap.add_argument("--source", type=pathlib.Path, required=True, help="GameCube source tree (big-endian)")
    ap.add_argument("--textures", type=pathlib.Path, required=True, help="base native packages (fixtures/tex)")
    ap.add_argument("--texdir", type=pathlib.Path, action="append", default=[], help="stage TEXDIRS, in order")
    ap.add_argument("--output", type=pathlib.Path, required=True)
    ap.add_argument("--pvrtex", default=vq.PVRTEX)
    a = ap.parse_args(argv)
    from PIL import Image
    pngs = sorted(p for p in a.overrides.rglob("*") if p.is_file() and p.suffix.lower() == ".png")
    if not pngs:
        raise SystemExit("ui_overrides: no PNG under %s" % a.overrides)
    a.output.mkdir(parents=True, exist_ok=False)
    report, keys = [], {}
    with tempfile.TemporaryDirectory() as scratch:
        for png in pngs:
            rel = png.relative_to(a.overrides)
            match = NAME.fullmatch(png.name)
            if not match:
                raise SystemExit("ui_overrides: %s: not an extract_ui_images.py name" % rel)
            archive, entry_off, tpl_off, im = locate(a.source, rel.parent, match)
            key, _ = image_identity(im)
            if key in keys:
                raise SystemExit("ui_overrides: %s and %s replace the same image %s" % (keys[key], rel, key))
            keys[key] = rel
            base = a.textures / (key + ".re4tex")
            if not base.is_file():
                raise SystemExit("ui_overrides: %s: %s has no native package (never loaded by the runtime)" % (rel, key))
            staged_dir = a.textures
            for d in a.texdir:
                if (d / (key + ".re4tex")).is_file():
                    staged_dir = d
            staged = (staged_dir / (key + ".re4tex")).read_bytes()
            vq_dir = staged_dir if vq_listed(staged_dir, key) else None
            if package_16(im) != base.read_bytes():
                raise SystemExit("ui_overrides: %s: rebuilding %s does not reproduce %s" % (rel, key, base))
            original, _ = encode(key, im, None, vq_dir, a.pvrtex, scratch)
            if original != staged:
                raise SystemExit("ui_overrides: %s: re-encoding the original does not reproduce %s/%s.re4tex" % (
                    rel, staged_dir, key))
            blob = png.read_bytes()
            image = Image.open(png)
            if image.size != (im.width, im.height):
                raise SystemExit("ui_overrides: %s is %dx%d; the source image is %dx%d" % (
                    rel, image.size[0], image.size[1], im.width, im.height))
            pixels = list(image.convert("RGBA").getdata())
            package, quality = encode(key, im, pixels, vq_dir, a.pvrtex, scratch)
            (a.output / (key + ".re4tex")).write_bytes(package)
            report.append(dict(
                override=rel.as_posix(), override_sha256=sha256(blob), key=key,
                archive=archive.relative_to(a.source).as_posix(), entry_offset=entry_off, tpl_offset=tpl_off,
                tag=match["tag"], entry=int(match["entry"]), tpl=int(match["tpl"]), tex=int(match["tex"]),
                source_format=xui.NAMES[im.format], width=im.width, height=im.height,
                encoding="vq" if vq_dir else "16bit", encoding_dir=str(staged_dir),
                original_package_sha256=sha256(staged), package_sha256=sha256(package),
                package_bytes=len(package), psnr_db_vs_16bit=quality))
            print("ui override %s -> %s.re4tex (%s, %s) sha256 %s" % (
                rel, key, "vq" if vq_dir else "16bit", staged_dir, sha256(blob)[:16]))
    (a.output / "ui-overrides-report.json").write_text(json.dumps(dict(overrides=report), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
