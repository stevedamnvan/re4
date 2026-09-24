"""Module wiring and porting-trap lint for `assets.sh discover` (round 2).

Wiring: a REL module the room needs is linked into the image by four edits, all derived from
the source tree (the em2a fix, e6f65cc, did them by hand):
  * port/dreamcast/game/Makefile `MODULES = ...`: the module name;
  * platform/modules.cpp `MODULE(name)`: its entry-point declarations;
  * platform/modules.cpp `MODULE(id, name)`: the REL header id from rel.json module_id;
  * the ENEMY_DEMAND audit list (Makefile `filter-out ...,$(MODULES)`), which says the module's
    direct-slot consumers were reviewed. It is written only when the lint below is clean.
Game logic is never generated: the wiring only links the original module's own code.

Lint: the known off-GameCube porting traps, over the module's units (splits.txt, as
tools/gen_modules.py resolves them), in the code the Dreamcast build compiles (`#if` evaluated
with __PPC__ undefined and RE4DC_GAME defined, other macros 0 as in cpp):
  value-init    `new (p) cEmXX()`: value-initialisation zeroes the fields cEmMgr::construct just
                set (em2a's subArc: no model, no collision). Use `new (p) cEmXX;` off the GC.
  asm-alias     `extern T x asm("y")` where y is a file-static of the same file: off the GC the
                static has no global symbol, so the alias binds to a missing-symbol stub.
  slot-math     `EmMgr.pArray` / `EmMgr.size * n`: the port backs enemy slots sparsely; scans go
                through EmMgr.workAt(n) with a null check.
  vptr-offset   `(u8*)this + 4 + ...`: GCC 2.95 put the vptr after the introducing class's fields,
                modern GCC at offset 0; hand-written offsets past it are wrong here.
"""
import re
import runpy
from pathlib import Path

GAME = "port/dreamcast/game"
RULES = [
    ("value-init", "error", re.compile(r"\bnew\s*\(\s*[\w.>-]+\s*\)\s*(c\w+)\s*\(\s*\)")),
    ("slot-math", "error", re.compile(r"\bEmMgr\s*\.\s*pArray\b|\bEmMgr\s*\.\s*size\s*\*")),
    ("vptr-offset", "warning", re.compile(r"\(\s*u8\s*\*\s*\)\s*this\s*\+\s*4\s*\+")),
]
ALIAS = re.compile(r"\bextern\s+[\w:<>\s\*]+?\b(\w+)\s+(?:asm|__asm__)\s*\(\s*\"(\w+)\"\s*\)")
DEFINED = {"RE4DC_GAME": 1}


def _cond(expr):
    """Value of a #if expression in the Dreamcast build (unknown macros are 0, as in cpp)."""
    e = re.sub(r"//.*|/\*.*?\*/", "", expr)
    e = re.sub(r"defined\s*\(\s*(\w+)\s*\)|defined\s+(\w+)", lambda m: str(DEFINED.get(m.group(1) or m.group(2), 0)), e)
    e = e.replace("&&", " and ").replace("||", " or ")
    e = re.sub(r"!(?!=)", " not ", e)
    e = re.sub(r"\b([A-Za-z_]\w*)\b", lambda m: m.group(1) if m.group(1) in ("and", "or", "not") else str(DEFINED.get(m.group(1), 0)), e)
    e = re.sub(r"\b(0x[0-9a-fA-F]+|\d+)[uUlL]+\b", r"\1", e)
    try:
        return bool(eval(e, {"__builtins__": {}}))
    except Exception:
        return True   # unparsable: lint both branches


def active_lines(text):
    """(line number, line) for the lines the Dreamcast build compiles."""
    stack = []   # (this branch active, some branch taken, parent active)
    on = True
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        m = re.match(r"#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)", s)
        if m:
            k, rest = m.group(1), m.group(2)
            if k in ("if", "ifdef", "ifndef"):
                v = _cond(rest) if k == "if" else (DEFINED.get(rest.split()[0], 0) != 0) ^ (k == "ifndef") if rest.split() else True
                stack.append((on and v, v, on))
            elif k == "elif" and stack:
                _, taken, parent = stack[-1]
                v = (not taken) and _cond(rest)
                stack[-1] = (parent and v, taken or v, parent)
            elif k == "else" and stack:
                _, taken, parent = stack[-1]
                stack[-1] = (parent and not taken, True, parent)
            elif k == "endif" and stack:
                stack.pop()
            on = stack[-1][0] if stack else True
            continue
        if on:
            yield n, line


def module_sources(repo, mod):
    gm = runpy.run_path(str(Path(repo) / GAME / "tools/gen_modules.py"))
    _, srcs = gm["units"](str(Path(repo) / "config/G4BE08/modules"), mod)
    return [s for s in srcs if (Path(repo) / s).exists()]


def lint_file(repo, rel):
    text = (Path(repo) / rel).read_text(errors="replace")
    statics = set(re.findall(r"^\s*static\s+[\w:<>\s\*]+?\b(\w+)\s*(?:\[[^\]]*\])?\s*(?:=|;)", text, re.M))
    out = []
    for n, line in active_lines(text):
        code = line.split("//")[0]
        for rule, sev, rx in RULES:
            if rx.search(code):
                out.append({"rule": rule, "severity": sev, "file": rel, "line": n, "text": line.strip()})
        m = ALIAS.search(code)
        if m and m.group(2) in statics:
            out.append({"rule": "asm-alias", "severity": "error", "file": rel, "line": n, "text": line.strip()})
    return out


def lint_module(repo, mod):
    out = []
    for s in module_sources(repo, mod):
        out += lint_file(repo, s)
    return out


def _sub1(text, pat, repl, what):
    new, n = re.subn(pat, repl, text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("wire: can't find %s" % what)
    return new


def wire(repo, mod, rid, comment, audit):
    """Link `mod` (REL id `rid`) into the image; `audit` also adds it to the ENEMY_DEMAND list.
    Returns the edits made (empty when it was wired already)."""
    dc = Path(repo) / GAME
    mk_p, mc_p = dc / "Makefile", dc / "platform/modules.cpp"
    mk, mc = mk_p.read_text(), mc_p.read_text()
    done = []
    mods = re.search(r"^MODULES = (.*)$", mk, re.M).group(1).split()
    if mod not in mods:
        mk = _sub1(mk, r"^(MODULES = .*)$", r"\1 " + mod, "MODULES")
        done.append("Makefile MODULES += %s" % mod)
    am = re.search(r"(ifeq \(\$\(ENEMY_DEMAND\),1\)\s*\nifneq \(\$\(filter-out )([^,]*)(,\$\(MODULES\)\))", mk)
    if audit and am and mod not in am.group(2).split():
        mk = mk[:am.start(2)] + am.group(2) + " " + mod + mk[am.end(2):]
        done.append("ENEMY_DEMAND audit list += %s" % mod)
    if not re.search(r"^MODULE\(%s\)$" % re.escape(mod), mc, re.M):
        last = list(re.finditer(r"^MODULE\((\w+)\)\n(?=#if RE4DC_SUBSCREEN && !RE4DC_SUBSCREEN_OVL)", mc, re.M))
        if not last:
            raise SystemExit("wire: can't find the MODULE(name) list end in modules.cpp")
        i = last[-1].end()
        mc = mc[:i] + "MODULE(%s)\n" % mod + mc[i:]
        done.append("modules.cpp MODULE(%s)" % mod)
    if not re.search(r"MODULE\(\d+,\s*%s\)" % re.escape(mod), mc):
        m = re.search(r"^    MODULE\(\d+, \w+\),.*\n(?=#if RE4DC_SUBSCREEN_OVL\n    \{71)", mc, re.M)
        if not m:
            raise SystemExit("wire: can't find the g_modules table end in modules.cpp")
        line = "    MODULE(%d, %s),%s\n" % (rid, mod, ("  // " + comment) if comment else "")
        mc = mc[:m.end()] + line + mc[m.end():]
        done.append("modules.cpp MODULE(%d, %s)" % (rid, mod))
    if done:
        mk_p.write_text(mk)
        mc_p.write_text(mc)
    return done
