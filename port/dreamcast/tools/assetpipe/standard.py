"""Standard budgets and VRAM for `assets.sh discover` (round 2).

Standard's room assets load only with QUALITY_ASSETS=1 (010169c, not in the canonical recipe yet),
so measured runs so far use the Original packages. The Standard numbers come from the room's
Standard set index (stdindex.py, <assets_root>/out/standard/<room>/low/index.txt):
  * heap: the native static packages are heap 4 ("native static package" in the census);
    Standard's delta = sum(mesh) - sum(orig). The enemy heap-4 room in Standard is the measured
    (Original-package) room minus that delta.
  * VRAM: Standard adds the `tex` records' VRAM (impostor atlases, shell textures) and never draws
    the `drop` textures (their VRAM is not in the index: the estimate keeps them, an upper bound).
    Against [room.X.standard.budget_context] vram = {pool, original_used}.
From a run log: the lowest texture-pool free, rejects, and texture packages the room asked for that
are not on the disc ("package rejected: open failed").
"""
import re
from pathlib import Path

from . import stdindex


def std_set(root, room_name):
    p = Path(root) / "out/standard" / room_name / "low/index.txt"
    if not p.exists():
        return None
    ix = stdindex.parse(p.read_text())
    mesh = sum(int(r[1]) for r in ix["mesh"])
    orig = sum(int(r[1]) for r in ix["orig"])
    return {"index": str(p), "mesh_bytes": mesh, "orig_bytes": orig, "heap_delta": mesh - orig,
            "tex": len(ix["tex"]), "tex_vram": sum(int(r[3]) for r in ix["tex"]), "drops": len(ix["drop"])}


def budgets(std, enemy_budget, ctx):
    """Standard heap/VRAM figures and problems. ctx: [room.X.standard.budget_context] (may be {})."""
    out, problems = {}, []
    if std is None:
        return {"verdict": "no Standard set built for this room"}, problems
    out.update(std)
    if enemy_budget is not None:
        out["enemy_heap4_bytes"] = enemy_budget - std["heap_delta"]
    v = (ctx or {}).get("vram") or {}
    if v.get("pool") and v.get("original_used") is not None:
        used = v["original_used"] + std["tex_vram"]
        out["vram"] = {"pool": v["pool"], "original_used": v["original_used"], "standard_used_max": used,
                       "standard_free_min": v["pool"] - used, "source": v.get("source")}
        if used > v["pool"]:
            problems.append("VRAM: Standard needs up to %d of a %d pool (%d over; drops not counted)" % (
                used, v["pool"], used - v["pool"]))
    return out, problems


def vram_log(text):
    """Texture-pool facts from a run's log."""
    frees = [int(f) for f in re.findall(r"native UI VRAM: frame=\d+ budget=\d+ used=\d+ free=(\d+)", text)]
    used = [int(u) for u in re.findall(r"native UI VRAM: frame=\d+ budget=\d+ used=(\d+)", text)]
    rejects = [int(r) for r in re.findall(r"native UI VRAM: .* rejects=(\d+)", text)]
    missing = re.findall(r"native UI: load (\S+) [^\n]*\nnative UI: package rejected: open failed", text)
    out = {"min_free": min(f for f, u in zip(frees, used) if u) if any(used) else None,
           "max_used": max(used) if used else None, "rejects": max(rejects) if rejects else 0,
           "missing_textures": sorted(set(missing))}
    problems = []
    if out["missing_textures"]:
        problems.append("run: %d texture package(s) the room loads are not on the disc (open failed), e.g. %s" % (
            len(out["missing_textures"]), ", ".join(out["missing_textures"][:3])))
    if out["rejects"]:
        problems.append("run: %d texture upload(s) rejected for VRAM" % out["rejects"])
    return out, problems
