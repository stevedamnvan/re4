/* GAME_SH4_MATH=1 (game30.mk): as platform/ps_alias.ld, but the hot entry points are bound to
 * the hand-scheduled bodies in platform/mtx_sh4.S, which execute the identical FP dataflow
 * (proof: tools/fpsym2.py --strict against the C bodies in the same linked image). The C_*
 * bodies remain for the few direct C_* callers (tools, id_sys, mes) and SDK-internal calls. */
_PSMTXIdentity = _re4dc_sh4_MTXIdentity;
_PSMTXCopy = _re4dc_sh4_MTXCopy;
_PSMTXConcat = _re4dc_sh4_MTXConcat;
_PSMTXTranspose = _re4dc_sh4_MTXTranspose;
_PSMTXInverse = _re4dc_sh4_MTXInverse;
_PSMTXRotRad = _C_MTXRotRad;
_PSMTXRotTrig = _C_MTXRotTrig;
_PSMTXRotAxisRad = _C_MTXRotAxisRad;
_PSMTXTrans = _re4dc_sh4_MTXTrans;
_PSMTXTransApply = _C_MTXTransApply;
_PSMTXScale = _re4dc_sh4_MTXScale;
_PSMTXQuat = _C_MTXQuat;
_PSMTXMultVec = _re4dc_sh4_MTXMultVec;
_PSMTXMultVecArray = _C_MTXMultVecArray;
_PSMTXMultVecSR = _re4dc_sh4_MTXMultVecSR;
_PSMTX44MultVec = _C_MTX44MultVec;
_PSMTXReorder = _re4dc_sh4_MTXReorder;
_PSVECAdd = _re4dc_sh4_VECAdd;
_PSVECSubtract = _re4dc_sh4_VECSubtract;
_PSVECScale = _re4dc_sh4_VECScale;
_PSVECNormalize = _C_VECNormalize;
_PSVECSquareMag = _C_VECSquareMag;
_PSVECMag = _C_VECMag;
_PSVECDotProduct = _re4dc_sh4_VECDotProduct;
_PSVECCrossProduct = _re4dc_sh4_VECCrossProduct;
_PSVECSquareDistance = _C_VECSquareDistance;
_PSVECDistance = _C_VECDistance;
