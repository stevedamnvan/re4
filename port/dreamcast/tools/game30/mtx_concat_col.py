#!/usr/bin/env python3
"""mtx_concat_col.py: design-logic P3 - generate a column-major, list-scheduled contract-off MTXConcat body.

Dataflow is exactly platform/mtx_sh4.S RE4DC_FP_CONTRACT_OFF (= GCC's contract-off C_MTXConcat), per element:
  j<3: ab_ij = add(n: add(n: mul(n a_i0, m b_0j), m: mul(n a_i1, m b_1j)), m: add(n: mul(n a_i2, m b_2j), m: +0))
       except ab_22 = add(n: add(n: +0, m: mul(a_22, b_22)), m: add(mul(a_20, b_02), mul(a_21, b_12)))
  j=3: ab_i3 = add(n: add(n: add(n: mul(a_i0,b_03), m: mul(a_i1,b_13)), m: mul(a_i2,b_23)), m: a_i3)
Only the instruction order, register allocation and addressing differ; tools/fpsym2.py --strict proves it.

Layout: b column j is loaded once (b_0j,b_1j,b_2j) and kept while rows 0..2 use it; each product's n
operand (a_ik) is loaded straight into the product register (the load replaces the old fmov copy).
LS 65 / FE 72 per call instead of 99 / 72. ab == a is computed into a 48-byte stack temporary (a is
re-read for every column); ab == b is safe in place (column j of b is loaded before column j of ab
is stored, and later columns never read earlier ones).

Registers: r1 = a cursor (a_00 a_01 a_02 [skip] a_10 ... ; column 3 reads rows whole), r2/r3/r5 = b row
cursors (b, b+16, b+32, post-increment per column), r6 = ab row 0 (+4 per column), r7 = ab row 1
(+4 per column), r0 = 16 (row 2 = @(r0,r7)); fr0-fr10 allocated by the scheduler, fr11 = +0.

usage: mtx_concat_col.py OUT.S [--label NAME] [--report]
"""
import sys, collections

OUT = sys.argv[1]
LABEL = '_re4dc_sh4_MTXConcat'
if '--label' in sys.argv:
    LABEL = sys.argv[sys.argv.index('--label') + 1]

# ------------------------------------------------------------------ virtual program
# instruction: dict(op, grp, defs=[vreg], uses=[vreg], ireg_use, ireg_def, fmt)
prog = []
vcount = [0]
def V(tag):
    vcount[0] += 1
    return '%s%d' % (tag, vcount[0])

def ins(op, grp, fmt, fdefs=(), fuses=(), iuses=(), idefs=(), lat=1, upd=None):
    prog.append(dict(op=op, grp=grp, fmt=fmt, fdefs=list(fdefs), fuses=list(fuses), iuses=list(iuses),
                     idefs=list(idefs), lat=lat, upd=upd))
    return len(prog) - 1

Z = 'Z'   # +0, pinned fr11

def load(ptr, v, post=True):
    # fmov.s @ptr+,v  (address update 1 cycle, data 2)
    if post:
        return ins('ld', 'LS', 'fmov.s\t@%s+,{d0}' % ptr, fdefs=[v], iuses=[ptr], idefs=[ptr], lat=2)
    return ins('ld', 'LS', 'fmov.s\t@%s,{d0}' % ptr, fdefs=[v], iuses=[ptr], lat=2)

def addi(reg, imm):
    return ins('add', 'EX', 'add\t#%d,%s' % (imm, reg), iuses=[reg], idefs=[reg], lat=1)

def fmul(n, m):   # n = n * m
    return ins('fmul', 'FE', 'fmul\t{u1},{d0}', fdefs=[n], fuses=[n, m], lat=3)

def fadd(n, m):   # n = n + m
    return ins('fadd', 'FE', 'fadd\t{u1},{d0}', fdefs=[n], fuses=[n, m], lat=3)

def store(v, where):
    return ins('st', 'LS', 'fmov.s\t{u0},%s' % where, fuses=[v], iuses=[w for w in ('r0', 'r6', 'r7') if w in where], lat=1)

for j in range(4):
    B = [V('b%d%d_' % (k, j)) for k in range(3)]
    for k, ptr in enumerate(('r2', 'r3', 'r5')):
        load(ptr, B[k])
    for i in range(3):
        P = [V('p%d%d%d_' % (i, j, k)) for k in range(3)]
        for k in range(3):
            load('r1', P[k])
            fmul(P[k], B[k])
        if j < 3:
            if i < 2:
                addi('r1', 4)             # skip a_i3
            else:
                addi('r1', -44)           # back to a_00 for the next column
        if j < 3:
            fadd(P[0], P[1])              # t = add(n p0, m p1)
            if (i, j) == (2, 2):
                W = V('w')
                ins('fmovz', 'LS', 'fmov\t{u0},{d0}', fdefs=[W], fuses=[Z], lat=1)
                fadd(W, P[2])             # w = add(n +0, m v)
                fadd(W, P[0])             # ab_22 = add(n w, m t)
                res = W
            else:
                fadd(P[2], Z)             # v = add(n v, m +0)
                fadd(P[0], P[2])          # ab = add(n t, m v)
                res = P[0]
        else:
            fadd(P[0], P[1])
            fadd(P[0], P[2])
            A3 = V('a%d3_' % i)
            load('r1', A3)                # column 3 reads a row whole: a_i3 follows a_i2
            fadd(P[0], A3)
            res = P[0]
        where = {0: '@r6', 1: '@r7', 2: '@(r0,r7)'}[i]
        store(res, where)
    if j < 3:
        addi('r6', 4)
        addi('r7', 4)

# ------------------------------------------------------------------ dependencies
N = len(prog)
preds = [set() for _ in range(N)]   # (pred, latency)
last_f_def = {}; f_readers = collections.defaultdict(list)
last_i_def = {}; i_readers = collections.defaultdict(list)
store_idx = []
for x, p in enumerate(prog):
    for u in p['fuses']:
        if u in last_f_def: preds[x].add((last_f_def[u], prog[last_f_def[u]]['lat']))
    for u in p['iuses']:
        if u in last_i_def: preds[x].add((last_i_def[u], 1))
    for d in p['fdefs']:
        # in-place redefinition of the same vreg: WAR against its readers since the last def
        for r in f_readers[d]:
            if r != x: preds[x].add((r, 0))
        if d in last_f_def and last_f_def[d] != x: preds[x].add((last_f_def[d], 1))
    for d in p['idefs']:
        for r in i_readers[d]:
            if r != x: preds[x].add((r, 0))
        if d in last_i_def and last_i_def[d] != x: preds[x].add((last_i_def[d], 1))
    # the order of stores between themselves is free (distinct addresses); loads never alias stores
    # except a == ab, which runs on a temporary (see the header)
    for u in p['fuses']: f_readers[u].append(x)
    for u in p['iuses']: i_readers[u].append(x)
    for d in p['fdefs']:
        last_f_def[d] = x; f_readers[d] = [r for r in f_readers[d] if r == x]
    for d in p['idefs']:
        last_i_def[d] = x; i_readers[d] = [r for r in i_readers[d] if r == x]
succs = [[] for _ in range(N)]
for x in range(N):
    for (q, l) in preds[x]: succs[q].append((x, l))
# priority: longest latency path to the end
prio = [0] * N
for x in reversed(range(N)):
    prio[x] = max([l + prio[s] for s, l in succs[x]] + [prog[x]['lat']])

# vreg lifetimes (for the physical allocator): last reader index of each vreg value
vreg_last_use = {}
for x, p in enumerate(prog):
    for u in p['fuses']: vreg_last_use[u] = x
    for d in p['fdefs']: vreg_last_use.setdefault(d, x)

# ------------------------------------------------------------------ list scheduler + allocator
def schedule(WIN, PRI):
    PHYS = ['fr%d' % k for k in range(11)]          # fr11 = +0
    phys_of = {Z: 'fr11'}
    free = list(PHYS)
    pending_free = []                                # (cycle_available, reg)
    ready_at = [None] * N
    done = [False] * N
    issue_cycle = [None] * N
    remaining_uses = collections.Counter()
    for p in prog:
        for u in p['fuses']: remaining_uses[u] += 1
    order = []
    cycle = 0
    def first_open():
        for y in range(N):
            if not done[y]: return y
        return N
    def is_new_def(x):
        p = prog[x]
        return [d for d in p['fdefs'] if d not in p['fuses'] and d not in phys_of]
    while len(order) < N:
        # release registers whose last reader issued before this cycle
        for (c, r) in list(pending_free):
            if c <= cycle:
                free.append(r); pending_free.remove((c, r))
        cand = []
        for x in range(N):
            if done[x]: continue
            if x - first_open() > WIN: break
            ok = True; t = 0
            for (q, l) in preds[x]:
                if not done[q]: ok = False; break
                t = max(t, issue_cycle[q] + l)
            if ok and t <= cycle: cand.append(x)
        cand.sort(key=lambda x: (-prio[x], x) if PRI else (x,))
        slot = []
        for x in cand:
            if len(slot) == 2: break
            p = prog[x]
            nd = is_new_def(x)
            if len(nd) > len(free) - sum(len(is_new_def(y)) for y in slot): continue
            if slot:
                f = prog[slot[0]]
                if f['grp'] == p['grp'] and f['grp'] != 'MT': continue
                wf = set(phys_of.get(d, 'new%s' % d) for d in f['fdefs']) | set(f['idefs'])
                rs = set(phys_of.get(u, u) for u in p['fuses']) | set(p['iuses'])
                ws = set(phys_of.get(d, 'new%s' % d) for d in p['fdefs']) | set(p['idefs'])
                if wf & (rs | ws): continue
                if 'r0' in wf and 'r0' in rs: continue
            slot.append(x)
        for x in slot:
            p = prog[x]
            for d in is_new_def(x):
                phys_of[d] = free.pop(0)
            done[x] = True; issue_cycle[x] = cycle; order.append(x)
            for u in p['fuses']:
                remaining_uses[u] -= 1
                if remaining_uses[u] == 0 and u != Z and u not in p['fdefs']:
                    pending_free.append((cycle + 1, phys_of[u]))
            for d in p['fdefs']:
                if remaining_uses[d] == 0 and d != Z:
                    pending_free.append((cycle + 1, phys_of[d]))   # dead after this def (stored later? no: stores use it)
        cycle += 1
        if cycle > 3000: return None
    return order, issue_cycle, phys_of, cycle

best = None
for WIN in (4, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64, 200):
    for PRI in (1, 0):
        r = schedule(WIN, PRI)
        if r and (best is None or r[3] < best[3]): best = r; bw = (WIN, PRI)
order, issue_cycle, phys_of, cycle = best
print('best window %s priority %s' % bw)

# a value defined by an in-place op keeps its register; fix the "dead after def" release for values still read
# (the Counter above only reaches 0 after the final reader, so a def with remaining readers is not released)

def fmt(x):
    p = prog[x]
    d0 = phys_of[p['fdefs'][0]] if p['fdefs'] else ''
    u0 = phys_of[p['fuses'][0]] if p['fuses'] else ''
    u1 = phys_of[p['fuses'][1]] if len(p['fuses']) > 1 else ''
    return p['fmt'].format(d0=d0, u0=u0, u1=u1)

body = []
for x in order:
    body.append('        %-28s/* c%d */' % (fmt(x), issue_cycle[x]))
sched_cycles = cycle

src = '''/* design-logic P3: contract-off MTXConcat, column-major + list-scheduled (generated by tools/game30/mtx_concat_col.py).
 * Same per-element dataflow and operand roles as the RE4DC_FP_CONTRACT_OFF row macro (see the generator);
 * proof: tools/game30/prove_concat_col.sh (fpsym2 --strict vs the build's own C_MTXConcat). Static schedule %d cycles. */
        .text
        .align  2
        .global %s
        .type   %s, @function
%s:                           /* r4 = a, r5 = b, r6 = ab */
        cmp/eq  r4,r6
        mov     r4,r1           /* a cursor */
        bf/s    1f
        mov     r5,r2           /* b row 0 cursor */
        add     #-48,r15        /* ab == a: compute into a stack temporary (a is re-read per column) */
        mov     r15,r6
1:      mov     r5,r3
        add     #16,r3          /* b row 1 cursor */
        add     #32,r5          /* b row 2 cursor */
        mov     r6,r7
        add     #16,r7          /* ab row 1 (row 2 = @(r0,r7)) */
        mov     #16,r0
        fldi0   fr11            /* +0 */
%s
        bt      2f              /* T from the entry cmp/eq r4,r6 (nothing in the body writes T): ab == a */
        rts
        nop
2:      mov     r15,r1          /* the temporary */
        mov     r4,r2           /* ab (== a) */
        fmov.s  @r1+,fr0
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr4
        fmov.s  @r1+,fr5
        fmov.s  @r1+,fr6
        fmov.s  @r1+,fr7
        fmov.s  @r1+,fr8
        fmov.s  @r1+,fr9
        fmov.s  @r1+,fr10
        fmov.s  @r1+,fr11
        add     #48,r2
        fmov.s  fr11,@-r2
        fmov.s  fr10,@-r2
        fmov.s  fr9,@-r2
        fmov.s  fr8,@-r2
        fmov.s  fr7,@-r2
        fmov.s  fr6,@-r2
        fmov.s  fr5,@-r2
        fmov.s  fr4,@-r2
        fmov.s  fr3,@-r2
        fmov.s  fr2,@-r2
        fmov.s  fr1,@-r2
        fmov.s  fr0,@-r2
        rts
        add     #48,r15
        .size   %s, .-%s
''' % (sched_cycles, LABEL, LABEL, LABEL, '\n'.join(body), LABEL, LABEL)
open(OUT, 'w').write(src)
grp = collections.Counter(p['grp'] for p in prog)
print('insns %d (%s), static schedule %d cycles' % (N, dict(grp), sched_cycles))
