"""Vendored tools the asset pipeline runs before their own lane item lands in the checkout.

Each file is a byte-for-byte copy of a file from a delivered (not yet committed) lane patch.
generators.item_tool() uses the checkout's copy (tools/<path>) once it exists, else this one.
When the lane item is committed, delete the copy here and its row below. tests/test_assetpipe.py
checks that every vendored file still matches its recorded sha256 (never edit them here).
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

# vendored name -> (path in the checkout once landed, source patch, sha256 of the file)
FILES = {
    "bl_house_shell.py": ("blender/bl_house_shell.py",
                          "ps2-blender/item21-house-shells.patch (sha256 1ecedfdd05e3...)",
                          "3d3a492c3388f97d12177801519484a3812e99cd31644d76e5520c601a1f2b2b"),
    "house_shells.py": ("house_shells.py",
                        "ps2-blender/item21-house-shells.patch (sha256 1ecedfdd05e3...)",
                        "cfd9b6848c67521af6f33403c68f950c23b994b201da9ca7891a4a8d06b3c388"),
    # item 20: impostor.py imports its kPal4 packaging (package_pal4) for the rooms without a pinned bake
    "tree_impostors.py": ("tree_impostors.py",
                          "ps2-blender/item20-tree-impostor.patch (sha256 7e9e4d622679...)",
                          "485de043a954271faf06fad31ddccb77ea6f8d62164420cf7d14e18257fd02ce"),
}
