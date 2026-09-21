"""Source-layout room constants and collision conversion, without private data."""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('le_room', ROOT/'port/dreamcast/tools/le_mirror.py')
le = importlib.util.module_from_spec(spec)
spec.loader.exec_module(le)


def collision():
    # One polygon; root with two leaves in original order, including a duplicate
    # polygon reference. Duplicate suppression belongs to the source query.
    out = bytearray(struct.pack('>BB9H', 0xFF, 0, 3, 1, 3, 0, 1, 1, 0, 0, 3))
    out += struct.pack('>21f', *range(21))
    out += struct.pack('>7H2xI', 0, 1, 2, 0, 0, 1, 2, 0x12345678)
    for count, flags, following in [(0, 1, 0), (1, 0, 40), (1, 0, 0)]:
        out += struct.pack('>6f4HI', 1, 2, 3, 4, 5, 6, count, 0, 0, flags, following)
        if count: out += struct.pack('>H2x', 0)
    return out


class RoomFormats(unittest.TestCase):
    def convert(self, data, handler):
        out = bytearray(data)
        sw = le.Swapper(out, 'fixture')
        entry = {}
        le.guarded(sw, handler, 0, len(out), 'fixture', entry)
        return out, entry

    def test_constants_bitmap_crosses_word(self):
        values = [33, 1, 1] + list(range(33))
        raw = struct.pack('>36I', *values)
        out, entry = self.convert(raw, le.fmt_cns)
        self.assertTrue(entry['complete'])
        self.assertEqual(struct.unpack('<36I', out), tuple(values))

    def test_collision_preserves_hierarchy_and_attributes(self):
        raw = collision()
        out, entry = self.convert(raw, le.fmt_sat)
        self.assertTrue(entry['complete'])
        self.assertEqual(out[:2], raw[:2])  # 0xff means file, not multi-SAT
        self.assertEqual(struct.unpack_from('<9H', out, 2), struct.unpack_from('>9H', raw, 2))
        self.assertEqual(struct.unpack_from('<21f', out, 20), tuple(range(21)))
        poly = 20+84
        self.assertEqual(struct.unpack_from('<7H2xI', out, poly), struct.unpack_from('>7H2xI', raw, poly))
        root = poly+20
        for off in [root, root+36, root+76]:
            self.assertEqual(struct.unpack_from('<6f4HI', out, off), struct.unpack_from('>6f4HI', raw, off))
        self.assertEqual(out[root+72:root+76], bytes(4))
        self.assertEqual(out[root+112:root+116], bytes(4))

    def test_multiple_sections_and_shared_offsets(self):
        part = collision()
        raw = bytes([0x80, 3, 0, 0])+struct.pack('>3I', 16, 16, 16+len(part))+part+part
        out, entry = self.convert(raw, le.fmt_sat)
        self.assertTrue(entry['complete'])
        self.assertEqual(struct.unpack_from('<3I', out, 4), (16, 16, 16+len(part)))
        self.assertEqual(out[16:16+len(part)], out[16+len(part):])

    def test_bad_references_rollback_entire_collision_region(self):
        for field, fmt, value in [(20+84, '>H', 3), (20+84+20+36+32, '>I', 4),
                                  (18, '>H', 4), (20+84+20+36+36, '>H', 1)]:
            raw = collision(); struct.pack_into(fmt, raw, field, value)
            out, entry = self.convert(raw, le.fmt_sat)
            self.assertFalse(entry['complete'])
            self.assertIn('error', entry)
            self.assertEqual(out, raw)

    def test_motion_codec_preserves_all_source_key_types_and_layout(self):
        fcv = le.motion_codec()
        joints = []
        for kind in fcv.FCC_FMT:
            v, t = fcv.FCC_FMT[kind]
            values = (1.25 if v == 'f' else -17,)
            if t:
                values += ((0.5, -0.25) if t == 'f' else (4, -3))
            joints.append(fcv.Joint(2, 0, kind, len(joints),
                [fcv.Axis([0, 10], [values, values]) for _ in range(3)]))
        motion = fcv.Motion(10, joints, list(reversed(range(len(joints)))))
        raw = fcv.serialise(motion)
        out, entry = self.convert(raw, le.fmt_fcv)
        self.assertTrue(entry['complete'], entry)
        n = len(joints)
        self.assertEqual(struct.unpack_from('<H', out)[0], 10)
        self.assertEqual(out[2], n)
        table = ((3+3*n+3)&~3)+4
        for i, joint in enumerate(joints):
            self.assertEqual(struct.unpack_from('<H', out, 3+2*i)[0], joint.info)
            offset = struct.unpack_from('<I', out, table+4*i)[0]
            self.assertEqual(offset, struct.unpack_from('>I', raw, table+4*i)[0])
            value, tangent = fcv.FCC_FMT[joint.fcc_type]
            fmt = value + (2*tangent if tangent else '')
            stride = struct.calcsize('<'+fmt)
            for axis in joint.axes:
                self.assertEqual(struct.unpack_from('<3H', out, offset), (2, 0, 10))
                offset += 6
                for key in axis.keys:
                    self.assertEqual(struct.unpack_from('<'+fmt, out, offset), key)
                    offset += stride
        # Bounds, unknown key type and noncanonical source bytes fail closed.
        for mutation in ('offset', 'type', 'padding'):
            bad = bytearray(raw)
            if mutation == 'offset': struct.pack_into('>I', bad, table, len(bad))
            elif mutation == 'type': struct.pack_into('>H', bad, 3, 0x3002)
            else: bad[-1] ^= 1
            unchanged, entry = self.convert(bad, le.fmt_fcv)
            self.assertFalse(entry['complete'], entry)
            self.assertEqual(unchanged, bad)

    def test_named_motion_zero_padding_roundtrips_without_changing_keys(self):
        fcv = le.motion_codec()
        joint = fcv.Joint(2, 0, 10, 0, [fcv.Axis([0], [(1, -2, 3)]) for _ in range(3)])
        raw = fcv.serialise(fcv.Motion(1, [joint], [0], padding_byte=0))
        self.assertEqual(fcv.serialise(fcv.parse(raw)), raw)
        out, entry = self.convert(raw, le.fmt_fcv)
        self.assertTrue(entry['complete'], entry)
        self.assertEqual(out[-23:], bytes(23))
        raw = fcv.serialise_seq(fcv.Sequence(0, [fcv.SeqKey(64, 4, 5)], padding_byte=0))
        self.assertEqual(fcv.serialise_seq(fcv.parse_seq(raw)), raw)
        out, entry = self.convert(raw, le.fmt_fcvseq)
        self.assertTrue(entry['complete'], entry)
        self.assertEqual(out[8:], bytes(24))

    def test_motion_sequence_preserves_sound_and_event_bytes(self):
        fcv = le.motion_codec()
        raw = fcv.serialise_seq(fcv.Sequence(1, [fcv.SeqKey(64, 7, 0xa5),
                                                fcv.SeqKey(129, 11, 0x81)]))
        out, entry = self.convert(raw, le.fmt_fcvseq)
        self.assertTrue(entry['complete'], entry)
        self.assertEqual(struct.unpack_from('<HBBHBBHBB', out),
                         (2, 1, 0, 64, 7, 0xa5, 129, 11, 0x81))
        self.assertEqual(out[12:], raw[12:])

    def item_pack(self):
        model = self.model_fixture()
        # Two IDs deliberately share one BIN and one TPL. Offsets are relative
        # to their own table, not to the archive; use nonzero padding too.
        data = bytearray(96) + model + bytearray(48)
        struct.pack_into('>4I', data, 0, 3, 32, 64, 416)
        struct.pack_into('>IHHIHHI', data, 32, 2, 7, 0, 0, 255, 0, 0)
        struct.pack_into('>3I', data, 64, 2, 32, 32)
        struct.pack_into('>3I', data, 416, 2, 16, 16)
        struct.pack_into('>3I', data, 432, 0x20af30, 0, 12)
        return data

    def test_item_pack_source_lookup_and_shared_resources(self):
        data = self.item_pack()
        out, entry = self.convert(data, le.fmt_itm)
        self.assertTrue(entry['complete'], entry)
        # Execute the same three-table addressing used by cItmSys::DataLoad.
        oi, ob, ot = struct.unpack_from('<3I', out, 4)
        count, = struct.unpack_from('<I', out, oi)
        for i, expected_id in enumerate((7, 255)):
            self.assertEqual(struct.unpack_from('<H', out, oi+4+8*i)[0], expected_id)
            model = ob + struct.unpack_from('<I', out, ob+4+4*i)[0]
            texture = ot + struct.unpack_from('<I', out, ot+4+4*i)[0]
            expected, _ = self.convert(self.model_fixture(), le.fmt_bin)
            self.assertEqual(out[model:model+320], expected)
            self.assertEqual(struct.unpack_from('<3I', out, texture), (0x20af30, 0, 12))

    def test_item_pack_rejects_bad_counts_ids_and_cross_table_payload(self):
        for at, fmt, value in ((64, '>I', 3), (36, '>H', 256),
                               (68, '>I', 400), (68, '>I', 4)):
            raw = self.item_pack(); struct.pack_into(fmt, raw, at, value)
            out, entry = self.convert(raw, le.fmt_itm)
            self.assertFalse(entry['complete'], entry)
            self.assertEqual(out, raw)

    def block_pack(self):
        data = bytearray(144)
        struct.pack_into('>4sHBBHH3I', data, 0, b'BLK\0', 0x100, 0, 2, 1, 2, 24, 48, 104)
        data[24:48] = bytes([1, 0, 0, 0, 1]+[255]*7+[1, 0, 0, 0, 0]+[255]*7)
        struct.pack_into('>IBBH11f4B', data, 48, 0, 1, 1, 0, *range(11), 1, 0, 1, 7)
        data[104:124] = bytes([1, 0, 0, 0, 1]+[255]*7+[0]+[255]*7)
        data[124:144] = bytes([1, 1, 0, 0]+[255]*16)
        return data

    def test_block_residency_keeps_source_sets_and_area_order(self):
        raw = self.block_pack(); out, entry = self.convert(raw, le.fmt_blk)
        self.assertTrue(entry['complete'], entry)
        self.assertEqual(struct.unpack_from('<4sHBBHH3I', out),
                         struct.unpack_from('>4sHBBHH3I', raw))
        self.assertEqual(struct.unpack_from('<IBBH11f4B', out, 48),
                         struct.unpack_from('>IBBH11f4B', raw, 48))
        self.assertEqual(out[24:48], raw[24:48])
        self.assertEqual(out[104:], raw[104:])  # signed -1 lists / active flags

    def test_block_residency_rejects_invalid_refs_and_overlap(self):
        for at, fmt, value in ((28, '>B', 2), (103, '>B', 8), (102, '>B', 2),
                               (105, '>B', 2), (16, '>I', 24)):
            raw = self.block_pack(); struct.pack_into(fmt, raw, at, value)
            out, entry = self.convert(raw, le.fmt_blk)
            self.assertFalse(entry['complete'], entry)
            self.assertEqual(out, raw)

    def etc_pack(self, unknown=False):
        data = bytearray(32); struct.pack_into('>I', data, 0, 2)
        for name, body in ((b'object.bin', self.model_fixture()),
                           (b'unknown.xyz' if unknown else b'object.tpl',
                            struct.pack('>3I', 0x20af30, 0, 12))):
            header = bytearray(64);struct.pack_into('>I', header, 0, 64+len(body))
            header[32:32+len(name)] = name
            data += header+body
        return data

    def test_etc_named_walk_and_unknown_member_fail_closed(self):
        for unknown in (False, True):
            raw = self.etc_pack(unknown);out, entry = self.convert(raw, le.fmt_etm)
            self.assertEqual(entry['complete'], not unknown, entry)
            count, = struct.unpack_from('<I', out);self.assertEqual(count, 2)
            p = 32
            for name in (b'object.bin', b'unknown.xyz' if unknown else b'object.tpl'):
                self.assertEqual(out[p+32:p+64].split(b'\0', 1)[0], name)
                p += struct.unpack_from('<I', out, p)[0]
            self.assertEqual(p, len(out))
            if unknown:
                self.assertEqual(out[-12:], raw[-12:])
                self.assertIn('etc member unknown.xyz', entry['raw_parts'])
        raw = self.etc_pack();struct.pack_into('>I', raw, 32, 32)
        out, entry = self.convert(raw, le.fmt_etm)
        self.assertFalse(entry['complete']);self.assertEqual(out, raw)

    def test_shadow_relative_model_and_placement(self):
        model=self.model_fixture()
        data=bytearray(128)+model
        data[0]=0x40
        struct.pack_into('>HI',data,2,1,96)
        struct.pack_into('>9f',data,16,*range(9))
        struct.pack_into('>I',data,96,32)
        out,entry=self.convert(data,le.fmt_shd)
        self.assertTrue(entry['complete'],entry)
        self.assertEqual(struct.unpack_from('<9f',out,16),tuple(range(9)))
        expected,_=self.convert(model,le.fmt_bin)
        self.assertEqual(out[128:],expected)
        struct.pack_into('>I',data,96,len(data))
        out,entry=self.convert(data,le.fmt_shd)
        self.assertFalse(entry['complete'])
        self.assertEqual(out,data)

    def test_room_texture_nested_payloads(self):
        from test_le_mirror import make_tpl, make_anm
        tpl=make_tpl([(8,8,5,bytes(range(128)))])
        anm=make_anm(8,8,4,4,1)
        data=bytearray(96)+tpl+anm
        struct.pack_into('>4I',data,0,3,32,64,80)
        struct.pack_into('>IHHI',data,32,1,17,0,0)
        struct.pack_into('>2I',data,64,1,32)
        struct.pack_into('>2I',data,80,1,16+len(tpl))
        out,entry=self.convert(data,le.fmt_tex)
        self.assertTrue(entry['complete'],entry)
        self.assertEqual(struct.unpack_from('<IHHI',out,32),(1,17,0,0))
        expected,_=self.convert(tpl,le.fmt_tpl)
        self.assertEqual(out[96:96+len(tpl)],expected)
        self.assertEqual(struct.unpack_from('<5H',out,96+len(tpl)),(8,8,4,4,1))

    def test_floor_empty_sentinel_and_bgm_area(self):
        sentinel = bytes(16) + bytes([0xcd])*16
        out, entry = self.convert(sentinel, le.fmt_fse)
        self.assertTrue(entry['complete'])
        self.assertEqual(out, sentinel)
        data = bytearray(16+132)
        data[:4] = b'FSE\0'
        struct.pack_into('>HH', data, 4, 0x103, 1)
        data[17] = 2
        data[37] = 1
        struct.pack_into('>11f', data, 40, *range(11))
        struct.pack_into('>2i2Hi', data, 88, -10, 200, 3, 4, 90)
        out, entry = self.convert(data, le.fmt_fse)
        self.assertTrue(entry['complete'])
        self.assertEqual(struct.unpack_from('<11f', out, 40), tuple(range(11)))
        self.assertEqual(struct.unpack_from('<2i2Hi', out, 88), (-10,200,3,4,90))

    def test_sequence_scalars_keep_byte_colors_and_unknown_union_incomplete(self):
        data=bytearray(48+300)
        struct.pack_into('>H',data,0,1)
        struct.pack_into('>6f',data,12,*range(6))
        p=48
        struct.pack_into('>H',data,p+4,259)
        struct.pack_into('>36f',data,p+12,*range(36))
        data[p+156:p+160]=bytes([11,22,33,44])
        struct.pack_into('>6H',data,p+176,*range(100,106))
        struct.pack_into('>4h',data,p+272,-1,2,-3,4)
        out,entry=self.convert(data,le.fmt_sequence)
        self.assertTrue(entry['complete'])
        self.assertEqual(struct.unpack_from('<H',out,p+4)[0],259)
        self.assertEqual(struct.unpack_from('<36f',out,p+12),tuple(range(36)))
        self.assertEqual(out[p+156:p+160],bytes([11,22,33,44]))
        self.assertEqual(struct.unpack_from('<4h',out,p+272),(-1,2,-3,4))
        data[p+205]=123
        out,entry=self.convert(data,le.fmt_sequence)
        self.assertFalse(entry['complete'])
        self.assertNotIn('error',entry)  # preserve already-qualified EFF fields
        self.assertEqual(out[p+204:p+212],data[p+204:p+212])

    def test_r120_unused_normal_work_contract_is_scoped(self):
        data=bytearray(16+144); data[1]=1; data[16+20]=17
        for ctx,complete in [('st1/r120.arc#9',True),('st1/r100.arc#9',False)]:
            out=bytearray(data);sw=le.Swapper(out,ctx);entry={}
            le.guarded(sw,le.fmt_smx,0,len(out),ctx,entry)
            self.assertEqual(entry['complete'],complete)
            self.assertEqual(out[32:148],data[32:148])

    def test_native_room_preserves_sound_and_requires_complete_coverage(self):
        # A native sound table and bytes retain their absolute/relative offsets;
        # the replacement room becomes the only top-level MRAM allocation.
        data = bytearray(le.CONTAINER_MAGIC + bytes(2048-32))
        struct.pack_into('<8I', data, 32, 0, 32, 0, 1024, 0, 0, 0, 0)
        struct.pack_into('<8I', data, 64, 4, 512, 0, 1536, 0, 0, 0, 0)
        struct.pack_into('<I', data, 96, le.END_OF_TABLE)
        data[1536:] = bytes(range(256))*2
        arc = b'converted room data'
        entries = [dict(file='st1/r100.arc', handled=True, complete=True),
                   dict(file='st1/r100.arc', sub='st1/r100.arc#0', handled=True, complete=True),
                   dict(file='st1/r100.das', part='0', type=0, handled=False),
                   dict(file='st1/r100.das', part='1/0', type=1, handled=True, complete=True)]
        name, out = le.prepare_native_room('st1/r100.das', data, arc, entries)
        self.assertEqual(name, 'st1/r100.dar')
        self.assertEqual(out[64:2048], data[64:])
        self.assertEqual(struct.unpack_from('<4I', out, 32), (0, len(arc), 0, 2048))
        self.assertEqual(out[2048:2048+len(arc)], arc)
        self.assertEqual(len(out) % 32, 0)
        for i in (1, 3):
            failed = [dict(e) for e in entries]
            failed[i]['complete'] = False
            with self.assertRaisesRegex(ValueError, 'unqualified'):
                le.prepare_native_room('st1/r100.das', data, arc, failed)
        struct.pack_into('<I', data, 40, 0x80500000)
        with self.assertRaisesRegex(ValueError, 'destination'):
            le.prepare_native_room('st1/r100.das', data, arc, entries)

    def test_room_sidecar_uses_normal_handlers_and_keeps_container(self):
        # A minimal CNS archive, plus a nested sound container entry which must
        # remain in the original .das rather than being interpreted as YZ2.
        arc = struct.pack('>I3I I 4s 2I', 1, 0, 0, 0, 24, b'CNS\0', 0, 0)
        source = bytearray(le.CONTAINER_MAGIC + bytes(1024))
        struct.pack_into('>4I', source, 32, 0, 8, 0, 1024)
        struct.pack_into('>4I', source, 64, le.NESTED, 0, 0, 1032)
        struct.pack_into('>I', source, 96, le.END_OF_TABLE)
        source[1024:1032] = b'payload!'
        before = bytes(source)
        decoder = mock.Mock(return_value=arc)
        le.REPORT.clear()
        with mock.patch.dict(sys.modules, {'decode_yz2': types.SimpleNamespace(decode=decoder)}):
            name, converted = le.prepare_room_archive('st1/r120.das', source)
        self.assertEqual(name, 'st1/r120.arc')
        decoder.assert_called_once_with(b'payload!')
        self.assertEqual(bytes(source), before)
        self.assertEqual(struct.unpack_from('<I', converted)[0], 1)
        self.assertTrue(all(e.get('complete') for e in le.REPORT))

    def test_incomplete_room_remains_rejected_by_dependency_gate(self):
        arc = bytearray(struct.pack('>I3I I 4s 2I', 1, 0, 0, 0, 24, b'MHT\0', 0, 0))
        le.REPORT.clear()
        le.convert_file('st1/r120.arc', arc)
        with tempfile.TemporaryDirectory() as tmp:
            deps=Path(tmp)/'deps.txt'; deps.write_text('st1/r120.arc\n')
            problems=le.check_required(le.REPORT, deps)
        self.assertTrue(any('MHT' in x for x in problems))

    def test_light_path_byte_count_offsets_and_terminators(self):
        raw=bytes([3,0xCD,0xCD,0xCD])+struct.pack('>3I',16,0,19)+bytes([0,200,255,100,255])
        out,entry=self.convert(raw,le.fmt_light_paths)
        self.assertTrue(entry['complete'],entry)
        self.assertEqual(out[:4],raw[:4])
        self.assertEqual(struct.unpack_from('<3I',out,4),(16,0,19))
        self.assertEqual(out[16:],raw[16:])
        out,entry=self.convert(raw[:-1],le.fmt_light_paths)
        self.assertIn('unterminated',entry['error'])
        self.assertEqual(out,raw[:-1])

    def camera_fixture(self, kind=6):
        d=bytearray(256);d[:7]=b'B404'+bytes([1,1,1])
        struct.pack_into('>2I',d,24,32,80)
        d[32:36]=bytes([1,2,3,0x40])
        struct.pack_into('>f',d,36,0.25)
        struct.pack_into('>2f2I',d,64,100,-20,3,148)
        d[80:84]=bytes([1,3,kind,0x30])
        struct.pack_into('>3fIf',d,84,1,2,3,248 if kind==6 else 0x818C3400,0.75)
        struct.pack_into('>5I',d,112,2,184,208,232,240)
        d[132:137]=bytes([1,2,3,4,5]);struct.pack_into('>I',d,140,15)
        struct.pack_into('>25f',d,148,*range(25));struct.pack_into('>2H',d,248,0,30)
        return d

    def test_camera_consumes_authored_offsets_and_type_specific_frames(self):
        for kind in (6,8):
            raw=self.camera_fixture(kind);out,entry=self.convert(raw,le.fmt_cam)
            self.assertTrue(entry['complete'],entry)
            self.assertEqual(out[:7],raw[:7])
            self.assertEqual(struct.unpack_from('<2I',out,24),(32,80))
            self.assertEqual(struct.unpack_from('<25f',out,148),tuple(range(25)))
            self.assertEqual(struct.unpack_from('<I',out,140)[0],15)
            if kind==6:self.assertEqual(struct.unpack_from('<2H',out,248),(0,30))
            else:
                self.assertEqual(out[248:252],raw[248:252])
                self.assertEqual(struct.unpack_from('<I',out,96)[0],0x818C3400)
        raw=self.camera_fixture();struct.pack_into('>I',raw,120,184)  # shared pos/at
        out,entry=self.convert(raw,le.fmt_cam)
        self.assertTrue(entry['complete'],entry)
        raw=self.camera_fixture();struct.pack_into('>I',raw,76,0xFFFFFFFF)
        out,entry=self.convert(raw,le.fmt_cam)
        self.assertFalse(entry['complete']);self.assertEqual(out,raw)

    def test_light_colors_shared_cuts_and_typed_work(self):
        d=bytearray(16+260+600)
        struct.pack_into('>HBB2I',d,0,2,0x2C,2,16,16)
        p=16;d[p:p+4]=bytes([11,22,33,44]);struct.pack_into('>I',d,p+4,2)
        struct.pack_into('>I2f',d,p+8,2,1.25,9000)
        d[p+20:p+24]=bytes([55,66,77,88])
        for i,kind in enumerate((2,4)):
            w=p+260+i*300;d[w:w+4]=bytes([1,3,kind,0x40])
            struct.pack_into('>4f',d,w+4,1,2,3,100)
            d[w+20:w+24]=bytes([128,129,130,131])
            struct.pack_into('>f',d,w+24,0.5)
            struct.pack_into('>IHHI',d,w+32,0x00020003,100,2,9)
            struct.pack_into('>9f',d,w+44,*range(9))
        struct.pack_into('>4f',d,16+260+108,1,2,3,4)
        struct.pack_into('>2h',d,16+260+300+108+4,-90,45)
        out,entry=self.convert(d,le.fmt_lit)
        self.assertTrue(entry['complete'],entry)
        self.assertEqual(out[p:p+4],d[p:p+4])
        self.assertEqual(out[p+20:p+24],d[p+20:p+24])
        self.assertEqual(struct.unpack_from('<I',out,p+260+32)[0],0x00020003)
        self.assertEqual(struct.unpack_from('<4f',out,p+260+108),(1,2,3,4))
        self.assertEqual(struct.unpack_from('<2h',out,p+260+300+112),(-90,45))
        d[p+80]=1;out,entry=self.convert(d,le.fmt_lit)
        self.assertTrue(entry['complete'])  # documented opaque padding
        self.assertEqual(out[p+80],1)
        d[p+260+2]=16;out,entry=self.convert(d,le.fmt_lit)
        self.assertEqual(entry['raw_parts'],['cut0 light0 type16 work'])

    @unittest.skipUnless(shutil.which('g++'), 'host compiler required')
    def test_light_parent_numeric_and_halfword_views(self):
        header=(ROOT/'include/light.h').read_text()
        begin=header.index('    union {\n        u32 ParentNo;')
        end=header.index('    };',begin)+6
        source='#include <cassert>\nusing u16=unsigned short;using u32=unsigned;struct Test {\n'+header[begin:end]+'\n};\n'
        source+='int main(){Test l{};l.ParentNo=0x12345678;assert(l.parent.partsNo==0x1234 && l.parent.no==0x5678);}'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(source)
            subprocess.run(['g++',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

    def model_fixture(self, byte_normals=False):
        data=bytearray(320)
        struct.pack_into('>I',data,0,80)
        struct.pack_into('>3I',data,12,148,136,128)
        data[24:26]=bytes([1,1])
        struct.pack_into('>H3I',data,26,1,160,0xA0000000 if byte_normals else 0x80000000,1)
        data[40]=8
        struct.pack_into('>H3I2H3I',data,42,0,0,96,120,3,1,0x20030818,224,240)
        data[80:84]=bytes([0,255,7,8]);struct.pack_into('>3f',data,84,1.5,-2,3)
        struct.pack_into('>12h',data,96,-12,23,-34,0,56,67,78,0,90,-101,112,0)
        if byte_normals: data[120:124]=bytes([127,128,1,0])
        else: struct.pack_into('>4h',data,120,-16384,123,16384,0)
        # Joint 9 refers to the owner's rig, not this attached model's nParts.
        data[128:136]=bytes([9,0,0,1,100,0,0,0])
        struct.pack_into('>6h',data,136,-1,2,3,-4,5,6)
        data[148:160]=bytes(range(12))
        data[171:176]=bytes([4,2,3,4,5])
        struct.pack_into('>2I',data,184,32,1)
        data[192:195]=bytes([0x90,0,3])
        for i in range(3): struct.pack_into('>4H',data,195+8*i,i,0,i,i)
        struct.pack_into('>I4H',data,224,1,0,9,4,50)
        struct.pack_into('>IH',data,240,1,9)
        return data

    def test_bin_keeps_distinct_arrays_and_gx_bytes(self):
        for byte_normals in [False,True]:
            raw=self.model_fixture(byte_normals)
            out,entry=self.convert(raw,le.fmt_bin)
            self.assertTrue(entry['complete'],entry)
            self.assertEqual(out[80:84],raw[80:84])
            self.assertEqual(struct.unpack_from('<3f',out,84),(1.5,-2,3))
            self.assertEqual(struct.unpack_from('<12h',out,96),struct.unpack_from('>12h',raw,96))
            if byte_normals: self.assertEqual(out[120:124],raw[120:124])
            else: self.assertEqual(struct.unpack_from('<4h',out,120),struct.unpack_from('>4h',raw,120))
            self.assertEqual(out[128:136],raw[128:136])
            self.assertEqual(struct.unpack_from('<6h',out,136),(-1,2,3,-4,5,6))
            self.assertEqual(out[148:184],raw[148:184])
            self.assertEqual(out[192:224],raw[192:224])
            self.assertEqual(struct.unpack_from('<I4H',out,224),(1,0,9,4,50))
            self.assertEqual(struct.unpack_from('<IH',out,240),(1,9))

    def test_bin_rejects_bad_draw_refs_and_preserves_morphs(self):
        raw=self.model_fixture();struct.pack_into('>H',raw,195,3)
        out,entry=self.convert(raw,le.fmt_bin)
        self.assertIn('index outside',entry['error']);self.assertEqual(out,raw)
        raw=self.model_fixture();struct.pack_into('>I',raw,44,272)
        struct.pack_into('>3I8h',raw,272,1,8,2,0,-1,2,-3,2,4,-5,6)
        out,entry=self.convert(raw,le.fmt_bin)
        self.assertTrue(entry['complete'],entry)
        self.assertEqual(struct.unpack_from('<3I8h',out,272),(1,8,2,0,-1,2,-3,2,4,-5,6))
        struct.pack_into('>H',raw,284,3)
        out,entry=self.convert(raw,le.fmt_bin)
        self.assertIn('morph vertex outside',entry['error'])
        self.assertEqual(out,raw)

    def test_smd_uses_existing_motion_codec_and_rejects_bad_motion(self):
        fcv = le.motion_codec()
        motion = fcv.serialise(fcv.Motion(2, [], []))
        data = bytearray(96) + motion
        struct.pack_into('>BBH3I', data, 0, 0, 0, 1, 0, 0, 88)
        data[52:55] = bytes([255, 255, 0])
        struct.pack_into('>I', data, 88, 8)
        out, entry = self.convert(data, le.fmt_smd)
        self.assertTrue(entry['complete'], entry)
        self.assertEqual(out[96:], fcv.serialise(fcv.parse(motion), '<'))
        data[-1] ^= 1
        out, entry = self.convert(data, le.fmt_smd)
        self.assertFalse(entry['complete']);self.assertEqual(out, data)

    def test_smd_groups_reserve_slots_not_extra_records(self):
        # nModel=1, group has 100 deferred block slots. Only one work lives here.
        data=bytearray(116)
        struct.pack_into('>BBH3I', data, 0, 64, 1, 1, 104, 116, 116)
        struct.pack_into('>2I', data, 16, 1, 100)
        struct.pack_into('>9f', data, 24, *range(9))
        data[60:64]=bytes([0, 255, 255, 7])
        struct.pack_into('>I', data, 92, 0x12340008)
        struct.pack_into('>I', data, 104, 4)
        data[108:116]=b'RAW BIN!'
        with mock.patch.object(le, 'fmt_bin', return_value=['fixture payload']):
            out, entry=self.convert(data, le.fmt_smd)
        self.assertFalse(entry['complete'])
        self.assertEqual(entry['raw_parts'], ['BIN0 fixture payload'])
        self.assertEqual(struct.unpack_from('<2I', out,16), (1,100))
        self.assertEqual(struct.unpack_from('<9f', out,24), tuple(range(9)))
        self.assertEqual(struct.unpack_from('<I',out,92)[0],0x12340008)
        self.assertEqual(out[108:],b'RAW BIN!')
        self.assertEqual(out[60:64],data[60:64])

    def test_smx_movers_keep_byte_flags_and_report_unknown_work(self):
        data=bytearray(16+3*144); data[1]=3
        for i,kind in enumerate([1,2,0]):
            p=16+i*144; data[p:p+4]=bytes([i,kind,5,2])
            struct.pack_into('>3I',data,p+4,0x12345678,0x10,0x11223344)
            struct.pack_into('>I2f',data,p+132,0x55667788,0.5,-0.25)
        struct.pack_into('>3f',data,32,1,2,3);data[44]=1
        struct.pack_into('>13f',data,176,*range(13))
        data[320]=9
        out,entry=self.convert(data,le.fmt_smx)
        self.assertEqual(entry['raw_parts'],['SMX2 type0 callback work'])
        self.assertEqual(struct.unpack_from('<3f',out,32),(1,2,3))
        self.assertEqual(out[44],1)
        self.assertEqual(struct.unpack_from('<13f',out,176),tuple(range(13)))
        self.assertEqual(out[320],9)
        self.assertEqual(struct.unpack_from('<3I',out,20),(0x12345678,0x10,0x11223344))
        self.assertEqual(struct.unpack_from('<I2f',out,148),(0x55667788,0.5,-0.25))

    @unittest.skipUnless(shutil.which('g++'), 'host compiler required')
    def test_native_scene_flag_and_color_views(self):
        header=(ROOT/'include/scroll.h').read_text()
        work=header[header.index('struct SmdWork {'):header.index('class cSmd {')]
        source=(ROOT/'src/game/scroll.cpp').read_text()
        begin=source.index('static void NativeStoreSourceColor(')
        helper=source[begin:source.index('#endif',begin)]
        fixture='#include <cassert>\nusing u8=unsigned char; using u32=unsigned; struct Vec {float x,y,z;};\n'+work+helper
        fixture+='int main(){ SmdWork w{}; w.flags=0x12345678; assert(w.b.x47==0x78); static_assert(sizeof(SmdWork)==72); u8 c[4]; NativeStoreSourceColor(c,0x11223344); assert(c[0]==0x11 && c[1]==0x22 && c[2]==0x33 && c[3]==0x44); }'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(fixture)
            subprocess.run(['g++',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

    @unittest.skipUnless(shutil.which('g++'), 'host compiler required')
    def test_native_attribute_word_and_halves_agree(self):
        header = (ROOT/'include/at_sub.h').read_text()
        begin = header.index('struct AtPoly {')
        end = header.index('\n};', begin)+3
        source = '#include <cassert>\n#include <cstddef>\nusing u8=unsigned char; using u16=unsigned short; using u32=unsigned;\n'
        source += header[begin:end]
        source += '\nint main() { AtPoly p{}; p.attr=0x12345678; assert(p.attrHi==0x1234 && p.attrLo==0x5678); assert(((p.attrHi<<16)|p.attrLo)==p.attr); static_assert(sizeof(AtPoly)==20); static_assert(offsetof(AtPoly,attr)==16); }'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'test.cpp').write_text(source)
            subprocess.run(['g++',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)


if __name__ == '__main__': unittest.main()