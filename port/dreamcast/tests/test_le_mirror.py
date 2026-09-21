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
    out = be32(n, 0, 0, 0) + be32(*offs) + b"".join(t.encode() + b"\0" for t, _ in parts)
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
