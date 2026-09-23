"""Built-in generators: thin, cached wrappers around the existing tools.

Every generator is a cache step: key = (params, input contents, tool fingerprint).
The wrapped tools are run unchanged as subprocesses with a deterministic
environment; their outputs are hashed and staged from the cache.
"""
import json
import shutil
import sys
from pathlib import Path

from .cache import fingerprint
from .config import TOOLS
from .util import run, det_env, write_json, dumps, parse_ranges

PY = sys.executable


def tool(name, tools_dir=None):
    return Path(tools_dir or TOOLS) / name


def converter_dir(cfg):
    """convert_room_bins.py to use: sources key `converter` (a tools dir), else the
    checkout's. W9b options need a converter that has them (see supports())."""
    d = cfg.src.get("converter") or ""
    return Path(d) if d else TOOLS


def supports(tools_dir, flag):
    return flag in (Path(tools_dir) / "convert_room_bins.py").read_text()


def converter_fp(tools_dir):
    return fingerprint([tool(n, tools_dir) for n in ("convert_room_bins.py", "mesh_lod.py", "room_smd.py")],
                       dict(python=sys.version.split()[0]))


class Gen:
    def __init__(self, cfg, cache):
        self.cfg, self.cache = cfg, cache
        self.kos = cfg.path("kos")
        self.pvrtex = self.kos / "utils/pvrtex/pvrtex" if self.kos else None

    # ---- pinned inputs (manual / Windows-side outputs, hashed by content)
    def pinned(self, key):
        p = self.cfg.path(key)
        if not p or not p.exists():
            raise FileNotFoundError("pinned input %s missing: %s" % (key, p))
        return p

    # ---- r100 placement scales (make_scales.py rule, from the reclaim placements)
    def scales(self, room):
        data = room.scales()

        def fn(out, work):
            (out / "scales.json").write_text(json.dumps(data, indent=0, sort_keys=True))
            return dict(bins=len(data))
        return self.cache.step("room.scales", dict(room=room.name, scales=data), {}, {"rule": "max|scale|/1"}, fn,
                               label="%s scales" % room.name)

    # ---- PS2 trees (ps2_trees.py) and bark (ps2_tree_texture.py)
    def ps2_trees(self, room):
        t = room.recipe["trees"]
        obj = Path(t["ps2_obj"])
        idx = obj.with_name(obj.name[:-len(".obj")] + ".idx_ps2_smd")
        args, inputs = ["--ps2-obj", obj, "--ps2-idx", idx, "--dc-uv"], dict(ps2_obj=obj, ps2_idx=idx)
        if room.kind == "export":
            args += ["--export", self.cfg.path("r100_export")]
            inputs["export_obj"] = self.cfg.path("r100_export") / "R100.allparts.obj"
        else:
            das = room.das_path()
            owner, bins = t["gc"].split(":")
            args += ["--room", das, "--gc-bins", bins, "--ps2-bins", t["ps2_bins"]]
            inputs["das"] = das
        fp = fingerprint([tool("ps2_trees.py"), tool("export_room_bins_obj.py"), tool("convert_room_bins.py")],
                         dict(python=sys.version.split()[0]))

        def fn(out, work):
            run([PY, "-B", tool("ps2_trees.py"), out] + args, cwd=work, log=work / "log.txt")
            return dict(objs=sorted(p.name for p in out.glob("*.obj")))
        return self.cache.step("tree.ps2", dict(room=room.name, gc=t["gc"], ps2_bins=t.get("ps2_bins")), inputs, fp,
                               fn, label="%s ps2 trees" % room.name)

    def ps2_bark(self, room):
        t = room.recipe["trees"]
        png = Path(t["bark_png"])
        exp = self.cfg.path("r100_export")
        fp = fingerprint([tool("ps2_tree_texture.py"), tool("convert_tpl.py"), self.pvrtex],
                         dict(python=sys.version.split()[0]))

        def fn(out, work):
            run([PY, "-B", tool("ps2_tree_texture.py"), png, work / "bark", "--export", exp, "--pvrtex", self.pvrtex],
                cwd=work, log=work / "log.txt")
            (out / "tex").mkdir()
            for f in sorted((work / "bark" / "tex").iterdir()):
                shutil.copy2(f, out / "tex" / f.name)
            prev = work / "bark" / "preview"
            if prev.exists():
                shutil.copytree(prev, out / "preview")
            return dict(key=t.get("bark_key"))
        return self.cache.step("texture.ps2bark", dict(room=room.name, key=t.get("bark_key")),
                               dict(png=png, gc_tpl=exp / "R100.TPL.TPL"), fp, fn, label="%s ps2 bark" % room.name)

    # ---- scenery packages (convert_room_bins.py)
    def package(self, room, owner, spec, scales_obj=None, substitutes=()):
        """One R4IM package. spec: dict(bias=[...], floor, share, classes=[...], class_auto,
        class_rules=[...]) in the converter's own argument forms."""
        conv = converter_dir(self.cfg)
        cm = self.cfg.cost["lod"]
        args = ["--owner", "0x%02x" % owner["code"] if owner["code"] >= 0xF0 else str(owner["code"])]
        inputs = {}
        if room.kind == "export":
            args += ["--bins", owner["dir"]]
            inputs["bins"] = owner["dir"]
            if owner["common"]:
                args.append("--common")
        else:
            args += ["--smd", owner["das"]]
            inputs["das"] = owner["das"]
        args += list(spec["lod_args"] if "lod_args" in spec else cm["lod_args"])
        if scales_obj is not None:
            args += ["--scales", scales_obj.path("scales.json")]
            inputs["scales"] = scales_obj
        for b in spec.get("bias", []):
            args += ["--lod-bias", b]
        w9b = []
        for f in spec.get("floor", []):
            w9b += ["--lod-floor", str(f)]
        if spec.get("share"):
            w9b.append("--lod-share")
        for c in spec.get("classes", []):
            w9b += ["--class", c]
        if spec.get("class_auto"):
            w9b.append("--class-auto")
        for r in spec.get("class_rules", []):
            w9b += ["--class-rule", r]
        if w9b and not supports(conv, "--lod-share"):
            raise RuntimeError("%s needs W9b converter options (%s); set RE4DC_SRC_CONVERTER to a tools dir "
                               "with w9b-scenery-share-classes.patch" % (room.name, " ".join(w9b[:2])))
        args += w9b
        for i, s in enumerate(substitutes):
            args += ["--lod-substitute", s.out if hasattr(s, "out") else s]
            inputs["subst%d" % i] = s
        name = owner["name"] + ".re4mesh"
        params = dict(room=room.name, owner=owner["name"], spec=spec, argv=[str(a) for a in args
                      if not str(a).startswith("/")])

        def fn(out, work):
            run([PY, "-B", tool("convert_room_bins.py", conv), out / name] + args, cwd=work, log=work / "log.txt")
            summary = json.loads(Path(str(out / name) + ".json").read_text())
            return {k: summary.get(k) for k in ("package_bytes", "meshes", "parts", "meshlets", "vertices",
                                                "clusters", "levels", "level0_triangles", "version",
                                                "replaced_bins", "substituted_parts", "sha256")}
        return self.cache.step("scenery.r4im", params, inputs, converter_fp(conv), fn,
                               label="%s %s" % (room.name, owner["name"]))

    # ---- texture VQ overlay (vq_native_ui.py, pinned pvrtex)
    def vq_overlay(self, logs, model_min_bytes=16384):
        fixtures = self.cfg.path("fixtures") / "tex"
        fp = fingerprint([tool("vq_native_ui.py"), tool("convert_tpl.py"), tool("prepare_native_ui.py"),
                          self.pvrtex], dict(python=sys.version.split()[0]))
        logs = sorted(Path(p) for p in logs)

        def fn(out, work):
            cmd = [PY, "-B", tool("vq_native_ui.py"), "--textures", fixtures]
            for lg in logs:
                cmd += ["--log", lg]
            cmd += ["--model-min-bytes", str(model_min_bytes), "--output", work / "vq", "--pvrtex", self.pvrtex,
                    "--previews", work / "previews"]
            run(cmd, cwd=work, log=work / "log.txt")
            for f in sorted((work / "vq").iterdir()):
                shutil.copy2(f, out / f.name)
            if (work / "previews").exists():
                shutil.copytree(work / "previews", out / "previews")
            rep = json.loads((out / "vq-native-ui-report.json").read_text())
            return dict(images=len(rep.get("images", rep)) if isinstance(rep, dict) else len(rep))
        return self.cache.step("texture.vq", dict(model_min_bytes=model_min_bytes, logs=[p.name for p in logs]),
                               dict(fixtures=fixtures, logs=logs), fp, fn, label="VQ overlay")

    # ---- audio (aica_banks.py; the same cache stage.sh uses)
    def audio(self, route="title,r100,r101,r103"):
        mirror = self.cfg.path("mirror")
        acache = self.cfg.path("aica_cache")
        fp = fingerprint([tool("aica_banks.py")], dict(python=sys.version.split()[0]))

        def fn(out, work):
            run([PY, "-B", tool("aica_banks.py"), "build", "--mirror", mirror, "--out", out / "overlay",
                 "--route", route, "--cache", acache, "--json", out / "aica-budget.json"], cwd=work,
                log=work / "log.txt")
            run([PY, "-B", tool("aica_banks.py"), "streams", "--mirror", mirror, "--out", out / "overlay"], cwd=work,
                log=work / "log-streams.txt")
            return dict(files=sum(1 for _ in (out / "overlay").rglob("*") if _.is_file()))
        return self.cache.step("audio.aica", dict(route=route), dict(mirror=mirror), fp, fn, label="audio banks")

    # ---- cutscene movies (convert_route_movies.py, ffmpeg pinned, single thread)
    def movie(self, name):
        import subprocess
        ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        iso = Path(self.cfg.src["ps2_iso"])
        fp = fingerprint([tool("convert_route_movies.py")], dict(ffmpeg=ver, python=sys.version.split()[0]))
        size = "288x192"

        def fn(out, work):
            drv = work / "drive.py"
            drv.write_text(MOVIE_DRIVER)
            run([PY, "-B", drv, str(TOOLS), str(out), name, size, str(iso)], cwd=work, log=work / "log.txt",
                env=det_env(dict(RE4DC_MOVIE_SIZE=size, RE4DC_MOVIE_RANGE="full")))
            return json.loads((out / name / "manifest.json").read_text())
        return self.cache.step("movie.fmv", dict(name=name, size=size, range="full"), dict(ps2_iso=iso), fp, fn,
                               label="movie %s" % name)


# convert_route_movies.py has fixed output/ISO paths and runs ffmpeg with 2 threads; the
# driver imports it unchanged, points OUT/ISO at the step's directories and forces
# -threads 1 so the MPEG-1 stream is reproducible.
MOVIE_DRIVER = r'''
import sys, pathlib
tools, out, name, size, iso = sys.argv[1:6]
sys.path.insert(0, tools)
sys.argv = [sys.argv[0]]
import convert_route_movies as M
M.OUT = pathlib.Path(out); M.ISO = pathlib.Path(iso)
orig = M.run
def run(*a):
    a = list(a)
    if a and a[0] == 'ffmpeg':
        if '-threads' in a:
            a[a.index('-threads') + 1] = '1'
        else:
            a[1:1] = ['-threads', '1']
        a[-1:-1] = ['-fflags', '+bitexact', '-flags', '+bitexact']   # output options
    return orig(*a)
M.run = run
M.OUT.mkdir(parents=True, exist_ok=True)
r = M.one(name, M.afs_index())
for p in (M.OUT / name).iterdir():
    if p.suffix in ('.sfd', '.m1v', '.pcm'):
        p.unlink()
'''
