import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "tools" / "convert_tpl.py"
SPEC = importlib.util.spec_from_file_location("convert_tpl", SCRIPT)
TPL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = TPL
SPEC.loader.exec_module(TPL)


def make_tpl(images):
    count = len(images)
    table_offset = 12
    header_offset = table_offset + count * 8
    data_offset = header_offset + count * 36
    output = bytearray(struct.pack(">III", TPL.TPL_MAGIC, count, table_offset))
    for index in range(count):
        output.extend(struct.pack(">II", header_offset + index * 36, 0))
    payload = bytearray()
    for index, (width, height, image_format, data) in enumerate(images):
        output.extend(struct.pack(">HHIIIIIIfBBBB", height, width, image_format,
                                  data_offset + len(payload), 0, 0, 0, 0, 0.0,
                                  0, 0, 0, 0))
        payload.extend(data)
    output.extend(payload)
    return bytes(output)


class ConvertTplTests(unittest.TestCase):
    def test_box_downsample_averages_rgba_channels(self):
        pixels = [
            (0, 0, 0, 0), (100, 0, 0, 100),
            (0, 100, 0, 200), (0, 0, 100, 255),
        ]
        result, width, height = TPL.downsample_box(pixels, 2, 2)
        self.assertEqual((width, height), (1, 1))
        self.assertEqual(result, [(25, 25, 25, 138)])

    def test_i4_block_decodes_high_nibble_first(self):
        image = TPL.TplImage(8, 8, TPL.GX_TF_I4, bytes([0xF0]) + bytes(31))
        pixels = TPL.decode_i4(image)
        self.assertEqual(pixels[0], (255, 255, 255, 255))
        self.assertEqual(pixels[1], (0, 0, 0, 255))

    def test_ia8_block_decodes_alpha_then_intensity(self):
        image = TPL.TplImage(
            4, 4, TPL.GX_TF_IA8, bytes((0x80, 0x40)) + bytes(30)
        )
        pixels = TPL.decode_ia8(image)
        self.assertEqual(pixels[0], (0x40, 0x40, 0x40, 0x80))

    def test_i8_and_ia4_blocks_decode_gamecube_tiles(self):
        i8 = TPL.TplImage(8, 4, TPL.GX_TF_I8, bytes([0x41]) + bytes(31))
        self.assertEqual(TPL.decode_i8(i8)[0], (0x41, 0x41, 0x41, 255))
        ia4 = TPL.TplImage(8, 4, TPL.GX_TF_IA4, bytes([0xA3]) + bytes(31))
        self.assertEqual(TPL.decode_ia4(ia4)[0], (0x33, 0x33, 0x33, 0xAA))

    def test_c4_and_c8_use_rgb5a3_palette(self):
        palette = struct.pack(">HH", 0xFFFF, 0x7123)
        c4 = TPL.TplImage(
            8, 8, TPL.GX_TF_C4, bytes([0x10]) + bytes(31),
            TPL.GX_TL_RGB5A3, palette,
        )
        self.assertEqual(TPL.decode_indexed(c4)[0], (0x11, 0x22, 0x33, 255))
        self.assertEqual(TPL.decode_indexed(c4)[1], (255, 255, 255, 255))
        c8 = TPL.TplImage(
            8, 4, TPL.GX_TF_C8, bytes([1]) + bytes(31),
            TPL.GX_TL_RGB5A3, palette,
        )
        self.assertEqual(TPL.decode_indexed(c8)[0], (0x11, 0x22, 0x33, 255))

    def test_rgba8_block_decodes_split_ar_and_gb_planes(self):
        block = bytearray(64)
        block[0:2] = bytes((0x80, 0x40))
        block[32:34] = bytes((0x20, 0x10))
        image = TPL.TplImage(4, 4, TPL.GX_TF_RGBA8, bytes(block))
        pixels = TPL.decode_rgba8(image)
        self.assertEqual(pixels[0], (0x40, 0x20, 0x10, 0x80))

    def test_cmpr_subblocks_and_selector_order(self):
        subblock = struct.pack(">HH4B", 0xF800, 0x07E0, 0x1B, 0, 0, 0)
        image = TPL.TplImage(8, 8, TPL.GX_TF_CMPR, subblock * 4)
        pixels = TPL.decode_cmpr(image)
        self.assertEqual(pixels[0][:3], (255, 0, 0))
        self.assertEqual(pixels[1][:3], (0, 255, 0))
        self.assertEqual(pixels[8 * 4][:3], (255, 0, 0))
        self.assertEqual(pixels[4][:3], (255, 0, 0))

    def test_builds_deterministic_material_pack_with_alpha(self):
        color_block = struct.pack(">HH4B", 0xF800, 0x07E0, 0, 0, 0, 0) * 4
        alpha_block = bytes([0xF0]) * 32
        source = make_tpl([
            (8, 8, TPL.GX_TF_CMPR, color_block),
            (8, 8, TPL.GX_TF_I4, alpha_block),
        ])
        images = TPL.parse_tpl(source)
        bindings = TPL.parse_mtl(
            "newmtl ROOM_MATERIAL_000\n"
            "map_Kd folder/room-0.png\n"
            "map_d folder/room-1.png\n"
        )
        first, metadata = TPL.build_package(images, bindings)
        second, _ = TPL.build_package(images, bindings)
        self.assertEqual(first, second)
        values = TPL.HEADER.unpack_from(first)
        self.assertEqual(values[0], TPL.MAGIC)
        self.assertEqual(values[4], 1)
        descriptor = TPL.TEXTURE.unpack_from(first, values[5])
        self.assertEqual(descriptor[1:4], (8, 8, TPL.FORMAT_ARGB4444))
        self.assertEqual(descriptor[6], TPL.FLAG_ALPHA)
        self.assertEqual(metadata["texture_bytes"], 128)

    def test_argb4444_preserves_alpha_gradient(self):
        self.assertEqual(TPL._pack_4444((0x12, 0x34, 0x56, 0x78)), 0x7135)

    def test_reuses_identical_texture_payloads_across_materials(self):
        color_block = struct.pack(">HH4B", 0xF800, 0x07E0, 0, 0, 0, 0) * 4
        images = TPL.parse_tpl(make_tpl([(8, 8, TPL.GX_TF_CMPR, color_block)]))
        package, metadata = TPL.build_package(images, [
            TPL.MaterialBinding("PART_000", 0, None),
            TPL.MaterialBinding("PART_001", 0, None),
        ])
        values = TPL.HEADER.unpack_from(package)
        first = TPL.TEXTURE.unpack_from(package, values[5])
        second = TPL.TEXTURE.unpack_from(package, values[5] + TPL.TEXTURE.size)
        self.assertEqual(first[4:6], second[4:6])
        self.assertEqual(metadata["texture_bytes"], 128)

    def test_cli_writes_private_package_and_manifest(self):
        color_block = struct.pack(">HH4B", 0xF800, 0x07E0, 0, 0, 0, 0) * 4
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            tpl_path = root / "room.tpl"
            mtl_path = root / "room.mtl"
            output = root / "room.re4tex"
            tpl_path.write_bytes(make_tpl([(8, 8, TPL.GX_TF_CMPR, color_block)]))
            mtl_path.write_text(
                "newmtl ROOM_MATERIAL_000\nmap_Kd room/room-0.png\n",
                encoding="utf-8",
            )
            self.assertEqual(TPL.main([str(tpl_path), str(mtl_path), str(output)]), 0)
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".re4tex.json").is_file())


if __name__ == "__main__":
    unittest.main()
