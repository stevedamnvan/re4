#!/usr/bin/env python3
"""Build a little-endian mirror of the GameCube data tree for the Dreamcast
game target.

--decode-rooms also writes decoded, converted st*/r*.arc sidecars using the
recovered offline decoder. They remain unqualified until --require coverage
passes for each sidecar; the current runtime does not yet load these files.

    le_mirror.py <src-tree> <dst-tree> [--force] [--require <deps.txt>]

--require names a file listing the disc paths a boot fixture actually reads
(one per line, # comments); the run fails (exit 2) unless every part of every
listed file was converted completely or carries an explicit safe-raw contract
(ARAM sample bytes, text). Formats the fixture does not touch may stay raw.

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
    """In-place byte swapper over a bytearray with double-swap protection and
    a bounds stack: every handler runs inside `bounded(off, size)` and can
    neither read nor swap a byte outside that region, so a corrupt or
    unexpected offset in one sub-file is an error for that sub-file only and
    never reaches a neighbour."""

    def __init__(self, data, label):
        self.data = data
        self.label = label
        self.done = bytearray(len(data))
        self.lo = 0
        self.hi = len(data)
        self._stack = []

    class _Bound:
        def __init__(self, sw, lo, hi):
            self.sw, self.lo, self.hi = sw, lo, hi

        def __enter__(self):
            sw = self.sw
            sw._stack.append((sw.lo, sw.hi))
            sw.lo, sw.hi = self.lo, self.hi
            return sw

        def __exit__(self, *exc):
            self.sw.lo, self.sw.hi = self.sw._stack.pop()
            return False

    def bounded(self, off, size):
        """Context manager narrowing the accessible region to [off, off+size),
        which must lie inside the current region."""
        if size < 0 or off < self.lo or off + size > self.hi:
            raise ValueError("%s: region %#x/%d outside the current region %#x..%#x" %
                             (self.label, off, size, self.lo, self.hi))
        return Swapper._Bound(self, off, off + size)

    def _check(self, off, size):
        if off < self.lo or off + size > self.hi:
            raise ValueError("%s: field at %#x/%d outside the region %#x..%#x" %
                             (self.label, off, size, self.lo, self.hi))

    def _mark(self, off, size):
        self._check(off, size)
        if any(self.done[off:off + size]):
            raise ValueError("%s: byte %#x swapped twice" % (self.label, off))
        for o in range(off, off + size):
            self.done[o] = 1

    def peek32(self, off):
        self._check(off, 4)
        return struct.unpack_from(">I", self.data, off)[0]

    def peek16(self, off):
        self._check(off, 2)
        return struct.unpack_from(">H", self.data, off)[0]

    def swapped(self, off):
        self._check(off, 1)
        return bool(self.done[off])

    def val32(self, off):
        """The original (big-endian) value of a u32 whether or not it has been swapped."""
        self._check(off, 4)
        return struct.unpack_from("<I" if self.done[off] else ">I", self.data, off)[0]

    def val16(self, off):
        self._check(off, 2)
        return struct.unpack_from("<H" if self.done[off] else ">H", self.data, off)[0]

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



def fmt_eff(sw, off, size, ctx):
    """Effect data file, version 0xB (src/game/eff_sys.cpp EffData; the ID
    layout system reads the same block through src/game/id_tex.cpp
    IdTexDataLoad): twelve u32 offsets from the block start, then
      - the texture id table (TexIdTbl: u32 num, {u16 id, u16 x2, u32 x4}[num]),
      - the TPL offset table (TexOfsTbl: u32 num, u32 ofs[num] relative to the
        table) whose targets are TPL palettes (fmt_tpl; a target shared by
        several entries is converted once),
      - the animation offset table (same shape) whose targets are EspAnmData
        records (u16 Width, Height, s16 Cx, Cy, u16 Frames at +8, bytes at
        +0xA..+0xF, then the byte pattern / frame-time tables, untouched),
      - the effect model id table and the model offset table (EffEfmEnt: five
        u32 from the entry, model / TPL / motion bodies relative to it) whose
        TPL is converted and whose model and motion bodies stay raw (recorded),
      - the est / sst / path lists and data blocks, raw when present (recorded).
    Image and palette data keep their GameCube encoding (fmt_tpl contract)."""
    hdr = sw.u32s(off, 12)
    (version, ofs_tex_id, ofs_est_list, ofs_sst_list, ofs_path_list, ofs_efm_id,
     ofs_tpl, ofs_anm, ofs_est_data, ofs_sst_data, ofs_path_data, ofs_efm) = hdr
    if version != 0xB:
        raise ValueError("%s: EFF version %#x, expected 0xB" % (ctx, version))
    raw = []

    def id_table(o):
        n = sw.u32(o)
        ids = []
        for i in range(n):
            e = o + 4 + 8 * i
            ids.append(sw.u16(e))
            sw.u16(e + 2)
            sw.u32(e + 4)
        return ids

    def ofs_table(o):
        n = sw.u32(o)
        return [o + v for v in sw.u32s(o + 4, n)]

    tex_ids = id_table(off + ofs_tex_id)
    # The game forms the table pointers unconditionally but dereferences them
    # only inside the per-id loops; a file without textures carries offset 0
    # (which would alias the header) and is left alone the same way.
    if tex_ids:
        if not (ofs_tpl and ofs_anm):
            raise ValueError("%s: %d texture ids but no TPL / animation table" % (ctx, len(tex_ids)))
        tpls = ofs_table(off + ofs_tpl)
        anms = ofs_table(off + ofs_anm)
    else:
        tpls = anms = []
    if not (len(tex_ids) == len(tpls) == len(anms)):
        raise ValueError("%s: texture tables disagree (%d ids, %d TPLs, %d animations)" %
                         (ctx, len(tex_ids), len(tpls), len(anms)))
    seen_tpl = set()
    for i, t in enumerate(tpls):
        if t in seen_tpl:
            continue  # shared reference: one conversion, both entries resolve to it
        seen_tpl.add(t)
        fmt_tpl(sw, t, off + size - t, ctx + "/tpl%d" % i)
    seen_anm = set()
    for i, a in enumerate(anms):
        if a in seen_anm:
            continue
        seen_anm.add(a)
        width, height, cx, cy, frames = sw.u16s(a, 5)
        if frames == 0:
            raise ValueError("%s: animation %d has no frames" % (ctx, i))
        n_desc = sw.val32(tpls[i] + 4)
        if n_desc != frames:
            raise ValueError("%s: animation %d frames %d != TPL images %d" % (ctx, i, frames, n_desc))
    efm_ids = id_table(off + ofs_efm_id) if ofs_efm_id else []
    if efm_ids:
        if not ofs_efm:
            raise ValueError("%s: %d effect model ids but no model table" % (ctx, len(efm_ids)))
        efms = ofs_table(off + ofs_efm)
        if len(efm_ids) != len(efms):
            raise ValueError("%s: effect model tables disagree" % ctx)
        for i, e in enumerate(efms):
            x0, o_model, o_tpl, o_mot, o_x = sw.u32s(e, 5)
            fmt_tpl(sw, e + o_tpl, off + size - (e + o_tpl), ctx + "/efm%d" % i)
            raw.append("efm%d model body" % i)
            if o_mot:
                raw.append("efm%d motion body" % i)
            if o_x:
                raw.append("efm%d extra body" % i)
    for name, o_list, o_data in (("est", ofs_est_list, ofs_est_data), ("sst", ofs_sst_list, ofs_sst_data),
                                 ("path", ofs_path_list, ofs_path_data)):
        if o_list and sw.peek32(off + o_list):
            raw.append("%s list and data" % name)
    return raw



def fmt_roominfo(sw, off, size, ctx):
    """debug/roomInfo.dat (src/game/room_jmp.cpp cRoomJmp, include/room_jmp.h
    CRoomInfo): u32 stage count, u32 ofs[count] from the table start (0 = no
    table), and per stage u32 record count followed by 0x20-byte records
    {u16 flag, u16 roomNo (stage << 8 | room), Vec pos, f32 angle, u32 name,
    scr, soft string offsets from the table start}. The strings stay raw.
    getIndexNum reads the record count's low byte and the record's `room`
    byte through a union; the Dreamcast build of those accessors follows the
    swapped layout (room_jmp.cpp / room_jmp.h)."""
    count = sw.u32(off)
    offs = sw.u32s(off + 4, count)
    for stage, o in enumerate(offs):
        if o == 0:
            continue
        base = off + o
        n = sw.u32(base)
        for i in range(n):
            r = base + 4 + 0x20 * i
            sw.u16s(r, 2)
            sw.f32s(r + 4, 4)
            sw.u32s(r + 0x14, 3)



def fmt_rel(sw, off, size, ctx):
    """REL module header (include/main_sub.h OSModuleHeader, the SDK
    OSModuleInfo + OSModuleHeader v3): sixteen u32 words (id, link, section
    count / table offset, name offset / size, version, bss size, relocation
    / import offsets, prolog / epilog / unresolved section and offsets ...).
    The code and relocation bodies are PowerPC and stay raw: on the Dreamcast
    the module is compiled into the image and OSLink binds the header's entry
    points to it (platform/modules.cpp)."""
    sw.u32s(off, 16)
    return ["PowerPC code, data and relocations (static module in the image)"]


def fmt_cns(sw, off, size, ctx):
    """cons.cpp ConsRoom: count, (count >> 5)+1 bitmap words, values."""
    count = sw.u32(off)
    words = (count >> 5) + 1
    sw._check(off + 4, 4 * (words + count))
    sw.u32s(off + 4, words + count)


def fmt_sat(sw, off, size, ctx):
    """atari.h/cSat::operator=: retain native source layout and block graph.

    SAT and EAT share this format but remain separate source resources/managers.
    Attribute words use the native AtPoly half-word view in include/at_sub.h.
    No coordinate scaling, welding, reordering or hierarchy rebuilding occurs.
    """
    sw._check(off, 4)
    version = sw.data[off]
    if version != 0xFF and version & 0x80:
        # The shipped archive's byte 1 counts offset entries (same format used
        # by convert_sat.py); the runtime indexes them with the source type.
        count = sw.data[off + 1]
        if count == 0:
            raise ValueError('empty multi-SAT header')
        offsets = sw.u32s(off + 4, count)
        if any(x < 4 + 4 * count or x + 20 > size for x in offsets):
            raise ValueError('SAT section offset outside archive')
        unique = sorted(set(offsets))
        for i, start in enumerate(unique):
            end = unique[i + 1] if i + 1 < len(unique) else size
            with sw.bounded(off + start, end - start):
                _fmt_sat_file(sw, off + start, end - start)
    else:
        _fmt_sat_file(sw, off, size)


def _fmt_sat_file(sw, off, size):
    nv, nn, ne, unused, np, nf, ns, nw, nb = sw.u16s(off + 2, 9)
    if np > 0x1FFF or nf + ns + nw != np:
        raise ValueError('invalid SAT polygon counts')
    vectors = off + 20
    sw._check(vectors, (nv + nn + ne) * 12 + np * 20)
    sw.f32s(vectors, (nv + nn + ne) * 3)
    polygons = vectors + (nv + nn + ne) * 12
    for i in range(np):
        p = polygons + i * 20
        indices = sw.u16s(p, 7)
        if any(x >= nv for x in indices[:3]) or indices[3] >= nn or any(x >= ne for x in indices[4:]):
            raise ValueError('SAT polygon index outside source table')
        sw.u32(p + 16)
    first = polygons + np * 20
    todo = [first] if nb else []
    visited = set()
    while todo:
        p = todo.pop()
        if p in visited:
            raise ValueError('shared or cyclic SAT block')
        if len(visited) >= nb or p < first:
            raise ValueError('SAT block count or offset invalid')
        sw._check(p, 36)
        visited.add(p)
        sw.f32s(p, 6)
        floor, slope, wall, flags = sw.u16s(p + 24, 4)
        following = sw.u32(p + 32)
        count = floor + slope + wall
        if flags & 1:
            if count:
                raise ValueError('SAT parent contains polygon indices')
            todo.append(p + 36)
        else:
            indices = sw.u16s(p + 36, count)
            if any(x >= np for x in indices):
                raise ValueError('SAT leaf polygon outside source table')
        if following:
            if following < 36 or following & 3:
                raise ValueError('invalid SAT next relative offset')
            todo.append(p + following)
    if len(visited) != nb:
        raise ValueError('SAT block count does not match graph')

def fmt_smd(sw, off, size, ctx):
    """scroll.h cSmd/SmdWork: source instances and table-relative resources.

    Model and motion payloads remain explicit coverage debt; textures use the
    existing TPL handler. Do not report the full SMD as ready from metadata alone.
    """
    sw._check(off, 16)
    flag = sw.data[off + 1]
    count = sw.u16(off + 2)
    tables = sw.u32s(off + 4, 3)
    work = off + 16
    total = count
    if flag & 1:
        groups = sw.u32(work)
        sizes = sw.u32s(work + 4, groups)
        # Group counts reserve runtime slots for separately loaded blocks;
        # this file still contains exactly nModel placement records.
        work += 4 + 4 * groups
    sw._check(work, total * 72)
    local_ids = [set(), set(), set()]
    for i in range(total):
        p = work + i * 72
        sw.f32s(p, 9)
        flags = sw.u32(p + 68)
        ids = sw.data[p + 36:p + 39]
        # Retain every placement, including unused records. Resource references
        # with common-model flags resolve from the other SMD at runtime.
        for j, common in enumerate((0x10, 0x10, 0x40)):
            if not flags & common and ids[j] != 0xFF:
                local_ids[j].add(ids[j])
    raw = []
    for kind, table, ids in zip(('BIN', 'TPL', 'FCV'), tables, local_ids):
        if not ids:
            continue
        if not 16 <= table < size:
            raise ValueError('SMD referenced table outside file')
        # Count comes from source references, not padding before the first body.
        n = max(ids) + 1
        base = off + table
        offsets = sw.u32s(base, n)
        for ident in sorted(ids):
            relative = offsets[ident]
            target = base + relative
            if relative < 4 * n or target >= off + size:
                raise ValueError('SMD resource offset outside file')
            if kind == 'TPL':
                if not sw.swapped(target):
                    fmt_tpl(sw, target, off + size - target, ctx + '/tpl%d' % ident)
            else:
                raw.append('%s%d payload' % (kind, ident))
    return raw


def fmt_smx(sw, off, size, ctx):
    """scroll.h SmxWork plus obj02.cpp's rotate/swing work layouts."""
    sw._check(off, 16)
    count = sw.data[off + 1]
    sw._check(off + 16, count * 144)
    raw = []
    for i in range(count):
        p = off + 16 + i * 144
        kind = sw.data[p + 1]
        sw.u32s(p + 4, 3)  # selection mask, flags, packed numeric RGBA
        sw.u32(p + 132)    # packed numeric color2
        sw.f32s(p + 136, 2)
        work = p + 16
        if kind == 1:
            sw.f32s(work, 3)  # rotation speed; byte flag at +12 stays byte
            if any(sw.data[work + 13:work + 116]):
                raw.append('SMX%d extra rotate work' % i)
        elif kind == 2:
            sw.f32s(work, 13)  # phase/amplitude/frequency/time/base rotation
            if any(sw.data[work + 52:work + 116]):
                raw.append('SMX%d extra swing work' % i)
        elif any(sw.data[work:work + 116]):
            # Type zero's normal mover ignores work, but room callbacks may
            # consume it. Do not guess its scalar layout from nonzero bytes.
            raw.append('SMX%d type%d callback work' % (i, kind))
    return raw

TAG_FORMATS = {
    b"SMD\0": fmt_smd,
    b"SMX\0": fmt_smx,
    b"CNS\0": fmt_cns,
    b"SAT\0": fmt_sat,
    b"EAT\0": fmt_sat,
    b"MDT\0": fmt_mdt,
    b"TPL\0": fmt_tpl,
    b"UWF\0": fmt_uwf,
    b"EFF\0": fmt_eff,
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
            guarded(sw, fmt_tagged, off + start, end - start, sub_ctx, entry)
        REPORT.append(entry)


def guarded(sw, handler, off, size, ctx, entry):
    """Runs a handler confined to [off, off+size); on a layout error that
    region (and only that region) is restored raw and the error recorded, so
    one unexpected sub-file never aborts the mirror or damages a neighbour.
    A handler may return a list of "raw parts" it left untouched on purpose
    (an explicit safe-raw contract); they are recorded and the entry is
    marked incomplete."""
    backup = bytes(sw.data[off:off + size])
    marks = bytes(sw.done[off:off + size])
    try:
        with sw.bounded(off, size):
            raw = handler(sw, off, size, ctx)
        if raw:
            entry["raw_parts"] = list(raw)
            # a static-module REL is complete by contract: only its header is data
            entry["complete"] = handler is fmt_rel
        else:
            entry["complete"] = True
    except (ValueError, IndexError, struct.error) as e:
        sw.data[off:off + size] = backup
        sw.done[off:off + size] = marks
        entry["handled"] = False
        entry["complete"] = False
        entry["error"] = str(e)


# Files the game reads but never overlays a structure on (or only through a
# consumer outside the boot fixture): copied verbatim under a named contract.
RAW_CONTRACTS = {
    "etc/sizetbl.dat": "stored in cDvd::pSizeTbl by SizeTableRead and never dereferenced (src/game/dvd.cpp)",
}

FILE_FORMATS = [
    ("bgm/bio4str.hed", fmt_bio4str_hed),
    ("bgm/bio4midi.hed", fmt_u32_array),
    ("bgm/doorse.hed", fmt_doorse_hed),
    ("bgm/bgmtbl.dat", fmt_bgmtbl_dat),
    ("debug/roominfo.dat", fmt_roominfo),
    ("rel/*.rel", fmt_rel),
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
        guarded(sw, fmt_tagged, part_off, size, "%s:%s" % (rel, key), entry)
    elif entry["type"] == 2:
        # ARAM sample data: raw PCM / ADPCM bytes the sound DSP consumes as a
        # byte stream; no game structure is overlaid on it (explicit safe-raw).
        entry["format"] = "ARAM"
        entry["handled"] = True
        entry["complete"] = True
        entry["safe_raw"] = "sample bytes"


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
        entry = {"file": rel, "handled": True, "size": len(data), "format": "ARC"}
        guarded(sw, fmt_tagged, 0, len(data), rel, entry)
        REPORT.append(entry)
    elif rel in RAW_CONTRACTS:
        REPORT.append({"file": rel, "handled": True, "complete": True, "size": len(data),
                       "format": "RAW", "safe_raw": RAW_CONTRACTS[rel]})
    elif rel.endswith(".txt"):
        # Text the game parses byte by byte (debug/config.txt): explicit safe-raw.
        REPORT.append({"file": rel, "handled": True, "complete": True, "size": len(data),
                       "format": "TXT", "safe_raw": "text"})
    else:
        REPORT.append({"file": rel, "handled": False, "size": len(data)})


def check_required(report, deps_path):
    """Every entry of every required file must be handled and complete (or
    safe-raw). Returns the list of violations as strings."""
    required = []
    with open(deps_path) as f:
        lines = f.readlines()
    for line in lines:
        # a comment starts the line or follows whitespace ("#n" names a sub-file)
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split(" #", 1)[0].split(chr(9) + "#", 1)[0].strip().lower()
        if line:
            required.append(line)
    by_file = {}
    for e in report:
        by_file.setdefault(e["file"], []).append(e)
    problems = []
    for line in required:
        # "file" = every part and sub-file of it; "file:part" = that container
        # part; "file:part#n" or "file#n" = that tagged sub-file only.
        rel = line.split(":", 1)[0].split("#", 1)[0]
        entries = by_file.get(rel)
        if not entries:
            problems.append("%s: not in the tree" % rel)
            continue
        if "#" in line:
            entries = [e for e in entries if e.get("sub") == line]
        elif ":" in line:
            entries = [e for e in entries if "%s:%s" % (rel, e.get("part")) == line]
        if not entries:
            problems.append("%s: no such part" % line)
            continue
        for e in entries:
            where = e.get("sub") or ("%s:%s" % (rel, e["part"]) if "part" in e else rel)
            if e.get("error"):
                problems.append("%s: error: %s" % (where, e["error"]))
            elif not e.get("handled"):
                problems.append("%s: no handler (tag %s)" % (where, e.get("tag", e.get("format", "?"))))
            elif e.get("complete") is False:
                problems.append("%s: incomplete, raw parts: %s" % (where, ", ".join(e.get("raw_parts", []))))
    return problems


def prepare_room_archive(rel, data):
    """Decode the source room's single type-0 payload, then use normal handlers.

    The returned .arc is a build artifact, not runtime-ready unless every entry
    passes check_required. Original compressed files remain independently copied.
    """
    from decode_yz2 import decode
    if data[:32] != CONTAINER_MAGIC:
        raise ValueError(rel + ': room is not a DVD container')
    payloads = []
    terminated = False
    for pos in range(ENTRY_SIZE, HEADER_TABLE, ENTRY_SIZE):
        kind, size, dest, offset = struct.unpack_from('>4I', data, pos)
        if kind == END_OF_TABLE:
            terminated = True
            break
        if kind == 0:
            if offset < HEADER_TABLE or offset + size > len(data):
                raise ValueError(rel + ': room payload outside container')
            payloads.append((offset, size))
        elif kind not in (NESTED, SKIP_ENTRY):
            raise ValueError(rel + ': unexpected top-level room entry')
    if not terminated or len(payloads) != 1:
        raise ValueError(rel + ': expected one type-0 room payload')
    offset, size = payloads[0]
    decoded = bytearray(decode(data[offset:offset + size]))
    if not looks_like_tagged(decoded, 0, len(decoded)):
        raise ValueError(rel + ': decoded room is not a tagged archive')
    native_rel = rel[:-4] + '.arc'
    convert_file(native_rel, decoded)
    return native_rel, decoded


def main():
    argv = sys.argv[1:]
    require = None
    if "--require" in argv:
        i = argv.index("--require")
        require = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    force = "--force" in argv
    decode_rooms = "--decode-rooms" in argv
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
            if decode_rooms and fnmatch.fnmatchcase(rel, "st*/r*.das"):
                native_rel, decoded = prepare_room_archive(rel, open(sp, "rb").read())
                native_path = os.path.join(dst, native_rel)
                with open(native_path, "wb") as f:
                    f.write(decoded)
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
    errors = [e for e in REPORT if e.get("error")]
    if errors:
        print("le_mirror: %d handler errors (rolled back to raw), first: %s: %s"
              % (len(errors), errors[0].get("sub") or errors[0]["file"], errors[0]["error"]))
    if require:
        problems = check_required(REPORT, require)
        if problems:
            print("le_mirror: boot fixture dependencies not satisfied (%s):" % require)
            for m in problems:
                print("  " + m)
            sys.exit(2)
        print("le_mirror: boot fixture dependencies satisfied (%s)" % require)


if __name__ == "__main__":
    main()
