"""Persistent option/death owner: real conversion, synthetic source assets."""
from pathlib import Path
import struct,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_native_ui as ui
import convert_tpl as tpl
from test_le_mirror import make_eff,make_tpl,make_anm

def fixture():
    image=tpl.TplImage(16,16,1,bytes(range(256)))
    texture=bytearray(make_tpl([(16,16,1,image.data)]))
    texture[84:84]=bytes(12);struct.pack_into('>I',texture,28,96)
    texture+=bytes((-len(texture))%32)
    effect,_=make_eff([(7,texture,make_anm(16,16,0,0,1))])
    # CPU-noise family remains byte-identical; real death palette images are
    # additionally checked against the private qualified archive.
    noise=bytearray(effect);struct.pack_into('>H',noise,68,0xfe)
    archive=bytearray(128);struct.pack_into('>I',archive,0,11)
    for i in range(11):
        struct.pack_into('>I',archive,16+4*i,len(archive))
        archive[60+4*i:64+4*i]=b'EFF\0' if i in (0,4) else b'UWF\0'
        archive+=noise if i==0 else effect if i==4 else b'2.00'+bytes(28)
    return archive,image

def body(data,i):
    count=struct.unpack_from('<I',data)[0];ofs=struct.unpack_from('<%dI'%count,data,16)
    return data[ofs[i]:min([o for o in ofs if o>ofs[i]]+[len(data)])]

class CompactOption(unittest.TestCase):
    def test_actual_tagged_transport_keeps_layouts_and_source_identity(self):
        source,image=fixture()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);file=p/'option.dat';file.write_bytes(source);tex=p/'tex';tex.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (tex/(key+'.re4tex')).write_bytes(package)
            report=ui.compact_option(file,tex,p/'candidate')
            compact=(p/'candidate/option.dat').read_bytes();reference=bytearray(source)
            ui.mirror.convert_file('ss/eng/option.dat',reference)
            self.assertEqual(file.read_bytes(),source)
            self.assertEqual(len(report['selected']),1)
            self.assertEqual(report['archive_recovery_bytes'],160)
            self.assertEqual(report['required_reservation_bytes'],len(compact))
            for i in set(range(11))-{4}:self.assertEqual(body(reference,i),body(compact,i))
            e=report['selected'][0]
            self.assertEqual(compact[e['resident_payload']:e['resident_payload']+8],b'R4NREF\0\0')
            self.assertEqual(struct.unpack_from('<I',compact,e['resident_header']+8)[0]+e['resident_tpl'],e['resident_payload'])
            self.assertEqual(e['key'],key)
            with self.assertRaises(FileExistsError):ui.compact_option(file,tex,p/'candidate')
            # An unknown sibling invalidates the whole option owner.
            bad=bytearray(source);bad[64:68]=b'BAD\0';file.write_bytes(bad)
            with self.assertRaisesRegex(ValueError,'unqualified'):ui.compact_option(file,tex,p/'bad')
            self.assertFalse((p/'bad').exists())
            file.write_bytes(source);(tex/(key+'.re4tex')).write_bytes(b'bad texture')
            with self.assertRaisesRegex(ValueError,'non-reference'):ui.compact_option(file,tex,p/'bad-tex')
            self.assertFalse((p/'bad-tex').exists())
            self.assertIsNone(ui.mirror.TPL_OBSERVER);self.assertIsNone(ui.mirror.OFFSET_OBSERVER)

if __name__=='__main__':unittest.main()
