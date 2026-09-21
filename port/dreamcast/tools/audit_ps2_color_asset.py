#!/usr/bin/env python3
"""Read-only corroboration of a bounded PS2 scenario COLOR BIN export.

Not an exporter or renderer. Established JADERLINK tools remain the extraction
path. This audit independently samples the original integer records and fails
closed outside the selected unweighted, zero-rotation scenario variant.
"""
import argparse
import hashlib
import json
import math
import pathlib
import struct


def span(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data)-offset:
        raise ValueError('truncated or out-of-range record')
    return data[offset:offset+size]


def unpack(fmt, data, offset):
    return struct.unpack(fmt, span(data, offset, struct.calcsize(fmt)))


def instance(data, index):
    magic, count, bins, textures, reserved = unpack('<HHIII', data, 0)
    if magic != 0x40:
        raise ValueError('unsupported SMD variant (only 0x40 audited)')
    span(data, 16, count*64)
    if not 0 <= index < count:
        raise ValueError('instance index out of bounds')
    values = unpack('<12f4B3I', data, 16+index*64)
    if not all(math.isfinite(v) for v in values[:12]):
        raise ValueError('non-finite instance transform')
    if any(values[4:7]):
        raise ValueError('nonzero rotation outside this corroboration contract')
    if any(s <= 0 for s in values[8:11]):
        raise ValueError('unsupported nonpositive scale')
    return dict(position=values[:3], rotation=values[4:7], scale=values[8:11],
                bin=values[12], tpl=values[13], smx=values[15], flags=values[17])


def raw_color_bin(data, transform):
    span(data, 0, 80)
    if unpack('<H', data, 0)[0] != 0x0030:
        raise ValueError('unsupported BIN magic')
    count, table = unpack('<HI', data, 10)
    if count == 0:
        raise ValueError('empty BIN material table')
    span(data, table, count*16)
    vertices, faces, materials, offsets = [], [], [], []
    for m in range(count):
        raw = span(data, table+m*16, 16)
        materials.append(raw[:12].hex())
        node = unpack('<I', raw, 12)[0]
        _, extra, bones = unpack('<HBB', data, node)
        cursor = node + ((4+bones+15)//16)*16
        for segment in range(extra+1):
            h1 = span(data, cursor, 16)
            if h1[12] == 0 and h1[14] > 1:
                raise ValueError('weighted/normal BIN unsupported by color audit')
            h2, h3 = span(data, cursor+16, 16), span(data, cursor+32, 16)
            scale = unpack('<f', h2, 12)[0]
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError('invalid position conversion factor')
            n, size = h2[0], h3[0]*16
            if n == 0 or n*24 > size:
                raise ValueError('vertex records exceed VIF payload')
            start = cursor+48
            span(data, start, size)
            inv = False
            for j in range(n):
                at = start+j*24
                x,y,z,mount,u,v,unknown,restart,r,g,b,a = unpack('<3hH2h2H3hH', data, at)
                xyz = tuple(q*scale/100*s+p/100 for q,s,p in zip((x,y,z), transform['scale'], transform['position']))
                vertices.append((*xyz, u/255, v/255, r/128, g/128, b/128, a/128))
                offsets.append(at)
                end = len(vertices)-1
                if j >= 2 and restart == 0:
                    tri = (end,end-1,end-2) if inv else (end-2,end-1,end)
                    faces.append((m,tri));inv=not inv
                else:
                    inv=False
            cursor = start+size
            if segment > 0:
                span(data,cursor,16);cursor+=16
    return dict(vertices=vertices, faces=faces, materials=materials, raw_offsets=offsets)


def exported_group(text, name):
    positions, uv, vertices, faces, mats = [], [], [], [], []
    group = None; material = None; own=[]
    for line in text.splitlines():
        f=line.split()
        if not f or f[0].startswith('#'): continue
        if f[0]=='g': group=f[1]
        elif f[0]=='v':
            positions.append(tuple(map(float,f[1:])))
            if group==name: own.append(len(positions)-1)
        elif f[0]=='vt': uv.append(tuple(map(float,f[1:3])))
        elif f[0]=='usemtl': material=f[1]
        elif f[0]=='f' and group==name:
            if len(f)!=4: raise ValueError('non-triangle export')
            if material not in mats: mats.append(material)
            tri=[]
            for token in f[1:]:
                parts=token.split('/')
                if len(parts)!=2: raise ValueError('unexpected normal/missing UV on COLOR export')
                vi,ti=(int(p)-1 for p in parts)
                if not 0<=vi<len(positions) or not 0<=ti<len(uv): raise ValueError('invalid exported corner index')
                if len(positions[vi])!=7: raise ValueError('missing RGBA on exported corner')
                tri.append((vi,ti))
            faces.append((mats.index(material),tri))
    if not own or not faces: raise ValueError('selected COLOR group missing')
    lookup={v:i for i,v in enumerate(own)}; uv_by_vertex={}
    remapped=[]
    for m,tri in faces:
        ids=[]
        for vi,ti in tri:
            if vi not in lookup: raise ValueError('cross-instance vertex reference')
            if vi in uv_by_vertex and uv_by_vertex[vi]!=uv[ti]: raise ValueError('unexpected per-corner UV split')
            uv_by_vertex[vi]=uv[ti];ids.append(lookup[vi])
        remapped.append((m,tuple(ids)))
    # Unused strip restart vertices can be retained by the exporter: report
    # their positions/colors, but only compare UVs on referenced corners.
    for vi in own:
        p=positions[vi];vertices.append((*p[:3],*uv_by_vertex.get(vi,(None,None)),*p[3:]))
    return dict(vertices=vertices,faces=remapped,materials=mats)


def compare(raw, exported):
    if len(raw['vertices'])!=len(exported['vertices']): raise ValueError('vertex count differs')
    if raw['faces']!=exported['faces']: raise ValueError('primitive order/winding/material boundaries differ')
    max_error=0
    for r,e in zip(raw['vertices'],exported['vertices']):
        for i,(a,b) in enumerate(zip(r,e)):
            if b is None: continue
            tolerance=0.0001 if i<3 else 0.000002
            if not math.isfinite(b) or abs(a-b)>tolerance: raise ValueError('source attribute differs at component '+str(i))
            max_error=max(max_error,abs(a-b))
    rgb=[x for v in raw['vertices'] for x in v[5:8]]
    return dict(vertex_records=len(raw['vertices']), triangles=len(raw['faces']),
                material_batches=len(raw['materials']), max_export_rounding_error=max_error,
                rgb_min=min(rgb),rgb_max=max(rgb),
                vertices_above_one=sum(any(x>1 for x in v[5:8]) for v in raw['vertices']),
                alpha_values=sorted(set(v[8] for v in raw['vertices'])),
                bounds=[list(map(min,zip(*(v[:3] for v in raw['vertices'])))),list(map(max,zip(*(v[:3] for v in raw['vertices']))))],
                material_bytes=raw['materials'], first_record_offset=raw['raw_offsets'][0],
                first_decoded_record=raw['vertices'][0],
                native_room_v3_compatible=False,
                required_adaptation='Explicit authored-color support and range-preserving material conversion; direct room-v3 import drops colors')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin',type=pathlib.Path,required=True);p.add_argument('--smd',type=pathlib.Path,required=True)
    p.add_argument('--obj',type=pathlib.Path,required=True);p.add_argument('--instance',type=int,required=True)
    a=p.parse_args(); b=a.bin.read_bytes();s=a.smd.read_bytes();o=a.obj.read_bytes()
    tr=instance(s,a.instance)
    name=f"PS2SCENARIO#SMD_{a.instance:03}#SMX_{tr['smx']:03}#TYPE_{tr['flags']:02X}#BIN_{tr['bin']:03}#COLOR#"
    result=compare(raw_color_bin(b,tr),exported_group(o.decode('utf-8-sig'),name))
    result.update(instance=tr,group=name,identities={k:hashlib.sha256(v).hexdigest() for k,v in [('bin',b),('smd',s),('obj',o)]})
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()

