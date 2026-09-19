#!/usr/bin/env python3
"""Deterministic inventory of source constructs that need Dreamcast treatment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


PATTERNS = {
    "sdk_headers": re.compile(r"#\s*include\s*[<\"]dolphin/"),
    "gx_api": re.compile(r"\bGX[A-Z][A-Za-z0-9_]*\s*\("),
    "gx_fifo": re.compile(r"GXWGFifo|wgPipe|0xCC008000", re.IGNORECASE),
    "os_api": re.compile(r"\bOS[A-Z][A-Za-z0-9_]*\s*\("),
    "dvd_aram_api": re.compile(r"\b(?:DVD|ARQ)[A-Z][A-Za-z0-9_]*"),
    "card_api": re.compile(r"\bCARD[A-Z][A-Za-z0-9_]*"),
    "rel_modules": re.compile(r"\b(?:OSLink|OSUnlink|OSModuleHeader)\b|\.rel\b", re.IGNORECASE),
    "ppc_assembly": re.compile(r"\basm\s*(?:volatile\s*)?[({]"),
    "register_pins": re.compile(r"\basm\s*\(\s*[\"']r\d+"),
    "fixed_gc_addresses": re.compile(r"\b0x8[0-2][0-9A-Fa-f]{6}\b"),
    "pointer_to_u32": re.compile(r"\(\s*u32\s*\)\s*(?:[A-Za-z_]|\()"),
}

SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hpp"}
SOURCE_DIRS = ("src", "include")


def iter_source_files(root: Path):
    for dirname in SOURCE_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
                yield path


def audit(root: Path) -> dict:
    root = root.resolve()
    categories = {
        name: {"matches": 0, "files": 0, "file_counts": {}, "locations": []}
        for name in PATTERNS
    }
    scanned_files = 0
    for path in iter_source_files(root):
        scanned_files += 1
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for name, pattern in PATTERNS.items():
            file_matches = 0
            for number, line in enumerate(lines, 1):
                hits = list(pattern.finditer(line))
                if not hits:
                    continue
                file_matches += len(hits)
                if len(categories[name]["locations"]) < 100:
                    categories[name]["locations"].append(
                        {"path": relative, "line": number, "text": line.strip()[:240]}
                    )
            if file_matches:
                categories[name]["files"] += 1
                categories[name]["matches"] += file_matches
                categories[name]["file_counts"][relative] = file_matches
    return {
        "schema": "re4dc-portability-audit-v1",
        "root": str(root),
        "scanned_files": scanned_files,
        "categories": categories,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", type=Path, dest="json_path")
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    for name, values in result["categories"].items():
        print(f"{name}: {values['matches']} matches in {values['files']} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
