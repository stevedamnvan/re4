"""Read the game's RAM boot log (platform/mem.cpp re4dc_logbuf) out of the
running Flycast process.

    read_log.py <logbuf-offset> <head-offset> <stage-offset> [poll-seconds]

Offsets are RAM offsets (symbol address - 0x8C000000, from `sh-elf-nm`).
Polls until the process exits or the poll time is over, printing new text as
it appears and the stage word at the end.
"""
import ctypes, os, re, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PID = int(open(os.path.join(HERE, "flycast.pid"), encoding="utf-8").read())
LOG_SIZE = 0x10000

def ram_base():
    for _ in range(6000):
        try:
            log = open(os.path.join(HERE, "flycast.log"), encoding="utf-8", errors="ignore").read()
            m = re.findall(r"RAM\(16 MB\) ([0-9A-Fa-f]+)", log)
            if m:
                return int(m[-1], 16)
        except OSError:
            pass
        time.sleep(0.005)
    raise SystemExit("no RAM base in flycast.log")

RAM = ram_base()
k32 = ctypes.windll.kernel32
handle = k32.OpenProcess(0x0010 | 0x0400, False, PID)
nread = ctypes.c_size_t(0)

def read(offset, count):
    b = ctypes.create_string_buffer(count)
    ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(RAM + offset), b, count, ctypes.byref(nread))
    return b.raw if ok else None

buf_off = int(sys.argv[1], 0)
head_off = int(sys.argv[2], 0)
stage_off = int(sys.argv[3], 0)
poll = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
started = time.time()
end = started + poll
reason = "deadline"
print("[capture start=%s budget=%s]" % (started,poll),flush=True)
shown = 0
last_stage = None
while time.time() < end:
    h = read(head_off, 4)
    if h is None:
        # Not yet committed (the guest has not touched the page) or gone.
        code = ctypes.c_ulong(0)
        k32.GetExitCodeProcess(handle, ctypes.byref(code))
        if code.value != 259:  # STILL_ACTIVE
            reason = "process-exited"
            print("[process exited, code %d elapsed=%.3f]" % (code.value,time.time()-started))
            break
        time.sleep(0.05)
        continue
    head = struct.unpack("<I", h)[0]
    if head < shown:
        print("[log head decreased: reset or process teardown; not proof of guest reboot]")
        shown = 0
    if head > shown:
        if head - shown > LOG_SIZE:
            shown = head - LOG_SIZE
        data = read(buf_off, LOG_SIZE)
        chunk = bytes(data[i % LOG_SIZE] for i in range(shown, head))
        sys.stdout.write(chunk.decode("ascii", "replace"))
        sys.stdout.flush()
        shown = head
    s = read(stage_off, 4)
    stage = struct.unpack("<I", s)[0] if s else None
    if stage != last_stage:
        print("[stage %s]" % stage)
        last_stage = stage
    time.sleep(0.005)
print("[end: head=%d stage=%s]" % (shown, last_stage))

print("[capture stop reason=%s elapsed=%.3f]" % (reason,time.time()-started),flush=True)
