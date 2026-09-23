"""Texture formulas (section 4.4) and a read-only .re4tex header reader."""
import math
import struct

HEADER = struct.Struct("<8s10I")      # room/texture_package.hpp Header (48 B)
TEXTURE = struct.Struct("<64s8I")     # Texture (96 B)
PAYLOADS = {0: "linear", 1: "twiddled", 2: "vq"}
FORMATS = {0: "RGB565", 1: "ARGB1555", 2: "ARGB4444"}


def read_re4tex(path):
    d = open(path, "rb").read()
    h = HEADER.unpack_from(d, 0)
    if h[0] != b"RE4DCTX\0":
        raise ValueError("%s: not a re4tex" % path)
    count, toff, stride = h[4], h[5], h[3]
    out = []
    for i in range(count):
        t = TEXTURE.unpack_from(d, toff + i * stride)
        w, hh, fmt, doff, dsize, flags, payload = t[1:8]
        out.append(dict(width=w, height=hh, format=FORMATS.get(fmt, fmt), payload=PAYLOADS.get(payload, payload),
                        data_bytes=dsize, vram_bytes=vram_bytes(PAYLOADS.get(payload, "linear"), w, hh)))
    return dict(file_bytes=len(d), textures=out, vram_bytes=sum(t["vram_bytes"] for t in out))


def pow2(n):
    return 1 << max(3, math.ceil(math.log2(max(1, n))))


def vram_bytes(kind, w, h):
    """Section 4.4: 16-bit 2wh; full-codebook VQ 2048 + wh/4; PAL4 wh/2; PAL8 wh."""
    w, h = pow2(w), pow2(h)
    if kind == "vq":
        return 2048 + w * h // 4
    if kind == "pal4":
        return w * h // 2
    if kind == "pal8":
        return w * h
    return 2 * w * h


def needed_scale(rho_texels_per_mm, z_min_mm, k=415.692):
    """Largest magnification m = K / (z_min * rho); recommended size factor
    2^floor(log2(min(1, 2m))) (1 = keep, 1/2 = half is invisible, ...)."""
    if rho_texels_per_mm <= 0 or z_min_mm <= 0:
        return 1.0, 0.0
    m = k / (z_min_mm * rho_texels_per_mm)
    f = min(1.0, 2.0 * m)
    return (2.0 ** math.floor(math.log2(f)) if f > 0 else 1.0), m


def vq_loss(psnr, coverage, ref=48.0):
    return coverage * max(0.0, (ref - psnr) / ref)
