"""Enemy placement conversion against the source EmListData consumer layout."""
import pathlib
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / 'tools'))
import le_mirror as LE


class EnemyListTest(unittest.TestCase):
    def setUp(self):
        LE.REPORT.clear()

    def convert(self, source):
        data = bytearray(source)
        LE.convert_file('etc/emleon00.esl', data)
        return data, LE.REPORT[-1]

    def test_native_fields_and_source_room_eligibility(self):
        # Synthetic source records, including inactive and maximal slot values.
        # The numeric source fields and byte-only fields are checked separately.
        source = bytearray()
        for i in range(256):
            source += struct.pack('>4BIH2B6hHh4s', i & 15, 0x12, 3, 0x1b,
                                  0x24000100 + i, 1000 + i, i, 7,
                                  -8395 + i, 83, -3296, 0, 3, -32768,
                                  0x100 if i % 2 else 0x120, -200, b'KEEP')
        data, report = self.convert(source)
        self.assertTrue(report['complete'])
        for i in range(256):
            p = i * 32
            self.assertEqual(struct.unpack_from('>4BIH2B6hHh4s', source, p),
                             struct.unpack_from('<4BIH2B6hHh4s', data, p))
            room = struct.unpack_from('<H', data, p + 24)[0]
            self.assertEqual((room >> 8, room & 255), (1, 0 if i % 2 else 0x20))
            for a, b in ((0, 4), (10, 12), (28, 32)):
                self.assertEqual(source[p+a:p+b], data[p+a:p+b])

    def test_255_record_file_does_not_grow_into_extra_source_slot(self):
        data, report = self.convert(bytes(255 * 32))
        self.assertEqual(len(data), 8160)
        self.assertTrue(report['complete'])

    def test_invalid_extents_rejected_without_mutation(self):
        for n in (0, 31, 33, 8161, 8193, 8224):
            with self.subTest(size=n):
                source = bytes((i & 255 for i in range(n)))
                data, report = self.convert(source)
                self.assertIn('invalid ESL', report['error'])
                self.assertEqual(data, source)
                with tempfile.TemporaryDirectory() as d:
                    deps = pathlib.Path(d) / 'required.txt'
                    deps.write_text('etc/emleon00.esl\n')
                    self.assertTrue(LE.check_required([report], deps))

    def test_bounded_embedded_extent_preserves_neighbors(self):
        source = bytearray(b'L' * 32 + bytes(32) + b'R' * 32)
        report = {}
        LE.guarded(LE.Swapper(source, 'fixture'), LE.fmt_esl, 32, 32, 'fixture', report)
        self.assertTrue(report['complete'])
        self.assertEqual(source[:32], b'L' * 32)
        self.assertEqual(source[64:], b'R' * 32)


if __name__ == '__main__':
    unittest.main()
