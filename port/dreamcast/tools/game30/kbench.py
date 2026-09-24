#!/usr/bin/env python3
"""kbench.py ELF SYMBOL [ITER] [--taken bf,bf/s] : synthetic hwtrace for one straight-line kernel path.

Walks SYMBOL's disassembly from its entry: conditional branches listed in --taken (by mnemonic, first
occurrence order) are taken, others fall through; stops after the rts delay slot. Writes a hwtrace file
(type-1 run records only: pure issue model, run hwsim with --perfect-ic --perfect-dc) that repeats the
path ITER times, and prints the path. design-logic P3 kernel benchmark."""
import re, subprocess, struct, sys
elf, sym = sys.argv[1], sys.argv[2]
it = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else 1000
taken = sys.argv[sys.argv.index('--taken') + 1].split(',') if '--taken' in sys.argv else ['bf/s', 'bf']
taken = taken + [t.replace('/', '.') for t in taken]
NM = '/opt/toolchains/dc/sh-elf/bin/sh-elf-nm'; OD = '/opt/toolchains/dc/sh-elf/bin/sh-elf-objdump'
addr = None
for l in subprocess.run([NM, elf], capture_output=True, text=True).stdout.splitlines():
    p = l.split()
    if len(p) == 3 and p[2] == sym: addr = int(p[0], 16)
dis = subprocess.run([OD, '-d', '--start-address=%#x' % addr, '--stop-address=%#x' % (addr + 0x1000), elf],
                     capture_output=True, text=True).stdout
ins = {}
for l in dis.splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]{2} [0-9a-f]{2}\s+(\S+)\s*(.*)', l)
    if m: ins[int(m.group(1), 16)] = (m.group(2), m.group(3))
runs = []; pc = addr; start = addr; n = 0; steps = 0
while True:
    op, args = ins[pc]; n += 1; steps += 1
    if op in ('bf', 'bt', 'bf/s', 'bt/s', 'bf.s', 'bt.s'):
        tgt = int(args.split()[0], 16)
        if op in taken:
            if op.endswith('/s') or op.endswith('.s'):
                n += 1                       # delay slot
            runs.append((start, n)); start = pc = tgt; n = 0
            continue
    if op == 'rts':
        n += 1; runs.append((start, n)); break
    pc += 2
    if steps > 2000: raise SystemExit('no rts')
path = sum(r[1] for r in runs)
with open('kbench.trace.bin', 'wb') as f:
    for _ in range(it):
        for s, c in runs:
            f.write(struct.pack('<II', s, (1 << 28) | c))
print('%s: runs %s, %d instructions per call, %d iterations' % (sym, ['%x+%d' % r for r in runs], path, it))
