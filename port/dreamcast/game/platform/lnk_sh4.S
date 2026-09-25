/* platform/lnk_sh4.S -- GAME_LINE_LEAF (game30.mk; the 30 fps rethink, G: collision traversal; exact):
 * the polygon loop of blkPolyLineCkCore (atari.cpp) over one leaf's index range, as three SH-4 passes:
 *   0. the dedup: each index's polyBit bit tested and set as the C loop did (a polygon is tested once
 *      per piece and query); the untested polygons go to a list, their polygon line prefetched;
 *   A. At_poly_line_ck's plane test: d0 = vert0 - v0, d1 = vert1 - v0, dp = (dx*nx + dy*ny) + dz*nz;
 *      the polygon is out when dp0 * dp1 > 0;
 *   B. its three edge tests, k = 0..2: b = vert0 - v[k], c = cross(edge[e[k]], a) with a = vert1 - vert0;
 *      the polygon is out when dot(c, b) < 0. cross and dot are vec.c's: c = (ey*az - ez*ay,
 *      ez*ax - ex*az, ex*ay - ey*ax), dot = cz*bz + (cx*bx + cy*by).
 * The same float operations on the same operands (fmul / fadd operands commuted only; a is the same
 * subtraction At_poly_line_ck repeats per polygon), compared as it compares, so a polygon leaves exactly
 * where At_poly_line_ck would return 0. The survivors (in index order) are returned; the C loop runs
 * At_poly_line_ck on each (t, the hit point, the attribute filter) and the hit compare as before.
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r14 and fr12-fr15.
 *
 * int re4dc_line_leaf(const LineLeafQ* q, const u16* idx, int n, u16* out), 0 < n <= 64.
 * LineLeafQ (atari.cpp): p0 0x00, p1 0x0C, a 0x18, vtx 0x24, nrm 0x28, edge 0x2C, poly 0x30, bits 0x34.
 * AtPoly (at_sub.h): v[3] 0x00, n 0x06, e[3] 0x08, 20 bytes; Vec 12 bytes.
 */
        /* \out = \base + r0 * 12 (r0: a u16 index, sign-extended by mov.w) */
        .macro  IDX12 base, out
        extu.w  r0,r0
        mov     r0,\out
        add     \out,\out
        add     r0,\out
        shll2   \out
        add     \base,\out
        .endm

        /* \out = poly + \no * 20 */
        .macro  POLY no, out
        mov     \no,\out
        shll2   \out
        add     \no,\out
        shll2   \out
        add     r11,\out
        .endm

        /* one edge test of polygon r1: vertex index at \vo, edge index at \eo. b -> fr6-8 (vert0 in
           fr13-15), e -> fr0-2, a in fr9-11; T = 1 when dot(c, b) < 0 (the polygon is out) */
        .macro  EDGE vo, eo
        mov.w   @(\vo,r1),r0
        IDX12   r8, r2
        fmov.s  @r2+,fr3
        fmov.s  @r2+,fr4
        fmov.s  @r2,fr5
        mov.w   @(\eo,r1),r0
        IDX12   r10, r2
        fmov    fr13,fr6
        fsub    fr3,fr6                 /* bx = vert0.x - v.x */
        fmov    fr14,fr7
        fsub    fr4,fr7                 /* by */
        fmov    fr15,fr8
        fsub    fr5,fr8                 /* bz */
        fmov.s  @r2+,fr0                /* ex */
        fmov.s  @r2+,fr1                /* ey */
        fmov.s  @r2,fr2                 /* ez */
        fmov    fr1,fr3
        fmul    fr11,fr3                /* ey * az */
        fmov    fr2,fr4
        fmul    fr10,fr4                /* ez * ay */
        fsub    fr4,fr3                 /* cx */
        fmov    fr2,fr4
        fmul    fr9,fr4                 /* ez * ax */
        fmov    fr0,fr5
        fmul    fr11,fr5                /* ex * az */
        fsub    fr5,fr4                 /* cy */
        fmul    fr10,fr0                /* ex * ay */
        fmul    fr9,fr1                 /* ey * ax */
        fsub    fr1,fr0                 /* cz */
        fmul    fr6,fr3                 /* cx * bx */
        fmul    fr7,fr4                 /* cy * by */
        fadd    fr4,fr3                 /* cx*bx + cy*by */
        fmul    fr8,fr0                 /* cz * bz */
        fadd    fr3,fr0                 /* dot */
        fldi0   fr1
        fcmp/gt fr0,fr1                 /* 0 > dot */
        .endm

        .text
        .align  2
        .global _re4dc_line_leaf
        .type   _re4dc_line_leaf, @function
_re4dc_line_leaf:
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        mov.l   r10,@-r15
        mov.l   r11,@-r15
        mov.l   r12,@-r15
        mov.l   r13,@-r15
        mov.l   r14,@-r15
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
        add     #-128,r15               /* the untested list: 64 x u16 */
        mov.l   @(36,r4),r8             /* vtx */
        mov.l   @(40,r4),r9             /* nrm */
        mov.l   @(44,r4),r10            /* edge */
        mov.l   @(48,r4),r11            /* poly */
        mov.l   @(52,r4),r12            /* polyBit */
        mov     r15,r13                 /* list end */

        /* pass 0: the dedup */
.Lp0:
        mov.w   @r5+,r0
        extu.w  r0,r3                   /* no */
        mov     r3,r0
        and     #7,r0
        mov     #1,r2
        shld    r0,r2                   /* 1 << (no & 7) */
        mov     r3,r0
        shlr2   r0
        shlr    r0                      /* no >> 3 */
        mov.b   @(r0,r12),r1
        tst     r2,r1
        bf      1f                      /* tested before in this query */
        or      r2,r1
        mov.b   r1,@(r0,r12)
        POLY    r3, r1
        pref    @r1                     /* its record (v, n, e) */
        mov.w   r3,@r13
        add     #2,r13
1:      dt      r6
        bf      .Lp0
        mov     r7,r5                   /* out start */
        cmp/eq  r15,r13
        bf      4f
        bra     .Ldone                  /* every polygon tested before */
        nop
4:

        /* pass A: the plane test; vert0 -> fr13-15, vert1 -> fr9-11 */
        mov     r4,r0
        fmov.s  @r0+,fr13
        fmov.s  @r0+,fr14
        fmov.s  @r0+,fr15
        fmov.s  @r0+,fr9
        fmov.s  @r0+,fr10
        fmov.s  @r0,fr11
        mov     r15,r14                 /* list read */
.La:
        mov.w   @r14+,r0
        extu.w  r0,r3                   /* no */
        POLY    r3, r1
        mov.w   @r1,r0                  /* v[0] */
        IDX12   r8, r2
        mov.w   @(6,r1),r0              /* n */
        IDX12   r9, r1
        fmov.s  @r2+,fr0
        fmov.s  @r2+,fr1
        fmov.s  @r2,fr2                 /* v0 */
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr4
        fmov.s  @r1,fr5                 /* nrm */
        fmov    fr13,fr6
        fsub    fr0,fr6                 /* d0x = vert0.x - v0.x */
        fmov    fr14,fr7
        fsub    fr1,fr7                 /* d0y */
        fmov    fr15,fr8
        fsub    fr2,fr8                 /* d0z */
        fmov    fr9,fr12
        fsub    fr0,fr12                /* d1x = vert1.x - v0.x */
        fmov    fr10,fr0
        fsub    fr1,fr0                 /* d1y */
        fmov    fr11,fr1
        fsub    fr2,fr1                 /* d1z */
        fmul    fr3,fr6                 /* d0x * nx */
        fmul    fr4,fr7                 /* d0y * ny */
        fmul    fr5,fr8                 /* d0z * nz */
        fmul    fr3,fr12                /* d1x * nx */
        fmul    fr4,fr0                 /* d1y * ny */
        fmul    fr5,fr1                 /* d1z * nz */
        fadd    fr7,fr6                 /* d0x*nx + d0y*ny */
        fadd    fr0,fr12                /* d1x*nx + d1y*ny */
        fadd    fr8,fr6                 /* dp0 */
        fadd    fr1,fr12                /* dp1 */
        fmul    fr6,fr12                /* dp0 * dp1 */
        fldi0   fr0
        fcmp/gt fr0,fr12
        bt      2f                      /* both ends on one side */
        mov.w   r3,@r7
        add     #2,r7
2:      cmp/eq  r14,r13
        bf      .La
        cmp/eq  r5,r7
        bf      5f
        bra     .Ldone                  /* no polygon crossed */
        nop
5:

        /* pass B: the three edge tests, survivors compacted in place; a -> fr9-11 */
        mov     r4,r0
        add     #24,r0
        fmov.s  @r0+,fr9
        fmov.s  @r0+,fr10
        fmov.s  @r0,fr11
        mov     r7,r6                   /* plane survivors end */
        mov     r5,r14                  /* read */
        mov     r5,r7                   /* write */
.Lb:
        mov.w   @r14+,r0
        extu.w  r0,r3                   /* no */
        POLY    r3, r1
        EDGE    0, 8
        bt      .Lbout
        EDGE    2, 10
        bt      .Lbout
        EDGE    4, 12
        bt      .Lbout
        mov.w   r3,@r7
        add     #2,r7
.Lbout:
        cmp/eq  r14,r6
        bt      .Ldone
        bra     .Lb
        nop

.Ldone:
        mov     r7,r0
        sub     r5,r0
        shar    r0                      /* survivors */
        add     #127,r15
        add     #1,r15
        fmov.s  @r15+,fr15
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
        mov.l   @r15+,r14
        mov.l   @r15+,r13
        mov.l   @r15+,r12
        mov.l   @r15+,r11
        mov.l   @r15+,r10
        mov.l   @r15+,r9
        rts
        mov.l   @r15+,r8
        .size   _re4dc_line_leaf, .-_re4dc_line_leaf
