/* platform/pmc_sh4.S -- GAME_PMC_KERNEL (game30.mk; the 30 fps rethink, step 2): cModel::partsMatCalc's
 * loop (every part: RotMatrix(l_mat, &ang), TransMatrix(l_mat, &pos), ScaleMatrix(l_mat, &scale),
 * PSMTXCopy(l_mat, mat)) as one streaming SH-4 loop for the parts whose rotation is in RotMatrix's
 * memo (GAME_ROT_CACHE, math_sub.cpp).
 *
 * Exact twin: a memo hit copies the memo's twelve words (RotMatrix), the translation column becomes
 * pos (TransMatrix), the 3x3 words are fmul(n word, m scale_c) (ScaleMatrix's GCC operand roles) and
 * mat receives the same twelve words (PSMTXCopy moves bits). The hash, the probe (valid and the three
 * key words) and the hit counter are RotMatrix's own. A memo miss returns the part (r0) to the C
 * wrapper, which runs the original four calls for it (RotMatrix then misses, computes and fills the
 * memo exactly as before) and resumes the kernel with its pList.
 *
 * cParts offsets (static_asserts in math_sub.cpp / model.cpp): mat 0x0C, l_mat 0x3C, pos 0x94,
 * ang 0xA0, scale 0xAC, pList 0xF4. Memo entry: key[3], valid, m[12] (64 bytes), 32 entries.
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r9; fr0-fr11 only.
 */
        .text
        .align  2
        .global _re4dc_pmc_run
        .type   _re4dc_pmc_run, @function
_re4dc_pmc_run:                         /* r4 = first part (not NULL) */
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        mov.l   .Lcache,r8              /* re4dc_rot_cache (32 x 64 bytes) */
        mov.l   .Lhits,r9               /* re4dc_rot_cache_hits */
.Lpart:
        mov     r4,r1
        add     #127,r1
        add     #33,r1                  /* ang (0xA0) */
        mov.l   @r1+,r5                 /* kx */
        mov.l   @r1+,r6                 /* ky */
        mov.l   @r1+,r7                 /* kz; r1 = scale (0xAC) */
        mov     r6,r0
        shll    r0                      /* ky << 1 */
        xor     r5,r0
        mov     r7,r3
        shll2   r3                      /* kz << 2 */
        xor     r3,r0                   /* h */
        mov     r0,r3
        mov     #-15,r2
        shld    r2,r3
        xor     r3,r0                   /* h ^= h >> 15 */
        mov     r0,r3
        mov     #-7,r2
        shld    r2,r3
        xor     r3,r0                   /* h ^= h >> 7 */
        and     #31,r0
        shll2   r0
        shll2   r0
        shll2   r0                      /* (h & 31) * 64 */
        mov     r8,r2
        add     r0,r2                   /* e */
        mov.l   @r2+,r3
        cmp/eq  r3,r5
        bf      .Lmiss                  /* key[0] */
        mov.l   @r2+,r3
        cmp/eq  r3,r6
        bf      .Lmiss                  /* key[1] */
        mov.l   @r2+,r3
        cmp/eq  r3,r7
        bf      .Lmiss                  /* key[2] */
        mov.l   @r2+,r3
        tst     r3,r3
        bt      .Lmiss                  /* !valid */
        mov.l   @r9,r3
        add     #1,r3
        mov.l   r3,@r9                  /* re4dc_rot_cache_hits++ */
        fmov.s  @r2+,fr0                /* m[0][0] */
        fmov.s  @r2+,fr1
        fmov.s  @r2+,fr2
        add     #4,r2                   /* m[0][3]: pos.x replaces it */
        fmov.s  @r2+,fr3
        fmov.s  @r2+,fr4
        fmov.s  @r2+,fr5
        add     #4,r2
        fmov.s  @r2+,fr6
        fmov.s  @r2+,fr7
        fmov.s  @r2,fr8
        fmov.s  @r1+,fr9                /* scale.x */
        fmov.s  @r1+,fr10               /* scale.y */
        fmov.s  @r1,fr11                /* scale.z; r1 = 0xB4 */
        fmul    fr9,fr0                 /* m[i][0] *= scale.x */
        fmul    fr10,fr1                /* m[i][1] *= scale.y */
        fmul    fr11,fr2                /* m[i][2] *= scale.z */
        fmul    fr9,fr3
        fmul    fr10,fr4
        fmul    fr11,fr5
        fmul    fr9,fr6
        fmul    fr10,fr7
        fmul    fr11,fr8
        add     #-32,r1                 /* pos (0x94) */
        mov.l   @r1+,r5                 /* pos.x bits */
        mov.l   @r1+,r6
        mov.l   @r1,r7
        mov     r4,r1
        add     #108,r1                 /* end of l_mat (0x6C) */
        mov.l   r7,@-r1                 /* l_mat[2][3] = pos.z */
        fmov.s  fr8,@-r1
        fmov.s  fr7,@-r1
        fmov.s  fr6,@-r1
        mov.l   r6,@-r1
        fmov.s  fr5,@-r1
        fmov.s  fr4,@-r1
        fmov.s  fr3,@-r1
        mov.l   r5,@-r1
        fmov.s  fr2,@-r1
        fmov.s  fr1,@-r1
        fmov.s  fr0,@-r1                /* r1 = l_mat = end of mat (0x3C) */
        mov.l   r7,@-r1                 /* mat = l_mat (PSMTXCopy) */
        fmov.s  fr8,@-r1
        fmov.s  fr7,@-r1
        fmov.s  fr6,@-r1
        mov.l   r6,@-r1
        fmov.s  fr5,@-r1
        fmov.s  fr4,@-r1
        fmov.s  fr3,@-r1
        mov.l   r5,@-r1
        fmov.s  fr2,@-r1
        fmov.s  fr1,@-r1
        fmov.s  fr0,@-r1
        mov.w   .LoNext,r0
        mov.l   @(r0,r4),r4             /* pList (0xF4) */
        tst     r4,r4
        bf      .Lpart
        bra     .Lret
        mov     #0,r0
.Lmiss:
        mov     r4,r0
.Lret:
        mov.l   @r15+,r9
        rts
        mov.l   @r15+,r8
        .align  1
.LoNext: .word  0xF4
        .align  2
.Lcache: .long  _re4dc_rot_cache
.Lhits:  .long  _re4dc_rot_cache_hits
        .size   _re4dc_pmc_run, .-_re4dc_pmc_run
