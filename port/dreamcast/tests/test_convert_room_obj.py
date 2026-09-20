import importlib.util
import json
import pathlib
import struct
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "tools" / "convert_room_obj.py"
SPEC = importlib.util.spec_from_file_location("convert_room_obj", SCRIPT)
ROOM = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ROOM
SPEC.loader.exec_module(ROOM)


OBJ = """\
v 0 0 0
v 2 0 0
v 2 0 2
v 0 0 2
vn 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
g floor
usemtl stone
f 1/1/1 2/2/1 3/3/1 4/4/1
g marker
usemtl red
f -4/1/1 -3/2/1 -2/3/1
"""


class ConvertRoomObjTests(unittest.TestCase):
    def test_deterministic_package_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "room.obj"
            first = root / "first.re4room"
            second = root / "second.re4room"
            source.write_text(OBJ, encoding="utf-8")

            self.assertEqual(ROOM.main([str(source), str(first)]), 0)
            self.assertEqual(ROOM.main([str(source), str(second)]), 0)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            values = ROOM.HEADER.unpack_from(first.read_bytes())
            self.assertEqual(values[0], ROOM.MAGIC)
            self.assertEqual(values[1], ROOM.VERSION)
            self.assertEqual(values[8:13], (4, 9, 2, 2, 2))
            manifest = json.loads(first.with_suffix(".re4room.json").read_text())
            self.assertEqual(manifest["triangles"], 3)
            self.assertEqual(
                manifest["bounds"],
                {"min": [0.0, 0.0, 0.0], "max": [2.0, 0.0, 2.0]},
            )

    def test_source_scale_converts_export_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "room.obj"
            output = root / "scaled.re4room"
            source.write_text(OBJ, encoding="utf-8")
            self.assertEqual(
                ROOM.main([str(source), str(output), "--source-scale", "0.1"]), 0
            )
            manifest = json.loads(output.with_suffix(".re4room.json").read_text())
            self.assertEqual(manifest["source_scale"], 0.1)
            self.assertEqual(manifest["bounds"]["max"], [0.2, 0.0, 0.2])

    def test_appends_source_smx_group_metadata(self):
        source_text = OBJ.replace("g floor", "g FILE_01#SMX_007#").replace(
            "g marker", "g FILE_01#SMX_254#"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "room.obj"
            smx = root / "room.smx"
            output = root / "room.re4room"
            source.write_text(source_text, encoding="utf-8")
            smx_data = bytearray(0x10 + ROOM.SMX_WORK_SIZE)
            smx_data[0] = 0x10
            smx_data[1] = 1
            struct.pack_into("4B", smx_data, 0x10, 7, 4, 5, 2)
            struct.pack_into(">I", smx_data, 0x14, 0xF0F0AA55)
            struct.pack_into(">I", smx_data, 0x18, 0x12345678)
            smx.write_bytes(smx_data)

            self.assertEqual(
                ROOM.main([str(source), str(output), "--smx", str(smx)]), 0
            )
            package = output.read_bytes()
            header = ROOM.HEADER.unpack_from(package)
            self.assertEqual(header[19], ROOM.FLAG_SOURCE_GROUP_METADATA)
            metadata_offset = header[17] + header[9] * ROOM.INDEX.size
            first = ROOM.SOURCE_GROUP.unpack_from(package, metadata_offset)
            second = ROOM.SOURCE_GROUP.unpack_from(
                package, metadata_offset + ROOM.SOURCE_GROUP.size
            )
            self.assertEqual(first[:7], (0xF0F0AA55, 7, 4, 5, 2, 0x12345678, 0))
            self.assertEqual(second[:7], (0xFFFFFFFF, 254, 0, 3, 0, 0, 0))
            self.assertEqual(first[7:13], (0.0,) * 6)
            self.assertEqual(first[13:], (1.0, 0.0, 0.0,
                                           0.0, 1.0, 0.0,
                                           0.0, 0.0, 1.0))
            manifest = json.loads(output.with_suffix(".re4room.json").read_text())
            self.assertEqual(manifest["source_group_metadata"], 2)
            self.assertEqual(manifest["source_cull_modes"], {"0": 1, "2": 1})

    def test_recovers_source_box_light_volume(self):
        data = bytearray(0xC0)
        data[0] = 0x40
        struct.pack_into(">H", data, 2, 1)
        struct.pack_into(">I", data, 4, 0x60)
        struct.pack_into(">9f4B", data, 0x10,
                         10.0, 20.0, 30.0,
                         0.0, 0.0, 0.0,
                         2.0, 3.0, 4.0,
                         0, 0, 255, 7)
        struct.pack_into(">I", data, 0x54, 0)
        struct.pack_into(">I", data, 0x60, 4)
        model = 0x64
        struct.pack_into(">I", data, model + 0x30, 0x48)
        struct.pack_into(">H", data, model + 0x38, 2)
        data[model + 0x28] = 0
        struct.pack_into(">4h", data, model + 0x48, -1, -2, -3, 0)
        struct.pack_into(">4h", data, model + 0x50, 1, 2, 3, 0)
        with tempfile.TemporaryDirectory() as directory:
            smd = pathlib.Path(directory) / "placed.smd"
            smd.write_bytes(data)
            name = "FILE_01#SMD_000#SMX_007#TYPE_08#BIN_000#"
            source = {name: ROOM.SourceGroupData(0xFFFFFFFF, 7, 0, 3, 2, 0)}
            result = ROOM.add_source_light_volumes(
                source, {"FILE_01": smd}, None, 0.001
            )[name]
            self.assertEqual(result.metadata_flags,
                             ROOM.SOURCE_GROUP_HAS_LIGHT_VOLUME)
            self.assertEqual(result.light_center, (0.01, 0.02, 0.03))
            self.assertEqual(result.light_size, (0.002, 0.006, 0.012))
            self.assertEqual(result.inverse_rotation,
                             (1.0, 0.0, 0.0,
                              0.0, 1.0, 0.0,
                              0.0, 0.0, 1.0))

    def test_rejects_out_of_range_index(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "bad.obj"
            source.write_text("v 0 0 0\nf 1 2 3\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "out of range"):
                ROOM.parse_obj(source)

    def test_spatial_partition_preserves_triangles(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "room.obj"
            source.write_text(OBJ, encoding="utf-8")
            parsed = ROOM.parse_obj(source)
            ROOM.spatial_partition(parsed, 1.0)
            self.assertEqual(sum(len(batch.indices) for batch in parsed["batches"]), 9)
            self.assertEqual(parsed["source_groups"], 2)
            self.assertEqual(parsed["cell_size"], 1.0)

    def test_spatial_partition_retains_source_group_metadata(self):
        source_text = OBJ.replace("g floor", "g FILE_01#SMX_007#").replace(
            "g marker", "g FILE_01#SMX_008#"
        )
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "room.obj"
            source.write_text(source_text, encoding="utf-8")
            parsed = ROOM.parse_obj(source)
            source_groups = {
                name: ROOM.SourceGroupData(
                    1 << index, 7 + index, index, 3, 2, index
                )
                for index, name in enumerate(parsed["group_order"])
            }
            result = ROOM.spatial_partition(
                parsed, 1.0, source_groups, {"red"}
            )
            self.assertEqual(
                sum(len(batch.indices) for batch in parsed["batches"]), 9
            )
            self.assertEqual(len(result), len(parsed["group_order"]))
            self.assertEqual(
                {record.source_id for record in result.values()}, {7, 8}
            )
            self.assertEqual(parsed["source_groups"], 2)
            self.assertEqual(parsed["source_child_groups"], len(result))
            self.assertTrue(any(
                name.endswith("_unpartitioned")
                for name in parsed["group_order"]
            ))

    def test_vertex_cluster_lod_drops_degenerate_triangle(self):
        source_text = """\
v 0 0 0
v 0.1 0 0
v 0 0 2
v 2 0 0
vn 0 1 0
g floor
usemtl stone
f 1//1 2//1 3//1
f 1//1 3//1 4//1
"""
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "lod.obj"
            source.write_text(source_text, encoding="utf-8")
            parsed = ROOM.parse_obj(source)
            ROOM.cluster_geometry(parsed, 0.5)
            self.assertEqual(parsed["cluster_source_triangles"], 2)
            self.assertEqual(parsed["triangles"], 1)
            self.assertEqual(len(parsed["vertices"]), 3)


if __name__ == "__main__":
    unittest.main()
