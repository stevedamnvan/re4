/* Shim seen by the SDK matrix/vector units compiled for the Dreamcast in place
 * of the real <dolphin.h>, which drags in the CodeWarrior libc and OS headers.
 * Only the types and the mtx interface those units need. */
#ifndef RE4DC_SDK_SHIM_DOLPHIN_H
#define RE4DC_SDK_SHIM_DOLPHIN_H

#include <dolphin/types.h>
#include <dolphin/mtx.h>

/* The SDK asserts are compiled out of the release library too. */
#define ASSERTMSGLINE(line, cond, msg) ((void) 0)
#define ASSERTMSG(cond, msg) ((void) 0)
#define ASSERT(cond) ((void) 0)
#define ASSERTMSG1(cond, msg, a) ((void) 0)
#define ASSERTMSG2(cond, msg, a, b) ((void) 0)

#endif
