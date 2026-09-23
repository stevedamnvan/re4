"""Blender (-b --python): visual-loss metrics of substitute OBJs against the GC source BIN OBJs.

usage: blender -b --factory-startup --python bl_measure.py -- <src_dir> <out.json> <cand_dir>[,<cand_dir>...]
Metrics as bl_decimate.measure (model units = source mm; uv in texture repeats). The normal metric is
unreliable on coincident double-sided sheets (nearest face may be the back face) and is reported only.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl_decimate as bd  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:]
src_dir, out = Path(argv[0]), Path(argv[1])
rng = np.random.default_rng(11)
rep = {}
for cd in argv[2].split(','):
    cd = Path(cd)
    for p in sorted(cd.glob('*.obj')):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        s = bd.import_obj(src_dir / p.name)
        src = bd.tri_data(s)
        c = bd.import_obj(p)
        dst = bd.tri_data(c)
        m = bd.measure(src, dst, rng)
        m.update(src_tris=int(len(src[1])), tris=int(len(dst[1])))
        rep.setdefault(cd.name, {})[p.stem] = m
        print(cd.name, p.stem, m['src_tris'], '->', m['tris'], 'fwd', m['fwd_mean'], m['fwd_p90'], 'rev', m['rev_mean'], m['rev_p90'], m['rev_max'], 'uv', m['uv_mean'])
        sys.stdout.flush()
out.write_text(json.dumps(rep, indent=1))
