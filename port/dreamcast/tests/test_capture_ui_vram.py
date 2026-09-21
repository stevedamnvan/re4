import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import capture_ui_vram as C

class Readback(unittest.TestCase):
    def test_kos_pointer_and_bank_mapping(self):
        self.assertEqual(C.framebuffer_offset(0xa514e900), 0x0a7480)
        self.assertEqual(C.framebuffer_offset(0xa594e900), 0x4a7480)
        self.assertEqual(C.map_32bit_vram(0x0a7480), 0x14e900)
        self.assertEqual(C.map_32bit_vram(0x4a7480), 0x14e904)
        # The old mask aliases front/back and reads the wrong location.
        self.assertEqual(0xa514e900 & 0x7fffff, 0xa594e900 & 0x7fffff)
        for invalid in (0xa4000000, 0xa6000000, 0xa5000001):
            with self.assertRaises(ValueError): C.framebuffer_offset(invalid)

    def test_separate_banks_and_primary_colours(self):
        vram = bytearray(C.VRAM_SIZE)
        vram[0:8] = bytes.fromhex("00f8e0071f00ffff")
        self.assertEqual(C.decode_rgb565(vram, 0, 2, 1), bytes([255,0,0,0,255,0]))
        self.assertEqual(C.decode_rgb565(vram, 0x400000, 2, 1), bytes([0,0,255,255,255,255]))
        with self.assertRaises(ValueError): C.decode_rgb565(vram, C.VRAM_SIZE - 4)

if __name__ == "__main__": unittest.main()
