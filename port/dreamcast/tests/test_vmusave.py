"""VMU saves (VMU_SAVE=1): the host tool (tools/vmusave.py) and the Dreamcast codec
(game/platform/lz_small.cpp) must agree byte for byte, round-trip every buffer, and the save
container must rebuild the GameCube image exactly."""
from pathlib import Path
import importlib.util, random, struct, subprocess, tempfile, unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vmusave', ROOT / 'tools/vmusave.py')
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include "lz_small.h"
static unsigned short table[1u << LZS_HASH_BITS];
int main(int argc, char** argv) {
    FILE* f = fopen(argv[1], "rb"); static unsigned char in[70000], out[80000], back[70000];
    unsigned n = (unsigned) fread(in, 1, sizeof(in), f); fclose(f);
    int c = lzs_encode(in, n, out, sizeof(out), table);
    if (c < 0) return 2;
    if (lzs_decode(out, (unsigned) c, back, n) != (int) n) return 3;
    for (unsigned i = 0; i < n; ++i) if (back[i] != in[i]) return 4;
    if (lzs_verify(out, (unsigned) c, in, n) != (int) n) return 7;
    if (n) { in[n / 2] ^= 1; if (lzs_verify(out, (unsigned) c, in, n) != -1) return 8; in[n / 2] ^= 1; }
    if (n && lzs_decode(out, (unsigned) c, back, n - 1) != -1) return 5;   /* wrong length refused */
    if (c > 1 && lzs_decode(out, (unsigned) c - 1, back, n) != -1 && n) return 6;  /* truncated refused */
    f = fopen(argv[2], "wb"); fwrite(out, 1, (size_t) c, f); fclose(f);
    return 0;
}
'''


def buffers(seed=7, count=300):
    rnd = random.Random(seed)
    yield b''
    yield b'abc'
    yield bytes(vs.RAW_LEN)
    yield bytes(range(256)) * 255
    for _ in range(count):
        n = rnd.randrange(0, 60000)
        kind = rnd.randrange(4)
        if kind == 0:
            yield bytes(rnd.getrandbits(8) for _ in range(min(n, 3000)))
        elif kind == 1:
            yield bytes(rnd.choice(b'\0\0\0\0\x01\xff\x10') for _ in range(n))
        elif kind == 2:
            b = bytearray(n)
            for _ in range(n // 40 + 1):
                if n:
                    b[rnd.randrange(n)] = rnd.getrandbits(8)
            yield bytes(b)
        else:
            unit = bytes(rnd.getrandbits(8) for _ in range(rnd.randrange(1, 64)))
            yield (unit * (n // len(unit) + 1))[:n]


def save_like(seed):
    """A save-shaped image: header, sparse flags, a structured enemy list, zero padding."""
    rnd = random.Random(seed)
    img = bytearray(vs.SAVE_SIZE)
    img[0x2004:0x2008] = struct.pack('<I', 0x116)
    for _ in range(400):
        img[rnd.randrange(0x2034, 0x572C)] = rnd.getrandbits(8)
    for i in range(256):                       # an ESL-like 32 B record table at global 0x52E8
        o = 0x2034 + 0x368 + i * 32
        img[o:o + 32] = struct.pack('<HHhhhhHH', 1, rnd.randrange(64), rnd.randrange(-9999, 9999), 0,
                                    rnd.randrange(-9999, 9999), 0, i, 0) + bytes(16)
    for i in range(0, 121 * 0xD8, 0xD8):
        if rnd.random() < 0.1:
            img[0x6940 + i:0x6940 + i + 16] = bytes(rnd.getrandbits(8) for _ in range(16))
    img[0x2000:0x2004] = struct.pack('<I', vs.game_crc(img[0x2004:0x2200]))
    img[vs.SAVE_CRC:vs.SAVE_SIZE] = struct.pack('<I', vs.game_crc(img[:vs.SAVE_CRC]))
    return bytes(img)


class VmuSave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / 'h.c').write_text(HARNESS)
        plat = ROOT / 'game/platform'
        subprocess.run(['c++', '-O2', '-Wall', '-Werror', '-DRE4DC_VMU_SAVE=1', '-I', str(plat / 'include'),
                        '-x', 'c++', str(cls.tmp / 'h.c'), str(plat / 'lz_small.cpp'), '-o', str(cls.tmp / 'lzs')], check=True)

    def c_encode(self, data):
        (self.tmp / 'in').write_bytes(data)
        r = subprocess.run([str(self.tmp / 'lzs'), str(self.tmp / 'in'), str(self.tmp / 'out')])
        self.assertEqual(r.returncode, 0)
        return (self.tmp / 'out').read_bytes()

    def test_c_matches_python(self):
        for b in buffers():
            py = vs.lz_encode(b)
            self.assertEqual(vs.lz_decode(py, len(b)), b)
            self.assertEqual(self.c_encode(b), py)

    def test_save_images(self):
        for seed in range(5):
            img = save_like(seed)
            payload = img[vs.SAVE_PAYLOAD:vs.SAVE_CRC]
            self.assertEqual(self.c_encode(payload), vs.lz_encode(payload))
            vms = vs.save_pack(img, slot=seed, seq=3)
            self.assertEqual(len(vms) % 512, 0)
            back, meta = vs.save_unpack(vms)
            self.assertTrue(meta['crc_ok'])
            self.assertEqual(back[0x2000:], img[0x2000:])      # every byte the load copies
            self.assertEqual(back[:0x2000], bytes(0x2000))     # the GameCube banner area is dropped
            self.assertEqual(vs.game_crc(back[:vs.SAVE_CRC]), struct.unpack_from('<I', back, vs.SAVE_CRC)[0])

    def test_vms_crc_and_vmu_image(self):
        vms = vs.save_pack(save_like(9), slot=4)
        bad = bytearray(vms); bad[700] ^= 1
        with self.assertRaises(ValueError):
            vs.save_unpack(bytes(bad))
        vmu = vs.Vmu(vs.vmu_format())
        self.assertEqual(vmu.free_blocks(), 200)
        vmu.write('RE4DCS05A', vms)
        self.assertEqual(vmu.read('RE4DCS05A'), vms)
        self.assertEqual(vmu.free_blocks(), 200 - len(vms) // 512)
        vmu.delete('RE4DCS05A')
        self.assertEqual(vmu.free_blocks(), 200)

    def test_sys_file(self):
        img = bytearray(vs.SYS_SIZE)
        img[vs.SYS_WORK:vs.SYS_CRC] = bytes(range(56))
        struct.pack_into('<I', img, vs.SYS_CRC, vs.game_crc(img[:vs.SYS_CRC]))
        back = vs.sys_unpack(vs.sys_pack(bytes(img)))
        self.assertEqual(back[vs.SYS_WORK:], bytes(img[vs.SYS_WORK:]))

    def test_crc16_matches_kos(self):
        # net_crc16ccitt reference value (CRC-16/XMODEM of "123456789").
        self.assertEqual(vs.crc16_ccitt(b'123456789'), 0x31C3)


if __name__ == '__main__':
    unittest.main()
