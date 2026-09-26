"""Generates port/dreamcast/game/platform/avk_sh4.S (game30.mk ACTOR_VTX_KERNEL) from pos.tpl / light.tpl.

Each template is one loop iteration (vertex k's work, the previous vertex's @tail, the next record's
loads; @skin / @u16 / @pf lines per variant). Each variant's body is list-scheduled and annealed against
sim.py (the issue rules of tools/hwmodel/hwsim.c, no caches) with two copies in flight, then emitted as a
two-half loop (positions: fv0 / fv4 alternate) with drains after the end / palette-switch branches, a
restart half for the first record, and the skinned switch code. Schedules are cached in
sched-<variant>.txt (delete one to reschedule it). Usage: python3 mkavk.py <out.S> [anneal steps]"""
import sys, os, re, random, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim
import gen_util as G

STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
HERE = os.path.dirname(os.path.abspath(__file__))


def load_tpl(path, flags):
    out = []
    for raw in open(path).read().splitlines():
        l = raw.split("!")[0].rstrip()
        if not l.strip():
            continue
        tags = set(re.findall(r"@(tail|skin|u16|pf)\b", l))
        text = re.sub(r"@(tail|skin|u16|pf)\b", "", l).strip()
        if ("skin" in tags and "skin" not in flags) or ("u16" in tags and "u16" not in flags) or \
                ("pf" in tags and "pf" not in flags):
            continue
        out.append((text, "tail" in tags))
    return out


def sim_text(t):
    """text used for timing / dependency analysis: branch pseudo-targets become plain labels"""
    return re.sub(r"@(end|switch|slow)", "x", t)


def fake_regs(t):
    if "@slow" in t:
        return {"r4", "r8", "r9"}
    return set()


def build_deps(lines):
    res = G.sub([sim_text(t) for t, _ in lines], 0, 4)
    dec = [sim.decode(x) for x in res]
    n = len(lines)
    deps = [set() for _ in range(n)]
    for j in range(n):
        gj, lj, dj, uj, kj, d2j = dec[j]
        Dj = set(dj) | set(d2j) | fake_regs(lines[j][0])
        Uj = set(uj) | fake_regs(lines[j][0])
        for i in range(j):
            gi, li, di, ui, ki, d2i = dec[i]
            Di = set(di) | set(d2i) | fake_regs(lines[i][0])
            Ui = set(ui) | fake_regs(lines[i][0])
            if Di & Uj or Dj & Ui or Di & Dj:
                deps[j].add(i)
            if "store" in ki and "store" in kj:
                deps[j].add(i)
            # branches keep their order among themselves
            if gi == "BR" and gj == "BR":
                deps[j].add(i)
    lat = [d[1] for d in dec]
    return deps, lat


def loop_cycles(lines, order, two):
    seq = [sim_text(lines[k][0]) for k in order]
    if two:
        body = G.sub(seq, 0, 4) + G.sub(seq, 4, 0)
    else:
        body = G.sub(seq, 0, 4) + G.sub(seq, 0, 4)
    return sim.simulate(body + ["bra x", "nop"], iters=24) / 2.0


def schedule(lines, two, steps, seed=1):
    n = len(lines)
    deps, lat = build_deps(lines)
    prio = [0] * n
    for i in reversed(range(n)):
        succ = [j for j in range(i + 1, n) if i in deps[j]]
        prio[i] = max([lat[i] + prio[j] for j in succ] + [lat[i]])

    def greedy(noise, s):
        rnd = random.Random(s)
        placed, left = [], set(range(n))
        while left:
            ready = [k for k in left if deps[k] <= set(placed)]
            best = None
            for k in ready:
                seq = G.sub([sim_text(lines[x][0]) for x in placed + [k]], 0, 4)
                t = sim.issue_time_last(seq)
                key = (t, -prio[k] + noise * rnd.random(), k)
                if best is None or key < best[0]:
                    best = (key, k)
            placed.append(best[1])
            left.discard(best[1])
        return placed

    best = None
    for s in range(30):
        o = greedy(0.0 if s == 0 else 3.0, s)
        c = loop_cycles(lines, o, two)
        if best is None or c < best[0]:
            best = (c, o)
    rnd = random.Random(seed)
    cur, cc = list(best[1]), best[0]
    bestc, besto = cc, list(cur)
    for s in range(steps):
        T = 1.0 * (1 - s / steps) + 0.02
        i = rnd.randrange(n)
        k = cur[i]
        pos = {x: j for j, x in enumerate(cur)}
        lo = max([pos[d] for d in deps[k]] + [-1]) + 1
        hi = min([pos[j] for j in range(n) if k in deps[j]] + [n])
        cand = cur[:i] + cur[i + 1:]
        lo2 = lo if lo <= i else lo - 1
        hi2 = hi - 1 if hi > i else hi
        if hi2 < lo2:
            continue
        p = rnd.randint(lo2, hi2)
        new = cand[:p] + [k] + cand[p:]
        if new == cur:
            continue
        c = loop_cycles(lines, new, two)
        if c <= cc or rnd.random() < math.exp(-(c - cc) / T):
            cur, cc = new, c
            if c < bestc:
                bestc, besto = c, list(new)
    pos = {x: j for j, x in enumerate(besto)}
    assert all(pos[d] < pos[k] for k in range(n) for d in deps[k])
    return bestc, besto


def get_schedule(name, lines, two):
    path = os.path.join(HERE, "sched-%s.txt" % name)
    key = "\n".join("%s%s" % ("T " if tl else "  ", t) for t, tl in lines)
    if os.path.exists(path):
        txt = open(path).read()
        head, _, body = txt.partition("\n==\n")
        if head == key:
            order = [int(x) for x in body.split()[1:]]
            return float(body.split()[0]), order
    c, o = schedule(lines, two, STEPS)
    open(path, "w").write(key + "\n==\n%.2f %s\n" % (c, " ".join(map(str, o))))
    return c, o


class Emitter:
    def __init__(self, prefix):
        self.p = prefix
        self.out = []
        self.n = 0

    def lab(self, s):
        return ".L%s_%s" % (self.p, s)

    def fresh(self, s):
        self.n += 1
        return ".L%s_%s%d" % (self.p, s, self.n)


def render(em, seq, par, targets, tramp, slows):
    """seq: list of (text, tail) in order; par: (V, N); targets: dict end/switch -> label;
    branches go through trampolines (collected in tramp) since the drains are far away."""
    v, n = par
    out = []
    for t, _ in seq:
        x = G.sub([t], v, n)[0]
        m = re.match(r"(bt|bf)\s+@(end|switch|slow)", x)
        if m:
            if m.group(2) == "slow":
                tl = em.fresh("tslow")
                sl = em.fresh("slow")
                rl = em.fresh("ret")
                out.append("        %s      %s" % (m.group(1), tl))
                out.append("%s:" % rl)
                tramp.append((tl, sl))
                slows.append((sl, rl))
            else:
                tl = em.fresh("t" + m.group(2))
                out.append("        %s      %s" % (m.group(1), tl))
                tramp.append((tl, targets[m.group(2)]))
            continue
        out.append("        " + x)
    return out


def split_after(seq, which):
    """instructions after the branch 'bt/bf @which', without the @end/@switch branches"""
    idx = [i for i, (t, _) in enumerate(seq) if re.search(r"@%s\b" % which, t)][0]
    rest = seq[idx + 1:]
    return [(t, tl) for t, tl in rest if not re.search(r"@(end|switch)\b", t)]


def between(seq):
    """instructions between bt @end and bf @switch (without branches)"""
    a = [i for i, (t, _) in enumerate(seq) if re.search(r"@end\b", t)][0]
    b = [i for i, (t, _) in enumerate(seq) if re.search(r"@switch\b", t)][0]
    return [(t, tl) for t, tl in seq[a + 1:b] if not re.search(r"@(end|switch)\b", t)]


XMTRX_LOAD = ["fschg"] + ["fmov    @r0+,xd%d" % i for i in range(0, 16, 2)] + ["fschg"]


def pos_kernel(name, flags):
    skin = "skin" in flags
    u16 = "u16" in flags
    lines = load_tpl(os.path.join(HERE, "pos.tpl"), flags)
    cyc, order = get_schedule(name, lines, True)
    seq = [lines[k] for k in order]
    em = Emitter(name)
    L = em.lab
    o = []
    o.append("/* %s: scheduled loop %.2f model cycles per vertex (sim.py) */" % (name, cyc))
    o += ["        .align  5", "        .global _re4dc_avk_%s" % name, "        .type   _re4dc_avk_%s, @function" % name,
          "_re4dc_avk_%s:" % name]
    ins = []
    for r in range(8, 15):
        ins.append("mov.l   r%d,@-r15" % r)
    for f in range(12, 16):
        ins.append("fmov.s  fr%d,@-r15" % f)
    ins += ["mov.l   r4,@-r15", "mov     r4,r0", "add     #40,r0"]
    ins += ["fmov.s  @r0+,fr%d" % f for f in range(8, 16)]
    ins += ["mov.l   @(0,r4),r5", "mov.l   @(4,r4),r6", "mov.l   @(8,r4),r12", "mov.l   @(12,r4),r13",
            "mov.l   @(16,r4),r7", "mov.l   @(20,r4),r8", "mov.l   @(24,r4),r11"]
    if skin:
        ins += ["mov.w   @r5,r1", "shll2   r1", "add     r1,r1", "add     r12,r1", "mov.w   @(6,r1),r0",
                "mov     r0,r14", "mov.l   @(36,r4),r2", "cmp/hs  r2,r0", "bf      1f", "mov     #0,r0", "1:",
                "mov.l   @(32,r4),r2", "mov.b   @(r0,r2),r2", "tst     r2,r2", "bf      3f", "bra     %s" % L("exit"),
                "nop", "3:", "shll2   r0", "shll2   r0", "shll2   r0", "mov.l   @(28,r4),r2", "add     r2,r0"]
    else:
        ins += ["mov.l   @(28,r4),r0"]
    ins += XMTRX_LOAD
    ins += ["mov.w   @r5,r1", "mov.w   @(4,r5),r0", "add     r11,r5", "shll2   r1", "add     r1,r1",
            "add     r12,r1", "shll2   r0", "add     r13,r0", "mov.w   @r0+,r9", "mov.w   @r0,r10"]
    if u16:
        ins += ["extu.w  r9,r9", "extu.w  r10,r10"]
    ins += ["mov.w   @r1+,r2", "mov.w   @r1+,r3", "mov.w   @r1,r1", "lds     r2,fpul", "float   fpul,fr0",
            "lds     r3,fpul", "float   fpul,fr1", "lds     r1,fpul", "float   fpul,fr2", "fldi1   fr3",
            "add     #24,r7", "bra     %s" % L("rA"), "nop"]
    o += [("        " + x) if not x.endswith(":") else x for x in ins]
    tramp, slows = [], []
    tgtA = {"end": L("deA"), "switch": L("dsA")}
    tgtB = {"end": L("deB"), "switch": L("dsB")}
    # loop
    o.append("        .align  5")
    o.append("%s:" % L("hA"))
    o += render(em, seq, (0, 4), tgtA, tramp, slows)
    o.append("%s:" % L("hB"))
    bodyB = render(em, seq, (4, 0), tgtB, tramp, slows)
    # delay slot: move the last plain instruction of B into the bra slot
    last = bodyB[-1]
    if not last.endswith(":") and not re.match(r"\s*(bt|bf|bra)", last):
        o += bodyB[:-1] + ["        bra     %s" % L("hA"), last]
    else:
        o += bodyB + ["        bra     %s" % L("hA"), "        nop"]
    for tl, tg in tramp:
        o += ["%s:" % tl, "        bra     %s" % tg, "        nop"]
    tramp.clear()
    # restart A (entry): half A without the previous vertex's tail, then half B
    # (its drains are its own: a tail line scheduled after the branches must not run there)
    o.append("%s:" % L("rA"))
    o += render(em, [x for x in seq if not x[1]], (0, 4), {"end": L("deR"), "switch": L("dsR")}, tramp, slows)
    o += ["        bra     %s" % L("hB"), "        nop"]
    for tl, tg in tramp:
        o += ["%s:" % tl, "        bra     %s" % tg, "        nop"]
    tramp.clear()
    # drains
    for P, par, nxt, part in (("A", (0, 4), "hB", seq), ("B", (4, 0), "hA", seq),
                              ("R", (0, 4), "hB", [x for x in seq if not x[1]])):
        tg = {"end": L("de" + P), "switch": L("ds" + P)}
        o.append("%s:" % L("de" + P))
        if skin:
            o += render(em, between(part), par, tg, tramp, slows)
            o.append("%s:" % L("ds" + P))
            o += render(em, split_after(part, "switch"), par, tg, tramp, slows)
        else:
            o += render(em, split_after(part, "end"), par, tg, tramp, slows)
        o += ["        tst     r6,r6", "        bt      %s" % L("t" + P)]
        if skin:
            sw = ["mov     r5,r1", "sub     r11,r1", "mov.w   @r1,r1", "shll2   r1", "add     r1,r1",
                  "add     r12,r1", "mov.w   @(6,r1),r0", "mov     r0,r14", "mov.l   @r15,r2",
                  "mov.l   @(36,r2),r3", "cmp/hs  r3,r0", "bf      1f", "mov     #0,r0", "1:",
                  "mov.l   @(32,r2),r3", "mov.b   @(r0,r3),r3", "tst     r3,r3", "bt      %s" % L("t" + P),
                  "shll2   r0", "shll2   r0", "shll2   r0", "mov.l   @(28,r2),r3", "add     r3,r0"] + XMTRX_LOAD + \
                 ["bra     %s" % L(nxt), "nop"]
            o += [("        " + x) if not x.endswith(":") else x for x in sw]
        o.append("%s:" % L("t" + P))
        o += render(em, [x for x in seq if x[1]], par, tg, tramp, slows)
        o += ["        bra     %s" % L("exit"), "        nop"]
        for tl, tgl in tramp:
            o += ["%s:" % tl, "        bra     %s" % tgl, "        nop"]
        tramp.clear()
    ex = ["mov.l   @r15+,r4", "mov     r6,r0"] + ["fmov.s  @r15+,fr%d" % f for f in (15, 14, 13, 12)] + \
         ["mov.l   @r15+,r%d" % r for r in range(14, 7, -1)] + ["rts", "nop"]
    o.append("%s:" % L("exit"))
    o += ["        " + x for x in ex]
    o.append("        .size   _re4dc_avk_%s, .-_re4dc_avk_%s" % (name, name))
    assert not slows
    return o, cyc


def light_kernel(name, flags):
    skin = "skin" in flags
    lines = load_tpl(os.path.join(HERE, "light.tpl"), flags)
    cyc, order = get_schedule(name, lines, False)
    seq = [lines[k] for k in order]
    em = Emitter(name)
    L = em.lab
    o = ["/* %s: scheduled loop %.2f model cycles per vertex (sim.py) */" % (name, cyc)]
    o += ["        .align  5", "        .global _re4dc_avk_%s" % name, "        .type   _re4dc_avk_%s, @function" % name,
          "_re4dc_avk_%s:" % name]
    ins = ["mov.l   r%d,@-r15" % r for r in range(8, 15)] + ["fmov.s  fr%d,@-r15" % f for f in range(12, 16)]
    ins += ["mov.l   r4,@-r15", "mov.l   @(0,r4),r5", "mov.l   @(4,r4),r6", "mov.l   @(8,r4),r13",
            "mov.l   @(12,r4),r7", "mov.l   @(16,r4),r11", "mov.l   @(36,r4),r10", "mov     #-1,r12",
            "extu.b  r12,r12", "mov.l   %s,r3" % L("s8f"), "mov.l   @(20,r4),r0"] + XMTRX_LOAD
    # PRE(0): normal 0 through the s8 -> float table into fv4
    ins += ["mov.w   @(2,r5),r0", "add     r11,r5", "shll2   r0", "mov     r13,r1", "add     r0,r1"]
    for f in (4, 5, 6):
        ins += ["mov.b   @r1+,r0", "shll2   r0", "fmov.s  @(r0,r3),fr%d" % f]
    if skin:
        ins += ["mov.b   @r1,r0", "mov     r0,r14", "extu.b  r0,r0", "mov.l   @(32,r4),r8", "cmp/hs  r8,r0",
                "bf      1f", "mov     #0,r0", "1:", "mov.l   @(28,r4),r8", "mov.b   @(r0,r8),r8", "tst     r8,r8",
                "bf      3f", "bra     %s" % L("exit"), "nop", "3:", "shll2   r0", "shll2   r0", "mov     r0,r8",
                "add     r0,r0", "add     r8,r0", "mov.l   @(24,r4),r8", "add     r8,r0"]
    else:
        ins += ["mov.l   @(24,r4),r0"]
    ins += ["fmov.s  @r0+,fr%d" % f for f in (8, 9, 10, 11, 12, 13, 14, 15, 0, 1, 2, 3)]
    ins += ["fldi0   fr7", "bra     %s" % L("rA"), "nop", ".align  2", "%s:" % L("s8f"),
            ".long   .Lavk_s8f+512"]
    o += [("        " + x) if not x.endswith(":") else x for x in ins]
    tramp, slows = [], []
    tg = {"end": L("de"), "switch": L("ds")}
    o.append("        .align  5")
    o.append("%s:" % L("hA"))
    o += render(em, seq, (0, 4), tg, tramp, slows)
    bodyB = render(em, seq, (0, 4), tg, tramp, slows)
    last = bodyB[-1]
    if not last.endswith(":") and not re.match(r"\s*(bt|bf|bra)", last):
        o += bodyB[:-1] + ["        bra     %s" % L("hA"), last]
    else:
        o += bodyB + ["        bra     %s" % L("hA"), "        nop"]
    for tl, tgl in tramp:
        o += ["%s:" % tl, "        bra     %s" % tgl, "        nop"]
    tramp.clear()
    # (its drains are its own: a tail line scheduled after the branches must not run there)
    o.append("%s:" % L("rA"))
    o += render(em, [x for x in seq if not x[1]], (0, 4), {"end": L("deR"), "switch": L("dsR")}, tramp, slows)
    o += ["        bra     %s" % L("hA"), "        nop"]
    for tl, tgl in tramp:
        o += ["%s:" % tl, "        bra     %s" % tgl, "        nop"]
    tramp.clear()
    for P, part in (("R", [x for x in seq if not x[1]]), ("", seq)):
        o += light_drain(em, L, P, part, skin, tramp, slows)
    o.append("%s:" % L("t"))
    o += render(em, [x for x in seq if x[1]], (0, 4), tg, tramp, slows)
    o += ["        bra     %s" % L("exit"), "        nop"]
    for tl, tgl in tramp:
        o += ["%s:" % tl, "        bra     %s" % tgl, "        nop"]
    tramp.clear()
    for sl, rl in slows:
        o += ["%s:" % sl, "        cmp/gt  r12,r4", "        bf      1f", "        mov     r12,r4", "1:",
              "        cmp/gt  r12,r8", "        bf      1f", "        mov     r12,r8", "1:",
              "        cmp/gt  r12,r9", "        bf      1f", "        mov     r12,r9", "1:",
              "        bra     %s" % rl, "        nop"]
    ex = ["mov.l   @r15+,r4", "mov     r6,r0"] + ["fmov.s  @r15+,fr%d" % f for f in (15, 14, 13, 12)] + \
         ["mov.l   @r15+,r%d" % r for r in range(14, 7, -1)] + ["rts", "nop"]
    o.append("%s:" % L("exit"))
    o += ["        " + x for x in ex]
    o.append("        .size   _re4dc_avk_%s, .-_re4dc_avk_%s" % (name, name))
    return o, cyc


def light_drain(em, L, P, seq, skin, tramp, slows):
    """drain after vertex k (P = "R": entered from the restart half, no previous-vertex tail lines),
    then: the tail of k and exit (last record), or the directions switch and back into the loop."""
    tg = {"end": L("de" + P), "switch": L("ds" + P)}
    o = ["%s:" % L("de" + P)]
    if skin:
        o += render(em, between(seq), (0, 4), tg, tramp, slows)
        o.append("%s:" % L("ds" + P))
        o += render(em, split_after(seq, "switch"), (0, 4), tg, tramp, slows)
    else:
        o += render(em, split_after(seq, "end"), (0, 4), tg, tramp, slows)
    o += ["        tst     r6,r6", "        bt      %s" % L("t")]
    if skin:
        sw = ["mov.l   r4,@-r15", "mov.l   r8,@-r15", "mov.l   r9,@-r15",
              "mov     r5,r8", "sub     r11,r8", "mov.w   @(2,r8),r0", "shll2   r0", "add     r13,r0",
              "mov.b   @(3,r0),r0", "mov     r0,r14", "extu.b  r0,r0", "mov.l   @(12,r15),r4", "mov.l   @(32,r4),r8",
              "cmp/hs  r8,r0", "bf      1f", "mov     #0,r0", "1:", "mov.l   @(28,r4),r8", "mov.b   @(r0,r8),r8",
              "tst     r8,r8", "bt      2f", "shll2   r0", "shll2   r0", "mov     r0,r8", "add     r0,r0",
              "add     r8,r0", "mov.l   @(24,r4),r8", "add     r8,r0",
              "fmov.s  @r0+,fr8", "fmov.s  @r0+,fr9", "fmov.s  @r0+,fr10", "add     #4,r0",
              "fmov.s  @r0+,fr12", "fmov.s  @r0+,fr13", "fmov.s  @r0+,fr14", "add     #4,r0",
              "fmov.s  @r0+,fr0", "fmov.s  @r0+,fr1", "fmov.s  @r0,fr2", "fldi0   fr7",
              "mov.l   @r15+,r9", "mov.l   @r15+,r8", "mov.l   @r15+,r4", "bra     %s" % L("hA"), "nop",
              "2:", "mov.l   @r15+,r9", "mov.l   @r15+,r8", "mov.l   @r15+,r4", "bra     %s" % L("t"), "nop"]
        o += [("        " + x) if not x.endswith(":") else x for x in sw]
    else:
        o += ["        bra     %s" % L("t"), "        nop"]
    return o


HEADER = """/* platform/avk_sh4.S -- ACTOR_VTX_KERNEL (game30.mk): the actors30 meshlet vertex passes of
 * native_actor_fast.cpp (re4dc_actor_submit) as software-pipelined SH-4 loops.
 *
 * GENERATED by the vertex-loop lane's mkavk.py from pos.tpl / light.tpl (list-scheduled against the
 * hwmodel issue rules); edit the templates, not this file.
 *
 * re4dc_avk_pos_{skin,rigid}_{s16,u16}(AvkPos*): pass 1 over up to n records (stride 8 positions):
 * the float operations of ACTOR_POS_ASM (ftrv through XMTRX, fmul w*w, fsrra, fmul x / y, u / v =
 * t * a + b by fmul + fadd), outcode bits near far left right top bottom (MSB first: the layout the
 * knob gives kOc*), two vertices in flight (fv0 / fv4). Skinned: a record whose position palette
 * index differs from the current one drains the pipeline and loads that entry's matrix from the skin
 * table when its ready byte is set; otherwise the kernel stops. Returns the records not processed.
 * all / any are not accumulated (the caller folds the outcode bytes).
 *
 * re4dc_avk_light_{skin,rigid}(AvkLight*): pass 2 (fast lights, s8 normals, stride 4) with the float
 * operations of ACTOR_LIGHT_ASM (three fipr, m = d + |d|, colour by ftrv), the 255 clamp done on the
 * truncated integers (same result), one vertex's ftrc / pack overlapped with the next one's dot
 * products. Normal bytes become floats through a 256-entry table (the values float() gives). The
 * colour matrix's row 3 is zero (build_lights), so the colour ftrv leaves fr7 = 0: the normal's w for
 * the next vertex's fipr (whose w slot then holds a colour copy). Skinned: a normal palette index
 * change loads that entry's directions (ready byte set) or stops. Returns the records not processed.
 *
 * Records are read one ahead (and their lines prefetched two ahead): up to two records past the last
 * one and the position / uv / normal words they index are read and discarded.
 * ABI: KOS -m4-single -ml, FPSCR.PR = SZ = 0 on entry and exit; saves r8-r14 and fr12-fr15; XMTRX is
 * clobbered.
 */
        .text
"""


def main():
    out = [HEADER]
    rep = []
    for name, flags in (("pos_skin_s16", {"skin", "pf"}), ("pos_skin_u16", {"skin", "u16", "pf"}),
                        ("pos_rigid_s16", {"pf"}), ("pos_rigid_u16", {"u16", "pf"})):
        o, c = pos_kernel(name, flags)
        out += o + [""]
        rep.append((name, c))
    for name, flags in (("light_skin", {"skin"}), ("light_rigid", set())):
        o, c = light_kernel(name, flags)
        out += o + [""]
        rep.append((name, c))
    import struct
    out += ["/* s8 -> float for the light kernels' normal bytes: entry i = (float)(i - 128), indexed with the",
            " * sign-extended byte x 4 from .Lavk_s8f + 512. */", "        .section .rodata", "        .align  5",
            ".Lavk_s8f:"]
    for i in range(-128, 128, 4):
        out.append("        .long   " + ", ".join("0x%08x" % struct.unpack("<I", struct.pack("<f", float(j)))[0]
                                                  for j in range(i, i + 4)))
    open(sys.argv[1], "w", newline="\n").write("\n".join(out) + "\n")
    for n, c in rep:
        print("%-16s %.2f cycles/vertex (model, no misses)" % (n, c))


main()
