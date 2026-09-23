#!/usr/bin/env python3
"""hwreport.py: turn hwsim per-PC output into per-function / per-area hardware projections.

  hwreport.py --elf ELF --sim PREFIX [--whatif NAME=PREFIX ...] [--pcs-csv ALL.csv --pcs-tid1 T1.csv
              --pcs-tid12 T12.csv] [--counts counts.bin --count-frames N] [--out DIR] [--top N]

PREFIX is an hwsim --out prefix (PREFIX.pcs.tsv, PREFIX.sum.txt). Flycast sampled ms come from
pcs_symbolize.py --csv (frames 2401:2520 of the LD run). All ms are per frame at 200 MHz.
"""
import argparse, bisect, collections, csv, os, re, struct, subprocess, sys

TOOL = '/opt/toolchains/dc/sh-elf/bin/sh-elf-'
CATS = ['base', 'dep_load', 'dep_fpu', 'dep_fdiv', 'dep_other', 'flock', 'branch', 'imiss', 'dmiss', 'pfwait',
        'sq', 'uncached']
CNTS = ['imiss', 'drmiss', 'dwmiss', 'pf', 'pfuse', 'sqf', 'stream_miss', 'uncached_n', 'reads', 'writes', 'fdiv',
        'induced', 'words_used', 'fills_owned']
MHZ = 200000.0  # cycles per ms


class Syms:
    def __init__(self, elf):
        out = subprocess.run([TOOL + 'nm', '-n', '-S', '-C', '--defined-only', elf], capture_output=True,
                             text=True).stdout
        rows = []
        for l in out.splitlines():
            m = re.match(r'^([0-9a-f]{8}) (?:([0-9a-f]{8}) )?([tTwW]) (.*)$', l)
            if not m:
                continue
            a = int(m.group(1), 16)
            if a < 0x8c000000:
                continue
            name = m.group(4)
            if name.startswith('.') or name in ('start', '_start') and False:
                continue
            rows.append((a, int(m.group(2), 16) if m.group(2) else 0, name))
        rows.sort()
        # de-duplicate aliases at the same address: keep the first non-local-looking name
        self.start, self.size, self.name = [], [], []
        for a, s, n in rows:
            if self.start and self.start[-1] == a:
                if self.size[-1] == 0 and s:
                    self.size[-1] = s
                continue
            self.start.append(a); self.size.append(s); self.name.append(n)
        self.elf = elf

    def lookup(self, pc):
        i = bisect.bisect_right(self.start, pc) - 1
        if i < 0:
            return None, '[unknown]'
        a, s = self.start[i], self.size[i]
        if s and pc >= a + s:
            # asm label regions without size (L_* loops) follow a sized symbol; report "after"
            return a, '[after %s]' % self.name[i]
        return a, self.name[i]

    def files(self, addrs):
        addrs = sorted(set(addrs))
        if not addrs:
            return {}
        p = subprocess.run([TOOL + 'addr2line', '-e', self.elf] + ['%x' % a for a in addrs], capture_output=True,
                           text=True)
        res = {}
        for a, l in zip(addrs, p.stdout.splitlines()):
            f = l.rsplit(':', 1)[0]
            res[a] = f
        return res


def load_sim(prefix):
    rows = {}
    with open(prefix + '.pcs.tsv') as f:
        hdr = f.readline().rstrip('\n').split('\t')
        for l in f:
            v = l.rstrip('\n').split('\t')
            d = {}
            for k, x in zip(hdr, v):
                if k == 'pc':
                    continue
                d[k] = float(x)
            rows[int(v[0], 16)] = d
    summ = {}
    for l in open(prefix + '.sum.txt'):
        k, v = l.split()
        summ[k] = float(v)
    return rows, summ


FILE_AREA = [
    (r'native_actor|native_model|model_asset_bridge|model_bridge|native_draw_plan|actor', 'actors'),
    (r'native_static|/room/|mesh_fastpath|pvr_geometry|source_lighting|texture_package', 'scenery'),
    (r'native_ui|frontend|ui_', 'ui'),
    (r'memset|memcpy|memmove|memcmp|L_store|L_movmem|L_al4|L_memcpy|__movmem|movstr', 'copies'),
    (r'hardware/sq\.c|pvr|sq_fast_cpy|sq_cpy|/pvr/', 'ta-submit'),
    (r'kos-re4dc|kos/kernel|/kernel/|thread|mutex|genwait|irq|timer|pc_sampler|arch_sleep|thd_|entry\.o', 'kos-idle'),
    (r'D:/Bio4|src/game|sdk/gen|platform/mtx|gx_stub|libm|newlib/libm|libgcc|softfp|soft-fp|os\.cpp|OSAlloc|'
     r'platform/|newlib|\?\?|_movmem|port/dreamcast/game', 'game'),
]
NAME_AREA = [
    (r'^(memset|memcpy|memmove|memcmp|L_store_long_loop|L_store_byte_loop|L_movmem_loop|L_al4both_loop|'
     r'__movmem|__movstr|L_memcpy|\[after (memset|memcpy|memmove)\])', 'copies'),
    (r'^(sq_fast_cpy|sq_cpy|sq_lock|sq_unlock|sq_set|pvr_)', 'ta-submit'),
    (r'^(thd_|arch_sleep|irq_|_irq|genwait|mutex_|timer_|re4dc_pcs|pcsIrq|spinlock|sem_|cond_)', 'kos-idle'),
]


def area_of(name, fname):
    for rx, a in NAME_AREA:
        if re.search(rx, name):
            return a
    for rx, a in FILE_AREA:
        if re.search(rx, fname or ''):
            return a
    return 'other'


def load_pcs_csv(path):
    d = {}
    if not path or not os.path.exists(path):
        return d
    for r in csv.DictReader(open(path)):
        if r['table'] != 'functions':
            continue
        d[r['key']] = float(r['ms_per_frame'])
    return d


def norm_name(n):
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', required=True)
    ap.add_argument('--sim', required=True)
    ap.add_argument('--whatif', action='append', default=[])
    ap.add_argument('--pcs-csv'); ap.add_argument('--pcs-tid1'); ap.add_argument('--pcs-tid12')
    ap.add_argument('--counts'); ap.add_argument('--count-frames', type=int, default=120)
    ap.add_argument('--out', default='.')
    ap.add_argument('--top', type=int, default=60)
    a = ap.parse_args()
    syms = Syms(a.elf)
    base, bsum = load_sim(a.sim)
    nfr = bsum['frames']
    whatifs = []
    for w in a.whatif:
        n, p = w.split('=', 1)
        whatifs.append((n, load_sim(p)))

    def per_func(rows):
        F = collections.defaultdict(lambda: collections.defaultdict(float))
        for pc, d in rows.items():
            fa, fn = syms.lookup(pc) if pc else (None, '[outside RAM]')
            f = F[fn]
            f['_start'] = fa or 0
            for k, v in d.items():
                f[k] += v
        return F

    FB = per_func(base)
    starts = [f['_start'] for f in FB.values() if f['_start']]
    files = syms.files(starts)
    fly_all = load_pcs_csv(a.pcs_csv); fly1 = load_pcs_csv(a.pcs_tid1); fly12 = load_pcs_csv(a.pcs_tid12)
    counts_f = None
    if a.counts and os.path.exists(a.counts):
        raw = open(a.counts, 'rb').read()
        n = len(raw) // 4
        cnt = struct.unpack('<%dI' % n, raw)
        counts_f = collections.defaultdict(float)
        for i, c in enumerate(cnt):
            if c:
                _, fn = syms.lookup(0x8c000000 | (i << 1))
                counts_f[fn] += c / a.count_frames
    os.makedirs(a.out, exist_ok=True)
    WF = [(n, per_func(r), s) for n, (r, s) in whatifs]

    table = []
    for fn, f in FB.items():
        cyc = sum(f[c] for c in CATS)
        fname = files.get(f['_start'], '')
        ar = area_of(fn, fname)
        t1, t12 = fly1.get(fn, 0.0), fly12.get(fn, 0.0)
        if ar == 'game':
            ar = 'game-logic' if t12 > t1 else 'game-render-side'
        row = {
            'func': fn, 'file': fname, 'area': ar,
            'fly_ms': fly_all.get(fn, 0.0), 'fly_t1': t1, 'fly_t12': t12,
            'insn_pf': f['exec'] / nfr,
            'insn_pf_120': (counts_f or {}).get(fn, 0.0) if counts_f else 0.0,
            'flymodel_ms': f['fly'] / nfr / MHZ,
            'hw_ms': cyc / nfr / MHZ,
        }
        for c in CATS:
            row[c] = f[c] / nfr / MHZ
        for c in ['imiss_n', 'drmiss', 'dwmiss', 'pf', 'sqf', 'stream_miss', 'fdiv', 'induced']:
            row[c + '_pf'] = f.get(c, 0.0) / nfr
        row['line_util'] = (f['words_used'] / (8.0 * f['fills_owned'])) if f['fills_owned'] else 0.0
        for n, W, s in WF:
            g = W.get(fn)
            row['wi_' + n] = (sum(g[c] for c in CATS) / s['frames'] / MHZ) if g else 0.0
        table.append(row)
    table.sort(key=lambda r: -r['hw_ms'])
    cols = ['func', 'area', 'fly_ms', 'flymodel_ms', 'hw_ms', 'insn_pf', 'insn_pf_120'] + CATS + \
           ['imiss_n_pf', 'drmiss_pf', 'dwmiss_pf', 'stream_miss_pf', 'fdiv_pf', 'induced_pf', 'pf_pf', 'sqf_pf',
            'line_util', 'fly_t1', 'fly_t12', 'file'] + ['wi_' + n for n, _, _ in WF]
    with open(os.path.join(a.out, 'functions.tsv'), 'w') as o:
        o.write('\t'.join(cols) + '\n')
        for r in table:
            o.write('\t'.join(('%.4f' % r[c]) if isinstance(r[c], float) else str(r[c]) for c in cols) + '\n')
    # areas
    A = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in table:
        # shared GC helpers (C_MTXConcat, PSVEC*, ...) run on both the render thread (tid 1) and the
        # logic thread (tid 12): split them by the sampled tid shares
        split = [(r['area'], 1.0)]
        if r['area'].startswith('game-') and r['fly_t1'] + r['fly_t12'] > 0:
            f12 = r['fly_t12'] / (r['fly_t1'] + r['fly_t12'])
            split = [('game-logic', f12), ('game-render-side', 1.0 - f12)]
        for ar, fr in split:
            for c in cols:
                if isinstance(r[c], float) and c not in ('line_util',):
                    A[ar][c] += r[c] * fr
    acols = ['fly_ms', 'flymodel_ms', 'hw_ms', 'insn_pf'] + CATS + ['imiss_n_pf', 'drmiss_pf', 'dwmiss_pf'] + \
            ['wi_' + n for n, _, _ in WF]
    with open(os.path.join(a.out, 'areas.tsv'), 'w') as o:
        o.write('area\t' + '\t'.join(acols) + '\n')
        for ar in sorted(A, key=lambda k: -A[k]['hw_ms']):
            o.write(ar + '\t' + '\t'.join('%.3f' % A[ar][c] for c in acols) + '\n')
        tot = {c: sum(A[k][c] for k in A) for c in acols}
        o.write('TOTAL\t' + '\t'.join('%.3f' % tot[c] for c in acols) + '\n')
    # console summary
    print('traced frames %d; model %.2f ms/frame; Flycast-charge model %.2f ms/frame; insns/frame %.0f' % (
        nfr, sum(r['hw_ms'] for r in table), sum(r['flymodel_ms'] for r in table), bsum['insn_per_frame']))
    for n, W, s in WF:
        print('what-if %-14s %.2f ms/frame' % (n, s['ms_per_frame']))
    print('\n%-16s %8s %8s %8s %6s %7s %7s %7s %7s %7s' % ('area', 'fly_ms', 'flymod', 'hw_ms', 'hw/fly', 'pipe',
                                                            'imiss', 'dmiss', 'fdiv', 'other'))
    for ar in sorted(A, key=lambda k: -A[k]['hw_ms']):
        x = A[ar]
        pipe = x['base'] + x['dep_load'] + x['dep_fpu'] + x['dep_other'] + x['flock'] + x['branch']
        print('%-16s %8.2f %8.2f %8.2f %6.2f %7.2f %7.2f %7.2f %7.2f %7.2f' % (
            ar, x['fly_ms'], x['flymodel_ms'], x['hw_ms'], x['hw_ms'] / x['flymodel_ms'] if x['flymodel_ms'] else 0,
            pipe, x['imiss'], x['dmiss'] + x['pfwait'], x['dep_fdiv'], x['sq'] + x['uncached']))
    print('\ntop functions by projected hardware ms/frame')
    print('%7s %7s %7s %5s %6s %6s %6s %6s %6s  %s' % ('fly', 'flymod', 'hw', 'hw/fm', 'pipe', 'imiss', 'dmiss',
                                                       'fdiv', 'util', 'function [area]'))
    for r in table[:a.top]:
        pipe = r['base'] + r['dep_load'] + r['dep_fpu'] + r['dep_other'] + r['flock'] + r['branch']
        print('%7.2f %7.2f %7.2f %5.2f %6.2f %6.2f %6.2f %6.2f %6.2f  %s [%s]' % (
            r['fly_ms'], r['flymodel_ms'], r['hw_ms'], r['hw_ms'] / r['flymodel_ms'] if r['flymodel_ms'] else 0,
            pipe, r['imiss'], r['dmiss'] + r['pfwait'], r['dep_fdiv'], r['line_util'], r['func'][:80], r['area']))


if __name__ == '__main__':
    main()
