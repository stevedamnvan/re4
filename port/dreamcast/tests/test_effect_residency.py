"""Exercise the real native EST adapter and recovered repeating constructor."""
from pathlib import Path
import json,struct,subprocess,sys,tempfile,unittest,zlib,shutil
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'port/dreamcast/tools'))
import compact_effect_records as codec
from test_motion_residency import headers,SUPPORT

def function(text,name):
    start=text.index(name);start=text.rfind('\n',0,start)+1
    brace=text.index('{',start);depth=1;i=brace+1
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}');i+=1
    return text[start:i]

def fixture(path, core=False):
    records=[]
    for i in range(24):
        r=bytearray(300);r[1]=11;r[264]=i%2;r[265]=0
        struct.pack_into('<I',r,12,0x80000000 if i==0 else i*1024) # negative zero bits survive
        struct.pack_into('<I',r,16,0x7fc12345) # NaN payload, no float arithmetic
        r[268]=i;r[269]=i%3;r[270]=i;r[271]=255;r[272]=i+4
        records.append(bytes(r))
    r=bytearray(records[0]);r[1]=14;records.append(bytes(r)) # retaining sprite must stay raw
    r=bytearray(records[1]);r[265]=2;records.append(bytes(r)) # unadapted controller stays raw
    seq=struct.pack('<H',len(records))+bytes(46)+b''.join(records)
    seq+=bytes((-len(seq))%32)
    ranges,entries=codec.prepare_sequences([(64,seq,'em/em12.drs:0#0/est')],'em/em12.drs:0#0')
    body=bytearray(64)+ranges[0][2];off=len(body)
    idx=codec.identity_index(entries,lambda n:n,len(body)+64+64)
    assert len(idx)==64
    body+=idx+bytes(64)
    struct.pack_into('<2I',body,0,2,len(body)-64);struct.pack_into('<2I',body,16,64,off)
    body[24:32]=b'EFF\0ESQ\0'
    if core:
        body=body[:-64];struct.pack_into('<I',body,4,0);struct.pack_into('<I',body,off+24,len(body))
    (path/'candidate.arc').write_bytes(body)
    (path/'reference.bin').write_bytes(seq)
    (path/'heads.bin').write_bytes(struct.pack('<3I',64,0,len(records)))
    return body,records

SETUP=r"""
#include "native_effect.h"
using u8=unsigned char;using s8=signed char;using u16=unsigned short;using s16=short;
using u32=unsigned;using f32=float;struct Vec{float x,y,z;};using Mtx=float[3][4];
struct cModel{unsigned serial;};struct EspSeqOpt{unsigned words[7];};
struct EspgenWork{alignas(16) unsigned char work[512]{};};
unsigned rng_calls;unsigned Rnd(){return ++rng_calls*29;}
void PSMTXCopy(const Mtx a,Mtx b){memcpy(b,a,48);}
"""
MAIN=r"""
int bind(const std::vector<unsigned char>& a){
 return word(a.data()+4)?re4dc_effect_bind((void*)a.data(),a.size()):re4dc_effect_bind_core((void*)a.data(),a.size());
}
int main(int argc,char**argv){
 assert(argc==2);root=argv[1];auto a=read_bytes_file(root+"/candidate.arc"),original=a;
 auto ref=read_bytes_file(root+"/reference.bin"),heads=read_bytes_file(root+"/heads.bin");
 auto bad=a;unsigned esq=0;for(unsigned i=0;i<word(a.data());++i)
  if(!memcmp(a.data()+16+4*word(a.data())+4*i,"ESQ",4))esq=word(a.data()+16+4*i);
 assert(esq);bad[esq+8]=2;assert(!bind(bad));
 // Malformed index, span, count, mask and noncontiguous record starts fail
 // before publishing a binding or reading past the archive.
 for(unsigned test=0;test<6;++test){
  auto broken=a;auto put=[&](unsigned at,unsigned v){memcpy(broken.data()+at,&v,4);};
  unsigned head=word(a.data()+esq+32),first=word(a.data()+head+48)&~1U;
  switch(test){
   case 0:put(esq+32,1);break;
   case 1:put(esq+36,0xffffffe0U);break;
   case 2:put(esq+40,65536);break;
   case 3:put(head+48,3);break;
   case 4:put(head+first+8,0xffffffffU);break;
   case 5:put(head+48+4,word(a.data()+head+48));break;
  }
  if(test<3)put(esq+20,net_crc32le(broken.data()+esq+32,12*word(a.data()+esq+12)));
  assert(!bind(broken));
 }
 assert(bind(a));assert(!bind(a));
 // The persistent core binding must leave all four module bindings available.
 auto module=a,core=a;
 if(!word(module.data()+4)){unsigned end=module.size();module.resize(end+64);memcpy(module.data()+4,&end,4);unsigned total=module.size();memcpy(module.data()+esq+24,&total,4);}
 if(word(core.data()+4)){core.resize(core.size()-64);unsigned zero=0,total=core.size();memcpy(core.data()+4,&zero,4);memcpy(core.data()+esq+24,&total,4);}
 assert(!re4dc_effect_bind(core.data(),core.size()));assert(!re4dc_effect_bind_core(module.data(),module.size()));
 std::vector<std::vector<unsigned char>> other;other.reserve(4);
 for(unsigned i=0;i<(word(a.data()+4)?3U:4U);++i){other.push_back(module);assert(bind(other.back()));}
 if(word(a.data()+4))assert(bind(core));
 auto excess=module;assert(!bind(excess));auto extra_core=core;assert(!bind(extra_core));
 // Room lifetime is independent of all four modules and the persistent core.
 auto room=core,extra_room=core;
 assert(!re4dc_effect_bind_room(module.data(),module.size()));
 assert(re4dc_effect_bind_room(room.data(),room.size()));
 assert(!re4dc_effect_bind_room(extra_room.data(),extra_room.size()));
 auto* room_head=reinterpret_cast<EspSeqData*>(room.data()+word(heads.data()));
 void* room_ref=re4dc_effect_ref(room_head,0);unsigned room_scratch[75];
 assert(!memcmp(re4dc_effect_record_read(room_ref,room_scratch),ref.data()+48,300));
 re4dc_effect_retire_room();re4dc_effect_retire_room();
 bool stale=false;try{re4dc_effect_record_read(room_ref,room_scratch);}catch(const std::runtime_error&){stale=true;}assert(stale);
 assert(!bind(excess));assert(!bind(extra_core)); // other lifetimes untouched
 assert(re4dc_effect_bind_room(extra_room.data(),extra_room.size()));re4dc_effect_retire_room();
 for(auto& m:other)re4dc_effect_unbind(m.data());if(word(a.data()+4))re4dc_effect_unbind(core.data());
 unsigned checked=0,retained=0,raw=0;std::vector<void*> saved;
 for(unsigned group=0;group<heads.size()/12;++group){
  const auto* ent=heads.data()+group*12;auto* head=reinterpret_cast<EspSeqData*>(a.data()+word(ent));
  auto* oldhead=reinterpret_cast<EspSeqData*>(ref.data()+word(ent+4));unsigned n=word(ent+8);
  assert(!memcmp(head,oldhead,48));
  for(unsigned i=0;i<n;++i){
   auto* token=re4dc_effect_ref(head,i);EspGenWork scratch;auto* row=re4dc_effect_read(token,scratch);
   auto* old=&oldhead->rec[i];assert(re4dc_effect_ref(oldhead,i)==old);assert(!memcmp(row,old,300));++checked;saved.push_back(token);
   if(!(reinterpret_cast<std::uintptr_t>(token)&1)){assert(row==token);++raw;}
   if(row->Kind==1 && row->Espgen_id==0){
    EspgenWork x{},y{};Vec pos{1,2,3},rot{4,5,6};Mtx matrix{};cModel model{812};EspSeqOpt opt{};
    rng_calls=0;assert(Espgen00_SetFreeWork(&x,token,head,&model,0xfe,&matrix,&pos,&rot,&opt,1));unsigned calls=rng_calls;
    rng_calls=0;assert(Espgen00_SetFreeWork(&y,old,oldhead,&model,0xfe,&matrix,&pos,&rot,&opt,1));assert(rng_calls==calls);
    auto* px=reinterpret_cast<Espgen00Work*>(x.work);auto* py=reinterpret_cast<Espgen00Work*>(y.work);
    assert(px->rec==token);auto keep=px->rec;px->rec=py->rec=nullptr;px->pOpt=py->pOpt=nullptr;
    assert(!memcmp(x.work,y.work,sizeof(Espgen00Work)));
    // The actual constructor returned; its scratch is dead. Repeating emissions
    // still resolve every original byte through the retained archive reference.
    for(unsigned tick=0;tick<100;++tick){EspGenWork later;assert(!memcmp(re4dc_effect_read(keep,later),old,300));}
    ++retained;
   }
  }
 }
 assert(a==original);re4dc_effect_unbind(a.data());
 for(void* p:saved)if(reinterpret_cast<std::uintptr_t>(p)&1){unsigned scratch[75];bool failed=false;
  try{re4dc_effect_record_read(p,scratch);}catch(const std::runtime_error&){failed=true;}assert(failed);break;}
 // Relocate/rebind the same archive while its old backing stays allocated.
 auto relocated=a;assert(relocated.data()!=a.data());assert(bind(relocated));
 for(unsigned group=0;group<heads.size()/12;++group){const auto* e=heads.data()+group*12;
  auto* h=reinterpret_cast<EspSeqData*>(relocated.data()+word(e));auto* old=reinterpret_cast<EspSeqData*>(ref.data()+word(e+4));
  for(unsigned i=0;i<word(e+8);++i){EspGenWork s;assert(!memcmp(re4dc_effect_read(re4dc_effect_ref(h,i),s),&old->rec[i],300));}}
 re4dc_effect_unbind(relocated.data());Re4dcEffectStats stats{};re4dc_effect_get_stats(&stats);
 assert(!stats.sequences && !stats.records);assert(!heap_live && !reads && !read_bytes);
 printf("{\"checked_records\":%u,\"retained_generators\":%u,\"raw_records\":%u,\"decode_reads\":%u,\"io_bytes\":0,\"heap_allocations\":0}\n",checked,retained,raw,stats.reads);
}
"""
def compile_fixture(root):
    headers(root)
    esp=(ROOT/'include/esp.h').read_text();records=esp[esp.index('struct EspGenPrmW'):esp.index('// Texture animation data')]
    gen=(ROOT/'src/game/espgen00.cpp').read_text();work=gen[gen.index('struct Espgen00Work {'):gen.index('// Rebuilds the emitter')]
    ctor=function(gen,'int Espgen00_SetFreeWork(')
    text=SUPPORT+SETUP+records+'\n#include "native_effect_source.h"\n'+work+ctor+MAIN
    src=root/'effects.cpp';src.write_text(text);exe=root/'check'
    result=subprocess.run(['g++','-std=c++20','-fpermissive','-DRE4DC_GAME','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',
                    '-I'+str(root),'-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(src),
                    str(ROOT/'port/dreamcast/game/platform/native_effect.cpp'),'-lz','-o',str(exe)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return exe

class EffectResidency(unittest.TestCase):
    def test_bit_patterns_and_exclusions(self):
        for i in range(75):
            r=bytearray(300);struct.pack_into('<I',r,i*4,0x80000000+i)
            self.assertEqual(codec.unpack_record(codec.pack_record(r)),r)
        with self.assertRaises(ValueError):codec.unpack_record(struct.pack('<3I',0,0,1<<11))
    def test_powerpc_source_unchanged(self):
        for file in ('read','espgen','espgen00','espgen01','espgen10','esp_sub'):
            path='src/game/'+file+'.cpp'
            old=subprocess.check_output(['git','show','168f4e2:'+path],cwd=ROOT,text=True)
            def pp(text):
                text='\n'.join(l for l in text.splitlines() if not l.startswith('#include'))
                return subprocess.check_output(['g++','-E','-P','-x','c++','-D__PPC__','-'],input=text,text=True)
            self.assertEqual(pp(old),pp((ROOT/path).read_text()),path)
    @unittest.skipUnless(shutil.which('g++'),'host compiler needed')
    def test_delayed_retention_relocation_and_retirement(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);exe=compile_fixture(path)
            for core in (False,True):
                fixture(path,core)
                result=subprocess.run([str(exe),str(path)],check=True,capture_output=True,text=True)
                report=json.loads(result.stdout);self.assertEqual(report['checked_records'],26)
                self.assertEqual(report['retained_generators'],12);self.assertEqual(report['raw_records'],2)
if __name__=='__main__':unittest.main()
