import importlib.util
import json
import pathlib
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
