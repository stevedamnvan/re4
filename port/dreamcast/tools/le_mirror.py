#!/usr/bin/env python3
"""Build a little-endian mirror of the GameCube data tree for the Dreamcast
game target.

    le_mirror.py <src-tree> <dst-tree> [--force]

The recovered game code overlays its structures straight onto the files it
reads (include/dvd.h DvdHeader, include/snd.h, include/snd_drv.h, ...).  On
the SH-4 those structures are little-endian, so every scalar the game reads
from a file has to be byte-swapped once, offline, with the layout left
untouched.  Each format gets a handler that walks the layout the game
headers describe; bytes no handler covers are copied as they are and listed
in <dst-tree>/le_mirror_report.json, which is how the boot log's next
failure is mapped to the next format to cover.

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
        self.done = set()

    def _mark(self, off, size):
        if off < 0 or off + size > len(self.data):
            raise ValueError("%s: field at %#x/%d outside %#x bytes" % (self.label, off, size, len(self.data)))
        for o in range(off, off + size):
            if o in self.done:
                raise ValueError("%s: byte %#x swapped twice" % (self.label, o))
            self.done.add(o)

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


# ----------------------------------------------------------------- formats

def fmt_u32_array(sw, off, size):
    """A plain u32 table (bgm/bio4midi.hed: SndMem.bgm_file[no] file offsets)."""
    sw.u32s(off, size // 4)


def fmt_bio4str_hed(sw, off, size):
    """bgm/bio4str.hed: two stream blocks (snd.cpp SndInit, snd_sub3.cpp
    Snd_str_blk_init): u32 block_ofs[2]; block = {u32 num, shd_tbl_ofs,
    rit_ofs}; rit = SND_RIT[num]; shd table = u32 offsets (relative to the
    table) to SND_SHD records (include/snd_drv.h)."""
    blocks = sw.u32s(off, 2)
    for b in blocks:
        base = off + b
        num, shd_tbl, rit = sw.u32s(base, 3)
        # SND_RIT: s16 shd_no, then bytes, u16 flag at 0x0C, bytes
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


def fmt_doorse_hed(sw, off, size):
    """bgm/doorse.hed: SndDoorTbl {u32 file_ofs, num_ofs}; u16 count at
    num_ofs; u32 file offsets[count] at file_ofs (snd.cpp 1735/1753)."""
    file_ofs, num_ofs = sw.u32s(off, 2)
    count = sw.u16(off + num_ofs)
    sw.u32s(off + file_ofs, count)


def fmt_bgmtbl_dat(sw, off, size):
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


FILE_FORMATS = [
    ("bgm/bio4str.hed", fmt_bio4str_hed),
    ("bgm/bio4midi.hed", fmt_u32_array),
    ("bgm/doorse.hed", fmt_doorse_hed),
    ("bgm/bgmtbl.dat", fmt_bgmtbl_dat),
]

# Container parts: (archive pattern, part key) -> handler. Part keys are the
# top-level index ("2") or nested index ("2/0"). Nothing is registered yet;
# every part is reported so the boot log names the next format to cover.
PART_FORMATS = []


def find_handler(table, key):
    for pattern, handler in table:
        if fnmatch.fnmatchcase(key, pattern):
            return handler
    return None


def convert_container(sw, rel, report):
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
                    report.append({"file": rel, "part": key, "note": "nested table below the game's nest limit"})
            else:
                part_off = base + ofs
                if part_off + size > len(data):
                    raise ValueError("%s part %s outside the file" % (rel, key))
                handler = find_handler(PART_FORMATS, "%s:%s" % (rel, key))
                entry = {"file": rel, "part": key, "type": t, "ofs": part_off, "size": size,
                         "snd": [snd_type, snd_arg, snd_no], "handled": handler is not None}
                if handler:
                    handler(sw, part_off, size)
                report.append(entry)
            off += ENTRY_SIZE
            i += 1

    walk(0, "", 0)


def convert_file(rel, data, report):
    sw = Swapper(data, rel)
    handler = find_handler(FILE_FORMATS, rel)
    if handler:
        handler(sw, 0, len(data))
        report.append({"file": rel, "handled": True, "size": len(data)})
    elif data[:32] == CONTAINER_MAGIC:
        convert_container(sw, rel, report)
    else:
        report.append({"file": rel, "handled": False, "size": len(data)})


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
    report = []
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
                    report.extend(previous[rel])
                    skipped += 1
                    continue
            data = bytearray(open(sp, "rb").read())
            convert_file(rel, data, report)
            with open(dp, "wb") as f:
                f.write(data)
            converted += 1
    with open(report_path, "w") as f:
        json.dump(report, f, indent=1)
    parts = [e for e in report if "part" in e]
    print("le_mirror: %d converted, %d up to date; %d files handled, %d container parts (%d handled), %d raw files"
          % (converted, skipped, sum(1 for e in report if e.get("handled") and "part" not in e), len(parts),
             sum(1 for e in parts if e.get("handled")),
             sum(1 for e in report if "part" not in e and not e.get("handled"))))


if __name__ == "__main__":
    main()
