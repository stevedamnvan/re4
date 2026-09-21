"""Focused tests of tools/le_mirror.py: the EFF (effect / id texture data)
handler against its consumers' layouts (src/game/id_tex.cpp IdTexDataLoad,
src/game/eff_sys.cpp EspDataLoad, include/tpl.h, include/esp.h), sub-file
isolation (a child handler can neither read nor change a neighbour, and a
failed child rolls back only itself), shared references, and the boot
fixture dependency check."""
import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "tools" / "le_mirror.py"
SPEC = importlib.util.spec_from_file_location("le_mirror", SCRIPT)
LE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = LE
SPEC.loader.exec_module(LE)


def be32(*values):
    return struct.pack(">%dI" % len(values), *values)


def make_tpl(images):
    """TPL (include/tpl.h): TEXPalette, TEXDescriptor[n], TEXHeader[n] (0x24
    each, padded to 0x40 for the game's alignment), then the image bytes."""
    n = len(images)
    desc_ofs = 12
    hdr_ofs = desc_ofs + 8 * n
    data_ofs = hdr_ofs + 0x40 * n
    out = bytearray(be32(0x0020AF30, n, desc_ofs))
    for i in range(n):
        out += be32(hdr_ofs + 0x40 * i, 0)
    payload = bytearray()
    for w, h, fmt, data in images:
        hdr = struct.pack(">HHIIIIIIfBBBB", h, w, fmt, data_ofs + len(payload), 0, 0, 1, 1, 0.0, 0, 0, 0, 0)
        out += hdr + bytes(0x40 - len(hdr))
        payload += data
    out += payload
    while len(out) % 32:
        out += b"\0"
    return bytes(out)


def make_anm(width, height, cx, cy, frames, tail=b""):
    """EspAnmData (include/esp.h): u16 Width, Height, s16 Cx, Cy, u16 Frames,
    u8 Xn, Loop, Data_num, pad[3], then the byte pattern tables."""
    rec = struct.pack(">HHhhHBBB3x", width, height, cx, cy, frames, 0, 1, 0) + tail
    while len(rec) % 32:
        rec += b"\0"
    return rec


def make_eff(entries, shared_tpl=False):
    """An EFF block (src/game/eff_sys.cpp EffData version 0xB) holding
    `entries` = [(tex_id, tpl_bytes, anm_bytes)]; with shared_tpl every entry's
    TPL offset points at the first TPL (a shared reference)."""
    n = len(entries)
    id_tbl = be32(n) + b"".join(struct.pack(">HHI", tid, 0, 0) for tid, _, _ in entries)
    id_tbl += bytes((-len(id_tbl)) % 32)
    empty = be32(0) + bytes(28)   # est / sst / path lists, efm ids: zero counts
    hdr_size = 0x40
    ofs_tex_id = hdr_size
    ofs_est = ofs_tex_id + len(id_tbl)
    ofs_sst = ofs_est + 32
    ofs_path = ofs_sst + 32
    ofs_efm_id = ofs_path + 32
    ofs_tpl = ofs_efm_id + 32
    tpl_tbl_size = (4 + 4 * n + 31) // 32 * 32
    tpl_blobs = bytearray()
    tpl_rel = []
    for i, (_, tpl, _) in enumerate(entries):
        if shared_tpl and i > 0:
            tpl_rel.append(tpl_rel[0])
            continue
        tpl_rel.append(tpl_tbl_size + len(tpl_blobs))
        tpl_blobs += tpl
    tpl_tbl = be32(n, *tpl_rel) + bytes(tpl_tbl_size - 4 - 4 * n)
    ofs_anm = ofs_tpl + len(tpl_tbl) + len(tpl_blobs)
    anm_tbl_size = (4 + 4 * n + 31) // 32 * 32
    anm_blobs = bytearray()
    anm_rel = []
    for _, _, anm in entries:
        anm_rel.append(anm_tbl_size + len(anm_blobs))
        anm_blobs += anm
    anm_tbl = be32(n, *anm_rel) + bytes(anm_tbl_size - 4 - 4 * n)
    hdr = be32(0xB, ofs_tex_id, ofs_est, ofs_sst, ofs_path, ofs_efm_id, ofs_tpl, ofs_anm, 0, 0, 0, 0) + bytes(16)
    blob = hdr + id_tbl + empty * 4 + tpl_tbl + tpl_blobs + anm_tbl + anm_blobs
    return bytes(blob), {"ofs_tpl": ofs_tpl, "ofs_anm": ofs_anm, "tpl_rel": tpl_rel, "anm_rel": anm_rel,
                         "ofs_tex_id": ofs_tex_id}


def make_tagged(parts):
    """Tagged archive: u32 count, 12 bytes, u32 ofs[count], char tag[count][4]."""
    n = len(parts)
    head = 0x10 + 8 * n
    head = (head + 31) // 32 * 32
    offs = []
    body = bytearray()
    for tag, data in parts:
        offs.append(head + len(body))
        body += data
        while len(body) % 32:
            body += b"\0"
    out = be32(n, 0, 0, 0) + be32(*offs) + b"".join(t.encode().ljust(4, b"\0") for t, _ in parts)
    out += bytes(head - len(out)) + body
    return bytes(out)


IMAGE = bytes(range(256)) * 2   # 512 bytes of recognisable image data


class EffHandlerTest(unittest.TestCase):
    def setUp(self):
        self.tpl_a = make_tpl([(16, 16, 5, IMAGE)])
        self.tpl_b = make_tpl([(8, 8, 5, IMAGE[:128]), (8, 8, 5, IMAGE[128:256])])
        self.anm_a = make_anm(16, 16, 8, 8, 1, b"\x03")
        self.anm_b = make_anm(8, 8, 4, 4, 2, b"\x00\x01\x05\x05")

    def convert(self, blob):
        data = bytearray(blob)
        sw = LE.Swapper(data, "eff")
        entry = {}
        LE.guarded(sw, LE.fmt_eff, 0, len(data), "eff", entry)
        return data, entry

    def test_tables_ids_and_animations_are_swapped_and_images_untouched(self):
        blob, lay = make_eff([(0x13, self.tpl_a, self.anm_a), (0x80, self.tpl_b, self.anm_b)])
        data, entry = self.convert(blob)
        self.assertTrue(entry["complete"], entry)
        # header offsets are little-endian now and still table-relative
        self.assertEqual(struct.unpack_from("<12I", data, 0)[:2], (0xB, lay["ofs_tex_id"]))
        self.assertEqual(struct.unpack_from("<I", data, lay["ofs_tpl"])[0], 2)
        self.assertEqual(struct.unpack_from("<2I", data, lay["ofs_tpl"] + 4), tuple(lay["tpl_rel"]))
        # texture ids keep their u16 width (IdTexDataLoad reads ent[i].id as u8 of a u16 field)
        self.assertEqual(struct.unpack_from("<HHI", data, lay["ofs_tex_id"] + 4), (0x13, 0, 0))
        self.assertEqual(struct.unpack_from("<HHI", data, lay["ofs_tex_id"] + 12), (0x80, 0, 0))
        # animation record: five u16 swapped, the pattern bytes untouched
        a0 = lay["ofs_anm"] + lay["anm_rel"][0]
        self.assertEqual(struct.unpack_from("<HHhhH", data, a0), (16, 16, 8, 8, 1))
        self.assertEqual(data[a0 + 10:a0 + 17], b"\x00\x01\x00\x00\x00\x00\x03")
        # TPL: header swapped, image bytes byte-identical to the source
        t0 = lay["ofs_tpl"] + lay["tpl_rel"][0]
        self.assertEqual(struct.unpack_from("<3I", data, t0), (0x0020AF30, 1, 12))
        img = struct.unpack_from("<I", data, t0 + 12 + 8 + 8)[0]   # TEXHeader.data of image 0
        self.assertEqual(bytes(data[t0 + img:t0 + img + len(IMAGE)]), IMAGE)

    def test_shared_tpl_reference_is_converted_once_and_resolves_for_both_ids(self):
        blob, lay = make_eff([(1, self.tpl_a, self.anm_a), (2, self.tpl_a, self.anm_a)], shared_tpl=True)
        data, entry = self.convert(blob)
        self.assertTrue(entry["complete"], entry)
        self.assertEqual(lay["tpl_rel"][0], lay["tpl_rel"][1])
        t0 = lay["ofs_tpl"] + lay["tpl_rel"][0]
        self.assertEqual(struct.unpack_from("<3I", data, t0), (0x0020AF30, 1, 12))
        # a second conversion of the same bytes would have produced big-endian again
        self.assertNotEqual(struct.unpack_from(">I", data, t0)[0], 0x0020AF30)

    def test_frame_count_must_match_tpl_images(self):
        blob, lay = make_eff([(1, self.tpl_b, self.anm_a)])   # 2 images, 1 frame
        data, entry = self.convert(blob)
        self.assertFalse(entry["handled"])
        self.assertIn("frames 1 != TPL images 2", entry["error"])
        self.assertEqual(bytes(data), blob)   # rolled back

    def test_texture_less_file_leaves_absent_tables_alone(self):
        blob, lay = make_eff([])
        # no textures: the game never dereferences the TPL / animation tables;
        # give them offset 0 like the real files do
        blob = bytearray(blob)
        struct.pack_into(">II", blob, 0x18, 0, 0)
        data, entry = self.convert(bytes(blob))
        self.assertTrue(entry["complete"], entry)
        self.assertEqual(struct.unpack_from("<I", data, 0)[0], 0xB)


class EffectPathTest(unittest.TestCase):
    def fixture(self, shared=False):
        blob, _ = make_eff([])
        data = bytearray(blob)
        # Reuse the path list's 32-byte reservation; append table-relative
        # path data. The two IDs may intentionally resolve one shared path.
        li = struct.unpack_from('>I', data, 16)[0]
        struct.pack_into('>IHHIHHI', data, li, 2 if shared else 1,
                         3, 0x1234, 0x12345678, 9, 0, 0)
        table = len(data)
        struct.pack_into('>I', data, 40, table)
        data += be32(2, 32, 32) + bytes(20) if shared else be32(1, 32) + bytes(24)
        path = len(data)
        data += struct.pack('>H2s', 2, b'PQ')
        for position, normal, distance in [((1.,2.,3.), (0.,1.,0.), 0.), ((4.,5.,6.), (0.,1.,0.), 9.25)]:
            data += struct.pack('>7f12B', *position, *normal, distance,
                                4, 7, 9, 3, 25, 50, 0, 11, 22, 33, 44, 55)
        data += bytes((-len(data)) % 32)
        return bytes(data), li, table, path

    def convert(self, blob):
        data = bytearray(blob); entry = {}
        LE.guarded(LE.Swapper(data, 'effect-path'), LE.fmt_eff, 0, len(data), 'effect-path', entry)
        return data, entry

    def test_source_polyline_values_weights_and_shared_offset_identity(self):
        for shared in (False, True):
            original, li, table, path = self.fixture(shared)
            data, entry = self.convert(original)
            self.assertTrue(entry['complete'], entry)
            self.assertEqual(struct.unpack_from('<HHI', data, li+4), (3, 0x1234, 0x12345678))
            self.assertEqual(struct.unpack_from('<I', data, table+4)[0]+table, path)
            self.assertEqual(struct.unpack_from('<H', data, path)[0], 2)
            self.assertEqual(data[path+2:path+4], b'PQ')
            for i in range(2):
                p = path+4+i*40
                self.assertEqual(struct.unpack_from('<7f', data, p), struct.unpack_from('>7f', original, p))
                self.assertEqual(data[p+28:p+40], original[p+28:p+40])
            # PathGetLength and PathGetPos inputs retain exact source values.
            self.assertEqual(struct.unpack_from('<f', data, path+4+40+24)[0], 9.25)
            if shared:self.assertEqual(struct.unpack_from('<I', data, table+8)[0]+table, path)

    def test_invalid_path_rejected_without_partial_conversion(self):
        original, li, table, path = self.fixture()
        for field, fmt, value in [(path, '>H', 500), (path+4+31, 'B', 4),
                                  (path+4+40+24, '>f', -1), (path+4, '>f', float('nan')),
                                  (table+4, '>I', 4)]:
            data = bytearray(original);struct.pack_into(fmt, data, field, value)
            out, entry = self.convert(bytes(data))
            self.assertFalse(entry['handled'], entry)
            self.assertEqual(out, data)


class IsolationTest(unittest.TestCase):
    def test_child_cannot_reach_a_neighbour_through_a_bad_offset(self):
        tpl = make_tpl([(16, 16, 5, IMAGE)])
        anm = make_anm(16, 16, 8, 8, 1)
        eff, lay = make_eff([(1, tpl, anm)])
        eff = bytearray(eff)
        # point the animation table past the end of this EFF, into the neighbour
        struct.pack_into(">I", eff, 0x1C, len(eff) + 0x40)
        neighbour = make_tpl([(8, 8, 5, IMAGE[:128])])
        arc = make_tagged([("EFF", bytes(eff)), ("TPL", neighbour)])
        data = bytearray(arc)
        LE.REPORT.clear()
        LE.convert_file("iso/test.dat", data)
        subs = {e["sub"]: e for e in LE.REPORT if "sub" in e}
        self.assertFalse(subs["iso/test.dat#0"]["handled"])
        self.assertIn("outside the region", subs["iso/test.dat#0"]["error"])
        self.assertTrue(subs["iso/test.dat#1"]["complete"])
        # the EFF bytes are exactly the source again, the neighbour converted once
        n0 = struct.unpack_from(">I", arc, 0x10)[0]
        n1 = struct.unpack_from(">I", arc, 0x14)[0]
        self.assertEqual(bytes(data[n0:n1]), arc[n0:n1])
        self.assertEqual(struct.unpack_from("<3I", data, n1), (0x0020AF30, 1, 12))

    def test_child_cannot_read_outside_its_region(self):
        sw = LE.Swapper(bytearray(64), "b")
        with sw.bounded(16, 16):
            sw.u32(16)
            with self.assertRaises(ValueError):
                sw.peek32(8)
            with self.assertRaises(ValueError):
                sw.u16(31)
            with self.assertRaises(ValueError):
                sw.bounded(0, 8)    # cannot widen
        sw.u32(0)                    # bounds restored

    def test_rollback_covers_only_the_failed_child(self):
        good = make_tpl([(8, 8, 5, IMAGE[:128])])
        bad = bytearray(make_tpl([(8, 8, 5, IMAGE[:128])]))
        struct.pack_into(">I", bad, 8, 0x7FFFFFF0)   # descriptor table far outside
        arc = make_tagged([("TPL", good), ("TPL", bytes(bad)), ("TPL", good)])
        data = bytearray(arc)
        LE.REPORT.clear()
        LE.convert_file("iso/roll.dat", data)
        subs = {e["sub"]: e for e in LE.REPORT if "sub" in e}
        offs = struct.unpack_from(">3I", arc, 0x10)
        self.assertTrue(subs["iso/roll.dat#0"]["complete"])
        self.assertFalse(subs["iso/roll.dat#1"]["handled"])
        self.assertTrue(subs["iso/roll.dat#2"]["complete"])
        self.assertEqual(bytes(data[offs[1]:offs[2]]), arc[offs[1]:offs[2]])
        for o in (offs[0], offs[2]):
            self.assertEqual(struct.unpack_from("<3I", data, o), (0x0020AF30, 1, 12))


class ArchiveSlotsTest(unittest.TestCase):
    def test_empty_slots_retain_source_indices_and_offsets(self):
        tpl = make_tpl([(8, 8, 5, IMAGE[:128])])
        raw = make_tagged([('', b''), ('TPL', tpl), ('', b''),
                           ('', b''), ('TPL', tpl), ('', b'')])
        self.assertTrue(LE.looks_like_tagged(raw, 0, len(raw)))
        out = bytearray(raw); LE.REPORT.clear()
        LE.convert_file('player.dat', out)
        offsets = struct.unpack_from('>6I', raw, 16)
        self.assertEqual(struct.unpack_from('<6I', out, 16), offsets)
        self.assertEqual(out[40:64], raw[40:64])  # including zero tags
        subs = [e for e in LE.REPORT if 'sub' in e]
        self.assertEqual([e['sub'] for e in subs], ['player.dat#1', 'player.dat#4'])
        self.assertTrue(all(e.get('complete') for e in subs))
        for i in (1, 4):
            self.assertEqual(struct.unpack_from('<3I', out, offsets[i]),
                             (0x0020AF30, 1, 12))

    def test_untagged_payload_is_not_an_empty_slot(self):
        tpl = make_tpl([(8, 8, 5, IMAGE[:128])])
        for parts in [[('', bytes(32)), ('TPL', tpl)],
                      [('TPL', tpl), ('', bytes(32))]]:
            raw = make_tagged(parts)
            self.assertFalse(LE.looks_like_tagged(raw, 0, len(raw)))
        raw = bytearray(make_tagged([('', b''), ('TPL', tpl)]))
        struct.pack_into('>I', raw, 4, 32)  # embedded REL is not this contract
        self.assertFalse(LE.looks_like_tagged(raw, 0, len(raw)))

    def test_unknown_nonempty_neighbor_still_fails_qualification(self):
        raw = make_tagged([('', b''), ('XYZ', bytes(32)), ('', b'')])
        out = bytearray(raw); LE.REPORT.clear()
        LE.convert_file('player.dat', out)
        with tempfile.TemporaryDirectory() as work:
            deps = pathlib.Path(work)/'required.txt'; deps.write_text('player.dat\n')
            self.assertEqual(LE.check_required(LE.REPORT, deps),
                             ['player.dat#1: no handler (tag XYZ)'])


class DrsBoundaryTest(unittest.TestCase):
    @staticmethod
    def fixture():
        body = bytearray(make_tagged([('TPL', make_tpl([(8, 8, 5, IMAGE[:128])])), ('', b'')]))
        rel_off = len(body)
        struct.pack_into('>I', body, 4, rel_off)
        rel = bytearray(96)
        struct.pack_into('>I', rel, 0, 4)
        struct.pack_into('>I', rel, 0x1c, 3)
        struct.pack_into('>2I', rel, 0x28, 64, 8)
        struct.pack_into('>2I', rel, 64, 0, 72)
        rel[74] = 203  # R_DOLPHIN_END, existing tools/relfile.py
        rel[80:] = b'\xcd' * 16
        body += rel
        magic = 'ハカセのアホーーーーーーー！！！'.encode('shift_jis')
        head = magic + be32(0, len(body), 0, 1024, 0, 0, 0, 0)
        head += be32(0xfffffffe, 0, 0, 1024 + len(body), 0, 0, 0, 0)
        head += be32(0xffffffff, 0, 0, 0, 0, 0, 0, 0)
        return head + bytes(1024 - len(head)) + body, 1024 + rel_off

    def test_embedded_rel_does_not_extend_last_asset(self):
        raw, rel_off = self.fixture(); out = bytearray(raw); LE.REPORT.clear()
        LE.convert_file('em/wep02.drs', out)
        self.assertTrue(all(e.get('handled') and e.get('complete') for e in LE.REPORT), LE.REPORT)
        self.assertEqual(struct.unpack_from('<4I', out, 32), (0, len(raw)-1024, 0, 1024))
        self.assertEqual(struct.unpack_from('<I', out, 1028)[0], rel_off-1024)
        entry = next(e for e in LE.REPORT if e.get('tag') == 'REL')
        self.assertEqual((entry['module_id'], entry['ofs']), (4, rel_off))
        self.assertTrue(entry['native_binding_required'])
        self.assertEqual(out[rel_off+64:], raw[rel_off+64:])
        self.assertEqual(struct.unpack_from('<I', out, rel_off)[0], 4)
        self.assertEqual(len([e for e in LE.REPORT if e.get('tag') == 'TPL']), 1)

    def test_invalid_rel_offset_rolls_back_entire_container(self):
        raw, rel_off = self.fixture(); out = bytearray(raw)
        struct.pack_into('>I', out, 1028, len(raw)+32)
        before = bytes(out); LE.REPORT.clear()
        LE.convert_file('em/wep02.drs', out)
        self.assertEqual(out, before)
        self.assertFalse(LE.REPORT[-1]['complete'])

    def test_unknown_neighbor_is_not_qualified_by_container_success(self):
        raw, _ = self.fixture(); out = bytearray(raw)
        out[1024+24:1024+28] = b'XYZ\0'; LE.REPORT.clear()
        LE.convert_file('em/wep02.drs', out)
        with tempfile.TemporaryDirectory() as work:
            deps = pathlib.Path(work)/'deps'; deps.write_text('em/wep02.drs\n')
            self.assertIn('em/wep02.drs:0#0: no handler (tag XYZ)', LE.check_required(LE.REPORT,deps))


class CompactStaticRelTest(unittest.TestCase):
    def converted(self):
        raw, offset = DrsBoundaryTest.fixture()
        out = bytearray(raw); LE.REPORT.clear()
        LE.convert_file('em/wep02.drs', out)
        return out, offset

    def test_keeps_assets_slots_and_empty_sound_record(self):
        out, offset = self.converted(); original = bytes(out)
        compact = LE.compact_static_rel('em/wep02.drs', out, LE.REPORT, {4:'wep02'})
        self.assertEqual(compact[1024:offset], original[1024:offset])
        self.assertEqual(len(compact), len(original)-32)
        self.assertEqual(struct.unpack_from('<I',compact,36)[0],len(compact)-1024)
        self.assertEqual(struct.unpack_from('<I',compact,76)[0],len(compact))
        self.assertEqual(struct.unpack_from('<I',compact,offset)[0],4)
        self.assertEqual(struct.unpack_from('<I',compact,offset+28)[0],LE.STATIC_REL_VERSION)
        self.assertEqual(compact[offset+52:offset+64], bytes(12))
        entry=next(e for e in LE.REPORT if e.get('tag')=='REL')
        self.assertEqual(entry['size'],64)
        self.assertEqual(LE.REPORT[-1]['unused_ppc_bytes_removed'],32)

    def test_moves_sound_whole_and_rebases_report(self):
        out, offset = self.converted(); end=len(out)
        sound=bytes(range(256))*8
        struct.pack_into('<8I',out,64,4,len(sound),0,end,0,0,0,0)
        out+=sound
        LE.REPORT.append({'file':'em/wep02.drs','part':'1/1','handled':True,
                          'complete':True,'ofs':end+1024,'size':1024})
        compact=LE.compact_static_rel('em/wep02.drs',out,LE.REPORT,{4:'wep02'})
        moved=struct.unpack_from('<I',compact,76)[0]
        self.assertEqual(moved,end-32);self.assertEqual(compact[moved:],sound)
        self.assertEqual(LE.REPORT[-1]['ofs'],moved+1024)

    def test_unknown_or_incomplete_stays_reference(self):
        out,_=self.converted();original=bytes(out)
        self.assertEqual(LE.compact_static_rel('em/wep02.drs',out,LE.REPORT,{}),original)
        LE.REPORT[0]['complete']=False
        self.assertEqual(LE.compact_static_rel('em/wep02.drs',out,LE.REPORT,{4:'wep02'}),original)
        self.assertFalse(any(e.get('native_compacted') for e in LE.REPORT))

    def test_cli_switch_back_does_not_reuse_compacted_cache(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            src=pathlib.Path(tmp)/'src';dst=pathlib.Path(tmp)/'dst'
            (src/'em').mkdir(parents=True)
            raw,_=DrsBoundaryTest.fixture();(src/'em/wep02.drs').write_bytes(raw)
            cmd=[sys.executable,str(SCRIPT),str(src),str(dst)]
            subprocess.run(cmd,check=True,capture_output=True)
            reference=(dst/'em/wep02.drs').read_bytes()
            subprocess.run(cmd+['--compact-static-rel'],check=True,capture_output=True)
            self.assertLess((dst/'em/wep02.drs').stat().st_size,len(reference))
            subprocess.run(cmd,check=True,capture_output=True)
            self.assertEqual((dst/'em/wep02.drs').read_bytes(),reference)

    def test_standalone_retains_bss_rejects_bad_header(self):
        raw=bytearray(256);struct.pack_into('<I',raw,0,74)
        struct.pack_into('<2I',raw,28,3,128)
        report=[{'file':'rel/st1_0.rel','handled':True,'complete':True,'size':256}]
        compact=LE.compact_static_rel('rel/st1_0.rel',raw,report,{74:'st1_0'})
        self.assertEqual(len(compact),64)
        self.assertEqual(struct.unpack_from('<2I',compact,28),(LE.STATIC_REL_VERSION,128))
        with self.assertRaisesRegex(ValueError,'version 3'):
            LE.compact_static_rel('rel/st1_0.rel',compact,report,{74:'st1_0'})


class EventArchiveTest(unittest.TestCase):
    @staticmethod
    def fixture():
        packets = bytearray()
        for kind,length in ((0,16),(9,80),(15,32),(27,16)):
            packet = bytearray(length)
            struct.pack_into('>IIhhhh',packet,0,kind,0x80000000,-1,125,length,0)
            if kind == 9:
                packet[16:20]=b'cam\0'; packet[28:32]=b'oya\0'
                struct.pack_into('>7i',packet,40,-200,300,-400,90,-180,45,7)
            if kind == 15:struct.pack_into('>3i',packet,16,2,17,-1)
            packets += packet
        bo=80+len(packets);asset=bo+64
        head=bytearray(80);head[:16]=b'event/test.evd\0\0'
        head[32:37]=b'r100\0';head[40:44]=b's40\0';head[51]=18
        struct.pack_into('>I',head,52,0x80000000)
        # Explicit header writes (EvtHeader is exactly 80 bytes).
        head=head[:80];struct.pack_into('>4I',head,64,80,len(packets),1,bo)
        record=bytearray(64);record[:10]=b'model.tpl\0';struct.pack_into('>I',record,48,asset)
        return bytes(head+packets+record+make_tpl([(8,8,5,IMAGE[:128])])),bo,asset

    def test_packet_scalars_names_and_named_asset(self):
        raw,bo,asset=self.fixture();out=bytearray(raw);LE.REPORT.clear()
        LE.convert_file('evd/test.evd',out)
        self.assertTrue(all(e.get('complete') for e in LE.REPORT),LE.REPORT)
        self.assertEqual(out[:52],raw[:52])
        self.assertEqual(struct.unpack_from('<I',out,52)[0],0x80000000)
        self.assertEqual(struct.unpack_from('<IIhhhh',out,96),(9,0x80000000,-1,125,80,0))
        self.assertEqual(struct.unpack_from('<7i',out,136),(-200,300,-400,90,-180,45,7))
        self.assertEqual(struct.unpack_from('<3i',out,192),(2,17,-1))
        self.assertEqual(struct.unpack_from('<I',out,bo+48)[0],asset)
        self.assertEqual(struct.unpack_from('<I',out,asset)[0],0x0020af30)

    def test_unknown_packet_and_asset_overlap_reject(self):
        raw,bo,_=self.fixture()
        for offset,value in ((80,0x7f),(bo+48,80),(80+8,0)):
            out=bytearray(raw)
            if offset==88:struct.pack_into('>h',out,92,0) # zero packet stride
            else:struct.pack_into('>I',out,offset,value)
            original=bytes(out);LE.REPORT.clear();LE.convert_file('evd/test.evd',out)
            self.assertFalse(LE.REPORT[-1]['complete']);self.assertEqual(out,original)

    def test_missing_end_marker_rejects(self):
        raw,bo,_=self.fixture();out=bytearray(raw);struct.pack_into('>I',out,bo-16,0)
        LE.REPORT.clear();LE.convert_file('evd/test.evd',out)
        self.assertIn('lacks EndPac',LE.REPORT[-1]['error'])


class EventCurveVariantTest(unittest.TestCase):
    def test_empty_curve_preserves_frames_and_zero_fill(self):
        f=LE.motion_codec();raw=struct.pack('>HBBI',0x1234,0,0,32)+bytes(24)
        curve=f.parse(raw);self.assertEqual(f.serialise(curve),raw)
        native=f.serialise(curve,'<')
        self.assertEqual(struct.unpack_from('<HBBI',native),(0x1234,0,0,32))
        self.assertEqual(native[8:],raw[8:])

    def test_zero_size_and_aligned_keys_roundtrip(self):
        f=LE.motion_codec()
        joint=lambda:f.Joint(4,0,10,0,[f.Axis([0],[(1,2,3)]) for _ in range(3)])
        curve=f.Motion(4,[joint(),joint()],[0,1],zero_size=True,block_padding={1:bytes(3)})
        raw=f.serialise(curve);decoded=f.parse(raw)
        self.assertEqual(f.serialise(decoded),raw)
        native=f.serialise(decoded,'<');self.assertEqual(struct.unpack_from('<I',native,12)[0],0)
        second=struct.unpack_from('>I',raw,20)[0]
        self.assertEqual(native[second-3:second],bytes(3))
        broken=bytearray(raw);broken[second-1]=1
        with self.assertRaises(ValueError):f.parse(broken)


class RequireTest(unittest.TestCase):
    def test_required_parts_must_be_complete_or_safe_raw(self):
        report = [
            {"file": "a.dat", "sub": "a.dat#0", "tag": "EFF", "handled": True, "complete": True},
            {"file": "a.dat", "sub": "a.dat#1", "tag": "LIT", "handled": False},
            {"file": "b.dat", "part": "1/1", "type": 2, "format": "ARAM", "handled": True, "complete": True,
             "safe_raw": "sample bytes"},
            {"file": "c.dat", "sub": "c.dat#0", "tag": "EFF", "handled": True, "complete": False,
             "raw_parts": ["efm0 model body"]},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("a.dat#0\nb.dat:1/1\nc.dat\nmissing.dat\n# comment\n")
        problems = LE.check_required(report, f.name)
        self.assertEqual(problems, ["c.dat#0: incomplete, raw parts: efm0 model body", "missing.dat: not in the tree"])
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("a.dat\n")
        self.assertEqual(LE.check_required(report, f.name), ["a.dat#1: no handler (tag LIT)"])


class RoomInfoTest(unittest.TestCase):
    def test_room_info_table(self):
        # two stages, the second without a table; one record with strings
        rec = struct.pack(">HH3ffIII", 1, 0x0120, 1.0, 2.0, 3.0, 0.5, 0x40, 0x48, 0x50)
        tbl = be32(2, 12, 0) + be32(1) + rec
        tbl += bytes(0x40 - len(tbl)) + b"r120\0\0\0\0" + b"scr\0\0\0\0\0" + b"soft\0\0\0\0"
        data = bytearray(tbl)
        sw = LE.Swapper(data, "roominfo")
        entry = {}
        LE.guarded(sw, LE.fmt_roominfo, 0, len(data), "roominfo", entry)
        self.assertTrue(entry["complete"], entry)
        self.assertEqual(struct.unpack_from("<3I", data, 0), (2, 12, 0))
        self.assertEqual(struct.unpack_from("<I", data, 12), (1,))
        self.assertEqual(data[12], 1)   # getIndexNum's low byte on the little-endian target
        self.assertEqual(struct.unpack_from("<HH3ffIII", data, 16), (1, 0x0120, 1.0, 2.0, 3.0, 0.5, 0x40, 0x48, 0x50))
        self.assertEqual(data[16 + 2], 0x20)   # CRoomInfo.room, first byte of the swapped u16
        self.assertEqual(bytes(data[0x40:0x44]), b"r120")


if __name__ == "__main__":
    unittest.main()
