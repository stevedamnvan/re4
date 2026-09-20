#!/usr/bin/env python3
"""Static per-iteration cost of SH-4 loops under the calibrated Flycast model.

R3w measured Flycast's SH-4 cost model with hand-written loops (evidence
`d251-flycast-calibration`): a loop of "op; dt; bf" costs 10.0 ns whether the
op is add, fmul, fdiv or fsqrt, and 20.0 ns when the op is a load or store.
So the model charges about 3.3 ns per non-memory instruction and about
13.3 ns per memory instruction, with no floating-point latency. This tool
lists the backward-branch loops of the named functions with their instruction
and memory-instruction counts and that estimate, so a change can be sized
before it is captured. It is not a hardware model: a real SH-4 pays for fdiv
and fsqrt and much less for cached loads and stores.

Usage: sh4_loop_cost.py ELF SUBSTRING [SUBSTRING...]
Needs sh-elf-objdump on PATH (source port/dreamcast/kos-env.sh).
"""
import re
import subprocess
import sys

PLAIN_NS = 3.3
MEMORY_NS = 13.3
MEMORY_OPS = {"pref", "movca.l", "ocbwb", "ocbp", "ocbi"}
BACKWARD = {"bf", "bt", "bf/s", "bt/s", "bra"}


def parse(elf):
    text = subprocess.run(
        ["sh-elf-objdump", "-d", "--no-show-raw-insn", elf],
        capture_output=True, text=True, check=True).stdout
    functions = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^([0-9a-f]+) <(.+)>:$", line)
        if header:
            current = header.group(2)
            functions[current] = []
            continue
        insn = re.match(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if insn and current is not None:
            functions[current].append(
                (int(insn.group(1), 16), insn.group(2), insn.group(3)))
    return functions


def is_memory(op, arg):
    return "@" in arg or op in MEMORY_OPS


def loops(ops):
    addresses = [address for address, _, _ in ops]
    found = []
    for index, (address, op, arg) in enumerate(ops):
        if op not in BACKWARD:
            continue
        target = re.match(r"([0-9a-f]+)", arg)
        if not target:
            continue
        target = int(target.group(1), 16)
        if target >= address or target < addresses[0]:
            continue
        body = ops[addresses.index(target):index + 1]
        memory = sum(1 for _, o, a in body if is_memory(o, a))
        found.append((target, address, len(body), memory))
    return sorted(found, key=lambda item: item[1] - item[0], reverse=True)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    functions = parse(argv[1])
    for name, ops in functions.items():
        if not any(sub in name for sub in argv[2:]):
            continue
        total_memory = sum(1 for _, o, a in ops if is_memory(o, a))
        print("== %s: %d instructions, %d memory" % (name, len(ops), total_memory))
        for target, address, count, memory in loops(ops)[:8]:
            estimate = (count - memory) * PLAIN_NS + memory * MEMORY_NS
            print("   %08x-%08x  %4d insns  %4d mem  ~%5.0f ns/iter"
                  % (target, address, count, memory, estimate))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
