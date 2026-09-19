import importlib.util
import json
import pathlib
import struct
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "tools" / "convert_sat.py"
SPEC = importlib.util.spec_from_file_location("convert_sat", SCRIPT)
SAT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = SAT
SPEC.loader.exec_module(SAT)


def make_sat() -> bytes:
    vertices = [(0.0, 0.0, 0.0), (200.0, 0.0, 0.0), (0.0, 0.0, 200.0), (0.0, 200.0, 0.0)]
    normals = [(0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]
    edges = [(0.0, 0.0, 0.0)] * 6
    polygons = [
        (0, 2, 1, 0, 0, 1, 2, 0xE0000000),
        (0, 3, 2, 1, 3, 4, 5, 0x20000000),
    ]
    section = bytearray(SAT.SAT_HEADER.pack(0x20, 0, 4, 2, 6, 0, 2, 1, 0, 1, 0))
    for vector in vertices + normals + edges:
        section.extend(SAT.SAT_VECTOR.pack(*vector))
    for polygon in polygons:
        section.extend(SAT.SAT_POLYGON.pack(*polygon))
    return bytes((0x80, 1, 0xFF, 0x79)) + struct.pack(">I", 8) + section


class ConvertSatTests(unittest.TestCase):
    def test_container_is_scaled_and_packaged_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "fixture.SAT"
            first = root / "first.re4sat"
            second = root / "second.re4sat"
            source.write_bytes(make_sat())

            self.assertEqual(SAT.main([str(source), str(first)]), 0)
            self.assertEqual(SAT.main([str(source), str(second)]), 0)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            values = SAT.HEADER.unpack_from(first.read_bytes())
            self.assertEqual(values[0], SAT.MAGIC)
            self.assertEqual(values[1], SAT.VERSION)
            self.assertEqual(values[6:12], (4, 2, 2, 1, 0, 1))
            vertex_offset = values[12]
            self.assertEqual(SAT.VECTOR.unpack_from(first.read_bytes(), vertex_offset + SAT.VECTOR.size), (2.0, 0.0, 0.0))
            manifest = json.loads(first.with_suffix(".re4sat.json").read_text())
            self.assertEqual(manifest["polygons"], 2)
            self.assertEqual(manifest["bounds"]["max"], [2.0, 2.0, 2.0])

    def test_rejects_inconsistent_polygon_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "bad.SAT"
            data = bytearray(make_sat())
            struct.pack_into(">H", data, 8 + 12, 0)
            source.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "do not match"):
                SAT.parse_sat(source)

    def test_rejects_invalid_section_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "fixture.SAT"
            source.write_bytes(make_sat())
            with self.assertRaisesRegex(ValueError, "out of range"):
                SAT.parse_sat(source, 1)


if __name__ == "__main__":
    unittest.main()
