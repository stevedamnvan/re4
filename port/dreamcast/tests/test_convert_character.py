import importlib.util
import math
from pathlib import Path
import struct
from types import SimpleNamespace
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
        struct.pack_into(">I", data, 0x34, 0x120)
        struct.pack_into(">H", data, 0x38, 4)
        struct.pack_into(">H", data, 0x3A, 4)
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
            struct.pack_into(">3hH", data, 0x120 + index * 8,
                             0, 16384, 0, 0)

        (positions, palette, weights, source_normals, normal_palettes,
         draw_sources, draw_normals, normal_count, texcoords, indices,
         batches, bindings, primitive_indices, primitives,
         batch_primitive_ranges) = MODULE.parse_geometry(data)
        self.assertEqual(positions[0], (1.0, 2.0, 3.0))
        self.assertEqual(palette, [0, 0, 0, 0])
        self.assertEqual(weights, [((0,), (100,))])
        self.assertEqual(source_normals, [(0, 16384, 0)] * 4)
        self.assertEqual(normal_palettes, [0, 0, 0, 0])
        self.assertEqual(draw_sources, [0, 1, 2, 3])
        self.assertEqual(draw_normals, [0, 1, 2, 3])
        self.assertEqual(normal_count, 4)
        self.assertEqual(texcoords[3], (0.75, 0.375))
        self.assertEqual(indices, [0, 1, 2, 0, 2, 3])
        self.assertEqual(batches, [(0, 6, 3, 0)])
        self.assertEqual(primitive_indices, [0, 1, 2, 3])
        self.assertEqual(primitives, [(0, 0, 4, 6, 0x80)])
        self.assertEqual(batch_primitive_ranges, [(0, 1)])
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

    def test_attachment_spec_and_frame_sampling(self):
        self.assertEqual(
            MODULE.parse_clip("aim:wep02.drs:0x27"),
            ("aim", "wep02.drs", 0x27, None),
        )
        self.assertEqual(
            MODULE.parse_clip("aim-up:wep02.drs:0x28:16"),
            ("aim-up", "wep02.drs", 0x28, 16),
        )
        with self.assertRaises(MODULE.argparse.ArgumentTypeError):
            MODULE.parse_clip("aim-up:wep02.drs:0x28:0")
        self.assertEqual(
            MODULE.parse_attachment("hair:pl00.drs:2:3"),
            ("hair", "pl00.drs", 2, "pl00.drs", 3),
        )
        self.assertEqual(
            MODULE.parse_attachment(
                "right-hand:wep02.drs:6:pl00.drs:13"
            ),
            ("right-hand", "wep02.drs", 6, "pl00.drs", 13),
        )
        self.assertEqual(
            MODULE.parse_rigid_attachment("handgun:wep02.drs:2:1:10"),
            ("handgun", "wep02.drs", 2, 1, 10, (0.0, 0.0, 0.0), 0.0),
        )
        self.assertEqual(
            MODULE.parse_rigid_attachment(
                "hatchet:em12.drs:616:617:10:-313.85:-21.2:102.21:-1.0402162"
            ),
            (
                "hatchet", "em12.drs", 616, 617, 10,
                (-313.85, -21.2, 102.21), -1.0402162,
            ),
        )
        self.assertEqual(
            MODULE.parse_rigid_marker(
                "axe-tip:10:-313.85:-21.2:102.21:-1.0402162:0:0:50"
            ),
            (
                "axe-tip", 10, (-313.85, -21.2, 102.21), -1.0402162,
                (0.0, 0.0, 50.0),
            ),
        )
        self.assertEqual(
            MODULE.parse_rigid_marker(
                "pl-hit3-bottom:18:0:0:0:0:-20:-300:0"
            ),
            (
                "pl-hit3-bottom", 18, (0.0, 0.0, 0.0), 0.0,
                (-20.0, -300.0, 0.0),
            ),
        )
        self.assertEqual(MODULE.sampled_frame_indices(7, 2), [0, 2, 4, 6])
        self.assertEqual(MODULE.sampled_frame_indices(8, 3), [0, 3, 6, 7])
        self.assertAlmostEqual(
            MODULE.sampled_frames_per_second([0, 3, 6, 7], 7, 30.0),
            90.0 / 7.0,
        )

    def test_rigid_attachment_applies_source_yaw_then_translation(self):
        point = MODULE.transform_rigid_point(
            (100.0, 20.0, 0.0), (10.0, -5.0, 30.0), math.pi * 0.5
        )
        self.assertAlmostEqual(point[0], 10.0)
        self.assertAlmostEqual(point[1], 15.0)
        self.assertAlmostEqual(point[2], -70.0)

    def test_extracts_source_root_motion_speed(self):
        def axis(start, end):
            return SimpleNamespace(keys=[(start,), (end,)])

        motion = SimpleNamespace(
            max_frame=60,
            joints=[SimpleNamespace(
                kind=1,
                parts_no=0,
                axes=[axis(0.0, 0.0), axis(0.0, 0.0), axis(100.0, 3100.0)],
            )],
        )
        self.assertAlmostEqual(
            MODULE.root_forward_speed_mps(motion, 30.0), 1.5
        )

    def test_weight_palette_reuses_source_remainder_and_quantises_pose(self):
        def translated(x, y, z):
            return [
                1.0, 0.0, 0.0, x,
                0.0, 1.0, 0.0, y,
                0.0, 0.0, 1.0, z,
            ]

        pose = SimpleNamespace(mat=[
            translated(10.0, 0.0, 0.0),
            translated(0.0, 20.0, 0.0),
            translated(0.0, 0.0, 30.0),
        ])
        palette = MODULE.make_weight_palette(
            pose,
            [(0.0, 0.0, 0.0)] * 3,
            [((0, 1, 2), (20, 30, 0))],
        )
        # The source assigns the remainder to the final influence: 20/30/50.
        self.assertEqual(
            MODULE.skin_frame([(1.0, 2.0, 3.0)], [0], palette)[0],
            (3.0, 8.0, 18.0),
        )
        packed, maximum_linear_error = MODULE.quantise_pose_matrices([palette])
        self.assertEqual(len(packed), MODULE.POSE_MATRIX.size)
        self.assertEqual(maximum_linear_error, 0.0)
        maximum_position_error, exact, compared = (
            MODULE.pose_matrix_position_error(
                [palette], [(1.0, 2.0, 3.0, 0)],
                [[(3.0, 8.0, 18.0)]], 0.25
            )
        )
        self.assertEqual(maximum_position_error, 0.0)
        self.assertEqual((exact, compared), (1, 1))

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
