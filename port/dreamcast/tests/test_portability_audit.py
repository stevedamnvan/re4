import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "tools" / "portability_audit.py"
SPEC = importlib.util.spec_from_file_location("portability_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PortabilityAuditTests(unittest.TestCase):
    def test_classifies_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "include").mkdir()
            (root / "src" / "fixture.cpp").write_text(
                '#include <dolphin/gx.h>\n'
                'void f(void* p) { GXBegin(0, 0, 3); auto n = (u32)p; }\n'
                'asm("mr r3,r4");\n'
                'auto address = 0x80350000;\n',
                encoding="utf-8",
            )
            result = MODULE.audit(root)
            categories = result["categories"]
            self.assertEqual(result["scanned_files"], 1)
            self.assertEqual(categories["sdk_headers"]["matches"], 1)
            self.assertEqual(categories["gx_api"]["matches"], 1)
            self.assertEqual(categories["gx_api"]["file_counts"]["src/fixture.cpp"], 1)
            self.assertEqual(categories["ppc_assembly"]["matches"], 1)
            self.assertEqual(categories["fixed_gc_addresses"]["matches"], 1)
            self.assertEqual(categories["pointer_to_u32"]["matches"], 1)

    def test_current_tree_exposes_known_port_boundaries(self):
        root = Path(__file__).parents[3]
        result = MODULE.audit(root)
        self.assertGreater(result["scanned_files"], 900)
        for category in (
            "sdk_headers",
            "gx_api",
            "os_api",
            "rel_modules",
            "ppc_assembly",
            "fixed_gc_addresses",
        ):
            self.assertGreater(result["categories"][category]["matches"], 0, category)


if __name__ == "__main__":
    unittest.main()
