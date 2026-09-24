"""Heap-4 options per enemy archive (`assets.sh discover`, round 2).

An enemy archive's heap-4 cost is its prepared body (the .drs record 0 size, "DVD: Mem Alloc").
The body is a tagged entry list (tools/drs.py): BIN models, TPL textures, FCV/SEQ/MTC/ESQ motion,
EFF effects, NTR native texture records, and the embedded REL. When a room's live archives don't
fit its measured heap-4 room, these are the ways to shrink one, each a lossless preparation of the
same archive (tools/prepare_enemy_motions.py contracts; game logic is never changed):

  rel-strip       the REL is linked into the image (MODULES), so the body copy is dead weight
                  (the prepared Ganado/small archives keep a 64-byte stub). Exact.
  tex-upload      TPL texels that a native texture package holds are uploaded to VRAM and not kept
                  (prepare_enemy_motions --textures). Upper bound: the TPL bytes (palettes and mip
                  chains may stay; under 4 KB left is that residue, no option).
  motion-stream   FCV key payloads leave the body and are read through bounded motion leases
                  (the Ganado contract). Upper bound: the FCV bytes (the hot set stays).
  effect-compact  EST records compacted losslessly (--compact-effects). Upper bound unknown:
                  counted 0 until measured; listed when the archive has EFF bytes.

Each option is `applied` (the prepared archive already has it), `qualified` (prepare_enemy_motions
supports it for this archive: run it), or `needs-contract` (the contract must be extended and
proved for this enemy first). The plan covers a shortfall with qualified options first, then the
largest needs-contract ones, and says what remains.
"""
import re
import struct
from collections import Counter
from pathlib import Path

MOTION_TAGS = ("FCV",)
REL_STUB = 64
TPL_RESIDUE = 4096   # below this the TPL bytes are headers/palettes the texture contract keeps (em12/em15 ~3-4 KB)


def breakdown(path):
    """{tag: bytes} of the prepared (little-endian) archive's heap-4 body, plus 'body'."""
    d = Path(path).read_bytes()
    _, size, _, off = struct.unpack_from("<4I", d, 0x20)
    b = d[off:off + size]
    n, rel = struct.unpack_from("<2I", b, 0)
    offs = struct.unpack_from("<%dI" % n, b, 16)
    tags = [b[16 + 4 * (n + i):20 + 4 * (n + i)].rstrip(b"\0").decode("ascii", "replace") or "-" for i in range(n)]
    end = rel if rel else size
    c = Counter()
    order = sorted(range(n), key=lambda i: offs[i])
    for k, i in enumerate(order):
        nxt = offs[order[k + 1]] if k + 1 < n else end
        c[tags[i]] += max(0, nxt - offs[i])
    c["REL"] = size - end if rel else 0
    c["body"] = size
    return dict(c)


def contracts(repo):
    """Archive names per prepare_enemy_motions.py contract (GANADO: motion+textures+effects;
    SMALL: textures+effects), read from the tool so the two never disagree."""
    src = (Path(repo) / "port/dreamcast/tools/prepare_enemy_motions.py").read_text()
    out = {}
    for name in ("GANADO", "SMALL"):
        m = re.search(r"^%s\s*=\s*\(([^)]*)\)" % name, src, re.M)
        out[name] = re.findall(r"'([\w.]+)'", m.group(1)) if m else []
    return out


def options(archive, br, contract, applied):
    """The heap-4 options of one archive. `contract`: 'GANADO', 'SMALL' or None.
    `applied`: the compaction-summary entry when the prepared archive is already compacted."""
    applied = applied or {}
    rows = []

    def add(name, save, qualified, done, basis):
        status = "applied" if done else ("qualified" if qualified else "needs-contract")
        rows.append({"archive": archive, "option": name, "bytes": 0 if done else save, "status": status, "basis": basis})
    rel = br.get("REL", 0)
    if rel > REL_STUB:
        add("rel-strip", rel - REL_STUB, False, False, "exact")
    tex = br.get("TPL", 0)
    if tex > TPL_RESIDUE:
        add("tex-upload", tex, contract in ("GANADO", "SMALL"), applied.get("textures_selected", 0) > 0, "upper bound")
    mot = sum(br.get(t, 0) for t in MOTION_TAGS)
    if mot:
        add("motion-stream", mot, contract == "GANADO", "hot_payload_bytes" in applied, "upper bound")
    if br.get("EFF"):
        add("effect-compact", 0, contract in ("GANADO", "SMALL"), applied.get("effects_recovery", 0) > 0 or
            "no eligible effect sequences" in applied.get("rejected", []), "unmeasured")
    return rows


def plan(short, opts):
    """Options that cover `short` bytes: qualified first (largest first), then needs-contract."""
    live = [o for o in opts if o["status"] != "applied" and o["bytes"] > 0]
    rank = {"qualified": 0, "needs-contract": 1}
    chosen, got = [], 0
    for o in sorted(live, key=lambda o: (rank[o["status"]], -o["bytes"])):
        if got >= short:
            break
        chosen.append(o)
        got += o["bytes"]
    return {"short": short, "covered": got, "remaining": max(0, short - got), "chosen": chosen}
