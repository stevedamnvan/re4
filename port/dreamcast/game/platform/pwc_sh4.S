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
#if RE4DC_PWC_SCHED
/* GAME_PWC_SCHED (lane gskel; exact): the same kernel, rescheduled for the SH-4 pipeline. Every FP operation
 * is the one of the loop below (the !RE4DC_PWC_SCHED body) with the same operand roles; only the order of
 * independent instructions changes:
 *   - r_scale (scale_c * rs_c) is computed first, in the back bank, while the l_mat rows load;
 *   - each fmul follows its load by one or more instructions (loads are 2-cycle), paired with the next load;
 *   - FTRV fv0 is issued as soon as the first parent row is ready, fv4 / fv8 as the pitch allows, and each
 *     result row is stored as it arrives (mat row by row, world after its row);
 *   - the rare paths (class change, skip, C path) sit above the loop top, so every hot conditional branch is
 *     a short one (the original's long branches were bt + bra pairs), and the constants are immediates.
 * No store overlaps a field this part or its parent reads, so the final memory is the same.
 *
 * RE4DC_PWC_PF (GAME_PWC_PF=1, with SCHED): each part prefetches the lines the next part (pList) will touch,
 * at exact field addresses, so the part alignment does not matter (a part is 0x1D8 bytes, not a multiple
 * of 32): flags 0x1C0, pList 0xF4, 0x6C / 0x4C / 0x2C / 0x0C and 0x7B (mat, l_mat, pParent, world: every
 * line of 0x0C-0x7B), 0xAC and 0xC3 (scale, r_scale). The PREFs are spread over the part in the order the
 * next part reads the lines (loop top: flags, pList; back bank: 0x6C, 0xAC, then 0x4C, 0x2C; stores: 0x0C,
 * 0x7B, 0xC3), so two PREFs that may share a line (0x6C / 0x7B, 0xAC / 0xC3) are ~80 cycles apart and at
 * most three PREFs are issued together. The last part prefetches its own lines (hits). The first part
 * prefetches its own lines on entry. A PREF of a line already in the cache costs no bus time; results are
 * unchanged.
 */
#if RE4DC_PWC_PF
        .macro  PF_A                    /* r6 = the next part (or this one): pParent line, scale */
        mov     r6,r3
        add     #108,r3
        pref    @r3                     /* 0x6C: pParent, l_mat tail, world head */
        add     #64,r3
        pref    @r3                     /* 0xAC: scale, r_scale head */
        .endm
        .macro  PF_B                    /* l_mat, mat tail */
        mov     r6,r3
        add     #76,r3
        pref    @r3                     /* 0x4C */
        add     #-32,r3
        pref    @r3                     /* 0x2C */
        .endm
        .macro  PF_C                    /* mat head, world tail, r_scale tail */
        mov     r6,r3
        add     #12,r3
        pref    @r3                     /* 0x0C */
        add     #111,r3
        pref    @r3                     /* 0x7B */
        add     #72,r3
        pref    @r3                     /* 0xC3 */
        .endm
#else
        .macro  PF_A
        .endm
        .macro  PF_B
        .endm
        .macro  PF_C
        .endm
#endif
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
#if RE4DC_PWC_PF
        mov.l   r14,@-r15
#endif
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        mov     #46,r8
        shll2   r8                      /* 0xB8: r_scale */
        mov     #64,r9
        shll16  r9
        shll8   r9                      /* 0x40000000: motParts.flags bit 30 */
        mov     #2,r13                  /* cached class: 2 = the C path (safe for any key) */
        mov     #-1,r10                 /* cached r_scale bits */
        mov     #-1,r11
        mov     #-1,r12
#if RE4DC_PWC_PF
        /* the first part's own read lines, in the order the loop reads them */
        mov     #112,r0
        shll2   r0
        add     r4,r0
        pref    @r0                     /* flags (0x1C0) */
        mov     r4,r3
        add     #127,r3
        add     #117,r3
        pref    @r3                     /* pList (0xF4) */
        mov     r4,r6
        PF_A
        PF_B
        add     #-32,r3
        pref    @r3                     /* 0x0C */
#endif
        bra     .Lpart
        mov     #108,r0                 /* (the loop top's first instruction) */
.Lclass:
        /* a new parent r_scale: classify as the C loop does and cache the inverse scales */
        mov     r2,r10
        mov     r3,r11
        mov     r7,r12
        lds     r2,fpul
        fsts    fpul,fr0                /* rs.x */
        lds     r3,fpul
        fsts    fpul,fr1                /* rs.y */
        lds     r7,fpul
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
.Lskip:
        bra     .Lnext                  /* motParts.flags bit 1: skipped */
        nop
.Lbail:
        mov     r4,r0
.Lret:
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
#if RE4DC_PWC_PF
        mov.l   @r15+,r14
#endif
        mov.l   @r15+,r13
        mov.l   @r15+,r12
        mov.l   @r15+,r11
        mov.l   @r15+,r10
        mov.l   @r15+,r9
        rts
        mov.l   @r15+,r8
#if RE4DC_PWC_PF
.Llastpf:
        bra     3f
        mov     r4,r6                   /* the last part: prefetch base = this part (hits) */
#endif
.Lpart:                                 /* r0 = 108 */
        mov.l   @(r0,r4),r5             /* parent (0x6C; not used when the part is skipped) */
#if RE4DC_PWC_PF
        mov     #61,r0
        shll2   r0                      /* 0xF4 */
        mov.l   @(r0,r4),r14            /* the next part (pList) */
#endif
        mov     #112,r0
        shll2   r0                      /* 0x1C0 */
        mov.l   @(r0,r4),r1             /* motParts.flags */
#if RE4DC_PWC_PF
        mov     r14,r6
        tst     r6,r6
        bt      .Llastpf
3:      add     r6,r0
        pref    @r0                     /* next: flags (0x1C0) */
        mov     r6,r3
        add     #127,r3
        add     #117,r3
        pref    @r3                     /* next: pList (0xF4) */
#endif
        mov     r1,r0
        tst     #2,r0
        bf      .Lskip                  /* bit 1: skipped */
        tst     r9,r1
        bf      .Lbail                  /* addRot pending: the C path */
        mov     r5,r1
        add     r8,r1
        mov.l   @r1+,r2                 /* parent r_scale bits */
        mov.l   @r1+,r3
        mov.l   @r1,r7
        cmp/eq  r2,r10
        bf      .Lclass
        cmp/eq  r3,r11
        bf      .Lclass
        cmp/eq  r7,r12
        bf      .Lclass
.Lhave:
        mov     r13,r0
        cmp/eq  #1,r0
        bf      .Lnotscaled
        /* non-uniform parent scale S (no zero): XMTRX = l_mat columns times S (translation column
           row-scaled), the parent rows' columns 0-2 times S^-1 */
        mov     r5,r1
        add     r8,r1                   /* parent r_scale */
        mov     r4,r2
        add     #127,r2
        add     #45,r2                  /* scale (0xAC) */
        mov     r4,r7
        add     #60,r7                  /* l_mat (0x3C) */
        frchg
        fmov.s  @r1+,fr12               /* rs.x (back bank) */
        fmov.s  @r1+,fr13               /* rs.y */
        fmov.s  @r1,fr14                /* rs.z */
        fmov.s  @r2+,fr9                /* scale.x */
        fmov.s  @r2+,fr10               /* scale.y */
        fmul    fr12,fr9                /* r_scale.x = scale.x * rs.x */
        fmov.s  @r2+,fr11               /* scale.z; r2 = r_scale (0xB8) */
        fmul    fr13,fr10               /* r_scale.y */
        fmov.s  @r7+,fr0
        fmul    fr14,fr11               /* r_scale.z */
        fmov.s  @r7+,fr1
        add     #12,r2                  /* end of r_scale */
        fmul    fr12,fr0                /* L0 * rs.x */
        fmov.s  @r7+,fr2
        fmul    fr13,fr1                /* L1 * rs.y */
        fmov.s  fr11,@-r2
        fmul    fr14,fr2                /* L2 * rs.z */
        fmov.s  fr10,@-r2
        fmov.s  @r7+,fr3
        fmov.s  fr9,@-r2
        PF_A
        fmov.s  @r7+,fr4
        fmul    fr12,fr3                /* L3 * rs.x */
        fmov.s  @r7+,fr5
        fmul    fr12,fr4                /* L4 * rs.x */
        fmov.s  @r7+,fr6
        fmul    fr13,fr5                /* L5 * rs.y */
        fmov.s  @r7+,fr7
        fmul    fr14,fr6                /* L6 * rs.z */
        fmov.s  @r7+,fr8
        fmul    fr13,fr7                /* L7 * rs.y */
        fmov.s  @r7+,fr9
        fmul    fr12,fr8                /* L8 * rs.x */
        fmov.s  @r7+,fr10
        fmul    fr13,fr9                /* L9 * rs.y */
        fmov.s  @r7+,fr11
        fmul    fr14,fr10               /* L10 * rs.z */
        fldi0   fr12
        fmul    fr14,fr11               /* L11 * rs.z */
        fldi0   fr13
        fldi0   fr14
        fldi1   fr15
        frchg
        PF_B
        mov     r5,r1
        add     #12,r1                  /* parent mat */
        mov     r4,r2
        fmov.s  @r1+,fr0
        add     #28,r2                  /* end of mat row 0 (0x1C) */
        fmov.s  @r1+,fr1
        fmul    fr12,fr0                /* P0 * ix */
        fmov.s  @r1+,fr2
        fmul    fr13,fr1                /* P1 * iy */
        fmov.s  @r1+,fr3
        fmul    fr14,fr2                /* P2 * iz */
        fmov.s  @r1+,fr4
        fmov.s  @r1+,fr5
        fmul    fr12,fr4                /* P4 * ix */
        fmov.s  @r1+,fr6
        fmul    fr13,fr5                /* P5 * iy */
        fmov.s  @r1+,fr7
        ftrv    xmtrx,fv0
        fmov.s  @r1+,fr8
        fmul    fr14,fr6                /* P6 * iz */
        fmov.s  @r1+,fr9
        fmul    fr12,fr8                /* P8 * ix */
        fmov.s  @r1+,fr10
        fmul    fr13,fr9                /* P9 * iy */
        fmov.s  @r1+,fr11
        fmul    fr14,fr10               /* P10 * iz */
        mov     #112,r0                 /* world (0x70) */
        ftrv    xmtrx,fv4
.Ltail:
        /* fv0 and fv4 issued; fr8-fr11 ready; r2 = end of mat row 0; r0 = 0x70 */
        PF_C
        fmov.s  fr3,@-r2
        fmov.s  fr2,@-r2
        fmov.s  fr1,@-r2
        fmov.s  fr0,@-r2                /* mat row 0 */
        ftrv    xmtrx,fv8
        add     #32,r2                  /* end of row 1 (0x2C) */
        fmov.s  fr3,@(r0,r4)            /* world.x = mat[0][3] */
        mov     #116,r0
        fmov.s  fr7,@-r2
        fmov.s  fr6,@-r2
        fmov.s  fr5,@-r2
        fmov.s  fr4,@-r2                /* mat row 1 */
        fmov.s  fr7,@(r0,r4)            /* world.y */
        add     #32,r2                  /* end of row 2 (0x3C) */
        mov     #120,r0
        fmov.s  fr11,@-r2
        fmov.s  fr10,@-r2
        fmov.s  fr9,@-r2
        fmov.s  fr8,@-r2                /* mat row 2 */
        fmov.s  fr11,@(r0,r4)           /* world.z */
.Lnext:
#if RE4DC_PWC_PF
        mov     r14,r4
#else
        mov     #61,r0
        shll2   r0                      /* 0xF4 */
        mov.l   @(r0,r4),r4             /* pList */
#endif
        tst     r4,r4
        bt      .Lend
        bra     .Lpart
        mov     #108,r0                 /* (the loop top's first instruction) */
.Lend:
        bra     .Lret
        mov     #0,r0
.Lbail2:
        bra     .Lbail
        nop
.Lnotscaled:
        cmp/eq  #2,r0
        bt      .Lbail2                 /* a zero component: the C path */
        /* uniform parent scale: XMTRX = l_mat rows, the parent rows as they are */
        mov     r5,r1
        add     r8,r1                   /* parent r_scale */
        mov     r4,r2
        add     #127,r2
        add     #45,r2                  /* scale (0xAC) */
        mov     r4,r7
        add     #60,r7                  /* l_mat (0x3C) */
        frchg
        fmov.s  @r1+,fr12               /* rs.x (back bank) */
        fmov.s  @r1+,fr13               /* rs.y */
        fmov.s  @r1,fr14                /* rs.z */
        fmov.s  @r2+,fr9                /* scale.x */
        fmov.s  @r2+,fr10               /* scale.y */
        fmul    fr12,fr9                /* r_scale.x = scale.x * rs.x */
        fmov.s  @r2+,fr11               /* scale.z; r2 = r_scale (0xB8) */
        fmul    fr13,fr10               /* r_scale.y */
        fmov.s  @r7+,fr0
        fmul    fr14,fr11               /* r_scale.z */
        fmov.s  @r7+,fr1
        add     #12,r2                  /* end of r_scale */
        fmov.s  @r7+,fr2
        fmov.s  @r7+,fr3
        fmov.s  @r7+,fr4
        fmov.s  fr11,@-r2
        fmov.s  fr10,@-r2
        fmov.s  fr9,@-r2
        PF_A
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
        PF_B
        mov     r5,r1
        add     #12,r1                  /* parent mat */
        mov     r4,r2
        fmov.s  @r1+,fr0
        add     #28,r2                  /* end of mat row 0 (0x1C) */
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr4
        fmov.s  @r1+,fr5
        ftrv    xmtrx,fv0
        fmov.s  @r1+,fr6
        fmov.s  @r1+,fr7
        fmov.s  @r1+,fr8
        fmov.s  @r1+,fr9
        ftrv    xmtrx,fv4
        fmov.s  @r1+,fr10
        fmov.s  @r1+,fr11
        bra     .Ltail
        mov     #112,r0                 /* world (0x70) */
        .size   _re4dc_pwc_ftrv_run, .-_re4dc_pwc_ftrv_run
#else   /* !RE4DC_PWC_SCHED: the original schedule */
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
#endif  /* RE4DC_PWC_SCHED */
