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

// `inline` members whose out-of-line copy the original compiler emitted for other
// units (GCC 2.95 -fkeep-inline-functions behaviour): ordinary definitions elsewhere.
#if defined(__PPC__) || defined(__powerpc__)
#define RE4_INLINE inline
#else
#define RE4_INLINE
#endif

// HALT(): the original stores to 0x11111111 to stop the game. On the SH-4 that address is in
// area 4 (TA FIFO): Flycast takes the misaligned store as a TA/YUV input word and the game runs
// on, and real hardware raises an address error. The port stops explicitly instead
// (platform/fault.cpp re4dc_halt: file:line to the log, then a deterministic stop).
#if defined(__PPC__)
#define RE4DC_HALT_STORE() (*(volatile u32*) 0x11111111 = 0)
#else
#ifdef __cplusplus
extern "C"
#endif
void re4dc_halt(const char* file, int line);
#define RE4DC_HALT_STORE() re4dc_halt(__FILE__, __LINE__)
#endif

#ifndef NULL
#define NULL 0
#endif

#endif
