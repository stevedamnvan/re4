/* platform/lnw_sh4.S -- GAME_LINE_WALK (game30.mk; the 30 fps rethink, G: collision traversal; exact):
 * a scenery line query's block walk (atari.cpp blkPolyLineCk and its recursion) as one SH-4 loop: every
 * block of a chain gets cSatBlock::lineOverlap's test, an overlapped node descends into its child chain
 * (blk->idx) and the walk resumes after it, an overlapped leaf is written out. The leaves come out in
 * the recursive walk's order; the C loop then runs blkPolyLineCkCore on each (the walk reads no state the
 * leaves write). lineOverlap's float operations on the same operands, compared as it compares:
 *   hx = size.x * 0.5; d.x = (mid.x - min.x) - hx; out when |d.x| > |dir.x| + hx; the same in z;
 *   out when |d.x * dir.z - d.z * dir.x| > (size.x * |dir.z| + size.z * |dir.x|) * 0.5.
 * The next block of a chain is prefetched while a block is tested (as blkPolyLineCk's COL_PREFETCH).
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r9 and fr12-fr14. With RE4DC_LINE_PIECE (GAME_LINE_PIECE)
 * a second entry, re4dc_line_piece (below the walk), does hitCheck2's per-piece setup and joins the walk.
 *
 * int re4dc_line_walk(const LineWalkQ* q, cSatBlock* blk, cSatBlock** out, int max): the leaf count,
 * or -1 when the walk nests deeper than 16 chains or finds more than max leaves (the caller then walks
 * recursively). LineWalkQ (atari.cpp): mid.x 0x00, mid.z 0x04, dir.x 0x08, dir.z 0x0C, |dir.x| 0x10,
 * |dir.z| 0x14. cSatBlock (atari.h): min 0x00, m_Size 0x0C, m_Flag 0x1E (bit 0: node), next 0x20,
 * the child chain at 0x24.
 */
        .text
        .align  2
        .global _re4dc_line_walk
        .type   _re4dc_line_walk, @function
_re4dc_line_walk:
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        add     #-64,r15                /* the continuation stack: 16 blocks */
        mov     r15,r8                  /* its base */
        mov     r15,r9                  /* its top */
        fmov.s  @r4+,fr8                /* mid.x */
        fmov.s  @r4+,fr9                /* mid.z */
        fmov.s  @r4+,fr10               /* dir.x */
        fmov.s  @r4+,fr11               /* dir.z */
        fmov.s  @r4+,fr12               /* |dir.x| */
        fmov.s  @r4,fr13                /* |dir.z| */
        mova    .Lhalf,r0
        fmov.s  @r0,fr14                /* 0.5 */
.Lstart:
        mov     r6,r3                   /* out start */
.Lw:
        tst     r5,r5
        bf      .Lblk
        cmp/eq  r8,r9
        bt      .Lend                   /* the first chain is done */
        add     #-4,r9
        bra     .Lw
        mov.l   @r9,r5                  /* the block after a finished node */
.Lblk:
        mov.l   @(32,r5),r1             /* next */
        tst     r1,r1
        bt      1f
        pref    @r1
1:      fmov.s  @r5,fr0                 /* min.x */
        mov     r5,r2
        add     #8,r2
        fmov.s  @r2+,fr1                /* min.z */
        fmov.s  @r2+,fr2                /* size.x */
        add     #4,r2
        fmov.s  @r2,fr3                 /* size.z */
        fmov    fr2,fr4
        fmul    fr14,fr4                /* hx = size.x * 0.5 */
        fmov    fr8,fr5
        fsub    fr0,fr5                 /* mid.x - min.x */
        fsub    fr4,fr5                 /* d.x */
        fadd    fr12,fr4                /* |dir.x| + hx */
        fmov    fr5,fr6
        fabs    fr6
        fcmp/gt fr4,fr6
        bt      .Lskip                  /* |d.x| > |dir.x| + hx */
        fmov    fr3,fr4
        fmul    fr14,fr4                /* hz */
        fmov    fr9,fr7
        fsub    fr1,fr7                 /* mid.z - min.z */
        fsub    fr4,fr7                 /* d.z */
        fadd    fr13,fr4                /* |dir.z| + hz */
        fmov    fr7,fr6
        fabs    fr6
        fcmp/gt fr4,fr6
        bt      .Lskip                  /* |d.z| > |dir.z| + hz */
        fmul    fr11,fr5                /* d.x * dir.z */
        fmul    fr10,fr7                /* d.z * dir.x */
        fsub    fr7,fr5
        fabs    fr5
        fmul    fr13,fr2                /* size.x * |dir.z| */
        fmul    fr12,fr3                /* size.z * |dir.x| */
        fadd    fr3,fr2
        fmul    fr14,fr2                /* (...) * 0.5 */
        fcmp/gt fr2,fr5
        bt      .Lskip                  /* the separating axis along the segment */
        mov.w   @(30,r5),r0             /* m_Flag */
        tst     #1,r0
        bt      .Lleaf
        mov     r8,r0
        add     #64,r0
        cmp/eq  r0,r9
        bt      .Lfull                  /* 16 chains deep */
        mov.l   r1,@r9                  /* resume after the node */
        add     #4,r9
        bra     .Lw
        add     #36,r5                  /* its child chain */
.Lleaf:
        tst     r7,r7
        bt      .Lfull                  /* more than max leaves */
        add     #-1,r7
        mov.l   r5,@r6
        add     #4,r6
.Lskip:
        bra     .Lw
        mov     r1,r5
.Lfull:
        bra     .Lret
        mov     #-1,r0
.Lend:
        mov     r6,r0
        sub     r3,r0
        shar    r0
        shar    r0                      /* leaves */
.Lret:
        add     #64,r15
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
        mov.l   @r15+,r9
        rts
        mov.l   @r15+,r8
        .align  2
.Lhalf:
        .long   0x3f000000              /* 0.5f */
        .size   _re4dc_line_walk, .-_re4dc_line_walk

#if defined(RE4DC_LINE_PIECE) && RE4DC_LINE_PIECE
/* int re4dc_line_piece(LinePieceQ* q, cSatBlock* blk, cSatBlock** out, int max) -- GAME_LINE_PIECE: hitCheck2's
 * per-piece setup, then the walk above (same result). LinePieceQ (atari.cpp): the piece's inverse matrix
 * 0x00, the world segment ends p0 0x04 and p1 0x08; written for the =2 check: la.x 0x0C, la.z 0x10, lb.x
 * 0x14, lb.z 0x18. la = m * p0 and lb = m * p1, the x and z rows only, with MTXMultVec's contract-off
 * dataflow and operand roles (platform/mtx_sh4.S): x = add(add(add(mul(n p.x, m m00), mul(n p.y, m m01)),
 * mul(n p.z, m m02)), m m03); z = add(add(add(mul(n m20, m p.x), mul(n m21, m p.y)), mul(n m22, m p.z)),
 * m m23). Then lineWalkPiece's setup as hitCheck2 compiles it: mid = mul(n add(n lb, m la), m 0.5),
 * dir = la - mid, |dir|, x and z (the walk reads nothing else).
 */
        .align  2
        .global _re4dc_line_piece
        .type   _re4dc_line_piece, @function
_re4dc_line_piece:
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        add     #-64,r15                /* the walk's continuation stack */
        mov     r15,r8
        mov     r15,r9
        mov.l   @(4,r4),r1              /* p0 */
        mov.l   @(8,r4),r2              /* p1 */
        mov.l   @r4,r0                  /* m */
        fmov.s  @r1+,fr0                /* p0.x */
        fmov.s  @r2+,fr3                /* p1.x */
        fmov.s  @r1+,fr1                /* p0.y */
        fmov.s  @r2+,fr4                /* p1.y */
        fmov.s  @r1,fr2                 /* p0.z */
        fmov.s  @r2,fr5                 /* p1.z */
        fmov.s  @r0+,fr6                /* m00 */
        fmov.s  @r0+,fr7                /* m01 */
        fmov.s  @r0+,fr8                /* m02 */
        fmov.s  @r0+,fr9                /* m03 */
        fmov    fr0,fr10
        fmul    fr6,fr10                /* mul(n p0.x, m m00) */
        fmov    fr3,fr11
        fmul    fr6,fr11                /* mul(n p1.x, m m00) */
        fmov    fr1,fr12
        fmul    fr7,fr12                /* mul(n p0.y, m m01) */
        fmov    fr4,fr13
        fmul    fr7,fr13                /* mul(n p1.y, m m01) */
        fadd    fr12,fr10               /* add(n p0.x*m00, m p0.y*m01) */
        fmov    fr2,fr12
        fmul    fr8,fr12                /* mul(n p0.z, m m02) */
        fadd    fr13,fr11               /* add(n p1.x*m00, m p1.y*m01) */
        fmov    fr5,fr13
        fmul    fr8,fr13                /* mul(n p1.z, m m02) */
        add     #16,r0                  /* row 2 */
        fadd    fr12,fr10               /* + p0.z*m02 */
        fmov.s  @r0+,fr6                /* m20 */
        fadd    fr13,fr11               /* + p1.z*m02 */
        fmov.s  @r0+,fr7                /* m21 */
        fadd    fr9,fr10                /* la.x = + m03 */
        fmov.s  @r0+,fr8                /* m22 */
        fadd    fr9,fr11                /* lb.x = + m03 */
        fmov.s  @r0,fr9                 /* m23 */
        fmov    fr6,fr12
        fmul    fr0,fr12                /* mul(n m20, m p0.x) */
        fmov    fr6,fr13
        fmul    fr3,fr13                /* mul(n m20, m p1.x) */
        fmov    fr7,fr14
        fmul    fr1,fr14                /* mul(n m21, m p0.y) */
        fmul    fr4,fr7                 /* mul(n m21, m p1.y) */
        fadd    fr14,fr12               /* add(n m20*p0.x, m m21*p0.y) */
        fmov    fr8,fr14
        fmul    fr2,fr14                /* mul(n m22, m p0.z) */
        fadd    fr7,fr13                /* add(n m20*p1.x, m m21*p1.y) */
        fmul    fr5,fr8                 /* mul(n m22, m p1.z) */
        fadd    fr14,fr12               /* + m22*p0.z */
        fadd    fr8,fr13                /* + m22*p1.z */
        fadd    fr9,fr12                /* la.z = + m23 */
        fadd    fr9,fr13                /* lb.z = + m23 */
        mov     r4,r1
        add     #28,r1
        fmov.s  fr13,@-r1               /* lb.z */
        fmov.s  fr11,@-r1               /* lb.x */
        fmov.s  fr12,@-r1               /* la.z */
        fmov.s  fr10,@-r1               /* la.x */
        mova    .Lhalfp,r0
        fmov.s  @r0,fr14                /* 0.5 */
        fadd    fr10,fr11               /* add(n lb.x, m la.x) */
        fadd    fr12,fr13               /* add(n lb.z, m la.z) */
        fmul    fr14,fr11               /* mid.x */
        fmul    fr14,fr13               /* mid.z */
        fmov    fr11,fr8                /* the walk's mid.x */
        fsub    fr11,fr10               /* dir.x = la.x - mid.x */
        fmov    fr13,fr9                /* the walk's mid.z */
        fsub    fr13,fr12               /* dir.z = la.z - mid.z */
        fmov    fr12,fr11               /* the walk's dir.z */
        fmov    fr10,fr12
        fabs    fr12                    /* |dir.x| */
        fmov    fr11,fr13
        bra     .Lstart
        fabs    fr13                    /* |dir.z| */
        .align  2
.Lhalfp:
        .long   0x3f000000              /* 0.5f */
        .size   _re4dc_line_piece, .-_re4dc_line_piece
#endif
