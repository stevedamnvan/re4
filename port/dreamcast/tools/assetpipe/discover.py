"""Room demand discovery (`assets.sh discover <room>`): what a room can load, and whether the
build and the prepared disc provide it. Static: the source game data plus the port's own source
tables, no emulator. `--log run-output.txt` compares one run against the prediction.

Sources, in the order the game uses them:
  * the enemy list (etc/emleonNN.esl) chosen by stage.cpp checkEmListNo for the room; every entry
    of the room is a possible spawn. Entries with the alive bit set in the file spawn at entry;
    entries without it spawn only after a room script or story state enables them (em2a in r100).
  * the room script (src/st<N>/r<room>.cpp): EmSetFromList2(<entry>) spawns, EmReadSearch /
    SearchEmModule(<id>) direct archive loads (event reservations, shared Ganado data).
  * enemy id -> read.cpp EmFileTbl[id] (Leon's table) -> dvd.cpp FileTbl names: the archive
    (em/emXX.das, prepared as .drs when the entry has a DLL) and the REL (rel/emXX.rel).
  * the prepared archive header: u32 LE at 0x24 is the heap-4 allocation readEmData makes
    (matches "DVD: Mem Alloc" in run logs).
Checks: the REL is linked (Makefile MODULES, platform/modules.cpp MODULE(id, name) with the
rel.json module_id, the ENEMY_DEMAND audit list), no missing-symbol stub names it, the prepared
archive exists, at most 4 enemy archives are live (read.cpp EmReadModule[4]), and the enemy
archives fit the room's measured heap-4 room for them (rooms.toml [room.X.demand]).
"""
import json
import re
import struct
from pathlib import Path

from .util import write_json

ESL_REC = struct.Struct(">BBBBIHBB3h3hHh4x")   # include/em_set.h EmListData (big-endian source)
EM_SLOTS = 4                                     # read.cpp EmReadModule[4]
ESL_FILES = ["etc/emleon0%d.esl" % i for i in range(8)] + ["etc/omake0%d.esl" % i for i in range(3)]


def _num(s):
    return int(s, 0)


class Tables:
    """The port's source tables (read from the checkout, never copied)."""

    def __init__(self, repo):
        self.repo = Path(repo)
        s = (self.repo / "src/game/dvd.cpp").read_text()
        b = s[s.index("FileTblEntry FileTbl[] = {"):]
        self.files = re.findall(r'\{"([^"]*)",\s*0\}', b[:b.index("};")])
        r = (self.repo / "src/game/read.cpp").read_text()
        t = r[r.index("ReadFile EmFileTbl[64] = {"):]
        self.em = [tuple(int(x, 16) if i < 2 else int(x) for i, x in enumerate(m)) for m in re.findall(
            r"\{\s*0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*(\d)\s*\}", t[:t.index("};")])]
        assert len(self.em) == 64, len(self.em)

    def enemy(self, eid):
        """{archive, rel, module} for enemy id, or None when the id has no file (objects, doors)."""
        if eid >= len(self.em) or self.em[eid][0] == 0:
            return None
        f, rel, dll = self.em[eid]
        arc = self.files[f]
        if dll:
            arc = arc.rsplit(".", 1)[0] + ".drs"
        out = {"archive": arc}
        if dll:
            out["rel"] = self.files[rel]
            out["module"] = Path(self.files[rel]).stem
        return out


def esl_list_numbers(room):
    """stage.cpp checkEmListNo, stage 1 (Leon's main game): [(list, condition)]."""
    stage = room >> 8
    if stage != 1:
        raise SystemExit("discover: stage %d list rules not mirrored yet (stage.cpp checkEmListNo)" % stage)
    if room == 0x120:
        return [(0, "always")]
    if room == 0x10E:
        return [(1, "System_flg & 0x2000"), (None, "else: keeps the current list")]
    return [(1 if room > 0x10B else 0, "always")]


def esl_entries(path, room):
    data = Path(path).read_bytes()
    out = []
    for no in range(len(data) // 0x20):
        be, eid, typ, st, flag, hp, _, ch, px, py, pz, rx, ry, rz, rm, guard = ESL_REC.unpack_from(data, no * 0x20)
        if eid and rm == room:
            out.append({"no": no, "id": eid, "type": typ, "set": st, "flag": "%08x" % flag,
                        "alive": bool(be & 1), "pos_mm": [px * 10, py * 10, pz * 10]})
    return out


def script_refs(repo, room):
    p = Path(repo) / ("src/st%x/r%03x.cpp" % (room >> 8, room))
    if not p.exists():
        return {"file": None, "list_spawns": [], "loads": []}
    s = p.read_text()
    spawns = sorted({_num(m) for m in re.findall(r"EmSetFromList2\(\s*(0x[0-9a-fA-F]+|\d+)", s)})
    loads = sorted({_num(m) for m in re.findall(r"(?:EmReadSearch|SearchEmModule)\(\s*(0x[0-9a-fA-F]+|\d+)", s)})
    return {"file": str(p.relative_to(repo)), "list_spawns": spawns, "loads": loads}


def build_state(repo, obj=None):
    dc = Path(repo) / "port/dreamcast/game"
    mk = (dc / "Makefile").read_text()
    modules = re.search(r"^MODULES = (.*)$", mk, re.M).group(1).split()
    m = re.search(r"ifeq \(\$\(ENEMY_DEMAND\),1\)\s*\nifneq \(\$\(filter-out ([^,]*),\$\(MODULES\)\)", mk)
    audited = m.group(1).split() if m else []
    table = {name: int(i) for i, name in re.findall(r"MODULE\((\d+),\s*(\w+)\)", (dc / "platform/modules.cpp").read_text())}
    miss = Path(obj) / "missing.txt" if obj else dc / "obj/missing.txt"
    missing = miss.read_text().split() if miss.exists() else None
    return {"modules": modules, "audited": audited, "table": table, "missing": missing, "missing_file": str(miss)}


def rel_id(repo, module):
    p = Path(repo) / "config/G4BE08/modules" / module / "rel.json"
    return json.loads(p.read_text()).get("module_id") if p.exists() else None


def heap4_bytes(prepared_dir, archive):
    p = Path(prepared_dir) / archive
    if not p.exists():
        return None
    h = p.read_bytes()[:0x28]
    return struct.unpack_from("<I", h, 0x24)[0] if len(h) >= 0x28 else None


def discover(cfg, room_name, repo=None, obj=None, log=None, out_dir=None):
    repo = Path(repo or cfg.path("checkout") or Path(__file__).resolve().parents[4])
    room = int(room_name.lstrip("r"), 16)
    game = cfg.path("game_data")
    prepared = cfg.path("prepared_mirror")
    tab = Tables(repo)
    lists = esl_list_numbers(room)
    entries = []
    for no, cond in lists:
        if no is None:
            continue
        for e in esl_entries(game / ESL_FILES[no], room):
            e["list"] = ESL_FILES[no]
            e["list_condition"] = cond
            entries.append(e)
    sc = script_refs(repo, room)
    by_no = {e["no"]: e for e in entries}
    need = {}   # enemy id -> {reasons}

    def add(eid, why):
        need.setdefault(eid, set()).add(why)
    for e in entries:
        add(e["id"], "entry" if e["alive"] else "enabled-later")
    for no in sc["list_spawns"]:
        if no in by_no:
            add(by_no[no]["id"], "script-spawn")
    for eid in sc["loads"]:
        add(eid, "script-load")
    bs = build_state(repo, obj)
    rcfg = cfg.room(room_name).get("demand", {})
    rows, problems = [], []
    for eid in sorted(need):
        info = tab.enemy(eid) or {}
        r = {"id": "0x%02x" % eid, "reasons": sorted(need[eid]),
             "entries": [e["no"] for e in entries if e["id"] == eid], **info}
        if "archive" in info:
            r["heap4_bytes"] = heap4_bytes(prepared, info["archive"])
            if r["heap4_bytes"] is None:
                problems.append("%s: prepared archive %s missing in %s" % (r["id"], info["archive"], prepared))
        mod = info.get("module")
        if mod:
            rid = rel_id(repo, mod)
            r["module_id"] = rid
            chk = {"makefile": mod in bs["modules"], "audit": mod in bs["audited"],
                   "table": bs["table"].get(mod) == rid and rid is not None}
            if bs["missing"] is not None:
                key = mod.lower()
                chk["stubs"] = [s for s in bs["missing"] if key in s.lower()]
            r["build"] = chk
            for k in ("makefile", "audit", "table"):
                if not chk[k]:
                    problems.append("%s %s: not in %s%s" % (r["id"], mod, {"makefile": "Makefile MODULES",
                                    "audit": "the ENEMY_DEMAND audit list", "table": "platform/modules.cpp MODULE(%s, %s)" % (rid, mod)}[k],
                                    "" if k != "table" else " (rel.json module_id %s)" % rid))
            if chk.get("stubs"):
                problems.append("%s %s: missing-symbol stubs %s" % (r["id"], mod, ", ".join(chk["stubs"])))
        rows.append(r)
    arcs = [r for r in rows if r.get("archive")]
    total = sum(r.get("heap4_bytes") or 0 for r in arcs)
    budget = rcfg.get("enemy_heap4_bytes")
    heap = {"enemy_archives": len(arcs), "slots": EM_SLOTS, "worst_case_bytes": total,
            "budget_bytes": budget, "budget_source": rcfg.get("enemy_heap4_source")}
    if len(arcs) > EM_SLOTS:
        problems.append("%d enemy archives can be live, read.cpp has %d slots" % (len(arcs), EM_SLOTS))
    if budget is None:
        heap["verdict"] = "no budget: measure one run (--log) and record [room.%s.demand]" % room_name
    elif total > budget:
        heap["verdict"] = "SHORT by %d bytes when every archive is live" % (total - budget)
        problems.append("heap 4: enemy archives %d > measured room %d (short %d)" % (total, budget, total - budget))
    else:
        heap["verdict"] = "fits (%d spare)" % (budget - total)
    res = {"room": room_name, "lists": [{"list": ESL_FILES[n] if n is not None else None, "condition": c} for n, c in lists],
           "script": sc, "entries": entries, "demand": rows, "heap4": heap, "problems": problems,
           "inputs": {"repo": str(repo), "game_data": str(game), "prepared": str(prepared), "missing": bs["missing_file"]}}
    if log:
        res["run"] = compare_log(log, rows)
        problems.extend(res["run"]["problems"])
    if out_dir:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        write_json(Path(out_dir) / ("%s.json" % room_name), res)
    return res


def compare_log(path, rows):
    t = Path(path).read_text(errors="replace")
    loaded = re.findall(r"DVD: Read File: (em/em[0-9a-f]{2}\.drs)", t)
    failed = re.findall(r"readEmData\(\): error! (em/\S+)", t)
    shortfalls = [(int(a, 16), int(f, 16)) for a, f in re.findall(r"alloc\[([0-9a-f]+)\]:free\[([0-9a-f]+)\]", t)]
    linked = re.findall(r"module: id (\d+) -> (\w+)", t)
    halts = re.findall(r"HALT [^\n]*", t)
    predicted = {r["archive"] for r in rows if r.get("archive")}
    out = {"loaded": sorted(set(loaded)), "failed": sorted(set(failed)), "linked": sorted({m for _, m in linked}),
           "halts": halts[:5], "problems": []}
    extra = sorted(set(loaded) - predicted)
    if extra:
        out["problems"].append("run loaded archives the discovery did not predict: %s" % ", ".join(extra))
    for f in sorted(set(failed)):
        out["problems"].append("run: %s failed to load" % f)
    if shortfalls:
        a, f = shortfalls[0]
        out["shortfall"] = {"alloc": a, "free": f, "short": a - f}
    for h in halts[:2]:
        out["problems"].append("run: %s" % h)
    return out


def report(res):
    print("== %s: lists %s; script %s" % (res["room"], ", ".join("%s (%s)" % (l["list"], l["condition"]) for l in res["lists"]),
                                           res["script"]["file"]))
    for r in res["demand"]:
        b = r.get("build", {})
        print("  %s %-12s %-9s heap4 %8s  %s%s" % (
            r["id"], r.get("archive", "(no file)"), r.get("module", "-"),
            r.get("heap4_bytes", "-"), ",".join(r["reasons"]),
            ("  build " + " ".join("%s=%s" % (k, "ok" if v is True else ("NO" if v is False else (v or "none")))
                                   for k, v in b.items())) if b else ""))
    h = res["heap4"]
    print("  heap 4: %d enemy archives (slots %d), worst case %d bytes, budget %s: %s" % (
        h["enemy_archives"], h["slots"], h["worst_case_bytes"], h["budget_bytes"], h["verdict"]))
    if "run" in res:
        run = res["run"]
        print("  run: loaded %s; failed %s; linked %s%s" % (", ".join(run["loaded"]) or "-", ", ".join(run["failed"]) or "-",
                                                         ", ".join(run["linked"]),
                                                         ("; shortfall %s" % run["shortfall"]) if "shortfall" in run else ""))
    for p in res["problems"]:
        print("  PROBLEM " + p)
    if not res["problems"]:
        print("  ok")
