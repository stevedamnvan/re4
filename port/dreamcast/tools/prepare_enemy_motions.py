#!/usr/bin/env python3
"""Selectable em12 key residency via existing qualified source/FCV transport.

All FCV headers/joint identities, SEQ event tables, EFF data, meshes and ordinal
slots stay resident. Native key files are exact existing little-endian codec
output, consumed only through bounded source-motion evaluation leases. No clip
is removed because it was absent from a replay; original DRS remains untouched.
"""
from pathlib import Path
import argparse, hashlib, json, struct, tempfile, zlib
import le_mirror as mirror
from prepare_native_ui import compact_spans

MAGIC=b'R4MOTBL\0'
STRIDE=20
MAX_CLIP=32768

def prepare(source, destination, hot_slots):
    source,destination=map(Path,(source,destination))
    if source.name.lower()!='em12.drs':raise ValueError('first qualified contract is em12.drs')
    if destination.exists():raise FileExistsError(destination)
    hot_slots=set(hot_slots)
    original=source.read_bytes();converted=bytearray(original);refs=[]
    old=mirror.OFFSET_OBSERVER;start=len(mirror.REPORT)
    mirror.OFFSET_OBSERVER=lambda file,field,base,value:refs.append((field,base,value))
    try:mirror.convert_file('em/em12.drs',converted)
    finally:mirror.OFFSET_OBSERVER=old
    coverage=mirror.REPORT[start:]
    with tempfile.NamedTemporaryFile(mode='w') as required:
        required.write('em/em12.drs\n');required.flush()
        bad=mirror.check_required(coverage,required.name)
    if bad:raise ValueError('unqualified enemy: '+', '.join(bad))
    # Retain the already-implemented static REL policy; don't restore PPC code.
    converted=mirror.compact_static_rel('em/em12.drs',converted,coverage,mirror.static_module_ids())
    slot=mirror.native_payload_slot(converted)
    size,base=struct.unpack_from('<I4xI',converted,slot+4)
    body=converted[base:base+size]
    count,rel=struct.unpack_from('<2I',body)
    offsets=struct.unpack_from('<%dI'%count,body,16)
    tags=[bytes(body[16+4*count+4*i:20+4*count+4*i]) for i in range(count)]
    first=min(x for x in offsets if x)
    header_growth=32 if first<16+8*(count+1) else 0
    if rel+64!=len(body):raise ValueError('expected retained 64-byte static REL descriptor')
    original_size,original_base=struct.unpack_from('>I4xI',original,slot+4)
    codec=mirror.motion_codec();ranges=[];entries=[];files={}
    for off in sorted(set(offsets)):
        if not off:continue
        slots=[i for i,o in enumerate(offsets) if o==off]
        if tags[slots[0]]!=b'FCV\0':continue
        if any(tags[i]!=b'FCV\0' for i in slots):raise ValueError('mixed-tag alias')
        end=min([o for o in offsets if o>off]+[rel])
        raw=original[original_base+off:original_base+end]
        parsed=codec.parse(raw)
        if codec.serialise(parsed)!=raw:raise ValueError('source FCV roundtrip differs')
        native=codec.serialise(parsed,'<')
        if native!=body[off:end]:raise ValueError('native FCV differs from qualified archive')
        if not parsed.joints:continue # empty motion is already 32 bytes; keep ordinary
        if len(native)>MAX_CLIP:raise ValueError('clip exceeds validated em12 cache slot')
        prefix=codec.header_size(len(parsed.joints));resident=(prefix+31)&~31
        if resident>=len(native):continue
        crc=zlib.crc32(native)&0xffffffff
        fnv=2166136261
        for byte in native:fnv=((fnv^byte)*16777619)&0xffffffff
        key='%08x-%08x'%(crc,fnv)
        if key in files and files[key]!=native:raise ValueError('motion identity collision')
        files[key]=native
        ranges.append((off,end,native[:prefix]+bytes(resident-prefix)))
        entries.append({'source_offset':off,'slots':slots,'bytes':len(native),'prefix_bytes':prefix,
                        'resident_bytes':resident,'hot':bool(hot_slots.intersection(i+4 for i in slots)),'source_arc_indices':[i+4 for i in slots],'key':key,'crc':crc,'fnv':fnv,
                        'sha256':hashlib.sha256(native).hexdigest(),'classification':'reloadable key data; stable header retained'})
    if not entries:raise ValueError('no qualified motion payloads')
    local_refs=[(f-base,b-base,v) for f,b,v in refs if base<=f<base+rel]
    # Existing fmt_drs_body preserves this scalar; it is also an archive-relative
    # boundary and must follow the moved static REL, unlike per-FCV key offsets.
    local_refs.append((4,0,rel))
    if header_growth:ranges.insert(0,(first,first,bytes(header_growth)))
    out,mapped=compact_spans(body,local_refs,ranges)
    # Insert MTC before the static module so readEmData's data/REL split stays true.
    new_rel=mapped(rel);table=bytearray()
    for e in entries:
        e['resident_offset']=mapped(e['source_offset'])
        table+=struct.pack('<5I',e['resident_offset'],e['bytes'],e['crc'],e['fnv'],int(e['hot']))
    table_bytes=(32+len(table)+31)&~31
    final_bytes=len(out)+table_bytes
    header=struct.pack('<8s6I',MAGIC,2,len(entries),STRIDE,zlib.crc32(table)&0xffffffff,final_bytes,MAX_CLIP)
    out=out[:new_rel]+header+table+bytes(table_bytes-32-len(table))+out[new_rel:]
    struct.pack_into('<2I',out,0,count+1,new_rel+table_bytes)
    struct.pack_into('<I',out,16+4*count,new_rel)
    out[16+4*(count+1):16+8*(count+1)]=b''.join(tags)+b'MTC\0'
    # Every non-FCV archive family and module descriptor retains exact bytes.
    for off in sorted(set(offsets)):
        if not off:continue
        end=min([o for o in offsets if o>off]+[rel])
        if tags[list(offsets).index(off)]!=b'FCV\0':
            assert out[mapped(off):mapped(end)]==body[off:end]
    assert out[-64:]==body[-64:]
    packaged=mirror.replace_native_payload(converted,out)
    report={'contract':'em12-source-motion-cache-v2','source_sha256':hashlib.sha256(original).hexdigest(),
            'original_static_body_bytes':size,'resident_body_bytes':len(out),
            'archive_recovery_bytes':size-len(out),'index_bytes':table_bytes,'header_growth_bytes':header_growth,
            'motion_source_bytes':sum(e['bytes'] for e in entries),'motion_header_bytes':sum(e['resident_bytes'] for e in entries),
            'max_clip_bytes':max(e['bytes'] for e in entries),
            'hot_payload_bytes':sum(e['bytes'] for e in entries if e['hot']),
            'cold_reserve_bytes':2*max((e['bytes'] for e in entries if not e['hot']),default=0),
            'cache_policy':'retain hot set and LRU cold entries until capacity pressure; evaluation release never evicts','entries':entries,'qualification':coverage,
            'retained':'all SEQ events, EFF tables/payloads, models/materials/skeletons and exact FCV headers',
            'lifetime':'keys remain cached; pins protect source MotionSetCore, MotionMoveCore, MotionGetSpeed and MotionGetPosition; header/SEQ pointers remain source-archive-owned',
            'limits':'offline contract only until native bind/load/reload/source-evaluation and actual heap measurements pass'}
    destination.mkdir();(destination/'mot').mkdir()
    for key,data in files.items():(destination/'mot'/(key+'.fcv')).write_bytes(data)
    (destination/'em12.drs').write_bytes(packaged)
    (destination/'em12.arc').write_bytes(out)
    (destination/'motion-residency-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--hot-audit',required=True,type=Path,help='Source-derived diagnostic hot-set audit; not a replay usage filter')
    p.add_argument('--diagnostic-incomplete-prefetch',action='store_true',help='Allow a clearly labelled source-audit diagnostic, never production qualification')
    a=p.parse_args();audit=json.loads(a.hot_audit.read_text())
    if not audit.get('source_complete') and not a.diagnostic_incomplete_prefetch:
        p.error('prefetch/concurrency audit is incomplete; explicit diagnostic selection required')
    r=prepare(a.source,a.output,audit['union']['source_arc_indices'])
    report_path=a.output/'motion-residency-report.json'
    r['prefetch_audit']=audit
    r['runtime_qualified']=False
    report_path.write_text(json.dumps(r,indent=2)+'\n')
    print('em12 resident body',r['original_static_body_bytes'],'->',r['resident_body_bytes'],'motion entries',len(r['entries']),'hot + cold cap',r['hot_payload_bytes']+r['cold_reserve_bytes'])
