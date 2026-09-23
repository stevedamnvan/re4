/* trig_exhaustive.c: GAME_TRIG=1 sinf/cosf (port/dreamcast/game/game30_trig.c) against the game's
 * recovered fdlibm sinf/cosf (src/lib/fdlibm) for every one of the 2^32 float inputs, bit for bit.
 * Host float math (SSE, -ffp-contract=off) with MXCSR FTZ+DAZ, the SH-4 FPSCR.DN=1 behaviour.
 * Build/run: tools/trig_exhaustive.sh <tree>. Exit 0 = identical everywhere. */
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <xmmintrin.h>

float ref_sinf(float), ref_cosf(float), new_sinf(float), new_cosf(float);

#define NT 16
static uint64_t mism[NT], first_bad[NT];
static uint64_t checked[NT];

static inline uint32_t bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

static void* run(void* arg)
{
    const int t = (int) (intptr_t) arg;
    _mm_setcsr(_mm_getcsr() | 0x8040);   /* FTZ | DAZ */
    first_bad[t] = ~0ull;
    const uint64_t span = (1ull << 32) / NT;
    for (uint64_t k = t * span; k < (t + 1) * span; k++) {
        const uint32_t u = (uint32_t) k;
        float x; memcpy(&x, &u, 4);
        const uint32_t a = bits(ref_sinf(x)), b = bits(new_sinf(x));
        const uint32_t c = bits(ref_cosf(x)), d = bits(new_cosf(x));
        if (a != b || c != d) { if (!mism[t]) first_bad[t] = k; mism[t]++; }
        checked[t]++;
    }
    return 0;
}

int main(void)
{
    pthread_t th[NT];
    for (int t = 0; t < NT; t++) pthread_create(&th[t], 0, run, (void*) (intptr_t) t);
    uint64_t n = 0, bad = 0, fb = ~0ull;
    for (int t = 0; t < NT; t++) { pthread_join(th[t], 0); n += checked[t]; bad += mism[t]; if (first_bad[t] < fb) fb = first_bad[t]; }
    printf("inputs %llu, sinf+cosf mismatches %llu", (unsigned long long) n, (unsigned long long) bad);
    if (bad) printf(" (first at input 0x%08llx)", (unsigned long long) fb);
    printf("\n");
    /* spot values so the run is visibly non-trivial */
    float xs[] = {0.5f, 1.0f, 2.0f, 3.14159265f, -100.0f, 1e6f, 1e-30f};
    for (unsigned i = 0; i < sizeof xs / sizeof xs[0]; i++)
        printf("  x=%-12g sin %08x/%08x cos %08x/%08x\n", xs[i], bits(ref_sinf(xs[i])), bits(new_sinf(xs[i])),
               bits(ref_cosf(xs[i])), bits(new_cosf(xs[i])));
    return bad != 0;
}
