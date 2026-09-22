"""Em12 construction preserves the resource installed by the source manager."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
class EnemyConstruction(unittest.TestCase):
 def test_archive_lifetime(self):
  source=(ROOT/'src/em12/em12_set.cpp').read_text()
  a=source.index('void Em12Init(cEm* em)\n{');b=source.index('\n}',a)+2
  function=source[a:b]
  text="""#include <new>
#include <cassert>
struct cEm {void* subArc;unsigned flags;cEm(){flags=0x21;}virtual ~cEm(){} };
struct cEm10: cEm {};
"""+function+"""
int main(){cEm10 slot;int resource;slot.subArc=&resource;slot.flags=99;
Em12Init(&slot);assert(slot.subArc==&resource&&slot.flags==0x21);}
"""
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'check.cpp').write_text(text)
   subprocess.run(['g++','-std=c++20','-O1','-DRE4DC_GAME','-fsanitize=address,undefined','-fno-pie','-no-pie',str(p/'check.cpp'),'-o',str(p/'check')],check=True)
   subprocess.run([str(p/'check')],check=True)
  old=subprocess.check_output(['git','show','4b85a3f:src/em12/em12_set.cpp'],cwd=ROOT,text=True)
  def pp(s):
   return subprocess.check_output(['g++','-E','-P','-x','c++','-D__PPC__','-'],input='\n'.join(l for l in s.splitlines() if not l.startswith('#include')),text=True)
  self.assertEqual(pp(old),pp(source))
if __name__=='__main__':unittest.main()
