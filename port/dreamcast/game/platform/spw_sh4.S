/* platform/spw_sh4.S -- GAME_SPHERE_WALK (game30.mk; the 30 fps rethink, G: collision traversal; exact):
 * the swept-sphere queries' block walk (atari.cpp cSatMgr::polySphereCk -> blkPolySphereCk and its
 * recursion, cSatBlock::hitCheckSphere on every block of a chain) as a resumable SH-4 loop. A leaf's
 * polygon test (blkPolySphereCkCore) can move the sphere's end, and the recursive walk tests every later
 * block against the moved end, so the kernel returns each overlapped leaf as it finds it; the C runs the
 * leaf and calls re4dc_sphere_walk, which reads the ends again and resumes after that leaf.
 * hitCheckSphere's float operations on the same operands (fmul / fadd operands commuted only), compared
 * as it compares; its tests are side-effect free and combined by OR, so their order is free:
 *   cx = (p0.x + p1.x) * 0.5, hx = |p0.x - p1.x| * 0.5 + r (and z): the block is out when
 *   x0 + size.x < cx - hx, x0 - size.x > cx + hx, z0 + size.z < cz - hz or z0 - size.z > cz + hz;
 *   in when p0 or p1 lies in [x0 - r, x1] x [z0 - r, z1] (x1 = (x0 + size.x) + r, z1 = (z0 + size.z) + r;
 *   the C's compare senses: out of it when p.x < x0 - r || p.x > x1 || p.z < z0 - r || p.z > z1);
 *   else in when p0-p1 crosses one of the edges (x0,z0)-(x1,z0), (x0,z1)-(x1,z1), (x0,z0)-(x0,z1),
 *   (x1,z0)-(x1,z1) as lineCross decides it: denom = dbx * (d.z - c.z) - dbz * (d.x - c.x) with
 *   db = p1 - p0; 0 -> no crossing; ax = p0.x - c.x, az = p0.z - c.z; t = az * (d.x - c.x) - ax * (d.z - c.z),
 *   s = az * dbx - ax * dbz; each of t and s: v < 0 -> out when denom >= 0 (denom > 0 here: denom != 0)
 *   or v < denom; else out when denom < 0 or v > denom.
 *   The four edges share their differences and two products (exactly the values each lineCross computes):
 *   ax1 = p0.x - x0 (edges 1-3), az1 = p0.z - z0 (1, 3, 4), dcx1 = x1 - x0 (1, 2), dcz3 = z1 - z0 (3, 4),
 *   dbz * dcx1 (1, 2), dbx * dcz3 (3, 4); s3 = s1.
 * The next block of a chain is prefetched while a block is tested (as blkPolySphereCk's COL_PREFETCH).
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves fr12-fr15.
 *
 * SphereWalkQ (atari.cpp): m 0x00 (the piece's inverse matrix), p0 0x04 and p1 0x08 (the world ends),
 * r 0x0C, lo 0x10 and lp 0x14 (the piece-space ends the leaves use), cur 0x18 (the block to test next),
 * sp 0x1C (the continuation stack's top), 0x20-0x2C the swept box, 0x30-0x3C the ends' x / z in use
 * (lo.x, lo.z, lp.x, lp.z; the piece entry's for the =2 check), stk 0x40-0x7C (16 continuations).
 * cSatBlock (atari.h): min 0x00, m_Size 0x0C, m_Flag 0x1E (bit 0: node), next 0x20, the child chain
 * at 0x24.
 *
 * cSatBlock* re4dc_sphere_piece(SphereWalkQ* q, cSatBlock* blk): the piece's ends from m, p0 and p1
 * (the x and z rows only, with MTXMultVec's contract-off dataflow and operand roles, as
 * re4dc_line_piece), then the walk from blk. cSatBlock* re4dc_sphere_walk(SphereWalkQ* q): the walk
 * resumed with the ends read from lo and lp. Both return the next overlapped leaf, node | 1 when a node
 * overlaps 16 chains deep (the C walks its child chain recursively, then resumes), or 0 at the end.
 */
        .text
        .align  2
        .global _re4dc_sphere_piece
        .type   _re4dc_sphere_piece, @function
_re4dc_sphere_piece:
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
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
        fadd    fr9,fr10                /* lo.x = + m03 */
        fmov.s  @r0+,fr8                /* m22 */
        fadd    fr9,fr11                /* lp.x = + m03 */
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
        fadd    fr9,fr12                /* lo.z = + m23 */
        fadd    fr9,fr13                /* lp.z = + m23 */
        fmov    fr13,fr7                /* p1.z */
        fmov    fr12,fr14               /* p0.z */
        fmov    fr11,fr15               /* p1.x */
        fmov    fr10,fr13               /* p0.x */
        mov     r4,r7
        add     #64,r7                  /* the continuation stack */
        bra     .Lsetup
        mov     r7,r6                   /* empty; r5 = blk */
        .size   _re4dc_sphere_piece, .-_re4dc_sphere_piece

        .global _re4dc_sphere_walk
        .type   _re4dc_sphere_walk, @function
_re4dc_sphere_walk:
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
        mov.l   @(16,r4),r1             /* lo */
        mov.l   @(20,r4),r2             /* lp */
        fmov.s  @r1,fr13                /* p0.x */
        add     #8,r1
        fmov.s  @r2,fr15                /* p1.x */
        add     #8,r2
        fmov.s  @r1,fr14                /* p0.z */
        fmov.s  @r2,fr7                 /* p1.z */
        mov.l   @(24,r4),r5             /* cur */
        mov.l   @(28,r4),r6             /* sp */
        mov     r4,r7
        add     #64,r7                  /* the stack base */
.Lsetup:
        /* the ends' x / z (0x30) and the swept box (0x20): lx fr8, ux fr9, lz fr10, uz fr11; r fr12;
           p0 (fr13, fr14), p1 (fr15, fr7) */
        mov     r7,r1                   /* q + 0x40 */
        fmov.s  fr7,@-r1                /* 0x3C p1.z */
        fmov    fr13,fr0
        fmov.s  fr15,@-r1               /* 0x38 p1.x */
        fsub    fr15,fr0                /* p0.x - p1.x */
        fmov.s  fr14,@-r1               /* 0x34 p0.z */
        fmov    fr13,fr2
        fmov.s  fr13,@-r1               /* 0x30 p0.x */
        fadd    fr15,fr2                /* p0.x + p1.x */
        mova    .Lhalf,r0
        fmov.s  @r0,fr1                 /* 0.5 */
        fmov    fr14,fr3
        fsub    fr7,fr3                 /* p0.z - p1.z */
        mov     #12,r0
        fmov.s  @(r0,r4),fr12           /* r */
        fmov    fr14,fr4
        fadd    fr7,fr4                 /* p0.z + p1.z */
        fabs    fr0
        fmul    fr1,fr2                 /* cx */
        fabs    fr3
        fmul    fr1,fr0
        fmul    fr1,fr4                 /* cz */
        fmul    fr1,fr3
        fadd    fr12,fr0                /* hx = |..| * 0.5 + r */
        fmov    fr2,fr8
        fadd    fr12,fr3                /* hz */
        fmov    fr2,fr9
        fsub    fr0,fr8                 /* lx = cx - hx */
        fmov    fr4,fr10
        fadd    fr0,fr9                 /* ux = cx + hx */
        fmov    fr4,fr11
        fsub    fr3,fr10                /* lz = cz - hz */
        fadd    fr3,fr11                /* uz = cz + hz */
        fmov.s  fr11,@-r1               /* 0x2C uz */
        fmov.s  fr10,@-r1               /* 0x28 lz */
        fmov.s  fr9,@-r1                /* 0x24 ux */
        fmov.s  fr8,@-r1                /* 0x20 lx */
.Lw:
        tst     r5,r5
        bf      .Lblk
        cmp/eq  r7,r6
        bt      .Ldone                  /* the piece's chain is done */
        add     #-4,r6
        bra     .Lw
        mov.l   @r6,r5                  /* the block after a finished node */
.Lblk:
        mov.l   @(32,r5),r1             /* next */
        mov     r5,r2
        fmov.s  @r5,fr0                 /* x0 = min.x */
        add     #8,r2
        fmov.s  @r2+,fr1                /* z0 = min.z */
        fmov.s  @r2+,fr2                /* size.x */
        add     #4,r2
        fmov.s  @r2,fr3                 /* size.z */
        tst     r1,r1
        fmov    fr2,fr4
        bt      1f
        pref    @r1
1:      fadd    fr0,fr4                 /* x0 + size.x */
        fmov    fr0,fr6
        fsub    fr2,fr6                 /* x0 - size.x */
        fmov    fr3,fr5
        fadd    fr1,fr5                 /* z0 + size.z */
        fmov    fr1,fr2
        fsub    fr3,fr2                 /* z0 - size.z */
        fcmp/gt fr4,fr8
        bt      .Lmiss                  /* x0 + size.x < cx - hx */
        fcmp/gt fr9,fr6
        bt      .Lmiss                  /* x0 - size.x > cx + hx */
        fcmp/gt fr5,fr10
        bt      .Lmiss                  /* z0 + size.z < cz - hz */
        fcmp/gt fr11,fr2
        bt      .Lmiss                  /* z0 - size.z > cz + hz */
        fadd    fr12,fr4                /* x1 = x0 + size.x + r */
        fmov    fr0,fr2
        fadd    fr12,fr5                /* z1 = z0 + size.z + r */
        fmov    fr1,fr3
        fsub    fr12,fr2                /* x0 - r */
        fsub    fr12,fr3                /* z0 - r */
        fcmp/gt fr4,fr13
        bt      .Lp1                    /* p0.x > x1 */
        fcmp/gt fr5,fr14
        bt      .Lp1                    /* p0.z > z1 */
        fcmp/gt fr13,fr2
        bt      .Lp1                    /* p0.x < x0 - r */
        fcmp/gt fr14,fr3
        bf      .Lhit                   /* p0.z >= z0 - r: p0 inside */
.Lp1:
        fcmp/gt fr4,fr15
        bt      .Ledge                  /* p1.x > x1 */
        fcmp/gt fr5,fr7
        bt      .Ledge                  /* p1.z > z1 */
        fcmp/gt fr15,fr2
        bt      .Ledge                  /* p1.x < x0 - r */
        fcmp/gt fr7,fr3
        bt      .Ledge                  /* p1.z < z0 - r */
.Lhit:
        mov.w   @(30,r5),r0             /* m_Flag */
        tst     #1,r0
        bt      .Lleaf
        mov     r7,r0
        add     #64,r0
        cmp/eq  r0,r6
        bt      .Ldeep                  /* 16 chains deep */
        mov.l   r1,@r6                  /* resume after the node */
        add     #4,r6
        bra     .Lw
        add     #36,r5                  /* its child chain */
.Lmiss:
        bra     .Lw
        mov     r1,r5
.Lleaf:
        mov.l   r1,@(24,r4)             /* resume after the leaf */
        mov.l   r6,@(28,r4)
        bra     .Lret
        mov     r5,r0
.Ldeep:
        mov.l   r1,@(24,r4)             /* resume after the node */
        mov.l   r6,@(28,r4)
        mov     r5,r0
        bra     .Lret
        or      #1,r0
.Ldone:
        mov     #0,r0
.Lret:
        fmov.s  @r15+,fr15
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        rts
        fmov.s  @r15+,fr12

        /* lineCross's t test (\t against the denominator \d; fr5 = 0): falls through when the segments
           cannot cross (to the next edge), to \s when they may (the s test) */
        .macro  TTEST d, t, s
        fcmp/eq fr5,\d
        bt      2f                      /* parallel */
        fcmp/gt \t,fr5
        bf      1f                      /* t >= 0 (or unordered) */
        fcmp/gt fr5,\d
        bt      2f                      /* t < 0, denom > 0 */
        fcmp/gt \t,\d
        bt      2f                      /* t < denom */
        bra     \s
        nop
1:      fcmp/gt \d,fr5
        bt      2f                      /* denom < 0 */
        fcmp/gt \d,\t
        bt      2f                      /* t > denom */
        bra     \s
        nop
2:
        .endm

        /* lineCross's s test (\v = s against \d): to .Lehit when the segments cross, else to \next */
        .macro  STEST d, v, next
        fcmp/gt \v,fr5
        bf      1f
        fcmp/gt fr5,\d
        bt      3f                      /* s < 0, denom > 0 */
        fcmp/gt \v,\d
        bt      3f                      /* s < denom */
        bra     .Lehit
        nop
1:      fcmp/gt \d,fr5
        bt      3f                      /* denom < 0 */
        fcmp/gt \d,\v
        bt      3f                      /* s > denom */
        bra     .Lehit
        nop
3:      bra     \next
        nop
        .endm

        /* the query registers again: r, the swept box, the ends' x / z but p1.z (the caller loads it
           in its branch's delay slot) */
        .macro  RELOAD
        mov     r4,r2
        add     #12,r2
        fmov.s  @r2+,fr12               /* r */
        add     #16,r2
        fmov.s  @r2+,fr8                /* lx */
        fmov.s  @r2+,fr9                /* ux */
        fmov.s  @r2+,fr10               /* lz */
        fmov.s  @r2+,fr11               /* uz */
        fmov.s  @r2+,fr13               /* p0.x */
        fmov.s  @r2+,fr14               /* p0.z */
        fmov.s  @r2+,fr15               /* p1.x */
        .endm

        /* x0 fr0, z0 fr1, x1 fr4, z1 fr5; p0 (fr13, fr14), p1 (fr15, fr7) */
.Ledge:
        fsub    fr13,fr15               /* dbx = p1.x - p0.x */
        fmov    fr13,fr8
        fsub    fr14,fr7                /* dbz = p1.z - p0.z */
        fmov    fr14,fr9
        fsub    fr0,fr8                 /* ax1 = p0.x - x0 */
        fmov    fr14,fr10
        fsub    fr1,fr9                 /* az1 = p0.z - z0 */
        fmov    fr4,fr11
        fsub    fr5,fr10                /* az2 = p0.z - z1 */
        fmov    fr1,fr12
        fsub    fr4,fr13                /* ax4 = p0.x - x1 */
        fmov    fr5,fr14
        fsub    fr0,fr11                /* dcx1 = x1 - x0 */
        fmov    fr5,fr6
        fsub    fr1,fr12                /* dcz1 = z0 - z0 */
        fsub    fr5,fr14                /* dcz2 = z1 - z1 */
        fsub    fr1,fr6                 /* dcz3 = z1 - z0 */
        fsub    fr0,fr0                 /* dcx3 = x0 - x0 */
        fsub    fr4,fr4                 /* dcx4 = x1 - x1 */
        fldi0   fr5
        /* edge 1 (x0,z0)-(x1,z0): denom = dbx*dcz1 - dbz*dcx1, t = az1*dcx1 - ax1*dcz1 */
        fmov    fr15,fr1
        fmul    fr12,fr1                /* dbx * dcz1 */
        fmov    fr7,fr2
        fmul    fr11,fr2                /* P = dbz * dcx1 (edges 1, 2) */
        fmov    fr9,fr3
        fmul    fr11,fr3                /* az1 * dcx1 */
        fmul    fr8,fr12                /* ax1 * dcz1 */
        fsub    fr2,fr1                 /* denom */
        fsub    fr12,fr3                /* t */
        TTEST   fr1, fr3, .Ls1
.Le2:   /* edge 2 (x0,z1)-(x1,z1): denom = dbx*dcz2 - P, t = az2*dcx1 - ax1*dcz2 */
        fmov    fr15,fr1
        fmul    fr14,fr1                /* dbx * dcz2 */
        fmov    fr10,fr3
        fmul    fr11,fr3                /* az2 * dcx1 */
        fmul    fr8,fr14                /* ax1 * dcz2 */
        fsub    fr2,fr1                 /* denom */
        fsub    fr14,fr3                /* t */
        TTEST   fr1, fr3, .Ls2
.Le3:   /* edge 3 (x0,z0)-(x0,z1): denom = Q - dbz*dcx3 (Q = dbx*dcz3), t = az1*dcx3 - ax1*dcz3 */
        fmov    fr15,fr2
        fmul    fr6,fr2                 /* Q = dbx * dcz3 (edges 3, 4) */
        fmov    fr7,fr1
        fmul    fr0,fr1                 /* dbz * dcx3 */
        fmov    fr9,fr3
        fmul    fr0,fr3                 /* az1 * dcx3 */
        fmov    fr8,fr11
        fmul    fr6,fr11                /* ax1 * dcz3 */
        fmov    fr2,fr14
        fsub    fr1,fr14                /* denom */
        fsub    fr11,fr3                /* t */
        TTEST   fr14, fr3, .Ls3
.Le4:   /* edge 4 (x1,z0)-(x1,z1): denom = Q - dbz*dcx4, t = az1*dcx4 - ax4*dcz3 */
        fmov    fr7,fr1
        fmul    fr4,fr1                 /* dbz * dcx4 */
        fmov    fr9,fr3
        fmul    fr4,fr3                 /* az1 * dcx4 */
        fmul    fr13,fr6                /* ax4 * dcz3 */
        fsub    fr1,fr2                 /* denom */
        fsub    fr6,fr3                 /* t */
        TTEST   fr2, fr3, .Ls4
.Lemiss:
        mov     r1,r5
        RELOAD
        bra     .Lw                     /* the next block */
        fmov.s  @r2,fr7                 /* p1.z */
.Lehit:
        RELOAD
        bra     .Lhit                   /* the overlapped block */
        fmov.s  @r2,fr7                 /* p1.z */
        /* the s tests: s1 = s3 = az1*dbx - ax1*dbz, s2 = az2*dbx - ax1*dbz, s4 = az1*dbx - ax4*dbz */
.Ls1:
        fmov    fr9,fr3
        fmul    fr15,fr3                /* az1 * dbx */
        fmov    fr8,fr12
        fmul    fr7,fr12                /* ax1 * dbz */
        fsub    fr12,fr3                /* s */
        STEST   fr1, fr3, .Le2
.Ls2:
        fmov    fr10,fr3
        fmul    fr15,fr3                /* az2 * dbx */
        fmov    fr8,fr12
        fmul    fr7,fr12                /* ax1 * dbz */
        fsub    fr12,fr3                /* s */
        STEST   fr1, fr3, .Le3
.Ls3:
        fmov    fr9,fr3
        fmul    fr15,fr3                /* az1 * dbx */
        fmov    fr8,fr12
        fmul    fr7,fr12                /* ax1 * dbz */
        fsub    fr12,fr3                /* s */
        STEST   fr14, fr3, .Le4
.Ls4:
        fmov    fr9,fr3
        fmul    fr15,fr3                /* az1 * dbx */
        fmov    fr13,fr12
        fmul    fr7,fr12                /* ax4 * dbz */
        fsub    fr12,fr3                /* s */
        STEST   fr2, fr3, .Lemiss
        .align  2
.Lhalf:
        .long   0x3f000000              /* 0.5f */
        .size   _re4dc_sphere_walk, .-_re4dc_sphere_walk
