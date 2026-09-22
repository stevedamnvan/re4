#!/usr/bin/env python3
"""Inventory private PS2 scenario BINs using the pinned JADERLINK decoder.

This orchestration reads container identities and instance bindings, not VIF
vertex formats. Every BIN is reported; unsupported containers/decoder failures
remain rejected. Authored attributes go to private gzip JSONL, never source Git.
"""
import argparse,collections,gzip,hashlib,json,math,os,pathlib,struct,subprocess
from audit_ps2_rigid32 import audit_rigid32
from convert_room_obj import smd_work,model_bounds

def container(path):
 d=path.read_bytes()
 if len(d)<16:raise ValueError('short SMD')
 magic,count,bins,tpl,_=struct.unpack_from('<HHIII',d)
 if magic!=0x40:raise ValueError('unqualified SMD magic')
 if not (count and bins==16+count*64 and bins<=tpl<=len(d)):
  # Known audit lead only: PS2 disc block 01 has a LE magic and BE body.
  bc,bb,bt=struct.unpack_from('>HII',d,2)
  if bc and 16+bc*72<=bb<=16+bc*72+64 and bb<=bt<=len(d):
   works=[smd_work(d,i) for i in range(bc)];n=max(w['bin'] for w in works)+1
   starts=[bb+struct.unpack_from('>I',d,bb+i*4)[0] for i in range(n)];records=[]
   for i,start in enumerate(starts):
    end=min([x for x in starts if x>start]+[bt]);b=d[start:end];model_bounds(d,i)
    vc,nc=struct.unpack_from('>HH',b,0x38);flags=struct.unpack_from('>I',b,0x20)[0];no=struct.unpack_from('>I',b,0x34)[0];ns=4 if flags&0x20000000 else 8
    if not nc or no+nc*ns>len(b):raise ValueError('GC normal array extent')
    np=struct.unpack_from('>H',b,0x1a)[0];cursor=struct.unpack_from('>I',b,0x1c)[0];materials=[]
    for mi in range(np):
     if cursor+32>len(b):raise ValueError('GC material header extent')
     stream=struct.unpack_from('>I',b,cursor+24)[0]
     if cursor+32+stream>len(b):raise ValueError('GC primitive stream extent')
     materials.append(dict(index=mi,descriptor=b[cursor:cursor+32].hex(),texture=b[cursor+12],stream_bytes=stream));cursor+=32+stream
    records.append(dict(bin=i,offset=start,bytes=end-start,status='audited-GC-layout',kind='NORMAL_GC_LAYOUT',position_records=vc,normal_records=nc,materials=materials,instances=[j for j,w in enumerate(works) if w['bin']==i],render_qualified=False))
   return dict(path=str(path),sha256=hashlib.sha256(d).hexdigest(),bytes=len(d),status='mixed-endian-GC-body-audit',instances=bc,bins=records,qualification='BE scenario/model structures in PS2 disc member, header magic LE; actual PS2 use not established')
  raise ValueError('unqualified SMD record layout')
 instances=[]
 for i in range(count):
  v=struct.unpack_from('<12f4B3I',d,16+i*64)
  if not all(math.isfinite(x) for x in v[:12]):raise ValueError('nonfinite instance')
  instances.append(dict(instance=i,position=v[:3],rotation=v[4:7],scale=v[8:11],bin=v[12],tpl=v[13],smx=v[15],flags=v[17]))
 n=max(v['bin'] for v in instances)+1
 if bins+n*4>tpl:raise ValueError('BIN table exceeds range')
 pointers=struct.unpack_from('<'+str(n)+'I',d,bins)
 starts=sorted(set(bins+p for p in pointers if p))
 if any(s<bins+n*4 or s>=tpl for s in starts):raise ValueError('BIN extent')
 ends={s:next((p for p in starts if p>s),tpl) for s in starts}
 records=[]
 for i,p in enumerate(pointers):
  start=bins+p
  records.append(dict(bin=i,offset=start if p else None,bytes=ends[start]-start if p else 0,instances=[v for v in instances if v['bin']==i],status='pending' if p else 'empty'))
 return dict(path=str(path),sha256=hashlib.sha256(d).hexdigest(),bytes=len(d),status='qualified-container',instances=count,bins=records)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);p.add_argument('--decoder',type=pathlib.Path,required=True);p.add_argument('--assembly',type=pathlib.Path,required=True);a=p.parse_args()
 a.output.mkdir(exist_ok=False);summary={'decoder':str(a.decoder),'assembly':str(a.assembly),'assembly_sha256':hashlib.sha256(a.assembly.read_bytes()).hexdigest(),'containers':[]}
 requests=[];lookup={}
 for smd in sorted(a.input.rglob('*.SMD')):
  c=container(smd);summary['containers'].append(c)
  for r in c.get('bins',[]):
   if r['status']=='pending':requests.append(f"{smd}\t{r['bin']}\t{r['offset']}\t{r['bytes']}\n");lookup[(str(smd),r['bin'])]=r
 request=a.output/'requests.tsv';request.write_text(''.join(requests))
 source_cache={}
 env=dict(os.environ,MONO_PATH=str(a.assembly.parent));proc=subprocess.Popen(['mono',str(a.decoder),str(request)],stdout=subprocess.PIPE,text=True,env=env)
 with gzip.open(a.output/'source-attributes.jsonl.gz','wt',encoding='utf8') as raw:
  for line in proc.stdout:
   row=json.loads(line)
   if row['smd'] not in source_cache:source_cache[row['smd']]=pathlib.Path(row['smd']).read_bytes()
   payload=source_cache[row['smd']][row['offset']:row['offset']+row['bytes']]
   try:row.update(audit_rigid32(payload))
   except ValueError:pass
   raw.write(json.dumps(row)+'\n');r=lookup[(row['smd'],row['bin'])];r.update({k:v for k,v in row.items() if k not in ('smd','bin','materials')})
   if row['status'] in ('decoded','audited-rigid32'):
    r['materials']=[];rgb=[];alphas=set();positions=set()
    for m in row['materials']:
     kinds=collections.Counter();nv=nt=0
     for s in m['segments']:
      kinds[s['kind']]+=len(s['vertices']);nv+=len(s['vertices'])
      for j,v in enumerate(s['vertices']):
       positions.add(tuple(x*s['scale'] for x in v[:3]));nt+=int(j>=2 and v[9]==0)
       if s['kind'] in ('COLOR','NORMAL_WITH_COLOR'):rgb.append(v[5:8]);alphas.add(v[8])
     r['materials'].append(dict(index=m['material'],descriptor=m['descriptor'],records=nv,triangles=nt,kinds=dict(kinds)))
    r['unique_local_positions']=len(positions)
    if rgb:r['rgb_range_raw']=[list(map(min,zip(*rgb))),list(map(max,zip(*rgb)))];r['rgb_divisor']=128;r['records_above_one']=sum(any(x>128 for x in v) for v in rgb);r['alpha_values_raw']=sorted(alphas)
 if proc.wait():raise RuntimeError('decoder driver failed')
 summary['counts']=dict(collections.Counter(r.get('kind',r['status']) for c in summary['containers'] for r in c.get('bins',[])))
 (a.output/'inventory.json').write_text(json.dumps(summary,indent=2));print(json.dumps({'counts':summary['counts'],'containers':[(pathlib.Path(c['path']).name,c['status']) for c in summary['containers']]}))
if __name__=='__main__':main()