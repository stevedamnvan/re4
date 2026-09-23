"""Source UV sharing: full archive relocation and per-corner semantic identity."""
from pathlib import Path
import hashlib
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_native_ui as ui
import convert_tpl as tpl
from test_compact_room import fixture


def model(colored=True):
    stride=8 if colored else 6
    data=bytearray(320)
    struct.pack_into('>I',data,0,80)
    struct.pack_into('>3I',data,12,168,192,160)
    data[24:26]=bytes([1,1])
    struct.pack_into('>H3I',data,26,2,320,0xA0000000 if colored else 0x20000000,1)
    data[40]=8
    struct.pack_into('>H3I2H3I',data,42,0,0,112,144,4,4,0x20030818,0,0)
    data[81]=255
    for i in range(4):
        struct.pack_into('>4h',data,112+i*8,i*32,-i*15,i*7,0)
        data[144+i*4:148+i*4]=bytes([127,i,0,0])
        data[168+i*4:172+i*4]=bytes([i*20,128,255,255])
    data[163]=1;data[164]=100
    for i in range(32):struct.pack_into('>2h',data,192+i*4,(i%3)*100-100,(i%3)*20)
    for ordinal,(op,n) in enumerate([(0x80,32),(0x98,12)]):
        stream=bytearray([op])+struct.pack('>H',n)
        for i in range(n):
            values=(i%4,(i+ordinal)%4,i%4,i) if colored else (i%4,(i+ordinal)%4,i)
            stream+=struct.pack('>'+str(stride//2)+'H',*values)
        stream+=bytes((-len(stream))%32)
        header=bytearray(32);header[11:24]=bytes(range(13))
        struct.pack_into('>2I',header,24,len(stream),n-2)
        data+=header+stream
    return data


def resolve(data,base):
    """Read values as source/native drawing does, independent of the builder."""
    U=lambda o:struct.unpack_from('<I',data,base+o)[0]
    H=lambda o:struct.unpack_from('<H',data,base+o)[0]
    vp,np,tp,cp=[base+U(o) for o in (48,52,16,12)]
    parts=[];cursor=base+U(28);stride=8 if U(32)&0x80000000 else 6
    for _ in range(H(26)):
        header=bytes(data[cursor:cursor+32]);size=struct.unpack_from('<I',header,24)[0]
        p=cursor+32;end=p+size;commands=[]
        while p<end:
            op=data[p];p+=1
            if not op:continue
            count=struct.unpack_from('>H',data,p)[0];p+=2;corners=[]
            for _ in range(count):
                vi,ni=struct.unpack_from('>2H',data,p);ti=struct.unpack_from('>H',data,p+stride-2)[0]
                corner=(bytes(data[vp+vi*8:vp+vi*8+8]),bytes(data[np+ni*4:np+ni*4+4]),bytes(data[tp+ti*4:tp+ti*4+4]))
                if stride==8:
                    ci=struct.unpack_from('>H',data,p+4)[0];corner+=(bytes(data[cp+ci*4:cp+ci*4+4]),)
                corners.append(corner);p+=stride
            commands.append((op,tuple(corners)))
        parts.append((header,tuple(commands)));cursor=end
    return tuple(parts)


def scene_fixture():
    original,container,image=fixture();ofs=struct.unpack_from('>51I',original,16)
    bodies=[original[a:b] for a,b in zip(ofs,ofs[1:]+(len(original),))]
    texture=bodies[5][128:];models=[model(),model(False)]
    smd=bytearray(256);smd[0]=0x20;struct.pack_into('>H3I',smd,2,2,160,192,0)
    for i in range(2):
        struct.pack_into('>9f',smd,16+i*72,*([0.]*6+[1.]*3))
        smd[52+i*72:55+i*72]=bytes([i,0,255])
        struct.pack_into('>I',smd,160+4*i,len(smd)-160);smd+=models[i]
    struct.pack_into('>I',smd,192,len(smd)-192);smd+=texture;bodies[5]=smd
    out=bytearray(original[:448])
    for i,body in enumerate(bodies):struct.pack_into('>I',out,16+4*i,len(out));out+=body
    return out,container,image


class CompactModelUvs(unittest.TestCase):
    def test_archive_round_trip_preserves_all_draw_values_and_reduces_final_allocation(self):
        original,container,image=scene_fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'r100.das';source.write_bytes(container);textures=root/'tex';textures.mkdir()
            key,_=ui.image_identity(image)
            package,_=tpl.build_package([image],[tpl.MaterialBinding('source',0,None)],twiddle=True,pad_to_power_of_two=True,source_intensity_alpha=True)
            (textures/(key+'.re4tex')).write_bytes(package)
            sentinel=lambda *a:None
            with mock.patch.object(ui.mirror,'MODEL_OBSERVER',sentinel),mock.patch.dict(sys.modules,{'decode_yz2':types.SimpleNamespace(decode=lambda _:original)}):
                reference=ui.compact_room(source,textures,root/'reference')
                candidate=ui.compact_room(source,textures,root/'candidate',compact_uvs=True)
                self.assertIs(ui.mirror.MODEL_OBSERVER,sentinel)
            small=(root/'candidate/r100.arc').read_bytes();large=(root/'reference/r100.arc').read_bytes()
            self.assertEqual(reference['resident_archive_bytes']-candidate['resident_archive_bytes'],192)
            self.assertEqual(candidate['model_uvs']['runtime_metadata_bytes'],0)
            self.assertEqual(candidate['model_uvs']['runtime_scratch_bytes'],0)
            def models(data):
                smd=struct.unpack_from('<I',data,16+5*4)[0]
                table=smd+struct.unpack_from('<I',data,smd+4)[0]
                return [table+struct.unpack_from('<I',data,table+i*4)[0] for i in range(2)]
            for a,b in zip(models(large),models(small)):
                self.assertEqual(resolve(large,a),resolve(small,b))
                self.assertEqual(struct.unpack_from('<I',small,b+28)[0]%32,0)
                # Bind/bounds arrays and counts are unmodified, including seams.
                self.assertEqual(large[a+24:a+28],small[b+24:b+28])
                self.assertEqual(large[a+56:a+64],small[b+56:b+64])
            self.assertEqual(candidate['model_uvs']['recovery_bytes'],192)
            for entry in candidate['model_uvs']['entries']:
                self.assertEqual(entry['source_records'],32);self.assertEqual(entry['unique_records'],3)
                self.assertEqual(entry['padding_bytes'],20)
            for entry in candidate['selected']:
                h=entry['resident_header'];base=entry['resident_tpl']
                self.assertEqual(base+struct.unpack_from('<I',small,h+8)[0],entry['resident_payload'])
                self.assertEqual(small[entry['resident_payload']:entry['resident_payload']+8],b'R4NREF\0\0')
            dar=(root/'candidate/r100.dar').read_bytes()
            self.assertEqual(struct.unpack_from('<I',dar,36)[0],len(small))
            self.assertEqual(source.read_bytes(),container)

    def observed(self):
        source=model();data=bytearray(source);models=[];refs=[]
        with mock.patch.object(ui.mirror,'MODEL_OBSERVER',lambda f,o,n,c,l:models.append((o,n,c,l))),mock.patch.object(ui.mirror,'OFFSET_OBSERVER',lambda f,o,b,v:refs.append((o,b,v))):
            ui.mirror.fmt_bin(ui.mirror.Swapper(data,'test'),0,len(data),'st1/r100.arc#5/BIN0')
        return data,models,refs

    def test_retains_nonrigid_and_other_families_and_rejects_overlap(self):
        data,models,refs=self.observed();baseline=bytes(data);layout=models[0][3]
        for key,value in [('joints',2),('shape',1),('blend',1),('flip',1),('weights',2),('extended_weights',256)]:
            with mock.patch.dict(layout,{key:value}):
                ranges,entries,retained=ui.compact_model_uvs(data,models)
                self.assertFalse(ranges);self.assertFalse(entries);self.assertEqual(len(retained),1)
                self.assertEqual(data,baseline)
        other=[(0,len(data),'st1/r100.arc#11/enemy.bin',layout)]
        self.assertEqual(ui.compact_model_uvs(data,other),([],[],[]))
        layout['occupied'].append((layout['uv_offset']+4,layout['uv_offset']+8))
        with self.assertRaisesRegex(ValueError,'overlaps'):ui.compact_model_uvs(data,models)
        self.assertEqual(data,baseline)

    def test_retained_reference_into_removed_array_fails_closed(self):
        data,models,refs=self.observed()
        ranges,entries,_=ui.compact_model_uvs(data,models)
        self.assertTrue(ranges)
        refs.append((4,0,models[0][3]['uv_offset']+4))
        with self.assertRaisesRegex(ValueError,'enters replaced span'):ui.compact_spans(data,refs,ranges)


if __name__=='__main__':unittest.main()