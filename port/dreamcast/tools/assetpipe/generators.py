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

    # ---- a replacement directory without some <OWNER>_<bin>.obj (e.g. planar2 minus the shelled houses)
    def subst_without(self, src, exclude):
        src_dir = Path(src.out if hasattr(src, "out") else src)
        exclude = sorted(set(exclude))

        def fn(out, work):
            kept = []
            for f in sorted(src_dir.iterdir()):
                if f.is_file() and f.stem not in exclude:
                    shutil.copy2(f, out / f.name)
                    kept.append(f.name)
            return dict(kept=len(kept), excluded=exclude)
        return self.cache.step("subst.filter", dict(exclude=exclude), dict(src=src), {"rule": "copy minus exclude"},
                               fn, label="subst %s minus %s" % (src_dir.name, ",".join(exclude)))

    # ---- decoded room TPL (convert_tpl.decode_image -> RGBA PNG <index>.png; deterministic)
    def tpl_png(self, room):
        from . import texture
        tpl_path = self.cfg.path("r100_export") / "R100.TPL.TPL" if room.kind == "export" else None
        if tpl_path is None:
            raise NotImplementedError("tpl_png: %s (smd rooms: TPL from the room archive, step d)" % room.name)
        fp = fingerprint([tool("convert_tpl.py")], dict(python=sys.version.split()[0]))

        def fn(out, work):
            imgs = texture.tpl_images(tpl_path, TOOLS)
            for i, im in enumerate(imgs):
                (out / ("%d.png" % i)).write_bytes(texture.png_rgba_bytes(im))
            return dict(images=len(imgs))
        return self.cache.step("texture.tpl_png", dict(room=room.name), dict(tpl=tpl_path), fp, fn,
                               label="%s TPL -> PNG" % room.name)

    # ---- source BINs as OBJ (export_room_bins_obj.py: model space, one material per part)
    def bin_objs(self, room, keys):
        if room.kind != "export":
            raise NotImplementedError("bin_objs: %s (smd rooms arrive with step d)" % room.name)
        exp = self.cfg.path("r100_export")
        keys = sorted(keys)
        fp = fingerprint([tool("export_room_bins_obj.py"), tool("convert_room_bins.py"), tool("mesh_lod.py")],
                         dict(python=sys.version.split()[0]))
        inputs = {}
        for k in keys:
            owner, b = k.rsplit("_", 1)
            d = {"MAINSCENARIO": "R100.FILE_MAIN", "COMMON": "R100.FILE_SHARED"}.get(
                owner, "R100.FILE_%d" % int(owner[5:]) if owner.startswith("FILE_") else owner)
            inputs[k] = exp / d / ("%04d.BIN" % int(b))

        def fn(out, work):
            run([PY, "-B", tool("export_room_bins_obj.py"), out, "--export", exp, "--keys", ",".join(keys)],
                cwd=work, log=work / "log.txt")
            return dict(objs=sorted(p.name for p in out.glob("*.obj")))
        return self.cache.step("scenery.bin_obj", dict(room=room.name, keys=keys), inputs, fp, fn,
                               label="%s BIN OBJ %s" % (room.name, ",".join(keys)))

    # ---- Blender reductions (tools/blender/bl_decimate.py: planar dissolve / collapse, normals kept)
    def decimate(self, room, keys, variant, ops):
        """Whole-BIN replacement OBJs <out>/<KEY>.obj (+ blender-report.json) for convert_room_bins.py
        --lod-substitute. ops: [["planar", deg] | ["collapse", ratio], ...]."""
        import os
        import subprocess
        blender = Path(self.cfg.src["blender"])
        bwork = Path(self.cfg.src["blender_work"])
        keys = sorted(keys)
        objs = self.bin_objs(room, keys)
        st = blender.stat()
        script = tool("blender/bl_decimate.py")
        fp = fingerprint([script], dict(blender="%s:%d:%d" % (blender.name, st.st_size, int(st.st_mtime))))
        spec = {variant: dict(keys=keys, ops=[list(o) for o in ops])}

        def win(p):
            return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True,
                                  check=True).stdout.strip()

        def fn(out, work):
            w = bwork / ("decimate-%s-%d" % (variant, os.getpid()))
            if w.exists():
                shutil.rmtree(w)
            (w / "in").mkdir(parents=True)
            for k in keys:
                shutil.copy2(objs.path(k + ".obj"), w / "in" / (k + ".obj"))
            shutil.copy2(script, w / "bl_decimate.py")
            (w / "spec.json").write_text(json.dumps(spec, indent=1, sort_keys=True))
            try:
                run([blender, "-b", "--factory-startup", "--python", win(w / "bl_decimate.py"), "--",
                     win(w / "in"), win(w / "out"), win(w / "spec.json")], cwd=w, log=work / "blender.txt",
                    timeout=7200)
                for f in sorted((w / "out" / variant).glob("*.obj")):
                    shutil.copy2(f, out / f.name)
                rep = json.loads((w / "out" / "blender-report.json").read_text())
                (out / "blender-report.json").write_text(json.dumps(rep, indent=1, sort_keys=True))
            finally:
                shutil.rmtree(w, ignore_errors=True)
            return dict(objs=len(keys))
        return self.cache.step("scenery.decimate", dict(room=room.name, variant=variant, spec=spec),
                               dict(objs=objs), fp, fn, label="%s decimate %s (%d BINs)" % (room.name, variant,
                                                                                           len(keys)))

    # ---- house shells (item 21: Blender bl_house_shell.py + house_shells.py VQ packaging)
    def house_shell(self, room, key, faces, tex_size=512, extra=()):
        """One baked low-poly render shell for BIN `key` (e.g. FILE_01_17). Blender 5.2 (Windows) runs
        on copies in sources [paths] blender_work; Cycles CPU bake, fixed seeds (bl_house_shell.py).
        Outputs: <key>.obj/.png/.json (Blender), replace/<key>.obj, tex/<crc>-<fnv>.re4tex,
        preview/<key>.png (as pvrtex decodes it), textures.json (house_shells.py)."""
        import os
        import subprocess
        ext = self.pinned("item2x_tools")
        blender = Path(self.cfg.src["blender"])
        bwork = Path(self.cfg.src["blender_work"])
        objs = self.bin_objs(room, [key])
        tpl = self.tpl_png(room)
        st = blender.stat()
        fp = fingerprint([ext / "blender/bl_house_shell.py", ext / "house_shells.py", tool("convert_tpl.py"),
                          self.pvrtex], dict(python=sys.version.split()[0],
                                             blender="%s:%d:%d" % (blender.name, st.st_size, int(st.st_mtime))))
        args = ["--keep-alpha", "--cull-hidden", "--faces", str(int(faces)), "--tex-size", str(int(tex_size))]
        args += [str(a) for a in extra]

        def win(p):
            return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True,
                                  check=True).stdout.strip()

        def fn(out, work):
            w = bwork / ("%s-%d" % (key, os.getpid()))
            if w.exists():
                shutil.rmtree(w)
            (w / "tex").mkdir(parents=True)
            (w / "out").mkdir()
            shutil.copy2(objs.path(key + ".obj"), w / (key + ".obj"))
            for f in sorted(tpl.out.glob("*.png")):
                shutil.copy2(f, w / "tex" / f.name)
            shutil.copy2(ext / "blender/bl_house_shell.py", w / "bl_house_shell.py")
            try:
                run([blender, "-b", "--factory-startup", "--python", win(w / "bl_house_shell.py"), "--",
                     win(w / (key + ".obj")), win(w / "tex"), win(w / "out")] + args, cwd=w, log=work / "blender.txt",
                    timeout=3600)
                shells = work / "shells"
                shells.mkdir()
                for suf in (".obj", ".png", ".json"):
                    shutil.copy2(w / "out" / (key + suf), shells / (key + suf))
                    shutil.copy2(w / "out" / (key + suf), out / (key + suf))
            finally:
                shutil.rmtree(w, ignore_errors=True)
            run([PY, "-B", ext / "house_shells.py", work / "pkg", shells, "--pvrtex", self.pvrtex], cwd=work,
                log=work / "log.txt", env=det_env(dict(PYTHONPATH=str(TOOLS))))
            for d in ("replace", "tex", "preview"):
                shutil.copytree(work / "pkg" / d, out / d)
            shutil.copy2(work / "pkg" / "textures.json", out / "textures.json")
            m = json.loads((out / (key + ".json")).read_text())
            return {k: m.get(k) for k in ("source_triangles", "shell_triangles", "alpha_triangles",
                                          "hidden_faces_removed", "source_to_shell_cm", "shell_to_source_cm")}
        return self.cache.step("house.shell", dict(room=room.name, key=key, args=args),
                               dict(obj=objs, tpl=tpl), fp, fn, label="%s shell %s %d faces" % (room.name, key, faces))

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
