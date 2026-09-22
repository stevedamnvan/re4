"""Enemy construction preserves the resource installed by the source manager."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
class EnemyConstruction(unittest.TestCase):
 def test_archive_lifetime(self):
  for path,name,cls,baseline in (('src/em12/em12_set.cpp','Em12Init','cEm10','4b85a3f'),
                               ('src/em23/em23.cpp','Em23Init','cEm23','4279bc5')):
   with self.subTest(enemy=cls):self.check_archive_lifetime(path,name,cls,baseline)
 def check_archive_lifetime(self,path,name,cls,baseline):
  source=(ROOT/path).read_text()
  a=source.index('void '+name+'(cEm* em)\n{');b=source.index('\n}',a)+2
  function=source[a:b]
  text="""#include <new>
#include <cassert>
struct cEm {void* subArc;unsigned flags;cEm(){flags=0x21;}virtual ~cEm(){} };
struct ENEMY: cEm {};
"""+function+"""
int main(){ENEMY slot;int resource;slot.subArc=&resource;slot.flags=99;
CONSTRUCT(&slot);assert(slot.subArc==&resource&&slot.flags==0x21);}
"""
  text=text.replace('ENEMY',cls).replace('CONSTRUCT',name)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'check.cpp').write_text(text)
   subprocess.run(['g++','-std=c++20','-O1','-DRE4DC_GAME','-fsanitize=address,undefined','-fno-pie','-no-pie',str(p/'check.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
  old=subprocess.check_output(['git','show',baseline+':'+path],cwd=ROOT,text=True)
  def pp(s):
   return subprocess.check_output(['g++','-E','-P','-x','c++','-D__PPC__','-'],input='\n'.join(l for l in s.splitlines() if not l.startswith('#include')),text=True)
  self.assertEqual(pp(old),pp(source))
if __name__=='__main__':unittest.main()
