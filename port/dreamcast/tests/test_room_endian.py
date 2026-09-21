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
        arc = bytearray(struct.pack('>I3I I 4s 2I', 1, 0, 0, 0, 24, b'CAM\0', 0, 0))
        le.REPORT.clear()
        le.convert_file('st1/r120.arc', arc)
        with tempfile.TemporaryDirectory() as tmp:
            deps=Path(tmp)/'deps.txt'; deps.write_text('st1/r120.arc\n')
            problems=le.check_required(le.REPORT, deps)
        self.assertTrue(any('CAM' in x for x in problems))

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
        out, entry=self.convert(data, le.fmt_smd)
        self.assertFalse(entry['complete'])
        self.assertEqual(entry['raw_parts'], ['BIN0 payload'])
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