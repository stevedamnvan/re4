#!/usr/bin/env python3
"""Copy an SDK C unit without its CodeWarrior assembly functions.

The Dolphin SDK matrix/vector units (src/lib/mtx.c, mtxvec.c, mtx44.c, vec.c,
quat.c) carry each routine twice: a portable C_* function and a paired-single
PS* function written as a CodeWarrior `asm void f(...) { ... }` body or as a C
function wrapping an `asm { ... }` block. GCC cannot parse either form. This
writes a copy with every PS* function removed; the Dreamcast platform layer
then provides the PS* names as calls to the C_* functions (platform/mtx.cpp),
so the game runs the SDK's own reference arithmetic.

    strip_cw_asm.py <in.c> <out.c>
"""
import re
import sys

src = open(sys.argv[1], encoding="utf-8", errors="replace").read()

# A function definition header at column 0 whose name starts with PS.
head = re.compile(r"^(?:asm\s+)?(?:static\s+)?(?:void|u32|f32|BOOL|s32|int)\s+\*?\s*((?:__)?PS[A-Za-z0-9_]+)\s*\(", re.M)
out = []
pos = 0
removed = []
while True:
    m = head.search(src, pos)
    if not m:
        out.append(src[pos:])
        break
    # Find the body: the first '{' after the header, then its matching '}'.
    brace = src.index("{", m.end())
    depth = 0
    i = brace
    while True:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    out.append(src[pos:m.start()])
    removed.append(m.group(1))
    pos = i + 1

text = "".join(out)
if "asm" in re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S).replace("ASSERTMSG", ""):
    for line in text.splitlines():
        if re.search(r"\basm\b", line) and not line.strip().startswith("//"):
            raise SystemExit("%s: assembly left after stripping: %r" % (sys.argv[1], line.strip()))
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("/* generated from %s by strip_cw_asm.py: PS* assembly functions removed */\n" % sys.argv[1])
    f.write(text)
print("%s: removed %d PS* functions" % (sys.argv[1], len(removed)))
