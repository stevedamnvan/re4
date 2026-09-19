#!/usr/bin/env python3
"""Create or validate immutable RE4 Dreamcast evidence manifests."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


SCHEMA = "re4dc-evidence-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_manifest(root: Path, output: Path, platform: str, run_id: str,
                    files: list[Path], identity: dict[str, object]) -> dict:
    root = root.resolve()
    output = output.resolve()
    entries = []
    for supplied in files:
        path = supplied.resolve()
        if not path.is_file():
            raise ValueError(f"evidence input is not a file: {path}")
        try:
            relative = path.relative_to(output.parent).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"evidence file must be beneath the manifest directory: {path}"
            ) from exc
        entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    entries.sort(key=lambda entry: entry["path"])
    return {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_git_sha": git_head(root),
        "platform": platform,
        "run_id": run_id,
        "identity": identity,
        "files": entries,
    }


def validate_manifest(path: Path) -> list[str]:
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if data.get("schema") != SCHEMA:
        errors.append("unexpected schema")
    if not data.get("source_git_sha"):
        errors.append("missing source_git_sha")
    if not data.get("run_id"):
        errors.append("missing run_id")
    if not isinstance(data.get("identity"), dict):
        errors.append("identity must be an object")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty array")
        return errors
    seen = set()
    for entry in files:
        relative = entry.get("path", "")
        if not relative or relative in seen:
            errors.append(f"invalid or duplicate path: {relative!r}")
            continue
        seen.add(relative)
        candidate = (path.parent / relative).resolve()
        try:
            candidate.relative_to(path.parent)
        except ValueError:
            errors.append(f"path escapes manifest directory: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"missing file: {relative}")
            continue
        if candidate.stat().st_size != entry.get("bytes"):
            errors.append(f"size mismatch: {relative}")
        if sha256(candidate) != entry.get("sha256"):
            errors.append(f"hash mismatch: {relative}")
    return errors


def parse_identity(values: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"identity must be KEY=VALUE: {value}")
        key, item = value.split("=", 1)
        if not key or key in result:
            raise ValueError(f"invalid or duplicate identity key: {key!r}")
        result[key] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--repo", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--platform", choices=("dolphin", "flycast", "dreamcast"), required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--identity", action="append", default=[], metavar="KEY=VALUE")
    create.add_argument("files", type=Path, nargs="+")
    validate = sub.add_parser("validate")
    validate.add_argument("manifest", type=Path)
    args = parser.parse_args()

    if args.command == "create":
        result = create_manifest(
            args.repo, args.output, args.platform, args.run_id, args.files,
            parse_identity(args.identity),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(args.output)
        return 0

    errors = validate_manifest(args.manifest)
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print(f"OK: {args.manifest}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
