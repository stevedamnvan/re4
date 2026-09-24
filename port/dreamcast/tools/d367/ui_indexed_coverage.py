#!/usr/bin/env python3
"""Write a synthetic run log naming every indexed (C4/C8) native UI image, for the VQ step.

ui_indexed_coverage.py --report <native-ui-report.json> --fixtures <tex dir> --output <x-run-output.txt>

vq_native_ui.py (assets.sh texture.vq) only re-encodes images that some run log shows being loaded
("native UI: load <path> WxH fmt=N"). An image no scripted run ever opened stayed 16-bit: the r101
scope overlay (st1/r101.arc#35, 256x224 C4, 128 KiB padded) was first loaded in a user's play session,
found no contiguous block in a fragmented pool and locked the game. This log lists every indexed image
in the prepare_native_ui report whose package exists in the fixtures, so VQ selection covers all of
them (vq_native_ui applies its own size and side limits). Put the output in sources.toml ui_logs.
Private inputs and output: nothing produced here belongs in Git.
"""
from __future__ import annotations

import argparse
import json
import pathlib


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--report", type=pathlib.Path, required=True)
    ap.add_argument("--fixtures", type=pathlib.Path, required=True, help="native package dir (<key>.re4tex)")
    ap.add_argument("--output", type=pathlib.Path, required=True, help="*run-output.txt in the ui_logs dir")
    a = ap.parse_args()
    have = {p.name[:17] for p in a.fixtures.glob("*.re4tex")}
    lines, seen, missing = [], set(), []
    for e in json.loads(a.report.read_text())["entries"]:
        key = e["key"]
        if e.get("format") not in (8, 9) or key in seen:
            continue
        seen.add(key)
        if key not in have:
            missing.append(key)
            continue
        lines.append("native UI: load /cd/dc/tex/%s/%s.re4tex %dx%d fmt=%d  (%s)"
                     % (key[0], key, e["width"], e["height"], e["format"], e["context"]))
    a.output.write_text("# ui_indexed_coverage.py: every indexed (C4/C8) image of %s\n%s\n"
                        % (a.report.name, "\n".join(lines)))
    print("%d indexed images, %d without a package in %s" % (len(lines), len(missing), a.fixtures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
