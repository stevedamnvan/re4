import importlib.util
import pathlib
import struct
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "tools" / "convert_rtp.py"
SPEC = importlib.util.spec_from_file_location("convert_rtp", MODULE_PATH)
assert SPEC and SPEC.loader
convert_rtp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convert_rtp)


class ConvertRtpTests(unittest.TestCase):
    def make_source(self, path: pathlib.Path) -> None:
        points = [
            (1000.0, 0.0, 2000.0, 0, 1),
            (3000.0, 0.0, 2000.0, 1, 2),
            (3000.0, 0.0, 5000.0, 3, 1),
        ]
        links = [(1, 0), (0, 0), (2, 0), (1, 0)]
        next_hops = bytes([0, 1, 1, 0, 1, 2, 1, 1, 2])
        point_offset = convert_rtp.SOURCE_HEADER.size
        link_offset = point_offset + len(points) * convert_rtp.SOURCE_POINT.size
        next_offset = link_offset + len(links) * convert_rtp.SOURCE_LINK.size
        blob = convert_rtp.SOURCE_HEADER.pack(
            convert_rtp.SOURCE_MAGIC,
            0,
            len(points),
            b"\x00\xa0\x11\x04",
            point_offset,
            link_offset,
            next_offset,
        )
        blob += b"".join(convert_rtp.SOURCE_POINT.pack(*point) for point in points)
        blob += b"".join(convert_rtp.SOURCE_LINK.pack(*link) for link in links)
        blob += next_hops
        path.write_bytes(blob)

    def test_converts_big_endian_graph_and_scales_points(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "room.RTP"
            self.make_source(source)
            parsed = convert_rtp.parse_rtp(source)
            package, manifest = convert_rtp.build_package(parsed)
            self.assertEqual(parsed["points"][0][:3], (1.0, 0.0, 2.0))
            self.assertEqual(parsed["links"], [(1, 0), (0, 0), (2, 0), (1, 0)])
            self.assertEqual(parsed["next_hops"], bytes([0, 1, 1, 0, 1, 2, 1, 1, 2]))
            self.assertEqual(manifest["points"], 3)
            header = convert_rtp.HEADER.unpack_from(package)
            self.assertEqual(header[0], convert_rtp.MAGIC)
            self.assertEqual(header[5:8], (3, 4, 9))

    def test_rejects_invalid_next_hop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "room.RTP"
            self.make_source(source)
            data = bytearray(source.read_bytes())
            next_offset = convert_rtp.SOURCE_HEADER.unpack_from(data)[6]
            data[next_offset] = 3
            source.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "invalid point"):
                convert_rtp.parse_rtp(source)


if __name__ == "__main__":
    unittest.main()
