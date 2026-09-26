! Light kernel iteration k: tail of vertex k-1 (colour ints in r4/r8/r9: each clamped to 255 without a
! branch, x | -(x > 255) then its low byte, packed with alpha, stored at r7); vertex k (normal floats in
! fv4, fr7 = 0): three fipr, m = d + |d|, colour ftrv, colour copied into the w slots (fr11 / fr15 / fr3,
! free once the m are built) and truncated into r4/r8/r9; PRE(k+1): its normal bytes through the s8 ->
! float table (r3 = table + 512) into fv4, palette byte in r2.
! Entry state: fv4 = normal(k), fr7 = 0; r5 = record k+1; r6 = n - k; r7 = &entry[k-1].argb.
@tail cmp/gt r12,r4
@tail subc r0,r0
@tail or r0,r4
@tail extu.b r4,r4
@tail cmp/gt r12,r8
@tail subc r1,r1
@tail or r1,r8
@tail extu.b r8,r8
@tail cmp/gt r12,r9
@tail subc r2,r2
@tail or r2,r9
@tail extu.b r9,r9
@tail shll16 r4
@tail shll8 r8
@tail or r8,r4
@tail or r9,r4
@tail or r10,r4
@tail mov.l r4,@r7
@tail add #32,r7
fipr fv4,fv8
fipr fv4,fv12
fipr fv4,fv0
fmov fr11,fr4
fabs fr4
fadd fr11,fr4
fmov fr15,fr5
fabs fr5
fadd fr15,fr5
fmov fr3,fr6
fabs fr6
fadd fr3,fr6
fldi1 fr7
ftrv xmtrx,fv4
fmov fr4,fr11
fmov fr5,fr15
fmov fr6,fr3
mov.w @(2,r5),r0
add r11,r5
shll2 r0
mov r13,r1
add r0,r1
mov.b @r1+,r0
shll2 r0
fmov.s @(r0,r3),fr4
mov.b @r1+,r0
shll2 r0
fmov.s @(r0,r3),fr5
mov.b @r1+,r0
shll2 r0
fmov.s @(r0,r3),fr6
@skin mov.b @r1,r2
ftrc fr11,fpul
sts fpul,r4
ftrc fr15,fpul
sts fpul,r8
ftrc fr3,fpul
sts fpul,r9
dt r6
bt @end
@skin cmp/eq r14,r2
@skin bf @switch
