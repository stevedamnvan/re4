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
# ESL entries r101's bell (r101_Event30) sets dead: the villagers who leave for the church.
R101_BELL_DEAD = [0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1E, 0x1F, 0x22, 0x23, 0x24, 0x28, 0x29,
                  0x2A, 0x2B, 0x2C, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3C, 0x3D, 0x3E,
                  0x3F, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46]
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
    # The same door in the natural after state (s03 + s20 done, ambush over). Entering r100 with
    # flag 10 set spawns em2a (traps): linked since e6f65cc (was HALT main_sub.cpp(1440), warp-east-1).
    # The crow archive (em23) does not fit heap 4 in this state with Original packages.
    "r100-east-door-after": dict(room=0x100, pos=(96523, -6771, -8536), ang=2.247,
                                 rsf={0x100: R100_AFTER_S03_S20 + [4, 12, 14, 15]}, scenario={0: 0x10}, find=0x4000,
                                 door=[("fwd", 30, 20), ("a", 60, 4), ("a", 150, 4), ("a", 240, 4)],
                                 notes="r101 door, after state (crows absent: heap 4)"),
    # r101 fresh entry (first visit: typewriter + Hunnigan call via r101_execOperator2).
    "r101-entry": dict(room=0x101, notes="fresh r101 entry (first visit, Item_find 0x2000 clear)"),
    # The square before the fight: first visit done (Item_find 0x2000: no typewriter call), fight
    # not started (flag 6 clear): r101_checkFindPlayer starts it when a Ganado finds Leon.
    # Leon at the square's examine point (AEV area 09), facing the square (area 0B). The bell
    # itself (s30) needs 15 kills or 11700 fight frames counted at run time (r101_checkEmNum):
    # not a flag state, so the preset stops at the fight start.
    "r101-bell-fight": dict(room=0x101, pos=(-7914, 0, -254), ang=2.96, find=0x2000,
                            notes="r101 square, fight about to start (flags 6/7 clear, first visit done)"),
    # The same fight, then the bell: `trg 0` makes the source's developer shortcut DebugTrg(0) fire in
    # r101_checkEmNum, which starts event 30 (bell, chapter title, r101s30) as 15 kills would. About
    # 1,000 fight frames with Ganados engaged come first (the fight starts ~150-250 frames in).
    "r101-bell": dict(room=0x101, pos=(-7914, 0, -254), ang=2.96, find=0x2000, trg=(0, 1200, 0x101),
                      notes="r101 square fight, bell forced at room frame 1200 (DebugTrg(0))"),
    # r101 after the bell, at the r103 door: room flag 7 (bell done) set and 10 (post-bell call) clear,
    # so R101Init runs r101_execOperator (radio term 2, stream 1:0x33) and installs no
    # r101_DoorDontOpen103 lock. Leon stands where r103's door back puts him (r103 AEV record 0,
    # angle -1.5038), turned to face the door, with the ESL entries the bell sets dead (R101_BELL_DEAD;
    # without them a Ganado grabs Leon at the door, warp-r101-pbdoor1). --door closes the call (A:
    # it closed on the first A at room frame 800 in pbdoor1; B did not), steps forward, presses A.
    "r101-post-bell-door": dict(room=0x101, pos=(39372, 3201, -26667), ang=1.6378, rsf={0x101: [6, 7]}, find=0x2000,
                                dead=R101_BELL_DEAD,
                                door=[("a", 700, 4), ("a", 820, 4), ("fwd", 940, 25), ("a", 980, 4),
                                      ("a", 1070, 4), ("a", 1160, 4), ("a", 1250, 4)],
                                notes="r101 after the bell at the r103 door (post-bell call runs first)"),
    # r103 as the r101 door delivers Leon (r101 AEV record 2: dst -47609.06, 11.83, 7083.56, angle
    # 1.889). r103 has no events and no story flags of its own on the route (design-r103 PLAN 1.1).
    "r103-entry": dict(room=0x103, pos=(-47609, 12, 7084), ang=1.889,
                       notes="r103 from the r101 door (5 Ganados, corpses, cows, chickens, dog)"),
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
    dead = list(p.get("dead") or [])
    for i in range(0, len(dead), 10):   # the rig reads at most 12 tokens per line
        out.append("dead " + " ".join("0x%02x" % n for n in dead[i:i + 10]))
    out.append("inv default")
    if door:
        for kind, frame, hold in p.get("door", []):
            out.append("act %d %s %d" % (frame, kind, hold))
    if p.get("trg"):
        no, frame, room = (tuple(p["trg"]) + (0,))[:3]
        out.append("trg %d %d" % (no, frame) + (" 0x%03x" % room if room else ""))
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
    ap.add_argument("--trg", help="NO:FRAME[:ROOM] make DebugTrg(NO) return 1 once (r101 bell: 0)")
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
    if a.trg:
        f = a.trg.split(":")
        p["trg"] = (int(f[0], 0), int(f[1], 0), int(f[2], 0) if len(f) > 2 else 0)
    text = lines_for(p, door=a.door or bool(a.act), dump=a.dump, name=a.preset or "explicit")
    if a.output:
        open(a.output, "w").write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
