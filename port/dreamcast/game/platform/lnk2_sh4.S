/* platform/lnk2_sh4.S -- GAME_LINE_LEAF2 (game30.mk; G: collision traversal; exact; needs GAME_LINE_LEAF=1):
 * platform/lnk_sh4.S's leaf kernel (the dedup, At_poly_line_ck's plane test, its three edge tests) as
 * re4dc_line_leaf2, software-pipelined: every float operation of lnk_sh4.S on the same operands in the same
 * roles (registers renamed, independent operations reordered), compared as it compares, so the same
 * polygons survive in the same order. What changes is when the addresses are formed:
 *   pass 0: the next index is loaded one step ahead (the load was the dedup's first stall);
 *   pass A: the vertex and normal addresses of the polygon two ahead are formed, and their lines
 *           prefetched, while a polygon's plane test runs (its loads use addresses formed two steps before);
 *   pass B: while edge 0 of a polygon runs, the next polygon's edge-0 addresses (edge line prefetched) and
 *           this polygon's edge-1 addresses (both lines prefetched) are formed; edge 1 forms edge 2's.
 * The lists get sentinel copies of their last entry (two for the untested list, one for the plane
 * survivors), so a step ahead always reads an entry of the list. The dedup reads one index past the
 * chunk (idx[n], inside the collision file; the value is not used).
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r14 and fr12-fr15.
 *
 * int re4dc_line_leaf2(const LineLeafQ* q, const u16* idx, int n, u16* out), 0 < n <= 64; out holds 65.
 * LineLeafQ (atari.cpp): p0 0x00, p1 0x0C, a 0x18, vtx 0x24, nrm 0x28, edge 0x2C, poly 0x30, bits 0x34.
 * AtPoly (at_sub.h): v[3] 0x00, n 0x06, e[3] 0x08, 20 bytes; Vec 12 bytes.
 * Frame: q @0, out @4, the untested list @8 (64 entries + 2 sentinels).
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

        .text
        .align  2
        .global _re4dc_line_leaf2
        .type   _re4dc_line_leaf2, @function
_re4dc_line_leaf2:
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
        add     #-128,r15
        add     #-12,r15                /* 140: q, out, 66 x u16 */
        mov.l   r4,@r15                 /* q */
        mov.l   r7,@(4,r15)             /* out */
        mov.l   @(36,r4),r8             /* vtx */
        mov.l   @(40,r4),r9             /* nrm */
        mov.l   @(44,r4),r10            /* edge */
        mov.l   @(48,r4),r11            /* poly */
        mov.l   @(52,r4),r12            /* polyBit */
        mov     r15,r13
        add     #8,r13                  /* list end */

        /* pass 0: the dedup; r3 = this index, r4 = the next (loaded a step ahead) */
        mov.w   @r5+,r0
        extu.w  r0,r3
.Lp0:
        mov     r3,r0
        and     #7,r0
        mov     #1,r2
        shld    r0,r2                   /* 1 << (no & 7) */
        mov     r3,r0
        shlr2   r0
        shlr    r0                      /* no >> 3 */
        mov.b   @(r0,r12),r1
        mov.w   @r5+,r4                 /* the next index (idx[n] on the last step: not used) */
        tst     r2,r1
        bf      1f                      /* tested before in this query */
        or      r2,r1
        mov.b   r1,@(r0,r12)
        POLY    r3, r1
        pref    @r1                     /* its record (v, n, e) */
        mov.w   r3,@r13
        add     #2,r13
1:      extu.w  r4,r3
        dt      r6
        bf      .Lp0
        mov     r15,r14
        add     #8,r14                  /* list start */
        cmp/eq  r14,r13
        bf      4f
        bra     .Ldone                  /* every polygon tested before */
        nop
4:
        mov     r13,r0
        add     #-2,r0
        mov.w   @r0,r0
        mov.w   r0,@r13                 /* two sentinels: the last entry again */
        add     #2,r13
        mov.w   r0,@r13
        add     #2,r13                  /* r13: the read pointer's value after the last real entry's step */

        /* pass A: the plane test; vert0 -> fr13-15, vert1 -> fr9-11. This polygon's vertex and normal
           addresses: r2, r1; the next one's: r6, r4 (prefetched); the one after is formed in r5, r10 */
        mov.l   @r15,r0                 /* q */
        fmov.s  @r0+,fr13
        fmov.s  @r0+,fr14
        fmov.s  @r0+,fr15
        fmov.s  @r0+,fr9
        fmov.s  @r0+,fr10
        fmov.s  @r0,fr11
        mov.w   @r14+,r0
        extu.w  r0,r3
        POLY    r3, r4
        mov.w   @r4,r0                  /* v[0] */
        IDX12   r8, r2
        mov.w   @(6,r4),r0              /* n */
        IDX12   r9, r1
        mov.w   @r14+,r0
        extu.w  r0,r3
        POLY    r3, r5
        mov.w   @r5,r0
        IDX12   r8, r6
        pref    @r6
        mov.w   @(6,r5),r0
        IDX12   r9, r4
        pref    @r4
.La:
        fmov.s  @r2+,fr0                /* v0.x */
        mov.w   @r14+,r0                /* the entry two ahead */
        fmov.s  @r2+,fr1                /* v0.y */
        extu.w  r0,r12
        fmov.s  @r2,fr2                 /* v0.z */
        mov     r12,r3
        fmov.s  @r1+,fr3                /* nrm.x */
        shll2   r3
        fmov.s  @r1+,fr4                /* nrm.y */
        add     r12,r3
        fmov.s  @r1,fr5                 /* nrm.z */
        shll2   r3
        fmov    fr13,fr6
        add     r11,r3                  /* its record */
        fsub    fr0,fr6                 /* d0x = vert0.x - v0.x */
        mov.w   @r3,r0                  /* its v[0] */
        fmov    fr14,fr7
        fsub    fr1,fr7                 /* d0y */
        fmov    fr15,fr8
        fsub    fr2,fr8                 /* d0z */
        extu.w  r0,r0
        fmov    fr9,fr12
        fsub    fr0,fr12                /* d1x = vert1.x - v0.x */
        mov     r0,r5
        fmov    fr10,fr0
        fsub    fr1,fr0                 /* d1y */
        add     r5,r5
        fmov    fr11,fr1
        fsub    fr2,fr1                 /* d1z */
        add     r0,r5
        fmul    fr3,fr6                 /* d0x * nx */
        shll2   r5
        fmul    fr4,fr7                 /* d0y * ny */
        add     r8,r5                   /* its vertex */
        fmul    fr5,fr8                 /* d0z * nz */
        pref    @r5
        fmul    fr3,fr12                /* d1x * nx */
        mov.w   @(6,r3),r0              /* its n */
        fmul    fr4,fr0                 /* d1y * ny */
        extu.w  r0,r0
        fmul    fr5,fr1                 /* d1z * nz */
        mov     r0,r10
        fadd    fr7,fr6                 /* d0x*nx + d0y*ny */
        add     r10,r10
        fadd    fr0,fr12                /* d1x*nx + d1y*ny */
        add     r0,r10
        fadd    fr8,fr6                 /* dp0 */
        shll2   r10
        fadd    fr1,fr12                /* dp1 */
        add     r9,r10                  /* its normal */
        pref    @r10
        mov     r6,r2
        mov     r4,r1
        fmul    fr6,fr12                /* dp0 * dp1 */
        mov     r5,r6
        mov     r10,r4
        mov     #-6,r0
        mov.w   @(r0,r14),r0            /* this polygon's entry */
        fldi0   fr0
        fcmp/gt fr0,fr12
        bt/s    2f                      /* both ends on one side */
        mov.w   r0,@r7                  /* (kept only when the test passes) */
        add     #2,r7
2:      cmp/eq  r14,r13
        bf      .La
        mov.l   @(4,r15),r5             /* out start */
        cmp/eq  r5,r7
        bf      5f
        bra     .Ldone                  /* no polygon crossed */
        nop
5:

        /* pass B: the three edge tests, survivors compacted in place; a -> fr9-11. This polygon: record
           r1, edge k's vertex address r2 and edge address r4; the next: record r3, edge-0 vertex r12,
           edge r13 */
        mov.l   @r15,r0
        mov.l   @(44,r0),r10            /* edge */
        add     #24,r0
        fmov.s  @r0+,fr9
        fmov.s  @r0+,fr10
        fmov.s  @r0,fr11
        mov     r7,r0
        add     #-2,r0
        mov.w   @r0,r0
        mov.w   r0,@r7                  /* sentinel */
        mov     r7,r6
        add     #2,r6                   /* r6: the read pointer's value after the last real entry's step */
        mov     r5,r14                  /* read */
        mov     r5,r7                   /* write */
        mov.w   @r14+,r0
        extu.w  r0,r3
        POLY    r3, r1
        mov.w   @r1,r0                  /* v[0] */
        IDX12   r8, r2
        mov.w   @(8,r1),r0              /* e[0] */
        IDX12   r10, r4
.Lb:
        /* edge 0 */
        fmov.s  @r2+,fr3                /* v.x */
        mov.w   @r14+,r0                /* the next entry */
        fmov.s  @r2+,fr4
        extu.w  r0,r0
        fmov.s  @r2,fr5
        mov     r0,r3
        fmov.s  @r4+,fr0                /* e.x */
        shll2   r3
        fmov.s  @r4+,fr1
        add     r0,r3
        fmov.s  @r4,fr2
        shll2   r3
        fmov    fr13,fr6
        add     r11,r3                  /* the next record */
        fsub    fr3,fr6                 /* bx = vert0.x - v.x */
        mov.w   @r3,r0                  /* its v[0] */
        fmov    fr14,fr7
        fsub    fr4,fr7                 /* by */
        fmov    fr15,fr8
        fsub    fr5,fr8                 /* bz */
        fmov    fr1,fr3
        fmul    fr11,fr3                /* ey * az */
        extu.w  r0,r0
        fmov    fr2,fr4
        fmul    fr10,fr4                /* ez * ay */
        mov     r0,r12
        fmov    fr2,fr12
        fmul    fr9,fr12                /* ez * ax */
        add     r12,r12
        fmov    fr0,fr5
        fmul    fr11,fr5                /* ex * az */
        add     r0,r12
        fmul    fr10,fr0                /* ex * ay */
        shll2   r12
        fmul    fr9,fr1                 /* ey * ax */
        add     r8,r12                  /* its edge-0 vertex */
        fsub    fr4,fr3                 /* cx */
        mov.w   @(8,r3),r0              /* its e[0] */
        fsub    fr5,fr12                /* cy */
        extu.w  r0,r0
        fsub    fr1,fr0                 /* cz */
        mov     r0,r13
        fmul    fr6,fr3                 /* cx * bx */
        add     r13,r13
        fmul    fr7,fr12                /* cy * by */
        add     r0,r13
        fmul    fr8,fr0                 /* cz * bz */
        shll2   r13
        add     r10,r13                 /* its edge-0 edge */
        pref    @r13
        mov.w   @(2,r1),r0              /* this polygon's v[1] */
        fadd    fr12,fr3                /* cx*bx + cy*by */
        extu.w  r0,r0
        mov     r0,r2
        add     r2,r2
        fadd    fr3,fr0                 /* dot */
        add     r0,r2
        shll2   r2
        add     r8,r2                   /* edge 1's vertex */
        pref    @r2
        mov.w   @(10,r1),r0             /* e[1] */
        extu.w  r0,r0
        mov     r0,r4
        add     r4,r4
        fldi0   fr1
        add     r0,r4
        shll2   r4
        fcmp/gt fr0,fr1                 /* 0 > dot: out */
        add     r10,r4                  /* edge 1's edge */
        bt      .Lbout
        /* edge 1 */
        fmov.s  @r2+,fr3
        fmov.s  @r4+,fr0
        fmov.s  @r2+,fr4
        fmov.s  @r4+,fr1
        fmov.s  @r2,fr5
        fmov.s  @r4,fr2
        fmov    fr13,fr6
        fsub    fr3,fr6                 /* bx */
        fmov    fr14,fr7
        fsub    fr4,fr7                 /* by */
        fmov    fr15,fr8
        fsub    fr5,fr8                 /* bz */
        fmov    fr1,fr3
        fmul    fr11,fr3                /* ey * az */
        mov.w   @(4,r1),r0              /* v[2] */
        fmov    fr2,fr4
        fmul    fr10,fr4                /* ez * ay */
        extu.w  r0,r0
        fmov    fr2,fr12
        fmul    fr9,fr12                /* ez * ax */
        mov     r0,r2
        fmov    fr0,fr5
        fmul    fr11,fr5                /* ex * az */
        add     r2,r2
        fmul    fr10,fr0                /* ex * ay */
        add     r0,r2
        fmul    fr9,fr1                 /* ey * ax */
        shll2   r2
        fsub    fr4,fr3                 /* cx */
        add     r8,r2                   /* edge 2's vertex */
        fsub    fr5,fr12                /* cy */
        pref    @r2
        fsub    fr1,fr0                 /* cz */
        mov.w   @(12,r1),r0             /* e[2] */
        fmul    fr6,fr3                 /* cx * bx */
        extu.w  r0,r0
        fmul    fr7,fr12                /* cy * by */
        mov     r0,r4
        fmul    fr8,fr0                 /* cz * bz */
        add     r4,r4
        add     r0,r4
        shll2   r4
        fadd    fr12,fr3                /* cx*bx + cy*by */
        add     r10,r4                  /* edge 2's edge */
        pref    @r4
        fadd    fr3,fr0                 /* dot */
        fldi0   fr1
        fcmp/gt fr0,fr1
        bt      .Lbout
        /* edge 2 */
        fmov.s  @r2+,fr3
        fmov.s  @r4+,fr0
        fmov.s  @r2+,fr4
        fmov.s  @r4+,fr1
        fmov.s  @r2,fr5
        fmov.s  @r4,fr2
        fmov    fr13,fr6
        fsub    fr3,fr6                 /* bx */
        fmov    fr14,fr7
        fsub    fr4,fr7                 /* by */
        fmov    fr15,fr8
        fsub    fr5,fr8                 /* bz */
        fmov    fr1,fr3
        fmul    fr11,fr3                /* ey * az */
        fmov    fr2,fr4
        fmul    fr10,fr4                /* ez * ay */
        fmov    fr2,fr12
        fmul    fr9,fr12                /* ez * ax */
        fmov    fr0,fr5
        fmul    fr11,fr5                /* ex * az */
        fmul    fr10,fr0                /* ex * ay */
        fmul    fr9,fr1                 /* ey * ax */
        fsub    fr4,fr3                 /* cx */
        fsub    fr5,fr12                /* cy */
        fsub    fr1,fr0                 /* cz */
        fmul    fr6,fr3                 /* cx * bx */
        fmul    fr7,fr12                /* cy * by */
        fmul    fr8,fr0                 /* cz * bz */
        mov     #-4,r0
        fadd    fr12,fr3                /* cx*bx + cy*by */
        mov.w   @(r0,r14),r0            /* this polygon's index (the entry before the next) */
        fadd    fr3,fr0                 /* dot */
        fldi0   fr1
        fcmp/gt fr0,fr1
        bt      .Lbout
        mov.w   r0,@r7
        add     #2,r7
.Lbout:
        mov     r3,r1
        mov     r12,r2
        cmp/eq  r14,r6
        bt      .Ldone
        bra     .Lb
        mov     r13,r4

.Ldone:
        mov.l   @(4,r15),r5
        mov     r7,r0
        sub     r5,r0
        shar    r0                      /* survivors */
        add     #127,r15
        add     #13,r15                 /* 140 */
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
        .size   _re4dc_line_leaf2, .-_re4dc_line_leaf2
