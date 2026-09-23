/* mode1raw: 2048-byte ISO sectors -> 2352-byte raw MODE1 sectors (sync, header,
 * EDC, ECC P/Q), the Redump/TOSEC "track03.bin" form that every GDEMU firmware
 * and emulator accepts. D367 W10, used by tools/d367/mkgdi.sh when SECTOR=2352.
 *
 *   mode1raw <in.iso> <out.bin> <first-lba>
 *
 * The header address is the absolute FAD (first-lba + 150 + n) in BCD MSF.
 * GD-ROM FADs above 99:59:74 (beyond ~882 MB into the high-density area) keep
 * a hexadecimal minute byte (e.g. 100 -> 0xA0); drives and ODEs return only the
 * 2048 user bytes, so the header is informational.
 * The EDC is CRC-32 (polynomial 0xD8018001, reflected) over bytes 0..2063, and
 * P/Q parity is the ECMA-130 Reed-Solomon product code over bytes 12..2075.
 * Written from the ECMA-130 description; no external code. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t ecc_f[256], ecc_b[256];
static uint32_t edc_lut[256];

static void init_tables(void)
{
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t j = (i << 1) ^ ((i & 0x80) ? 0x11D : 0);
        ecc_f[i] = (uint8_t) j;
        ecc_b[i ^ j] = (uint8_t) i;
        uint32_t e = i;
        for (int k = 0; k < 8; k++) e = (e >> 1) ^ ((e & 1) ? 0xD8018001u : 0);
        edc_lut[i] = e;
    }
}

static void ecc_block(const uint8_t* src, uint32_t major_count, uint32_t minor_count,
                      uint32_t major_mult, uint32_t minor_inc, uint8_t* dest)
{
    const uint32_t size = major_count * minor_count;
    for (uint32_t major = 0; major < major_count; major++) {
        uint32_t index = (major >> 1) * major_mult + (major & 1);
        uint8_t a = 0, b = 0;
        for (uint32_t minor = 0; minor < minor_count; minor++) {
            const uint8_t t = src[index];
            index += minor_inc;
            if (index >= size) index -= size;
            a ^= t; b ^= t;
            a = ecc_f[a];
        }
        a = ecc_b[ecc_f[a] ^ b];
        dest[major] = a;
        dest[major + major_count] = a ^ b;
    }
}

static uint8_t bcd(uint32_t v) { return (uint8_t) (v < 100 ? ((v / 10) << 4) | (v % 10) : 0xA0 + (v - 100)); }

static void encode(uint8_t* s, uint32_t fad)
{
    s[0] = 0; memset(s + 1, 0xFF, 10); s[11] = 0;
    s[12] = bcd(fad / 4500); s[13] = bcd((fad / 75) % 60); s[14] = bcd(fad % 75); s[15] = 1;
    uint32_t edc = 0;
    for (int i = 0; i < 2064; i++) edc = (edc >> 8) ^ edc_lut[(edc ^ s[i]) & 0xFF];
    s[2064] = (uint8_t) edc; s[2065] = (uint8_t) (edc >> 8);
    s[2066] = (uint8_t) (edc >> 16); s[2067] = (uint8_t) (edc >> 24);
    memset(s + 2068, 0, 8);
    ecc_block(s + 12, 86, 24, 2, 86, s + 2076);   /* P parity */
    ecc_block(s + 12, 52, 43, 86, 88, s + 2248);  /* Q parity */
}

int main(int argc, char** argv)
{
    if (argc != 4) { fprintf(stderr, "usage: mode1raw <in.iso> <out.bin> <first-lba>\n"); return 2; }
    FILE* in = fopen(argv[1], "rb");
    FILE* out = fopen(argv[2], "wb");
    if (!in || !out) { perror("mode1raw"); return 1; }
    const uint32_t lba = (uint32_t) strtoul(argv[3], NULL, 0);
    init_tables();
    static uint8_t s[2352];
    uint32_t n = 0;
    size_t got;
    while ((got = fread(s + 16, 1, 2048, in)) > 0) {
        if (got < 2048) memset(s + 16 + got, 0, 2048 - got);
        encode(s, lba + 150 + n);
        if (fwrite(s, 1, 2352, out) != 2352) { perror("mode1raw: write"); return 1; }
        n++;
    }
    if (ferror(in) || fclose(out)) { perror("mode1raw"); return 1; }
    fclose(in);
    fprintf(stderr, "mode1raw: %u sectors from LBA %u\n", n, lba);
    return 0;
}
