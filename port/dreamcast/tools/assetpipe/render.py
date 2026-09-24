"""Textured scene renderer for the review sheet (whole views, identical for every mode).

Approximates the native mesh path: PVR modulate (texel * vertex colour / 255 * gain),
punch-through alpha (>= 50%), linear fog to the fog colour, one mip level per triangle
(box-filtered chain), near-plane clipping, z-buffer. It gives a like-for-like picture of
what each mode draws; it is not a Flycast frame. Pure Python, deterministic.
"""
from .raster import png_bytes


def mip_chain(img):
    """[(w, h, rgba bytes)] from full size down to 1 texel wide/high (2x2 box filter)."""
    chain = [(img.w, img.h, img.rgba)]
    w, h, px = img.w, img.h, img.rgba
    while w > 1 and h > 1:
        nw, nh = w // 2, h // 2
        out = bytearray(4 * nw * nh)
        for y in range(nh):
            r0 = 8 * y * w
            r1 = r0 + 4 * w
            o = 4 * y * nw
            for x in range(nw):
                a = r0 + 8 * x
                b = r1 + 8 * x
                for c in range(4):
                    out[o + c] = (px[a + c] + px[a + 4 + c] + px[b + c] + px[b + 4 + c] + 2) >> 2
                o += 4
        w, h, px = nw, nh, bytes(out)
        chain.append((w, h, px))
    return chain


_MIPS = {}


def mips(img):
    m = _MIPS.get(id(img))
    if m is None:
        m = _MIPS[id(img)] = (img, mip_chain(img))
    return m[1]


def _clip_near(poly, zn):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina, inb = a[2] >= zn, b[2] >= zn
        if ina:
            out.append(a)
        if ina != inb:
            t = (zn - a[2]) / (b[2] - a[2])
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(len(a))))
    return out


def render_scene(view, tris, fog=(3000.0, 25000.0), fog_rgb=(139, 137, 115), gain=2.0, sky=None, mask=None,
                 raw=False):
    """tris: [(P0, P1, P2, uv0, uv1, uv2, c0, c1, c2, tex, atex)]: world positions, GX UVs
    (v = 0 is image row 0), vertex colours (r, g, b) 0..255, texture Image or None, alpha
    Image (its red channel is the alpha) or None. -> (png bytes, pixels written)."""
    W, H = view.w, view.h
    sky = sky or fog_rgb
    rgb = bytearray(bytes(sky) * (W * H))
    zbuf = [1e30] * (W * H)
    cx, cy, k, zn = W / 2.0, H / 2.0, view.k, view.znear
    f0, f1 = fog
    fr, fgc, fb = fog_rgb
    fscale = 1.0 / max(1.0, f1 - f0)
    drawn = 0
    for P0, P1, P2, t0, t1, t2, c0, c1, c2, tex, atex in tris:
        vs = []
        for P, t, c in ((P0, t0, c0), (P1, t1, c1), (P2, t2, c2)):
            x, y, z = view.to_cam(P)
            vs.append((x, y, z, t[0], t[1], c[0], c[1], c[2]))
        zmin = min(v[2] for v in vs)
        if zmin >= f1 or max(v[2] for v in vs) < zn:
            continue
        poly = vs if zmin >= zn else _clip_near(vs, zn)
        if len(poly) < 3:
            continue
        pts = [(cx + k * v[0] / v[2], cy - k * v[1] / v[2], 1.0 / v[2], v) for v in poly]
        chain = mips(tex) if tex is not None else None
        achain = mips(atex) if atex is not None else None
        opaque = tex is None or (tex.opaque and atex is None)
        for i in range(1, len(pts) - 1):
            a, b, c = pts[0], pts[i], pts[i + 1]
            x0, y0, x1, y1, x2, y2 = a[0], a[1], b[0], b[1], c[0], c[1]
            A0, B0, C0 = y1 - y2, x2 - x1, x1 * y2 - x2 * y1
            A1, B1, C1 = y2 - y0, x0 - x2, x2 * y0 - x0 * y2
            A2, B2, C2 = y0 - y1, x1 - x0, x0 * y1 - x1 * y0
            area = C0 + C1 + C2
            if abs(area) < 1e-9:
                continue
            if area < 0:
                A0, B0, C0, A1, B1, C1, A2, B2, C2 = -A0, -B0, -C0, -A1, -B1, -C1, -A2, -B2, -C2
                area = -area
            inv = 1.0 / area
            q = [(p[2], p[3][3] * p[2], p[3][4] * p[2], p[3][5] * p[2], p[3][6] * p[2], p[3][7] * p[2])
                 for p in (a, b, c)]
            pl = [((A0 * q[0][j] + A1 * q[1][j] + A2 * q[2][j]) * inv,
                   (B0 * q[0][j] + B1 * q[1][j] + B2 * q[2][j]) * inv,
                   (C0 * q[0][j] + C1 * q[1][j] + C2 * q[2][j]) * inv) for j in range(6)]
            tw = th = 1
            px = apx = None
            if chain is not None:
                ua, va = a[3][3], a[3][4]
                tarea = abs((b[3][3] - ua) * (c[3][4] - va) - (c[3][3] - ua) * (b[3][4] - va)) * tex.w * tex.h
                ratio = tarea / max(area, 1e-6)      # both are twice the triangle areas
                lvl = 0
                while ratio > 4.0 and lvl < len(chain) - 1:
                    ratio /= 4.0
                    lvl += 1
                tw, th, px = chain[lvl]
                if achain is not None:
                    apx = achain[min(lvl, len(achain) - 1)]
            ymin = max(0, int(min(y0, y1, y2)))
            ymax = min(H - 1, int(max(y0, y1, y2)) + 1)
            xl_all = max(0.0, min(x0, x1, x2) - 1)
            xr_all = min(float(W), max(x0, x1, x2) + 1)
            (zA, zB, zC), (uA, uB, uC), (vA, vB, vC), (rA, rB, rC), (gA, gB, gC), (bA, bB, bC) = pl
            tw_off, th_off = tw * 4096, th * 4096
            for y in range(ymin, ymax + 1):
                py = y + 0.5
                lo, hi = xl_all, xr_all
                ok = True
                for A, B, C in ((A0, B0, C0), (A1, B1, C1), (A2, B2, C2)):
                    e = C + B * py
                    if A > 1e-12:
                        t = -e / A
                        if t > lo:
                            lo = t
                    elif A < -1e-12:
                        t = -e / A
                        if t < hi:
                            hi = t
                    elif e < 0:
                        ok = False
                        break
                if not ok or lo > hi:
                    continue
                xs = int(lo - 0.5)
                if xs + 0.5 < lo:
                    xs += 1
                xe = int(hi - 0.5)
                if xe + 0.5 > hi:
                    xe -= 1
                if xs < 0:
                    xs = 0
                if xe > W - 1:
                    xe = W - 1
                if xs > xe:
                    continue
                pxc = xs + 0.5
                iz = zA * pxc + zB * py + zC
                uz = uA * pxc + uB * py + uC
                vz = vA * pxc + vB * py + vC
                rz = rA * pxc + rB * py + rC
                gz = gA * pxc + gB * py + gC
                bz = bA * pxc + bB * py + bC
                row = y * W
                for x in range(xs, xe + 1):
                    if iz > 0:
                        z = 1.0 / iz
                        i = row + x
                        if z < zbuf[i]:
                            keep = True
                            if px is not None:
                                tx = int(uz * z * tw + tw_off) % tw
                                ty = int(vz * z * th + th_off) % th
                                o = 4 * (ty * tw + tx)
                                if not opaque:
                                    if apx is not None:
                                        aw, ah, ap = apx
                                        al = ap[4 * ((ty * ah // th) * aw + tx * aw // tw)]
                                    else:
                                        al = px[o + 3]
                                    keep = al >= 128
                                if keep:
                                    s = z * gain / 255.0
                                    r = px[o] * rz * s
                                    g = px[o + 1] * gz * s
                                    bb = px[o + 2] * bz * s
                            else:
                                s = z * gain * 0.6
                                r, g, bb = rz * s, gz * s, bz * s
                            if keep:
                                fo = (z - f0) * fscale
                                if fo > 0:
                                    if fo > 1:
                                        fo = 1.0
                                    r += (fr - r) * fo
                                    g += (fgc - g) * fo
                                    bb += (fb - bb) * fo
                                zbuf[i] = z
                                o = 3 * i
                                rgb[o] = 255 if r > 255 else int(r)
                                rgb[o + 1] = 255 if g > 255 else int(g)
                                rgb[o + 2] = 255 if bb > 255 else int(bb)
                                if mask is not None:
                                    mask[i] = 1
                                drawn += 1
                    iz += zA
                    uz += uA
                    vz += vA
                    rz += rA
                    gz += gA
                    bz += bA
    if raw:
        return rgb, drawn
    return png_bytes(W, H, rgb), drawn
