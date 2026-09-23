"""Optional editor topology identity must not alter the normal converter path."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
ROOT = pathlib.Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("room_editor_indices", ROOT / "tools/convert_room_obj.py")
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)

class EditorSourceIndicesTests(unittest.TestCase):
    def test_seams_and_negative_indices_keep_source_identity_without_changing_package(self):
        obj = """v 0 0 0
v 1 0 0
v 0 1 0
vt 0 0
vt 1 0
vt 0 1
vt .5 .5
vn 0 0 1
g FILE_01#SMD_1#SMX_2#BIN_3#
usemtl surface
f 1/1/1 2/2/1 3/3/1
f -3/4/1 -2/2/1 -1/3/1
"""
        with tempfile.TemporaryDirectory() as temp:
            p = pathlib.Path(temp) / "fixture.obj"
            p.write_text(obj)
            ordinary = C.parse_obj(p)
            editing = C.parse_obj(p, retain_source_indices=True)
        self.assertNotIn("vertex_source_indices", ordinary)
        self.assertEqual(editing["vertex_source_indices"], [(0, 0, 0), (1, 1, 0), (2, 2, 0), (0, 3, 0)])
        self.assertEqual(ordinary["vertices"], editing["vertices"])
        self.assertEqual(C.build_package(ordinary)[0], C.build_package(editing)[0])

if __name__ == "__main__":
    unittest.main()
