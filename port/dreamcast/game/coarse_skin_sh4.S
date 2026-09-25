/* coarse_skin_sh4.S -- COARSE_SKIN_FTRV (game30.mk): the coarse actor adapters' palette matrices
 * (coarse_actor.cpp, coarse_ganado.cpp) with FTRV instead of the C concat + weight-blend loops.
 *
 * re4dc_coarse_skin_bones(inv, jobs, n): per job, T = inv x P x B as a 3x4 matrix stored as four
 *   columns of three floats (the palette layout native_actor_fast reads: R0, R1, R2, t).
 *   inv: 16 floats, the root inverse as XMTRX (column-major 4x4, bottom row 0 0 0 1).
 *   job: {const float* P; const float* B; float* T;} with P, B row-major 3x4 (Mtx).
 *   Two FTRV passes: XMTRX = inv transforms P's columns (w 0 0 0 1) into A = inv x P; FRCHG makes
 *   A the XMTRX (its columns are fv0 / fv4 / fv8 / fv12); B's columns are transformed by it.
 * re4dc_coarse_skin_groups(stream, groups, T, out, entries): palette entries grouped by their bone
 *   set. Per group and block q (0..2): XMTRX columns = the bones' 4-float blocks q of T, then one
 *   FTRV per entry with its weights as the vector (w3 = 0; missing weights 0); the result is block q
 *   of the entry's 12 floats. One-bone groups (weight 1.0) copy the bone's T to each entry.
 *   group header (16 bytes): s16 offset[3] (bytes into T: bone * 48); u16 count; u16 n; u16 pad[3];
 *   then n entries (24 bytes): float w[4]; u32 out offset (entry * 48); u32 pad.
 *
 * Memory: the output lines are first allocated with MOVCA.L (no fill from memory: every byte of them
 * is written before it is read), so out must be 32-byte aligned with room up to the next 32-byte
 * boundary after entries x 48 bytes. (No PREF: back-to-back PREFs serialize on the SH-4; the bones
 * routine measured slower with them, cl32.)
 * Ordering: each FTRV's result is consumed (stored) before XMTRX or the FR bank changes, so no
 * FTRV is in flight when its matrix is rewritten.
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0 FR=0 on entry and exit. fr12-fr15 (bank 0) are saved by
 * the bones routine; the back bank (XMTRX) is clobbered, as the other FTRV kernels do (every
 * XMTRX user loads it at the point of use). T, out and the entries must be 8-byte aligned.
 */
        .text
        .align  2
        .global _re4dc_coarse_skin_bones
        .type   _re4dc_coarse_skin_bones, @function
_re4dc_coarse_skin_bones:               /* r4 = inv (16 floats), r5 = jobs, r6 = n */
        tst     r6,r6
        bt      .Lb_ret
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
.Lb_job:
        fschg                           /* SZ=1: XMTRX = inv */
        mov     r4,r0
        fmov    @r0+,xd0
        fmov    @r0+,xd2
        fmov    @r0+,xd4
        fmov    @r0+,xd6
        fmov    @r0+,xd8
        fmov    @r0+,xd10
        fmov    @r0+,xd12
        fmov    @r0+,xd14
        fschg                           /* SZ=0 */
        mov.l   @r5+,r1                 /* P */
        mov.l   @r5+,r2                 /* B */
        mov.l   @r5+,r3                 /* T */
        /* P's columns: fv0 = (P00 P10 P20 0), fv4 = (P01 P11 P21 0), fv8 = (P02 ...), fv12 = (P03 P13 P23 1) */
        fmov.s  @r1+,fr0
        fmov.s  @r1+,fr4
        fmov.s  @r1+,fr8
        fmov.s  @r1+,fr12
        fmov.s  @r1+,fr1
        fmov.s  @r1+,fr5
        fmov.s  @r1+,fr9
        fmov.s  @r1+,fr13
        fmov.s  @r1+,fr2
        fmov.s  @r1+,fr6
        fmov.s  @r1+,fr10
        fmov.s  @r1+,fr14
        fldi0   fr3
        fldi0   fr7
        fldi0   fr11
        fldi1   fr15
        ftrv    xmtrx,fv0
        ftrv    xmtrx,fv4
        ftrv    xmtrx,fv8
        ftrv    xmtrx,fv12
        fmov    fr15,fr15               /* waits for the last FTRV: no FTRV in flight across FRCHG */
        frchg                           /* XMTRX = A = inv x P; the FR bank is the old XMTRX (scratch) */
        fmov.s  @r2+,fr0
        fmov.s  @r2+,fr4
        fmov.s  @r2+,fr8
        fmov.s  @r2+,fr12
        fmov.s  @r2+,fr1
        fmov.s  @r2+,fr5
        fmov.s  @r2+,fr9
        fmov.s  @r2+,fr13
        fmov.s  @r2+,fr2
        fmov.s  @r2+,fr6
        fmov.s  @r2+,fr10
        fmov.s  @r2+,fr14
        fldi0   fr3
        fldi0   fr7
        fldi0   fr11
        fldi1   fr15
        ftrv    xmtrx,fv0
        ftrv    xmtrx,fv4
        ftrv    xmtrx,fv8
        ftrv    xmtrx,fv12
        add     #48,r3                  /* T: column c = fv(4c) rows 0-2, stored backwards */
        fmov.s  fr14,@-r3
        fmov.s  fr13,@-r3
        fmov.s  fr12,@-r3
        fmov.s  fr10,@-r3
        fmov.s  fr9,@-r3
        fmov.s  fr8,@-r3
        fmov.s  fr6,@-r3
        fmov.s  fr5,@-r3
        fmov.s  fr4,@-r3
        fmov.s  fr2,@-r3
        fmov.s  fr1,@-r3
        fmov.s  fr0,@-r3
        frchg                           /* FPSCR.FR back: bank 0 is the FR bank again */
        dt      r6
        bf      .Lb_job
        fmov.s  @r15+,fr15
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
.Lb_ret:
        rts
        nop
        .size   _re4dc_coarse_skin_bones, .-_re4dc_coarse_skin_bones

        .align  2
        .global _re4dc_coarse_skin_groups
        .type   _re4dc_coarse_skin_groups, @function
/* One group's block q (q = 0, 1, 2): XMTRX columns = the group's bones' 4-float block q (T pointers
 * r1 / r2 / r3 stream through the rows), then every entry of the group: FTRV of its weights, the
 * result stored at out + entry offset + 16q (r10). Two vectors (fv4 / fv8) alternate so one FTRV
 * runs while the previous result is stored; the block's last result is stored before the next block
 * rewrites XMTRX. r0 = 8 (the @(r0,Rn) store), r4 = the group's entries, r8 = n, r9 = count. */
        .macro  GROUP_BLOCK
        fmov    @r1+,xd0
        fmov    @r1+,xd2
        fmov    @r2+,xd4
        fmov    @r2+,xd6
        mov     #3,r13
        cmp/eq  r13,r9
        bf      1f
        fmov    @r3+,xd8
        fmov    @r3+,xd10
1:      mov     r4,r11
        mov     r8,r12
        fmov    @r11+,dr4
        fmov    @r11+,dr6
        ftrv    xmtrx,fv4
        mov.l   @r11+,r13
        add     #4,r11
        dt      r12
        bt/s    3f
        add     r10,r13
2:      fmov    @r11+,dr8
        fmov    @r11+,dr10
        ftrv    xmtrx,fv8
        mov.l   @r11+,r14
        add     #4,r11
        add     r10,r14
        fmov    dr4,@r13
        fmov    dr6,@(r0,r13)
        dt      r12
        bt      4f
        fmov    @r11+,dr4
        fmov    @r11+,dr6
        ftrv    xmtrx,fv4
        mov.l   @r11+,r13
        add     #4,r11
        add     r10,r13
        fmov    dr8,@r14
        fmov    dr10,@(r0,r14)
        dt      r12
        bf      2b
3:      fmov    dr4,@r13
        bra     5f
        fmov    dr6,@(r0,r13)
4:      fmov    dr8,@r14
        fmov    dr10,@(r0,r14)
5:      add     #16,r10
        .endm

_re4dc_coarse_skin_groups:              /* r4 = stream, r5 = groups, r6 = T, r7 = out, @r15 = entries */
        tst     r5,r5
        bt      .Lg_ret
        mov.l   @r15,r1                 /* output lines: ceil(entries x 48 / 32), allocated without a fill */
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        mov.l   r10,@-r15
        mov.l   r11,@-r15
        mov.l   r12,@-r15
        mov.l   r13,@-r15
        mov.l   r14,@-r15
        mov     r1,r2
        shll    r1
        add     r2,r1
        shll2   r1
        shll2   r1
        add     #31,r1
        shlr2   r1
        shlr2   r1
        shlr    r1
        tst     r1,r1
        bt/s    .Lg_start
        mov     r7,r2
.Lg_alloc:
        movca.l r0,@r2
        dt      r1
        bf/s    .Lg_alloc
        add     #32,r2
.Lg_start:
        fschg                           /* SZ=1 for the whole routine: pair moves */
        fldi0   fr0
        fldi0   fr1
        fmov    dr0,xd8                 /* XMTRX column 2 = 0 until a three-bone group loads it */
        fmov    dr0,xd10
        fmov    dr0,xd12                /* column 3 = 0 (w3 = 0) */
        fmov    dr0,xd14
        mov     #8,r0
.Lg_group:
        mov.w   @r4+,r1                 /* header: T offsets of the bones, count, n, 3 pad */
        add     r6,r1
        mov.w   @r4+,r2
        add     r6,r2
        mov.w   @r4+,r3
        add     r6,r3
        mov.w   @r4+,r9
        mov.w   @r4+,r8
        add     #6,r4                   /* the group's entries */
        mov     #1,r13
        cmp/eq  r13,r9
        bt/s    .Lg_copy
        mov     r7,r10
        GROUP_BLOCK
        GROUP_BLOCK
        GROUP_BLOCK
        bra     .Lg_next
        nop
.Lg_copy:                               /* one bone, weight 1.0: its 12 floats to every entry */
        fmov    @r1+,xd0
        fmov    @r1+,xd2
        fmov    @r1+,xd4
        fmov    @r1+,xd6
        fmov    @r1+,xd8
        fmov    @r1+,xd10
        mov     r4,r11
        mov     r8,r12
6:      add     #16,r11
        mov.l   @r11+,r13
        add     #4,r11
        add     r7,r13
        add     #48,r13
        fmov    xd10,@-r13
        fmov    xd8,@-r13
        fmov    xd6,@-r13
        fmov    xd4,@-r13
        fmov    xd2,@-r13
        dt      r12
        bf/s    6b
        fmov    xd0,@-r13
.Lg_next:
        mov     r8,r13                  /* past the entries: n x 24 bytes */
        shll    r13
        add     r8,r13
        shll2   r13
        shll    r13
        dt      r5
        bf/s    .Lg_group
        add     r13,r4
        fschg                           /* SZ=0 */
        mov.l   @r15+,r14
        mov.l   @r15+,r13
        mov.l   @r15+,r12
        mov.l   @r15+,r11
        mov.l   @r15+,r10
        mov.l   @r15+,r9
        mov.l   @r15+,r8
.Lg_ret:
        rts
        nop
        .size   _re4dc_coarse_skin_groups, .-_re4dc_coarse_skin_groups
