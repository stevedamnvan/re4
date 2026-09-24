"""Event actors (evd files) for `assets.sh discover` (round 2).

A room script names its events as `evd/r<room>s<NN>.evd` (r100_evtName, r101's data units). An evd is
self-contained (event.h EvtHeader, le_mirror.fmt_evd): a packet stream whose model-set packets
(kind 3: actor name, model .bin, texture .tpl; kind 4: parts of an actor) name the actors, and an
asset table holding every model, texture, motion, effect and light the event uses. Event actors
therefore need no enemy REL or archive; what an event needs is its file:
  * a route movie (cutscenes movies dir, <name>/<name>.seq): the movie presents the event and the
    evd is never loaded (r101EventReserve / the route movie path);
  * otherwise the prepared evd plus its qualified `.evq` sidecar (native_event_file.cpp refuses
    an evd without one), and room for its size when it loads.
Names the script mentions that are not on the disc are listed and ignored (r100s01/s02/s42 are
table entries the game never reaches with a file).
"""
import re
import struct
from collections import Counter
from pathlib import Path

EVD_NAME = re.compile(r"evd/(r[0-9a-f]{3}s[0-9a-f]{2})\.evd")


def script_events(repo, room):
    p = Path(repo) / ("src/st%x/r%03x.cpp" % (room >> 8, room))
    if not p.exists():
        return []
    seen = []
    for n in EVD_NAME.findall(p.read_text(errors="replace").lower()):
        if n not in seen and n.startswith("r%03x" % room):
            seen.append(n)
    return seen


def parse(data):
    """Actors and asset bytes of a source (big-endian) evd."""
    def nm(o, n):
        return data[o:o + n].split(b"\0")[0].decode("ascii", "replace")
    if data[:5] != b"event":
        raise ValueError("not an evd")
    po, ps, count, bo = struct.unpack_from(">4I", data, 64)
    actors = []
    pos, end = po, po + ps
    while pos < end:
        kind = struct.unpack_from(">I", data, pos)[0]
        length = struct.unpack_from(">H", data, pos + 12)[0]
        if kind == 3:
            actors.append({"name": nm(pos + 16, 12), "model": nm(pos + 28, 48)})
        if kind == 27 or not length:
            break
        pos += length
    starts = sorted((struct.unpack_from(">I", data, bo + 64 * i + 48)[0], nm(bo + 64 * i, 48)) for i in range(count))
    by_type = Counter()
    for i, (s, name) in enumerate(starts):
        e = starts[i + 1][0] if i + 1 < len(starts) else len(data)
        by_type[name.rsplit(".", 1)[-1].upper()] += max(0, e - s)
    kinds = Counter()
    for a in actors:
        m = re.match(r"(em[0-9a-f]{2}|pl[0-9a-f]{2}|obm|ev)", a["name"])
        kinds[m.group(1) if m else a["name"]] += 1
    return {"actors": actors, "actor_groups": dict(sorted(kinds.items())), "assets": count,
            "asset_bytes": dict(sorted(by_type.items()))}


def events(repo, room, iso, prepared, movies):
    """One row per event the room script names."""
    rows, problems = [], []
    for name in script_events(repo, room):
        rel = "Evd/%s.evd" % name
        key = iso.find(rel) if iso else None
        r = {"event": name, "on_disc": key is not None}
        if key is None:
            rows.append(r)
            continue
        data = iso.read(rel)
        r["bytes"] = len(data)
        r.update(parse(data))
        r["movie"] = bool(movies) and (Path(movies) / name / (name + ".seq")).exists()
        pe = Path(prepared) / "evd" / (name + ".evd")
        r["prepared"] = pe.exists()
        r["qualified"] = (pe.parent / (pe.name + ".evq")).exists()
        if not r["movie"] and not (r["prepared"] and r["qualified"]):
            problems.append("event %s: no route movie and %s" % (
                name, "no prepared evd" if not r["prepared"] else "no qualified .evq sidecar"))
        rows.append(r)
    return rows, problems
