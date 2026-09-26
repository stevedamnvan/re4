#!/usr/bin/env python3
"""mtx_inverse_sched.py: lane gskel - generate a list-scheduled contract-off MTXInverse body (GAME_MTXINV_SCHED).

Dataflow is exactly the RE4DC_FP_CONTRACT_OFF _re4dc_sh4_MTXInverse in platform/mtx_sh4.S (= GCC's contract-off
C_MTXInverse; mul(n, m) = fmul m,n, sub(n, m) = fsub m,n):
  det = sub(sub(sub(add(add(mul(mul(s00,s11),s22), mul(mul(s01,s12),s20)), mul(mul(s02,s10),s21)),
            mul(mul(s20,s11),s02)), mul(mul(s10,s01),s22)), mul(mul(s00,s21),s12))
  fcmp/eq +0,det -> return 0 with inv untouched;  r = div(1, det)
  mij = mul([neg](sub(mul(a,b), mul(c,d))), r)  (the nine cofactors of the header comment there)
  mi3 = sub(sub(mul(neg(mi0), s03), mul(mi1, s13)), mul(mi2, s23))
Only the instruction order, register allocation and addressing differ. Options:
  --nocse   (used for GAME_MTXINV_SCHED) no sharing; without it, an inner product that the determinant and a
            cofactor both compute (mul(s00,s11), mul(s01,s12), mul(s20,s11), mul(s10,s01), mul(s00,s21):
            the same instruction on the same operands in the same roles) is computed once and copied.
  --save K  (used: 4) fr12..fr12+K-1 are pushed when the scheduler wants them and popped after their last
            use and on the det == 0 exit (fpsym2 checks stack balance and fr12-fr15 on every path).
  --planb / --reload  cofactors after the branch / mi0..mi2 re-read from inv (register-poor variants).
  --tries N --local N --seed S  randomised list scheduling, then a local search on the priorities.
The cofactor products and differences do not depend on the determinant; they may issue before the
det == 0 branch (registers only). Stores, 1/det and everything after it come after the branch.
A source is used in place (no copy) only as the n operand of its last read.
tools/game30/prove_mtxinv_sched.sh proves the result (fpsym2 --strict vs the old body, commutative vs the
build's own C_MTXInverse).

In place (src == inv): the nine rotation values are loaded before the branch, so before any store; s03 /
s13 / s23 are loaded before any column-3 store; mi0..mi2 stay in registers (the old body re-read them).

Registers: r4 = src cursor (s00..s22 with @r4+, then back to s23 / s13 / s03), r5 = inv, r0 = store
offset, r15 = the pushes; fr0-fr11 and the pushed fr12.. allocated by the scheduler.

The model is tools/hwmodel/hwsim.c's in-order dual issue. GAME_MTXINV_SCHED's body was generated with
  mtx_inverse_sched.py OUT.S --tries 1500 --local 6000 --save 4 --nocse --seed 3
(static 86 cycles; hwsim with perfect caches over the kbench.py path: 89 cycles per call, the old body 228).

usage: mtx_inverse_sched.py OUT.S [--label NAME] [--nocse] [--noinplace] [--save K] [--planb] [--reload]
                            [--tries N] [--local N] [--seed S]
"""
import sys, collections

OUT = sys.argv[1]
LABEL = '_re4dc_sh4_MTXInverse'
if '--label' in sys.argv:
    LABEL = sys.argv[sys.argv.index('--label') + 1]
CSE = '--nocse' not in sys.argv
INPLACE = '--noinplace' not in sys.argv

PLANB = '--planb' in sys.argv      # cofactors after the branch, each stored at once; mi0..mi2 re-read
RELOAD = PLANB or '--reload' in sys.argv
prog = []
EXTRA_X = []
def ins(op, grp, fmt, fdefs=(), fuses=(), iuses=(), idefs=(), lat=1, xdefs=(), xuses=(), note=''):
    prog.append(dict(op=op, grp=grp, fmt=fmt, fdefs=list(fdefs), fuses=list(fuses), iuses=list(iuses),
                     idefs=list(idefs), lat=lat, xdefs=list(xdefs), xuses=list(xuses) + EXTRA_X, note=note))
    return len(prog) - 1

def load(v, post=True, note='', ptr='r4'):
    if post:
        return ins('ld', 'LS', 'fmov.s\t@%s+,{d0}' % ptr, fdefs=[v], iuses=[ptr], idefs=[ptr], lat=2, note=note)
    return ins('ld', 'LS', 'fmov.s\t@%s,{d0}' % ptr, fdefs=[v], iuses=[ptr], lat=2, note=note)
def addi(reg, imm):
    return ins('add', 'EX', 'add\t#%d,%s' % (imm, reg), iuses=[reg], idefs=[reg], lat=1)
def copy(dst, src):     # fmov src,dst (LS, result at once)
    return ins('fmov', 'LS', 'fmov\t{u0},{d0}', fdefs=[dst], fuses=[src], lat=0)
def fmul(n, m, note=''):     # n = mul(n, m)
    return ins('fmul', 'FE', 'fmul\t{u1},{d0}', fdefs=[n], fuses=[n, m], lat=3, note=note)
def fadd(n, m, note=''):
    return ins('fadd', 'FE', 'fadd\t{u1},{d0}', fdefs=[n], fuses=[n, m], lat=3, note=note)
def fsub(n, m, note=''):
    return ins('fsub', 'FE', 'fsub\t{u1},{d0}', fdefs=[n], fuses=[n, m], lat=3, note=note)
def fneg(n):
    return ins('fneg', 'LS', 'fneg\t{d0}', fdefs=[n], fuses=[n], lat=0)
def store(v, off, note=''):
    if off == 0:
        return ins('st', 'LS', 'fmov.s\t{u0},@r5', fuses=[v], iuses=['r5'], xuses=['BR'], lat=1, note=note)
    ins('movr0', 'EX', 'mov\t#%d,r0' % off, idefs=['r0'], xuses=['BR'], lat=1)
    return ins('st', 'LS', 'fmov.s\t{u0},@(r0,r5)', fuses=[v], iuses=['r0', 'r5'], xuses=['BR'], lat=1, note=note)

SAVE = int(sys.argv[sys.argv.index('--save') + 1]) if '--save' in sys.argv else 0
# --save K: fr12 .. fr12+K-1 (callee-saved) pushed on the stack when the scheduler wants them, popped after
# their last use (placed into free LS slots by the post-pass below)
for k in range(SAVE):
    ins('save', 'LS', 'fmov.s\t{u0},@-r15', fuses=['__fr%d' % (12 + k)], iuses=['r15'], idefs=['r15'], lat=1)
S = {}
if RELOAD:
    ins('mov', 'MT', 'mov\tr5,r6', iuses=['r5'], idefs=['r6'], lat=0)   # inv cursor for re-reading mi0..mi2
# ---- the nine rotation values (r4 walks the rows, skipping column 3)
for i in range(3):
    for j in range(3):
        S[(i, j)] = 's%d%d' % (i, j)
        load(S[(i, j)], note='s%d%d' % (i, j))
    if i < 2:
        addi('r4', 4)
s = lambda i, j: S[(i, j)]

n_uses = collections.Counter()
# pass 1: count n-operand uses per source (products whose n operand is a source)
PRODS_DET = [((0, 0), (1, 1), (2, 2)), ((0, 1), (1, 2), (2, 0)), ((0, 2), (1, 0), (2, 1)),
             ((2, 0), (1, 1), (0, 2)), ((1, 0), (0, 1), (2, 2)), ((0, 0), (2, 1), (1, 2))]
# (i, j, a, b, c, d, neg): m_ij = mul([neg](sub(mul(a,b), mul(c,d))), r)
COF = [(0, 0, (2, 2), (1, 1), (2, 1), (1, 2), 0),
       (0, 1, (0, 1), (2, 2), (2, 1), (0, 2), 1),
       (0, 2, (0, 1), (1, 2), (1, 1), (0, 2), 0),
       (1, 0, (1, 0), (2, 2), (2, 0), (1, 2), 1),
       (1, 1, (0, 0), (2, 2), (2, 0), (0, 2), 0),
       (1, 2, (0, 0), (1, 2), (1, 0), (0, 2), 1),
       (2, 0, (1, 0), (2, 1), (2, 0), (1, 1), 0),
       (2, 1, (0, 0), (2, 1), (2, 0), (0, 1), 1),
       (2, 2, (0, 0), (1, 1), (1, 0), (0, 1), 0)]
det_inner = {}
for k, (a, b, c) in enumerate(PRODS_DET):
    det_inner[(a, b)] = k
shared = {}   # (a, b) -> det product index, for cofactor products equal to a det inner product
for (i, j, a, b, c, d, neg) in COF:
    for (x, y) in ((a, b), (c, d)):
        if CSE and (x, y) in det_inner:
            shared[(x, y)] = det_inner[(x, y)]
# every read of a source (n or m operand) in emission order; a source is used in place (no copy) only
# as the n operand of its very last read
for (a, b, c) in PRODS_DET:
    for x in (a, b, c):
        n_uses[s(*x)] += 1
for (i, j, a, b, c, d, neg) in COF:
    for (x, y) in ((a, b), (c, d)):
        if (x, y) not in shared:
            n_uses[s(*x)] += 1
            n_uses[s(*y)] += 1

uses_left = dict(n_uses)
vc = [0]
def V(tag):
    vc[0] += 1
    return '%s_%d' % (tag, vc[0])
def nsrc(src):
    uses_left[src] -= 1
    if INPLACE and uses_left[src] == 0:
        return src
    v = V('c' + src)
    copy(v, src)
    return v
def msrc(src):
    uses_left[src] -= 1
    assert uses_left[src] >= 0
    return src

# ---- determinant
inner = {}
T = []
for k, (a, b, c) in enumerate(PRODS_DET):
    p = nsrc(s(*a))
    fmul(p, msrc(s(*b)), note='mul(s%d%d,s%d%d)' % (a + b))
    if (a, b) in shared:
        keep = V('p')
        copy(keep, p)          # the cofactor's copy of the shared inner product
        inner[(a, b)] = keep
    fmul(p, msrc(s(*c)), note='T%d' % (k + 1))
    T.append(p)
acc = T[0]
fadd(acc, T[1]); fadd(acc, T[2]); fsub(acc, T[3]); fsub(acc, T[4]); fsub(acc, T[5], note='det')
Z = V('zero')
ins('fldi0', 'LS', 'fldi0\t{d0}', fdefs=[Z], lat=0)
ins('fcmp', 'FE', 'fcmp/eq\t{u0},{u1}', fuses=[Z, acc], xdefs=['T'], lat=2)
ins('bt', 'BR', 'bt\t9f', xuses=['T'], xdefs=['BR'], lat=1)

# ---- cofactor differences (independent of det)
if PLANB:
    R = V('one')
    ins('fldi1', 'LS', 'fldi1\t{d0}', fdefs=[R], lat=0)
    ins('fdiv', 'FE', 'fdiv\t{u1},{d0}', fdefs=[R], fuses=[R, acc], xuses=['BR'], lat=12, note='r = 1/det')
    EXTRA_X.append('BR')
D = {}
STORE = {}
for (i, j, a, b, c, d, neg) in COF:
    if (a, b) in inner:
        x = inner[(a, b)]
    else:
        x = nsrc(s(*a)); fmul(x, msrc(s(*b)), note='mul(s%d%d,s%d%d)' % (a + b))
    if (c, d) in inner:
        y = inner[(c, d)]
    else:
        y = nsrc(s(*c)); fmul(y, msrc(s(*d)), note='mul(s%d%d,s%d%d)' % (c + d))
    fsub(x, y, note='d%d%d' % (i, j))
    if neg:
        fneg(x)
    D[(i, j)] = x
    if PLANB:
        fmul(x, R, note='m%d%d' % (i, j))
        STORE[(i, j)] = store(x, 16 * i + 4 * j, note='m%d%d' % (i, j))
del EXTRA_X[:]

# ---- r = 1 / det (after the branch), the cofactors
if not PLANB:
    R = V('one')
    ins('fldi1', 'LS', 'fldi1\t{d0}', fdefs=[R], lat=0)
    ins('fdiv', 'FE', 'fdiv\t{u1},{d0}', fdefs=[R], fuses=[R, acc], xuses=['BR'], lat=12, note='r = 1/det')
    for (i, j, a, b, c, d, neg) in COF:
        fmul(D[(i, j)], R, note='m%d%d' % (i, j))
        STORE[(i, j)] = store(D[(i, j)], 16 * i + 4 * j, note='m%d%d' % (i, j))

# ---- column 3: s23 = @r4 (r4 = src + 44), s13, s03 walking back
C3 = {}
C3[2] = V('s23'); c3l = [load(C3[2], post=False, note='s23')]
addi('r4', -16); C3[1] = V('s13'); c3l.append(load(C3[1], post=False, note='s13'))
addi('r4', -16); C3[0] = V('s03'); c3l.append(load(C3[0], post=False, note='s03'))
c3st = []
memdeps = []    # (store, load) pairs: the re-read after the store of the same word
for i in range(3):
    if RELOAD:
        mi = []
        for j in range(3):
            v = V('m%d%d' % (i, j))
            memdeps.append((STORE[(i, j)], load(v, ptr='r6', note='m%d%d' % (i, j))))
            mi.append(v)
        if i < 2:
            addi('r6', 4)
        x, y, w = mi
    else:
        x, y, w = D[(i, 0)], D[(i, 1)], D[(i, 2)]
    fneg(x)                     # neg(mi0) (in place after mi0's store)
    fmul(x, C3[0])
    fmul(y, C3[1])
    fsub(x, y)
    fmul(w, C3[2])
    fsub(x, w, note='m%d3' % i)
    c3st.append(store(x, 16 * i + 12, note='m%d3' % i))

# ------------------------------------------------------------------ dependencies
N = len(prog)
preds = [set() for _ in range(N)]
last_f_def = {}; f_readers = collections.defaultdict(list)
last_i_def = {}; i_readers = collections.defaultdict(list)
last_x_def = {}
for x, p in enumerate(prog):
    for u in p['fuses']:
        if u in last_f_def: preds[x].add((last_f_def[u], prog[last_f_def[u]]['lat']))
    for u in p['iuses']:
        if u in last_i_def:
            q = last_i_def[u]
            preds[x].add((q, 1))
    for u in p['xuses']:
        if u in last_x_def: preds[x].add((last_x_def[u], prog[last_x_def[u]]['lat']))
    for d in p['fdefs']:
        for r in f_readers[d]:
            if r != x: preds[x].add((r, 0))
        if d in last_f_def and last_f_def[d] != x: preds[x].add((last_f_def[d], 1))
    for d in p['idefs']:
        for r in i_readers[d]:
            if r != x: preds[x].add((r, 0))
        if d in last_i_def and last_i_def[d] != x: preds[x].add((last_i_def[d], 1))
    for u in p['fuses']: f_readers[u].append(x)
    for u in p['iuses']: i_readers[u].append(x)
    for d in p['fdefs']:
        last_f_def[d] = x; f_readers[d] = [r for r in f_readers[d] if r == x]
    for d in p['idefs']:
        last_i_def[d] = x; i_readers[d] = [r for r in i_readers[d] if r == x]
    for d in p['xdefs']:
        last_x_def[d] = x
# in place: every column-3 store after the three column-3 loads
for st in c3st:
    for l in c3l:
        preds[st].add((l, 0))
for (st, ld) in memdeps:
    preds[ld].add((st, 1))
succs = [[] for _ in range(N)]
for x in range(N):
    for (q, l) in preds[x]: succs[q].append((x, l))
prio = [0] * N
for x in reversed(range(N)):
    prio[x] = max([l + prio[s_] for s_, l in succs[x]] + [prog[x]['lat']])

# ------------------------------------------------------------------ list scheduler + allocator
# In-order dual issue as tools/hwmodel/hwsim.c models it: two instructions per cycle from different groups
# (MT pairs with anything), no register written by the first and read or written by the second; results
# after lat cycles (loads 2, fadd/fsub/fmul 3, fcmp -> T 2, fdiv 12, fmov/fneg/fldi 0, EX 1).
# Randomised list scheduling (critical-path priority plus noise) with a register reserve for instructions
# ahead of the program-order head; the shortest complete schedule of --tries attempts is kept.
import random
TRIES = int(sys.argv[sys.argv.index('--tries') + 1]) if '--tries' in sys.argv else 3000
SEED = int(sys.argv[sys.argv.index('--seed') + 1]) if '--seed' in sys.argv else 1
total_uses = collections.Counter()
for p in prog:
    for u in p['fuses']: total_uses[u] += 1
newdefs = [[d for d in p['fdefs'] if d not in p['fuses']] for p in prog]

def schedule(WIN, pr, RES, limit):
    PHYS = ['fr%d' % k for k in range(12)]
    phys_of = dict(('__fr%d' % (12 + k), 'fr%d' % (12 + k)) for k in range(SAVE))
    free = list(PHYS)
    pending_free = []
    done = [False] * N
    issue_cycle = [None] * N
    remaining_uses = collections.Counter(total_uses)
    order = []
    cycle = 0
    head = 0
    while len(order) < N:
        if pending_free:
            keep = []
            for (c, r) in pending_free:
                if c <= cycle: free.append(r)
                else: keep.append((c, r))
            pending_free = keep
        while head < N and done[head]: head += 1
        # program-order head of the instructions that need a new register
        nh = head
        while nh < N and (done[nh] or not newdefs[nh]): nh += 1
        cand = []
        for x in range(head, min(N, head + WIN + 1)):
            if done[x]: continue
            ok = True; t = 0
            for (q, l) in preds[x]:
                if not done[q]: ok = False; break
                t = max(t, issue_cycle[q] + l)
            if ok and t <= cycle: cand.append(x)
        cand.sort(key=lambda x: -pr[x])
        slot = []
        used_new = 0
        for x in cand:
            if len(slot) == 2: break
            p = prog[x]
            nd = [d for d in newdefs[x] if d not in phys_of]
            if nd:
                need = len(nd) + (0 if x == nh else RES)
                if need > len(free) - used_new: continue
            if slot:
                f = prog[slot[0]]
                if f['grp'] == p['grp'] and f['grp'] != 'MT': continue
                wf = set(phys_of.get(d, 'new%s' % d) for d in f['fdefs']) | set(f['idefs']) | set(f['xdefs'])
                rs = set(phys_of.get(u, u) for u in p['fuses']) | set(p['iuses']) | set(p['xuses'])
                ws = set(phys_of.get(d, 'new%s' % d) for d in p['fdefs']) | set(p['idefs']) | set(p['xdefs'])
                if wf & (rs | ws): continue
            slot.append(x)
            used_new += len(nd)
        for x in slot:
            p = prog[x]
            for d in newdefs[x]:
                if d not in phys_of:
                    phys_of[d] = free.pop(0)
            done[x] = True; issue_cycle[x] = cycle; order.append(x)
            for u in p['fuses']:
                remaining_uses[u] -= 1
                if remaining_uses[u] == 0 and u not in p['fdefs']:
                    pending_free.append((cycle + 1, phys_of[u]))
            for d in p['fdefs']:
                if remaining_uses[d] == 0:
                    pending_free.append((cycle + 1, phys_of[d]))
        cycle += 1
        if cycle > limit: return None
    return order, issue_cycle, phys_of, cycle

rng = random.Random(SEED)
LOCAL = int(sys.argv[sys.argv.index('--local') + 1]) if '--local' in sys.argv else 4000
best = None
for k in range(TRIES):
    WIN = rng.choice((4, 8, 12, 16, 24, 32, 48, 64, 200))
    noise = rng.choice((0, 0.5, 1, 2, 4, 8))
    RES = rng.choice((0, 1, 2, 3))
    pr = [prio[x] + rng.random() * noise for x in range(N)]
    r = schedule(WIN, pr, RES, best[3] if best else 400)
    if r and (best is None or r[3] < best[3]): best = r; bw = [WIN, noise, RES, k]; bpr = pr
if best is None:
    sys.exit('no schedule')
# local search on the priority vector of the best schedule (equal length accepted: drift across plateaus)
cur = list(bpr); curlen = best[3]
for k in range(LOCAL):
    pr = list(cur)
    for _ in range(rng.choice((1, 2, 3, 5, 8))):
        x = rng.randrange(N)
        pr[x] += rng.uniform(-6, 6)
    r = schedule(bw[0], pr, bw[2], curlen)
    if r and r[3] <= curlen:
        cur = pr; curlen = r[3]
        if r[3] < best[3]:
            best = r; bw[3] = 'local %d' % k
order, issue_cycle, phys_of, cycle = best

def fmt(x):
    p = prog[x]
    d0 = phys_of[p['fdefs'][0]] if p['fdefs'] else ''
    u0 = phys_of[p['fuses'][0]] if p['fuses'] else ''
    u1 = phys_of[p['fuses'][1]] if len(p['fuses']) > 1 else ''
    return p['fmt'].format(d0=d0, u0=u0, u1=u1)

rows = []          # (cycle, position in the cycle, text, group, phys regs written, phys regs read)
per_cycle = collections.defaultdict(list)
last_ref = collections.Counter()
for x in order:
    p = prog[x]
    note = p['note']
    w = set(phys_of[d] for d in p['fdefs']) | set(p['idefs'])
    r_ = set(phys_of[u] for u in p['fuses']) | set(p['iuses'])
    per_cycle[issue_cycle[x]].append((p['grp'], w, r_))
    for reg in w | r_:
        last_ref[reg] = max(last_ref[reg], issue_cycle[x])
    rows.append((issue_cycle[x], len(per_cycle[issue_cycle[x]]) - 1,
                 '        %-24s/* c%d%s */' % (fmt(x), issue_cycle[x], (' ' + note) if note else '')))
# pops, LIFO (fr12 was pushed first): each after the last reference of its register and the previous pop,
# in a cycle whose single instruction is not LS and does not touch the register or r15
bcyc = issue_cycle[[x for x in range(N) if prog[x]['op'] == 'bt'][0]]
t_prev = bcyc
for k in reversed(range(SAVE)):
    reg = 'fr%d' % (12 + k)
    c = max(last_ref[reg] + 1, t_prev + 1)
    while True:
        slot = per_cycle.get(c, [])
        if len(slot) == 0:
            break
        if len(slot) == 1 and slot[0][0] != 'LS' and not ((slot[0][1] | slot[0][2]) & {reg, 'r15'}):
            break
        c += 1
    per_cycle[c].append(('LS', {reg, 'r15'}, {'r15'}))
    rows.append((c, len(per_cycle[c]) - 1, '        %-24s/* c%d pop */' % ('fmov.s\t@r15+,%s' % reg, c)))
    t_prev = c
rows.sort()
cycle = max(cycle, t_prev + 1)
body = [r[2] for r in rows]
grp = collections.Counter(p['grp'] for p in prog)
# det == 0 exit: pop what was pushed before the branch (LIFO)
bt_row = [i for i, r in enumerate(rows) if 'bt\t9f' in r[2]][0]
pushed = [i for i, r in enumerate(rows) if '@-r15' in r[2] and i < bt_row]
zero_pops = ''.join('        fmov.s\t@r15+,fr%d\n' % (12 + k) for k in reversed(range(len(pushed))))
src = '''/* lane gskel GAME_MTXINV_SCHED: contract-off MTXInverse, list-scheduled (generated by
 * tools/game30/mtx_inverse_sched.py%s). Same dataflow and operand roles as the RE4DC_FP_CONTRACT_OFF body
 * below (see the generator); proof:
 * tools/game30/prove_mtxinv_sched.sh (fpsym2 --strict vs the build's own C_MTXInverse, every alias
 * partition). Static schedule %d cycles (branch at c%d), %d instructions. */
        .align  2
        .global %s
        .type   %s, @function
%s:                     /* r4 = src, r5 = inv */
%s
        rts
        mov     #1,r0
9:
%s        rts
        mov     #0,r0           /* det == 0: inv untouched */
        .size   %s, . - %s
''' % ((' ' + ' '.join(a for a in sys.argv[2:])) if len(sys.argv) > 2 else '', cycle, bcyc,
       N + SAVE + 4 + len(pushed), LABEL, LABEL, LABEL, '\n'.join(body), zero_pops, LABEL, LABEL)
open(OUT, 'w').write(src)
print('best window %s noise %s reserve %s try %s; insns %d (%s), static schedule %d cycles, branch at c%d' % (bw[0], bw[1], bw[2], bw[3], N, dict(grp), cycle, bcyc))
