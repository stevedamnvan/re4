"""Offline decoder checks; optional private-disc goldens never enter the repo."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/decode_yz2.py'
spec = importlib.util.spec_from_file_location('decode_yz2', TOOL)
yz2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yz2)


class DecoderValidation(unittest.TestCase):
    def test_rejects_bad_header_before_running_tools(self):
        for payload in [b'', b'garbage', b'10 0\n'+bytes(64),
                        b'10 2000001\n'+bytes(64), b'100 20\n'+bytes(32)]:
            with self.subTest(payload=payload[:20]), self.assertRaises(ValueError):
                yz2.decode(payload)

    @unittest.skipUnless(os.environ.get('RE4_PRIVATE_DATA') and
                         shutil.which('qemu-ppc') and
                         shutil.which('powerpc-linux-gnu-gcc'),
                         'set RE4_PRIVATE_DATA and install offline PPC tools')
    def test_private_room_archives(self):
        goldens = {
            'r100': (4669568, '8cb4cbd4f7f85f925c76703405d0f164891cf068dc6e815d0a842fccdd3146dc', 51),
            'r101': (5466016, '8d2161f73f2359874c885a755722f06118de05c3423fb86147f54517c5b30d15', 37),
            'r120': (6086688, '8c39abc0499273d8f516bf03f5e1c806a10472176c0e7feca7330a9d9f26d6a9', 13),
        }
        for room, (size, digest, count) in goldens.items():
            with self.subTest(room=room):
                data = (Path(os.environ['RE4_PRIVATE_DATA'])/'st1'/(room+'.das')).read_bytes()
                kind, packed, _, offset = struct.unpack_from('>4I', data, 32)
                self.assertEqual(kind, 0)
                out = yz2.decode(data[offset:offset+packed])
                self.assertEqual((len(out), hashlib.sha256(out).hexdigest()), (size, digest))
                self.assertEqual(struct.unpack_from('>I', out)[0], count)
                offsets = struct.unpack_from('>'+str(count)+'I', out, 16)
                self.assertEqual(list(offsets), sorted(offsets))
                self.assertTrue(all(16+8*count <= x < len(out) for x in offsets))
                tags = out[16+4*count:16+8*count]
                self.assertEqual(tags[:4], b'CAM\0')
                self.assertIn(b'LIT\0', tags)


if __name__ == '__main__':
    unittest.main()