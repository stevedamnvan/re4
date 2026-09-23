#!/usr/bin/env python3
"""Package baked house shells (tools/blender/bl_house_shell.py) for game MESH_TEXTURES=1.

  house_shells.py <out dir> <shell dir>... [--owner 1] [--pvrtex PATH]

Each <shell dir> holds <OWNER>_<bin>.obj/.png/.json from bl_house_shell.py (e.g. FILE_01_17).
1. The baked image is encoded by KOS pvrtex as RGB565 full-codebook VQ (-f RGB565 -c: 2 KiB codebook
   + one byte per 2x2 block) and wrapped as a one-texture package (convert_tpl.package_existing_vq):
   <out>/tex/<crc>-<fnv>.re4tex, the key being (crc32, FNV-1a) of the payload.
2. The shell OBJ is copied to <out>/replace/<OWNER>_<bin>.obj for convert_room_bins.py
   --lod-substitute <out>/replace (whole-BIN replacement: the carrier part draws the shell, alpha parts
   keep their source faces, every other part draws nothing; collision never reads this geometry).
3. <out>/textures.json lists one record per shell (BIN, carrier part, size, key) for
   mesh_annotate.py --textures, plus each shell's metrics and VRAM bytes.
Previews of the encoded textures (as pvrtex decodes them) go to <out>/preview/<OWNER>_<bin>.png:
compare against those, not the lossless bake.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_tpl as tpl  # noqa: E402


def fnv1a(data):
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def carrier_part(obj_text):
    parts = {int(m.group(1)) for m in re.finditer(r"^usemtl p(\d+)_shell\b", obj_text, re.M)}
    if len(parts) != 1:
        raise ValueError("expected exactly one p<part>_shell material")
    return parts.pop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("shells", type=Path, nargs="+")
    ap.add_argument("--pvrtex", type=Path,
                    default=Path(os.environ.get("RE4DC_KOS_BASE", "/root/work/kos-re4dc-d367")) / "utils/pvrtex/pvrtex")
    a = ap.parse_args()
    for d in ("tex", "preview", "replace", "work"):
        (a.out / d).mkdir(parents=True, exist_ok=True)
    records = []
    for d in a.shells:
        for obj in sorted(d.glob("*.obj")):
            m = re.fullmatch(r"(MAINSCENARIO|COMMON|FILE_(\d+))_(\d+)", obj.stem)
            if not m:
                continue
            text = obj.read_text()
            part = carrier_part(text)
            work = a.out / "work" / (obj.stem + ".dt")
            subprocess.run([str(a.pvrtex), "-i", str(obj.with_suffix(".png")), "-o", str(work), "-f", "RGB565", "-c",
                            "--preview", str(a.out / "preview" / (obj.stem + ".png"))],
                           check=True, stdout=subprocess.DEVNULL)
            blob, info = tpl.package_existing_vq(work.read_bytes(), obj.stem + "_shell")
            payload_start = tpl.HEADER.size + tpl.TEXTURE.size
            payload = blob[payload_start:]
            key = (zlib.crc32(payload) & 0xFFFFFFFF, fnv1a(payload))
            (a.out / "tex" / ("%08x-%08x.re4tex" % key)).write_bytes(blob)
            shutil.copyfile(obj, a.out / "replace" / obj.name)
            metrics = json.loads(obj.with_suffix(".json").read_text())
            common = m.group(1) == "COMMON"
            owner = {"MAINSCENARIO": 0xFF, "COMMON": 0xFE}.get(m.group(1), int(m.group(2) or 0))
            records.append(dict(owner=owner, bin=int(m.group(3)), common=common, part=part,
                                key=["%08x" % key[0], "%08x" % key[1]], width=info["width"], height=info["height"],
                                vram_bytes=len(payload), metrics=metrics))
    manifest = dict(format="RGB565 VQ", vram_bytes=sum(r["vram_bytes"] for r in records), textures=records)
    (a.out / "textures.json").write_text(json.dumps(manifest, indent=1))
    shutil.rmtree(a.out / "work")
    print(json.dumps(dict(shells=len(records), vram_bytes=manifest["vram_bytes"])))


if __name__ == "__main__":
    main()
