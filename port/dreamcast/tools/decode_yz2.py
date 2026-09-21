#!/usr/bin/env python3
"""Decode a private YZ2 payload offline using the recovered PowerPC implementation.

Requires qemu-user and gcc-powerpc-linux-gnu. This is an asset-build helper, not
PowerPC emulation in the Dreamcast runtime. Input must be a trusted disc payload
including its ASCII size header (not the enclosing DVD container).
"""
import argparse
import ast
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def decode(payload, timeout=120):
    header = payload[:32].split(b'\0', 1)[0].split()
    if len(header) < 2:
        raise ValueError('missing YZ2 ASCII sizes')
    packed, unpacked = (int(x, 16) for x in header[:2])
    if packed <= 0 or packed + 32 > len(payload):
        raise ValueError('truncated YZ2 payload')
    if not (0 < unpacked <= 32 * 1024 * 1024):
        raise ValueError('invalid YZ2 output size')
    asm_source = (ROOT / 'src/game/yz2asm.cpp').read_text()
    asm_source = re.sub(r'^#include.*$', '', asm_source, flags=re.M)
    assembly = ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"', re.sub(r'//[^\n]*|/\*.*?\*/', '', asm_source, flags=re.S)))
    setup = (ROOT / 'src/game/yz2code.cpp').read_text()
    setup = setup.replace('#include "types.h"', 'typedef unsigned char u8; typedef unsigned short u16; typedef unsigned int u32;')
    setup = setup.replace('extern "C" {', '').replace('}\n\n// Input state', '\n// Input state', 1)
    setup = '\n'.join('typedef struct %s %s;' % (name, name) for name in ['Yz2InEv', 'Yz2Freq', 'Yz2Dec', 'Yz2Model', 'Yz2DicEnt', 'Yz2Ctx']) + '\n' + setup
    wrapper = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern unsigned Yz2DecodeSet(char*, void*);
extern void Yz2DecodeExec(void*);
int main(int argc, char** argv) {
    if (argc != 3) return 2;
    FILE* f = fopen(argv[1], "rb"); if (!f) return 3;
    fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
    char* in = aligned_alloc(32, (n + 63) & ~31);
    void* work = calloc(1, 2 * 1024 * 1024);
    if (!in || !work || fread(in, 1, n, f) != (size_t)n) return 4;
    fclose(f); memset(in+n, 0, 32);
    unsigned size = Yz2DecodeSet(in, work);
    if (!size || size > 32 * 1024 * 1024) return 5;
    void* out = calloc(1, size + 65536); if (!out) return 6;
    Yz2DecodeExec(out);
    f = fopen(argv[2], "wb"); if (!f) return 7;
    if (fwrite(out, 1, size, f) != size) return 8;
    return fclose(f) != 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='re4-yz2-') as tmp:
        p = Path(tmp)
        (p/'decoder.s').write_text(assembly.replace('\t.rodata', '\t.section .rodata') + '\n.section .note.GNU-stack,"",@progbits\n')
        (p/'setup.c').write_text(setup)
        (p/'main.c').write_text(wrapper)
        (p/'input.yz2').write_bytes(payload)
        subprocess.run(['powerpc-linux-gnu-gcc', '-static', '-O2', '-fno-pie', '-no-pie', '-Wa,-mregnames', str(p/'main.c'), str(p/'setup.c'), str(p/'decoder.s'), '-o', str(p/'decode')], check=True, timeout=30)
        subprocess.run(['qemu-ppc', str(p/'decode'), str(p/'input.yz2'), str(p/'output.arc')], check=True, timeout=timeout)
        output = (p/'output.arc').read_bytes()
        if len(output) != unpacked:
            raise ValueError('decoded size mismatch')
        return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; select a new output path')
    args.output.write_bytes(decode(args.input.read_bytes()))