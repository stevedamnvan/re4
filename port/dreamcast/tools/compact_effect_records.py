"""Lossless, resident EST record layout for audited effect consumers only.

Original 48-byte heads survive. Each sequence holds record offsets followed by
raw or zero-word-elided records. No disc cache, clip selection, float conversion,
RNG call or source effect is removed. Family qualification belongs to the caller;
unknown/retaining consumers stay raw.
"""
import struct, zlib
MAGIC=b'R4ESQTBL'
# Audited EspSeqSet/EfmSeqSet leaves copy their parameters. cEsp0e retains gen;
# it and unreviewed IDs keep an ordinary record. Espgen00 retains a reference
# which its native SetFreeWork/EspSeqSet adapters preserve and resolve.
COPY_IDS={0,1,2,3,7,9,11,16,17,22,26,64,69,70,74,254}

def eligible(record):
    return record[1] in COPY_IDS and (record[264]==0 or (record[264]==1 and record[265]==0))

def pack_record(record):
    if len(record)!=300:raise ValueError('effect record must be 300 bytes')
    words=struct.unpack('<75I',record);masks=[0,0,0];values=[]
    for i,w in enumerate(words):
        if w:masks[i//32]|=1<<(i%32);values.append(w)
    return struct.pack('<%dI'%(3+len(values)),*masks,*values)

def unpack_record(data):
    if len(data)<12 or len(data)%4:raise ValueError('effect record bounds')
    m=struct.unpack_from('<3I',data)
    if m[2]>>11:raise ValueError('effect mask overflow')
    if len(data)!=12+4*sum(x.bit_count() for x in m):raise ValueError('effect word count')
    words=[];cursor=12
    for i in range(75):
        v=0
        if m[i//32]&(1<<(i%32)):v=struct.unpack_from('<I',data,cursor)[0];cursor+=4
        words.append(v)
    return struct.pack('<75I',*words)

def prepare_sequences(sequences, family):
    ranges=[];entries=[];seen=set()
    for off,raw,ctx in sorted(sequences):
        if ctx!=family+'/est':continue # no new owner/SST/path contract
        if off in seen:continue
        seen.add(off);n=struct.unpack_from('<H',raw)[0]
        if not n:continue
        used=48+300*n
        if used>len(raw):raise ValueError('effect sequence truncated')
        # Do not discard unexplained trailer bytes. Alignment padding survives.
        if any(raw[used:]):raise ValueError('nonzero effect trailer')
        out=bytearray(raw[:48]+bytes(4*n));packed=kept=0
        for i in range(n):
            rec=raw[48+300*i:48+300*(i+1)];encoded=pack_record(rec)
            compact=eligible(rec) and len(encoded)<300
            if compact:
                if unpack_record(encoded)!=rec:raise ValueError('effect bitwise roundtrip')
                payload=encoded;packed+=1
            else:payload=rec;kept+=1
            struct.pack_into('<I',out,48+4*i,len(out)|int(compact))
            out+=payload
        out+=bytes((-len(out))%32)
        if len(out)>=len(raw):continue
        ranges.append((off,off+len(raw),bytes(out)))
        entries.append({'source_offset':off,'source_bytes':len(raw),'resident_bytes':len(out),
                        'records':n,'packed_records':packed,'raw_records':kept,
                        'restored_crc32':zlib.crc32(raw[:used])&0xffffffff})
    return ranges,entries

def identity_index(entries,mapped,archive_bytes):
    table=b''.join(struct.pack('<3I',mapped(e['source_offset']),e['resident_bytes'],e['records']) for e in entries)
    data=struct.pack('<8s6I',MAGIC,1,len(entries),12,zlib.crc32(table)&0xffffffff,archive_bytes,0)+table
    return data+bytes((-len(data))%32)
