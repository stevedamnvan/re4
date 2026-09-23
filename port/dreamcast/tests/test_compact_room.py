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
    def test_room_est_rebases_nested_member_lengths_and_keeps_other_members(self):
        import compact_effect_records as codec
        original,container,image=fixture()
        ofs=struct.unpack_from('>51I',original,16)
        bodies=[original[a:b] for a,b in zip(ofs,ofs[1:]+(len(original),))]
        eff=bytearray(bodies[8]);ids=len(eff);struct.pack_into('>I',eff,8,ids)
        eff+=struct.pack('>IHHI',1,7,0,0)+bytes(20)
        table=len(eff);struct.pack_into('>I',eff,32,table)
        record=bytearray(300);record[1]=11
        raw=bytearray(record);raw[1]=14 # retaining reader must stay raw
        seq=bytearray(struct.pack('>H',2)+bytes(46)+record+raw);seq+=bytes((-len(seq))%32)
        eff+=struct.pack('>2I',1,32)+bytes(24)+seq
        bodies[8]=eff
        nested=bytearray(struct.pack('>I',2)+bytes(28))
        for name in ('et00.eff','et03.eff'):
            nested+=struct.pack('>I',64+len(eff))+bytes(28)+name.encode()+bytes(32-len(name))+eff
        bodies[11]=nested
        rebuilt=bytearray(original[:448]);rebuilt[220+11*4:224+11*4]=b'ETM\0'
        for i,body in enumerate(bodies):
            struct.pack_into('>I',rebuilt,16+4*i,len(rebuilt));rebuilt+=body
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'r100.das';source.write_bytes(container);tex=p/'tex';tex.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (tex/(key+'.re4tex')).write_bytes(package)
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:rebuilt)}):
                baseline=ui.compact_room(source,tex,p/'baseline')
                report=ui.compact_room(source,tex,p/'candidate',compact_effects=True)
            self.assertEqual(len(report['effects']['entries']),2)
            self.assertEqual(baseline['resident_archive_bytes']-report['resident_archive_bytes'],report['effects']['recovery_bytes'])
            small=(p/'candidate/r100.arc').read_bytes();before=(p/'baseline/r100.arc').read_bytes()
            def members(data):
                at=struct.unpack_from('<I',data,16+11*4)[0];n=struct.unpack_from('<I',data,at)[0];at+=32;out=[]
                for _ in range(n):
                    size=struct.unpack_from('<I',data,at)[0];self.assertGreaterEqual(size,64)
                    out.append((data[at+32:at+64].split(b'\0')[0],data[at+64:at+size]));at+=size
                self.assertEqual(at,struct.unpack_from('<I',data,16+12*4)[0])
                return out
            new_members,old_members=members(small),members(before)
            self.assertEqual(new_members[1],old_members[1]) # unselected sibling survives GetEtcAddr traversal
            self.assertEqual(new_members[0][0],b'et00.eff')
            for entry in report['effects']['entries']:
                self.assertEqual(entry['packed_records'],1);self.assertEqual(entry['raw_records'],1)
                h=entry['resident_offset'];r0,r1=struct.unpack_from('<2I',small,h+48)
                self.assertEqual(codec.unpack_record(small[h+(r0&~1):h+r1]),record)
                self.assertEqual(small[h+r1:h+r1+300],raw)
            self.assertEqual(ui.mirror.SEQUENCE_OBSERVER,None)

    def test_selectable_index_release_keeps_source_palette_and_mips(self):
        original,container,_=fixture()
        offsets=struct.unpack_from('>51I',original,16)
        bodies=[original[a:b] for a,b in zip(offsets,offsets[1:]+(len(original),))]
        # Existing EFF ownership and animation table, now with a non-noise ID.
        eff=bytearray(bodies[8][:128]);struct.pack_into('>H',eff,52,7)
        tex=bytearray(96+256+512)
        struct.pack_into('>3I',tex,0,tpl.TPL_MAGIC,1,12)
        struct.pack_into('>2I',tex,12,20,56)
        struct.pack_into('>HHII',tex,20,16,16,9,96)
        struct.pack_into('>HBBII',tex,56,256,0,0,2,352)
        tex[96:352]=bytes(range(256));tex[352:]=bytes(range(256))*2
        eff+=tex;bodies[8]=eff
        rebuilt=bytearray(original[:448])
        for i,body in enumerate(bodies):
            struct.pack_into('>I',rebuilt,16+4*i,len(rebuilt));rebuilt+=body
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'r100.das';source.write_bytes(container);textures=root/'tex';textures.mkdir()
            for raw in (tex,bodies[26]):
                for image in tpl.parse_tpl(raw):
                    key,_=ui.image_identity(image)
                    package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
                    (textures/(key+'.re4tex')).write_bytes(package)
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:rebuilt)}):
                baseline=ui.compact_room(source,textures,root/'baseline')
                candidate=ui.compact_room(source,textures,root/'candidate',compact_palettes=True)
            added=[e for e in candidate['selected'] if e.get('palette_bytes')]
            self.assertEqual(len(added),1);entry=added[0]
            self.assertEqual(entry['source_bytes'],256);self.assertEqual(entry['record_bytes'],64)
            # The additional descriptor fits this fixture's existing table padding.
            self.assertEqual(baseline['resident_archive_bytes']-candidate['resident_archive_bytes'],192)
            small=(root/'candidate/r100.arc').read_bytes()
            rec=small[entry['resident_payload']:entry['resident_payload']+64]
            self.assertEqual(rec[:8],b'R4PREF\0\0')
            self.assertEqual(struct.unpack_from('<2I',rec,32),(2,512))
            owner=entry['resident_tpl'];desc=owner+struct.unpack_from('<I',small,owner+8)[0]
            clut=owner+struct.unpack_from('<I',small,desc+4)[0]
            pal=owner+struct.unpack_from('<I',small,clut+8)[0]
            self.assertEqual(small[pal:pal+512],tex[352:])
            for slot in (28,): # the source mip owner survives byte-for-byte
                def body(data):
                    n=struct.unpack_from('<I',data)[0];ofs=struct.unpack_from('<%dI'%n,data,16)
                    return data[ofs[slot]:min([o for o in ofs if o>ofs[slot]]+[len(data)])]
                self.assertEqual(body(small),body((root/'baseline/r100.arc').read_bytes()))
            self.assertEqual(source.read_bytes(),container)
            # Preparation refuses mismatched native artwork; no reference resizing
            # or source index elimination without an existing exact package.
            key=entry['key'];(textures/(key+'.re4tex')).write_bytes(b'bad')
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:rebuilt)}):
                with self.assertRaisesRegex(ValueError,'non-reference'):
                    ui.compact_room(source,textures,root/'bad',compact_palettes=True)

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

class CompactR101Room(unittest.TestCase):
    """Frontier W4 L2: the reviewed r101 slot contract (37 slots) externalizes only
    SMD#4 TPL0, EFF#7/#35 images, ITM#9 items and model TPLs #27/#29/#34."""
    def build(self):
        room,container,image=fixture()
        ofs=struct.unpack_from('>51I',room,16)
        r100=[room[a:b] for a,b in zip(ofs,ofs[1:]+(len(room),))]
        texture=r100[26];model=room_fixtures.RoomFormats().model_fixture()
        upload=bytearray(r100[8]);struct.pack_into('>H',upload,52,7) # EFF#7: upload-only ID; EFF#35 keeps CPU noise 0xFE
        bodies=[bytes(32) for _ in range(37)];tags=[b'CNS\0']*37
        for slot,tag,body in [(4,b'SMD\0',r100[5]),(7,b'EFF\0',bytes(upload)),(9,b'ITM\0',r100[10]),(35,b'EFF\0',r100[8]),
                              (26,b'BIN\0',model),(27,b'TPL\0',texture),(28,b'BIN\0',model),(29,b'TPL\0',texture),
                              (33,b'BIN\0',model),(34,b'TPL\0',texture)]:
            bodies[slot]=body;tags[slot]=tag
        archive=bytearray(320);struct.pack_into('>I',archive,0,37)
        for i,(tag,body) in enumerate(zip(tags,bodies)):
            struct.pack_into('>I',archive,16+4*i,len(archive));archive[164+4*i:168+4*i]=tag;archive+=body
        return archive,container,image
    def test_r101_contract_keeps_every_other_slot(self):
        archive,container,image=self.build()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'r101.das';source.write_bytes(container);textures=root/'tex';textures.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (textures/(key+'.re4tex')).write_bytes(package)
            with mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:bytes(archive))}):
                report=ui.compact_room(source,textures,root/'out')
                with self.assertRaisesRegex(ValueError,'r100 only'):
                    ui.compact_room(source,textures,root/'effects',compact_effects=True)
            self.assertEqual(report['contract'],'r101-upload-only-v1')
            owners={e['context'].split('/tpl')[0] for e in report['selected']}
            self.assertEqual(owners,{'st1/r101.arc#'+s for s in ('4/TPL0','7','9/item','27','29','34')})
            small=(root/'out/r101.arc').read_bytes();before=bytearray(archive)
            ui.mirror.convert_file('st1/r101.arc',before)
            def body(data,i):
                count,=struct.unpack_from('<I',data);offsets=struct.unpack_from('<%dI'%count,data,16)
                end=min([x for x in offsets if x>offsets[i]]+[len(data)])
                return data[offsets[i]:end]
            self.assertEqual(struct.unpack_from('<I',small)[0],38)
            for i in set(range(37))-{4,7,9,27,29,34}: # EFF#35 (CPU noise only) stays whole
                self.assertEqual(body(small,i),body(before,i),i)
            self.assertEqual(source.read_bytes(),container)
            other=root/'r102.das';other.write_bytes(container)
            with self.assertRaisesRegex(ValueError,'reviewed r100/r101'):
                ui.compact_room(other,textures,root/'r102')

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


    def test_opt_in_core_effect_paths_relocate_and_noise_stays_resident(self):
        from test_le_mirror import make_eff, make_anm, make_tpl
        image=tpl.TplImage(16,16,1,bytes(range(256)))
        texture=make_tpl([(image.width,image.height,image.format,image.data)])
        # Source texel spans are 32-byte aligned, as required by compact.
        texture=bytearray(texture);texture[84:84]=bytes(12);struct.pack_into('>I',texture,28,96)
        eff,_=make_eff([(7,bytes(texture),make_anm(16,16,0,0,1)),
                        (0xfe,bytes(texture),make_anm(16,16,0,0,1))])
        eff=bytearray(eff);li=struct.unpack_from('>I',eff,16)[0]
        struct.pack_into('>IHHI',eff,li,1,9,0,0)
        table=len(eff);struct.pack_into('>I',eff,40,table)
        eff+=struct.pack('>2I',1,32)+bytes(24)+struct.pack('>H2x',2)
        for distance in (0.,10.):eff+=struct.pack('>7f12B',distance,1.,2.,0.,1.,0.,distance,2,3,0,2,40,0,0,0,0,0,0,0)
        eff+=bytes((-len(eff))%32)
        archive=bytearray(320);struct.pack_into('>I',archive,0,36)
        for i in range(36):
            struct.pack_into('>I',archive,16+4*i,len(archive))
            archive[160+4*i:164+4*i]=b'EFF\0' if i in (1,25) else b'CNS\0'
            archive+=eff if i in (1,25) else bytes(32)
        container=bytearray(ui.mirror.CONTAINER_MAGIC+bytes(1024-32))+archive
        struct.pack_into('>4I',container,32,0,len(archive),0,1024)
        struct.pack_into('>I',container,64,ui.mirror.END_OF_TABLE)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'core.das';source.write_bytes(container);textures=root/'tex';textures.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (textures/(key+'.re4tex')).write_bytes(package)
            report=ui.compact_core(source,textures,root/'effects',include_effects=True)
            self.assertEqual(len(report['selected']),2) # one ID7 each; CPU ID FE retained
            data=(root/'effects/core.arc').read_bytes()
            for i in (1,25):
                e=struct.unpack_from('<I',data,16+4*i)[0]
                t=e+struct.unpack_from('<I',data,e+40)[0]
                path=t+struct.unpack_from('<I',data,t+4)[0]
                self.assertEqual(struct.unpack_from('<H',data,path)[0],2)
                self.assertEqual(struct.unpack_from('<7f',data,path+44),(10.,1.,2.,0.,1.,0.,10.))
                self.assertEqual(data[path+32:path+44],bytes([2,3,0,2,40,0,0,0,0,0,0,0]))
                t=e+struct.unpack_from('<I',data,e+24)[0]
                palette=t+struct.unpack_from('<I',data,t+8)[0] # noise ID FE, second palette
                desc=palette+struct.unpack_from('<I',data,palette+8)[0]
                hdr=palette+struct.unpack_from('<I',data,desc)[0]
                pixels=palette+struct.unpack_from('<I',data,hdr+8)[0]
                self.assertEqual(data[pixels:pixels+256],image.data)
            # A missing qualified-path conversion cannot be waved through.
            bad=bytearray(container);e=1024+struct.unpack_from('>I',bad,1024+20)[0]
            t=e+struct.unpack_from('>I',bad,e+40)[0];path=t+struct.unpack_from('>I',bad,t+4)[0]
            struct.pack_into('>H',bad,path,0);source.write_bytes(bad)
            with self.assertRaisesRegex(ValueError,'unqualified selected'):
                ui.compact_core(source,textures,root/'bad',include_effects=True)

class CompactCoreEst(unittest.TestCase):
    def test_native_indices_and_nonzero_trailers_survive(self):
        from test_le_mirror import make_eff, make_anm, make_tpl
        image=tpl.TplImage(16,16,1,bytes(range(256)))
        texture=bytearray(make_tpl([(16,16,1,image.data)]))
        texture[84:84]=bytes(12);struct.pack_into('>I',texture,28,96)
        eff,_=make_eff([(7,bytes(texture),make_anm(16,16,0,0,1))])
        eff=bytearray(eff);eff+=bytes((-len(eff))%32);ids=struct.unpack_from('>I',eff,8)[0]
        struct.pack_into('>IHHIHHI',eff,ids,2,1,0,0,2,0,0)
        record=bytearray(300);record[1]=11
        seq=bytearray(struct.pack('>H',2)+bytes(46)+record*2);seq+=bytes((-len(seq))%32)
        raw=bytearray(struct.pack('>H',1)+bytes(46)+record);raw+=bytes((-len(raw))%32)+b'TRAILER!'+bytes(24)
        table=len(eff);struct.pack_into('>I',eff,32,table)
        eff+=struct.pack('>3I',2,32,32+len(seq))+bytes(20)+seq+raw
        arc=bytearray(320);struct.pack_into('>I',arc,0,36)
        for i in range(36):
            struct.pack_into('>I',arc,16+4*i,len(arc))
            arc[160+4*i:164+4*i]=b'EFF\0' if i in (1,16,25) else b'CNS\0'
            arc+=eff if i in (1,16,25) else bytes(32)
        container=bytearray(ui.mirror.CONTAINER_MAGIC+bytes(1024-32))+arc
        struct.pack_into('>4I',container,32,0,len(arc),0,1024);struct.pack_into('>I',container,64,ui.mirror.END_OF_TABLE)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'core.das';source.write_bytes(container);tex=root/'tex';tex.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (tex/(key+'.re4tex')).write_bytes(package)
            baseline=ui.compact_core(source,tex,root/'baseline',include_effects=True)
            report=ui.compact_core(source,tex,root/'candidate',include_effects=True,compact_effects=True)
            self.assertEqual(len(report['effects']['entries']),2);self.assertEqual(len(report['effects']['skipped']),2)
            self.assertEqual(baseline['resident_archive_bytes']-report['resident_archive_bytes'],report['effects']['recovery_bytes'])
            data=(root/'candidate/core.arc').read_bytes();n=struct.unpack_from('<I',data)[0]
            self.assertEqual(n,38)
            for i in (1,16):
                e=struct.unpack_from('<I',data,16+4*i)[0];t=e+struct.unpack_from('<I',data,e+32)[0]
                second=t+struct.unpack_from('<I',data,t+8)[0]
                self.assertEqual(data[second+352:second+384],b'TRAILER!'+bytes(24))
            for e in report['selected']:
                self.assertEqual(data[e['resident_payload']:e['resident_payload']+8],b'R4NREF\0\0')
            for slot in (36,37):
                off=struct.unpack_from('<I',data,16+4*slot)[0]
                size_at=24 if slot==36 else 28
                self.assertEqual(struct.unpack_from('<I',data,off+size_at)[0],len(data))
            self.assertEqual(source.read_bytes(),container)

if __name__=='__main__':unittest.main()
