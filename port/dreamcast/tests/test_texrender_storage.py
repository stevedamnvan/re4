"""Execute source target acquisition/copy dimensions with guarded host storage."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
def function(s,name):
 a=s.index(name);a=s.rfind('\n',0,a)+1;b=s.index('{',a);d=1;i=b+1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
class TexRenderStorage(unittest.TestCase):
 def test_sized_allocation_copy_and_ownership(self):
  s=(ROOT/'src/game/TexRender.cpp').read_text();a=s.index('#if defined(RE4DC_GAME)',s.index('// Claims the next free'))
  b=s.index('// EFB x offset',a)
  funcs=s[a:b]+'\n'+function(s,'void TexRenderMng::Init()')+'\n'+function(s,'int TexRenderMng::AllocBuf()')+'\n'+function(s,'void CopyTexRenderMgr(')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'check.cpp').write_text(SETUP+funcs+CHECKS)
   subprocess.run(['g++','-std=c++20','-O1','-DRE4DC_GAME','-fsanitize=address,undefined','-fno-pie','-no-pie',str(p/'check.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
 def test_ppc_path_unchanged(self):
  def pp(s):return subprocess.check_output(['g++','-E','-P','-x','c++','-D__PPC__','-'],input='\n'.join(l for l in s.splitlines() if not l.startswith('#include')),text=True)
  for f in ('include/TexRender.h','src/game/TexRender.cpp','src/st1/r100.cpp'):
   old=subprocess.check_output(['git','show','9c604ad:'+f],cwd=ROOT,text=True)
   self.assertEqual(pp(old),pp((ROOT/f).read_text()),f)
SETUP=r"""
#include <cassert>
#include <cstring>
#include <vector>
#include <cstdlib>
#include <cstdint>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;using f32=float;
struct GXTexObj {unsigned width,height,format;};
struct TexRenderMng {int used;GXTexObj m_Tex_obj;void* buf;u8 texId,x29;u16 mask;u32 m_W_size,m_H_size;int m_Rep_type;void Init();int AllocBuf();};
TexRenderMng g_RndMgr[8];u32 g_RndMgrNum;int g_draw;
struct Log{void err(int,int,const char*,...){}} logger;Log* pLog=&logger;
struct Global{unsigned Status_flg[2];} global;Global* pG=&global;
struct GXRenderModeObj{u8 sample_pattern[12][2];u8 aa;u8 vfilter[7];} Rmode;
unsigned requests,total,copy_w,copy_h;bool deny;
std::vector<void*> live;
void* alloc(unsigned n){++requests;if(deny)return nullptr;void* p=malloc(n);assert(p);memset(p,0xa5,n);live.push_back(p);total+=n;return p;}
#define MEM_ALLOC(n,a,b) alloc(n)
void GXSetCopyFilter(int,void*,int,void*){}void GXSetAlphaUpdate(int){}
void GXSetTexCopySrc(unsigned,unsigned,unsigned w,unsigned h){assert(w==128&&h==128);}
void GXSetTexCopyDst(unsigned w,unsigned h,int format,int mip){assert(format==6&&mip==1);copy_w=w;copy_h=h;}
void GXCopyTex(void* p,int clear){assert(clear);memset(p,0x33,copy_w*copy_h*4);}
void GXPixModeSync(){}void GXInvalidateTexAll(){}
void GXInitTexObj(GXTexObj* o,void*,unsigned w,unsigned h,int f,int,int,int mip){assert(!mip);*o={w,h,unsigned(f)};}
void GXInitTexObjLOD(GXTexObj*,int,int,float,float,float,int,int,int){}
void ScreenReSize(unsigned,unsigned){}void SetScissorState(){}
"""
CHECKS=r"""
int main(){
 TexRenderMng* target=nullptr;assert(GetTexRenderMgrSized(&target,64,64));
 assert(requests==1&&total==16384&&target==g_RndMgr&&target->used&&target->texId==0xf8&&target->mask==8);
 // Execute the actual source copy callback: destination writes and the sampled
 // descriptor agree on the full allocated 64x64 RGBA8 buffer, under ASan.
 global.Status_flg[1]=0x08000000;CopyTexRenderMgr(target);
 assert(copy_w==64&&copy_h==64&&target->m_Tex_obj.width==64&&target->m_Tex_obj.height==64);
 assert(((u8*)target->buf)[16383]==0x33&&g_draw==1&&!global.Status_flg[1]);
 auto saved=target->buf;deny=true;assert(!GetTexRenderMgrSized(&target,64,64));assert(g_RndMgrNum==1);deny=false;
 assert(GetTexRenderMgr(&target));assert(target->m_W_size==128&&target->m_H_size==128&&total==16384+65536);
 assert(g_RndMgr[0].buf==saved&&target->texId==0xf9&&target->mask==16);
 assert(!GetTexRenderMgrSized(&target,0,64)&&!GetTexRenderMgrSized(&target,65535,65535)&&g_RndMgrNum==2);
 while(g_RndMgrNum<8)assert(GetTexRenderMgrSized(&target,64,64));
 unsigned before=requests;assert(!GetTexRenderMgr(&target)&&requests==before);
 for(auto p:live)free(p);live.clear();g_RndMgrNum=0;for(auto& m:g_RndMgr)m.Init();
 assert(GetTexRenderMgrSized(&target,64,64)&&target->texId==0xf8);for(auto p:live)free(p);
}
"""
if __name__=='__main__':unittest.main()
