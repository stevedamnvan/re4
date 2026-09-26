"""Tiny SH-4 issue model mirroring port/dreamcast/tools/hwmodel/hwsim.c's step() (in-order dual issue,
group pairing, latencies, F0 lock, branch redirect); no caches. Input: asm text (one insn per line,
labels 'x:' ignored, '!' comments). simulate(lines, iters) runs the sequence `iters` times (a loop body
whose last insn is the back branch) and returns cycles per iteration in steady state."""
import re, sys

MT, EX, LS, FE, BR, CO = "MT", "EX", "LS", "FE", "BR", "CO"


def R(n):
    return "r%d" % n


def fr(n):
    return "fr%d" % n


def fv(n):
    return [fr(n + i) for i in range(4)]


def parse_reg(s):
    s = s.strip()
    return s


def decode(ins):
    """returns (grp, lat, defs, uses, kind, def2)"""
    ins = ins.split("!")[0].strip()
    m = re.match(r"(\S+)\s*(.*)", ins)
    op, args = m.group(1), m.group(2)
    a = [x.strip() for x in re.split(r",(?![^()]*\))", args)] if args else []
    kind = set()
    d2 = []
    def regs_in(x):
        return re.findall(r"\b(r\d+|fr\d+)\b", x)
    if op in ("mov.w", "mov.b", "mov.l", "fmov.s", "fmov", "mov") and a:
        src, dst = a[0], a[1]
        if src.startswith("@"):  # load
            uses = regs_in(src)
            if src.endswith("+"):
                d2 = regs_in(src)
            g = LS
            lat = 2
            defs = [dst]
            if op == "fmov" and dst.startswith("dr"):
                n = int(dst[2:]); defs = [fr(n), fr(n + 1)]
            if op == "fmov" and dst.startswith("xd"):
                n = int(dst[2:]); defs = ["xf%d" % n, "xf%d" % (n + 1)]
            return (g, lat, defs, uses, {"load"}, d2)
        if dst.startswith("@"):  # store
            uses = regs_in(dst) + regs_in(src)
            if dst.startswith("@-"):
                d2 = regs_in(dst)
            return (LS, 1, [], uses, {"store"}, d2)
        if op == "mov":
            if src.startswith("#"):
                return (EX, 1, [dst], [], set(), [])
            return (MT, 0, [dst], [src], set(), [])
        if op == "fmov":
            return (LS, 0, [dst], [src], set(), [])
    if op in ("add", "sub", "and", "or", "xor", "addc", "subc", "neg", "not", "extu.w", "extu.b", "exts.w", "exts.b",
              "shld", "shad", "swap.w"):
        if a[0].startswith("#"):
            return (EX, 1, [a[1]], [a[1]], set(), [])
        uses = [a[0], a[1]] if op not in ("neg", "not", "extu.w", "extu.b", "exts.w", "exts.b", "swap.w") else [a[0]]
        if op == "and" and a[1] == "r0" and a[0].startswith("#"):
            pass
        defs = [a[1]] + (["T"] if op in ("addc", "subc") else [])
        return (EX, 1, defs, uses, set(), [])
    if op in ("shll2", "shll8", "shll16", "shlr2", "shlr8", "shlr16"):
        return (EX, 1, [a[0]], [a[0]], set(), [])
    if op in ("shll", "shlr", "shal", "shar", "rotl", "rotr", "rotcl", "rotcr"):
        return (EX, 1, [a[0], "T"], [a[0], "T"], set(), [])
    if op == "dt":
        return (EX, 1, [a[0], "T"], [a[0]], set(), [])
    if op == "movt":
        return (EX, 1, [a[0]], ["T"], set(), [])
    if op in ("cmp/eq", "cmp/hs", "cmp/ge", "cmp/gt", "cmp/hi", "tst"):
        if a[0].startswith("#"):
            return (MT, 1, ["T"], [a[1]], set(), [])
        return (MT, 1, ["T"], [a[0], a[1]], set(), [])
    if op in ("cmp/pz", "cmp/pl"):
        return (MT, 1, ["T"], [a[0]], set(), [])
    if op == "lds":
        return (LS, 1, ["FPUL"], [a[0]], set(), [])
    if op == "sts":
        return (LS, 3, [a[1]], ["FPUL"], set(), [])
    if op == "flds":
        return (LS, 0, ["FPUL"], [a[0]], set(), [])
    if op == "float":
        return (FE, 3, [a[1]], ["FPUL"], set(), [])
    if op == "ftrc":
        return (FE, 3, ["FPUL"], [a[0]], set(), [])
    if op in ("fadd", "fmul", "fsub"):
        return (FE, 3, [a[1]], [a[0], a[1]], set(), [])
    if op == "fmac":
        return (FE, 3, [a[2]], [a[0], a[1], a[2]], set(), [])
    if op in ("fcmp/gt", "fcmp/eq"):
        return (FE, 2, ["T"], [a[0], a[1]], set(), [])
    if op in ("fldi0", "fldi1"):
        return (LS, 0, [a[0]], [], set(), [])
    if op in ("fabs", "fneg"):
        return (LS, 0, [a[0]], [a[0]], set(), [])
    if op == "fsrra":
        return (FE, 5, [a[0]], [a[0]], set(), [])
    if op == "fipr":
        m1, n1 = int(a[0][2:]), int(a[1][2:])
        return (FE, 4, [fr(n1 + 3)], fv(m1) + fv(n1), {"fipr"}, [])
    if op == "ftrv":
        n1 = int(a[1][2:])
        return (FE, 6, fv(n1), fv(n1) + ["XMTRX"], {"ftrv"}, [])
    if op in ("fschg", "frchg"):
        return (FE, 1, [], [], set(), [])
    if op in ("bt", "bf"):
        return (BR, 2, [], ["T"], {"brc"}, [])
    if op in ("bt/s", "bf/s"):
        return (BR, 2, [], ["T"], {"brcd"}, [])
    if op in ("bra",):
        return (BR, 2, [], [], {"bru"}, [])
    if op == "nop":
        return (MT, 1, [], [], set(), [])
    if op == "pref":
        return (LS, 1, [], regs_in(a[0]), set(), [])
    raise ValueError("unknown insn: " + ins)


def clean(lines):
    out = []
    for l in lines:
        l = l.split("!")[0].strip()
        if not l or l.endswith(":") or l.startswith("."):
            continue
        out.append(l)
    return out


def simulate(lines, iters=40, taken_last=True, verbose=False):
    """lines: loop body; the last-but-one or last insn is the back branch (bra + slot, or bt/bf).
    Returns steady-state cycles per iteration."""
    body = clean(lines)
    dec = [dec_cached(x) for x in body]
    rready = {}
    t_prev = 0.0
    prev_paired = True
    prev_grp = CO
    prev_def = set()
    prev_issue = 1
    f0_free = 0.0
    floor_t = 0.0
    br_t = -1
    starts = []
    trace = []
    for it in range(iters):
        starts.append(None)
        for i, (g, lat, defs, uses, kind, d2) in enumerate(dec):
            base = t_prev + prev_issue
            can_pair = (not prev_paired) and prev_grp != CO and g != CO and (g != prev_grp or g == MT) \
                and not (set(defs) & prev_def)
            dep = max([rready.get(u, 0.0) for u in uses] + [0.0])
            lockt = f0_free if ("ftrv" in kind or "fipr" in kind) else 0.0
            if can_pair and dep <= t_prev and lockt <= t_prev and floor_t <= t_prev:
                t = t_prev
                prev_paired = True
            else:
                t = max(base, floor_t, dep, lockt)
                prev_paired = False
            floor_t = 0.0
            if starts[-1] is None:
                starts[-1] = t
            for dd in defs:
                rready[dd] = t + lat
            for dd in d2:
                if dd not in defs:
                    rready[dd] = t + 1
            if "ftrv" in kind:
                f0_free = t + 4
            if "fipr" in kind:
                f0_free = t + 1
            if verbose and it == iters - 2:
                trace.append("%6.1f %s %s" % (t - starts[-1], "P" if prev_paired else " ", body[i]))
            last = i == len(dec) - 1
            # branches: assume the loop's last branch is taken; others not taken
            if "brcd" in kind or "bru" in kind:
                br_t = t
                br_i = i
            if last and taken_last:
                # redirect: delayed branch -> br_t + 2; plain bt/bf -> t + 2
                if "brc" in kind:
                    floor_t = t + 2
                else:
                    floor_t = max(br_t + 2, t + 1)
            t_prev = t
            prev_issue = 1
            prev_grp = g
            prev_def = set(defs)
    per = (starts[-1] - starts[-11]) / 10.0
    if verbose:
        print("\n".join(trace))
    return per


if __name__ == "__main__":
    txt = open(sys.argv[1]).read().splitlines()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print("cycles/iter %.2f  per vertex %.2f  insns %d" % (simulate(txt, verbose="-v" in sys.argv), simulate(txt) / n,
                                                           len(clean(txt))))


_dcache = {}


def dec_cached(x):
    d = _dcache.get(x)
    if d is None:
        d = _dcache[x] = decode(x)
    return d


def issue_time_last(seq):
    rready = {}
    t_prev = 0.0
    prev_paired = True
    prev_grp = CO
    prev_def = set()
    f0_free = 0.0
    t = 0.0
    for x in seq:
        g, lat, defs, uses, kind, d2 = dec_cached(x)
        base = t_prev + 1
        can_pair = (not prev_paired) and prev_grp != CO and g != CO and (g != prev_grp or g == MT) \
            and not (set(defs) & prev_def)
        dep = max([rready.get(u, 0.0) for u in uses] + [0.0])
        lockt = f0_free if ("ftrv" in kind or "fipr" in kind) else 0.0
        if can_pair and dep <= t_prev and lockt <= t_prev:
            t = t_prev
            prev_paired = True
        else:
            t = max(base, dep, lockt)
            prev_paired = False
        for dd in defs:
            rready[dd] = t + lat
        for dd in d2:
            if dd not in defs:
                rready[dd] = t + 1
        if "ftrv" in kind:
            f0_free = t + 4
        if "fipr" in kind:
            f0_free = t + 1
        t_prev = t
        prev_grp = g
        prev_def = set(defs)
    return t
