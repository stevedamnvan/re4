#!/usr/bin/env python3
"""D367 VMU saves: host tools for the virtual memory card (design-vmu/DESIGN.md).

The Dreamcast side (platform/lz_small.cpp, vmu_store.cpp, card.cpp) stores a GameCube save image
(bh4_dataNN, 0xEAFC bytes) as a VMS data file RE4DCSnnA/B:

    VMS header (128 B) + one 32x32 16-colour icon (512 B)      <- BIOS file manager
    R4DC header (32 B, big-endian)                              <- this tool / card.cpp
    SaveInfo raw: image[0x2000:0x2200] (512 B)                  <- the load list (3 blocks)
    LZ stream:    LZ4-block format over image[0x2200:0xEAF8]

Everything in image[0x2000:0xEAF8] is kept byte for byte; the banner/icon/comment area
(0x0000-0x2000) is GameCube-only and comes back as zeros, and the image CRC at 0xEAF8 is
recomputed on load (the game's own CRCCalc), so the game's unchanged loadMain sees the same bytes
as from a GameCube card.

Commands:
  lz-selftest                       codec round trip over synthetic and random buffers
  pack <gc-image> <out.vms> [--slot N] [--kind save|dbg]   GameCube image -> VMS file
  unpack <file.vms> <gc-image>      VMS file -> GameCube image (CRC recomputed)
  info <file.vms>                   headers, sizes, block count
  vmu-list <vmu_save_A1.bin>        list a Flycast VMU image (flash dump, 128 KiB)
  vmu-extract <vmu.bin> <NAME> <out>
  vmu-insert <vmu.bin> <NAME> <file.vms>   (data file, placed from the top as the BIOS does)
  vmu-format <vmu.bin>              write an empty formatted VMU image
  vmu-fill <vmu.bin> <free-blocks>  add a filler file so only <free-blocks> stay free
  sys-pack <gc-sys-image> <out.vms> / sys-unpack <file.vms> <gc-sys-image>
Deterministic: the same input gives the same bytes (fixed hash, greedy parse, no timestamps
unless --time is given).
"""
import argparse
import struct
import sys
from pathlib import Path

# ----------------------------------------------------------------------------- constants
SAVE_SIZE = 0xEAFC          # card.cpp SAVE_SIZE
SAVE_HDR = 0x2000           # SaveInfo / header CRC area
SAVE_PAYLOAD = 0x2200       # first byte of the compressed range
SAVE_CRC = 0xEAF8           # image CRC position (CRCCalc over 0..0xEAF8)
RAW_LEN = SAVE_CRC - SAVE_PAYLOAD  # 0xC8F8
SYS_SIZE = 0x1E7C
SYS_WORK = 0x1E40
SYS_CRC = 0x1E78
SYS_WORK_LEN = SYS_CRC - SYS_WORK  # 56 B
VMS_HDR = 128
ICON = 512
R4DC_HDR = 32
BLOCK = 512
PREFIX = VMS_HDR + ICON + R4DC_HDR + 512      # save prefix before the LZ stream: 1184 B
KIND_SAVE, KIND_SYS, KIND_DBG, KIND_CFG = 1, 2, 4, 8
MAGIC = b'R4DC'
FMT = 1

# ----------------------------------------------------------------------------- CRCs
def _crc_table():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
        t.append(c)
    return t


_CRC_T = _crc_table()


def game_crc(data):
    """The game's CRCCalc (card.cpp CRCInit/CRCCalc): MSB-first CRC-32, poly 0x04C11DB7, init 0,
    no final xor."""
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CRC_T[(crc >> 24) ^ b]
    return crc


def crc16_ccitt(data, crc=0):
    """KOS net_crc16ccitt (poly 0x1021, MSB first) as vmu_pkg_build uses it (start 0)."""
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc

# ----------------------------------------------------------------------------- LZ (LZ4 block)
HASH_BITS = 11              # 2048 u16 positions = 4 KiB table
MIN_MATCH = 4
MFLIMIT = 12                # a match may not start within the last 12 bytes
LASTLITERALS = 5            # the last 5 bytes are always literals
MAX_DIST = 0xFFFF


def _hash(v):
    return ((v * 2654435761) & 0xFFFFFFFF) >> (32 - HASH_BITS)


def lz_encode(src):
    """Deterministic greedy LZ4-block encoder; platform/lz_small.cpp matches it byte for byte.
    Inputs are at most 65535 bytes (u16 positions)."""
    src = bytes(src)
    n = len(src)
    assert n <= 0xFFFF
    out = bytearray()
    table = [0] * (1 << HASH_BITS)
    anchor = ip = 0
    rd = lambda p: src[p] | src[p + 1] << 8 | src[p + 2] << 16 | src[p + 3] << 24
    limit = n - MFLIMIT          # last position a match may start at (inclusive)
    while ip <= limit:
        h = _hash(rd(ip))
        cand = table[h]
        table[h] = ip
        if cand < ip and ip - cand <= MAX_DIST and rd(cand) == rd(ip):
            ml = MIN_MATCH
            end = n - LASTLITERALS
            while ip + ml < end and src[cand + ml] == src[ip + ml]:
                ml += 1
            _seq(out, src, anchor, ip - anchor, ip - cand, ml)
            ip += ml
            anchor = ip
        else:
            ip += 1
    _last(out, src, anchor, n - anchor)
    return bytes(out)


def _len_ext(out, v):
    while v >= 255:
        out.append(255)
        v -= 255
    out.append(v)


def _seq(out, src, lit_pos, lit_len, off, ml):
    m = ml - MIN_MATCH
    out.append((min(lit_len, 15) << 4) | min(m, 15))
    if lit_len >= 15:
        _len_ext(out, lit_len - 15)
    out += src[lit_pos:lit_pos + lit_len]
    out += struct.pack('<H', off)
    if m >= 15:
        _len_ext(out, m - 15)


def _last(out, src, lit_pos, lit_len):
    out.append(min(lit_len, 15) << 4)
    if lit_len >= 15:
        _len_ext(out, lit_len - 15)
    out += src[lit_pos:lit_pos + lit_len]


def lz_decode(comp, raw_len):
    comp = bytes(comp)
    out = bytearray()
    i = 0
    n = len(comp)
    while i < n:
        tok = comp[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = comp[i]; i += 1
                lit += b
                if b != 255:
                    break
        out += comp[i:i + lit]; i += lit
        if i >= n:
            break
        off = comp[i] | comp[i + 1] << 8; i += 2
        if off == 0 or off > len(out):
            raise ValueError('bad offset %d at %d' % (off, i))
        ml = tok & 15
        if ml == 15:
            while True:
                b = comp[i]; i += 1
                ml += b
                if b != 255:
                    break
        ml += MIN_MATCH
        s = len(out) - off
        for k in range(ml):
            out.append(out[s + k])
    if len(out) != raw_len:
        raise ValueError('length %d != %d' % (len(out), raw_len))
    return bytes(out)

# ----------------------------------------------------------------------------- VMS package
DESC_SHORT = b'RESIDENT EVIL 4'
APP_ID = b'RE4DC'


def default_icon():
    """A plain 32x32 4-bit icon (RE4DC placeholder until the TPL #2 conversion is supplied):
    dark red square with a light frame. Returns (palette[16] ARGB4444, 512 B pixels)."""
    pal = [0x0000, 0xF311, 0xFCCB, 0xFA22] + [0xF000] * 12
    px = bytearray(512)
    for y in range(32):
        for x in range(32):
            c = 2 if x in (0, 31) or y in (0, 31) else 3 if 10 <= x <= 21 and 10 <= y <= 21 else 1
            i = y * 32 + x
            px[i >> 1] |= c << 4 if not (i & 1) else c
    return pal, bytes(px)


def vms_build(desc_long, payload, icon=None):
    pal, px = icon or default_icon()
    hdr = bytearray(VMS_HDR)
    hdr[0:16] = DESC_SHORT.ljust(16, b' ')
    hdr[16:48] = desc_long.encode('ascii')[:32].ljust(32, b' ')
    hdr[48:64] = APP_ID.ljust(16, b'\0')
    struct.pack_into('<HHHHI', hdr, 64, 1, 0, 0, 0, len(payload))
    struct.pack_into('<16H', hdr, 96, *pal)
    body = bytes(hdr) + px + bytes(payload)
    crc = crc16_ccitt(body)
    body = body[:70] + struct.pack('<H', crc) + body[72:]
    pad = (-len(body)) % BLOCK
    return body + b'\0' * pad


def vms_parse(data):
    icon_cnt, speed, ec, crc, data_len = struct.unpack_from('<HHHHI', data, 64)
    assert ec == 0, 'eyecatch not supported'
    total = VMS_HDR + ICON * icon_cnt + data_len
    if total > len(data):
        raise ValueError('VMS header corrupted')
    chk = bytearray(data[:total]); chk[70:72] = b'\0\0'
    if crc16_ccitt(chk) != crc:
        raise ValueError('VMS CRC mismatch')
    return {'desc_short': data[:16], 'desc_long': data[16:48], 'app_id': data[48:64],
            'payload': bytes(data[VMS_HDR + ICON * icon_cnt:total])}

# ----------------------------------------------------------------------------- R4DC save
def r4dc_header(kind, slot, seq, raw_len, comp_len, crc_raw, build_tag=0, flags=0):
    return MAGIC + struct.pack('>BBBBIIIIII', FMT, kind, slot, flags, seq, raw_len, comp_len,
                               crc_raw, build_tag, 0)


def save_pack(image, slot=0, seq=1, kind=KIND_SAVE, extras=b'', ring=None):
    """GameCube save image -> VMS file bytes. extras/ring: debug slot only (kind 4)."""
    image = bytes(image)
    assert len(image) >= SAVE_CRC
    info = image[SAVE_HDR:SAVE_PAYLOAD]
    raw = image[SAVE_PAYLOAD:SAVE_CRC]
    comp = lz_encode(raw)
    assert lz_decode(comp, len(raw)) == raw
    crc_raw = game_crc(image[SAVE_HDR:SAVE_CRC])
    body = r4dc_header(kind, slot, seq, len(raw), len(comp), crc_raw) + info + comp
    if kind == KIND_DBG:
        body += bytes(extras).ljust(256, b'\0')[:256]
    desc = ('RE4DC FILE %02d' % (slot + 1)) if kind == KIND_SAVE else 'RE4DC DEBUG SLOT'
    vms = vms_build(desc, body)
    if ring is not None:
        vms += bytes(ring).ljust(BLOCK, b'\0')[:BLOCK]
    return vms


def save_unpack(vms):
    p = vms_parse(vms)['payload']
    if p[:4] != MAGIC:
        raise ValueError('not an R4DC file')
    fmt, kind, slot, flags, seq, raw_len, comp_len, crc_raw, tag, _ = struct.unpack_from('>BBBBIIIIII', p, 4)
    info = p[R4DC_HDR:R4DC_HDR + 512]
    comp = p[R4DC_HDR + 512:R4DC_HDR + 512 + comp_len]
    raw = lz_decode(comp, raw_len)
    image = bytearray(SAVE_SIZE)
    image[SAVE_HDR:SAVE_PAYLOAD] = info
    image[SAVE_PAYLOAD:SAVE_CRC] = raw
    ok = game_crc(image[SAVE_HDR:SAVE_CRC]) == crc_raw
    struct.pack_into('<I', image, SAVE_CRC, game_crc(image[:SAVE_CRC]))  # native (SH-4) order
    return bytes(image), {'fmt': fmt, 'kind': kind, 'slot': slot, 'seq': seq, 'raw_len': raw_len,
                          'comp_len': comp_len, 'crc_ok': ok, 'blocks': len(vms) // BLOCK}


def sys_pack(sysimg, seq=1):
    work = bytes(sysimg[SYS_WORK:SYS_CRC])
    body = r4dc_header(KIND_SYS, 0, seq, len(work), len(work), game_crc(work)) + work
    return vms_build('RE4DC SYSTEM', body)


def sys_unpack(vms):
    p = vms_parse(vms)['payload']
    assert p[:4] == MAGIC and p[5] == KIND_SYS
    work = p[R4DC_HDR:R4DC_HDR + SYS_WORK_LEN]
    img = bytearray(SYS_SIZE)
    img[SYS_WORK:SYS_CRC] = work
    struct.pack_into('<I', img, SYS_CRC, game_crc(img[:SYS_CRC]))
    return bytes(img)

# ----------------------------------------------------------------------------- VMU image
VMU_BLOCKS = 256
ROOT_BLK, FAT_BLK, DIR_BLK, DIR_SIZE, USER_BLOCKS = 255, 254, 253, 13, 200
FAT_FREE, FAT_END = 0xFFFC, 0xFFFA


class Vmu:
    """A Flycast vmu_save_XX.bin (128 KiB flash dump, little-endian as the maple driver sees it)."""

    def __init__(self, data):
        assert len(data) == VMU_BLOCKS * BLOCK
        self.d = bytearray(data)
        root = self.blk(ROOT_BLK)
        assert root[:16] == b'\x55' * 16, 'unformatted VMU image'
        self.fat_loc, self.fat_size, self.dir_loc, self.dir_size, _, self.blk_cnt = \
            struct.unpack_from('<6H', root, 0x46)

    def blk(self, n):
        return self.d[n * BLOCK:(n + 1) * BLOCK]

    def fat(self, i):
        return struct.unpack_from('<H', self.d, self.fat_loc * BLOCK + 2 * i)[0]

    def set_fat(self, i, v):
        struct.pack_into('<H', self.d, self.fat_loc * BLOCK + 2 * i, v)

    def dirents(self):
        for k in range(self.dir_size * 16):
            blk = self.dir_loc - k // 16
            off = blk * BLOCK + (k % 16) * 32
            yield off, self.d[off:off + 32]

    def files(self):
        for off, e in self.dirents():
            if e[0]:
                yield {'name': e[4:16].rstrip(b'\0').decode('ascii', 'replace'), 'type': e[0],
                       'first': struct.unpack_from('<H', e, 2)[0], 'blocks': struct.unpack_from('<H', e, 0x18)[0],
                       'off': off}

    def free_blocks(self):
        return sum(1 for i in range(self.blk_cnt) if self.fat(i) == FAT_FREE)

    def read(self, name):
        for f in self.files():
            if f['name'] == name:
                out, b = bytearray(), f['first']
                for _ in range(f['blocks']):
                    out += self.blk(b)
                    b = self.fat(b)
                assert b == FAT_END, 'FAT chain mismatch'
                return bytes(out)
        raise KeyError(name)

    def delete(self, name):
        for f in self.files():
            if f['name'] == name:
                b = f['first']
                for _ in range(f['blocks']):
                    nb = self.fat(b); self.set_fat(b, FAT_FREE); b = nb
                self.d[f['off']:f['off'] + 32] = bytes(32)
                return True
        return False

    def write(self, name, data, filetype=0x33):
        assert len(data) % BLOCK == 0
        n = len(data) // BLOCK
        self.delete(name)
        free = [i for i in range(self.blk_cnt - 1, -1, -1) if self.fat(i) == FAT_FREE]
        if len(free) < n:
            raise ValueError('VMU full: need %d, free %d' % (n, len(free)))
        chain = free[:n]
        for k, b in enumerate(chain):
            self.d[b * BLOCK:(b + 1) * BLOCK] = data[k * BLOCK:(k + 1) * BLOCK]
            self.set_fat(b, chain[k + 1] if k + 1 < n else FAT_END)
        for off, e in self.dirents():
            if not e[0]:
                ent = bytearray(32)
                ent[0] = filetype
                struct.pack_into('<H', ent, 2, chain[0])
                ent[4:16] = name.encode('ascii')[:12].ljust(12, b'\0')
                ent[16:24] = bytes([0x20, 0x26, 0x09, 0x23, 0x12, 0, 0, 2])  # fixed BCD time
                struct.pack_into('<HH', ent, 0x18, n, 0)
                self.d[off:off + 32] = ent
                return chain[0]
        raise ValueError('directory full')


def vmu_format():
    d = bytearray(VMU_BLOCKS * BLOCK)
    root = bytearray(BLOCK)
    root[:16] = b'\x55' * 16
    root[0x10:0x15] = bytes([1, 0xFF, 0xFF, 0xFF, 0x64])   # as Flycast formats (custom colour)
    root[0x30:0x38] = bytes([0x19, 0x98, 0x11, 0x27, 0, 0, 0x59, 4])
    root[0x44] = ROOT_BLK
    struct.pack_into('<8H', root, 0x46, FAT_BLK, 1, DIR_BLK, DIR_SIZE, 0, USER_BLOCKS, 0, 0)
    d[ROOT_BLK * BLOCK:] = root
    fat = [FAT_FREE] * VMU_BLOCKS
    fat[ROOT_BLK] = FAT_END
    fat[FAT_BLK] = FAT_END
    for k in range(DIR_SIZE):
        b = DIR_BLK - k
        fat[b] = b - 1 if k + 1 < DIR_SIZE else FAT_END
    d[FAT_BLK * BLOCK:(FAT_BLK + 1) * BLOCK] = struct.pack('<256H', *fat)
    return bytes(d)

# ----------------------------------------------------------------------------- self test
def lz_selftest(count=1000, seed=1):
    import random
    rnd = random.Random(seed)
    cases = [b'', b'a', b'abcd' * 3, bytes(RAW_LEN), bytes(range(256)) * 200]
    for _ in range(count):
        n = rnd.randrange(0, 65535)
        kind = rnd.randrange(4)
        if kind == 0:
            b = bytes(rnd.getrandbits(8) for _ in range(min(n, 4000)))
        elif kind == 1:
            b = bytes(rnd.choice(b'\0\0\0\0\x01\xff') for _ in range(n))
        elif kind == 2:
            b = bytearray(n)
            for _ in range(n // 50 + 1):
                if n:
                    b[rnd.randrange(n)] = rnd.getrandbits(8)
            b = bytes(b)
        else:
            unit = bytes(rnd.getrandbits(8) for _ in range(rnd.randrange(1, 40)))
            b = (unit * (n // len(unit) + 1))[:n]
        cases.append(b)
    for b in cases:
        c = lz_encode(b)
        assert lz_decode(c, len(b)) == b
    return len(cases)

# ----------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd')
    ap.add_argument('args', nargs='*')
    ap.add_argument('--slot', type=int, default=0)
    ap.add_argument('--seq', type=int, default=1)
    a = ap.parse_args(argv)
    A = a.args
    if a.cmd == 'lz-selftest':
        print('lz round trip ok: %d buffers' % lz_selftest())
    elif a.cmd == 'lz':
        data = Path(A[0]).read_bytes()
        Path(A[1]).write_bytes(lz_encode(data))
    elif a.cmd == 'pack':
        Path(A[1]).write_bytes(save_pack(Path(A[0]).read_bytes(), a.slot, a.seq))
    elif a.cmd == 'unpack':
        img, meta = save_unpack(Path(A[0]).read_bytes())
        Path(A[1]).write_bytes(img)
        print(meta)
    elif a.cmd == 'info':
        img, meta = save_unpack(Path(A[0]).read_bytes())
        print(meta)
    elif a.cmd == 'sys-pack':
        Path(A[1]).write_bytes(sys_pack(Path(A[0]).read_bytes(), a.seq))
    elif a.cmd == 'sys-unpack':
        Path(A[1]).write_bytes(sys_unpack(Path(A[0]).read_bytes()))
    elif a.cmd == 'vmu-format':
        Path(A[0]).write_bytes(vmu_format())
    elif a.cmd == 'vmu-list':
        v = Vmu(Path(A[0]).read_bytes())
        for f in v.files():
            print('%-12s type=%02x first=%3d blocks=%3d' % (f['name'], f['type'], f['first'], f['blocks']))
        print('free %d of %d' % (v.free_blocks(), v.blk_cnt))
    elif a.cmd == 'vmu-extract':
        Path(A[2]).write_bytes(Vmu(Path(A[0]).read_bytes()).read(A[1]))
    elif a.cmd == 'vmu-insert':
        v = Vmu(Path(A[0]).read_bytes())
        v.write(A[1], Path(A[2]).read_bytes())
        Path(A[0]).write_bytes(v.d)
    elif a.cmd == 'vmu-fill':
        v = Vmu(Path(A[0]).read_bytes())
        want = int(A[1])
        n = v.free_blocks() - want
        if n > 0:
            v.write('FILLER', vms_build('FILLER', bytes(n * BLOCK - VMS_HDR - ICON)))
        Path(A[0]).write_bytes(v.d)
        print('free now', v.free_blocks())
    else:
        ap.error('unknown command ' + a.cmd)


if __name__ == '__main__':
    main()
