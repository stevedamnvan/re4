#!/usr/bin/env python3
"""Build a little-endian mirror of the GameCube data tree for the Dreamcast
game target.

    le_mirror.py <src-tree> <dst-tree> [--force]

The recovered game code overlays its structures straight onto the files it
reads (include/dvd.h DvdHeader, include/snd.h, include/snd_drv.h, the
tagged archives of include/global.h, mes.cpp, include/tpl.h, include/id_sys.h
...).  On the SH-4 those structures are little-endian, so every scalar the
game reads from a file has to be byte-swapped once, offline, with the layout
left untouched.  Each format gets a handler that walks the layout the game
headers describe; bytes no handler covers are copied as they are and listed
in <dst-tree>/le_mirror_report.json, which is how the boot log's next
failure is mapped to the next format to cover.

Two archive shapes carry almost everything:

* the DVD container (dvd.cpp): 32 bytes of magic, then 32-byte DvdHeader
  entries (type, size, dest, ofs, sndType, sndArg, sndNo) up to 0xFFFFFFFF,
  one nesting level (type 4);
* the tagged archive (read.cpp GetDataExt, global.h ArcFile, title.h
  TitleArc, card.h CardArc): u32 count, 12 bytes, u32 offsets[count],
  char tags[count][4]; the tag names the sub-file's format (TPL, MDT, UWF,
  EFF, LIT, SAT, ...).

The tree and the mirror are private game data; only this tool is committed.
"""
import fnmatch
import json
import os
import struct
import sys

CONTAINER_MAGIC = b"\xca\xb6\xbe\x20" * 8
HEADER_TABLE = 0x400
ENTRY_SIZE = 0x20
END_OF_TABLE = 0xFFFFFFFF
SKIP_ENTRY = 0xFFFFFFFE
NESTED = 4


class Swapper:
    """In-place byte swapper over a bytearray with double-swap protection."""

    def __init__(self, data, label):
        self.data = data
        self.label = label
        self.done = bytearray(len(data))

    def _mark(self, off, size):
        if off < 0 or off + size > len(self.data):
            raise ValueError("%s: field at %#x/%d outside %#x bytes" % (self.label, off, size, len(self.data)))
        if any(self.done[off:off + size]):
            raise ValueError("%s: byte %#x swapped twice" % (self.label, off))
        for o in range(off, off + size):
            self.done[o] = 1

    def peek32(self, off):
        return struct.unpack_from(">I", self.data, off)[0]

    def peek16(self, off):
        return struct.unpack_from(">H", self.data, off)[0]

    def swapped(self, off):
        return bool(self.done[off])

    def u32(self, off):
        """Swap the u32 at off; returns its (big-endian, original) value."""
        self._mark(off, 4)
        v = struct.unpack_from(">I", self.data, off)[0]
        struct.pack_into("<I", self.data, off, v)
        return v

    def u16(self, off):
        self._mark(off, 2)
        v = struct.unpack_from(">H", self.data, off)[0]
        struct.pack_into("<H", self.data, off, v)
        return v

    def u32s(self, off, count):
        return [self.u32(off + 4 * i) for i in range(count)]

    def u16s(self, off, count):
        return [self.u16(off + 2 * i) for i in range(count)]

    f32 = u32

    def f32s(self, off, count):
        return self.u32s(off, count)


# ----------------------------------------------------------------- formats

def fmt_u32_array(sw, off, size, ctx):
    """A plain u32 table (bgm/bio4midi.hed: SndMem.bgm_file[no] file offsets)."""
    sw.u32s(off, size // 4)


def fmt_bio4str_hed(sw, off, size, ctx):
    """bgm/bio4str.hed: two stream blocks (snd.cpp SndInit, snd_sub3.cpp
    Snd_str_blk_init): u32 block_ofs[2]; block = {u32 num, shd_tbl_ofs,
    rit_ofs}; rit = SND_RIT[num]; shd table = u32 offsets (relative to the
    table) to SND_SHD records (include/snd_drv.h)."""
    blocks = sw.u32s(off, 2)
    for b in blocks:
        base = off + b
        num, shd_tbl, rit = sw.u32s(base, 3)
        max_shd = -1
        for i in range(num):
            r = base + rit + 0x10 * i
            shd_no = sw.u16(r)
            if shd_no != 0xFFFF:
                max_shd = max(max_shd, shd_no)
            sw.u16(r + 0x0C)
        tbl = base + shd_tbl
        seen = set()
        for i in range(max_shd + 1):
            o = sw.u32(tbl + 4 * i)
            if o in seen:
                continue
            seen.add(o)
            shd = tbl + o
            sw.u32s(shd, 8)             # flag .. offset
            sw.u16s(shd + 0x20, 0x2E)   # coef[16], coefR[16], gain, ps, yn1, yn2, lps, lyn1, lyn2


def fmt_doorse_hed(sw, off, size, ctx):
    """bgm/doorse.hed: SndDoorTbl {u32 file_ofs, num_ofs}; u16 count at
    num_ofs; u32 file offsets[count] at file_ofs (snd.cpp 1735/1753)."""
    file_ofs, num_ofs = sw.u32s(off, 2)
    count = sw.u16(off + num_ofs)
    sw.u32s(off + file_ofs, count)


def fmt_bgmtbl_dat(sw, off, size, ctx):
    """bgm/bgmtbl.dat: SndBgmTbl {u32 room_ofs, list_ofs}; u16 room id list
    (0xFFFF terminated) at list_ofs; u32 offsets[n] at room_ofs (relative to
    that array) to SndBgmRoom {u32 num; SndBgmEnt e[num]} (13 u32 each)."""
    room_ofs, list_ofs = sw.u32s(off, 2)
    n = 0
    while True:
        v = sw.u16(off + list_ofs + 2 * n)
        n += 1
        if v == 0xFFFF:
            break
    n -= 1
    offs = sw.u32s(off + room_ofs, n)
    seen = set()
    for o in offs:
        if o in seen:
            continue
        seen.add(o)
        room = off + room_ofs + o
        num = sw.u32(room)
        sw.u32s(room + 4, 13 * num)


def fmt_mdt(sw, off, size, ctx):
    """Message table (mes.cpp MessageData::getAddr): u32 languages, u32
    block_ofs[languages]; block = MesTblBlock {u32 x0, u32 count, u32
    ofs[count]} followed by the u16 code streams of its messages."""
    nlang = sw.u32(off)
    if nlang == 0 or nlang > 16:
        raise ValueError("%s: MDT with %d languages" % (sw.label, nlang))
    block_ofs = sw.u32s(off + 4, nlang)
    bounds = sorted(set(block_ofs)) + [size]
    for b in sorted(set(block_ofs)):
        end = bounds[bounds.index(b) + 1]
        blk = off + b
        sw.u32(blk)
        count = sw.u32(blk + 4)
        offs = sw.u32s(blk + 8, count)
        if count == 0:
            continue
        first = min(offs)
        # message streams: u16 codes from the first message to the block end
        n16 = ((end - b) - first) // 2
        sw.u16s(blk + first, n16)


def fmt_tpl(sw, off, size, ctx):
    """TPL texture palette (include/tpl.h): TEXPalette {u32 version, u32
    num, u32 desc_ofs}; TEXDescriptor[num] {u32 tex_ofs, u32 clut_ofs};
    TEXHeader {u16 h, u16 w, u32 fmt, u32 data, u32 wrapS, wrapT, minF,
    magF, f32 lod, 4 bytes}; CLUTHeader {u16 n, 2 bytes, u32 fmt, u32 data}.
    Image and palette data stay in their GameCube layout (the renderer
    converts them)."""
    sw.u32(off)
    num = sw.u32(off + 4)
    desc = sw.u32(off + 8)
    seen_tex = set()
    seen_clut = set()
    for i in range(num):
        d = off + desc + 8 * i
        tex, clut = sw.u32s(d, 2)
        if tex and tex not in seen_tex:
            seen_tex.add(tex)
            h = off + tex
            sw.u16s(h, 2)
            sw.u32s(h + 4, 7)
        if clut and clut not in seen_clut:
            seen_clut.add(clut)
            c = off + clut
            sw.u16(c)
            sw.u32s(c + 4, 2)


def fmt_uwf(sw, off, size, ctx):
    """Id data table (include/id_sys.h, id_sys.cpp IDSystem::set):
    IdDataHeader {char version[5] "1.00"/"2.00", u8 num, 2 bytes}; entries
    from 0x08 (0x88 bytes for version 1, 0x8C for version 2): bytes, Vec pos
    at 0x14, Vec vtx[4] at 0x20, f32 sizeX/sizeY at 0x50, colour bytes, Vec
    rot, bytes, u32 ofs[6] (path0, path1, curve[4]; offsets from the table
    start). path0 = FuncPathData {s8 k, 6 bytes, s8 n, Vec pos[n]}, path1 =
    FuncPathWork {int k, int n, Vec alpha[n]}, curves = Hermite1 {s32 num,
    HermiteKey {f32 t, v, out, in}[num]}."""
    version = bytes(sw.data[off:off + 4])
    num = sw.data[off + 5]
    if version == b"1.00":
        stride, rot, ofs = 0x88, 0x5C, 0x70
    elif version == b"2.00":
        stride, rot, ofs = 0x8C, 0x60, 0x74
    else:
        raise ValueError("%s: UWF version %r" % (sw.label, version))
    seen = set()
    for i in range(num):
        e = off + 8 + stride * i
        sw.f32s(e + 0x14, 3 + 12 + 2)   # pos, vtx[4], sizeX, sizeY
        sw.f32s(e + rot, 3)
        refs = sw.u32s(e + ofs, 6)
        for k, r in enumerate(refs):
            if r == 0 or (k, r) in seen:
                continue
            seen.add((k, r))
            p = off + r
            if k == 0:
                n = sw.data[p + 7]
                sw.f32s(p + 8, 3 * n)
            elif k == 1:
                if sw.swapped(p):
                    continue
                n = sw.peek32(p + 4)
                if n > 256:
                    continue
                sw.u32s(p, 2)
                sw.f32s(p + 8, 3 * n)
            else:
                n = sw.u32(p)
                sw.f32s(p + 4, 4 * n)


def fmt_fnt(sw, off, size, ctx):
    """Font file (mes.cpp setupFont): MesFontFile {u32 tplOfs, u32 widthOfs,
    ...}; a TPL at tplOfs, glyph width bytes at widthOfs."""
    tpl_ofs, width_ofs = sw.u32s(off, 2)
    fmt_tpl(sw, off + tpl_ofs, size - tpl_ofs, ctx)


def fmt_snd_mram(sw, off, size, ctx, bgm=False):
    """Sound (ISS) block, the MRAM half of a container sound part
    (snd.cpp SndBlkInit, snd_sub3.cpp Snd_iss_blk_init, include/snd_drv.h,
    include/dolphin/syn.h): u32 block_ofs, u32 x4 (BGM blocks start at the
    header directly); header {u32 num, dls_ofs, sit_ofs, seq_ofs}; SIT[num]
    (0x18: u16 prog, bytes, u16 pitch_l/pitch_hi at 0x0A/0x0C, u16 flag at
    0x16); wavetable SND_WT_HDR {6 u32} then WTINST u16 note table, WTREGION
    (0x18), WTART (0x50), WTSAMPLE (0x10), WTADPCM (0x2E) sections in offset
    order; sequence table {u32 count, u32 ofs[count]} with raw MIDI bodies."""
    if bgm:
        hdr = off
    else:
        block_ofs = sw.u32(off)
        sw.u32(off + 4)
        hdr = off + block_ofs
    num, dls, sit, seq = sw.u32s(hdr, 4)
    end = off + size
    starts = sorted(x for x in (dls, sit, seq) if x)
    def section_end(o):
        later = [x for x in starts if x > o]
        return hdr + later[0] if later else end
    for i in range(num):
        r = hdr + sit + 0x18 * i
        sw.u16(r)
        sw.u16(r + 0x0A)
        sw.u16(r + 0x0C)
        sw.u16(r + 0x16)
    if dls:
        wt = hdr + dls
        wt_end = section_end(dls)
        x0, inst, rgn, art, smp, adpcm = sw.u32s(wt, 6)
        secs = sorted(x for x in (inst, rgn, art, smp, adpcm) if x)
        def wt_sec_end(o):
            later = [x for x in secs if x > o]
            return wt + later[0] if later else wt_end
        if inst:
            sw.u16s(wt + inst, (wt_sec_end(inst) - (wt + inst)) // 2)
        for k in range((wt_sec_end(rgn) - (wt + rgn)) // 0x18 if rgn else 0):
            r = wt + rgn + 0x18 * k
            sw.u16(r + 2)
            sw.u32s(r + 4, 5)
        if art:
            sw.u32s(wt + art, (wt_sec_end(art) - (wt + art)) // 4)
        for k in range((wt_sec_end(smp) - (wt + smp)) // 0x10 if smp else 0):
            r = wt + smp + 0x10 * k
            sw.u16s(r, 2)
            sw.u32s(r + 4, 2)
            sw.u16(r + 0x0C)
        for k in range((wt_sec_end(adpcm) - (wt + adpcm)) // 0x2E if adpcm else 0):
            sw.u16s(wt + adpcm + 0x2E * k, 23)
    if seq:
        t = hdr + seq
        count = sw.u32(t)
        sw.u32s(t + 4, count)


TAG_FORMATS = {
    b"MDT\0": fmt_mdt,
    b"TPL\0": fmt_tpl,
    b"UWF\0": fmt_uwf,
}


def looks_like_tagged(data, off, size):
    if size < 0x18:
        return False
    n = struct.unpack_from(">I", data, off)[0]
    if n == 0 or n > 0x100 or 0x10 + 8 * n > size:
        return False
    if any(struct.unpack_from(">3I", data, off + 4)):
        return False
    offs = struct.unpack_from(">%dI" % n, data, off + 0x10)
    if offs[0] < 0x10 + 8 * n or any(b > size for b in offs):
        return False
    if any(offs[i] > offs[i + 1] for i in range(n - 1)):
        return False
    tags = data[off + 0x10 + 4 * n: off + 0x10 + 8 * n]
    for i in range(n):
        t = tags[4 * i:4 * i + 4]
        if not (t[:3].isalpha() and t[:3].isupper() and t[3] == 0):
            return False
    return True


def fmt_tagged(sw, off, size, ctx):
    """Tagged archive: u32 count, 12 bytes, u32 ofs[count], char tag[count][4];
    every sub-file is dispatched on its tag."""
    n = sw.u32(off)
    offs = sw.u32s(off + 0x10, n)
    tags = [bytes(sw.data[off + 0x10 + 4 * n + 4 * i: off + 0x10 + 4 * n + 4 * i + 4]) for i in range(n)]
    order = sorted(range(n), key=lambda i: offs[i])
    for rank, i in enumerate(order):
        start = offs[i]
        end = offs[order[rank + 1]] if rank + 1 < n else size
        if end <= start:
            continue
        sub_ctx = "%s#%d" % (ctx, i)
        handler = TAG_FORMATS.get(tags[i])
        entry = {"file": sw.label, "sub": sub_ctx, "tag": tags[i][:3].decode("ascii", "replace"),
                 "ofs": off + start, "size": end - start, "handled": handler is not None}
        if handler:
            if not sw.swapped(off + start):
                guarded(sw, handler, off + start, end - start, sub_ctx, entry)
        elif looks_like_tagged(sw.data, off + start, end - start):
            entry["tag"] = "ARC"
            entry["handled"] = True
            fmt_tagged(sw, off + start, end - start, sub_ctx)
        REPORT.append(entry)


def guarded(sw, handler, off, size, ctx, entry):
    """Runs a handler; on a layout error the region is restored raw and the
    error recorded, so one unexpected file never aborts the mirror."""
    backup = bytes(sw.data[off:off + size])
    marks = bytes(sw.done[off:off + size])
    try:
        handler(sw, off, size, ctx)
    except (ValueError, IndexError, struct.error) as e:
        sw.data[off:off + size] = backup
        sw.done[off:off + size] = marks
        entry["handled"] = False
        entry["error"] = str(e)


FILE_FORMATS = [
    ("bgm/bio4str.hed", fmt_bio4str_hed),
    ("bgm/bio4midi.hed", fmt_u32_array),
    ("bgm/doorse.hed", fmt_doorse_hed),
    ("bgm/bgmtbl.dat", fmt_bgmtbl_dat),
    ("font/*.fnt", fmt_fnt),
    ("*.tpl", fmt_tpl),
]

REPORT = []


def find_handler(table, key):
    for pattern, handler in table:
        if fnmatch.fnmatchcase(key, pattern):
            return handler
    return None


def convert_part(sw, rel, key, part_off, size, entry):
    if entry["type"] == 1:  # sound block, MRAM half (type 2 is the ARAM sample data)
        entry["format"] = "SND"
        entry["handled"] = True
        guarded(sw, lambda sw_, o, n, c: fmt_snd_mram(sw_, o, n, c, bgm=entry["snd"][0] == 3),
                part_off, size, "%s:%s" % (rel, key), entry)
    elif looks_like_tagged(sw.data, part_off, size):
        entry["format"] = "ARC"
        entry["handled"] = True
        fmt_tagged(sw, part_off, size, "%s:%s" % (rel, key))


def convert_container(sw, rel):
    data = sw.data

    def walk(base, key_prefix, depth):
        off = base + ENTRY_SIZE  # entry 0 is the magic block
        i = 0
        while off + ENTRY_SIZE <= base + HEADER_TABLE:
            t, size, dest, ofs, snd_type, snd_arg, snd_no, x1c = sw.u32s(off, 8)
            key = "%s%d" % (key_prefix, i)
            if t == END_OF_TABLE:
                break
            if t == SKIP_ENTRY:
                pass
            elif t == NESTED:
                if depth == 0:
                    walk(ofs, key + "/", 1)
                else:
                    REPORT.append({"file": rel, "part": key, "note": "nested table below the game's nest limit"})
            else:
                part_off = base + ofs
                if part_off + size > len(data):
                    raise ValueError("%s part %s outside the file" % (rel, key))
                entry = {"file": rel, "part": key, "type": t, "ofs": part_off, "size": size,
                         "snd": [snd_type, snd_arg, snd_no], "handled": False}
                convert_part(sw, rel, key, part_off, size, entry)
                REPORT.append(entry)
            off += ENTRY_SIZE
            i += 1

    walk(0, "", 0)


def convert_file(rel, data):
    sw = Swapper(data, rel)
    handler = find_handler(FILE_FORMATS, rel)
    if handler:
        entry = {"file": rel, "handled": True, "size": len(data)}
        guarded(sw, handler, 0, len(data), rel, entry)
        REPORT.append(entry)
    elif data[:32] == CONTAINER_MAGIC:
        convert_container(sw, rel)
    elif looks_like_tagged(data, 0, len(data)):
        fmt_tagged(sw, 0, len(data), rel)
        REPORT.append({"file": rel, "handled": True, "size": len(data), "format": "ARC"})
    else:
        REPORT.append({"file": rel, "handled": False, "size": len(data)})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if len(args) != 2:
        sys.exit(__doc__)
    src, dst = args
    tool_mtime = os.path.getmtime(os.path.abspath(__file__))
    report_path = os.path.join(dst, "le_mirror_report.json")
    previous = {}
    if os.path.exists(report_path):
        for e in json.load(open(report_path)):
            previous.setdefault(e["file"], []).append(e)
    converted = skipped = 0
    for root, dirs, files in sorted(os.walk(src)):
        for name in sorted(files):
            sp = os.path.join(root, name)
            rel = os.path.relpath(sp, src).replace(os.sep, "/").lower()
            dp = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            if not force and os.path.exists(dp) and rel in previous:
                dm = os.path.getmtime(dp)
                if dm >= os.path.getmtime(sp) and dm >= tool_mtime:
                    REPORT.extend(previous[rel])
                    skipped += 1
                    continue
            data = bytearray(open(sp, "rb").read())
            convert_file(rel, data)
            with open(dp, "wb") as f:
                f.write(data)
            converted += 1
    with open(report_path, "w") as f:
        json.dump(REPORT, f, indent=1)
    subs = [e for e in REPORT if "sub" in e]
    raw_tags = {}
    for e in subs:
        if not e.get("handled"):
            raw_tags[e["tag"]] = raw_tags.get(e["tag"], 0) + 1
    print("le_mirror: %d converted, %d up to date; %d whole files handled, %d raw files; "
          "%d tagged sub-files (%d handled); raw by tag: %s"
          % (converted, skipped, sum(1 for e in REPORT if e.get("handled") and "part" not in e and "sub" not in e),
             sum(1 for e in REPORT if "part" not in e and "sub" not in e and not e.get("handled")),
             len(subs), sum(1 for e in subs if e.get("handled")),
             " ".join("%s=%d" % kv for kv in sorted(raw_tags.items()))))


if __name__ == "__main__":
    main()
