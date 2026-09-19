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
        struct.pack_into(">I", data, 0x10, 0x100)
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
            struct.pack_into(">4H", data, 0xC3 + index * 8, index, index, 0, index)
            struct.pack_into(">2h", data, 0x100 + index * 4,
                             index * 64, index * 32)

        (positions, palette, weights, draw_sources, texcoords, indices, batches,
         bindings) = MODULE.parse_geometry(data)
        self.assertEqual(positions[0], (1.0, 2.0, 3.0))
        self.assertEqual(palette, [0, 0, 0, 0])
        self.assertEqual(weights, [((0,), (100,))])
        self.assertEqual(draw_sources, [0, 1, 2, 3])
        self.assertEqual(texcoords[3], (0.75, 0.375))
        self.assertEqual(indices, [0, 1, 2, 0, 2, 3])
        self.assertEqual(batches, [(0, 6, 3, 0)])
        self.assertEqual(bindings[0].name, "PART_000")
        self.assertEqual(bindings[0].color_image, 3)

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

    def test_clusters_every_animation_frame_and_removes_degenerate_faces(self):
        positions = [
            (0.0, 0.0, 0.0),
            (0.1, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ]
        indices = [0, 2, 3, 0, 1, 3]
        batches = [(0, 6, 2, 7)]
        texcoords = [(0.0, 0.0)] * 4
        frames = [positions, [(x + 1.0, y, z) for x, y, z in positions]]
        result = MODULE.cluster_animated_geometry(
            positions, texcoords, indices, batches, frames, 0.5
        )
        new_positions, new_texcoords, new_indices, new_batches, new_frames = result
        self.assertEqual(len(new_positions), 3)
        self.assertEqual(len(new_texcoords), 3)
        self.assertEqual(len(new_indices), 3)
        self.assertEqual(new_batches, [(0, 3, 2, 7)])
        self.assertEqual(len(new_frames), 2)
        self.assertAlmostEqual(new_positions[0][0], 0.05)
        self.assertAlmostEqual(new_frames[1][0][0], 1.05)


if __name__ == "__main__":
    unittest.main()
