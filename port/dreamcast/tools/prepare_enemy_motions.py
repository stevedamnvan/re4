#!/usr/bin/env python3
"""Selectable em12 key residency via existing qualified source/FCV transport.

All FCV headers/joint identities, SEQ event tables, EFF behavior, meshes and ordinal
slots stay resident. Native key files are exact existing little-endian codec
output, consumed only through bounded source-motion evaluation leases. No clip
is removed because it was absent from a replay; original DRS remains untouched.
Optional upload-only textures use the existing NTR/shared native package path;
palettes, mip chains and unreviewed embedded EFM textures stay resident.
"""
from pathlib import Path
import argparse, hashlib, json, struct, tempfile, zlib
import le_mirror as mirror
from prepare_native_ui import compact_spans, select_upload_only, native_identity_index

MAGIC=b'R4MOTBL\0'
STRIDE=20
MAX_CLIP=32768

def prepare(source, destination, hot_slots=(), textures=None, keep_motion_resident=False):
    source,destination=map(Path,(source,destination))
    if source.name.lower()!='em12.drs':raise ValueError('supported source contract is em12.drs')
    if keep_motion_resident and textures is None:raise ValueError('no selected compaction')
    if destination.exists():raise FileExistsError(destination)
    hot_slots=set(hot_slots)
    original=source.read_bytes();converted=bytearray(original);refs=[];palettes=[]
    old=mirror.OFFSET_OBSERVER;old_tpl=mirror.TPL_OBSERVER;start=len(mirror.REPORT)
    mirror.OFFSET_OBSERVER=lambda file,field,base,value:refs.append((field,base,value))
    mirror.TPL_OBSERVER=lambda file,off,data,ctx:palettes.append((off,data,ctx))
    try:mirror.convert_file('em/em12.drs',converted)
    finally:mirror.OFFSET_OBSERVER=old;mirror.TPL_OBSERVER=old_tpl
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
    extra_slots=int(not keep_motion_resident)+int(textures is not None)
    header_growth=(max(0,16+8*(count+extra_slots)-first)+31)&~31
    texture_ranges=[];selected=[];retained=[]
    if textures is not None:
        # em10_R0_Init registers EFF slot0; Em12Set/WeaponSet and em10ModelInit
        # pass top-level TPL descriptors to the source texture system. Preserve
        # palette/mips and the shared CPU-noise ID0xfe exactly as room/core do.
        if tags[0]!=b'EFF\0':raise ValueError('em12 effect family changed')
        eff=offsets[0];ids_at=eff+struct.unpack_from('<I',body,eff+4)[0]
        num_ids=struct.unpack_from('<I',body,ids_at)[0]
        ids=[struct.unpack_from('<H',body,ids_at+4+i*8)[0] for i in range(num_ids)]
        top_tpl={'em/em12.drs:0#'+str(i) for i,t in enumerate(tags) if t==b'TPL\0'}
        def allowed(ctx):
            if ctx in top_tpl:return True
            if ctx.startswith('em/em12.drs:0#0/tpl'):
                i=int(ctx.rsplit('tpl',1)[1]);return i<len(ids) and ids[i]!=0xfe
            return False
        local_palettes=[(o-base,d,c) for o,d,c in palettes if base<=o<base+rel]
        texture_ranges,selected,retained=select_upload_only(body,local_palettes,Path(textures),allowed)
        if not texture_ranges:raise ValueError('no qualified enemy textures selected')
    if rel+64!=len(body):raise ValueError('expected retained 64-byte static REL descriptor')
    original_size,original_base=struct.unpack_from('>I4xI',original,slot+4)
    codec=mirror.motion_codec();ranges=[];entries=[];files={}
    for off in ([] if keep_motion_resident else sorted(set(offsets))):
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
    if not entries and not keep_motion_resident:raise ValueError('no qualified motion payloads')
    ranges=sorted(ranges+texture_ranges)
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
    table_bytes=((32+len(table)+31)&~31) if entries else 0
    texture_index_bytes=((32+12*len(selected)+31)&~31) if selected else 0
    final_bytes=len(out)+table_bytes+texture_index_bytes
    tables=bytearray();new_tags=[];new_offsets=[]
    if selected:
        new_tags.append(b'NTR\0');new_offsets.append(new_rel)
        tables+=native_identity_index(selected,mapped,len(body),final_bytes)
    if entries:
        new_tags.append(b'MTC\0');new_offsets.append(new_rel+len(tables))
        header=struct.pack('<8s6I',MAGIC,2,len(entries),STRIDE,zlib.crc32(table)&0xffffffff,final_bytes,MAX_CLIP)
        tables+=header+table+bytes(table_bytes-32-len(table))
    out=out[:new_rel]+tables+out[new_rel:]
    struct.pack_into('<2I',out,0,count+extra_slots,new_rel+len(tables))
    for i,off in enumerate(new_offsets):struct.pack_into('<I',out,16+4*(count+i),off)
    out[16+4*(count+extra_slots):16+8*(count+extra_slots)]=b''.join(tags+new_tags)
    # Every non-FCV archive family and module descriptor retains exact bytes.
    for off in sorted(set(offsets)):
        if not off:continue
        end=min([o for o in offsets if o>off]+[rel])
        if (keep_motion_resident or tags[list(offsets).index(off)]!=b'FCV\0') and not any(off<=a<end for a,b,_ in texture_ranges):
            assert out[mapped(off):mapped(end)]==body[off:end]
    assert out[-64:]==body[-64:]
    packaged=mirror.replace_native_payload(converted,out)
    report={'contract':'em12-native-textures-v1' if keep_motion_resident else 'em12-source-motion-cache-v2','source_sha256':hashlib.sha256(original).hexdigest(),
            'original_static_body_bytes':size,'resident_body_bytes':len(out),
            'archive_recovery_bytes':size-len(out),'index_bytes':table_bytes,'header_growth_bytes':header_growth,
            'motion_source_bytes':sum(e['bytes'] for e in entries),'motion_header_bytes':sum(e['resident_bytes'] for e in entries),
            'motions_resident':keep_motion_resident,
            'textures':{'selected':selected,'retained':retained,'identity_table_bytes':texture_index_bytes,
                'removed_payload_bytes':sum(b-a for a,b,_ in texture_ranges),
                'replacement_record_bytes':32*len(texture_ranges)},
            'max_clip_bytes':max((e['bytes'] for e in entries),default=0),
            'hot_payload_bytes':sum(e['bytes'] for e in entries if e['hot']),
            'cold_reserve_bytes':2*max((e['bytes'] for e in entries if not e['hot']),default=0),
            'cache_policy':None if keep_motion_resident else 'retain hot set and LRU cold entries until capacity pressure; evaluation release never evicts','entries':entries,'qualification':coverage,
            'retained':'all SEQ events, EFF behavior tables, CPU/palette/mip texels, models/materials/skeletons and exact FCV headers',
            'lifetime':'keys remain cached; pins protect source MotionSetCore, MotionMoveCore, MotionGetSpeed and MotionGetPosition; header/SEQ pointers remain source-archive-owned',
            'limits':'offline contract only until native binding, source consumer lifetimes, actual heap and visible output are qualified; motion selection also requires complete prefetch/concurrency audit'}
    destination.mkdir();(destination/'mot').mkdir()
    for key,data in files.items():(destination/'mot'/(key+'.fcv')).write_bytes(data)
    (destination/'em12.drs').write_bytes(packaged)
    (destination/'em12.arc').write_bytes(out)
    (destination/'motion-residency-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--hot-audit',type=Path,help='Source-derived diagnostic hot-set audit; not a replay usage filter')
    p.add_argument('--diagnostic-incomplete-prefetch',action='store_true',help='Allow a clearly labelled source-audit diagnostic, never production qualification')
    p.add_argument('--textures',type=Path,help='Existing exact native texture packages; externalize reviewed upload-only enemy texels')
    p.add_argument('--keep-motion-resident',action='store_true',help='Texture-only selection retains every FCV payload; no motion cache')
    a=p.parse_args()
    if not a.keep_motion_resident and not a.hot_audit:p.error('--hot-audit is required for motion residency')
    audit=json.loads(a.hot_audit.read_text()) if a.hot_audit else {}
    if not a.keep_motion_resident and not audit.get('source_complete') and not a.diagnostic_incomplete_prefetch:
        p.error('prefetch/concurrency audit is incomplete; explicit diagnostic selection required')
    r=prepare(a.source,a.output,audit.get('union',{}).get('source_arc_indices',()),a.textures,a.keep_motion_resident)
    report_path=a.output/'motion-residency-report.json'
    r['prefetch_audit']=audit
    r['runtime_qualified']=False
    report_path.write_text(json.dumps(r,indent=2)+'\n')
    print('em12 resident body',r['original_static_body_bytes'],'->',r['resident_body_bytes'],'motion entries',len(r['entries']),'hot + cold cap',r['hot_payload_bytes']+r['cold_reserve_bytes'])
