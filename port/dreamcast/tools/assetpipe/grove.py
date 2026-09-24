"""Per-tree impostors for split groves (docs/D367_ASSET_PIPELINE.md s16.5).

A grove BIN (several trees in one mesh) is converted with --lod-cluster-trees, so each tree's
clusters are contiguous in its part and no cluster spans two trees. This bakes one atlas per
tree from those clusters' finest level, exactly as impostor.py bakes a whole BIN (same
renderer, frame, cell layout and kPal4 package), and writes impostors.json with one record per
tree: the item 20 fields plus part (index among the mesh's parts), first / count (the tree's
clusters within that part) and tree (index in the grove).
"""
import json
import shutil

from . import impostor, texture
from .rooms import placement_matrix
from .scene import SceneBuilder

FLAT = impostor.FLAT


def grove_tris(pk, owner, code, b, common, part, first, count, textures, cost):
    """Model-space textured triangles of one tree (clusters [first, first + count) of the
    mesh's part `part`, finest level) and its mean vertex colour."""
    w = dict(owner=owner, code=code, bin=b, common=common, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0),
             scale=(1.0, 1.0, 1.0))
    sb = SceneBuilder({owner: pk}, [w], {owner: code}, cost, textures)
    mk = pk.mesh_by_bin()[(b, bool(common))]
    M = placement_matrix(w)
    p = pk.meshes[mk][6] + part
    pp = pk.parts[p]
    tex, atex = textures.lookup(code, b, part, pp[2], pp[3], pp[4])
    tris, csum, n = [], [0.0, 0.0, 0.0], 0
    for cl in pk.part_levels(p)[first:first + count]:
        for let in cl["levels"][0][1]:
            for (p0, t0, c0), (p1, t1, c1), (p2, t2, c2) in sb._meshlet_tris(pk, mk, p, let):
                tris.append((sb._xf(M, p0), sb._xf(M, p1), sb._xf(M, p2), t0, t1, t2, FLAT, FLAT, FLAT, tex, atex))
                for c in (c0, c1, c2):
                    for j in range(3):
                        csum[j] += c[j]
                n += 3
    return tris, [int(round(x / max(1, n))) for x in csum]


_JOBS = None


def _bake(i):
    jobs, views, cell, ss = _JOBS
    pk, owner, code, b, common, part, k, first, count, textures, cost = jobs[i]
    tris, rgb = grove_tris(pk, owner, code, b, common, part, first, count, textures, cost)
    img, info = impostor.bake(tris, views, cell, ss)
    return texture.png_rgba_bytes(img), info, rgb


def write_trees(out, jobs, pvrtex, views, cell, ss, workers=1):
    """jobs: [(pk, owner, code, bin, common, part, tree, first, count, textures, cost)] ->
    impostors.json + tex/, preview/, atlas/ in out."""
    global _JOBS
    for d in ("tex", "preview", "atlas", "work"):
        (out / d).mkdir(parents=True, exist_ok=True)
    _JOBS = (jobs, views, cell, ss)
    try:
        if workers > 1 and len(jobs) > 1:
            import multiprocessing
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(min(workers, len(jobs)), mp_context=multiprocessing.get_context("fork")) as ex:
                baked = list(ex.map(_bake, range(len(jobs))))
        else:
            baked = [_bake(i) for i in range(len(jobs))]
    finally:
        _JOBS = None
    atlases, records = {}, []
    for (pk, owner, code, b, common, part, k, first, count, _, _), (png, info, rgb) in zip(jobs, baked):
        name = "%d_p%d_t%d" % (b, part, k)
        a = out / "atlas" / (name + ".png")
        a.write_bytes(png)
        blob, key, meta = impostor.package(a, out / "work" / name, pvrtex, "impostor_" + name,
                                           out / "preview" / (name + ".png"))
        pname = "%08x-%08x.re4tex" % key
        (out / "tex" / pname).write_bytes(blob)
        atlases[name] = dict(meta, key=["%08x" % key[0], "%08x" % key[1]], package=pname, cell=info["cell"],
                             cols=info["cols"], atlas=info["atlas"])
        records.append(dict(owner="0x%02x" % code if code >= 0xF0 else str(code), code=code, bin=b,
                            common=bool(common), part=part, tree=k, first=first, count=count, atlas_name=name,
                            key=atlases[name]["key"], views=views, cols=info["cols"], cell=info["cell"],
                            atlas=info["atlas"], centre=[round(x, 3) for x in info["centre"]],
                            half_w=round(info["half_w"], 3), half_h=round(info["half_h"], 3), rgb=rgb))
    shutil.rmtree(out / "work")
    man = dict(views=views, cell_h=cell, light="flat", supersample=ss, alpha_cut=0.5, renderer="assetpipe.render",
               vram_bytes=sum(v["vram_bytes"] for v in atlases.values()), atlases=atlases, records=records)
    (out / "impostors.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    return dict(records=len(records), vram_bytes=man["vram_bytes"])
