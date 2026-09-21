#!/usr/bin/env python3
"""Prepare source-identified UI images using the existing TPL converter/package.
prepare_native_ui.py <source-tree> <files.txt> <out-texture-dir>
No resizing, image substitution or runtime GameCube texture decoder. Existing
16-bit package quantization is a visible candidate requiring image acceptance.
"""
import json
from pathlib import Path
import struct
import sys
import zlib
import hashlib
import le_mirror as mirror
from convert_tpl import parse_tpl, build_package, MaterialBinding


def image_identity(image):
    palette=image.palette_data or b''
    metadata=struct.pack('<5I',image.width,image.height,image.format,
                         image.palette_format if image.palette_format is not None else 0xffffffff,len(palette))
    payload=metadata+image.data+palette
    fnv=2166136261
    for byte in payload:fnv=((fnv^byte)*16777619)&0xffffffff
    return '%08x-%08x'%(zlib.crc32(payload)&0xffffffff,fnv),payload


def prepare(source, paths, dest):
    # Refuse a stale/mixed destination; a failed build is never promoted over
    # a previous qualified set. The caller packages only after exit status 0.
    dest.mkdir(parents=True,exist_ok=False)
    source_files={p.relative_to(source).as_posix().lower():p for p in source.rglob('*') if p.is_file()}
    entries=[];errors=[];identities={};seen=set()
    def tpl(file,offset,data,context):
        if not any(context == selector or context.startswith(selector + '/')
                   or (':' not in selector and '#' not in selector and
                       (context.startswith(selector + ':') or context.startswith(selector + '#')))
                   for selector in paths):
            return
        try:
            images=parse_tpl(data)
            for i,image in enumerate(images):
                key,payload=image_identity(image);sha=hashlib.sha256(payload).hexdigest()
                if key in identities and identities[key]!=sha:
                    raise ValueError('texture identity collision')
                identities[key]=sha
                if key not in seen:
                    package,meta=build_package([image],[MaterialBinding('source',0,None)],
                                              twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
                    path=dest/(key+'.re4tex')
                    tmp=path.with_suffix('.tmp');tmp.write_bytes(package);tmp.replace(path)
                    seen.add(key)
                entries.append({'file':file,'context':context,'tpl_offset':offset,'image':i,'key':key,'source_sha256':sha,
                                'width':image.width,'height':image.height,'format':image.format})
        except (ValueError,IndexError,struct.error) as exc:
            errors.append({'file':file,'tpl_offset':offset,'error':str(exc)})
    previous_observer=mirror.TPL_OBSERVER
    report_start=len(mirror.REPORT)
    mirror.TPL_OBSERVER=tpl
    try:
        for rel in sorted(set(p.split(':',1)[0].split('#',1)[0] for p in paths)):
            if rel not in source_files:
                errors.append({'file':rel,'error':'source file absent'});continue
            mirror.convert_file(rel,bytearray(source_files[rel].read_bytes()))
            # Reuse the existing qualification gate, independently of image export.
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w',suffix='.txt') as required:
            required.write('\n'.join(paths));required.flush()
            errors.extend({'error':p} for p in mirror.check_required(mirror.REPORT[report_start:],required.name))
    finally:mirror.TPL_OBSERVER=previous_observer
    report={'entries':entries,'errors':errors,'unique_images':len(set(e['key'] for e in entries)),
            'presentation':'Existing RGB565/ARGB4444 quantization; source dimensions/texels retained before quantization, padding only; visual acceptance pending.'}
    (dest/'native-ui-report.json').write_text(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    source,manifest,dest=map(Path,sys.argv[1:])
    paths=[s.strip().lower() for s in manifest.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
    report=prepare(source,paths,dest)
    print('native UI images:',report['unique_images'],'errors:',report['errors'])
    sys.exit(2 if report['errors'] else 0)
