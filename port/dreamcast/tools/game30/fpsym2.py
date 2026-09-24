#!/usr/bin/env python3
"""fpsym2: symbolic equivalence prover for SH-4 functions (game30, D367).

Extends the logic agent's fpsym.py (straight-line only) to whole functions:

  * every path is explored: conditional branches on pointer equality are decided per
    *alias partition* of the pointer arguments (each partition of {r4..r7} into equal
    classes is run separately; distinct classes are assumed not to overlap), branches on
    FP comparisons fork with a recorded predicate (fcmp/eq, fcmp/gt, __unordsf2);
  * calls through literal pools are followed into the callee (same ELF), except a small
    table of opaque library functions (sqrtf, sinf, ...) that become uninterpreted terms;
  * memory is modelled: stores to argument regions are what the function "returns", loads
    see earlier stores (so in-place / aliased calls are proved too), stack spills round-trip,
    reads of .rodata constants become their bit patterns, other globals are named leaves
    (symbol+offset, so two different links compare equal);
  * FP arithmetic builds expression trees. --strict keeps operand order exactly (fmul a,b
    and fmul b,a differ; fmac product roles FR0 vs FRm differ): identical trees then mean
    the same instructions on the same operands, i.e. identical bits on any IEEE
    implementation including NaN-payload propagation. Without --strict, the operands of
    fmul/fadd and of the fmac product are sorted (commutative; differs only in which NaN
    payload survives when BOTH operands are NaN on a host FPU that propagates payloads).

Result per partition: for every pair of feasible paths (A-path, B-path) whose predicate sets
are jointly consistent, the final argument-memory maps and return values must be identical.

usage:
  fpsym2.py ELF_A FUNC_A ELF_B FUNC_B --args p,p,p [--fargs 1] [--ret void|int|float] [--strict]
            [--maxdepth N]
  --args: kinds of r4..r7 in order (p = pointer, i = integer, e.g. 'p,i' for (Mtx, char))
"""
import argparse, itertools, re, struct, subprocess, sys

OBJDUMP = '/opt/toolchains/dc/sh-elf/bin/sh-elf-objdump'
NM = '/opt/toolchains/dc/sh-elf/bin/sh-elf-nm'

OPAQUE = {  # name: (float args, int args, returns)
    '_sqrtf': (1, 0, 'f'), '_sinf': (1, 0, 'f'), '_cosf': (1, 0, 'f'), '_tanf': (1, 0, 'f'),
    '_acosf': (1, 0, 'f'), '_asinf': (1, 0, 'f'), '_atan2f': (2, 0, 'f'), '_atanf': (1, 0, 'f'),
}

class Unsupported(Exception):
    pass

# ----------------------------------------------------------------------------- ELF access
class Elf:
    def __init__(self, path):
        self.path = path
        d = open(path, 'rb').read()
        self.data = d
        assert d[:4] == b'\x7fELF' and d[4] == 1 and d[5] == 1, 'ELF32 little-endian only'
        shoff, = struct.unpack_from('<I', d, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
        secs = []
        for i in range(shnum):
            name, typ, flags, addr, off, size = struct.unpack_from('<IIIIII', d, shoff + i * shentsize)
            secs.append([name, typ, flags, addr, off, size])
        strtab = secs[shstrndx]
        def nm(o):
            s = d[strtab[4] + o:]
            return s[:s.index(b'\0')].decode()
        self.sections = [(nm(s[0]), s[1], s[2], s[3], s[4], s[5]) for s in secs]
        self.syms = {}      # name -> (addr, size)
        self.byaddr = []    # sorted (addr, size, name) for data naming
        out = subprocess.run([NM, '-S', '-n', '--defined-only', path], capture_output=True, text=True).stdout
        for l in out.splitlines():
            p = l.split()
            if len(p) == 4:
                a, s, t, n = int(p[0], 16), int(p[1], 16), p[2], p[3]
            elif len(p) == 3:
                a, s, t, n = int(p[0], 16), 0, p[1], p[2]
            else:
                continue
            self.syms.setdefault(n, (a, s))
            self.byaddr.append((a, s, n, t))
        self.byaddr.sort()
        self._dis = {}

    def section_of(self, addr):
        for name, typ, flags, a, off, size in self.sections:
            if (flags & 2) and a <= addr < a + size:
                return name, typ, off + (addr - a)
        return None

    def read32(self, addr):
        s = self.section_of(addr)
        if not s or s[1] == 8:   # NOBITS
            return None
        return struct.unpack_from('<I', self.data, s[2])[0]

    def name_of(self, addr):
        best = None
        for a, s, n, t in self.byaddr:
            if a <= addr and (addr < a + max(s, 1)):
                best = (n, addr - a)
            if a > addr:
                break
        return best

    def func(self, name):
        if name in self._dis:
            return self._dis[name]
        out = subprocess.run([OBJDUMP, '-d', '--no-show-raw-insn', '--disassemble=' + name, self.path],
                             capture_output=True, text=True).stdout
        ins = {}
        on = False
        for l in out.splitlines():
            if re.match(r'^[0-9a-f]+ <%s>:' % re.escape(name), l):
                on = True; continue
            if on:
                m = re.match(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$', l)
                if m:
                    ins[int(m.group(1), 16)] = (m.group(2), m.group(3))
                elif re.match(r'^[0-9a-f]+ <', l):
                    break
        if not ins:
            raise Unsupported('function %s not found in %s' % (name, self.path))
        self._dis[name] = ins
        return ins

    def func_at(self, addr):
        for a, s, n, t in self.byaddr:
            if a == addr and t in 'Tt':
                return n
        return None

# ----------------------------------------------------------------------------- expressions
def norm(op, *a, strict=False):
    if not strict:
        if op in ('mul', 'add'):
            return (op,) + tuple(sorted(a, key=repr))
        if op == 'fma':
            return ('fma',) + tuple(sorted(a[:2], key=repr)) + (a[2],)
    return (op,) + a

ZERO = ('c', 0x00000000)
ONE = ('c', 0x3f800000)

def fconst_from_bits(bits):
    return ('c', bits)

class Path:
    """One execution state (copied on forks)."""
    def __init__(self):
        self.R = {}
        self.F = {}
        self.T = None
        self.fpul = None
        self.pr = None
        self.mem = {}          # (region, off) -> value (FP expr or int value); 4-byte granularity
        self.preds = []        # [(atom, bool)]
        self.macl = None

    def copy(self):
        p = Path()
        p.R = dict(self.R); p.F = dict(self.F); p.T = self.T; p.fpul = self.fpul; p.pr = self.pr
        p.mem = dict(self.mem); p.preds = list(self.preds); p.macl = self.macl
        return p

class Machine:
    def __init__(self, elf, strict, maxsteps=20000):
        self.elf = elf
        self.strict = strict
        self.maxsteps = maxsteps

    # values: ('ptr', region, off) | ('int', n) | ('sym', ...) | ('ret', depth)
    def region_ptr(self, v):
        if v and v[0] == 'ptr':
            return v[1], v[2]
        if v and v[0] == 'int':
            return ('abs', v[1])
        raise Unsupported('not a pointer: %r' % (v,))

    def addr_key(self, v):
        if v[0] == 'ptr':
            return (v[1], v[2])
        if v[0] == 'int':
            nm = self.elf.name_of(v[1])
            if nm is None:
                raise Unsupported('absolute address %x without a symbol' % v[1])
            return ('g:' + nm[0], nm[1])
        raise Unsupported('not an address: %r' % (v,))

    def load(self, p, key, fp):
        if key in p.mem:
            return p.mem[key]
        region, off = key
        if region.startswith('g:'):
            addr = self.elf.syms[region[2:]][0] + off
            sec = self.elf.section_of(addr)
            if sec and sec[0].startswith('.rodata'):
                w = self.elf.read32(addr)
                return fconst_from_bits(w) if fp else ('int', w)
        return ('ld', region, off)

    def store(self, p, key, val):
        p.mem[key] = val

    def reg(self, p, r):
        if r not in p.R:
            raise Unsupported('read of undefined %s' % r)
        return p.R[r]

    def freg(self, p, r):
        return p.F.get(r, ('undef', r))

    def cond_T(self, p):
        t = p.T
        if t is None:
            raise Unsupported('branch on undefined T')
        return t

    def decide(self, p, t):
        """Returns True/False when T is decidable, else None."""
        if t[0] == 'const':
            return t[1]
        if t[0] == 'eqv':           # integer/pointer equality
            a, b = t[1], t[2]
            if a == b:
                return True
            if a[0] == 'ptr' and b[0] == 'ptr':
                if a[1] != b[1]:
                    return False   # distinct alias classes (partition assumption)
                return a[2] == b[2]
            if a[0] == 'int' and b[0] == 'int':
                return a[1] == b[1]
            if a[0] == 'ptr' and b[0] == 'int' or a[0] == 'int' and b[0] == 'ptr':
                return False       # argument pointers are never absolute constants / NULL here
            return None
        if t[0] == 'not':
            v = self.decide(p, t[1])
            return None if v is None else (not v)
        return None

    def branch(self, p, want, target, delayed):
        t = self.cond_T(p)
        v = self.decide(p, t)
        if v is not None:
            if v == want:
                return ('delay', target) if delayed else ('jump', target)
            return None
        # symbolic predicate: fork
        atom = t
        taken = p.copy(); taken.preds.append((atom, want))
        fall = p.copy(); fall.preds.append((atom, not want))
        if delayed:
            return ('fork', [(taken, target, True), (fall, 'FALL', True)])
        return ('fork', [(taken, target, False), (fall, 'FALL', False)])

    def step(self, p, op, a, pc, fname, depth):
        A = [x.strip() for x in a.split(',')] if a else []
        # re-join @(r0,rN) / @(disp,rN) split by the comma
        B = []
        i = 0
        while i < len(A):
            x = A[i]
            if x.startswith('@(') and not x.endswith(')') and i + 1 < len(A):
                x = x + ',' + A[i + 1]; i += 1
            B.append(x); i += 1
        A = B
        R = p.R
        def ival(x):
            if x.startswith('#'):
                return ('int', int(x[1:]))
            return self.reg(p, x)
        def target():
            m = re.match(r'([0-9a-f]+)', a)
            return int(m.group(1), 16)
        def ea(x, size=4):
            """effective address for @rN, @rN+, @-rN, @(disp,rN), @(r0,rN); returns key and post-action"""
            m = re.match(r'^@-(r\d+)$', x)
            if m:
                r = m.group(1); v = self.reg(p, r)
                nv = self.add(v, -size); R[r] = nv
                return self.addr_key(nv)
            m = re.match(r'^@(r\d+)\+$', x)
            if m:
                r = m.group(1); v = self.reg(p, r)
                R[r] = self.add(v, size)
                return self.addr_key(v)
            m = re.match(r'^@(r\d+)$', x)
            if m:
                return self.addr_key(self.reg(p, m.group(1)))
            m = re.match(r'^@\((\d+),(r\d+)\)$', x)
            if m:
                return self.addr_key(self.add(self.reg(p, m.group(2)), int(m.group(1))))
            m = re.match(r'^@\(r0,(r\d+)\)$', x)
            if m:
                r0 = self.reg(p, 'r0'); base = self.reg(p, m.group(1))
                if r0[0] == 'int':
                    return self.addr_key(self.add(base, r0[1]))
                if base[0] == 'int':
                    return self.addr_key(self.add(r0, base[1]))
                raise Unsupported('indexed address with symbolic parts')
            raise Unsupported('addressing mode %s' % x)

        if op == 'nop':
            return None
        if op in ('.word', '.long'):
            raise Unsupported('executed data at %x in %s' % (pc, fname))
        # ---------------------------------------------------------------- integer moves
        if op == 'mov':
            if A[0].startswith('#'):
                R[A[1]] = ('int', int(A[0][1:]))
            else:
                R[A[1]] = self.reg(p, A[0])
            return None
        if op == 'mov.l':
            s, d = A
            m = re.match(r'^([0-9a-f]{8})\b', s)
            if m:      # pc-relative literal
                w = self.elf.read32(int(m.group(1), 16))
                R[d] = ('int', w)
                return None
            if s.startswith('@') and d.startswith('r'):
                R[d] = self.load(p, ea(s), False)
                return None
            if s.startswith('r') and d.startswith('@'):
                v = self.reg(p, s)
                self.store(p, ea(d), v)
                return None
            raise Unsupported('mov.l %s' % a)
        if op == 'mova':
            m = re.match(r'^([0-9a-f]{8})\b', A[0])
            R['r0'] = ('int', int(m.group(1), 16)); return None
        if op == 'sts.l' and A[0] == 'pr':
            self.store(p, ea(A[1]), p.pr); return None
        if op == 'lds.l' and A[1] == 'pr':
            p.pr = self.load(p, ea(A[0]), False); return None
        if op == 'sts' and A[0] == 'pr':
            R[A[1]] = p.pr; return None
        if op == 'lds' and A[1] == 'pr':
            p.pr = self.reg(p, A[0]); return None
        if op == 'add':
            if A[0].startswith('#'):
                R[A[1]] = self.add(self.reg(p, A[1]), int(A[0][1:]))
            else:
                x, y = self.reg(p, A[0]), self.reg(p, A[1])
                if x[0] == 'int':
                    R[A[1]] = self.add(y, x[1])
                elif y[0] == 'int':
                    R[A[1]] = self.add(x, y[1])
                else:
                    raise Unsupported('add of two symbolic values')
            return None
        if op in ('extu.b', 'exts.b', 'extu.w', 'exts.w'):
            v = self.reg(p, A[0])
            if v[0] == 'int':
                n = v[1]
                if op == 'extu.b': n &= 0xff
                elif op == 'extu.w': n &= 0xffff
                elif op == 'exts.b': n = ((n & 0xff) ^ 0x80) - 0x80
                else: n = ((n & 0xffff) ^ 0x8000) - 0x8000
                R[A[1]] = ('int', n)
            else:
                R[A[1]] = (op, v)
            return None
        # ---------------------------------------------------------------- compares/branches
        if op == 'cmp/eq':
            x, y = ival(A[0]), self.reg(p, A[1])
            p.T = ('eqv', x, y); return None
        if op == 'tst':
            x, y = self.reg(p, A[0]), self.reg(p, A[1])
            if A[0] == A[1] and x[0] == 'pred':     # tst r0,r0 after __unordsf2
                p.T = ('not', x[1]); return None
            if x[0] == 'int' and y[0] == 'int':
                p.T = ('const', (x[1] & y[1]) == 0); return None
            if A[0] == A[1]:
                p.T = ('eqv', x, ('int', 0)); return None
            raise Unsupported('tst %s' % a)
        if op in ('bt', 'bf', 'bt.s', 'bf.s', 'bt/s', 'bf/s'):
            want = op.startswith('bt')
            delayed = op.endswith('s') and len(op) > 2
            r = self.branch(p, want, target(), delayed)
            if r is None and delayed:
                return None   # not taken: the delay slot still executes as a normal instruction
            if r and r[0] == 'fork':
                # not taken: the delay slot (if any) runs as the next instruction, then pc+4
                return ('fork', [(q, pc + 2, False) if tgt == 'FALL' else (q, tgt, dl) for q, tgt, dl in r[1]])
            return r
        if op == 'bra':
            return ('delay', target())
        if op == 'rts':
            if depth > 0 or p.pr is not None and p.pr != ('ret', 0):
                pass
            return ('delay', 'RET')
        if op == 'jmp':
            t = self.reg(p, A[0][1:])
            callee = self.elf.func_at(t[1]) if t[0] == 'int' else None
            if callee is None:
                raise Unsupported('indirect jump %r' % (t,))
            return ('tail', callee)
        if op in ('jsr', 'bsr'):
            if op == 'jsr':
                t = self.reg(p, A[0][1:])
                if t[0] != 'int':
                    raise Unsupported('indirect call through %r' % (t,))
                addr = t[1]
            else:
                addr = target()
            callee = self.elf.func_at(addr)
            if callee is None:
                raise Unsupported('call to unknown address %x' % addr)
            return ('call', callee)
        # ---------------------------------------------------------------- FP
        if op == 'fldi0':
            p.F[A[0]] = ZERO; return None
        if op == 'fldi1':
            p.F[A[0]] = ONE; return None
        if op in ('fmov', 'fmov.s'):
            s, d = A
            if s.startswith('fr') and d.startswith('fr'):
                p.F[d] = self.freg(p, s); return None
            if s.startswith('@') and d.startswith('fr'):
                p.F[d] = self.load(p, ea(s), True); return None
            if s.startswith('fr') and d.startswith('@'):
                self.store(p, ea(d), self.freg(p, s)); return None
            raise Unsupported('fmov %s' % a)
        st = self.strict
        if op in ('fmul', 'fadd'):
            n = A[1]; m = A[0]
            p.F[n] = norm('mul' if op == 'fmul' else 'add', self.freg(p, n), self.freg(p, m), strict=st); return None
        if op == 'fsub':
            p.F[A[1]] = ('sub', self.freg(p, A[1]), self.freg(p, A[0])); return None
        if op == 'fdiv':
            p.F[A[1]] = ('div', self.freg(p, A[1]), self.freg(p, A[0])); return None
        if op == 'fmac':
            n = A[2]
            p.F[n] = norm('fma', self.freg(p, 'fr0'), self.freg(p, A[1]), self.freg(p, n), strict=st); return None
        if op in ('fneg', 'fabs', 'fsqrt', 'fsrra'):
            p.F[A[0]] = (op, self.freg(p, A[0])); return None
        if op == 'fcmp/eq':
            x, y = self.freg(p, A[1]), self.freg(p, A[0])
            p.T = self.fpred('EQ', x, y); return None
        if op == 'fcmp/gt':      # T = FRn > FRm
            x, y = self.freg(p, A[1]), self.freg(p, A[0])
            p.T = self.fpred('GT', x, y); return None
        if op == 'flds':
            p.fpul = self.freg(p, A[0]); return None
        if op == 'fsts':
            p.F[A[1]] = p.fpul; return None
        if op == 'lds' and A[1] == 'fpul':
            p.fpul = self.reg(p, A[0]); return None
        if op == 'sts' and A[0] == 'fpul':
            R[A[1]] = p.fpul; return None
        if op == 'float':
            p.F[A[1]] = ('float', p.fpul); return None
        if op == 'ftrc':
            p.fpul = ('ftrc', self.freg(p, A[0])); return None
        raise Unsupported('instruction %s %s at %x in %s' % (op, a, pc, fname))

    def fpred(self, rel, x, y):
        # canonical atom: ('fp', rel, lhs, rhs) with +0/-0 constants merged
        def z(e):
            return ZERO if e in (('c', 0), ('c', 0x80000000)) else e
        x, y = z(x), z(y)
        if rel == 'EQ' and repr(x) > repr(y):
            x, y = y, x
        return ('fp', rel, x, y)

    def add(self, v, n):
        if v[0] == 'ptr':
            return ('ptr', v[1], v[2] + n)
        if v[0] == 'int':
            return ('int', (v[1] + n) & 0xffffffff)
        raise Unsupported('arith on %r' % (v,))

# ----------------------------------------------------------------------------- driver
class Runner(Machine):
    """Adds call handling on top of Machine.step."""
    def run_fn(self, p, fname, depth=0):
        if depth > 8:
            raise Unsupported('call depth')
        ins = self.elf.func(fname)
        pc0 = min(ins)
        results = []
        stack = [(p, pc0, None)]
        steps = 0
        while stack:
            p, pc, pend = stack.pop()
            while True:
                steps += 1
                if steps > self.maxsteps:
                    raise Unsupported('step limit in %s' % fname)
                if pc not in ins:
                    raise Unsupported('pc %x outside %s' % (pc, fname))
                op, args = ins[pc]
                args = args.split('!')[0].strip()
                res = self.step(p, op, args, pc, fname, depth)
                if pend is not None:
                    tgt = pend; pend = None
                    if res is not None and res[0] != 'call':
                        raise Unsupported('branch in delay slot at %x' % pc)
                    if res is not None and res[0] == 'call':
                        raise Unsupported('call in delay slot')
                    if tgt == 'RET':
                        results.append(p); break
                    if isinstance(tgt, tuple) and tgt[0] == 'CALL':
                        # delayed call: now perform it
                        callee, back = tgt[1], tgt[2]
                        outs = self.call(p, callee, depth)
                        if back == 'RET':
                            results.extend(outs); break
                        for q in outs[1:]:
                            stack.append((q, back, None))
                        p = outs[0]; pc = back; continue
                    pc = tgt; continue
                if res is None:
                    pc += 2; continue
                k = res[0]
                if k == 'jump':
                    pc = res[1]; continue
                if k == 'delay':
                    pend = res[1]; pc += 2; continue
                if k == 'call':
                    pend = ('CALL', res[1], pc + 4); pc += 2; continue
                if k == 'tail':
                    pend = ('CALL', res[1], 'RET'); pc += 2; continue
                if k == 'fork':
                    for q, tgt, dl in res[1]:
                        if dl:
                            stack.append((q, pc + 2, tgt))
                        else:
                            stack.append((q, tgt, None))
                    break
                raise Unsupported(repr(res))
        return results

    def call(self, p, callee, depth):
        if callee in OPAQUE:
            nf, ni, rt = OPAQUE[callee]
            args = tuple(self.freg(p, 'fr%d' % (4 + i)) for i in range(nf)) + tuple(p.R.get('r%d' % (4 + i)) for i in range(ni))
            self.clobber(p)
            if rt == 'f':
                p.F['fr0'] = ('call', callee) + args
            return [p]
        if callee == '___unordsf2':
            x, y = self.freg(p, 'fr4'), self.freg(p, 'fr5')
            self.clobber(p)
            p.R['r0'] = ('pred', self.fpred('UN', x, y))
            return [p]
        saved_pr = p.pr
        p.pr = ('ret', depth + 1)
        outs = self.run_fn(p, callee, depth + 1)
        for q in outs:
            if q.pr != ('ret', depth + 1):
                raise Unsupported('callee %s did not restore pr' % callee)
            q.pr = saved_pr
        return outs

    def clobber(self, p):
        for r in ('r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7'):
            p.R.pop(r, None)
        for i in range(12):
            p.F.pop('fr%d' % i, None)
        p.T = None

def partitions(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for smaller in partitions(rest):
        for i in range(len(smaller)):
            yield smaller[:i] + [[first] + smaller[i]] + smaller[i + 1:]
        yield [[first]] + smaller

def execute(elf, fn, kinds, nfargs, part, strict, maxsteps):
    m = Runner(elf, strict, maxsteps)
    p = Path()
    cls = {}
    for i, blk in enumerate(part):
        for r in blk:
            cls[r] = 'M%d' % i
    for i, k in enumerate(kinds):
        r = 'r%d' % (4 + i)
        if k == 'p':
            p.R[r] = ('ptr', cls[r], 0)
        elif k == 'i':
            p.R[r] = ('sym', 'arg' + r)
        elif k.startswith('#'):
            p.R[r] = ('int', int(k[1:], 0))
    for i in range(nfargs):
        p.F['fr%d' % (4 + i)] = ('farg', i)
    p.R['r15'] = ('ptr', 'SP', 0)
    for r in ('r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14'):
        p.R[r] = ('callee_saved', r)
    for i in range(12, 16):
        p.F['fr%d' % i] = ('callee_saved', 'fr%d' % i)
    p.pr = ('ret', 0)
    outs = m.run_fn(p, fn, 0)
    res = []
    for q in outs:
        if q.pr != ('ret', 0):
            raise Unsupported('%s: pr not restored' % fn)
        if q.R.get('r15') != ('ptr', 'SP', 0):
            raise Unsupported('%s: stack not balanced: %r' % (fn, q.R.get('r15')))
        for r in ('r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14'):
            if q.R.get(r) != ('callee_saved', r):
                raise Unsupported('%s: callee-saved %s clobbered' % (fn, r))
        for i in range(12, 16):
            if q.F.get('fr%d' % i) != ('callee_saved', 'fr%d' % i):
                raise Unsupported('%s: callee-saved fr%d clobbered' % (fn, i))
        # a location rewritten with its own original contents is unchanged memory
        memout = {k: v for k, v in q.mem.items() if k[0] != 'SP' and v != ('ld', k[0], k[1])}
        res.append((q.preds, memout, q.R.get('r0'), q.F.get('fr0')))
    return res

def consistent(preds):
    """Is a set of FP predicate literals satisfiable? Pairs (lhs,rhs) are independent;
    each pair takes one relation class in {LT, EQ, GT, UN}."""
    by = {}
    for atom, val in preds:
        if atom[0] == 'not':
            atom, val = atom[1], not val
        if atom[0] != 'fp':
            by.setdefault(('opaque', atom), set()).add(val)
            continue
        _, rel, x, y = atom
        key = tuple(sorted([repr(x), repr(y)]))
        swapped = repr(x) > repr(y)
        by.setdefault(key, []).append((rel, swapped, val))
    for key, lits in by.items():
        if key[0] == 'opaque':
            if len(lits) > 1:
                return False
            continue
        ok = False
        for cls in ('LT', 'EQ', 'GT', 'UN'):
            good = True
            for rel, swapped, val in lits:
                c = cls
                if swapped:
                    c = {'LT': 'GT', 'GT': 'LT'}.get(c, c)
                if rel == 'EQ': truth = c == 'EQ'
                elif rel == 'GT': truth = c == 'GT'
                elif rel == 'UN': truth = c == 'UN'
                else: raise Unsupported(rel)
                if truth != val:
                    good = False; break
            if good:
                ok = True; break
        if not ok:
            return False
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('elfA'); ap.add_argument('fnA'); ap.add_argument('elfB'); ap.add_argument('fnB')
    ap.add_argument('--args', required=True)
    ap.add_argument('--fargs', type=int, default=0)
    ap.add_argument('--ret', default='void', choices=['void', 'int', 'float'])
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--maxsteps', type=int, default=20000)
    ap.add_argument('-v', action='store_true')
    a = ap.parse_args()
    kinds = a.args.split(',')
    ptrs = ['r%d' % (4 + i) for i, k in enumerate(kinds) if k == 'p']
    EA, EB = Elf(a.elfA), Elf(a.elfB)
    total_ok = True
    npaths = 0
    try:
        for part in partitions(ptrs):
            RA = execute(EA, a.fnA, kinds, a.fargs, part, a.strict, a.maxsteps)
            RB = execute(EB, a.fnB, kinds, a.fargs, part, a.strict, a.maxsteps)
            tag = ' '.join('{' + ','.join(b) + '}' for b in part)
            pairs = 0
            for pa in RA:
                for pb in RB:
                    if not consistent(pa[0] + pb[0]):
                        continue
                    pairs += 1
                    diffs = []
                    keys = set(pa[1]) | set(pb[1])
                    for k in sorted(keys, key=repr):
                        if pa[1].get(k) != pb[1].get(k):
                            diffs.append(('mem', k, pa[1].get(k), pb[1].get(k)))
                    if a.ret == 'int' and pa[2] != pb[2]:
                        diffs.append(('r0', pa[2], pb[2]))
                    if a.ret == 'float' and pa[3] != pb[3]:
                        diffs.append(('fr0', pa[3], pb[3]))
                    if diffs:
                        total_ok = False
                        print('partition %s: DIFF under predicates A=%r B=%r' % (tag, pa[0], pb[0]))
                        for d in diffs[:6]:
                            print('   ', d)
            npaths += pairs
            if a.v:
                print('partition %-16s A paths %d, B paths %d, consistent pairs %d' % (tag, len(RA), len(RB), pairs))
            if pairs == 0:
                total_ok = False
                print('partition %s: no consistent path pair' % tag)
    except Unsupported as e:
        print('UNSUPPORTED:', e)
        sys.exit(2)
    nA = len(EA.func(a.fnA)); nB = len(EB.func(a.fnB))
    print('%s (%d insn words) vs %s (%d insn words), %s mode, %d path pairs checked' %
          (a.fnA, nA, a.fnB, nB, 'strict' if a.strict else 'commutative', npaths))
    print('EQUIVALENT' if total_ok else 'NOT PROVEN EQUIVALENT')
    sys.exit(0 if total_ok else 1)

if __name__ == '__main__':
    main()
