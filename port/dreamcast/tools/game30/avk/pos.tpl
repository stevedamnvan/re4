! Position kernel half-body: vertex k in fvV, vertex k+1 prepared into fvN.
! Entry state: fvV = (x, y, z, 1) of k; r9/r10 = tu/tv(k); r5 = record k+1; r6 = n - k;
! r7 = entry k + 24; r8 = oc[k-1] (tail stores it); r4 = code of k-1 (tail).
@tail mov.b r4,@r8
@tail add #1,r8
ftrv xmtrx,fvV
lds r9,fpul
float fpul,N1
lds r10,fpul
float fpul,N2
fmul fr12,N1
fmul fr14,N2
fadd fr13,N1
fadd fr15,N2
fmov.s N2,@-r7
fmov.s N1,@-r7
fldi0 N3
mov.w @r5,r1
mov.w @(4,r5),r0
add r11,r5
shll2 r1
add r1,r1
add r12,r1
shll2 r0
add r13,r0
mov.w @r0+,r9
mov.w @r0,r10
@u16 extu.w r9,r9
@u16 extu.w r10,r10
@skin mov.w @(6,r1),r0
mov.w @r1+,r2
mov.w @r1+,r3
mov.w @r1,r1
fcmp/gt V2,fr10
movt r4
fcmp/gt fr11,V2
rotcl r4
dt r6
bt @end
@skin cmp/eq r14,r0
@skin bf @switch
@pf mov.w @r5,r0
@pf shll2 r0
@pf add r0,r0
@pf add r12,r0
@pf pref @r0
@pf mov.w @(4,r5),r0
@pf shll2 r0
@pf add r13,r0
@pf pref @r0
fmul V3,V3
fsrra V3
fmul V3,V0
fmul V3,V1
fmov.s V3,@-r7
fcmp/gt V0,N3
rotcl r4
fcmp/gt fr8,V0
rotcl r4
fmov.s V1,@-r7
fcmp/gt V1,N3
fldi1 N3
rotcl r4
fcmp/gt fr9,V1
rotcl r4
fmov.s V0,@-r7
add #52,r7
lds r2,fpul
float fpul,N0
lds r3,fpul
float fpul,N1
lds r1,fpul
float fpul,N2
