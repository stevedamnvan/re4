#!/usr/bin/env python3
"""gen_whatif.py: build what-if inputs for hwsim from a baseline run.

  gen_whatif.py --elf ELF --sim BASE_PREFIX --funcs functions.tsv --out DIR

Writes into DIR:
  icmap_func.txt   hot functions first, 32-byte aligned, in descending executed-instruction order
                   (linker ordering; -ffunction-sections + a section order file)
  icmap_lines.txt  only executed 32 B lines packed hot-first (upper bound for hot/cold block splitting)
  render_fdiv.txt  PC ranges of render-only functions (areas actors/scenery/ui/ta-submit) for the
                   FDIV -> FSRRA what-if
  copies.txt       PC ranges of copy functions (area copies) for the copy-removal bound
  sqcpy.txt        sq_fast_cpy (staging buffer -> TA copy) for the direct store-queue bound
  pin_best8k.txt   the 256 RAM lines with the most miss stall (oracle 8 KB OC-RAM contents)
  pin_xform8k.txt  the 256 most-stalled lines first missed by render transform code
"""
import argparse, collections, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwreport import Syms, load_sim

XFORM = re.compile(r'vp::transform|skin_|MeshDraw::draw|re4dc_actor_submit|load_screen|mesh_submit|'
                   r'clip_projected|view_words|commonModelTrans|C_MTX|PSMTX')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', required=True); ap.add_argument('--sim', required=True)
    ap.add_argument('--funcs', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    syms = Syms(a.elf)
    rows, _ = load_sim(a.sim)
    area = {}
    for l in open(a.funcs).read().splitlines()[1:]:
        v = l.split('\t'); area[v[0]] = v[1]
    # function extents (sized symbols; unsized labels extend to the next symbol)
    ext = {}
    for i, (s, z, n) in enumerate(zip(syms.start, syms.size, syms.name)):
        e = s + z if z else (syms.start[i + 1] if i + 1 < len(syms.start) else s + 2)
        ext.setdefault(n, (s, e))
    exec_f = collections.Counter(); line_exec = collections.Counter(); line_fn = {}
    for pc, d in rows.items():
        if not pc or not d['exec']:
            continue
        _, fn = syms.lookup(pc)
        exec_f[fn] += d['exec']
        line_exec[pc & ~31] += d['exec']
        line_fn.setdefault(pc & ~31, fn)
    text_lo = 0x8c010000
    # 1. function order
    hot = [f for f, _ in exec_f.most_common() if f in ext]
    cur = text_lo; out = []
    placed = set()
    for f in hot:
        s, e = ext[f]
        base = s & ~31
        for ln in range(base, (e + 31) & ~31, 32):
            out.append((ln, cur + (ln - base)))
        cur += ((e + 31) & ~31) - base
        placed.add(f)
    with open(os.path.join(a.out, 'icmap_func.txt'), 'w') as o:
        for x, y in out:
            o.write('%08x %08x\n' % (x, y))
    # 2. executed lines only, hot functions first, address order within a function
    cur = text_lo; out = []
    byf = collections.defaultdict(list)
    for ln in line_exec:
        byf[line_fn[ln]].append(ln)
    for f, _ in exec_f.most_common():
        for ln in sorted(byf.get(f, [])):
            out.append((ln, cur)); cur += 32
    with open(os.path.join(a.out, 'icmap_lines.txt'), 'w') as o:
        for x, y in out:
            o.write('%08x %08x\n' % (x, y))
    # 3/4. range files
    def ranges(pred, path):
        rs = sorted(ext[f] for f in ext if pred(f))
        with open(path, 'w') as o:
            for s, e in rs:
                o.write('%08x %08x\n' % (s, e))
        return len(rs)
    n1 = ranges(lambda f: area.get(f) in ('actors', 'scenery', 'ui', 'ta-submit'), os.path.join(a.out, 'render_fdiv.txt'))
    n2 = ranges(lambda f: area.get(f) == 'copies', os.path.join(a.out, 'copies.txt'))
    ranges(lambda f: f.startswith('sq_fast_cpy'), os.path.join(a.out, 'sqcpy.txt'))
    # 5. pin lists
    lines = []
    for l in open(a.sim + '.lines.tsv').read().splitlines()[1:]:
        ln, miss, stall, pc = l.split('\t')
        lines.append((float(stall), int(ln, 16), int(pc, 16)))
    lines.sort(reverse=True)
    with open(os.path.join(a.out, 'pin_best8k.txt'), 'w') as o:
        for st, ln, pc in lines[:256]:
            o.write('%08x\n' % ln)
    xf = [(st, ln, pc) for st, ln, pc in lines if XFORM.search(syms.lookup(pc)[1])]
    with open(os.path.join(a.out, 'pin_xform8k.txt'), 'w') as o:
        for st, ln, pc in xf[:256]:
            o.write('%08x\n' % ln)
    tot = sum(x[0] for x in lines)
    print('functions ordered %d; executed lines %d (%d KB); render ranges %d; copy ranges %d' % (
        len(hot), len(line_exec), len(line_exec) * 32 // 1024, n1, n2))
    print('miss stall share of best 256 lines %.1f%%, of best 256 transform lines %.1f%%' % (
        100 * sum(x[0] for x in lines[:256]) / tot, 100 * sum(x[0] for x in xf[:256]) / tot))


if __name__ == '__main__':
    main()
