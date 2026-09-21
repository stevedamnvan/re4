// Force-included ahead of every recovered game unit in the Dreamcast build.
//
// The units declare the few libc functions they use themselves, in the
// spellings below, instead of including a libc header (the original tree's
// headers are CodeWarrior's). A handful of units rely on another unit's
// declaration having been seen first; this makes the same declarations
// visible everywhere. Spellings match the game's own (joy.h,
// emwindow.cpp), so a unit's later re-declaration is identical rather than
// conflicting. Only the functions some unit fails to declare are here.
#ifndef RE4DC_PRELUDE_H
#define RE4DC_PRELUDE_H

#ifdef __cplusplus
extern "C" {
#endif
void* memcpy(void* dst, const void* src, unsigned int n);

int strcmp(const char* a, const char* b);
#ifdef __cplusplus
}
#endif

#endif
