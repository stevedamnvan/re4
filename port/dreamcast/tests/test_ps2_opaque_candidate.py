import pathlib
import struct
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import audit_ps2_color_asset as audit
import ps2_opaque_candidate as candidate


def fixture():
    b=bytearray(240)
    struct.pack_into('<H',b,0,0x30)
    struct.pack_into('<HI',b,10,1,80)
    struct.pack_into('<I',b,92,96)
    struct.pack_into('<HBB',b,96,144,0,0)
    b[128]=3
    struct.pack_into('<f',b,140,1)
    b[144]=5
    for i in range(3):
        struct.pack_into('<3hH2h2H3hH',b,160+i*24,i*100,0,0,0,i*255,0,0,0,64+i*32,96,128,128)
    return bytes(b)


class RawAuditTests(unittest.TestCase):
    def setUp(self):
        self.transform={'scale':(1,1,1),'position':(0,0,0)}
    def test_integer_attributes_winding_and_material(self):
        r=audit.raw_color_bin(fixture(),self.transform)
        self.assertEqual(r['faces'],[(0,(0,1,2))])
        self.assertEqual(r['vertices'][1],(1,0,0,1,0,.75,.75,1,1))
        self.assertEqual(r['raw_offsets'],[160,184,208])
    def test_every_truncation_inside_required_records_rejected(self):
        for n in [0,12,79,95,99,127,143,159,160,231,239]:
            with self.subTest(n=n),self.assertRaises(ValueError):audit.raw_color_bin(fixture()[:n],self.transform)
    def test_material_pointer_overflow(self):
        b=bytearray(fixture());struct.pack_into('<I',b,12,0xfffffff0)
        with self.assertRaises(ValueError):audit.raw_color_bin(b,self.transform)
    def test_unsupported_weighted_variant(self):
        b=bytearray(fixture());b[126]=2
        with self.assertRaisesRegex(ValueError,'weighted'):audit.raw_color_bin(b,self.transform)
    def test_invalid_vif_vertex_count(self):
        b=bytearray(fixture());b[128]=4
        with self.assertRaisesRegex(ValueError,'VIF'):audit.raw_color_bin(b,self.transform)
    def test_wrong_corner_attribute_or_winding_rejected(self):
        r=audit.raw_color_bin(fixture(),self.transform)
        e={'vertices':list(r['vertices']),'faces':[(0,(2,1,0))]}
        with self.assertRaisesRegex(ValueError,'winding'):audit.compare(r,e)
        e['faces']=r['faces'];e['vertices'][0]=(9,)+e['vertices'][0][1:]
        with self.assertRaisesRegex(ValueError,'attribute'):audit.compare(r,e)
    def test_smd_transform_identity_and_rejections(self):
        b=bytearray(80);struct.pack_into('<HHIII',b,0,0x40,1,0,0,0)
        struct.pack_into('<12f4B3I',b,16,100,200,300,1,0,0,0,0,2,3,4,1,42,0,255,7,0,8,0)
        t=audit.instance(b,0)
        self.assertEqual(t['bin'],42);self.assertEqual(t['smx'],7)
        r=audit.raw_color_bin(fixture(),t)
        self.assertEqual(r['vertices'][1][:3],(3,2,3))
        with self.assertRaises(ValueError):audit.instance(b,1)
        struct.pack_into('<f',b,32,1)
        with self.assertRaisesRegex(ValueError,'rotation'):audit.instance(b,0)


class FactorizationTests(unittest.TestCase):
    def test_overbright_source_preserved_without_clipping(self):
        p=[(128,100,80,255),(64,50,40,255)];c=[(1.5,1.25,1,1),(.75,.5,.25,1)]
        encoded,normalized,gains=candidate.factorize(p,c)
        self.assertEqual(gains,[1.5,1.25,1]);self.assertEqual(encoded[0],(192,125,80,255))
        # Arbitrary bilinear texture and barycentric color samples commute with
        # constant per-channel scaling. Allow only intermediate byte rounding.
        for t in [0,.1,.5,1]:
            for w in [0,.3,.8,1]:
                for k in range(3):
                    expected=((1-t)*p[0][k]+t*p[1][k])*((1-w)*c[0][k]+w*c[1][k])
                    actual=((1-t)*encoded[0][k]+t*encoded[1][k])*((1-w)*normalized[0][k]+w*normalized[1][k])
                    self.assertLessEqual(abs(actual-expected),.5)
    def test_alpha_overflow_and_nonfinite_refused(self):
        for p,c in [([(200,0,0,255)],[(1.5,0,0,1)]), ([(1,2,3,254)],[(1,1,1,1)]), ([(1,2,3,255)],[(1,1,1,.5)]), ([(1,2,3,255)],[(float('nan'),1,1,1)])]:
            with self.subTest(p=p,c=c),self.assertRaises(ValueError):candidate.factorize(p,c)
    def test_sidecar_identity_is_explicit(self):
        h=candidate.header(0x12345678,100,[(1,.5,0)])
        self.assertIn('version = 1',h);self.assertIn('0x12345678U',h)
        self.assertIn('first = 100U',h);self.assertIn('count = 1U',h)

if __name__=='__main__':unittest.main()
