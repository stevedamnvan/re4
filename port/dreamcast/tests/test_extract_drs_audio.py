import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
TOOL = ROOT / "port" / "dreamcast" / "tools" / "extract_drs_audio.py"
SPEC = importlib.util.spec_from_file_location("extract_drs_audio", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DspAdpcmDecodeTests(unittest.TestCase):
    def test_zero_predictor_decodes_signed_nibbles(self):
        encoded = bytes([0x00, 0x17, 0xF8, 0x20, 0x00, 0x00, 0x00, 0x00])
        decoded = MODULE.decode_dsp_adpcm(encoded, 8, (0,) * 16)
        self.assertEqual(decoded, [1, 7, -1, -8, 2, 0, 0, 0])

    def test_declared_samples_must_fit_complete_frames(self):
        with self.assertRaisesRegex(ValueError, "ends before"):
            MODULE.decode_dsp_adpcm(b"\0" * 7, 1, (0,) * 16)

    def test_coefficient_count_is_checked(self):
        with self.assertRaisesRegex(ValueError, "16 coefficients"):
            MODULE.decode_dsp_adpcm(b"\0" * 8, 1, (0,) * 15)


if __name__ == "__main__":
    unittest.main()
