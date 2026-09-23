"""Deterministic software rasteriser and PNG writer for the review sheet.

Pure Python (no PIL/numpy in WSL): z-buffered triangles with per-vertex Lambert
shading, a fixed light, a fixed palette per part. Byte-identical output for the same
input (no floating-point order dependence beyond Python's own IEEE arithmetic).
"""
import math
import struct
import zlib

SKY = (196, 208, 220)
LIGHT = (0.35, 0.85, 0.40)


def png_bytes(width, height, rgb):
    """rgb: bytearray of width*height*3."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride:(y + 1) * stride])

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def part_color(p):
    """Stable mid-grey tints per part index (so parts read apart, before and after alike)."""
    h = (p * 0.61803398875) % 1.0
    r = 150 + int(60 * math.sin(6.2831853 * h))
    g = 150 + int(60 * math.sin(6.2831853 * (h + 0.33)))
    b = 150 + int(60 * math.sin(6.2831853 * (h + 0.66)))
    return (r, g, b)


class View:
    """Look-at camera matching the runtime projection (fovy, 4:3)."""

    def __init__(self, eye, target, width=320, height=240, fovy=60.0, znear=100.0):
        self.eye = eye
        f = [target[i] - eye[i] for i in range(3)]
        n = math.sqrt(sum(x * x for x in f)) or 1.0
        self.f = [x / n for x in f]
        up = (0.0, 1.0, 0.0)
        r = [self.f[1] * up[2] - self.f[2] * up[1], self.f[2] * up[0] - self.f[0] * up[2],
             self.f[0] * up[1] - self.f[1] * up[0]]
        n = math.sqrt(sum(x * x for x in r)) or 1.0
        self.r = [x / n for x in r]
        self.u = [self.r[1] * self.f[2] - self.r[2] * self.f[1], self.r[2] * self.f[0] - self.r[0] * self.f[2],
                  self.r[0] * self.f[1] - self.r[1] * self.f[0]]
        self.w, self.h = width, height
        self.k = (height / 2.0) / math.tan(math.radians(fovy / 2.0))
        self.znear = znear

    def to_cam(self, p):
        d = (p[0] - self.eye[0], p[1] - self.eye[1], p[2] - self.eye[2])
        return (d[0] * self.r[0] + d[1] * self.r[1] + d[2] * self.r[2],
                d[0] * self.u[0] + d[1] * self.u[1] + d[2] * self.u[2],
                d[0] * self.f[0] + d[1] * self.f[1] + d[2] * self.f[2])

    def depth_of_box(self, c, e):
        """Nearest view depth of a world box (the runtime's zmin)."""
        d = [c[a] - self.eye[a] for a in range(3)]
        vz = sum(d[a] * self.f[a] for a in range(3))
        rz = sum(abs(self.f[a]) * e[a] for a in range(3))
        return max(self.znear, vz - rz)


def render(view, tris, width=None, height=None):
    """tris: [(p0, p1, p2, n0, n1, n2, part)] in world space -> (png bytes, pixels drawn)."""
    W, H = view.w, view.h
    rgb = bytearray()
    for y in range(H):
        t = y / max(1, H - 1)
        c = tuple(int(SKY[i] * (1.0 - 0.25 * t)) for i in range(3))
        rgb.extend(bytes(c) * W)
    zbuf = [float("inf")] * (W * H)
    cx, cy, k = W / 2.0, H / 2.0, view.k
    drawn = 0
    for p0, p1, p2, n0, n1, n2, part in tris:
        cs = [view.to_cam(p) for p in (p0, p1, p2)]
        if min(c[2] for c in cs) < view.znear:
            continue       # near-plane rejection (review only; the runtime clips)
        sx = [cx + k * c[0] / c[2] for c in cs]
        sy = [cy - k * c[1] / c[2] for c in cs]
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if area == 0:
            continue
        base = part_color(part)
        shade = []
        for n in (n0, n1, n2):
            l = abs(n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
            shade.append(0.35 + 0.65 * l)
        iz = [1.0 / c[2] for c in cs]
        x0 = max(0, int(math.floor(min(sx))))
        x1 = min(W - 1, int(math.ceil(max(sx))))
        y0 = max(0, int(math.floor(min(sy))))
        y1 = min(H - 1, int(math.ceil(max(sy))))
        if x0 > x1 or y0 > y1:
            continue
        inv = 1.0 / area
        for y in range(y0, y1 + 1):
            py = y + 0.5
            for x in range(x0, x1 + 1):
                px = x + 0.5
                w0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) * inv
                w1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) * inv
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                z = 1.0 / (w0 * iz[0] + w1 * iz[1] + w2 * iz[2])
                i = y * W + x
                if z >= zbuf[i]:
                    continue
                zbuf[i] = z
                s = w0 * shade[0] + w1 * shade[1] + w2 * shade[2]
                o = 3 * i
                rgb[o] = min(255, int(base[0] * s))
                rgb[o + 1] = min(255, int(base[1] * s))
                rgb[o + 2] = min(255, int(base[2] * s))
                drawn += 1
    return png_bytes(W, H, rgb), drawn
