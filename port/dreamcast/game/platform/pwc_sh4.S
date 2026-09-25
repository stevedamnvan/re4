/* platform/pwc_sh4.S -- GAME_PWC_KERNEL (game30.mk; the 30 fps rethink, step 2: whole skeleton
 * operations): the part-world pass of model.cpp's skelPass (GAME_SKEL_FTRV=1, live mode) as one
 * streaming SH-4 loop.
 *
 * Exact twin of the C loop: every part takes the same FP operations on the same operands, with
 * GCC's operand roles (FRn = FRn op FRm):
 *   - the scaled path's l_mat columns: Ls_k = fmul(n L_k, m rs_c) (c = x y z x / x y z y / x y z z);
 *   - the inverse scales: fdiv(n 1.0f, m rs_c);
 *   - the parent rows: fmul(n P_k, m inv_c) for columns 0-2, P_k3 as is;
 *   - three FTRVs with XMTRX = the l_mat rows as columns 0-2 plus the constant row 0 0 0 1, the
 *     parent rows in fv0 / fv4 / fv8;
 *   - r_scale = fmul(n scale_c, m rs_c).
 * Only addressing changes: SH-4 fmov has no displacement form, so the compiled loop spends three
 * instructions per field; this one streams l_mat / parent rows with @Rn+ loads and mat / world /
 * r_scale with @-Rn stores. The inverse scales are computed once per distinct parent r_scale (bit
 * pattern), not once per part (the same fdiv on the same bits gives the same result).
 *
 * Returns (r0) the first part that needs the C path, or 0 at the end of the list:
 *   - motParts.flags bit 30 (an addRot request: model.cpp skelPartLive applies it);
 *   - a non-uniform parent r_scale with a zero component (skelScaledOriginal).
 * Parts with motParts.flags bit 1 are skipped, as in the C loop. The C wrapper runs the returned
 * part and calls again with its pList.
 *
 * cCoord / cParts offsets (static_asserts in model.cpp): mat 0x0C, l_mat 0x3C, pParent 0x6C,
 * world 0x70, scale 0xAC, r_scale 0xB8, pList 0xF4, motParts.flags 0x1C0.
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r13 and fr12-fr14;
 * clobbers the back bank (XMTRX), as the C path's skelLoadRows does.
 */
        .text
        .align  2
        .global _re4dc_pwc_ftrv_run
        .type   _re4dc_pwc_ftrv_run, @function
_re4dc_pwc_ftrv_run:                    /* r4 = first part (not NULL) */
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        mov.l   r10,@-r15
        mov.l   r11,@-r15
        mov.l   r12,@-r15
        mov.l   r13,@-r15
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        mov.w   .LoRs,r8                /* 0xB8: r_scale */
        mov.l   .Lk40,r9                /* motParts.flags bit 30 */
        mov     #2,r13                  /* cached class: 2 = the C path (safe for any key) */
        mov     #-1,r10                 /* cached r_scale bits */
        mov     #-1,r11
        mov     #-1,r12
.Lpart:
        mov.w   .LoFl,r0
        mov.l   @(r0,r4),r1             /* motParts.flags */
        mov     r1,r0
        tst     #2,r0
        bf      .Lnext                  /* bit 1: skipped */
        tst     r9,r1
        bf      .Lbail                  /* addRot pending: the C path */
        mov     #108,r0
        mov.l   @(r0,r4),r5             /* parent (0x6C) */
        mov     r5,r1
        add     r8,r1
        mov.l   @r1+,r2                 /* parent r_scale bits */
        mov.l   @r1+,r3
        mov.l   @r1,r6
        cmp/eq  r2,r10
        bf      .Lclass
        cmp/eq  r3,r11
        bf      .Lclass
        cmp/eq  r6,r12
        bf      .Lclass
.Lhave:
        mov     r13,r0
        cmp/eq  #1,r0
        bt      .Lscaled
        cmp/eq  #2,r0
        bt      .Lbail
        /* uniform parent scale: XMTRX = l_mat rows, the parent rows as they are */
        mov     r4,r7
        add     #60,r7                  /* l_mat */
        frchg
        fmov.s  @r7+,fr0
        fmov.s  @r7+,fr1
        fmov.s  @r7+,fr2
        fmov.s  @r7+,fr3
        fmov.s  @r7+,fr4
        fmov.s  @r7+,fr5
        fmov.s  @r7+,fr6
        fmov.s  @r7+,fr7
        fmov.s  @r7+,fr8
        fmov.s  @r7+,fr9
        fmov.s  @r7+,fr10
        fmov.s  @r7+,fr11
        fldi0   fr12
        fldi0   fr13
        fldi0   fr14
        fldi1   fr15
        frchg
        mov     r5,r1
        add     #12,r1                  /* parent mat */
        fmov.s  @r1+,fr0
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr4
        fmov.s  @r1+,fr5
        fmov.s  @r1+,fr6
        fmov.s  @r1+,fr7
        fmov.s  @r1+,fr8
        fmov.s  @r1+,fr9
        fmov.s  @r1+,fr10
        bra     .Lftrv
        fmov.s  @r1+,fr11
.Lscaled:
        /* non-uniform parent scale S (no zero): XMTRX = l_mat columns times S (translation column
           row-scaled), the parent rows' columns 0-2 times S^-1 */
        mov     r4,r7
        add     #60,r7                  /* l_mat */
        mov     r5,r1
        add     r8,r1                   /* parent r_scale */
        frchg
        fmov.s  @r1+,fr12               /* rs.x (back bank) */
        fmov.s  @r1+,fr13               /* rs.y */
        fmov.s  @r1,fr14                /* rs.z */
        fmov.s  @r7+,fr0
        fmul    fr12,fr0                /* L0 * rs.x */
        fmov.s  @r7+,fr1
        fmul    fr13,fr1                /* L1 * rs.y */
        fmov.s  @r7+,fr2
        fmul    fr14,fr2                /* L2 * rs.z */
        fmov.s  @r7+,fr3
        fmul    fr12,fr3                /* L3 * rs.x */
        fmov.s  @r7+,fr4
        fmul    fr12,fr4                /* L4 * rs.x */
        fmov.s  @r7+,fr5
        fmul    fr13,fr5                /* L5 * rs.y */
        fmov.s  @r7+,fr6
        fmul    fr14,fr6                /* L6 * rs.z */
        fmov.s  @r7+,fr7
        fmul    fr13,fr7                /* L7 * rs.y */
        fmov.s  @r7+,fr8
        fmul    fr12,fr8                /* L8 * rs.x */
        fmov.s  @r7+,fr9
        fmul    fr13,fr9                /* L9 * rs.y */
        fmov.s  @r7+,fr10
        fmul    fr14,fr10               /* L10 * rs.z */
        fmov.s  @r7+,fr11
        fmul    fr14,fr11               /* L11 * rs.z */
        fldi0   fr12
        fldi0   fr13
        fldi0   fr14
        fldi1   fr15
        frchg
        mov     r5,r1
        add     #12,r1                  /* parent mat */
        fmov.s  @r1+,fr0
        fmul    fr12,fr0                /* P0 * ix */
        fmov.s  @r1+,fr1
        fmul    fr13,fr1                /* P1 * iy */
        fmov.s  @r1+,fr2
        fmul    fr14,fr2                /* P2 * iz */
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr4
        fmul    fr12,fr4
        fmov.s  @r1+,fr5
        fmul    fr13,fr5
        fmov.s  @r1+,fr6
        fmul    fr14,fr6
        fmov.s  @r1+,fr7
        fmov.s  @r1+,fr8
        fmul    fr12,fr8
        fmov.s  @r1+,fr9
        fmul    fr13,fr9
        fmov.s  @r1+,fr10
        fmul    fr14,fr10
        fmov.s  @r1+,fr11
.Lftrv:
        ftrv    xmtrx,fv0
        ftrv    xmtrx,fv4
        ftrv    xmtrx,fv8
        mov     r4,r2
        add     #60,r2                  /* end of mat (0x3C) */
        fmov.s  fr11,@-r2
        fmov.s  fr10,@-r2
        fmov.s  fr9,@-r2
        fmov.s  fr8,@-r2
        fmov.s  fr7,@-r2
        fmov.s  fr6,@-r2
        fmov.s  fr5,@-r2
        fmov.s  fr4,@-r2
        fmov.s  fr3,@-r2
        fmov.s  fr2,@-r2
        fmov.s  fr1,@-r2
        fmov.s  fr0,@-r2
        mov     r4,r2
        add     #124,r2                 /* end of world (0x7C) */
        fmov.s  fr11,@-r2               /* world = mat's translation column */
        fmov.s  fr7,@-r2
        fmov.s  fr3,@-r2
        add     #60,r2                  /* scale (0xAC) */
        mov     r5,r1
        add     r8,r1                   /* parent r_scale */
        fmov.s  @r1+,fr0
        fmov.s  @r1+,fr1
        fmov.s  @r1,fr2
        fmov.s  @r2+,fr3
        fmov.s  @r2+,fr4
        fmov.s  @r2+,fr5                /* r2 = r_scale (0xB8) */
        fmul    fr0,fr3                 /* scale.x * rs.x */
        fmul    fr1,fr4
        fmul    fr2,fr5
        add     #12,r2
        fmov.s  fr5,@-r2
        fmov.s  fr4,@-r2
        fmov.s  fr3,@-r2
.Lnext:
        mov.w   .LoNext,r0
        mov.l   @(r0,r4),r4             /* pList (0xF4) */
        tst     r4,r4
        bf      .Lpart
        bra     .Lret
        mov     #0,r0
.Lclass:
        /* a new parent r_scale: classify as the C loop does and cache the inverse scales */
        mov     r2,r10
        mov     r3,r11
        mov     r6,r12
        lds     r2,fpul
        fsts    fpul,fr0                /* rs.x */
        lds     r3,fpul
        fsts    fpul,fr1                /* rs.y */
        lds     r6,fpul
        fsts    fpul,fr2                /* rs.z */
        fcmp/eq fr0,fr1
        bf      1f                      /* rs.x != rs.y */
        fcmp/eq fr1,fr2
        bf      1f                      /* rs.y != rs.z */
        bra     .Lhave
        mov     #0,r13                  /* uniform */
1:      fldi0   fr3
        fcmp/eq fr3,fr0
        bt      2f
        fcmp/eq fr3,fr1
        bt      2f
        fcmp/eq fr3,fr2
        bt      2f
        fldi1   fr12
        fdiv    fr0,fr12                /* ix = 1.0f / rs.x */
        fldi1   fr13
        fdiv    fr1,fr13                /* iy */
        fldi1   fr14
        fdiv    fr2,fr14                /* iz */
        bra     .Lhave
        mov     #1,r13                  /* scaled */
2:      bra     .Lhave
        mov     #2,r13                  /* a zero component: skelScaledOriginal (the C path) */
.Lbail:
        mov     r4,r0
.Lret:
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
        mov.l   @r15+,r13
        mov.l   @r15+,r12
        mov.l   @r15+,r11
        mov.l   @r15+,r10
        mov.l   @r15+,r9
        rts
        mov.l   @r15+,r8
        .align  1
.LoRs:  .word   0xB8
.LoFl:  .word   0x1C0
.LoNext: .word  0xF4
        .align  2
.Lk40:  .long   0x40000000
        .size   _re4dc_pwc_ftrv_run, .-_re4dc_pwc_ftrv_run
