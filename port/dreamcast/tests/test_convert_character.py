import importlib.util
from pathlib import Path
import struct
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "convert_character.py"
SPEC = importlib.util.spec_from_file_location("convert_character", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CharacterConverterTests(unittest.TestCase):
    def test_triangulates_gamecube_primitives(self):
        self.assertEqual(
            list(MODULE.triangulate(0x80, [0, 1, 2, 3])),
            [(0, 1, 2), (0, 2, 3)],
        )
        self.assertEqual(
            list(MODULE.triangulate(0x98, [0, 1, 2, 3, 4])),
            [(0, 1, 2), (2, 1, 3), (2, 3, 4)],
        )

    def test_parses_skinned_model_geometry(self):
        data = bytearray(0x140)
        struct.pack_into(">I", data, 0x14, 0x80)
        data[0x18] = 1
        struct.pack_into(">H", data, 0x1A, 1)
        struct.pack_into(">I", data, 0x1C, 0xA0)
        struct.pack_into(">I", data, 0x20, 0x80000000)
        data[0x28] = 1
        struct.pack_into(">H", data, 0x2A, 1)
        struct.pack_into(">I", data, 0x30, 0x60)
        struct.pack_into(">H", data, 0x38, 4)
        vertices = ((2, 4, 6, 0), (4, 4, 6, 0), (4, 6, 6, 0), (2, 6, 6, 0))
        for index, vertex in enumerate(vertices):
            struct.pack_into(">4h", data, 0x60 + index * 8, *vertex)
        data[0x80:0x88] = bytes((0, 0, 0, 1, 100, 0, 0, 0))
        data[0xAC] = 3
        struct.pack_into(">I", data, 0xB8, 35)
        struct.pack_into(">I", data, 0xBC, 2)
        data[0xC0] = 0x80
        struct.pack_into(">H", data, 0xC1, 4)
        for index in range(4):
            struct.pack_into(">4H", data, 0xC3 + index * 8, index, index, 0, 0)

        positions, palette, weights, indices, batches = MODULE.parse_geometry(data)
        self.assertEqual(positions[0], (1.0, 2.0, 3.0))
        self.assertEqual(palette, [0, 0, 0, 0])
        self.assertEqual(weights, [((0,), (100,))])
        self.assertEqual(indices, [0, 1, 2, 0, 2, 3])
        self.assertEqual(batches, [(0, 6, 3, 0)])

    def test_affine_inverse_round_trip(self):
        matrix = [0.0, -1.0, 0.0, 4.0,
                  1.0, 0.0, 0.0, -2.0,
                  0.0, 0.0, 1.0, 7.0]
        inverse = MODULE.affine_inverse(matrix)
        point = (2.0, 3.0, 5.0)
        transformed = MODULE.transform_point(matrix, point)
        restored = MODULE.transform_point(inverse, transformed)
        for actual, expected in zip(restored, point):
            self.assertAlmostEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
