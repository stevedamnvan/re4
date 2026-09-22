import importlib.util, pathlib, struct, unittest
spec=importlib.util.spec_from_file_location("rigid32",pathlib.Path(__file__).parents[1]/"tools/audit_ps2_rigid32.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture():
 b=bytearray(144);b[:2]=b"\x30\0";struct.pack_into("<HI",b,10,1,16);struct.pack_into("<I",b,28,32)
 struct.pack_into("<HBB",b,32,96,0,1);b[60:64]=bytes.fromhex("2080016c");b[64]=1;struct.pack_into("<f",b,76,100);b[92:94]=bytes.fromhex("2180");b[80]=2
 struct.pack_into("<3hH3hH2h2H3hH",b,96,1,2,3,0,0,127,0,0,128,256,0,0,64,128,192,128)
 return b
class Rigid32Test(unittest.TestCase):
 def test_normal_and_color_are_separate_and_not_runtime_qualified(self):
  r=m.audit_rigid32(fixture());s=r['materials'][0]['segments'][0]
  self.assertEqual(r['kind'],'NORMAL_WITH_COLOR');self.assertFalse(r['render_qualified'])
  self.assertEqual(s['normals'],[(0,127,0)]);self.assertEqual(s['vertices'][0][5:8],[64,128,192])
 def test_truncated_payload_rejected(self):
  with self.assertRaises(ValueError):m.audit_rigid32(fixture()[:120])
 def test_conflicting_extent_rejected(self):
  b=fixture();struct.pack_into('<H',b,32,88)
  with self.assertRaises(ValueError):m.audit_rigid32(b)
 def test_invalid_normal_rejected(self):
  b=fixture();struct.pack_into('<h',b,106,200)
  with self.assertRaises(ValueError):m.audit_rigid32(b)
if __name__=='__main__':unittest.main()
