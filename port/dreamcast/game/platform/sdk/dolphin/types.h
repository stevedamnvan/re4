/* Shim for <dolphin/types.h>: the SDK's own header includes the CodeWarrior
 * libc. Same typedefs as the game's include/types.h (s32/u32 are long, as the
 * SDK and the game agree), no libc. */
#ifndef _DOLPHIN_TYPES_H_
#define _DOLPHIN_TYPES_H_

typedef signed char s8;
typedef unsigned char u8;
typedef signed short int s16;
typedef unsigned short int u16;
typedef signed long s32;
typedef unsigned long u32;
typedef signed long long int s64;
typedef unsigned long long int u64;
typedef float f32;
typedef double f64;
typedef char* Ptr;
typedef int BOOL;

#define FALSE 0
#define TRUE 1
#define ATTRIBUTE_ALIGN(num) __attribute__((aligned(num)))
#ifndef NULL
#define NULL ((void*) 0)
#endif

#endif
