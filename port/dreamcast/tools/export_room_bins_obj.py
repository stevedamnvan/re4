#!/usr/bin/env python3
"""Export r100 scenery BINs as model-space OBJ in the replacement format of
convert_room_bins.py (--lod-substitute DIR): DIR/<OWNER>_<bin>.obj.

  export_room_bins_obj.py <out dir> [--export DIR] [--keys COMMON_0,FILE_01_17,...]

Positions are welded by exact coordinate (Blender and other editors see the
connectivity); vt are the source UVs as parse_bin decodes them (GX convention,
v = 0 is image row 0, no flip); vn the source normals. Each source part is one
group "part_<n>" with material "p<n>_t<texture>_a<alpha>_f<flags>", the name
the converter uses to put replacement faces back into that part. Converting
an unedited export as a replacement reproduces the source triangles.

--export defaults to $RE4DC_R100_EXPORT, else the checkout's private
orig/G4BE08/rooms/r100/stream/r100_full_export (never committed).
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_room_bins as crb  # noqa: E402
import mesh_lod  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT = Path(os.environ.get("RE4DC_R100_EXPORT",
                                     ROOT / "orig/G4BE08/rooms/r100/stream/r100_full_export"))
# Replacement owner name -> BIN directory of the r100 export.
DIRS = {"MAINSCENARIO": "R100.FILE_MAIN", "COMMON": "R100.FILE_SHARED"}
DIRS.update({"FILE_%02d" % n: "R100.FILE_%d" % n for n in range(5)})


def all_bins(export):
    """-> [(key "<OWNER>_<bin>", BIN path)] for every scenery BIN of the export."""
    out = []
    for owner, d in DIRS.items():
        for p in sorted((Path(export) / d).glob("*.BIN")):
            out.append(("%s_%d" % (owner, int(p.stem)), p))
    return out


def export_bin(path, out):
    """One BIN -> OBJ; returns the triangle count."""
    src = crb.parse_bin(Path(path).read_bytes())
    ids, welded = mesh_lod.weld(src["positions"])
    lines = ["# r100 BIN model space (%s); parts=%d" % (Path(path).name, len(src["parts"]))]
    for k in sorted(welded):
        lines.append("v %.6f %.6f %.6f" % welded[k])
    uvi, nvi = {}, {}
    faces_by_part = []
    for pi, part in enumerate(src["parts"]):
        tris = [t for s in part["strips"] for t in crb.strip_triangles(s)] + [tuple(t) for t in part["loose"]]
        fl = []
        for t in tris:
            if len({ids[k[0]] for k in t}) < 3:
                continue
            corner = []
            for k in t:
                uv, n = src["uv"](k[2]), src["normal"](k[3])
                uvi.setdefault(uv, len(uvi))
                nvi.setdefault(n, len(nvi))
                corner.append((ids[k[0]] + 1, uvi[uv] + 1, nvi[n] + 1))
            fl.append(corner)
        faces_by_part.append((pi, part, fl))
    lines += ["vt %.6f %.6f" % uv for uv in uvi]
    lines += ["vn %.6f %.6f %.6f" % n for n in nvi]
    for pi, part, fl in faces_by_part:
        lines.append("g part_%d" % pi)
        lines.append("usemtl p%d_t%d_a%d_f%d" % (pi, part["texture"], part["alpha"], part["flags"]))
        lines += ["f " + " ".join("%d/%d/%d" % c for c in corner) for corner in fl]
    Path(out).write_text("\n".join(lines) + "\n")
    return sum(len(fl) for _, _, fl in faces_by_part)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT, help="r100_full_export directory")
    ap.add_argument("--keys", help="comma list of <OWNER>_<bin> to export (default: all)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    keys = set(a.keys.split(",")) if a.keys else None
    total = 0
    for key, path in all_bins(a.export):
        if keys is None or key in keys:
            total += export_bin(path, a.out / (key + ".obj"))
    print("exported triangles", total)


if __name__ == "__main__":
    main()
