#!/usr/bin/env python3
"""One opt-in opaque PS2 COLOR asset through existing room/texture packers.

The default builds GC. The PS2 branch requires pinned private inputs, equivalent
placement already reviewed, and a single opaque material. Generated sidecar v1
is a compile-time diagnostic table tied to the complete room payload CRC.
"""
import argparse
import json
import math
import pathlib
import struct
from PIL import Image
import audit_ps2_color_asset as audit
import convert_room_obj as room
import convert_tpl as tex
from texture_candidate import checked, rgba_image, sha


def factorize(pixels, colors):
    if not colors or not pixels: raise ValueError('empty colors/texture')
    if any(len(c)!=4 or not all(math.isfinite(x) for x in c) or any(x<0 for x in c) or c[3]!=1 for c in colors):
        raise ValueError('requires finite nonnegative opaque authored RGBA')
    if any(p[3]!=255 for p in pixels): raise ValueError('requires opaque texture')
    # Full texture extrema cover every repeated/clamped/bilinear sample, not
    # merely the vertices or a guessed visible subset.
    gains=[max(1.0,max(c[k] for c in colors)) for k in range(3)]
    if any(max(p[k] for p in pixels)*gains[k]>255 for k in range(3)):
        raise ValueError('factorization would clip a texture channel')
    encoded=[tuple(round(p[k]*gains[k]) for k in range(3))+(255,) for p in pixels]
    normalized=[tuple(c[k]/gains[k] for k in range(3)) for c in colors]
    return encoded,normalized,gains


def header(crc, first, colors):
    rows=',\n'.join('    {'+', '.join(format(v,'.9g')+'f' if any(x in format(v,'.9g') for x in '.e') else format(v,'.9g')+'.0f' for v in c)+'}' for c in colors)
    return f'''// Generated private diagnostic sidecar; do not commit asset values.
#pragma once
#include <cstdint>
namespace ps2_candidate {{
inline constexpr std::uint32_t version = 1;
inline constexpr std::uint32_t room_crc = 0x{crc:08x}U;
inline constexpr std::uint32_t first = {first}U;
inline constexpr std::uint32_t count = {len(colors)}U;
inline constexpr float colors[count][3] = {{
{rows}
}};
}}
'''


def build(selection, variant, output):
    data={k:checked(pathlib.Path(v['path']),v['sha256']) for k,v in selection['inputs'].items()}
    parsed=room.parse_obj(pathlib.Path(selection['inputs']['gc_obj']['path']))
    group=selection['gc_group']; target=[b for b in parsed['batches'] if b.group==group]
    if len(target)!=1 or target[0].material!=selection['gc_material']: raise ValueError('GC material/group contract changed')
    if any(b.material==selection['gc_material'] and b.group!=group for b in parsed['batches']): raise ValueError('GC material is shared outside selected object')
    colors=[];first=0;gains=[1,1,1]
    images=tex.parse_tpl(data['gc_tpl']);bindings=tex.parse_mtl(data['gc_mtl'].decode('utf-8-sig'))
    if variant=='ps2':
        tr=audit.instance(data['ps2_smd'],selection['ps2_instance'])
        raw=audit.raw_color_bin(data['ps2_bin'],tr)
        name=f"PS2SCENARIO#SMD_{selection['ps2_instance']:03}#SMX_{tr['smx']:03}#TYPE_{tr['flags']:02X}#BIN_{tr['bin']:03}#COLOR#"
        audit.compare(raw,audit.exported_group(data['ps2_obj'].decode('utf-8-sig'),name))
        if raw['materials']!=selection['ps2_material_bytes'] or len(raw['materials'])!=1: raise ValueError('unsupported PS2 material contract')
        mat=bytes.fromhex(raw['materials'][0])
        if mat[0]!=0 or mat[2:5]!=b'\xff\xff\xff' or any(mat[5:11]) or mat[11]!=255:
            raise ValueError('only plain diffuse PS2 material is supported')
        if mat[1]!=selection['ps2_image_index']:
            raise ValueError('PS2 texture slot differs')
        image=Image.open(pathlib.Path(selection['inputs']['ps2_png']['path'])).convert('RGBA')
        pixels,colors,gains=factorize(list(image.getdata()),[v[5:9] for v in raw['vertices']])
        image.putdata(pixels)
        bindings=[tex.MaterialBinding(b.name,len(images),None) if b.name==selection['gc_material'] else b for b in bindings]
        images.append(rgba_image(image))
        # Remove only unused GC vertices, preserve remaining per-corner identity.
        retained=sorted(set(i for b in parsed['batches'] if b.group!=group for i in b.indices))
        remap={old:new for new,old in enumerate(retained)}
        old_vertices=parsed['vertices'];parsed['vertices']=[old_vertices[i] for i in retained]
        for b in parsed['batches']:
            if b.group!=group: b.indices=[remap[i] for i in b.indices]
        first=len(parsed['vertices'])
        parsed['vertices'].extend((*v[:3],0.0,0.0,0.0,*v[3:5]) for v in raw['vertices'])
        target[0].indices=[first+i for m,tri in raw['faces'] for i in tri]
        g=parsed['groups'][group];g.bounds_min=[math.inf]*3;g.bounds_max=[-math.inf]*3
        for v in raw['vertices']:g.include(v[:3])
    for i,v in enumerate(parsed['vertices']):parsed['vertices'][i]=tuple(x*.1 for x in v[:3])+v[3:]
    for g in parsed['groups'].values():
        g.bounds_min=[x*.1 for x in g.bounds_min];g.bounds_max=[x*.1 for x in g.bounds_max]
    groups=room.source_groups_for_names(parsed['group_order'],room.parse_smx(pathlib.Path(selection['inputs']['gc_smx']['path'])))
    groups=room.add_source_light_volumes(groups,{'GGSCENARIO':pathlib.Path(selection['inputs']['gc_smd']['path'])},None,.001)
    groups=room.spatial_partition(parsed,4.0,groups,set())
    package,meta=room.build_package(parsed,groups)
    textures,tmeta=tex.build_package(images,bindings,256,True)
    output.mkdir(parents=True,exist_ok=False)
    (output/'room.re4room').write_bytes(package);(output/'room.re4tex').write_bytes(textures)
    if variant=='ps2': (output/'ps2_candidate_generated.hpp').write_text(header(struct.unpack_from('<I',package,92)[0],first,colors))
    info=dict(variant=variant,room=meta,textures=tmeta,room_sha256=sha(package),texture_sha256=sha(textures),
              color_records=len(colors),color_bytes=len(colors)*12,color_first=first,gains=gains,
              qualification='diagnostic candidate; no visual acceptance',
              texture_quantization='RGBA bridge rounds nearest; native RGB565 truncates 5/6/5 bits')
    (output/'manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    return info


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('selection',type=pathlib.Path);p.add_argument('output',type=pathlib.Path)
    p.add_argument('--variant',choices=['gc','ps2'],default='gc');a=p.parse_args()
    info=build(json.loads(a.selection.read_text()),a.variant,a.output)
    print(json.dumps({k:info[k] for k in ['variant','color_records','color_bytes','gains']}))
if __name__=='__main__':main()
