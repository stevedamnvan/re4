#!/usr/bin/env python3
"""Bounded source-reference audit over an EXISTING em12 residency inventory.

Not an extractor, reachability prover or production prefetch selector. Expands
known WALK/BACK macros, preserves source ARC (+4 header-word) indices, and
reports indirect/event closure as unresolved. Never infers need from a replay.
"""
from pathlib import Path
import argparse, hashlib, json, re
ROOT=Path(__file__).resolve().parents[3]
NUMBER=r'(0x[0-9A-Fa-f]+|[0-9]+)'

def audit(source, inventory):
    source=Path(source);text=source.read_text();entries=inventory['entries']
    by={i+4:e for e in entries for i in e['slots']}
    functions={}
    for m in re.finditer(r'^(?:static )?(?:void|int|bool|u32|f32)\s+(\w+)\([^;\n]*\)\s*\n\{',text,re.M):
        # Source functions close at column zero. No attempt to resolve function
        # pointers, preprocessing alternatives or arbitrary constant expressions.
        end=text.find('\n}',m.end());body=text[m.start():end+2]
        indices={int(x,0) for x in re.findall(r'PL_ARC_PTR\(em->subArc,\s*'+NUMBER+r'\s*\)',body)}
        for base in re.findall(r'EM10_WALK_MOT\(\s*'+NUMBER+r'\s*\)',body):
            indices.update(range(int(base,0),int(base,0)+6))
        for a,b in re.findall(r'EM10_BACK_MOT\(\s*'+NUMBER+r'\s*,\s*'+NUMBER+r'\s*\)',body):
            indices.update((int(a,0),int(b,0)))
        dynamic=[x.strip() for x in re.findall(r'PL_ARC_PTR\(em->subArc,\s*([^)]*)\)',body)
                 if not re.fullmatch(NUMBER,x.strip())]
        functions[m[1]]={'line':text.count('\n',0,m.start())+1,
            'indices':sorted(indices&by.keys()),'calls':re.findall(r'\b(em10\w+)\(',body),'dynamic':dynamic}
    groups={
        'response':[n for n in functions if '_Dm_' in n or '_Die_' in n or 'DmSet' in n],
        'locomotion':[n for n in functions if any(k in n for k in ['SetWaitMotion','SetWalkMotion','SetDashMotion','_Wait','_Walk','_Dash','_Back','_Goto','_Stay','_Turn180','_SideStep','_Find','_Threat','_DownWake'])],
        'cabin_attack':[n for n in functions if any(k in n for k in ['AxeAtk','Catch','NeckHang','Backhold','_Crash','R100'])],
    }
    report={'source':str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else source.name,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_complete':False,'profile':'diagnostic conservative literal/macro closure',
            'index_contract':'PL_ARC_PTR source ARC word index = inventory entry ordinal + 4',
            'unresolved':['indirect R1 dispatch and event-selected motion reachability',
                'initialization/module Work-table aliases outside em10.cpp',
                'all active instances, blend/shape/camera concurrency and release boundaries'],
            'consumer_contract':'R4_NATIVE_PRIMITIVE_LIFETIME_CHECKPOINT.md#d325-motion-key-residency-candidate'}
    union=set()
    for name,seeds in groups.items():
        closure=set(seeds)
        while True:
            old=len(closure);closure.update(c for n in list(closure) for c in functions[n]['calls'] if c in functions)
            if len(closure)==old:break
        ids=set(i for n in closure for i in functions[n]['indices']);keys={by[i]['key']:by[i] for i in ids};union.update(ids)
        report[name]={'functions':sorted(closure),'source_arc_indices':sorted(ids),'unique':len(keys),
            'bytes':sum(e['bytes'] for e in keys.values()),
            'dynamic_references':{n:functions[n]['dynamic'] for n in sorted(closure) if functions[n]['dynamic']}}
    keys={by[i]['key']:by[i] for i in union}
    report['union']={'source_arc_indices':sorted(union),'keys':sorted(keys),'unique':len(keys),'bytes':sum(e['bytes'] for e in keys.values())}
    all_ids={i for f in functions.values() for i in f['indices']};all_keys={by[i]['key']:by[i] for i in all_ids}
    report['all_direct_source_references']={'unique':len(all_keys),'bytes':sum(e['bytes'] for e in all_keys.values())}
    report['unresolved_entries']=[{'source_arc_indices':[i+4 for i in e['slots']],'bytes':e['bytes']} for e in entries if e['key'] not in all_keys]
    report['all_retained_keys_bytes']=sum(e['bytes'] for e in entries)
    report['acceptance']='No production hot-set certification. Do not promote on warm-profile success alone.'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--source',type=Path,default=ROOT/'src/em10/em10.cpp')
    a=p.parse_args()
    if a.output.exists():p.error('fresh audit output required')
    result=audit(a.source,json.loads(a.inventory.read_text()))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('source_complete','union','all_direct_source_references','all_retained_keys_bytes')},indent=2))
