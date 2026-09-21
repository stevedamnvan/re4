"""Qualified archive compaction through existing parsers; no private game data."""
from pathlib import Path
import struct,sys,tempfile,types,unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_native_ui as ui
import convert_tpl as tpl
from test_convert_tpl import make_tpl
import test_room_endian as room_fixtures


def fixture():
    image=(16,16,1,bytes(range(256)))
    texture=bytearray(make_tpl([image]))
    texture[56:56]=bytes(8);struct.pack_into('>I',texture,28,64)
    # One SMD placement resolves its local TPL, with no referenced BIN or motion.
    smd=bytearray(128);smd[0]=0x20;struct.pack_into('>H',smd,2,1)
    struct.pack_into('>3I',smd,4,0,96,0);smd[52:55]=bytes([255,0,255])
    struct.pack_into('>I',smd,96,32);smd+=texture
    eff=bytearray(128)
    struct.pack_into('>12I',eff,0,11,48,0,0,0,112,64,80,0,0,0,0)
    struct.pack_into('>IHHI',eff,48,1,0xfe,0,0)
    struct.pack_into('>2I',eff,64,1,64);struct.pack_into('>2I',eff,80,1,16)
    struct.pack_into('>5H',eff,96,16,16,0,0,1);eff+=texture
    mip=bytearray(texture)+bytes(64);mip[20+34]=1
    bodies=[bytes(32) for _ in range(51)];tags=[b'CNS\0']*51
    itm=bytearray(448)
    struct.pack_into('>4I',itm,0,3,32,64,416)
    struct.pack_into('>IHHI',itm,32,1,7,0,0)
    struct.pack_into('>2I',itm,64,1,32)
    struct.pack_into('>2I',itm,416,1,32)
    itm[96:416]=room_fixtures.RoomFormats().model_fixture();itm+=texture
    for slot,tag,body in [(10,b'ITM\0',itm),(5,b'SMD\0',smd),(8,b'EFF\0',eff),(26,b'TPL\0',texture),(28,b'TPL\0',mip)]:
        bodies[slot]=body;tags[slot]=tag
    archive=bytearray(448);struct.pack_into('>I',archive,0,51)
    for i,(tag,body) in enumerate(zip(tags,bodies)):
        struct.pack_into('>I',archive,16+4*i,len(archive));archive[220+4*i:224+4*i]=tag;archive+=body
    container=bytearray(ui.mirror.CONTAINER_MAGIC+bytes(1056-32))
    struct.pack_into('>4I',container,32,0,8,0,1024);struct.pack_into('>I',container,64,ui.mirror.END_OF_TABLE)
    container[1024:1032]=b'payload!'
    return archive,container,tpl.TplImage(*image)


class CompactRoom(unittest.TestCase):
    def test_offset_identity_and_retained_cpu_mip_data(self):
        original,container,image=fixture()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'r100.das';source.write_bytes(container);textures=root/'tex';textures.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (textures/(key+'.re4tex')).write_bytes(package)
            decoder=mock.Mock(return_value=bytes(original))
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=decoder)}):
                report=ui.compact_room(source,textures,root/'out')
            decoder.assert_called_once_with(b'payload!')
            self.assertEqual(len(report['selected']),3) # CPU noise 0xFE and mip chain retained
            self.assertEqual(report['archive_recovery_bytes'],576)
            small=(root/'out/r100.arc').read_bytes();before=bytearray(original)
            ui.mirror.convert_file('st1/r100.arc',before)
            def body(data,i):
                count,=struct.unpack_from('<I',data);offsets=struct.unpack_from('<%dI'%count,data,16)
                end=min([x for x in offsets if x>offsets[i]]+[len(data)])
                return data[offsets[i]:end]
            for i in set(range(51))-{5,10,26}:
                self.assertEqual(body(small,i),body(before,i),i)
            for entry in report['selected']:
                p=entry['resident_payload'];self.assertEqual(small[p:p+8],b'R4NREF\0\0')
                h=entry['resident_header'];self.assertEqual(struct.unpack_from('<I',small,h+8)[0]+entry['resident_tpl'],p)
            item=body(small,10);old_item=body(before,10)
            oi,ob,ot=struct.unpack_from('<3I',item,4)
            model=ob+struct.unpack_from('<I',item,ob+4)[0]
            self.assertEqual(item[model:model+320],old_item[96:416])
            self.assertEqual(struct.unpack_from('<H',item,oi+4)[0],7)
            palette=ot+struct.unpack_from('<I',item,ot+4)[0]
            self.assertEqual(struct.unpack_from('<I',item,palette)[0],tpl.TPL_MAGIC)
            native=(root/'out/r100.dar').read_bytes()
            self.assertEqual(struct.unpack_from('<I',native,36)[0],len(small))
            self.assertEqual(source.read_bytes(),container)
            with self.assertRaises(FileExistsError):ui.compact_room(source,textures,root/'out')
            bad=bytearray(original);bad[224:228]=b'BAD\0'
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:bad)}):
                with self.assertRaisesRegex(ValueError,'unqualified'):ui.compact_room(source,textures,root/'rejected')
            self.assertFalse((root/'rejected').exists())
            (textures/(key+'.re4tex')).write_bytes(b'invalid')
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:original)}):
                with self.assertRaisesRegex(ValueError,'non-reference'):ui.compact_room(source,textures,root/'wrong-image')

class CompactCore(unittest.TestCase):
    def test_selected_family_compacts_without_qualifying_or_mutating_other_families(self):
        room,_,image=fixture()
        old_offsets=struct.unpack_from('>51I',room,16)
        eff=bytearray(room[old_offsets[8]:old_offsets[9]])
        struct.pack_into('>H',eff,52,7) # upload-only HUD ID, not CPU noise 0xFE
        archive=bytearray(320);struct.pack_into('>I',archive,0,36)
        for i in range(36):
            struct.pack_into('>I',archive,16+4*i,len(archive))
            archive[160+4*i:164+4*i]=b'EFF\0' if i==25 else b'VIB\0' if i==1 else b'CNS\0'
            archive+=eff if i==25 else bytes([1 if i==1 else 0])*32
        container=bytearray(ui.mirror.CONTAINER_MAGIC+bytes(1024-32))+archive
        struct.pack_into('>4I',container,32,0,len(archive),0,1024)
        struct.pack_into('>I',container,64,ui.mirror.END_OF_TABLE)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'core.das';source.write_bytes(container);textures=root/'tex';textures.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (textures/(key+'.re4tex')).write_bytes(package)
            report=ui.compact_core(source,textures,root/'out')
            self.assertEqual(len(report['selected']),1)
            self.assertEqual(report['archive_recovery_bytes'],160)
            self.assertEqual([e['sub'] for e in report['retained_unqualified']],['etc/core.das:0#1'])
            small=(root/'out/core.arc').read_bytes();packed=(root/'out/core.das').read_bytes()
            size,base=struct.unpack_from('<I4xI',packed,36)
            self.assertEqual(packed[base:base+size],small)
            self.assertEqual(source.read_bytes(),container)
            before=bytearray(container);ui.mirror.convert_file('etc/core.das',before)
            self.assertEqual(packed[64:1024],before[64:1024]) # DVD sound/header transport unchanged
            selected=report['selected'][0]
            self.assertEqual(small[selected['resident_payload']:selected['resident_payload']+8],b'R4NREF\0\0')
            # Unknown selected data is rejected; an unrelated raw family is not
            # silently presented as qualified merely because compaction worked.
            bad=bytearray(container);bad[1024+160+25*4:1024+164+25*4]=b'BAD\0';source.write_bytes(bad)
            with self.assertRaisesRegex(ValueError,'unqualified selected'):
                ui.compact_core(source,textures,root/'bad')
            self.assertFalse((root/'bad').exists())
            source.write_bytes(container)
            with self.assertRaises(FileExistsError):ui.compact_core(source,textures,root/'out')

if __name__=='__main__':unittest.main()