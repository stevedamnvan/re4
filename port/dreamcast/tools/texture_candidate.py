#!/usr/bin/env python3
"""Build a selectable private texture candidate through the existing native packer.

This is an offline adapter, not a PS2 runtime/parser. Supply PNGs decoded by a
pinned upstream tool and an explicit reviewed source mapping. No resize or flip
is performed on the candidate. Geometry, source state and material names stay GC.
"""
import argparse
import hashlib
import json
import pathlib
from PIL import Image
import convert_tpl as tpl


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, digest):
    data = path.read_bytes()
    if sha(data) != digest:
        raise ValueError(f'identity mismatch: {path}')
    return data


def rgba_image(image):
    """Losslessly bridge decoded RGBA to the existing TPL packer's input API."""
    image = image.convert('RGBA')
    w, h = image.size
    if min(w, h) < 8 or max(w, h) > 1024 or w & (w-1) or h & (h-1):
        raise ValueError('candidate dimensions must be PVR power-of-two 8..1024')
    pixels = list(image.getdata())
    out = bytearray()
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            block = [pixels[(y+dy)*w+x+dx] for dy in range(4) for dx in range(4)]
            out.extend(v for r,g,b,a in block for v in (a,r))
            out.extend(v for r,g,b,a in block for v in (g,b))
    return tpl.TplImage(w,h,tpl.GX_TF_RGBA8,bytes(out))


def build(selection, variant):
    gc = checked(pathlib.Path(selection['gc_tpl']), selection['gc_tpl_sha256'])
    mtl = checked(pathlib.Path(selection['gc_mtl']), selection['gc_mtl_sha256'])
    images = tpl.parse_tpl(gc)
    bindings = tpl.parse_mtl(mtl.decode('utf-8-sig'))
    index = selection['gc_image_index']
    affected = [b.name for b in bindings if b.color_image == index]
    if not affected or any(b.alpha_image == index for b in bindings):
        raise ValueError('candidate must reference a used color image, not an alpha plane')
    if affected != selection['materials']:
        raise ValueError('material mapping changed')
    if variant == 'ps2':
        path = pathlib.Path(selection['ps2_png'])
        checked(path, selection['ps2_png_sha256'])
        with Image.open(path) as image:
            candidate = rgba_image(image)
        if any(p[3] != 255 for p in tpl.decode_image(candidate)):
            raise ValueError('this bounded opaque candidate must not change alpha semantics')
        images[index] = candidate
    package, info = tpl.build_package(images, bindings,
                                      selection['reference_max_dimension'], True)
    info.update(variant=variant, affected_materials=affected, package_bytes=len(package),
                package_sha256=sha(package), qualification='candidate-only',
                target_timing_measured=False, visual_acceptance=False)
    return package, info


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('selection',type=pathlib.Path)
    p.add_argument('output',type=pathlib.Path)
    p.add_argument('--variant',choices=['gc','ps2'],default='gc')
    a=p.parse_args()
    if a.output.exists() or a.output.with_suffix(a.output.suffix+'.json').exists():
        raise ValueError('refusing to overwrite an existing candidate/reference')
    package, info=build(json.loads(a.selection.read_text()),a.variant)
    info['selection_sha256']=sha(a.selection.read_bytes())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(package)
    a.output.with_suffix(a.output.suffix+'.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps({k:info[k] for k in ('variant','package_bytes','texture_bytes','affected_materials')}))

if __name__=='__main__':
    main()
