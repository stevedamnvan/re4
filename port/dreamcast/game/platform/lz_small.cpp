// D367 VMU saves (VMU_SAVE=1): a small deterministic LZ4-block codec for the save payload.
// The encoder is greedy with a fixed 2048-entry hash table of u16 positions (4 KiB, caller
// memory), no acceleration and no backward extension, so tools/vmusave.py reproduces it byte for
// byte (port/dreamcast/tests/test_vmusave.py checks both on the same buffers). The output is a
// standard LZ4 block (any LZ4 decoder reads it). Inputs are at most 65535 bytes.
// Compiled only with VMU_SAVE=1 (vmusave.mk); empty in the default image.
#if RE4DC_VMU_SAVE
#include "lz_small.h"

#define LZS_MIN_MATCH 4u
#define LZS_MFLIMIT 12u
#define LZS_LASTLITERALS 5u

static unsigned lzs_rd32(const unsigned char* p)
{
    return (unsigned) p[0] | (unsigned) p[1] << 8 | (unsigned) p[2] << 16 | (unsigned) p[3] << 24;
}

static unsigned lzs_hash(unsigned v)
{
    return (v * 2654435761u) >> (32 - LZS_HASH_BITS);
}

// Appends a length extension; 0 when `out` would overflow.
static int lzs_ext(unsigned char** o, unsigned char* end, unsigned v)
{
    while (v >= 255) {
        if (*o >= end) return 0;
        *(*o)++ = 255;
        v -= 255;
    }
    if (*o >= end) return 0;
    *(*o)++ = (unsigned char) v;
    return 1;
}

static int lzs_literals(unsigned char** o, unsigned char* end, const unsigned char* src, unsigned n)
{
    if ((unsigned) (end - *o) < n) return 0;
    for (unsigned i = 0; i < n; ++i) (*o)[i] = src[i];
    *o += n;
    return 1;
}

int lzs_encode(const void* srcv, unsigned n, void* dstv, unsigned cap, unsigned short* table)
{
    const unsigned char* src = (const unsigned char*) srcv;
    unsigned char* o = (unsigned char*) dstv;
    unsigned char* const end = o + cap;
    unsigned anchor = 0, ip = 0;
    if (n > 0xFFFFu) return -1;
    for (unsigned i = 0; i < (1u << LZS_HASH_BITS); ++i) table[i] = 0;
    if (n >= LZS_MFLIMIT) {
        const unsigned limit = n - LZS_MFLIMIT;
        const unsigned mend = n - LZS_LASTLITERALS;
        while (ip <= limit) {
            const unsigned v = lzs_rd32(src + ip);
            const unsigned h = lzs_hash(v);
            const unsigned cand = table[h];
            table[h] = (unsigned short) ip;
            if (cand < ip && ip - cand <= 0xFFFFu && lzs_rd32(src + cand) == v) {
                unsigned ml = LZS_MIN_MATCH;
                while (ip + ml < mend && src[cand + ml] == src[ip + ml]) ++ml;
                const unsigned lit = ip - anchor, m = ml - LZS_MIN_MATCH, off = ip - cand;
                if (o >= end) return -1;
                *o++ = (unsigned char) ((lit < 15 ? lit : 15) << 4 | (m < 15 ? m : 15));
                if (lit >= 15 && !lzs_ext(&o, end, lit - 15)) return -1;
                if (!lzs_literals(&o, end, src + anchor, lit)) return -1;
                if (end - o < 2) return -1;
                *o++ = (unsigned char) off;
                *o++ = (unsigned char) (off >> 8);
                if (m >= 15 && !lzs_ext(&o, end, m - 15)) return -1;
                ip += ml;
                anchor = ip;
            } else {
                ++ip;
            }
        }
    }
    {
        const unsigned lit = n - anchor;
        if (o >= end) return -1;
        *o++ = (unsigned char) ((lit < 15 ? lit : 15) << 4);
        if (lit >= 15 && !lzs_ext(&o, end, lit - 15)) return -1;
        if (!lzs_literals(&o, end, src + anchor, lit)) return -1;
    }
    return (int) (o - (unsigned char*) dstv);
}

static int lzs_run(const void* srcv, unsigned n, void* dstv, unsigned raw_len, int verify)
{
    const unsigned char* s = (const unsigned char*) srcv;
    const unsigned char* const send = s + n;
    unsigned char* const d0 = (unsigned char*) dstv;  // verify: the expected bytes (read only)
    unsigned char* d = d0;
    unsigned char* const dend = d0 + raw_len;
    while (s < send) {
        const unsigned tok = *s++;
        unsigned lit = tok >> 4;
        if (lit == 15) {
            unsigned b;
            do {
                if (s >= send) return -1;
                b = *s++;
                lit += b;
            } while (b == 255);
        }
        if ((unsigned) (send - s) < lit || (unsigned) (dend - d) < lit) return -1;
        for (unsigned i = 0; i < lit; ++i) {
            if (verify) {
                if (d[i] != s[i]) return -1;
            } else {
                d[i] = s[i];
            }
        }
        d += lit;
        s += lit;
        if (s >= send) break;  // the last sequence has literals only
        if (send - s < 2) return -1;
        const unsigned off = (unsigned) s[0] | (unsigned) s[1] << 8;
        s += 2;
        if (off == 0 || off > (unsigned) (d - d0)) return -1;
        unsigned ml = tok & 15;
        if (ml == 15) {
            unsigned b;
            do {
                if (s >= send) return -1;
                b = *s++;
                ml += b;
            } while (b == 255);
        }
        ml += LZS_MIN_MATCH;
        if ((unsigned) (dend - d) < ml) return -1;
        const unsigned char* m = d - off;
        for (unsigned i = 0; i < ml; ++i) {
            if (verify) {
                if (d[i] != m[i]) return -1;  // m[] already verified equal to the source
            } else {
                d[i] = m[i];
            }
        }
        d += ml;
    }
    return d == dend ? (int) raw_len : -1;
}

int lzs_decode(const void* src, unsigned n, void* dst, unsigned raw_len) { return lzs_run(src, n, dst, raw_len, 0); }

// Write-verify without scratch memory: decodes `src` against `expected` (raw_len bytes) and
// returns raw_len only when every byte matches.
int lzs_verify(const void* src, unsigned n, const void* expected, unsigned raw_len)
{
    return lzs_run(src, n, const_cast<void*>(expected), raw_len, 1);
}
#endif  // RE4DC_VMU_SAVE
