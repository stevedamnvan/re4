#!/usr/bin/env python3
"""hwcompare.py: print a candidate's hardware projection by area, and its delta against a reference.

  hwcompare.py --cand PROJDIR [--ref PROJDIR] [--trace-log hwtrace.log]

PROJDIR is an hwproject.sh output dir (nominal/low/high/nodma .sum.txt and rep/areas.tsv).
'fly' = Flycast dynarec cycle-charge model (Sh4Cycles::countCycles) over the same traces, which
tracks the sampled Flycast ms within ~1%; 'hw' = projected SH-4 hardware ms (nominal model,
[low..high] = fill/write-back/SQ timing band). All ms per frame at 200 MHz.
"""
import argparse, os


def sums(p, name):
    d = {}
    fn = os.path.join(p, name + '.sum.txt')
    if os.path.exists(fn):
        for line in open(fn):
            k, _, v = line.partition(' ')
            try:
                d[k] = float(v)
            except ValueError:
                pass
    return d


def areas(p):
    A = {}
    fn = os.path.join(p, 'rep', 'areas.tsv')
    rows = [l.rstrip('\n').split('\t') for l in open(fn)]
    hdr = rows[0]
    for r in rows[1:]:
        A[r[0]] = {h: float(v) for h, v in zip(hdr[1:], r[1:])}
    return A


def trace_repr(log):
    cnt, tr = [], []
    if not log or not os.path.exists(log):
        return None
    for line in open(log):
        w = line.split()
        if len(w) >= 4 and w[0] == 'frame':
            n = int(w[3])
            if 'counted' in w:
                cnt.append(n)
            if 'traced' in w:
                tr.append(n)
    if not cnt or not tr:
        return None
    return sum(cnt) / len(cnt), sum(tr) / len(tr), len(cnt), len(tr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cand', required=True)
    ap.add_argument('--ref')
    ap.add_argument('--trace-log')
    a = ap.parse_args()
    C = areas(a.cand)
    cs = {n: sums(a.cand, n) for n in ('nominal', 'low', 'high', 'nodma')}
    R = areas(a.ref) if a.ref and os.path.exists(os.path.join(a.ref, 'rep', 'areas.tsv')) else None
    rs = {n: sums(a.ref, n) for n in ('nominal', 'low', 'high', 'nodma')} if R else None

    def tot(s):
        return s.get('ms_per_frame', 0.0)

    ct = C['TOTAL']
    print('candidate  %s' % os.path.abspath(a.cand))
    print('  traced frames %d, insns/frame %.2fM' % (cs['nominal'].get('frames', 0),
                                                     cs['nominal'].get('insn_per_frame', 0) / 1e6))
    rep = trace_repr(a.trace_log)
    if rep:
        print('  representativeness: counted %d frames %.2fM insns/frame, traced %d frames %.2fM (%+.1f%%)' % (
            rep[2], rep[0] / 1e6, rep[3], rep[1] / 1e6, 100.0 * (rep[1] / rep[0] - 1)))
    print('  Flycast (dynarec charge model) %.1f ms/frame' % ct['flymodel_ms'])
    print('  hardware projection            %.1f ms/frame  [low %.1f .. high %.1f]' % (
        tot(cs['nominal']), tot(cs['low']), tot(cs['high'])))
    if cs['nodma']:
        print('  of which PVR/DMA bus contention %.1f ms (%.0f KB/frame DMA from RAM)' % (
            tot(cs['nominal']) - tot(cs['nodma']), cs['nominal'].get('dma_bytes_per_frame', 0) / 1024))
    if R:
        rt = R['TOTAL']
        print('reference  %s' % os.path.abspath(a.ref))
        print('  Flycast %.1f  hardware %.1f [%.1f .. %.1f]' % (rt['flymodel_ms'], tot(rs['nominal']),
                                                                  tot(rs['low']), tot(rs['high'])))
        dfly = ct['flymodel_ms'] - rt['flymodel_ms']
        dhw = tot(cs['nominal']) - tot(rs['nominal'])
        print('  delta: Flycast %+.1f ms, hardware %+.1f ms [low %+.1f .. high %+.1f]%s' % (
            dfly, dhw, tot(cs['low']) - tot(rs['low']), tot(cs['high']) - tot(rs['high']),
            ('  (hardware keeps %.0f%% of the Flycast delta)' % (100 * dhw / dfly)) if abs(dfly) > 0.5 else ''))
        def parts(x):
            return (sum(x[c] for c in ('base', 'dep_load', 'dep_fpu', 'dep_fdiv', 'dep_other', 'flock', 'branch')),
                    x['imiss'], x['dmiss'] + x['pfwait'], x['sq'] + x['uncached'])
        pc, pr = parts(ct), parts(rt)
        print('  hardware delta by cause: pipeline %+.1f, I-miss %+.1f, D-miss %+.1f, SQ/uncached %+.1f' % tuple(
            c - r for c, r in zip(pc, pr)))
    print()
    keys = sorted([k for k in C if k != 'TOTAL'], key=lambda k: -C[k]['hw_ms'])
    if R:
        keys += [k for k in sorted(R, key=lambda k: -R[k]['hw_ms']) if k not in C and k != 'TOTAL']
        print('%-17s %7s %7s %7s | %7s %7s %7s %7s %7s | %6s' % (
            'area', 'fly-ref', 'fly', 'd-fly', 'hw-ref', 'hw', 'hw-lo', 'hw-hi', 'd-hw', 'kept'))
        z = {'flymodel_ms': 0.0, 'hw_ms': 0.0, 'wi_low': 0.0, 'wi_high': 0.0}
        for k in keys + ['TOTAL']:
            c, r = C.get(k, z), R.get(k, z)
            df, dh = c['flymodel_ms'] - r['flymodel_ms'], c['hw_ms'] - r['hw_ms']
            kept = ('%5.0f%%' % (100 * dh / df)) if abs(df) >= 0.5 else '     -'
            print('%-17s %7.1f %7.1f %+7.1f | %7.1f %7.1f %7.1f %7.1f %+7.1f | %s' % (
                k, r['flymodel_ms'], c['flymodel_ms'], df, r['hw_ms'], c['hw_ms'], c.get('wi_low', 0),
                c.get('wi_high', 0), dh, kept))
    else:
        print('%-17s %7s %7s %7s %7s %6s %7s %7s %7s %7s' % ('area', 'fly', 'hw', 'hw-lo', 'hw-hi', 'hw/fly',
                                                             'pipe', 'imiss', 'dmiss', 'dma'))
        for k in keys + ['TOTAL']:
            c = C[k]
            pipe = sum(c[x] for x in ('base', 'dep_load', 'dep_fpu', 'dep_fdiv', 'dep_other', 'flock', 'branch'))
            print('%-17s %7.1f %7.1f %7.1f %7.1f %6.2f %7.1f %7.1f %7.1f %7.1f' % (
                k, c['flymodel_ms'], c['hw_ms'], c.get('wi_low', 0), c.get('wi_high', 0),
                c['hw_ms'] / c['flymodel_ms'] if c['flymodel_ms'] else 0, pipe, c['imiss'],
                c['dmiss'] + c['pfwait'], c['hw_ms'] - c.get('wi_nodma', c['hw_ms'])))
    print('\nbreakdown (hw ms): pipe = issue+dependency+branch, imiss/dmiss = cache fills, other = SQ+uncached')
    print('%-17s %7s %7s %7s %7s %7s %7s' % ('area', 'hw', 'pipe', 'imiss', 'dmiss', 'other', 'dma'))
    for k in keys + ['TOTAL']:
        if k not in C:
            continue
        c = C[k]
        pipe = sum(c[x] for x in ('base', 'dep_load', 'dep_fpu', 'dep_fdiv', 'dep_other', 'flock', 'branch'))
        print('%-17s %7.1f %7.1f %7.1f %7.1f %7.1f %7.1f' % (k, c['hw_ms'], pipe, c['imiss'], c['dmiss'] + c['pfwait'],
                                                          c['sq'] + c['uncached'],
                                                          c['hw_ms'] - c.get('wi_nodma', c['hw_ms'])))


if __name__ == '__main__':
    main()
