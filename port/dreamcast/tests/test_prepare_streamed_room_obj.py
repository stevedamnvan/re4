import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "tools" / "prepare_streamed_room_obj.py"
SPEC = importlib.util.spec_from_file_location("prepare_streamed_room_obj", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

class PrepareStreamedRoomObjTests(unittest.TestCase):
    def test_restores_shared_texture_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            bins = root / "bins"
            bins.mkdir()
            model = bytearray(0x60 + 12)
            struct.pack_into(">H", model, 0x1A, 1)
            struct.pack_into(">I", model, 0x1C, 0x40)
            model[0x4B] = 0x04
            model[0x4C] = 32
            model[0x4E] = 33
            struct.pack_into(">II", model, 0x58, 12, 1)
            (bins / "0004.BIN").write_bytes(model)
            mtl = root / "room.mtl"
            mtl.write_text(
                "newmtl ROOM_MATERIAL_014\n"
                "map_Kd R100.TPL/R100.TPL-32.png\n"
                "map_d R100.TPL/R100.TPL-33.png\n", encoding="utf-8")
            obj = root / "room.obj"
            obj.write_text(
                "mtllib room.mtl\n"
                "v 0 0 0\nv 1 0 0\nv 0 0 1\n"
                "vt 0 0\nvt 1 0\nvt 0 1\n"
                "vn 0 1 0\n"
                "g FILE_01#SMD_000#SMX_004#TYPE_08#BIN_004#\n"
                "usemtl UNKNOWN_MATERIAL\n"
                "f 1/1/1 2/2/1 3/3/1\n", encoding="utf-8")
            output = root / "prepared.obj"
            self.assertEqual(MODULE.main([
                str(obj), str(mtl), str(output),
                "--bin-root", f"FILE_01={bins}",
                "--include-prefix", "FILE_01",
                "--center-x", "0", "--center-z", "0", "--radius", "2",
            ]), 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("usemtl ROOM_MATERIAL_014", text)
            self.assertNotIn("UNKNOWN_MATERIAL", text)

if __name__ == "__main__":
    unittest.main()
