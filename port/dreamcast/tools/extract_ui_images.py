#!/usr/bin/env python3
"""Extract every GameCube TPL image embedded in an RE4 ss/*.dat (or a bare .tpl).

Usage: extract_ui_images.py <file.dat|file.tpl> <outdir> [--prefix NAME]

The .dat header is a big-endian u32 count, then offsets at 0x10 and 4-byte tags
(EFF/UWF/...) after them. Each entry is scanned for TPL magic 0x0020AF30 and
every structurally valid TPL is decoded with convert_tpl's GX decoders (plus
RGB565/RGB5A3 here). Outputs are private game assets: never commit them.
Writes <prefix>_<tag><entry>_tpl<k>_tex<nn>_<FMT>_<W>x<H>.png and index.tsv.
"""
from __future__ import annotations
import argparse, pathlib, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import convert_tpl as ct
from PIL import Image

NAMES = {0: 'I4', 1: 'I8', 2: 'IA4', 3: 'IA8', 4: 'RGB565', 5: 'RGB5A3',
         6: 'RGBA8', 8: 'CI4', 9: 'CI8', 14: 'CMPR'}
BPP = {0: 4, 1: 8, 2: 8, 3: 16, 4: 16, 5: 16, 6: 32, 8: 4, 9: 8, 14: 4}
TILE = {4: (8, 8), 8: (8, 4), 16: (4, 4), 32: (4, 4)}


def img_size(w, h, f):
    tw, th = TILE[BPP[f]]
    return ((w + tw - 1) // tw) * ((h + th - 1) // th) * 32 * (2 if f == 6 else 1)


def decode_16(img):
    px = [(0, 0, 0, 0)] * (img.width * img.height)
    o = 0
    for ty in range(0, img.height, 4):
        for tx in range(0, img.width, 4):
            for r in range(4):
                for c in range(4):
                    v = struct.unpack_from('>H', img.data, o)[0]; o += 2
                    x, y = tx + c, ty + r
                    if x < img.width and y < img.height:
                        px[y * img.width + x] = (ct._decode_palette_entry(
                            v, ct.GX_TL_RGB565 if img.format == 4 else ct.GX_TL_RGB5A3))
    return px


def parse_tpl_at(d, base):
    """Parse a TPL at d[base:], offsets relative to base. Returns (images, end) or None."""
    try:
        magic, n, desc = struct.unpack_from('>III', d, base)
    except struct.error:
        return None
    if magic != ct.TPL_MAGIC or not 0 < n < 512 or desc != 12:
        return None
    out, end = [], base + 12 + 8 * n
    for i in range(n):
        th, ph = struct.unpack_from('>II', d, base + desc + 8 * i)
        if th == 0 or base + th + 12 > len(d):
            return None
        h, w, f, do = struct.unpack_from('>HHII', d, base + th)
        if f not in NAMES or not (0 < w <= 4096 and 0 < h <= 4096):
            return None
        sz = img_size(w, h, f)
        if base + do + sz > len(d):
            return None
        pf = pd = None
        if f in (8, 9):
            if ph == 0:
                return None
            ne, _, _, pf, po = struct.unpack_from('>HBBII', d, base + ph)
            pd = d[base + po:base + po + ne * 2]
            end = max(end, base + po + ne * 2)
        end = max(end, base + do + sz)
        out.append(ct.TplImage(w, h, f, d[base + do:base + do + sz], pf, pd))
    return out, end


def entries(d):
    if d[:4] == struct.pack('>I', ct.TPL_MAGIC):
        return [('tpl', 0, 0, len(d))]
    n = struct.unpack_from('>I', d, 0)[0]
    offs = [struct.unpack_from('>I', d, 0x10 + 4 * i)[0] for i in range(n)]
    tags = [d[0x10 + 4 * n + 4 * i:0x10 + 4 * n + 4 * i + 3].decode('ascii', 'replace').lower()
            for i in range(n)]
    bounds = [o for o in offs if o] + [len(d)]
    res = []
    for i, (o, t) in enumerate(zip(offs, tags)):
        if o:
            nxt = min([b for b in bounds if b > o] or [len(d)])
            res.append((t, i, o, nxt))
    return res


def iter_images(d):
    """Yield (tag, entry, entry_off, tpl_off, tpl_index, tex_index, TplImage) in file order.
    The scan (and so the tpl/tex numbering in the PNG names) is shared with ui_overrides.py."""
    for tag, ei, start, stop in entries(d):
        pos, k = start, 0
        while True:
            pos = d.find(struct.pack('>I', ct.TPL_MAGIC), pos, stop)
            if pos < 0:
                break
            r = parse_tpl_at(d[:stop], pos)
            if not r:
                pos += 4; continue
            imgs, end = r
            for j, im in enumerate(imgs):
                yield tag, ei, start, pos, k, j, im
            k += 1
            pos = max(end, pos + 4)
            pos = (pos + 3) & ~3


def image_name(prefix, tag, ei, k, j, im):
    return f'{prefix}_{tag}{ei}_tpl{k:02d}_tex{j:02d}_{NAMES[im.format]}_{im.width}x{im.height}.png'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('outdir'); ap.add_argument('--prefix')
    a = ap.parse_args(argv)
    d = pathlib.Path(a.src).read_bytes()
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    pre = a.prefix or pathlib.Path(a.src).stem
    rows = ['file\tentry\ttag\tentry_off\ttpl_off\tindex\tformat\twidth\theight']
    for tag, ei, start, pos, k, j, im in iter_images(d):
        px = decode_16(im) if im.format in (4, 5) else ct.decode_image(im)
        fn = image_name(pre, tag, ei, k, j, im)
        Image.frombytes('RGBA', (im.width, im.height),
                        bytes(c for p in px for c in p)).save(out / fn)
        rows.append(f'{fn}\t{ei}\t{tag}\t0x{start:x}\t0x{pos:x}\t{j}\t'
                    f'{NAMES[im.format]}\t{im.width}\t{im.height}')
    (out / 'index.tsv').write_text('\n'.join(rows) + '\n')
    print(f'{len(rows) - 1} images -> {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
