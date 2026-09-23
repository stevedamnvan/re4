"""Stream the PC sampler ring (platform/pc_sampler.cpp, symbol re4dc_pcs) out of
the running Flycast process into a .pcs file for pcs_symbolize.py.

    read_pcs.py <pcs-offset> <out.pcs> [poll-seconds] [--dir EVIDENCE_DIR] [--interval S]

<pcs-offset> is the RAM offset of re4dc_pcs (symbol address - 0x8C000000, from
sh-elf-nm, exactly like the read_log.py offsets in syms.txt). Uses the same
read-only mechanism as read_log.py: RAM base from "RAM(16 MB) <addr>" in
flycast.log, PID from flycast.pid, ReadProcessMemory. Never writes guest memory.

Output format (.pcs):
  bytes 0..127  guest header snapshot taken when the sampler was first seen running
  then 8-byte records (w0, w1 little-endian) in guest sequence order;
  a record with w1 == 0xFFFFFFFF is a host gap marker, w0 = records lost
  (overrun: the host fell more than one ring behind the guest).
A sidecar <out.pcs>.json holds the final guest header and host bookkeeping.
"""
import argparse, ctypes, json, os, re, struct, sys, time

HEADER_WORDS = 32
MAGIC = 0x31534350
H = dict(MAGIC=0, VERSION=1, HEADER_WORDS=2, CAPACITY=3, HZ=4, PERIOD_TICKS=5, JITTER_MASK=6,
         STATE=7, HEAD=8, SAMPLES=9, MARKERS=10, LAT_SUM_LO=11, LAT_SUM_HI=12, LAT_MAX=13,
         LATE=14, LATE_TICKS=15, LAST_FRAME=16, STAGE_SOURCE=17, START_SECS=18, START_TICKS=19)
GAP_W1 = 0xFFFFFFFF


def ram_base(evidence):
    for _ in range(6000):
        try:
            with open(os.path.join(evidence, "flycast.log"), encoding="utf-8", errors="ignore") as f:
                m = re.findall(r"RAM\(16 MB\) ([0-9A-Fa-f]+)", f.read())
            if m:
                return int(m[-1], 16)
        except OSError:
            pass
        time.sleep(0.005)
    raise SystemExit("no RAM base in flycast.log")


class Guest:
    def __init__(self, evidence):
        self.pid = int(open(os.path.join(evidence, "flycast.pid"), encoding="utf-8").read())
        self.base = ram_base(evidence)
        self.k32 = ctypes.windll.kernel32
        self.handle = self.k32.OpenProcess(0x0010 | 0x0400, False, self.pid)  # VM_READ | QUERY_INFORMATION
        self.nread = ctypes.c_size_t(0)

    def read(self, offset, count):
        b = ctypes.create_string_buffer(count)
        ok = self.k32.ReadProcessMemory(self.handle, ctypes.c_void_p(self.base + offset), b, count,
                                        ctypes.byref(self.nread))
        return b.raw if ok else None

    def alive(self):
        code = ctypes.c_ulong(0)
        self.k32.GetExitCodeProcess(self.handle, ctypes.byref(code))
        return code.value == 259  # STILL_ACTIVE


def words(raw):
    return list(struct.unpack("<%dI" % (len(raw) // 4), raw))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("offset", type=lambda s: int(s, 0))
    ap.add_argument("out")
    ap.add_argument("seconds", nargs="?", type=float, default=60.0)
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--interval", type=float, default=0.02)
    a = ap.parse_args()

    g = Guest(a.dir)
    start = time.time()
    end = start + a.seconds
    out = None
    last = None  # next guest sequence number the host still needs
    lost = written = markers = polls = 0
    first_hdr = hdr = None
    reason = "deadline"
    while time.time() < end:
        raw = g.read(a.offset, HEADER_WORDS * 4)
        if raw is None:
            if not g.alive():
                reason = "process-exited"
                break
            time.sleep(0.05)
            continue
        hdr = words(raw)
        if hdr[H["MAGIC"]] != MAGIC or hdr[H["CAPACITY"]] == 0:
            time.sleep(0.05)  # sampler not started yet (bss still zero)
            continue
        cap = hdr[H["CAPACITY"]]
        if out is None:
            first_hdr = hdr
            out = open(a.out, "wb")
            out.write(raw)
            last = hdr[H["HEAD"]] - min(hdr[H["HEAD"]], cap - 1)  # keep what the ring still holds
            print("[pcs start hz=%d capacity=%d head=%d]" % (hdr[H["HZ"]], cap, hdr[H["HEAD"]]), flush=True)
        head1 = hdr[H["HEAD"]]
        if head1 != last:
            ring = g.read(a.offset + HEADER_WORDS * 4, cap * 8)
            raw2 = g.read(a.offset, HEADER_WORDS * 4)
            if ring is None or raw2 is None:
                continue
            head2 = words(raw2)[H["HEAD"]]
            if head1 < last:  # guest restarted from zero (reboot)
                print("[pcs head went backwards %d -> %d; resync]" % (last, head1), flush=True)
                last = max(0, head1 - cap)
            # Slots at or below head2 - cap may have been overwritten during the ring read.
            lower = min(head1, max(last, head2 - cap + 1))
            if lower > last:
                lost += lower - last
                out.write(struct.pack("<II", lower - last, GAP_W1))
            if lower < head1:
                rec = ring
                buf = bytearray()
                for seq in range(lower, head1):
                    i = (seq % cap) * 8
                    buf += rec[i:i + 8]
                    if struct.unpack_from("<I", rec, i + 4)[0] & 0x80000000:
                        markers += 1
                out.write(buf)
                written += head1 - lower
            last = head1
        polls += 1
        time.sleep(a.interval)
    final = {}
    raw = g.read(a.offset, HEADER_WORDS * 4)
    if raw is not None:
        hdr = words(raw)
    if hdr is not None:
        final = {k: hdr[v] for k, v in H.items()}
    if out is not None:
        out.close()
    side = {"reason": reason, "host_seconds": time.time() - start, "records_written": written,
            "records_lost": lost, "markers_seen": markers, "polls": polls,
            "first_header": ({k: first_hdr[v] for k, v in H.items()} if first_hdr else None),
            "final_header": final}
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump(side, f, indent=2)
    print("[pcs stop reason=%s written=%d lost=%d markers=%d elapsed=%.1f]" %
          (reason, written, lost, markers, time.time() - start), flush=True)


if __name__ == "__main__":
    main()
