"""tools/aica_banks.py: codec parity with platform/audio_aica.cpp and in-place bank rewriting."""
import math
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import aica_banks as ab  # noqa: E402


def dsp_encode_silence_frames(n_frames):
    # DSP-ADPCM frames with scale 0 / predictor 0 and zero nibbles decode to 0.
    return bytes(8 * n_frames)


def make_archive(path, samples_len, rate):
    """A minimal DvdHeader archive: one ROOM (t=6) block, MRAM (ISS + WT) and ARAM parts."""
    n = len(samples_len)
    wt = bytearray(24)
    smp_ofs, adp_ofs = 24, 24 + 16 * n
    offs, table = 0, b''
    for ln in samples_len:
        table += struct.pack('<HHIIHH', 0, rate, offs * 2, ln, 0, 0)   # nibble address of the first frame header
        offs += (ln + 13) // 14 * 8
    wt[0:24] = struct.pack('<6I', 0, 0, 0, 0, smp_ofs, adp_ofs)
    wt += table + bytes(0x2E)
    iss = struct.pack('<4I', 1, 16, 0, 0)
    mram = struct.pack('<I', 4) + iss + bytes(wt)
    aram = dsp_encode_silence_frames(offs // 8)
    hdr = bytearray(b'\xca\xb6\xbe\x20' * 8)
    body_ofs = 0x20 + 32 * 3
    hdr += struct.pack('<8I', 1, len(mram), 0, body_ofs, 6, 256, 0, 0)
    hdr += struct.pack('<8I', 2, len(aram), 0, body_ofs + len(mram), 6, 256, 0, 0)
    hdr += struct.pack('<8I', 0xFFFFFFFF, 0, 0, 0, 0, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(bytes(hdr) + mram + aram)
    return body_ofs + len(mram), len(aram)


class Codec(unittest.TestCase):
    def test_sample_shift_matches_runtime_rules(self):
        self.assertEqual(ab.sample_shift(32000, 1000, 32000), 0)
        self.assertEqual(ab.sample_shift(32000, 1000, 16000), 1)
        self.assertEqual(ab.sample_shift(32000, 1000, 8000), 2)
        self.assertEqual(ab.sample_shift(11025, 200000, 32000), 2)   # AICA 16-bit LEA limit
        self.assertEqual(ab.sample_bytes(15, 0), 8)
        self.assertEqual(ab.sample_bytes(16, 1), 4)

    def test_yamaha_round_trip_snr(self):
        x = [int(12000 * math.sin(i * 0.05)) for i in range(4000)]
        enc = ab.yamaha_encode(x)
        self.assertEqual(len(enc), ab.sample_bytes(len(x), 0))
        y = ab.yamaha_decode(enc, len(x))
        sig, err = ab.energies(x, y)
        self.assertGreater(10 * math.log10(sig / err), 20.0)

    def test_decimate_truncates_like_c(self):
        self.assertEqual(ab.decimate([4, 4, -3], 1), [4, -3])
        self.assertEqual(ab.decimate([-1, -2, -1, -1, -1, -1, 0], 2), [-2, 0])   # >> floors, the tail / truncates


class Build(unittest.TestCase):
    def test_rewrite_in_place(self):
        with tempfile.TemporaryDirectory() as d:
            mirror, out = os.path.join(d, 'm'), os.path.join(d, 'o')
            os.makedirs(os.path.join(mirror, 'st1'))
            ao, asz = make_archive(os.path.join(mirror, 'st1', 'r100.dar'), [1400, 280], 32000)
            old = ab.ROOMS, ab.RESIDENT
            ab.ROOMS, ab.RESIDENT = {'r100': ['st1/r100.dar']}, []
            try:
                budget = ab.AICA_POOL - ab.MOVIE_RESERVE - ab.STREAM_RING
                res, per_room, uniq, slots, arena = ab.plan(mirror, ['r100'], budget)
                ab.build(mirror, out, res, per_room, uniq, slots, None, False)
            finally:
                ab.ROOMS, ab.RESIDENT = old
            src = open(os.path.join(mirror, 'st1', 'r100.dar'), 'rb').read()
            dst = open(os.path.join(out, 'st1', 'r100.dar'), 'rb').read()
            self.assertEqual(len(src), len(dst))
            self.assertEqual(src[:ao], dst[:ao])               # headers and MRAM part untouched
            h = ab.HDR.unpack_from(dst, ao)
            self.assertEqual(h[0], ab.MAGIC)
            self.assertEqual(h[2], 16000)                     # ROOM preferred cap
            self.assertEqual(h[3], ab.sample_bytes(1400, 1) + ab.sample_bytes(280, 1))
            self.assertEqual(h[7], 8)                         # room arena slot
            self.assertEqual(h[9 + 8], (h[3] + 31) & ~31)     # layout slot_bytes[8] = room arena


class Reserve(unittest.TestCase):
    def test_disc_refuses_to_eat_the_movie_reserve(self):
        with tempfile.TemporaryDirectory() as d:
            mirror = os.path.join(d, 'm')
            os.makedirs(os.path.join(mirror, 'st1'))
            make_archive(os.path.join(mirror, 'st1', 'r100.dar'), [60000, 60000], 8000)
            old = ab.ROOMS, ab.RESIDENT, ab.AICA_POOL
            ab.ROOMS, ab.RESIDENT = {'r100': ['st1/r100.dar']}, []
            ab.AICA_POOL = ab.MOVIE_RESERVE + ab.STREAM_RING + 1000   # too small even at the lowest cap
            try:
                with self.assertRaises(SystemExit):
                    ab.disc(mirror, os.path.join(d, 'out'), os.path.join(d, 'cache'), ['r100'], [], None)
            finally:
                ab.ROOMS, ab.RESIDENT, ab.AICA_POOL = old
            self.assertFalse(os.path.exists(os.path.join(d, 'out')))


class Streams(unittest.TestCase):
    def test_interleave_2k_blocks(self):
        a, b = bytes([1]) * 3000, bytes([2]) * 100
        out = ab.interleave([a, b])
        self.assertEqual(len(out), 2 * 2 * ab.STR_BLOCK)      # 2 blocks x 2 channels, zero padded
        self.assertEqual(out[:2048], a[:2048])
        self.assertEqual(out[2048:2148], b)
        self.assertEqual(out[4096:4096 + 952], a[2048:])

    def test_encoder_state_carries_over(self):
        x = [int(8000 * math.sin(i * 0.07)) for i in range(2000)]
        whole, p, s = ab.yamaha_encode_state(x)
        head, p1, s1 = ab.yamaha_encode_state(x[:1000])
        tail, p2, s2 = ab.yamaha_encode_state(x[1000:], p1, s1)
        self.assertEqual(head + tail, whole)                   # a region continues its predecessor's decoder state
        self.assertEqual((p2, s2), (p, s))


if __name__ == '__main__':
    unittest.main()
