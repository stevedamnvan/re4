// game/lightInfo: per-model lighting info (D:/Bio4/Prog/lightInfo.cpp). cLightInfo (embedded in
// cModel) holds the model's light bounding volume (Offset/Size relative to a parts, Flag = shape
// type), the light enable/select masks and the up to 8 lights cLightMgr picked for it.
#include "model.h"
#include "db_log.h"
#include "math_sub.h"

// pointer to game memory (0x80000000 .. 0x82FFFFFF)
#define VALID_PTR(p) ((u32) (p) >= 0x80000000 && (u32) (p) <= 0x82FFFFFF)

// Empty info: no lights, no masks, zero volume.
cLightInfo::cLightInfo()
{
    int i;

    for (i = 0; i < 8; i++) {
        pLight[i] = 0;
    }
    EnableMask = 0;
    Flag = 0;
    PartsNo = 0;
    x53 = 0;
    SelectMask = 0;
    Offset.x = Offset.y = Offset.z = 0.0f;
    Size.x = Size.y = Size.z = 0.0f;
}

// Sets the lighting volume: type (Flag & 3: 0 capsule-like Size.x+Size.y, 1 sphere Size.x, else box
// diagonal) attached to parts partsNo (0 = the model origin), centre offset, size and the light
// kind enable mask. Returns 0 on invalid pointers.
int cLightInfo::init2(int type, int partsNo, const Vec* pOffset, const Vec* pSize, int mask)
{
    int i;

    if (!VALID_PTR(pOffset) || !VALID_PTR(pSize)) {
        pLog->err(0, 0, "cLightInfo::init2() PTR ERROR %08X %08X", pOffset, pSize);
        return 0;
    }
    for (i = 0; i < 8; i++) {
        pLight[i] = 0;
    }
    Flag = type;
    EnableMask = mask;
    PartsNo = partsNo;
    SelectMask = 0xFFFFFFFF;
    Offset = *pOffset;
    Size = *pSize;
    if ((Flag & 3) == 0) {
        Radius = Size.x + Size.y;
    } else if ((Flag & 3) != 2) {
        Radius = Size.x;
    } else {
        Radius = SQRTF(Size.x * Size.x + Size.y * Size.y + Size.z * Size.z);
    }
    return 1;
}

// Number of lights currently assigned to the model.
u32 cLightInfo::getLightNum()
{
    u8 n = 0;
    u8 i;

    for (i = 0; i < 8; i++) {
        if (pLight[i] != 0) {
            n++;
        }
    }
    return n;
}

// Rebuilds imat, the inverse of the volume's world matrix (offset scaled and rotated by the model,
// at the model position or the parts' world position), for the lighting tests.
#if defined(RE4DC_LIGHT_LAZY) && RE4DC_LIGHT_LAZY
// GAME_LIGHT_LAZY (game30.mk; lane gskel, deferral 1): imat's only reader is lightHitCheckBBox
// (light.cpp, from cLightMgr::setModel2: drawing only -- ModelTrans, the examine view, the sub screen),
// and imat is a pure function of this call's inputs. So updateMatrix keeps the inputs in imat itself --
// row 0 = Offset * scale (the same three products), row 1 = the model's ang, row 2 = the model position
// or the parts' world position (each word copied) -- and marks x53 (otherwise written only by the
// constructor); the reader calls re4dc_light_materialize, which runs the original RotVector /
// PSVECAdd / RotMatrix / TransMatrix / PSMTXInverse on those words (all pure functions). The early
// return (a parts model without parts) leaves imat and the mark as they were, as the original leaves
// imat. RotMatrix of a rotation cannot give det 0, so PSMTXInverse always writes imat.
// =2 (check build): the original also runs at every call into a side table and every
// materialization is compared with it word for word ("LLZ" log line).
extern "C" void re4dc_log(const char* fmt, ...);
namespace {
#if RE4DC_LIGHT_LAZY == 2
struct LlzShadow {
    const cLightInfo* key;
    u32 w[12];
};
LlzShadow llzShadow[256];
u32 llzUpd, llzMat, llzChk, llzMis, llzGone, llzSing;
inline LlzShadow* llzSlot(const cLightInfo* li)
{
    return &llzShadow[((u32) li >> 4) & 255];
}
#endif
}   // namespace
extern "C" void re4dc_light_materialize(cLightInfo* li)
{
    Vec v;
    Vec ang;
    Vec base;
    Mtx tmp;

    v.x = li->imat[0][0];
    v.y = li->imat[0][1];
    v.z = li->imat[0][2];
    ang.x = li->imat[1][0];
    ang.y = li->imat[1][1];
    ang.z = li->imat[1][2];
    base.x = li->imat[2][0];
    base.y = li->imat[2][1];
    base.z = li->imat[2][2];
    li->x53 = 0;
    RotVector(&v, &ang, &v);
    PSVECAdd(&v, &base, &v);
    RotMatrix(tmp, &ang);
    TransMatrix(tmp, &v);
    PSMTXInverse(tmp, li->imat);
#if RE4DC_LIGHT_LAZY == 2
    LlzShadow* s = llzSlot(li);
    llzMat++;
    if (s->key == li) {
        u32 a[12];
        __builtin_memcpy(a, li->imat, sizeof(a));
        u32 bad = 0;
        for (int i = 0; i < 12; i++) {
            bad += a[i] != s->w[i];
        }
        llzChk++;
        llzMis += bad != 0;
    } else {
        llzGone++;
    }
    if ((llzMat & 0xFF) == 0) {
        re4dc_log("LLZ upd=%u mat=%u checked=%u mismatch=%u evicted=%u singular=%u\n", llzUpd, llzMat, llzChk, llzMis,
                  llzGone, llzSing);
    }
#endif
}
void cLightInfo::updateMatrix(cModel* m)
{
    Vec v;
    const Vec* base;

    v.x = Offset.x * m->scale.x;
    v.y = Offset.y * m->scale.y;
    v.z = Offset.z * m->scale.z;
    if (PartsNo == 0) {
        base = &m->pos;
    } else {
        if (m->pParts == 0) {
            return;
        }
        base = &m->getPartsPtr(PartsNo - 1)->world;
    }
#if RE4DC_LIGHT_LAZY == 2
    {
        Vec e = v;
        Mtx tmp;
        Mtx inv;
        LlzShadow* s = llzSlot(this);
        RotVector(&e, &m->ang, &e);
        PSVECAdd(&e, base, &e);
        RotMatrix(tmp, &m->ang);
        TransMatrix(tmp, &e);
        if (PSMTXInverse(tmp, inv)) {
            s->key = this;
            __builtin_memcpy(s->w, inv, sizeof(s->w));
        } else {
            s->key = 0;
            llzSing++;
        }
        llzUpd++;
        if ((llzUpd & 0x7FF) == 0) {
            re4dc_log("LLZ upd=%u mat=%u checked=%u mismatch=%u evicted=%u singular=%u\n", llzUpd, llzMat, llzChk,
                      llzMis, llzGone, llzSing);
        }
    }
#endif
    imat[0][0] = v.x;
    imat[0][1] = v.y;
    imat[0][2] = v.z;
    imat[1][0] = m->ang.x;
    imat[1][1] = m->ang.y;
    imat[1][2] = m->ang.z;
    imat[2][0] = base->x;
    imat[2][1] = base->y;
    imat[2][2] = base->z;
    x53 = 1;
}
#else
void cLightInfo::updateMatrix(cModel* m)
{
    Vec v;
    Mtx tmp;

    v.x = Offset.x * m->scale.x;
    v.y = Offset.y * m->scale.y;
    v.z = Offset.z * m->scale.z;
    RotVector(&v, &m->ang, &v);
    if (PartsNo == 0) {
        PSVECAdd(&v, &m->pos, &v);
    } else {
        if (m->pParts == 0) {
            return;
        }
        PSVECAdd(&v, &m->getPartsPtr(PartsNo - 1)->world, &v);
    }
    RotMatrix(tmp, &m->ang);
    TransMatrix(tmp, &v);
    PSMTXInverse(tmp, imat);
}
#endif

// World-space offset of the volume centre (rotated by the parts' matrix); returns the parts used.
cModel* cLightInfo::getPos(cModel* m, Vec* out)
{
    cModel* c;

    if (PartsNo > 0) {
        c = m->getPartsPtr(PartsNo - 1);
        if (!VALID_PTR(c)) {
            pLog->err(0, 0, "litHitCk PNo%d %d %d %x %x", PartsNo - 1, m->kindid, m->id, Flag, EnableMask);
            c = m;
        }
        PSMTXMultVecSR(c->mat, &Offset, out);
        PSVECAdd(out, &c->world, out);
    } else {
        c = m;
        PSMTXMultVecSR(c->mat, &Offset, out);
        PSVECAdd(out, &c->pos, out);
    }
    return c;
}
