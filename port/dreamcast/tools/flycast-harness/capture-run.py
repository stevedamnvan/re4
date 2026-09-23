"""D367: boot the candidate through the D362 harness, then capture framebuffers
at fixed host times after the source room binds its native static package.

Observation only: framebuffer samples are not a pixel comparison, and this is
Flycast, not hardware. Adapted from d362-shared-uv/capture-run.py."""
from pathlib import Path
import importlib.util, json, shutil, subprocess, sys, time

e = Path(__file__).resolve().parent
seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 340
shots = [int(s) for s in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["45", "90", "150"])]
spec = importlib.util.spec_from_file_location("capture", e / "capture_ui_vram.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
with (e / "run-output.txt").open("wb") as out:
    p = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                          str(e / "boot2.ps1"), "-Seconds", str(seconds)], stdout=out, stderr=subprocess.STDOUT)
    start = time.time(); bound_at = None; taken = set()
    while p.poll() is None:
        text = (e / "run-output.txt").read_text(errors="replace")
        if bound_at is None and ("native static: /cd/dc/native/" in text or "native mesh: /cd/dc/native/" in text):
            bound_at = time.time()
            print("package event at %.1fs" % (bound_at - start), flush=True)
        if bound_at is not None:
            for due in shots:
                if due not in taken and time.time() - bound_at > due:
                    shot = e / ("shot-%03ds" % due); shot.mkdir(exist_ok=True)
                    for name in ("emu.cfg", "flycast.log", "flycast.pid"):
                        shutil.copy2(e / name, shot / name)
                    (shot / "boot.log").write_text(text, encoding="utf-16")  # capture_ui_vram reads UTF-16
                    offsets = m.capture(shot, shot / "frames")
                    (shot / "capture.json").write_text(json.dumps({
                        "host_after_package_s": time.time() - bound_at, "offsets": offsets,
                        "scope": "sampled framebuffer; not a matched tick or pixel comparison"}, indent=2))
                    print("captured", shot.name, flush=True); taken.add(due)
        time.sleep(1)
print("done", flush=True)
