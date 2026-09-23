/* GAME_PS_ALIAS=1 (game30.mk): bind the paired-single SDK entry points straight to the SDK's C
 * reference bodies. platform/mtx.cpp defines each PS* as a one-line forwarder to C_*; at -O1
 * every forwarder is a full call frame (sts.l pr / literal / jsr / lds.l pr / rts: 7-9
 * instructions) on top of the real call. With these assignments (and the forwarders compiled
 * out, RE4DC_PS_ALIAS) every PS* call lands on the C_* body directly: the executed arithmetic
 * is the same machine code, so results are bit-identical by construction.
 * Passed to the final link as an input script (link.sh), after the objects. */
_PSMTXIdentity = _C_MTXIdentity;
_PSMTXCopy = _C_MTXCopy;
_PSMTXConcat = _C_MTXConcat;
_PSMTXTranspose = _C_MTXTranspose;
_PSMTXInverse = _C_MTXInverse;
_PSMTXRotRad = _C_MTXRotRad;
_PSMTXRotTrig = _C_MTXRotTrig;
_PSMTXRotAxisRad = _C_MTXRotAxisRad;
_PSMTXTrans = _C_MTXTrans;
_PSMTXTransApply = _C_MTXTransApply;
_PSMTXScale = _C_MTXScale;
_PSMTXQuat = _C_MTXQuat;
_PSMTXMultVec = _C_MTXMultVec;
_PSMTXMultVecArray = _C_MTXMultVecArray;
_PSMTXMultVecSR = _C_MTXMultVecSR;
_PSMTX44MultVec = _C_MTX44MultVec;
_PSVECAdd = _C_VECAdd;
_PSVECSubtract = _C_VECSubtract;
_PSVECScale = _C_VECScale;
_PSVECNormalize = _C_VECNormalize;
_PSVECSquareMag = _C_VECSquareMag;
_PSVECMag = _C_VECMag;
_PSVECDotProduct = _C_VECDotProduct;
_PSVECCrossProduct = _C_VECCrossProduct;
_PSVECSquareDistance = _C_VECSquareDistance;
_PSVECDistance = _C_VECDistance;
