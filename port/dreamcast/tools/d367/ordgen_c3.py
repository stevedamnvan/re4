#!/usr/bin/env python3
"""Profile-guided code placement for the game ELF (game30.mk LINK_ORDER=<file>; exact: placement only).

The SH-4's 8 KB instruction cache is direct mapped: code that runs together conflicts when its addresses
meet modulo 8 KB. This writes an ld --section-ordering-file that puts the hot code first in .text, as
call chains clustered to at most --max bytes (HFSort's C3):
  - call edges are exact: every static call site (bsr / bra to another function; jsr / jmp @rN after a
    PC-relative literal load of the target) weighted by its execution count in the run's trace/counts.bin
    (per-instruction counts over the counted ticks), summed over the given hwproject evidence runs;
  - nodes are input sections (a C / C++ function's .text.<name>, an assembler object's whole .text);
    hotness is hw ms from each run's proj/rep/functions.tsv;
  - in decreasing hotness, a node's cluster is appended to the cluster of its most frequent caller while
    the merged cluster stays <= --max bytes; clusters are then placed by density (hotness per byte).
Library code (libc, libgcc, KOS) stays where it is.

r101 square, 2026-09-25 (8 KB clusters from a never-draw and a drawn run): never-draw work -1.25 hw ms
(I-miss 4.67 -> 3.74 ms), every tick drawn -0.94; logic trace STRICT, every decision identical. 4 KB
clusters: -0.77 / -0.97. Hottest-first without clustering: +0.17 / +0.05.

usage: ordgen_c3.py --objdir <OBJDIR of a build with the same code> [--max 8192] [--limit 400000]
                    [--evidence-root D] -o <out.ld> <hwproject evidence dir name>...
Regenerate after code changes (sections it names that no longer exist are ignored by ld)."""
import argparse
import bisect
import collections
import glob
import os
import re
import struct
import subprocess

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--objdir", required=True)
ap.add_argument("--max", type=int, default=8192, help="largest cluster in bytes (the I-cache size)")
ap.add_argument("--limit", type=int, default=400000, help="bytes of hot code to place")
ap.add_argument("--evidence-root", default=os.environ.get("HWM_EVIDENCE", "/mnt/d/Flycast-Evidence/re4-dreamcast"))
ap.add_argument("--tools", default="/opt/toolchains/dc/sh-elf/bin/sh-elf-")
ap.add_argument("-o", "--out", required=True)
ap.add_argument("runs", nargs="+")
a = ap.parse_args()
TOOLS = a.tools


def run(*args):
    return subprocess.run(list(args), capture_output=True, text=True, check=True).stdout


# objects: symbol (as stored, leading underscore) -> input section; input section -> size
where, secsize = {}, {}
for o in sorted(glob.glob(a.objdir + "/**/*.o", recursive=True)):
    base = os.path.basename(o)
    for l in run(TOOLS + "objdump", "-t", o).splitlines():
        p = l.split()
        if len(p) >= 5 and p[-3].startswith(".text"):
            where.setdefault(p[-1], (base, p[-3]))
    for l in run(TOOLS + "objdump", "-h", o).splitlines():
        p = l.split()
        if len(p) >= 3 and p[1].startswith(".text"):
            secsize[(base, p[1])] = int(p[2], 16)

hot = collections.Counter()
edge = collections.Counter()
rx = re.compile(r"^\s*([0-9a-f]+):\s+(\S+)\s+(.*)$")
lit = re.compile(r"mov\.l\s+.*?,(r\d+)\s+!\s*([0-9a-f]+)")
for name in a.runs:
    E = os.path.join(a.evidence_root, name)
    ELF = E + "/re4dc-game.elf"
    raw = open(E + "/trace/counts.bin", "rb").read()
    cnt = struct.unpack("<%dI" % (len(raw) // 4), raw)
    nm = run(TOOLS + "nm", "-n", ELF).splitlines()
    nmc = run(TOOLS + "nm", "-n", "-C", ELF).splitlines()
    assert len(nm) == len(nmc)
    starts, names, dem2m, start_of = [], [], {}, {}
    for m, d in zip(nm, nmc):
        pm = m.split(None, 2)
        if len(pm) != 3 or pm[1] not in ("t", "T", "W"):
            continue
        ad = int(pm[0], 16)
        starts.append(ad)
        names.append(pm[2])
        start_of.setdefault(ad, pm[2])
        dem2m.setdefault(d.split(None, 2)[2], pm[2])

    def fn(ad):
        i = bisect.bisect_right(starts, ad) - 1
        return names[i] if i >= 0 else None

    L = open(E + "/proj/rep/functions.tsv").read().splitlines()
    h = L[0].split("\t")
    fi, hi = h.index("func"), h.index("hw_ms")
    for l in L[1:]:
        f = l.split("\t")
        m = dem2m.get(f[fi])
        if m:
            hot[m] += float(f[hi])
    recent = {}
    for line in run(TOOLS + "objdump", "-d", "--no-show-raw-insn", ELF).splitlines():
        mm = rx.match(line)
        if not mm:
            continue
        pc, op, args = int(mm.group(1), 16), mm.group(2), mm.group(3)
        if op == "mov.l":
            lm = lit.search(line)
            if lm:
                recent[lm.group(1)] = (int(lm.group(2), 16), pc)
            continue
        tgt = None
        if op in ("jsr", "jmp"):
            r = args.split("@")[-1].strip()
            if r in recent and pc - recent[r][1] < 64:
                tgt = recent[r][0]
        elif op in ("bsr", "bra"):
            t = re.search(r"([0-9a-f]+) <", args)
            if t:
                tgt = int(t.group(1), 16)
        if tgt is None or tgt not in start_of:
            continue
        caller, callee = fn(pc), start_of[tgt]
        if caller is None or caller == callee:
            continue
        i = (pc - 0x8c000000) >> 1
        c = cnt[i] if 0 <= i < len(cnt) else 0
        if c:
            edge[(caller, callee)] += c

nhot = collections.Counter()
for s, w in hot.items():
    if s in where:
        nhot[where[s]] += w
callers = collections.defaultdict(collections.Counter)
for (x, y), w in edge.items():
    kx, ky = where.get(x), where.get(y)
    if kx and ky and kx != ky:
        callers[ky][kx] += w

cluster = {k: [k] for k in nhot}
cof = {k: k for k in nhot}
csize = {k: secsize.get(k, 0) for k in nhot}
chot = dict(nhot)
merges = 0
for k, w in nhot.most_common():
    if w < 0.002 or not callers[k]:
        continue
    c = max(callers[k].items(), key=lambda kv: kv[1])[0]
    if c not in cof:
        continue
    A, B = cof[c], cof[k]
    if A == B or csize[A] + csize[B] > a.max:
        continue
    cluster[A] += cluster[B]
    for n in cluster[B]:
        cof[n] = A
    csize[A] += csize[B]
    chot[A] += chot[B]
    del cluster[B], csize[B], chot[B]
    merges += 1

order = sorted(cluster, key=lambda c: -(chot[c] / max(csize[c], 32)))
rules, total, cov = [], 0, 0.0
for c in order:
    if chot[c] < 0.002:
        continue
    if total + csize[c] > a.limit:
        break
    rules += ["*%s(%s)" % n for n in cluster[c]]
    total += csize[c]
    cov += chot[c]
with open(a.out, "w") as f:
    f.write("/* ordgen_c3.py: clusters <= %d B, %d input sections, %d B, %.2f of %.2f hw ms; runs: %s */\n" % (
        a.max, len(rules), total, cov, sum(hot.values()), " ".join(a.runs)))
    f.write(".text : {\n  *_kos_startup.o(.text)\n")
    for r in rules:
        f.write("  %s\n" % r)
    f.write("}\n")
print("%s: %d sections, %d B, %.2f of %.2f hw ms placed, %d merges, %d call edges" % (
    a.out, len(rules), total, cov, sum(hot.values()), merges, len(edge)))
