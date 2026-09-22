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
from convert_tpl import parse_tpl, build_package, MaterialBinding, TPL_MAGIC


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
    entries=[];errors=[];identities={};seen=set();empty_palettes=[]
    def tpl(file,offset,data,context):
        if not any(context == selector or context.startswith(selector + '/')
                   or (':' not in selector and '#' not in selector and
                       (context.startswith(selector + ':') or context.startswith(selector + '#')))
                   for selector in paths):
            return
        try:
            # Source SMDs can use a zero-descriptor palette and pAddTpl.
            # It has no native image to emit; a malformed header still fails.
            empty=False
            if len(data)>=12:
                magic,count,desc=struct.unpack_from('>3I',data)
                empty=magic==TPL_MAGIC and count==0 and 12<=desc<=len(data)
            if empty:
                images=[];empty_palettes.append({'file':file,'context':context,'tpl_offset':offset})
            else:
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
            if rel.endswith('.arc') and rel not in source_files:
                # Room source TPLs are inside the original compressed container.
                # Reuse the recovered offline decoder and the same qualification
                # traversal; do not treat a viewer package as a source archive.
                container=source_files.get(rel[:-4]+'.das')
                if container is None:
                    errors.append({'file':rel,'error':'source room container absent'});continue
                try:
                    mirror.prepare_room_archive(rel[:-4]+'.das',container.read_bytes())
                except (ValueError,RuntimeError) as exc:
                    errors.append({'file':rel,'error':str(exc)})
            elif rel not in source_files:
                errors.append({'file':rel,'error':'source file absent'});continue
            else:
                mirror.convert_file(rel,bytearray(source_files[rel].read_bytes()))
            # Reuse the existing qualification gate, independently of image export.
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w',suffix='.txt') as required:
            required.write('\n'.join(paths));required.flush()
            errors.extend({'error':p} for p in mirror.check_required(mirror.REPORT[report_start:],required.name))
    finally:mirror.TPL_OBSERVER=previous_observer
    report={'entries':entries,'errors':errors,'empty_palettes':empty_palettes,'unique_images':len(set(e['key'] for e in entries)),
            'presentation':'Existing RGB565/ARGB4444 quantization; source dimensions/texels retained before quantization, padding only; visual acceptance pending.'}
    (dest/'native-ui-report.json').write_text(json.dumps(report,indent=2))
    return report

# Compact contracts are explicitly selected: r100 scenery/model/effect tables
# and the qualified core HUD table. Keep core noise, card images, font data,
# palettes, mip chains and unreviewed CPU consumers resident.
_NATIVE_RECORD = struct.Struct('<8s6I')
_NATIVE_MAGIC = b'R4NREF\0\0'
_NATIVE_TABLE_MAGIC = b'R4NTBL\0\0'


def compact_spans(decoded, references, ranges):
    """Replace sorted non-overlapping source spans and rebase observed offsets.

    Returns the compact bytes and original-to-resident offset mapping. A retained
    reference into a discarded span is rejected, never silently redirected.
    """
    for previous,current in zip(ranges,ranges[1:]):
        if previous[1]>current[0]:raise ValueError('overlapping replacement spans')
    def mapped(offset):
        saved=0
        for a,b,record in ranges:
            if offset<a or (offset==a and a!=b):break
            if offset<b:raise ValueError('retained offset enters replaced span')
            saved+=b-a-len(record)
        return offset-saved
    out=bytearray();cursor=0
    for a,b,record in ranges:
        out+=decoded[cursor:a]+record;cursor=b
    out+=decoded[cursor:]
    for field,base,value in references:
        struct.pack_into('<I',out,mapped(field),mapped(base+value)-mapped(base))
    return out,mapped


def select_upload_only(decoded, palettes, textures, allowed):
    """Existing qualified image selection, shared by room/core/enemy producers."""
    selected=[];retained=[];seen={}
    for tpl_off,raw,ctx in palettes:
        if not allowed(ctx):
            continue
        count,desc=struct.unpack_from('>2I',raw,4)
        if not count:continue
        images=parse_tpl(raw)
        for i,image in enumerate(images):
            header,clut=struct.unpack_from('>2I',raw,desc+i*8)
            pixel=struct.unpack_from('>I',raw,header+8)[0]
            lo,hi=raw[header+33:header+35]
            reason=None
            if clut or image.palette_data:reason='palette/CPU semantics retained'
            elif lo or hi:reason='source mip chain retained'
            elif image.format in (8,9):reason='indexed source retained'
            if reason:
                retained.append({'context':ctx,'image':i,'reason':reason});continue
            key,identity=image_identity(image)
            package_path=textures/(key+'.re4tex')
            # Verify the existing file against the existing deterministic converter
            # in memory. No candidate encoder or output texture file is written.
            reference,_=build_package([image],[MaterialBinding('source',0,None)],
                twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            if not package_path.is_file() or package_path.read_bytes()!=reference:
                raise ValueError('missing or non-reference native texture: '+key)
            a=tpl_off+pixel;b=a+len(image.data)
            if len(image.data)<32 or a%32 or b%32 or b>len(decoded):
                raise ValueError('external texture payload violates source alignment/range')
            crc,fnv=(int(x,16) for x in key.split('-'))
            record=_NATIVE_RECORD.pack(_NATIVE_MAGIC,crc,fnv,image.width,image.height,image.format,len(image.data))
            entry={'context':ctx,'image':i,'key':key,'source_header':tpl_off+header,
                   'source_tpl':tpl_off,'source_payload':a,'source_bytes':len(image.data),
                   'source_sha256':hashlib.sha256(identity).hexdigest(),
                   'native_package_sha256':hashlib.sha256(reference).hexdigest()}
            if a in seen:
                if seen[a][0]!=b or seen[a][1]!=record:raise ValueError('incompatible shared payload')
            else:seen[a]=(b,record)
            selected.append(entry)
    ranges=sorted((a,b,record) for a,(b,record) in seen.items())
    return ranges, selected, retained


def native_identity_index(selected, mapped, original_bytes, resident_bytes):
    """Serialize the existing NTR records; archive placement belongs to its loader."""
    table=bytearray()
    for item in selected:
        table+=struct.pack('<3I',mapped(item['source_payload']),mapped(item['source_header']),mapped(item['source_tpl']))
        item['resident_payload']=mapped(item['source_payload'])
        item['resident_header']=mapped(item['source_header'])
        item['resident_tpl']=mapped(item['source_tpl'])
    table_size=(32+len(table)+31)&~31
    header=struct.pack('<8s6I',_NATIVE_TABLE_MAGIC,1,len(selected),12,zlib.crc32(table)&0xffffffff,original_bytes,resident_bytes)
    return header+table+bytes(table_size-32-len(table))


def _compact_upload_only(decoded, references, palettes, textures, allowed, effect_ranges=(), effect_entries=()):
    """Shared source-layout transform, using the existing converter's offsets."""
    import compact_effect_records as effects
    n=struct.unpack_from('<I',decoded)[0]
    offsets=struct.unpack_from('<%dI'%n,decoded,16)
    tags=[bytes(decoded[16+4*n+4*i:20+4*n+4*i]) for i in range(n)]
    extra=1+bool(effect_entries)
    if min(x for x in offsets if x)<16+8*(n+extra):
        raise ValueError('archive lacks spare native-identity header slot')
    ranges,selected,retained=select_upload_only(decoded,palettes,textures,allowed)
    if not ranges:raise ValueError('no qualified upload-only payloads')
    out,mapped=compact_spans(decoded,references,sorted(ranges+list(effect_ranges)))
    table_size=(32+12*len(selected)+31)&~31
    effect_size=((32+12*len(effect_entries)+31)&~31) if effect_entries else 0
    final_bytes=len(out)+table_size+effect_size
    new_offsets=[];new_tags=[]
    if effect_entries:
        new_offsets.append(len(out));new_tags.append(b'ESQ\0')
        out+=effects.identity_index(effect_entries,mapped,final_bytes)
    new_offsets.append(len(out));new_tags.append(b'NTR\0')
    out+=native_identity_index(selected,mapped,len(decoded),final_bytes)
    struct.pack_into('<I',out,0,n+extra)
    for i,off in enumerate(new_offsets):struct.pack_into('<I',out,16+4*(n+i),off)
    out[16+4*(n+extra):16+8*(n+extra)]=b''.join(tags+new_tags)
    report={'original_archive_bytes':len(decoded),'resident_archive_bytes':len(out),
        'archive_recovery_bytes':len(decoded)-len(out),'identity_table_bytes':table_size,
        'replacement_record_bytes':32*len(ranges),'selected':selected,'retained':retained}
    if effect_entries:
        for e in effect_entries:e['resident_offset']=mapped(e['source_offset'])
        report['effects']={'entries':effect_entries,'index_bytes':effect_size,
            'recovery_bytes':sum(b-a-len(v) for a,b,v in effect_ranges)-effect_size,
            'policy':'resident exact records; unsupported records/trailers retained; no I/O'}
    return out,report


def compact_room(source_file, textures, destination, compact_effects=False):
    """Prepare one smaller qualified .dar through the existing room builder.

    Uses the converter's recorded relative offsets, not a second archive parser
    or runtime lazy loader. No texture files are generated by this operation.
    """
    source_file, textures, destination = map(Path, (source_file, textures, destination))
    if source_file.name.lower() != 'r100.das':
        raise ValueError('only the reviewed r100 consumer contract is supported')
    if destination.exists():
        raise FileExistsError(destination)
    rel='st1/r100.das';arc='st1/r100.arc'
    source=source_file.read_bytes();references=[];palettes=[];sequences=[]
    previous_tpl,previous_offsets,previous_seq=mirror.TPL_OBSERVER,mirror.OFFSET_OBSERVER,mirror.SEQUENCE_OBSERVER
    start=len(mirror.REPORT)
    mirror.TPL_OBSERVER=lambda file,off,data,ctx: palettes.append((off,data,ctx))
    mirror.OFFSET_OBSERVER=lambda file,field,base,value: references.append((field,base,value)) if file==arc else None
    mirror.SEQUENCE_OBSERVER=lambda file,off,data,ctx: sequences.append((off,data,ctx)) if file==arc else None
    try:
        _,decoded=mirror.prepare_room_archive(rel,source)
        container=bytearray(source);mirror.convert_file(rel,container)
    finally:
        mirror.TPL_OBSERVER,mirror.OFFSET_OBSERVER,mirror.SEQUENCE_OBSERVER=previous_tpl,previous_offsets,previous_seq
    coverage=mirror.REPORT[start:]
    # This is the existing whole-archive + sound qualification gate, before any
    # candidate transformation. It cannot be replaced by sidecar existence.
    mirror.prepare_native_room(rel,container,decoded,coverage)
    n=struct.unpack_from('<I',decoded)[0]
    offsets=struct.unpack_from('<%dI'%n,decoded,16)
    tags=[bytes(decoded[16+4*n+4*i:20+4*n+4*i]) for i in range(n)]
    if n!=51 or tags[5]!=b'SMD\0' or tags[8]!=b'EFF\0' or tags[10]!=b'ITM\0' or min(offsets)<16+8*(n+1):
        raise ValueError('r100 archive layout differs from reviewed contract')
    eff=offsets[8];eff_ids=eff+struct.unpack_from('<I',decoded,eff+4)[0]
    num_eff=struct.unpack_from('<I',decoded,eff_ids)[0]
    ids=[struct.unpack_from('<H',decoded,eff_ids+4+i*8)[0] for i in range(num_eff)]
    model_slots={26,28,33,36,38,46}
    def allowed(ctx):
        if ctx.startswith(arc+'#8/tpl'):
            ident=int(ctx.rsplit('tpl',1)[1])
            # Espgen42/45 consume 0xFE as CPU noise. Never externalize it.
            return ident<len(ids) and ids[ident]!=0xfe
        return ctx in (arc+'#5/TPL0',arc+'#10/item') or any(ctx==arc+'#'+str(i) for i in model_slots)
    effect_ranges=[];effect_entries=[];skipped=[]
    if compact_effects:
        import compact_effect_records as effects
        # These EFF owners all register through EspDataLoad. EST access uses the
        # existing opaque-reference adapter; SST/path/model data remain raw.
        families=[arc+'#8']+[arc+'#11/'+name+'.eff' for name in ('et00','et01','et02','et0d','obm2b')]
        if tags[11]!=b'ETM\0' or struct.unpack_from('<I',decoded,4)[0]:
            raise ValueError('r100 effect ownership layout differs from reviewed contract')
        for family in families:
            qualified=[]
            for off,data,ctx in sequences:
                if ctx!=family+'/est':continue
                used=48+300*struct.unpack_from('<H',data)[0]
                if used>len(data):raise ValueError('truncated room sequence')
                if any(data[used:]):
                    skipped.append({'source_offset':off,'source_bytes':len(data),'reason':'unexplained trailer retained unchanged'})
                else:qualified.append((off,data,ctx))
            er,ee=effects.prepare_sequences(qualified,family)
            effect_ranges+=er;effect_entries+=ee
        effect_ranges.sort();effect_entries.sort(key=lambda e:e['source_offset'])
        if not effect_entries:raise ValueError('no qualified room sequences')
    out,stats=_compact_upload_only(decoded,references,palettes,textures,allowed,effect_ranges,effect_entries)
    if compact_effects:stats['effects']['skipped']=skipped
    _,packaged=mirror.prepare_native_room(rel,container,out,coverage)
    report={'contract':'r100-resident-effects-v1' if compact_effects else 'r100-upload-only-v1','source_file':str(source_file),
            'source_sha256':hashlib.sha256(source).hexdigest(),
            **stats,
            'qualification':coverage,'loading':'source DVD queue reads compact type-0 directly; original sound container retained',
            'limits':'No mip/palette/CPU-noise removal; no source-archive saving accepted before target measurement.'}
    destination.mkdir()
    (destination/'r100.dar').write_bytes(packaged)
    (destination/'r100.arc').write_bytes(out)
    (destination/'compact-room-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def compact_core(source_file, textures, destination, include_effects=False, compact_effects=False):
    """Externalize core HUD #25 and optionally the qualified effect #1 table.

    Optional EST packing reuses the resident codec for audited core owners 0/D1.
    Nonzero sequence trailers stay raw; original heads and all records survive.
    Other families retain exact converted bytes and qualification status.
    The optional effect family requires its Path/PathVtx conversion as well;
    it never qualifies VIB/SAT. CPU noise, palettes and mip chains stay resident.
    """
    source_file,textures,destination=map(Path,(source_file,textures,destination))
    if source_file.name.lower()!='core.das':raise ValueError('expected core.das')
    if destination.exists():raise FileExistsError(destination)
    rel='etc/core.das';slots=(1,25) if include_effects else (25,)
    families=[rel+':0#'+str(i) for i in slots]
    source=source_file.read_bytes();container=bytearray(source);references=[];palettes=[];sequences=[]
    old_tpl,old_offsets,old_seq=mirror.TPL_OBSERVER,mirror.OFFSET_OBSERVER,mirror.SEQUENCE_OBSERVER
    start=len(mirror.REPORT)
    mirror.TPL_OBSERVER=lambda file,off,data,ctx: palettes.append((off,data,ctx))
    mirror.OFFSET_OBSERVER=lambda file,field,base,value: references.append((field,base,value))
    mirror.SEQUENCE_OBSERVER=lambda file,off,data,ctx:sequences.append((off,data,ctx))
    try:mirror.convert_file(rel,container)
    finally:mirror.TPL_OBSERVER,mirror.OFFSET_OBSERVER,mirror.SEQUENCE_OBSERVER=old_tpl,old_offsets,old_seq
    coverage=mirror.REPORT[start:]
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w') as required:
        required.write('\n'.join(families+([rel+':0#1',rel+':0#16'] if compact_effects else []))+'\n');required.flush()
        bad=mirror.check_required(coverage,required.name)
    # Sound semantics stay on the original DVD queue, with the converted nested
    # container retained verbatim. Require its existing conversion to succeed.
    bad += [str(e.get('part')) for e in coverage if '/' in str(e.get('part','')) and
            (not e.get('handled') or e.get('complete') is not True or e.get('error'))]
    if bad:raise ValueError('unqualified selected core dependency: '+', '.join(bad))
    slot=mirror.native_payload_slot(container)
    size,base=struct.unpack_from('<I4xI',container,slot+4)
    decoded=container[base:base+size]
    n=struct.unpack_from('<I',decoded)[0]
    offsets=struct.unpack_from('<%dI'%n,decoded,16)
    checked_slots=set(slots).union((1,16) if compact_effects else ())
    if n!=36 or any(decoded[16+4*n+i*4:20+4*n+i*4]!=b'EFF\0' for i in checked_slots):
        raise ValueError('core layout differs from reviewed contract')
    ids_by_family={}
    for slot,family in zip(slots,families):
        eff=offsets[slot];ids_at=eff+struct.unpack_from('<I',decoded,eff+4)[0]
        count=struct.unpack_from('<I',decoded,ids_at)[0]
        ids_by_family[family]=[struct.unpack_from('<H',decoded,ids_at+4+i*8)[0] for i in range(count)]
    def allowed(ctx):
        for family,ids in ids_by_family.items():
            if ctx.startswith(family+'/tpl'):
                index=int(ctx.rsplit('tpl',1)[1])
                return index<len(ids) and ids[index]!=0xfe
        return False
    refs=[(f-base,b-base,v) for f,b,v in references if base<=f<base+size]
    palettes=[(o-base,d,c) for o,d,c in palettes if base<=o<base+size]
    effect_ranges=[];effect_entries=[];skipped=[]
    if compact_effects:
        import compact_effect_records as effects
        if struct.unpack_from('<I',decoded,4)[0]:raise ValueError('core REL not supported')
        for i in (1,16):
            family=rel+':0#'+str(i);qualified=[]
            for o,data,ctx in sequences:
                if ctx!=family+'/est':continue
                used=48+300*struct.unpack_from('<H',data)[0]
                if used>len(data):raise ValueError('truncated core sequence')
                if any(data[used:]):
                    skipped.append({'source_offset':o-base,'source_bytes':len(data),'reason':'unexplained trailer retained unchanged'})
                else:qualified.append((o-base,data,ctx))
            er,ee=effects.prepare_sequences(qualified,family)
            effect_ranges+=er;effect_entries+=ee
        effect_ranges.sort();effect_entries.sort(key=lambda e:e['source_offset'])
        if not effect_entries:raise ValueError('no qualified core sequences')
    out,stats=_compact_upload_only(decoded,refs,palettes,textures,allowed,effect_ranges,effect_entries)
    if compact_effects:stats['effects']['skipped']=skipped
    # A whole unselected family can move, but its internal offsets and all
    # payload bytes must remain unchanged, including presently raw sections.
    def body(data,i):
        num=struct.unpack_from('<I',data)[0];ofs=struct.unpack_from('<%dI'%num,data,16)
        return data[ofs[i]:min([o for o in ofs if o>ofs[i]]+[len(data)])]
    for i in range(n):
        if i not in checked_slots and offsets[i] and body(decoded,i)!=body(out,i):
            raise ValueError('unselected core family changed: '+str(i))
    packaged=mirror.replace_native_payload(container,out)
    report={'contract':'core-resident-effects-v1' if compact_effects else 'core-effects-hud-upload-only-v1' if include_effects else 'core-hud-upload-only-v1','source_file':str(source_file),
        'source_sha256':hashlib.sha256(source).hexdigest(),**stats,
        'qualification':coverage,'qualified_selection':sorted(set(families+([rel+':0#1',rel+':0#16'] if compact_effects else []))),
        'retained_unqualified':[e for e in coverage if e.get('complete') is False or not e.get('handled')],
        'loading':'compact type-0 reads directly into matching fixed core reservation; original sound blocks retained',
        'limits':'Selected upload-only textures and optional audited EST readers only; other core coverage unchanged. Target savings require a smaller actual reservation. Debug effect editing is not qualified.'}
    destination.mkdir();(destination/'core.das').write_bytes(packaged)
    (destination/'core.arc').write_bytes(out)
    (destination/'compact-core-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    if '--compact-room' in sys.argv or '--compact-core' in sys.argv:
        import argparse
        parser=argparse.ArgumentParser(description='Compact reviewed source texture families using existing native packages')
        choice=parser.add_mutually_exclusive_group(required=True)
        choice.add_argument('--compact-room',type=Path)
        choice.add_argument('--compact-core',type=Path)
        parser.add_argument('--core-effects',action='store_true',help='also externalize qualified core EFF #1 upload-only images')
        parser.add_argument('--compact-core-est',action='store_true',help='lossless resident packing for qualified core EST #1/#16')
        parser.add_argument('--compact-room-est',action='store_true',help='lossless resident packing for qualified r100 EST owners')
        parser.add_argument('--textures',type=Path,required=True)
        parser.add_argument('--output',type=Path,required=True)
        args=parser.parse_args()
        fn,source=(compact_room,args.compact_room) if args.compact_room else (compact_core,args.compact_core)
        if args.core_effects and not args.compact_core:parser.error('--core-effects requires --compact-core')
        if args.compact_core_est and not args.compact_core:parser.error('--compact-core-est requires --compact-core')
        if args.compact_room_est and not args.compact_room:parser.error('--compact-room-est requires --compact-room')
        report=compact_core(source,args.textures,args.output,args.core_effects,args.compact_core_est) if args.compact_core else compact_room(source,args.textures,args.output,args.compact_room_est)
        print('compact archive:',report['original_archive_bytes'],'->',report['resident_archive_bytes'],
              'recovery',report['archive_recovery_bytes'],'identities',len(report['selected']))
    else:
        source,manifest,dest=map(Path,sys.argv[1:])
        paths=[s.strip().lower() for s in manifest.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
        report=prepare(source,paths,dest)
        print('native UI images:',report['unique_images'],'errors:',report['errors'])
        sys.exit(2 if report['errors'] else 0)
