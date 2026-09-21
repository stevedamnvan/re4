import pathlib
import sys
import unittest
from PIL import Image
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import texture_candidate as candidate
import convert_tpl as tpl

class TextureCandidateTests(unittest.TestCase):
    def test_lossless_bridge_with_rectangular_colored_alpha_fixture(self):
        image=Image.new('RGBA',(16,8))
        pixels=[((i*37)%256,(i*73)%256,(i*13)%256,(i*17)%256) for i in range(128)]
        image.putdata(pixels)
        converted=candidate.rgba_image(image)
        self.assertEqual(tpl.decode_image(converted),pixels)
        self.assertEqual((converted.width,converted.height),(16,8))

    def test_reject_unsupported_dimensions_without_resizing(self):
        with self.assertRaises(ValueError):
            candidate.rgba_image(Image.new('RGBA',(15,8)))

if __name__=='__main__':unittest.main()
