import re


def sub(lines, v, n):
    out = []
    for l in lines:
        def rep(m):
            base = v if m.group(1) == "V" else n
            return "fr%d" % (base + int(m.group(2)))
        l = re.sub(r"\b([VN])(\d)\b", rep, l)
        l = l.replace("fvV", "fv%d" % v).replace("fvN", "fv%d" % n)
        out.append(l)
    return out
