import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "tools" / "evidence_manifest.py"
SPEC = importlib.util.spec_from_file_location("evidence_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EvidenceManifestTests(unittest.TestCase):
    def make_repo(self, root: Path):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)

    def test_manifest_detects_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.make_repo(root)
            evidence = root / "evidence"
            evidence.mkdir()
            frame = evidence / "frame.bin"
            frame.write_bytes(b"reference-frame")
            manifest_path = evidence / "manifest.json"
            manifest = MODULE.create_manifest(
                root,
                manifest_path,
                "flycast",
                "fixture-run",
                [frame],
                {"room": "r100", "tick": "42"},
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(MODULE.validate_manifest(manifest_path), [])
            frame.write_bytes(b"changed-frame")
            errors = MODULE.validate_manifest(manifest_path)
            self.assertTrue(any("mismatch" in error for error in errors))

    def test_rejects_file_outside_manifest_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            self.make_repo(root)
            evidence = root / "evidence"
            evidence.mkdir()
            outside = root / "outside.bin"
            outside.write_bytes(b"outside")
            with self.assertRaisesRegex(ValueError, "beneath"):
                MODULE.create_manifest(
                    root, evidence / "manifest.json", "dolphin", "fixture", [outside], {}
                )


if __name__ == "__main__":
    unittest.main()
