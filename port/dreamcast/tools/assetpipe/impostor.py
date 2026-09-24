"""Tree impostor atlases for any room, rendered by the pipeline's own rasteriser.

Item 20 bakes the r100 PS2 trees in Blender (bl_impostor_bake.py: one bark image, COMMON_<b>
names); r100 keeps that pinned output. For the other rooms this step renders every tree BIN of
the recipe package the same way, with the room's own textures (GC trees with alpha-masked
leaves as well as PS2 replacements), in pure Python, so it is deterministic by construction:

- geometry: the package's finest level of every part of the BIN, in model space;
- per view k (a = 360k/views, around the vertical axis at elevation 0) a near-orthographic
  render from 1 km away (render.py, fog off), `ss` x `ss` supersampled, texture colour only
  (the runtime modulates the atlas by the mesh's mean lit vertex colour, recorded as `rgb`);
- frame, cell aspect, atlas layout and view direction exactly as bl_impostor_bake.py
  (back_k = (cos a, 0, -sin a) in model space; cells 1:2 when the frame is at most half as
  wide as tall; rows of at most 1024 texels; power-of-two sides; row 0 at the top);
- coverage-weighted box filter, alpha cut at 50 %, cut texels' colours dilated 4 texels;
- encoded by KOS pvrtex as 4bpp palettised full-codebook VQ and wrapped as a kPal4 texture
  package (item 20 tree_impostors.package_pal4, vendored), keyed (crc32, FNV-1a).

Output: tex/<crc>-<fnv>.re4tex, preview/<bin>.png (as pvrtex decodes it), atlas/<bin>.png and
impostors.json in the item 20 record format (plus `rgb`), one model per BIN.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

from .raster import View
from .render import render_scene
from .rooms import placement_matrix
from .scene import SceneBuilder, Textures
from . import texture

D_MM = 1.0e6          # camera distance (1 km: perspective error < 0.2 texel at 128 texel cells)
FLAT = (128, 128, 128)
GAIN = 255.0 / 128.0  # texel x 128 x GAIN / 255 = texel


def tree_tris(pk, owner, code, b, common, textures, cost):
    """Model-space textured triangles of the BIN's finest level, and its mean vertex colour."""
    w = dict(owner=owner, code=code, bin=b, common=common, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0),
             scale=(1.0, 1.0, 1.0))
    sb = SceneBuilder({owner: pk}, [w], {owner: code}, cost, textures)
    mk = pk.mesh_by_bin()[(b, bool(common))]
    M = placement_matrix(w)
    first = pk.meshes[mk][6]
    tris, csum, n = [], [0.0, 0.0, 0.0], 0
    for p in pk.mesh_parts(mk):
        part = pk.parts[p]
        tex, atex = textures.lookup(code, b, p - first, part[2], part[3], part[4])
        for cl in pk.part_levels(p):
            for let in cl["levels"][0][1]:
                for (p0, t0, c0), (p1, t1, c1), (p2, t2, c2) in sb._meshlet_tris(pk, mk, p, let):
                    tris.append((sb._xf(M, p0), sb._xf(M, p1), sb._xf(M, p2), t0, t1, t2, FLAT, FLAT, FLAT,
                                 tex, atex))
                    for c in (c0, c1, c2):
                        for j in range(3):
                            csum[j] += c[j]
                    n += 3
    rgb = [int(round(x / max(1, n))) for x in csum]
    return tris, rgb


def _pow2(n):
    p = 8
    while p < n:
        p *= 2
    return p


def frame_of(tris):
    xs = [P[0] for t in tris for P in t[:3]]
    ys = [P[1] for t in tris for P in t[:3]]
    zs = [P[2] for t in tris for P in t[:3]]
    ax, az = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    r = max(math.hypot(x - ax, z - az) for x, z in zip(xs, zs))
    return ax, az, min(ys), max(ys), r


def bake(tris, views=16, cell=128, ss=4):
    """-> (atlas Image RGBA, info dict) for model-space triangles."""
    ax, az, y0, y1, r = frame_of(tris)
    H, W = (y1 - y0) * 1.02, 2 * r * 1.02
    aspect = 0.5 if W <= 0.5 * H else 1.0
    fh = max(H, W / aspect)
    ch, cw = cell, int(cell * aspect)
    cols = min(views, 1024 // cw)
    rows = -(-views // cols)
    aw, ah = _pow2(cols * cw), _pow2(rows * ch)
    atlas = bytearray(aw * ah * 4)
    C = (ax, (y0 + y1) / 2, az)
    fovy = math.degrees(2 * math.atan((fh / 2) / D_MM))
    for k in range(views):
        a = 2 * math.pi * k / views
        back = (math.cos(a), 0.0, -math.sin(a))
        eye = tuple(C[i] + back[i] * D_MM for i in range(3))
        v = View(eye, C, cw * ss, ch * ss, fovy=fovy, znear=D_MM - 2 * fh)
        mask = bytearray(cw * ss * ch * ss)
        rgb, _ = render_scene(v, tris, fog=(1e12, 2e12), gain=GAIN, sky=(0, 0, 0), mask=mask, raw=True)
        W2 = cw * ss
        cov = [0.0] * (cw * ch)
        col = [(0.0, 0.0, 0.0)] * (cw * ch)
        for y in range(ch):
            for x in range(cw):
                s, acc = 0, [0, 0, 0]
                for dy in range(ss):
                    row = (y * ss + dy) * W2 + x * ss
                    for dx in range(ss):
                        i = row + dx
                        if mask[i]:
                            s += 1
                            acc[0] += rgb[3 * i]
                            acc[1] += rgb[3 * i + 1]
                            acc[2] += rgb[3 * i + 2]
                cov[y * cw + x] = s / (ss * ss)
                if s:
                    col[y * cw + x] = (acc[0] / s, acc[1] / s, acc[2] / s)
        keep = [c >= 0.5 for c in cov]
        col = _dilate(col, keep, cw, ch)
        oy, ox = (k // cols) * ch, (k % cols) * cw
        for y in range(ch):
            for x in range(cw):
                i = y * cw + x
                o = 4 * ((oy + y) * aw + ox + x)
                c = col[i]
                atlas[o:o + 4] = bytes((int(round(c[0])), int(round(c[1])), int(round(c[2])), 255 if keep[i] else 0))
    info = dict(cell_aspect=aspect, cell=[cw, ch], cols=cols, rows=rows, atlas=[aw, ah], frame_h=fh,
                centre=[ax, (y0 + y1) / 2, az], half_w=fh * aspect / 2, half_h=fh / 2)
    return texture.Image(aw, ah, atlas), info


def _dilate(col, keep, w, h, steps=4):
    col, m = list(col), list(keep)
    for _ in range(steps):
        grow = []
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if m[i]:
                    continue
                acc, n = [0.0, 0.0, 0.0], 0
                for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    yy, xx = (y + dy) % h, (x + dx) % w
                    j = yy * w + xx
                    if m[j]:
                        c = col[j]
                        acc[0] += c[0]
                        acc[1] += c[1]
                        acc[2] += c[2]
                        n += 1
                if n:
                    grow.append((i, (acc[0] / n, acc[1] / n, acc[2] / n)))
        for i, c in grow:
            col[i] = c
            m[i] = True
    return col


def package(png_path, work, pvrtex, name, preview):
    """pvrtex PAL4BPP VQ + item 20 package_pal4 -> (package bytes, key, meta)."""
    from .config import TOOLS
    from .generators import item_tool
    sys.path.insert(0, str(TOOLS))
    import importlib.util
    spec = importlib.util.spec_from_file_location("tree_impostors_vendored", item_tool("tree_impostors.py"))
    ti = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ti)
    dt = Path(str(work) + ".dt")
    subprocess.run([str(pvrtex), "-i", str(png_path), "-o", str(dt), "-f", "PAL4BPP", "-c", "--preview",
                    str(preview)], check=True, stdout=subprocess.DEVNULL)
    return ti.package_pal4(dt.read_bytes(), Path(str(dt) + ".pal").read_bytes(), name)


def write_room(out, jobs, pvrtex, views, cell, ss, workers=1):
    """jobs: [(pk, owner, code, bin, common, textures, cost)] -> impostors.json + files in out."""
    for d in ("tex", "preview", "atlas", "work"):
        (out / d).mkdir(parents=True, exist_ok=True)
    global _JOBS
    _JOBS = (jobs, views, cell, ss)
    try:
        if workers > 1 and len(jobs) > 1:
            import multiprocessing
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(min(workers, len(jobs)), mp_context=multiprocessing.get_context("fork")) as ex:
                baked = list(ex.map(_bake_job, range(len(jobs))))
        else:
            baked = [_bake_job(i) for i in range(len(jobs))]
    finally:
        _JOBS = None
    atlases, records = {}, []
    for (pk, owner, code, b, common, _, _), (png, info, rgb) in zip(jobs, baked):
        a = out / "atlas" / ("%d.png" % b)
        a.write_bytes(png)
        blob, key, meta = package(a, out / "work" / str(b), pvrtex, "impostor_%d" % b,
                                  out / "preview" / ("%d.png" % b))
        pname = "%08x-%08x.re4tex" % key
        (out / "tex" / pname).write_bytes(blob)
        atlases[str(b)] = dict(meta, key=["%08x" % key[0], "%08x" % key[1]], package=pname, cell=info["cell"],
                               cols=info["cols"], atlas=info["atlas"])
        records.append(dict(owner="0x%02x" % code if code >= 0xF0 else str(code), bin=b, common=bool(common),
                            model=b, key=atlases[str(b)]["key"], views=views, cols=info["cols"], cell=info["cell"],
                            atlas=info["atlas"], centre=[round(x, 3) for x in info["centre"]],
                            half_w=round(info["half_w"], 3), half_h=round(info["half_h"], 3), rgb=rgb))
    import shutil
    shutil.rmtree(out / "work")
    man = dict(views=views, cell_h=cell, light="flat", supersample=ss, alpha_cut=0.5, renderer="assetpipe.render",
               vram_bytes=sum(v["vram_bytes"] for v in atlases.values()), atlases=atlases, records=records)
    (out / "impostors.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    return dict(records=len(records), vram_bytes=man["vram_bytes"])


_JOBS = None


def _bake_job(i):
    jobs, views, cell, ss = _JOBS
    pk, owner, code, b, common, textures, cost = jobs[i]
    tris, rgb = tree_tris(pk, owner, code, b, common, textures, cost)
    img, info = bake(tris, views, cell, ss)
    return texture.png_rgba_bytes(img), info, rgb
