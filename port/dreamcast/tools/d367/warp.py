#!/usr/bin/env python3
"""D367 test warp rig: write /cd/dc/warp.txt for a DBG_WARP=1 test build (README "Warp rig").

    warp.py list
    warp.py <preset> [--door] [--dump] [-o <fixtures-dir>/warp.txt]
    warp.py --room 0x100 --pos X Y Z --dir 0x8000 [--rsf ROOM:BIT,BIT] [--scenario 0:HEX] ... -o F

Each preset is a start point on the opening route with the scenario state its event needs,
derived from the room scripts (src/st1/r100.cpp, r101.cpp) and noted per preset. --door adds
the preset's door-test actions (step forward / press A at the door). A warp start is not STRICT
against continued play: use it for iteration and bring-up, and normal runs for logic proofs.
"""
import argparse
import sys

# Room save flag bits (RsfSet(G_ROOM_ID, n)) of r100 (src/st1/r100.cpp):
#   0 area 6 reached (s03/s20 preloads)   1 areas 7/8 reached   3 s03 done (the look at the house)
#   4 ambush over (gate door normal)      10 s20 done (officers dead: after state, ambush set)
#   12 battle streams faded               13 room entry event done (s40 + radio call)
#   14 ravine event done                  15 house Ganado event done
R100_AFTER_S03_S20 = [0, 1, 3, 10, 13]
PRESETS = {
    # r100 fresh entry: R100Init runs r100_StartEvent (s40 movie, then the radio call) because
    # room flag 13 is clear; the event itself places Leon at the gate (-99685,-484,-1343).
    "r100-spawn": dict(room=0x100, notes="fresh r100 entry: s40 + radio call run (flag 13 clear)"),
    # After the radio call: flag 13 set (the re-entry path skips r100_StartEvent), Leon where
    # r100_StartEvent leaves him (pos/ang from the source), s40 marked done (Scenario[0] 0x10).
    "r100-post-radio": dict(room=0x100, pos=(-99685, -484, -1343), ang=2.246, rsf={0x100: [13]},
                             scenario={0: 0x10}, notes="after s40 + radio call, at the gate"),
    # Before s03: flags 3/10 clear (area 0xA armed with r100_Sce_look), 13 set. Leon on the path
    # before the house; --door steps him into area 0xA.
    "r100-house-door": dict(room=0x100, pos=(-82910, 860, -38480), ang=-0.1293, rsf={0x100: [13]}, scenario={0: 0x10},
                            door=[("fwd", 30, 150)], notes="just before s03 (area 0xA armed: flags 3/10 clear)"),
    # s44 (r100_EventBrige, area 0x1B, readEvent(8) = r100s44): only while flag 10 is clear.
    "r100-bridge": dict(room=0x100, pos=(-112251, -193, -4420), ang=-1.5172, rsf={0x100: [13]}, scenario={0: 0x10},
                        door=[("fwd", 30, 90)], notes="just before s44 (area 0x1B, flag 10 clear)"),
    # The r101 door with the after state (s03 + s20 done, ambush over): the gate door watcher
    # (r100_DoorCk) is normal once flags 3 and 4 are set.
    # The r100 -> r101 door (AEV area 0: DOOR -> r101, action button, no lock). Leon stands where
    # r101's door back to r100 puts him (r101 AEV no 0 dstPos/dstAngle), turned to face the door.
    # The door has no flag condition; the room is entered in the post-radio state.
    "r100-east-door": dict(room=0x100, pos=(96523, -6771, -8536), ang=2.247, rsf={0x100: [13]},
                           scenario={0: 0x10}, door=[("fwd", 30, 20), ("a", 60, 4), ("a", 150, 4), ("a", 240, 4)],
                           notes="at the r100 -> r101 door (door area 0 has no lock or flag)"),
    # The same door in the natural after state (s03 + s20 done, ambush over). BLOCKED: entering
    # r100 with flag 10 set spawns an ESL entry of em2a, whose module (id 28) is not in the image
    # (HALT main_sub.cpp(1440) "DLL link/unlink failed"; evidence warp-east-1).
    "r100-east-door-after": dict(room=0x100, pos=(96523, -6771, -8536), ang=2.247,
                                 rsf={0x100: R100_AFTER_S03_S20 + [4, 12, 14, 15]}, scenario={0: 0x10}, find=0x4000,
                                 door=[("fwd", 30, 20), ("a", 60, 4), ("a", 150, 4), ("a", 240, 4)],
                                 notes="r101 door, after state: BLOCKED (em2a module 28 not in the image)"),
    # r101 fresh entry (first visit: typewriter + Hunnigan call via r101_execOperator2).
    "r101-entry": dict(room=0x101, notes="fresh r101 entry (first visit, Item_find 0x2000 clear)"),
    # The square before the fight: first visit done (Item_find 0x2000: no typewriter call), fight
    # not started (flag 6 clear): r101_checkFindPlayer starts it when a Ganado finds Leon.
    # Leon at the square's examine point (AEV area 09), facing the square (area 0B). The bell
    # itself (s30) needs 15 kills or 11700 fight frames counted at run time (r101_checkEmNum):
    # not a flag state, so the preset stops at the fight start.
    "r101-bell-fight": dict(room=0x101, pos=(-7914, 0, -254), ang=2.96, find=0x2000,
                            notes="r101 square, fight about to start (flags 6/7 clear, first visit done)"),
}


def lines_for(p, door=False, dump=False, name=None):
    out = []
    if name:
        out.append("name %s" % name)
    out.append("# %s" % p.get("notes", ""))
    out.append("room 0x%03x" % p["room"])
    if p.get("pos"):
        out.append("pos %d %d %d" % tuple(p["pos"]))
    if p.get("ang") is not None:
        out.append("ang %.4f" % p["ang"])
    for room, bits in sorted((p.get("rsf") or {}).items()):
        out.append("rsf 0x%03x %s" % (room, " ".join(str(b) for b in bits)))
    for i, v in sorted((p.get("scenario") or {}).items()):
        if v:
            out.append("scenario %d 0x%08x" % (i, v))
    if p.get("find"):
        out.append("find 0x%08x" % p["find"])
    for i, v in sorted((p.get("unlock") or {}).items()):
        out.append("unlock %d 0x%08x" % (i, v))
    out.append("inv default")
    if door:
        for kind, frame, hold in p.get("door", []):
            out.append("act %d %s %d" % (frame, kind, hold))
    if dump:
        out.append("dump")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("preset", nargs="?")
    ap.add_argument("--door", action="store_true")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--room", type=lambda s: int(s, 0))
    ap.add_argument("--pos", type=float, nargs=3)
    ap.add_argument("--ang", type=float)
    ap.add_argument("--rsf", action="append", default=[], help="ROOM:BIT[,BIT...]")
    ap.add_argument("--scenario", action="append", default=[], help="0|1:HEX")
    ap.add_argument("--find", type=lambda s: int(s, 0))
    ap.add_argument("--act", action="append", default=[], help="KIND:FRAME:HOLD")
    ap.add_argument("-o", "--output")
    a = ap.parse_args(argv)
    if a.preset == "list":
        for k, p in PRESETS.items():
            print("%-18s %s" % (k, p.get("notes", "")))
        return 0
    if a.preset:
        if a.preset not in PRESETS:
            ap.error("unknown preset %s (warp.py list)" % a.preset)
        p = dict(PRESETS[a.preset])
        if p.get("pos", 0) is None:
            ap.error("preset %s has no verified position yet" % a.preset)
    elif a.room is not None:
        p = dict(room=a.room, notes="explicit")
    else:
        ap.error("a preset or --room")
    if a.pos:
        p["pos"] = a.pos
    if a.ang is not None:
        p["ang"] = a.ang
    rsf = {k: list(v) for k, v in (p.get("rsf") or {}).items()}
    for r in a.rsf:
        room, bits = r.split(":")
        rsf.setdefault(int(room, 0), []).extend(int(b) for b in bits.split(","))
    p["rsf"] = rsf
    sc = dict(p.get("scenario") or {})
    for s in a.scenario:
        i, v = s.split(":")
        sc[int(i)] = sc.get(int(i), 0) | int(v, 16)
    p["scenario"] = sc
    if a.find is not None:
        p["find"] = (p.get("find") or 0) | a.find
    door = list(p.get("door", []))
    for act in a.act:
        kind, frame, hold = act.split(":")
        door.append((kind, int(frame), int(hold)))
    p["door"] = door
    text = lines_for(p, door=a.door or bool(a.act), dump=a.dump, name=a.preset or "explicit")
    if a.output:
        open(a.output, "w").write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
