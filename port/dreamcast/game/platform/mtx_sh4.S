/* Hand-scheduled SH-4 bodies for the hottest SDK matrix/vector entry points (D367 game30).
 *
 * Each routine executes EXACTLY the floating-point dataflow that GCC 15.2 -O1
 * (-ffp-contract=fast, the current build) emits for the SDK C reference function in
 * platform/sdk/gen/{mtx,mtxvec,vec}.c (and PSMTXReorder in platform/mtx.cpp): the same
 * fmul/fadd/fsub/fmac/fneg/fdiv/fldi instructions on the same operands in the same operand
 * roles (destination/source of fmul/fadd/fsub, FR0/FRm of fmac), so results are bit-identical
 * on hardware and in Flycast, NaN payloads included. What changes is addressing and register
 * allocation: SH-4 fmov has no displacement form, so GCC spends a mov+add per load/store and
 * reloads under register pressure; these bodies stream rows with @Rn+ loads / @-Rn stores.
 *
 * Two dataflows, selected by RE4DC_FP_CONTRACT_OFF (game30.mk GAME_FP_CONTRACT=off, fusing policy
 * 6B): the default one mirrors -ffp-contract=fast (fmac where GCC fuses), the other mirrors
 * -ffp-contract=off (MTXConcat, MTXMultVec(SR), VECDotProduct and the MTXInverse determinant use
 * fmul + fadd; the other kernels have no multiply-add and are the same in both builds).
 *
 * Proof: tools/fpsym2.py --strict (symbolic execution of both LINKED bodies over every
 * pointer-alias partition and every FP branch) -> proofs/sh4-math.txt. Regenerate it after
 * any change here or of the SDK compile flags (e.g. -ffp-contract=off changes the reference
 * dataflow; the prover then reports NOT PROVEN EQUIVALENT and these bodies must not be used).
 *
 * ABI: KOS -m4-single -ml; FPSCR.PR=0 SZ=0; float args in fr5, fr4, fr7, fr6 (little-endian
 * pair order); only caller-saved r0-r7 / fr0-fr11 are written; the stack is used only by
 * MTXConcat's ab == b path and the GAME_MTXINV_SCHED MTXInverse (pushes fr12-fr15 and pops them on
 * both exits). Built only with GAME_SH4_MATH=1 (game30.mk); the PS* entry points
 * are bound to these labels by platform/ps_alias_sh4.ld, the C_* SDK bodies stay for direct
 * callers. Alias assumption (as for the C bodies): distinct pointer arguments never partially
 * overlap (equal pointers, i.e. in-place calls, are handled and proved).
 */
        .text

/* ---------------------------------------------------------------------------------------
 * MTXConcat(a, b, ab) -- C_MTXConcat, 265 -> 150 instructions.
 * GCC dataflow, row i:
 *   j<3: ab[i][j] = add(n: fma(FR0 a_i0, FRm b_0j, mul(n a_i1, m b_1j)), m: fma(FR0 a_i2, FRm b_2j, +0))
 *   j=3: ab[i][3] = add(n: fma(a_i2, b_23, fma(a_i0, b_03, mul(a_i1, b_13))), m: a_i3)
 * ab == a is computed in place (each row of a is fully loaded before that row is stored);
 * ab == b uses a 48-byte stack temporary like the C body (b is re-read for every row).
 * r4 a cursor, r5 b, r3 b+16, r6 ab, r7 output cursor (row end, pre-decrement), r1 b cursor.
 */
#if RE4DC_FP_CONTRACT_OFF
/* GAME_FP_CONTRACT=off dataflow (no fmac), row i:
 *   j<3: ab[i][j] = add(n: add(n: mul(n a_i0, m b_0j), m: mul(n a_i1, m b_1j)),
 *                       m: add(n: mul(n a_i2, m b_2j), m: +0))
 *        except ab[2][2] = add(n: add(n: +0, m: mul(a_22, b_22)), m: add(mul(a_20, b_02), mul(a_21, b_12)))
 *   j=3: ab[i][3] = add(add(add(mul(a_i0, b_03), mul(a_i1, b_13)), mul(a_i2, b_23)), a_i3)
 * r1 walks b row by row; a_i3 is loaded after the row's other loads, before its stores. */
        .macro  CONCAT_ROW last
        fmov.s  @r4+,fr0        /* a_i0 */
        fmov.s  @r4+,fr1        /* a_i1 */
        fmov.s  @r4+,fr2        /* a_i2 */
        mov     r5,r1
        fmov.s  @r1+,fr8        /* b_0j */
        fmov.s  @r1+,fr9
        fmov.s  @r1+,fr10
        fmov.s  @r1+,fr11
        fmov    fr0,fr4
        fmul    fr8,fr4         /* t_j = mul(a_i0, b_0j) */
        fmov    fr0,fr5
        fmul    fr9,fr5
        fmov    fr0,fr6
        fmul    fr10,fr6
        fmov    fr0,fr7
        fmul    fr11,fr7
        fmov.s  @r1+,fr8        /* b_1j */
        fmov.s  @r1+,fr9
        fmov.s  @r1+,fr10
        fmov.s  @r1+,fr11
        fmov    fr1,fr3
        fmul    fr8,fr3         /* u_0 = mul(a_i1, b_10) */
        fmov    fr1,fr8
        fmul    fr9,fr8         /* u_1 */
        fadd    fr3,fr4         /* t_0 = add(t_0, u_0) */
        fmov    fr1,fr9
        fmul    fr10,fr9        /* u_2 */
        fadd    fr8,fr5
        fmov    fr1,fr10
        fmul    fr11,fr10       /* u_3 */
        fadd    fr9,fr6
        fadd    fr10,fr7
        fmov.s  @r1+,fr8        /* b_2j */
        fmov.s  @r1+,fr9
        fmov.s  @r1+,fr10
        fmov.s  @r1+,fr11
        fldi0   fr1
        fmov    fr2,fr0
        fmul    fr8,fr0         /* v_0 = mul(a_i2, b_20) */
        fadd    fr1,fr0         /* v_0 = add(v_0, +0) */
        fadd    fr0,fr4         /* ab_i0 = add(t_0, v_0) */
        fmov    fr2,fr0
        fmul    fr9,fr0
        fadd    fr1,fr0
        fadd    fr0,fr5
        fmov    fr2,fr0
        fmul    fr10,fr0
        .if \last
        fmov    fr1,fr3         /* ab[2][2]: GCC's operand roles differ for this element */
        fadd    fr0,fr3         /* add(n +0, m v_2) */
        fadd    fr6,fr3         /* ab_22 = add(n that, m t_2) */
        fmov    fr3,fr6
        .else
        fadd    fr1,fr0
        fadd    fr0,fr6
        .endif
        fmov    fr2,fr0
        fmul    fr11,fr0        /* mul(a_i2, b_23): no +0 in column 3 */
        fadd    fr0,fr7
        fmov.s  @r4+,fr3        /* a_i3 */
        fadd    fr3,fr7         /* ab_i3 = add(t_3, a_i3) */
        fmov.s  fr7,@-r7
        fmov.s  fr6,@-r7
        fmov.s  fr5,@-r7
        .if \last
        .else
        fmov.s  fr4,@-r7
        add     #32,r7          /* next row end */
        .endif
        .endm
#else
        .macro  CONCAT_ROW last
        fmov.s  @r4+,fr0        /* a_i0 */
        fmov.s  @r4+,fr4        /* a_i1 */
        mov     r3,r1           /* b row 1 */
        fmov    fr4,fr5
        fmov    fr4,fr6
        fmov    fr4,fr7
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr11
        fmul    fr1,fr4         /* t_j = a_i1 * b_1j */
        fmul    fr2,fr5
        fmul    fr3,fr6
        fmul    fr11,fr7
        mov     r5,r1           /* b row 0 */
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr11
        fmac    fr0,fr1,fr4     /* t_j = fma(a_i0, b_0j, t_j) */
        fmac    fr0,fr2,fr5
        fmac    fr0,fr3,fr6
        fmac    fr0,fr11,fr7
        fmov.s  @r4+,fr0        /* a_i2 */
        add     #16,r1          /* b row 2 */
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr3
        fmov.s  @r1+,fr11
        fldi0   fr8
        fldi0   fr9
        fldi0   fr10
        fmac    fr0,fr1,fr8     /* u_j = fma(a_i2, b_2j, +0) */
        fmac    fr0,fr2,fr9
        fmac    fr0,fr3,fr10
        fmac    fr0,fr11,fr7    /* t_3 = fma(a_i2, b_23, t_3) */
        fadd    fr8,fr4         /* ab_ij = t_j + u_j */
        fadd    fr9,fr5
        fadd    fr10,fr6
        fmov.s  @r4+,fr1        /* a_i3 */
        fadd    fr1,fr7         /* ab_i3 = t_3 + a_i3 */
        fmov.s  fr7,@-r7
        fmov.s  fr6,@-r7
        fmov.s  fr5,@-r7
        .if \last
        .else
        fmov.s  fr4,@-r7
        add     #32,r7          /* next row end */
        .endif
        .endm
#endif

#if RE4DC_FP_CONTRACT_OFF && RE4DC_CONCAT_COL
/* design-logic P3: contract-off MTXConcat, column-major + list-scheduled (generated by tools/game30/mtx_concat_col.py).
 * Same per-element dataflow and operand roles as the RE4DC_FP_CONTRACT_OFF row macro (see the generator);
 * proof: tools/game30/prove_concat_col.sh (fpsym2 --strict vs the build's own C_MTXConcat). Static schedule 90 cycles. */
        .align  2
        .global _re4dc_sh4_MTXConcat
        .type   _re4dc_sh4_MTXConcat, @function
_re4dc_sh4_MTXConcat:                           /* r4 = a, r5 = b, r6 = ab */
        cmp/eq  r4,r6
        mov     r4,r1           /* a cursor */
        bf/s    1f
        mov     r5,r2           /* b row 0 cursor */
        add     #-48,r15        /* ab == a: compute into a stack temporary (a is re-read per column) */
        mov     r15,r6
1:      mov     r5,r3
        add     #16,r3          /* b row 1 cursor */
        add     #32,r5          /* b row 2 cursor */
        mov     r6,r7
        add     #16,r7          /* ab row 1 (row 2 = @(r0,r7)) */
        mov     #16,r0
        fldi0   fr11            /* +0 */
        fmov.s	@r1+,fr0             /* c0 */
        fmov.s	@r1+,fr1             /* c1 */
        fmov.s	@r1+,fr2             /* c2 */
        add	#4,r1                   /* c3 */
        fmov.s	@r2+,fr3             /* c3 */
        fmov.s	@r1+,fr4             /* c4 */
        fmov.s	@r1+,fr5             /* c5 */
        fmul	fr3,fr0                /* c5 */
        fmov.s	@r1+,fr6             /* c6 */
        fmul	fr3,fr4                /* c6 */
        add	#4,r1                   /* c7 */
        fmov.s	@r3+,fr7             /* c7 */
        fmov.s	@r1+,fr8             /* c8 */
        fmov.s	@r1+,fr9             /* c9 */
        fmul	fr7,fr1                /* c9 */
        fmov.s	@r1+,fr10            /* c10 */
        fmul	fr7,fr5                /* c10 */
        add	#-44,r1                 /* c11 */
        fmul	fr3,fr8                /* c11 */
        fmov.s	@r5+,fr3             /* c12 */
        fmul	fr7,fr9                /* c12 */
        fmov.s	@r2+,fr7             /* c13 */
        fadd	fr1,fr0                /* c13 */
        fmov.s	@r3+,fr1             /* c14 */
        fmul	fr3,fr2                /* c14 */
        fmul	fr3,fr6                /* c15 */
        fmul	fr3,fr10               /* c16 */
        fmov.s	@r1+,fr3             /* c17 */
        fadd	fr11,fr2               /* c17 */
        fadd	fr5,fr4                /* c18 */
        fmov.s	@r1+,fr5             /* c19 */
        fmul	fr7,fr3                /* c19 */
        fadd	fr11,fr6               /* c20 */
        fmul	fr1,fr5                /* c21 */
        fadd	fr9,fr8                /* c22 */
        fmov.s	@r5+,fr9             /* c23 */
        fadd	fr11,fr10              /* c23 */
        fadd	fr2,fr0                /* c24 */
        fmov.s	@r1+,fr2             /* c25 */
        fadd	fr6,fr4                /* c25 */
        fadd	fr10,fr8               /* c26 */
        fmov.s	fr0,@r6              /* c27 */
        add	#4,r1                   /* c28 */
        fmul	fr9,fr2                /* c28 */
        fmov.s	@r1+,fr6             /* c29 */
        fadd	fr5,fr3                /* c29 */
        fmov.s	@r1+,fr10            /* c30 */
        add	#4,r6                   /* c30 */
        fmov.s	@r1+,fr0             /* c31 */
        fmul	fr7,fr6                /* c31 */
        fmul	fr1,fr10               /* c32 */
        fmov.s	fr4,@r7              /* c32 */
        add	#4,r1                   /* c33 */
        fmul	fr9,fr0                /* c33 */
        fmov.s	@r1+,fr5             /* c34 */
        fadd	fr11,fr2               /* c34 */
        fmov.s	@r1+,fr4             /* c35 */
        fadd	fr10,fr6               /* c35 */
        fmov.s	@r1+,fr10            /* c36 */
        fmul	fr7,fr5                /* c36 */
        fmul	fr1,fr4                /* c37 */
        fmov.s	fr8,@(r0,r7)         /* c37 */
        add	#-44,r1                 /* c38 */
        fmul	fr9,fr10               /* c38 */
        fadd	fr11,fr0               /* c39 */
        add	#4,r7                   /* c39 */
        fmov.s	@r1+,fr7             /* c40 */
        fadd	fr4,fr5                /* c40 */
        fmov.s	@r1+,fr1             /* c41 */
        fadd	fr11,fr10              /* c41 */
        fmov.s	@r2+,fr8             /* c42 */
        fadd	fr2,fr3                /* c42 */
        fmov.s	@r1+,fr9             /* c43 */
        fadd	fr0,fr6                /* c43 */
        fmov.s	@r3+,fr4             /* c44 */
        fmul	fr8,fr7                /* c44 */
        fmov.s	@r5+,fr2             /* c45 */
        fadd	fr10,fr5               /* c45 */
        fmul	fr4,fr1                /* c46 */
        fmov.s	fr3,@r6              /* c46 */
        add	#4,r1                   /* c47 */
        fmul	fr2,fr9                /* c47 */
        fmov.s	@r1+,fr0             /* c48 */
        add	#4,r6                   /* c48 */
        fmov.s	@r1+,fr10            /* c49 */
        fadd	fr1,fr7                /* c49 */
        fmov.s	@r1+,fr3             /* c50 */
        fmul	fr8,fr0                /* c50 */
        fmul	fr4,fr10               /* c51 */
        fmov.s	fr6,@r7              /* c51 */
        add	#4,r1                   /* c52 */
        fmul	fr2,fr3                /* c52 */
        fmov.s	@r1+,fr1             /* c53 */
        fadd	fr11,fr9               /* c53 */
        fmov.s	@r1+,fr6             /* c54 */
        fadd	fr10,fr0               /* c54 */
        fmov.s	@r1+,fr10            /* c55 */
        fmul	fr8,fr1                /* c55 */
        fmul	fr4,fr6                /* c56 */
        fmov.s	fr5,@(r0,r7)         /* c56 */
        add	#-44,r1                 /* c57 */
        fmul	fr2,fr10               /* c57 */
        fadd	fr11,fr3               /* c58 */
        add	#4,r7                   /* c58 */
        fmov.s	@r1+,fr8             /* c59 */
        fadd	fr6,fr1                /* c59 */
        fmov.s	@r1+,fr4             /* c60 */
        fadd	fr9,fr7                /* c60 */
        fmov.s	@r2+,fr5             /* c61 */
        fadd	fr3,fr0                /* c61 */
        fmov.s	@r3+,fr2             /* c62 */
        fmul	fr5,fr8                /* c63 */
        fmov.s	@r5+,fr6             /* c63 */
        fmul	fr2,fr4                /* c64 */
        fmov	fr11,fr9               /* c64 */
        fadd	fr10,fr9               /* c65 */
        fmov.s	fr7,@r6              /* c65 */
        fmov.s	@r1+,fr3             /* c66 */
        add	#4,r6                   /* c66 */
        fmov.s	@r1+,fr10            /* c67 */
        fadd	fr4,fr8                /* c67 */
        fmov.s	@r1+,fr7             /* c68 */
        fmul	fr6,fr3                /* c68 */
        fmov.s	@r1+,fr4             /* c69 */
        fadd	fr1,fr9                /* c69 */
        fmul	fr5,fr7                /* c70 */
        fmov.s	fr0,@r7              /* c70 */
        fmov.s	@r1+,fr1             /* c71 */
        fmul	fr2,fr4                /* c71 */
        fmov.s	@r1+,fr0             /* c72 */
        fadd	fr3,fr8                /* c72 */
        fmov.s	@r1+,fr3             /* c73 */
        fmul	fr6,fr1                /* c73 */
        fadd	fr4,fr7                /* c74 */
        fmov.s	fr9,@(r0,r7)         /* c74 */
        fmov.s	@r1+,fr4             /* c75 */
        fmul	fr5,fr3                /* c75 */
        fmov.s	@r1+,fr9             /* c76 */
        fadd	fr10,fr8               /* c76 */
        fmul	fr2,fr4                /* c77 */
        add	#4,r7                   /* c77 */
        fmul	fr6,fr9                /* c78 */
        fmov.s	@r1+,fr5             /* c78 */
        fadd	fr1,fr7                /* c79 */
        fmov.s	fr8,@r6              /* c79 */
        fadd	fr4,fr3                /* c80 */
        fadd	fr0,fr7                /* c82 */
        fadd	fr9,fr3                /* c83 */
        fmov.s	fr7,@r7              /* c85 */
        fadd	fr5,fr3                /* c86 */
        fmov.s	fr3,@(r0,r7)         /* c89 */
        bt      2f              /* T from the entry cmp/eq r4,r6 (nothing in the body writes T): ab == a */
        rts
        nop
2:      mov     r15,r1          /* the temporary */
        mov     r4,r2           /* ab (== a) */
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
        fmov.s  @r1+,fr11
        add     #48,r2
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
        rts
        add     #48,r15
        .size   _re4dc_sh4_MTXConcat, .-_re4dc_sh4_MTXConcat
#else
        .align  2
        .global _re4dc_sh4_MTXConcat
        .type   _re4dc_sh4_MTXConcat, @function
_re4dc_sh4_MTXConcat:           /* r4 = a, r5 = b, r6 = ab */
        mov     r5,r3
        add     #16,r3
        cmp/eq  r5,r6
        bf/s    1f
        mov     r6,r7
        add     #-48,r15        /* ab == b: compute into a stack temporary */
        mov     r15,r7
1:      add     #16,r7
        CONCAT_ROW 0
        CONCAT_ROW 0
        CONCAT_ROW 1
        cmp/eq  r5,r6
        bt/s    2f
        fmov.s  fr4,@-r7        /* last store of the last row (delay slot) */
        rts
        nop
2:      fmov.s  @r15+,fr0       /* copy the temporary to ab (== b) and pop it */
        fmov.s  @r15+,fr1
        fmov.s  @r15+,fr2
        fmov.s  @r15+,fr3
        fmov.s  @r15+,fr4
        fmov.s  @r15+,fr5
        fmov.s  @r15+,fr6
        fmov.s  @r15+,fr7
        fmov.s  @r15+,fr8
        fmov.s  @r15+,fr9
        fmov.s  @r15+,fr10
        fmov.s  @r15+,fr11
        add     #48,r6
        fmov.s  fr11,@-r6
        fmov.s  fr10,@-r6
        fmov.s  fr9,@-r6
        fmov.s  fr8,@-r6
        fmov.s  fr7,@-r6
        fmov.s  fr6,@-r6
        fmov.s  fr5,@-r6
        fmov.s  fr4,@-r6
        fmov.s  fr3,@-r6
        fmov.s  fr2,@-r6
        fmov.s  fr1,@-r6
        rts
        fmov.s  fr0,@-r6
        .size   _re4dc_sh4_MTXConcat, . - _re4dc_sh4_MTXConcat
#endif /* RE4DC_CONCAT_COL */

/* ---------------------------------------------------------------------------------------
 * MTXMultVec(m, src, dst) -- C_MTXMultVec, 62 -> 34 instructions. GCC dataflow:
 *   dst.x = add(n: fma(FR0 z, FRm m02, fma(FR0 x, FRm m00, mul(n y, m m01))), m: m03)
 *   dst.y = add(fma(z, m12, fma(x, m10, mul(n m11, m y))), m13)
 *   dst.z = add(fma(z, m22, fma(x, m20, mul(n m21, m y))), m23)
 * All loads precede the stores (src == dst works in place, as in the C body).
 */
        .align  2
        .global _re4dc_sh4_MTXMultVec
        .type   _re4dc_sh4_MTXMultVec, @function
_re4dc_sh4_MTXMultVec:          /* r4 = m, r5 = src, r6 = dst */
#if RE4DC_FP_CONTRACT_OFF && RE4DC_MULTVEC_SCHED
        /* design-logic P3b body: contract-off MTXMultVec with the three rows interleaved. Same
         * operations and operand roles as the serial body above (fpsym2 --strict), fr0-fr11 only,
         * every load before the first store (src == dst and m overlapping dst work as before). */
        fmov.s  @r5+,fr0        /* x */
        fmov.s  @r4+,fr6        /* m00 */
        fmov.s  @r5+,fr1        /* y */
        fmov    fr0,fr3
        fmov.s  @r4+,fr7        /* m01 */
        fmov    fr1,fr4
        fmov.s  @r5,fr2         /* z */
        fmul    fr6,fr3         /* mul(n x, m m00) */
        fmov.s  @r4+,fr6        /* m02 */
        fmul    fr7,fr4         /* mul(n y, m m01) */
        fmov    fr2,fr5
        fmov.s  @r4+,fr7        /* m03 */
        fmul    fr6,fr5         /* mul(n z, m m02) */
        fmov.s  @r4+,fr6        /* m10 */
        fadd    fr4,fr3         /* add(n x*m00, m y*m01) */
        fmov.s  @r4+,fr8        /* m11 */
        fmul    fr0,fr6         /* mul(n m10, m x) */
        fmov.s  @r4+,fr9        /* m12 */
        fmul    fr1,fr8         /* mul(n m11, m y) */
        fmov.s  @r4+,fr10       /* m13 */
        fmul    fr2,fr9         /* mul(n m12, m z) */
        fmov.s  @r4+,fr4        /* m20 */
        fadd    fr5,fr3         /* + z*m02 */
        fmov.s  @r4+,fr11       /* m21 */
        fmul    fr0,fr4         /* mul(n m20, m x) */
        fmov.s  @r4+,fr0        /* m22 */
        fmul    fr1,fr11        /* mul(n m21, m y) */
        fmov.s  @r4,fr5         /* m23 */
        fadd    fr8,fr6         /* add(n m10*x, m m11*y) */
        fmul    fr2,fr0         /* mul(n m22, m z) */
        fadd    fr7,fr3         /* dst.x = + m03 */
        fadd    fr11,fr4        /* add(n m20*x, m m21*y) */
        fadd    fr9,fr6         /* + m12*z */
        add     #12,r6
        fadd    fr0,fr4         /* + m22*z */
        fadd    fr10,fr6        /* dst.y = + m13 */
        fadd    fr5,fr4         /* dst.z = + m23 */
        fmov.s  fr4,@-r6
        fmov.s  fr6,@-r6
        rts
        fmov.s  fr3,@-r6
#elif RE4DC_FP_CONTRACT_OFF
        /* unfused: dst.k = add(add(add(mul(x, m_k0), mul(y, m_k1)), mul(z, m_k2)), m_k3) with
         * row 0 as mul(n x|y|z, m m0j) and rows 1, 2 as mul(n m_kj, m x|y|z) (GCC's operand roles) */
        fmov.s  @r5+,fr0        /* x */
        fmov.s  @r5+,fr1        /* y */
        fmov.s  @r5,fr2         /* z */
        fmov.s  @r4+,fr3        /* m00 */
        fmov.s  @r4+,fr4        /* m01 */
        fmov.s  @r4+,fr5        /* m02 */
        fmov.s  @r4+,fr6        /* m03 */
        fmov    fr0,fr7
        fmul    fr3,fr7         /* mul(x, m00) */
        fmov    fr1,fr8
        fmul    fr4,fr8         /* mul(y, m01) */
        fadd    fr8,fr7
        fmov    fr2,fr8
        fmul    fr5,fr8         /* mul(z, m02) */
        fadd    fr8,fr7
        fadd    fr6,fr7         /* dst.x */
        fmov.s  @r4+,fr3        /* m10 */
        fmul    fr0,fr3         /* mul(m10, x) */
        fmov.s  @r4+,fr4        /* m11 */
        fmul    fr1,fr4
        fadd    fr4,fr3
        fmov.s  @r4+,fr4        /* m12 */
        fmul    fr2,fr4
        fadd    fr4,fr3
        fmov.s  @r4+,fr4        /* m13 */
        fadd    fr4,fr3         /* dst.y */
        fmov.s  @r4+,fr5        /* m20 */
        fmul    fr0,fr5
        fmov.s  @r4+,fr4        /* m21 */
        fmul    fr1,fr4
        fadd    fr4,fr5
        fmov.s  @r4+,fr4        /* m22 */
        fmul    fr2,fr4
        fadd    fr4,fr5
        fmov.s  @r4,fr4         /* m23 */
        fadd    fr4,fr5         /* dst.z */
        add     #12,r6
        fmov.s  fr5,@-r6
        fmov.s  fr3,@-r6
        rts
        fmov.s  fr7,@-r6
#else
        fmov.s  @r5+,fr0        /* x */
        fmov.s  @r5+,fr3        /* y */
        fmov.s  @r5,fr8         /* z */
        fmov.s  @r4+,fr4        /* m00 */
        fmov.s  @r4+,fr5        /* m01 */
        fmov    fr3,fr1
        fmul    fr5,fr1         /* acc0 = y * m01 */
        fmac    fr0,fr4,fr1     /* acc0 = fma(x, m00, acc0) */
        fmov.s  @r4+,fr6        /* m02 */
        fmov.s  @r4+,fr7        /* m03 */
        fmov.s  @r4+,fr4        /* m10 */
        fmov.s  @r4+,fr2        /* m11 */
        fmul    fr3,fr2         /* acc1 = m11 * y */
        fmac    fr0,fr4,fr2
        fmov.s  @r4+,fr9        /* m12 */
        fmov.s  @r4+,fr10       /* m13 */
        fmov.s  @r4+,fr4        /* m20 */
        fmov.s  @r4+,fr5        /* m21 */
        fmul    fr3,fr5         /* acc2 = m21 * y */
        fmac    fr0,fr4,fr5
        fmov.s  @r4+,fr11       /* m22 */
        fmov.s  @r4,fr3         /* m23 */
        fmov    fr8,fr0         /* z */
        fmac    fr0,fr6,fr1
        fmac    fr0,fr9,fr2
        fmac    fr0,fr11,fr5
        fadd    fr7,fr1
        fadd    fr10,fr2
        fadd    fr3,fr5
        add     #12,r6
        fmov.s  fr5,@-r6
        fmov.s  fr2,@-r6
        rts
        fmov.s  fr1,@-r6
#endif
        .size   _re4dc_sh4_MTXMultVec, . - _re4dc_sh4_MTXMultVec

/* MTXMultVecSR(m, src, dst) -- C_MTXMultVecSR, 50 -> 30: MultVec without the translation. */
        .align  2
        .global _re4dc_sh4_MTXMultVecSR
        .type   _re4dc_sh4_MTXMultVecSR, @function
_re4dc_sh4_MTXMultVecSR:
#if RE4DC_FP_CONTRACT_OFF
        fmov.s  @r5+,fr0        /* x */
        fmov.s  @r5+,fr1        /* y */
        fmov.s  @r5,fr2         /* z */
        fmov.s  @r4+,fr3        /* m00 */
        fmov.s  @r4+,fr4        /* m01 */
        fmov.s  @r4+,fr5        /* m02 */
        add     #4,r4
        fmov    fr0,fr7
        fmul    fr3,fr7
        fmov    fr1,fr8
        fmul    fr4,fr8
        fadd    fr8,fr7
        fmov    fr2,fr8
        fmul    fr5,fr8
        fadd    fr8,fr7         /* dst.x */
        fmov.s  @r4+,fr3        /* m10 */
        fmul    fr0,fr3
        fmov.s  @r4+,fr4
        fmul    fr1,fr4
        fadd    fr4,fr3
        fmov.s  @r4+,fr4
        fmul    fr2,fr4
        fadd    fr4,fr3         /* dst.y */
        add     #4,r4
        fmov.s  @r4+,fr5        /* m20 */
        fmul    fr0,fr5
        fmov.s  @r4+,fr4
        fmul    fr1,fr4
        fadd    fr4,fr5
        fmov.s  @r4,fr4
        fmul    fr2,fr4
        fadd    fr4,fr5         /* dst.z */
        add     #12,r6
        fmov.s  fr5,@-r6
        fmov.s  fr3,@-r6
        rts
        fmov.s  fr7,@-r6
#else
        fmov.s  @r5+,fr0        /* x */
        fmov.s  @r5+,fr3        /* y */
        fmov.s  @r5,fr8         /* z */
        fmov.s  @r4+,fr4        /* m00 */
        fmov.s  @r4+,fr5        /* m01 */
        fmov    fr3,fr1
        fmul    fr5,fr1         /* acc0 = y * m01 */
        fmac    fr0,fr4,fr1
        fmov.s  @r4+,fr6        /* m02 */
        add     #4,r4
        fmov.s  @r4+,fr4        /* m10 */
        fmov.s  @r4+,fr2        /* m11 */
        fmul    fr3,fr2         /* acc1 = m11 * y */
        fmac    fr0,fr4,fr2
        fmov.s  @r4+,fr9        /* m12 */
        add     #4,r4
        fmov.s  @r4+,fr4        /* m20 */
        fmov.s  @r4+,fr5        /* m21 */
        fmul    fr3,fr5         /* acc2 = m21 * y */
        fmac    fr0,fr4,fr5
        fmov.s  @r4,fr11        /* m22 */
        fmov    fr8,fr0         /* z */
        fmac    fr0,fr6,fr1
        fmac    fr0,fr9,fr2
        fmac    fr0,fr11,fr5
        add     #12,r6
        fmov.s  fr5,@-r6
        fmov.s  fr2,@-r6
        rts
        fmov.s  fr1,@-r6
#endif
        .size   _re4dc_sh4_MTXMultVecSR, . - _re4dc_sh4_MTXMultVecSR

/* ---------------------------------------------------------------------------------------
 * VECAdd / VECSubtract (a, b, ab): 20 -> 14. ab.k = a.k (+|-) b.k (n = a, m = b).
 */
        .align  2
        .global _re4dc_sh4_VECAdd
        .type   _re4dc_sh4_VECAdd, @function
_re4dc_sh4_VECAdd:
        fmov.s  @r4+,fr1
        fmov.s  @r5+,fr2
        fmov.s  @r4+,fr3
        fmov.s  @r5+,fr4
        fmov.s  @r4,fr5
        fmov.s  @r5,fr6
        fadd    fr2,fr1
        fadd    fr4,fr3
        fadd    fr6,fr5
        add     #12,r6
        fmov.s  fr5,@-r6
        fmov.s  fr3,@-r6
        rts
        fmov.s  fr1,@-r6
        .size   _re4dc_sh4_VECAdd, . - _re4dc_sh4_VECAdd

        .align  2
        .global _re4dc_sh4_VECSubtract
        .type   _re4dc_sh4_VECSubtract, @function
_re4dc_sh4_VECSubtract:
        fmov.s  @r4+,fr1
        fmov.s  @r5+,fr2
        fmov.s  @r4+,fr3
        fmov.s  @r5+,fr4
        fmov.s  @r4,fr5
        fmov.s  @r5,fr6
        fsub    fr2,fr1
        fsub    fr4,fr3
        fsub    fr6,fr5
        add     #12,r6
        fmov.s  fr5,@-r6
        fmov.s  fr3,@-r6
        rts
        fmov.s  fr1,@-r6
        .size   _re4dc_sh4_VECSubtract, . - _re4dc_sh4_VECSubtract

/* VECScale(src, dst, scale in fr5): 15 -> 11. dst.k = mul(n src.k, m scale). */
        .align  2
        .global _re4dc_sh4_VECScale
        .type   _re4dc_sh4_VECScale, @function
_re4dc_sh4_VECScale:
        fmov.s  @r4+,fr1
        fmov.s  @r4+,fr2
        fmov.s  @r4,fr3
        fmul    fr5,fr1
        fmul    fr5,fr2
        fmul    fr5,fr3
        add     #12,r5
        fmov.s  fr3,@-r5
        fmov.s  fr2,@-r5
        rts
        fmov.s  fr1,@-r5
        .size   _re4dc_sh4_VECScale, . - _re4dc_sh4_VECScale

/* VECDotProduct(a, b): 15 -> 11. fma(FR0 a.z, FRm b.z, fma(FR0 a.x, FRm b.x, mul(n a.y, m b.y))). */
        .align  2
        .global _re4dc_sh4_VECDotProduct
        .type   _re4dc_sh4_VECDotProduct, @function
_re4dc_sh4_VECDotProduct:
#if RE4DC_FP_CONTRACT_OFF
        /* unfused: add(add(mul(ax, bx), mul(ay, by)), mul(az, bz)) */
        fmov.s  @r4+,fr0
        fmov.s  @r5+,fr1
        fmul    fr1,fr0
        fmov.s  @r4+,fr1
        fmov.s  @r5+,fr2
        fmul    fr2,fr1
        fadd    fr1,fr0
        fmov.s  @r4,fr1
        fmov.s  @r5,fr2
        fmul    fr2,fr1
        rts
        fadd    fr1,fr0
#else
        fmov.s  @r4+,fr0        /* a.x */
        fmov.s  @r5+,fr2        /* b.x */
        fmov.s  @r4+,fr1        /* a.y */
        fmov.s  @r5+,fr3        /* b.y */
        fmul    fr3,fr1
        fmac    fr0,fr2,fr1
        fmov.s  @r4,fr0         /* a.z */
        fmov.s  @r5,fr2         /* b.z */
        fmac    fr0,fr2,fr1
        rts
        fmov    fr1,fr0
#endif
        .size   _re4dc_sh4_VECDotProduct, . - _re4dc_sh4_VECDotProduct

/* VECCrossProduct(a, b, axb): 32 -> 22.
 *   x = sub(mul(ay, bz), mul(az, by)); y = sub(mul(az, bx), mul(bz, ax)); z = sub(mul(by, ax), mul(ay, bx))
 * All loads precede the stores (in place safe, as in the C body). */
        .align  2
        .global _re4dc_sh4_VECCrossProduct
        .type   _re4dc_sh4_VECCrossProduct, @function
_re4dc_sh4_VECCrossProduct:
        fmov.s  @r4+,fr7        /* ax */
        fmov.s  @r4+,fr3        /* ay */
        fmov.s  @r4,fr2         /* az */
        fmov.s  @r5+,fr6        /* bx */
        fmov.s  @r5+,fr1        /* by */
        fmov.s  @r5,fr4         /* bz */
        fmov    fr3,fr5
        fmul    fr4,fr5         /* ay*bz */
        fmov    fr2,fr0
        fmul    fr1,fr0         /* az*by */
        fsub    fr0,fr5
        fmul    fr6,fr2         /* az*bx */
        fmul    fr7,fr4         /* bz*ax */
        fsub    fr4,fr2
        fmul    fr7,fr1         /* by*ax */
        fmul    fr6,fr3         /* ay*bx */
        fsub    fr3,fr1
        add     #12,r6
        fmov.s  fr1,@-r6
        fmov.s  fr2,@-r6
        rts
        fmov.s  fr5,@-r6
        .size   _re4dc_sh4_VECCrossProduct, . - _re4dc_sh4_VECCrossProduct

/* ---------------------------------------------------------------------------------------
 * Pure data movement (no arithmetic): MTXCopy 69 -> 28, MTXTranspose 79 -> 26,
 * PSMTXReorder 38 -> 27, MTXIdentity / MTXScale / MTXTrans 36 -> 15..16.
 */
        .align  2
        .global _re4dc_sh4_MTXCopy
        .type   _re4dc_sh4_MTXCopy, @function
_re4dc_sh4_MTXCopy:             /* r4 = src, r5 = dst; nothing when src == dst */
        cmp/eq  r4,r5
        bt      9f
        fmov.s  @r4+,fr0
        fmov.s  @r4+,fr1
        fmov.s  @r4+,fr2
        fmov.s  @r4+,fr3
        fmov.s  @r4+,fr4
        fmov.s  @r4+,fr5
        fmov.s  @r4+,fr6
        fmov.s  @r4+,fr7
        fmov.s  @r4+,fr8
        fmov.s  @r4+,fr9
        fmov.s  @r4+,fr10
        fmov.s  @r4,fr11
        add     #48,r5
        fmov.s  fr11,@-r5
        fmov.s  fr10,@-r5
        fmov.s  fr9,@-r5
        fmov.s  fr8,@-r5
        fmov.s  fr7,@-r5
        fmov.s  fr6,@-r5
        fmov.s  fr5,@-r5
        fmov.s  fr4,@-r5
        fmov.s  fr3,@-r5
        fmov.s  fr2,@-r5
        fmov.s  fr1,@-r5
        fmov.s  fr0,@-r5
9:      rts
        nop
        .size   _re4dc_sh4_MTXCopy, . - _re4dc_sh4_MTXCopy

        .align  2
        .global _re4dc_sh4_MTXTranspose
        .type   _re4dc_sh4_MTXTranspose, @function
_re4dc_sh4_MTXTranspose:        /* r4 = src, r5 = xPose; loads first, so src == xPose works */
        fmov.s  @r4+,fr0        /* s00 */
        fmov.s  @r4+,fr1        /* s01 */
        fmov.s  @r4+,fr2        /* s02 */
        add     #4,r4
        fmov.s  @r4+,fr3        /* s10 */
        fmov.s  @r4+,fr4        /* s11 */
        fmov.s  @r4+,fr5        /* s12 */
        add     #4,r4
        fmov.s  @r4+,fr6        /* s20 */
        fmov.s  @r4+,fr7        /* s21 */
        fmov.s  @r4,fr8         /* s22 */
        fldi0   fr9
        add     #48,r5
        fmov.s  fr9,@-r5        /* x23 = 0 */
        fmov.s  fr8,@-r5        /* x22 = s22 */
        fmov.s  fr5,@-r5        /* x21 = s12 */
        fmov.s  fr2,@-r5        /* x20 = s02 */
        fmov.s  fr9,@-r5        /* x13 */
        fmov.s  fr7,@-r5        /* x12 = s21 */
        fmov.s  fr4,@-r5        /* x11 = s11 */
        fmov.s  fr1,@-r5        /* x10 = s01 */
        fmov.s  fr9,@-r5        /* x03 */
        fmov.s  fr6,@-r5        /* x02 = s20 */
        fmov.s  fr3,@-r5        /* x01 = s10 */
        rts
        fmov.s  fr0,@-r5        /* x00 = s00 */
        .size   _re4dc_sh4_MTXTranspose, . - _re4dc_sh4_MTXTranspose

/* PSMTXReorder(src 3x4, dst 4x3): dst[i][k] = src[k][i]. Callers (trans.cpp) write the LC
 * skinning palette from a stack matrix: src and dst never alias (the C loop is not in-place
 * safe either). */
        .align  2
        .global _re4dc_sh4_MTXReorder
        .type   _re4dc_sh4_MTXReorder, @function
_re4dc_sh4_MTXReorder:
        fmov.s  @r4+,fr0        /* s00 */
        fmov.s  @r4+,fr1        /* s01 */
        fmov.s  @r4+,fr2        /* s02 */
        fmov.s  @r4+,fr3        /* s03 */
        fmov.s  @r4+,fr4        /* s10 */
        fmov.s  @r4+,fr5        /* s11 */
        fmov.s  @r4+,fr6        /* s12 */
        fmov.s  @r4+,fr7        /* s13 */
        fmov.s  @r4+,fr8        /* s20 */
        fmov.s  @r4+,fr9        /* s21 */
        fmov.s  @r4+,fr10       /* s22 */
        fmov.s  @r4,fr11        /* s23 */
        add     #48,r5
        fmov.s  fr11,@-r5       /* d32 = s23 */
        fmov.s  fr7,@-r5        /* d31 = s13 */
        fmov.s  fr3,@-r5        /* d30 = s03 */
        fmov.s  fr10,@-r5       /* d22 = s22 */
        fmov.s  fr6,@-r5        /* d21 = s12 */
        fmov.s  fr2,@-r5        /* d20 = s02 */
        fmov.s  fr9,@-r5        /* d12 = s21 */
        fmov.s  fr5,@-r5        /* d11 = s11 */
        fmov.s  fr1,@-r5        /* d10 = s01 */
        fmov.s  fr8,@-r5        /* d02 = s20 */
        fmov.s  fr4,@-r5        /* d01 = s10 */
        rts
        fmov.s  fr0,@-r5        /* d00 = s00 */
        .size   _re4dc_sh4_MTXReorder, . - _re4dc_sh4_MTXReorder

        .align  2
        .global _re4dc_sh4_MTXIdentity
        .type   _re4dc_sh4_MTXIdentity, @function
_re4dc_sh4_MTXIdentity:
        fldi1   fr2
        fldi0   fr1
        add     #48,r4
        fmov.s  fr1,@-r4
        fmov.s  fr2,@-r4        /* m22 */
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr2,@-r4        /* m11 */
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        rts
        fmov.s  fr2,@-r4        /* m00 */
        .size   _re4dc_sh4_MTXIdentity, . - _re4dc_sh4_MTXIdentity

        .align  2
        .global _re4dc_sh4_MTXScale
        .type   _re4dc_sh4_MTXScale, @function
_re4dc_sh4_MTXScale:            /* xS fr5, yS fr4, zS fr7 */
        fldi0   fr1
        add     #48,r4
        fmov.s  fr1,@-r4
        fmov.s  fr7,@-r4        /* m22 = zS */
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr4,@-r4        /* m11 = yS */
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        rts
        fmov.s  fr5,@-r4        /* m00 = xS */
        .size   _re4dc_sh4_MTXScale, . - _re4dc_sh4_MTXScale

        .align  2
        .global _re4dc_sh4_MTXTrans
        .type   _re4dc_sh4_MTXTrans, @function
_re4dc_sh4_MTXTrans:            /* xT fr5, yT fr4, zT fr7 */
        fldi1   fr2
        fldi0   fr1
        add     #48,r4
        fmov.s  fr7,@-r4        /* m23 = zT */
        fmov.s  fr2,@-r4        /* m22 */
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        fmov.s  fr4,@-r4        /* m13 = yT */
        fmov.s  fr1,@-r4
        fmov.s  fr2,@-r4        /* m11 */
        fmov.s  fr1,@-r4
        fmov.s  fr5,@-r4        /* m03 = xT */
        fmov.s  fr1,@-r4
        fmov.s  fr1,@-r4
        rts
        fmov.s  fr2,@-r4        /* m00 */
        .size   _re4dc_sh4_MTXTrans, . - _re4dc_sh4_MTXTrans

/* ---------------------------------------------------------------------------------------
 * MTXInverse(src, inv) -> 1, or 0 (inv untouched) when the determinant is zero.
 * C_MTXInverse, 242 -> 150 instruction words (no stack frame, no MTXCopy call). GCC dataflow (mul(n, m) = fmul m,n):
 *   det = sub(sub(sub(fma(FR0 mul(s02,s10), FRm s21, fma(FR0 mul(s00,s11), FRm s22,
 *               mul(mul(s01,s12),s20))), mul(mul(s20,s11),s02)), mul(mul(s10,s01),s22)),
 *               mul(mul(s00,s21),s12));  det == 0 -> return 0;  r = div(1, det)
 *   m00 = mul(sub(mul(s22,s11), mul(s21,s12)), r)        m01 = mul(neg(sub(mul(s01,s22), mul(s21,s02))), r)
 *   m02 = mul(sub(mul(s01,s12), mul(s11,s02)), r)        m10 = mul(neg(sub(mul(s10,s22), mul(s20,s12))), r)
 *   m11 = mul(sub(mul(s00,s22), mul(s20,s02)), r)        m12 = mul(neg(sub(mul(s00,s12), mul(s10,s02))), r)
 *   m20 = mul(sub(mul(s10,s21), mul(s20,s11)), r)        m21 = mul(neg(sub(mul(s00,s21), mul(s20,s01))), r)
 *   m22 = mul(sub(mul(s00,s11), mul(s10,s01)), r)
 *   mi3 = sub(sub(mul(neg(mi0), s03), mul(mi1, s13)), mul(mi2, s23))
 * src == inv (in place) needs no temporary: all nine rotation values are in registers before the
 * first store, s03/s13/s23 (column 3) are loaded before any column-3 store, and mi0..mi2 are
 * re-read from inv after being stored (bit-exact fmov).
 * fr1..fr9 = s00 s01 s02 s10 s11 s12 s20 s21 s22, fr0 = r, fr10/fr11 temporaries.
 */
        .macro  COFACTOR a, b, c, d, neg
        fmov    \a,fr10
        fmul    \b,fr10         /* mul(a, b) */
        fmov    \c,fr11
        fmul    \d,fr11         /* mul(c, d) */
        fsub    fr11,fr10
        .if \neg
        fneg    fr10
        .endif
        fmul    fr0,fr10        /* mul(., r) */
        fmov.s  fr10,@-r6
        .endm

        .macro  TRANSLATION
        fmov.s  @r6+,fr4        /* mi0 (as stored) */
        fmov.s  @r6+,fr5        /* mi1 */
        fmov.s  @r6+,fr6        /* mi2 */
        fneg    fr4
        fmul    fr1,fr4         /* mul(neg(mi0), s03) */
        fmul    fr2,fr5         /* mul(mi1, s13) */
        fsub    fr5,fr4
        fmul    fr3,fr6         /* mul(mi2, s23) */
        fsub    fr6,fr4
        fmov.s  fr4,@r6         /* mi3 */
        .endm

#if RE4DC_FP_CONTRACT_OFF && RE4DC_MTXINV_SCHED
/* lane gskel GAME_MTXINV_SCHED: contract-off MTXInverse, list-scheduled (generated by
 * tools/game30/mtx_inverse_sched.py --tries 1500 --local 6000 --save 4 --nocse --seed 3). Same dataflow and operand roles as the RE4DC_FP_CONTRACT_OFF body
 * below (see the generator); proof:
 * tools/game30/prove_mtxinv_sched.sh (fpsym2 --strict vs the RE4DC_FP_CONTRACT_OFF body below from a
 * build without the knob, and commutative-mode vs the build's own C_MTXInverse, the standard that body
 * meets; every alias partition, both det branches). Static schedule 86 cycles (branch at c33), 156 instructions. */
        .align  2
        .global _re4dc_sh4_MTXInverse
        .type   _re4dc_sh4_MTXInverse, @function
_re4dc_sh4_MTXInverse:                     /* r4 = src, r5 = inv */
        fmov.s	@r4+,fr0         /* c0 s00 */
        fmov.s	@r4+,fr1         /* c1 s01 */
        fmov.s	@r4+,fr2         /* c2 s02 */
        add	#4,r4               /* c3 */
        fmov	fr1,fr3            /* c3 */
        fmov.s	@r4+,fr4         /* c4 s10 */
        fmov.s	@r4+,fr5         /* c5 s11 */
        fmov.s	@r4+,fr6         /* c6 s12 */
        fmov	fr2,fr7            /* c7 */
        add	#4,r4               /* c7 */
        fmov.s	@r4+,fr8         /* c8 s20 */
        fmul	fr6,fr3            /* c8 mul(s01,s12) */
        fmov	fr0,fr9            /* c9 */
        fmul	fr4,fr7            /* c9 mul(s02,s10) */
        fmul	fr5,fr9            /* c10 mul(s00,s11) */
        fmov.s	@r4+,fr10        /* c10 s21 */
        fmov.s	@r4+,fr11        /* c11 s22 */
        fmul	fr8,fr3            /* c11 T2 */
        fmul	fr10,fr7           /* c12 T3 */
        fmov.s	fr12,@-r15       /* c12 */
        fmul	fr11,fr9           /* c13 T1 */
        fmov	fr8,fr12           /* c13 */
        fmul	fr5,fr12           /* c14 mul(s20,s11) */
        fmov.s	fr13,@-r15       /* c14 */
        fmov	fr4,fr13           /* c15 */
        fadd	fr3,fr9            /* c16 */
        fmov.s	fr14,@-r15       /* c16 */
        fmov	fr0,fr3            /* c17 */
        fmul	fr2,fr12           /* c17 T4 */
        fmul	fr1,fr13           /* c18 mul(s10,s01) */
        fldi0	fr14              /* c18 */
        fadd	fr7,fr9            /* c19 */
        fmov.s	fr15,@-r15       /* c19 */
        fmul	fr10,fr3           /* c20 mul(s00,s21) */
        fldi1	fr7               /* c20 */
        fmul	fr11,fr13          /* c21 T5 */
        fmov	fr11,fr15          /* c21 */
        fsub	fr12,fr9           /* c22 */
        fmul	fr6,fr3            /* c23 T6 */
        fmov	fr10,fr12          /* c23 */
        fmul	fr5,fr15           /* c24 mul(s22,s11) */
        fsub	fr13,fr9           /* c25 */
        fmov	fr1,fr13           /* c26 */
        fmul	fr6,fr12           /* c26 mul(s21,s12) */
        fmul	fr11,fr13          /* c27 mul(s01,s22) */
        fsub	fr3,fr9            /* c28 det */
        fmov	fr10,fr3           /* c29 */
        fsub	fr12,fr15          /* c29 d00 */
        fmov	fr1,fr12           /* c30 */
        fmul	fr2,fr3            /* c30 mul(s21,s02) */
        fcmp/eq	fr14,fr9        /* c31 */
        fmul	fr6,fr12           /* c32 mul(s01,s12) */
        fmov	fr5,fr14           /* c32 */
        bt	9f                   /* c33 */
        fmul	fr2,fr14           /* c33 mul(s11,s02) */
        fdiv	fr9,fr7            /* c34 r = 1/det */
        mov	#4,r0               /* c34 */
        fsub	fr3,fr13           /* c35 d01 */
        fmov	fr4,fr9            /* c35 */
        fsub	fr14,fr12          /* c36 d02 */
        fmov	fr8,fr3            /* c36 */
        fmul	fr11,fr9           /* c37 mul(s10,s22) */
        fmov	fr0,fr14           /* c37 */
        fmul	fr11,fr14          /* c38 mul(s00,s22) */
        fneg	fr13               /* c38 */
        fmul	fr6,fr3            /* c39 mul(s20,s12) */
        fmov	fr8,fr11           /* c39 */
        fmul	fr2,fr11           /* c40 mul(s20,s02) */
        fsub	fr3,fr9            /* c42 d10 */
        fmov	fr0,fr3            /* c43 */
        fsub	fr11,fr14          /* c43 d11 */
        fmov	fr4,fr11           /* c44 */
        fmul	fr6,fr3            /* c44 mul(s00,s12) */
        fmul	fr2,fr11           /* c45 mul(s10,s02) */
        fneg	fr9                /* c45 */
        fmov	fr0,fr6            /* c46 */
        fmul	fr7,fr13           /* c46 m01 */
        fmul	fr10,fr6           /* c47 mul(s00,s21) */
        fmov	fr4,fr2            /* c47 */
        fmul	fr10,fr2           /* c48 mul(s10,s21) */
        fsub	fr11,fr3           /* c49 d12 */
        fmov	fr8,fr10           /* c49 */
        fmul	fr5,fr10           /* c50 mul(s20,s11) */
        fmov.s	@r4,fr11         /* c50 s23 */
        fmul	fr1,fr8            /* c51 mul(s20,s01) */
        add	#-16,r4             /* c51 */
        fmul	fr1,fr4            /* c52 mul(s10,s01) */
        fmov.s	fr13,@(r0,r5)    /* c52 m01 */
        fsub	fr10,fr2           /* c53 d20 */
        mov	#8,r0               /* c53 */
        fsub	fr8,fr6            /* c54 d21 */
        fmov.s	@r4,fr1          /* c54 s13 */
        fmul	fr7,fr15           /* c55 m00 */
        add	#-16,r4             /* c55 */
        fmul	fr7,fr14           /* c56 m11 */
        fmov.s	@r4,fr10         /* c56 s03 */
        fneg	fr6                /* c57 */
        fmul	fr5,fr0            /* c57 mul(s00,s11) */
        fmul	fr7,fr12           /* c58 m02 */
        fmov.s	fr15,@r5         /* c58 m00 */
        fneg	fr15               /* c59 */
        fmul	fr7,fr6            /* c59 m21 */
        fmul	fr10,fr15          /* c60 */
        fneg	fr3                /* c60 */
        fmov.s	fr12,@(r0,r5)    /* c61 m02 */
        fmul	fr7,fr3            /* c61 m12 */
        mov	#16,r0              /* c62 */
        fmul	fr7,fr9            /* c62 m10 */
        fsub	fr4,fr0            /* c63 d22 */
        fmul	fr7,fr2            /* c64 m20 */
        fmul	fr1,fr13           /* c65 */
        fmov.s	fr9,@(r0,r5)     /* c65 m10 */
        fmul	fr7,fr0            /* c66 m22 */
        mov	#20,r0              /* c66 */
        fmov.s	fr14,@(r0,r5)    /* c67 m11 */
        fmul	fr11,fr12          /* c67 */
        mov	#24,r0              /* c68 */
        fmul	fr1,fr14           /* c68 */
        fmov.s	fr3,@(r0,r5)     /* c69 m12 */
        fsub	fr13,fr15          /* c69 */
        fmul	fr11,fr3           /* c70 */
        fneg	fr9                /* c70 */
        fmul	fr10,fr9           /* c71 */
        mov	#32,r0              /* c71 */
        fmov.s	fr2,@(r0,r5)     /* c72 m20 */
        fsub	fr12,fr15          /* c72 m03 */
        mov	#36,r0              /* c73 */
        fneg	fr2                /* c73 */
        fmov.s	fr6,@(r0,r5)     /* c74 m21 */
        fmul	fr10,fr2           /* c74 */
        mov	#40,r0              /* c75 */
        fmul	fr1,fr6            /* c75 */
        fsub	fr14,fr9           /* c76 */
        fmov.s	fr0,@(r0,r5)     /* c76 m22 */
        fmul	fr11,fr0           /* c77 */
        mov	#12,r0              /* c77 */
        fmov.s	fr15,@(r0,r5)    /* c78 m03 */
        fsub	fr6,fr2            /* c78 */
        fsub	fr3,fr9            /* c79 m13 */
        mov	#28,r0              /* c79 */
        fmov.s	@r15+,fr15       /* c80 pop */
        fsub	fr0,fr2            /* c81 m23 */
        fmov.s	@r15+,fr14       /* c81 pop */
        fmov.s	fr9,@(r0,r5)     /* c82 m13 */
        mov	#44,r0              /* c83 */
        fmov.s	@r15+,fr13       /* c83 pop */
        fmov.s	fr2,@(r0,r5)     /* c84 m23 */
        fmov.s	@r15+,fr12       /* c85 pop */
        rts
        mov     #1,r0
9:
        fmov.s	@r15+,fr15
        fmov.s	@r15+,fr14
        fmov.s	@r15+,fr13
        fmov.s	@r15+,fr12
        rts
        mov     #0,r0           /* det == 0: inv untouched */
        .size   _re4dc_sh4_MTXInverse, . - _re4dc_sh4_MTXInverse
#else
        .align  2
        .global _re4dc_sh4_MTXInverse
        .type   _re4dc_sh4_MTXInverse, @function
_re4dc_sh4_MTXInverse:          /* r4 = src, r5 = inv */
        fmov.s  @r4+,fr1        /* s00 */
        fmov.s  @r4+,fr2        /* s01 */
        fmov.s  @r4+,fr3        /* s02 */
        add     #4,r4
        fmov.s  @r4+,fr4        /* s10 */
        fmov.s  @r4+,fr5        /* s11 */
        fmov.s  @r4+,fr6        /* s12 */
        add     #4,r4
        fmov.s  @r4+,fr7        /* s20 */
        fmov.s  @r4+,fr8        /* s21 */
        fmov.s  @r4,fr9         /* s22; r4 = src + 40 */
#if RE4DC_FP_CONTRACT_OFF
        /* unfused: det = add(add(mul(mul(s00,s11),s22), mul(mul(s01,s12),s20)), mul(mul(s02,s10),s21)) - ... */
        fmov    fr1,fr10
        fmul    fr5,fr10
        fmul    fr9,fr10        /* mul(mul(s00, s11), s22) */
        fmov    fr2,fr11
        fmul    fr6,fr11
        fmul    fr7,fr11        /* mul(mul(s01, s12), s20) */
        fadd    fr11,fr10
        fmov    fr3,fr11
        fmul    fr4,fr11
        fmul    fr8,fr11        /* mul(mul(s02, s10), s21) */
        fadd    fr11,fr10
#else
        fmov    fr1,fr0
        fmul    fr5,fr0         /* P1 = mul(s00, s11) */
        fmov    fr2,fr10
        fmul    fr6,fr10        /* mul(s01, s12) */
        fmul    fr7,fr10        /* Q = mul(., s20) */
        fmac    fr0,fr9,fr10    /* fma(P1, s22, Q) */
        fmov    fr3,fr0
        fmul    fr4,fr0         /* P2 = mul(s02, s10) */
        fmac    fr0,fr8,fr10    /* fma(P2, s21, .) */
#endif
        fmov    fr7,fr0
        fmul    fr5,fr0
        fmul    fr3,fr0         /* mul(mul(s20, s11), s02) */
        fsub    fr0,fr10
        fmov    fr4,fr0
        fmul    fr2,fr0
        fmul    fr9,fr0         /* mul(mul(s10, s01), s22) */
        fsub    fr0,fr10
        fmov    fr1,fr0
        fmul    fr8,fr0
        fmul    fr6,fr0         /* mul(mul(s00, s21), s12) */
        fsub    fr0,fr10        /* det */
        fldi0   fr11
        fcmp/eq fr11,fr10
        bf/s    1f
        mov     r5,r6
        rts
        mov     #0,r0
1:      fldi1   fr0
        fdiv    fr10,fr0        /* r = 1 / det */
        add     #44,r6          /* cofactors stored backwards from m22 */
        COFACTOR fr1,fr5,fr4,fr2,0   /* m22 = mul(sub(mul(s00,s11), mul(s10,s01)), r) */
        COFACTOR fr1,fr8,fr7,fr2,1   /* m21 */
        COFACTOR fr4,fr8,fr7,fr5,0   /* m20 = mul(sub(mul(s10,s21), mul(s20,s11)), r) */
        add     #-4,r6               /* skip m13 */
        COFACTOR fr1,fr6,fr4,fr3,1   /* m12 */
        COFACTOR fr1,fr9,fr7,fr3,0   /* m11 */
        COFACTOR fr4,fr9,fr7,fr6,1   /* m10 */
        add     #-4,r6               /* skip m03 */
        COFACTOR fr2,fr6,fr5,fr3,0   /* m02 */
        COFACTOR fr2,fr9,fr8,fr3,1   /* m01 */
        COFACTOR fr9,fr5,fr8,fr6,0   /* m00 = mul(sub(mul(s22,s11), mul(s21,s12)), r) */
        add     #4,r4
        fmov.s  @r4,fr3         /* s23 */
        add     #-16,r4
        fmov.s  @r4,fr2         /* s13 */
        add     #-16,r4
        fmov.s  @r4,fr1         /* s03 */
        TRANSLATION             /* m03; r6 = inv + 12 */
        add     #4,r6
        TRANSLATION             /* m13 */
        add     #4,r6
        TRANSLATION             /* m23 */
        rts
        mov     #1,r0
        .size   _re4dc_sh4_MTXInverse, . - _re4dc_sh4_MTXInverse
#endif /* RE4DC_MTXINV_SCHED */
