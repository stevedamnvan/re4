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
        self.assertEqual(
            descriptor[6], TPL.FLAG_ALPHA | TPL.FLAG_BINARY_ALPHA
        )
        self.assertTrue(metadata["materials"][0]["binary_alpha"])
        self.assertEqual(metadata["texture_bytes"], 128)

    def test_source_mask_uses_alpha_not_intensity_and_preserves_legacy(self):
        color=TPL.TplImage(8,8,TPL.GX_TF_CMPR,struct.pack(">HH4B",0xf800,0x07e0,0,0,0,0)*4)
        mask=TPL.TplImage(8,8,TPL.GX_TF_IA8,bytes([0x80,0x40])*64)
        binding=[TPL.MaterialBinding("source",0,1)]
        def pixel(blob):
            h=TPL.HEADER.unpack_from(blob)
            t=TPL.TEXTURE.unpack_from(blob,h[5])
            return struct.unpack_from("<H",blob,t[4])[0]
        legacy,_=TPL.build_package([color,mask],binding)
        source,_=TPL.build_package([color,mask],binding,source_mask_alpha=True)
        self.assertEqual(pixel(legacy)>>12,4)
        self.assertEqual(pixel(source)>>12,8)
        self.assertEqual(pixel(legacy)&0xfff,pixel(source)&0xfff)
        i4=TPL.TplImage(8,8,TPL.GX_TF_I4,bytes([0xF8])*32)
        color=TPL.TplImage(8,8,TPL.GX_TF_CMPR,struct.pack(">HH4B",0xf800,0x07e0,0,0,0,0)*4)
        blob,meta=TPL.build_package([color,i4],binding,source_intensity_alpha=True,source_mask_alpha=True)
        self.assertFalse(meta['materials'][0]['binary_alpha'])
        h=TPL.HEADER.unpack_from(blob);t=TPL.TEXTURE.unpack_from(blob,h[5])
        self.assertEqual([v[0]>>12 for v in struct.iter_unpack("<H",blob[t[4]:t[4]+t[5]])][:2],[15,8])

    def test_argb4444_preserves_alpha_gradient(self):
        self.assertEqual(TPL._pack_4444((0x12, 0x34, 0x56, 0x78)), 0x7135)

    def test_gradient_alpha_is_not_marked_binary(self):
        color_block = struct.pack(">HH4B", 0xF800, 0x07E0, 0, 0, 0, 0) * 4
        alpha_block = bytes([0xF8]) * 32
        images = TPL.parse_tpl(make_tpl([
            (8, 8, TPL.GX_TF_CMPR, color_block),
            (8, 8, TPL.GX_TF_I4, alpha_block),
        ]))
        package, metadata = TPL.build_package(images, [
            TPL.MaterialBinding("ROOM_MATERIAL_000", 0, 1),
        ])
        values = TPL.HEADER.unpack_from(package)
        descriptor = TPL.TEXTURE.unpack_from(package, values[5])
        self.assertEqual(descriptor[6], TPL.FLAG_ALPHA)
        self.assertFalse(metadata["materials"][0]["binary_alpha"])

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

    def test_partial_alpha_above_half_is_not_opaque(self):
        image = TPL.TplImage(4, 4, TPL.GX_TF_IA8, bytes([0xCC, 0x80])*16)
        package, _ = TPL.build_package([image], [TPL.MaterialBinding("ui", 0, None)])
        h = TPL.HEADER.unpack_from(package)
        t = TPL.TEXTURE.unpack_from(package, h[5])
        self.assertEqual(t[3], TPL.FORMAT_ARGB4444)
        self.assertEqual(t[6], TPL.FLAG_ALPHA)

    def test_native_padding_preserves_texels_and_replicates_border(self):
        image = TPL.TplImage(3, 2, TPL.GX_TF_I8, bytes(range(32)))
        package, _ = TPL.build_package([image], [TPL.MaterialBinding("ui", 0, None)],
                                      pad_to_power_of_two=True)
        h = TPL.HEADER.unpack_from(package)
        t = TPL.TEXTURE.unpack_from(package, h[5])
        self.assertEqual(t[1:3], (8, 8))
        actual = struct.unpack_from("<64H", package, t[4])
        pixels = TPL.decode_image(image)
        expected = [TPL._pack_565(pixels[min(y,1)*3 + min(x,2)])
                    for y in range(8) for x in range(8)]
        self.assertEqual(list(actual), expected)

    def test_source_intensity_alpha_is_explicit(self):
        image = TPL.TplImage(8, 4, TPL.GX_TF_I8, bytes([0x88])*32)
        args = ([image], [TPL.MaterialBinding("ui", 0, None)])
        source, _ = TPL.build_package(*args, source_intensity_alpha=True)
        legacy, _ = TPL.build_package(*args)
        hs = TPL.HEADER.unpack_from(source)
        ts = TPL.TEXTURE.unpack_from(source, hs[5])
        tl = TPL.TEXTURE.unpack_from(legacy, hs[5])
        self.assertEqual(ts[3], TPL.FORMAT_ARGB4444)
        self.assertEqual(tl[3], TPL.FORMAT_RGB565)
        self.assertEqual(struct.unpack_from("<H", source, ts[4])[0], 0x8888)

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
