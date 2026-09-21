#ifndef TYPES_H
#define TYPES_H

typedef signed char s8;
typedef signed short s16;
typedef signed long s32;
typedef signed long long s64;
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned long u32;
typedef unsigned long long u64;
typedef float f32;
typedef double f64;
typedef int BOOL;

// `register T x asm("rN")` pins reproduce the original register allocation.
// They are PowerPC register names; on any other target the pin is dropped and
// the declaration is an ordinary local.
#if defined(__PPC__) || defined(__powerpc__)
#define PPC_REG(r) asm(r)
#else
#define PPC_REG(r)
#endif

#ifndef NULL
#define NULL 0
#endif

#endif
