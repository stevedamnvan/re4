"""Configuration: costmodel.toml, sources.toml, rooms.toml, plugins.toml.

Sources: RE4DC_SRC_<KEY> overrides a key; "${key}" expands another key.
The private root is RE4DC_ASSETS_ROOT (default sources.toml assets_root).
"""
import copy
import os
import re
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent                      # port/dreamcast/tools
REPO_DC = TOOLS.parent                   # port/dreamcast


def _load(name):
    p = HERE / name
    return tomllib.loads(p.read_text()) if p.exists() else {}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Config:
    def __init__(self, costmodel=None):
        self.cost = _load("costmodel.toml")
        if costmodel:
            self.cost = _merge(self.cost, tomllib.loads(Path(costmodel).read_text()))
        src = _load("sources.toml")
        self.rooms_cfg = _load("rooms.toml")
        self.plugins_cfg = _load("plugins.toml")
        flat = {}
        for section in ("paths", "pinned"):
            for k, v in src.get(section, {}).items():
                flat[k] = os.environ.get("RE4DC_SRC_" + k.upper(), v)
        if "RE4DC_ASSETS_ROOT" in os.environ:
            flat["assets_root"] = os.environ["RE4DC_ASSETS_ROOT"]
        self.src = {k: self.expand(v, flat) for k, v in flat.items()}
        self.root = Path(self.src["assets_root"])

    @staticmethod
    def expand(value, table, depth=0):
        if not isinstance(value, str) or depth > 8:
            return value

        def sub(m):
            return str(Config.expand(table.get(m.group(1), ""), table, depth + 1))
        return re.sub(r"\$\{([a-z0-9_]+)\}", sub, value)

    def path(self, key):
        v = self.src.get(key, "")
        return Path(v) if v else None

    def room(self, name):
        """Room recipe: [defaults] merged with [room.<name>], ${key} expanded."""
        d = _merge(self.rooms_cfg.get("defaults", {}), self.rooms_cfg.get("room", {}).get(name, {}))

        def ex(v):
            if isinstance(v, str):
                return self.expand(v, self.src)
            if isinstance(v, dict):
                return {k: ex(x) for k, x in v.items()}
            if isinstance(v, list):
                return [ex(x) for x in v]
            return v
        d = ex(d)
        d["name"] = name
        return d

    def route(self):
        return list(self.rooms_cfg.get("route", {}).get("rooms", []))

    def budgets(self, mode):
        return dict(self.cost.get("budgets", {}).get(mode, {}))

    def c(self, section, key, default=None):
        return self.cost.get(section, {}).get(key, default)

    def cost_hash_view(self):
        """The cost model as it enters cache keys and manifests."""
        return self.cost
