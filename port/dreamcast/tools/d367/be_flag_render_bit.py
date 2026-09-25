#!/usr/bin/env python3
"""Guard for LOGIC_TRACE_MASK_RENDER (logic_trace.cpp): be_flag bit 27 (0x08000000) must stay a
render-only marker, or masking it out of the determinism trace could hide a logic change.

    be_flag_render_bit.py [REPO_ROOT]      exit 0: only the known sites; 1: a new use (listed)

It scans every .cpp/.c/.h under src/ and port/dreamcast/game/ for a line that names be_flag and
an integer constant with bit 27 set (hex, decimal, or 1 << 27), and compares the hits with the
known render-side sites below (by file and normalised line text, so edits elsewhere never move
them). Known sites, all in src/game/trans.cpp:
  set    end of commonModelTrans / frontNativeRender (ModelRender), for ot_type 7 models
  clear  ModelTrans, case 7, before the model is inserted again
  read   the commonModelTrans / frontNativeModelTrans info walks (which pass draws which info)
  note   the FRONT_NATIVE=2 comment
A hit anywhere else (logic reading the bit, another writer) fails: review it, and keep
LOGIC_TRACE_MASK_RENDER off until it is understood. Limits: a mask built at run time or taken
from a table is not seen; the whole-word copies in trans.cpp's FRONT_NATIVE=2 replay save and
restore the full be_flag around the draw (net zero) and do not name the bit.
"""
import os
import re
import sys

KNOWN = {
    ("src/game/trans.cpp", "m->be_flag &= ~0x08000000;"),
    ("src/game/trans.cpp", "m->be_flag |= 0x08000000;"),
    ("src/game/trans.cpp", "if (m->be_flag & 0x08000000) {"),
    ("src/game/trans.cpp", "if ((m->be_flag & 0x08000000) ? !(info->be_flag & 0x40) : (info->be_flag & 0x40)) {"),
    ("src/game/trans.cpp", "// be_flag 0x08000000) would steer the info walk, so it is set aside meanwhile."),
    # not the bit: be_flag & 3 on a line that tests Disp_flg 0x08000000 (FRONT_LEAN light skip)
    ("src/game/trans.cpp", "} else if ((lean & FRONT_LEAN_LIGHTS) && (m->be_flag & 3) == 3 && !(pG->Disp_flg & 0x08000000) &&"),
    # the trace mask itself (LOGIC_TRACE_MASK_RENDER=1 only) and its comment
    ("port/dreamcast/game/logic_trace.cpp", "discrete.add(m->be_flag & ~0x08000000u);"),
    ("port/dreamcast/game/logic_trace.cpp", "// LOGIC_TRACE_MASK_RENDER=1 (opt-in; frame pacing gates): be_flag 0x08000000 is left out of the"),
}
BIT = 1 << 27
NUM = re.compile(r"\b(0[xX][0-9a-fA-F]+|\d+)[uUlL]*\b")
SHIFT = re.compile(r"\b1[uU]?\s*<<\s*27\b")


def hits(root):
    out = []
    for top in ("src", "port/dreamcast/game"):
        for d, _, files in os.walk(os.path.join(root, top)):
            for f in files:
                if not f.endswith((".cpp", ".c", ".h", ".hpp")):
                    continue
                path = os.path.join(d, f)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                for n, line in enumerate(open(path, errors="replace"), 1):
                    if "be_flag" not in line:
                        continue
                    bit = bool(SHIFT.search(line))
                    for m in NUM.finditer(line):
                        try:
                            v = int(m.group(1), 0)
                        except ValueError:
                            continue
                        if v & BIT and v < (1 << 32):
                            bit = True
                    if bit:
                        out.append((rel, n, line.strip()))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../.."))
    found = hits(root)
    unknown = [h for h in found if (h[0], h[2]) not in KNOWN]
    for rel, n, text in found:
        print("%s %s:%d: %s" % ("NEW " if (rel, text) not in KNOWN else "ok  ", rel, n, text))
    print("be_flag bit 27: %d sites, %d new" % (len(found), len(unknown)))
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
