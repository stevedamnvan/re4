"""Built-in generators: thin, cached wrappers around the existing tools.

Every generator is a cache step: key = (params, input contents, tool fingerprint).
The wrapped tools are run unchanged as subprocesses with a deterministic
environment; their outputs are hashed and staged from the cache.
"""
import json
import os
import shutil
import sys
from pathlib import Path

from .cache import fingerprint
from .config import TOOLS
from .util import run, det_env, write_json, dumps, parse_ranges

PY = sys.executable


def tool(name, tools_dir=None):
    return Path(tools_dir or TOOLS) / name


def item_tool(name):
    """A lane tool the pipeline runs: the checkout's copy once its lane item has landed,
    else the vendored copy (assetpipe/vendor; see its FILES table)."""
    from .vendor import FILES, HERE
    rel = FILES[name][0]
    p = Path(TOOLS) / rel
    return p if p.exists() else HERE / name


def converter_dir(cfg, room=None):
    """convert_room_bins.py to use: sources key `converter` (a tools dir), else the
    checkout's. W9b options need a converter that has them (see supports()). A room with
    `w9b = false` (r100: its accepted packages predate W9b) always uses the checkout's, so
    setting the key for r101/r103 does not change r100's bytes."""
    if room is not None and not room.recipe.get("w9b", True):
        return TOOLS
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
        conv = converter_dir(self.cfg, room)
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
        # split groves (s16.5): per-tree clusters for these BINs ("0xff:13-17"; owner_filter keeps this owner's)
        for c in spec.get("cluster_trees", []):
            args += ["--lod-cluster-trees", c]
        if spec.get("cluster_trees") and not supports(conv, "--lod-cluster-trees"):
            raise RuntimeError("%s: grove_split needs a converter with --lod-cluster-trees (HEAD, or the W9b "
                               "converter with w9b-lod-cluster-trees.patch)" % room.name)
        subst_dirs = []
        for i, s in enumerate(substitutes):
            subst_dirs.append(Path(s.out if hasattr(s, "out") else s))
            inputs["subst%d" % i] = s
        name = owner["name"] + ".re4mesh"
        params = dict(room=room.name, owner=owner["name"], spec=spec, argv=[str(a) for a in args
                      if not str(a).startswith("/")], substitutes=len(subst_dirs))

        def fn(out, work):
            # substitutes are linked into the work dir, so the converter's report names
            # $WORK/subst<i>, not another step's cache location (which changes with that
            # step's key even when its content does not)
            sub = []
            for i, d in enumerate(subst_dirs):
                w = work / ("subst%d" % i)
                w.mkdir()
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        os.link(f, w / f.name) if os.stat(f).st_dev == os.stat(work).st_dev else shutil.copy2(f, w / f.name)
                sub += ["--lod-substitute", w]
            run([PY, "-B", tool("convert_room_bins.py", conv), out / name] + args + sub, cwd=work,
                log=work / "log.txt")
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

    # ---- the room's scenery TPL (BIN part texture byte = image index)
    def room_tpl(self, room):
        """r100: the export's R100.TPL. SMD rooms: TPL 0 of the SMD's own TPL table (every r101 /
        r103 placement has tplNo 0 and no common flag); cached as <room>.tpl."""
        if room.kind == "export":
            return self.cfg.path("r100_export") / "R100.TPL.TPL"
        das = room.das_path()
        fp = fingerprint([tool("room_smd.py")], dict(python=sys.version.split()[0]))

        def fn(out, work):
            import struct
            sys.path.insert(0, str(TOOLS))
            import room_smd
            smd, e = room_smd.load_smd(das)
            sm = room_smd.Smd(smd, e)
            tpls = {p["tpl"] for p in sm.used() if not p["common"]}
            if tpls != {0}:
                raise ValueError("%s: placements use TPLs %s; only TPL 0 is handled" % (room.name, sorted(tpls)))
            base = sm.tables[1]
            start = base + struct.unpack_from(e + "I", smd, base)[0]
            later = [t for t in sm.tables if t > base]
            (out / (room.name + ".tpl")).write_bytes(smd[start:min(later) if later else len(smd)])
            return dict(bytes=(out / (room.name + ".tpl")).stat().st_size)
        obj = self.cache.step("texture.room_tpl", dict(room=room.name), dict(das=das), fp, fn,
                              label="%s SMD TPL 0" % room.name)
        return obj.path(room.name + ".tpl")

    # ---- decoded room TPL (convert_tpl.decode_image -> RGBA PNG <index>.png; deterministic)
    def tpl_png(self, room):
        from . import texture
        tpl_path = self.room_tpl(room)
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
        keys = sorted(keys)
        fp = fingerprint([tool("export_room_bins_obj.py"), tool("convert_room_bins.py"), tool("mesh_lod.py")],
                         dict(python=sys.version.split()[0]))
        if room.kind != "export":
            das = room.das_path()

            def fn_smd(out, work):
                run([PY, "-B", tool("export_room_bins_obj.py"), out, "--smd", das, "--keys", ",".join(keys)],
                    cwd=work, log=work / "log.txt")
                return dict(objs=sorted(p.name for p in out.glob("*.obj")))
            return self.cache.step("scenery.bin_obj", dict(room=room.name, keys=keys), dict(das=das), fp, fn_smd,
                                   label="%s BIN OBJ %d BINs" % (room.name, len(keys)))
        exp = self.cfg.path("r100_export")
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
        fp = fingerprint([script], dict(blender="%s:%d:%d" % (blender.name, st.st_size, int(st.st_mtime)),
                                        blender_threads="1"))
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
                run([blender, "-b", "--threads", "1", "--factory-startup", "--python", win(w / "bl_decimate.py"), "--",
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
        preview/<key>.png (as pvrtex decodes it), textures.json (house_shells.py).
        Every Blender step runs with --threads 1: with the default (one per CPU) the same shell comes
        out with a different vertex order on a machine with a different core count (measured
        2026-09-23)."""
        import os
        import subprocess
        shell_py, pack_py = item_tool("bl_house_shell.py"), item_tool("house_shells.py")
        blender = Path(self.cfg.src["blender"])
        bwork = Path(self.cfg.src["blender_work"])
        objs = self.bin_objs(room, [key])
        tpl = self.tpl_png(room)
        st = blender.stat()
        fp = fingerprint([shell_py, pack_py, tool("convert_tpl.py"),
                          self.pvrtex], dict(python=sys.version.split()[0], blender_threads="1",
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
            shutil.copy2(shell_py, w / "bl_house_shell.py")
            try:
                run([blender, "-b", "--threads", "1", "--factory-startup", "--python", win(w / "bl_house_shell.py"), "--",
                     win(w / (key + ".obj")), win(w / "tex"), win(w / "out")] + args, cwd=w, log=work / "blender.txt",
                    timeout=3600)
                shells = work / "shells"
                shells.mkdir()
                for suf in (".obj", ".png", ".json"):
                    shutil.copy2(w / "out" / (key + suf), shells / (key + suf))
                    shutil.copy2(w / "out" / (key + suf), out / (key + suf))
            finally:
                shutil.rmtree(w, ignore_errors=True)
            run([PY, "-B", pack_py, work / "pkg", shells, "--pvrtex", self.pvrtex], cwd=work,
                log=work / "log.txt", env=det_env(dict(PYTHONPATH=str(TOOLS))))
            for d in ("replace", "tex", "preview"):
                shutil.copytree(work / "pkg" / d, out / d)
            shutil.copy2(work / "pkg" / "textures.json", out / "textures.json")
            m = json.loads((out / (key + ".json")).read_text())
            return {k: m.get(k) for k in ("source_triangles", "shell_triangles", "alpha_triangles",
                                          "hidden_faces_removed", "source_to_shell_cm", "shell_to_source_cm")}
        return self.cache.step("house.shell", dict(room=room.name, key=key, args=args),
                               dict(obj=objs, tpl=tpl), fp, fn, label="%s shell %s %d faces" % (room.name, key, faces))

    # ---- empty-level guard (Standard): a baked bias must not make objects vanish nearer than Original
    def vanish_guard(self, room, owner, pkg_obj, vmin):
        """Copy of package step `pkg_obj` (owner `owner`) whose empty LOD levels (no meshlets: the
        object draws nothing there) store at least vmin[(bin, common)] as their error. The runtime
        picks the coarsest level with err x scale x K / zmin <= px, so an empty level's error sets
        the vanish distance, and a Standard bias scales it down with every other level (r103 fence
        panels: 18 m in Original, 1.8 m in Standard before this guard). Only those floats change."""
        name = owner + ".re4mesh"
        vm = sorted((b, bool(c), float("%.6g" % v)) for (b, c), v in vmin.items())
        here = Path(__file__).resolve().parent

        def fn(out, work):
            import hashlib
            import struct
            from . import r4im
            data = bytearray(pkg_obj.path(name).read_bytes())
            pk = r4im.Package(bytes(data))
            llo = r4im.LOD_HEADER.unpack_from(data, r4im.HEADER.size)[4]
            want = {(b, c): v for b, c, v in vm}
            changed = 0
            for (b, c), k in sorted(pk.mesh_by_bin().items()):
                v = want.get((b, c))
                if v is None:
                    continue
                for p in pk.mesh_parts(k):
                    fc, nc = pk.part_lod[p]
                    for cl in pk.clusters[fc:fc + nc]:
                        for li in range(cl[6], cl[6] + cl[7]):
                            f, cnt, err = pk.levels[li]
                            if cnt == 0 and err < v:
                                struct.pack_into("<f", data, llo + 12 * li + 8, v)
                                changed += 1
            (out / name).write_bytes(bytes(data))
            summary = json.loads(Path(str(pkg_obj.path(name)) + ".json").read_text())
            summary["sha256"] = hashlib.sha256(bytes(data)).hexdigest()
            summary["vanish_guard_levels"] = changed
            (out / (name + ".json")).write_text(json.dumps(summary, sort_keys=True))
            info = dict(pkg_obj.info)
            info.update(sha256=summary["sha256"], vanish_guard_levels=changed)
            return info
        return self.cache.step("scenery.vanish_guard", dict(room=room.name, owner=owner, vmin=vm),
                               # the summary JSON is an input too: two bias specs can give the same package
                               # bytes (a one-level BIN) with different summaries
                               dict(pkg=pkg_obj.path(name), summary=Path(str(pkg_obj.path(name)) + ".json")),
                               fingerprint([here / "r4im.py"], {"rule": "empty>=vmin"}),
                               fn, label="%s %s vanish guard" % (room.name, owner))

    # ---- r100 PS2-tree impostors (item 20: Blender bl_impostor_bake.py + tree_impostors.py)
    def tree_bake(self, room, views=16, cell=128, light="flat"):
        """One atlas per PS2 tree model of room.recipe["trees"] (the GC BINs using a model share it),
        baked by Blender 5.2 (Windows, a copy in sources [paths] blender_work, Workbench, --threads 1)
        from the ps2_trees() OBJs and the ps2_bark() preview, then encoded by tree_impostors.py (kPal4
        VQ). Outputs as the pinned item 20 bake: impostors.json, tex/<crc>-<fnv>.re4tex, preview/<model>.png;
        bake/ keeps Blender's atlases and report."""
        import subprocess
        bake_py, enc_py = item_tool("bl_impostor_bake.py"), item_tool("tree_impostors.py")
        blender = Path(self.cfg.src["blender"])
        bwork = Path(self.cfg.src["blender_work"])
        trees, bark = self.ps2_trees(room), self.ps2_bark(room)
        st = blender.stat()
        fp = fingerprint([bake_py, enc_py, tool("convert_tpl.py"), self.pvrtex],
                         dict(python=sys.version.split()[0], blender_threads="1",
                              blender="%s:%d:%d" % (blender.name, st.st_size, int(st.st_mtime))))
        args = ["--views", str(int(views)), "--cell", str(int(cell)), "--light", light]

        def win(p):
            return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True,
                                  check=True).stdout.strip()

        def fn(out, work):
            w = bwork / ("tree-bake-%s-%d" % (room.name, os.getpid()))
            if w.exists():
                shutil.rmtree(w)
            (w / "out").mkdir(parents=True)
            shutil.copytree(trees.out, w / "in")
            shutil.copy2(bark.path("preview/ps2-bark-vq.png"), w / "in" / "ps2-bark-vq.png")
            shutil.copy2(bake_py, w / "bl_impostor_bake.py")
            try:
                run([blender, "-b", "--threads", "1", "--factory-startup", "--python", win(w / "bl_impostor_bake.py"),
                     "--", win(w / "in"), win(w / "out")] + args, cwd=w, log=work / "blender.txt", timeout=3600)
                shutil.copytree(w / "out", out / "bake")
            finally:
                shutil.rmtree(w, ignore_errors=True)
            run([PY, "-B", enc_py, work / "enc", "--bake", out / "bake", "--trees", trees.out,
                 "--pvrtex", self.pvrtex], cwd=work, log=work / "log.txt", env=det_env(dict(PYTHONPATH=str(TOOLS))))
            for d in ("tex", "preview"):
                shutil.copytree(work / "enc" / d, out / d)
            shutil.copy2(work / "enc" / "impostors.json", out / "impostors.json")
            m = json.loads((out / "impostors.json").read_text())
            return dict(views=m["views"], cell_h=m["cell_h"], atlases=len(m["atlases"]), records=len(m["records"]),
                        vram_bytes=m["vram_bytes"])
        return self.cache.step("tree.bake", dict(room=room.name, args=args), dict(trees=trees, bark=bark), fp, fn,
                               label="%s tree bake %d views h%d" % (room.name, views, cell))

    # ---- tree impostors for rooms without a pinned item 20 bake (impostor.py, pure Python + pvrtex)
    def room_impostors(self, room, owner, pkg_obj, bins, views=16, cell=128, ss=4, jobs=1):
        """Atlases + records for tree BINs `bins` [(code, bin, common)] of owner `owner` (a package step
        Obj of the recipe build: its finest level is what gets baked)."""
        here = Path(__file__).resolve().parent
        tpl = self.room_tpl(room)
        fp = fingerprint([here / n for n in ("impostor.py", "render.py", "scene.py", "raster.py", "r4im.py",
                                             "texture.py", "camera.py")] +
                         [item_tool("tree_impostors.py"), tool("convert_tpl.py"), self.pvrtex],
                         dict(python=sys.version.split()[0]))
        name = owner + ".re4mesh"
        bins = sorted(bins)
        cfg, pvrtex = self.cfg, self.pvrtex

        def fn(out, work):
            from . import impostor, r4im, texture
            from .scene import Textures
            pk = r4im.load(pkg_obj.path(name))
            tex = Textures(texture.tpl_images(tpl, TOOLS))
            js = [(pk, owner, code, b, common, tex, cfg.cost) for code, b, common in bins]
            return impostor.write_room(out, js, pvrtex, views, cell, ss, workers=jobs)
        return self.cache.step("tree.impostor", dict(room=room.name, owner=owner, bins=bins, views=views, cell=cell,
                                                     ss=ss), dict(pkg=pkg_obj.path(name), tpl=tpl), fp, fn,
                               label="%s impostors %d BINs" % (room.name, len(bins)))

    # ---- per-tree impostors for split groves (grove.py)
    def grove_impostors(self, room, owner, pkg_obj, groves, views=8, cell=128, ss=4, jobs=1):
        """One atlas + record per tree of the split grove BINs of owner `owner` (a package step
        built with --lod-cluster-trees). groves: [(code, bin, common, part, [[first, count], ...])]."""
        here = Path(__file__).resolve().parent
        tpl = self.room_tpl(room)
        fp = fingerprint([here / n for n in ("grove.py", "impostor.py", "render.py", "scene.py", "raster.py",
                                             "r4im.py", "texture.py")] +
                         [item_tool("tree_impostors.py"), tool("convert_tpl.py"), self.pvrtex],
                         dict(python=sys.version.split()[0]))
        name = owner + ".re4mesh"
        groves = [[int(c), int(b), bool(cm), int(p), [[int(f), int(n)] for f, n in trees]]
                  for c, b, cm, p, trees in sorted(groves)]
        cfg, pvrtex = self.cfg, self.pvrtex

        def fn(out, work):
            from . import grove, r4im, texture
            from .scene import Textures
            pk = r4im.load(pkg_obj.path(name))
            tex = Textures(texture.tpl_images(tpl, TOOLS))
            js = [(pk, owner, c, b, cm, p, k, f, n, tex, cfg.cost)
                  for c, b, cm, p, trees in groves for k, (f, n) in enumerate(trees)]
            return grove.write_trees(out, js, pvrtex, views, cell, ss, workers=jobs)
        return self.cache.step("tree.grove_impostor", dict(room=room.name, owner=owner, groves=groves, views=views,
                                                           cell=cell, ss=ss), dict(pkg=pkg_obj.path(name), tpl=tpl),
                               fp, fn, label="%s grove impostors %d trees" % (
                                   room.name, sum(len(g[4]) for g in groves)))

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
