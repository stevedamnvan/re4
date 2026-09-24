/* sincos_exhaustive.c: GAME_SINCOS re4dc_sincosf (port/dreamcast/game/game30_trig.c) against the game's
 * recovered fdlibm sinf/cosf (src/lib/fdlibm) for every one of the 2^32 float inputs, bit for bit.
 * Host float math (SSE, -ffp-contract=off) with MXCSR FTZ+DAZ, the SH-4 FPSCR.DN=1 behaviour.
 * Build/run: tools/game30/sincos_exhaustive.sh <tree>. Exit 0 = identical everywhere.
 * Negative control: SINCOS_NEG=1 flips the low bit of cos for one input and must report 1 mismatch. */
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <xmmintrin.h>

float ref_sinf(float), ref_cosf(float);
void re4dc_sincosf(float, float*, float*);

#define NT 16
static uint64_t mism[NT], first_bad[NT], checked[NT];
static int neg;

static inline uint32_t bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

static void* run(void* arg)
{
    const int t = (int) (intptr_t) arg;
    _mm_setcsr(_mm_getcsr() | 0x8040);   /* FTZ | DAZ */
    first_bad[t] = ~0ull;
    const uint64_t span = (1ull << 32) / NT;
    for (uint64_t k = t * span; k < (t + 1) * span; k++) {
        const uint32_t u = (uint32_t) k;
        float x, s, c; memcpy(&x, &u, 4);
        re4dc_sincosf(x, &s, &c);
        uint32_t cb = bits(c);
        if (neg && u == 0x3f800000u) cb ^= 1;
        if (bits(ref_sinf(x)) != bits(s) || bits(ref_cosf(x)) != cb) { if (!mism[t]) first_bad[t] = k; mism[t]++; }
        checked[t]++;
    }
    return 0;
}

int main(void)
{
    neg = getenv("SINCOS_NEG") != 0;
    pthread_t th[NT];
    for (int t = 0; t < NT; t++) pthread_create(&th[t], 0, run, (void*) (intptr_t) t);
    uint64_t n = 0, bad = 0, fb = ~0ull;
    for (int t = 0; t < NT; t++) { pthread_join(th[t], 0); n += checked[t]; bad += mism[t]; if (first_bad[t] < fb) fb = first_bad[t]; }
    printf("inputs %llu, sincosf vs sinf/cosf mismatches %llu%s", (unsigned long long) n, (unsigned long long) bad,
           neg ? " (negative control)" : "");
    if (bad) printf(" (first at input 0x%08llx)", (unsigned long long) fb);
    printf("\n");
    float xs[] = {0.5f, 1.0f, 2.0f, 3.14159265f, -100.0f, 1e6f, 1e-30f};
    for (unsigned i = 0; i < sizeof xs / sizeof xs[0]; i++) {
        float s, c; re4dc_sincosf(xs[i], &s, &c);
        printf("  x=%-12g sin %08x/%08x cos %08x/%08x\n", xs[i], bits(ref_sinf(xs[i])), bits(s), bits(ref_cosf(xs[i])), bits(c));
    }
    return neg ? bad != 1 : bad != 0;
}
