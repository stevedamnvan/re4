#!/usr/bin/env python3
"""D367 whole-game asset pipeline: formula-driven, cached, deterministic.

  assets.sh [build] <room|route|all> [--mode standard|low] [--plan recipe|solve] [--only CLASS]
            [--override FILE] [--verify] [--no-review]
  assets.sh rooms | inventory <room> | plan <room> | review <room> | stage-env <rooms> | calibrate

Design, formulas and formats: port/dreamcast/docs/D367_ASSET_PIPELINE.md. Private
inputs/outputs live under RE4DC_ASSETS_ROOT (default /root/probe/d367-agents/assets).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assetpipe.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
