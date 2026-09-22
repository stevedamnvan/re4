"""Qualified enemy texture-only transport; source behavior payloads stay resident."""
from pathlib import Path
import struct,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_le_mirror import make_tpl,make_eff,make_anm,make_tagged
import test_le_mirror as mirror_fixtures
import prepare_enemy_motions as enemy
import prepare_native_ui as ui
import convert_tpl as tpl

class CompactEnemy(unittest.TestCase):
    def test_source_slots_sound_noise_mips_and_offsets(self):
        image=tpl.TplImage(16,16,1,bytes(range(256)))
        texture=bytearray(make_tpl([(16,16,1,image.data)]))
        texture[84:84]=bytes(12);struct.pack_into('>I',texture,28,96)
        mip=bytearray(texture)+bytes(64);mip[54]=1
        eff,_=make_eff([(7,texture,make_anm(16,16,0,0,1)),(0xfe,texture,make_anm(16,16,0,0,1))])
        body=bytearray(make_tagged([('EFF',eff),('TPL',texture),('TPL',mip),('CNS',bytes(32))]))
        struct.pack_into('>I',body,4,len(body))
        reference,rel=mirror_fixtures.DrsBoundaryTest.fixture();body+=reference[rel:]
        # Existing known module descriptor; this fixture tests transport, not
        # synthetic em12 gameplay or new module generation.
        samples=bytes(range(128))*4
        sound=bytearray(ui.mirror.CONTAINER_MAGIC+bytes(1024-32))+samples
        struct.pack_into('>4I',sound,32,2,len(samples),0,1024)
        struct.pack_into('>I',sound,64,ui.mirror.END_OF_TABLE)
        data=bytearray(ui.mirror.CONTAINER_MAGIC+bytes(1024-32))+body+sound
        struct.pack_into('>4I',data,32,0,len(body),0,1024)
        struct.pack_into('>4I',data,64,4,len(sound),0,1024+len(body))
        struct.pack_into('>I',data,96,ui.mirror.END_OF_TABLE)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'em12.drs';source.write_bytes(data);tex=root/'tex';tex.mkdir()
            key,_=ui.image_identity(image)
            native,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (tex/(key+'.re4tex')).write_bytes(native)
            report=enemy.prepare(source,root/'out',textures=tex,keep_motion_resident=True)
            self.assertTrue(report['motions_resident']);self.assertEqual(report['entries'],[])
            self.assertEqual(len(report['textures']['selected']),2)
            self.assertEqual(report['hot_payload_bytes'],0);self.assertEqual(report['index_bytes'],0)
            packed=(root/'out/em12.drs').read_bytes();small=(root/'out/em12.arc').read_bytes()
            self.assertEqual(struct.unpack_from('<I',packed,36)[0],len(small))
            sound_at=struct.unpack_from('<I',packed,76)[0];self.assertEqual(packed[sound_at+1024:sound_at+len(sound)],samples)
            self.assertEqual(struct.unpack_from('<4I',packed,sound_at+32),(2,len(samples),0,1024))
            self.assertEqual(source.read_bytes(),data)
            n=struct.unpack_from('<I',small)[0];self.assertEqual(n,5)
            self.assertEqual(small[16+4*n:16+8*n],b'EFF\0TPL\0TPL\0CNS\0NTR\0')
            offsets=struct.unpack_from('<5I',small,16)
            self.assertEqual(small[offsets[3]:offsets[4]],bytes(32))
            self.assertEqual(small[offsets[2]+96:offsets[2]+352],image.data) # retained mip texels
            for item in report['textures']['selected']:
                h=item['resident_header'];pixels=item['resident_payload']
                self.assertEqual(small[pixels:pixels+8],b'R4NREF\0\0')
                self.assertEqual(struct.unpack_from('<I',small,h+8)[0]+item['resident_tpl'],pixels)
            eff_at=offsets[0];tbl=eff_at+struct.unpack_from('<I',small,eff_at+24)[0]
            palette=tbl+struct.unpack_from('<I',small,tbl+8)[0]
            hdr=palette+struct.unpack_from('<I',small,palette+12)[0]
            pixels=palette+struct.unpack_from('<I',small,hdr+8)[0]
            self.assertEqual(small[pixels:pixels+256],image.data) # CPU noise stays readable
            with self.assertRaises(FileExistsError):enemy.prepare(source,root/'out',textures=tex,keep_motion_resident=True)
            (tex/(key+'.re4tex')).write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'non-reference'):enemy.prepare(source,root/'bad',textures=tex,keep_motion_resident=True)
            self.assertFalse((root/'bad').exists())

if __name__=='__main__':unittest.main()
